# Direct vs v1-style vs Graphori v2 protocol

This protocol compares orchestration strategies, not providers. Codex and Claude are
reported separately.

## Fixed matrix

- Providers: Codex and Claude Code.
- Arms: Direct, v1-style, and Graphori v2.
- Tasks: one small fix, one bounded feature, one multi-file feature, and one
  boundary-heavy bug fix.
- Repetitions: three fresh repositories and fresh provider sessions per cell.
- Total: 2 providers × 3 arms × 4 tasks × 3 repetitions = 72 runs.
- Order: deterministic shuffle with seed `20260828`.

For one provider/task cell, every arm uses the same Graphori-routed model and effort,
the same starting Git tree, visible test, hidden test, read/write scope, timeout, and
network constraint. Hidden tests are materialized only after the arm finishes.

## Arms

- **Direct:** one implementation session.
- **v1-style:** one implementation session followed by a fresh read-only AI review
  session using the same provider, model, and effort.
- **Graphori v2:** the same implementation route followed by Graphori's deterministic
  verifier, journal, scope check, and terminal projection.

The v1-style reviewer cannot edit or see hidden tests. It does not trigger rework.
Graphori v2 may record rework only if the deterministic visible verifier requests it.

## Metrics

Quality is reported before speed or cost: hidden tests, completion-claim agreement,
scope violations, and rework. TTUR is wall time from fresh fixture creation through the
hidden verifier. Usage keeps total, cached, fresh, and output tokens separate.

Claude cache-creation input is counted as fresh input and cache-read input as cached.
Codex uses the CLI's total and cached input fields, with fresh input calculated as their
difference. Provider-reported cost is recorded only when supplied; otherwise it remains
`null`.

Raw records contain hashes and bounded metadata, not prompts or provider transcripts.
An infrastructure failure is `unknown`, never an inferred test failure or success.

## Commands

```bash
PYTHONPATH=src python benchmarks/three_arm/run.py \
  --output benchmarks/three_arm/raw-results.jsonl
python benchmarks/three_arm/analyze.py
```

The runner fsyncs each JSONL record and resumes by skipping completed matrix cells.
