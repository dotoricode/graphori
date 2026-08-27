# I02 portable core 재검수 보고서 (Claude, 적대적 재검수)

## 최종 판정: **REVISE**

> 12살에게 설명: 이번에 나온 규칙 공책(코드)은 지난번 지적을 많이 고쳤어요. 그런데
> 제가 "일부러 나쁜 짓"을 해보니 아직 문이 3곳이나 활짝 열려 있었어요. (1) 카드
> 상태를 아무 순서로나 바꿀 수 있고, (2) "증거 없이 통과!"라고 써도 막지 않고,
> (3) 검사하는 사람 이름만 살짝 바꾸면 사실 같은 사람인데도 "다른 사람"이라고
> 속일 수 있었어요. 그래서 아직 APPROVE라고 도장을 찍을 수 없습니다.

- 검수자: Claude (독립, 구현/테스트 파일 미수정, 읽기 전용 one-liner만 실행)
- 검수 대상: `src/graphori_core/*`, `tests/test_core.py`, `pyproject.toml`, `.gitignore`
- 기준 문서: `docs/architecture/GRAPHORI_ARCHITECTURE.md`, `docs/architecture/EVENT_PROTOCOL.md`,
  `docs/architecture/PORTABILITY_CONTRACT.md`, `docs/IMPLEMENTATION_PLAN.md`, `TEAM_TOPOLOGY.md`,
  `docs/decisions/0001~0004`
- 비교 대상: `docs/verification/I02_CORE_REVIEW_CODEX.md`, `docs/verification/I02_CORE_REVIEW_CLAUDE.md`,
  `docs/verification/I02_CORE_FIX_REPORT_LUNA.md`
- 실행 환경: Windows(PowerShell/Git Bash), Python 3.12.1 (`requires-python >=3.11` 충족)
- macOS: **실행하지 않음.** 모든 macOS 판정은 `deferred/unknown`이다.
- PROCESS.md 및 다른 문서는 수정하지 않았다. 구현/테스트 파일도 수정하지 않았다.

## 0. 실행 결과 요약

```text
$ python --version
Python 3.12.1
$ python -m unittest discover -s tests -v
Ran 12 tests in 0.005s
OK
$ python -m compileall -q src tests
(종료 코드 0)
```

Luna 수정 보고서와 동일하게 12개 테스트가 모두 통과하고 `compileall`도 성공한다.
하지만 아래 §2에서 보이듯, **테스트가 통과하는 것과 계약이 실제로 지켜지는 것은
다른 이야기**다. 새로 시도한 공격 입력 다수가 테스트되지 않은 경로를 그대로
통과했다.

## 1. 최초 P0/P1/P2 재현 판정 (Codex + Claude)

