# I02 portable core revision-4 최종 독립 검수 (Claude)

검수일: 2026-08-09 (Windows, Python 3.12.1)
검수자: Claude — 독립 검증자. `src/graphori_core/*`, `tests/test_core.py`, `pyproject.toml`를
**수정하지 않았다.** 이 보고서 파일 하나만 새로 썼다.
검수 대상: `docs/verification/I02_CORE_FIX4_REPORT_LUNA.md`(revision-4 수정 주장)와 그 근거
코드 `src/graphori_core/{models,compiler,reducer,__init__}.py`, `tests/test_core.py`(21개).
비교 대상(직전 라운드): `I02_CORE_POST_FIX3_REVIEW_CODEX.md`, `I02_CORE_POST_FIX3_REVIEW_CLAUDE.md`.
기준 문서: `docs/architecture/EVENT_PROTOCOL.md`, `docs/IMPLEMENTATION_PLAN.md`.

## 0. 12살에게 설명

지난 라운드(revision-3)에서 두 검수자가 같은 틈을 찾았다. "이 카드는 어느 경주에 속해요"
라는 이름표를 미리 붙여두면, "경주 시작!"이라는 영수증(`run_created`) 없이도
"그래프 공개!"와 "경주 끝, 성공!"까지 찍을 수 있었다. 이번 revision-4는 그 틈과, 코덱스가
같은 라운드에서 찾은 "첫 영수증의 작업 이름표가 달라도 받아준다"는 틈을 확실히 막았다.
직접 다시 두드려 봐도 두 틈은 이제 전부 거절됐다.

그런데 코덱스가 같은 라운드에서 찾은 **세 번째 틈은 이번 수정에서 건드리지 않았다.**
"경주에 들어간 선수(node)가 아직 출발선에 서 있기만(pending) 해도, 심판이 '경주 끝,
전원 성공!'이라고 도장을 찍을 수 있다"는 문제다. 직접 다시 두드려 보니 여전히 그대로
뚫려 있었다. 그래서 이번에도 REVISE다.

## 1. 실행 결과 요약 (직접 실행, Windows)

```text
$ python --version
Python 3.12.1

$ python -m unittest discover -s tests -v
Ran 21 tests in 0.008s
OK

$ python -m compileall -q src tests
(종료 코드 0)

$ git diff --check
(종료 코드 0)

$ python -m pip install . --no-deps --target <임시폴더> -q
$ PYTHONPATH=<임시폴더> python -c "import graphori_core"
IMPORT_OK <임시폴더>\graphori_core\__init__.py

$ AST로 src/graphori_core/*.py import 전수 조사
compiler.py: __future__, dataclasses, enum, typing
models.py:   __future__, dataclasses, enum, typing
reducer.py:  __future__, dataclasses, re, typing
__init__.py: (없음)
```

21개 테스트(기존 19 + FIX4가 추가한 2) 전부 통과. `compileall`, `git diff --check`,
임시 target `pip install`과 그 경로에서의 `import`, stdlib-only import(0건 외부 의존,
0건 `orca` import)까지 전부 성공. macOS는 이 Windows 작업 환경에서 실행할 수 없으므로
`deferred/unknown`이다.

**주의**: "21개 테스트가 통과했다"를 그대로 판정 근거로 쓰지 않았다. 아래 §2, §3은
전부 `tests/test_core.py`를 실행하지 않고 이번 검수에서 직접 만든 `python -c` 반례다.

## 2. revision-3까지의 모든 P0/P1을 이번에 직접 다시 공격 — 전부 CLOSED 재확인

