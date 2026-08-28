import asyncio
from contextlib import redirect_stdout
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from graphori_core import (
    ActivationScope, AdapterCapabilities, DispatchHandle, ExecutionResult, GraphExecutionEngine,
    NodeSpec, RunConstraints, RunPlan, RunSpec, RuntimeEvent, RuntimeRunHandle,
    Scheduler, SchedulerPolicy, SessionHandle, SkillBinding, TeamSpec,
)
from graphori_core.dashboard import DashboardStore, create_server
from graphori_core.product_cli import main as product_main
from graphori_core.projection import _criterion_evidence, _usage_summary


class DashboardFakeAdapter:
    adapter_id = "fake"

    def probe(self):
        return AdapterCapabilities(self.adapter_id, True, max_concurrency=4)

    def route_health_snapshot(self, plan):
        return (
            {"route": "direct-codex", "provider": "openai", "health": "ready",
             "selected": True, "reason": ""},
            {"route": "orca-codex", "provider": "openai", "health": "blocked",
             "selected": False, "reason": "launch strategy blocked"},
        )

    async def prepare_run(self, plan):
        return RuntimeRunHandle(self.adapter_id, plan.run_id)

    async def start_session(self, node):
        return SessionHandle(self.adapter_id, f"session:{node.node_id}")

    async def dispatch(self, session, node, context):
        return DispatchHandle(self.adapter_id, f"dispatch:{node.node_id}", node.node_id)

    async def events(self, dispatch):
        actor = "verifier" if dispatch.node_id.startswith("verify") else "worker"
        yield RuntimeEvent(
            "worker_finished", dispatch.node_id, actor,
            {"outcome": "succeeded", "summary": f"completed {dispatch.node_id}",
             "evidence_ids": [f"ev:{dispatch.node_id}"]},
        )
        if actor == "verifier":
            yield RuntimeEvent(
                "verdict_recorded", dispatch.node_id, "verifier",
                {"verdict": "pass", "evidence_ids": ["ev:independent"]},
            )

    async def cancel(self, dispatch, reason):
        return None

    async def collect(self, dispatch):
        return ExecutionResult("succeeded", evidence_ids=(f"ev:{dispatch.node_id}",))

    async def release(self, session):
        return None


class OutcomeUnknownAdapter(DashboardFakeAdapter):
    async def events(self, dispatch):
        if False:
            yield

    async def collect(self, dispatch):
        return ExecutionResult("outcome_unknown")


class FailedAdapter(DashboardFakeAdapter):
    async def events(self, dispatch):
        if False:
            yield

    async def collect(self, dispatch):
        return ExecutionResult("failed", exit_code=2, error_kind="process_exit")


