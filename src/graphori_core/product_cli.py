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

from .execution_engine import GraphExecutionEngine
from .dashboard import DashboardStore, create_server
from .journal import ensure_run_dirs
from .journal import RunPaths, replay_journal
from .model_routing import Availability
from .process_supervisor import ProcessLimits
from .presentation import (doctor_label, effort_label, normalized_locale,
                           resolve_locale, route_label, status_label, team_label)
from .product import ProductPlanCompiler, execute_product, render_plan_preview
from .run_spec import RunConstraints, RunSpec, extract_acceptance_criteria
from .projection import resolve_projection_metadata
from .skills import SkillRegistryError, _package_digest


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
    result: dict[str, Availability] = {}
    codex_status = Availability.AVAILABLE if codex.probe().available else Availability.UNAVAILABLE
    claude_status = Availability.AVAILABLE if claude.probe().available else Availability.UNAVAILABLE
    for model in ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"):
        result[model] = codex_status
    for model in ("claude-sonnet-5", "claude-opus-5"):
        result[model] = claude_status
    return result


def _spec(args: argparse.Namespace, root: Path) -> RunSpec:
    objective = _objective(args.objective)
    criteria = tuple(args.criterion) or extract_acceptance_criteria(objective)
    return RunSpec(
        objective, args.host, str(root),
        constraints=RunConstraints(
            max_parallelism=args.max_parallelism,
            allow_network=not args.no_network,
        ),
        runtime_preference=("codex", "claude", "generic_process"),
        acceptance_criteria=criteria,
    )