| 원 finding (출처) | 이번 재공격 | 결과 |
|---|---|---|
| Node 상태 역방향/부활, 증거 없는 verdict, verdict 권한 위조, identity-only 독립성 우회, Critical/Human Gate 독립성, `rework_of` cycle, revision 원자성, digest/prev_digest 형식, actor.role_id, genesis sentinel (REVIEW~POST_FIX3 전 라운드) | `tests/test_core.py`의 해당 21개 테스트를 그대로 재실행 + 대표 반례(증거 없는 verdict 7종, 부분 identity 공유 5종, `digest`/`prev_digest` 악성값) 직접 재실행 | **CLOSED** — 전부 예외 발생, 21/21 OK |
| **Codex Finding 2 (revision-3, P1): 주입된 Run에서 `run_created` 없이 `graph_published` 통과** | `Task(run_id=..., graph_version=1)`과 `Run(...)`을 둘 다 미리 만든 뒤 `run_created` 없이 바로 `graph_published` 전송(Attack B), `Task.run_id`만 채운 경우도 별도 확인(Attack B2), `run_terminal`을 바로 전송(Attack B3) | **CLOSED** — 3가지 전부 `StateTransitionError: graph_published requires run_created` / `run_terminal requires graph_published` |
| **Claude Finding (revision-3, P1): 같은 문제의 동일 근본원인** | 위와 동일 반례 | **CLOSED** — `_run_created_applied` 플래그가 실제 이벤트 적용 여부를 추적함을 코드(`reducer.py:133-149`, `:192-221`)로 확인 |
| **Codex Finding 3 (revision-3, P1): 첫 `run_created`의 `entity.task_id`가 실제 Task와 달라도 받아들임** | `Task('task-real', ...)`에 `entity.task_id='task-other'`인 `run_created` 전송(Attack C) | **CLOSED** — `StateTransitionError: entity.task_id does not match Task.task_id` |
| Run projection 정상 순서, graph version 역행, 다른 run_id, terminal 역전 (POST_FIX3 두 보고서 모두 CLOSED로 재확인했던 항목) | 아래 §3의 Attack G/H/J/K로 재확인 | **CLOSED** (재확인) |

**결론: revision-3에서 제기된 4건의 P1 중 3건(Codex 2, Codex 3, Claude의 순서 문제)은
revision-4에서 실제로 닫혔다.** `FIX4_REPORT_LUNA.md`의 주장과 코드가 일치한다.

## 3. 이번 검수에서 직접 실행한 추가 반례 (요청 항목별)

### 3.1 pre-injected Run/Task가 있어도 `run_created` 이전 `graph_published`/`run_terminal` 차단 — CLOSED

```text
Attack B  (Run 객체 + Task.run_id 둘 다 주입, run_created 생략, graph_published 시도)
  -> StateTransitionError: graph_published requires run_created
Attack B2 (Task.run_id만 주입, Run 객체 없음, graph_published 시도)
  -> StateTransitionError: graph_published requires run_created
Attack B3 (Run 객체 주입, run_created 생략, run_terminal 바로 시도)
  -> StateTransitionError: run_terminal requires graph_published
```

### 3.2 run_created 첫 사건 identity/version mismatch, duplicate/reopen — CLOSED

```text
Attack C (entity.task_id != Task.task_id인 첫 run_created)
  -> StateTransitionError: entity.task_id does not match Task.task_id
Attack D (run_created의 graph_version != Task.graph_version)
  -> StateTransitionError: run_created graph version does not match Task.graph_version
Attack E (run_created를 같은 reducer에 두 번 전송)
  -> StateTransitionError: run_created cannot be duplicated or reopen a Run
Attack F (run_terminal 이후 run_created로 재오픈 시도)
  -> StateTransitionError: run_created cannot be duplicated or reopen a Run
```

### 3.3 graph publish 순서/version, terminal immutability — CLOSED

```text
Attack G (graph_published의 graph_version이 run_created가 세운 버전보다 낮음, 2 -> 1)
  -> StateTransitionError: graph version cannot regress
Attack J (graph_published 없이 run_terminal 먼저 시도)
  -> StateTransitionError: run_terminal requires graph_published
Attack K (graph_published를 같은 reducer에 두 번 전송)
  -> StateTransitionError: graph_published cannot be duplicated
Attack H (run_terminal(succeeded) 확정 후 failed/cancelled/rejected/blocked/inconclusive/
          succeeded 6가지 값으로 다시 덮어쓰기 시도)
  -> 6가지 전부 StateTransitionError (terminal status 불변 확인)
```

### 3.4 정상 3사건 순서 통과 — CLOSED

```text
Attack I: run_created(seq=1) -> graph_published(seq=2) -> run_terminal(succeeded, seq=3)
결과: 예외 없이 통과, run.terminal_status == "succeeded"
```

