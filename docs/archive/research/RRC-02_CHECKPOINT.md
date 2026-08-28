# RRC-02 Work Checkpoint

Updated: 2026-08-14 (Asia/Seoul)

> Resumed on 2026-08-18. This checkpoint is retained as historical handoff
> evidence; use `RRC-02_ORCA_INSTRUCTION_DELIVERY.md` and
> `RRC-02_RESULTS.json` for the completed investigation.

This is a continuation checkpoint, not a completion report. Stop here. Do not
start PR8, change routing policy, or run further live Orca probes until the user
asks to resume.

## Resume objective

Continue **RRC-02 Orca Instruction Delivery / Lifecycle Isolation** without
restarting or redesigning PR0-PR7 and RRC-01.

The required outcome is:

1. Isolate the Orca failure stage for Codex and Claude using Direct,
   terminal-only, orchestration, and (when supported) already-ready terminal
   arms.
2. Fix only proven Graphori invocation/correlation/lifecycle bugs.
3. Keep Orca runtime failures isolated without converting process exit success
   into Graphori worker completion.
4. Prevent repeated 120-second failures through an environment-scoped route
   circuit breaker.
5. Produce the final RRC-02 report and evidence. Do not start Skill Registry.

## Repository safety

The working tree contains extensive uncommitted work from PR0-PR7, RRC-01, and
the Live Office work. These changes belong to the user and must not be reset,
cleaned, reformatted wholesale, or reconstructed.

Do not run destructive Git commands. Do not commit, push, or create a PR.

## Skills and Orca contract already inspected

The following skill instructions were read completely for this work:

- `~/.agents/skills/orca-cli/SKILL.md`
- `~/.agents/skills/orchestration/SKILL.md`
- `~/.agents/skills/tdd/SKILL.md`

The installed version-matched guides were also inspected with:

```text
/usr/local/bin/orca skills get orca-cli
/usr/local/bin/orca skills get orchestration
```

Observed environment:

```text
Orca version: 1.4.182
Runtime ID: e890d763-c77f-4305-a9b4-8dcdaaf4149b
```

Important guide findings:

- Terminal input must wait for `terminal wait --for tui-idle` before send.
- Already-ready terminal orchestration is supported through a terminal handle.
- `worker-start` supports `--terminal`.
- A worker without an accepted `worker_done` must not be released as completed.
- On unconfirmed completion, inspect and stop/abandon the worker; do not invent
  completion authority.
- Lifecycle completion must remain Worker-authored.

## RRC-01 baseline

RRC-01 was completed before this checkpoint.

```text
Direct Codex: READY
  cold 19.348s
  warm median 33.946s

Direct Claude: DEGRADED
  cold 19.764s
  warm 29.658s
  deterministic verification passed; WorkerReport self-report failed

Orca -> Codex: BLOCKED
Orca -> Claude: BLOCKED
  no worker_done within 120 seconds; process later exited 0
```

Evidence:

- `docs/research/RRC-01_REPORT.md`
- `docs/research/RRC-01-RESULTS.json`

Last full-suite RRC-01 baseline:

```text
288 passed / 6 skipped
```

## RRC-02 code already added

### Lifecycle diagnostics and circuit breaker

New file:

- `src/graphori_core/orca_lifecycle.py`

It currently defines:

- `LifecycleFailureStage`
- `OrcaLifecycleTimeline`
- `InstructionDeliveryEvidence`
- `RouteHealthStatus`
- `RouteHealthKey`
- `RouteHealthRecord`
- `RouteCircuitBreaker`

The circuit key is scoped by Orca version, runtime ID, guide digest, provider,
and agent version. Exact blocked routes are excluded before dispatch, while a
changed environment returns to `RECHECK`. Post-dispatch automatic fallback is
forbidden.

Public exports were added to:

- `src/graphori_core/__init__.py`

Tests were added in:

- `tests/test_orca_lifecycle_diagnostics.py`

These six tests passed before the most recent unverified test edits.

### Orca adapter circuit integration

Modified:

- `src/graphori_adapters/orca/execution.py`

`OrcaExecutionAdapter` can now receive a route circuit breaker and exact route
health key. Its probe blocks a matching `BLOCKED` route before dispatch and
records route health evidence.

Test added in:

- `tests/test_orca_execution_adapter.py`
  - `test_blocked_exact_route_fails_probe_before_any_dispatch`

The lifecycle tests plus this adapter test previously passed (`7 passed`).

## Last edits are intentionally unverified

Immediately before stopping, tests were changed to expose two remaining
truthfulness bugs. These changed assertions have **not** been run yet.

