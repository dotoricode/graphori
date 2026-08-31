"""Deterministic product entry planning and human-readable Plan Preview."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import sys
from typing import Mapping

from .acceptance import (
    AcceptanceContract, AcceptanceContractCompiler, AcceptanceProof, AcceptanceSource,
)
from .model_routing import Availability, ModelRouter, default_model_catalog
from .presentation import (
    effort_label, normalized_locale, omission_reason_label, route_label, status_label, team_label,
)
from .run_plan import NodeSpec, RunPlan, TeamSpec
from .run_spec import RunSpec, criterion_id
from .sprout import ProofObligation
from .execution_engine import GraphExecutionEngine, RunProjection


TEAM_ORDER = ("planning", "research", "design", "implementation", "verification")


@dataclass(frozen=True)
class ProductCommand:
    argv: tuple[str, ...]
    verdict_file: str = ""
    verdict_from_exit: bool = False
    criterion_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductPlanBundle:
    plan: RunPlan
    profile: str
    process_commands: Mapping[str, ProductCommand]
    assumptions: tuple[str, ...] = ()
    acceptance_contract: AcceptanceContract | None = None


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


def _verifier_command(
        argv: tuple[str, ...], verdict_file: str,
        criterion_ids: tuple[str, ...] = ()) -> ProductCommand:
    del verdict_file
    return ProductCommand(
        argv, verdict_from_exit=True, criterion_ids=criterion_ids,
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
        known = dict(availability or {})
        catalog = default_model_catalog(known)
        self.router = ModelRouter(catalog)
        self.ready_provider_families = frozenset(
            model.provider for model in catalog.provider_catalog.models
            if model.availability is Availability.AVAILABLE
        )

    @staticmethod
    def _cross_review_warranted(
            spec: RunSpec, profile: str, write_scope: tuple[str, ...]) -> bool:
        policy = spec.constraints.cross_review
        if policy == "never":
            return False
        if policy == "always":
            return True
        sensitive = _contains(spec.objective, (
            "security", "authentication", "authorization", "permission", "secret",
            "보안", "인증", "인가", "권한", "비밀",
        ))
        broad_scope = len(set(write_scope)) >= 2 or any(
            scope in {".", "**", "**/*"}
            or scope.endswith("/")
            or any(marker in scope for marker in "*?[")
            or not Path(scope.rstrip("/")).suffix
            for scope in write_scope
        )
        synthesis = profile in {"research-and-implementation", "design-and-implementation"}
        high_uncertainty = spec.constraints.uncertainty == "high"
        return sensitive or broad_scope or synthesis or high_uncertainty

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
            verification_argv: tuple[str, ...] | None = None,
            verification_criteria: tuple[str, ...] = (),
            repository_acceptance_proofs: tuple[AcceptanceProof, ...] = (),
            deterministic_acceptance_proofs: tuple[AcceptanceProof, ...] = (),
            llm_acceptance_proofs: tuple[AcceptanceProof, ...] = ()) -> ProductPlanBundle:
        profile = _profile(spec.objective)
        display_title = _objective_title(spec.objective, "the requested change")
        declared_criteria = {criterion_id(item) for item in spec.acceptance_criteria}
        mapped_criteria = tuple(sorted(set(verification_criteria)))
        unknown_criteria = set(mapped_criteria) - declared_criteria
        if unknown_criteria:
            raise ValueError(
                f"unknown verification criteria: {', '.join(sorted(unknown_criteria))}"
            )
        contract_compiler = AcceptanceContractCompiler()
        user_proofs = contract_compiler.user_proofs(spec.acceptance_criteria)
        mapped_proofs = tuple(AcceptanceProof(
            criterion=next(
                item for item in spec.acceptance_criteria
                if criterion_id(item) == identifier
            ),
            proof=ProofObligation(
                f"deterministic:{identifier}", "verification-command",
            ),
            source=AcceptanceSource.DETERMINISTIC,
        ) for identifier in mapped_criteria)
        acceptance_contract = contract_compiler.compile(
            user=user_proofs,
            repository=repository_acceptance_proofs,
            deterministic=tuple((*mapped_proofs, *deterministic_acceptance_proofs)),
            llm=llm_acceptance_proofs,
        )
        nodes: list[NodeSpec] = []
        if profile in {"research", "research-and-implementation"}:
            nodes.extend((
                NodeSpec(
                    "r1", "research", "Gather authoritative sources",
                    f"Research current primary-source evidence for: {spec.objective}", "worker",
                    role="researcher",
                    read_scope=read_scope, task_kind="research",
                    verification_policy="deterministic", estimated_startup_ms=5_000,
                    estimated_execution_ms=90_000, permission_profile="read_only",
                ),
                NodeSpec(
                    "r2", "research", "Establish the scope of the change",
                    f"Inspect the current workspace and identify bounded impact for: {spec.objective}",
                    "worker", role="researcher", read_scope=read_scope, task_kind="research",
                    verification_policy="deterministic", estimated_startup_ms=5_000,
                    estimated_execution_ms=80_000, permission_profile="read_only",
                ),
            ))
        if profile in {"design-and-implementation", "research-and-implementation"}:
            dependencies = ("r1", "r2") if profile == "research-and-implementation" else ()
            nodes.append(NodeSpec(
                "d1", "design", f"Design an approach: {display_title}",
                f"Design the smallest compatible implementation for: {spec.objective}", "worker",
                role="designer",
                dependencies=dependencies, read_scope=read_scope, task_kind="design",
                verification_policy="deterministic", estimated_startup_ms=5_000,
                estimated_execution_ms=50_000, permission_profile="read_only",
            ))
        if profile != "research":
            dependency = "d1" if profile in {"design-and-implementation", "research-and-implementation"} else ""
            implementation_adapter = spec.constraints.implementation_provider
            uncertainty = {
                "auto": 0, "low": 1, "medium": 2, "high": 3,
            }[spec.constraints.uncertainty]
            nodes.append(NodeSpec(
                "i1", "implementation", display_title, spec.objective, "worker",
                role="implementer",
                dependencies=(dependency,) if dependency else (), read_scope=read_scope,
                write_scope=write_scope, task_kind="bounded_implementation",
                adapter_requirements=(
                    () if implementation_adapter == "auto" else (implementation_adapter,)
                ),
                verification_policy="independent", estimated_startup_ms=5_000,
                estimated_execution_ms=90_000, uncertainty=uncertainty,
            ))

        unrouted = RunPlan(
            run_id, 1, "committed", nodes=tuple(nodes),
            critical_path=tuple(
                node_id for node_id in ("r1", "d1", "i1")
                if any(node.node_id == node_id for node in nodes)
            ),
        )
        routed = self.router.route_plan(unrouted)
        assumptions = [
            "Planning is the current coordinator; no Planner sub-agent is created.",
            "External Skills remain unbound by default.",
        ]
        review_enabled = False
        if profile != "research" and self._cross_review_warranted(spec, profile, write_scope):
            if self.ready_provider_families == {"openai", "anthropic"}:
                implementation = next(node for node in routed.nodes if node.node_id == "i1")
                review = NodeSpec(
                    "cr1", "verification", f"Cross-review: {display_title}",
                    (
                        "Review the implementation for correctness, security, scope, and "
                        "acceptance-criteria gaps. Do not modify files. Report status=succeeded "
                        "only when no blocking issue remains; otherwise report status=failed and "
                        "describe each blocking issue in limitations."
                    ),
                    "worker", role="reviewer", dependencies=("i1",),
                    read_scope=tuple(sorted(set((*read_scope, *write_scope)))), write_scope=(),
                    task_kind="verification", verification_policy="deterministic",
                    estimated_startup_ms=5_000, estimated_execution_ms=45_000,
                    permission_profile="read_only", requires_cross_provider=True,
                    excluded_provider=implementation.provider_family,
                    evidence_requirements=("cross-provider-review-report",),
                    reviews_unverified_dependencies=True,
                )
                unrouted = replace(unrouted, nodes=tuple((*unrouted.nodes, review)))
                routed = self.router.route_plan(unrouted)
                review_enabled = True
            else:
                ready_names = ", ".join(sorted(self.ready_provider_families)) or "none"
                assumptions.append(
                    "Cross-provider review omitted: both Codex and Claude Code must be "
                    f"installed, compatible, and authenticated (ready providers: {ready_names})."
                )
        commands: dict[str, ProductCommand] = {}
        if profile != "research":
            argv = verification_argv or default_verification_argv(spec.workspace)
            verifier = NodeSpec(
                "v1", "verification", f"Verify: {display_title}",
                "Run the deterministic acceptance command and record an independent verdict.",
                "verifier", role="verifier",
                dependencies=(("i1", "cr1") if review_enabled else ("i1",)),
                read_scope=tuple(sorted(set((*read_scope, *write_scope)))),
                write_scope=(), adapter="generic-process",
                provider="generic-process", task_kind="deterministic",
                verification_policy="independent", estimated_execution_ms=30_000,
                permission_profile="read_only",
                routing_reason_codes=("DETERMINISTIC_VERIFIER",),
                evidence_requirements=tuple(
                    f"criterion:{identifier}" for identifier in mapped_criteria
                ),
            )
            routed = replace(routed, nodes=tuple((*routed.nodes, verifier)))
            commands["v1"] = _verifier_command(argv, "", mapped_criteria)
            commands["v1:rework:1"] = _verifier_command(
                argv, "", mapped_criteria,
            )
        routed = replace(
            routed, teams=self._teams(routed.nodes),
            nodes=tuple(replace(node, acceptance_criteria=spec.acceptance_criteria)
                        for node in routed.nodes),
            critical_path=tuple((
                *routed.critical_path,
                *(("cr1",) if review_enabled else ()),
                *(("v1",) if profile != "research" else ()),
            )),
            assumptions=tuple(assumptions),
        )
        return ProductPlanBundle(
            routed, profile, commands, routed.assumptions, acceptance_contract,
        )


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
