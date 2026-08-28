"""Provider-neutral task and worker-report contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from graphori_core.skills import SkillBinding


_REPORT_FIELDS = frozenset({
    "schema_version", "status", "summary", "files_modified", "evidence", "limitations",
})
_REPORT_STATUSES = frozenset({"succeeded", "failed", "incomplete"})


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be an array of strings")
    return tuple(value)


@dataclass(frozen=True)
class EvidenceReference:
    """One worker-reported evidence reference, not an independent verdict."""

    kind: str
    reference: str

    @classmethod
    def from_mapping(cls, value: Any) -> "EvidenceReference":
        if not isinstance(value, Mapping) or set(value) != {"kind", "reference"}:
            raise ValueError("evidence entries require only kind and reference")
        kind = value.get("kind")
        reference = value.get("reference")
        if not isinstance(kind, str) or not kind:
            raise ValueError("evidence kind must be a non-empty string")
        if not isinstance(reference, str) or not reference:
            raise ValueError("evidence reference must be a non-empty string")
        return cls(kind=kind, reference=reference)


@dataclass(frozen=True)
class WorkerReport:
    """A worker's bounded self-report; never a Graphori verification verdict."""

    schema_version: int
    status: str
    summary: str
    files_modified: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]
    limitations: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Any) -> "WorkerReport":
        if not isinstance(value, Mapping):
            raise ValueError("worker report must be an object")
        unknown = set(value) - _REPORT_FIELDS
        missing = _REPORT_FIELDS - set(value)
        if unknown or missing:
            raise ValueError(
                f"worker report fields mismatch: missing={sorted(missing)} unknown={sorted(unknown)}"
            )
        if value.get("schema_version") != 1:
            raise ValueError("unsupported worker report schema_version")
        status = value.get("status")
        if status not in _REPORT_STATUSES:
            raise ValueError(f"invalid worker report status: {status!r}")
        summary = value.get("summary")
        if not isinstance(summary, str):
            raise ValueError("summary must be a string")
        evidence_value = value.get("evidence")
        if not isinstance(evidence_value, list):
            raise ValueError("evidence must be an array")
        return cls(
            schema_version=1,
            status=status,
            summary=summary,
            files_modified=_string_tuple(value.get("files_modified"), "files_modified"),
            evidence=tuple(EvidenceReference.from_mapping(item) for item in evidence_value),
            limitations=_string_tuple(value.get("limitations"), "limitations"),
        )


@dataclass(frozen=True)
class AgentTaskEnvelope:
    """The minimal provider-neutral context for one one-shot worker session."""

    task_id: str
    attempt_id: str
    team: str
    role: str
    objective: str
    constraints: tuple[str, ...] = ()
    working_directory: str = "."
    read_scope: tuple[str, ...] = ()
    write_scope: tuple[str, ...] = ()
    verification_expectation: str = "Report evidence; do not claim verification PASS."
    requested_model: str = ""
    skill_bindings: tuple[SkillBinding, ...] = ()


def worker_report_schema() -> dict[str, Any]:
    """Return the strict JSON Schema accepted from provider workers."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_REPORT_FIELDS),
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "status": {"type": "string", "enum": sorted(_REPORT_STATUSES)},
            "summary": {"type": "string"},
            "files_modified": {"type": "array", "items": {"type": "string"}},
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "reference"],
                    "properties": {
                        "kind": {"type": "string", "minLength": 1},
                        "reference": {"type": "string", "minLength": 1},
                    },
                },
            },
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
    }


def render_task_prompt(envelope: AgentTaskEnvelope) -> str:
    """Render one concise prompt whose meaning is shared by all CLI providers."""

    def lines(values: tuple[str, ...]) -> str:
        return "\n".join(f"- {item}" for item in values) or "- none"

    role = envelope.role if envelope.role.endswith("worker") else f"{envelope.role} worker"
    verification = envelope.verification_expectation.replace(
        "do not claim verification PASS", "Do not claim verification PASS",
    )
    if envelope.skill_bindings:
        rendered_skills = []
        for binding in envelope.skill_bindings:
            arguments = ", ".join(
                f"{key}={value}" for key, value in binding.arguments
            ) or "none"
            rendered_skills.append(
                f"- {binding.name}\n"
                f"  path: {binding.snapshot_path}\n"
                f"  digest: {binding.digest}\n"
                f"  args: {arguments}"
            )
        skills = (
            "\nSkills for this attempt:\n"
            + "\n".join(rendered_skills)
            + "\nRead each listed SKILL.md before working. Do not discover or invoke "
              "any other skills. Do not execute package scripts or hooks.\n"
        )
    else:
        skills = "\nSkills for this attempt:\n- none\n"
    return f"""You are a {role} for the {envelope.team} team.

Task ID: {envelope.task_id}
Attempt ID: {envelope.attempt_id}
Objective: {envelope.objective}
Working directory: {envelope.working_directory}

Read scope:
{lines(envelope.read_scope)}

Write scope:
{lines(envelope.write_scope)}

Constraints:
{lines(envelope.constraints)}
{skills}
- Do not create or delegate to nested agents.
- Do not load or invoke external skills unless it is listed above.
- Preserve existing user changes and never reset, clean, or roll back the working tree.

Completion contract:
- {verification}
- Return only the final structured WorkerReport required by the supplied JSON schema.
- WorkerReport is a self-report, not a verification verdict.
- status=succeeded reports task execution and requested local checks, never verification PASS.
"""