golden path는 정상적으로 열려 있다. 문제는 여기가 아니라 §4다.

### 3.5 — **REVISE 사유: Codex Finding 1 (revision-3, P1)이 revision-4에서도 그대로 열려 있음**

#### Finding [P1] `run_terminal(succeeded)`이 노드 완료 여부를 전혀 확인하지 않는다

- 위치: `src/graphori_core/reducer.py:218-230`의 `run_terminal` 분기. `run_created`와
  `graph_published`가 적용됐는지, terminal_status가 유효한 enum인지, 이미 terminal이
  아닌지만 확인한다. `run.graph.nodes`의 어떤 node 상태도, `self.node_statuses`의 어떤
  값도 읽지 않는다.
- 계약 위반: `EVENT_PROTOCOL.md` §6 "Run은 모든 필수 scope가 terminal이고 gate 조건이
  충족될 때만 `succeeded`다"와 `IMPLEMENTATION_PLAN.md` 2단계 acceptance "in-memory
  fixture 세 가지가 동일한 graph와 **terminal projection**을 만든다"를 어긴다. Run이
  "성공"이라고 기록되는 순간에는 그 밑의 worker/verifier/human_gate node들이 실제로
  끝났다는 최소한의 확인이 있어야 한다.
- 재현 명령 (읽기 전용, 구현/테스트 파일 미수정):

```python
import sys; sys.path.insert(0, 'src')
from graphori_core import *

t = Task('t', 'x', run_id='r', graph_version=1)
r = Run('r', 1)
r.graph.add_node(Node('n', NodeKind.WORKER, 'pending'))   # node는 시작도 안 함
p = StateReducer(t, r)
p.apply(canonical_event('run_created', run_id='r', task_id='t', graph_version=1))
p.apply(canonical_event('graph_published', run_id='r', task_id='t', graph_version=1))
p.apply(canonical_event('run_terminal', run_id='r', task_id='t', graph_version=1,
                        payload={'terminal_status': 'succeeded'}))
print(r.terminal_status.value)
```

- 실제 결과: `succeeded`. worker node `n`이 `pending`(출발도 안 한 상태) 그대로인데도
  Run 전체가 "성공"으로 확정된다.
- 추가 확인 — node_status_changed와 Run.graph.nodes의 연결 자체가 없음:

```python
p.apply(canonical_event('node_status_changed', entity={'node_id': 'n'},
                        payload={'status': 'ready'}))
print(p.node_statuses['n'])       # -> ready  (reducer 내부 dict만 바뀜)
print(r.graph.nodes['n'].state)   # -> pending (Node 객체는 그대로)
```

  `node_status_changed`는 reducer 안의 별도 `dict[str, NodeState]`만 갱신하고,
  `Run.graph.nodes[node_id].state`는 절대 건드리지 않는다. 즉 이벤트로 아무리 "이
  노드는 이미 통과했다"고 보고해도 `run_terminal`이 볼 수 있는 어떤 상태도 실제로
  갱신되지 않는다 — `run_terminal`이 노드를 확인하려 해도 확인할 연결된 데이터가
  없다.
- 기대 결과: `run_terminal(succeeded)`는 Run에 속한 필수 node가 전부 terminal
  상태(passed 계열)이고 필수 gate가 충족됐는지 확인한 뒤에만 통과해야 한다. 최소한
  "확인할 방법 자체가 없다"는 상태여서는 안 된다.
- Stage3(hash chain, JSONL writer)와 혼동 아님: 이 결함은 hash 계산이나 monotonic
  seq, idempotency와 무관하다. 순수하게 in-memory Run/Graph/Node 객체 사이의
  projection 정합성 문제이며, `IMPLEMENTATION_PLAN.md` 2단계(portable core)
  acceptance("terminal projection") 범위 안이다. Stage3 미구현을 이유로 이 finding을
  덮을 수 없다.
