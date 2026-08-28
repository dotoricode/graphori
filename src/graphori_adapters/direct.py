"""Route each planned Node to its explicit portable ExecutionAdapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import uuid

from graphori_core.ports import (
    AdapterCapabilities, ContextBundle, DispatchHandle, ExecutionAdapter,
    RuntimeEvent, RuntimeRunHandle, SessionHandle,
)
from graphori_core.run_plan import NodeSpec, RunPlan


@dataclass(frozen=True)
class _SessionRoute:
    adapter: ExecutionAdapter
    inner: SessionHandle


@dataclass(frozen=True)
class _DispatchRoute:
    adapter: ExecutionAdapter
    inner: DispatchHandle


class RoutedExecutionAdapter:
    """A small multiplexer; route choice remains compiler-owned on NodeSpec."""

    adapter_id = "direct-routes"

    def __init__(self, adapters: Mapping[str, ExecutionAdapter]) -> None:
        if not adapters:
            raise ValueError("at least one routed adapter is required")
        self.adapters = dict(adapters)
        self._sessions: dict[str, _SessionRoute] = {}
        self._dispatches: dict[str, _DispatchRoute] = {}
        self._prepared: dict[str, RuntimeRunHandle] = {}

    def probe(self) -> AdapterCapabilities:
        probes = tuple(adapter.probe() for adapter in self.adapters.values())
        available = tuple(item for item in probes if item.available)
        return AdapterCapabilities(
            self.adapter_id, bool(available),
            max_concurrency=sum(int(item.max_concurrency or 1) for item in available) or 1,
            supports_cancel=all(item.supports_cancel for item in available),
            supports_reconcile=False,
            supports_heartbeat=all(item.supports_heartbeat for item in available),
            supports_progress=all(item.supports_progress for item in available),
            supports_worktree=all(item.supports_worktree for item in available),
            supports_persistent_session=False,
            supports_questions=False,
            supports_gate=False,
            supports_usage=all(item.supports_usage for item in available),
            supports_files_modified=all(item.supports_files_modified for item in available),
            supports_structured_result=all(
                item.supports_structured_result for item in available
            ),
            supports_nested_agents=False,
            supports_delivery_ack=False,
            reason="" if available else "no routed adapter is available",
        )

    def route_health_snapshot(self, plan: RunPlan) -> tuple[Mapping[str, object], ...]:
        """Freeze per-route availability without leaking provider branches into Core."""

        selected = {node.adapter or node.provider for node in plan.nodes}
        values = []
        for route, adapter in sorted(self.adapters.items()):
            capability = adapter.probe()
            values.append({
                "route": route,
                "provider": route,
                "health": "ready" if capability.available else "unavailable",
                "reason": capability.reason,
                "selected": route in selected,
                "max_concurrency": capability.max_concurrency,
            })
        return tuple(values)

    def _adapter_for(self, node: NodeSpec) -> ExecutionAdapter:
        key = node.adapter or node.provider
        try:
            adapter = self.adapters[key]
        except KeyError as exc:
            raise ValueError(f"no ExecutionAdapter for planned route: {key or '<empty>'}") from exc
        probe = adapter.probe()
        if not probe.available:
            raise RuntimeError(probe.reason or f"planned adapter is unavailable: {key}")
        return adapter

    async def prepare_run(self, plan: RunPlan) -> RuntimeRunHandle:
        used: dict[str, ExecutionAdapter] = {}
        for node in plan.nodes:
            adapter = self._adapter_for(node)
            used[adapter.adapter_id] = adapter
        self._prepared = {
            adapter_id: await adapter.prepare_run(plan)
            for adapter_id, adapter in sorted(used.items())
        }
        value = ",".join(
            f"{key}={handle.value}" for key, handle in sorted(self._prepared.items())
        )
        return RuntimeRunHandle(self.adapter_id, value)

    async def start_session(self, node: NodeSpec) -> SessionHandle:
        adapter = self._adapter_for(node)
        inner = await adapter.start_session(node)
        value = f"session:{uuid.uuid4().hex}"
        self._sessions[value] = _SessionRoute(adapter, inner)
        return SessionHandle(self.adapter_id, value)

    def _session(self, session: SessionHandle) -> _SessionRoute:
        if session.adapter_id != self.adapter_id:
            raise ValueError("session belongs to another adapter")
        try:
            return self._sessions[session.value]
        except KeyError as exc:
            raise ValueError("unknown routed session") from exc

    def _dispatch(self, dispatch: DispatchHandle) -> _DispatchRoute:
        if dispatch.adapter_id != self.adapter_id:
            raise ValueError("dispatch belongs to another adapter")
        try:
            return self._dispatches[dispatch.value]
        except KeyError as exc:
            raise ValueError("unknown routed dispatch") from exc

    async def dispatch(self, session: SessionHandle, node: NodeSpec,
                       context: ContextBundle) -> DispatchHandle:
        route = self._session(session)
        if route.adapter is not self._adapter_for(node):
            raise ValueError("Node route changed after session creation")
        inner = await route.adapter.dispatch(route.inner, node, context)
        value = f"dispatch:{uuid.uuid4().hex}"
        self._dispatches[value] = _DispatchRoute(route.adapter, inner)
        return DispatchHandle(self.adapter_id, value, node.node_id)

    async def events(self, dispatch: DispatchHandle):
        route = self._dispatch(dispatch)
        async for event in route.adapter.events(route.inner):
            yield event

    async def acknowledge(self, event: RuntimeEvent) -> None:
        del event

    async def cancel(self, dispatch: DispatchHandle, reason: str) -> None:
        route = self._dispatch(dispatch)
        await route.adapter.cancel(route.inner, reason)

    async def collect(self, dispatch: DispatchHandle):
        route = self._dispatch(dispatch)
        try:
            return await route.adapter.collect(route.inner)
        finally:
            self._dispatches.pop(dispatch.value, None)

    async def release(self, session: SessionHandle) -> None:
        route = self._session(session)
        try:
            await route.adapter.release(route.inner)
        finally:
            self._sessions.pop(session.value, None)
