# I10 installable skill 독립 검증 (12살도 이해하는 버전)

이 문서는 PR #2("installable Graphori skill and document indexes")를 **구현팀 설명을 믿지 않고**, 검증팀이 직접 명령을 실행해서 확인한 기록입니다. 어려운 말 없이, "무엇을 확인했고, 기대한 값은 무엇이고, 실제로 나온 값은 무엇인지"만 적습니다.

## 한눈에 보기

- 확인한 커밋(SHA): `d6a34ce294458643629447216bbb04b6bc9f895f`
- PR #2 주소: https://github.com/dotoricode/graphori/pull/2
- **최종 결론: REVISE (두 가지를 고쳐야 통과할 수 있어요)**
  1. README에 적힌 Windows 시작 명령 중 두 줄이 그대로 실행하면 에러가 납니다.
  2. 저장소 밖(`<outside-workspace>\build\ci-artifacts\README.md`)에 우연히 생긴 것으로 보이는 파일이 있습니다.
- 그 외 나머지 항목(테스트 118개, skill validator, 설치기, 개인정보 흔적, 대시보드 화면, 실제 완료 100% 증거)은 모두 통과했습니다.

---

## 1. git 상태와 PR #2, Actions 결과

**확인 명령**
```
git status --short --branch
git rev-parse HEAD
gh pr view 2 --json number,title,state,isDraft,mergeable,headRefOid
gh api repos/dotoricode/graphori/commits/<SHA>/check-runs
```

**기대값**: PR #2가 열려 있고(OPEN), 병합 가능(MEARGEABLE)하며, Windows Python 3.11 / 3.12 / macOS 세 개 잡이 **그 커밋(SHA)** 에서 전부 성공(success).

**실제값**
- 브랜치: `feat/installable-skills-and-doc-indexes`, 작업 트리 깨끗함(clean)
- 최신 커밋: `d6a34ce294458643629447216bbb04b6bc9f895f`
- PR #2: `state: OPEN`, `isDraft: false`, `mergeable: MERGEABLE`, `headRefOid`가 위 커밋과 정확히 같음
- Actions 결과(정확히 이 커밋 기준, `check-runs` API로 직접 조회):
  - Windows Python 3.11 → `success`
  - Windows Python 3.12 → `success`
  - macOS contract fixtures → `success`

**판정: PASS**

---

## 2. README에 적힌 순서 그대로 따라 하기 (Windows / macOS)

README의 "Windows 빠른 시작"에는 이렇게 적혀 있습니다.

```powershell
python -m unittest discover -s tests -v
python scripts/dashboard_server.py --root .
python -m src.graphori_core.cli --root . --run-id run-demo run -- python -c "print('hello')"
python -m src.graphori_core.cli --root . --run-id run-demo status --json
python scripts/publish_snapshot.py --root . --run-id run-demo --output build/run-demo.snapshot.json
```

**실제로 그대로 실행해 봤습니다.**

- `python -m src.graphori_core.cli --root . --run-id run-verify-test run -- python -c "print('hello')"`
  → **에러**: `error: run root must be an absolute path: '.'`
- `python -m src.graphori_core.cli --root . --run-id run-verify-test status --json`도 같은 이유로 실패할 것입니다(같은 코드 경로 사용).
- `python scripts/dashboard_server.py --root .` → 정상 시작(내부에서 `Path(root).resolve()`로 알아서 절대경로로 바꿔줌)
- `python scripts/publish_snapshot.py --root . --run-id run-verify-test --output build/run-verify-test.snapshot.json` → 정상 동작(마찬가지로 내부에서 알아서 절대경로로 바꿔줌)
- 같은 명령을 **절대경로**로 바꿔서 실행하면 (`--root "$(pwd)"`) 전부 정상 동작하고, 실제 journal과 상태 결과가 나옵니다.

