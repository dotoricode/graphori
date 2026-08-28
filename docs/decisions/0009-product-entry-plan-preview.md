# ADR 0009: product entry and pre-dispatch Plan Preview

- Status: accepted
- Date: 2026-08-20

## Decision

The `graphori plan|run` command is the production-facing boundary for Graphori
v2. It compiles a user objective into a deterministic `RunPlan`, displays the
five logical teams, Node routes, model/effort placement, Skill bindings, gates,
and dependency edges, and then executes the same plan through
`GraphExecutionEngine`.

The current host remains the Planning coordinator; Graphori does not create a
Planner child Agent. Simple work may use zero child Agents. For graph work, the
Plan Preview is published before the first adapter dispatch, but safe
independent read-only Nodes do not wait for a second user confirmation.

Provider selection is implemented by a small `RoutedExecutionAdapter`. Core
code reads the portable `NodeSpec.adapter` placement and does not branch on
provider class names. Direct Codex and Claude run Worker Nodes. A generic
process adapter runs explicit deterministic verification argv and writes the
verdict consumed by the existing verifier contract.

Downstream Node context is derived from bounded `worker_finished` summaries in
the canonical journal. Engine memory is not a handoff authority. Product runs
persist `run-spec.json` and `run-plan.json` next to the journal so replay and a
future Dashboard can render the exact published plan.

## Consequences

- `worker_finished` remains distinct from verifier PASS.
- Plan Preview and execution cannot silently compile different graphs.
- No external Skill is bound by default.
- Premium Nodes remain blocked until the canonical Human Gate is resolved;
  unrelated ready Nodes may continue.
- The default verifier is intentionally structural when no project-specific
  test command is supplied. Users should provide `--verify-command` for an
  acceptance-level run.
- Dashboard projection unification, resume UX, migration, and release hardening
  remain PR10 and PR11 work.
