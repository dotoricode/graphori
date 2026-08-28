# ADR 0007: deterministic latency-first routing and node-local premium gates

- Status: accepted
- Date: 2026-08-14

## Decision

Graphori routes each non-deterministic Node through a fixed `ModelCatalog`
snapshot. Runtime identities, benchmark identities, and their explicit
bindings remain separate. Provider discovery determines availability;
benchmark data supplies only a versioned prior.

Routing first removes candidates that violate capability, provider
independence, risk, or quality constraints. It then prefers a normal approval
class, minimizes expected wall time, uses cost as a tie-breaker, and finally
uses reliability and stable identity ordering. It does not collapse these
policies into one weighted score and does not invoke an LLM.

Sol-class, Opus-class, and future catalog entries marked `premium` require a
node-local Human Gate. The approval is bounded by a `PremiumApprovalEnvelope`.
Independent Nodes continue while the gate is open. Fallbacks are selected
before the gate is created, and retry cannot change the approved route.

## Consequences

- A stronger model is not automatically preferred when a faster model meets
  the quality floor.
- Benchmark updates are explicit data changes and change the snapshot digest.
- Provider or adapter failures do not cause intelligence escalation.
- Premium approval and fallback selection replay from the canonical journal.
- Local telemetry is recorded now, but adaptive policy changes remain a later
  decision.
