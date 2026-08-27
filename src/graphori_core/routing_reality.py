"""Collect-only telemetry and reporting for Routing Reality Check runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
import statistics
import subprocess
from typing import Any, Mapping, Sequence


class AdapterRouteHealth(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class FailureDomain(str, Enum):
    NONE = "none"
    ADAPTER = "adapter"
    PROVIDER = "provider"
    MODEL = "model"
    VERIFICATION = "verification"
    POLICY = "policy"


class SelfReportClassification(str, Enum):
    CONSISTENT = "consistent"
    PROVIDER_SELF_REPORT_INCONSISTENCY = "provider_self_report_inconsistency"
    PROTOCOL_FAILURE = "protocol_failure"
    VERIFICATION_FAILURE = "verification_failure"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TelemetrySample:
    route_id: str
    routing_decision_id: str
    routing_decision_digest: str
    provider: str
    adapter: str
    requested_model: str
    observed_model: str
    requested_effort: str
    observed_effort: str
    task_kind: str
    risk: str
    read_only: bool
    cold_start: bool
    queue_ms: int
    startup_ms: int
    provider_start_ms: int
    first_event_ms: int
    worker_report_ms: int
    execution_ms: int
    collect_ms: int
    cleanup_ms: int
    total_ms: int
    worker_outcome: str
    verification_outcome: str
    structured_result_valid: bool
    rework_count: int
    scope_violation: bool
    adapter_health: str
    failure_domain: FailureDomain
    timestamp: str
    orca_run_setup_ms: int = 0
    orca_task_setup_ms: int = 0
    dispatch_start_ms: int = 0
    delivery_wait_ms: int = 0
    ack_ms: int = 0
    release_ms: int = 0
    failure_reason: str = ""
    workload_id: str = ""
    process_spawn_ms: int = 0
    structured_result_ms: int = 0
    verification_ms: int = 0
    ttur_ms: int = 0
    effective_time_ms: int = 0
    worker_report_status: str = "unknown"
    self_report_disagreement: bool = False
    usage_status: str = "unknown"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    estimated_cost: float | None = None

    def __post_init__(self) -> None:
        if not self.route_id or not self.routing_decision_id:
            raise ValueError("telemetry route and routing decision identities are required")
        for name in (
                "queue_ms", "startup_ms", "provider_start_ms", "first_event_ms",
                "worker_report_ms", "execution_ms", "collect_ms", "cleanup_ms",
                "total_ms", "rework_count", "orca_run_setup_ms", "orca_task_setup_ms",
                "dispatch_start_ms", "delivery_wait_ms", "ack_ms", "release_ms"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        for name in (
                "process_spawn_ms", "structured_result_ms", "verification_ms",
                "ttur_ms", "effective_time_ms"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        for name in ("input_tokens", "output_tokens", "cached_tokens"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["failure_domain"] = self.failure_domain.value
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TelemetrySample":
        unknown = set(value) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown telemetry fields: {', '.join(sorted(unknown))}")
        data = dict(value)
        data["failure_domain"] = FailureDomain(data["failure_domain"])
        return cls(**data)


def classify_self_report(sample: TelemetrySample) -> SelfReportClassification:
    """Classify Worker self-report separately from canonical verification."""

    if not sample.structured_result_valid:
        return SelfReportClassification.PROTOCOL_FAILURE
    if sample.verification_outcome == "revise":
        return SelfReportClassification.VERIFICATION_FAILURE
    if (sample.worker_report_status in {"failed", "incomplete"}
            and sample.verification_outcome == "pass"):
        return SelfReportClassification.PROVIDER_SELF_REPORT_INCONSISTENCY
    if sample.worker_report_status in {"succeeded", "failed", "incomplete"}:
        return SelfReportClassification.CONSISTENT
    return SelfReportClassification.UNKNOWN


@dataclass(frozen=True)
class WorkloadBaselineSummary:
    samples: int
    cold_total_ms: int | None
    warm_median_total_ms: int | None
    warm_median_ttur_ms: int | None
    warm_median_effective_time_ms: int | None
    structured_result_failures: int
    verification_passes: int
    reworks: int
    scope_violations: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DirectBaselineReport:
    workloads: Mapping[str, Mapping[str, WorkloadBaselineSummary]]
    route_startup_penalty_ms: Mapping[str, int]
    parallel_break_even_ms: Mapping[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workloads": {
                route: {
                    workload: summary.to_dict()
                    for workload, summary in sorted(values.items())
                }
                for route, values in sorted(self.workloads.items())
            },
            "route_startup_penalty_ms": dict(sorted(self.route_startup_penalty_ms.items())),
            "parallel_break_even_ms": dict(sorted(self.parallel_break_even_ms.items())),
        }


@dataclass(frozen=True)
class RouteSummary:
    route_id: str
    samples: int
    cold_total_ms: int | None
    warm_median_total_ms: int | None
    warm_median_startup_ms: int | None
    warm_median_execution_ms: int | None
    warm_median_cleanup_ms: int | None
    health: AdapterRouteHealth
    verification_passes: int
    reworks: int
    scope_violations: int
    structured_result_failures: int
    failure_domains: tuple[FailureDomain, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["health"] = self.health.value
        value["failure_domains"] = [item.value for item in self.failure_domains]
        return value


@dataclass(frozen=True)
class RealityCheckReport:
    routes: Mapping[str, RouteSummary]
    orca_overhead_ms: Mapping[str, int | None]

    def to_dict(self) -> dict[str, Any]:
        return {
            "routes": {
                key: self.routes[key].to_dict() for key in sorted(self.routes)
            },
            "orca_overhead_ms": dict(sorted(self.orca_overhead_ms.items())),
        }


def _median(values: Sequence[int]) -> int | None:
    return round(statistics.median(values)) if values else None


def summarize_direct_baseline(
        samples: Sequence[TelemetrySample]) -> DirectBaselineReport:
    """Summarize direct-route measurements without collapsing quality into a score.

    The break-even value is a practical measured lower bound: the warm W1
    minimal-useful-task cost plus the route's median deterministic verification
    time. Handoff and fan-in costs remain separate until they are measured.
    """

    grouped: dict[str, dict[str, list[TelemetrySample]]] = {}
    by_route: dict[str, list[TelemetrySample]] = {}
    for sample in samples:
        if not sample.route_id.startswith("direct-"):
            continue
        workload = sample.workload_id or sample.task_kind
        grouped.setdefault(sample.route_id, {}).setdefault(workload, []).append(sample)
        by_route.setdefault(sample.route_id, []).append(sample)
    workloads: dict[str, dict[str, WorkloadBaselineSummary]] = {}
    startup: dict[str, int] = {}
    break_even: dict[str, int] = {}
    for route, workload_values in sorted(grouped.items()):
        workloads[route] = {}
        for workload, values in sorted(workload_values.items()):
            cold = [item for item in values if item.cold_start]
            warm = [item for item in values if not item.cold_start]
            workloads[route][workload] = WorkloadBaselineSummary(
                samples=len(values),
                cold_total_ms=cold[0].total_ms if cold else None,
                warm_median_total_ms=_median([item.total_ms for item in warm]),
                warm_median_ttur_ms=_median([item.ttur_ms for item in warm]),
                warm_median_effective_time_ms=_median([
                    item.effective_time_ms for item in warm
                ]),
                structured_result_failures=sum(
                    not item.structured_result_valid for item in values
                ),
                verification_passes=sum(
                    item.verification_outcome == "pass" for item in values
                ),
                reworks=sum(item.rework_count for item in values),
                scope_violations=sum(item.scope_violation for item in values),
            )
        route_values = by_route[route]
        warm_values = [item for item in route_values if not item.cold_start]
        startup[route] = _median([
            item.first_event_ms for item in warm_values
        ]) or 0
        verification = _median([
            item.verification_ms for item in warm_values
            if item.verification_ms > 0
        ]) or 0
        minimal_task = workloads[route].get("w1-read")
        minimal_task_ms = (
            minimal_task.warm_median_total_ms
            if minimal_task and minimal_task.warm_median_total_ms is not None
            else startup[route]
        )
        break_even[route] = minimal_task_ms + verification
    return DirectBaselineReport(workloads, startup, break_even)


def _health(samples: Sequence[TelemetrySample]) -> AdapterRouteHealth:
    if not samples or all(item.adapter_health == "unavailable" for item in samples):
        return AdapterRouteHealth.UNAVAILABLE
    if any(
            item.adapter_health == "degraded"
            or item.failure_domain is not FailureDomain.NONE
            for item in samples):
        return AdapterRouteHealth.DEGRADED
    usable = any(
        item.structured_result_valid
        and not item.scope_violation
        and item.worker_outcome == "succeeded"
        and item.verification_outcome in {"pass", "not_required"}
        for item in samples
    )
    return AdapterRouteHealth.READY if usable else AdapterRouteHealth.DEGRADED


def summarize_routes(samples: Sequence[TelemetrySample]) -> RealityCheckReport:
    grouped: dict[str, list[TelemetrySample]] = {}
    for item in samples:
        grouped.setdefault(item.route_id, []).append(item)
    summaries: dict[str, RouteSummary] = {}
    for route_id, values in sorted(grouped.items()):
        cold = [item for item in values if item.cold_start]
        warm = [item for item in values if not item.cold_start]
        summaries[route_id] = RouteSummary(
            route_id=route_id,
            samples=len(values),
            cold_total_ms=cold[0].total_ms if cold else None,
            warm_median_total_ms=_median([item.total_ms for item in warm]),
            warm_median_startup_ms=_median([item.first_event_ms for item in warm]),
            warm_median_execution_ms=_median([
                max(0, item.worker_report_ms - item.first_event_ms)
                for item in warm
            ]),
            warm_median_cleanup_ms=_median([item.cleanup_ms for item in warm]),
            health=_health(values),
            verification_passes=sum(
                item.verification_outcome == "pass" for item in values
            ),
            reworks=sum(item.rework_count for item in values),
            scope_violations=sum(item.scope_violation for item in values),
            structured_result_failures=sum(
                not item.structured_result_valid for item in values
            ),
            failure_domains=tuple(sorted(
                {item.failure_domain for item in values
                 if item.failure_domain is not FailureDomain.NONE},
                key=lambda item: item.value,
            )),
        )
    overhead: dict[str, int | None] = {}
    for provider in ("codex", "claude"):
        direct = summaries.get(f"direct-{provider}")
        orca = summaries.get(f"orca-{provider}")
        if (direct is None or orca is None
                or direct.warm_median_total_ms is None
                or orca.warm_median_total_ms is None):
            overhead[provider] = None
        else:
            overhead[provider] = (
                orca.warm_median_total_ms - direct.warm_median_total_ms
            )
    return RealityCheckReport(summaries, overhead)


def required_sample_count(total_ms: Sequence[int]) -> int:
    if len(total_ms) < 2:
        return 2
    if len(total_ms) >= 3:
        return 3
    lower, upper = sorted(total_ms)
    return 3 if lower == 0 or (upper - lower) / lower > 0.20 else 2


@dataclass(frozen=True)
class DirectFixture:
    root: Path
    workload_id: str
    objective: str
    read_scope: tuple[str, ...]
    write_scope: tuple[str, ...]
    verification_argv: tuple[str, ...]


def _commit_fixture(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "rrc@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Graphori RRC"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "RRC fixture baseline"],
        check=True,
    )


def create_direct_fixture_repository(root: Path, workload_id: str) -> DirectFixture:
    """Create one clean, disposable direct-route workload repository."""

    root.mkdir(parents=True, exist_ok=False)
    (root / ".gitignore").write_text("__pycache__/\n*.py[cod]\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\nname = \"graphori-rrc04-fixture\"\nversion = \"0.0.1\"\n"
        "requires-python = \">=3.11\"\n",
        encoding="utf-8",
    )
    if workload_id == "w1-read":
        fixture = DirectFixture(
            root, workload_id,
            "Read pyproject.toml and report the project name and requires-python value. "
            "Do not modify any file.",
            ("pyproject.toml",), (), (),
        )
    elif workload_id == "w2-tiny-write":
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "src" / "math_utils.py").write_text(
            "def add(a, b):\n    raise NotImplementedError\n", encoding="utf-8",
        )
        (root / "tests" / "test_math_utils.py").write_text(
            "import unittest\nfrom src.math_utils import add\n\n"
            "class MathUtilsTests(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n",
            encoding="utf-8",
        )
        fixture = DirectFixture(
            root, workload_id,
            "Implement add(a, b) in src/math_utils.py. Run exactly: "
            "python -m unittest tests.test_math_utils. Modify only src/math_utils.py.",
            ("src/math_utils.py", "tests/test_math_utils.py"),
            ("src/math_utils.py",),
            ("python", "-m", "unittest", "tests.test_math_utils"),
        )
    elif workload_id == "w3-bounded-implementation":
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "src" / "inventory.py").write_text(
            "def total_cost(items):\n    raise NotImplementedError\n", encoding="utf-8",
        )
        (root / "src" / "reporting.py").write_text(
            "from src.inventory import total_cost\n\n"
            "def render_summary(items):\n    raise NotImplementedError\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_reporting.py").write_text(
            "import unittest\nfrom src.inventory import total_cost\n"
            "from src.reporting import render_summary\n\n"
            "class ReportingTests(unittest.TestCase):\n"
            "    def setUp(self):\n"
            "        self.items = [\n"
            "            {'name': 'A', 'price': 12, 'quantity': 2},\n"
            "            {'name': 'B', 'price': 5, 'quantity': 3},\n"
            "        ]\n\n"
            "    def test_total_cost(self):\n"
            "        self.assertEqual(total_cost(self.items), 39)\n\n"
            "    def test_render_summary(self):\n"
            "        self.assertEqual(render_summary(self.items), '2 items / total 39')\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n",
            encoding="utf-8",
        )
        fixture = DirectFixture(
            root, workload_id,
            "Implement total_cost(items) in src/inventory.py and render_summary(items) "
            "in src/reporting.py. Run exactly: python -m unittest tests.test_reporting. "
            "Modify only those two source files.",
            ("src/inventory.py", "src/reporting.py", "tests/test_reporting.py"),
            ("src/inventory.py", "src/reporting.py"),
            ("python", "-m", "unittest", "tests.test_reporting"),
        )
    else:
        raise ValueError(f"unknown direct workload: {workload_id}")
    (root / ".graphori-rrc.json").write_text(
        json.dumps({"temporary_fixture": True, "workload": workload_id}, sort_keys=True),
        encoding="utf-8",
    )
    _commit_fixture(root)
    return fixture


def create_fixture_repository(root: Path) -> Path:
    """Create the disposable repository used by all RRC write routes."""

    root.mkdir(parents=True, exist_ok=False)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text(
        "[project]\nname = \"graphori-rrc-fixture\"\nversion = \"0.0.1\"\n"
        "requires-python = \">=3.11\"\n",
        encoding="utf-8",
    )
    (root / "src" / "math_utils.py").write_text(
        "def add(a, b):\n    raise NotImplementedError\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_math_utils.py").write_text(
        "import unittest\nfrom src.math_utils import add\n\n"
        "class MathUtilsTests(unittest.TestCase):\n"
        "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n",
        encoding="utf-8",
    )
    (root / ".graphori-rrc.json").write_text(
        json.dumps({"temporary_fixture": True}, sort_keys=True), encoding="utf-8",
    )
    (root / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n", encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "rrc@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Graphori RRC"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "RRC fixture baseline"],
        check=True,
    )
    return root
