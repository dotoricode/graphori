# Three-arm benchmark protocol

This is reproducibility scaffolding, not a benchmark result. Do not commit generated results without the exact task set, tool versions, command transcript, and raw JSON records.

Arms are intentionally comparable and must be run separately for Codex and Claude:

1. `direct`: one bounded command without Graphori planning.
2. `v1-style`: implementation session plus an independent AI review session.
3. `graphori-v2`: compiled work graph, only justified workers, and deterministic verification.

Use the same repository snapshot, requirement, model, effort, hidden verifier, and write scope for every arm. The recommended public protocol is four tasks × three arms × three repetitions × two providers (72 runs). Never combine providers into one score.

Raw records keep total, cached, and fresh input tokens separate. Unknown telemetry and cost remain JSON `null`; they are never inferred from process success.

Run `python benchmarks/run_benchmark.py --help`. The runner refuses to invent a command, result, cost, or success value. Store raw JSON Lines matching `raw-result.schema.json`, then derive a report separately.
