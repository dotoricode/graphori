# Same-session repair

Same-session repair is an opt-in latency experiment for deterministic verifier
failures. It reuses model context; it never reuses a verifier verdict.

```text
implementation session
        ↓
deterministic verifier FAIL
        ↓ immutable NACK
same implementation session → repair → verifier
```

Enable it with `graphori run --same-session-repair ...`. Graphori resumes only
when run, node lineage, role, workspace, provider, requested model, effort,
agent contract, tool policy, permission profile, and the verdict's exact target
attempt all match. The verifier contributes facts—proof IDs, argv, exit code,
workspace digest, and evidence references—but cannot weaken acceptance rules.

Raw Codex and Claude session IDs are capabilities. They are stored in a
workspace-private file with mode `0600`; the canonical journal contains only a
random opaque handle and binding digests. Terminal runs remove those private
handles.

If the boundary or private binding is unavailable, Graphori starts a fresh
repair session containing the immutable NACK. If a resume was actually attempted
and then times out, is cancelled, exits nonzero, or returns malformed output,
Graphori does **not** automatically run the repair again: a CLI response cannot
prove that the first turn had no external effect.

The deterministic fixture benchmark covers both adapter protocols, boundary
isolation, correctness, and the no-double-execution rule. Its simulated latency
and tokens are mechanism checks, not provider performance claims. Real-provider
results require a separately approved and reported benchmark.
