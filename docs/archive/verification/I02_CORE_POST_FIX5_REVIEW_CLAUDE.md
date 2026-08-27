# I02 portable core Fix-5 사후 독립 검수 (Claude, fresh)

검수일: 2026-08-09 (Windows, Python 3.12.1)
검수자: Claude — 신선한(fresh) 독립 검증자. Codex의 결과를 보거나 따르지 않았고,
**`src/graphori_core/*`, `tests/test_core.py`, `pyproject.toml`를 수정하지 않았다.**
이 보고서 파일 하나만 새로 썼다.

검수 대상: `docs/verification/I02_CORE_FIX5_REPORT_LUNA.md`(Fix-5 작업 주장)와 그 근거 코드
`src/graphori_core/{models,compiler,reducer,__init__}.py`, `tests/test_core.py`(24개).
비교 대상(직전 라운드): `docs/verification/I02_CORE_POST_FIX4_REVIEW_CODEX.md`,
`docs/verification/I02_CORE_POST_FIX4_REVIEW_CLAUDE.md`.
기준 문서: `docs/architecture/EVENT_PROTOCOL.md`, `docs/IMPLEMENTATION_PLAN.md`.

## 0. 12살에게 설명

지난 라운드(Fix-4 사후 검수)에서 Codex와 Claude 둘 다 같은 구멍을 남겨뒀다고 판정했다.
"경주에 들어간 선수(node)가 아직 출발선에 서 있기만(pending) 해도, 심판이 '경주 끝,
전원 성공!'이라고 도장을 찍을 수 있다"는 문제였다. 이번 Fix-5는 그 구멍을 진짜로
막았다 — 직접 두드려 봐도 이제는 확실히 거절된다.

그런데 이번에 새로 두드려 보니, 같은 도장 찍기 규칙에 **다른 구멍**이 남아 있었다.
"terminal(더 이상 진행 중이 아님)"과 "성공(passed)"을 같은 것으로 취급하고 있어서,
선수 한 명이 완전히 **실패(failed)**했는데도 심판이 "전원 성공!" 도장을 찍을 수
있었다. 이건 이번 수정이 목표로 삼았던 문제(대기 중인 선수)와는 다른 종류의
구멍이라서, 이번 수정 범위 밖이라고 주장할 수는 있지만, "성공 도장이 진짜 성공을
보장한다"는 이 검수 시리즈 전체의 목적을 그대로 뚫는다. 그래서 이번에도 REVISE다.

## 1. 실행 결과 요약 (직접 실행, Windows)

```text
$ python --version
Python 3.12.1

$ python -m unittest discover -s tests -v
Ran 24 tests in 0.009s
OK

$ python -m compileall -q src tests
COMPILEALL_OK (종료 코드 0)

$ git diff --check
DIFF_CHECK_OK (종료 코드 0)

$ TMPDIR=$(mktemp -d)
$ python -m pip install . --no-deps --target "$TMPDIR" -q
$ PYTHONPATH="$TMPDIR" python -c "import graphori_core; from graphori_core import StateReducer, Run, Node, NodeKind, canonical_event"
PACKAGE_IMPORT_OK <temp>/graphori_core/__init__.py

$ python -c "AST로 src/graphori_core/*.py import 전수 조사"
__init__.py : compiler, models, reducer
compiler.py : __future__, dataclasses, enum, models, typing
models.py   : __future__, dataclasses, enum, typing
reducer.py  : __future__, compiler, dataclasses, models, re, typing
```

24개 테스트(Fix-5가 추가한 3개 포함) 전부 통과. `compileall`, `git diff --check`, 임시
target `pip install`과 그 경로에서의 `import`, stdlib-only import(0건 외부 의존, 0건
`orca` import)까지 전부 성공. macOS는 이 Windows 작업 환경에서 실행할 수 없으므로
`deferred/unknown`이다.

**주의**: "24개 테스트가 통과했다"를 그대로 판정 근거로 쓰지 않았다. 아래 §2, §3은 전부
`tests/test_core.py`를 실행하지 않고 이번 검수에서 직접 만든 19개 `python` 반례
(A1~A19)다. 소스/테스트 파일은 전혀 수정하지 않았고 `docs/verification/`에만 이 파일을
새로 썼다.

## 2. 이전 공통 P1 판정 — CLOSED

Fix-4 사후 검수에서 Codex와 Claude 둘 다 남겼던 P1: **"pending/nonterminal 상태인
실행 대상 node가 그래프에 남아 있어도 `run_terminal(succeeded)`가 통과한다"**.

