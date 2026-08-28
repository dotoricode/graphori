# ADR 0011: replay legacy journals through a deterministic projection adapter

- Status: accepted
- Date: 2026-08-20

## Decision

PR11A adds a read-time compatibility layer for journals created before PR10
recorded `RunSpec` and `RunPlan`. It validates the existing JSONL and hash
chain first, then constructs the minimum v3 projection inputs from recorded
event identity plus documented fixed legacy defaults. It never appends,
rewrites, or migrates the journal or its sidecars.

The snapshot exposes `metadata_provenance` outside `projection_digest`:

- `unknown` means the legacy journal did not record the value.
- `legacy_default` means a fixed compatibility value required to form the v3
  shape, not an observation or inferred claim.
- `recorded` means current v3 metadata was supplied in a valid sidecar or
  lifecycle event.

## Fail-closed boundary

Any current metadata declaration that is partial, malformed, conflicting, has
the wrong run identity, or disagrees with the journal graph version is rejected.
It cannot silently fall back to the legacy path. Legacy replay likewise rejects
ambiguous task IDs, graph versions, node identities, and worker role IDs.

## Consequences

- Cold Dashboard, `graphori status`, and `graphori replay` resolve the same
  metadata and therefore publish one digest for the same journal.
- Legacy node title/objective are explicitly unknown; compatibility does not
  invent original plan, scopes, provider, model, dependencies, or verification
  metadata.
- PR11B migration tooling remains out of scope: there is no destructive
  rewrite path in this decision.
