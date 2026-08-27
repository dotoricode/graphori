# RRC-03 Checkpoint

RRC-03 implementation and live diagnosis are complete. Do not start PR8 from
this checkpoint automatically.

## Implemented

- Route health schema v2 with `launch_strategy`.
- Backward-compatible schema-v1 loading as `orca_composed`.
- Explicit `OrcaLaunchStrategy` adapter selection; composed remains default.
- Ready-terminal create, `tui-idle` fence, exact terminal attach, no resend.
- Provider-specific model/effort launch command.
- Persisted Orca coordinator handle and explicit `worker-start --from`.
- Graphori-precreated resource ownership and bounded terminal cleanup.
- Ready-terminal timing fields.

## Live result

- Codex placement and Task effect passed, but Worker-authored `worker_done`
  failed to connect to Orca. Graphori recorded `outcome_unknown`.
- Claude placement and injection passed, but the injected task did not execute.
  Graphori recorded `outcome_unknown`.
- Both ready-terminal routes remain `BLOCKED` for Orca 1.4.184 runtime
  `26d74412-b4d4-41e9-9682-bc4073ec15bf` and the recorded guide digest.
- No coordinator-authored completion, prompt resend, or post-Dispatch fallback
  was used.

## Resume point

Focused tests passed (50 tests, 1 skipped), the full suite passed (306 tests,
6 skipped), and both `compileall` and `git diff --check` passed. If the Orca
version, runtime ID, guide digest, or Agent version changed, recheck only the
exact route-strategy key. Otherwise do not repeat the 180-second live failures;
use Direct routes or investigate the Orca lifecycle defect separately.