In `tests/test_orca_execution_adapter.py`:

- malformed delivery must fail closed without releasing an unsettled worker;
- `Dispatch capability is missing` must not release an unsettled worker;
- both cases expect the active handle to remain available for explicit
  inspection/cancel/reconciliation.

In `tests/test_v2_execution_engine.py`:

- `OutcomeUnknownAdapter` was added;
- the actual test asserting no post-dispatch retry has not yet been added.

The next session must begin with RED tests, not with live Orca execution.

## Proven implementation defects still open

### 1. Unconfirmed Orca worker is released

In `src/graphori_adapters/orca/execution.py`, the no-worker-event path currently
records `outcome_unknown` and then calls `_release(record)`. The installed Orca
guide says an unconfirmed worker must not be released as completed.

`release(session)` also removes dispatch/session records even when the outcome
is unknown. This destroys the handle needed for explicit stop or inspection.

Required minimal correction:

- do not call `_release(record)` when no authoritative worker completion exists;
- retain the handle/binding as unsettled;
- represent resource disposition as unknown or pending;
- allow explicit cancel/stop after final diagnostic inspection.

Do not translate terminal output or exit code 0 into `worker_finished`.

### 2. Engine retries post-dispatch `outcome_unknown`

`GraphExecutionEngine._execute_node` currently retries whenever the resulting
Node state is `outcome_unknown`. This can duplicate a mutation that may already
have happened in Orca.

Required minimal correction:

- automatic retry remains eligible for explicitly retryable startup/timeout
  outcomes under the existing PR3 policy;
- post-dispatch `outcome_unknown` is not automatically retried;
- preserve existing retry tests for genuine timeout/startup failures.

## Exact next steps

1. Add a contract test in `tests/test_v2_execution_engine.py` using
   `OutcomeUnknownAdapter` that proves exactly one dispatch and no retry.
2. Run only the new/changed RED tests:

   ```text
   python -m pytest \
     tests/test_orca_execution_adapter.py \
     tests/test_orca_lifecycle_diagnostics.py \
     tests/test_v2_execution_engine.py -q
   ```

3. Make the smallest Orca adapter lifecycle fix described above.
4. Make the smallest Engine retry-eligibility fix described above.
5. Re-run the narrow tests and preserve PR3 timeout retry behavior.
6. Only after those tests are green, implement the disposable RRC-02 live probe
   harness and perform the 3-arm matrix.

## Planned live probe, not yet implemented

Use a disposable temporary Git repository/worktree and a nonce sentinel file:

```text
rrc02-received-<nonce>.json
{
  "nonce": "...",
  "message": "instruction received"
}
```

Do not mention `worker_done` in the primary task. The sentinel proves task
instruction effect; it does not prove lifecycle completion.

Required arms, independently for Codex and Claude:

1. Direct baseline.
2. Orca terminal-only after `tui-idle` readiness.
3. Orca orchestration through `worker-start`.
4. Already-ready terminal orchestration when supported.

Collect only observable timestamps; unknown values remain `null`. Terminal
transcripts are bounded diagnostic evidence, never canonical completion.

On an orchestration timeout:

- do not call worker release as if completion were accepted;
- inspect bounded status/transcript evidence;
- explicitly stop/abandon the exact dispatch;
- clean only the disposable exact worktree/resource.

Expected final artifacts:

- `scripts/orca_lifecycle_probe.py` (or the smallest equivalent harness)
- `docs/research/RRC-02_RESULTS.json`
- `docs/research/RRC-02_ORCA_INSTRUCTION_DELIVERY.md`
- route-health evidence keyed to the exact environment
- an index entry in `docs/research/README.md`

## Review notes before live execution

Review these details while finishing the narrow unit work:

- `InstructionDeliveryEvidence.stage` currently maps `agent_ready=True` with no
  instruction to `INSTRUCTION_DELIVERED`; verify that this naming/ordering
  reflects the requested diagnostic contract.
- `RouteCircuitBreaker.allows_automatic_fallback` intentionally permits fallback
  only before dispatch, but currently ignores the outcome string. Keep or tighten
  this only with a focused contract test.
- Do not silently fall back from Orca to Direct after an attempt started.
- Direct Claude's WorkerReport self-report issue is out of RRC-02 scope.

## Final verification required after RRC-02 implementation

Run narrow tests first, then:

```text
python -m pytest
python -m compileall src tests scripts
git diff --check
```

Report actual results only. A valid RRC-02 completion may still classify both
Orca routes as `BLOCKED` if the runtime lifecycle fault is proven and isolated.
