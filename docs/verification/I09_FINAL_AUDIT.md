# I09 최종 독립 감사 보고서

- 감사자: 독립 최종 감사자(Claude Sonnet 5, 이번 I01~I08 구현·검수를 하지 않은 새 세션)
- 감사 대상: `dotoricode/graphori` PR #1, head SHA `317d32aa41e13090edf93244bceea0a30ffecb05`
- 감사 일시: 2026-08-10 (Asia/Seoul)
- 실행 환경: Windows, Python 3.12.1(로컬 재실행), GitHub Actions(Windows 3.11/3.12 + macOS, 실제 hosted runner)
- Human Gate 출처: **사용자가 2026-08-10 대화에서 단계별 검증과 PR push·merge를 명시적으로 승인**했다. 이 승인은 "검증을 대신 하겠다"는 뜻이 아니라 "검증한 결과를 push/merge해도 된다"는 뜻으로 해석했고, 검증되지 않은 사실은 만들어 쓰지 않았다.

## 0. 12살도 이해하는 요약

이번 감사는 지금까지 만든 여덟 개 숙제(I01~I08)를 처음부터 다시 확인하는
"마지막 시험관" 역할이다. 컴퓨터 검사(테스트)는 거의 다 통과했고, 실제
GitHub의 자동 검사도 성공했다. 그런데 시험관이 규칙 공책 세 권
(`ADR 0002`, `ADR 0005`, `docs/IMPLEMENTATION_PLAN.md`)을 나란히 놓고
읽어 보니, "다시 하기(REVISE)는 몇 번까지만 자동으로 봐주나?"라는 질문에
서로 다른 답이 적혀 있었다. 한 권은 "3번", 다른 두 권은 "1번"이라고
적혀 있었고, 실제로 짠 프로그램은 "3번" 쪽을 따르고 있었다. 이 불일치는
아무도 알아채지 못한 채 여덟 번의 검수를 모두 통과했다.

그래서 이번 시험관은 **"통과(APPROVE)" 도장을 찍지 않는다.** 다른 결함은
찾지 못했지만, 이 한 가지는 "약속한 안전장치가 약속대로 동작하는지"에
관한 것이라 그냥 넘어가지 않기로 했다. 진행률은 그대로 **8/9 = 88.9%**로
남긴다.

## 1. 감사 절차 — 무엇을, 어떤 순서로 읽고 실행했는가

### 1.1 읽은 문서 (원문 직접 읽음, 요약만 보지 않음)

1. `README.md`, `graphori/SKILL.md`
2. `docs/decisions/0001-portable-core-orca-adapter.md` ~ `0005-mvp-simple-single-verifier.md` 전체 5개
3. `docs/IMPLEMENTATION_PLAN.md` 전체
4. `TEAM_TOPOLOGY.md` (WIP/parallelism/REVISE 상한 절)
5. `docs/PROCESS.md` 전체(약 715줄, I01~I08 전체 기록)
6. `.github/workflows/ci.yml` 전체
7. I01~I08 최종 승인 보고서: `I01_SKILL_SCAFFOLD_REREVIEW_CLAUDE.md`,
   `I02_CORE_HARDENING1_REPORT_LUNA.md` + `I02_CORE_HARDENING1_REVIEW_CLAUDE.md`,
   `I03_I04_BUILD_REPORT.md` + `I03_I04_MILESTONE_REVIEW.md`,
   `I05_BUILD_REPORT.md` + `I05_STAGE_REVIEW.md`,
   `I06_BUILD_REPORT.md` + `I06_STAGE_REVIEW.md`,
   `I07_BUILD_REPORT.md` + `I07_STAGE_REVIEW.md`,
   `I08_BUILD_REPORT.md` + `I08_STAGE_REVIEW.md`
8. `src/graphori_core/*.py` 전체 소스(모델·리듀서·컴파일러·경로·프로세스·대시보드·에이전트러너·CLI, 총 약 3,100줄)와
   `src/graphori_adapters/orca/adapter.py`

### 1.2 처음 요구 vs 지금 결과 — 일치 여부 확인

각 ADR/IMPLEMENTATION_PLAN이 약속한 것과 실제 코드·테스트를 대조했다.

