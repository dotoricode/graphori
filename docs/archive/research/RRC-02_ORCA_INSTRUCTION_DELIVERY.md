# RRC-02 — Orca Instruction Delivery / Lifecycle Isolation

## Result

RRC-02 isolated the Orca failure before Graphori Worker completion semantics.
For both Codex and Claude, a freshly composed `worker-start` returned
`stage=input_accepted` before the newly launched TUI was ready. The injected
lifecycle preamble was observable, but the sentinel Task had no filesystem
effect and no `worker_done` was emitted.

The same Task succeeded when the Agent terminal was created first, fenced with
the official `terminal wait --for tui-idle` signal, and then attached to
orchestration with `worker-start --terminal` and the exact worktree selector.
Both ready-terminal probes created the sentinel and emitted a valid
Worker-authored `worker_done`.

The root cause is therefore classified as an Orca composed-start readiness
race, not model execution latency, terminal transport failure, Graphori
delivery correlation failure, or missing Worker completion capability.

## Environment

```text
Date:          2026-08-18
OS:            macOS / darwin
Orca:          1.4.184
Runtime:       26d74412-b4d4-41e9-9682-bc4073ec15bf
Guide digest:  sha256:68e11c5761af128b841d618cd6aa6ca4daac452c92be462fa652cab48273b42f
Codex CLI:     0.147.0
Claude Code:   2.1.220
```

The checkpoint environment was Orca 1.4.182 with a different runtime. Because
the version, runtime ID, and guide digest are part of the route-health key,
1.4.184 correctly entered `RECHECK` rather than inheriting the earlier block.

The installed version-matched guides were read from the selected executable:

```text
/usr/local/bin/orca skills get orca-cli
/usr/local/bin/orca skills get orchestration
```

## Three-arm results

| Arm | Codex | Claude |
|---|---|---|
| Direct | READY, RRC-01 baseline | DEGRADED, RRC-01 baseline |
| Orca terminal-only | Sentinel created | Sentinel created |
| Orca fresh orchestration | No sentinel; no `worker_done` | No sentinel; no `worker_done` |
| Orca already-ready terminal | Sentinel + `worker_done` | Sentinel + `worker_done` |

The Direct rows reuse the already completed RRC-01 live baseline. RRC-02 did
not spend another provider run merely to duplicate those measurements.

## Root cause by provider

### Codex

Terminal-only control succeeded after `tui-idle`, proving Orca terminal input
transport can deliver a prompt to Codex.

Fresh orchestration returned:

```text
task:       task_1dbf47ed04a2
dispatch:   ctx_2b3cf2f0c03e
terminal:   term_b89446f2-bc21-43cf-aa69-aafea1dedfee
stage:      input_accepted
```

The bounded terminal evidence contained a partially injected lifecycle
preamble during Codex MCP/TUI initialization. The sentinel was absent and the
Task instruction was not acted on. The Dispatch was stopped explicitly; it was
not released or promoted to Worker success.

Already-ready orchestration returned:

```text
task:       task_c8af7c542d71
dispatch:   ctx_540b514f4941
delivery:   delivery_4ff3c10bc62b
sentinel:   rrc02-received-ready-codex.json
elapsed:    approximately 17 seconds from dispatch to worker_done
```

This proves that Codex has valid lifecycle capability once readiness is fenced.

### Claude

Terminal-only control also created the sentinel, so the terminal transport is
not the blocker.

Fresh orchestration returned:

```text
task:       task_7ac7bca38e42
dispatch:   ctx_2eb5a9c249dd
terminal:   term_d7594538-5cd0-4c07-a977-22ad60387baf
stage:      input_accepted
```

The lifecycle preamble was visible in the terminal, including a redacted
Dispatch capability, but the Task had no filesystem effect. No completion was
attempted. This Dispatch was also stopped explicitly without release.

Already-ready orchestration returned:

```text
task:       task_7b91235693b8
dispatch:   ctx_55cdcab3911c
delivery:   delivery_77c355c15d86
sentinel:   rrc02-received-ready-claude.json
elapsed:    approximately 23 seconds from dispatch to worker_done
```

Claude therefore shows the same composed-start readiness race as Codex.

## Timeline

Unknown timestamps remain unreported rather than estimated. Orca's durable
Task/Dispatch timestamps provide these bounded sequences.

### Codex fresh orchestration

```text
01:37:02Z  task created
01:37:10Z  dispatch created; worker-start reports input_accepted
~15s       no sentinel, no worker_done, no Delivery
            lifecycle preamble visible during TUI initialization
final       worker-stop; no worker-release
```

### Codex already-ready orchestration

```text
terminal created
terminal wait --for tui-idle succeeds
01:38:29Z  task created
01:38:45Z  dispatch created
01:39:02Z  worker_done created and Delivery observed
            sentinel content verified
            external terminal retained by Orca, Delivery acknowledged
            exact diagnostic terminal then closed explicitly
```

