# Graphori domain language

## Model routing

**Runtime Model** — A provider model identity that an available execution
adapter can actually request. It is never derived from a benchmark label.

**Benchmark Model** — A model, effort, and harness identity measured by an
external benchmark snapshot. It is a performance prior, not proof of runtime
availability.

**Model Benchmark Binding** — An explicit, versioned relationship between one
Benchmark Model and one Runtime Model at a particular effort.

**Task Features** — Deterministic facts extracted from a planned Node and used
as the complete input to routing policy.

**Routing Decision** — The immutable primary route, ordered fallbacks, reason
codes, confidence, and snapshot identity selected for one Node.

**Premium Model** — A Runtime Model whose catalog Approval Class requires a
Human Gate before dispatch.

**Premium Approval Envelope** — Node-local human authority bounded by model
family, maximum effort, write scope, permission profile, Run, and plan version.

**Local Telemetry** — Graphori-observed execution timing and outcome records.
It does not automatically change routing policy in PR7.

## Skill compatibility

**Skill Package** — A directory rooted at `SKILL.md` whose instructions and
referenced files form one candidate capability. Scripts and hooks are package
inventory, not executable authority.

**Skill Snapshot** — A read-only, content-addressed copy of one Skill Package.
Its digest and source commit remain fixed for the lifetime of a RunPlan.

**Skill Manifest** — Graphori's explicit statement of a Skill Package's kind,
invocation policy, activation scope, dependencies, risks, host support, trust,
and immutable source identity. Unknown properties stay unknown rather than
being inferred optimistically.

**Skill Compatibility** — A deterministic eligibility result for one Skill
Manifest and one planned Node, including every reason that prevents binding.

**Skill Binding** — The immutable Skill Snapshot, arguments, activation scope,
and selection reason assigned to one Node before dispatch. A binding is part
of the RunPlan digest and cannot discover more skills at runtime.

**Skill Candidate** — A compatible but unselected Skill reported by PR8's
collect-only policy. A candidate never changes execution by itself.