- FIX4 범위와의 관계: `I02_CORE_FIX4_REPORT_LUNA.md`는 스스로 "이번 revision-4의
  범위는 이 한 가지 lifecycle projection 문제(= run_created 순서)입니다"라고 명시했다.
  즉 이번 수정은 Codex Finding 2/3과 Claude의 순서 문제만 겨냥했고, Codex Finding 1은
  범위에 없었다고 보고서 스스로 인정한 셈이다. 코드도 그 말대로였다 — Finding 1은
  손대지 않았다.
- Windows: 재현됨(FAIL). macOS: `deferred/unknown`(플랫폼 무관 로직으로 보이나
  확인 전이므로 단정하지 않음).

## 4. 잔존 위험 (REVISE 사유가 아닌 후속/관찰 항목)

- `NodeState.REJECTED`는 `NODE_TRANSITIONS`의 어떤 target에도 등장하지 않아
  `transition_node`로는 도달 불가(과잉차단, 이전 라운드부터 관찰됨. 취약점 아님).
- WIP/fan-in queue readiness 계산(`IMPLEMENTATION_PLAN.md` 2단계 acceptance,
  `NodeState.QUEUED`)은 `src`/`tests` 어디에도 구현·테스트가 없다. POST_FIX3_CODEX가
  P2로 분류했던 항목과 같으며, 이번 검수도 별도 관찰로만 남긴다(§3.5의 P1과는 다른
  결함이다 — §3.5는 "확인을 아예 안 함", 이 항목은 "queue 배치 로직이 없음").
- Stage3 실제 JSONL writer, hash 계산/chain, monotonic sequence, idempotency,
  crash-tail quarantine는 여전히 미구현이며 I02(2단계) 범위 밖이다. `digest`/
  `prev_digest`는 이번에도 형식(`sha256:<64hex>`)만 검사됨을 재확인했고, 이는
  `EVENT_PROTOCOL.md` §7이 Stage3 owner로 명시한 범위와 일치한다.
- 실제 Windows/macOS process adapter, dashboard, Orca adapter는 3~9단계이며
  이번 2단계 core 구현에는 포함되지 않는다.
- macOS 실행: 여전히 `deferred/unknown`. 이번 검수도 Windows에서만 실행했다.

## 5. 최종 판정

**REVISE.**

revision-3에서 두 검수자가 제기한 4건의 P1 중 3건(Run 순서 우회 두 건, 첫 사건 Task ID
불일치)은 revision-4에서 실제로 닫혔다. 이번 재공격(Attack B/B2/B3/C/D/E/F/G/H/J/K)이
전부 fail-closed로 확인됐고, 정상 3사건 순서(run_created → graph_published →
run_terminal)도 예외 없이 통과했다(Attack I).

그러나 남은 1건, Codex가 revision-3에서 P1으로 분류한 "끝나지 않은 노드가 있어도 Run
성공을 허용함"(§3.5)은 revision-4 수정 범위 밖이었고 코드도 그대로다. `pending` 상태인
worker node가 그래프에 남아 있어도 `run_terminal(succeeded)`가 그대로 통과한다. 게다가
`node_status_changed` 이벤트가 `Run.graph.nodes`의 실제 상태를 전혀 갱신하지 않아,
설령 나중에 "노드 상태를 확인하라"는 검사를 추가하려 해도 지금 구조에서는 확인할 데이터
자체가 없다. 이는 `EVENT_PROTOCOL.md` §6과 `IMPLEMENTATION_PLAN.md` 2단계 acceptance의
"terminal projection" 요구를 벗어나며, Stage3(hash chain/journal) 미구현과는 무관한
Stage2/I02 범위의 결함이므로 후속 단계 residual로 내릴 수 없다.

핵심 P1이 하나 남아 있으므로 `APPROVE with residual`로 바꿀 수 없다. 수정 범위는 비교적
좁다 — `run_terminal`이 `succeeded`를 기록하기 전에 `run.graph.nodes`(또는 이와 연결된
node 상태 저장소)의 필수 node가 전부 terminal인지 확인하는 gate를 추가하고,
`node_status_changed`가 실제로 `Run.graph.nodes[node_id].state`를 갱신하도록 연결한
뒤, "pending node가 있으면 run_terminal(succeeded)가 거절된다"는 회귀 테스트를
추가하면 닫을 수 있다.

VERDICT: REVISE