| 확인 항목 | 문서 근거 | 실제 코드 | 일치? |
|---|---|---|---|
| core는 Orca/OS API를 직접 import하지 않는다 | ADR 0001 | `src/graphori_core/*.py`에 `graphori_adapters`/`orca` import 0건(AST로 확인, probe 29) | 일치 |
| canonical enum은 EVENT_PROTOCOL 그대로, `task_status_changed`는 비canonical | 2단계 acceptance | `reducer.py` EVENT_TYPES에 없음, 방어적으로만 처리 | 일치 |
| `docs-only -> observer`(자동 verifier 강제 없음) | 계획 정정 기록(PROCESS.md) | `compiler.py`에 강제 automatic verifier 없음 | 일치 |
| Critical independence pool ≥2, Worker/Verifier 겸직 금지 | ADR 0002/0005 | `compile_topology`/`_validate_gate_pool`에서 실제로 최소 2명 강제 (probe 11, 12) | 일치 |
| WIP 기본값 1, active WIP는 필요할 때만 2 | ADR 0005 §10, TEAM_TOPOLOGY.md 5장 | TEAM_TOPOLOGY.md 원문에 "active WIP 기본값은 1"로 실제로 적혀 있음 | 일치(정책 문서 수준. 아래 4.2 참고) |
| Fast Mode 예산 기반 자동 라우팅 금지 | ADR 0005 §1 | `compile_risk`는 usage unknown/uncertainty>0/local_only 아님/reversible 아님/external_effect 있음 중 하나면 FAST 불가(probe 6, 9) | 일치 |
| **REVISE 자동 상한 1회, 2번째 revise는 거절** | `docs/IMPLEMENTATION_PLAN.md` 2단계 acceptance("revise 2회가 거절된다"), ADR 0005 §9("3회 상한을 1회로 낮춘다") | `compiler.py:430` `RevisionController.max_revisions: int = 3`(기본값). 실제 테스트 `test_revision_history_is_chain_and_fourth_revise_escalates`는 이름 그대로 **4번째**에서만 거절되는 것을 통과 조건으로 삼는다 | **불일치 — 2절에서 자세히** |
| 실패한 platform fixture가 자동으로 PASS가 되지 않는다 | 4단계 acceptance | `test_platform_and_failure_contract.py` 통과(probe 25로도 재확인) | 일치 |
| Windows pass + macOS deferred가 전체 성공으로 축약되지 않는다 | 4단계 acceptance | 동일 | 일치 |
| GitHub Actions에서 secret·사용자 절대경로 제거 | 8단계 acceptance | 실제 최신 artifact 다운로드해 확인(4장) | 일치 |

## 2. 핵심 발견 — REVISE 자동 상한 불일치 (승인을 막은 이유)

### 2.1 무엇이 문제인가 (쉬운 말로)

"확인하는 친구가 '다시 해와'라고 말하면 몇 번까지 자동으로 다시 해줄 수
있나?"라는 질문에 이 저장소 안에는 **서로 다른 대답 두 개**가 있다.

- `docs/decisions/0002-risk-compiled-task-graph.md` 18번째 줄: "한 논리
  작업의 REVISE 자동 루프는 **3회**로 제한하고 그 뒤에는 Human Gate다."
  (이 ADR은 지금도 `상태: accepted (canonical)`이고, 취소되지 않았다.)
- `docs/decisions/0005-mvp-simple-single-verifier.md` §9: "기존
  TEAM_TOPOLOGY.md의 **3회 상한을 1회로 낮춘다.**"
- `docs/IMPLEMENTATION_PLAN.md` 2단계(portable core) acceptance 원문:
  "... REVISE **1회**(ADR 0005), ... scheduling cycle·same-attempt
  verifier·**revise 2회가 거절된다**."

즉 실제 core 구현의 acceptance 기준으로 쓰인 문서(`IMPLEMENTATION_PLAN.md`)는
분명히 "두 번째 revise는 거절되어야 한다"(=자동으로 봐주는 건 1회뿐)고
적어 놓았다.

그런데 실제 코드는 다음과 같다.

```python
# src/graphori_core/compiler.py:428-439
@dataclass
class RevisionController:
    max_revisions: int = 3
    revise_count: int = 0
    ...
    def record(self, verdict: str, task=None, graph=None) -> RevisionAction:
        if str(verdict).lower() != "revise":
            return RevisionAction.IGNORED
        if self.revise_count >= self.max_revisions:
            ...
            return RevisionAction.ESCALATED
        ...
        return RevisionAction.REVISED
```

