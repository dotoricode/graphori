"""Journal-authoritative execution of committed Graphori run plans.

The adapter is deliberately outside the source-of-truth boundary. Runtime
results are normalized into canonical events, atomically journaled, and then
replayed through :class:`StateReducer` before the scheduler sees them.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .compiler import StateTransitionError
from .journal import (
    JournalWriter, RunPaths, ensure_run_dirs, read_journal_lines, replay_journal,
    submit_event,
)
from .models import NodeKind, NodeState
from .ports import (
    AdapterCapabilities, AdapterError, ContextBundle, DispatchHandle, ExecutionAdapter,
    ExecutionResult, RuntimeEvent, RuntimeRunHandle, SessionHandle,
)
from .reducer import StateReducer
from .projection import (
    RunProjection, build_canonical_projection, effective_plan, fresh_reducer,
)
from .model_routing import ApprovalClass, PremiumApprovalEnvelope, RouteTarget
from .run_plan import NodeSpec, RunPlan
from .run_spec import RunSpec
from .scheduler import Scheduler, SchedulerPolicy, SchedulingBatch, SchedulingState


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    plan_digest: str
    runtime: RuntimeRunHandle


@dataclass(frozen=True)
class EngineDecisionBatch:
    scheduling: SchedulingBatch
    events: tuple[RuntimeEvent, ...] = ()


@dataclass
class _EngineRun:
    spec: RunSpec
    plan: RunPlan
    runtime: RuntimeRunHandle
    scheduler: Scheduler
    paths: RunPaths
    writer: JournalWriter
    capabilities: AdapterCapabilities
    dispatches: dict[str, DispatchHandle] = field(default_factory=dict)
    sessions: dict[str, SessionHandle] = field(default_factory=dict)
    execution_tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    cancel_reason: str = ""


class GraphExecutionEngine:
    """Execute one scheduler wave at a time from a replayed projection."""

    def __init__(self, *, adapter: ExecutionAdapter,
                 plan_factory: Callable[[RunSpec], RunPlan],
                 scheduler: Scheduler | None = None):
        self._adapter = adapter
        self._plan_factory = plan_factory
        self._scheduler = scheduler
        self._runs: dict[str, _EngineRun] = {}

    @staticmethod
    def _task_id(plan: RunPlan) -> str:
        return f"task:{plan.run_id}"

    @staticmethod
    def _node_kind(node: NodeSpec) -> NodeKind:
        try:
            return NodeKind(node.kind)
        except ValueError:
            return NodeKind.WORKER

    def _fresh_reducer(self, plan: RunPlan) -> StateReducer:
        return fresh_reducer(plan)

    def _replay(self, run: _EngineRun) -> tuple[StateReducer, list[dict[str, Any]], str]:
        events, journal_digest = replay_journal(run.paths)
        reducer = self._fresh_reducer(run.plan)
        for event in events:
            reducer.apply(event)
        return reducer, events, journal_digest

    def _effective_plan(self, run: _EngineRun,
                        events: list[dict[str, Any]] | None = None) -> RunPlan:
        if events is None:
            events, _tail = read_journal_lines(run.paths.journal_file)
        return effective_plan(run.plan, events)

    def _preflight(self, run: _EngineRun, envelope: Mapping[str, Any]) -> None:
        reducer, _events, _digest = self._replay(run)
        candidate = dict(envelope)
        candidate.update({
            "seq": run.writer.next_seq,
            "recorded_at": envelope["occurred_at"],
            "prev_digest": run.writer.last_digest,
            "digest": "sha256:" + "f" * 64,
        })
        reducer.apply(candidate)

    def _append(self, run: _EngineRun, *, event_type: str, node_id: str | None,
                actor_role: str, payload: Mapping[str, Any] | None = None,
                attempt_id: str | None = None, event_id: str,
                producer_event_id: str | None = None,
                actor_role_id: str | None = None,
                occurred_at: str | None = None) -> str:
        entity: dict[str, Any] = {"task_id": self._task_id(run.plan)}
        if node_id is not None:
            entity["node_id"] = node_id
        if attempt_id is not None:
            entity["attempt_id"] = attempt_id
        role_id = actor_role_id or (
            f"role_{actor_role}_{node_id}" if node_id else f"role_{actor_role}"
        )
        envelope = {
            "schema_version": 1,
            "event_id": event_id,
            "producer_event_id": producer_event_id or event_id,
            "run_id": run.plan.run_id,
            "graph_version": run.plan.plan_version,
            "occurred_at": occurred_at or _now(),
            "actor": {"role": actor_role, "role_id": role_id},
            "type": event_type,
            "entity": entity,
            "payload": dict(payload or {}),
        }

        # Let the writer classify an already-seen identity before semantic
        # preflight. Exact redelivery is a no-op; conflicting content is
        # quarantined and reported fail-closed.
        existing, _tail = read_journal_lines(run.paths.journal_file)
        for accepted in existing:
            if (accepted["event_id"] == event_id
                    or accepted["producer_event_id"] == envelope["producer_event_id"]):
                ready = submit_event(run.paths, envelope, local_seq=run.writer.next_seq)
                outcome = run.writer.consume_one(ready)
                if outcome == "duplicate":
                    return outcome
                if outcome == "conflict":
                    raise StateTransitionError(f"idempotency conflict: {event_id}")
                raise StateTransitionError(
                    f"known identity produced unexpected journal outcome: {outcome}"
                )

        self._preflight(run, envelope)
        ready = submit_event(run.paths, envelope, local_seq=run.writer.next_seq)
        outcome = run.writer.consume_one(ready)
        if outcome == "conflict":
            raise StateTransitionError(f"idempotency conflict: {event_id}")
        if outcome not in {"accepted", "duplicate"}:
            raise StateTransitionError(f"journal rejected {event_type}: {outcome}")
        return outcome

    def _runtime_events(self, events: list[dict[str, Any]]) -> tuple[RuntimeEvent, ...]:
        return tuple(RuntimeEvent(
            event["type"], str(event["entity"].get("node_id", "")),
            event["actor"]["role"], event["payload"],
            event_id=event["event_id"],
            producer_event_id=event["producer_event_id"],
            actor_role_id=event["actor"]["role_id"],
            occurred_at=event["occurred_at"],
        ) for event in events)

    def _projection(self, run: _EngineRun) -> RunProjection:
        reducer, events, journal_digest = self._replay(run)
        node_states = {
            node_id: node.state.value for node_id, node in reducer.run.graph.nodes.items()
        }
        effective_plan = self._effective_plan(run, events)
        scheduling = run.scheduler.decide(
            effective_plan, SchedulingState(
                node_states=node_states,
                approved_nodes=frozenset(reducer.approved_nodes),
            ),
        ) if reducer.run.terminal_status is None else SchedulingBatch()
        return build_canonical_projection(
            spec=run.spec, published_plan=run.plan, plan=effective_plan,
            reducer=reducer, events=events, journal_digest=journal_digest,
            scheduling=scheduling,
        )

    async def start(self, run_spec: RunSpec) -> RunHandle:
        capabilities = self._adapter.probe()
        if not capabilities.available:
            raise RuntimeError(
                capabilities.reason or f"adapter {self._adapter.adapter_id} unavailable"
            )
        plan = self._plan_factory(run_spec)
        if plan.status != "committed":
            raise ValueError("execution requires a committed RunPlan")
        if plan.run_id in self._runs:
            raise ValueError(f"run already exists: {plan.run_id}")

        paths = ensure_run_dirs(Path(run_spec.workspace), plan.run_id)
        writer = JournalWriter(paths)
        try:
            base_policy = (
                self._scheduler.policy if self._scheduler is not None else SchedulerPolicy()
            )
            max_wip = min(
                base_policy.max_wip, run_spec.constraints.max_parallelism,
                max(1, capabilities.max_concurrency or 1),
            )
            scheduler = Scheduler(replace(base_policy, max_wip=max_wip))
            existing, _tail = read_journal_lines(paths.journal_file)
            if existing:
                created_digest = existing[0].get("payload", {}).get("plan_digest")
                if created_digest and created_digest != plan.digest():
                    raise StateTransitionError("journal plan digest does not match RunPlan")
            terminal_replay = bool(existing and existing[-1]["type"] == "run_terminal")
            runtime = (
                RuntimeRunHandle(self._adapter.adapter_id, f"replay:{plan.run_id}")
                if terminal_replay else await self._adapter.prepare_run(plan)
            )
            engine_run = _EngineRun(
                spec=run_spec, plan=plan, runtime=runtime, scheduler=scheduler,
                paths=paths, writer=writer, capabilities=capabilities,
            )
        except BaseException:
            writer.close()
            raise
        self._runs[plan.run_id] = engine_run

        if not existing:
            health_snapshot = getattr(self._adapter, "route_health_snapshot", None)
            route_health = (
                tuple(health_snapshot(plan)) if callable(health_snapshot) else ({
                    "route": capabilities.adapter_id,
                    "provider": capabilities.adapter_id,
                    "health": "ready" if capabilities.available else "unavailable",
                    "reason": capabilities.reason,
                    "selected": True,
                    "max_concurrency": capabilities.max_concurrency,
                },)
            )
            self._append(
                engine_run, event_type="run_created", node_id=None,
                actor_role="router", payload={
                    "plan_digest": plan.digest(),
                    "run_spec": run_spec.to_dict(),
                    "runtime_adapter": runtime.adapter_id,
                    "runtime_id": runtime.value,
                },
                event_id=f"engine:{plan.run_id}:run-created",
            )
            self._append(
                engine_run, event_type="graph_published", node_id=None,
                actor_role="router", payload={
                    "plan_digest": plan.digest(),
                    "plan": plan.to_dict(),
                    "scheduler_policy": asdict(scheduler.policy),
                    "route_health": list(route_health),
                    "skill_bindings": {
                        node.node_id: [binding.to_dict() for binding in node.skill_bindings]
                        for node in plan.nodes if node.skill_bindings
                    },
                },
                event_id=f"engine:{plan.run_id}:graph-published",
            )
            for node in plan.nodes:
                if not node.approval_required:
                    continue
                self._create_premium_gate(engine_run, node)
        else:
            self._reconcile_inflight(engine_run)
        if terminal_replay:
            writer.close()
        return RunHandle(plan.run_id, plan.digest(), runtime)

    def _run(self, run_id: str) -> _EngineRun:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise KeyError(f"unknown run: {run_id}") from exc

    def close(self, run_id: str | None = None) -> None:
        """Release canonical journal ownership for one Run or every owned Run.

        Call this before replacing an engine in the same process.  A process
        crash does not need this method because the OS releases its flock.
        """
        runs = (self._run(run_id),) if run_id is not None else tuple(self._runs.values())
        for run in runs:
            run.writer.close()

    def _reconcile_inflight(self, run: _EngineRun) -> None:
        reducer, _events, _digest = self._replay(run)
        for attempt_id, attempt in sorted(reducer.attempts.items()):
            if attempt.state.value not in {"dispatched", "running"}:
                continue
            node_id = reducer.attempt_nodes[attempt_id]
            self._append(
                run, event_type="reconciled", node_id=node_id,
                actor_role="router", attempt_id=attempt_id,
                payload={"outcome": "outcome_unknown", "reason": "engine_restart"},
                event_id=f"engine:{run.plan.run_id}:{attempt_id}:reconciled",
            )

    def _create_premium_gate(self, run: _EngineRun, node: NodeSpec) -> None:
        envelope = PremiumApprovalEnvelope.for_node(
            run.plan.run_id, run.plan.plan_version, node,
        )
        gate_id = f"gate:premium:{node.node_id}:{node.routing_decision_digest[-12:]}"
        self._append(
            run, event_type="gate_created", node_id=node.node_id,
            actor_role="router",
            payload={
                "gate_id": gate_id,
                "kind": "premium_model",
                "reason": "premium model approval required",
                "requested_model": node.model,
                "requested_effort": node.effort,
                "model_family": node.model_family,
                "provider_family": node.provider_family,
                "fallback_model": node.fallback_model,
                "fallback_effort": node.fallback_effort,
                "approval_envelope": envelope.to_dict(),
            },
            event_id=f"engine:{run.plan.run_id}:{gate_id}:created",
        )

    def _attempt_number(self, projection: RunProjection, node_id: str) -> int:
        return 1 + sum(
            1 for attempt_id in projection.attempt_states
            if attempt_id.startswith(f"attempt:{node_id}:")
        )

    @staticmethod
    def _result_payload(result: ExecutionResult, outcome: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "outcome": outcome,
            "runtime_id": result.runtime_id,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "cancelled": result.cancelled,
            "stdout_digest": result.stdout_digest,
            "stderr_digest": result.stderr_digest,
            "stdout_truncated": result.stdout_truncated,
            "stderr_truncated": result.stderr_truncated,
            "evidence_ids": list(result.evidence_ids),
            "summary": result.summary,
            "files_modified": list(result.files_modified),
            "reported_files_modified": list(result.reported_files_modified),
            "open_risks": list(result.open_risks),
            "runtime_metadata": dict(result.runtime_metadata),
            "metrics": {
                "adapter_start_ms": result.adapter_start_ms,
                "queue_wait_ms": result.queue_wait_ms,
                "execution_ms": result.execution_ms,
                "collect_ms": result.collect_ms,
                "total_attempt_ms": result.total_attempt_ms,
            },
        }
        if result.error_kind:
            payload["error_kind"] = result.error_kind
        if result.error_detail:
            payload["error_detail"] = result.error_detail
        return payload

    def _append_runtime_event(self, run: _EngineRun, event: RuntimeEvent,
                              *, attempt_id: str, ordinal: int,
                              dispatch: DispatchHandle | None = None) -> str:
        effective_plan = self._effective_plan(run)
        if event.node_id not in {node.node_id for node in effective_plan.nodes}:
            raise StateTransitionError(f"event references unknown node: {event.node_id}")
        payload = dict(event.payload)
        if (event.event_type in {"attempt_dispatched", "worker_finished", "reconciled"}
                or (event.event_type == "node_status_changed"
                    and payload.get("status") == "running")):
            payload.setdefault("attempt_id", attempt_id)
        node = next(item for item in effective_plan.nodes if item.node_id == event.node_id)
        if event.event_type == "verdict_recorded" and self._node_kind(node) is NodeKind.VERIFIER:
            targets = list(node.dependencies)
            payload.setdefault("target_node_ids", targets)
            current = self._projection(run)
            target_attempts: dict[str, str] = {}
            for target in targets:
                matching = [item for item in current.attempt_states
                            if item.startswith(f"attempt:{target}:")]
                if matching:
                    target_attempts[target] = sorted(matching)[-1]
            payload.setdefault("target_attempt_ids", target_attempts)
        identity = event.event_id or (
            f"adapter:{run.plan.run_id}:{dispatch.value if dispatch else event.node_id}:"
            f"{ordinal}:{event.event_type}"
        )
        outcome = self._append(
            run, event_type=event.event_type, node_id=event.node_id,
            actor_role=event.actor_role, actor_role_id=(
                event.actor_role_id
                or f"role_{event.actor_role}_{event.node_id}"
            ), payload=payload, attempt_id=attempt_id,
            event_id=identity,
            producer_event_id=event.producer_event_id or identity,
            occurred_at=(event.occurred_at or "1970-01-01T00:00:00.000000Z"
                         if event.event_id else None),
        )
        if (outcome == "accepted" and event.event_type == "verdict_recorded"
                and str(payload.get("verdict")) == "revise"
                and self._node_kind(node) is NodeKind.VERIFIER):
            targets = list(payload.get("target_node_ids", ()))
            if len(targets) == 1:
                target_id = targets[0]
                original_id = target_id.split(":rework:", 1)[0]
                current = self._projection(run)
                if current.rework_counts.get(original_id, 0) < 1:
                    revision = 1
                    rework_node_id = f"{original_id}:rework:{revision}"
                    rework_verifier_node_id = (
                        f"{event.node_id.split(':rework:', 1)[0]}:rework:{revision}"
                    )
                    self._append(
                        run, event_type="rework_created", node_id=target_id,
                        actor_role="router",
                        payload={
                            "original_node_id": original_id,
                            "rework_node_id": rework_node_id,
                            "verifier_node_id": event.node_id,
                            "rework_verifier_node_id": rework_verifier_node_id,
                        },
                        event_id=f"engine:{run.plan.run_id}:{original_id}:rework:{revision}",
                    )
                    revised_plan = self._effective_plan(run)
                    revised_nodes = {item.node_id: item for item in revised_plan.nodes}
                    for revised_id in (rework_node_id, rework_verifier_node_id):
                        revised_node = revised_nodes[revised_id]
                        if revised_node.approval_required:
                            self._create_premium_gate(run, revised_node)
                else:
                    self._append(
                        run, event_type="gate_created", node_id=target_id,
                        actor_role="router",
                        payload={
                            "gate_id": f"gate:{original_id}:rework-exhausted",
                            "reason": "automatic rework limit exhausted",
                        },
                        event_id=(
                            f"engine:{run.plan.run_id}:{original_id}:"
                            "rework-exhausted-gate"
                        ),
                    )
        return outcome

    def _context_for_node(self, run: _EngineRun, node: NodeSpec,
                          attempt_id: str) -> ContextBundle:
        context = replace(ContextBundle.from_node(node), attempt_id=attempt_id)
        if not node.dependencies:
            return context
        events, _tail = read_journal_lines(run.paths.journal_file)
        latest: dict[str, Mapping[str, Any]] = {}
        for event in events:
            if event["type"] != "worker_finished":
                continue
            dependency = event["entity"].get("node_id")
            if dependency in node.dependencies:
                latest[str(dependency)] = event["payload"]
        handoffs = []
        evidence = list(context.evidence_requirements)
        for dependency in node.dependencies:
            payload = latest.get(dependency, {})
            summary = str(payload.get("summary") or "execution completed")[:4_000]
            evidence_ids = tuple(
                str(item) for item in payload.get("evidence_ids", ())
                if isinstance(item, str)
            )
            handoffs.append(
                f"- {dependency}: {summary}"
                + (f" [evidence: {', '.join(evidence_ids)}]" if evidence_ids else "")
            )
            evidence.extend(evidence_ids)
        objective = context.objective + "\n\nDependency results from the canonical journal:\n" + "\n".join(handoffs)
        return replace(
            context, objective=objective,
            evidence_requirements=tuple(dict.fromkeys(evidence)),
        )

    async def _execute_node(self, run: _EngineRun, node: NodeSpec) -> None:
        projection = self._projection(run)
        if projection.node_states[node.node_id] == "pending":
            self._append(
                run, event_type="node_status_changed", node_id=node.node_id,
                actor_role="scheduler", payload={"status": "ready"},
                event_id=f"engine:{run.plan.run_id}:{node.node_id}:ready",
            )
        attempt_number = self._attempt_number(self._projection(run), node.node_id)
        attempt_id = f"attempt:{node.node_id}:{attempt_number}"
        previous = f"attempt:{node.node_id}:{attempt_number - 1}" if attempt_number > 1 else None
        session: SessionHandle | None = None
        dispatch: DispatchHandle | None = None
        automatic_retry_allowed = False
        try:
            session = await self._adapter.start_session(node)
            run.sessions[node.node_id] = session
            self._append(
                run, event_type="attempt_dispatched", node_id=node.node_id,
                actor_role="scheduler", attempt_id=attempt_id,
                payload={"attempt_id": attempt_id, **({"retry_of": previous} if previous else {})},
                event_id=f"engine:{run.plan.run_id}:{attempt_id}:dispatched",
            )
            dispatch = await self._adapter.dispatch(
                session, node, self._context_for_node(run, node, attempt_id),
            )
            run.dispatches[node.node_id] = dispatch
            if run.cancel_reason:
                await self._adapter.cancel(dispatch, run.cancel_reason)
            actor_role = "verifier" if self._node_kind(node) is NodeKind.VERIFIER else "worker"
            self._append(
                run, event_type="node_status_changed", node_id=node.node_id,
                actor_role=actor_role, actor_role_id=f"role_{actor_role}_{node.node_id}",
                attempt_id=attempt_id,
                payload={"status": "running", "attempt_id": attempt_id},
                event_id=f"engine:{run.plan.run_id}:{attempt_id}:running",
            )
            ordinal = 0
            saw_finished = False
            saw_verdict = False
            async for event in self._adapter.events(dispatch):
                ordinal += 1
                self._append_runtime_event(
                    run, event, attempt_id=attempt_id, ordinal=ordinal, dispatch=dispatch,
                )
                if run.capabilities.supports_delivery_ack:
                    await self._adapter.acknowledge(event)
                saw_finished = saw_finished or event.event_type == "worker_finished"
                saw_verdict = saw_verdict or event.event_type == "verdict_recorded"
            result = await self._adapter.collect(dispatch)
            routing_metadata = dict(result.runtime_metadata)
            routing_metadata.setdefault(
                "routing_decision_id",
                (f"routing:{node.node_id}:{node.routing_decision_digest[-12:]}"
                 if node.routing_decision_digest else ""),
            )
            routing_metadata.setdefault(
                "routing_decision_digest", node.routing_decision_digest,
            )
            routing_metadata.setdefault("requested_model", node.model)
            routing_metadata.setdefault("requested_effort", node.effort)
            routing_metadata.setdefault("observed_model", "")
            routing_metadata.setdefault("observed_effort", "")
            result = replace(result, runtime_metadata=routing_metadata)
            self._append(
                run, event_type="routing_observed", node_id=node.node_id,
                actor_role="router", attempt_id=attempt_id,
                payload={
                    "attempt_id": attempt_id,
                    "routing_decision_id": routing_metadata["routing_decision_id"],
                    "routing_decision_digest": routing_metadata["routing_decision_digest"],
                    "requested_model": routing_metadata["requested_model"],
                    "requested_effort": routing_metadata["requested_effort"],
                    "observed_model": routing_metadata["observed_model"],
                    "observed_effort": routing_metadata["observed_effort"],
                    "queue_ms": result.queue_wait_ms,
                    "startup_ms": result.adapter_start_ms,
                    "execution_ms": result.execution_ms,
                    "total_ms": result.total_attempt_ms,
                    "outcome": result.outcome,
                },
                event_id=f"engine:{run.plan.run_id}:{attempt_id}:routing-observed",
            )
            if result.outcome not in {
                    "succeeded", "failed", "timed_out", "timeout", "lost",
                    "outcome_unknown", "startup_failure", "cancelled",
                    "incomplete_result", "scope_violation"}:
                result_outcome = "malformed"
            else:
                result_outcome = result.outcome
            automatic_retry_allowed = result_outcome in {
                "timed_out", "timeout", "startup_failure",
            }
            if not saw_finished:
                self._append(
                    run, event_type="worker_finished", node_id=node.node_id,
                    actor_role=actor_role, actor_role_id=f"role_{actor_role}_{node.node_id}",
                    attempt_id=attempt_id,
                    payload=self._result_payload(result, result_outcome),
                    event_id=f"engine:{run.plan.run_id}:{attempt_id}:finished",
                )
            if (result_outcome == "succeeded" and node.verification_policy == "deterministic"
                    and self._node_kind(node) is not NodeKind.VERIFIER):
                self._append(
                    run, event_type="verdict_recorded", node_id=node.node_id,
                    actor_role="verifier", actor_role_id="role_deterministic_verifier",
                    payload={
                        "verdict": "pass",
                        "evidence_ids": list(result.evidence_ids) or [f"runtime:{attempt_id}"],
                        "target_node_ids": [node.node_id],
                        "target_attempt_ids": {node.node_id: attempt_id},
                    },
                    event_id=f"engine:{run.plan.run_id}:{attempt_id}:deterministic-verdict",
                )
            if (self._node_kind(node) is NodeKind.VERIFIER and result_outcome == "succeeded"
                    and not saw_verdict):
                # A verifier process ending without a verdict is execution
                # completion only, never an implicit PASS.
                pass
        except StateTransitionError:
            raise
        except AdapterError as exc:
            automatic_retry_allowed = exc.outcome in {
                "timed_out", "timeout", "startup_failure",
            }
            current = self._projection(run)
            if attempt_id in current.attempt_states and current.attempt_states[attempt_id] in {
                    "dispatched", "running"}:
                actor_role = "verifier" if self._node_kind(node) is NodeKind.VERIFIER else "worker"
                self._append(
                    run, event_type="worker_finished", node_id=node.node_id,
                    actor_role=actor_role, actor_role_id=f"role_{actor_role}_{node.node_id}",
                    attempt_id=attempt_id,
                    payload={
                        "outcome": exc.outcome,
                        "error_kind": exc.error_kind,
                        "error_detail": exc.detail,
                    },
                    event_id=f"engine:{run.plan.run_id}:{attempt_id}:adapter-error",
                )
        except Exception as exc:
            current = self._projection(run)
            if attempt_id in current.attempt_states and current.attempt_states[attempt_id] in {
                    "dispatched", "running"}:
                actor_role = "verifier" if self._node_kind(node) is NodeKind.VERIFIER else "worker"
                self._append(
                    run, event_type="worker_finished", node_id=node.node_id,
                    actor_role=actor_role, actor_role_id=f"role_{actor_role}_{node.node_id}",
                    attempt_id=attempt_id,
                    payload={"outcome": "outcome_unknown", "reason": type(exc).__name__},
                    event_id=f"engine:{run.plan.run_id}:{attempt_id}:exception",
                )
        finally:
            if session is not None:
                await self._adapter.release(session)
            run.dispatches.pop(node.node_id, None)
            run.sessions.pop(node.node_id, None)

        current = self._projection(run)
        if (current.node_states[node.node_id] == "outcome_unknown"
                and automatic_retry_allowed):
            retries = current.retry_counts.get(node.node_id, 0)
            if retries < 1:
                self._append(
                    run, event_type="retry_created", node_id=node.node_id,
                    actor_role="router", payload={"retry_of": attempt_id},
                    event_id=f"engine:{run.plan.run_id}:{node.node_id}:retry:1",
                )
                await self._execute_node(run, node)
            else:
                self._append(
                    run, event_type="node_status_changed", node_id=node.node_id,
                    actor_role="router", payload={"status": "blocked"},
                    event_id=f"engine:{run.plan.run_id}:{node.node_id}:retry-exhausted",
                )

    def _settle(self, run: _EngineRun) -> None:
        projection = self._projection(run)
        if projection.terminal_status is not None:
            return
        if projection.open_gates:
            return
        events, _tail = read_journal_lines(run.paths.journal_file)
        replaced: set[str] = set()
        for event in events:
            if event["type"] == "rework_created":
                replaced.add(event["entity"]["node_id"])
                replaced.add(event["payload"]["verifier_node_id"])
        states = tuple(
            state for node_id, state in projection.node_states.items()
            if node_id not in replaced
        )
        if states and all(state == "passed" for state in states):
            self._append(
                run, event_type="run_terminal", node_id=None, actor_role="router",
                payload={"terminal_status": "succeeded"},
                event_id=f"engine:{run.plan.run_id}:terminal:succeeded",
            )
        elif any(state == "blocked" for state in states):
            self._append(
                run, event_type="run_terminal", node_id=None, actor_role="router",
                payload={"terminal_status": "blocked", "blocking_reason": "retry exhausted"},
                event_id=f"engine:{run.plan.run_id}:terminal:blocked",
            )
        elif states and all(state in {
                "passed", "failed", "cancelled", "rejected", "inconclusive"}
                for state in states) and any(state == "failed" for state in states):
            self._append(
                run, event_type="run_terminal", node_id=None, actor_role="router",
                payload={"terminal_status": "failed"},
                event_id=f"engine:{run.plan.run_id}:terminal:failed",
            )

    async def advance(self, run_id: str,
                      events: tuple[RuntimeEvent, ...] = ()) -> EngineDecisionBatch:
        run = self._run(run_id)
        before = len(self._projection(run).events)
        if self._projection(run).terminal_status is not None:
            if events:
                raise StateTransitionError("Run is terminal; runtime events are rejected")
            return EngineDecisionBatch(SchedulingBatch())
        for ordinal, event in enumerate(events, start=1):
            attempt_id = str(event.payload.get("attempt_id", f"external:{event.node_id}"))
            self._append_runtime_event(
                run, event, attempt_id=attempt_id, ordinal=ordinal,
            )
        projection = self._projection(run)
        effective_plan = self._effective_plan(run)
        scheduling = run.scheduler.decide(
            effective_plan, SchedulingState(
                node_states=projection.node_states,
                approved_nodes=projection.approved_nodes,
            ),
        )
        nodes = {node.node_id: node for node in effective_plan.nodes}
        tasks = {
            decision.node_id: asyncio.create_task(
                self._execute_node(run, nodes[decision.node_id]),
            )
            for decision in scheduling.dispatches
        }
        run.execution_tasks.update(tasks)
        try:
            await asyncio.gather(*tasks.values())
        finally:
            for node_id, task in tasks.items():
                if run.execution_tasks.get(node_id) is task:
                    run.execution_tasks.pop(node_id, None)
        self._settle(run)
        if self._projection(run).terminal_status is not None:
            run.writer.close()
        all_events = self._projection(run).events
        return EngineDecisionBatch(scheduling, all_events[before:])

    def snapshot(self, run_id: str) -> RunProjection:
        return self._projection(self._run(run_id))

    async def resolve_premium_gate(
            self, run_id: str, gate_id: str, decision: str,
            envelope: PremiumApprovalEnvelope | None = None) -> None:
        run = self._run(run_id)
        projection = self._projection(run)
        if projection.terminal_status is not None:
            raise StateTransitionError("Run is terminal; premium approval is closed")
        existing = projection.gate_resolutions.get(gate_id)
        if existing is not None:
            if existing.get("decision") == decision:
                return
            raise StateTransitionError("premium gate already resolved differently")
        record = projection.gate_records.get(gate_id)
        if record is None or record.get("kind") != "premium_model":
            raise StateTransitionError("unknown premium gate")
        approval = record.get("approval_envelope")
        node_id = str(approval.get("node_id", "")) if isinstance(approval, Mapping) else ""
        effective_plan = self._effective_plan(run)
        node = next((item for item in effective_plan.nodes if item.node_id == node_id), None)
        if node is None:
            raise StateTransitionError("premium gate references unknown node")
        if decision == "approve":
            if envelope is None:
                raise StateTransitionError("premium approval envelope is required")
            target = RouteTarget(
                node.provider_family, node.adapter or node.provider, node.model,
                node.model_family, node.effort, ApprovalClass.PREMIUM,
            )
            if not envelope.covers(run_id, run.plan.plan_version, node, target):
                raise StateTransitionError("premium approval envelope does not cover route")
        elif decision == "use_fallback":
            if not node.fallback_model:
                raise StateTransitionError("premium route has no precomputed fallback")
            if node.fallback_approval_class != "normal":
                raise StateTransitionError("premium fallback requires its own approval")
        elif decision != "skip":
            raise StateTransitionError("unsupported premium gate decision")
        payload = {
            "gate_id": gate_id,
            "decision": decision,
            **({"approval_envelope": envelope.to_dict()} if envelope else {}),
        }
        self._append(
            run, event_type="gate_resolved", node_id=node_id,
            actor_role="human_gate", payload=payload,
            event_id=f"engine:{run_id}:{gate_id}:resolved:{decision}",
        )
        if decision == "skip":
            current = self._projection(run).node_states[node_id]
            if current == "pending":
                self._append(
                    run, event_type="node_status_changed", node_id=node_id,
                    actor_role="router", payload={"status": "ready"},
                    event_id=f"engine:{run_id}:{node_id}:skip-ready",
                )
            self._append(
                run, event_type="node_status_changed", node_id=node_id,
                actor_role="router", payload={"status": "cancelled"},
                event_id=f"engine:{run_id}:{node_id}:skipped",
            )

    async def cancel(self, run_id: str, reason: str) -> None:
        run = self._run(run_id)
        if self._projection(run).terminal_status is not None:
            return
        if (run.dispatches or run.execution_tasks) and not run.capabilities.supports_cancel:
            raise RuntimeError(
                f"adapter {run.capabilities.adapter_id} does not support cancellation"
            )
        run.cancel_reason = reason
        projection = self._projection(run)
        for gate_id, record in sorted(projection.gate_records.items()):
            if gate_id not in projection.open_gates:
                continue
            approval = record.get("approval_envelope")
            node_id = (
                str(approval.get("node_id", ""))
                if isinstance(approval, Mapping) else ""
            )
            if not node_id:
                continue
            self._append(
                run, event_type="gate_resolved", node_id=node_id,
                actor_role="router",
                payload={"gate_id": gate_id, "decision": "cancelled"},
                event_id=f"engine:{run_id}:{gate_id}:cancelled",
            )
        await asyncio.gather(*(
            self._adapter.cancel(dispatch, reason)
            for dispatch in tuple(run.dispatches.values())
        ))
        if run.execution_tasks:
            await asyncio.gather(*tuple(run.execution_tasks.values()))
        projection = self._projection(run)
        for node_id, state in sorted(projection.node_states.items()):
            if state in {"passed", "failed", "cancelled", "rejected", "inconclusive"}:
                continue
            if state == "pending":
                self._append(
                    run, event_type="node_status_changed", node_id=node_id,
                    actor_role="router", payload={"status": "ready"},
                    event_id=f"engine:{run.plan.run_id}:{node_id}:cancel-ready",
                )
            self._append(
                run, event_type="node_status_changed", node_id=node_id,
                actor_role="router", payload={"status": "cancelled"},
                event_id=f"engine:{run.plan.run_id}:{node_id}:cancelled",
            )
        self._append(
            run, event_type="run_terminal", node_id=None, actor_role="router",
            payload={"terminal_status": "cancelled", "reason": reason},
            event_id=f"engine:{run.plan.run_id}:terminal:cancelled",
        )
        run.writer.close()
