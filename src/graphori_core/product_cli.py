"""Production-facing ``graphori plan|run`` entrypoint for the v2 Engine."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
import uuid
import webbrowser

from graphori_adapters.claude.adapter import ClaudeCodeExecutionAdapter
from graphori_adapters.codex.adapter import CodexExecutionAdapter
from graphori_adapters.direct import RoutedExecutionAdapter
from graphori_adapters.generic.adapter import GenericProcessAdapter, ProcessCommand
from graphori_adapters.live_verify import LiveVerifyAdapter

from .execution_engine import GraphExecutionEngine
from .dashboard import DashboardStore, create_server
from .journal import ensure_run_dirs
from .journal import RunPaths, replay_journal
from .model_routing import Availability, default_model_catalog
from .process_supervisor import ProcessLimits
from .presentation import (doctor_label, effort_label, normalized_locale,
                           resolve_locale, route_label, runtime_label,
                           status_label, team_label)
from .product import ProductPlanCompiler, execute_product, render_plan_preview
from .run_spec import RunConstraints, RunSpec, extract_acceptance_criteria
from .projection import resolve_projection_metadata
from .skills import SkillRegistryError, _package_digest


_HELP_TEXT = {
    "description": {
        "en": "Plan, run, inspect, and replay Graphori work.",
        "ko": "Graphori 작업을 계획·실행·점검·재생합니다.",
    },
    "plan": {
        "en": "Preview the plan and approval points before execution.",
        "ko": "실행 전에 계획과 승인 지점을 미리 봅니다.",
    },
    "run": {
        "en": "Start a replayable Graphori run.",
        "ko": "기록을 재생할 수 있는 Graphori 실행을 시작합니다.",
    },
    "status": {
        "en": "Read the current state of a recorded run.",
        "ko": "기록된 실행의 현재 상태를 읽습니다.",
    },
    "replay": {
        "en": "Replay a journal without changing it.",
        "ko": "journal을 변경하지 않고 다시 재생합니다.",
    },
    "resume": {
        "en": "Safely resume an interrupted run.",
        "ko": "중단된 실행을 안전하게 재개합니다.",
    },
    "doctor": {
        "en": "Inspect the environment and journal without changing them.",
        "ko": "환경과 journal을 변경하지 않고 점검합니다.",
    },
    "dashboard": {
        "en": "Open the local run dashboard.",
        "ko": "로컬 실행 상태 대시보드를 엽니다.",
    },
    "criterion": {
        "en": "Stable acceptance criterion, for example AC-01: tests pass.",
        "ko": "안정적인 완료 기준입니다. 예: AC-01: 테스트 통과",
    },
    "verify_criterion": {
        "en": "Acceptance criterion ID proven by the verification command (repeatable).",
        "ko": "검증 명령이 증명하는 완료 기준 ID입니다. 여러 번 지정할 수 있습니다.",
    },
    "live_verify": {
        "en": ("Overlap a repeatable verification command with agent work; reuse it only "
               "when the final workspace digest is identical."),
        "ko": ("반복 실행해도 안전한 검증 명령을 작업과 겹쳐 실행합니다. 마지막 작업공간 "
               "해시가 정확히 같을 때만 결과를 재사용합니다."),
    },
    "language": {
        "en": "Help and output language: auto, en, or ko.",
        "ko": "도움말과 출력 언어: auto, en, ko 중 하나입니다.",
    },
    "cross_review": {
        "en": "Cross-provider review policy: auto, always, or never.",
        "ko": "교차 제공자 리뷰 정책: auto, always, never 중 하나입니다.",
    },
    "implementation_provider": {
        "en": "Implementation provider: auto, codex, or claude.",
        "ko": "구현 제공자: auto, codex, claude 중 하나입니다.",
    },
    "uncertainty": {
        "en": "Task uncertainty used by auto review: auto, low, medium, or high.",
        "ko": "자동 리뷰 판단에 사용할 작업 불확실성: auto, low, medium, high 중 하나입니다.",
    },
    "dashboard_run": {
        "en": "Run ID to display (default: latest run).",
        "ko": "표시할 작업 ID (기본: 가장 최근 작업)",
    },
    "no_open": {
        "en": "Do not open a browser automatically.",
        "ko": "브라우저를 자동으로 열지 않습니다.",
    },
}


def _help_text(key: str, locale: str) -> str:
    return _HELP_TEXT[key][normalized_locale(locale)]


def _bootstrap_objective(argv: list[str]) -> str:
    """Extract only plan/run positional text without executing the full parser."""
    command_index = next(
        (index for index, token in enumerate(argv) if token in {"plan", "run"}),
        None,
    )
    if command_index is None:
        return ""
    value_options = {
        "--root", "--host", "--run-id", "--max-parallelism", "--read-scope",
        "--write-scope", "--timeout", "--criterion", "--lang", "--locale",
        "--cross-review", "--implementation-provider", "--uncertainty",
        "--verify-criterion",
    }
    flag_options = {"--no-network", "--live-verify", "--json", "--help", "-h"}
    objective: list[str] = []
    skip_value = False
    for token in argv[command_index + 1:]:
        if skip_value:
            skip_value = False
            continue
        if token == "--verify-command":
            break
        if token in value_options:
            skip_value = True
            continue
        if token in flag_options or token.startswith(tuple(f"{name}=" for name in value_options)):
            continue
        if token.startswith("-"):
            continue
        objective.append(token)
    text = " ".join(objective)
    code_or_path_markers = ("/", "\\", "_", ".", "(", ")", "::")
    if objective and all(
        any(marker in token for marker in code_or_path_markers)
        for token in objective
    ):
        return ""
    return text


def _bootstrap_help_locale(argv: list[str]) -> str:
    """Resolve help language before argparse handles an early ``--help``."""
    preference = "auto"
    root = Path.cwd()
    bootstrap_argv = argv[:argv.index("--verify-command")] if "--verify-command" in argv else argv
    for index, token in enumerate(bootstrap_argv):
        if token in {"--lang", "--locale"} and index + 1 < len(bootstrap_argv):
            preference = bootstrap_argv[index + 1]
        elif token.startswith("--lang=") or token.startswith("--locale="):
            preference = token.split("=", 1)[1]
        elif token == "--root" and index + 1 < len(bootstrap_argv):
            root = Path(bootstrap_argv[index + 1])
        elif token.startswith("--root="):
            root = Path(token.split("=", 1)[1])
    return resolve_locale(
        preference, root=root, objective=_bootstrap_objective(bootstrap_argv),
    )


def _add_locale_argument(parser: argparse.ArgumentParser, *, locale: str,
                         default: object = argparse.SUPPRESS) -> None:
    parser.add_argument(
        "--lang", "--locale", dest="locale", choices=("auto", "ko", "en"),
        default=default, help=_help_text("language", locale),
    )


def _objective(parts: list[str]) -> str:
    value = " ".join(parts).strip()
    if not value:
        raise ValueError("objective must be non-empty")
    return value


def _direct_adapters(root: Path, timeout: float):
    limits = ProcessLimits(timeout_seconds=timeout, grace_seconds=3)
    codex = CodexExecutionAdapter(workspace_root=root, limits=limits)
    claude = ClaudeCodeExecutionAdapter(workspace_root=root, limits=limits)
    return codex, claude


def _availability(codex, claude) -> dict[str, Availability]:
    codex_status = Availability.AVAILABLE if codex.probe().available else Availability.UNAVAILABLE
    claude_status = Availability.AVAILABLE if claude.probe().available else Availability.UNAVAILABLE
    adapter_status = {"codex": codex_status, "claude": claude_status}
    return {
        model.runtime_model_id: adapter_status[model.adapter]
        for model in default_model_catalog().provider_catalog.models
    }


def _spec(args: argparse.Namespace, root: Path) -> RunSpec:
    objective = _objective(args.objective)
    criteria = tuple(args.criterion) or extract_acceptance_criteria(objective)
    return RunSpec(
        objective, args.host, str(root),
        constraints=RunConstraints(
            max_parallelism=args.max_parallelism,
            allow_network=not args.no_network,
            cross_review=args.cross_review,
            implementation_provider=args.implementation_provider,
            uncertainty=args.uncertainty,
        ),
        runtime_preference=("codex", "claude", "generic_process"),
        acceptance_criteria=criteria,
    )


def _bundle(args: argparse.Namespace, *, probe: bool = True):
    root = args.root.resolve()
    codex, claude = _direct_adapters(root, args.timeout)
    availability = _availability(codex, claude) if probe else {}
    if probe and not any(value is Availability.AVAILABLE for value in availability.values()):
        raise LocalizedRuntimeError(
            "no_direct_provider"
        )
    compiler = ProductPlanCompiler(availability=availability)
    spec = _spec(args, root)
    run_id = args.run_id or f"run-{uuid.uuid4().hex[:16]}"
    verify = tuple(args.verify_command) if args.verify_command else None
    bundle = compiler.compile(
        spec, run_id=run_id,
        read_scope=tuple(args.read_scope or (".",)),
        write_scope=tuple(args.write_scope or (".",)),
        verification_argv=verify,
        verification_criteria=tuple(args.verify_criterion),
    )
    return root, spec, bundle, codex, claude


def cmd_plan(args: argparse.Namespace) -> int:
    _root, _specification, bundle, _codex, _claude = _bundle(args)
    if args.json:
        print(json.dumps({
            "profile": bundle.profile, "plan": bundle.plan.to_dict(),
            "preview": render_plan_preview(bundle.plan, locale=args.locale),
        }, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(render_plan_preview(bundle.plan, locale=args.locale), end="")
    return 0


async def _run(args: argparse.Namespace) -> int:
    root, spec, bundle, codex, claude = _bundle(args)
    nodes = {node.node_id: node for node in bundle.plan.nodes}
    commands = {
        node_id: ProcessCommand(
            command.argv, verdict_file=command.verdict_file,
            verdict_from_exit=command.verdict_from_exit,
            criterion_ids=command.criterion_ids,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            limits=ProcessLimits(timeout_seconds=args.timeout, grace_seconds=3),
            permission_profile=nodes[node_id].permission_profile,
            sandbox_profile="none",
            network_policy=(
                "allowed" if spec.constraints.allow_network else "disabled_requested"
            ),
        )
        for node_id, command in bundle.process_commands.items()
    }
    generic = GenericProcessAdapter(
        workspace_root=root, commands=commands,
        max_concurrency=max(1, args.max_parallelism),
    )
    routed = RoutedExecutionAdapter({
        "codex": codex, "claude": claude, "generic-process": generic,
    })
    if args.live_verify:
        routed = LiveVerifyAdapter(
            routed, workspace_root=root, commands=commands,
        )
    engine = GraphExecutionEngine(adapter=routed, plan_factory=lambda _spec: bundle.plan)
    def publish(preview: str) -> None:
        print(preview, end="", flush=True)
        print("이제 첫 작업을 시작합니다.\n" if args.locale == "ko" else "Execution\n", flush=True)

    def persist_sidecars(_handle) -> None:
        # This callback runs only after the Engine owns the per-Run writer
        # lock and before any Node dispatch. A rejected contender therefore
        # cannot overwrite canonical metadata sidecars.
        paths = ensure_run_dirs(root, bundle.plan.run_id)
        run_root = paths.journal_file.parents[1]
        (run_root / "run-spec.json").write_text(
            json.dumps(spec.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (run_root / "run-plan.json").write_text(
            json.dumps(bundle.plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (run_root / "process-commands.json").write_text(
            json.dumps({
                node_id: {
                    "argv": list(command.argv),
                    "verdict_file": command.verdict_file,
                    "verdict_from_exit": command.verdict_from_exit,
                    "criterion_ids": list(command.criterion_ids),
                }
                for node_id, command in bundle.process_commands.items()
            }, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    projection = await execute_product(
        engine, spec, bundle.plan, preview_sink=publish, preview_locale=args.locale,
        started_sink=persist_sidecars,
    )
    result = {
        "run_id": bundle.plan.run_id,
        "plan_digest": bundle.plan.digest(),
        "terminal_status": projection.terminal_status,
        "node_states": dict(projection.node_states),
        "open_gates": list(projection.open_gates),
        "projection_digest": projection.projection_digest,
        "journal": str(
            root / ".graphori" / "runs" / bundle.plan.run_id / "journal" / "journal.jsonl"
        ),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        snapshot, _events = DashboardStore(root).snapshot(bundle.plan.run_id)
        print(_render_human_status(snapshot, locale=args.locale))
    if projection.terminal_status == "succeeded":
        return 0
    if projection.open_gates:
        return 3
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    return asyncio.run(_run(args))


def _recorded_run(root: Path, run_id: str) -> tuple[RunSpec, object, list[dict]]:
    """Load an immutable product run without creating or recovering files.

    Resume is deliberately a cold replay: it trusts only a complete canonical
    journal plus metadata recorded when the original writer owned the lock.
    In particular, it never recompiles the user's current request.
    """
    paths = RunPaths(root.resolve(), run_id)
    if not paths.journal_file.is_file():
        raise LocalizedValueError("resume_no_journal")
    events, _digest = replay_journal(paths)
    if not events:
        raise LocalizedValueError("resume_empty_journal")
    metadata = resolve_projection_metadata(root, run_id, events)
    plan = metadata.plan
    if plan.run_id != run_id:
        raise LocalizedValueError("resume_run_identity")
    recorded_digests = {
        payload.get("plan_digest")
        for event in events
        if event.get("type") in {"run_created", "graph_published"}
        for payload in [event.get("payload") or {}]
        if payload.get("plan_digest")
    }
    if recorded_digests != {plan.digest()}:
        raise LocalizedValueError("resume_plan_digest")
    if metadata.spec.workspace != str(root.resolve()):
        raise LocalizedValueError("resume_workspace")
    if any(event.get("type") == "run_terminal" for event in events):
        raise LocalizedValueError("resume_terminal")
    return metadata.spec, plan, events


def _verify_pinned_skills(plan, root: Path) -> None:
    """Reject changed/missing skill snapshots before a resumed dispatch."""
    for node in plan.nodes:
        for binding in node.skill_bindings:
            snapshot = Path(binding.snapshot_path)
            if not snapshot.is_absolute():
                snapshot = root / snapshot
            try:
                actual = _package_digest(snapshot)
            except SkillRegistryError as exc:
                raise ValueError(
                    "resume_skill_missing", binding.skill_id
                ) from exc
            if actual != binding.digest:
                raise ValueError(
                    "resume_skill_changed", binding.skill_id
                )


async def _resume(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    spec, plan, _events = _recorded_run(root, args.run_id)
    _verify_pinned_skills(plan, root)
    codex, claude = _direct_adapters(root, args.timeout)
    commands = {
        node.node_id: ProcessCommand(
            # The only product-managed process route is the verifier.  A
            # missing command is an unsafe plan, not an invitation to invent
            # a new command during replay.
            ("false",), verdict_file="",
            limits=ProcessLimits(timeout_seconds=args.timeout, grace_seconds=3),
        )
        for node in plan.nodes if (node.adapter or node.provider) == "generic-process"
    }
    # Restore the recorded verifier command exactly. Rebuilding it from an
    # ambient CLI/configuration would make replay dependent on changed input.
    commands_path = root / ".graphori" / "runs" / plan.run_id / "process-commands.json"
    try:
        recorded_commands = json.loads(commands_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalizedValueError("resume_no_command") from exc
    if not isinstance(recorded_commands, dict):
        raise LocalizedValueError("resume_bad_command")
    for node_id in commands:
        value = recorded_commands.get(node_id)
        if (not isinstance(value, dict) or not isinstance(value.get("argv"), list)
                or not all(isinstance(item, str) for item in value["argv"])
                or not isinstance(value.get("verdict_file"), str)
                or not isinstance(value.get("verdict_from_exit", False), bool)
                or not isinstance(value.get("criterion_ids", []), list)
                or not all(isinstance(item, str) and item
                           for item in value.get("criterion_ids", []))):
            raise LocalizedValueError("resume_unclear_command", node_id)
        commands[node_id] = ProcessCommand(
            tuple(value["argv"]), verdict_file=value["verdict_file"],
            verdict_from_exit=value.get("verdict_from_exit", False),
            criterion_ids=tuple(value.get("criterion_ids", ())),
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            limits=ProcessLimits(timeout_seconds=args.timeout, grace_seconds=3),
        )
    generic = GenericProcessAdapter(workspace_root=root, commands=commands,
                                    max_concurrency=max(1, spec.constraints.max_parallelism))
    engine = GraphExecutionEngine(
        adapter=RoutedExecutionAdapter({
            "codex": codex, "claude": claude, "generic-process": generic,
        }),
        plan_factory=lambda _spec: plan,
    )
    handle = await engine.start(spec)
    try:
        # ``start`` cold-replays then marks only in-flight attempts unknown.
        # Keep advancing newly-ready descendants, but stop at a gate, terminal
        # state, or a graph that cannot make safe progress. Unknown attempts
        # are never redelivered by the scheduler.
        dispatched_nodes: list[str] = []
        while True:
            snapshot = engine.snapshot(handle.run_id)
            if snapshot.terminal_status is not None or snapshot.open_gates:
                break
            decision = await engine.advance(handle.run_id)
            dispatched_nodes.extend(item.node_id for item in decision.scheduling.dispatches)
            snapshot = engine.snapshot(handle.run_id)
            if (snapshot.terminal_status is not None or snapshot.open_gates
                    or not decision.scheduling.dispatches):
                break
    finally:
        engine.close(handle.run_id)
    result = {
        "run_id": plan.run_id, "resumed": True,
        "terminal_status": snapshot.terminal_status,
        "node_states": dict(snapshot.node_states),
        "projection_digest": snapshot.projection_digest,
        "dispatched_nodes": dispatched_nodes,
    }
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) if args.json
          else _render_human_status(DashboardStore(root).snapshot(plan.run_id)[0], locale=args.locale))
    return 0 if snapshot.terminal_status == "succeeded" else 3 if snapshot.open_gates else 1


def cmd_resume(args: argparse.Namespace) -> int:
    return asyncio.run(_resume(args))


def _error_text(exc: BaseException, locale: str) -> str:
    """Render an error in the user's language when the condition has a name."""
    key = getattr(exc, "key", "")
    if not key:
        return str(exc)
    text = runtime_label(key, normalized_locale(locale or "auto"))
    detail = getattr(exc, "detail", "")
    return f"{text}: {detail}" if detail else text