그리고 이 클래스를 검증하는 기존 테스트 이름 자체가 그 사실을 그대로
보여준다.

```python
# tests/test_core.py:145
def test_revision_history_is_chain_and_fourth_revise_escalates(self):
    task, graph, revisions = Task("task", "change"), Graph(), RevisionController()
    for index in range(1, 4):
        self.assertEqual(revisions.record("revise", task, graph), RevisionAction.REVISED)
    ...
    self.assertEqual(revisions.record("revise", task, graph), RevisionAction.ESCALATED)
```

`RevisionController()`는 어디서도 `max_revisions=1`을 넘겨받지 않는다
(`src/graphori_adapters`, `cli.py`, `reducer.py` 어디에도 `RevisionController`를
불러 쓰는 곳이 없다 — 이 클래스는 지금은 `tests/test_core.py`에서만
단위 테스트로 실행되는 독립 유틸리티다). 즉 지금 상태로는 revise 1회
만에 거절되는 경로가 저장소 어디에도 실행 가능한 형태로 존재하지 않는다.

### 2.2 왜 이게 "문서 오타"가 아니라 "기능 결함"인가

- `docs/IMPLEMENTATION_PLAN.md` 2단계는 명백히 **core 구현의 acceptance
  기준**이다. 그 문장이 "revise 2회가 거절된다"고 적어놓은 이상, 그 조건을
  만족하는 코드가 있어야 I02가 "완료"라고 부를 수 있다.
- `docs/decisions/0005-mvp-simple-single-verifier.md` 기술 부록(§4)은
  스스로 "이 결정은 아직 구현되지 않은 core/runtime/dashboard의 **향후
  기본 정책**"이라고 밝혀서, ADR 0005가 이후 구현될 core 코드에도
  적용되어야 함을 명시했다.
- `docs/IMPLEMENTATION_PLAN.md` 9단계(I09) acceptance 자체가 "revise 상한
  우회는 rollback trigger다"라고 명시한다. 지금 상황은 정확히 그
  시나리오(2회, 3회 revise가 자동으로 허용됨)에 해당한다.
- I02를 실제로 승인한 두 문서(`I02_CORE_HARDENING1_REPORT_LUNA.md`,
  `I02_CORE_HARDENING1_REVIEW_CLAUDE.md`)를 처음부터 끝까지 읽었지만
  "revise"라는 단어가 단 한 번도 나오지 않는다. 즉 이 acceptance 항목은
  I02의 8번에 걸친 구현·검수 과정에서 **한 번도 실제로 확인된 적이
  없다.**
- `RevisionController`는 코드에 그대로 남아 있고 export도 되어 있어서
  ("소멸된 죽은 코드"가 아니다) 언젠가 다른 곳에서 연결되면 그 순간
  실제로 3회까지 자동 rework를 허용하게 된다. "지금은 안 쓰이니 상관없다"고
  넘길 수 없는 이유다.

### 2.3 이 감사 세션에서 직접 재현한 증거

임시 스크립트로 실제 라이브러리를 그대로 불러와 재현했다(제품 파일은
건드리지 않음, 3.2절 참고).

```
FAIL   14_revise_cap_matches_ADR0005_one_automatic_revise
       expected 2nd revise to ESCALATE per ADR0005/IMPLEMENTATION_PLAN.md,
       got RevisionAction.REVISED (RevisionController.max_revisions=3)
OK     14b_actual_shipped_behavior_documented
       (실제로는 3번까지 자동 REVISED, 4번째에만 ESCALATED임을 재확인)
```

### 2.4 판정에 미치는 영향

- 이 발견은 "코드가 즉시 위험한 일을 한다"는 뜻이 아니다. `RevisionController`가
  지금 실제 실행 경로에 연결되어 있지 않기 때문에, 오늘 당장 사용자가
  이 버그로 사고를 겪지는 않는다.
- 하지만 이 감사(I09)의 목적 자체가 "약속한 안전장치가 문서와 실제로
  일치하는지"를 마지막으로 확인하는 것이고, `docs/IMPLEMENTATION_PLAN.md`가
  스스로 이 항목을 rollback trigger로 지정했으므로, 감사자가 임의로
  "괜찮다"고 넘어갈 권한은 없다고 판단했다.
