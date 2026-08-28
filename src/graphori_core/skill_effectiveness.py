"""Collect-only paired Skill effectiveness measurements for RRC-05."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import statistics
import subprocess
from typing import Any, Sequence


NO_SKILL = "no-skill"
PONYTAIL_FULL = "ponytail-full"


class SkillValueClassification(str, Enum):
    AUTO_CANDIDATE = "auto_candidate"
    MANUAL_ONLY = "manual_only"
    NO_BENEFIT = "no_benefit"
    HARMFUL = "harmful"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class DiffMetrics:
    files_changed: int
    lines_added: int
    lines_deleted: int
    new_files: int
    new_dependencies: int


@dataclass(frozen=True)
class SkillBenchmarkSample:
    provider: str
    model: str
    effort: str
    workload: str
    arm: str
    pair_id: str
    repetition: int
    order_index: int
    skill_id: str
    skill_digest: str
    skill_source_revision: str
    skill_args: tuple[str, ...]
    startup_ms: int
    first_event_ms: int
    execution_ms: int
    structured_result_ms: int
    verification_ms: int
    ttur_ms: int
    total_ms: int
    effective_time_ms: int
    worker_report_status: str
    structured_result_valid: bool
    verification: str
    scope_violation: bool
    rework_count: int
    files_changed: int
    lines_added: int
    lines_deleted: int
    new_files: int
    new_dependencies: int
    skill_snapshot_verified: bool
    binding_rendered: bool
    observed_model: str = "unknown"
    observed_effort: str = "unknown"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    estimated_cost: float | None = None
    skill_resolution_ms: int = 0
    skill_materialization_ms: int = 0
    skill_instruction_overhead_ms: int | None = None
    run_plan_digest: str = ""
    replay_digest_matches: bool = False
    attempt_isolated: bool = True
    hooks_executed: bool = False
    plugin_installed: bool = False
    skill_contamination: bool = False
    effectiveness_eligible: bool = True
    failure_kind: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if self.arm not in {NO_SKILL, PONYTAIL_FULL}:
            raise ValueError(f"unknown benchmark arm: {self.arm}")
        for name in (
            "repetition", "order_index", "startup_ms", "first_event_ms", "execution_ms",
            "structured_result_ms", "verification_ms", "ttur_ms", "total_ms",
            "effective_time_ms", "rework_count", "files_changed", "lines_added",
            "lines_deleted", "new_files", "new_dependencies", "skill_resolution_ms",
            "skill_materialization_ms",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "observed_model": self.observed_model,
            "effort": self.effort,
            "observed_effort": self.observed_effort,
            "workload": self.workload,
            "arm": self.arm,
            "pair_id": self.pair_id,
            "repetition": self.repetition,
            "order_index": self.order_index,
            "skill": {
                "id": self.skill_id,
                "digest": self.skill_digest,
                "source_revision": self.skill_source_revision,
                "args": list(self.skill_args),
                "snapshot_verified": self.skill_snapshot_verified,
                "binding_rendered": self.binding_rendered,
                "resolution_ms": self.skill_resolution_ms,
                "materialization_ms": self.skill_materialization_ms,
                "instruction_overhead_ms": self.skill_instruction_overhead_ms,
                "hooks_executed": self.hooks_executed,
                "plugin_installed": self.plugin_installed,
                "contamination": self.skill_contamination,
            },
            "timing": {
                "startup_ms": self.startup_ms,
                "first_event_ms": self.first_event_ms,
                "execution_ms": self.execution_ms,
                "structured_result_ms": self.structured_result_ms,
                "verification_ms": self.verification_ms,
                "ttur_ms": self.ttur_ms,
                "total_ms": self.total_ms,
                "effective_time_ms": self.effective_time_ms,
            },
            "quality": {
                "worker_report": self.worker_report_status,
                "structured_result_valid": self.structured_result_valid,
                "verification": self.verification,
                "scope_violation": self.scope_violation,
                "rework": self.rework_count,
            },
            "diff": {
                "files_changed": self.files_changed,
                "added": self.lines_added,
                "deleted": self.lines_deleted,
                "net_loc": self.lines_added - self.lines_deleted,
                "new_files": self.new_files,
                "new_dependencies": self.new_dependencies,
            },
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "cached_tokens": self.cached_tokens,
                "estimated_cost": self.estimated_cost,
            },
            "run_plan_digest": self.run_plan_digest,
            "replay_digest_matches": self.replay_digest_matches,
            "attempt_isolated": self.attempt_isolated,
            "effectiveness_eligible": self.effectiveness_eligible,
            "failure_kind": self.failure_kind,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SkillBenchmarkSample":
        skill = value["skill"]
        timing = value["timing"]
        quality = value["quality"]
        diff = value["diff"]
        usage = value["usage"]
        return cls(
            provider=value["provider"], model=value["model"], effort=value["effort"],
            workload=value["workload"], arm=value["arm"], pair_id=value["pair_id"],
            repetition=value["repetition"], order_index=value["order_index"],
            skill_id=skill["id"], skill_digest=skill["digest"],
            skill_source_revision=skill["source_revision"],
            skill_args=tuple(skill["args"]), startup_ms=timing["startup_ms"],
            first_event_ms=timing["first_event_ms"], execution_ms=timing["execution_ms"],
            structured_result_ms=timing["structured_result_ms"],
            verification_ms=timing["verification_ms"], ttur_ms=timing["ttur_ms"],
            total_ms=timing["total_ms"], effective_time_ms=timing["effective_time_ms"],
            worker_report_status=quality["worker_report"],
            structured_result_valid=quality["structured_result_valid"],
            verification=quality["verification"], scope_violation=quality["scope_violation"],
            rework_count=quality["rework"], files_changed=diff["files_changed"],
            lines_added=diff["added"], lines_deleted=diff["deleted"],
            new_files=diff["new_files"], new_dependencies=diff["new_dependencies"],
            skill_snapshot_verified=skill["snapshot_verified"],
            binding_rendered=skill["binding_rendered"],
            observed_model=value.get("observed_model", "unknown"),
            observed_effort=value.get("observed_effort", "unknown"),
            input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
            cached_tokens=usage.get("cached_tokens"), estimated_cost=usage.get("estimated_cost"),
            skill_resolution_ms=skill["resolution_ms"],
            skill_materialization_ms=skill["materialization_ms"],
            skill_instruction_overhead_ms=skill.get("instruction_overhead_ms"),
            run_plan_digest=value["run_plan_digest"],
            replay_digest_matches=value["replay_digest_matches"],
            attempt_isolated=value["attempt_isolated"],
            hooks_executed=skill["hooks_executed"],
            plugin_installed=skill["plugin_installed"],
            skill_contamination=skill["contamination"],
            effectiveness_eligible=value["effectiveness_eligible"],
            failure_kind=value["failure_kind"], timestamp=value["timestamp"],
        )


def paired_orders(repetitions: int) -> tuple[tuple[str, str], ...]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    return tuple(
        (NO_SKILL, PONYTAIL_FULL) if index % 2 == 0 else (PONYTAIL_FULL, NO_SKILL)
        for index in range(repetitions)
    )


def _arms(samples: Sequence[SkillBenchmarkSample]
          ) -> tuple[list[SkillBenchmarkSample], list[SkillBenchmarkSample]]:
    eligible = [sample for sample in samples if sample.effectiveness_eligible]
    return (
        [sample for sample in eligible if sample.arm == NO_SKILL],
        [sample for sample in eligible if sample.arm == PONYTAIL_FULL],
    )


def _quality_clean(samples: Sequence[SkillBenchmarkSample]) -> bool:
    return all(
        sample.structured_result_valid
        and sample.verification == "pass"
        and not sample.scope_violation
        and sample.rework_count == 0
        and not sample.skill_contamination
        for sample in samples
    )


def needs_additional_pair(samples: Sequence[SkillBenchmarkSample]) -> bool:
    no_skill, ponytail = _arms(samples)
    if len(no_skill) < 2 or len(ponytail) < 2:
        return True
    if len(no_skill) >= 3 and len(ponytail) >= 3:
        return False
    if not _quality_clean((*no_skill, *ponytail)):
        return False
    pairs: dict[str, dict[str, SkillBenchmarkSample]] = {}
    for sample in (*no_skill, *ponytail):
        pairs.setdefault(sample.pair_id, {})[sample.arm] = sample
    paired_deltas = []
    for values in pairs.values():
        if NO_SKILL not in values or PONYTAIL_FULL not in values:
            continue
        baseline = values[NO_SKILL].ttur_ms
        if baseline:
            paired_deltas.append((values[PONYTAIL_FULL].ttur_ms - baseline) / baseline)
    if len(paired_deltas) >= 2 and max(paired_deltas) - min(paired_deltas) > 0.20:
        return True
    no_median = statistics.median(sample.ttur_ms for sample in no_skill)
    ponytail_median = statistics.median(sample.ttur_ms for sample in ponytail)
    if no_median == 0:
        return False
    return abs(ponytail_median - no_median) / no_median <= 0.10


def classify_skill_value(
        samples: Sequence[SkillBenchmarkSample]) -> SkillValueClassification:
    no_skill, ponytail = _arms(samples)
    if len(no_skill) < 2 or len(ponytail) < 2:
        return SkillValueClassification.INSUFFICIENT_DATA
    if not _quality_clean(ponytail):
        return SkillValueClassification.HARMFUL
    if sum(sample.rework_count for sample in ponytail) > sum(
            sample.rework_count for sample in no_skill):
        return SkillValueClassification.HARMFUL
    no_ttur = statistics.median(sample.ttur_ms for sample in no_skill)
    ponytail_ttur = statistics.median(sample.ttur_ms for sample in ponytail)
    if no_ttur == 0:
        return SkillValueClassification.INSUFFICIENT_DATA
    ratio = ponytail_ttur / no_ttur
    if ratio <= 0.90:
        return SkillValueClassification.AUTO_CANDIDATE
    if ratio > 1.20:
        return SkillValueClassification.HARMFUL
    no_loc = statistics.median(
        sample.lines_added + sample.lines_deleted for sample in no_skill
    )
    ponytail_loc = statistics.median(
        sample.lines_added + sample.lines_deleted for sample in ponytail
    )
    no_dependencies = sum(sample.new_dependencies for sample in no_skill)
    ponytail_dependencies = sum(sample.new_dependencies for sample in ponytail)
    material_reduction = (
        (no_loc > 0 and ponytail_loc <= no_loc * 0.75)
        or ponytail_dependencies < no_dependencies
    )
    if ratio <= 1.10 and material_reduction:
        return SkillValueClassification.MANUAL_ONLY
    return SkillValueClassification.NO_BENEFIT


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", "-C", str(root), *args), capture_output=True, text=True, check=False,
    )


def diff_metrics(root: Path) -> DiffMetrics:
    """Measure the working-tree delta using only Git and the standard library."""

    numstat = _git(root, "diff", "--numstat", "HEAD", "--")
    if numstat.returncode != 0:
        raise ValueError("git diff could not be measured")
    files = 0
    added = 0
    deleted = 0
    for line in numstat.stdout.splitlines():
        left, right, _path = line.split("\t", 2)
        files += 1
        if left.isdigit():
            added += int(left)
        if right.isdigit():
            deleted += int(right)
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode != 0:
        raise ValueError("git status could not be measured")
    untracked = [
        line[3:] for line in status.stdout.splitlines()
        if line.startswith("?? ") and not line[3:].startswith(".graphori/")
    ]
    for relative in untracked:
        path = root / relative
        if path.is_file():
            files += 1
            added += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    dependency_files = {
        "pyproject.toml", "requirements.txt", "requirements-dev.txt", "package.json",
    }
    changed_names = {
        line.split("\t", 2)[-1] for line in numstat.stdout.splitlines()
    } | set(untracked)
    new_dependencies = sum(name in dependency_files for name in changed_names)
    return DiffMetrics(files, added, deleted, len(untracked), new_dependencies)
