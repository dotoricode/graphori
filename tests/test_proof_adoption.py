from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

from graphori_core.proof_action import build_proof_action_key
from graphori_core.proof_adoption import ProofAdopter, ProofCandidate


class ProofAdoptionTests(unittest.TestCase):
    def _key(self, root: Path, *, input_digest: str = "sha256:workspace"):
        return build_proof_action_key(
            workspace_root=root,
            proof_ids=("AC-01",),
            argv=(sys.executable, "-c", "pass"),
            cwd=".",
            input_digest=input_digest,
            env={},
            permission_profile="read_only",
            sandbox_profile="none",
            network_policy="inherited",
            verifier_identity="generic-process-exit-v1",
        )

    def _candidate(self, key, *, source_digest: str = "sha256:workspace"):
        return ProofCandidate(
            proof_ids=("AC-01",),
            source_digest=source_digest,
            action_schema=key.schema,
            action_digest=key.digest(),
            evidence_refs=("evidence:test:exit:0",),
            verdict="pass",
        )

    def test_matching_candidate_is_adopted_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            key = self._key(Path(directory))
            candidate = self._candidate(key)
            first = ProofAdopter.decide(
                candidate, current_source_digest="sha256:workspace",
                current_action_key=key,
            )
            second = ProofAdopter.decide(
                candidate, current_source_digest="sha256:workspace",
                current_action_key=key,
            )
        self.assertTrue(first.adopted)
        self.assertEqual(first, second)
        self.assertEqual(candidate.digest(), self._candidate(key).digest())

    def test_source_action_schema_and_verdict_mismatches_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = self._key(root)
            candidate = self._candidate(key)
            cases = (
                (candidate, "sha256:changed", key, "source_changed"),
                (candidate, "sha256:workspace",
                 self._key(root, input_digest="sha256:changed"), "action_key_changed"),
                (replace(candidate, action_schema="future-schema"),
                 "sha256:workspace", key, "action_schema_changed"),
                (replace(candidate, verdict="fail"),
                 "sha256:workspace", key, "candidate_not_pass"),
            )
            for value, source, action, reason in cases:
                with self.subTest(reason=reason):
                    decision = ProofAdopter.decide(
                        value, current_source_digest=source,
                        current_action_key=action,
                    )
                    self.assertFalse(decision.adopted)
                    self.assertEqual(decision.reason, reason)


if __name__ == "__main__":
    unittest.main()
