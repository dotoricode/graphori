# I02 portable core revision-3 최종 독립 검수 (Claude)

검수일: 2026-08-09 (Asia/Seoul)
검수자: Claude — 독립 검증자. `src/graphori_core/*`, `tests/test_core.py`, `pyproject.toml`,
`.gitignore`를 **수정하지 않았다.** 이 보고서 파일 하나만 새로 썼다.
검수 대상: `docs/verification/I02_CORE_FIX3_REPORT_LUNA.md`(revision-3 수정 주장)와
그 근거가 된 코드 `src/graphori_core/{models,compiler,reducer,__init__}.py`,
`tests/test_core.py`(19개).
기준 문서: `docs/architecture/GRAPHORI_ARCHITECTURE.md`,
`docs/architecture/EVENT_PROTOCOL.md`, `docs/IMPLEMENTATION_PLAN.md`.
비교 대상(이전 라운드 전부): `I02_CORE_REVIEW_CLAUDE/CODEX.md`,
`I02_CORE_REREVIEW_CLAUDE/CODEX.md`, `I02_CORE_FINAL_REVIEW_CLAUDE/CODEX.md`,
`I02_CORE_FIX_REPORT_LUNA.md`, `I02_CORE_FIX2_REPORT_LUNA.md`.
실행 환경: Windows, Python 3.12.1. macOS: **실행하지 않음. `deferred/unknown`.**

## 0. 12살에게 설명

