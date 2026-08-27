# Security policy

## Reporting a vulnerability

Please do not open a public issue. Report it privately to the repository owner
with the affected version or commit, steps to reproduce, the impact you see,
and any mitigation you know of. Leave out credentials, private repositories,
and customer data.

There is no advisory channel configured yet, so use the owner's private contact
rather than the issue tracker.

This is a public beta with no response-time or bounty commitment. Reproducible
reports get acknowledged when practical, assessed, and fixed or disclosed in
coordination with the reporter before details are published.

## Scope

Graphori runs local tools when you ask it to. It is not a sandbox and does not
try to be one. Review write scopes and verification commands before a run: a
provider you authorize can edit files and execute commands within them.

The journal is append-only audit evidence. It records what happened; it does
not constrain what can happen.
