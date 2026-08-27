# RRC-04 — Direct Route Stabilization and Performance Baseline

Date: 2026-08-18
Mode: collect-only (`adaptive_routing_enabled=false`)
Raw result: `RRC-04_RESULTS.json`

## Result

Both Direct routes satisfy the production READY contract in the tested
environment. Orca routes were not executed and retain their RRC-03 BLOCKED
records.

```text
Direct Codex   READY
Direct Claude  READY
Orca routes    BLOCKED (unchanged, not benchmarked)
```

## Direct Claude diagnosis

Classification: **Graphori provider permission-contract defect**, adjacent to
the requested prompt-contract category rather than a parser, schema, or model
self-report defect.

Before the fix, Claude Code received `acceptEdits`, changed the correct file,
and returned valid structured output. Its exact requested command,
`python -m unittest tests.test_math_utils`, was denied because non-interactive
`acceptEdits` does not authorize Bash. Claude truthfully returned
`status=incomplete`; Graphori's independent verifier passed the resulting file.

The adapter now pre-authorizes only these bounded test command families for
write Nodes:

```text
Bash(python -m unittest *)
Bash(python3 -m unittest *)
```

It does not enable `Bash(*)`, bypass permissions, or reinterpret WorkerReport
after verification. The common completion prompt also states that
`status=succeeded` reports task execution and requested local checks, never
Graphori verification PASS.

After the fix, the sanitized protocol probe had zero permission denials and
returned `status=succeeded`. The baseline supplied four additional identical W2
samples; all four returned a valid succeeded WorkerReport and independent PASS.

## Environment

```text
Codex CLI:   codex-cli 0.147.0
Claude Code: 2.1.220
Codex model: gpt-5.6-luna / medium
Claude model: claude-sonnet-5 / medium
```

Every run used a fresh disposable Git repository. The Graphori working tree was
never a provider write target.

## Performance

Times are milliseconds. Warm values are medians of three one-shot executions.
TTUR includes deterministic verification and cleanup. There was no rework, so
effective time equals TTUR.

| Workload | Codex cold | Codex warm / TTUR | Claude cold | Claude warm / TTUR |
| --- | ---: | ---: | ---: | ---: |
| W1 read-only | 13,292 | 12,341 | 15,476 | 15,545 |
| W2 tiny write | 24,446 | 25,650 | 22,987 | 21,652 |
| W3 bounded implementation | 20,946 | 25,734 | 22,857 | 23,445 |

Warm timing decomposition:

| Workload | Route | first event | process execution | deterministic verification |
| --- | --- | ---: | ---: | ---: |
| W1 | Codex | 342 | 11,620 | 30 |
| W1 | Claude | 1,085 | 13,901 | 32 |
| W2 | Codex | 395 | 24,833 | 102 |
| W2 | Claude | 1,109 | 19,860 | 107 |
| W3 | Codex | 363 | 24,816 | 99 |
| W3 | Claude | 1,129 | 22,020 | 111 |

No provider ranking is inferred. Codex was faster on W1, while Claude was faster
on W2 and W3 in this small sample.

## Quality

```text
Samples:                   24
Process succeeded:         24 / 24
Structured WorkerReport:   24 / 24
WorkerReport succeeded:    24 / 24
Deterministic verification:24 / 24
Scope violations:           0
Rework:                     0
Self-report disagreements:  0
```

Usage was present for all samples. Claude reported a total provider cost of
USD 1.9865565 for its twelve baseline runs. Codex did not report a directly
usable cost, so its cost remains unknown rather than zero.

## Routing inputs

Measured process-to-first-event startup penalty:

```text
Direct Codex:   358 ms
Direct Claude: 1,109 ms
```

Practical parallel break-even lower bound:

```text
Direct Codex:  12,440 ms
Direct Claude: 15,652 ms
```

The lower bound is `warm W1 minimal useful task + median deterministic
verification`. It intentionally excludes unmeasured handoff and fan-in costs,
so a production Scheduler must require a larger expected saving, not treat this
number as a complete orchestration penalty.

## Evidence

- `RRC-04_RESULTS.json`: all bounded telemetry and summaries
- `RRC-04_CLAUDE_PROTOCOL_BEFORE_SANITIZED.jsonl`: permission-denied control
- `RRC-04_CLAUDE_PROTOCOL_SANITIZED.jsonl`: corrected protocol stream
- matching sanitized stderr files

## Recommendation

PR8 may proceed because two production Direct routes are READY and the baseline
contains startup, TTUR, verification, rework, scope, and break-even inputs.
RRC-04 does not change the PR7 Router or enable adaptive routing. PR8 should
compare each Skill against this no-Skill baseline rather than assuming value.

## Verification

```text
Focused:          55 tests passed, 2 skipped
Full:            310 tests passed, 6 skipped
compileall:      PASS
git diff --check: PASS
artifact checks: PASS
```
