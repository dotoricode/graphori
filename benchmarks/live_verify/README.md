# Live Verify benchmark

This benchmark measures the narrow optimization that Graphori can safely own:
overlapping an explicitly repeatable deterministic verifier with the tail of an
active worker, then reusing the result only if an exact workspace-content digest
still matches.

It compares the existing v2 adapter sequence with `LiveVerifyAdapter` through the
same real process supervisor and routed adapter seam. The worker is deterministic;
this is a control-plane wall-clock benchmark, not a live Codex or Claude quality
claim.

The gate fails unless all of these conditions hold:

- every result is correct;
- zero stale proofs are reused in injected late-write cases;
- AI sessions and fresh input tokens do not increase;
- median wall time improves by at least 25%;
- p95 wall time improves by at least 15%; and
- the paired bootstrap 95% lower bound exceeds 20%.

The output also reports the complete ActionKey count and rate, PASS candidate
and reuse counts, reuse rate, fallback count, and fallback reasons. These are
interpretation metrics rather than relaxed pass criteria: a fast result with
little eligible or reused work must remain visible instead of being presented
as broad product value.

Run it with:

```bash
python3.11 benchmarks/live_verify/run.py
```

Generated output belongs under `build/` and is not a published provider result.
Live provider benchmarks must be reported separately for Codex and Claude.