| 원 검수 | 항목 | 위치 | 이번 재현 결과 |
|---|---|---|---|
| Codex P1-01 | usage unknown → 무조건 Critical | compiler.py | **CLOSED** — `RiskInput(usage_status="unknown")` → `standard` 확인 |
| Codex P1-02 | 명시적 Standard가 Critical hard trigger 우회 | compiler.py | **CLOSED** — Critical task에 `mode=STANDARD` 요청해도 `task.mode == critical` 유지 확인 |
| Codex P1-03 | 독립성 검사가 tuple 전체만 비교(느슨함) | compiler.py:193-201 | **재현 형태 변경, OPEN** — §2.3 참고: identity 하나만 다르면 provider/model/checkout이 완전히 같아도 통과됨 |
| Codex P1-04 | revision node/rework history 미생성 | compiler.py | **부분 CLOSED, 새 결함 OPEN** — revision node는 생성되지만 `rework_of` edge가 전부 자기 자신을 가리키는 self-loop다. §2.4 참고 |
| Codex P1-05 | 알 수 없는 event/verdict actor 조용히 수용 | reducer.py | **부분 CLOSED, 관련 새 결함 OPEN** — actor 권한/unknown event는 막힘. 다만 evidence 없는 pass는 여전히 통과. §2.2 참고 |
| Codex P1-06 | canonical enum/모델 불완전 | models.py | **CLOSED** — `verification`/`progress`/`terminal_status`/`Run`/`Gate`/`GraphVersion` 모두 추가됨(§4 세부 비교는 남음) |
| Codex P2-01 | fan-in metadata가 이중 중첩 | compiler.py:267 | **CLOSED(중첩 문제), 새 결함 OPEN(타입 오염)** — §2.5 참고 |
| Codex P2-02 | 테스트가 happy path 위주 | tests/test_core.py | **부분 개선** — 12개로 늘었지만 §2의 4개 공격 경로는 여전히 테스트 없음 |
| Codex P2-03 | `.gitignore` 없음/캐시 오염 위험 | 저장소 루트 | **CLOSED** — `.gitignore` 확인, `git check-ignore`로 `__pycache__` 무시 확인 |
| Claude P0-1 | worker가 payload.actor_role 위조로 verdict 발행 | reducer.py | **CLOSED** — `event["actor"]["role"]`만 사용, `payload.actor_role` 위조 무시 확인 |
| Claude P0-2 | node_status_changed가 TaskState로 강제 변환되어 크래시 | reducer.py | **CLOSED** — Node/Task 상태 분리, 14개 canonical 값 모두 무크래시 확인. 단 §2.1의 새 결함과 별개 |
| Claude P0-3 | Standard/Critical topology가 worker-verifier 독립성 미검사 | compiler.py | **CLOSED(정확히 동일한 Role), OPEN(변형)** — §2.3과 동일한 결함으로 재발 |
| Claude P1-1 | usage_status 기본값이 "known" | compiler.py | **CLOSED** — 기본값이 "unknown"으로 바뀜, 누락 시 `usage_unknown` 트리거 확인 |
| Claude P1-2 | usage unknown 무조건 Critical | compiler.py | **CLOSED** (Codex P1-01과 동일 근거) |
| Claude P1-3 | ESCALATED가 막다른 상태 | compiler.py | **CLOSED** — `ESCALATED -> {BLOCKED, READY}` 확인 |
| Claude P1-4 | Human Gate 독립성 검사 함수 없음 | compiler.py | **CLOSED(함수 존재), OPEN(우회 가능)** — §2.3과 동일한 결함이 Gate pool에도 적용됨 |
| Claude P1-5 | Run 엔티티가 models.py에 없음 | models.py | **부분 CLOSED** — `Run`/`RunState` 클래스는 추가됐지만 reducer가 전혀 사용하지 않는다(§3.4) |
| Claude P1-6 | 미지 event 타입 조용히 무시 | reducer.py | **CLOSED** — `unknown event type` 예외 확인 |
| Claude P1-7 | 테스트가 P0를 못 잡음 | tests/test_core.py | **부분 개선** — Codex P2-02와 동일 평가 |
| Claude P1-8 | `.gitignore` 없음 | 저장소 루트 | **CLOSED** |
| Claude P2-1 | enum 대소문자 alias 중복 | models.py | **CLOSED** — `list(TaskMode)`가 3개만 반환 확인 |
| Claude P2-2 | verification metadata 누락 | compiler.py | **CLOSED** — Fast/Standard 모두 `verification` metadata 확인 |
| Claude P2-3 | DISPATCHED→CANCELLED 직접 불가 | compiler.py | **CLOSED** — `DISPATCHED -> CANCELLED` 허용 확인 |

## 2. 이번 재검수에서 새로 발견한 결함 (재현됨)

### 2.1 [P0] Node 상태는 아무 순서로나 바꿀 수 있다 — 역방향/terminal 되돌리기가 안 막힘

- 위치: `src/graphori_core/reducer.py:52-65`
- 문제: `node_status_changed` 이벤트는 값이 canonical `NodeState` enum에 속하기만
  하면 **순서 검사 없이** `self.node_statuses[node_id]`에 그대로 덮어쓴다.
  `TASK_TRANSITIONS`/`ATTEMPT_TRANSITIONS`처럼 Node 전용 전이표가 없다.
- 계약 위반: `EVENT_PROTOCOL.md` §4.1은 `cancelled`/`passed`/`failed` 같은 종단
  상태에서 되돌아가는 화살표를 정의하지 않으며, "`failed -> ready`(새 revision만;
  같은 node 재실행 금지)"처럼 명시적으로 좁은 예외만 허용한다. 이번 검수 항목
  #6("Task/Attempt transition을 역방향 또는 terminal에서 되돌려 보고 막히는지")의
  Node 레벨 대응 항목이 통째로 열려 있다.
- 재현 명령 (읽기 전용):

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, StateReducer
r = StateReducer(Task('t','x'))
for s in ['passed','pending','running','passed','failed','ready','cancelled','running']:
    r.apply({'type':'node_status_changed','entity':{'node_id':'n1'},'payload':{'status': s}})
    print(s, '-> 수락됨, 현재값=', r.node_statuses['n1'].value)
