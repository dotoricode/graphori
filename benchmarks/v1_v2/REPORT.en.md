# Graphori v1-style and v2 comparison result

In this small controlled comparison, both arms passed all four hidden checks. The v2
candidate used one implementation AI plus deterministic verification instead of a
second AI review.

| Metric | v1-style reconstruction | Graphori v2 candidate | Change |
| --- | ---: | ---: | ---: |
| Hidden checks passed | 4/4 | 4/4 | Same |
| Completion claim matched result | 4/4 | 4/4 | Same |
| Scope violations | 0 | 0 | Same |
| AI calls | 8 | 4 | -50.0% |
| Median completion time | 48.542 s | 32.110 s | -33.9% |
| Total input tokens | 567,584 | 333,681 | -41.2% |
| Cached input tokens | 396,800 | 267,776 | -32.5% |
| Fresh input tokens | 170,784 | 65,905 | -61.4% |
| Output tokens | 4,960 | 3,309 | -33.3% |
| New issues found by the second AI | 0 | Not applicable | — |
| Provider cost | Not recorded | Not recorded | Unknown |

Fresh input is derived as total input minus cached input. Rework was not recorded as a
standard field. Read the [protocol](PROTOCOL.en.md) before generalizing these numbers.
