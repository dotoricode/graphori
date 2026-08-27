"""Deterministic fixtures and measurements for the RRC-05B TDD benchmark."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
from typing import Any, Sequence


NO_SKILL = "no-skill"
TDD = "tdd"


class TddValueClassification(str, Enum):
    AUTO_CANDIDATE = "auto_candidate"
    CONDITIONAL = "conditional"
    MANUAL_ONLY = "manual_only"
    NO_BENEFIT = "no_benefit"
    HARMFUL = "harmful"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class TddBenchmarkSample:
    provider: str
    model: str
    effort: str
    workload: str
    arm: str
    pair_id: str
    repetition: int
    order_index: int
    ttur_ms: int
    effective_time_ms: int
    worker_report_status: str
    structured_result_valid: bool
    verification: str
    scope_violation: bool
    escaped_defect: bool
    rework_count: int
    regression_test_exists: bool
    mutation_detected: bool
    public_seam_test: bool
    startup_ms: int = 0
    first_event_ms: int = 0
    execution_ms: int = 0
    structured_result_ms: int = 0
    verification_ms: int = 0
    total_ms: int = 0
    production_loc: int = 0
    test_loc: int = 0
    files_changed: int = 0
    private_method_test_count: int = 0
    implementation_mock_count: int = 0
    skill_digest: str = ""
    skill_source_revision: str = ""
    skill_snapshot_verified: bool = False
    binding_rendered: bool = False
    approved_seams_present: bool = True
    unexpected_dependencies: tuple[str, ...] = ()
    user_question_count: int = 0
    nested_agent_count: int = 0
    hooks_executed: bool = False
    plugin_installed: bool = False
    skill_contamination: bool = False
    red_observed: str = "unknown"
    green_observed: str = "unknown"
    skill_read: str = "unknown"
    observed_model: str = "unknown"
    observed_effort: str = "unknown"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    estimated_cost: float | None = None
    run_plan_digest: str = ""
    replay_digest_matches: bool = False
    effectiveness_eligible: bool = True
    failure_kind: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if self.arm not in {NO_SKILL, TDD}:
            raise ValueError(f"unknown TDD benchmark arm: {self.arm}")
        for name in (
            "repetition", "order_index", "ttur_ms", "effective_time_ms",
            "rework_count", "startup_ms", "first_event_ms", "execution_ms",
            "structured_result_ms", "verification_ms", "total_ms",
            "production_loc", "test_loc", "files_changed",
            "private_method_test_count", "implementation_mock_count",
            "user_question_count", "nested_agent_count",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider, "model": self.model,
            "observed_model": self.observed_model, "effort": self.effort,
            "observed_effort": self.observed_effort, "workload": self.workload,
            "arm": self.arm, "pair_id": self.pair_id,
            "repetition": self.repetition, "order_index": self.order_index,
            "timing": {
                "startup_ms": self.startup_ms, "first_event_ms": self.first_event_ms,
                "execution_ms": self.execution_ms,
                "structured_result_ms": self.structured_result_ms,
                "verification_ms": self.verification_ms, "ttur_ms": self.ttur_ms,
                "total_ms": self.total_ms, "effective_time_ms": self.effective_time_ms,
            },
            "quality": {
                "worker_report": self.worker_report_status,
                "structured_result_valid": self.structured_result_valid,
                "verification": self.verification,
                "scope_violation": self.scope_violation,
                "escaped_defect": self.escaped_defect,
                "rework": self.rework_count,
                "regression_test_exists": self.regression_test_exists,
                "mutation_detected": self.mutation_detected,
                "public_seam_test": self.public_seam_test,
                "private_method_test_count": self.private_method_test_count,
                "implementation_mock_count": self.implementation_mock_count,
            },
            "diff": {
                "files_changed": self.files_changed,
                "production_loc": self.production_loc, "test_loc": self.test_loc,
            },
            "skill": {
                "id": "tdd" if self.arm == TDD else "",
                "digest": self.skill_digest,
                "source_revision": self.skill_source_revision,
                "snapshot_verified": self.skill_snapshot_verified,
                "binding_rendered": self.binding_rendered,
                "approved_seams_present": self.approved_seams_present,
                "unexpected_dependencies": list(self.unexpected_dependencies),
                "skill_read": self.skill_read,
                "red_observed": self.red_observed, "green_observed": self.green_observed,
                "hooks_executed": self.hooks_executed,
                "plugin_installed": self.plugin_installed,
                "contamination": self.skill_contamination,
            },
            "control": {
                "user_question_count": self.user_question_count,
                "nested_agent_count": self.nested_agent_count,
            },
            "usage": {
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cached_tokens": self.cached_tokens, "estimated_cost": self.estimated_cost,
            },
            "run_plan_digest": self.run_plan_digest,
            "replay_digest_matches": self.replay_digest_matches,
            "effectiveness_eligible": self.effectiveness_eligible,
            "failure_kind": self.failure_kind, "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TddBenchmarkSample":
        timing, quality, diff = value["timing"], value["quality"], value["diff"]
        skill, control, usage = value["skill"], value["control"], value["usage"]
        return cls(
            provider=value["provider"], model=value["model"], effort=value["effort"],
            workload=value["workload"], arm=value["arm"], pair_id=value["pair_id"],
            repetition=value["repetition"], order_index=value["order_index"],
            ttur_ms=timing["ttur_ms"], effective_time_ms=timing["effective_time_ms"],
            worker_report_status=quality["worker_report"],
            structured_result_valid=quality["structured_result_valid"],
            verification=quality["verification"],
            scope_violation=quality["scope_violation"],
            escaped_defect=quality["escaped_defect"], rework_count=quality["rework"],
            regression_test_exists=quality["regression_test_exists"],
            mutation_detected=quality["mutation_detected"],
            public_seam_test=quality["public_seam_test"],
            startup_ms=timing["startup_ms"], first_event_ms=timing["first_event_ms"],
            execution_ms=timing["execution_ms"],
            structured_result_ms=timing["structured_result_ms"],
            verification_ms=timing["verification_ms"], total_ms=timing["total_ms"],
            production_loc=diff["production_loc"], test_loc=diff["test_loc"],
            files_changed=diff["files_changed"],
            private_method_test_count=quality["private_method_test_count"],
            implementation_mock_count=quality["implementation_mock_count"],
            skill_digest=skill["digest"],
            skill_source_revision=skill["source_revision"],
            skill_snapshot_verified=skill["snapshot_verified"],
            binding_rendered=skill["binding_rendered"],
            approved_seams_present=skill["approved_seams_present"],
            unexpected_dependencies=tuple(skill["unexpected_dependencies"]),
            user_question_count=control["user_question_count"],
            nested_agent_count=control["nested_agent_count"],
            hooks_executed=skill["hooks_executed"],
            plugin_installed=skill["plugin_installed"],
            skill_contamination=skill["contamination"],
            red_observed=skill["red_observed"], green_observed=skill["green_observed"],
            skill_read=skill["skill_read"],
            observed_model=value.get("observed_model", "unknown"),
            observed_effort=value.get("observed_effort", "unknown"),
            input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
            cached_tokens=usage.get("cached_tokens"), estimated_cost=usage.get("estimated_cost"),
            run_plan_digest=value["run_plan_digest"],
            replay_digest_matches=value["replay_digest_matches"],
            effectiveness_eligible=value["effectiveness_eligible"],
            failure_kind=value["failure_kind"], timestamp=value["timestamp"],
        )


def paired_tdd_orders(repetitions: int) -> tuple[tuple[str, str], ...]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    return tuple(
        (NO_SKILL, TDD) if index % 2 == 0 else (TDD, NO_SKILL)
        for index in range(repetitions)
    )


def classify_tdd_value(samples: Sequence[TddBenchmarkSample]) -> TddValueClassification:
    eligible = [sample for sample in samples if sample.effectiveness_eligible]
    baseline = [sample for sample in eligible if sample.arm == NO_SKILL]
    tdd = [sample for sample in eligible if sample.arm == TDD]
    if len(baseline) < 2 or len(tdd) < 2:
        return TddValueClassification.INSUFFICIENT_DATA
    if any(
        not sample.structured_result_valid or sample.verification != "pass"
        or sample.scope_violation or not sample.public_seam_test
        or sample.private_method_test_count or sample.implementation_mock_count
        for sample in tdd
    ):
        return TddValueClassification.HARMFUL
    base_time = statistics.median(item.effective_time_ms for item in baseline)
    tdd_time = statistics.median(item.effective_time_ms for item in tdd)
    if not base_time:
        return TddValueClassification.INSUFFICIENT_DATA
    ratio = tdd_time / base_time
    defect_reduced = sum(item.escaped_defect for item in tdd) < sum(
        item.escaped_defect for item in baseline
    )
    rework_reduced = sum(item.rework_count for item in tdd) < sum(
        item.rework_count for item in baseline
    )
    mutation_improved = sum(item.mutation_detected for item in tdd) > sum(
        item.mutation_detected for item in baseline
    )
    if ratio < 1.0 and (defect_reduced or rework_reduced):
        return TddValueClassification.AUTO_CANDIDATE
    if ratio <= 1.15 and (defect_reduced or rework_reduced):
        return TddValueClassification.CONDITIONAL
    if ratio > 1.50:
        return TddValueClassification.HARMFUL
    if mutation_improved:
        return TddValueClassification.MANUAL_ONLY
    return TddValueClassification.NO_BENEFIT


@dataclass(frozen=True)
class TddFixture:
    root: Path
    workload_id: str
    objective: str
    read_scope: tuple[str, ...]
    write_scope: tuple[str, ...]
    verification_argv: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    preconditions: frozenset[str]
    baseline_test_count: int


@dataclass(frozen=True)
class TestQuality:
    regression_test_exists: bool
    public_seam_test: bool
    private_method_test_count: int
    implementation_mock_count: int


def _commit(root: Path) -> None:
    subprocess.run(("git", "init", "-q", str(root)), check=True)
    subprocess.run(("git", "-C", str(root), "config", "user.email", "rrc@example.invalid"), check=True)
    subprocess.run(("git", "-C", str(root), "config", "user.name", "Graphori RRC"), check=True)
    subprocess.run(("git", "-C", str(root), "add", "."), check=True)
    subprocess.run(("git", "-C", str(root), "commit", "-qm", "RRC fixture baseline"), check=True)


def create_tdd_fixture_repository(root: Path, workload_id: str) -> TddFixture:
    """Create a clean fixture whose approved seams are identical for both arms."""

    root.mkdir(parents=True, exist_ok=False)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / ".gitignore").write_text("__pycache__/\n*.py[cod]\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\nname='graphori-rrc05b-fixture'\nversion='0.0.1'\nrequires-python='>=3.11'\n",
        encoding="utf-8",
    )
    common = (
        "The approved test seams are already provided; treat them as pre-agreed.",
        "Use public interfaces only and do not test private implementation details.",
        "Do not ask the user questions; complete the bounded task.",
    )
    if workload_id == "w2-tiny-write":
        (root / "src" / "math_utils.py").write_text(
            "def add(a, b):\n    raise NotImplementedError\n", encoding="utf-8",
        )
        (root / "tests" / "test_math_utils.py").write_text(
            "import unittest\nfrom src.math_utils import add\n\n"
            "class MathUtilsTests(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8",
        )
        criteria = common + ("Approved public seam: src.math_utils.add(a, b).",)
        objective = (
            "Implement add(a, b). Preserve the public function. Run exactly: "
            "python -m unittest tests.test_math_utils. Modify only the source and its test."
        )
        paths = ("src/math_utils.py", "tests/test_math_utils.py")
        argv = ("python", "-m", "unittest", "tests.test_math_utils")
        baseline_tests = 1
    elif workload_id == "w3-bounded-implementation":
        (root / "src" / "inventory.py").write_text(
            "def total_cost(items):\n    raise NotImplementedError\n", encoding="utf-8",
        )
        (root / "src" / "reporting.py").write_text(
            "from src.inventory import total_cost\n\ndef render_summary(items):\n    raise NotImplementedError\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_reporting.py").write_text(
            "import unittest\nfrom src.inventory import total_cost\n"
            "from src.reporting import render_summary\n\n"
            "class ReportingTests(unittest.TestCase):\n"
            "    def setUp(self):\n        self.items = [{'name': 'A', 'price': 12, 'quantity': 2}, {'name': 'B', 'price': 5, 'quantity': 3}]\n\n"
            "    def test_total_cost(self):\n        self.assertEqual(total_cost(self.items), 39)\n\n"
            "    def test_render_summary(self):\n        self.assertEqual(render_summary(self.items), '2 items / total 39')\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8",
        )
        criteria = common + (
            "Approved public seams: src.inventory.total_cost(items) and src.reporting.render_summary(items).",
            "total_cost multiplies each price by quantity; render_summary returns '<count> items / total <total>'.",
        )
        objective = (
            "Implement total_cost(items) and render_summary(items). Run exactly: "
            "python -m unittest tests.test_reporting. Modify only the two source files and their test."
        )
        paths = ("src/inventory.py", "src/reporting.py", "tests/test_reporting.py")
        argv = ("python", "-m", "unittest", "tests.test_reporting")
        baseline_tests = 2
    elif workload_id == "w4-regression-prone":
        (root / "src" / "retry_after.py").write_text(
            "def parse_retry_after(value, now):\n    raise NotImplementedError\n", encoding="utf-8",
        )
        (root / "tests" / "test_retry_after.py").write_text(
            "import unittest\nfrom datetime import datetime, timezone\n"
            "from src.retry_after import parse_retry_after\n\n"
            "class RetryAfterTests(unittest.TestCase):\n"
            "    def test_integer_seconds(self):\n"
            "        now = datetime(2025, 1, 1, tzinfo=timezone.utc)\n"
            "        self.assertEqual(parse_retry_after('120', now), 120)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8",
        )
        criteria = common + (
            "Approved public seam: src.retry_after.parse_retry_after(value, now) -> int | None.",
            "Non-negative integer strings return seconds; zero returns zero; negative and invalid values return None.",
            "A valid HTTP-date returns remaining whole seconds, clamped to zero when in the past.",
            "Use timezone-aware datetime values and the Python standard library only.",
        )
        objective = (
            "Implement parse_retry_after(value, now) for integer seconds and HTTP-date values. "
            "Run exactly: python -m unittest tests.test_retry_after. Modify only the source and its test."
        )
        paths = ("src/retry_after.py", "tests/test_retry_after.py")
        argv = ("python", "-m", "unittest", "tests.test_retry_after")
        baseline_tests = 1
    else:
        raise ValueError(f"unknown TDD workload: {workload_id}")
    (root / ".graphori-rrc.json").write_text(
        json.dumps({"temporary_fixture": True, "workload": workload_id}, sort_keys=True),
        encoding="utf-8",
    )
    _commit(root)
    return TddFixture(
        root, workload_id, objective, paths, paths, argv, criteria,
        frozenset({"approved_test_seams"}), baseline_tests,
    )


def _run_tests(root: Path, argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    command = (sys.executable, *argv[1:]) if argv[0] == "python" else argv
    return subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=60, check=False)


def verify_tdd_fixture(fixture: TddFixture) -> tuple[str, int]:
    """Run a known-good verifier that is not writable by the Worker."""

    code = {
        "w2-tiny-write": (
            "from src.math_utils import add\n"
            "checks=[add(2,3)==5, add(-2,3)==1, add(0,0)==0]\n"
        ),
        "w3-bounded-implementation": (
            "from src.inventory import total_cost\nfrom src.reporting import render_summary\n"
            "items=[{'name':'A','price':12,'quantity':2},{'name':'B','price':5,'quantity':3}]\n"
            "checks=[total_cost(items)==39, total_cost([])==0, render_summary(items)=='2 items / total 39', render_summary([])=='0 items / total 0']\n"
        ),
        "w4-regression-prone": (
            "from datetime import datetime, timezone\nfrom src.retry_after import parse_retry_after\n"
            "now=datetime(2025,1,1,tzinfo=timezone.utc)\n"
            "checks=[parse_retry_after('120',now)==120, parse_retry_after('0',now)==0, parse_retry_after('-1',now) is None, parse_retry_after('bad',now) is None, parse_retry_after('Wed, 01 Jan 2025 00:02:00 GMT',now)==120, parse_retry_after('Tue, 31 Dec 2024 23:59:00 GMT',now)==0]\n"
        ),
    }[fixture.workload_id]
    result = subprocess.run(
        (sys.executable, "-c", code + "\nimport json; print(json.dumps(checks))"),
        cwd=fixture.root, capture_output=True, text=True, timeout=60, check=False,
    )
    if result.returncode != 0:
        return "revise", 1
    checks = json.loads(result.stdout.strip().splitlines()[-1])
    failures = sum(not bool(value) for value in checks)
    return ("pass" if not failures else "revise"), failures


def inspect_test_quality(fixture: TddFixture) -> TestQuality:
    files = sorted((fixture.root / "tests").glob("test_*.py"))
    test_count = 0
    private_count = 0
    mock_count = 0
    public_seen = False
    for path in files:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
        test_count += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_") for node in ast.walk(tree)
        )
        private_count += sum(
            isinstance(node, ast.Attribute) and node.attr.startswith("_")
            and not node.attr.startswith("__") for node in ast.walk(tree)
        )
        mock_count += source.count("unittest.mock") + source.count("from unittest import mock")
        public_seen = public_seen or any(
            name in source for name in ("add", "total_cost", "render_summary", "parse_retry_after")
        )
    return TestQuality(
        regression_test_exists=test_count > fixture.baseline_test_count,
        public_seam_test=public_seen and private_count == 0,
        private_method_test_count=private_count,
        implementation_mock_count=mock_count,
    )


def mutation_detected(fixture: TddFixture) -> bool:
    """Apply one hand-authored semantic mutation in a disposable copy."""

    with tempfile.TemporaryDirectory(prefix="graphori-rrc05b-mutation-") as temp:
        root = Path(temp) / "fixture"
        shutil.copytree(fixture.root, root, ignore=shutil.ignore_patterns(".git", ".graphori"))
        if fixture.workload_id == "w2-tiny-write":
            (root / "src" / "math_utils.py").write_text(
                "def add(a, b):\n    return a - b\n", encoding="utf-8",
            )
        elif fixture.workload_id == "w3-bounded-implementation":
            (root / "src" / "inventory.py").write_text(
                "def total_cost(items):\n    return sum(item['price'] for item in items)\n",
                encoding="utf-8",
            )
        else:
            (root / "src" / "retry_after.py").write_text(
                "def parse_retry_after(value, now):\n"
                "    return int(value) if isinstance(value, str) and value.isdigit() else None\n",
                encoding="utf-8",
            )
        return _run_tests(root, fixture.verification_argv).returncode != 0


def changed_loc(root: Path) -> tuple[int, int, int]:
    result = subprocess.run(
        ("git", "-C", str(root), "diff", "--numstat", "HEAD", "--"),
        capture_output=True, text=True, check=False,
    )
    production = test = files = 0
    for line in result.stdout.splitlines():
        added, deleted, path = line.split("\t", 2)
        amount = (int(added) if added.isdigit() else 0) + (int(deleted) if deleted.isdigit() else 0)
        if path.startswith("tests/"):
            test += amount
        else:
            production += amount
        files += 1
    return production, test, files