"
```

- 실제 결과: `cancelled -> running`, `passed -> pending`, `failed -> ready` 등 문서가
  금지하는 역방향 전이가 **전부 예외 없이 수락**됨.
- 기대 결과: `TASK_TRANSITIONS`/`ATTEMPT_TRANSITIONS`와 동등한 `NODE_TRANSITIONS`
  가드가 있어 잘못된 방향은 `StateTransitionError`가 나야 한다.
- Windows: 재현됨(FAIL). macOS: `deferred/unknown`(미실행, 코드 경로상 플랫폼
  무관 문제이므로 동일하게 발생할 것으로 예상되나 확인 전이라 단정하지 않음).

### 2.2 [P0] "증거 없는 pass"가 통과한다

- 위치: `src/graphori_core/reducer.py:83-86`
- 문제:

```python
evidence_ids = payload.get("evidence_ids", ())
if not isinstance(evidence_ids, (list, tuple)) or any(not str(item) for item in evidence_ids):
    raise StateTransitionError("evidence_ids must be a list of non-empty IDs")
self.verdicts.append(verdict)
```

  `evidence_ids`가 아예 없거나(`()`) 빈 리스트(`[]`)면 `isinstance` 검사는
  통과하고 `any(...)`는 빈 iterable에 대해 `False`이므로 **검사를 그냥 통과**한다.
  즉 "리스트 타입이면 통과, 심지어 비어 있어도 통과"다.
- 계약 위반: 이번 검수 항목 #2 "evidence 없는 pass"를 넣어 fail-closed인지
  확인하라는 요구사항 그 자체다. `GRAPHORI_ARCHITECTURE.md`는 "끝났다는 증거가
  무엇인지"를 카드의 핵심 요소로 규정하고, `platform_verdict_recorded`(같은 파일
  95-98줄)는 `PASS`일 때 `evidence_id` 필수를 이미 강제하고 있어 **동일 파일
  안에서도 두 이벤트 타입 간 기준이 다르다.**
- 재현 명령:

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, StateReducer
r = StateReducer(Task('t','x'))
r.apply({'type':'verdict_recorded','actor':{'role':'verifier'},'payload':{'verdict':'pass'}})
print('evidence_ids 필드 자체가 없어도 pass 수락됨:', r.verdicts)
r2 = StateReducer(Task('t2','x'))
r2.apply({'type':'verdict_recorded','actor':{'role':'human_gate'},'payload':{'verdict':'approve','evidence_ids':[]}})
print('빈 리스트 evidence_ids로 approve 수락됨:', r2.verdicts)
"
```

- 실제 결과: 두 경우 모두 예외 없이 `verdicts`에 추가됨.
- 기대 결과: `pass`/`approve`처럼 긍정 판정에는 최소 1개 이상의 비어있지 않은
  `evidence_ids`가 필수여야 한다(`revise`/`reject`/`inconclusive`는 별도 정책
  검토 가능).
- Windows: 재현됨(FAIL). macOS: `deferred/unknown`.

### 2.3 [P0] "이름만 다르면" 독립성 검사를 속일 수 있다 (Fast/Standard/Critical/Human Gate 전부)

- 위치: `src/graphori_core/compiler.py:193-201`(`_independence_key`,
  `_assert_verifier_independent`), `:286-297`(`_validate_gate_pool`),
  `:300-305`(`independent_verifier`)
- 문제: 독립성 판정이 `(identity, provider, model, checkout)` 4개 필드로 만든
  튜플이 **완전히 같은지**만 본다. `compile_topology`가 내부에서 만드는 Worker
  Role은 항상 `Role("role_worker", WORKER, "worker", "", "", "")`처럼
  provider/model/checkout이 빈 문자열이다. 공격자가 verifier(또는 Human Gate
  후보) Role의 `identity` 문자열만 바꾸고 provider/model/checkout을 worker와
  **완전히 동일하게(가짜 세션 재사용)** 맞추면, 튜플이 identity 한 글자 때문에
  달라져 "독립적"이라고 통과한다.
- 계약 위반: 이번 검수 항목 #3 "worker와 verifier가 이름만 다르고
  provider/model/checkout/session identity가 같은 경우"를 그대로 재현한다.
  `GRAPHORI_ARCHITECTURE.md` §4는 "Verifier는 작성 Worker와
  attempt/provider/model/checkout 중 최소 한 차원 이상 달라야 한다"고 못박는데,
  identity만 다른 이름표는 이 4가지 중 어떤 것도 다르게 만들지 않는다.
  (참고: 같은 문서 기술 부록 A 118줄 "동일한 identity와 checkout을... 재사용할
  수 없다"는 문장과 §4 문장이 서로 다른 조합을 기준으로 쓰여 있어, 문서 자체도
  약간 모호하다 — §4.4 참고.)
