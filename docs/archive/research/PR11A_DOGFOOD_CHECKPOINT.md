# PR11A Graphori dogfooding checkpoint

- Date: 2026-08-20
- Run: `run-pr11a-dogfood`
- Result: succeeded
- Scope: pre-PR10 journal read-time compatibility only

## Executed graph

```text
Planning / current coordinator
  -> Implementation / Codex / gpt-5.6-terra / medium
  -> Verification / GenericProcess / deterministic unittest
```

Research and Design were omitted. No Skill or premium model was used. The Run
created one LLM Worker Attempt and one deterministic Verifier Attempt; there was
no profitable parallel branch.

## Timing

- Plan preview command: 2.8 seconds, including provider probes
- Worker route total: 506,061 ms
- Deterministic verifier: 92,446 ms
- End-to-end TTUR: 599,532 ms
- Provider first structured event: 6,065 ms

## Result

The Worker added a deterministic read-time compatibility layer, immutable
legacy/current fixtures, provenance, fail-closed metadata checks, and ADR 0011.
The canonical journal remained append-only and the legacy fixture bytes were
unchanged across replay. The parent deterministic Verifier passed the complete
test suite.

The coordinator audit added true fresh-process replay coverage and explicit
malformed/conflicting metadata cases because the Worker tests had described a
same-process object reconstruction as cold-process coverage.

## Product observations

- The minimal team topology and non-premium routing were appropriate.
- Preview titles were too generic to explain the PR11A-specific work.
- No provider progress reached the journal during the 8.4-minute Worker run,
  leaving the product at a generic `running` state until completion.
- `observed_model` and `observed_effort` remained unknown.
- The Codex route reported 2,840,921 input tokens, mostly cached, which is high
  for this bounded change and should be investigated before routine use.
- Acceptance criteria remained embedded in objective prose instead of the
  structured `NodeSpec.acceptance_criteria` field.

PR11B was not started.

## Final verification

```text
focused legacy/dashboard tests: 20 passed
full tests: 360 passed / 6 skipped
compileall: PASS
git diff --check: PASS
```
