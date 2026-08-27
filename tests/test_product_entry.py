import asyncio
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_adapters.direct import RoutedExecutionAdapter
from graphori_adapters.generic.adapter import GenericProcessAdapter, ProcessCommand
from graphori_core import (
    AdapterCapabilities,
    Availability,
    DispatchHandle,
    ExecutionResult,
    RunConstraints,
    RunSpec,
    RuntimeEvent,
    RuntimeRunHandle,
    SessionHandle,
)
from graphori_core.product import ProductPlanCompiler, execute_product, render_plan_preview
from graphori_core.product_cli import _render_human_status, build_parser
from graphori_core.presentation import normalized_locale, objective_locale, resolve_locale
from graphori_core.run_spec import extract_acceptance_criteria


class RecordingAdapter:
    def __init__(self, adapter_id):
        self.adapter_id = adapter_id
        self.started = []
        self.sessions = {}
        self.contexts = {}

    def probe(self):
        return AdapterCapabilities(self.adapter_id, True, max_concurrency=2)

    async def prepare_run(self, plan):
        return RuntimeRunHandle(self.adapter_id, f"run:{self.adapter_id}")

    async def start_session(self, node):
        self.started.append(node.node_id)
        handle = SessionHandle(self.adapter_id, f"session:{node.node_id}")
        self.sessions[handle.value] = node.node_id
        return handle

    async def dispatch(self, session, node, context):
        self.contexts[node.node_id] = context
        return DispatchHandle(self.adapter_id, f"dispatch:{node.node_id}", node.node_id)

    async def events(self, dispatch):
        yield RuntimeEvent(
            "worker_finished", dispatch.node_id,
            "verifier" if dispatch.node_id == "v1" else "worker",
            {"outcome": "succeeded", "summary": f"result from {dispatch.node_id}"},
        )

    async def acknowledge(self, event):
        return None

    async def cancel(self, dispatch, reason):
        return None

    async def collect(self, dispatch):
        return ExecutionResult(
            "succeeded", runtime_id=dispatch.value,
            attempt_id=f"attempt:{dispatch.node_id}:1",
        )

    async def release(self, session):
        self.sessions.pop(session.value, None)


class WritingAdapter(RecordingAdapter):
    def __init__(self, adapter_id, root):
        super().__init__(adapter_id)
        self.root = Path(root)

    async def dispatch(self, session, node, context):
        handle = await super().dispatch(session, node, context)
        (self.root / "result.txt").write_text("ready\n", encoding="utf-8")
        return handle


