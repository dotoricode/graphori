# PR10 canonical Dashboard checkpoint

- Date: 2026-08-20
- Scope: canonical read model and existing Live Office integration only

```text
canonical journal
  -> StateReducer
  -> CanonicalRunProjection v3
       -> Engine snapshot
       -> graphori status/replay
       -> Dashboard snapshot/SSE
       -> Live Office
```

The removed `DashboardStore._projection()` previously interpreted event types
and could disagree with Engine replay. DashboardStore now cold-replays the same
reducer and projection builder. Connection age remains a transient transport
field and is excluded from the digest.

The published Scheduler policy is replayed with the plan so mid-run `ready`,
`waiting`, and `blocked` decisions produce the same projection digest in a new
process. The Live Office uses canonical team IDs and attempt assignments. Its eleven
characters remain a presentation pool; the inspector reports the actual Agent
count, Node route/model/effort/Skills, dependencies, execution outcome,
independent verification, timing, evidence references, gates, and graph edges.

Pre-PR10 journals lacking both embedded and sidecar RunSpec/RunPlan metadata are
rejected rather than guessed. Their migration belongs to PR11.

Verification at completion:

```text
focused: 84 passed
full: 354 passed / 6 skipped
compileall: PASS
git diff --check: PASS
UI static detector: PASS
```
