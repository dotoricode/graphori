# ADR 0006: v2 adaptive execution policy

- Status: accepted (canonical)
- Date: 2026-08-14
- Supersedes: ADR 0005's verifier-topology, planning ownership, and
  delegation-only portions

## Decision

Graphori keeps `fast`, `standard`, and `critical` as risk modes, but the mode
does not directly equal an agent count.

- Fast: `router -> worker -> observer`. Deterministic checks may run in the
  owning session; no separate verifier actor is created.
- Standard: the same minimal topology by default. A single independent
  verifier is added only for an explicit review trigger such as a milestone,
  public contract, irreversible change, high uncertainty, human gate, or
  `verification_required` policy.
- Critical: one independent verifier and a human gate by default. Two
  verifier branches plus fan-in are created only when
  `parallel_verification=true` records a need for independently produced
  evidence.

`worker_finished`, process exit code zero, heartbeat, and progress never mean
independent verification. Runtime events record the actor that actually made
the decision or observation: router, scheduler, worker, verifier, or human.

The five stable logical team IDs are `planning`, `research`, `design`,
`implementation`, and `verification`. They describe responsibility, not agent
count. A team that is unnecessary for a run is recorded as `omitted` rather
than represented by a fake worker. The current primary agent owns planning and
may execute small work directly when delegation has no expected net benefit.

## Consequences

The compiler no longer creates workers merely to make the graph look busy.
The future Scheduler may choose parallel execution only after checking WIP,
write-scope conflicts, and estimated net wall-time gain. The portable journal
and reducer remain the source of truth; Orca and native hosts remain adapters.
