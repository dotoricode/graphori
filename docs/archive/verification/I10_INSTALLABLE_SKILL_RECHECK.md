# I10 설치형 skill 최종 재검증 (recheck)

이 문서는 `I10_INSTALLABLE_SKILL_REVIEW.md`에서 **REVISE**로 남았던 두 문제를 `I10_FIX_REPORT.md`가 고친 뒤, 그 결과를 처음부터 다시 확인한 기록입니다. 이번이 REVISE 이후 딱 한 번 하는 recheck입니다. 코드나 기능은 하나도 고치지 않았고, 이 문서와 `docs/verification/README.md` 색인, PR #2 댓글만 새로 썼습니다. 모든 명령은 직접 실행했고, 화면에 찍힌 실제 값만 적었습니다.

## 요약: 최종 판정은 **APPROVE**

12살도 알 수 있게 말하면: "숙제 검사표에 있던 할 일을 하나씩 다시 해봤는데, 전부 성공(PASS)이었어요." 실패나 새로운 문제는 하나도 못 찾았습니다.

## 1. PR #2 head, 상태, 작업 폴더 확인

| 확인 항목 | 예상 값 | 실제 값 | 결과 |
|---|---|---|---|
| 로컬 브랜치 HEAD | `97ded0269bf53ee8f1080389b52dc138b5a8df9f` | `97ded0269bf53ee8f1080389b52dc138b5a8df9f` (`git rev-parse HEAD`) | PASS |
| origin의 같은 브랜치 | 위와 같음 | `git rev-parse origin/feat/installable-skills-and-doc-indexes` → 동일 | PASS |
| PR #2 head sha (GitHub) | 위와 같음 | `97ded0269bf53ee8f1080389b52dc138b5a8df9f` | PASS |
| PR 상태 | open, draft 아님 | `state: open`, `draft: false` | PASS |
| 병합 가능 상태 | 충돌 없음 | `mergeable_state: clean` | PASS |
| 작업 폴더(worktree) | clean | `git status` → `nothing to commit, working tree clean` (검사 시작 시점과 모든 검사를 마친 뒤 두 번 확인) | PASS |

## 2. README Windows 빠른 시작을 그대로 실행

README에 적힌 글자 그대로 PowerShell에서 실행했습니다.

```powershell
$root = (Get-Location).Path
python -m unittest discover -s tests -v
python scripts/dashboard_server.py --root $root
```

- `python -m unittest discover -s tests -v` → 실제로 **121개 테스트, 전부 OK** (아래 3번에 자세히 적었습니다).
- CLI 예시도 그대로 실행했습니다.

```powershell
$root = (Get-Location).Path
python -m src.graphori_core.cli --root $root --run-id run-i10-recheck-verify run -- python -c "print('hello')"
python -m src.graphori_core.cli --root $root --run-id run-i10-recheck-verify status --json
python scripts/publish_snapshot.py --root $root --run-id run-i10-recheck-verify --output build/run-i10-recheck-verify.snapshot.json
```

실제 결과:
- `run` 명령: `"exit_code": 0`, `"terminal_status": "succeeded"`, `"timed_out": false`
- `status --json` 명령: `"terminal_status": "succeeded"`, `"node_states": {"worker": "passed"}`, `"event_count": 10`
- `publish_snapshot.py`: `{"run_id": "run-i10-recheck-verify", "state": "completed", "percent": 0, ...}` — 여기서 percent가 0인 건 정상입니다. `run`/`status` 명령은 검증자의 "verdict"(합격 도장)를 안 남기기 때문에 진행률이 안 올라갑니다. 이건 8번 항목에서 실제로 verdict를 남기는 journal로 다시 확인했습니다.

**`--root .` 잔존 여부**: 사용자용 quickstart 전체(README.md, 이게 유일한 사용자용 quickstart 문서입니다)를 검색한 결과, `--root .` 는 **0건**이었습니다. Windows는 `$root = (Get-Location).Path`, macOS/Linux는 `repo_root="$(pwd -P)"`로 절대경로를 먼저 저장한 뒤 그 변수를 사용합니다. (`--root .` 라는 글자는 옛날 검토/수정 기록 문서인 `I06_BUILD_REPORT.md`, `I06_STAGE_REVIEW.md`, `I10_FIX_REPORT.md`, `I10_INSTALLABLE_SKILL_REVIEW.md` 안에는 "예전에 이게 문제였다"는 설명으로만 남아 있고, 실제 사용자용 명령에는 없습니다.) → **PASS**