- 따라서 **I09는 APPROVE가 아니라 REVISE**로 기록한다. 구체적인 결함은
  구현팀에게 전달하고, 다음 두 가지 중 하나를 Human Gate가 고르도록
  권고한다: (a) `RevisionController(max_revisions=1)`로 기본값을 낮추고
  실제 실행 경로에 연결한다, (b) ADR 0002의 "3회"를 유지하기로 다시
  결정하고 `docs/IMPLEMENTATION_PLAN.md`·ADR 0005 §9의 "1회" 문구를
  "core 구현에는 적용하지 않는다"고 명시적으로 좁혀 고친다. 어느 쪽이든
  **코드 또는 문서 중 하나를 실제로 고쳐서 두 문서가 같은 숫자를 말하게
  해야** I09를 다시 감사할 수 있다.

## 3. 컴퓨터 검사 재실행 (Windows, 이 세션에서 직접 실행)

### 3.1 필수 검사 5종

| 명령 | 결과 | 비고 |
|---|---|---|
| `python -m unittest discover -s tests -v` | **118/118 PASS** | I08 검수 때와 같은 118개, 회귀 없음 |
| `python -m compileall -q src tests` | 통과 | 문법·구문 오류 없음 |
| `python scripts/dashboard_smoke.py` | `{"status": "pass", "transport": "http", "finite": true}` | 유한 종료 확인 |
| `python graphori/scripts/validate_skill.py graphori` | `Skill is valid!` | exit 0 |
| `python scripts/generate_ci_evidence.py --platform windows --output ...` | 5개 fixture 모두 `pass` | 아래 3.3 참고 |

### 3.2 30개 이상 독립 probe (temp에서 실행, 제품 파일 미변경)

probe 스크립트는 세션 scratchpad에만 저장했고
(`i09_probes.py`), `sys.path`로 실제 `src/graphori_core`를 그대로
불러와서 실행했을 뿐 저장소의 어떤 파일도 쓰거나 지우지 않았다. 총
**40개** probe 중 **39개 OK**, **1개(위 2장 핵심 발견)** FAIL이다.

| # | probe | 결과 |
|---|---|---|
| 01 | TaskMode enum 값이 정확히 fast/standard/critical 3개 | OK |
| 02 | Risk 등급 순서(low<medium<high<critical) | OK |
| 03 | VerdictKind에 무언의 "통과 기본값"이 없음 | OK |
| 04 | 알 수 없는 event type은 reducer가 거절 | OK |
| 05 | `task_status_changed`는 canonical이 아님 | OK |
| 06 | usage unknown이면 Fast가 아니라 Standard로 강제 | OK |
| 07 | 명시적 Fast 선택도 Critical을 낮추지 못함(hard trigger 유지) | OK |
| 08 | budget 실패 시 무조건 Critical | OK |
| 09 | Fast는 known usage+local_only+reversible+무외부효과일 때만 | OK |
| 10 | verifier가 worker와 identity를 공유하면 즉시 거절 | OK |
| 11 | Critical은 독립 verifier 2명 이상 강제 | OK |
| 12 | Critical Human Gate authority pool 2명 이상 | OK |
| 13 | verifier는 자기 자신의 attempt를 검증 못함 | OK |
| 14 | **REVISE 2번째 자동 거절(ADR 0005/PLAN 기준)** | **FAIL(핵심 발견)** |
| 14b | 실제 동작(3회까지 자동, 4회째 거절)을 그대로 재확인 | OK |
| 15 | attempt는 RUNNING에서 PLANNED로 못 돌아감 | OK |
| 16 | 종료 상태(SUCCEEDED/FAILED/CANCELLED)는 후속 전이 없음 | OK |
| 17 | ProcessSupervisor가 문자열 shell 명령을 거절(list만 허용) | OK |
| 18 | env allowlist에 있어도 SECRET/API_KEY류 이름이면 제거 | OK |
| 19 | 실행 중 node가 있으면 `run_terminal(succeeded)` 거절 | OK |
| 20 | 모든 execution node가 passed면 succeeded 수락 | OK |
| 21 | 종료된 Run에는 어떤 후속 event도 거절 | OK |
| 22 | worker actor는 verdict를 위조 못함 | OK |
| 23 | verifier actor는 approve를 발행 못함(human_gate 전용) | OK |
| 24 | verdict는 evidence_ids가 비어있으면 거절 | OK |
| 25 | Windows pass + macOS deferred가 전체 성공으로 축약되지 않음 | OK |
| 26 | 드라이브 상대경로(`C:evil.txt`) 탈출 거절 | OK |
| 27 | `..` 상위 폴더 탈출 거절 | OK |
| 28 | UNC(`\\host\share`) 경로 거절 | OK |
| 29 | `graphori_core`에 `graphori_adapters` import 0건(AST 정적 검사) | OK |
| 30 | Orca adapter가 알 수 없는 event kind를 성공으로 꾸미지 않고 quarantine | OK |
| 31 | Orca adapter가 `sqlite3`/`orchestration.db`/외부 SDK를 import하지 않음 | OK |
| 32 | `rework_of` 2노드 순환 거절 | OK |
| 33 | 스케줄링 self-loop 거절 | OK |
| 34 | worker 연결 없는 verifier 노드 거절 | OK |
| 35 | 대시보드 progress는 heartbeat만으로 오르지 않음 | OK |
| 36 | 대시보드 progress는 verifier pass + node passed에서만 100% | OK |
| 37 | heartbeat 나이가 임계값을 넘으면 stale로 표시 | OK |
| 38 | CI workflow에 Windows/macOS job, `permissions: contents: read`가 실제로 있음 | OK |
| 39 | evidence 생성 스크립트가 runner 고유 python 경로를 매니페스트에서 제외 | OK |

