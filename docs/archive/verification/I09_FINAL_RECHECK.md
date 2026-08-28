# I09 독립 재검증 보고서 (fresh verifier)

- 재검증자: 독립 fresh verifier(Claude Sonnet 5). I01~I09의 어떤 구현·이전
  감사에도 참여하지 않은 새 세션이며, `I09_FIX_REPORT.md`를 작성한 구현자
  (Luna)와 다른 모델이다.
- 검증 대상: `dotoricode/graphori` PR #1, head SHA
  `e6fa7086a827c982a6632abd6664dbb048a7fd9a`
- 검증 일시: 2026-08-10 (Asia/Seoul)
- 실행 환경: Windows, Python 3.12.1(로컬 재실행), GitHub Actions(Windows
  3.11/3.12 + macOS, 실제 hosted runner)
- Human Gate 출처: **사용자가 2026-08-10 대화에서 단계별 검증과 PR
  push·merge를 명시적으로 승인**했다. 이 승인은 "검증을 대신 해준다"는
  뜻이 아니라 "검증한 결과를 push/merge해도 된다"는 뜻으로만 해석했고,
  이 승인이 실제 테스트 실행을 대신하지도 않았다 — 아래 모든 결과는 이번
  세션에서 직접 실행해 확인한 것이다.

## 0. 12살도 이해하는 요약

지난 시험(`I09_FINAL_AUDIT.md`)에서 시험관은 "다시 하기(REVISE)는 몇 번까지
자동으로 봐주나?"라는 질문에 규칙 공책끼리 답이 달랐던 것을 찾아냈다(한
권은 "3번", 두 권은 "1번"). 그래서 통과 도장을 찍지 않고 돌려보냈다.

이번에 구현자가 프로그램을 고쳤다: 이제 기본값은 "1번"이다. 첫 번째
"다시 해와"는 들어주고, 두 번째부터는 자동으로 안 봐주고 사람(Human Gate)을
부른다. 나는 이걸 구현자의 말만 믿지 않고, 완전히 새 시험 문제를 직접
만들어서 다시 풀어봤다 — 구현자가 쓴 테스트를 읽지 않고 내가 처음부터
짠 코드로 같은 걸 확인했다. 결과: 구현자 말대로였다. 그리고 옛날에 있던
118개 테스트, 문법 검사, 대시보드, skill 검사기, GitHub 자동 검사도 전부
다시 통과했다. 새로 망가진 곳은 없었다.

그래서 이번에는 **통과(APPROVE)** 도장을 찍는다. 진행률은 **9/9 = 100%**로
올린다.

## 1. 검증 범위 (이번 재검증은 범위를 넓히지 않았다)

지시에 따라 이번 재검증은 `I09_FINAL_AUDIT.md`가 남긴 **유일한 blocking
defect**(REVISE 자동 상한 불일치)와 그 수정으로 인한 **회귀 여부**만
확인했다. 이전 감사의 40개 probe 전체나 다른 ADR 항목을 처음부터 다시
넓게 훑지 않았다(이미 이전 감사에서 39/40 OK로 확인된 항목들이고, 이번
커밋은 그 항목들을 건드리지 않았다).

### 1.1 읽은 문서

1. `docs/verification/I09_FINAL_AUDIT.md` (이전 감사, REVISE 사유 전체)
2. `docs/verification/I09_FIX_REPORT.md` (구현자의 수정 보고)
3. `docs/decisions/0002-risk-compiled-task-graph.md`,
   `docs/decisions/0005-mvp-simple-single-verifier.md`
4. `docs/IMPLEMENTATION_PLAN.md` 2단계(I02)·9단계(I09) acceptance 문구
5. `src/graphori_core/compiler.py`의 `RevisionController` 전체와 그
   `git show e6fa708`(변경분)
6. `tests/test_core.py`의 변경된 테스트(`test_revision_limit_is_one_and_second_revise_escalates_without_new_worker`)

## 2. 핵심 결함 재검증 — 독립 재현

