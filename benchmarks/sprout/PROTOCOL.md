# Sprout routing-model benchmark protocol

This is a deterministic model of routing policies, not a production performance
benchmark. It executes no provider, node, or verifier. A declared proof is counted as
covered when the selected candidate metadata names it; that is why the metric is
`declared_proofs_closed`, not “tests passed” or “proofs executed.”

## Matrix

- Arms: `v1-target-review`, `graphori-v2`, `sprout-unconditional`,
  `graphori-sprout`, and `oracle-static`.
- Structurally distinct fixtures: regional collection, repository audit, release
  preflight, and API import. They use different obligations, candidate covers, costs,
  executor mixes, review costs, and branch budgets.
- Independent target counts: 1, 2, 4, 8, and 16.
- Repetitions: ten paired, seeded ±10% cost variations.
- Total: 5 arms × 4 workloads × 5 target counts × 10 repetitions = 1,000 cells.

For a workload/repetition pair, every arm and target count receives the exact same
materialized candidate costs and review cost. The fixture digest is recorded in every
row and analysis rejects an unpaired matrix.

## Arms

- **v1-target-review:** the current single-obligation static plan plus one target-level
  AI review after each target. It is deliberately not called historical Graphori v1;
  this fixture does not replay that implementation.
- **graphori-v2:** one predeclared single-obligation worker per obligation and no AI
  review.
- **sprout-unconditional:** the real `ProofFrontier` selects a bounded compound cover. One
  complete extra cover is executed as the pilot before target expansion. Pilot latency,
  process nodes, and agent nodes are all counted.
- **graphori-sprout:** the adaptive planning policy estimates the static route and
  pilot route with the same WIP model. It keeps v2 when the pilot cannot reduce modeled
  latency and pilots only after the declared break-even point.
- **oracle-static:** the same compound cover as Sprout, assumed to be known before the
  run, without a pilot. It isolates compound-cover pilot cost, but it is neither a
  global lower bound nor an available Graphori mode.
  The gap between it and Sprout exposes the modeled pilot cost directly.

The unconditional and oracle controls are essential: without them, savings caused by giving Sprout compound nodes
could be mistaken for savings caused by dynamic routing.

## Latency and quality model

Node estimates are synthetic milliseconds. Longest jobs are greedily placed onto three
identical WIP lanes. An enabled Sprout pilot completes before target work. Target reviews complete
after the v1 target-work stage. Every arm then pays 10 ms of modeled fan-in cost.

All arms must cover every declared target obligation and record zero invalid fan-ins.
Pilot obligations are calibration overhead and are not included in target proof counts.
The model cannot establish that a proof declaration is correct, only that the selected
metadata covers the declaration.

## Sensitivity and interpretation

Results are reported separately for 1, 2, 4, 8, and 16 targets. A repeated-target result
must not be generalized to a single target. Sprout should be compared both with current
v2 and with the oracle: the first includes plan-granularity differences; the second
isolates pilot overhead.

An earlier draft used four identically structured workloads, arm-specific jitter, a
review for every worker, and only eight targets. It was discarded after audit. The even
earlier single-target draft was slower than v2. Neither draft is retained as evidence.

## Reproduce

Generated files belong under `build/` and are intentionally not committed.

```bash
PYTHONPATH=src python benchmarks/sprout/run.py \
  --output build/benchmarks/sprout/raw-results.jsonl \
  --repetitions 10 --branches 1 2 4 8 16
python benchmarks/sprout/analyze.py \
  --raw build/benchmarks/sprout/raw-results.jsonl \
  --output build/benchmarks/sprout/results.json \
  --repetitions 10 --branches 1 2 4 8 16
```
