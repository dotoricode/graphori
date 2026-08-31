# Sprout routing-model benchmark

The audited 1,000-cell model produced a conditional result. An unconditional pilot
was slower than v2 through eight repeated targets and became 7.0% faster at 16.
The final adaptive policy avoided those predicted regressions by retaining v2 until
the declared pilot route crossed its break-even point.

## Modeled latency sensitivity

Median synthetic milliseconds across 40 paired workload/repetition cells per target
count:

| Targets | v1 target review | Graphori v2 | Unconditional pilot | Adaptive Sprout | Static oracle |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 234.0 | **123.5** | 240.0 | **123.5** | 125.0 |
| 2 | 316.5 | 206.0 | 290.0 | 206.0 | **178.0** |
| 4 | 612.0 | 395.0 | 453.0 | 377.5 | **341.0** |
| 8 | 1,103.0 | 776.0 | 779.5 | 703.5 | **666.5** |
| 16 | 2,192.0 | 1,539.0 | 1,431.0 | 1,389.0 | **1,319.0** |

Relative to v2, adaptive Sprout's modeled latency changed by 0.0%, 0.0%, -4.4%,
-9.3%, and -9.7% at 1, 2, 4, 8, and 16 targets. It enabled pilots in 0, 0, 3,
3, and 3 of the 40 paired cells respectively. The stricter gate rejects any pilot
that would increase modeled AI sessions. The compound-cover oracle was faster
at 2–16 targets; at one target, v2 remained 1.5 ms lower.

At 16 targets, adaptive Sprout covered the same 3,520 declared target obligations
with zero invalid fan-in declarations. It used 3,385 activated nodes versus v2's
3,520 (-3.8%), 755 agent nodes versus 800 (-5.6%), and 2,630 process nodes versus
2,720 (-3.3%).

## What this establishes

- The implementation deterministically finds a bounded declared-proof cover.
- The performance gate suppresses a pilot when its own declared estimates predict a
  regression.
- Compound covers reduce modeled work in repeated fixtures after a measurable
  break-even point.

It does not establish provider wall-clock speed, token or cost savings, verifier
correctness, model quality, or production reliability. The gate and benchmark share
the same estimates, so “never slower” is a policy invariant in this model, not an
independent real-world speed result. `declared_proofs_closed` counts metadata coverage,
not executed evidence.

[Protocol](PROTOCOL.md) · [Runner](run.py) · [Analyzer](analyze.py)
