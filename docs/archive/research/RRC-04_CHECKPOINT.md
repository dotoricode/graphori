# RRC-04 Checkpoint

RRC-04 implementation and live collection are complete. Do not rerun the 24
live samples unless the Direct adapter, CLI version, model identity, or baseline
fixture changes.

## State

- Direct Codex: READY
- Direct Claude: READY
- All exact RRC-03 Orca route-strategy keys: BLOCKED and unchanged
- Adaptive routing: disabled
- Benchmark snapshot: unchanged
- PR8: eligible, not started

## Claude fix

The previous degradation was caused by non-interactive Bash permission denial,
not parser/schema corruption. The Claude adapter allows only bounded Python
unittest command families for write Nodes. Before/after sanitized protocol
fixtures are stored beside the report.

## Baseline

- 24/24 process and WorkerReport success
- 24/24 deterministic verification PASS
- 0 scope violations
- 0 rework
- 0 self-report disagreements
- Direct Codex practical break-even lower bound: 12,440 ms
- Direct Claude practical break-even lower bound: 15,652 ms

## Resume point

Focused tests passed (55 tests, 2 skipped), the full suite passed (310 tests,
6 skipped), and compile, diff, and artifact checks passed. PR8 Skill Registry
may use `RRC-04_RESULTS.json` as its no-Skill baseline. Do not modify PR7
routing policy from these samples without a separate decision.