직접 재현(원래 Codex 보고서의 반례를 그대로 재사용):

```python
t = Task('t-pending', 'x', run_id='r-pending', graph_version=1)
r = Run('r-pending', 1)
r.graph.add_node(Node('n', NodeKind.WORKER, 'pending'))   # 시작도 안 함
p = StateReducer(t, r)
p.apply(canonical_event('run_created', ...))
p.apply(canonical_event('graph_published', ...))
p.apply(canonical_event('run_terminal', ..., payload={'terminal_status': 'succeeded'}))
```

결과:

```text
A1 pending-worker-succeeded (must be BLOCKED):
BLOCKED: succeeded run requires terminal execution nodes: n
```

`StateTransitionError`로 확실히 거절됨. router/verifier/human_gate/platform_gate
전부에 대해서도 같은 방식으로 각각 별도 반례를 만들어 재확인했다(§3.1). **이전 공통
P1은 CLOSED다.**

## 3. 이번에 직접 실행한 19개 반례 (A1~A19) — 요청 항목별

전체 원본 스크립트는 이 검수에서만 임시로 실행했고 저장소에는 남기지 않았다(요청대로
`src`/`tests` 미수정). 아래는 실제 실행 출력을 그대로 옮긴 것이다.

```text
A1  pending-worker-succeeded (must be BLOCKED)
    -> BLOCKED: succeeded run requires terminal execution nodes: n
A2  observer-only pending -> succeeded allowed (expected: succeeds)
    -> NO_EXCEPTION (기대대로 통과)
A3  pending human_gate (must be BLOCKED)
    -> BLOCKED: succeeded run requires terminal execution nodes: hg
A4  pending router (must be BLOCKED)
    -> BLOCKED: succeeded run requires terminal execution nodes: rt
A5  pending verifier (must be BLOCKED)
    -> BLOCKED: succeeded run requires terminal execution nodes: vf
A6  pending platform_gate (must be BLOCKED)
    -> BLOCKED: succeeded run requires terminal execution nodes: pg
A7  unknown node_id in node_status_changed (must be BLOCKED)
    -> BLOCKED: node_status_changed references unknown graph node: ghost
A8  node_statuses map 조작이 run_terminal 검사를 우회하면 안 됨 (must be BLOCKED)
    -> BLOCKED: succeeded run requires terminal execution nodes: w
A9  node_status_changed가 graph와 호환용 map을 함께 갱신하는지
    -> SYNC_OK
A10 동일 node_status_changed 재전송(replay) — 같은 값이면 예외 없이 통과해야 함
    -> REPLAY_ACCEPTED state=ready (기대대로, 아래 §4.1 참고)
A11 terminal node PASSED -> FAILED (must be BLOCKED)
    -> BLOCKED: invalid node transition passed -> failed
A12 pending sibling이 있어도 failed/cancelled terminal은 허용 (기존 의미 보존)
    -> FAILED_TERMINAL_OK w2_state=pending (기대대로)
A13 빈 graph(node 0개) -> succeeded
    -> EMPTY_GRAPH_SUCCEEDED terminal=succeeded   *** 신규 발견, §4.3 ***
A14 run_created 이전에 node_status_changed로 노드를 passed까지 밀어붙이기
    -> NODE_STATUS_BEFORE_RUN_CREATED_ACCEPTED state=passed run_created_applied=False
       *** 신규 발견, §4.4 ***
A15 위 A14의 pre-genesis passed 상태로 그대로 succeeded까지 도달하는지
    -> PRE_GENESIS_PASS_THEN_SUCCEEDED terminal=succeeded   *** 신규 발견, §4.4 ***
A16 human_gate 노드가 verdict_recorded 없이 node_status_changed만으로 passed가
    되어도 succeeded가 통과하는지
    -> GATE_PASSED_NO_VERDICT_SUCCEEDED terminal=succeeded verdicts=[]
       *** 신규 발견, §4.2 ***
A17 유일한 worker node가 failed로 끝나도 run_terminal(succeeded)가 통과하는지
    -> ALL_NODES_FAILED_RUN_SUCCEEDED terminal=succeeded node_state=failed
       *** 신규 발견(P1), §4.1 — 이번 REVISE의 핵심 사유 ***
A18 cancelled 확정 후 두 번째 run_terminal(succeeded) (must be BLOCKED)
    -> BLOCKED: Run terminal status cannot be changed or duplicated
A19 run_terminal(succeeded) 확정 후에도 새 node를 추가하고
    node_status_changed를 계속 적용할 수 있는지
    -> NODE_STATUS_AFTER_TERMINAL_ACCEPTED w2_state=ready   *** 신규 발견, §4.5 ***
```