### 3.3 일부러 이상한 입력(seed) — 검증기가 실제로 거부하는지

제품 파일은 그대로 두고, `graphori/`를 temp 폴더로 복사해서 일부러
망가뜨린 뒤 `graphori/scripts/validate_skill.py`로 검사했다.

| seed | 조작 내용 | 결과 |
|---|---|---|
| seed-1 | `SKILL.md` frontmatter `name: graphori` → `name: WRONG` | `Skill is invalid: frontmatter name must be graphori` (exit 1) |
| seed-2 | `SKILL.md`에 UTF-8 BOM(`EF BB BF`) 추가 | `Skill is invalid: UTF-8 BOM is not allowed` (exit 1) |
| seed-3 | `agents/openai.yaml`의 `default_prompt`에서 `$graphori` 자리표시자 제거 | `Skill is invalid: default_prompt must contain $graphori` (exit 1) |

세 가지 모두 검증기가 정확한 이유로 정확히 거부했다(성공한 척하지 않음).
위 probe 04·19·21·22·23·24·26~28·30·32~34도 같은 성격의 "일부러 나쁜
입력" 테스트이며 전부 올바르게 거절되었다.

## 4. 실제 GitHub Actions 확인 (`gh` CLI + GitHub API 직접 조회)

- `gh run list`로 PR #1 head SHA `317d32a...`의 실행 두 건을 직접 조회:
  - push: run `31325121336` → **success**
  - pull_request: run `31325123531` → **success**
  - 두 run 모두 Job `Windows Python 3.11`, `Windows Python 3.12`,
    `macOS contract fixtures`가 각각 **completed / success**임을
    `pull_request_read(get_check_runs)`로 재확인했다.
- `gh run download 31325123531`로 artifact 4개(Windows 3.11/3.12,
  macOS)를 실제로 내려받아 직접 열어봤다.
  - macOS/Windows evidence JSON 모두 `verdict: pass` 5건씩, `scope:
    runner_actual`.
  - `grep -riE "<personal-path-pattern>|<credential-pattern>"`를
    다운로드한 artifact 폴더 전체에 돌렸고 **0건**이었다.
  - 다만 `Get-FileHash` 결과를 그대로 저장한 `digest-3.12.json`에는
    `"Path":"D:\\a\\graphori\\graphori\\build\\ci-artifacts\\..."`가
    들어있다. 이는 GitHub 호스팅 Windows runner 자체의 표준 임시
    작업 경로(`D:\a\<owner>\<repo>\...`)이며 실제 개발자의 로�날 사용자
    이름·홈 경로가 아니다. 개인정보 유출은 아니지만, "sanitized
    evidence"를 자처하는 산출물 옆에 runner 경로가 그대로 찍혀 나오는
    것은 사소한 문서/구현 정확성 노트로 남긴다(차단 사유 아님).