**왜 이런 차이가 날까요?**
`src/graphori_core/paths.py`의 `resolve_run_root()` 함수는 일부러 상대경로를 거부하도록 설계되어 있습니다(보안 계약: run root는 반드시 절대경로). 반면 `scripts/dashboard_server.py`와 `scripts/publish_snapshot.py`는 내부에서 `Path(root).resolve()`를 호출해서 상대경로를 알아서 절대경로로 바꿔줍니다. 그런데 CLI(`graphori_core.cli`)의 `run`/`status` 명령은 이 변환을 하지 않고 곧바로 `resolve_run_root()`를 호출하기 때문에, README에 적힌 `--root .` 그대로는 실패합니다.

**macOS/Linux**: README는 macOS 관련해서는 "hosted CI에서 성공했고 로컬 macOS 직접 검증은 `deferred`"라고 명확히 적어 놓았고, 별도의 macOS 전용 quickstart 명령 블록은 없습니다(설치기 `install_skill.sh`만 안내). 이 부분은 README가 스스로 "아직 로컬 macOS는 못 해봤다"고 정직하게 적어 놓았으므로 문제로 보지 않습니다. macOS hosted CI 실제 로그는 5번 항목에서 확인합니다.

**판정: FAIL (Windows quickstart의 CLI 두 줄)** — README를 그대로 따라 하면 새로 시작하는 사람이 바로 에러를 만납니다.

**최소 수정 제안**: README의 CLI 예시 두 줄만 절대경로를 쓰도록 고치면 됩니다. 예:
```powershell
$root = (Get-Location).Path
python -m src.graphori_core.cli --root $root --run-id run-demo run -- python -c "print('hello')"
python -m src.graphori_core.cli --root $root --run-id run-demo status --json
```
CLI 코드 자체(보안 계약)는 바꿀 필요가 없습니다. 문서만 고치면 됩니다.

---

## 3. 전체 검증 명령 독립 실행

| 확인 항목 | 명령 | 기대값 | 실제값 | 판정 |
|---|---|---|---|---|
| 전체 단위 테스트 | `python -m unittest discover -s tests -v` | 전부 통과 | **118개 테스트, 전부 `OK`** | PASS |
| 컴파일 검사 | `python -m compileall -q src tests scripts graphori` | 에러 없음 | 에러 없음(EXIT 0) | PASS |
| skill validator | `python graphori/scripts/validate_skill.py graphori` | `Skill is valid!` | `Skill is valid!` | PASS |
| 대시보드 smoke | `python scripts/dashboard_smoke.py` | `finite: true` | `{"status": "pass", "transport": "http", "finite": true}` | PASS |
| diff 공백 검사 | `git diff --check main...HEAD` | 문제 없음 | 출력 없음(EXIT 0) | PASS |
| 문서 색인 완전성 | `python scripts/validate_docs_indexes.py` | 색인 완전 | `Document indexes are valid (74 markdown documents indexed).` | PASS |

**판정: PASS (전체)**

---

## 4. canonical `graphori/` skill 폴더 구조

**확인**: `graphori/` 폴더 안에 무엇이 있는지 직접 나열하고, `SKILL.md`를 직접 읽었습니다.

```
graphori/
  SKILL.md
  agents/openai.yaml
  references/canonical-routing.md
  scripts/validate_skill.py
```

- **README.md 없음**: 맞습니다. 확인했습니다.
- **`SKILL.md` frontmatter**: `name: graphori`, `description: ...` 정확히 있음(Claude Code가 요구하는 형식).
- **`agents/openai.yaml`**: `display_name`, `short_description`, `default_prompt` 있음(Codex 계열이 읽는 형식).
- **`references/canonical-routing.md`**: 존재, `SKILL.md`에서 링크로 참조됨.
- **실제로 Claude Code가 읽을 수 있는지**: 이 검증 작업 자체가 이 세션에서 `Skill(graphori)`를 호출해서 이 `SKILL.md` 내용을 그대로 불러왔습니다. 즉, "읽을 수 있다"는 것을 실제로 증명했습니다(추측이 아님).

**판정: PASS**

---

## 5. 설치기(installer) 검증

### 5-1. PowerShell installer — 임시 HOME 환경에서 직접 실행

가짜(임시) 홈 폴더를 만들어서 `$env:HOME`을 그 폴더로 돌리고, 진짜 내 컴퓨터 설정은 전혀 건드리지 않은 채로 아래를 순서대로 실행했습니다.