### Claude fresh orchestration

```text
01:41:15Z  task created
01:41:18Z  dispatch created; worker-start reports input_accepted
~15s       no sentinel, no worker_done, no Delivery
            lifecycle preamble visible, Task effect absent
final       worker-stop; no worker-release
```

### Claude already-ready orchestration

```text
terminal created
terminal wait --for tui-idle succeeds
01:42:38Z  task created
01:42:45Z  dispatch created
01:43:01Z  worker_done created and Delivery observed
            sentinel content verified
            external terminal retained by Orca, Delivery acknowledged
            exact diagnostic terminal then closed explicitly
```

## Instruction delivery and lifecycle verdict

```text
Terminal transport / Codex:          PASS
Terminal transport / Claude:         PASS
Fresh worker readiness / Codex:       FAIL
Fresh worker readiness / Claude:      FAIL
Lifecycle preamble availability:      PASS when TUI is ready
Worker completion authority:          PASS when TUI is ready
Delivery correlation:                 PASS for both ready-terminal probes
Dispatch capability missing:          NOT REPRODUCED on Orca 1.4.184
```

The earlier `Dispatch capability is missing` symptom is not the active failure
on this environment. The ready-terminal probes emitted accepted Worker-owned
completion messages, proving the capability exists when the full preamble is
delivered to a ready TUI.

## Graphori changes

### Truthful unsettled resource handling

The Orca adapter no longer calls `worker-release` when completion authority is
unconfirmed. It records resource disposition as `unknown` and retains the
runtime handle for explicit inspection, stop, or later reconciliation.

### Post-dispatch unknown retry isolation

`GraphExecutionEngine` no longer automatically retries every
`outcome_unknown`. Automatic retry remains available only for the existing
explicitly retryable timeout/startup classifications. An Attempt that reached
dispatch and later became unknown is not silently executed through another
route.

### Diagnostic classification

RRC-02 adds explicit instruction/lifecycle evidence and corrects the distinction
between an Agent merely being ready, an input being accepted, the Task having a
filesystem effect, and Worker completion being delivered.

No Graphori coordinator sends `worker_done` on behalf of a Worker. Exit code 0
is still not Worker completion or verification PASS.

## Why no automatic resend was added

A timer-based fallback such as:

```text
worker-start
wait 10 seconds
terminal send the Task again
```

is unsafe. A delayed original input could arrive after the fallback, causing a
write Node to execute twice. The adapter cannot prove that the original input
was lost, so Graphori leaves the post-dispatch Attempt unknown.

The safe ready-terminal recipe is useful diagnostic evidence, but replacing the
composed launcher in production would also need to preserve provider model and
effort placement without silently changing PR7 routing. That broader launch
contract is not introduced in RRC-02.

## Route health and circuit breaker

The exact environment keys are recorded in
`RRC-02_ROUTE_HEALTH.json`.

```text
Direct Codex:   READY
Direct Claude:  DEGRADED (RRC-01 WorkerReport self-report mismatch)
Orca -> Codex:  BLOCKED
Orca -> Claude: BLOCKED
```

For a Node that has not started, a matching BLOCKED Orca route can be excluded
and a precomputed Direct route may be selected. Once an Orca Dispatch has
started and its outcome is unknown, automatic Direct reexecution is forbidden.

The block is scoped, not permanent. It resets to `RECHECK` when any of these
change:

- Orca version
- Orca runtime ID
- version-matched guide digest
- Agent provider
- Agent CLI version
- explicit health recheck

## Artifacts

- `RRC-02_RESULTS.json`: structured matrix and observed identities
- `RRC-02_ROUTE_HEALTH.json`: exact environment-scoped circuit state
- `RRC-02_CHECKPOINT.md`: pre-resume implementation checkpoint

The temporary worktrees and exact Agent terminals created by the probes were
removed after each arm. No probe modified the user's dirty Graphori worktree.

Orca's `worker-list` and `worker-show` continue to expose four historical
RRC-02 Dispatch resource records as retained/not-requested metadata even though
`terminal list` contains no RRC-02 terminal and `worktree list` contains no
RRC-02 worktree. The two failed fresh workers were stopped, and the two
already-ready external terminals were closed explicitly after their Deliveries
were handled. RRC-02 does not run a global sweeper or mutate unrelated retained
resources.

## Verification

```text
Focused lifecycle/engine tests: 42 passed, 1 skipped
Full unittest suite:             298 passed, 6 skipped
compileall:                      PASS
git diff --check:                PASS
```

The default Python environment does not contain `pytest`, so the repository's
existing `unittest` runner was used. The full suite emitted one localhost HTTP
fixture connection-reset traceback during shutdown, but exited successfully.