class LocalizedError(Exception):
    """An error whose text is chosen at display time, not where it is raised."""

    def __init__(self, key: str, detail: str = "") -> None:
        text = runtime_label(key, "en")
        super().__init__(f"{text}: {detail}" if detail else text)
        self.key = key
        self.detail = detail


class LocalizedValueError(LocalizedError, ValueError):
    pass


class LocalizedRuntimeError(LocalizedError, RuntimeError):
    pass


def cmd_doctor(args: argparse.Namespace) -> int:
    """Read-only local diagnostics; it intentionally never calls ensure_run_dirs."""
    root = args.root.resolve()
    locale = normalized_locale(getattr(args, "locale", "auto") or "auto")
    codex, claude = _direct_adapters(root, args.timeout)
    providers = {"Codex": codex.probe(), "Claude Code": claude.probe()}
    lock_path = root / ".graphori" / "skills.lock.json"
    lock_status = doctor_label("lock_absent", locale)
    if lock_path.is_file():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock_status = (doctor_label("compatible", locale)
                           if isinstance(lock, dict) and lock.get("schema_version") == 1
                           else doctor_label("lock_unsupported", locale))
        except (OSError, json.JSONDecodeError):
            lock_status = doctor_label("lock_unreadable", locale)
    values: dict[str, object] = {
        "mode": "read_only", "providers": {
            name: {
                "available": probe.available,
                "authentication": probe.authentication,
                "reason": probe.reason,
            }
            for name, probe in providers.items()
        },
        "schemas": {"RunSpec": 2, "RunPlan": 2, "journal_event": 1,
                    "skills_lock": 1},
        "skill": {"graphori_skill": doctor_label("skill_contract", locale),
                  "lock": lock_status},
        "orca": {
            "required": False,
            "status": doctor_label("orca_optional", locale),
        },
    }
    values["provider_summary"] = (
        doctor_label("providers_none", locale)
        if not any(probe.available for probe in providers.values())
        else doctor_label("providers_ok", locale)
    )
    if args.run_id:
        paths = RunPaths(root, args.run_id)
        journal: dict[str, object] = {"path": str(paths.journal_file), "exists": paths.journal_file.is_file()}
        if paths.journal_file.is_file():
            try:
                events, digest = replay_journal(paths)
                journal.update({"status": doctor_label("journal_ok", locale),
                                "event_count": len(events), "digest": digest,
                                "terminal": any(e.get("type") == "run_terminal" for e in events)})
                try:
                    metadata = resolve_projection_metadata(root, args.run_id, events)
                    journal["plan_digest"] = metadata.plan.digest()
                    journal["schema_lock"] = doctor_label("compatible", locale)
                except ValueError as exc:
                    journal["schema_lock"] = f'{runtime_label("mismatch", locale)}: {exc}'
            except Exception as exc:
                journal["status"] = f'{runtime_label("check_failed", locale)}: {exc}'
        values["journal"] = journal
    runs_root = root / ".graphori" / "runs"
    interrupted: list[dict[str, object]] = []
    resumable: list[bool] = []
    if runs_root.is_dir():
        for run_root in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            paths = RunPaths(root, run_root.name)
            if not paths.journal_file.is_file():
                continue
            try:
                events, _digest = replay_journal(paths)
                if not events or any(event.get("type") == "run_terminal" for event in events):
                    continue
                snapshot, _replayed = DashboardStore(root).snapshot(run_root.name)
                unsafe_states = {"blocked", "failed", "cancelled", "outcome_unknown"}
                needs_review = (
                    snapshot.get("status") in {"blocked", "failed", "outcome_unknown"}
                    or any(
                        node.get("status") in unsafe_states
                        for node in snapshot.get("nodes", ())
                    )
                    or any(
                        (event.get("payload") or {}).get("outcome") == "outcome_unknown"
                        for event in events
                    )
                )
                resumable.append(not needs_review)
                interrupted.append({
                    "run_id": run_root.name,
                    "status": doctor_label(
                        "run_needs_review" if needs_review else "run_resumable", locale),
                })
            except Exception:
                resumable.append(False)
                interrupted.append({"run_id": run_root.name,
                                    "status": doctor_label("run_unreadable", locale)})
    values["interrupted_runs"] = {
        "count": len(interrupted),
        "resumable": sum(resumable),
        "needs_review": len(resumable) - sum(resumable),
        "runs": interrupted,
    }
    text = json.dumps(values, indent=2, sort_keys=True, ensure_ascii=False)
    print(text if args.json else doctor_label("title", locale) + "\n" + text)
    return 0


