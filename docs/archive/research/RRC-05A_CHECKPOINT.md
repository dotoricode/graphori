# RRC-05A Checkpoint

RRC-05A live collection and analysis are complete. Do not rerun the 22 live
samples unless the pinned Ponytail digest, provider CLI version, model identity,
or W2/W3 fixture changes.

## State

- Ponytail auto-binding: disabled
- Skill policy: collect-only; explicit binding only
- Adaptive model routing: unchanged and disabled
- Model Router and benchmark snapshot: unchanged
- Orca routes: not executed; existing BLOCKED health unchanged

## Skill identity

- Package digest: `sha256:147d4648f0a0644fb7c8c6d2bdd7afa089f7a97ede7cf385214fde3a6c5533ac`
- Local SKILL.md digest: `sha256:40519c9eb29bcbfe225bdf1c3566ecea7916a958f4a65c9ffae2979743cd67e2`
- Mode: `full`
- Git commit provenance: unavailable because the pre-existing user-local copy
  was not a Git checkout. No commit identity was fabricated.

## Result

All 22 samples passed deterministic verification. There were no structured
result failures, scope violations, reworks, plugin installations, hook
executions, replay mismatches, or cross-Attempt Skill contamination.

| Route/workload | Median TTUR delta | LOC delta | Classification |
|---|---:|---:|---|
| Codex W2 | +19.8% | 0% | NO_BENEFIT |
| Codex W3 | +12.3% | 0% | NO_BENEFIT |
| Claude W2 | +7.5% | 0% | NO_BENEFIT |
| Claude W3 | -2.7% | 0% | NO_BENEFIT |

Ponytail remains available only through explicit binding. RRC-05A supplies no
evidence for automatic binding on these models and workloads.

## Resume point

The next independent experiment may be RRC-05B TDD. It must use approved test
seams and evaluate verification/rework reduction rather than reuse Ponytail's
LOC-oriented hypothesis. Do not combine Ponytail and TDD in that experiment.
