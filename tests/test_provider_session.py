from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core.provider_session import (
    ProviderContinuation, ProviderSessionHandle, SessionBoundary, VerificationNack,
)
from graphori_core.provider_session_vault import (
    PrivateSessionBinding, ProviderSessionVault,
)


class ProviderSessionContractTests(unittest.TestCase):
    def _boundary(self):
        return SessionBoundary(
            run_id="run-1", node_lineage="i1", role="implementer",
            workspace="/workspace", provider="codex", model="model",
            effort="medium",
            system_prompt_digest="sha256:prompt", tool_policy_digest="sha256:tools",
            permission_profile="workspace_write",
        )

    def test_boundary_digest_is_stable_and_every_field_isolated(self):
        boundary = self._boundary()
        self.assertEqual(boundary.digest(), self._boundary().digest())
        for name in boundary.__dataclass_fields__:
            with self.subTest(name=name):
                changed = replace(boundary, **{name: getattr(boundary, name) + "-changed"})
                self.assertNotEqual(boundary.digest(), changed.digest())

    def test_nack_is_factual_bounded_and_preserves_original_rules(self):
        nack = VerificationNack(
            proof_ids=("AC-01",), command=("python", "-m", "unittest"),
            exit_code=1, evidence_refs=("evidence:failure",),
            workspace_digest="sha256:workspace", summary="failure\n" * 2_000,
        )
        rendered = nack.render()
        self.assertIn("Do not modify, weaken, or bypass", rendered)
        self.assertLess(len(nack.summary), 4_001)
        continuation = ProviderContinuation(
            ProviderSessionHandle(
                "codex", "opaque-session", self._boundary().digest(),
                "attempt:i1:1", True,
            ),
            nack,
        )
        self.assertTrue(continuation.handle.resumable)

    @unittest.skipUnless(
        ProviderSessionVault.secure_storage_supported(),
        "secure dir-fd storage is unavailable",
    )
    def test_private_vault_hides_raw_provider_id_and_checks_every_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = ProviderSessionVault(temporary)
            binding = PrivateSessionBinding(
                provider="codex", provider_session_id="raw-provider-secret",
                boundary_digest="sha256:boundary", attempt_id="attempt:i1:1",
                observed_model="model",
            )
            opaque = vault.put("run-1", binding)
            self.assertNotIn("raw-provider-secret", opaque)
            target = (Path(temporary) / ".graphori" / "runs" / "run-1"
                      / "private" / "sessions" / f"{opaque}.json")
            self.assertEqual(target.stat().st_mode & 0o077, 0)
            self.assertEqual(
                vault.resolve(
                    "run-1", opaque, provider="codex",
                    boundary_digest="sha256:boundary", attempt_id="attempt:i1:1",
                ),
                binding,
            )
            self.assertIsNone(vault.resolve(
                "run-1", opaque, provider="claude",
                boundary_digest="sha256:boundary", attempt_id="attempt:i1:1",
            ))
            self.assertIn("raw-provider-secret", json.loads(target.read_text()).values())
            vault.clear_run("run-1")
            self.assertFalse(target.exists())

    @unittest.skipUnless(
        hasattr(os, "symlink") and ProviderSessionVault.secure_storage_supported(),
        "secure symlink-resistant storage is unavailable",
    )
    def test_private_vault_rejects_symlink_escape_without_touching_external_files(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as outside:
            workspace = Path(temporary)
            sessions = workspace / ".graphori" / "runs" / "run-1" / "private"
            sessions.mkdir(parents=True)
            sessions.joinpath("sessions").symlink_to(outside, target_is_directory=True)
            marker = Path(outside) / ("a" * 32 + ".json")
            marker.write_text("external", encoding="utf-8")
            vault = ProviderSessionVault(workspace)
            binding = PrivateSessionBinding(
                provider="codex", provider_session_id="raw-provider-secret",
                boundary_digest="sha256:boundary", attempt_id="attempt:i1:1",
                observed_model="model",
            )

            with self.assertRaises(OSError):
                vault.put("run-1", binding)
            self.assertIsNone(vault.resolve(
                "run-1", "a" * 32, provider="codex",
                boundary_digest="sha256:boundary", attempt_id="attempt:i1:1",
            ))
            vault.clear_run("run-1")
            self.assertEqual(marker.read_text(encoding="utf-8"), "external")
            self.assertEqual(
                sorted(path.name for path in Path(outside).iterdir()), [marker.name],
            )


if __name__ == "__main__":
    unittest.main()
