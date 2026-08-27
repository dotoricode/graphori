# RRC-01 Routing Reality Check

Date: 2026-08-14
Mode: collect-only (`adaptive_routing_enabled=false`)
Raw result: `RRC-01-RESULTS.json`

## Environment

| Component | Version |
| --- | --- |
| Codex CLI | 0.147.0 |
| Claude Code | 2.1.220 |
| Orca | 1.4.182 |
| Python | 3.14.6 |
| OS | macOS 26.5.2 (x86_64) |

All write samples ran in disposable Git repositories. Orca samples additionally
used explicit disposable Orca worktree selectors. The Graphori working tree was
not used as a live write target.

## Route results

| Route | Cold total | Warm median | Startup | Execution | Cleanup | Health |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Direct Codex | 19.348 s | 33.946 s | 1.327 s | 29.574 s | 0.002 s | READY |
| Direct Claude | 19.764 s | 29.658 s | 1.230 s | 25.629 s | 0.001 s | DEGRADED |
| Orca → Codex | 133.343 s | unavailable | unavailable | unavailable | unavailable | DEGRADED / smoke BLOCKED |
| Orca → Claude | 132.983 s | unavailable | unavailable | unavailable | unavailable | DEGRADED / smoke BLOCKED |

`Startup` is process spawn to the first trustworthy structured provider event.
`Execution` is the interval from that event to the final structured worker
report. These values do not include raw stderr activity.

The Direct Codex and Direct Claude routes each have one cold read-only sample
and two warm bounded-write samples. The two Orca routes have one read-only
sample each because authoritative completion was unavailable; repeating write
samples would only repeat the same control-plane timeout.

## Orca observations

Both Orca routes created a worker in the intended disposable worktree and
forwarded the requested non-premium model and medium effort. Neither route
delivered an authoritative `worker_done` within 120 seconds.

| Segment | Orca → Codex | Orca → Claude |
| --- | ---: | ---: |
| Run setup | 0.810 s | 0.785 s |
| Task setup | 0.857 s | 0.776 s |
| Dispatch start | 2.632 s | 3.079 s |
| Delivery wait | 120.456 s | 120.417 s |
| ACK | not reached | not reached |
| Release | 0.772 s | 0.834 s |

Orca later recorded both dispatches as failed with `Agent exited with code 0`.
Graphori correctly kept both outcomes as `outcome_unknown`; process exit did not
become `worker_finished` or verification PASS.

An exact warm incremental Orca overhead cannot be calculated because neither
Orca route completed. The observed cold timeout deltas were 113.995 seconds for
Codex and 113.219 seconds for Claude, but these are failed-path lower bounds,
not valid orchestration-overhead estimates.

## Quality observations

- Direct Codex: 2/2 bounded-write samples independently verified PASS.
- Direct Claude: 2/2 bounded-write samples independently verified PASS, but
  both structured WorkerReports self-reported `failed`. This is a model-report
  mismatch, not an adapter/protocol failure and not a verification failure.
- Scope violations: 0 after ignoring repository-standard Python bytecode via
  the fixture `.gitignore`.
- Structured result failures: 0 on direct routes; 1 per Orca route because no
  completion report arrived.
- Rework: 0.

## Integration findings fixed during RRC-01

- Claude print-mode `stream-json` requires `--verbose`.
- Claude Code 2.1.220 rejects the draft 2020-12 `$schema` meta-schema marker;
  the Claude launch renderer now removes that marker without changing the
  common WorkerReport contract.
- Provider effort is now forwarded explicitly to both CLIs.
- Process capture records first and last stdout activity without waiting for
  EOF buffering.
- Orca `current` worktree selection follows coordinator binding rather than
  subprocess cwd. RRC now passes the exact disposable Orca worktree selector.

## Router impact

The benchmark snapshot and PR7 routing policy were not changed. This sample is
too small to reorder model priors. Direct Codex is operational; Direct Claude is
operational but its worker self-report mismatch needs a focused follow-up.
Orca routes need an RRC-02 startup/instruction-delivery investigation before
their latency can be used by adaptive routing.

Skill Registry should not use Orca routes as healthy execution paths until that
control-plane issue is resolved.
