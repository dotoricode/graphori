# PR9 product entry checkpoint

- Date: 2026-08-20
- Scope: `$graphori` product entry and Plan Preview only

## Completed path

```text
$graphori / graphori run
  -> RunSpec
  -> ProductPlanCompiler
  -> Plan Preview
  -> RoutedExecutionAdapter
  -> GraphExecutionEngine
  -> canonical journal
  -> reducer projection
```

The preview is emitted before adapter dispatch. Independent read-only roots can
then dispatch in the same run without waiting for a second confirmation.
Planning is the current coordinator and does not create a child Agent.

Direct Codex and Claude remain the product Worker routes. Generic process is
used for explicit deterministic verification. Orca is not selected by this
entrypoint. External Skill bindings remain empty by default.

## Preserved invariants

- `worker_finished != verification passed`
- `memory state != source of truth`
- dependency handoff comes from the canonical journal
- Premium approval is required before premium dispatch
- Plan Preview and execution use the same immutable RunPlan

## Deferred

- PR10 Dashboard canonical projection integration
- PR11 locks, migration, resume/doctor, installation and release hardening
- automatic Skill binding
- Orca route revalidation