### 3.1 Fix-5가 스스로 밝힌 세 가지 목표 — 전부 CLOSED로 확인

| Fix-5 목표 (`I02_CORE_FIX5_REPORT_LUNA.md` §3) | 이번 재확인 | 결과 |
|---|---|---|
| pending/nonterminal 실행 node가 있으면 succeeded 거절 | A1, A3~A6 (worker/human_gate/router/verifier/platform_gate 각각) | **CLOSED** |
| observer는 제외 | A2 (observer만 pending이어도 succeeded 통과) | **CLOSED** (제외 정책이 코드와 일치) |
| node_status_changed가 Run.graph와 node_statuses를 같은 순서로 동기화 | A9 (1개 이벤트 후 두 저장소 동시 확인), A8(맵을 직접 조작해도 succeeded 검사는 실제 graph만 봄 — 두 저장소가 분리돼 있지 않다는 뜻) | **CLOSED** |
| failed/cancelled는 기존 의미(중단) 보존, pending이 있어도 허용 | A12 | **CLOSED** |
| 이미 terminal인 Run에 두 번째 terminal 금지 (회귀 없음) | A18 | **CLOSED (회귀 없음)** |
| 존재하지 않는 node를 가리키는 상태 변경은 fail-closed | A7 | **CLOSED** |

## 4. 새로 발견한 항목 (요청받은 adversarial 관점별)

### 4.1 — P1 (신규): "terminal" 검사가 "실패로 끝남"과 "성공으로 끝남"을 구분하지 못한다

- 위치: `src/graphori_core/reducer.py:38-41`의 `_TERMINAL_NODE_STATES`와
  `reducer.py:199-206`의 `_require_execution_nodes_terminal`.
- 재현 (A17):

```python
t = Task('t-af', 'x', run_id='r-af', graph_version=1)
r = Run('r-af', 1)
r.graph.add_node(Node('w', NodeKind.WORKER, 'Worker'))
p = StateReducer(t, r)
p.apply(canonical_event('run_created', ...))
p.apply(canonical_event('graph_published', ...))
for status in ('ready', 'assigned', 'running', 'failed'):
    p.apply(canonical_event('node_status_changed', ..., entity={'node_id': 'w'},
                            payload={'status': status}))
p.apply(canonical_event('run_terminal', ..., payload={'terminal_status': 'succeeded'}))
```

- 실제 결과: `ALL_NODES_FAILED_RUN_SUCCEEDED terminal=succeeded node_state=failed`.
  그래프에 있는 유일한 worker node가 **완전히 실패**했는데도(대체 revision node도
  없고, 다른 어떤 node도 passed 상태가 아닌데도) Run 전체가 "성공"으로 확정된다.
- 근본 원인: `_TERMINAL_NODE_STATES`가 `{passed, failed, cancelled, blocked, rejected,
  inconclusive}`로 정의돼 있다. 즉 "이 node는 더 이상 진행 중이지 않다"만 확인하고,
  "이 node가 실제로 통과(passed)했다"는 확인하지 않는다. Fix-5가 스스로 밝힌 설계
  (`I02_CORE_FIX5_REPORT_LUNA.md` §3: "성공에만 모든 실행 대상 node **terminal**인지
  확인하는 검사를 추가했다")는 정확히 이 정의를 그대로 구현한 것이므로, 코드가
  보고서와 다르게 동작하는 것은 아니다. 문제는 "terminal"이라는 기준 자체가
  "succeeded"의 계약을 지키기에 충분하지 않다는 점이다.
- 왜 이게 revision/rework 설계와 모순되는가: `EVENT_PROTOCOL.md` §4.1은
  `failed -> ready (새 revision만; 같은 node 재실행 금지)`라고 말한다. 즉 어떤 node가
  failed로 끝나면, 원래 취지는 **새 revision node가 만들어져 그것이 다시 passed까지
  가야** 그 작업이 완료된 것이다. 지금 구현은 "실패한 원본 node가 그래프에 그대로
  남아 terminal 상태이기만 하면" 충분하다고 보기 때문에, 대체 revision node가 아예
  없어도(즉 아무도 그 실패를 만회하지 않았어도) succeeded가 통과한다.
- 계약 위반: `EVENT_PROTOCOL.md` §6 "Run은 모든 필수 scope가 terminal이고 gate 조건이
  충족될 때만 succeeded다"와, 이 검수 시리즈 전체(Fix-3→Fix-5, Codex/Claude 4개
  보고서)가 반복해서 요구해 온 "성공 도장은 진짜 성공을 보장해야 한다"는 목적을
  어긴다. "pending node가 있으면 거절"이라는 좁은 조건만 막았을 뿐, "failed node만
  있어도 성공"이라는 훨씬 노골적인 구멍은 그대로 열려 있다.
