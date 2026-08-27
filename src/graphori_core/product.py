"""Deterministic product entry planning and human-readable Plan Preview."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import sys
from typing import Mapping

from .model_routing import Availability, ModelRouter, default_model_catalog
from .presentation import (
    effort_label, normalized_locale, omission_reason_label, route_label, status_label, team_label,
)
from .run_plan import NodeSpec, RunPlan, TeamSpec
from .run_spec import RunSpec
from .execution_engine import GraphExecutionEngine, RunProjection


TEAM_ORDER = ("planning", "research", "design", "implementation", "verification")


@dataclass(frozen=True)
class ProductCommand:
    argv: tuple[str, ...]
    verdict_file: str


@dataclass(frozen=True)
class ProductPlanBundle:
    plan: RunPlan
    profile: str
    process_commands: Mapping[str, ProductCommand]
    assumptions: tuple[str, ...] = ()


def _contains(value: str, tokens: tuple[str, ...]) -> bool:
    lowered = value.casefold()
    return any(token.casefold() in lowered for token in tokens)


def _profile(objective: str) -> str:
    research = _contains(objective, ("조사", "리서치", "research", "최신", "문서 확인"))
    design = _contains(objective, ("설계", "architecture", "design"))
    write = _contains(
        objective,
        ("구현", "추가", "수정", "고쳐", "버그", "fix", "build", "implement", "change"),
    )
    bug = _contains(objective, ("버그", "오류", "고쳐", "fix", "bug", "regression"))
    if research and write:
        return "research-and-implementation"
    if research:
        return "research"
    if bug:
        return "bug-fix"
    if design and write:
        return "design-and-implementation"
    return "implementation"


def _objective_title(objective: str, fallback: str) -> str:
    """Derive a short display title without a second model call."""

    sentences = [item.strip(" :-\n\t") for item in objective.replace("\n", " ").split(".")]
    for sentence in sentences:
        if not sentence:
            continue
        lowered = sentence.casefold()
        if lowered.startswith("graphori v2 pr") and ("구현" in sentence or "implement" in lowered):
            continue
        title = sentence
        for suffix in ("해줘", "해주세요", "한다", "합니다"):
            if title.endswith(suffix):
                title = title[:-len(suffix)].rstrip()
                break
        if title:
            return title if len(title) <= 52 else title[:49].rstrip() + "…"
    return fallback


def _verifier_command(argv: tuple[str, ...], verdict_file: str) -> ProductCommand:
    script = (
        "import json,pathlib,subprocess,sys;"
        "command=json.loads(sys.argv[1]);target=pathlib.Path(sys.argv[2]);"
        "result=subprocess.run(command,check=False);target.parent.mkdir(parents=True,exist_ok=True);"
        "verdict='pass' if result.returncode==0 else 'revise';"
        "target.write_text(json.dumps({'verdict':verdict,'evidence_ids':['deterministic:'+str(result.returncode)]}))"
    )
    return ProductCommand(
        (sys.executable, "-c", script, json.dumps(list(argv)), verdict_file), verdict_file,
    )


def default_verification_argv(workspace: str) -> tuple[str, ...]:
    root = Path(workspace)
    if (root / "tests").is_dir():
        return (sys.executable, "-m", "unittest", "discover", "-s", "tests")
    if (root / "src").is_dir():
        return (sys.executable, "-m", "compileall", "-q", "src")
    return ("git", "diff", "--check")


class ProductPlanCompiler:
    """Compile a small product graph; the current host remains Planning."""

    def __init__(self, *, availability: Mapping[str, Availability] | None = None) -> None:
        self.router = ModelRouter(default_model_catalog(availability or {}))

    @staticmethod
    def _teams(nodes: tuple[NodeSpec, ...]) -> tuple[TeamSpec, ...]:
        active = {node.team_id for node in nodes} | {"planning"}
        omitted_reasons = {
            "research": "external_research_not_required",
            "design": "design_step_not_required",
            "implementation": "implementation_not_required",
            "verification": "verification_not_required",
        }
        return tuple(TeamSpec(
            team, "active" if team in active else "omitted",
            "" if team in active else omitted_reasons.get(team, "not_in_plan"),
        ) for team in TEAM_ORDER)

    def compile(
            self, spec: RunSpec, *, run_id: str,
            read_scope: tuple[str, ...] = (".",),
            write_scope: tuple[str, ...] = (".",),
            verification_argv: tuple[str, ...] | None = None) -> ProductPlanBundle:
        profile = _profile(spec.objective)
        display_title = _objective_title(spec.objective, "요청한 변경")
        nodes: list[NodeSpec] = []
        if profile in {"research", "research-and-implementation"}:
            nodes.extend((
                NodeSpec(
                    "r1", "research", "공식 근거 조사",
                    f"Research current primary-source evidence for: {spec.objective}", "worker",
                    role="researcher",
                    read_scope=read_scope, task_kind="research",
                    verification_policy="deterministic", estimated_startup_ms=5_000,
                    estimated_execution_ms=90_000, permission_profile="read_only",
                ),
                NodeSpec(
                    "r2", "research", "변경 범위 확인",
                    f"Inspect the current workspace and identify bounded impact for: {spec.objective}",
                    "worker", role="researcher", read_scope=read_scope, task_kind="research",
                    verification_policy="deterministic", estimated_startup_ms=5_000,
                    estimated_execution_ms=80_000, permission_profile="read_only",
                ),
            ))
        if profile in {"design-and-implementation", "research-and-implementation"}:
            dependencies = ("r1", "r2") if profile == "research-and-implementation" else ()
            nodes.append(NodeSpec(
                "d1", "design", f"{display_title} 방법 정리",
                f"Design the smallest compatible implementation for: {spec.objective}", "worker",
                role="designer",
                dependencies=dependencies, read_scope=read_scope, task_kind="design",
                verification_policy="deterministic", estimated_startup_ms=5_000,
                estimated_execution_ms=50_000, permission_profile="read_only",
            ))
        if profile != "research":
            dependency = "d1" if profile in {"design-and-implementation", "research-and-implementation"} else ""
            nodes.append(NodeSpec(
                "i1", "implementation", display_title, spec.objective, "worker",
                role="implementer",
                dependencies=(dependency,) if dependency else (), read_scope=read_scope,
                write_scope=write_scope, task_kind="bounded_implementation",
                verification_policy="independent", estimated_startup_ms=5_000,
                estimated_execution_ms=90_000,
            ))

        unrouted = RunPlan(
            run_id, 1, "committed", nodes=tuple(nodes),
            critical_path=tuple(
                node_id for node_id in ("r1", "d1", "i1")
                if any(node.node_id == node_id for node in nodes)
            ),
        )
        routed = self.router.route_plan(unrouted)
        commands: dict[str, ProductCommand] = {}
        if profile != "research":
            verdict_file = f".graphori/verdicts/{run_id}-v1.json"
            rework_verdict = f".graphori/verdicts/{run_id}-v1-rework-1.json"
            argv = verification_argv or default_verification_argv(spec.workspace)
            verifier = NodeSpec(
                "v1", "verification", f"{display_title} 결과 확인",
                "Run the deterministic acceptance command and record an independent verdict.",
                "verifier", role="verifier", dependencies=("i1",),
                read_scope=tuple(sorted(set((*read_scope, *write_scope)))),
                write_scope=(verdict_file,), adapter="generic-process",
                provider="generic-process", task_kind="deterministic",
                verification_policy="independent", estimated_execution_ms=30_000,
                routing_reason_codes=("DETERMINISTIC_VERIFIER",),
            )
            routed = replace(routed, nodes=tuple((*routed.nodes, verifier)))
            commands["v1"] = _verifier_command(argv, verdict_file)
            commands["v1:rework:1"] = _verifier_command(argv, rework_verdict)
        routed = replace(
            routed, teams=self._teams(routed.nodes),
            nodes=tuple(replace(node, acceptance_criteria=spec.acceptance_criteria)
                        for node in routed.nodes),
            critical_path=tuple((*routed.critical_path, *(("v1",) if profile != "research" else ()))),
            assumptions=(
                "Planning is the current coordinator; no Planner sub-agent is created.",
                "External Skills remain unbound by default.",
            ),
        )
        return ProductPlanBundle(routed, profile, commands, routed.assumptions)


def _render_korean_plan_preview(plan: RunPlan) -> str:
    """Render the plan as a short explanation, not an operations report."""

    nodes_by_team = {team: [] for team in TEAM_ORDER}
    for node in plan.nodes:
        nodes_by_team[node.team_id].append(node)
    ordered_nodes = [
        node for team in TEAM_ORDER if team != "planning"
        for node in nodes_by_team[team]
    ]
    stage_number = {node.node_id: index for index, node in enumerate(ordered_nodes, 1)}
    lines = [f"이번 작업은 {len(ordered_nodes)}단계로 진행합니다.", ""]

    for index, node in enumerate(ordered_nodes, 1):
        route = node.adapter or node.provider
        skills = ", ".join(binding.name for binding in node.skill_bindings)
        title = (
            "앞 단계의 결과가 요구사항을 만족하는지 확인"
            if node.team_id == "verification" else node.title
        )
        lines.append(f"{index}. {team_label(node.team_id, 'ko')}: {title}")
        if route == "generic-process":
            lines.append("   컴퓨터가 정해진 방법으로 결과를 다시 확인합니다.")
        else:
            lines.append(
                f"   담당: {route_label(route, 'ko')}"
            )
            if node.effort:
                lines.append(f"   살펴보는 정도: {effort_label(node.effort, 'ko')}")
        if skills:
            lines.append(f"   함께 사용할 작업법: {skills}")
        if node.acceptance_criteria:
            lines.append(f"   끝나기 전에 확인할 내용: {len(node.acceptance_criteria)}가지")
        if node.approval_required:
            lines.append(
                "   시작하려면 먼저 고성능 AI 사용 허락이 필요합니다."
                + (f" 대상: {node.model}" if node.model else "")
            )
        lines.append("")

    omitted = []
    for team in TEAM_ORDER:
        if team == "planning" or nodes_by_team[team]:
            continue
        declared = next((item for item in plan.teams if item.team_id == team), None)
        reason = declared.reason if declared else ""
        explanation = omission_reason_label(reason, "ko") if reason else ""
        omitted.append(f"- {team_label(team, 'ko')}: {explanation or '이번 작업에는 필요하지 않습니다.'}")
    if omitted:
        lines.extend(("이번에는 건너뛰는 단계", *omitted, ""))

    edges = sorted(
        (dependency, node.node_id) for node in plan.nodes for dependency in node.dependencies
    )
    lines.append("일하는 순서")
    if edges:
        lines.extend(
            f"- {stage_number[source]}단계가 끝나면 {stage_number[target]}단계를 시작합니다."
            for source, target in edges
        )
    else:
        lines.append("- 각 단계는 서로 기다리지 않고 시작할 수 있습니다.")
    return "\n".join(lines) + "\n"


def render_plan_preview(plan: RunPlan, *, locale: str = "en") -> str:
    locale = normalized_locale(locale)
    if locale == "ko":
        return _render_korean_plan_preview(plan)

    nodes_by_team = {team: [] for team in TEAM_ORDER}
    for node in plan.nodes:
        nodes_by_team[node.team_id].append(node)
    korean = False
    team_states = {
        team.team_id: status_label(team.status, locale) for team in plan.teams
    }
    lines = [
        "이번 작업은 이렇게 진행합니다." if korean else f"Graphori Plan v{plan.plan_version}",
        "" if korean else "",
    ]
    for team in TEAM_ORDER:
        lines.append(
            f"{team_label(team, locale)} · "
            f"{team_states.get(team, status_label('standby', locale))}"
        )
        if team == "planning":
            lines.append(
                "제가 전체 순서를 정하고 각 단계의 결과를 모읍니다."
                if korean else "The current Graphori coordinator manages this work."
            )
        elif not nodes_by_team[team]:
            declared = next((item for item in plan.teams if item.team_id == team), None)
            reason = declared.reason if declared else ""
            lines.append((omission_reason_label(reason, locale) if reason else "") or (
                "이번 작업에는 사용하지 않습니다."
                if korean else "This team is not used for this run."
            ))
        else:
            for index, node in enumerate(nodes_by_team[team]):
                branch = "└─" if index == len(nodes_by_team[team]) - 1 else "├─"
                route = node.adapter or node.provider
                skills = ", ".join(binding.name for binding in node.skill_bindings)
                lines.extend((
                    f"{branch} {node.title}" if korean else f"{branch} {node.node_id}: {node.title}",
                    f"   {'담당' if korean else 'Route'}: {route_label(route, locale)}",
                    f"   {'사용할 AI' if korean else 'Model'}: {node.model or ('없음' if korean else 'None')}",
                    f"   {'살펴보는 정도' if korean else 'Effort'}: {effort_label(node.effort, locale) if node.effort else ('해당 없음' if korean else 'Not applicable')}",
                    *(() if korean and not skills else (
                        f"   {'함께 사용할 작업법' if korean else 'Skills'}: {skills or 'None'}",
                    )),
                    f"   {'지금 상태' if korean else 'Status'}: {'시작 전에 고성능 AI 사용 허락이 필요함' if korean and node.approval_required else status_label('ready', locale)}",
                ))
                if node.acceptance_criteria:
                    lines.append(
                        f"   {'끝나기 전에 확인할 내용' if korean else 'Criteria'}: "
                        + (f"{len(node.acceptance_criteria)}가지" if korean else ", ".join(
                            item.split(":", 1)[0] for item in node.acceptance_criteria
                        ))
                    )
        lines.append("")
    edges = sorted(
        (dependency, node.node_id) for node in plan.nodes for dependency in node.dependencies
    )
    lines.append("일하는 순서" if korean else "Graph")
    titles = {node.node_id: node.title for node in plan.nodes}
    lines.extend(
        f"- {titles.get(source, source)} → {titles.get(target, target)}"
        if korean else f"- {source} -> {target}"
        for source, target in edges
    )
    if not edges:
        lines.append("- 앞 단계가 없어 바로 시작할 수 있습니다." if korean else "- independent root Nodes")
    return "\n".join(lines) + "\n"


async def execute_product(
        engine: GraphExecutionEngine, spec: RunSpec, plan: RunPlan, *,
        preview_sink=None, preview_locale: str = "en", started_sink=None) -> RunProjection:
    """Publish the preview before the first dispatch, then settle runnable waves."""

    if preview_sink is not None:
        preview_sink(render_plan_preview(plan, locale=preview_locale))
    handle = await engine.start(spec)
    try:
        if started_sink is not None:
            started_sink(handle)
        max_waves = max(2, len(plan.nodes) * 3)
        for _ in range(max_waves):
            projection = engine.snapshot(handle.run_id)
            if projection.terminal_status is not None or projection.open_gates:
                return projection
            batch = await engine.advance(handle.run_id)
            projection = engine.snapshot(handle.run_id)
            if projection.terminal_status is not None or projection.open_gates:
                return projection
            if not batch.scheduling.dispatches:
                return projection
        raise RuntimeError("product execution did not settle within the bounded wave limit")
    finally:
        # execute_product owns this bounded execution session.  Releasing the
        # OS lock on every normal, early-return, and exceptional exit prevents
        # a completed CLI invocation from retaining canonical writer authority.
        engine.close(handle.run_id)
