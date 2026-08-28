"""Small, dependency-free vocabulary for human-facing Graphori output.

Canonical identifiers remain English and are never localized before hashing.
Consumers select labels only while rendering a plan or projection.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


# ``auto`` is a presentation preference, never a value stored in a RunSpec,
# RunPlan, journal, or digest.  Canonical state remains locale-free.
SUPPORTED_LOCALES = frozenset({"auto", "ko", "en"})

TEAM_LABELS: Mapping[str, Mapping[str, str]] = {
    "planning": {"ko": "운영실", "en": "Planning"},
    "research": {"ko": "조사팀", "en": "Research"},
    "design": {"ko": "설계팀", "en": "Design"},
    "implementation": {"ko": "제작팀", "en": "Implementation"},
    "verification": {"ko": "품질관리팀", "en": "Verification"},
}

STATUS_LABELS: Mapping[str, Mapping[str, str]] = {
    "active": {"ko": "진행함", "en": "Active"},
    "standby": {"ko": "차례를 기다리는 중", "en": "Standby"},
    "omitted": {"ko": "이번에는 필요 없음", "en": "Omitted"},
    "complete": {"ko": "완료", "en": "Complete"},
    "pending": {"ko": "차례를 기다리는 중", "en": "Pending"},
    "ready": {"ko": "시작할 준비가 됨", "en": "Ready"},
    "assigned": {"ko": "담당자가 정해짐", "en": "Assigned"},
    "running": {"ko": "진행 중", "en": "Running"},
    "awaiting_verification": {"ko": "결과를 확인하는 중", "en": "Awaiting verification"},
    "outcome_unknown": {"ko": "끝났는지 다시 확인해야 함", "en": "Outcome unknown"},
    "passed": {"ko": "확인 완료", "en": "Passed"},
    "failed": {"ko": "문제가 생김", "en": "Failed"},
    "blocked": {"ko": "사람의 결정이 필요해 멈춤", "en": "Blocked"},
    "cancelled": {"ko": "취소", "en": "Cancelled"},
    "planning": {"ko": "계획을 세우는 중", "en": "Planning"},
    "waiting_approval": {"ko": "시작 전 결정을 기다리는 중", "en": "Waiting for approval"},
    "succeeded": {"ko": "완료", "en": "Succeeded"},
    "unknown": {"ko": "아직 확인하지 못함", "en": "Unknown"},
}

EFFORT_LABELS: Mapping[str, Mapping[str, str]] = {
    "low": {"ko": "빠르게", "en": "Low"},
    "medium": {"ko": "보통", "en": "Medium"},
    "high": {"ko": "꼼꼼하게", "en": "High"},
    "xhigh": {"ko": "아주 꼼꼼하게", "en": "Extra high"},
}

ROUTE_LABELS: Mapping[str, Mapping[str, str]] = {
    "codex": {"ko": "Codex가 맡음", "en": "Direct Codex"},
    "claude": {"ko": "Claude가 맡음", "en": "Direct Claude"},
    "generic-process": {"ko": "컴퓨터가 정해진 방법으로 확인", "en": "Automated check"},
}

OMISSION_REASON_LABELS: Mapping[str, Mapping[str, str]] = {
    "external_research_not_required": {
        "ko": "지금 가진 자료만으로 충분해 따로 자료를 찾지 않습니다.",
        "en": "No external research is needed for this request.",
    },
    "design_step_not_required": {
        "ko": "해야 할 일이 분명해 별도로 방법을 정하는 단계를 두지 않습니다.",
        "en": "The change is bounded, so no separate design task is needed.",
    },
    "implementation_not_required": {
        "ko": "새로 만들거나 고칠 것이 없어 이 단계를 건너뜁니다.",
        "en": "The request does not require an implementation task.",
    },
    "verification_not_required": {
        "ko": "새로 만든 결과가 없어 따로 확인할 것이 없습니다.",
        "en": "There is no implementation result requiring verification.",
    },
    "not_in_plan": {
        "ko": "현재 작업 범위에 포함되지 않았습니다.",
        "en": "This team is not part of the current plan.",
    },
}


RUNTIME_LABELS: Mapping[str, Mapping[str, str]] = {
    # Errors raised by the product CLI.
    "no_direct_provider": {
        "ko": "사용 가능한 Direct provider가 없습니다. Codex 또는 Claude Code CLI를 설치·로그인하세요.",
        "en": "No Direct provider is available. Install and sign in to the Codex "
              "or Claude Code CLI.",
    },
    "resume_no_journal": {
        "ko": "재개할 journal이 없습니다.",
        "en": "There is no journal to resume.",
    },
    "resume_empty_journal": {
        "ko": "빈 journal은 안전하게 재개할 수 없습니다.",
        "en": "An empty journal cannot be resumed safely.",
    },
    "resume_run_identity": {
        "ko": "저장된 plan의 run identity가 일치하지 않습니다.",
        "en": "The stored plan's run identity does not match.",
    },
    "resume_plan_digest": {
        "ko": "저장된 plan과 journal의 plan digest가 일치하지 않습니다.",
        "en": "The stored plan and the journal disagree on the plan digest.",
    },
    "resume_workspace": {
        "ko": "저장된 RunSpec workspace가 현재 --root와 일치하지 않습니다.",
        "en": "The stored RunSpec workspace does not match the current --root.",
    },
    "resume_terminal": {
        "ko": "terminal run은 재실행할 수 없습니다.",
        "en": "A run that already reached a terminal state cannot be resumed.",
    },
    "resume_skill_missing": {
        "ko": "Skill snapshot을 확인할 수 없습니다",
        "en": "The Skill snapshot could not be read",
    },
    "resume_skill_changed": {
        "ko": "Skill snapshot이 변경되었습니다",
        "en": "The Skill snapshot changed since the run was planned",
    },
    "resume_no_command": {
        "ko": "저장된 process command가 없어 안전하게 재개할 수 없습니다.",
        "en": "No stored process command, so the run cannot be resumed safely.",
    },
    "resume_bad_command": {
        "ko": "저장된 process command 형식이 올바르지 않습니다.",
        "en": "The stored process command is not in a valid form.",
    },
    "resume_unclear_command": {
        "ko": "저장된 process command가 불명확합니다",
        "en": "The stored process command is ambiguous",
    },
    # Doctor detail prefixes.
    "mismatch": {"ko": "불일치", "en": "mismatch"},
    "check_failed": {"ko": "점검 실패", "en": "check failed"},
    # Durations.
    "unknown": {"ko": "알 수 없음", "en": "unknown"},
    "hours": {"ko": "시간", "en": "h"},
    "minutes": {"ko": "분", "en": "m"},
    "seconds": {"ko": "초", "en": "s"},
    "ago": {"ko": "전", "en": "ago"},
    # Human status report.
    "status_title": {"ko": "지금 작업 상황", "en": "Where this run stands"},
    "status_overall": {"ko": "전체", "en": "Overall"},
    "status_running_for": {"ko": "시작한 지", "en": "Running for"},
    "status_last_change": {"ko": "마지막 변화", "en": "Last change"},
    "status_not_observed": {"ko": "아직 확인하지 못함", "en": "not observed yet"},
    "status_worker": {"ko": "작업자", "en": "Worker"},
    "status_progress": {"ko": "진행 정도", "en": "Progress"},
    "status_no_number": {"ko": "숫자로 확인할 수 없음", "en": "no number reported"},
    "status_by_step": {"ko": "단계별 상황", "en": "Step by step"},
    "status_untitled": {"ko": "제목 없음", "en": "untitled"},
    "status_route": {"ko": "담당", "en": "Route"},
    "status_effort": {"ko": "살펴보는 정도", "en": "Effort"},
    "status_criteria": {"ko": "끝나기 전에 확인할 내용", "en": "Before this can finish"},
    "live_working": {"ko": "정상적으로 일하는 중", "en": "working"},
    "live_done": {"ko": "일을 마침", "en": "finished"},
    "live_stale": {"ko": "멈췄는지 확인 필요", "en": "may have stalled"},
    "proof_proven": {"ko": "확인함", "en": "proven"},
    "proof_not_proven": {"ko": "아직 확인 전", "en": "not proven yet"},
    "proof_failed": {"ko": "조건을 만족하지 못함", "en": "not satisfied"},
    "proof_not_applicable": {"ko": "확인할 필요 없음", "en": "not applicable"},
    # Dashboard command.
    "dashboard_assets_missing": {
        "ko": "대시보드 화면 파일을 찾을 수 없습니다. Graphori를 다시 설치하거나 개발 checkout에서 실행하세요.",
        "en": "The dashboard assets are missing. Reinstall Graphori, or run it "
              "from a development checkout.",
    },
    "dashboard_run_missing": {
        "ko": "실행 기록을 찾을 수 없습니다",
        "en": "No run record found",
    },
    "dashboard_serving": {"ko": "Graphori 대시보드", "en": "Graphori dashboard"},
    "dashboard_showing": {"ko": "표시할 작업", "en": "Showing run"},
    "dashboard_no_runs": {
        "ko": "표시할 실행 기록이 없어 작업 ID 입력 화면을 엽니다.",
        "en": "No run to show, so the dashboard opens on its run-id prompt.",
    },
    "dashboard_no_browser": {
        "ko": "브라우저를 자동으로 열지 못했습니다. 위 주소를 직접 여세요.",
        "en": "Could not open a browser. Open the address above yourself.",
    },
}

JOURNAL_LABELS = {
    "writer_busy": {
        "ko": "이 작업은 다른 Graphori에서 실행 중입니다. 실행 기록은 변경하지 않았습니다.",
        "en": "Another Graphori run owns this journal. Nothing was recorded.",
    },
    "writer_unsupported": {
        "ko": "이 환경은 journal writer 잠금을 지원하지 않아 안전하게 실행할 수 없습니다.",
        "en": "This platform has no journal writer lock, so running would be unsafe.",
    },
    "writer_unavailable": {
        "ko": "journal writer 잠금을 확보하지 못해 안전하게 실행을 중단했습니다",
        "en": "Could not acquire the journal writer lock, so the run stopped",
    },
    "writer_closed": {
        "ko": "닫힌 journal writer는 이벤트를 기록할 수 없습니다.",
        "en": "A closed journal writer cannot record events.",
    },
}

DOCTOR_LABELS = {
    "title": {"ko": "Graphori 상태 점검 (읽기 전용)",
              "en": "Graphori status check (read-only)"},
    "lock_absent": {"ko": "없음 (pinned Skill 없음)", "en": "none (no pinned Skill)"},
    "compatible": {"ko": "호환", "en": "compatible"},
    "lock_unsupported": {"ko": "불일치: 지원하지 않는 skills.lock schema",
                         "en": "mismatch: unsupported skills.lock schema"},
    "lock_unreadable": {"ko": "불일치: skills.lock을 읽을 수 없음",
                        "en": "mismatch: skills.lock could not be read"},
    "skill_contract": {"ko": "Orca 없이 독립 실행 계약",
                       "en": "runs standalone, without Orca"},
    "orca_optional": {"ko": "선택 기능이므로 설치 여부가 Direct 실행에 영향을 주지 않습니다.",
                      "en": "Optional. Whether it is installed does not affect Direct execution."},
    "providers_none": {"ko": "사용 가능한 Direct provider가 없습니다. Codex 또는 Claude Code CLI를 설치·로그인하세요.",
                       "en": "No Direct provider is available. Install and sign in to the Codex or Claude Code CLI."},
    "providers_ok": {"ko": "사용 가능한 Direct provider를 확인했습니다.",
                     "en": "Found at least one available Direct provider."},
    "journal_ok": {"ko": "정상", "en": "ok"},
    "run_needs_review": {"ko": "결과 확인 필요", "en": "needs review"},
    "run_resumable": {"ko": "이어서 실행 가능", "en": "resumable"},
    "run_unreadable": {"ko": "읽을 수 없음", "en": "unreadable"},
}


def normalized_locale(locale: str) -> str:
    value = (locale or "auto").lower().replace("_", "-").split("-", 1)[0]
    if value == "auto":
        # Prefer the process locale, with LANG as the broadly portable
        # fallback.  Never mutate the environment or canonical data.
        value = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES")
                 or os.environ.get("LANG") or "en").lower().replace("_", "-").split("-", 1)[0]
    return value if value in {"ko", "en"} else "en"


def objective_locale(objective: str) -> str | None:
    """Detect supported natural language without storing it in canonical state."""

    if any("\uac00" <= character <= "\ud7a3" for character in objective or ""):
        return "ko"
    letters = [character for character in objective or "" if character.isalpha()]
    if letters and sum(character.isascii() for character in letters) / len(letters) >= 0.8:
        return "en"
    return None


def configured_locale(root: Path) -> str | None:
    """Read a presentation preference from project, then user configuration."""

    xdg_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    candidates = (root / ".graphori" / "config.json", xdg_root / "graphori" / "config.json")
    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get("language")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(value, str) and value.lower() in {"ko", "en"}:
            return value.lower()
    return None


def resolve_locale(
    preference: str,
    *,
    root: Path | None = None,
    objective: str = "",
) -> str:
    """Resolve explicit -> configured -> objective -> process locale."""

    if preference and preference.lower() != "auto":
        return normalized_locale(preference)
    configured = configured_locale((root or Path.cwd()).resolve())
    return configured or objective_locale(objective) or normalized_locale("auto")


def label(table: Mapping[str, Mapping[str, str]], key: str, locale: str) -> str:
    values = table.get(key)
    if values is None:
        return key
    language = normalized_locale(locale)
    return values.get(language) or values.get("en") or key


def team_label(team_id: str, locale: str) -> str:
    return label(TEAM_LABELS, team_id, locale)


def status_label(status: str, locale: str) -> str:
    return label(STATUS_LABELS, status, locale)


def effort_label(effort: str, locale: str) -> str:
    return label(EFFORT_LABELS, effort, locale)


def route_label(route: str, locale: str) -> str:
    return label(ROUTE_LABELS, route, locale)


def omission_reason_label(reason: str, locale: str) -> str:
    return label(OMISSION_REASON_LABELS, reason, locale)


def presentation_vocabulary() -> dict[str, object]:
    """Return labels for consumers without making them canonical state."""

    return {
        "supported_locales": sorted(SUPPORTED_LOCALES),
        "teams": {key: dict(value) for key, value in TEAM_LABELS.items()},
        "statuses": {key: dict(value) for key, value in STATUS_LABELS.items()},
        "efforts": {key: dict(value) for key, value in EFFORT_LABELS.items()},
        "routes": {key: dict(value) for key, value in ROUTE_LABELS.items()},
        "omission_reasons": {
            key: dict(value) for key, value in OMISSION_REASON_LABELS.items()
        },
    }

def doctor_label(key: str, locale: str) -> str:
    return label(DOCTOR_LABELS, key, locale)


def journal_label(key: str, locale: str) -> str:
    return label(JOURNAL_LABELS, key, locale)


def runtime_label(key: str, locale: str) -> str:
    """Look up a runtime message, falling back to the journal's own keys."""
    if key in RUNTIME_LABELS:
        return label(RUNTIME_LABELS, key, locale)
    return label(JOURNAL_LABELS, key, locale)