- Fix-5 범위와의 관계: Fix-5가 명시적으로 겨냥한 것(§3.1의 6개 목표)은 전부
  CLOSED이며, 이 finding은 Fix-5 보고서가 "이번 수정 범위"라고 적은 문장 밖에
  있다. 하지만 이 검수는 Fix-5 하나만이 아니라 "succeeded 판정이 신뢰할 수
  있는가"라는 원래 질문 전체에 답해야 하고, 그 질문 기준으로는 여전히 REVISE가
  맞다.
- Windows: 재현됨(FAIL). macOS: `deferred/unknown`(플랫폼 무관 로직으로 보이나 확인
  전이므로 단정하지 않음).

### 4.2 — P2 (신규, 사전 존재하는 구조적 한계): human_gate가 verdict 없이도 "passed"로 종료될 수 있다

- 재현 (A16): human_gate node를 `node_status_changed`만으로
  `pending -> ready -> assigned -> running -> awaiting_verification -> passed`까지
  이동시켰다. 이 과정에서 `verdict_recorded` 이벤트는 단 한 번도 보내지 않았다
  (`p.verdicts == []`). 그 뒤 `run_terminal(succeeded)`는 그대로 통과했다.
- 원인: `verdict_recorded`가 만드는 `self.verdicts`는 `node_id`와 전혀 연결되지 않은
  단순 리스트다(`reducer.py:290-310`). `_require_execution_nodes_terminal`은
  `node.state`만 보고 `self.verdicts`를 전혀 참조하지 않는다. 따라서 "human_gate가
  실제로 approve 판정을 냈는가"와 "human_gate node의 상태가 passed인가"는 완전히
  분리된 별개의 사실이다.
- 이 구멍은 Fix-5가 새로 만든 것이 아니다. `verdict`와 `node_id`를 잇는 구조는
  Fix-4 이전부터 존재하지 않았고, 4개의 이전 보고서 어디에도 이 연결을 요구하거나
  구현했다는 언급이 없다. `IMPLEMENTATION_PLAN.md`도 "terminal projection" 일치만
  acceptance로 요구하고, verdict-node 연결을 명시하지 않는다. 따라서 이번 REVISE의
  직접 사유로 올리지는 않지만, `EVENT_PROTOCOL.md` §6의 "gate 조건이 충족될 때만"이라는
  문장과 정면으로 어긋나는 잔존 위험이므로 후속 단계에서 반드시 닫아야 한다.

### 4.3 — P3 (신규, 좁은 경계 조건): 실행 대상 node가 0개인 graph는 succeeded를 무조건 통과한다

- 재현 (A13): `Run('r-em', 1)`을 만들고 node를 하나도 추가하지 않은 채
  `run_created -> graph_published -> run_terminal(succeeded)`를 그대로 보내면
  `EMPTY_GRAPH_SUCCEEDED terminal=succeeded`.
- `_execution_nodes`가 빈 튜플을 돌려주므로 "열린 node가 없다"는 조건이 공허하게
  참(vacuously true)이 되어 통과한다.
- 심각도를 P3로 낮게 매긴 이유: reducer의 `apply()`에는 `node_created`/`edge_created`
  이벤트를 처리하는 분기가 아예 없다(§4.6 참고). 즉 이벤트 스트림만으로는 애초에
  Run.graph에 node를 채울 방법이 없고, 지금 graph를 채우는 유일한 경로는 호출자가
  `Run` 객체를 직접 구성할 때뿐이다. 실전에서 `compile_topology`로 만든 그래프는
  router/worker/observer를 최소한으로 포함하므로 이 경계는 현재 컴파일러 경로로는
  발생하지 않는다. 다만 reducer 자체의 계약만 보면 "빈 graph도 성공"이라는 결론이
  명시적으로 막혀 있지 않다는 점은 기록해 둔다.

