# ADR 0008: pinned skill registry and compatibility compiler

- Status: accepted
- Date: 2026-08-19

## Decision

Graphori treats external skills as immutable instruction packages, not trusted
plugins. `SkillRegistry` pins source identity, creates a content-addressed
read-only snapshot, and verifies `skills.lock.json`. It records scripts and
hooks but PR8 never executes them.

`SkillCompatibilityCompiler` closes dependencies and rejects cycles, hidden
orchestration, nested agents, missing preconditions, unsupported hosts, and
conflicts before dispatch. One Node may request one primary skill; only one
required dependency may expand the resolved set to two.

`SkillPolicyEngine` remains collect-only. The default binding set is empty and
only an explicit request can create a `SkillBinding`. Bindings are Attempt
scoped, included in the RunPlan digest and `graph_published` event, and rendered
for Codex and Claude as a lazy path plus digest rather than inline content.

## Consequences

- Workflow and orchestrator skills cannot silently own a Worker lifecycle.
- TDD is ineligible until the plan contains approved test seams.
- Ponytail `ultra` is explicit-only and Ponytail never persists across Nodes.
- Provider-native plugin installation, script execution, and remote updates are
  outside PR8.
- No-skill RRC-04 results remain the performance baseline; effectiveness-based
  automatic binding requires a later benchmark.
