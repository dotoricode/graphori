# Graphori v1-style and v2 comparison protocol

Measured on 2026-08-24. The protocol was fixed before the result was analyzed.

The comparison used the same coding task, starting files, public tests, hidden final
checks, Codex model and effort, file permissions, and 240-second timeout. Every run
used a fresh Git repository and a fresh AI conversation. Execution order was shuffled
with seed `20260824`.

- **v1-style:** one implementation AI followed by a separate review AI.
- **Graphori v2 candidate:** one implementation AI followed by a predetermined
  deterministic check.

Two small Python tasks—`normalize-tags` and `config-parser`—were run twice per arm,
for four observations per arm. Hidden checks were revealed only after each run.

## Limits

- Four observations per arm cannot represent every coding task.
- v1-style reconstructed the rules from private development revision `93c5fcf`; it did
  not replay preserved historical runs. That revision is not reachable from this clean
  public history.
- The v2 source was an uncommitted candidate identified by the digest retained in the
  raw data.
- The benchmark used Codex only. It does not compare providers.
- An initial parser misread the four v2 terminal statuses. The corrected result was
  recalculated from retained stdout and 14 journal events per run without rerunning the
  agents. Both the raw and corrected files are retained.

See [raw-results.json](raw-results.json), [results.json](results.json), and
[verify_results.py](verify_results.py).