## 3. 테스트/검사 도구를 독립적으로 실행

| 명령 | 기대값 | 실제 값 | 결과 |
|---|---|---|---|
| `python -m unittest discover -s tests -v` | 약 121개, 전부 OK | `Ran 121 tests in 21.543s` / `OK` | PASS |
| `python -m compileall -q src scripts tests` | 에러 없음(종료 코드 0) | 종료 코드 0, 출력 없음 | PASS |
| `python scripts/validate_docs_indexes.py` | 문서 색인 정상 | `Document indexes are valid (76 markdown documents indexed).` | PASS |
| `python graphori/scripts/validate_skill.py graphori` | skill 정상 | `Skill is valid!` | PASS |
| `python scripts/test_installers.py --kind powershell` | 임시 HOME에 설치 성공 + force 백업 확인 | `installer temp-home test passed: powershell` | PASS |
| `python scripts/test_installers.py --kind sh` | Windows에서는 Git Bash HOME 한계로 deferred (설계상 정상, macOS hosted CI에서만 실제 검증) | `installer temp-home test deferred: POSIX shell requires POSIX CI` | PASS (문서와 일치하는 정상적인 deferred) |
| `python scripts/dashboard_smoke.py` | HTTP 응답에 "Graphori" 포함, 유한(finite) | `{"status": "pass", "transport": "http", "finite": true}` | PASS |
| `git diff --check main...HEAD` | 공백 오류 없음 | 종료 코드 0, 출력 없음 | PASS |
| `git diff --check` (작업 폴더) | 공백 오류 없음 | 종료 코드 0, 출력 없음 | PASS |

## 4. 실제 개인 이름·경로가 0건인지 검사

`getpass.getuser()`로 확인하는 `tests/test_personal_paths.py`도 121개 테스트 안에서 이미 통과했지만, 그 테스트는 `build/`와 `.graphori/` 폴더는 검사하지 않으므로 저장소 전체 git 추적 파일을 대상으로 직접 다시 찾아봤습니다.

```
git grep -nIi "<현재 사용자 이름>" -- .   # 테스트 파일 자기 자신 말고는 0건
git grep -nE "<absolute-home-pattern>" -- .
```

찾은 것은 딱 두 줄인데 둘 다 실제 개인 정보가 아니었습니다.
- `docs/research/PORTABILITY_AND_DEPENDENCY.md`: `<home>/graphori/runs` — 예시용 자리표시자(placeholder)입니다.
- `tests/test_process_supervisor.py`: `"HOME": "/home/x"` — 테스트에서 만든 가짜 값입니다.

실제 사용자 이름이나 진짜 Windows/macOS 개인 홈 경로는 **0건**이었습니다. → **PASS**

(이 보고서 자신도 규칙을 지켜서, 실제 이름이나 절대경로 대신 `<home>`, `<workspace>` 같은 자리표시자만 사용합니다.)

## 5. 저장소 밖 우발 파일 확인 (읽기 전용)

이전 검증(REVISE)에서 지적됐던 `<workspace-parent>/build/ci-artifacts/README.md`가 `I10_FIX_REPORT.md`에서 지웠다고 적은 그 파일입니다. 이번에는 지운 게 맞는지, 그리고 새로 생긴 우발 파일이 없는지 다시 확인했습니다(파일을 만들거나 지우지 않고 보기만 했습니다).

- `<workspace-parent>/build/ci-artifacts/README.md`: **없음** (해당 경로 자체가 존재하지 않음)
- `<workspace-parent>/build/`: **없음**
- 참고로 `<workspace>`(저장소) 상위 폴더 한 단계 더 위에서 이름만 `build`인 빈 폴더 하나를 발견했습니다. 안에 파일이 전혀 없고(용량 0), 이번 검증 세션이 시작된 시각과 거의 같은 시각에 만들어져 있어서 이번 도구 환경이 만든 것으로 보이고, 지적됐던 그 경로(`<workspace-parent>/build/ci-artifacts/README.md`)와는 다른 위치입니다. 읽기 전용 확인이라 건드리지 않았고, PR 코드와는 무관해 보입니다. → 지적된 우발 파일은 **PASS**(정상적으로 삭제됨 확인), 무관한 빈 폴더는 참고로만 기록.

