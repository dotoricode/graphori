# PR11A.1 dogfooding checkpoint

## Live run

- Run: `run-pr11a1-dogfood`
- Graph: Planning coordinator → one Codex implementation Worker → one
  deterministic process verifier
- Child LLM Agents: 1
- Deterministic verifier processes: 1
- Parallel work: none; the dependency chain was sequential
- Research and Design: omitted
- Skills: none
- Terminal status: succeeded
- Worker route: 404,907 ms
- Verifier route: 103,202 ms
- Time to verified result: about 509,806 ms
- First structured provider event: 2,612 ms
- Input tokens: 2,941,275
- Cached input tokens: 2,819,328
- Newly processed input tokens: 121,947
- Output tokens: 12,908
- Reasoning output tokens: 2,653

## Dogfood findings

The initial Preview still used English generic titles and the live status had no
provider progress events. The only canonical fact during the long call was that
the Worker attempt was running; process liveness and completion percentage were
not observable.

The live invocation embedded `AC-01` through `AC-18` in objective prose. Because
the pre-change CLI only accepted separate `--criterion` flags, the dispatched
plan contained no structured criteria. After the implementation, a plan-only
check extracted all 18 explicit IDs and delivered them to both Implementation
and Verification `NodeSpec` values.

The post-run audit found and fixed two unsafe shortcuts:

1. A passing generic verifier command had been promoted to `PROVEN` for every
   criterion. Criteria now remain `NOT_PROVEN` unless the verifier emits an
   explicit criterion-to-evidence mapping.
2. An event-level `usage: unknown` envelope masked known provider usage. Runtime
   usage now reports total, cached, and newly processed input separately.

## Result

The live Run succeeded and its independent full test command passed. The
post-fix contract was then verified with focused and full local tests. No
commit, push, PR, or PR11B work was performed.
