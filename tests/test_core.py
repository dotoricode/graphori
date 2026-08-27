import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    Attempt, AttemptState, Edge, EdgeKind, Graph, GraphValidationError,
    GraphVersion, Run, TerminalStatus,
    IndependenceError, Node, NodeKind, NodeState, PlatformStatus, Risk,
    RiskInput, RevisionAction, RevisionController, Role, StateReducer,
    StateTransitionError, Task, TaskMode, TaskState, Usage, UsageStatus,
    VerificationKind, canonical_event, compile_risk, compile_topology,
    transition_node, transition_task, validate_graph, verify_attempt,
)


class CoreContractTests(unittest.TestCase):
    def event(self, event_type, *, actor="verifier", payload=None, entity=None, **extra):
        return canonical_event(event_type, actor_role=actor, payload=payload,
                               entity=entity, **extra)

    def published_reducer(self, *, task_id="task_test", run_id="run_test",
                          nodes=(("worker", NodeKind.WORKER),), graph_version=1):
        task = Task(task_id, "published", run_id=run_id, graph_version=1)
        run = Run(run_id, graph_version=1)
        for node_id, kind in nodes:
            run.graph.add_node(Node(node_id, kind, node_id))
        reducer = StateReducer(task, run)
        reducer.apply(self.event("run_created", run_id=run_id, task_id=task_id,
                                 actor="router", seq=1, graph_version=1))
        reducer.apply(self.event("graph_published", run_id=run_id, task_id=task_id,
                                 actor="router", seq=2, graph_version=graph_version))
        return task, run, reducer

    def pass_node(self, reducer, *, node_id="worker", run_id="run_test",
                  task_id="task_test", start=3, graph_version=1):
        actors = {
            "ready": "scheduler", "assigned": "scheduler", "running": "worker",
            "awaiting_verification": "worker", "passed": "verifier",
        }
        for seq, status in enumerate(("ready", "assigned", "running",
                                      "awaiting_verification", "passed"), start=start):
            reducer.apply(self.event("node_status_changed", run_id=run_id,
                                     task_id=task_id, actor=actors[status], seq=seq,
                                     graph_version=graph_version,
                                     entity={"node_id": node_id},
                                     payload={"status": status}))

    def test_three_mode_fixtures_only_add_review_when_policy_requires_it(self):
        fast = compile_topology(Task("t-fast", "docs", metadata={
            "usage_status": "known", "local_only": True, "reversible": True,
            "external_effect": False,
        }))
        standard = compile_topology(Task("t-standard", "feature", risk=Risk.HIGH,
                                         metadata={"usage_status": "known", "local_only": True,
                                                   "reversible": True, "external_effect": False}))
        critical = compile_topology(Task("t-critical", "boundary", risk=Risk.CRITICAL))
        self.assertEqual(fast.task.mode, TaskMode.FAST)
        self.assertEqual(standard.task.mode, TaskMode.STANDARD)
        self.assertEqual(critical.task.mode, TaskMode.CRITICAL)
        self.assertNotIn("verifier", fast.graph.nodes)
        self.assertNotIn("verifier", standard.graph.nodes)
        self.assertIn("verifier", critical.graph.nodes)
        self.assertNotIn("verifier_normal", critical.graph.nodes)
        self.assertNotIn("verifier_adversarial", critical.graph.nodes)
        self.assertNotIn("verifier_fanin", critical.graph.nodes)
        self.assertIn("human_gate", critical.graph.nodes)

        reviewed = compile_topology(Task(
            "t-reviewed", "public API change", risk=Risk.HIGH,
            metadata={"verification_required": True},
        ))
        self.assertIn("verifier", reviewed.graph.nodes)

        parallel_critical = compile_topology(Task(
            "t-parallel-critical", "independent adversarial evidence", risk=Risk.CRITICAL,
            metadata={"parallel_verification": True},
        ))
        self.assertIn("verifier_normal", parallel_critical.graph.nodes)
        self.assertIn("verifier_adversarial", parallel_critical.graph.nodes)
        self.assertIn("verifier_fanin", parallel_critical.graph.nodes)

    def test_fast_boundaries_are_fail_closed(self):
        base = {"usage_status": "known", "local_only": True, "reversible": True,
                "external_effect": False}
        self.assertEqual(compile_risk(RiskInput(**base)).mode, TaskMode.FAST)
        for field, value in (("usage_status", "unknown"), ("usage_status", "estimate"),
                             ("local_only", None), ("local_only", False), ("reversible", None),
                             ("reversible", False), ("external_effect", None),
                             ("uncertainty", 1), ("risk_level", 1)):
            data = dict(base)
            data[field] = value
            self.assertNotEqual(compile_risk(RiskInput(**data)).mode, TaskMode.FAST,
                                msg=f"unexpected Fast for {field}={value!r}")
        self.assertEqual(compile_risk(RiskInput(**{**base, "uncertainty": 2})).mode, TaskMode.CRITICAL)
        self.assertEqual(compile_risk(RiskInput(**{**base, "external_effect": True})).mode, TaskMode.CRITICAL)
        self.assertEqual(compile_risk(RiskInput(**{**base, "tags": ("high-risk",)})).mode, TaskMode.CRITICAL)
        self.assertEqual(compile_topology(Task("critical", "x", risk=Risk.CRITICAL), mode=TaskMode.FAST).task.mode,
                         TaskMode.CRITICAL)

    def test_unknown_usage_is_not_zero(self):
        self.assertIsNone(Usage(UsageStatus.UNKNOWN).total_tokens)
        self.assertEqual(Usage(UsageStatus.ESTIMATE, predicted_tokens=42).total_tokens, 42)
        self.assertEqual(Usage(UsageStatus.KNOWN, input_tokens=3, output_tokens=4).total_tokens, 7)
        self.assertEqual(compile_risk(RiskInput(usage_status="unknown")).mode, TaskMode.STANDARD)

    def test_independence_rejects_partial_identity_and_resource_bypasses(self):
        worker = Role("w", NodeKind.WORKER, "same", "p", "m", "c", "s", "wt")
        verifier = Role("v", NodeKind.VERIFIER, "different", "p", "m", "c", "s", "wt")
        with self.assertRaises(IndependenceError):
            verify_attempt(Attempt("aw", "t", worker, AttemptState.SUCCEEDED),
                           Attempt("av", "t", verifier, AttemptState.SUCCEEDED))
        for changed in ({"identity": "different"}, {"provider": "other"},
                        {"model": "other"}, {"checkout": "other"},
                        {"session": "other"}, {"worktree": "other"}):
            values = {"role_id": "v", "role": NodeKind.VERIFIER, "identity": "same",
                      "provider": "p", "model": "m", "checkout": "c", "session": "s", "worktree": "wt"}
            values.update(changed)
            candidate = Role(**values)
            with self.assertRaises(IndependenceError):
                verify_attempt(Attempt("aw", "t", worker, AttemptState.SUCCEEDED),
                               Attempt("av", "t", candidate, AttemptState.SUCCEEDED))

    def test_critical_standard_and_gate_independence(self):
        normal = Role("n", NodeKind.VERIFIER, "normal", "same", "model", "c1")
        adversarial = Role("a", NodeKind.VERIFIER, "adversarial", "same", "model", "c2")
        with self.assertRaises(IndependenceError):
            compile_topology(Task("t", "boundary", risk=Risk.CRITICAL,
                                  metadata={"parallel_verification": True}),
                             verifier_roles=(normal, adversarial))
        standard = Role("v", NodeKind.VERIFIER, "different", "", "", "")
        with self.assertRaises(IndependenceError):
            compile_topology(Task("t", "docs", metadata={"usage_status": "known",
                                                            "local_only": True, "reversible": True,
                                                            "external_effect": False,
                                                            "verification_required": True}),
                             verifier_roles=(standard,))
        gate = (Role("g1", NodeKind.HUMAN_GATE, "g1", "p", "m", "shared"),
                Role("g2", NodeKind.HUMAN_GATE, "g2", "q", "n", "shared"))
        with self.assertRaises(IndependenceError):
            compile_topology(Task("t", "feature", risk=Risk.HIGH,
                                  metadata={"human_gate": True}), human_gate_roles=gate)

    def test_compile_metadata_and_verification_edges(self):
        topology = compile_topology(Task("t", "boundary", risk=Risk.CRITICAL,
                                         metadata={"parallel_verification": True}))
        self.assertEqual(topology.graph.nodes["verifier_normal"].metadata["verification"],
                         VerificationKind.FRESH_FULL.value)
        self.assertEqual(topology.graph.nodes["verifier_adversarial"].metadata["verification"],
                         VerificationKind.ADVERSARIAL.value)
        self.assertIsNone(topology.graph.nodes["verifier_fanin"].role)
        self.assertTrue(topology.graph.nodes["verifier_fanin"].metadata["fan_in"])
        self.assertTrue(any(e.kind is EdgeKind.VERIFIES for e in topology.graph.edges))

    def test_validate_graph_requires_verification_path_and_history_rules(self):
        graph = Graph()
        graph.add_node(Node("worker", NodeKind.WORKER, "worker"))
        graph.add_node(Node("verifier", NodeKind.VERIFIER, "verifier"))
        with self.assertRaises(GraphValidationError):
            validate_graph(graph)
        graph.add_edge(Edge("verifier", "worker", EdgeKind.VERIFIES))
        validate_graph(graph)
        graph.add_edge(Edge("verifier", "verifier", EdgeKind.REWORK_OF))
        with self.assertRaises(GraphValidationError):
            validate_graph(graph)

    def test_revision_limit_is_one_and_second_revise_escalates_without_new_worker(self):
        task, graph, revisions = Task("task", "change"), Graph(), RevisionController()
        graph.add_node(Node("task", NodeKind.WORKER, "original"))
        self.assertEqual(revisions.record("revise", task, graph), RevisionAction.REVISED)
        self.assertIn("task:revision-1", graph.nodes)
        self.assertEqual(revisions.revise_count, 1)
        worker_nodes_before_escalation = {
            node_id for node_id, node in graph.nodes.items()
            if node.kind is NodeKind.WORKER
        }
        revision_edges_before_escalation = {
            (edge.source, edge.target) for edge in graph.edges
            if edge.kind is EdgeKind.REWORK_OF
        }
        history = [edge for edge in graph.edges if edge.kind is EdgeKind.REWORK_OF]
        self.assertEqual([(e.source, e.target) for e in history], [
            ("task:revision-1", "task")])
        self.assertTrue(all(e.source != e.target for e in history))
        self.assertEqual(
            revisions.record("revise", task, graph), RevisionAction.ESCALATED
        )
        self.assertEqual(revisions.revise_count, 1)
        self.assertEqual(worker_nodes_before_escalation, {
            node_id for node_id, node in graph.nodes.items()
            if node.kind is NodeKind.WORKER
        })
        self.assertEqual(revision_edges_before_escalation, {
            (edge.source, edge.target) for edge in graph.edges
            if edge.kind is EdgeKind.REWORK_OF
        })
        self.assertNotIn("task:revision-2", graph.nodes)
        self.assertEqual(task.state, TaskState.ESCALATED)
        self.assertTrue(any(node.metadata.get("signal") == "human_gate_required"
                            for node in graph.nodes.values()))
        validate_graph(graph)

    def test_node_state_table_and_terminal_immutability(self):
        statuses = {}
        transition_node(statuses, "n", NodeState.READY)
        transition_node(statuses, "n", NodeState.ASSIGNED)
        transition_node(statuses, "n", NodeState.RUNNING)
        transition_node(statuses, "n", NodeState.AWAITING_VERIFICATION)
        transition_node(statuses, "n", NodeState.PASSED)
        for status in (NodeState.RUNNING, NodeState.READY, NodeState.FAILED, NodeState.CANCELLED):
            with self.assertRaises(StateTransitionError):
                transition_node(statuses, "n", status)

    def test_reducer_node_status_uses_transition_guard(self):
        reducer = StateReducer(Task("t", "x"),
                               node_statuses={"n": NodeState.PENDING})
        for status in ("ready", "assigned", "running", "awaiting_verification", "failed"):
            reducer.apply(self.event("node_status_changed", payload={"status": status},
                                      entity={"node_id": "n"}))
        for status in ("ready", "running"):
            with self.assertRaises(StateTransitionError):
                reducer.apply(self.event("node_status_changed", payload={"status": status},
                                          entity={"node_id": "n"}))

    def test_verdict_authority_evidence_and_actor_fail_closed(self):
        _, _, reducer = self.published_reducer(nodes=())
        for actor, verdict in (("worker", "pass"), ("router", "approve"),
                               ("verifier", "approve"), ("human_gate", "pass")):
            with self.assertRaises(StateTransitionError):
                reducer.apply(self.event("verdict_recorded", actor=actor,
                                          payload={"verdict": verdict, "evidence_ids": ["ev"]}))
        for evidence in (None, [], "ev", [""], [None], ["  "]):
            with self.assertRaises(StateTransitionError):
                reducer.apply(self.event("verdict_recorded", payload={"verdict": "pass",
                                                                        "evidence_ids": evidence}))
        event = self.event("verdict_recorded", actor="worker",
                           payload={"verdict": "pass", "evidence_ids": ["ev"]})
        event["payload"]["actor_role"] = "verifier"
        with self.assertRaises(StateTransitionError):
            reducer.apply(event)
        reducer.apply(self.event("verdict_recorded", payload={"verdict": "pass",
                                                               "evidence_ids": ["ev"]}))
        reducer.apply(self.event("verdict_recorded", actor="human_gate",
                                 payload={"verdict": "approve", "evidence_ids": ["ev2"]}))
        self.assertEqual([item.value for item in reducer.verdicts], ["pass", "approve"])

    def test_canonical_event_envelope_rejects_missing_bad_and_negative_fields(self):
        good = self.event("node_status_changed", payload={"status": "ready"}, entity={"node_id": "n"})
        for field in ("schema_version", "event_id", "run_id", "graph_version", "seq",
                      "occurred_at", "recorded_at", "actor", "entity", "payload"):
            malformed = dict(good)
            malformed.pop(field)
            with self.assertRaises(StateTransitionError, msg=field):
                StateReducer(Task("t", "x")).apply(malformed)
        for field, value in (("schema_version", "1"), ("event_id", ""), ("run_id", ""),
                             ("graph_version", -1), ("seq", -1), ("seq", "1"),
                             ("occurred_at", ""), ("actor", {}), ("entity", "bad"),
                             ("payload", [])):
            malformed = dict(good)
            malformed[field] = value
            with self.assertRaises(StateTransitionError):
                StateReducer(Task("t", "x")).apply(malformed)

    def test_platform_verdict_preserves_fixture_snapshot_units(self):
        _, _, reducer = self.published_reducer(task_id="t", run_id="run-platform", nodes=())
        reducer.apply(self.event("platform_verdict_recorded", run_id="run-platform", task_id="t",
                                payload={"platform": "windows", "status": "pass",
                                         "fixture_id": "fx-1", "evidence_id": "ev-1"}))
        reducer.apply(self.event("platform_verdict_recorded", run_id="run-platform", task_id="t",
                                payload={"platform": "windows", "status": "pass",
                                         "snapshot_id": "snap-2", "evidence_id": "ev-2"}, seq=2))
        reducer.apply(self.event("platform_verdict_recorded", run_id="run-platform", task_id="t",
                                payload={"platform": "macos", "status": "deferred"}, seq=3))
        summary = reducer.platform_summary()
        self.assertEqual(len(summary["platform_verdicts"]["windows"]["verdicts"]), 2)
        self.assertEqual(summary["scope"], "windows")
        self.assertEqual(summary["exclusions"], ["macos"])

    def test_task_and_attempt_terminal_guards(self):
        task = Task("t", "x")
        transition_task(task, TaskState.READY)
        transition_task(task, TaskState.RUNNING)
        transition_task(task, TaskState.FAILED)
        with self.assertRaises(StateTransitionError):
            transition_task(task, TaskState.READY)
        attempt = Attempt("a", "t", Role("w", NodeKind.WORKER, "w", checkout="c"))
        attempt.state = AttemptState.SUCCEEDED
        with self.assertRaises(StateTransitionError):
            from graphori_core import transition_attempt
            transition_attempt(attempt, AttemptState.RUNNING)

    def test_unknown_event_and_noncanonical_task_status_are_rejected(self):
        reducer = StateReducer(Task("t", "x"))
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("typo"))
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("task_status_changed", payload={"status": "ready"}))

    def test_canonical_digest_producer_and_actor_identifiers_fail_closed(self):
        good = self.event("heartbeat")
        self.assertRegex(good["digest"], r"^sha256:[0-9a-fA-F]{64}$")
        self.assertRegex(good["prev_digest"], r"^sha256:[0-9a-fA-F]{64}$")
        self.assertTrue(good["producer_event_id"])
        self.assertTrue(good["actor"]["role_id"])
        for field, values in {
            "producer_event_id": (None, "", 123),
            "digest": (None, "", "bad", 123, "sha256:" + "0" * 63,
                       "sha256:" + "g" * 64),
            "prev_digest": (None, "", "bad", 123, "sha256:" + "0" * 63,
                            "sha256:" + "g" * 64),
        }.items():
            for value in values:
                malformed = dict(good)
                malformed[field] = value
                with self.assertRaises(StateTransitionError, msg=f"{field}={value!r}"):
                    StateReducer(Task("t", "x")).apply(malformed)
        for actor in ({"role": "verifier"}, {"role": "verifier", "role_id": None},
                      {"role": "verifier", "role_id": ""},
                      {"role": "verifier", "role_id": 123},
                      {"role": None, "role_id": "role_v"}):
            malformed = dict(good)
            malformed["actor"] = actor
            with self.assertRaises(StateTransitionError):
                StateReducer(Task("t", "x")).apply(malformed)
        genesis = dict(good)
        genesis["seq"] = 0
        genesis["prev_digest"] = None
        with self.assertRaises(StateTransitionError):
            StateReducer(Task("t", "x")).apply(genesis)

    def test_rework_history_long_cycles_and_missing_original_are_rejected_atomically(self):
        for edges in ((("a", "b"), ("b", "a")),
                      (("a", "b"), ("b", "c"), ("c", "a"))):
            graph = Graph()
            for node_id in {item for pair in edges for item in pair}:
                graph.add_node(Node(node_id, NodeKind.WORKER, node_id))
            for source, target in edges:
                graph.add_edge(Edge(source, target, EdgeKind.REWORK_OF))
            with self.assertRaises(GraphValidationError):
                validate_graph(graph)
        task, graph, revisions = Task("missing", "change"), Graph(), RevisionController()
        before = (task.revision_id, task.state, revisions.revise_count,
                  tuple(graph.nodes), tuple(graph.edges))
        with self.assertRaises(GraphValidationError):
            revisions.record("revise", task, graph)
        self.assertEqual(before, (task.revision_id, task.state, revisions.revise_count,
                                  tuple(graph.nodes), tuple(graph.edges)))

    def test_run_graph_and_terminal_projection_is_ordered_and_fail_closed(self):
        task = Task("task-run", "run", run_id="run-1", graph_version=1)
        run = Run("run-1", graph_version=1)
        run.graph.add_node(Node("worker", NodeKind.WORKER, "Worker"))
        reducer = StateReducer(task, run)
        reducer.apply(self.event("run_created", run_id="run-1", task_id="task-run",
                                 actor="router", seq=1, graph_version=1))
        reducer.apply(self.event("graph_published", run_id="run-1", task_id="task-run",
                                 actor="router", seq=2, graph_version=2))
        self.assertEqual(task.graph_version, 2)
        self.assertEqual(run.graph_version, 2)
        self.assertIsInstance(reducer.graph_projection, GraphVersion)
        self.assertEqual(reducer.graph_version, 2)
        self.pass_node(reducer, run_id="run-1", task_id="task-run", graph_version=2)
        reducer.apply(self.event("run_terminal", run_id="run-1", task_id="task-run",
                                 actor="router", seq=8, graph_version=2,
                                 payload={"terminal_status": "succeeded"}))
        self.assertEqual(run.terminal_status, TerminalStatus.SUCCEEDED)
        self.assertTrue(run.is_terminal)
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("run_terminal", run_id="run-1", task_id="task-run",
                                     actor="router", seq=4, graph_version=2,
                                     payload={"terminal_status": "failed"}))
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("graph_published", run_id="run-1", task_id="task-run",
                                     actor="router", seq=5, graph_version=1))

        before = run.terminal_status
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("run_terminal", run_id="run-other", task_id="task-run",
                                     actor="router", seq=6, graph_version=2,
                                     payload={"terminal_status": "failed"}))
        self.assertIs(run.terminal_status, before)

    def test_run_succeeded_requires_terminal_execution_nodes(self):
        task = Task("task-pending", "run", run_id="run-pending", graph_version=1)
        run = Run("run-pending", graph_version=1)
        run.graph.add_node(Node("worker", NodeKind.WORKER, "Worker"))
        reducer = StateReducer(task, run)
        reducer.apply(self.event("run_created", run_id="run-pending", task_id="task-pending",
                                 actor="router", seq=1))
        reducer.apply(self.event("graph_published", run_id="run-pending", task_id="task-pending",
                                 actor="router", seq=2))
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("run_terminal", run_id="run-pending",
                                     task_id="task-pending", actor="router", seq=3,
                                     payload={"terminal_status": "succeeded"}))
        self.assertIsNone(run.terminal_status)
        self.assertEqual(run.graph.nodes["worker"].state, NodeState.PENDING)

    def test_node_status_changed_updates_canonical_run_graph(self):
        task = Task("task-node", "run", run_id="run-node", graph_version=1)
        run = Run("run-node", graph_version=1)
        run.graph.add_node(Node("worker", NodeKind.WORKER, "Worker"))
        reducer = StateReducer(task, run)
        self.assertEqual(reducer.node_statuses["worker"], NodeState.PENDING)
        reducer.apply(self.event("run_created", run_id="run-node", task_id="task-node",
                                 actor="router", seq=1))
        reducer.apply(self.event("graph_published", run_id="run-node", task_id="task-node",
                                 actor="router", seq=2))
        actors = {
            "ready": "scheduler", "assigned": "scheduler", "running": "worker",
            "awaiting_verification": "worker", "passed": "verifier",
        }
        for seq, status in enumerate(("ready", "assigned", "running", "awaiting_verification",
                                      "passed"), start=3):
            reducer.apply(self.event("node_status_changed", run_id="run-node",
                                     task_id="task-node", actor=actors[status], seq=seq,
                                     entity={"node_id": "worker"}, payload={"status": status}))
            self.assertEqual(reducer.node_statuses["worker"], NodeState(status))
            self.assertEqual(run.graph.nodes["worker"].state, NodeState(status))

    def test_worker_cannot_claim_that_its_node_passed_verification(self):
        task = Task("task-truth", "run", run_id="run-truth", graph_version=1)
        run = Run("run-truth", graph_version=1)
        run.graph.add_node(Node("worker", NodeKind.WORKER, "Worker"))
        reducer = StateReducer(task, run)
        reducer.apply(self.event("run_created", run_id="run-truth", task_id="task-truth",
                                 actor="router", seq=1))
        reducer.apply(self.event("graph_published", run_id="run-truth", task_id="task-truth",
                                 actor="router", seq=2))
        actors = ("scheduler", "scheduler", "worker", "worker")
        statuses = ("ready", "assigned", "running", "awaiting_verification")
        for seq, (actor, status) in enumerate(zip(actors, statuses), start=3):
            reducer.apply(self.event("node_status_changed", run_id="run-truth",
                                     task_id="task-truth", actor=actor, seq=seq,
                                     entity={"node_id": "worker"}, payload={"status": status}))
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("node_status_changed", run_id="run-truth",
                                     task_id="task-truth", actor="worker", seq=7,
                                     entity={"node_id": "worker"}, payload={"status": "passed"}))

    def test_failed_and_cancelled_run_terminal_preserve_abort_semantics(self):
        for terminal_status in ("failed", "cancelled"):
            with self.subTest(terminal_status=terminal_status):
                task = Task("task-abort", "run", run_id="run-abort", graph_version=1)
                run = Run("run-abort", graph_version=1)
                run.graph.add_node(Node("worker", NodeKind.WORKER, "Worker"))
                reducer = StateReducer(task, run)
                reducer.apply(self.event("run_created", run_id="run-abort", task_id="task-abort",
                                         actor="router", seq=1))
                reducer.apply(self.event("graph_published", run_id="run-abort", task_id="task-abort",
                                         actor="router", seq=2))
                reducer.apply(self.event("run_terminal", run_id="run-abort", task_id="task-abort",
                                         actor="router", seq=3,
                                         payload={"terminal_status": terminal_status}))
                self.assertEqual(run.terminal_status, TerminalStatus(terminal_status))
                self.assertTrue(run.is_terminal)

    def test_run_projection_rejects_reverse_event_order_and_version_mismatch(self):
        task = Task("task-run", "run", run_id="run-1", graph_version=1)
        reducer = StateReducer(task, Run("run-1", graph_version=1))
        terminal = self.event("run_terminal", run_id="run-1", task_id="task-run",
                              actor="router", payload={"terminal_status": "succeeded"})
        with self.assertRaises(StateTransitionError):
            reducer.apply(terminal)
        wrong_entity = self.event("run_created", run_id="run-1", task_id="task-run",
                                  actor="router", entity={"run_id": "run-other"})
        with self.assertRaises(StateTransitionError):
            reducer.apply(wrong_entity)
        wrong_version = self.event("run_created", run_id="run-1", task_id="task-run",
                                   actor="router", graph_version=2)
        with self.assertRaises(StateTransitionError):
            reducer.apply(wrong_version)

    def test_run_projection_does_not_treat_injected_run_as_run_created(self):
        """Codex/Claude repro: a prebuilt Run cannot skip the genesis event."""
        task = Task("task-repro", "run", run_id="run-repro", graph_version=1)
        run = Run("run-repro", graph_version=1)
        reducer = StateReducer(task, run)
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("graph_published", run_id="run-repro",
                                      task_id="task-repro", actor="router"))
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("run_terminal", run_id="run-repro",
                                      task_id="task-repro", actor="router",
                                      payload={"terminal_status": "succeeded"}))
        self.assertIsNone(run.terminal_status)

        task_only = Task("task-only", "run", run_id="run-only", graph_version=1)
        task_only_reducer = StateReducer(task_only)
        self.assertIsNone(task_only_reducer.run)
        with self.assertRaises(StateTransitionError):
            task_only_reducer.apply(self.event("graph_published", run_id="run-only",
                                                task_id="task-only", actor="router"))

    def test_run_projection_requires_first_event_identity_and_rejects_duplicates(self):
        task = Task("task-real", "run", run_id="run-real", graph_version=1)
        reducer = StateReducer(task)
        reducer.run = Run("run-real", graph_version=1)
        reducer.run.graph.add_node(Node("worker", NodeKind.WORKER, "Worker"))
        # The injected object is used only for its graph inventory; lifecycle
        # proof still starts with run_created.
        reducer.node_statuses = {"worker": NodeState.PENDING}
        mismatched_task = self.event("run_created", run_id="run-real",
                                     task_id="task-other", actor="router")
        with self.assertRaises(StateTransitionError):
            reducer.apply(mismatched_task)
        reducer.apply(self.event("run_created", run_id="run-real",
                                 task_id="task-real", actor="router"))
        duplicate_created = self.event("run_created", run_id="run-real",
                                       task_id="task-real", actor="router", seq=2)
        with self.assertRaises(StateTransitionError):
            reducer.apply(duplicate_created)
        reducer.apply(self.event("graph_published", run_id="run-real",
                                 task_id="task-real", actor="router", seq=3))
        self.pass_node(reducer, run_id="run-real", task_id="task-real", start=4)
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("graph_published", run_id="run-real",
                                     task_id="task-real", actor="router", seq=4))
        reducer.apply(self.event("run_terminal", run_id="run-real",
                                 task_id="task-real", actor="router", seq=9,
                                 payload={"terminal_status": "succeeded"}))
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("run_terminal", run_id="run-real",
                                     task_id="task-real", actor="router", seq=10,
                                     payload={"terminal_status": "succeeded"}))

    def test_hardening_succeeded_requires_non_observer_active_nodes_all_passed(self):
        # Each row is an adversarial terminal projection probe.  Non-success
        # terminal node states are never accepted as evidence of success.
        for index, state in enumerate((NodeState.PENDING, NodeState.READY,
                                       NodeState.ASSIGNED, NodeState.RUNNING,
                                       NodeState.AWAITING_VERIFICATION,
                                       NodeState.FAILED, NodeState.CANCELLED,
                                       NodeState.BLOCKED, NodeState.REJECTED,
                                       NodeState.INCONCLUSIVE), start=1):
            with self.subTest(state=state):
                task = Task(f"t-scope-{index}", "scope", run_id=f"r-scope-{index}")
                run = Run(f"r-scope-{index}")
                run.graph.add_node(Node("worker", NodeKind.WORKER, "worker", state=state))
                reducer = StateReducer(task, run)
                reducer.apply(self.event("run_created", run_id=run.run_id,
                                         task_id=task.task_id, actor="router", seq=1))
                reducer.apply(self.event("graph_published", run_id=run.run_id,
                                         task_id=task.task_id, actor="router", seq=2))
                with self.assertRaises(StateTransitionError):
                    reducer.apply(self.event("run_terminal", run_id=run.run_id,
                                             task_id=task.task_id, actor="router", seq=3,
                                             payload={"terminal_status": "succeeded"}))
                self.assertIsNone(run.terminal_status)

        for nodes in ((), (("observer", NodeKind.OBSERVER),)):
            with self.subTest(nodes=nodes):
                task, run, reducer = self.published_reducer(
                    task_id="t-empty", run_id="r-empty", nodes=nodes)
                with self.assertRaises(StateTransitionError):
                    reducer.apply(self.event("run_terminal", run_id=run.run_id,
                                             task_id=task.task_id, actor="router", seq=3,
                                             payload={"terminal_status": "succeeded"}))

    def test_hardening_terminal_rejects_every_later_mutation_event(self):
        task, run, reducer = self.published_reducer()
        self.pass_node(reducer)
        reducer.apply(self.event("run_terminal", run_id=run.run_id, task_id=task.task_id,
                                 actor="router", seq=8,
                                 payload={"terminal_status": "succeeded"}))
        mutation_events = (
            ("run_terminal", {"terminal_status": "failed"}, {}),
            ("graph_published", {}, {}),
            ("node_status_changed", {"status": "ready"}, {"node_id": "worker"}),
            ("verdict_recorded", {"verdict": "pass", "evidence_ids": ["ev"]}, {}),
            ("platform_verdict_recorded", {"platform": "windows", "status": "pass",
                                             "fixture_id": "fx", "evidence_id": "ev"}, {}),
            ("node_created", {"node_id": "intruder"}, {}),
            ("edge_created", {"source": "worker", "target": "worker"}, {}),
            ("heartbeat", {}, {}),
            ("progress_reported", {}, {}),
        )
        for seq, (event_type, payload, entity) in enumerate(mutation_events, start=9):
            with self.subTest(event_type=event_type):
                with self.assertRaises(StateTransitionError):
                    reducer.apply(self.event(event_type, run_id=run.run_id,
                                             task_id=task.task_id, actor="router", seq=seq,
                                             payload=payload, entity=entity))
        self.assertEqual(run.graph.nodes["worker"].state, NodeState.PASSED)
        self.assertEqual(run.terminal_status, TerminalStatus.SUCCEEDED)

    def test_hardening_node_identity_matrix_and_unknown_membership(self):
        task, run, reducer = self.published_reducer()
        cases = (
            ({}, {"status": "ready"}, "missing entity ID"),
            ({}, {"node_id": "worker", "status": "ready"}, "payload-only ID"),
            ({"node_id": "ghost"}, {"node_id": "worker", "status": "ready"}, "conflict"),
            ({"node_id": "ghost"}, {"status": "ready"}, "unknown graph ID"),
        )
        for entity, payload, label in cases:
            with self.subTest(label=label):
                with self.assertRaises(StateTransitionError):
                    reducer.apply(self.event("node_status_changed", run_id=run.run_id,
                                             task_id=task.task_id, actor="worker",
                                             entity=entity, payload=payload))
        reducer.apply(self.event("node_status_changed", run_id=run.run_id,
                                 task_id=task.task_id, actor="worker",
                                 entity={"node_id": "worker"},
                                 payload={"node_id": "worker", "status": "ready"}))
        self.assertEqual(run.graph.nodes["worker"].state, NodeState.READY)
        reducer.apply(self.event("node_status_changed", run_id=run.run_id,
                                 task_id=task.task_id, actor="worker",
                                 entity={"node_id": "worker"}, payload={"status": "assigned"}))
        self.assertEqual(run.graph.nodes["worker"].state, NodeState.ASSIGNED)

    def test_hardening_runless_compatibility_is_pre_registered_only(self):
        reducer = StateReducer(Task("task_test", "legacy"),
                               node_statuses={"legacy": NodeState.PENDING})
        reducer.apply(self.event("node_status_changed", entity={"node_id": "legacy"},
                                 payload={"status": "ready"}))
        self.assertEqual(reducer.node_statuses["legacy"], NodeState.READY)
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("node_status_changed", entity={"node_id": "ghost"},
                                     payload={"status": "ready"}))
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("run_terminal", payload={"terminal_status": "failed"}))
        self.assertIsNone(reducer.run)

    def test_hardening_lifecycle_events_need_run_created_and_graph_published(self):
        task = Task("task-life", "lifecycle", run_id="run-life")
        run = Run("run-life")
        run.graph.add_node(Node("worker", NodeKind.WORKER, "worker"))
        reducer = StateReducer(task, run)
        gated = (
            ("node_status_changed", {"status": "ready"}, {"node_id": "worker"}),
            ("verdict_recorded", {"verdict": "pass", "evidence_ids": ["ev"]}, {}),
            ("platform_verdict_recorded", {"platform": "windows", "status": "deferred"}, {}),
        )
        for event_type, payload, entity in gated:
            with self.subTest(stage="before run_created", event_type=event_type):
                with self.assertRaises(StateTransitionError):
                    reducer.apply(self.event(event_type, run_id="run-life",
                                             task_id="task-life", payload=payload, entity=entity))
        reducer.apply(self.event("run_created", run_id="run-life", task_id="task-life",
                                 actor="router", seq=1))
        for event_type, payload, entity in gated:
            with self.subTest(stage="before graph_published", event_type=event_type):
                with self.assertRaises(StateTransitionError):
                    reducer.apply(self.event(event_type, run_id="run-life",
                                             task_id="task-life", payload=payload, entity=entity,
                                             seq=2))
        reducer.apply(self.event("graph_published", run_id="run-life", task_id="task-life",
                                 actor="router", seq=3))
        reducer.apply(self.event("node_status_changed", run_id="run-life", task_id="task-life",
                                 entity={"node_id": "worker"}, payload={"status": "ready"}, seq=4))

    def test_hardening_published_snapshot_rejects_external_topology_and_state_mutation(self):
        task, run, reducer = self.published_reducer()
        run.graph.nodes["worker"].metadata["tampered"] = True
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("heartbeat", run_id=run.run_id, task_id=task.task_id))

        task, run, reducer = self.published_reducer(task_id="task-edge", run_id="run-edge")
        run.graph.add_node(Node("intruder", NodeKind.WORKER, "intruder"))
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("heartbeat", run_id=run.run_id, task_id=task.task_id))

        task, run, reducer = self.published_reducer(task_id="task-state", run_id="run-state")
        run.graph.nodes["worker"].state = NodeState.READY
        with self.assertRaises(StateTransitionError):
            reducer.apply(self.event("heartbeat", run_id=run.run_id, task_id=task.task_id))

    def test_hardening_non_success_terminal_evidence_and_abort_semantics(self):
        for status, payload in (("failed", {}), ("cancelled", {}),
                                ("rejected", {"reason": "assignment denied"}),
                                ("blocked", {"blocking_reason": "approval pending"}),
                                ("inconclusive", {"inconclusive_reason": "missing evidence"})):
            with self.subTest(status=status):
                task, run, reducer = self.published_reducer(
                    task_id=f"task-{status}", run_id=f"run-{status}")
                reducer.apply(self.event("run_terminal", run_id=run.run_id,
                                         task_id=task.task_id, actor="router", seq=3,
                                         payload={"terminal_status": status, **payload}))
                self.assertEqual(run.terminal_status, TerminalStatus(status))
        for status, payload in (("rejected", {}), ("blocked", {}), ("inconclusive", {})):
            with self.subTest(missing=status):
                task, run, reducer = self.published_reducer(
                    task_id=f"task-missing-{status}", run_id=f"run-missing-{status}")
                with self.assertRaises(StateTransitionError):
                    reducer.apply(self.event("run_terminal", run_id=run.run_id,
                                             task_id=task.task_id, actor="router", seq=3,
                                             payload={"terminal_status": status, **payload}))

    def test_hardening_rework_excludes_replaced_node_from_active_scope(self):
        task = Task("task-rework", "rework", run_id="run-rework")
        run = Run("run-rework")
        run.graph.add_node(Node("old", NodeKind.WORKER, "old", state=NodeState.FAILED))
        run.graph.add_node(Node("new", NodeKind.WORKER, "new"))
        run.graph.add_edge(Edge("new", "old", EdgeKind.REWORK_OF))
        reducer = StateReducer(task, run)
        reducer.apply(self.event("run_created", run_id=run.run_id, task_id=task.task_id,
                                 actor="router", seq=1))
        reducer.apply(self.event("graph_published", run_id=run.run_id, task_id=task.task_id,
                                 actor="router", seq=2))
        self.pass_node(reducer, node_id="new", run_id=run.run_id, task_id=task.task_id)
        reducer.apply(self.event("run_terminal", run_id=run.run_id, task_id=task.task_id,
                                 actor="router", seq=8,
                                 payload={"terminal_status": "succeeded"}))
        self.assertEqual(run.terminal_status, TerminalStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
