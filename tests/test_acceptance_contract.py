import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    AcceptanceContractCompiler,
    AcceptanceProof,
    AcceptanceSource,
    Availability,
    ProofObligation,
    RunSpec,
)
from graphori_core.product import ProductPlanCompiler  # noqa: E402


def proof(criterion, obligation_id, verifier, source, *, mandatory=True):
    return AcceptanceProof(
        criterion, ProofObligation(obligation_id, verifier), source, mandatory,
    )


class AcceptanceContractTests(unittest.TestCase):
    def setUp(self):
        self.compiler = AcceptanceContractCompiler()
        self.user = self.compiler.user_proofs(("AC-01: tests pass",))

    def test_layers_accumulate_in_user_repository_deterministic_llm_order(self):
        contract = self.compiler.compile(
            user=self.user,
            repository=(proof(
                "AC-02: policy passes", "repository:policy", "policy-check",
                AcceptanceSource.REPOSITORY,
            ),),
            deterministic=(proof(
                "AC-01: tests pass", "deterministic:tests", "unit-test",
                AcceptanceSource.DETERMINISTIC,
            ),),
            llm=(proof(
                "AC-03: edge cases reviewed", "review:edge-cases", "llm-review",
                AcceptanceSource.LLM,
            ),),
        )
        self.assertEqual(
            tuple(item.source for item in contract.proofs),
            (AcceptanceSource.USER, AcceptanceSource.REPOSITORY,
             AcceptanceSource.DETERMINISTIC, AcceptanceSource.LLM),
        )
        self.assertFalse(contract.used_v2_fallback)

    def test_later_layer_cannot_delete_or_make_a_mandatory_proof_optional(self):
        repository = proof(
            "AC-02: policy passes", "repository:policy", "policy-check",
            AcceptanceSource.REPOSITORY,
        )
        duplicate = proof(
            "AC-02: policy passes", "repository:policy", "policy-check",
            AcceptanceSource.LLM, mandatory=False,
        )
        contract = self.compiler.compile(
            user=self.user, repository=(repository,), llm=(duplicate,),
        )
        selected = next(item for item in contract.proofs
                        if item.proof.obligation_id == "repository:policy")
        self.assertTrue(selected.mandatory)
        self.assertEqual(selected.source, AcceptanceSource.REPOSITORY)

    def test_ambiguous_rewrite_falls_back_to_user_v2_contract(self):
        repository = proof(
            "AC-01: tests pass", "criterion:AC-01", "weaker-check",
            AcceptanceSource.REPOSITORY,
        )
        contract = self.compiler.compile(user=self.user, repository=(repository,))
        self.assertTrue(contract.used_v2_fallback)
        self.assertEqual(contract.fallback_reason, "proof_meaning_conflict")
        self.assertEqual(contract.proofs, self.user)

    def test_changed_criterion_text_falls_back_instead_of_rewriting_user_intent(self):
        changed = proof(
            "AC-01: some tests pass", "repository:tests", "unit-test",
            AcceptanceSource.REPOSITORY,
        )
        contract = self.compiler.compile(user=self.user, repository=(changed,))
        self.assertTrue(contract.used_v2_fallback)
        self.assertEqual(contract.fallback_reason, "criterion_text_conflict")
        self.assertEqual(contract.proofs[0].criterion, "AC-01: tests pass")

    def test_contract_digest_is_stable_across_input_order(self):
        left = proof(
            "AC-02: lint passes", "deterministic:lint", "lint",
            AcceptanceSource.DETERMINISTIC,
        )
        right = proof(
            "AC-03: schema passes", "deterministic:schema", "schema",
            AcceptanceSource.DETERMINISTIC,
        )
        first = self.compiler.compile(user=self.user, deterministic=(left, right))
        second = self.compiler.compile(user=self.user, deterministic=(right, left))
        self.assertEqual(first.digest(), second.digest())


class ProductCompilerAcceptanceTests(unittest.TestCase):
    def test_product_compiler_exposes_contract_without_changing_plan_digest(self):
        compiler = ProductPlanCompiler(availability={
            "gpt-5.6-luna": Availability.AVAILABLE,
        })
        spec = RunSpec(
            "Fix it", "codex", "/workspace",
            acceptance_criteria=("AC-01: focused check",),
        )
        baseline = compiler.compile(
            spec, run_id="run-contract", write_scope=("src/a.py",),
            verification_criteria=("AC-01",),
        )
        strengthened = compiler.compile(
            spec, run_id="run-contract", write_scope=("src/a.py",),
            verification_criteria=("AC-01",),
            llm_acceptance_proofs=(proof(
                "AC-02: edge cases reviewed", "review:edge-cases", "llm-review",
                AcceptanceSource.LLM,
            ),),
        )
        self.assertEqual(baseline.plan.digest(), strengthened.plan.digest())
        self.assertEqual(
            tuple(item.source for item in baseline.acceptance_contract.proofs),
            (AcceptanceSource.USER, AcceptanceSource.DETERMINISTIC),
        )
        self.assertEqual(len(strengthened.acceptance_contract.proofs), 3)


if __name__ == "__main__":
    unittest.main()