1. **처음 설치** (`-Target both`): `codex: installed...`, `claude: installed...`, 둘 다 `Skill is valid!` → **PASS**
2. **같은 상태에서 다시 실행(재실행 안전성)**: `codex: already matches canonical skill; validating.` / `claude: already matches canonical skill; validating.` → 아무것도 안 부수고 그대로 validator만 다시 통과 → **PASS**
3. **`graphori/SKILL.md`에 몰래 글자 추가(불일치 상황 흉내)한 뒤, `-Force` 없이 재실행**: `claude destination exists and differs: ... Use -Force to create a backup and replace it.`로 **거부**됨(에러코드 1, 아무것도 바꾸지 않음) → **PASS**
4. **`-Force`로 재실행**: `claude: backed up existing skill to ...\graphori.backup-20260810-030828`라는 날짜 붙은 백업을 만든 뒤 깨끗한 정식 버전으로 교체, `Skill is valid!` → **PASS**
5. **다른 skill(`other-skill`)을 미리 만들어 두고 위 과정 전부 실행**: 마지막에 확인해보니 `other-skill` 폴더와 내용(`SKILL.md`)이 전혀 손대지 않은 그대로 남아있음 → **PASS**

테스트가 끝난 뒤 임시 폴더는 모두 지웠습니다(내 실제 `.claude`, `.codex` 폴더는 손대지 않았습니다).

### 5-2. POSIX installer(`install_skill.sh`) — 로컬 Windows에서는 거짓 성공 처리하지 않음

Windows에서 `.sh` 스크립트를 억지로 돌려서 "성공했다"고 우기지 않았습니다. 대신 **macOS hosted CI의 실제 로그**를 그 커밋(SHA) 기준으로 직접 열어봤습니다.

- 워크플로 파일(`.github/workflows/ci.yml`) 확인: macOS 잡에 `POSIX installer temp-home test` 스텝이 있고, 실제로 `python scripts/test_installers.py --kind sh`를 실행함.
- 그 잡의 실제 로그(run id `31327886722`, job id `93281159930`)를 직접 열어보니:
  ```
  Run python scripts/test_installers.py --kind sh
  installer temp-home test passed: sh
  ```
- 이 run의 `headSha`가 `d6a34ce294458643629447216bbb04b6bc9f895f`로, PR #2의 최신 커밋과 정확히 같음을 확인.

**판정: PASS (둘 다)**

---

## 6. 실제 Codex/Claude Code 설치 경로와 canonical 파일 비교(읽기 전용)

내 컴퓨터에는 이미 예전에 설치된 graphori skill이 있었습니다(`~/.claude/skills/graphori`, `$CODEX_HOME/skills/graphori`). **이 폴더들을 수정하지 않고, 읽기만 해서** 저장소의 `graphori/` 폴더와 비교했습니다.

```
diff -rq graphori ~/.claude/skills/graphori
diff -rq graphori "$CODEX_HOME/skills/graphori"
python graphori/scripts/validate_skill.py ~/.claude/skills/graphori
python graphori/scripts/validate_skill.py "$CODEX_HOME/skills/graphori"
```

- 내용 파일은 전부 동일. 차이는 딱 두 가지뿐:
  - 설치된 쪽에 **빈** `assets/` 폴더가 남아있음(예전 스캐폴드 흔적, 지금 저장소의 canonical 소스에는 없음, 내용물이 없어서 기능에 영향 없음)
  - 저장소 쪽에만 `__pycache__`(파이썬이 자동으로 만드는 빌드 캐시, 애초에 배포 대상 아님)
- 두 설치 경로 모두 validator 결과 `Skill is valid!`
- **다른 skill(예: `caveman`, `tink`, `docpilot` 등)은 전혀 건드리지 않았습니다.**

**판정: PASS** (빈 `assets/` 폴더는 기능에 영향 없는 사소한 흔적으로만 기록)

---

## 7. 개인 절대경로 흔적 검사

**확인 명령**
```
git grep -In "<your-user-path>\|<your-user-name>" -- .
```

**기대값**: 저장소에 커밋된 파일 어디에도 실제 컴퓨터 사용자 이름이나 개인 절대경로가 남아있지 않아야 함.

