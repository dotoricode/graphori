# RRC-05A Ponytail Skill Effectiveness Benchmark

## Contract

- Collect-only; routing and auto-binding remain unchanged.
- Direct Codex and Direct Claude only; Orca was not executed.
- W2/W3 paired AB/BA runs use fresh disposable repositories.
- Correctness and scope are evaluated before latency or LOC.

## Skill provenance

- Skill: `ponytail` / mode `full`
- Package digest: `sha256:147d4648f0a0644fb7c8c6d2bdd7afa089f7a97ede7cf385214fde3a6c5533ac`
- Source revision: `local-sha256:40519c9eb29bcbfe225bdf1c3566ecea7916a958f4a65c9ffae2979743cd67e2`
- Git commit provenance: unavailable; source was an existing user-local copy.
- The immutable content digest, not a fabricated commit, identifies every sample.
- Plugin installation: none; hooks executed: none.

## Results

| Provider | Workload | No-skill TTUR | Ponytail TTUR | Delta | No-skill LOC | Ponytail LOC | Classification |
|---|---|---:|---:|---:|---:|---:|---|
| codex | w2-tiny-write | 21752 ms | 26052 ms | 19.8% | 2 | 2 | no_benefit |
| codex | w3-bounded-implementation | 30635 ms | 34406 ms | 12.3% | 4 | 4 | no_benefit |
| claude | w2-tiny-write | 24899 ms | 26754 ms | 7.5% | 2 | 2 | no_benefit |
| claude | w3-bounded-implementation | 25226 ms | 24545 ms | -2.7% | 4 | 4 | no_benefit |

## Usage observations

| Provider | Workload | No-skill input | Ponytail input | No-skill output | Ponytail output | No-skill cost | Ponytail cost |
|---|---|---:|---:|---:|---:|---:|---:|
| codex | w2-tiny-write | 75588 | 81462 | 488 | 706 | unknown | unknown |
| codex | w3-bounded-implementation | 95938 | 82123 | 823 | 1000 | unknown | unknown |
| claude | w2-tiny-write | 8 | 8 | 651 | 784 | 0.1619 | 0.1827 |
| claude | w3-bounded-implementation | 12 | 8 | 940 | 1012 | 0.1723 | 0.1900 |

## Reliability

- Live samples: 22; effectiveness-eligible: 22
- Ponytail snapshot verified: 11/11
- Ponytail binding rendered: 11/11
- Agent read observation: unknown (provider protocols expose no trustworthy read receipt).
- Median registry resolution/materialization: 3 ms / 10 ms
- Verification failures: 0
- Structured result failures: 0
- Rework: 0; scope violations: 0
- Skill contamination: 0; attempt isolation: 22/22
- Hook execution: 0; plugin installation: 0
- Replay digest mismatch: 0
- Requested effort was medium; observed effort remained unknown on both provider protocols.
- Codex did not report an observed model; Claude reported claude-sonnet-5.
- Usage fields are provider-reported and are not normalized across providers.

## Cross-model conclusion

- W2: no quality or LOC change; Ponytail increased median TTUR on both providers.
- W3: no quality or LOC change; Codex was slower and Claude's small speed difference did not reach the 10% material threshold after the third pair.
- All four provider/workload cells classify as `NO_BENEFIT`.

## Recommendation

- Auto candidate: no.
- Manual use: explicit opt-in remains available, but this benchmark found no measured benefit.
- Disabled conditions: Fast and safety-sensitive Nodes remain excluded by existing policy.
- SkillPolicyEngine, ModelRouter, benchmark priors, and adaptive routing remain unchanged.