### 4.4 — P2 (신규): node_status_changed는 run_created/graph_published보다 먼저 와도 막히지 않는다

- 재현 (A14, A15): `run_created`를 전혀 보내지 않은 상태(`_run_created_applied=False`)에서
  `node_status_changed`로 worker node를 `passed`까지 이동시켰다 —
  `NODE_STATUS_BEFORE_RUN_CREATED_ACCEPTED state=passed run_created_applied=False`.
  그 뒤에야 `run_created -> graph_published -> run_terminal(succeeded)`를 보내면
  이미 만들어진 "출발 전 passed" 상태를 그대로 인정해 succeeded가 통과한다 —
  `PRE_GENESIS_PASS_THEN_SUCCEEDED terminal=succeeded`.
- 원인: `_validate_context`의 `lifecycle_event` 판정은 `run_created`,
  `graph_published`, `run_terminal` 세 가지에만 적용된다(`reducer.py:169`).
  `node_status_changed`는 `_run_created_applied`/`_graph_was_published` 여부를
  전혀 확인하지 않는다.
- 이 순서 결함은 Fix-5가 새로 만든 것이 아니라 이전부터 있던 구조다(`node_status_changed`
  분기는 Fix-4에서도 이런 guard가 없었다). 하지만 Fix-5가 "succeeded는 이제
  Run.graph의 실제 상태를 본다"고 신뢰를 높였기 때문에, 그 신뢰의 전제 — "그
  상태는 run이 실제로 시작된 뒤에 쌓인 것이다" — 가 지켜지지 않는다는 점이 이번에
  더 중요해졌다. 다음 단계에서 `node_status_changed`도 `run_created`/
  `graph_published` 이후에만 허용하도록 좁히는 것을 권고한다.

### 4.5 — P3 (신규): Run이 terminal(succeeded)로 확정된 뒤에도 그래프에 새 node를 추가하고 상태를 바꿀 수 있다

- 재현 (A19): worker node를 정상적으로 `passed`까지 이동시키고
  `run_terminal(succeeded)`를 확정한 뒤, 같은 `Run.graph`에 새 node `w2`를
  추가하고 `node_status_changed(w2, ready)`를 보냈더니 예외 없이 통과했다 —
  `NODE_STATUS_AFTER_TERMINAL_ACCEPTED w2_state=ready`.
- `run_terminal` 분기(`reducer.py:251-265`)는 `run.terminal_status`가 이미 있으면
  **`run_terminal` 자체**의 재적용만 막을 뿐, `node_status_changed`가 terminal
  이후에도 계속 graph를 바꾸는 것은 막지 않는다. 즉 "succeeded" 도장을 찍은 뒤에도
  그 도장의 근거였던 graph 스냅샷이 계속 바뀔 수 있다 — 사후 감사(replay) 시
  "그때 succeeded라고 찍은 graph 상태"를 신뢰하기 어렵게 만드는 잔존 위험이다.
  Stage3(JSONL 저장/replay)가 실제로 구현되면 이 문제가 더 커질 수 있으므로 이번에
  기록해 둔다.

### 4.6 — P3 (관찰, 사전 존재): 대부분의 canonical event type이 reducer에서 조용히 무시된다

- `EVENT_TYPES`(`reducer.py:18-25`)에는 `node_created`, `edge_created`, `role_assigned`,
  `assignment_rejected`, `attempt_dispatched`, `heartbeat`, `progress_reported`,
  `worker_finished`, `gate_created`, `gate_resolved`, `usage_recorded`,
  `retry_created`, `stale_marked`, `reconciled`, `duplicate_ignored`,
  `idempotency_conflict`, `event_quarantined`이 전부 포함돼 있어
  `validate_event_envelope`를 통과하지만, `StateReducer.apply()`의 `elif` 체인에는
  이 중 어느 것도 처리 분기가 없다. 즉 이런 이벤트를 보내면 envelope 검사는
  통과하고, 아무 상태도 바뀌지 않은 채 `self`만 반환된다 — 에러도 나지 않고
  거절되지도 않는다.
- Fix-5가 만든 문제는 아니다(Fix-4에서도 동일). I02 portable core의 명시적 범위가
  "lifecycle 순서 + terminal projection"이었으므로 나머지 이벤트 타입의 실제 처리는
  아직 범위 밖일 수 있다. 다만 "unknown event는 거절된다"는 이전 회귀 항목과
  혼동하지 않도록 구분해 기록한다 — 이건 "unknown type"이 아니라 "known type인데
  아무 것도 안 함"이다.

