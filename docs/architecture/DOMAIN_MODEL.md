# Graphori domain model

This document names concepts that already exist in Graphori. It is not a type
migration, a second graph store, or a promise that each concept needs a public
class.

## Three views of one run

| View | Question | Current representation |
|---|---|---|
| Proof graph | What conditions remain open? | `ProofObligation`, `ProofResult`, and `ProofFrontier` |
| Execution graph | What work runs, and in what order? | `RunPlan` and `NodeSpec` |
| Evidence graph | Which artifacts support which result? | `ProofCarryingArtifact`, evidence IDs, and journal events |

`RunPlan` remains the canonical execution DAG. Proof and evidence views do not
introduce separate mutable graph databases. The append-only journal remains the
authority for replay and completion.

## Identity boundaries

| Concept | Meaning | Existing representation |
|---|---|---|
| Node | Planned work | `NodeSpec.node_id` |
| Executor | Runtime capable of doing the work | execution adapter and routed provider |
| Execution | One attempt to run a Node | attempt/runtime IDs and `ExecutionResult` |
| Session | Provider or adapter context handle | `SessionHandle` |
| Artifact | Output created by an execution | evidence-store artifact |
| Evidence | Artifact or fact used for a verdict | evidence IDs and proof-carrying artifacts |
| Proof | Condition that must be satisfied | `ProofObligation` and acceptance criteria |
| Plan revision | Append-only change after new evidence | RunPlan version and rework events |

A Node identity is not a Session identity. The current adapters may create an
attempt-scoped session for each Node, but that implementation choice does not
make the concepts equivalent. A future repair Node may resume an implementation
session without reusing the Node identity; an independent reviewer must not
inherit that implementation context.

## Change rule

This model was documented against the existing implementation. No identity
collision or correctness defect requiring a type refactor was reproduced, so
the existing public and internal types remain unchanged. Future refactoring
requires a focused reproduction that documentation or a local comment cannot
resolve.