이전 시험관이 쓴 테스트를 그대로 믿지 않고, **내가 새로 짠 별도의
probe 스크립트**로 같은 것을 확인했다(`sys.path`로 실제
`src/graphori_core`만 불러왔고, 저장소 파일은 하나도 건드리지 않았다).

| # | probe (직접 작성) | 결과 |
|---|---|---|
| 1 | `RevisionController()` 기본 `max_revisions`가 `1` | OK |
| 2 | 첫 번째 `record("revise")` → `REVISED` | OK |
| 3 | 첫 번째 호출 뒤 `revise_count == 1` | OK |
| 4 | `task:revision-1` 노드 생성됨 | OK |
| 5 | 두 번째 `record("revise")` → `ESCALATED` | OK |
| 6 | 두 번째 호출 뒤에도 `revise_count == 1`(더 늘지 않음) | OK |
| 7 | `task:revision-2` 노드는 생기지 않음 | OK |
| 8 | 두 번째 호출 전후로 WORKER 노드 집합이 그대로(새 worker 없음) | OK |
| 9 | 두 번째 호출 전후로 `rework_of` edge 집합이 그대로(새 edge 없음) | OK |
| 10 | `human_gate_required` signal을 가진 노드가 실제로 생김 | OK |
| 11 | 생성자에 `max_revisions=3`을 명시적으로 넘기면 그 값(3)이 그대로 적용됨(오버라이드 기능 자체는 살아있음) | OK |
| 12 | 그 오버라이드 인스턴스와 별개로, 이후 새로 만든 기본 `RevisionController()`는 여전히 `1`(오버라이드가 전역 기본값을 바꾸지 않음) | OK |
| 13 | `src/` 전체에 `RevisionController(`를 호출하는 곳이 `compiler.py`의 클래스 정의 자체를 빼면 **0곳**(AST 아님, 텍스트 스캔이지만 결과는 grep과 동일) | OK |

**13개 전부 OK.** 구현자의 수정이 실제로 ADR 0005 §9·
`IMPLEMENTATION_PLAN.md`("revise 2회가 거절된다")와 일치한다.

### 2.1 "기본값 우회" 질문에 대한 답 (지시 3번 항목)

`RevisionController`를 실제로 호출하는 곳은 저장소 전체에서
`tests/test_core.py` 두 곳뿐이다(`grep -rn "RevisionController"
src/ tests/ scripts/` 결과). `src/graphori_adapters`, `cli.py`,
`reducer.py` 어디에도 이 클래스를 인스턴스화하는 코드가 없다 — 즉 지금
**활성 실행 경로 자체가 존재하지 않는다**(이전 감사와 같은 관찰). 그래서
"다른 max_revisions를 명시적으로 주는 API가 활성 기본값을 몰래 우회하는가"
라는 질문의 답은: **우회할 활성 기본 경로가 아직 없으므로 우회도 없다.**
생성자의 명시적 override 기능(예: `RevisionController(max_revisions=3)`)은
남아 있고 이는 의도된 것이다(과거 fixture 등 다른 정책이 필요할 때를 위한
것이라고 `I09_FIX_REPORT.md`가 밝힘). 중요한 것은 **인자를 생략했을 때의
기본값**이며, probe 1·12가 그 기본값이 `1`이고 다른 인스턴스의 override로
흔들리지 않음을 확인했다.

## 3. 회귀 확인 — 전체 재실행 결과 (Windows, 이 세션에서 직접 실행)

