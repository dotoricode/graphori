# Direct vs v1-style vs Graphori v2

Measured on 2026-08-28 from source commit
`02fb61d6b130e8c94bd0c90d8f6ad0f5fbcd49b6`.

## Result

All 72 runs passed their visible and hidden tests. All 72 completion claims matched
the hidden result. There were no scope violations, reworks, or infrastructure-unknown
records.

### Codex

`gpt-5.6-terra`, medium; Codex CLI 0.150.1; 12 runs per arm.

| Metric | Direct | v1-style | Graphori v2 |
| --- | ---: | ---: | ---: |
| Hidden tests | 36/36 | 36/36 | 36/36 |
| AI sessions | 12 | 24 | 12 |
| Median TTUR | 29.059 s | 54.683 s | 34.823 s |
| Total / cached / fresh input | 967,834 / 800,512 / 167,322 | 1,614,763 / 1,330,688 / 284,075 | 1,080,869 / 905,984 / 174,885 |
| Output tokens | 11,905 | 19,714 | 15,109 |
| Provider-reported cost | unknown | unknown | unknown |

Compared with v1-style, v2 used 50% fewer sessions, had 36.3% lower median
TTUR, and used 33.1% fewer total input tokens. Compared with Direct, v2 had
19.8% higher median TTUR and 11.7% more total input tokens.

### Claude

`claude-sonnet-5`, medium; Claude Code 2.1.245; 12 runs per arm.

| Metric | Direct | v1-style | Graphori v2 |
| --- | ---: | ---: | ---: |
| Hidden tests | 36/36 | 36/36 | 36/36 |
| AI sessions | 12 | 24 | 12 |
| Median TTUR | 22.723 s | 55.287 s | 23.866 s |
| Total / cached / fresh input | 1,413,288 / 1,228,242 / 185,046 | 2,819,151 / 2,426,808 / 392,343 | 1,413,366 / 1,228,245 / 185,121 |
| Output tokens | 14,659 | 33,394 | 14,534 |
| Provider-reported cost | $1.1322 | $2.3883 | $1.1313 |

Compared with v1-style, v2 used 50% fewer sessions, had 56.8% lower median
TTUR, used 49.9% fewer total input tokens, and had 52.6% lower provider-reported
cost. Compared with Direct, v2 had 5.0% higher median TTUR; input tokens and
provider-reported cost were effectively unchanged.

## Interpretation

The independent second AI did not improve hidden-test correctness in this sample.
Graphori v2 retained the same measured quality with one AI session plus deterministic
verification. Direct remained the fastest strategy for these small tasks. Graphori's
measured value here is replacing an unhelpful second AI review with replayable scope,
journal, and deterministic-verification evidence—not making small Direct work faster.

These are four small deterministic Python fixtures, not production repositories.
`n=12` per provider/arm is useful evidence for this matrix, not a universal performance
claim.

[Protocol](PROTOCOL.md) · [Raw JSONL](raw-results.jsonl) ·
[Calculated result](results.json) · [Runner](run.py) · [Analyzer](analyze.py)