class ProductPlanTests(unittest.TestCase):
    def setUp(self):
        self.compiler = ProductPlanCompiler(availability={
            "gpt-5.6-luna": Availability.AVAILABLE,
            "claude-sonnet-5": Availability.AVAILABLE,
        })

    def test_research_and_implementation_plan_has_visible_teams_routes_and_fan_in(self):
        spec = RunSpec(
            "Android의 새 탐지 방식을 조사하고 구현해줘", "codex", "/workspace",
            constraints=RunConstraints(max_parallelism=2),
        )
        bundle = self.compiler.compile(
            spec, run_id="run-product", write_scope=("src/",),
            verification_argv=(sys.executable, "-m", "unittest", "discover", "-s", "tests"),
        )
        plan = bundle.plan
        self.assertEqual([node.node_id for node in plan.nodes], ["d1", "i1", "r1", "r2", "v1"])
        self.assertEqual(next(node for node in plan.nodes if node.node_id == "d1").dependencies,
                         ("r1", "r2"))
        self.assertEqual(next(node for node in plan.nodes if node.node_id == "v1").adapter,
                         "generic-process")
        self.assertEqual(next(node for node in plan.nodes if node.node_id == "v1").role,
                         "verifier")
        self.assertTrue(all(node.skill_bindings == () for node in plan.nodes))
        self.assertEqual({team.team_id: team.status for team in plan.teams}, {
            "planning": "active", "research": "active", "design": "active",
            "implementation": "active", "verification": "active",
        })
        self.assertTrue(next(node for node in plan.nodes if node.node_id == "i1").model)
        self.assertIn("v1", bundle.process_commands)

    def test_preview_shows_team_model_skill_status_and_graph(self):
        spec = RunSpec("작은 버그를 수정해줘", "codex", "/workspace")
        bundle = self.compiler.compile(spec, run_id="run-bug", write_scope=("src/a.py",))
        preview = render_plan_preview(bundle.plan)
        self.assertIn("Graphori Plan v1", preview)
        self.assertIn("Research · Omitted", preview)
        self.assertIn("Implementation · Active", preview)
        self.assertIn("Model:", preview)
        self.assertIn("Route: Automated check", preview)
        self.assertIn("Skills: None", preview)
        self.assertIn("i1 -> v1", preview)

    def test_korean_preview_uses_purpose_titles_and_explains_omissions(self):
        spec = RunSpec("작은 버그를 수정해줘", "codex", "/workspace")
        bundle = self.compiler.compile(spec, run_id="run-ko", write_scope=("src/a.py",))
        preview = render_plan_preview(bundle.plan, locale="ko")
        self.assertIn("이번 작업은 2단계로 진행합니다.", preview)
        self.assertIn("1. 제작팀:", preview)
        self.assertIn("2. 품질관리팀:", preview)
        self.assertIn("작은 버그를 수정", preview)
        self.assertIn("이번에는 건너뛰는 단계", preview)
        self.assertIn("조사팀:", preview)
        self.assertIn("지금 가진 자료만으로 충분해", preview)
        self.assertIn("살펴보는 정도:", preview)
        self.assertIn("담당:", preview)
        self.assertIn("일하는 순서", preview)
        self.assertIn("1단계가 끝나면 2단계를 시작합니다.", preview)
        self.assertNotIn("Skill:", preview)
        self.assertNotIn("실행 방식:", preview)
        self.assertNotIn("작업 강도:", preview)
        self.assertNotIn("i1:", preview)

    def test_korean_status_explains_progress_without_internal_details(self):
        rendered = _render_human_status({
            "status": "running",
            "activity": {"elapsed_ms": 65_000, "last_activity_age_seconds": 4},
            "liveness": {"status": "heartbeat_recent"},
            "provider_progress": {"percent": None},
            "nodes": [{
                "team_id": "implementation", "status": "running",
                "display_title": "노트 구조 만들기", "selected_route": "codex",
                "requested_model": "internal-model-id", "requested_effort": "medium",
            }],
            "verification": {"acceptance_criteria": [{
                "criterion_id": "AC-01",
                "criterion": "AC-01: 기존 노트를 그대로 보존",
                "status": "NOT_PROVEN", "evidence_ids": ["internal-evidence-id"],
            }]},
            "metrics": {"usage": {"status": "known", "input_tokens": 1_000_000}},
        }, locale="ko")

        self.assertIn("지금 작업 상황", rendered)
        self.assertIn("숫자로 확인할 수 없음", rendered)
        self.assertIn("아직 확인 전", rendered)
        self.assertNotIn("internal-model-id", rendered)
        self.assertNotIn("internal-evidence-id", rendered)
        self.assertNotIn("input_tokens", rendered)

    def test_explicit_criteria_are_extracted_without_an_llm(self):
        criteria = extract_acceptance_criteria(
            "기능을 고쳐라. AC-01 기존 동작 유지. AC-02: 별도 프로세스 재실행",
        )
        self.assertEqual(criteria, (
            "AC-01: 기존 동작 유지", "AC-02: 별도 프로세스 재실행",
        ))

    def test_locale_changes_only_preview_not_plan_digest(self):
        bundle = self.compiler.compile(
            RunSpec("작은 버그를 수정해줘", "codex", "/workspace"),
            run_id="run-locale", write_scope=("src/a.py",),
        )
        digest = bundle.plan.digest()
        self.assertNotEqual(
            render_plan_preview(bundle.plan, locale="ko"),
            render_plan_preview(bundle.plan, locale="en"),
        )
        self.assertEqual(bundle.plan.digest(), digest)

    def test_auto_locale_is_presentation_only_and_keeps_canonical_digest(self):
        bundle = self.compiler.compile(
            RunSpec("small bounded change", "codex", "/workspace"),
            run_id="run-auto-locale", write_scope=("src/a.py",),
        )
        digest = bundle.plan.digest()
        previous = os.environ.get("LC_ALL")
        try:
            os.environ["LC_ALL"] = "ko_KR.UTF-8"
            self.assertEqual(normalized_locale("auto"), "ko")
            self.assertIn("이번 작업은", render_plan_preview(bundle.plan, locale="auto"))
            self.assertEqual(bundle.plan.digest(), digest)
        finally:
            if previous is None:
                os.environ.pop("LC_ALL", None)
            else:
                os.environ["LC_ALL"] = previous

    def test_auto_locale_prefers_configuration_then_objective(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            previous = os.environ.get("XDG_CONFIG_HOME")
            os.environ["XDG_CONFIG_HOME"] = str(root / "user-config")
            try:
                self.assertEqual(objective_locale("이 버그를 고쳐줘"), "ko")
                self.assertEqual(objective_locale("Fix this race condition"), "en")
                self.assertEqual(resolve_locale("auto", root=root, objective="이 버그를 고쳐줘"), "ko")
                (root / ".graphori").mkdir()
                (root / ".graphori" / "config.json").write_text(
                    '{"language": "en"}\n', encoding="utf-8",
                )
                self.assertEqual(resolve_locale("auto", root=root, objective="이 버그를 고쳐줘"), "en")
                self.assertEqual(resolve_locale("ko", root=root, objective="Fix it"), "ko")
            finally:
                if previous is None:
                    os.environ.pop("XDG_CONFIG_HOME", None)
                else:
                    os.environ["XDG_CONFIG_HOME"] = previous

    def test_lang_and_legacy_locale_flags_share_the_presentation_option(self):
        parser = build_parser()
        self.assertEqual(parser.parse_args(["plan", "Fix it", "--lang", "en"]).locale, "en")
        self.assertEqual(parser.parse_args(["plan", "Fix it", "--locale", "ko"]).locale, "ko")

    def test_preview_is_published_before_safe_read_only_nodes_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = RunSpec(
                "최신 공식 문서를 조사해줘", "codex", temp,
                constraints=RunConstraints(max_parallelism=2),
            )
            bundle = self.compiler.compile(spec, run_id="run-preview")
            codex = RecordingAdapter("codex-cli")
            routed = RoutedExecutionAdapter({"codex": codex})
            from graphori_core import GraphExecutionEngine
            engine = GraphExecutionEngine(
                adapter=routed, plan_factory=lambda _spec: bundle.plan,
            )
            observed = []

            async def scenario():
                return await execute_product(
                    engine, spec, bundle.plan,
                    preview_sink=lambda preview: observed.append((preview, tuple(codex.started))),
                )

            projection = asyncio.run(scenario())
            self.assertEqual(observed[0][1], ())
            self.assertEqual(set(codex.started), {"r1", "r2"})
            self.assertEqual(projection.terminal_status, "succeeded")

    def test_product_bundle_runs_through_engine_and_independent_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = RunSpec(
                "작은 버그를 수정해줘", "codex", temp,
                acceptance_criteria=("AC-01: result.txt 내용 확인",),
            )
            bundle = self.compiler.compile(
                spec, run_id="run-product-e2e", write_scope=("result.txt",),
                verification_argv=(
                    sys.executable, "-c",
                    "from pathlib import Path; assert Path('result.txt').read_text() == 'ready\\n'",
                ),
            )
            codex = WritingAdapter("codex-cli", root)
            generic = GenericProcessAdapter(
                workspace_root=root,
                commands={
                    key: ProcessCommand(value.argv, verdict_file=value.verdict_file)
                    for key, value in bundle.process_commands.items()
                },
            )
            routed = RoutedExecutionAdapter({
                "codex": codex, "generic-process": generic,
            })
            from graphori_core import GraphExecutionEngine
            engine = GraphExecutionEngine(
                adapter=routed, plan_factory=lambda _spec: bundle.plan,
            )
            previews = []
            projection = asyncio.run(execute_product(
                engine, spec, bundle.plan, preview_sink=previews.append,
            ))
            self.assertEqual(projection.terminal_status, "succeeded")
            self.assertEqual(projection.node_states, {"i1": "passed", "v1": "passed"})
            self.assertTrue(previews and previews[0].startswith("Graphori Plan v1"))
            from graphori_core.dashboard import DashboardStore
            read_model, _events = DashboardStore(root).canonical_projection(bundle.plan.run_id)
            self.assertEqual(
                read_model.verification["requirements_status"], "not_proven",
            )
            self.assertEqual(
                read_model.verification["acceptance_criteria"][0]["status"],
                "NOT_PROVEN",
            )

    def test_contending_product_run_does_not_persist_sidecars_before_lock(self):
        from graphori_core import GraphExecutionEngine
        with tempfile.TemporaryDirectory() as temp:
            spec = RunSpec("작은 버그를 수정해줘", "codex", temp)
            bundle = self.compiler.compile(
                spec, run_id="run-contended-product", write_scope=("result.txt",),
            )
            first = GraphExecutionEngine(
                adapter=RecordingAdapter("codex-cli"),
                plan_factory=lambda _spec: bundle.plan,
            )
            second = GraphExecutionEngine(
                adapter=RecordingAdapter("codex-cli"),
                plan_factory=lambda _spec: bundle.plan,
            )

            async def scenario():
                handle = await first.start(spec)
                callbacks = []
                try:
                    with self.assertRaisesRegex(RuntimeError, "Another Graphori run"):
                        await execute_product(
                            second, spec, bundle.plan,
                            started_sink=lambda _handle: callbacks.append(True),
                        )
                finally:
                    first.close(handle.run_id)
                return callbacks

            self.assertEqual(asyncio.run(scenario()), [])


class RoutedAdapterTests(unittest.TestCase):
    def test_sessions_and_dispatches_stay_bound_to_the_selected_adapter(self):
        codex = RecordingAdapter("codex-cli")
        generic = RecordingAdapter("generic-process")
        routed = RoutedExecutionAdapter({"codex": codex, "generic-process": generic})

        async def scenario():
            from graphori_core import NodeSpec, RunPlan, ContextBundle
            worker = NodeSpec("i1", "implementation", "I", "work", "worker", adapter="codex")
            verifier = NodeSpec("v1", "verification", "V", "verify", "verifier",
                                adapter="generic-process")
            plan = RunPlan("run", 1, "committed", nodes=(worker, verifier))
            await routed.prepare_run(plan)
            first = await routed.start_session(worker)
            second = await routed.start_session(verifier)
            d1 = await routed.dispatch(first, worker, ContextBundle.from_node(worker))
            d2 = await routed.dispatch(second, verifier, ContextBundle.from_node(verifier))
            self.assertEqual((await routed.collect(d1)).runtime_id, "dispatch:i1")
            self.assertEqual((await routed.collect(d2)).runtime_id, "dispatch:v1")
            await routed.release(first)
            await routed.release(second)

        asyncio.run(scenario())
        self.assertEqual(codex.started, ["i1"])
        self.assertEqual(generic.started, ["v1"])

    def test_dependency_results_are_handed_off_from_the_canonical_journal(self):
        from graphori_core import GraphExecutionEngine, NodeSpec, RunPlan
        with tempfile.TemporaryDirectory() as temp:
            first = NodeSpec(
                "r1", "research", "R", "research", "worker", adapter="codex",
                verification_policy="deterministic",
            )
            second = NodeSpec(
                "d1", "design", "D", "design", "worker", adapter="codex",
                dependencies=("r1",), verification_policy="deterministic",
            )
            plan = RunPlan("run-handoff", 1, "committed", nodes=(first, second))
            adapter = RecordingAdapter("codex-cli")
            engine = GraphExecutionEngine(
                adapter=RoutedExecutionAdapter({"codex": adapter}),
                plan_factory=lambda _spec: plan,
            )

            async def scenario():
                await engine.start(RunSpec("handoff", "codex", temp))
                await engine.advance(plan.run_id)
                await engine.advance(plan.run_id)

            asyncio.run(scenario())
            self.assertIn(
                "r1: result from r1", adapter.contexts["d1"].objective,
            )


if __name__ == "__main__":
    unittest.main()
