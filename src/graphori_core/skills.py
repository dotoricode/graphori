"""Pinned skill packages and deterministic Node compatibility decisions.

PR8 deliberately treats skills as immutable instruction packages.  It does
not execute package scripts or hooks and does not select skills adaptively.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Iterable, Mapping


class SkillRegistryError(ValueError):
    """A skill package cannot be trusted or compiled safely."""


class SkillKind(str, Enum):
    DISCIPLINE = "discipline"
    WORKFLOW = "workflow"
    ORCHESTRATOR = "orchestrator"
    TOOLING = "tooling"
    REFERENCE = "reference"


class InvocationPolicy(str, Enum):
    MODEL_INVOKED = "model_invoked"
    EXPLICIT_ONLY = "explicit_only"


class ActivationScope(str, Enum):
    ATTEMPT = "attempt"
    NODE = "node"


class TrustLevel(str, Enum):
    BUILTIN = "builtin"
    PINNED_APPROVED = "pinned_approved"
    PROJECT_LOCAL = "project_local"
    USER_LOCAL = "user_local"
    UNTRUSTED = "untrusted"


class SkillPolicyMode(str, Enum):
    COLLECT_ONLY = "collect_only"


@dataclass(frozen=True)
class SkillManifest:
    skill_id: str
    name: str
    description: str
    source: str
    source_commit: str
    source_path: str
    license: str
    kind: SkillKind
    invocation_policy: InvocationPolicy
    activation_scope: ActivationScope
    supported_hosts: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    referenced_files: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    hooks: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    conflicts_with: tuple[str, ...] = ()
    requires_user_interaction: bool = False
    requires_nested_agents: bool = False
    requires_network: bool = False
    requires_shell: bool = False
    mutates_workspace: bool = False
    estimated_context_bytes: int = 0
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    content_digest: str = ""
    performance_status: str = "unmeasured_local"
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if not self.skill_id.strip() or not self.name.strip() or not self.description.strip():
            raise ValueError("skill_id, name, and description must be non-empty")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", self.skill_id):
            raise ValueError("skill_id must be a portable identifier")
        if self.estimated_context_bytes < 0:
            raise ValueError("estimated_context_bytes cannot be negative")
        for name in (
            "supported_hosts", "dependencies", "referenced_files", "scripts", "hooks",
            "preconditions", "conflicts_with",
        ):
            object.__setattr__(self, name, tuple(sorted(set(getattr(self, name)))))
        if self.execution_allowed:
            raise ValueError("PR8 skill scripts and hooks cannot be executable")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, Enum):
                result[name] = value.value
            elif isinstance(value, tuple):
                result[name] = list(value)
            else:
                result[name] = value
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SkillManifest":
        unknown = set(value) - set(cls.__dataclass_fields__)
        if unknown:
            raise SkillRegistryError(f"unknown SkillManifest fields: {sorted(unknown)}")
        data = dict(value)
        data["kind"] = SkillKind(data["kind"])
        data["invocation_policy"] = InvocationPolicy(data["invocation_policy"])
        data["activation_scope"] = ActivationScope(data["activation_scope"])
        data["trust_level"] = TrustLevel(data.get("trust_level", "untrusted"))
        for name in (
            "supported_hosts", "dependencies", "referenced_files", "scripts", "hooks",
            "preconditions", "conflicts_with",
        ):
            data[name] = tuple(data.get(name, ()))
        return cls(**data)


@dataclass(frozen=True)
class SkillBinding:
    """One immutable skill snapshot selected for one planned Attempt."""

    skill_id: str
    name: str
    digest: str
    snapshot_path: str
    source_commit: str
    arguments: tuple[tuple[str, str], ...] = ()
    reason: str = ""
    activation_scope: ActivationScope = ActivationScope.ATTEMPT

    def __post_init__(self) -> None:
        if not self.skill_id or not self.name or not self.digest or not self.snapshot_path:
            raise ValueError("skill binding identity, digest, and snapshot path are required")
        object.__setattr__(self, "arguments", tuple(sorted(set(self.arguments))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "digest": self.digest,
            "snapshot_path": self.snapshot_path,
            "source_commit": self.source_commit,
            "arguments": {key: value for key, value in self.arguments},
            "reason": self.reason,
            "activation_scope": self.activation_scope.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SkillBinding":
        expected = set(cls.__dataclass_fields__)
        unknown = set(value) - expected
        if unknown:
            raise ValueError(f"unknown SkillBinding fields: {sorted(unknown)}")
        arguments = value.get("arguments", {})
        if not isinstance(arguments, Mapping) or not all(
                isinstance(key, str) and isinstance(item, str)
                for key, item in arguments.items()):
            raise ValueError("skill binding arguments must be a string mapping")
        return cls(
            skill_id=str(value["skill_id"]), name=str(value["name"]),
            digest=str(value["digest"]), snapshot_path=str(value["snapshot_path"]),
            source_commit=str(value.get("source_commit", "")),
            arguments=tuple(arguments.items()), reason=str(value.get("reason", "")),
            activation_scope=ActivationScope(value.get("activation_scope", "attempt")),
        )


def _frontmatter(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise SkillRegistryError("SKILL.md cannot be read as UTF-8") from exc
    if not lines or lines[0].strip() != "---":
        raise SkillRegistryError("SKILL.md frontmatter is required")
    try:
        closing = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise SkillRegistryError("SKILL.md frontmatter is not closed") from exc
    values: dict[str, str] = {}
    folded_key = ""
    folded_lines: list[str] = []
    for line in lines[1:closing]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace():
            if not folded_key:
                raise SkillRegistryError("SKILL.md frontmatter is malformed")
            folded_lines.append(line.strip())
            continue
        if folded_key:
            values[folded_key] = " ".join(folded_lines).strip()
            folded_key = ""
            folded_lines = []
        if ":" not in line:
            raise SkillRegistryError("SKILL.md frontmatter is malformed")
        key, raw = line.split(":", 1)
        key, raw = key.strip(), raw.strip().strip("\"'")
        if not key:
            raise SkillRegistryError("SKILL.md frontmatter is malformed")
        if raw in {">", "|"}:
            folded_key = key
        elif raw:
            values[key] = raw
        else:
            raise SkillRegistryError("SKILL.md frontmatter is malformed")
    if folded_key:
        values[folded_key] = " ".join(folded_lines).strip()
    if not values.get("name") or not values.get("description"):
        raise SkillRegistryError("SKILL.md frontmatter requires name and description")
    return values


def _package_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir() or not (root / "SKILL.md").is_file():
        raise SkillRegistryError("skill package is missing SKILL.md")
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise SkillRegistryError("skill packages cannot contain symlinks")
        if path.is_file():
            files.append(path)
    return tuple(sorted(files, key=lambda item: item.relative_to(root).as_posix()))


def _package_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in _package_files(root):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        contents = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return "sha256:" + digest.hexdigest()


def _manifest_digest(manifest: SkillManifest) -> str:
    encoded = json.dumps(
        manifest.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class SkillRegistry:
    """Install and verify immutable, explicitly pinned skill snapshots."""

    def __init__(self, root: os.PathLike[str] | str) -> None:
        self.root = Path(root)
        self.lock_path = self.root.parent / "skills.lock.json"
        self._manifest_dir = self.root / ".manifests"
        self._manifests: dict[str, SkillManifest] = {}
        self._load_manifests()

    def _load_manifests(self) -> None:
        if not self._manifest_dir.is_dir():
            return
        for path in sorted(self._manifest_dir.glob("*.json")):
            manifest = SkillManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
            self._manifests[manifest.skill_id] = manifest

    @staticmethod
    def _external(manifest: SkillManifest) -> bool:
        return manifest.source.startswith(("github:", "http://", "https://", "git+"))

    def snapshot_path(self, skill_id: str) -> Path:
        manifest = self._manifests.get(skill_id)
        if manifest is None:
            raise SkillRegistryError(f"unknown skill: {skill_id}")
        return self.root / manifest.content_digest.removeprefix("sha256:")

    def install(self, manifest: SkillManifest, source_directory: os.PathLike[str] | str
                ) -> SkillManifest:
        source = Path(source_directory)
        files = _package_files(source)
        metadata = _frontmatter(source / "SKILL.md")
        if metadata["name"] != manifest.name:
            raise SkillRegistryError("SKILL.md name does not match SkillManifest")
        if self._external(manifest) and not manifest.source_commit:
            raise SkillRegistryError("external skill source requires a pinned commit")
        for declared in (*manifest.referenced_files, *manifest.scripts):
            relative = Path(declared)
            if relative.is_absolute() or ".." in relative.parts:
                raise SkillRegistryError(f"skill package path escapes snapshot: {declared}")
            if not (source / relative).is_file():
                raise SkillRegistryError(f"declared skill package file is missing: {declared}")
        digest = _package_digest(source)
        installed = replace(
            manifest, content_digest=digest,
            estimated_context_bytes=sum(path.stat().st_size for path in files),
        )
        snapshot = self.root / digest.removeprefix("sha256:")
        self.root.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            temporary = self.root / f".{digest.removeprefix('sha256:')}.tmp"
            if temporary.exists():
                shutil.rmtree(temporary)
            shutil.copytree(source, temporary)
            temporary.replace(snapshot)
            for path in sorted(snapshot.rglob("*"), reverse=True):
                path.chmod(0o555 if path.is_dir() else 0o444)
            snapshot.chmod(0o555)
        self._manifests[installed.skill_id] = installed
        self._write_manifest(installed)
        self._write_lock()
        return installed

    def _write_manifest(self, manifest: SkillManifest) -> None:
        self._manifest_dir.mkdir(parents=True, exist_ok=True)
        path = self._manifest_dir / f"{manifest.skill_id}.json"
        path.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _write_lock(self) -> None:
        entries = [{
            "source": item.source,
            "commit": item.source_commit,
            "path": item.source_path,
            "digest": item.content_digest,
            "manifest_digest": _manifest_digest(item),
            "license": item.license,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "manifest_version": 1,
            "skill_id": item.skill_id,
        } for item in sorted(self._manifests.values(), key=lambda value: value.skill_id)]
        self.lock_path.write_text(
            json.dumps({"schema_version": 1, "skills": entries}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def get(self, skill_id: str) -> SkillManifest:
        try:
            manifest = self._manifests[skill_id]
        except KeyError as exc:
            raise SkillRegistryError(f"unknown skill: {skill_id}") from exc
        self._verify_lock(manifest)
        actual = _package_digest(self.snapshot_path(skill_id))
        if actual != manifest.content_digest:
            raise SkillRegistryError(
                f"SKILL_CONTENT_CHANGED: expected {manifest.content_digest}, got {actual}"
            )
        return manifest

    def _verify_lock(self, manifest: SkillManifest) -> None:
        try:
            value = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SkillRegistryError("skills.lock.json is missing or invalid") from exc
        if not isinstance(value, Mapping) or value.get("schema_version") != 1:
            raise SkillRegistryError("unsupported skills.lock.json schema")
        entries = value.get("skills")
        if not isinstance(entries, list):
            raise SkillRegistryError("skills.lock.json entries are invalid")
        matches = [entry for entry in entries if isinstance(entry, Mapping)
                   and entry.get("skill_id") == manifest.skill_id]
        if len(matches) != 1:
            raise SkillRegistryError("skills.lock.json binding is missing or duplicated")
        entry = matches[0]
        expected = {
            "source": manifest.source,
            "commit": manifest.source_commit,
            "path": manifest.source_path,
            "digest": manifest.content_digest,
            "manifest_digest": _manifest_digest(manifest),
            "license": manifest.license,
            "manifest_version": 1,
            "skill_id": manifest.skill_id,
        }
        for key, expected_value in expected.items():
            if entry.get(key) != expected_value:
                raise SkillRegistryError(f"skills.lock.json mismatch: {key}")

    def manifests(self) -> Mapping[str, SkillManifest]:
        return {skill_id: self.get(skill_id) for skill_id in sorted(self._manifests)}


@dataclass(frozen=True)
class SkillNodeContext:
    node_id: str
    task_kind: str
    host: str
    risk: str
    preconditions: frozenset[str] = frozenset()
    fast_mode: bool = False


@dataclass(frozen=True)
class SkillCompatibility:
    eligible: bool
    reasons: tuple[str, ...] = ()


class SkillCompatibilityCompiler:
    """Purely close and validate the skill graph before dispatch."""

    def check(
            self, manifest: SkillManifest, context: SkillNodeContext, *,
            explicit: bool = False, arguments: Mapping[str, str] | None = None,
            dependency: bool = False) -> SkillCompatibility:
        reasons: list[str] = []
        if manifest.kind is SkillKind.WORKFLOW:
            reasons.append("workflow_skill")
        if manifest.kind is SkillKind.ORCHESTRATOR:
            reasons.append("orchestrator_skill")
        if manifest.kind is SkillKind.TOOLING:
            reasons.append("tooling_execution_disabled")
        if manifest.requires_nested_agents:
            reasons.append("requires_nested_agents")
        if manifest.requires_user_interaction:
            reasons.append("requires_user_interaction")
        if manifest.invocation_policy is InvocationPolicy.EXPLICIT_ONLY and not explicit:
            reasons.append("explicit_only")
        if manifest.supported_hosts and context.host not in manifest.supported_hosts:
            reasons.append(f"unsupported_host:{context.host}")
        for precondition in manifest.preconditions:
            if precondition not in context.preconditions:
                reasons.append(f"missing_precondition:{precondition}")
        mode = (arguments or {}).get("mode", "")
        if manifest.skill_id == "ponytail" and mode == "ultra" and not explicit:
            reasons.append("ponytail_ultra_explicit_only")
        if manifest.skill_id == "ponytail" and context.risk in {
                "critical", "security", "migration", "public_api", "data_integrity"}:
            if mode not in {"", "lite"}:
                reasons.append("ponytail_risk_requires_lite_or_disabled")
        if context.fast_mode and not explicit and not dependency:
            reasons.append("fast_mode_no_automatic_skill")
        if manifest.trust_level not in {TrustLevel.BUILTIN, TrustLevel.PINNED_APPROVED} \
                and not explicit:
            reasons.append("auto_binding_requires_approved_trust")
        return SkillCompatibility(not reasons, tuple(sorted(set(reasons))))

    def resolve(
            self, skill_id: str, manifests: Mapping[str, SkillManifest],
            context: SkillNodeContext, *, explicit: bool = False,
            arguments: Mapping[str, str] | None = None) -> tuple[SkillManifest, ...]:
        return self.resolve_many(
            (skill_id,), manifests, context, explicit=explicit,
            arguments={skill_id: dict(arguments or {})},
        )

    def resolve_many(
            self, skill_ids: Iterable[str], manifests: Mapping[str, SkillManifest],
            context: SkillNodeContext, *, explicit: bool = False,
            arguments: Mapping[str, Mapping[str, str]] | None = None,
            ) -> tuple[SkillManifest, ...]:
        requested = tuple(dict.fromkeys(skill_ids))
        if len(requested) > 1:
            raise SkillRegistryError(
                "only one primary skill may be requested; a second skill must be a dependency"
            )
        resolved: list[SkillManifest] = []
        visiting: list[str] = []

        def visit(skill_id: str, dependency: bool = False) -> None:
            if skill_id in (item.skill_id for item in resolved):
                return
            if skill_id in visiting:
                cycle = " -> ".join((*visiting, skill_id))
                raise SkillRegistryError(f"skill dependency cycle: {cycle}")
            try:
                manifest = manifests[skill_id]
            except KeyError as exc:
                raise SkillRegistryError(f"missing skill dependency: {skill_id}") from exc
            visiting.append(skill_id)
            for child in manifest.dependencies:
                visit(child, True)
            visiting.pop()
            result = self.check(
                manifest, context, explicit=explicit,
                arguments=(arguments or {}).get(skill_id, {}), dependency=dependency,
            )
            if not result.eligible:
                raise SkillRegistryError(
                    f"skill {skill_id} is incompatible: {', '.join(result.reasons)}"
                )
            resolved.append(manifest)

        for skill_id in requested:
            visit(skill_id)
        if len(resolved) > 2:
            raise SkillRegistryError("resolved skill set exceeds the maximum of 2")
        resolved_ids = {item.skill_id for item in resolved}
        for manifest in resolved:
            conflicts = (resolved_ids - {manifest.skill_id}) & set(manifest.conflicts_with)
            if conflicts:
                raise SkillRegistryError(
                    f"skill conflict: {manifest.skill_id} conflicts with {sorted(conflicts)}"
                )
        return tuple(resolved)


@dataclass(frozen=True)
class SkillPolicyDecision:
    candidates: tuple[str, ...] = ()
    selected: tuple[SkillBinding, ...] = ()
    exclusions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


_TASK_CANDIDATES: Mapping[str, tuple[str, ...]] = {
    "research": ("research",),
    "design": ("codebase-design", "domain-modeling"),
    "debugging": ("diagnosing-bugs",),
    "implementation": ("ponytail", "tdd"),
}


class SkillPolicyEngine:
    """Report candidates in PR8; bind only an explicit closed skill set."""

    def __init__(self, mode: SkillPolicyMode = SkillPolicyMode.COLLECT_ONLY) -> None:
        self.mode = mode
        self.compiler = SkillCompatibilityCompiler()

    def decide(
            self, manifests: Mapping[str, SkillManifest], context: SkillNodeContext, *,
            explicit_skills: tuple[str, ...] = (),
            arguments: Mapping[str, Mapping[str, str]] | None = None,
            snapshot_paths: Mapping[str, str] | None = None) -> SkillPolicyDecision:
        candidates: list[str] = []
        exclusions: dict[str, tuple[str, ...]] = {}
        for skill_id in _TASK_CANDIDATES.get(context.task_kind, ()):
            manifest = manifests.get(skill_id)
            if manifest is None:
                continue
            compatibility = self.compiler.check(manifest, context)
            if compatibility.eligible:
                candidates.append(skill_id)
            else:
                exclusions[skill_id] = compatibility.reasons
        if not explicit_skills:
            return SkillPolicyDecision(tuple(candidates), (), exclusions)
        resolved = self.compiler.resolve_many(
            explicit_skills, manifests, context, explicit=True, arguments=arguments,
        )
        bindings = tuple(SkillBinding(
            skill_id=item.skill_id,
            name=item.name,
            digest=item.content_digest,
            snapshot_path=(snapshot_paths or {}).get(
                item.skill_id,
                f".graphori/skills/{item.content_digest.removeprefix('sha256:')}/SKILL.md",
            ),
            source_commit=item.source_commit,
            arguments=tuple(sorted((arguments or {}).get(item.skill_id, {}).items())),
            reason="explicit_request",
            activation_scope=item.activation_scope,
        ) for item in resolved)
        return SkillPolicyDecision(tuple(candidates), bindings, exclusions)