- 재현 명령 (Fast):

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, Role, NodeKind, compile_topology
verifier = Role('role_verifier_evil', NodeKind.VERIFIER, 'verifier-different-name', '', '', '')
topo = compile_topology(Task('t-fast', 'docs', metadata={'usage_status':'known'}), verifier_roles=(verifier,))
print('worker  :', topo.roles['worker'])
print('verifier:', topo.roles['verifier'])
print('예외 없이 accepted (provider/model/checkout이 worker와 완전히 동일한데도 통과)')
"
```

- 실제 결과: `IndependenceError` 없이 `CompiledTopology` 반환. Standard 모드도
  동일하게 재현됨(별도 확인 완료).
- Critical 모드에서는 두 verifier끼리도 동일한 방식으로 속일 수 있다:

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, Role, NodeKind, Risk, compile_topology
normal = Role('role_v1', NodeKind.VERIFIER, 'verifier-normal-alias', 'openai', 'gpt-5', 'checkout-shared')
adversarial = Role('role_v2', NodeKind.VERIFIER, 'verifier-adversarial-alias', 'openai', 'gpt-5', 'checkout-shared')
compile_topology(Task('t-crit', 'boundary', risk=Risk.CRITICAL), verifier_roles=(normal, adversarial))
print('provider/model/checkout이 완전히 같은 두 검수자가 서로 독립적이라며 통과')
"
```

- Human Gate authority pool도 같은 결함:

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, Role, NodeKind, Risk, compile_topology
gate_pool = (
    Role('role_gate_evil', NodeKind.HUMAN_GATE, 'gate-but-really-worker', '', '', ''),
    Role('role_gate_1', NodeKind.HUMAN_GATE, 'gate-1', 'gp', 'gm', 'gc'),
)
compile_topology(Task('t-std-gate', 'feature', risk=Risk.HIGH, metadata={'human_gate': True}), human_gate_roles=gate_pool)
print('Human Gate 후보가 worker와 provider/model/checkout이 같은데도(이름만 다름) 통과')
"
```

- 대조군(정상 동작 확인): Role 4-튜플이 **완전히** 동일한 경우는 여전히 잘
  막힌다(`IndependenceError`) — Critical 두 verifier가 진짜로 같은 Role 값이면
  거부됨을 재확인했다. 즉 "완전 동일 재사용"은 막히지만 "이름만 바꾼 재사용"은
  뚫린다.
- Windows: 재현됨(FAIL, Fast/Standard/Critical/Human Gate 4곳 모두). macOS:
  `deferred/unknown`.

### 2.4 [P1] revision 이력(`rework_of`)이 전부 자기 자신을 가리키는 self-loop다

- 위치: `src/graphori_core/compiler.py:350-364`(`RevisionController.record`)
- 문제: `self.revise_count += 1`(350줄)을 먼저 실행한 뒤, 351-353줄에서
  `old_node`를 **이미 증가된** `self.revise_count`로 계산한다. 그 결과 1회차
  호출에서 `old_node == new_id == "task:revision-1"`이 되어버려, 361-364줄이
  "새 revision 노드"를 그래프에 추가한 **직후** 같은 ID를 `old_node`로 찾아
  자기 자신에게 `rework_of` 엣지를 긋는다. 원래 노드(`task`)나 이전 revision과의
  연결은 전혀 만들어지지 않는다.
- 계약 위반: 이번 검수 항목 #5 "revision 1~3의 별도 기록... history edge 예외가
  안전한지"에 해당한다. `GRAPHORI_ARCHITECTURE.md` 2번 결정 "`revise`는... 새
  revision node를 만들고 `rework_of` history 관계를 추가한다"는 문장에서 이력
  관계 자체가 실질적으로 비어 있다. `test_revision_nodes_history_and_human_gate`
  테스트는 `len(history) == 3`만 확인하기 때문에 self-loop라는 사실을 못 잡는다.
- 재현 명령:

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, Graph, Node, NodeKind, RevisionController, EdgeKind
task = Task('task', 'change')
graph = Graph()
graph.add_node(Node('task', NodeKind.WORKER, 'original'))
rc = RevisionController()
for _ in range(3):
    rc.record('revise', task, graph)
for e in graph.edges:
    if e.kind is EdgeKind.REWORK_OF:
        print(e.source, '->', e.target, '(self-loop!)' if e.source == e.target else '')
"
```

