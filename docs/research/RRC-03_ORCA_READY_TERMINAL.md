# RRC-03 — Orca Ready-Terminal Production Launch Path

Date: 2026-08-18

## Result

The ready-terminal launch strategy is implemented behind an explicit adapter
option, but it is **not eligible for production-default promotion** in the
tested Orca environment.

The implementation preserves the RRC-02 composed-route block and adds launch
strategy to the health identity. It performs this sequence:

```text
terminal create with explicit provider/model/effort argv
→ terminal wait --for tui-idle
→ worker-start --terminal with the exact coordinator handle
→ wait for Worker-authored worker_done
```

There is no automatic transition from composed launch to ready-terminal launch,
no prompt resend, and no post-Dispatch provider fallback.

## Environment

```text
Orca:          1.4.184
runtime ID:    26d74412-b4d4-41e9-9682-bc4073ec15bf
guide digest:  sha256:68e11c5761af128b841d618cd6aa6ca4daac452c92be462fa652cab48273b42f
Codex:         0.147.0
Claude Code:   2.1.220
```

## Graphori changes

- `RouteHealthKey` now includes `launch_strategy`.
- Schema-v1 RRC-02 records load as `orca_composed` only and are never rewritten
  merely by reading them.
- New health writes use schema version 2.
- `OrcaExecutionAdapter` accepts an explicit `OrcaLaunchStrategy`; composed
  remains the default.
- Ready-terminal startup requires an explicit runtime model and constructs a
  provider-specific TUI command with the requested effort.
- `tui-idle` is a hard pre-Dispatch fence. A readiness failure closes the
  Graphori-created terminal and is classified as startup failure.
- Run receipts persist the exact coordinator terminal handle. `worker-start`
  passes it through `--from`, preventing implicit caller drift after creating
  another terminal.
- Resource ownership distinguishes Orca-composed and Graphori-precreated
  terminals. A settled Graphori-owned terminal is closed explicitly.
- Route timing metadata now includes terminal creation, TUI readiness,
  worker-start, delivery wait, ACK, cleanup, and total route time when those
  stages complete.

## Live Codex result

Placement:

```text
requested provider: codex
requested model:    gpt-5.6-luna
requested effort:   medium
observed TUI:       gpt-5.6-luna / medium
```

The Agent created `result.txt` and `python verify_result.py` exited 0. The
Worker then attempted the injected `worker_done` command, but that command's
Orca CLI process reported that it could not connect to the running Orca app.
The coordinator-side `/usr/local/bin/orca status --json` remained healthy and
reachable at the same time.

Therefore:

```text
Task effect:             PASS
local deterministic QA: PASS
Worker-authored done:    FAILED TO DELIVER
Delivery:                NOT OBSERVED
Graphori state:          outcome_unknown
route health:            BLOCKED
```

Graphori did not synthesize `worker_done`, did not ACK a nonexistent Delivery,
and did not rerun the mutation through another route. The exact Dispatch was
stopped explicitly after diagnosis.

## Live Claude result

Placement:

```text
requested provider: claude
requested model:    claude-sonnet-5
requested effort:   medium
observed TUI:       Sonnet 5 / medium
```

The TUI reached `tui-idle`, the Dispatch was created, and Orca injected the
lifecycle/task block. The block remained in the Claude input surface without
starting task execution. No result file and no `worker_done` Delivery appeared.

Therefore:

```text
Task effect:          NOT OBSERVED
Worker-authored done: NOT OBSERVED
Delivery:             NOT OBSERVED
Graphori state:       outcome_unknown
route health:         BLOCKED
```

Graphori did not inject an additional Enter, resend the prompt, or fall back to
Direct Claude. The exact Dispatch was stopped explicitly.

## Route health

```text
Direct Codex / CLI:                  READY       (RRC-01)
Direct Claude / CLI:                 DEGRADED    (RRC-01)
Orca Codex / composed:               BLOCKED     (RRC-02)
Orca Codex / ready-terminal:         BLOCKED     (RRC-03)
Orca Claude / composed:              BLOCKED     (RRC-02)
Orca Claude / ready-terminal:        BLOCKED     (RRC-03)
```

The two Orca strategies remain independently keyed. A future Orca version,
runtime, guide digest, or Agent CLI version moves only the exact affected key
back to `recheck`.

## Performance

The valid Direct baselines remain:

```text
Direct Codex warm median: 33.946 s
Direct Claude warm:       29.658 s
```

Ready-terminal setup reached Graphori's running state in approximately 4.3 s
for Codex and 4.9 s for Claude. Both Attempts then consumed the configured
180-second Delivery window because no authoritative Delivery arrived. A valid
Orca incremental overhead cannot be calculated from failed routes.

## Recommendation

Do not promote ready-terminal to the production default and do not start PR8
under the assumption that Orca execution is healthy. Keep both Orca launch
strategies blocked for the exact tested environment while Direct routes remain
available pre-Dispatch. The next work should be a bounded Orca lifecycle issue
investigation or an Orca version recheck, not a Graphori completion workaround.

## Verification

```text
Focused:        50 tests passed, 1 skipped
Full:           306 tests passed, 6 skipped
compileall:     PASS
git diff --check: PASS
```

The live routes did not reach authoritative Worker completion, so they were not
promoted to verifier PASS or replayed as successful Runs. Existing deterministic
journal/replay coverage remained green.
