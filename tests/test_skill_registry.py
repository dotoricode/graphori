import json
import os
import stat
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    ActivationScope,
    InvocationPolicy,
    NodeSpec,
    RunPlan,
    SkillBinding,
    SkillCompatibilityCompiler,
    SkillKind,
    SkillManifest,
    SkillNodeContext,
    SkillPolicyEngine,
    SkillPolicyMode,
    SkillRegistry,
    SkillRegistryError,
    TrustLevel,
    ContextBundle,
)


def write_skill(root: Path, name: str = "ponytail", extra: str = "") -> Path:
    source = root / name
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test discipline\n---\n\n# {name}\n{extra}\n",
        encoding="utf-8",
    )
    return source


def manifest(skill_id: str, **changes) -> SkillManifest:
    values = {
        "skill_id": skill_id,
        "name": skill_id,
        "description": "Test discipline",
        "source": "github:example/skills",
        "source_commit": "abc123",
        "source_path": f"skills/{skill_id}",
        "license": "MIT",
        "kind": SkillKind.DISCIPLINE,
        "invocation_policy": InvocationPolicy.MODEL_INVOKED,
        "activation_scope": ActivationScope.ATTEMPT,
        "supported_hosts": ("codex", "claude"),
        "trust_level": TrustLevel.PINNED_APPROVED,
    }
    values.update(changes)
    return SkillManifest(**values)


class SkillRegistryTests(unittest.TestCase):
    def test_folded_yaml_description_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "ponytail"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: ponytail\ndescription: >\n"
                "  Minimal implementation discipline.\n"
                "  Standard library first.\n---\n\n# Ponytail\n",
                encoding="utf-8",
            )
            installed = SkillRegistry(root / "registry").install(
                manifest("ponytail"), source,
            )
            self.assertTrue(installed.content_digest.startswith("sha256:"))

    def test_import_creates_pinned_read_only_snapshot_and_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = write_skill(root / "source")
            registry = SkillRegistry(root / ".graphori" / "skills")

            installed = registry.install(manifest("ponytail"), source)

            self.assertTrue(installed.content_digest.startswith("sha256:"))
            snapshot = registry.snapshot_path(installed.skill_id)
            self.assertEqual((snapshot / "SKILL.md").read_text(encoding="utf-8"),
                             (source / "SKILL.md").read_text(encoding="utf-8"))
            self.assertFalse(os.stat(snapshot / "SKILL.md").st_mode & stat.S_IWUSR)
            lock = json.loads(registry.lock_path.read_text(encoding="utf-8"))
            self.assertEqual(lock["schema_version"], 1)
            self.assertEqual(lock["skills"][0]["commit"], "abc123")
            self.assertEqual(lock["skills"][0]["digest"], installed.content_digest)
            self.assertEqual(registry.get("ponytail"), installed)

    def test_digest_mismatch_missing_skill_and_invalid_frontmatter_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = SkillRegistry(root / "registry")
            source = write_skill(root / "source")
            installed = registry.install(manifest("ponytail"), source)
            snapshot_file = registry.snapshot_path("ponytail") / "SKILL.md"
            snapshot_file.chmod(0o644)
            snapshot_file.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(SkillRegistryError, "SKILL_CONTENT_CHANGED"):
                registry.get("ponytail")
            with self.assertRaisesRegex(SkillRegistryError, "missing SKILL.md"):
                registry.install(manifest("missing"), root / "absent")
            invalid = root / "invalid"
            invalid.mkdir()
            (invalid / "SKILL.md").write_text("# no frontmatter", encoding="utf-8")
            with self.assertRaisesRegex(SkillRegistryError, "frontmatter"):
                registry.install(manifest("invalid"), invalid)

    def test_external_source_requires_commit_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = SkillRegistry(root / "registry")
            source = write_skill(root / "source")
            with self.assertRaisesRegex(SkillRegistryError, "commit"):
                registry.install(replace(manifest("ponytail"), source_commit=""), source)
            target = source / "reference.md"
            target.write_text("reference", encoding="utf-8")
            (source / "linked.md").symlink_to(target)
            with self.assertRaisesRegex(SkillRegistryError, "symlink"):
                registry.install(manifest("linked"), source)

    def test_registry_reopens_from_metadata_without_updating_the_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = write_skill(root / "source")
            registry = SkillRegistry(root / ".graphori" / "skills")
            installed = registry.install(manifest("ponytail"), source)
            reopened = SkillRegistry(root / ".graphori" / "skills")
            self.assertEqual(reopened.get("ponytail"), installed)
            self.assertEqual(reopened.lock_path, root / ".graphori" / "skills.lock.json")

            lock = json.loads(reopened.lock_path.read_text(encoding="utf-8"))
            lock["skills"][0]["commit"] = "different"
            reopened.lock_path.write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(SkillRegistryError, "lock.*mismatch"):
                reopened.get("ponytail")

    def test_scripts_and_hooks_are_inventory_only_and_never_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = write_skill(root / "source")
            script = source / "scripts" / "run.sh"
            script.parent.mkdir()
            marker = root / "executed"
            script.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
            installed = SkillRegistry(root / "registry").install(
                manifest("ponytail", scripts=("scripts/run.sh",), hooks=("post-tool",)),
                source,
            )
            self.assertEqual(installed.scripts, ("scripts/run.sh",))
            self.assertFalse(installed.execution_allowed)
            self.assertFalse(marker.exists())

    def test_declared_package_paths_must_exist_inside_the_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = write_skill(root / "source")
            registry = SkillRegistry(root / "registry")
            with self.assertRaisesRegex(SkillRegistryError, "escapes snapshot"):
                registry.install(
                    manifest("ponytail", referenced_files=("../outside.md",)), source,
                )
            with self.assertRaisesRegex(SkillRegistryError, "is missing"):
                registry.install(
                    manifest("ponytail", scripts=("scripts/missing.sh",)), source,
                )


class SkillCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.compiler = SkillCompatibilityCompiler()
        self.context = SkillNodeContext(
            node_id="impl", task_kind="implementation", host="codex",
            risk="low", preconditions=frozenset(),
        )

    def test_workflow_orchestrator_nested_agent_and_user_only_are_not_auto_bindable(self):
        cases = (
            (manifest("workflow", kind=SkillKind.WORKFLOW), "workflow_skill"),
            (manifest("gajae", kind=SkillKind.ORCHESTRATOR), "orchestrator_skill"),
            (manifest("code-review", requires_nested_agents=True), "requires_nested_agents"),
            (manifest("implement", invocation_policy=InvocationPolicy.EXPLICIT_ONLY),
             "explicit_only"),
        )
        for item, reason in cases:
            with self.subTest(skill=item.skill_id):
                result = self.compiler.check(item, self.context, explicit=False)
                self.assertFalse(result.eligible)
                self.assertIn(reason, result.reasons)

    def test_tdd_requires_approved_test_seams(self):
        tdd = manifest("tdd", preconditions=("approved_test_seams",))
        missing = self.compiler.check(tdd, self.context, explicit=True)
        present = self.compiler.check(
            tdd, replace(self.context, preconditions=frozenset({"approved_test_seams"})),
            explicit=True,
        )
        self.assertFalse(missing.eligible)
        self.assertIn("missing_precondition:approved_test_seams", missing.reasons)
        self.assertTrue(present.eligible)

    def test_ponytail_is_attempt_scoped_and_ultra_is_explicit_only(self):
        ponytail = manifest("ponytail")
        automatic = self.compiler.check(ponytail, self.context, arguments={"mode": "ultra"})
        explicit = self.compiler.check(
            ponytail, self.context, explicit=True, arguments={"mode": "ultra"},
        )
        self.assertEqual(ponytail.activation_scope, ActivationScope.ATTEMPT)
        self.assertFalse(automatic.eligible)
        self.assertIn("ponytail_ultra_explicit_only", automatic.reasons)
        self.assertTrue(explicit.eligible)

    def test_dependency_resolution_is_closed_bounded_and_cycle_safe(self):
        registry = {
            "tdd": manifest("tdd", dependencies=("codebase-design",)),
            "codebase-design": manifest("codebase-design"),
        }
        resolved = self.compiler.resolve("tdd", registry, self.context, explicit=True)
        self.assertEqual(tuple(item.skill_id for item in resolved),
                         ("codebase-design", "tdd"))
        cyclic = {
            "a": manifest("a", dependencies=("b",)),
            "b": manifest("b", dependencies=("a",)),
        }
        with self.assertRaisesRegex(SkillRegistryError, "dependency cycle"):
            self.compiler.resolve("a", cyclic, self.context, explicit=True)
        too_many = {
            "a": manifest("a", dependencies=("b", "c")),
            "b": manifest("b"), "c": manifest("c"),
        }
        with self.assertRaisesRegex(SkillRegistryError, "maximum of 2"):
            self.compiler.resolve("a", too_many, self.context, explicit=True)

    def test_conflicts_fail_closed(self):
        registry = {
            "tdd": manifest(
                "tdd", dependencies=("ponytail",), conflicts_with=("ponytail",),
            ),
            "ponytail": manifest("ponytail"),
        }
        with self.assertRaisesRegex(SkillRegistryError, "conflict"):
            self.compiler.resolve("tdd", registry, self.context, explicit=True)

    def test_two_unrelated_primary_skills_are_rejected(self):
        registry = {"a": manifest("a"), "b": manifest("b")}
        with self.assertRaisesRegex(SkillRegistryError, "one primary"):
            self.compiler.resolve_many(("a", "b"), registry, self.context, explicit=True)