## 6. 실제 설치된 Codex/Claude Code 트리와 canonical `graphori/` 비교

이 컴퓨터에 실제로 설치돼 있는 두 위치를 canonical `graphori/`와 파일 목록·내용까지 비교했습니다.

- Claude Code: `<home>\.claude\skills\graphori`
- Codex: `$CODEX_HOME\skills\graphori` (이 환경은 `CODEX_HOME`이 지정돼 있어 그 경로를 사용, 기본값인 `~/.codex`가 아님)

```
diff -rq --exclude=__pycache__ graphori "<home>/.claude/skills/graphori"   → 차이 없음
diff -rq --exclude=__pycache__ graphori "<CODEX_HOME>/skills/graphori"    → 차이 없음
```

두 설치 폴더 모두 파일 4개(`SKILL.md`, `agents/openai.yaml`, `references/canonical-routing.md`, `scripts/validate_skill.py`)만 있고, canonical과 바이트까지 동일했습니다. README 파일이나 빈 `assets` 폴더 같은 잔여물은 **없었습니다**. 두 설치 폴더 모두에서 validator를 실행했습니다.

```
python graphori/scripts/validate_skill.py "<home>/.claude/skills/graphori"        → Skill is valid!
python graphori/scripts/validate_skill.py "<CODEX_HOME>/skills/graphori"          → Skill is valid!
```

다른 skill 폴더(`graphori.backup-*` 같은 이전 백업 등)는 건드리지 않았습니다. → **PASS**

## 7. GitHub Actions hosted CI 확인 (최신 SHA 97ded02...)

`gh run view 31329622907 --repo dotoricode/graphori`로 직접 확인했습니다.

