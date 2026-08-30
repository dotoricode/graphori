# Graphori Sprout

**Run one path. Test it. Expand only if it passes.**

Sprout is Graphori's opt-in proof-driven execution policy. A completed node does not
unlock more work by itself. A persisted artifact must close the declared proof
obligations for the next transition.

## Why it exists

A fixed graph spends work on branches before it knows whether the path is valid.
Sprout first proves one end-to-end pilot, then activates only nodes that close an
outstanding proof. This is a resource-efficiency design: better structure should
replace brute-force scale where the evidence supports it.

The analogy to DeepSeek is limited and deliberate. Graphori does not train a model.
It transfers two system ideas: sparse activation and reliable rule-based feedback.

## The invariant

> An artifact with an open, failed, or unknown proof obligation cannot authorize
> fan-in or commit. Every dynamically expanded node must close at least one named
> obligation.

An artifact carries:

```text
payload reference
raw artifact lineage
declared claims
open proof obligations
verifier results
evidence references
```

The executor is independent of the proof contract. It may be an agent, a process,
a verifier, a control node, or a human.

## Three authorities

- `EXPAND`: a qualified pilot may add an immutable plan revision.
- `FAN_IN`: only qualified branch artifacts may enter synthesis.
- `COMMIT`: a qualified synthesis may cause a reversible external effect.
  Irreversible Sprout commit is rejected in this version.

`ProofFrontier.route` computes a deterministic candidate cover within a branch budget.
It first minimizes parallel critical-path cost, then total cost and node count. A
failed proof selects a bounded repair; an unknown proof escalates. The decision has
canonical JSON and a digest, so the same inputs replay identically.
Exact search is bounded to 32 candidates and a branch budget of four by default;
larger searches fail closed to escalation instead of consuming unbounded coordinator time.
`route_if_profitable` compares the existing static route with pilot-plus-expansion
using declared costs, WIP, dependency, and scope-conflict constraints. It returns
`use_static` when the pilot cannot beat the absolute and relative gain thresholds, so
sparse execution is never mandatory. `authorize` is a pure planning evaluator: its
trusted digest set is a caller-owned boundary, not proof that Graphori read a journal.

## Runtime seam

`NodeSpec.requires_proofs` gates dispatch. `NodeSpec.closes_proofs` names the proofs
produced when that node reaches canonical PASS. A proof has one producer in a plan.
The scheduler derives proof state from the journal-backed node projection and never
turns process exit into evidence by itself.

Plans marked `proof_policy="sprout-1"` enforce producer existence, proof-complete fan-in,
and proof-gated reversible external commit through the production scheduler, execution
engine, and journal. Dynamic `EXPAND` and its performance gate are currently programmatic
core APIs: the default
CLI compiler does not invent proof obligations or rewrite a running plan. Callers must
establish their own trusted artifact boundary and explicitly declare the proof contract.

The first implementation intentionally omits online learning, a general proof DSL,
automatic verifier invention, distributed graph rewriting, and automatic policy
promotion. Those features would make the trust boundary larger before the core
mechanism has production evidence.

## Limits

Sprout enforces declared obligations; it cannot prove that the contract is complete.
Subjective work or work without a reliable verifier must remain `unknown` and reach a
human gate. The controlled policy benchmark models node latency; it is not a provider
wall-clock or token benchmark.

[한국어](SPROUT.ko.md) · [Benchmark](../../benchmarks/sprout/REPORT.md)