**실제값**: 검색 결과 **0건**(아무것도 안 나옴). `build/ci-artifacts/*.json` 같은 CI 증거 파일도 문서(`build/README.md`)에 "호스트 절대 경로나 비밀값을 넣지 않는다"고 명시돼 있고 실제로도 지켜지고 있음을 확인했습니다.

**판정: PASS**

---

## 8. journal/verdict/snapshot 실제 증거 만들기 (percent=100 실증)

CLI의 기본 `run` 명령은 검증자(verifier) 승인 사건을 만들지 않습니다(설계상 최소 1-worker 흐름). 그래서 진짜로 "검증자 승인(verdict) → 통과한(passed) 노드 → run 종료(run_terminal)"까지 있는 run을 만들려면, 저장소가 실제로 제공하는 공개 함수(`journal.submit_event`, `JournalWriter`, `StateReducer`, `EvidenceStore` 등, CLI가 내부적으로 쓰는 것과 같은 함수)를 사용해서 직접 사건을 순서대로 기록해야 했습니다. **값을 미리 정해서 파일에 써넣은 것이 아니라, 진짜 사건을 실제 journal에 기록하고, 그 결과를 대시보드가 계산하게 했습니다.**

만든 run: `run-pr2-verify-a80224aa` (저장소 밖 임시 폴더에 생성, 저장소를 더럽히지 않음)

사건 순서: `run_created → graph_published → node_status_changed(ready/assigned/running) → attempt_dispatched → heartbeat → worker_finished → node_status_changed(awaiting_verification) → verdict_recorded(actor=verifier, verdict=pass, evidence_ids=[실제 EvidenceStore에 저장한 증거 ID]) → node_status_changed(passed) → run_terminal(succeeded)`

**확인 명령(제품이 실제로 쓰는 스크립트로 재확인)**
```
python scripts/publish_snapshot.py --root <임시root> --run-id run-pr2-verify-a80224aa --output <경로>
```

**실제로 나온 스냅샷 값**
```json
{
  "state": "completed",
  "terminal_status": "succeeded",
  "updatedAt": "2026-08-09T18:12:32.315315Z",
  "heartbeat": {"updatedAt": "2026-08-09T18:12:32.137297Z", "status": "heartbeat_recent"},
  "lastEvent": {"type": "run_terminal", "seq": 11, "updatedAt": "2026-08-09T18:12:32.315315Z"},
  "progress": {"completed": 1, "required": 1, "percent": 100, "basis": "verified_terminal_nodes"}
}
```

- `percent`가 100이 된 이유는 코드가 하드코딩한 게 아니라, `completed / required * 100`을 실제로 계산한 값입니다(`completed=1`, `required=1`).
- 시간이 좀 지난 뒤 다시 스냅샷을 열어보니 `heartbeat.status`가 `stale`로 바뀌었지만, `state`는 여전히 `completed`이고 `percent`도 여전히 100이었습니다. 즉 **"heartbeat가 오래되어도 이미 끝난 run의 완료 결과는 되돌아가지 않는다"**는 문서의 약속이 실제로 지켜짐을 확인했습니다.

**판정: PASS**

---

## 9. 대시보드 화면(흰 배경/흰 글씨, 대비, JS 문법, 100% 표시)

- `docs/dashboard/style.css`, `index.html`, `app.js`를 직접 읽고 `white`, `#fff`, `#ffffff` 문자열을 검색 → **0건**. 배경은 아주 어두운 남색(`#080d16`)이고 글자색은 거의 흰색(`#f5f7fb`)이라 대비가 뚜렷합니다. `color-scheme: dark`가 명시돼 있어 브라우저가 마음대로 밝은 배경으로 바꾸지도 않습니다.
- `node --check docs/dashboard/app.js` → 문법 오류 없음(조용히 통과).
- `python scripts/dashboard_smoke.py` → `finite: true`(무한 루프 없이 끝남).
- `app.js`의 진행률 표시 코드는 `Math.max(0, Math.min(100, ...))`로 **0~100 사이로 항상 잘라서** 보여주므로 100%를 넘거나 음수가 되는 표시 사고가 나지 않습니다.
- **임시 포트(18765)에 대시보드 서버를 새로 띄워서** 실제 HTTP 응답을 확인했습니다(기존 8765 서버는 계속 그대로 켜둔 채로, 건드리지 않았습니다):
  - `GET /` → `200`
  - `GET /runs/run-pr2-verify-a80224aa/snapshot` → 위 8번 항목과 완전히 같은 값(`percent:100`, `state:completed` 등)을 실제 HTTP 응답으로 확인.
  - 확인 후 이 임시 서버는 종료했고, 포트 18765는 다시 비워졌습니다.

