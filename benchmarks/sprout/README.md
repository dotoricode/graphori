# Sprout routing-model benchmark

This deterministic fixture checks one narrow question: under declared node costs and a
three-lane WIP model, how do five routing policies scale as the number of repeated
targets changes?

It does **not** execute providers or verifiers and does not measure wall time, tokens,
cost, model quality, or production reliability. The committed repository contains the
runner, analyzer, protocol, and report—not generated results.

```bash
PYTHONPATH=src python benchmarks/sprout/run.py \
  --output build/benchmarks/sprout/raw-results.jsonl
python benchmarks/sprout/analyze.py \
  --raw build/benchmarks/sprout/raw-results.jsonl \
  --output build/benchmarks/sprout/results.json
```

[Protocol](PROTOCOL.md) · [Report](REPORT.md) ·
[한국어 규약](PROTOCOL.ko.md) · [한국어 결과](REPORT.ko.md)
