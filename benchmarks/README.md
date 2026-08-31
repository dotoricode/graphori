# Three-arm benchmark protocol

This directory contains two distinct things:

- [`v1_v2/`](v1_v2/) preserves a completed small two-arm comparison, including raw
  data, corrected results, analysis code, and an independent verifier.
- [`three_arm/`](three_arm/) contains the completed 72-run Direct/v1-style/
  Graphori v2 comparison, its fixed protocol, raw JSONL, and deterministic analysis.
- [`sprout/`](sprout/) compares v1 target review, Graphori v2, unconditional and
  adaptive Sprout, and a static oracle across repeated-target counts. Its latency is
  modeled, not provider wall time.
- [`live_verify/`](live_verify/) compares the v2 serial verifier path with exact-digest
  speculative verification using paired real-process wall time and stale-proof faults.
- [`session_repair/`](session_repair/) checks Codex and Claude same-session repair
  mechanisms with deterministic protocol fixtures. It is not a provider performance claim.

Do not commit generated results without the exact task set, tool versions, command
transcript, and raw JSON records.

Arms are intentionally comparable and must be run separately for Codex and Claude:

1. `direct`: one bounded command without Graphori planning.
2. `v1-style`: implementation session plus an independent AI review session.
3. `graphori-v2`: compiled work graph, only justified workers, and deterministic verification.

The completed public protocol used four tasks × three arms × three repetitions ×
two providers (72 runs). Providers are never combined into one score.

Raw records keep total, cached, and fresh input tokens separate. Unknown telemetry and cost remain JSON `null`; they are never inferred from process success.

Run `python benchmarks/three_arm/analyze.py` to reproduce the published summary.
The generic `python benchmarks/run_benchmark.py --help` recorder remains available
for future explicit commands.
