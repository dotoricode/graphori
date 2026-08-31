# Proof-driven execution

Read this reference for substantial Graphori work involving proof selection,
non-LLM nodes, speculative verification, repair sessions, or dynamic planning.

## Select work from the open proof frontier

Start with the acceptance conditions that remain open. For each condition,
compare candidate executions by expected proof gain, latency, cost, and risk.
Node count and agent count are not goals.

Candidate executors include:

- an existing artifact or journaled result;
- compiler, test runner, linter, schema checker, or local process;
- Codex or Claude when judgment or mutation is actually required;
- a human gate for irreversible or permission-expanding work.

Use the simple v2 implementation-then-verifier path for ordinary one-to-four-node
work. Creating no extra Node is a valid planning result.

## Preserve three distinct views

- Proof view: what condition must be satisfied?
- Execution view: what Node and attempt run next?
- Evidence view: what artifact or fact supports the verdict?

Keep `RunPlan` as the execution DAG and the append-only journal as canonical
authority. Do not create separate mutable graph stores merely to represent the
other views. Node identity is not Execution identity, and neither is Session
identity.

## Adopt speculative evidence safely

Live Verify produces a proof candidate, not canonical PASS. Adoption requires:

1. snapshot safety: source and copied input digests match, and the copy remains
   unchanged during verification;
2. a complete bounded `ProofActionKey` over Graphori-observable or explicitly
   declared execution-envelope inputs;
3. adoption safety: current source digest and a newly computed ActionKey match
   the candidate.

`ProofActionKey v0` does not prove complete transitive interpreter, library,
plugin, cache, or toolchain closure. Unknown transitive dependencies alone do
not make Python, Java, Gradle, or shell checks ineligible. If a required v0
field cannot be compared, run the ordinary v2 verifier.

Persist only environment variable names, one aggregate environment digest, and
completeness. Never persist raw environment values or per-variable value hashes.
The directly executed entry file identity is not a full toolchain identity.

## Repair without losing context

On deterministic verification failure, journal immutable failure evidence first.
The repair controller may send a factual NACK to the same implementation session
only when this full boundary matches:

```text
run + node lineage + role + workspace + provider + model
+ effort + system prompt + tool policy + permission profile
+ exact implementation attempt
```

The verifier states the failed proof, command, exit status, and bounded error
evidence. It does not instruct the agent to weaken or modify the verifier.
Keep raw provider session IDs in a private capability vault, never in the
canonical journal. A boundary mismatch detected before resume starts may use a
fresh repair session containing the immutable NACK. Once resume is attempted,
timeout, cancellation, nonzero exit, or malformed output must not automatically
start a second repair: the provider response cannot prove that the first turn
had no external effect. Implementation and independent-review sessions never
share context.

## Introduce automatic planning through evidence

Compile acceptance contracts monotonically:

1. user-declared completion conditions;
2. repository policy;
3. existing deterministic build/test/schema rules;
4. deterministic discovery;
5. optional LLM-proposed strengthening.

An LLM may propose or strengthen a proof. It may not delete, weaken, or relax a
mandatory proof or PASS rule.

Run dynamic Sprout planning in shadow mode before it controls execution. Record
the v2 plan, shadow plan, estimated and actual latency, proof coverage, planning
cost, incorrect expansion, and missed expansion. Activate only patterns that
pass a fixed gate; uncertainty falls back to v2. Conditional activation must
not increase modeled AI sessions compared with the v2 route.

## Required measurement

Do not lower an acceptance threshold after seeing results. For Live Verify report
eligible ActionKey count/rate, PASS candidate and reuse count/rate, fallback
count, and fallback reasons. For session repair report wall time, provider
latency, fresh input/output tokens, repository rediscovery, repair turns,
correctness, and scope violations. Separate Codex and Claude results.
