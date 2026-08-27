# Trust model

Graphori treats the append-only local journal and its deterministic reducer as the record of a run. A replay can show whether the stored events produce the same projection and digest. It does not prove that an agent's text is true, that a command was safe, or that the working tree is correct after a run.

| Graphori records | A human or external control must still decide |
| --- | --- |
| Plan nodes, dependencies, route selection, events, deterministic verifier exit evidence | Scope appropriateness, provider authorization, secret handling, review, deployment |
| Whether recorded digest chains and pinned metadata match | Whether a provider actually understood the request |
| A blocked/unknown state when safe replay is impossible | Whether to retry, accept, or discard ambiguous external work |

Keep credentials out of objectives, journals, evidence labels, and commands. Graphori is not a sandbox: a permitted adapter or verifier can affect the workspace. Use narrow write scopes, explicit verification, version control, and a human gate.