class SkillPolicyAndPlanTests(unittest.TestCase):
    def test_collect_only_selects_nothing_but_explicit_policy_binds_one(self):
        registry = {"ponytail": manifest("ponytail", content_digest="sha256:abc")}
        context = SkillNodeContext(
            node_id="impl", task_kind="implementation", host="codex", risk="low",
        )
        collect = SkillPolicyEngine(SkillPolicyMode.COLLECT_ONLY).decide(
            registry, context,
        )
        explicit = SkillPolicyEngine(SkillPolicyMode.COLLECT_ONLY).decide(
            registry, context, explicit_skills=("ponytail",),
        )
        self.assertEqual(collect.selected, ())
        self.assertEqual(collect.candidates, ("ponytail",))
        self.assertEqual(tuple(item.skill_id for item in explicit.selected), ("ponytail",))

    def test_skill_binding_changes_plan_digest_and_round_trips_immutably(self):
        binding = SkillBinding(
            skill_id="ponytail", name="ponytail", digest="sha256:abc",
            snapshot_path=".graphori/skills/abc/SKILL.md",
            source_commit="abc123", arguments=(("mode", "full"),),
            reason="explicit_request", activation_scope=ActivationScope.ATTEMPT,
        )
        node = NodeSpec(
            "impl", "implementation", "Implement", "Implement safely", "worker",
            skill_bindings=(binding,),
        )
        bound = RunPlan("run", 1, "committed", nodes=(node,))
        plain = RunPlan(
            "run", 1, "committed",
            nodes=(replace(node, skill_bindings=()),),
        )
        self.assertNotEqual(bound.digest(), plain.digest())
        self.assertEqual(RunPlan.from_dict(bound.to_dict()), bound)
        context = ContextBundle.from_node(node)
        self.assertEqual(context.skill_bindings, (binding,))
        with self.assertRaises(FrozenInstanceError):
            binding.reason = "changed"


if __name__ == "__main__":
    unittest.main()
