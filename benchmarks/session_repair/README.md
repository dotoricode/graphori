# Same-session repair fixture benchmark

This benchmark measures Graphori's provider-session mechanism, not real model
quality or production provider latency. It runs the real Codex and Claude Code
adapter paths against deterministic protocol fixtures with a fixed simulated
context-rediscovery penalty.

The gate is fixed before execution:

- identical structured correctness in both arms;
- zero write-scope violations and zero boundary leaks;
- median wall-time improvement of at least 10%, or fresh-input reduction of at
  least 15%; and
- no automatic fresh retry after an attempted resume fails.

Run it with:

```bash
PYTHONPATH=src python benchmarks/session_repair/run.py \
  --output build/session-repair-results.json
```

Real-provider measurements must be reported separately by provider and require
explicit cost approval. Fixture results must never be presented as product
latency or token savings.