class ReviseOnceAdapter(DashboardFakeAdapter):
    async def events(self, dispatch):
        verifier = dispatch.node_id.startswith("verify")
        yield RuntimeEvent(
            "worker_finished", dispatch.node_id, "verifier" if verifier else "worker",
            {"outcome": "succeeded", "evidence_ids": [f"ev:{dispatch.node_id}"]},
        )
        if verifier:
            yield RuntimeEvent(
                "verdict_recorded", dispatch.node_id, "verifier",
                {"verdict": "revise" if dispatch.node_id == "verify" else "pass",
                 "evidence_ids": [f"ev:{dispatch.node_id}"]},
            )


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def execute(self, plan, *, waves=10, adapter=None, scheduler=None):
        spec = RunSpec(
            "canonical dashboard fixture", "test", str(self.root),
            constraints=RunConstraints(max_parallelism=2),
        )
        engine = GraphExecutionEngine(
            adapter=adapter or DashboardFakeAdapter(), plan_factory=lambda _spec: plan,
            scheduler=scheduler,
        )

        async def scenario():
            handle = await engine.start(spec)
            for _ in range(waves):
                if engine.snapshot(handle.run_id).terminal_status is not None:
                    break
                batch = await engine.advance(handle.run_id)
                if not batch.scheduling.dispatches:
                    break
            return engine.snapshot(handle.run_id)

        return engine, asyncio.run(scenario())

    @staticmethod
    def read_sse_until(response, event_name):
        lines = []
        while True:
            line = response.readline().decode()
            if not line:
                break
            lines.append(line)
            if line == "\n" and any(item == f"event: {event_name}\n" for item in lines[-5:]):
                break
        return "".join(lines)

    def simple_plan(self, run_id="run-dashboard"):
        return RunPlan(
            run_id, 1, "committed",
            teams=(
                TeamSpec("planning", "active"), TeamSpec("research", "omitted"),
                TeamSpec("design", "omitted"), TeamSpec("implementation", "active"),
                TeamSpec("verification", "active"),
            ),
            nodes=(
                NodeSpec(
                    "worker-1", "implementation", "Dashboard CSS", "Implement", "worker",
                    role="implementer", provider="openai", adapter="codex",
                    model="gpt-5.6-luna", effort="medium",
                    verification_policy="independent",
                ),
                NodeSpec(
                    "verify-1", "verification", "Verify", "Verify implementation", "verifier",
                    role="verifier", dependencies=("worker-1",), adapter="generic-process",
                    provider="generic-process", verification_policy="independent",
                ),
            ),
        )

    def install_legacy_fixture(self):
        return self.install_fixture("legacy-pre-pr10.jsonl", "run-legacy-dashboard")

    def install_fixture(self, filename, run_id):
        source = Path(__file__).parent / "fixtures" / "dashboard" / filename
        target = self.root / ".graphori" / "runs" / run_id / "journal" / "journal.jsonl"
        target.parent.mkdir(parents=True)
        shutil.copyfile(source, target)
        return run_id, target

    def test_current_v3_fixture_stays_on_recorded_metadata_path(self):
        run_id, _journal = self.install_fixture("current-v3.jsonl", "run-current-v3-dashboard")
        projection, _ = DashboardStore(self.root).canonical_projection(run_id)
        snapshot = projection.to_dict()
        self.assertEqual(snapshot["objective"], "recorded current fixture")
        self.assertEqual(snapshot["metadata_provenance"]["source"], "canonical_v3")
        self.assertEqual(snapshot["metadata_provenance"]["run_spec"]["source"], "recorded")

    def test_legacy_journal_replays_without_rewriting_bytes_or_guessing_metadata(self):
        run_id, journal = self.install_legacy_fixture()
        original = journal.read_bytes()
        projections = [DashboardStore(self.root).canonical_projection(run_id)[0] for _ in range(10)]
        snapshot = projections[0].to_dict()

        self.assertEqual(len({item.projection_digest for item in projections}), 1)
        self.assertEqual(snapshot["metadata_provenance"]["source"], "legacy_journal")
        self.assertEqual(snapshot["metadata_provenance"]["run_spec"]["source"], "unknown")
        self.assertEqual(snapshot["metadata_provenance"]["run_plan"]["source"], "legacy_default")
        self.assertEqual(snapshot["objective"], "unknown")
        self.assertEqual(snapshot["nodes"][0]["title"], "Unknown legacy node: legacy-worker")
        self.assertEqual(journal.read_bytes(), original)

    def test_legacy_cold_cli_replay_and_dashboard_share_one_digest(self):
        run_id, _journal = self.install_legacy_fixture()
        first, _ = DashboardStore(self.root).canonical_projection(run_id)
        second, _ = DashboardStore(self.root).canonical_projection(run_id)
        values = []
        for command in ("status", "replay"):
            stream = io.StringIO()
            with redirect_stdout(stream):
                self.assertEqual(product_main([
                    command, "--root", str(self.root), "--run-id", run_id, "--json",
                ]), 0)
            values.append(json.loads(stream.getvalue()))
        dashboard, _ = DashboardStore(self.root).snapshot(run_id)
        self.assertEqual(first.projection_digest, second.projection_digest)
        self.assertEqual({item["projection_digest"] for item in values},
                         {first.projection_digest})
        self.assertEqual(dashboard["projection_digest"], first.projection_digest)

    def test_legacy_replay_is_stable_in_fresh_python_processes(self):
        run_id, _journal = self.install_legacy_fixture()
        expected, _ = DashboardStore(self.root).canonical_projection(run_id)
        environment = dict(os.environ)
        source_root = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = os.pathsep.join(filter(None, (
            source_root, environment.get("PYTHONPATH", ""),
        )))
        command = [
            sys.executable, "-m", "graphori_core.product_cli", "replay",
            "--root", str(self.root), "--run-id", run_id, "--json",
        ]
        digests = []
        for _ in range(2):
            result = subprocess.run(
                command, cwd=Path(__file__).resolve().parents[1], env=environment,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            digests.append(json.loads(result.stdout)["projection_digest"])
        self.assertEqual(digests, [expected.projection_digest] * 2)

    def test_partial_or_conflicting_metadata_fails_closed_instead_of_legacy_fallback(self):
        run_id, journal = self.install_legacy_fixture()
        run_root = journal.parents[1]
        (run_root / "run-spec.json").write_text(json.dumps({
            "schema_version": 2, "objective": "recorded", "host": "test",
            "workspace": "test", "constraints": {}, "premium_policy": {},
            "runtime_preference": ["native_host"],
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "partial canonical dashboard metadata"):
            DashboardStore(self.root).canonical_projection(run_id)

        run_id, journal = self.install_fixture(
            "current-v3.jsonl", "run-current-v3-dashboard",
        )
        run_root = journal.parents[1]
        first_event = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])
        conflicting = dict(first_event["payload"]["run_spec"])
        conflicting["objective"] = "conflicting sidecar objective"
        (run_root / "run-spec.json").write_text(
            json.dumps(conflicting), encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "ambiguous RunSpec metadata sources"):
            DashboardStore(self.root).canonical_projection(run_id)

    def test_malformed_canonical_metadata_fails_closed(self):
        run_id, journal = self.install_legacy_fixture()
        (journal.parents[1] / "run-plan.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid plan sidecar"):
            DashboardStore(self.root).canonical_projection(run_id)

    def test_dashboard_and_engine_share_the_same_projection_digest(self):
        plan = self.simple_plan()
        _engine, engine_projection = self.execute(plan)
        dashboard, _ = DashboardStore(self.root).snapshot(plan.run_id)
        self.assertEqual(dashboard["schema_version"], 3)
        self.assertEqual(dashboard["projection_digest"], engine_projection.projection_digest)
        self.assertEqual(dashboard["graph_digest"], engine_projection.graph_digest)
        self.assertEqual(dashboard["terminal_status"], "succeeded")
        self.assertEqual(dashboard["progress"], {
            "completed": 2, "required": 2, "percent": 100,
            "basis": "verified_terminal_nodes",
        })

    def test_dashboard_replays_the_published_scheduler_policy(self):
        plan = RunPlan(
            "run-scheduler-policy", 1, "committed",
            nodes=(
                NodeSpec("a", "research", "A", "A", "worker",
                         estimated_execution_ms=10_000, verification_policy="deterministic"),
                NodeSpec("b", "research", "B", "B", "worker",
                         estimated_execution_ms=10_000, verification_policy="deterministic"),
            ),
        )
        policy = SchedulerPolicy(max_wip=2, min_parallel_gain_ms=0,
                                 min_parallel_gain_ratio=0)
        _engine, live = self.execute(plan, waves=0, scheduler=Scheduler(policy))
        replayed, _ = DashboardStore(self.root).canonical_projection(plan.run_id)
        self.assertEqual(replayed.ready, ("a", "b"))
        self.assertEqual(replayed.projection_digest, live.projection_digest)

    def test_projection_exposes_five_teams_routes_skills_and_separate_verification(self):
        plan = self.simple_plan("run-details")
        self.execute(plan)
        snapshot, _ = DashboardStore(self.root).snapshot(plan.run_id)
        self.assertEqual(len(snapshot["teams"]), 5)
        self.assertEqual({item["team_id"]: item["status"] for item in snapshot["teams"]}, {
            "planning": "complete", "research": "omitted", "design": "omitted",
            "implementation": "complete", "verification": "complete",
        })
        worker = next(item for item in snapshot["nodes"] if item["node_id"] == "worker-1")
        self.assertEqual(worker["team_id"], "implementation")
        self.assertEqual(worker["requested_model"], "gpt-5.6-luna")
        self.assertEqual(worker["requested_effort"], "medium")
        self.assertEqual(worker["skills"], [])
        self.assertEqual(worker["execution"]["status"], "succeeded")
        self.assertEqual(worker["verification"]["status"], "pass")
        self.assertIn("ev:worker-1", worker["evidence_ids"])
        self.assertEqual(snapshot["actual_agent_count"], 2)
        self.assertEqual(len(snapshot["edges"]), 1)
        self.assertEqual(
            {item["route"]: item["health"] for item in snapshot["available_routes"]},
            {"direct-codex": "ready", "orca-codex": "blocked"},
        )

    def test_worker_completion_remains_awaiting_verification_in_dashboard(self):
        plan = RunPlan(
            "run-pending", 1, "committed",
            teams=(TeamSpec("planning", "active"), TeamSpec("implementation", "active")),
            nodes=(NodeSpec(
                "worker", "implementation", "Work", "Work", "worker",
                verification_policy="independent",
            ),),
        )
        _engine, projection = self.execute(plan, waves=1)
        snapshot, _ = DashboardStore(self.root).snapshot(plan.run_id)
        self.assertEqual(projection.node_states["worker"], "awaiting_verification")
        node = snapshot["nodes"][0]
        self.assertEqual(node["execution"]["status"], "succeeded")
        self.assertEqual(node["verification"]["status"], "pending")
        self.assertEqual(node["provider_progress"], {
            "state": "unknown", "percent": None, "updated_at": None, "source": None,
        })
        self.assertEqual(node["liveness"]["status"], "not_running")
        self.assertIsInstance(node["activity"]["elapsed_ms"], int)
        self.assertEqual(snapshot["terminal_status"], None)

    def test_parallel_fan_in_projection_uses_published_graph_identity(self):
        plan = RunPlan(
            "run-fan-in", 1, "committed",
            teams=(
                TeamSpec("planning", "active"), TeamSpec("research", "active"),
                TeamSpec("design", "active"),
            ),
            nodes=(
                NodeSpec("r1", "research", "Research A", "Research A", "worker",
                         verification_policy="deterministic", estimated_execution_ms=60_000),
                NodeSpec("r2", "research", "Research B", "Research B", "worker",
                         verification_policy="deterministic", estimated_execution_ms=60_000),
                NodeSpec("d1", "design", "Fan-in design", "Design", "worker",
                         dependencies=("r1", "r2"), verification_policy="deterministic"),
            ),
        )
        self.execute(plan, waves=1)
        snapshot, _ = DashboardStore(self.root).snapshot(plan.run_id)
        nodes = {item["node_id"]: item for item in snapshot["nodes"]}
        teams = {item["team_id"]: item for item in snapshot["teams"]}
        self.assertEqual(nodes["r1"]["status"], "passed")
        self.assertEqual(nodes["r2"]["status"], "passed")
        self.assertEqual(nodes["d1"]["scheduler_status"], "ready")
        self.assertEqual(teams["research"]["status"], "complete")
        self.assertEqual(teams["design"]["status"], "active")
        self.assertEqual(
            {(edge["from"], edge["to"]) for edge in snapshot["edges"]},
            {("r1", "d1"), ("r2", "d1")},
        )

    def test_premium_gate_and_skill_binding_are_canonical_dashboard_fields(self):
        binding = SkillBinding(
            "example", "Example", "sha256:abc", ".graphori/skills/abc/SKILL.md",
            "",
            activation_scope=ActivationScope.ATTEMPT,
        )
        node = NodeSpec(
            "premium", "design", "Premium design", "Design", "worker",
            provider="openai", provider_family="openai", adapter="codex",
            model="gpt-5.6-sol", model_family="gpt-5.6-sol", effort="high",
            approval_required=True, approval_class="premium",
            routing_decision_digest="sha256:routing", skill_bindings=(binding,),
        )
        plan = RunPlan(
            "run-gate", 1, "committed",
            teams=(TeamSpec("planning", "active"), TeamSpec("design", "blocked")),
            nodes=(node,),
        )
        self.execute(plan, waves=0)
        snapshot, _ = DashboardStore(self.root).snapshot(plan.run_id)
        self.assertEqual(snapshot["status"], "waiting_approval")
        self.assertEqual(snapshot["gates"][0]["status"], "pending")
        self.assertEqual(snapshot["nodes"][0]["scheduler_status"], "blocked")
        self.assertEqual(snapshot["nodes"][0]["skills"][0]["skill_id"], "example")
        self.assertEqual(
            next(team for team in snapshot["teams"] if team["team_id"] == "design")["status"],
            "blocked",
        )

    def test_outcome_unknown_and_cancelled_are_not_invented_as_failure_or_success(self):
        unknown_plan = RunPlan(
            "run-unknown", 1, "committed",
            nodes=(NodeSpec("work", "implementation", "Work", "Work", "worker"),),
        )
        self.execute(unknown_plan, waves=1, adapter=OutcomeUnknownAdapter())
        unknown, _ = DashboardStore(self.root).snapshot(unknown_plan.run_id)
        self.assertEqual(unknown["status"], "outcome_unknown")
        self.assertEqual(unknown["nodes"][0]["status"], "outcome_unknown")

        cancel_plan = RunPlan(
            "run-cancel", 1, "committed",
            nodes=(NodeSpec("work", "implementation", "Work", "Work", "worker"),),
        )
        spec = RunSpec("cancel", "test", str(self.root))
        engine = GraphExecutionEngine(
            adapter=DashboardFakeAdapter(), plan_factory=lambda _spec: cancel_plan,
        )

        async def cancel():
            await engine.start(spec)
            await engine.cancel(cancel_plan.run_id, "user requested")

        asyncio.run(cancel())
        cancelled, _ = DashboardStore(self.root).snapshot(cancel_plan.run_id)
        self.assertEqual(cancelled["terminal_status"], "cancelled")
        self.assertEqual(cancelled["nodes"][0]["status"], "cancelled")

    def test_failed_worker_blocks_downstream_without_dashboard_inference(self):
        plan = RunPlan(
            "run-failure", 1, "committed",
            nodes=(
                NodeSpec("work", "implementation", "Work", "Work", "worker"),
                NodeSpec("verify", "verification", "Verify", "Verify", "verifier",
                         dependencies=("work",)),
            ),
        )
        self.execute(plan, adapter=FailedAdapter())
        snapshot, _ = DashboardStore(self.root).snapshot(plan.run_id)
        nodes = {item["node_id"]: item for item in snapshot["nodes"]}
        self.assertEqual(snapshot["terminal_status"], "failed")
        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual(nodes["work"]["status"], "failed")
        self.assertEqual(nodes["work"]["execution"]["status"], "failed")
        self.assertEqual(nodes["verify"]["status"], "pending")
        self.assertIsNone(nodes["verify"]["scheduler_status"])

    def test_rework_nodes_and_edges_remain_visible_after_cold_replay(self):
        plan = RunPlan(
            "run-rework", 1, "committed",
            nodes=(
                NodeSpec("work", "implementation", "Work", "Work", "worker",
                         verification_policy="independent"),
                NodeSpec("verify", "verification", "Verify", "Verify", "verifier",
                         dependencies=("work",), verification_policy="independent"),
            ),
        )
        self.execute(plan, adapter=ReviseOnceAdapter())
        snapshot, _ = DashboardStore(self.root).snapshot(plan.run_id)
        identities = {item["node_id"] for item in snapshot["nodes"]}
        self.assertIn("work:rework:1", identities)
        self.assertIn("verify:rework:1", identities)
        self.assertTrue(any(edge["from"] == "work:rework:1" for edge in snapshot["edges"]))
        self.assertEqual(snapshot["rework_counts"], {"work": 1})

    def test_cold_dashboard_replay_is_deterministic(self):
        plan = self.simple_plan("run-cold")
        _engine, live = self.execute(plan)
        first, _ = DashboardStore(self.root).canonical_projection(plan.run_id)
        second, _ = DashboardStore(self.root).canonical_projection(plan.run_id)
        self.assertEqual(first.projection_digest, live.projection_digest)
        self.assertEqual(second.projection_digest, live.projection_digest)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_status_replay_and_dashboard_publish_the_same_digest(self):
        plan = self.simple_plan("run-cli-consistency")
        _engine, live = self.execute(plan)
        outputs = []
        for command in ("status", "replay"):
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = product_main([
                    command, "--root", str(self.root), "--run-id", plan.run_id, "--json",
                ])
            self.assertEqual(code, 0)
            outputs.append(json.loads(stream.getvalue()))
        dashboard, _ = DashboardStore(self.root).snapshot(plan.run_id)
        self.assertEqual(outputs[0]["projection_digest"], live.projection_digest)
        self.assertEqual(outputs[1]["projection_digest"], live.projection_digest)
        self.assertEqual(dashboard["projection_digest"], live.projection_digest)
        self.assertTrue(outputs[1]["replay_verified"])

    def test_recent_event_exposes_evidence_without_inventing_it(self):
        plan = self.simple_plan("run-evidence")
        self.execute(plan)
        snapshot, _ = DashboardStore(self.root).snapshot(plan.run_id)
        evidence_events = [item for item in snapshot["recentEvents"] if item["evidence_ids"]]
        self.assertTrue(evidence_events)
        self.assertTrue(all("payload" in item for item in evidence_events))
        self.assertTrue(all(item["producer"]["role"] for item in evidence_events))

    def test_sse_snapshot_replay_gap_and_last_event_id_use_canonical_snapshot(self):
        plan = self.simple_plan("run-sse")
        self.execute(plan)
        server = create_server(self.root, replay_limit=2)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}/runs/{plan.run_id}/events"
            request = Request(base, headers={"Last-Event-ID": "0"})
            with urlopen(request, timeout=5) as response:
                data = self.read_sse_until(response, "replay_gap")
            self.assertIn("event: snapshot", data)
            self.assertIn('"schema_version":3', data)
            self.assertIn("event: replay_gap", data)
        finally:
            server.shutdown()
            server.server_close()

    def test_static_file_is_confined(self):
        static = self.root / "static"
        static.mkdir()
        (static / "ok.txt").write_text("ok")
        server = create_server(self.root, static_dir=static)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_address[1]}/ok.txt", timeout=5) as response:
                self.assertEqual(response.read(), b"ok")
            with self.assertRaises(Exception):
                urlopen(f"http://127.0.0.1:{server.server_address[1]}/../secret", timeout=5)
        finally:
            server.shutdown()
            server.server_close()


