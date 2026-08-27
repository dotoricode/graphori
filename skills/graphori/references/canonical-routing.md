# Find the canonical document

Read only the canonical document needed for the current question. Paths are relative
to the Graphori repository root.

| Topic | Read first |
| --- | --- |
| Architecture and nodes | `docs/architecture/GRAPHORI_ARCHITECTURE.md` |
| Event ordering and state | `docs/architecture/EVENT_PROTOCOL.md` |
| Snapshot, SSE, stale state, progress | `docs/architecture/DASHBOARD_CONTRACT.md` |
| Windows and macOS portability | `docs/architecture/PORTABILITY_CONTRACT.md` |
| Current stage and scope | `docs/IMPLEMENTATION_PLAN.md` |
| MVP, WIP=1, one verifier, revision limit | `docs/decisions/0005-mvp-simple-single-verifier.md` |
| Design comparison or verification evidence | The relevant file under `docs/design/` or `docs/verification/` |

`docs/decisions/0004-token-aware-fast-mode.md` records an old idea. Do not treat Fast
Mode as Graphori's default. Label documents without execution evidence as plans or
proposals rather than proof of success.