## 5. 이전 라운드 P0/P1 회귀 재확인 (unittest 없이 직접)

기존 24개 테스트가 이 항목들을 이미 담고 있지만, "테스트가 통과했다"만으로 믿지
않기 위해 대표 반례를 §3의 A7, A11, A18에서 직접 재실행했다:

- 존재하지 않는 node 참조 (unknown node fail-closed) — A7 BLOCKED.
- terminal node immutability(passed -> failed) — A11 BLOCKED.
- 이미 terminal인 Run에 두 번째 terminal 금지 — A18 BLOCKED.

Fix-4까지 CLOSED로 확인됐던 나머지 항목(증거 없는 verdict, 권한 위조, identity
독립성 우회, `rework_of` cycle, digest 형식, run_created 순서/버전/중복 등)은
reducer.py의 해당 코드가 이번에도 그대로임을 diff 없는 상태(git이 아직 초기 커밋
전이라 `git diff` 자체가 무의미하지만, `Fix-5 report`가 "기존 event 순서, ID/run
ID/graph version 검사, duplicate 거절, terminal 불변성은 건드리지 않았다"고 명시한
부분)로 확인했고, 24개 unittest 전체 통과로 재확인했다. 이 항목들에서 새로운
회귀는 발견하지 못했다.

## 6. 판정 요약

| 분류 | 내용 | 상태 |
|---|---|---|
| P1 (구) | pending/nonterminal 실행 node가 있어도 succeeded 통과 | **CLOSED** (§2) |
| P1 (신규) | failed로 끝난 유일한 실행 node가 있어도 succeeded 통과 (§4.1) | **OPEN** |
| P2 (신규) | human_gate가 verdict 없이 node 상태만으로 passed 처리돼도 succeeded 통과 (§4.2) | OPEN, 사전 존재, 후속 과제 |
| P2 (신규) | node_status_changed가 run_created/graph_published보다 먼저 와도 막히지 않음 (§4.4) | OPEN, 사전 존재, 후속 과제 |
| P3 (신규) | 실행 node 0개인 빈 graph는 succeeded를 공허하게 통과 (§4.3) | OPEN, 좁은 경계, 현재 컴파일러 경로로는 도달 불가 |
| P3 (신규) | terminal 확정 후에도 node_status_changed로 graph가 계속 바뀜 (§4.5) | OPEN, 사후 감사 위험 |
| P3 (관찰) | 대부분의 canonical event type이 reducer에서 조용히 무시됨 (§4.6) | OPEN, I02 범위 밖으로 보임 |

Fix-5는 스스로 밝힌 목표(pending/nonterminal 거절, graph/map 동기화, failed/cancelled
기존 의미 보존, observer 제외)를 정확히 구현했고, 이번 재공격(A1~A9, A12, A18)에서
전부 CLOSED로 재확인됐다. `LUNA` 보고서의 "24개 테스트 통과 = APPROVE 아님, fresh dual
review 대기" 자세도 정확했다 — 실제로 fresh 독립 검수에서 새 문제가 나왔다.

그러나 §4.1의 신규 P1은 이 검수 시리즈가 Fix-3부터 계속 요구해 온 것과 정확히 같은
종류의 요구("succeeded 도장은 실제 성공을 의미해야 한다")를 다른 경로로 위반한다.
"pending node가 있으면 거절"이라는 조건만으로는 "이미 실패한 node가 있어도 성공"이라는
훨씬 직접적인 반례를 막지 못했다. 이 상태로 `APPROVE`를 주면, Run이 "성공"이라고
기록해도 그 밑의 유일한 작업이 실패했을 수 있다는 사실을 감추게 된다.

권고하는 다음 수정 범위는 좁다: `_TERMINAL_NODE_STATES`를 succeeded 판정에 그대로
재사용하지 말고, succeeded 전용으로 "각 실행 대상 node는 `passed`이거나, 그 node를
`rework_of`로 대체하는 다른 node가 있고 그 대체 체인의 최신 node가 `passed`다"라는
조건으로 좁히거나, 최소한 "하나라도 `failed`/`cancelled`/`rejected`/`inconclusive`인
채로 대체되지 않은 실행 node가 있으면 succeeded를 거절"하는 가드를 추가하면 된다.
§4.2, §4.4는 후속 단계 잔존 위험으로 남기고, §4.3, §4.5, §4.6은 관찰로 기록한다.

VERDICT: REVISE
