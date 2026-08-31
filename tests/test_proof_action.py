from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from graphori_core.proof_action import (
    INCOMPLETE, REUSABLE, build_proof_action_key,
)


class ProofActionKeyTests(unittest.TestCase):
    def _key(self, root: Path, **changes):
        values = {
            "workspace_root": root,
            "proof_ids": ("AC-01",),
            "argv": (sys.executable, "-c", "pass"),
            "cwd": ".",
            "input_digest": "sha256:workspace",
            "env": {"GRAPHORI_MODE": "test", "GRAPHORI_LEVEL": "1"},
            "env_allowlist": frozenset({"PATH", "GRAPHORI_MODE", "GRAPHORI_LEVEL"}),
            "permission_profile": "read_only",
            "sandbox_profile": "none",
            "network_policy": "inherited",
            "verifier_identity": "generic-process-exit-v1",
            "base_env": {"PATH": str(Path(sys.executable).parent)},
        }
        values.update(changes)
        return build_proof_action_key(**values)

    def test_mapping_order_does_not_change_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._key(root)
            second = self._key(
                root,
                env={"GRAPHORI_LEVEL": "1", "GRAPHORI_MODE": "test"},
                base_env={"PATH": str(Path(sys.executable).parent)},
            )
        self.assertEqual(first.eligibility, REUSABLE)
        self.assertEqual(first.digest(), second.digest())

    def test_environment_values_are_aggregated_and_never_persisted(self):
        sensitive_marker = "value-that-must-never-be-serialized"
        with tempfile.TemporaryDirectory() as directory:
            key = self._key(
                Path(directory),
                env={"GRAPHORI_MODE": sensitive_marker},
                env_allowlist=frozenset({"PATH", "GRAPHORI_MODE"}),
            )
        serialized = json.dumps(key.to_dict(), sort_keys=True)
        self.assertNotIn(sensitive_marker, serialized)
        self.assertEqual(key.env_names, ("GRAPHORI_MODE", "PATH"))

    def test_interpreter_is_reusable_without_transitive_dependency_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            key = self._key(Path(directory))
        self.assertEqual(key.eligibility, REUSABLE)
        self.assertEqual(key.entry_executable_identity.basename,
                         Path(sys.executable).resolve().name)

    def test_unobservable_entry_executable_is_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            key = self._key(
                Path(directory), argv=("missing-graphori-executable",),
                base_env={"PATH": ""},
            )
        self.assertEqual(key.eligibility, INCOMPLETE)
        self.assertIn("entry_executable_unavailable", key.incomplete_reasons)

    def test_every_declared_action_input_changes_the_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "subdir").mkdir()
            baseline = self._key(root)
            mutations = (
                {"proof_ids": ("AC-02",)},
                {"argv": (sys.executable, "-c", "print('changed')")},
                {"cwd": "subdir"},
                {"input_digest": "sha256:changed"},
                {"env": {"GRAPHORI_MODE": "changed", "GRAPHORI_LEVEL": "1"}},
                {"permission_profile": "workspace_write"},
                {"sandbox_profile": "sandbox-v2"},
                {"network_policy": "disabled"},
                {"verifier_identity": "generic-process-exit-v2"},
            )
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    self.assertNotEqual(baseline.digest(), self._key(root, **mutation).digest())

    def test_entry_executable_content_changes_the_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "verifier"
            executable.write_text("first", encoding="utf-8")
            first = self._key(root, argv=("./verifier",))
            executable.write_text("second", encoding="utf-8")
            second = self._key(root, argv=("./verifier",))
        self.assertNotEqual(first.entry_executable_identity,
                            second.entry_executable_identity)
        self.assertNotEqual(first.digest(), second.digest())


if __name__ == "__main__":
    unittest.main()