def _format_duration(milliseconds, locale: str = "ko") -> str:
    if not isinstance(milliseconds, (int, float)):
        return runtime_label("unknown", locale)
    seconds = max(0, round(milliseconds / 1000))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    hour_unit = runtime_label("hours", locale)
    minute_unit = runtime_label("minutes", locale)
    second_unit = runtime_label("seconds", locale)
    if hours:
        return f"{hours}{hour_unit} {minutes}{minute_unit} {seconds}{second_unit}"
    if minutes:
        return f"{minutes}{minute_unit} {seconds}{second_unit}"
    return f"{seconds}{second_unit}"


def _render_human_status(snapshot: dict, *, locale: str) -> str:
    """Explain a run in plain language, in the reader's language.

    English used to get raw JSON here while Korean got this report, which made
    the English experience strictly worse for no reason. Both now render the
    same layout from the same labels.
    """
    locale = normalized_locale(locale)

    def text(key: str) -> str:
        return runtime_label(key, locale)

    lines = [text("status_title"), "",
             f"{text('status_overall')}  "
             f"{status_label(snapshot.get('status', 'unknown'), locale)}"]
    activity = snapshot.get("activity") or {}
    lines.append(f"{text('status_running_for')}  "
                 f"{_format_duration(activity.get('elapsed_ms'), locale)}")
    age = activity.get("last_activity_age_seconds")
    if isinstance(age, (int, float)):
        elapsed = f"{_format_duration(age * 1000, locale)} {text('ago')}"
    else:
        elapsed = text("status_not_observed")
    lines.append(f"{text('status_last_change')}  {elapsed}")
    liveness = (snapshot.get("liveness") or {}).get("status", "unknown")
    liveness_text = {
        "heartbeat_recent": text("live_working"),
        "completed": text("live_done"),
        "stale": text("live_stale"),
    }.get(liveness, text("status_not_observed"))
    percent = (snapshot.get("provider_progress") or {}).get("percent")
    progress = (f"{percent}%" if isinstance(percent, (int, float))
                else text("status_no_number"))
    lines.extend((f"{text('status_worker')}  {liveness_text}",
                  f"{text('status_progress')}  {progress}",
                  "", text("status_by_step")))
    for node in snapshot.get("nodes", []):
        lines.append(f"- {team_label(node.get('team_id', ''), locale)}: "
                     f"{status_label(node.get('status', 'unknown'), locale)}")
        lines.append("  " + (node.get("display_title") or node.get("title")
                             or text("status_untitled")))
        lines.append(f"  {text('status_route')}: "
                     f"{route_label(node.get('selected_route') or '', locale)}")
        if node.get("requested_effort"):
            lines.append(f"  {text('status_effort')}: "
                         f"{effort_label(node.get('requested_effort') or '', locale)}")
    criteria = ((snapshot.get("verification") or {}).get("acceptance_criteria") or [])
    if criteria:
        lines.extend(("", text("status_criteria")))
        proof_labels = {
            "PROVEN": text("proof_proven"),
            "NOT_PROVEN": text("proof_not_proven"),
            "FAILED": text("proof_failed"),
            "NOT_APPLICABLE": text("proof_not_applicable"),
        }
        for criterion in criteria:
            mark = {"PROVEN": "\u2713", "FAILED": "\u2717", "NOT_APPLICABLE": "-"}.get(
                criterion.get("status"), "?",
            )
            description = str(criterion.get("criterion", "")).partition(":")[2].strip()
            lines.append(
                f"{mark} {criterion.get('criterion_id')} {description} - "
                f"{proof_labels.get(criterion.get('status'), text('proof_not_proven'))}"
            )
    return "\n".join(lines)


