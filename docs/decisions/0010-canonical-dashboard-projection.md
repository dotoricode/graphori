# ADR 0010: one canonical projection for Engine, CLI, replay, and Dashboard

- Status: accepted
- Date: 2026-08-20

## Decision

Graphori has one read model: `CanonicalRunProjection` schema version 3. The
projection is built from the published `RunSpec`, immutable `RunPlan`, replayed
canonical journal, and `StateReducer`. Engine snapshots, `graphori status`,
`graphori replay`, the Dashboard snapshot endpoint, SSE snapshots, and atomic
published snapshots all consume that contract.

`DashboardStore` no longer interprets event types to create Node state,
progress, verdicts, gates, or terminal status. It replays the reducer and adds
only transient connection/heartbeat age outside the projection digest. The
browser maps canonical team IDs and actual attempt assignments onto the fixed
eleven-character presentation pool. A character is not an Agent identity.

New journals embed `run_spec`, the full published plan, the effective Scheduler
policy, Skill bindings, and an adapter route-health snapshot in lifecycle
events. Sidecar `run-spec.json` and `run-plan.json` remain supported, but a cold
Dashboard process does not require Engine memory or Scheduler configuration.

## Consequences

- CLI, replay, and Dashboard projection digests must match for one journal.
- Execution outcome and independent verification remain separate fields.
- Planning is always represented as the current coordinator with zero child
  Agents unless a future plan explicitly changes that contract.
- Pre-PR10 journals without embedded or sidecar plan metadata fail closed and
  require the PR11 migration path.
- Dashboard mutation actions and schema migration tooling remain outside PR10.