- 실제 결과:
  ```
  task:revision-1 -> task:revision-1 (self-loop!)
  task:revision-2 -> task:revision-2 (self-loop!)
  task:revision-3 -> task:revision-3 (self-loop!)
  ```
- 기대 결과: `task:revision-1 -> task`(원본), `task:revision-2 ->
  task:revision-1`, `task:revision-3 -> task:revision-2`처럼 실제 이전 노드를
  가리켜야 감사(audit) 시 "무엇을 고쳐서 다시 만들었는지" 추적이 가능하다.
- 부가 확인: `validate_graph`는 `REWORK_OF`를 cycle 검사 대상에서 제외하므로
  self-loop가 있어도 예외를 던지지 않는다(설계상 의도된 예외 처리 자체는 맞다).
  4번째 revise의 Human Gate 연결(`task:revision-3 -> human_gate:revision:4`)은
  올바르게 최신 revision 노드를 가리켜 정상 동작함을 확인했다(이 부분은
  CLOSED).
- Windows: 재현됨(부분 FAIL — 카운터/에스컬레이션은 정상, 이력 링크만 깨짐).
  macOS: `deferred/unknown`.

### 2.5 [P2] fan-in 노드의 `.role` 필드가 문자열로 오염된다

- 위치: `src/graphori_core/compiler.py:183-185`(`_node` 헬퍼),
  `:267`(호출부)
- 문제: `_node(graph, node_id, kind, label, role=None, **metadata)`의 `role`
  파라미터 이름이, fan-in 노드를 만들 때 쓰는 `_node(graph, "verifier_fanin",
  NodeKind.VERIFIER, "Fan-in Verifier", fan_in=True, role="fan_in")` 호출의
  `role="fan_in"` 키워드와 충돌한다. 원래 `metadata`에 `{"role": "fan_in"}`을
  넣으려던 의도로 보이지만, 실제로는 `Node.role`(타입은 `Role | None`)에
  문자열 `"fan_in"`이 그대로 대입된다.