def _read_projection(args: argparse.Namespace, *, replayed: bool) -> int:
    store = DashboardStore(args.root.resolve())
    projection, _events = store.canonical_projection(args.run_id)
    value = projection.to_dict()
    if replayed:
        value["replay_verified"] = True
    if args.json:
        print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        snapshot, _events = store.snapshot(args.run_id)
        print(_render_human_status(snapshot, locale=args.locale))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    return _read_projection(args, replayed=False)


def cmd_replay(args: argparse.Namespace) -> int:
    return _read_projection(args, replayed=True)


def _dashboard_static_dir() -> Path:
    """Resolve dashboard assets without making callers know the checkout layout."""
    candidates = (
        Path(__file__).resolve().parents[2] / "docs" / "dashboard",
        Path(sys.prefix) / "share" / "graphori" / "dashboard",
    )
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    raise ValueError(
        runtime_label("dashboard_assets_missing", "auto")
    )


def _latest_dashboard_run(root: Path) -> str | None:
    runs_root = root / ".graphori" / "runs"
    if not runs_root.is_dir():
        return None
    candidates: list[tuple[int, str]] = []
    for run_root in runs_root.iterdir():
        journal = run_root / "journal" / "journal.jsonl"
        if not run_root.is_dir() or not journal.is_file():
            continue
        try:
            candidates.append((journal.stat().st_mtime_ns, run_root.name))
        except OSError:
            continue
    return max(candidates, default=(0, ""))[1] or None


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Serve the canonical dashboard and optionally open the selected Run."""
    locale = normalized_locale(getattr(args, "locale", "auto") or "auto")
    root = args.root.resolve()
    run_id = args.run_id or _latest_dashboard_run(root)
    if args.run_id:
        journal = RunPaths(root, args.run_id).journal_file
        if not journal.is_file():
            raise LocalizedValueError("dashboard_run_missing", args.run_id)

    server = create_server(
        root,
        host="127.0.0.1",
        port=args.port,
        static_dir=_dashboard_static_dir(),
    )
    host, port = server.server_address[:2]
    query = "?" + urlencode({"run": run_id}) if run_id else ""
    url = f"http://{host}:{port}/{query}"
    print(f'{runtime_label("dashboard_serving", locale)}: {url}', flush=True)
    if run_id:
        print(f'{runtime_label("dashboard_showing", locale)}: {run_id}', flush=True)
    else:
        print(runtime_label("dashboard_no_runs", locale), flush=True)
    if not args.no_open and not webbrowser.open(url):
        print(runtime_label("dashboard_no_browser", locale), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def build_parser(*, locale: str = "en") -> argparse.ArgumentParser:
    locale = normalized_locale(locale)
    parser = argparse.ArgumentParser(
        prog="graphori",
        description=_help_text("description", locale),
    )
    _add_locale_argument(parser, locale=locale, default="auto")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, function in (
            ("plan", cmd_plan),
            ("run", cmd_run),
    ):
        help_text = _help_text(name, locale)
        command = sub.add_parser(name, help=help_text, description=help_text)
        command.add_argument("objective", nargs="+")
        command.add_argument("--root", type=Path, default=Path.cwd())
        command.add_argument("--host", default="codex")
        command.add_argument("--run-id")
        command.add_argument("--max-parallelism", type=int, default=2)
        command.add_argument("--read-scope", action="append", default=[])
        command.add_argument("--write-scope", action="append", default=[])
        command.add_argument("--timeout", type=float, default=300)
        command.add_argument("--no-network", action="store_true")
        command.add_argument(
            "--cross-review", choices=("auto", "always", "never"), default="auto",
            help=_help_text("cross_review", locale),
        )
        command.add_argument(
            "--implementation-provider", choices=("auto", "codex", "claude"),
            default="auto", help=_help_text("implementation_provider", locale),
        )
        command.add_argument(
            "--uncertainty", choices=("auto", "low", "medium", "high"),
            default="auto", help=_help_text("uncertainty", locale),
        )
        command.add_argument("--criterion", action="append", default=[], metavar="ID:DESCRIPTION",
                             help=_help_text("criterion", locale))
        command.add_argument(
            "--verify-criterion", action="append", default=[], metavar="ID",
            help=_help_text("verify_criterion", locale),
        )
        command.add_argument(
            "--live-verify", action="store_true",
            help=_help_text("live_verify", locale),
        )
        command.add_argument("--verify-command", nargs=argparse.REMAINDER)
        command.add_argument("--json", action="store_true")
        _add_locale_argument(command, locale=locale)
        command.set_defaults(func=function)
    for name, function in (
            ("status", cmd_status),
            ("replay", cmd_replay),
    ):
        help_text = _help_text(name, locale)
        command = sub.add_parser(name, help=help_text, description=help_text)
        command.add_argument("--root", type=Path, default=Path.cwd())
        command.add_argument("--run-id", required=True)
        command.add_argument("--json", action="store_true")
        _add_locale_argument(command, locale=locale)
        command.set_defaults(func=function)
    help_text = _help_text("resume", locale)
    command = sub.add_parser("resume", help=help_text, description=help_text)
    command.add_argument("--root", type=Path, default=Path.cwd())
    command.add_argument("--run-id", required=True)
    command.add_argument("--timeout", type=float, default=300)
    command.add_argument("--json", action="store_true")
    _add_locale_argument(command, locale=locale)
    command.set_defaults(func=cmd_resume)
    help_text = _help_text("doctor", locale)
    command = sub.add_parser("doctor", help=help_text, description=help_text)
    command.add_argument("--root", type=Path, default=Path.cwd())
    command.add_argument("--run-id")
    command.add_argument("--timeout", type=float, default=5)
    command.add_argument("--json", action="store_true")
    _add_locale_argument(command, locale=locale)
    command.set_defaults(func=cmd_doctor)
    help_text = _help_text("dashboard", locale)
    command = sub.add_parser("dashboard", help=help_text, description=help_text)
    command.add_argument("--root", type=Path, default=Path.cwd())
    command.add_argument("--run-id", help=_help_text("dashboard_run", locale))
    command.add_argument("--port", type=int, default=8765)
    command.add_argument("--no-open", action="store_true",
                         help=_help_text("no_open", locale))
    _add_locale_argument(command, locale=locale)
    command.set_defaults(func=cmd_dashboard)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = None
    try:
        raw_argv = list(sys.argv[1:] if argv is None else argv)
        args = build_parser(locale=_bootstrap_help_locale(raw_argv)).parse_args(raw_argv)
        # Resolve only at the presentation boundary. Plans, journals, and
        # their digests never receive this value.
        if hasattr(args, "locale"):
            args.locale = resolve_locale(
                args.locale,
                root=getattr(args, "root", Path.cwd()),
                objective=" ".join(getattr(args, "objective", ())),
            )
        return args.func(args)
    except (RuntimeError, ValueError, OSError) as exc:
        locale = getattr(args, "locale", "auto") if args is not None else "auto"
        print(f"error: {_error_text(exc, locale)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