class PresentationEvidenceTests(unittest.TestCase):
    def test_runtime_usage_wins_over_unknown_event_envelope(self):
        summary = _usage_summary(({
            "usage": {"status": "unknown"},
            "payload": {"runtime_metadata": {"usage": {
                "input_tokens": 2_840_921,
                "cached_input_tokens": 2_707_200,
            }}},
        },))
        self.assertEqual(summary, {
            "status": "known", "input_tokens": 2_840_921,
            "cached_input_tokens": 2_707_200, "new_input_tokens": 133_721,
        })

    def test_verifier_command_exit_does_not_prove_every_criterion(self):
        node = NodeSpec(
            "verify", "verification", "검증", "검증", "verifier",
            acceptance_criteria=("AC-01: 전체 요구사항 충족",),
        )
        result = _criterion_evidence(node, ({
            "actor": {"role": "verifier"},
            "payload": {"evidence_ids": ["subprocess:verifier-command:exit:0"]},
        },))
        self.assertEqual(result[0]["status"], "NOT_PROVEN")

    def test_cold_process_requires_test_boundary_evidence(self):
        node = NodeSpec(
            "verify", "verification", "검증", "검증", "verifier",
            acceptance_criteria=("AC-11: 별도 프로세스 재실행",),
        )
        weak = _criterion_evidence(node, ({
            "actor": {"role": "verifier"},
            "payload": {"criterion_evidence": {"AC-11": {
                "status": "PROVEN",
                "evidence_ids": ["subprocess:verifier-command:exit:0"],
            }}},
        },))
        strong = _criterion_evidence(node, ({
            "actor": {"role": "verifier"},
            "payload": {"criterion_evidence": {"AC-11": {
                "status": "PROVEN",
                "evidence_ids": ["subprocess:test:test_cold_replay"],
            }}},
        },))
        self.assertEqual(weak[0]["status"], "NOT_PROVEN")
        self.assertEqual(strong[0]["status"], "PROVEN")

    def test_explicit_criterion_command_requires_matching_plan_requirement(self):
        evidence = ({
            "actor": {"role": "verifier"},
            "payload": {"criterion_evidence": {"AC-12": {
                "status": "PROVEN",
                "evidence_ids": ["subprocess:criterion-command:AC-12:exit:0"],
            }}},
        },)
        unmapped = NodeSpec(
            "verify", "verification", "Verify", "verify", "verifier",
            acceptance_criteria=("AC-12: cold process check",),
        )
        mapped = NodeSpec(
            "verify", "verification", "Verify", "verify", "verifier",
            acceptance_criteria=("AC-12: cold process check",),
            evidence_requirements=("criterion:AC-12",),
        )
        self.assertEqual(_criterion_evidence(unmapped, evidence)[0]["status"], "NOT_PROVEN")
        self.assertEqual(_criterion_evidence(mapped, evidence)[0]["status"], "PROVEN")


if __name__ == "__main__":
    unittest.main()