- macOS 결과는 이번 감사에서도 **실제 `macos-latest` GitHub 호스팅
  runner에서 나온 `runner_actual` 범위**로만 인정했다. 로컬에는 macOS
  실행 환경이 없으므로 macOS "제품 전체 보장"으로 확대하지 않는다.

## 5. 사용자 관점 — "내일 Windows에서 무엇을 실제로 할 수 있나"

이 세션에서 실제로 한 번 끝까지 실행해 직접 확인했다(각본이 아니라 진짜
subprocess와 진짜 파일 I/O).

```powershell
$env:PYTHONPATH = "src"
python -m graphori_core.cli --root <workspace> --run-id demo1 run -- python -c "print('hello graphori')"
python -m graphori_core.cli --root <workspace> --run-id demo1 status
python -m graphori_core.cli --root <workspace> --run-id demo1 replay --verify
```

- `run`은 실제 `python -c "print(...)"` 프로세스를 실제로 실행했고,
  종료 코드 0을 확인한 뒤 `.graphori/runs/demo1/journal/journal.jsonl`에
  이벤트 10개(run_created ~ run_terminal)를 실제로 기록했다.
- 자식 프로세스에 넘어간 환경변수를 확인해보니 `OPENAI_API_KEY`,
  `GEMINI_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `ORCA_*` 토큰류가
  전부 `dropped_env_keys`에 실제로 걸러졌다(허용 목록 밖 + 비밀 이름
  이중 차단이 실제 환경에서도 동작함을 확인).
- 별도 프로세스로 `status`/`replay --verify`를 실행해도 같은
  journal만 읽어서 같은 결과(`terminal_status: succeeded`,
  `projection_digest` 동일)를 재현했다 — "메모리에 있던 값"이 아니라
  "저장된 사실"임을 실제로 확인했다.
- 같은 workspace를 대시보드 서버(`scripts/dashboard_server.py --root
  .`)로 열면 `worker` 노드가 `status: passed`로 뜬다. 다만 **진행률
  (progress)은 0%로 남는다** — CLI의 `run`은 verifier를 부르지 않기
  때문이다. 이는 버그가 아니라 ADR 0003의 "verifier/gate 완료 사건만
  진행률로 센다"는 설계를 그대로 지킨 정직한 동작이지만, 사용자가
  "worker가 끝났는데 왜 0%지?"라고 오해할 수 있는 지점이라 명확히
  적어둔다.

**정리**: 내일 사용자가 Windows에서 할 수 있는 일은 (1) Orca 없이도
`graphori-cli`로 실제 명령을 하나 실행하고 journal로 기록·재생하는 것,
(2) 로컬 대시보드를 띄워 실시간으로(SSE) 그 상태를 보는 것, (3) `orca`
CLI가 설치돼 있으면 `graphori_adapters.orca`로 읽기 전용 상태를
가져오는 것이다. **할 수 없는 일**은: 자동으로 여러 worker/verifier를
오케스트레이션해 주는 것(그런 자동화 계층은 아직 없음 — 지금 있는
CLI는 "한 worker, 한 attempt"만 다룬다), macOS에서 직접 실행해 보는
것(로컬 macOS 환경 없음, CI에서만 확인됨), 그리고 REVISE 자동 상한이
문서대로(1회) 지켜지는 것(2장 참고, 애초에 이 경로가 어디서도 호출되지
않는다).

## 6. 보안 점검

- **절대경로/사용자명 누출**: 실제 배포·전달 대상(CI evidence
  manifest, 다운로드한 artifact, 대시보드 HTTP 응답, CLI 표준출력)에는
  `<home>`류 경로나 사용자명이 없었다(4장, probe 39). 내부
  개발 기록용 `docs/verification/*.md`에는 로컬 재현 경로가 남아있는데,
  이는 "이 컴퓨터에서 이렇게 확인했다"는 감사 로그 성격이라 보안
  유출로 분류하지 않았다.
- **secret 누출**: `TOKEN`/`SECRET`/`PASSWORD`/`API_KEY`/`ghp_`/`gho_`류
  문자열을 산출물·저장소 추적 파일에서 검색해 0건 확인. 실제
  `OPENAI_API_KEY` 등 진짜 환경변수를 자식 프로세스에 넘기는 실험에서도
  이름 기반으로 실제로 걸러짐(5장).
- **외부 SDK/API 의존**: `src/graphori_core`, `src/graphori_adapters`
  전체가 표준 라이브러리(`subprocess`, `json`, `http.server`,
  `dataclasses`, `hashlib`, `uuid`, `datetime`, `ctypes`(Windows Job
  Object 전용))만 사용한다. `openai`, `anthropic`, `requests`, `httpx`
  같은 외부 패키지 import가 코드 전체에 0건이다(probe 31).
- **Orca 내부 DB 의존**: `graphori_adapters/orca/adapter.py`는
  `orca status --json` 등 **공개 CLI를 subprocess로만** 호출하고,
  `orchestration.db`(SQLite)나 Orca의 내부 파일을 직접 열지 않는다
  (probe 31). Orca CLI가 없거나 응답이 이상해도
  `event_quarantined`로 처리할 뿐 core corruption을 만들지 않는다
  (probe 30).

## 7. 최종 판정

> **VERDICT: REVISE (APPROVE 아님)**

- 118개 unittest, compileall, dashboard smoke, skill validator, CI
  evidence, GitHub Actions 실제 성공, 40개 중 39개 독립 probe, 3개
  seed-defect 거부 테스트는 모두 통과했다.
- 그러나 2장에서 재현한 **REVISE 자동 상한 불일치**
  (`RevisionController.max_revisions=3` vs `docs/IMPLEMENTATION_PLAN.md`
  2단계 acceptance의 "revise 2회가 거절된다")는 코드 결함이며, 이
  항목은 I09 자신의 acceptance가 명시한 rollback trigger("revise 상한
  우회")에 해당한다고 판단했다. 그래서 최종 승인 도장을 찍지 않는다.
- 이번 세션에서 코드는 전혀 고치지 않았다(지시대로). 사소한 문서
  기록만 이 파일과 `docs/PROCESS.md`에 추가한다.

### 진행률

승인된 구현 단계 기준 진행률은 **8/9 = 88.9%로 유지**한다(I09는
REVISE이므로 9/9로 올리지 않는다).

### 남은 일

1. `RevisionController`의 revise 자동 상한을 ADR 0002(3회)와 ADR
   0005/`IMPLEMENTATION_PLAN.md`(1회) 중 어느 쪽으로 확정할지 Human
   Gate가 결정한다.
2. 결정된 숫자에 맞춰 코드(`max_revisions` 기본값과 실제 연결 경로)
   또는 문서(ADR 0005 §9, `IMPLEMENTATION_PLAN.md` 2단계 문구) 중
   실제로 틀린 쪽을 고친다.
3. 고친 뒤 fresh 독립 검수(가능하면 이번 감사자와 다른 모델)를 한 번
   더 받는다.
4. 그 검수가 REVISE 사유 없이 끝나면 I09를 다시 감사해 9/9 승인 여부를
   판단한다.
5. (차단 사유는 아니지만) `README.md`가 안내하는 `quick_validate.py`
   절대경로가 이 개발자의 로컬 설치 경로에 고정돼 있어 다른 사용자
   환경에서는 그대로 복사해 쓸 수 없다는 점을 문서 정확성 관점에서
   남겨둔다.

## 8. 부록 — 실행한 전체 명령 목록

```
python --version
python -m unittest discover -s tests -v
python -m compileall -q src tests
python graphori/scripts/validate_skill.py graphori
python scripts/dashboard_smoke.py
python scripts/generate_ci_evidence.py --platform windows --output <temp>/ci-evidence-windows-local.json
gh run list --repo dotoricode/graphori --limit 6 --json ...
gh run download 31325123531 --repo dotoricode/graphori --dir <temp>/artifacts
grep -riE "<personal-path-pattern>|<credential-pattern>" <temp>/artifacts
python <temp>/i09_probes.py   # 40개 독립 probe, temp에서만 실행
python -m graphori_core.cli --root <temp e2e> --run-id demo1 run -- python -c "print('hello graphori')"
python -m graphori_core.cli --root <temp e2e> --run-id demo1 status
python -m graphori_core.cli --root <temp e2e> --run-id demo1 replay --verify
# temp 안에서만: graphori/SKILL.md name 변조, BOM 삽입, $graphori 제거 후 validate_skill.py 재실행
```

모든 임시 파일은 `<home>\AppData\Local\Temp\claude\i09audit\`와
세션 scratchpad 아래에서만 만들었고, 저장소 안의 어떤 제품 파일도
수정하지 않았다.