- `headSha`: `97ded0269bf53ee8f1080389b52dc138b5a8df9f` (PR #2 head와 동일)
- 전체 `conclusion`: **success**
- Windows Python 3.11: **success** (모든 단계 success, "Unit and contract tests"부터 "Windows installer temp-home test"까지 포함)
- Windows Python 3.12: **success**
- macOS contract fixtures: **success** ("Run portable/core/adapter/dashboard and POSIX supervisor fixtures", "POSIX installer temp-home test" 포함)

GitHub PR check-runs API로도 같은 head sha에 대해 같은 세 job이 모두 `success`임을 다시 확인했습니다(중복 실행된 `31329625144`도 마찬가지로 세 job 모두 success). → **PASS**

## 8. 실제 journal로 progress=100% 계약 확인 (하드코딩 아님)

`python -m src.graphori_core.cli ... run`은 검증자의 "합격(verdict)" 사건을 남기지 않기 때문에 2번 항목에서는 percent가 0이었습니다. 그래서 이번에는 저장소 코드가 실제로 쓰는 것과 같은 방법(journal에 이벤트를 하나씩 쌓는 방식)으로, **저장소 밖 임시 폴더**에 직접 완전한 journal을 새로 만들었습니다: `run_created` → `graph_published` → `node_status_changed`(ready→assigned→running→awaiting_verification→passed) → **`verdict_recorded`(verdict=pass, 검증자 role)** → **`run_terminal`(terminal_status=succeeded)**.

그 다음 `scripts/publish_snapshot.py`를 그 journal에 대해 실행했습니다(숫자를 코드에 미리 써넣지 않고, 실제 journal 파일을 읽어서 계산한 결과입니다).

```json
{
  "state": "completed",
  "terminal_status": "succeeded",
  "updatedAt": "2026-08-09T18:48:14.744722Z",
  "heartbeat": {"updatedAt": null, "age_seconds": null, "status": "unknown"},
  "lastEvent": {"type": "run_terminal", "seq": 8, "updatedAt": "2026-08-09T18:48:14.744722Z"},
  "progress": {"completed": 1, "required": 1, "percent": 100, "basis": "verified_terminal_nodes"},
  "nodes": [{"id": "worker", "status": "passed", "progress": "advanced", "verdict": "pass"}]
}
```

`percent`가 정확히 **100**, `completed`(1) == `required`(1), `state`가 `completed`, `terminal_status`가 `succeeded`, `updatedAt`/`heartbeat`/`lastEvent`가 모두 값을 가지고 있는 것을 확인했습니다. `heartbeat.updatedAt`이 `null`인 이유는 이 시나리오에서 heartbeat 사건을 하나도 안 남겼기 때문이며(진행률이 heartbeat만으로 올라가지 않는다는 README의 설명과 일치), progress 계산과는 무관합니다. → **PASS**

## 9. 대시보드 화면(HTML/CSS/JS) 확인

파일: `docs/dashboard/index.html`, `docs/dashboard/style.css`, `docs/dashboard/app.js`

- **어두운 배경 / 밝은 글씨**: `style.css`의 `:root`에 `color-scheme:dark`, `--bg:#080d16`(아주 어두운 남색), `--text:#f5f7fb`(거의 흰색)가 이름 그대로 명시돼 있습니다. `body`도 어두운 색 그라데이션 배경을 씁니다.
- **대비(contrast)**: `--text`(#f5f7fb) 대 `--bg`(#080d16) 대비비를 계산하면 약 **18:1**로 WCAG AAA 기준(7:1)을 훨씬 넘습니다. 부제목에 쓰는 `--muted`(#9eabc0) 대 배경 대비도 약 **8.7:1**로 AA/AAA 기준을 넉넉히 넘습니다. 흰 바탕에 흰 글씨 같은 문제는 없습니다.
- **JS 문법**: `node --check docs/dashboard/app.js` → 에러 없이 통과.
- **finite number / 100% 계약**: `app.js`의 `render()` 함수에서 `const pct = Math.max(0, Math.min(100, Number(progress.percent) || 0));`로, 값이 숫자가 아니거나(NaN) 없어도 0으로, 100을 넘으면 100으로 강제로 묶습니다. 화면 진행률 막대 폭도 이 `pct` 값을 그대로 사용합니다.
- **HTTP smoke**: `python scripts/dashboard_smoke.py`는 자기만의 임시 폴더와 임시 포트로 서버를 새로 띄우고 끝나면 스스로 정리하는 독립 검사이며, 기존에 떠 있던 `127.0.0.1:8765` 서버와는 무관합니다. 실행 결과 `{"status": "pass", "transport": "http", "finite": true}`.
- 이미 떠 있던 실제 대시보드 서버(`127.0.0.1:8765`)는 **닫지 않았고**, 이 검증 과정에서 읽기 전용으로 `GET /`을 한 번 보내 `HTTP 200`과 정상 HTML(`<title>Graphori // Run HUD</title>`)을 받는 것만 확인했습니다. Orca 탭도 그대로 뒀습니다.

→ **PASS**

## 10. macOS 상태에 대한 명확한 안내

이번 recheck에서 macOS는 **hosted CI(7번 항목의 GitHub Actions)에서만** 실제로 검증됐습니다. 로컬 macOS 환경에서 직접 실행해 본 검증은 이번에도 **하지 않았고, 여전히 보류(deferred)** 상태입니다. README와 코드도 이 상태를 "deferred"라고 그대로 표시하며, `deferred`를 성공으로 바꿔 부르지 않습니다.

## 결론

REVISE로 남았던 두 문제(README quickstart의 `--root .`, 저장소 밖 우발 파일)는 모두 실제로 고쳐졌고, 이번 recheck에서 코드를 다시 읽고 명령을 다시 실행해서 독립적으로 확인했습니다. 그 외 항목(테스트 121개, compileall, 문서 색인 검사, skill validator, 설치기 임시 HOME 검사, 실제 설치 트리 비교, hosted CI, journal의 100% 진행률 계약, 대시보드 대비/문법)도 모두 실제 명령·실제 값으로 PASS를 확인했습니다. 새로운 문제는 발견하지 못했습니다.

**최종 검증팀 의견: APPROVE**