| 명령 | 결과 |
|---|---|
| `python -m unittest discover -s tests -v` | **118/118 PASS** (`Ran 118 tests in 14.740s`, `OK`) — I09 이전 감사 때와 같은 개수, 회귀 없음 |
| `python -m compileall -q src tests scripts graphori` | 통과, 문법 오류 없음 |
| `python scripts/dashboard_smoke.py` | `{"status": "pass", "transport": "http", "finite": true}` |
| `python graphori/scripts/validate_skill.py graphori` | `Skill is valid!` |
| `python scripts/generate_ci_evidence.py --platform windows --output <scratchpad>/ci-evidence-windows.json` | 5개 fixture(`portable`, `core`, `adapter`, `dashboard`, `process_supervisor`) 모두 `pass`, `scope: runner_actual` |
| `git status` | `nothing to commit, working tree clean`, `up to date with 'origin/feat/mvp-demo-i05-i08'` |
| `git diff --check` | 공백/개행 오류 없음 |

## 4. GitHub Actions 실제 확인 (`gh` CLI로 새 SHA 직접 조회)

- `gh run list --repo dotoricode/graphori`로 head SHA
  `e6fa7086a827c982a6632abd6664dbb048a7fd9a`의 실행 두 건을 직접 조회:
  - `push` run `31326371177` → **success**
  - `pull_request` run `31326373980` → **success**
- `gh run view 31326371177 --json jobs`로 job 단위까지 확인:
  - `Windows Python 3.12` → `completed` / **success**
  - `Windows Python 3.11` → `completed` / **success**
  - `macOS contract fixtures` → `completed` / **success**
- PR #1(`I08 GitHub Actions portable contract CI`, `feat/mvp-demo-i05-i08`
  → `main`)은 여전히 `OPEN`, `mergeable: MERGEABLE`.

## 5. 이전 감사가 지적한 문서 불일치가 실제로 해소됐는가

- `docs/decisions/0002-risk-compiled-task-graph.md`에 "ADR 0005가 이
  문서의 REVISE 3회·WIP 4·고정 team 문구를 부분 대체한다"는 안내문이
  추가됐고, 본문의 "3회"·"WIP 4" 표현에도 "과거 기록값이며 현재 정책이
  아니다"라는 문구가 붙었다. 직접 읽어 확인했다.
- `docs/IMPLEMENTATION_PLAN.md`의 "revise 2회가 거절된다"·"1회 revise
  뒤 자동 작업이 더 생기지 않는다" 문구는 이번 커밋에서 바뀌지 않았고,
  지금 코드 동작과 정확히 일치한다(2장 probe로 확인).
- `docs/decisions/0005-mvp-simple-single-verifier.md` §9의 "1회만
  자동으로 한다"는 문구도 바뀌지 않았고 동일하게 일치한다.

세 문서가 이제 같은 숫자(1)를 말한다. 이전 감사가 요구한 "코드 또는 문서
중 하나를 고쳐서 두 문서가 같은 숫자를 말하게 한다"는 조건이 코드를 문서
쪽(1회)에 맞추는 방식으로 충족됐다.

## 6. 판정

> **VERDICT: APPROVE**

- 이전 감사의 유일한 blocking defect(REVISE 자동 상한 불일치)는 코드
  수정으로 실제로 해소됐다. 독립적으로 새로 작성한 13개 probe로 직접
  재현·확인했다.
- 118개 unittest, compileall, dashboard smoke, skill validator, Windows
  evidence manifest(5 fixture), `git diff --check` 모두 이 세션에서
  다시 실행해 통과를 직접 확인했다 — 이전 감사 대비 회귀 없음.
- 새 SHA(`e6fa708`)의 GitHub Actions push/PR 실행이 모두 success이고,
  Windows 3.11/3.12·macOS job 셋 다 success임을 `gh` CLI로 직접
  조회했다.
- 이번 재검증은 유일한 blocking defect와 회귀만 확인했고, 이전 감사가
  이미 39/40으로 통과시킨 나머지 항목을 다시 넓게 훑지는 않았다(지시된
  범위를 그대로 지켰다).

### 진행률

승인된 구현 단계 기준 진행률을 **9/9 = 100%**로 올린다. I01~I09 전체가
독립 검증을 통과했다.

### 남은 일

- 없음(차단 사유 없음). 문서 커밋 후 PR #1에 이번 최종 독립 검증 결과를
  쉬운 한국어로 남긴다.
