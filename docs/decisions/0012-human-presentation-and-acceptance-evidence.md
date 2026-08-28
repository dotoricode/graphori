# ADR 0012: Human presentation and acceptance evidence stay separate from canonical state

## Status

Accepted for PR11A.1.

## Context

The first product-entry dogfood exposed generic node titles, no truthful
activity context during long provider calls, and acceptance criteria that
existed only as prose. English runtime vocabulary also made the default Korean
experience harder to scan.

## Decision

- Keep canonical team, node, event, and status identifiers in English.
- Render Korean by default through a dependency-free `ko`/`en` vocabulary.
- Derive short node display titles deterministically without another model call.
- Keep liveness, elapsed time, last activity, and provider progress separate.
- Carry explicit `AC-N: description` criteria through `RunSpec`, `RunPlan`, and
  `NodeSpec`.
- Project criterion evidence as `PROVEN`, `NOT_PROVEN`, `FAILED`, or
  `NOT_APPLICABLE`.
- Never turn a passing verifier command into proof for every criterion.
- Require `subprocess:test:*` evidence for a criterion that explicitly requires
  a separate or cold process boundary.
- Report Worker execution and independent verification as separate sources.

## Consequences

Changing locale does not change plan or projection identity. A Run can have a
successful execution verdict while its user requirements remain visibly
`NOT_PROVEN`; changing terminal success policy is deferred until criterion
evidence producers are sufficiently complete.
