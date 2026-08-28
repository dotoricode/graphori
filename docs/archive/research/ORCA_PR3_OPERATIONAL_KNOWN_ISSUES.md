# Orca operational observations during Graphori PR3

Status: observed, not fixed in Graphori Core
Environment: Orca-managed Codex terminal and orchestration CLI, 2026-08-14

These observations are adapter evidence. They do not change Graphori's
canonical meanings for execution, verification, or terminal status.

## Delayed initial instruction delivery

- Reproduction: start a Codex worker while its TUI is still initializing and
  immediately send the initial task instruction.
- Expected: the worker receives the instruction as soon as the session starts.
- Actual: delivery can be delayed during TUI initialization.
- Graphori impact: a future Orca adapter needs readiness probing before it
  treats a dispatch as delivered.

## `worker_done` capability rejection

- Reproduction: allow a worker to finish and submit its result through the
  orchestration completion path.
- Expected: the completed result is accepted and closes the dispatch.
- Actual: the result can arrive while completion is rejected with
  `Dispatch capability is missing`.
- Graphori impact: result arrival and dispatch completion must remain separate
  adapter facts. Core must not convert this rejection into a verifier verdict.

## Retained stopped dispatch

- Reproduction: stop the terminal and then request worker release for its
  stopped dispatch.
- Expected: the stopped dispatch releases its retained resource.
- Actual: worker release can reject the stopped dispatch, leaving a retained
  resource.
- Graphori impact: a future Orca adapter needs capability probing, degraded
  mode, and explicit retained-resource reporting. PR3 does not add an
  Orca-specific workaround to portable Core.

## Deferred adapter requirements

The Orca execution adapter phase should handle these as adapter degradation:

- capability probe before dispatch and completion;
- readiness acknowledgement for initial instruction delivery;
- separate result-arrived and worker-done states;
- release failure and retained-resource evidence;
- no promotion from platform completion to Graphori verification PASS.