- 재현 명령:

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, Risk, compile_topology
node = compile_topology(Task('t', 'boundary', risk=Risk.CRITICAL)).graph.nodes['verifier_fanin']
print('node.role =', repr(node.role), type(node.role))
print('node.metadata =', node.metadata)
"
```

- 실제 결과: `node.role = 'fan_in' <class 'str'>`, `node.metadata = {'fan_in':
  True}` (의도했던 `role` metadata는 사라짐).
- 영향: `Node.role`이 `Role` 객체라고 가정하는 후속 코드(예: 대시보드/투영
  로직이 `node.role.identity`를 읽는 경우)가 이 노드를 만나면
  `AttributeError`가 난다. 보안 우회는 아니지만 타입 계약 위반이며, Critical
  경로에서만 생기는 fan-in 노드라는 점에서 조용히 넘기기엔 위험도가 있다.
- Windows: 재현됨. macOS: `deferred/unknown`.

## 3. 검수 항목별 결과 (요청받은 1~10번 순서)

1. **최초 findings 재현** — §1 표 참고. Codex 6건/Claude 12건 중 다수가
   CLOSED이나, Codex P1-03/Claude P0-3(독립성), Codex P1-04(revision 이력),
   Codex P1-05 일부(evidence)는 형태를 바꿔 재발했다.
2. **payload.actor_role 위조, actor 누락/다른 role, unknown event, malformed
   entity/payload, evidence 없는 pass, 잘못된 status** — actor 위조·누락·
   unknown event·malformed entity/payload·잘못된 node/task/platform status는
   전부 fail-closed(CLOSED, §2 이전 확인). **evidence 없는 pass만 예외
   (OPEN, §2.2).**
3. **이름만 다른 worker/verifier, 같은 두 Critical verifier, Human Gate와
   worker 겹침** — 완전 동일 재사용은 거부되지만(CLOSED), 이름(identity)만
   바꾸는 변형은 Fast/Standard/Critical/Human Gate 네 곳 전부 뚫린다(OPEN,
   §2.3).
4. **Critical에 Standard/Fast 요청, usage×uncertainty×external_effect×
   high-risk 경계값** — 전부 CLOSED. 아래 §3.1 boundary 표 참고.
5. **revision 1~3 별도 기록, 4번째 escalation, cycle 검사, history edge 예외**
   — 카운터/에스컬레이션/cycle 예외는 CLOSED, `rework_of` 실제 연결은 OPEN
   (§2.4).
6. **Task/Attempt 역방향·terminal 복귀** — Task/Attempt 두 엔티티는 전부
   CLOSED(막힘, §3.2 표 참고). **Node 엔티티는 가드 자체가 없어 OPEN**(§2.1).
7. **canonical 문서 vs enum/event/metadata 모순** — §3.3 참고. 대부분 일치,
   `task_status_changed`(EVENT_TYPES에 있지만 EVENT_PROTOCOL 부록 A엔 없음),
   `EdgeKind.VERIFIES`(정의는 있지만 compiler가 생성하지 않음), `RunState`
   (Run 관련 canonical enum이 EVENT_PROTOCOL에 없는데 새로 도입됨) 3건은
   불일치/모호함이 있다(P2, 문서 정합 문제이지 실행 결함은 아님).
8. **stdlib-only/이식성, Windows 직접 실행, macOS deferred** — `ast` 기반 정적
   검사로 `src/graphori_core/*.py`에 stdlib(`__future__`, `dataclasses`,
   `enum`, `typing`)와 sibling module(`models`, `compiler`) 외 import가 0건임을
   재확인. `python -m unittest`/`compileall`을 Windows에서 직접 실행해 통과를
   확인했다(§0). macOS는 실행하지 않았으므로 `deferred/unknown`으로 남긴다.
9. **테스트가 실제로 취약점을 막는지** — 12개 테스트 모두 §2의 4개 신규 결함
   (Node 전이, evidence-less pass, identity-only 독립성, rework_of self-loop)
   중 어느 것도 검증하지 않는다. 필요한 공격 입력은 전부 읽기 전용
   `python -c` one-liner로만 실행했고 구현/테스트 파일은 수정하지 않았다.
10. **저장소 오염/패키지 사용성** — `.gitignore`와 `__pycache__` 무시는
    CLOSED(§3.5). `pip install`/`PYTHONPATH` 없이 `import graphori_core`가
    실패하는 점은 Codex 원 보고서와 동일하게 "결함이 아니라 설치 절차 필요"로
    분류하고 residual risk로 남긴다(§5).

### 3.1 위험 분류 경계값 재확인

```text
{}                                              -> low     standard  ('usage_unknown',)
{'usage_status': 'unknown'}                     -> low     standard  ('usage_unknown',)
{'usage_status': 'estimate'}                    -> low     standard  ()
{'usage_status': 'known'}                       -> low     fast      ()
{'usage_status': 'known', 'uncertainty': 1}     -> low     standard  ()
{'usage_status': 'known', 'uncertainty': 2}     -> critical critical ('uncertainty',)
{'usage_status': 'known', 'external_effect': True} -> critical critical ('external_side_effect',)
{'usage_status': 'known', 'tags': ('high-risk',)}  -> critical critical ('hard_tag',)
{'usage_status': 'bogus-value'}                 -> low     standard  ('usage_unknown',)  # 잘못된 값도 unknown 취급 (fail-closed, 안전)
{'usage_status': None}                          -> low     standard  ('usage_unknown',)
```

모두 기대대로 동작한다(CLOSED). 다만 `TEAM_TOPOLOGY.md:36`은 "Fast 조건:
`risk_level <= 1`"이라고 적었는데, 실제 `compile_risk`는 `risk_level=1`이면
가중치(3×risk_level=3)만으로 `score>=3` 분기에 걸려 항상 Standard로 간다
(risk_level=0일 때만 Fast 도달 가능). 보안적으로 더 엄격한 방향이라 위험하지는
않지만, 문서 문구와 코드가 정확히 일치하지 않는다(P2, §3.3에 포함).

### 3.2 Task/Attempt 역방향·terminal 전이 전수 확인

```text
[Task]      succeeded -> running    : blocked
[Task]      succeeded -> ready      : blocked
[Task]         failed -> ready      : blocked   (같은 node 재실행 금지 규칙 유지)
[Task]      escalated -> succeeded  : blocked
[Attempt]   succeeded -> running    : blocked
[Attempt]   cancelled -> dispatched : blocked
[Attempt] outcome_unknown -> running: blocked
```

시도한 11개(Task) + 10개(Attempt) 조합 전부 `StateTransitionError`로 막혔다.
**Task/Attempt는 CLOSED.** Node는 §2.1 참고(OPEN).

### 3.3 canonical 문서 vs 구현 정합성

| 항목 | 문서 | 구현 | 판정 |
|---|---|---|---|
| `node_status`(14종) | EVENT_PROTOCOL.md:26-28 | `NodeState` 14종 일치 | 일치 |
| `attempt_status`(9종) | EVENT_PROTOCOL.md:29-30 | `AttemptState` 9종 일치 | 일치 |
| `verdict`(6종) | EVENT_PROTOCOL.md:31 | `VerdictKind` 6종 일치 | 일치 |
| `liveness`/`progress`/`usage_status`/`platform_status` | EVENT_PROTOCOL.md:32-35 | 각 enum 일치 | 일치 |
| 필수 event 타입 | EVENT_PROTOCOL.md 부록 A(23종) | `reducer.EVENT_TYPES`에 23종 + `task_status_changed` 추가 | **불일치(P2)** — 문서에 없는 타입이 구현에 있음 |
| `EdgeKind.VERIFIES` | GRAPHORI_ARCHITECTURE.md §5 "검증은 verifies로 고정" | `compiler.py`는 worker→verifier 엣지를 전부 `EdgeKind.REQUIRES`로 생성, `VERIFIES`는 어디서도 만들지 않음 | **불일치(P2)** — 다만 EVENT_PROTOCOL §4.2 "requires/requires_gate만 스케줄링을 막는다"와 함께 보면 문서 자체가 두 엣지 종류의 역할 분담을 완전히 명시하지 않아 모호함도 있음 |
| `Run`/`RunState` | EVENT_PROTOCOL.md canonical enum 표(§2)에 `run_state` 없음; Run terminal은 §6에서 `terminal_status` 값(`succeeded` 등)을 그대로 씀 | `models.py`가 `RunState`(PLANNED/RUNNING/SUCCEEDED/FAILED/BLOCKED/ESCALATED)라는 별도 enum을 새로 도입, `TerminalStatus`와 값 집합이 다름 | **불일치(P2)** — Claude 원 리뷰 P1-5로 지적된 "Run 없음"은 존재 자체는 closed지만, canonical enum과 안 맞는 새 enum을 만든 대가로 재발함. reducer도 Run을 다루지 않아(§3.4) 사실상 미사용 스캐폴딩 |

### 3.4 `Run`이 추가됐지만 거버넌스에 연결되지 않음

`models.py`의 `Run`/`RunState`는 dataclass로만 존재하고, `reducer.py`의
`StateReducer`는 `Task`만 다루며 `run_created`/`run_terminal` 이벤트를
받아 `Run.state`를 바꾸는 코드가 전혀 없다. `Run.state`는 아무 가드 없이
Python에서 직접 대입 가능하다(`run.state = RunState.SUCCEEDED`처럼). Claude
원 리뷰 P1-5("Run 엔티티가 없다")는 "존재" 기준으로는 CLOSED이지만, 실질적인
"Run 판정 거버넌스"는 여전히 없다. I02 범위(2단계: Run/graph/node/edge/
attempt/reducer/risk compiler)를 보면 Run 전이 가드가 빠진 것은 후속 단계로
미루기보다 이번 단계의 acceptance("in-memory fixture가 동일한 graph와 terminal
projection을 만든다")에 걸쳐 있어 residual risk로만 두기엔 애매하다. 심각도는
P1-5 계열의 잔존 이슈로 P2로 남긴다(신규 회귀를 만들지는 않았기 때문).

### 3.5 저장소 오염 확인

```text
$ git status --short
?? .gitignore
?? README.md
?? TEAM_TOPOLOGY.md
?? docs/
?? graphori/
?? pyproject.toml
?? src/
?? tests/

$ git check-ignore -v src/graphori_core/__pycache__/compiler.cpython-312.pyc tests/__pycache__/test_core.cpython-312.pyc
.gitignore:1:__pycache__/	src/graphori_core/__pycache__/compiler.cpython-312.pyc
.gitignore:1:__pycache__/	tests/__pycache__/test_core.cpython-312.pyc
```

`__pycache__`가 `.gitignore`로 정확히 걸러진다. **CLOSED.**

## 4. 이번 검수의 총평

- P0급 신규(또는 형태 변경 재발) 결함이 3건(§2.1, §2.2, §2.3), P1급 1건(§2.4),
  P2급 다수(§2.5, §3.3)다. 세 P0 모두 이번 검수 요청서에 명시된 공격
  시나리오(#2, #3, #6)를 그대로 재현한 것이라 "테스트를 통과했으니 안전하다"고
  볼 수 없다.
- 좋은 소식: Claude/Codex 원 검수의 P0/P1 대부분(actor 권한, node_status
  crash, usage 기본값/무조건 Critical, ESCALATED 막다른 상태, 미지 이벤트,
  enum alias, `.gitignore`)은 재현 시도에서 실제로 막혔다. Luna의 수정은
  절반 이상 진짜로 닫혔다.
- 남은 문제의 공통점: **"완전히 같은 값"만 비교하는 방어**(독립성 tuple
  전체 일치, evidence_ids가 리스트이기만 하면 통과, node_status는 canonical
  값이기만 하면 통과)가 반복적으로 등장한다. 이 패턴을 한 번에 점검하면
  §2.1/§2.2/§2.3을 비슷한 방식으로 고칠 수 있을 것으로 보인다(구현은 이번
  검수 범위 밖이므로 수정하지 않았다).

## 5. Residual risk (I02 범위 밖으로 분리)

- 패키지 미설치 상태에서 `import graphori_core`가 실패하는 점(`PYTHONPATH=src`
  또는 `pip install -e .` 필요) — Codex 원 보고서와 동일하게 결함이 아니라
  설치 절차 필요로 분류.
- `active_wip`/`task_parallelism`/fan-in queue/`priority` 정렬,
  Human Gate holder heartbeat/takeover, seeded-defect 감사 주기 —
  `IMPLEMENTATION_PLAN.md` 3~9단계 범위이며 이번 2단계 core에는 아직 없다.
  없는 것 자체는 이번 검수의 REVISE 사유가 아니다.
- `EdgeKind.VERIFIES` 사용 여부와 `GRAPHORI_ARCHITECTURE.md` §5/`EVENT_PROTOCOL.md`
  §4.2 간의 문서 정합성은 코드보다 문서 쪽 명확화가 먼저 필요해 보인다(설계
  결정 필요, 구현 재검수만으로 결론 내리지 않음).
- macOS 실행: 여전히 `deferred/unknown`. 이번 검수도 Windows에서만 실행했다.

## 6. 재현 명령 요약 (전부 읽기 전용, 구현/테스트 파일 미수정)

```bash
# 환경/기본 확인
python --version
python -m unittest discover -s tests -v
python -m compileall -q src tests
git status --short
git check-ignore -v src/graphori_core/__pycache__/compiler.cpython-312.pyc tests/__pycache__/test_core.cpython-312.pyc

# §2.1 Node 상태 역방향
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, StateReducer; r=StateReducer(Task('t','x')); [ (r.apply({'type':'node_status_changed','entity':{'node_id':'n1'},'payload':{'status':s}}), print(s, r.node_statuses['n1'].value)) for s in ['passed','pending','running','passed','failed','ready','cancelled','running'] ]"

# §2.2 evidence 없는 pass
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, StateReducer; r=StateReducer(Task('t','x')); r.apply({'type':'verdict_recorded','actor':{'role':'verifier'},'payload':{'verdict':'pass'}}); print(r.verdicts)"

# §2.3 identity만 다른 독립성 우회 (Fast)
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, Role, NodeKind, compile_topology; v=Role('rv', NodeKind.VERIFIER, 'diff-name', '', '', ''); t=compile_topology(Task('t','docs',metadata={'usage_status':'known'}), verifier_roles=(v,)); print(t.roles['worker'], t.roles['verifier'])"

# §2.4 rework_of self-loop
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, Graph, Node, NodeKind, RevisionController, EdgeKind; task=Task('task','change'); g=Graph(); g.add_node(Node('task',NodeKind.WORKER,'orig')); rc=RevisionController(); [rc.record('revise', task, g) for _ in range(3)]; [print(e.source,'->',e.target) for e in g.edges if e.kind is EdgeKind.REWORK_OF]"

# §2.5 fan-in role 오염
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, Risk, compile_topology; n=compile_topology(Task('t','boundary',risk=Risk.CRITICAL)).graph.nodes['verifier_fanin']; print(repr(n.role), n.metadata)"
```

## 7. 결론

**REVISE.** §2.1(Node 전이 무가드), §2.2(evidence 없는 pass 통과),
§2.3(identity만 다른 독립성 우회 — Fast/Standard/Critical/Human Gate 전부)은
이번 검수 요청서가 명시한 공격 시나리오를 그대로 재현한 P0급 결함이며, 셋 다
"통과 중인 12개 테스트"가 전혀 잡아내지 못한다. §2.4(rework_of self-loop)는
감사 추적성을 실질적으로 무력화하는 P1이다. 이 4건을 고치고 각각에 대한
회귀 테스트(특히 부정 경로: 역방향 node 전이, evidence 누락, identity만 다른
독립성 시도, revision 이력의 실제 참조 대상)를 추가한 뒤 Windows에서 동일
명령으로 재검수해야 다음 판정을 논의할 수 있다. macOS는 실행하지 않았으므로
`deferred/unknown`이며, 이 보고서의 판정은 Windows 실행 결과에만 근거한다.
