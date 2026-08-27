# RRC-05B TDD Skill Effectiveness Benchmark

## Contract

- Collect-only: SkillPolicyEngine, ModelRouter, and adaptive routing are unchanged.
- Direct Codex/Claude only; each workload uses paired AB/BA disposable repositories.
- Both arms receive identical approved public seams and independent verification.
- RED/GREEN and skill-read observations remain unknown unless provider evidence proves them.

## Skill provenance

- Skill: `tdd`
- Package digest: `sha256:f7762d76e11000f502a707b08f3ef292cd13c5e752c2d3bb38a66b69ce9c82f2`
- Source revision: `local-sha256:020e48193f19c303f462ac6c6bf16548f10e3b1f706df562f8fb8f6b3efb43a6`
- Git commit provenance: unavailable; the immutable package digest is authoritative.
- Resolved dependency set: `[tdd]`; scripts/hooks/plugins executed: none.

## Results

| Provider | Workload | No-skill TTUR | TDD TTUR | Delta | Escaped defects N/T | Mutation N/T | Classification |
|---|---|---:|---:|---:|---:|---:|---|
| codex | w2-tiny-write | 27743 ms | 44528 ms | 60.5% | 0/0 | 2/2 | harmful |
| codex | w3-bounded-implementation | 29732 ms | 34662 ms | 16.6% | 0/0 | 2/2 | no_benefit |
| codex | w4-regression-prone | 32434 ms | 57748 ms | 78.0% | 0/0 | 2/2 | harmful |
| claude | w2-tiny-write | 17196 ms | 17693 ms | 2.9% | 0/0 | 2/2 | no_benefit |
| claude | w3-bounded-implementation | 19465 ms | 24003 ms | 23.3% | 0/0 | 2/2 | no_benefit |
| claude | w4-regression-prone | 35741 ms | 42778 ms | 19.7% | 0/0 | 1/2 | manual_only |

## Codex

| Workload | No-skill TTUR | TDD TTUR | Delta | No-skill effective | TDD effective | Classification |
|---|---:|---:|---:|---:|---:|---|
| w2-tiny-write | 27743 ms | 44528 ms | 60.5% | 29063 ms | 46004 ms | harmful |
| w3-bounded-implementation | 29732 ms | 34662 ms | 16.6% | 30416 ms | 35986 ms | no_benefit |
| w4-regression-prone | 32434 ms | 57748 ms | 78.0% | 32946 ms | 58234 ms | harmful |

- Provider classification: `harmful`.
- Escaped defects (no-skill/TDD): 0/0.
- Rework (no-skill/TDD): 0/0.
- Mutation detections (no-skill/TDD): 6/6.

## Claude

| Workload | No-skill TTUR | TDD TTUR | Delta | No-skill effective | TDD effective | Classification |
|---|---:|---:|---:|---:|---:|---|
| w2-tiny-write | 17196 ms | 17693 ms | 2.9% | 17856 ms | 18384 ms | no_benefit |
| w3-bounded-implementation | 19465 ms | 24003 ms | 23.3% | 20139 ms | 24660 ms | no_benefit |
| w4-regression-prone | 35741 ms | 42778 ms | 19.7% | 36338 ms | 43400 ms | manual_only |

- Provider classification: `manual_only`.
- Escaped defects (no-skill/TDD): 0/0.
- Rework (no-skill/TDD): 0/0.
- Mutation detections (no-skill/TDD): 5/6.

## Reliability

- Live samples: 24; eligible: 24.
- Approved seams present: 24/24.
- Unexpected dependencies: 0.
- User questions: 0; nested agents: 0.
- Contamination: 0; scope violations: 0.
- Replay mismatches: 0.

## Workload conclusion

- W2: quality was identical; TDD was harmful on Codex and provided no benefit on Claude.
- W3: quality and mutation detection were identical; TDD provided no benefit on either provider.
- W4: Codex was substantially slower with no quality gain. Claude gained one mutation detection but was 19.7% slower, so it is manual-only.

## Recommendation

- Overall TDD classification: `harmful`.
- Fast: OFF.
- Simple implementation: OFF.
- Regression-prone behavior: Codex OFF; Claude explicit manual use only.
- Complex behavior: insufficient data beyond this bounded W4; no automatic binding.
- No automatic binding was enabled by this benchmark.