**판정: PASS**

---

## 10. 저장소 밖에 생긴 의심스러운 파일

**확인 대상**: `<outside-workspace>\build\ci-artifacts\README.md` (저장소 폴더 `<repo-root>\` 밖에 있음)

**실제로 있었습니다.** 내용을 저장소 안의 `build/ci-artifacts/README.md`와 비교했더니:

- 이 파일은 **저장소의 커밋 `95d1ee3`("fix: make installer failures diagnosable and index build evidence") 시점의 `build/ci-artifacts/README.md` 내용과 한 글자도 다르지 않게 완전히 같습니다.**
- 이 파일이 만들어진 시각은 `2026-08-10 02:43:31`인데, 커밋 `95d1ee3`가 만들어진 시각은 `2026-08-10 02:57:00`, 바로 앞 커밋 `a22108a`는 `02:54:47`입니다. 즉 **이 PR을 작업하던 바로 그 시간대(02:43~02:58) 안에 만들어졌습니다.**
- 경로도 `<repo-root>\build\ci-artifacts\README.md`가 아니라 그 **한 단계 위**인 `<outside-workspace>\build\ci-artifacts\README.md`에 생겼습니다. 즉 어떤 명령이 저장소 폴더가 아니라 그 부모 폴더에서 실행되면서, 상대경로로 같은 파일을 하나 더 만든 것으로 보입니다.
- 그 폴더(`<outside-workspace>\build\`) 안에는 이 파일 하나만 있고 다른 것은 없습니다.

이 정도면 "이번 PR 작업 중 실수로 생긴 파일"이라는 근거가 충분하다고 판단합니다. **검증팀은 이 파일을 지우지 않았습니다**(코드/파일 수정 금지 규칙). 구현팀이 안전하게 확인 후 지워주세요.

**판정: REVISE 대상** — 재현 방법: 위 경로를 직접 열어 커밋 `95d1ee3`의 `build/ci-artifacts/README.md`와 바이트 단위로 비교하면 동일함을 확인할 수 있습니다. 최소 수정 범위: `<outside-workspace>\build\` 폴더(파일 1개 + 빈 폴더 2개)만 삭제하면 됩니다. 저장소 안 파일이 아니므로 git 작업은 필요 없습니다.

---

## 최종 결론

| 항목 | 판정 |
|---|---|
| 1. git/PR2/Actions | PASS |
| 2. README quickstart 그대로 실행 | **FAIL** (CLI `--root .` 두 줄) |
| 3. 테스트/검증 스크립트 | PASS |
| 4. canonical skill 구조 | PASS |
| 5. installer(PowerShell 임시 HOME + macOS hosted 로그) | PASS |
| 6. 실제 설치 경로 비교 | PASS |
| 7. 개인 경로 흔적 | PASS |
| 8. journal/verdict/snapshot 100% 실증 | PASS |
| 9. 대시보드 화면/대비/JS | PASS |
| 10. 저장소 밖 우발 파일 | **REVISE 필요** |

**최종 판정: REVISE**

**구현팀에게 요청하는 최소 수정 두 가지**
1. README "Windows 빠른 시작"의 CLI(`run`, `status`) 예시 두 줄에서 `--root .`를 절대경로로 바꿔주세요(코드 수정 아님, 문서만 수정).
2. `<outside-workspace>\build\ci-artifacts\README.md`(저장소 밖, 이번 작업 중 실수로 생긴 것으로 보임)를 확인 후 삭제해주세요.

그 외 모든 항목은 실제로 명령을 실행해서 직접 확인했고 전부 기대한 대로 동작했습니다.
