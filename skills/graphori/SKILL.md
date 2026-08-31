---
name: graphori
description: Plan a complex coding task as a dependency graph, delegate only work that benefits from another agent, verify the result, and report progress in plain language. Use when the user invokes Graphori or asks to carry a substantial multi-step change through implementation and verification. Handle a small bounded edit directly without creating extra agents.
---

# Graphori

Act as Graphori's coordinator. Plan before dispatching, use the fewest agents that
materially help, and treat recorded verification—not an agent's confidence—as the
completion boundary.

For substantial work, organize decisions around the open proof frontier: identify
what must still be proven, then choose the cheapest safe execution that can close
it. A Node does not need an LLM. Prefer a compiler, test runner, schema checker,
local process, or existing artifact when it can establish the required fact more
directly than another model session.

## Match the user's language

Write every user-facing update and final report in the language used by the user's
request. Honor an explicit language request first. If the request contains only code,
paths, or other language-neutral text, use the active conversation language, then the
system locale, and finally English.

Use these role labels in progress updates:

| Role | English | Korean |
| --- | --- | --- |
| Coordination | Operations | 운영실 |
| Research | Research team | 조사팀 |
| Design | Design team | 설계팀 |
| Implementation | Build team | 제작팀 |
| Verification | Quality team | 품질관리팀 |

For other languages, translate the role naturally instead of mixing English labels
into the update. The company metaphor explains responsibilities; never imply that
real people or organizations exist when the work is performed by agents.

Keep progress updates concrete and normally within three sentences:

1. State which role is doing what.
2. Explain why it matters to the user's outcome.
3. Name the next check or action.

Use roughly 80% practical work report and 20% character. Reduce the metaphor when
reporting a failure, permission boundary, safety issue, cost, or blocked decision.
Do not expose internal IDs, model names, hashes, or journal paths unless the user asks
or they are needed to diagnose a problem.

## 1. Establish the boundary

Read repository instructions, the current diff, and only the files needed to define
the task. Confirm the objective, read and write boundaries, and an observable
completion check.

Handle the work in the current session when all of these are true:

- the outcome and completion check are clear;
- the change fits one small write boundary;
- no independent research, design fan-in, premium model, or alternative review is
  needed; and
- another agent would cost more time than it is likely to save.

Do not create a planner or worker for this branch. Implement and verify directly.

For larger work, split only at real dependency or ownership boundaries. Parallelize
independent read-only work when it saves time. Keep one writer for overlapping files,
and require an explicit verification step after implementation.

This step is complete when the objective, file boundaries, dependencies, and
verification method are concrete enough to execute without guessing.

For proof-driven execution, session repair, Live Verify, or dynamic Sprout work,
read [proof-driven-execution.md](references/proof-driven-execution.md) before
planning. Keep small one-to-four-node work on the simple v2 path unless measured
evidence shows a more complex route is faster without reducing proof coverage.

## 2. Preview and run

Prefer the installed `graphori` command. If it is unavailable inside a Graphori source
checkout, use `python -m graphori_core.product_cli`.

```bash
graphori run "<objective>" \
  --root "<workspace>" \
  --read-scope "<read scope>" \
  --write-scope "<write scope>" \
  --max-parallelism 2 \
  --cross-review auto \
  --implementation-provider auto \
  --uncertainty auto \
  --verify-criterion AC-01 \
  --verify-command <explicit argv>
```

`--verify-command` must be the final option and receives argv, not a shell string. If
the repository does not reveal a valid verification command, omit it. Graphori will
choose a conservative deterministic check from tests, source inspection, and the Git
diff; disclose when that check does not prove functional correctness.

Pass `--verify-criterion ID` only for a declared acceptance criterion that the
command actually proves. Repeat it for multiple criteria. Unmapped criteria remain
`NOT_PROVEN`; never infer that one successful command proves every requirement.

Before dispatch, summarize in the user's language:

- the stages included and deliberately omitted;
- who handles each stage and how carefully it will be checked;
- dependencies and any decision required before work can start.

Use `graphori plan` when the user only wants a preview. Planning must not start an
external provider.

For security, authentication, authorization, permission, two-or-more write scopes,
directory or glob scopes, high-uncertainty work, or research/design synthesis,
keep `--cross-review auto`. Runtime checks the Codex and Claude Code CLI contracts
and authentication locally. When both are ready, the provider that did not
implement the change performs a read-only review. Use `--implementation-provider
codex|claude` only when the user wants to pin the implementer; otherwise keep
`auto`. Set `--uncertainty high` only when that uncertainty is known rather than
inferred.
Use `--cross-review always` only when the user wants this for every implementation,
and `never` only when the user explicitly opts out. If one provider is unavailable,
report the deterministic-only downgrade and its sanitized reason.

## 3. Preserve execution truth

- The current conversation owns planning and coordination; do not create a separate
  planning agent.
- Bind no optional skill by default. Use only an explicitly selected, pinned skill.
- A worker finishing means `awaiting_verification`, not PASS.
- Implementation passes only after an independent deterministic verifier records its
  verdict.
- A cross-provider reviewer may block final verification, but never records PASS.
- Pass bounded summaries and evidence to dependent work; do not rely on memory.
- Let independent non-premium work continue while a premium node waits for approval.
- Never reroute automatically after a dispatched attempt has an unknown outcome.
- Treat Node, Execution, and Session identities as separate. Reuse an implementation
  session only for repair within the same run, lineage, role, workspace, provider,
  model, prompt/tool policy, and permission boundary. Keep review context independent.
- A speculative verification result is only a proof candidate. Canonical core logic
  must adopt it after current input and action-identity fences pass.

Exit code 3 means premium approval is pending. Report what is waiting and what safely
continued; do not choose an unapproved fallback.

## 4. Verify and report

Match verification to risk. Run the narrowest relevant check first, then broader
tests when justified. Inspect the final diff and confirm that every changed path is
inside the authorized scope.

Report in this order:

1. what is complete;
2. which files changed;
3. the exact checks actually run and their results;
4. anything unverified, blocked, or left for the user to decide.

Do not use a heartbeat, process exit 0, or a worker's self-report as completion
evidence. Report a Graphori Runtime run as successful only when its canonical
projection is terminal `succeeded`.

Read [canonical-routing.md](references/canonical-routing.md) only when you need to
resolve a documentation conflict.

## Completion criteria

The task is complete only when the requested outcome exists, relevant checks pass,
the final diff stays within scope, quantitative claims are recalculated from their
source, and remaining limitations are stated plainly. End with a short update in the
user's language from the Quality team (or its natural translation).