def _bundle(args: argparse.Namespace, *, probe: bool = True):
    root = args.root.resolve()
    codex, claude = _direct_adapters(root, args.timeout)
    availability = _availability(codex, claude) if probe else {}
    if probe and not any(value is Availability.AVAILABLE for value in availability.values()):
        raise RuntimeError(
            "사용 가능한 Direct provider가 없습니다. Codex 또는 Claude Code CLI를 설치·로그인하세요."
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
    commands = {
        node_id: ProcessCommand(
            command.argv, verdict_file=command.verdict_file,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            limits=ProcessLimits(timeout_seconds=args.timeout, grace_seconds=3),
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
                node_id: {"argv": list(command.argv), "verdict_file": command.verdict_file}
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
        raise ValueError("재개할 journal이 없습니다.")
    events, _digest = replay_journal(paths)
    if not events:
        raise ValueError("빈 journal은 안전하게 재개할 수 없습니다.")
    metadata = resolve_projection_metadata(root, run_id, events)
    plan = metadata.plan
    if plan.run_id != run_id:
        raise ValueError("저장된 plan의 run identity가 일치하지 않습니다.")
    recorded_digests = {
        payload.get("plan_digest")
        for event in events
        if event.get("type") in {"run_created", "graph_published"}
        for payload in [event.get("payload") or {}]
        if payload.get("plan_digest")
    }
    if recorded_digests != {plan.digest()}:
        raise ValueError("저장된 plan과 journal의 plan digest가 일치하지 않습니다.")
    if metadata.spec.workspace != str(root.resolve()):
        raise ValueError("저장된 RunSpec workspace가 현재 --root와 일치하지 않습니다.")
    if any(event.get("type") == "run_terminal" for event in events):
        raise ValueError("terminal run은 재실행할 수 없습니다.")
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
                    f"Skill snapshot을 확인할 수 없습니다: {binding.skill_id}"
                ) from exc
            if actual != binding.digest:
                raise ValueError(
                    f"Skill snapshot이 변경되었습니다: {binding.skill_id}"
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
        raise ValueError("저장된 process command가 없어 안전하게 재개할 수 없습니다.") from exc
    if not isinstance(recorded_commands, dict):
        raise ValueError("저장된 process command 형식이 올바르지 않습니다.")
    for node_id in commands:
        value = recorded_commands.get(node_id)
        if (not isinstance(value, dict) or not isinstance(value.get("argv"), list)
                or not all(isinstance(item, str) for item in value["argv"])
                or not isinstance(value.get("verdict_file"), str)):
            raise ValueError(f"저장된 process command가 불명확합니다: {node_id}")
        commands[node_id] = ProcessCommand(
            tuple(value["argv"]), verdict_file=value["verdict_file"],
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
            name: {"available": probe.available, "reason": probe.reason}
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
                    journal["schema_lock"] = f"불일치: {exc}"
            except Exception as exc:
                journal["status"] = f"점검 실패: {exc}"
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


def _format_duration(milliseconds) -> str:
    if not isinstance(milliseconds, (int, float)):
        return "알 수 없음"
    seconds = max(0, round(milliseconds / 1000))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}시간 {minutes}분 {seconds}초"
    if minutes:
        return f"{minutes}분 {seconds}초"
    return f"{seconds}초"


def _render_human_status(snapshot: dict, *, locale: str) -> str:
    locale = normalized_locale(locale)
    if locale != "ko":
        return json.dumps({
            "run_id": snapshot.get("run_id"), "status": snapshot.get("status"),
            "terminal_status": snapshot.get("terminal_status"),
            "projection_digest": snapshot.get("projection_digest"),
        }, indent=2, sort_keys=True, ensure_ascii=False)
    lines = ["지금 작업 상황", "", f"전체  {status_label(snapshot.get('status', 'unknown'), locale)}"]
    activity = snapshot.get("activity") or {}
    lines.append(f"시작한 지  {_format_duration(activity.get('elapsed_ms'))}")
    age = activity.get("last_activity_age_seconds")
    lines.append(f"마지막 변화  {_format_duration(age * 1000) + ' 전' if isinstance(age, (int, float)) else '아직 확인하지 못함'}")
    liveness = (snapshot.get("liveness") or {}).get("status", "unknown")
    liveness_text = {"heartbeat_recent": "정상적으로 일하는 중", "completed": "일을 마침", "stale": "멈췄는지 확인 필요"}.get(liveness, "아직 확인하지 못함")
    lines.extend((f"작업자  {liveness_text}", "진행 정도  " + (
        f"{snapshot['provider_progress']['percent']}%" if isinstance(
            (snapshot.get("provider_progress") or {}).get("percent"), (int, float),
        ) else "숫자로 확인할 수 없음"
    ), "", "단계별 상황"))
    for node in snapshot.get("nodes", []):
        lines.append(f"- {team_label(node.get('team_id', ''), locale)}: {status_label(node.get('status', 'unknown'), locale)}")
        lines.append(f"  {node.get('display_title') or node.get('title') or '제목 없음'}")
        lines.append(f"  담당: {route_label(node.get('selected_route') or '', locale)}")
        if node.get("requested_effort"):
            lines.append(f"  살펴보는 정도: {effort_label(node.get('requested_effort') or '', locale)}")
    criteria = ((snapshot.get("verification") or {}).get("acceptance_criteria") or [])
    if criteria:
        lines.extend(("", "끝나기 전에 확인할 내용"))
        proof_labels = {
            "PROVEN": "확인함", "NOT_PROVEN": "아직 확인 전",
            "FAILED": "조건을 만족하지 못함", "NOT_APPLICABLE": "확인할 필요 없음",
        }
        for criterion in criteria:
            mark = {"PROVEN": "✓", "FAILED": "✗", "NOT_APPLICABLE": "-"}.get(
                criterion.get("status"), "?",
            )
            description = str(criterion.get("criterion", "")).partition(":")[2].strip()
            lines.append(
                f"{mark} {criterion.get('criterion_id')} {description} — "
                f"{proof_labels.get(criterion.get('status'), '아직 확인 전')}"
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
        "대시보드 화면 파일을 찾을 수 없습니다. Graphori를 다시 설치하거나 "
        "개발 checkout에서 실행하세요."
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
    root = args.root.resolve()
    run_id = args.run_id or _latest_dashboard_run(root)
    if args.run_id:
        journal = RunPaths(root, args.run_id).journal_file
        if not journal.is_file():
            raise ValueError(f"실행 기록을 찾을 수 없습니다: {args.run_id}")

    server = create_server(
        root,
        host="127.0.0.1",
        port=args.port,
        static_dir=_dashboard_static_dir(),
    )
    host, port = server.server_address[:2]
    query = "?" + urlencode({"run": run_id}) if run_id else ""
    url = f"http://{host}:{port}/{query}"
    print(f"Graphori 대시보드: {url}", flush=True)
    if run_id:
        print(f"표시할 작업: {run_id}", flush=True)
    else:
        print("표시할 실행 기록이 없어 작업 ID 입력 화면을 엽니다.", flush=True)
    if not args.no_open and not webbrowser.open(url):
        print("브라우저를 자동으로 열지 못했습니다. 위 주소를 직접 여세요.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graphori",
        description="Graphori 작업 계획·실행·기록 점검 도구",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, function, help_text in (
            ("plan", cmd_plan, "실행 전에 계획과 승인 지점을 미리 봅니다."),
            ("run", cmd_run, "기록 가능한 Graphori 실행을 시작합니다."),
    ):
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
        command.add_argument("--criterion", action="append", default=[], metavar="ID:DESCRIPTION",
                             help="stable acceptance criterion, e.g. AC-01: tests pass")
        command.add_argument("--verify-command", nargs=argparse.REMAINDER)
        command.add_argument("--json", action="store_true")
        command.add_argument("--lang", "--locale", dest="locale",
                             choices=("auto", "ko", "en"), default="auto",
                             help="output language: auto, en, or ko")
        command.set_defaults(func=function)
    for name, function, help_text in (
            ("status", cmd_status, "기록된 실행의 현재 상태를 읽습니다."),
            ("replay", cmd_replay, "journal을 읽기 전용으로 다시 재생합니다."),
    ):
        command = sub.add_parser(name, help=help_text, description=help_text)
        command.add_argument("--root", type=Path, default=Path.cwd())
        command.add_argument("--run-id", required=True)
        command.add_argument("--json", action="store_true")
        command.add_argument("--lang", "--locale", dest="locale",
                             choices=("auto", "ko", "en"), default="auto",
                             help="output language: auto, en, or ko")
        command.set_defaults(func=function)
    command = sub.add_parser("resume", help="중단된 실행을 안전하게 재개합니다.")
    command.add_argument("--root", type=Path, default=Path.cwd())
    command.add_argument("--run-id", required=True)
    command.add_argument("--timeout", type=float, default=300)
    command.add_argument("--json", action="store_true")
    command.add_argument("--lang", "--locale", dest="locale",
                         choices=("auto", "ko", "en"), default="auto",
                         help="output language: auto, en, or ko")
    command.set_defaults(func=cmd_resume)
    command = sub.add_parser("doctor", help="환경과 journal을 읽기 전용으로 점검합니다.")
    command.add_argument("--root", type=Path, default=Path.cwd())
    command.add_argument("--run-id")
    command.add_argument("--timeout", type=float, default=5)
    command.add_argument("--json", action="store_true")
    command.add_argument("--lang", "--locale", dest="locale",
                         choices=("auto", "ko", "en"), default="auto",
                         help="output language: auto, en, or ko")
    command.set_defaults(func=cmd_doctor)
    command = sub.add_parser("dashboard", help="실행 상태 대시보드를 엽니다.")
    command.add_argument("--root", type=Path, default=Path.cwd())
    command.add_argument("--run-id", help="표시할 작업 ID (기본: 가장 최근 작업)")
    command.add_argument("--port", type=int, default=8765)
    command.add_argument("--no-open", action="store_true", help="브라우저를 자동으로 열지 않습니다.")
    command.set_defaults(func=cmd_dashboard)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
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
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