지난 라운드(revision-2)에서 검수자 두 명이 "영수증 도장(digest)이 비어 있어도
통과한다"와 "다시 하기 기록이 두 칸짜리로 빙글빙글 돈다"는 두 가지 틈을 찾았다.
이번 revision-3은 그 두 틈과, 제가 이번에 다시 두드려 본 "이름표 준 사람이 진짜
확인 도장(role_id)을 찍었는지"까지 전부 잘 막았다. 그런데 새로 아주 세게 두드려
보니 다른 틈 하나가 나왔다. "이 실행 카드는 어느 경주(Run)에 속해요"라는 이름표를
카드에 미리 붙여 놓으면(테스트 파일이 실제로 항상 이렇게 한다), "경주 시작!"이라는
영수증(`run_created`) 없이 바로 "그래프 공개!"(`graph_published`)와 "경주 끝!"
(`run_terminal`, 성공)까지 찍을 수 있다. 시작 영수증을 아예 안 받고도 경주가
끝났다고 기록되는 것이다. 이건 이번 검수 항목 4번("run_created→graph_published→
run_terminal projection")이 정확히 겨냥한 지점이라서 REVISE로 판정한다.

## 1. 실행 결과 요약 (직접 실행)

```text
$ python --version
Python 3.12.1

$ python -m unittest discover -s tests -v
Ran 19 tests in 0.003s
OK

$ python -m compileall -q src tests
(종료 코드 0)

$ git diff --check
(종료 코드 0, 변경 없음 — 이번 검수는 보고서 파일만 새로 만듦)

$ python -m pip install . --no-deps --target <임시폴더> -q
$ PYTHONPATH=<임시폴더> python -c "import graphori_core"
import OK: <임시폴더>\graphori_core\__init__.py

$ AST로 src/graphori_core/*.py import 전수 조사
compiler.py: __future__, dataclasses, enum, typing (+ .models)
models.py:   __future__, dataclasses, enum, typing
reducer.py:  __future__, dataclasses, re, typing (+ .models, .compiler)
__init__.py: (없음, sibling만)
```

19개 테스트 전부 통과, `compileall`/`git diff --check`/`pip install --target` +
`import` 전부 성공. stdlib 이외 import 0건, `orca` import 0건 (core 경계 유지).
macOS는 이 Windows 작업 환경에서 실행할 수 없으므로 `deferred/unknown`으로 유지한다.

**주의**: "19개 테스트가 통과했다"는 것 자체를 판정 근거로 삼지 않았다. 아래 §2, §3은
테스트가 아니라 이번 검수에서 직접 실행한 `python -c` 반례다. §4가 이번에 새로
찾은 문제다.

## 2. 이전 라운드 P0/P1을 실제 반례로 재확인 — 전부 CLOSED

아래는 REVIEW/REREVIEW/FINAL_REVIEW(Claude/Codex) 전 라운드에서 나온 모든 `[P0]`,
`[P1]` 항목을 이번에 직접 다시 공격한 결과다. 표시가 CLOSED인 것은 이번 검수에서
직접 실행한 명령이 예외를 던졌다는 뜻이다.

| 원 finding (출처) | 이번 재공격 | 결과 |
|---|---|---|
| Node 상태 역방향/부활 (REVIEW_CODEX P0-2, REREVIEW §2.1, FINAL §2.1) | `passed`/`failed`/`cancelled`/`inconclusive` 4개 종단 상태 각각에서 `ready`/`running`/`assigned`/`pending`으로 16가지 시도 | **CLOSED** — 16가지 전부 `StateTransitionError` |
| `REJECTED`가 `NODE_TRANSITIONS`에서 도달 불가 (FINAL §4 관찰) | `awaiting_verification -> rejected` 시도 | 여전히 도달 불가 확인(과잉차단, 취약점 아님. §5에 잔존 관찰로 유지) |
| 증거 없는 verdict pass (REVIEW_CODEX P0-1, REREVIEW §2.2, FINAL §2.2) | `evidence_ids`에 `None,[],"ev",[""],[None],["  "],[123]` 7가지 주입 | **CLOSED** — 7가지 전부 `StateTransitionError` |
| verdict 발행 권한 위조 (worker/router/observer가 verdict, verifier가 approve, human_gate가 pass, `payload.actor_role` 위조) | 6가지 actor/verdict 조합 + payload 위조 1건 | **CLOSED** — 7가지 전부 `StateTransitionError` |
| identity-only 독립성 우회 (REVIEW_CODEX P0-3, REREVIEW §2.3, FINAL §2.3) | `verify_attempt`에 identity만 같고 provider/model/checkout/session/worktree 전부 다른 경우 + provider만/model만/checkout만/session만/worktree만 공유 5가지(문서 규칙상 checkout/session/worktree 단독 공유는 차단돼야 하고 provider/model 단독 공유는 "최소 한 차원 이상 다름" 조건을 충족해 허용이 맞음) | **CLOSED** — identity 공유 및 checkout/session/worktree 단독 공유는 차단. provider/model 단독 공유는 설계대로 허용(우회 아님, `GRAPHORI_ARCHITECTURE.md` §4 "attempt/provider/model/checkout 중 최소 한 차원 이상 달라야 한다"와 일치) |
| Critical 두 verifier provider+model 공유 | `compile_topology(risk=CRITICAL, verifier_roles=(같은 provider+model 두 개))` | **CLOSED** — `IndependenceError` |
| Human Gate pool 독립성(checkout 공유, pool 크기 1) | 2가지 시도 | **CLOSED** — 둘 다 `IndependenceError` |
| `rework_of` self-loop (REREVIEW §2.4, FINAL §2.4) | `A rework_of A` | **CLOSED** — `GraphValidationError: self-loop` |
| `rework_of` 길이 2/3/4 순환 (FINAL §2-B, 새로 발견돼 열려 있던 것) | `A->B->A`, `A->B->C->A`, `A->B->C->D->A` | **CLOSED** — 3가지 전부 `GraphValidationError: rework_of history contains a cycle` |
| revision 원본 노드 누락 시 무원자적 생략 (FINAL §2-C 관찰) | 원본 노드 없는 그래프에 `RevisionController.record("revise", ...)` 호출, 호출 전/후 task·controller·graph 상태 비교 | **CLOSED** — `GraphValidationError`를 던지고 task/controller/graph 상태가 호출 전과 정확히 동일함을 확인(원자성) |
| `digest`/`prev_digest`가 `None`/`"bad"`/짧은 hex/대문자 접두사/긴 hex여도 통과 (FINAL §2-A, REREVIEW_CODEX O1) | 두 필드에 9가지 값(`None,"","bad",123,63-hex,64-hex-invalid-char,SHA256:,65-hex,접두사콜론없음`) | **CLOSED** — 18가지 전부 `StateTransitionError: ... must match sha256:<64 hex characters>` |
| `actor.role_id` 누락/빈값/공백/`None` (REREVIEW_CODEX O2) | actor 4가지 변형 | **CLOSED** — 4가지 전부 `StateTransitionError` |
| genesis `seq=0 + prev_digest=None` 허용 여부 (FIX3 보고서가 "허용 안 함"이라고 주장) | `seq=0, prev_digest=None` | **CLOSED** — canonical 문서가 genesis sentinel을 정의하지 않으므로 그대로 digest 형식 검사에 걸려 거부됨. 문서 정합적 |
| platform pass에 `evidence_id`/`fixture_id`·`snapshot_id` 누락 | 2가지 | **CLOSED** — 둘 다 `StateTransitionError` |

**결론: 지금까지 모든 라운드에서 제기된 P0/P1은 이번 재공격에서 예외 없이 전부
CLOSED로 재확인됐다.** 새 변형(길이 2+ cycle, digest None, role_id 누락)도
revision-3에서 실제로 막혔다.

## 3. 이번 검수 항목별 확인 (요청 순서대로)

### 3.1 rework_of 1/2/3+ cycle, source/target, missing-original 원자성

§2 표에 포함. 추가로 방향(`source`가 새 revision, `target`이 옛 node)을
`test_revision_history_is_chain_and_fourth_revise_escalates`와 동일한 논리로
직접 재구성해 `revision-1 -> task`, `revision-2 -> revision-1`,
`revision-3 -> revision-2` 순서를 재확인했다. `compile_topology`가 만드는
worker node id(`"worker"`)와 `RevisionController`가 기대하는 원본 id
(`task.task_id`)가 서로 다르다는 점(FINAL §2-C 관찰)도 이번엔 두 컴포넌트를
같은 graph에 실제로 합쳐 실행했다. 결과: 원본이 없으므로 `GraphValidationError`로
fail-closed 됐다 — 이전 라운드가 우려했던 "조용한 생략"은 이제 발생하지 않는다.

### 3.2 actor.role_id/producer_event_id 필수, digest/prev_digest sha256:64hex, genesis fail-closed

§2 표에 포함. `producer_event_id`는 EVENT_PROTOCOL이 `producer:<id>:<local-seq>`
형태의 자유 문자열로 정의하고 sha256 형식을 요구하지 않으므로, "non-empty string"
검사만 하는 현재 구현이 계약과 일치한다(sha256 형식 강제는 과잉 요구라 시도하지
않았다). `digest`/`prev_digest`만 sha256:64hex 정규식(`_DIGEST_PATTERN`)으로
강제되고, 이번 검수에서 9가지 악성값씩 총 18개 조합이 전부 거부됨을 확인했다.

### 3.3 run_created→graph_published→run_terminal projection, ID/version/order/terminal immutability — **REVISE 사유 발견**

ID 일치, graph_version 역행 금지, terminal 역전 금지는 CLOSED (§2, 아래 재확인).
그러나 **순서(run_created가 먼저 와야 한다는 요구)는 흔한 구성 방식에서 지켜지지
않는다.**

#### Finding [P1] `graph_published`가 `run_created` 없이도 통과하고, 그대로 `run_terminal`까지 성공한다

- 위치: `src/graphori_core/reducer.py:133-144`(`__post_init__`), `:187-190`
  (`graph_published`의 순서 검사).
- 문제: `graph_published` 핸들러의 순서 검사는 `if run is None: raise
  "graph_published requires run_created"` 딱 한 줄이다(189-190줄). 그런데
  `__post_init__`(133-144줄)은 `Task.run_id`가 이미 채워져 있거나 `Run` 객체가
  생성자에 직접 전달되면, **어떤 이벤트도 적용하기 전에** `self.run`을 미리
  만들어 둔다. 그 결과 `run is None` 조건이 처음부터 거짓이 되어, `run_created`
  이벤트를 한 번도 적용하지 않고 바로 `graph_published`를 보내도 "run_created가
  먼저 와야 한다"는 검사를 통과한다. `run_terminal`은 `_graph_was_published`
  플래그(이벤트가 실제로 적용됐는지 추적하는 진짜 상태)로 지키는데, `graph_published`의
  순서 검사만 "Run 객체가 존재하는가"라는 잘못된 대리 지표를 쓴다.
  이 구성 방식은 가정이 아니다 — `tests/test_core.py`의 기존 Run 관련 테스트
  4개(`test_run_graph_and_terminal_projection_is_ordered_and_fail_closed`,
  `test_run_projection_rejects_reverse_event_order_and_version_mismatch` 포함)
  전부가 `Task(..., run_id="run-1", graph_version=1)`처럼 `run_id`를 미리 채우거나
  `StateReducer(task, Run("run-1", 1))`처럼 `Run`을 직접 넘기는 방식으로 reducer를
  만든다. `.graphori/runs/<run_id>/...` 디렉터리 구조(`EVENT_PROTOCOL.md` §7)로
  볼 때 실제 writer/replay 코드도 어느 run을 다루는지 미리 알고 시작할 가능성이
  높으므로, 이 구성 방식은 예외적 케이스가 아니라 자연스러운 사용법이다.
- 계약 위반: `EVENT_PROTOCOL.md` 부록 A와 §4.3이 `run_created`를 첫 필수 사건으로
  전제하고, `GRAPHORI_ARCHITECTURE.md` §2-7 "오케스트레이터는... 저장소를 직접
  구현하거나 테스트하지 않는다"와 별개로 core 자신이 스스로 "Run 투영은 순서를
  지킨다"고 약속한 부분이다. 이번 검수 항목 4번이 정확히 이 순서를 확인하라고
  요청했다.
- 재현 명령 (읽기 전용, 구현/테스트 파일 미수정):

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from graphori_core import Task, StateReducer, canonical_event

t = Task('t2', 'x', run_id='run-y', graph_version=1)
r = StateReducer(t)
r.apply(canonical_event('graph_published', run_id='run-y', task_id='t2',
        actor_role='router', seq=1, graph_version=1))
r.apply(canonical_event('run_terminal', run_id='run-y', task_id='t2',
        actor_role='router', seq=2, graph_version=1,
        payload={'terminal_status': 'succeeded'}))
print('run.terminal_status =', r.run.terminal_status)
print('run_created applied? NO. terminal reached anyway.')
"
```

- 실제 결과:

```text
run.terminal_status = succeeded
run_created applied? NO. terminal reached anyway.
```

  예외 없이, `run_created`를 단 한 번도 적용하지 않고 `graph_published`와
  `run_terminal(succeeded)`가 둘 다 성공해서 Run이 정상적으로 "끝났다"고
  기록된다.
- 기대 결과: `graph_published`가 이 순서를 지키려면 "Run 객체 존재 여부"가 아니라
  "이 reducer 인스턴스가 실제로 `run_created` 이벤트를 적용했는가"를 별도 플래그
  (`run_terminal`이 이미 쓰는 `_graph_was_published`와 같은 방식)로 추적해서
  검사해야 한다. `Task`/`Run`을 미리 구성했다고 해서 genesis 사건 자체가
  면제되어서는 안 된다.
- 영향 범위: 이 틈으로 verdict를 위조하거나 독립성을 우회할 수는 없다(§2의
  다른 방어선은 그대로 살아 있다). 다만 "Run이 언제, 누구에 의해 시작됐는가"라는
  감사 기록(genesis event)이 통째로 비어 있어도 그래프 공개와 종료까지 정상
  진행된 것처럼 투영되므로, Run lifecycle 투영의 완전성이라는 이번 검수 항목
  4번의 핵심을 정면으로 벗어난다. `verdict_recorded`/`platform_verdict_recorded`
  같은 권한·증거 계층 위조보다는 좁지만, "run_created→graph_published→
  run_terminal 순서"라는 명시적 요청 항목이므로 P1로 분류하고 REVISE 사유로
  포함한다.
- Windows: 재현됨(FAIL). macOS: `deferred/unknown`(플랫폼 무관 로직으로 보이나
  확인 전이므로 단정하지 않음).

#### 그 외 §3.3 항목 — CLOSED

```text
graph_version 역행(3 -> 2)                         blocked
run_id/entity 불일치 (event.run_id vs Task.run_id)  blocked
entity.task_id 불일치                               blocked
terminal 이후 재-run_created(재오픈) 시도            blocked
terminal 이후 graph_published 시도                  blocked
terminal_status를 다른 값으로 뒤집기 시도            blocked
run_terminal이 graph_published보다 먼저 오는 경우    blocked (_graph_was_published 플래그가 정상 작동)
```

`run_terminal`의 순서 보호는 실제 이벤트 적용 여부를 추적하는 별도 플래그를 쓰기
때문에 이번 틈의 영향을 받지 않는다. `run_created` 쪽만 고쳐야 한다.

### 3.4 19개 테스트 수를 신뢰하지 않고 누락 반례 직접 실행

§2, §3.3의 표는 전부 `tests/test_core.py`를 실행하지 않고 별도 `python -c`
스크립트로 직접 만든 반례다(스크립트는
`<temp>/claude/.../scratchpad/probe1.py`,
`probe2.py`에 보존, 구현/테스트 디렉터리 밖). 구현·테스트 파일은 수정하지
않았다. §3.3의 새 finding은 기존 19개 테스트 중 어느 것도 잡지 못한다 —
`test_run_projection_rejects_reverse_event_order_and_version_mismatch`라는
이름은 "역순을 거부한다"고 말하지만 실제로는 `run_terminal`이 먼저 오는 경우와
`run_created`의 entity/version 불일치만 검사하고, "`run_created` 자체를 건너뛰고
`graph_published`로 시작하는 경우"는 검사하지 않는다.

### 3.5 Windows unittest/compileall/install/import, git diff --check. macOS deferred/unknown

§1 참고. 전부 통과했고 이번 검수로 만든 코드 변경은 없다(`git diff --check`
종료 코드 0). macOS는 이 Windows 환경에서 실행할 수 없으므로 계속
`deferred/unknown`이다.

### 3.6 Stage3 실제 hash chain/journal 범위와 I02 계약의 분리

`reducer.py:86-88`의 주석 "EVENT_PROTOCOL presents both values as canonical
sha256 digests. It does not define a null genesis sentinel, so seq=0 still
requires the same digest shape; Stage 3 owns computing the actual chain."이
정확히 이 경계를 명시한다. 이번 코드는 `digest`/`prev_digest`가 "sha256:64hex
형식인가"만 검사하고, 실제로 이전 사건 payload로부터 hash를 재계산해서 체인이
맞는지는 검사하지 않는다 — 이는 `IMPLEMENTATION_PLAN.md` 3단계(single writer,
sequence/digest 계산, idempotency, crash-tail 격리)의 몫이며 I02(2단계, portable
core) 범위가 아니다. 이번 검수는 이 경계를 존중해서 "형식 검사"만 I02 계약
위반 여부로 판단했고, "실제 hash chain 무결성"은 결함으로 세지 않았다.

## 4. 잔존 위험 (I02 REVISE의 근거가 아닌 후속/관찰 항목)

- `NodeState.REJECTED`가 `NODE_TRANSITIONS`의 어떤 target으로도 등장하지 않아
  `transition_node`로는 절대 도달할 수 없다(과잉차단, FINAL §4에서 이미 관찰).
- `StateReducer.apply()`는 envelope 통과 후 `run_created`/`graph_published`/
  `run_terminal`/`node_status_changed`/`verdict_recorded`/`platform_verdict_recorded`
  6종 외의 13개 canonical 타입(`node_created`, `edge_created`, `role_assigned`,
  `heartbeat`, `usage_recorded` 등)에 대해 아무 프로젝션도 만들지 않고 `self`만
  반환한다. 에러는 아니며 REVISE 사유가 아니지만, "지원 선언한 타입마다 payload
  의미를 검증해야 한다"는 이전 재검수 권고는 아직 완료되지 않았다.
- Stage3 실제 writer(single writer, monotonic seq 계산, idempotency, crash-tail
  quarantine)는 여전히 미구현이며 I02 범위 밖이다.
- 실제 Windows process/path/symlink adapter, macOS adapter, dashboard, Orca
  adapter는 `IMPLEMENTATION_PLAN.md` 5~9단계이며 이번 2단계 core 구현에는
  포함되지 않는다. 없는 것 자체는 REVISE 사유가 아니다.
- macOS 실행: 여전히 `deferred/unknown`. 이번 검수도 Windows에서만 실행했다.

## 5. 최종 판정

**REVISE.**

이전 모든 라운드(REVIEW/REREVIEW/FINAL_REVIEW Claude+Codex)에서 제기된 P0/P1은
이번 독립 재공격에서 예외 없이 전부 CLOSED로 재확인됐다: Node 상태 역전/부활,
증거 없는 verdict, verdict 권한 위조, identity-only 독립성 우회, Critical/Human
Gate 독립성 우회, `rework_of` self-loop와 길이 2 이상 순환, revision 원자성,
`digest`/`prev_digest` 형식, `actor.role_id`, genesis sentinel 처리까지 모두
막혔다.

그러나 이번 검수 항목이 명시적으로 요구한 "run_created→graph_published→
run_terminal projection ... order" 확인 과정에서 새 결함을 찾았다(§3.3): `Task`
또는 `Run`이 `run_id`/`graph_version`을 미리 가진 채로 `StateReducer`가 만들어지면
(기존 테스트 4개가 실제로 이렇게 구성한다), `run_created` 이벤트 없이
`graph_published`와 `run_terminal(succeeded)`이 그대로 통과해서 Run이 시작
기록 없이 "성공적으로 끝났다"고 투영된다. 이는 Run lifecycle 순서 보증이
Task/Run 생성 방식에 따라 실제로는 지켜지지 않을 수 있다는 뜻이며, 검수 항목
4번의 핵심을 벗어나는 P1이므로 REVISE로 판정한다. 수정 범위는 좁다 —
`graph_published` 핸들러의 순서 검사를 `run is None`이 아니라 `run_created`
이벤트가 실제로 적용됐는지를 추적하는 전용 플래그(`run_terminal`이 이미 쓰는
`_graph_was_published`와 같은 방식)로 바꾸고, 회귀 테스트로 "run_id/Run을
미리 구성한 뒤 `run_created` 없이 `graph_published`를 보내면 거부된다"를
추가하면 닫을 수 있다. 그 외 항목은 모두 통과했다.

VERDICT: REVISE
