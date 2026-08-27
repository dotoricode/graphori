"""Orca as a replaceable Graphori execution infrastructure adapter."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import shlex
import time
from typing import Any, Mapping, Sequence
import uuid

from graphori_core.ports import (
    AdapterCapabilities,
    AdapterError,
    ContextBundle,
    DispatchHandle,
    ExecutionResult,
    RuntimeEvent,
    RuntimeRunHandle,
    SessionHandle,
)
from graphori_core.run_plan import NodeSpec, RunPlan
from graphori_core.orca_lifecycle import (
    OrcaLaunchStrategy, RouteCircuitBreaker, RouteHealthKey, RouteHealthStatus,
)

from .bridge import OrcaJournalBridge
from .capabilities import AdapterHealth, AdapterHealthState
from .client import OrcaClient, resolve_orca_executable
from .protocol import OrcaProtocolError, nested_id, result_object, rows


class ReconciliationStatus(str, Enum):
    MATCHED = "matched"
    STILL_RUNNING = "still_running"
    COMPLETED_CONFIRMED = "completed_confirmed"
    MISSING = "missing"
    CONFLICTING = "conflicting"
    AMBIGUOUS = "ambiguous"


class RuntimeResourceOwnership(str, Enum):
    ORCA_COMPOSED = "orca_composed"
    GRAPHORI_PRECREATED = "graphori_precreated"
    USER_SUPPLIED = "user_supplied"


@dataclass
class OrcaBinding:
    graphori_run_id: str
    orca_run_id: str
    coordinator_handle: str = ""
    nodes: dict[str, str] = field(default_factory=dict)
    attempts: dict[str, str] = field(default_factory=dict)
    pending_acks: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "graphori_run_id": self.graphori_run_id,
            "orca_run_id": self.orca_run_id,
            "coordinator_handle": self.coordinator_handle,
            "nodes": dict(sorted(self.nodes.items())),
            "attempts": dict(sorted(self.attempts.items())),
            "pending_acks": dict(sorted(self.pending_acks.items())),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OrcaBinding":
        return cls(
            graphori_run_id=str(value["graphori_run_id"]),
            orca_run_id=str(value["orca_run_id"]),
            coordinator_handle=str(value.get("coordinator_handle", "")),
            nodes=dict(value.get("nodes", {})),
            attempts=dict(value.get("attempts", {})),
            pending_acks=dict(value.get("pending_acks", {})),
        )


class OrcaBindingStore:
    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root / ".graphori" / "orca-bindings"

    def load(self, run_id: str) -> OrcaBinding | None:
        path = self.root / f"{run_id}.json"
        if not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise OrcaProtocolError("persisted Orca binding must be an object")
        return OrcaBinding.from_dict(value)

    def save(self, binding: OrcaBinding) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{binding.graphori_run_id}.json"
        temporary = path.with_suffix(f".tmp-{uuid.uuid4().hex}")
        temporary.write_text(
            json.dumps(binding.to_dict(), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, path)


@dataclass
class _Session:
    run_id: str
    node: NodeSpec
    task_id: str


@dataclass
class _Dispatch:
    session_id: str
    run_id: str
    node: NodeSpec
    context: ContextBundle
    task_id: str
    dispatch_id: str
    runtime_id: str
    terminal_handle: str = ""
    resource_ownership: RuntimeResourceOwnership = RuntimeResourceOwnership.ORCA_COMPOSED
    route_started_at: float = 0.0
    result: ExecutionResult | None = None
    delivery_id: str = ""
    acknowledged: bool = False
    timings_ms: dict[str, int] = field(default_factory=dict)


class OrcaExecutionAdapter:
    """Map Graphori scheduling decisions onto supervised Orca workers."""

    adapter_id = "orca-execution"

    def __init__(
            self, *, workspace_root: os.PathLike[str] | str,
            executable: Sequence[str] | None = None,
            process_env: Mapping[str, str] | None = None,
            delivery_timeout_ms: int = 900_000,
            client: OrcaClient | None = None,
            worktree_selector: str | None = None,
            route_circuit_breaker: RouteCircuitBreaker | None = None,
            route_health_key: RouteHealthKey | None = None,
            launch_strategy: OrcaLaunchStrategy = OrcaLaunchStrategy.ORCA_COMPOSED,
            ready_timeout_ms: int = 60_000) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.executable = resolve_orca_executable(executable)
        self.client = client or OrcaClient(
            self.executable, process_env=process_env, cwd=self.workspace_root,
        )
        self.delivery_timeout_ms = delivery_timeout_ms
        self.worktree_selector = worktree_selector
        self.route_circuit_breaker = route_circuit_breaker
        self.route_health_key = route_health_key
        self.launch_strategy = OrcaLaunchStrategy(launch_strategy)
        self.ready_timeout_ms = ready_timeout_ms
        if ready_timeout_ms < 1:
            raise ValueError("ready_timeout_ms must be positive")
        if (route_health_key is not None
                and route_health_key.launch_strategy is not self.launch_strategy):
            raise ValueError("route health key launch strategy does not match adapter")
        self.binding_store = OrcaBindingStore(self.workspace_root)
        self.bridge = OrcaJournalBridge()
        self.health = AdapterHealth()
        self.environment_evidence: dict[str, Any] = {}
        self.resource_dispositions: dict[str, str] = {}
        self.resource_ownership: dict[str, RuntimeResourceOwnership] = {}
        self._probe: AdapterCapabilities | None = None
        self._bindings: dict[str, OrcaBinding] = {}
        self._node_runs: dict[str, set[str]] = {}
        self._sessions: dict[str, _Session] = {}
        self._dispatches: dict[str, _Dispatch] = {}

    @property
    def active_handles(self) -> int:
        return len(self._dispatches)

    @staticmethod
    def _sha256(*values: str) -> str:
        digest = hashlib.sha256()
        for value in values:
            digest.update(value.encode("utf-8"))
            digest.update(b"\0")
        return "sha256:" + digest.hexdigest()

    def probe(self) -> AdapterCapabilities:
        if self._probe is not None:
            return self._probe
        version = self.client.call(("--version",))
        orchestration_guide, orchestration_response = self.client.guide("orchestration")
        cli_guide, cli_response = self.client.guide("orca-cli")
        status, status_response = self.client.status()
        required_commands = (
            "run-create", "task-create", "worker-start", "check",
            "worker-release", "worker-stop", "worker-show",
        )
        command_support = {
            command: self.client.help(command).ok for command in required_commands
        }
        terminal_command_support = {
            command: self.client.terminal_help(command).ok
            for command in ("create", "wait", "close")
        }
        available = all((
            orchestration_response.ok, cli_response.ok,
            status_response.ok, isinstance(status, Mapping),
            all(command_support.values()),
        ))
        if self.launch_strategy is OrcaLaunchStrategy.ORCA_READY_TERMINAL:
            available = available and all(terminal_command_support.values())
        runtime_id = ""
        app_version = ""
        runtime_capabilities: tuple[str, ...] = ()
        if isinstance(status, Mapping):
            try:
                result = result_object(status)
                runtime = result.get("runtime", result)
                if isinstance(runtime, Mapping):
                    runtime_id = str(runtime.get("runtimeId", ""))
                    app_version = str(runtime.get("appVersion", ""))
                    caps = runtime.get("capabilities", ())
                    if isinstance(caps, list):
                        runtime_capabilities = tuple(
                            item for item in caps if isinstance(item, str)
                        )
                if not app_version:
                    app = result.get("app")
                    app_version = (
                        str(app.get("appVersion", ""))
                        if isinstance(app, Mapping) else ""
                    )
            except OrcaProtocolError:
                available = False
                app_version = ""
        else:
            app_version = ""
        available = available and bool(app_version or (version.ok and version.stdout.strip()))
        contract = "orchestration.contract.v1" in runtime_capabilities
        available = available and contract
        guide_digest = self._sha256(orchestration_guide or "", cli_guide or "")
        self.environment_evidence = {
            "resolved_executable": self.executable[0],
            "resolved_argv": list(self.executable),
            "orca_version": app_version or version.stdout.strip(),
            "runtime_id": runtime_id,
            "orca_guide_digest": guide_digest,
            "runtime_capabilities": list(runtime_capabilities),
            "command_support": command_support,
            "terminal_command_support": terminal_command_support,
            "launch_strategy": self.launch_strategy.value,
        }
        route_blocked = False
        if self.route_circuit_breaker is not None and self.route_health_key is not None:
            observed_identity = (
                app_version or version.stdout.strip(), runtime_id, guide_digest,
            )
            requested_identity = (
                self.route_health_key.orca_version,
                self.route_health_key.runtime_id,
                self.route_health_key.guide_digest,
            )
            route_blocked = (
                observed_identity == requested_identity
                and self.route_circuit_breaker.status(self.route_health_key)
                is RouteHealthStatus.BLOCKED
            )
            self.environment_evidence["route_health_key"] = self.route_health_key.digest
            self.environment_evidence["route_circuit_status"] = (
                RouteHealthStatus.BLOCKED.value if route_blocked
                else RouteHealthStatus.RECHECK.value
            )
        available = available and not route_blocked
        for component in (
                "create_run", "create_task", "dispatch", "delivery", "release", "cancel"):
            self.health.set(
                component,
                AdapterHealthState.HEALTHY if available else AdapterHealthState.UNAVAILABLE,
            )
        self.health.set("reconcile", AdapterHealthState.DEGRADED, "experimental only")
        self._probe = AdapterCapabilities(
            adapter_id=self.adapter_id,
            available=available,
            reason=(
                "Orca route blocked by environment-scoped circuit breaker"
                if route_blocked else
                ("" if available else "Orca runtime or orchestration contract unavailable")
            ),
            max_concurrency=3,
            supports_sessions=True,
            supports_cancel=True,
            supports_reconcile=False,
            supports_heartbeat=False,
            supports_progress=False,
            supports_worktree=True,
            supports_persistent_session=False,
            supports_questions=False,
            supports_gate=False,
            supports_usage=False,
            supports_files_modified=True,
            supports_structured_result=False,
            supports_nested_agents=False,
            supports_delivery_ack=True,
        )
        return self._probe

    @staticmethod
    def _run_marker(run_id: str) -> str:
        return f"[graphori-run:{run_id}]"

    @staticmethod
    def _node_marker(run_id: str, node_id: str) -> str:
        return f"[graphori-node:{run_id}:{node_id}]"

    async def prepare_run(self, plan: RunPlan) -> RuntimeRunHandle:
        if not self.probe().available:
            raise AdapterError("startup_failure", "AdapterUnavailable", self._probe.reason)
        started_at = time.monotonic()
        binding = self.binding_store.load(plan.run_id)
        if binding is None:
            marker = self._run_marker(plan.run_id)
            listed, response = await asyncio.to_thread(self.client.run_list)
            if not response.ok:
                self.health.set("create_run", AdapterHealthState.DEGRADED, "run-list failed")
                raise AdapterError("outcome_unknown", "OrcaRunLookupFailed")
            matches = [row for row in rows(listed, "runs") if marker in str(row.get("objective", ""))]
            if len(matches) > 1:
                raise AdapterError("outcome_unknown", "AmbiguousOrcaRun")
            if matches:
                run_value = matches[0]
                orca_run_id = nested_id(run_value, ("id",), ("runId",))
            else:
                created, response = await asyncio.to_thread(
                    self.client.run_create, f"{marker} {plan.run_id}",
                )
                if not response.ok or created is None:
                    self.health.set("create_run", AdapterHealthState.DEGRADED, "create uncertain")
                    raise AdapterError("outcome_unknown", "OrcaRunCreateUncertain")
                result = result_object(created)
                orca_run_id = nested_id(result, ("run", "id"), ("runId",), ("id",))
                run_value = result.get("run", result)
            coordinator_handle = ""
            if isinstance(run_value, Mapping):
                coordinator_handle = str(
                    run_value.get(
                        "coordinator_handle",
                        run_value.get("coordinatorHandle", ""),
                    )
                )
            binding = OrcaBinding(
                plan.run_id, orca_run_id, coordinator_handle=coordinator_handle,
            )
            self.binding_store.save(binding)
        self._bindings[plan.run_id] = binding
        await self._recover_pending_acks(binding)
        for node in plan.nodes:
            self._node_runs.setdefault(node.node_id, set()).add(plan.run_id)
        self.environment_evidence["orca_run_setup_ms"] = max(
            0, round((time.monotonic() - started_at) * 1000)
        )
        return RuntimeRunHandle(self.adapter_id, binding.orca_run_id)

    async def _recover_pending_acks(self, binding: OrcaBinding) -> None:
        """Retry only ACKs known to follow a durable journal append."""

        for delivery_id in tuple(binding.pending_acks):
            for _attempt in range(2):
                _value, response = await asyncio.to_thread(
                    self.client.acknowledge, binding.orca_run_id, delivery_id,
                )
                if response.ok:
                    binding.pending_acks.pop(delivery_id, None)
                    self.binding_store.save(binding)
                    self.health.set("delivery", AdapterHealthState.HEALTHY)
                    break
            else:
                self.health.set(
                    "delivery", AdapterHealthState.DEGRADED,
                    "pending ACK recovery failed",
                )

    def _binding_for_node(self, node_id: str) -> OrcaBinding:
        run_ids = self._node_runs.get(node_id, set())
        if len(run_ids) != 1:
            raise AdapterError("startup_failure", "AmbiguousGraphoriNodeRun")
        return self._bindings[next(iter(run_ids))]

    async def start_session(self, node: NodeSpec) -> SessionHandle:
        started_at = time.monotonic()
        binding = self._binding_for_node(node.node_id)
        task_id = binding.nodes.get(node.node_id)
        if not task_id:
            marker = self._node_marker(binding.graphori_run_id, node.node_id)
            listed, response = await asyncio.to_thread(
                self.client.task_list, binding.orca_run_id,
            )
            if not response.ok:
                self.health.set("create_task", AdapterHealthState.DEGRADED, "task-list failed")
                raise AdapterError("outcome_unknown", "OrcaTaskLookupFailed")
            matches = [row for row in rows(listed, "tasks") if marker in str(row.get("spec", ""))]
            if len(matches) > 1:
                raise AdapterError("outcome_unknown", "AmbiguousOrcaTask")
            if matches:
                task_id = nested_id(matches[0], ("id",), ("taskId",))
            else:
                created, response = await asyncio.to_thread(
                    self.client.task_create, binding.orca_run_id,
                    (
                        f"{marker}\n{node.objective}\n\n"
                        "Do not invoke Graphori or Orca orchestration. "
                        "Do not create nested agents or workers. "
                        "Stay within the assigned task and scopes."
                    ),
                    node.title,
                )
                if not response.ok or created is None:
                    self.health.set("create_task", AdapterHealthState.DEGRADED, "create uncertain")
                    raise AdapterError("outcome_unknown", "OrcaTaskCreateUncertain")
                result = result_object(created)
                task_id = nested_id(result, ("task", "id"), ("taskId",), ("id",))
            binding.nodes[node.node_id] = task_id
            self.binding_store.save(binding)
        session_id = f"orca-session:{uuid.uuid4().hex}"
        self._sessions[session_id] = _Session(binding.graphori_run_id, node, task_id)
        self.environment_evidence["orca_task_setup_ms"] = max(
            0, round((time.monotonic() - started_at) * 1000)
        )
        return SessionHandle(self.adapter_id, session_id)

    async def dispatch(
            self, session: SessionHandle, node: NodeSpec,
            context: ContextBundle) -> DispatchHandle:
        active = self._sessions.get(session.value)
        if session.adapter_id != self.adapter_id or active is None or active.node != node:
            raise ValueError("unknown Orca session")
        agent = node.adapter or node.provider
        if agent not in {"codex", "claude"}:
            raise AdapterError("startup_failure", "UnsupportedOrcaAgent")
        binding = self._bindings[active.run_id]
        args = ["--task", active.task_id, "--run", binding.orca_run_id]
        if binding.coordinator_handle:
            args.extend(("--from", binding.coordinator_handle))
        elif self.launch_strategy is OrcaLaunchStrategy.ORCA_READY_TERMINAL:
            raise AdapterError("startup_failure", "OrcaCoordinatorHandleMissing")
        terminal_handle = ""
        ownership = RuntimeResourceOwnership.ORCA_COMPOSED
        launch_timings: dict[str, int] = {}
        route_started_at = time.monotonic()
        if self.launch_strategy is OrcaLaunchStrategy.ORCA_READY_TERMINAL:
            if node.worktree_policy != "current":
                raise AdapterError("startup_failure", "ReadyTerminalRequiresExistingWorktree")
            terminal_handle, launch_timings = await self._create_ready_terminal(node, agent)
            ownership = RuntimeResourceOwnership.GRAPHORI_PRECREATED
            args.extend(("--terminal", terminal_handle))
        else:
            if node.worktree_policy == "current":
                args.extend(("--worktree", self.worktree_selector or "current"))
            elif node.worktree_policy == "isolated":
                args.extend((
                    "--worktree", "new-child", "--name", f"graphori-{node.node_id}",
                    "--setup", "run",
                ))
            else:
                raise AdapterError("startup_failure", "UnsupportedWorktreePolicy")
            args.extend(("--agent", agent))
            if node.model:
                args.extend(("--model", node.model))
            if node.effort:
                args.extend(("--effort", node.effort))
        started_at = time.monotonic()
        started, response = await asyncio.to_thread(self.client.worker_start, args)
        if not response.ok or started is None:
            self.health.set("dispatch", AdapterHealthState.DEGRADED, "worker-start unconfirmed")
            if terminal_handle:
                possible_dispatch = self._optional_dispatch_id(started)
                if not possible_dispatch:
                    await asyncio.to_thread(self.client.terminal_close, terminal_handle)
                    raise AdapterError(
                        "startup_failure", "OrcaDispatchNotStarted",
                        "ready terminal was closed before any Dispatch was observed",
                    )
            raise AdapterError(
                "outcome_unknown", "OrcaDispatchUnconfirmed",
                "Orca worker-start did not establish authoritative Dispatch completion",
            )
        result = result_object(started)
        dispatch_id = nested_id(
            result, ("dispatch", "id"), ("dispatch", "dispatchId"), ("dispatchId",),
        )
        binding.attempts[context.attempt_id] = dispatch_id
        self.binding_store.save(binding)
        runtime_id = f"orca:{dispatch_id}"
        record = _Dispatch(
            session.value, active.run_id, node, context, active.task_id,
            dispatch_id, runtime_id, terminal_handle, ownership, route_started_at,
        )
        record.timings_ms.update(launch_timings)
        worker_start_ms = max(
            0, round((time.monotonic() - started_at) * 1000)
        )
        record.timings_ms["dispatch_start_ms"] = worker_start_ms
        record.timings_ms["worker_start_ms"] = worker_start_ms
        self._dispatches[runtime_id] = record
        self.resource_ownership[runtime_id] = ownership
        return DispatchHandle(self.adapter_id, runtime_id, node.node_id)

    @staticmethod
    def _optional_dispatch_id(value: Any) -> str:
        if not isinstance(value, Mapping):
            return ""
        try:
            result = result_object(value)
            return nested_id(
                result, ("dispatch", "id"), ("dispatch", "dispatchId"),
                ("dispatchId",),
            )
        except (OrcaProtocolError, KeyError, TypeError, ValueError):
            return ""

    @staticmethod
    def _agent_command(node: NodeSpec, agent: str) -> str:
        if not node.model:
            raise AdapterError("startup_failure", "ReadyTerminalModelRequired")
        if agent == "codex":
            argv = ["codex", "--model", node.model]
            if node.effort:
                argv.extend(("-c", f'model_reasoning_effort="{node.effort}"'))
        elif agent == "claude":
            argv = ["claude", "--model", node.model]
            if node.effort:
                argv.extend(("--effort", node.effort))
        else:
            raise AdapterError("startup_failure", "UnsupportedOrcaAgent")
        return shlex.join(argv)

    async def _create_ready_terminal(
            self, node: NodeSpec, agent: str) -> tuple[str, dict[str, int]]:
        worktree = self.worktree_selector or "current"
        command = self._agent_command(node, agent)
        started_at = time.monotonic()
        created, response = await asyncio.to_thread(
            self.client.terminal_create,
            worktree=worktree, title=f"graphori-{node.node_id}", command=command,
        )
        terminal_create_ms = max(
            0, round((time.monotonic() - started_at) * 1000),
        )
        self.environment_evidence["terminal_create_ms"] = terminal_create_ms
        if not response.ok or created is None:
            raise AdapterError("startup_failure", "OrcaTerminalCreateFailed")
        result = result_object(created)
        terminal_handle = nested_id(
            result, ("terminal", "handle"), ("terminalHandle",), ("handle",),
        )
        launch = result.get("launch")
        if isinstance(launch, Mapping):
            observed_model = str(launch.get("model", node.model))
            observed_effort = str(launch.get("effort", node.effort))
            if observed_model != node.model or observed_effort != node.effort:
                await asyncio.to_thread(self.client.terminal_close, terminal_handle)
                raise AdapterError("startup_failure", "OrcaPlacementMismatch")
        ready_at = time.monotonic()
        _value, ready_response = await asyncio.to_thread(
            self.client.terminal_wait_ready, terminal_handle, self.ready_timeout_ms,
        )
        tui_idle_wait_ms = max(
            0, round((time.monotonic() - ready_at) * 1000),
        )
        self.environment_evidence["tui_idle_wait_ms"] = tui_idle_wait_ms
        if not ready_response.ok:
            await asyncio.to_thread(self.client.terminal_close, terminal_handle)
            raise AdapterError(
                "startup_failure", "OrcaAgentNotReady",
                "tui-idle was not observed before dispatch",
            )
        self.environment_evidence.update({
            "launch_provider": agent,
            "launch_model": node.model,
            "launch_effort": node.effort,
        })
        return terminal_handle, {
            "terminal_create_ms": terminal_create_ms,
            "tui_idle_wait_ms": tui_idle_wait_ms,
        }

    def _require(self, dispatch: DispatchHandle) -> _Dispatch:
        if dispatch.adapter_id != self.adapter_id:
            raise ValueError("dispatch belongs to another adapter")
        try:
            return self._dispatches[dispatch.value]
        except KeyError as exc:
            raise ValueError("unknown Orca dispatch") from exc

    async def events(self, dispatch: DispatchHandle):
        record = self._require(dispatch)
        binding = self._bindings[record.run_id]
        yield RuntimeEvent(
            "runtime_binding_recorded", record.node.node_id, "router",
            {
                "attempt_id": record.context.attempt_id,
                "adapter": self.adapter_id,
                "external_run_id": binding.orca_run_id,
                "external_task_id": record.task_id,
                "external_dispatch_id": record.dispatch_id,
            },
            event_id=f"orca:{record.dispatch_id}:binding",
            producer_event_id=f"orca:{record.dispatch_id}:binding",
        )
        delivery_started_at = time.monotonic()
        value, response = await asyncio.to_thread(
            self.client.check, binding.orca_run_id, self.delivery_timeout_ms,
        )
        record.timings_ms["delivery_wait_ms"] = max(
            0, round((time.monotonic() - delivery_started_at) * 1000)
        )
        record.timings_ms["dispatch_to_worker_done_ms"] = record.timings_ms[
            "delivery_wait_ms"
        ]
        worker_events: tuple[RuntimeEvent, ...] = ()
        if response.ok and value is not None:
            try:
                result = result_object(value)
                delivery = result.get("delivery", result)
                if isinstance(delivery, Mapping):
                    worker_events = self.bridge.events(
                        delivery, node_id=record.node.node_id,
                        expected_task_id=record.task_id,
                        expected_dispatch_id=record.dispatch_id,
                    )
            except OrcaProtocolError:
                self.health.set("delivery", AdapterHealthState.DEGRADED, "malformed delivery")
        if not worker_events:
            self.health.set("delivery", AdapterHealthState.DEGRADED, "completion unconfirmed")
            self.resource_dispositions[record.dispatch_id] = "unknown"
            record.result = ExecutionResult(
                "outcome_unknown", runtime_id=record.runtime_id,
                attempt_id=record.context.attempt_id,
                error_kind="OrcaCompletionUnconfirmed",
                runtime_metadata=self._metadata(record),
            )
            yield RuntimeEvent(
                "worker_finished", record.node.node_id,
                "verifier" if record.node.kind == "verifier" else "worker",
                {"outcome": "outcome_unknown", "runtime_id": record.runtime_id},
                event_id=f"orca:{record.dispatch_id}:completion-unknown",
                producer_event_id=f"orca:{record.dispatch_id}:completion-unknown",
            )
            yield RuntimeEvent(
                "runtime_resource_changed", record.node.node_id, "router",
                {
                    "external_dispatch_id": record.dispatch_id,
                    "disposition": "unknown",
                },
                event_id=f"orca:{record.dispatch_id}:resource:unknown",
                producer_event_id=f"orca:{record.dispatch_id}:resource:unknown",
            )
            return
        event = worker_events[0]
        if record.node.kind == "verifier":
            event = RuntimeEvent(
                event.event_type, event.node_id, "verifier", event.payload,
                event_id=event.event_id, producer_event_id=event.producer_event_id,
            )
        record.delivery_id = str(event.payload["_orca_delivery_id"])
        outcome = str(event.payload["outcome"])
        record.result = ExecutionResult(
            outcome,
            summary=str(event.payload.get("summary", "")),
            reported_files_modified=tuple(event.payload.get("reported_files_modified", ())),
            runtime_id=record.runtime_id,
            attempt_id=record.context.attempt_id,
            runtime_metadata=self._metadata(record),
        )
        yield event
        disposition = await self._release(record)
        yield RuntimeEvent(
            "runtime_resource_changed", record.node.node_id, "router",
            {
                "external_dispatch_id": record.dispatch_id,
                "disposition": disposition,
            },
            event_id=f"orca:{record.dispatch_id}:resource:{disposition}",
            producer_event_id=f"orca:{record.dispatch_id}:resource:{disposition}",
        )

    async def acknowledge(self, event: RuntimeEvent) -> None:
        delivery_id = event.payload.get("_orca_delivery_id")
        if not isinstance(delivery_id, str) or not delivery_id:
            return
        dispatch_id = str(event.payload.get("external_dispatch_id", ""))
        record = next(
            (item for item in self._dispatches.values()
             if item.dispatch_id == dispatch_id and item.delivery_id == delivery_id),
            None,
        )
        if record is None or record.acknowledged:
            return
        binding = self._bindings[record.run_id]
        binding.pending_acks[delivery_id] = record.dispatch_id
        self.binding_store.save(binding)
        started_at = time.monotonic()
        for _attempt in range(2):
            _value, response = await asyncio.to_thread(
                self.client.acknowledge, binding.orca_run_id, delivery_id,
            )
            if response.ok:
                record.timings_ms["ack_ms"] = max(
                    0, round((time.monotonic() - started_at) * 1000)
                )
                record.timings_ms["delivery_to_ack_ms"] = record.timings_ms["ack_ms"]
                record.acknowledged = True
                binding.pending_acks.pop(delivery_id, None)
                self.binding_store.save(binding)
                self.health.set("delivery", AdapterHealthState.HEALTHY)
                return
        self.health.set("delivery", AdapterHealthState.DEGRADED, "ACK failed")
        record.timings_ms["ack_ms"] = max(
            0, round((time.monotonic() - started_at) * 1000)
        )

    async def _release(self, record: _Dispatch) -> str:
        started_at = time.monotonic()
        for _attempt in range(2):
            value, response = await asyncio.to_thread(
                self.client.worker_release, record.dispatch_id,
            )
            if response.ok and value is not None:
                try:
                    result = result_object(value)
                    state = str(result.get("releaseState", result.get("state", "released")))
                except OrcaProtocolError:
                    state = "unknown"
                mapping = {
                    "released": "released",
                    "already_released": "released",
                    "retained": "retained_intentionally",
                    "release_pending": "release_pending",
                }
                disposition = mapping.get(state, "unknown")
                if (record.resource_ownership
                        is RuntimeResourceOwnership.GRAPHORI_PRECREATED):
                    _closed, close_response = await asyncio.to_thread(
                        self.client.terminal_close, record.terminal_handle,
                    )
                    if close_response.ok:
                        disposition = "released"
                    else:
                        disposition = "release_failed"
                self.resource_dispositions[record.dispatch_id] = disposition
                record.timings_ms["release_ms"] = max(
                    0, round((time.monotonic() - started_at) * 1000)
                )
                record.timings_ms["cleanup_ms"] = record.timings_ms["release_ms"]
                if disposition == "release_failed":
                    self.health.set(
                        "release", AdapterHealthState.DEGRADED,
                        "Graphori-owned terminal close failed",
                    )
                else:
                    self.health.set("release", AdapterHealthState.HEALTHY)
                return disposition
        self.resource_dispositions[record.dispatch_id] = "release_failed"
        record.timings_ms["release_ms"] = max(
            0, round((time.monotonic() - started_at) * 1000)
        )
        record.timings_ms["cleanup_ms"] = record.timings_ms["release_ms"]
        self.health.set("release", AdapterHealthState.DEGRADED, "bounded release failed")
        return "release_failed"

    def _metadata(self, record: _Dispatch) -> dict[str, Any]:
        binding = self._bindings[record.run_id]
        return {
            **self.environment_evidence,
            "adapter": self.adapter_id,
            "external_run_id": binding.orca_run_id,
            "external_task_id": record.task_id,
            "external_dispatch_id": record.dispatch_id,
            "launch_strategy": self.launch_strategy.value,
            "resource_ownership": record.resource_ownership.value,
            "adapter_health": dict(self.health.snapshot()),
            **record.timings_ms,
        }

    async def cancel(self, dispatch: DispatchHandle, reason: str) -> None:
        del reason
        record = self._require(dispatch)
        value, response = await asyncio.to_thread(
            self.client.worker_stop, record.dispatch_id,
        )
        if not response.ok or value is None:
            self.health.set("cancel", AdapterHealthState.DEGRADED, "stop unconfirmed")
            if record.result is None:
                record.result = ExecutionResult(
                    "outcome_unknown", runtime_id=record.runtime_id,
                    attempt_id=record.context.attempt_id,
                    error_kind="OrcaCancelUnconfirmed",
                )
            return
        try:
            result = result_object(value)
            stopped = str(result.get("state", result.get("workerState", ""))) in {
                "stopped", "cancelled", "canceled",
            }
        except OrcaProtocolError:
            stopped = False
        if not stopped:
            self.health.set("cancel", AdapterHealthState.DEGRADED, "stop not confirmed")
            record.result = ExecutionResult(
                "outcome_unknown", runtime_id=record.runtime_id,
                attempt_id=record.context.attempt_id,
                error_kind="OrcaCancelUnconfirmed",
                runtime_metadata=self._metadata(record),
            )
            return
        self.health.set("cancel", AdapterHealthState.HEALTHY)
        record.result = ExecutionResult(
            "cancelled", runtime_id=record.runtime_id,
            attempt_id=record.context.attempt_id, cancelled=True,
            runtime_metadata=self._metadata(record),
        )

    async def collect(self, dispatch: DispatchHandle) -> ExecutionResult:
        record = self._require(dispatch)
        if record.route_started_at:
            record.timings_ms["total_route_ms"] = max(
                0, round((time.monotonic() - record.route_started_at) * 1000),
            )
        if record.result is None:
            record.result = ExecutionResult(
                "outcome_unknown", runtime_id=record.runtime_id,
                attempt_id=record.context.attempt_id,
                error_kind="OrcaResultUnavailable",
                runtime_metadata=self._metadata(record),
            )
        record.result = replace(
            record.result, runtime_metadata=self._metadata(record),
        )
        return record.result

    async def release(self, session: SessionHandle) -> None:
        for runtime_id, record in tuple(self._dispatches.items()):
            if record.session_id == session.value:
                if record.result is None or record.result.outcome == "outcome_unknown":
                    continue
                self._dispatches.pop(runtime_id, None)
        if not any(
                record.session_id == session.value
                for record in self._dispatches.values()):
            self._sessions.pop(session.value, None)

    def classify_reconciliation(
            self, *, journal_state: str,
            observed: Mapping[str, Any] | None) -> ReconciliationStatus:
        if observed is None:
            return ReconciliationStatus.MISSING
        worker = str(observed.get("workerState", ""))
        dispatch = str(observed.get("dispatchStatus", ""))
        if journal_state == "terminal" and worker in {"running", "ready"}:
            return ReconciliationStatus.CONFLICTING
        if journal_state == "running" and worker in {"running", "ready"}:
            return ReconciliationStatus.STILL_RUNNING
        if journal_state == "running" and worker in {"succeeded", "failed"}:
            return ReconciliationStatus.COMPLETED_CONFIRMED
        if not worker and not dispatch:
            return ReconciliationStatus.AMBIGUOUS
        return ReconciliationStatus.MATCHED
