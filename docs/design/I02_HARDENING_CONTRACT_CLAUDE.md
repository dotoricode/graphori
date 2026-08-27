# I02 Hardening Contract — Claude 독립 설계안

작성일: 2026-08-09
작성자: Claude — fresh 독립 계약 검증자. Codex가 이번에 작성했을 수도 있는
`I02_HARDENING_CONTRACT_CODEX.md`(또는 동급 문서)를 찾아보지도, 읽지도 않고
`docs/architecture/EVENT_PROTOCOL.md`와 `src/graphori_core/*`, `tests/test_core.py`,
그리고 두 개의 Fix-5 사후 검수 보고서(`I02_CORE_POST_FIX5_REVIEW_CODEX.md`,
`I02_CORE_POST_FIX5_REVIEW_CLAUDE.md`)만 근거로 독립적으로 설계했다.
**이 문서 하나만 새로 썼다. `src/`, `tests/`, `EVENT_PROTOCOL.md`, `docs/PROCESS.md`는
전혀 건드리지 않았다.**

---

## 0. 12살에게 설명하는 요약

Graphori는 "성공 도장"을 함부로 찍지 않으려고 만든 시스템이다. 그런데 두 명의
독립 검수자(Codex, Claude)가 각각 따로 이 시스템을 두드려 보니, 도장을 찍는
방식에 **새로운 구멍 네 개**를 발견했다.

1. **"끝났음"과 "성공했음"을 헷갈림** — 선수 한 명이 완전히 넘어져서 실패했는데도
   "경기가 끝났으니 성공!" 도장을 찍을 수 있었다.
2. **도장을 찍은 뒤에도 기록을 고칠 수 있음** — "성공!" 도장을 찍고 나서도 몰래
   경기 결과판을 다시 만질 수 있었다.
3. **영수증에 적힌 이름과 실제로 바뀐 카드가 다를 수 있음** — 영수증에는
   "유령" 카드를 바꾼다고 적혀 있는데, 실제로는 다른 진짜 카드가 바뀌었다.
4. **팀 명단이 없을 때는 아무 이름이나 만들어서 카드를 만들 수 있음** — 원래는
   "팀 명단에 없는 이름은 카드로 인정하지 않는다"가 목표인데, 명단 자체가 없는
   경우엔 이 규칙이 통째로 사라졌다.

이 문서는 이 네 구멍을 막는 데 필요한 **가장 작은 규칙**을 하나씩 제안하고,
각 규칙이 실제로 막는 공격, 최소 테스트, 그리고 "이 규칙을 넣으면 무엇이
깨지는가"(API 호환성 비용)를 정리한다. 마지막에는 "이 참에 더 고치고 싶은
유혹이 드는 것들" 중 **지금 하면 안 되는 것**도 따로 적었다.

---

## 1. 검증 범위와 방법

읽은 것: `docs/architecture/EVENT_PROTOCOL.md`(전체), `src/graphori_core/models.py`,
`compiler.py`, `reducer.py`(전체, `__init__.py` export 확인 포함),
`tests/test_core.py`(24개 테스트 전체), `docs/verification/I02_CORE_POST_FIX5_REVIEW_CODEX.md`,
`docs/verification/I02_CORE_POST_FIX5_REVIEW_CLAUDE.md`.

읽지 않은 것(의도적): Codex가 이번 라운드에 독립적으로 작성했을 수 있는 동급
"하드닝 계약" 설계 문서. 독립성을 지키기 위해 검색조차 하지 않았다.

방법: 코드를 실행하지 않았고(구현 전 계약 설계 단계이므로), 두 검수 보고서에
기록된 반례(A1~A19, Codex probe 1~6)를 코드를 직접 읽으며 라인 단위로
재확인했다. 아래 각 규칙의 "재현 위치"는 이번에 내가 직접 읽고 확인한
`reducer.py`/`compiler.py` 라인 번호다.

---

## 2. 새 P1 네 개 — 최종 요약표

| # | 이름 | 최초 발견 | 재현 위치 | 상태 |
|---|---|---|---|---|
| P1-A | succeeded와 failed node 모순 | Claude §4.1 (A17) | `reducer.py:38-41`, `199-206` | 이 문서의 R1로 닫음 |
| P1-B | terminal 이후 event 불변성 없음 | Codex P1-1 (Claude A19도 동일 현상) | `reducer.py:251-265`, `266-289` | 이 문서의 R2로 닫음 |
| P1-C | entity/payload node ID 이중 출처 | Codex P1-2 | `reducer.py:274-276` | 이 문서의 R3로 닫음 |
| P1-D | Run 없는 호환 경로의 unknown node 허용 | Codex P1-3 | `reducer.py:266-289`, `compiler.py:521-536` | 이 문서의 R4로 닫음 |

네 규칙은 서로 독립적이다 — 하나를 빼고 나머지 셋만 적용해도 나머지 셋은
여전히 유효하다. 구현 순서는 상관없지만, R2(terminal 불변성)를 먼저 넣으면
R1의 최소 테스트를 작성할 때 "terminal 이후" 케이스와 "terminal 이전" 케이스를
헷갈리지 않게 되므로 R2 → R1 → R3 → R4 순서를 권장한다(순전히 작업 편의,
계약상 순서 요구사항은 아니다).

---

## 3. R1 — succeeded는 "안 끝남이 없음"이 아니라 "전부 passed"를 뜻해야 한다

### 3.1 문제

`_TERMINAL_NODE_STATES`(`reducer.py:38-41`)는 `{passed, failed, cancelled, blocked,
rejected, inconclusive}`다. `_require_execution_nodes_terminal`(`reducer.py:199-206`)은
이 집합에 **속하기만 하면** 통과시킨다. 즉 "이 node가 더 이상 진행 중이 아니다"만
확인하고 "이 node가 실제로 통과했다"는 확인하지 않는다.

### 3.2 반례 (Claude A17을 그대로 재확인)

worker node 하나짜리 그래프에서 `ready → assigned → running → failed`까지
보낸 뒤 `run_terminal(succeeded)`를 보내면 **현재 코드는 통과시킨다**.
유일한 실행 대상이 완전히 실패했는데 Run은 "성공"으로 확정된다.

### 3.3 규칙 R1

> **succeeded 판정은 observer를 제외한 모든 실행 node가 정확히 `passed`일 것을
> 요구한다.** `failed`/`cancelled`/`blocked`/`rejected`/`inconclusive`는 더 이상
> "성공 판정에 쓸 수 있는 terminal"이 아니다. 이 다섯 상태는 여전히 "진행 중이
> 아님"을 뜻하는 유효한 terminal 상태이지만, **succeeded의 전제 조건에서는
> 제외**한다.
>
> 다른 `terminal_status`(`failed`, `cancelled`, `rejected`, `blocked`,
> `inconclusive`)는 지금처럼 node 상태와 무관하게 통과한다 — 이건 "중단"이지
> "완주 판정"이 아니기 때문이다. 이 비대칭이 핵심이다: **오직 succeeded만
> node 단위로 엄격하게 검증하고, 나머지 terminal_status는 "언제든 중단할 수
> 있다"는 기존 abort semantics를 그대로 유지한다.**

### 3.4 상태전이표 — succeeded 판정 입력/출력

| Run.terminal_status 요청 | 실행 node 상태 | 결과 |
|---|---|---|
| succeeded | 전부 `passed` | 허용 |
| succeeded | 하나라도 `failed` | 거부 (StateTransitionError) |
| succeeded | 하나라도 `cancelled`/`blocked`/`rejected`/`inconclusive` | 거부 |
| succeeded | 하나라도 `pending`/`ready`/.../`stale`/`outcome_unknown` (비terminal) | 거부 (기존 Fix-5 동작 유지) |
| failed | 무관 (pending도 허용) | 허용 (기존 abort semantics 유지) |
| cancelled | 무관 | 허용 (기존 abort semantics 유지) |
| rejected / blocked / inconclusive | 무관 | 허용 (failed/cancelled과 동일하게 abort류로 취급) |

### 3.5 최소 테스트

```python
def test_run_succeeded_rejects_failed_execution_node(self):
    task = Task("t-af", "x", run_id="r-af", graph_version=1)
    run = Run("r-af", graph_version=1)
    run.graph.add_node(Node("w", NodeKind.WORKER, "Worker"))
    reducer = StateReducer(task, run)
    reducer.apply(self.event("run_created", run_id="r-af", task_id="t-af", actor="router", seq=1))
    reducer.apply(self.event("graph_published", run_id="r-af", task_id="t-af", actor="router", seq=2))
    for seq, status in enumerate(("ready", "assigned", "running", "failed"), start=3):
        reducer.apply(self.event("node_status_changed", run_id="r-af", task_id="t-af",
                                  actor="worker", seq=seq, entity={"node_id": "w"},
                                  payload={"status": status}))
    with self.assertRaises(StateTransitionError):
        reducer.apply(self.event("run_terminal", run_id="r-af", task_id="t-af", actor="router",
                                  seq=7, payload={"terminal_status": "succeeded"}))
    self.assertIsNone(run.terminal_status)  # 거부됐으니 여전히 미확정
```

기존 `test_failed_and_cancelled_run_terminal_preserve_abort_semantics`는 그대로
통과해야 한다(변경 없음) — 이 테스트가 정확히 "failed/cancelled terminal은 node
상태 무관하게 허용된다"를 확인하고 있으므로, R1이 이 회귀를 만들지 않는다는
증거로 재사용할 수 있다.

### 3.6 API 호환성 비용

- **행동 축소(narrowing)**: 이전에는 통과하던 `run_terminal(succeeded)` 호출 중
  일부가 이제 `StateTransitionError`를 던진다. 이건 의도된 비용이다 — "성공
  도장이 실제 실패를 가릴 수 있다"는 안전 결함을 막는 대가다.
- 시그니처 변경 없음. 새 예외 타입 없음(기존 `StateTransitionError` 재사용).
- 에러 메시지를 "not terminal"에서 "not passed"로 구분해 원인을 명확히 하는
  걸 권장하지만, 필수는 아니다.
- **알려진 결합 위험 (지금 발생하지 않음, 문서로만 남김)**: `compiler.py`의
  `RevisionController`(`revise → 새 revision worker node + rework_of edge`)가
  만드는 그래프를 그대로 `Run.graph`에 연결해 사용하는 호출자가 미래에 생기면,
  실패한 원본 node가 그래프에 영원히 남아 `passed`가 될 수 없으므로 Run이
  영원히 succeeded에 도달하지 못하는 교착이 생길 수 있다. **현재 코드에서는
  `compile_topology`도 `RevisionController`도 `Run`/`StateReducer`를 참조하지
  않으므로 이 시나리오는 오늘 어떤 실행 경로로도 발생하지 않는다.** R1은 이
  결합을 지금 처리하지 않는다(§6 "지나친 확장" 참고) — 나중에 revision 그래프를
  Run에 연결하는 기능을 추가할 때, succeeded 판정이 `rework_of` 체인의 최신
  head node만 보도록 확장해야 한다는 점을 계약 문서에 남겨 둔다.

---

## 4. R2 — terminal Run은 닫힌 장부다: 그 이후 어떤 event도 상태를 바꾸지 못한다

### 4.1 문제

`run_terminal` 분기(`reducer.py:251-265`)는 **두 번째 `run_terminal`**만 막는다.
`node_status_changed`(`reducer.py:266-289`), `verdict_recorded`(`290-310`),
`platform_verdict_recorded`(`311-333`)는 `self.run.is_terminal` 여부를 전혀
확인하지 않는다.

### 4.2 반례 (Codex P1-1 / Claude A19 재확인)

worker node를 `passed`까지 정상적으로 이동시키고 `run_terminal(succeeded)`를
확정한 뒤, 같은 reducer에 `node_status_changed(worker, "ready")`를 보내면
**예외 없이 통과**하고 `Run.graph.nodes["worker"].state`가 `ready`로 되돌아간다.
"성공" 도장을 찍은 근거였던 그래프 스냅샷 자체가 사후에 바뀐다.

### 4.3 규칙 R2

> **`self.run.is_terminal`이 참이면, `apply()`는 어떤 event type이 오더라도 상태를
> 바꾸지 않고 즉시 `StateTransitionError`를 던진다.** 이미 `run_terminal` 자체를
> 막는 개별 가드(run_created/graph_published/run_terminal 각 분기)가 있지만,
> 이번 규칙은 **`apply()` 최상단 한 곳**에 두는 걸 권장한다 — node_status_changed
> 하나만 막고 나면 내일 누군가 `attempt_dispatched`나 `usage_recorded` 처리
> 분기를 새로 추가하면서 이 가드를 또 깜빡할 수 있기 때문이다(실제로 지금
> `verdict_recorded`, `platform_verdict_recorded`가 정확히 그렇게 깜빡한
> 상태다). 한 곳에 규칙을 두면 "새 분기를 추가할 때마다 terminal 가드를
> 기억해야 한다"는 부담이 사라진다.
>
> 예외는 두지 않는다. terminal 이후에 오는 모든 event(중복 lifecycle event
> 포함)는 거부다. "같은 값으로의 idempotent replay는 봐줘야 하지 않냐"는
> 반론은 §7에서 다룬다 — reducer 계층에는 이미 반영된 이벤트를 식별할 방법이
> 없으므로(그건 writer의 책임, EVENT_PROTOCOL §7) reducer가 "이건 그냥
> replay니까 괜찮아"라고 판단할 근거가 없다. fail-closed가 맞다.

### 4.4 상태전이표

| Run.terminal_status | 들어온 event type | 결과 |
|---|---|---|
| `None` (미확정) | 아무 타입 | 기존 규칙대로 처리 (변경 없음) |
| 확정됨 (`succeeded`/`failed`/`cancelled`/`rejected`/`blocked`/`inconclusive`) | `node_status_changed` | 거부 (신규) |
| 확정됨 | `verdict_recorded` | 거부 (신규) |
| 확정됨 | `platform_verdict_recorded` | 거부 (신규) |
| 확정됨 | `run_created`/`graph_published`/`run_terminal` | 거부 (기존 개별 가드와 동일 결과, 메시지만 통일) |

### 4.5 최소 테스트

```python
def test_terminal_run_rejects_further_node_mutation(self):
    task = Task("t-term", "x", run_id="r-term", graph_version=1)
    run = Run("r-term", graph_version=1)
    run.graph.add_node(Node("w", NodeKind.WORKER, "Worker"))
    reducer = StateReducer(task, run)
    reducer.apply(self.event("run_created", run_id="r-term", task_id="t-term", actor="router", seq=1))
    reducer.apply(self.event("graph_published", run_id="r-term", task_id="t-term", actor="router", seq=2))
    for seq, status in enumerate(("ready", "assigned", "running", "awaiting_verification", "passed"), start=3):
        reducer.apply(self.event("node_status_changed", run_id="r-term", task_id="t-term",
                                  actor="worker", seq=seq, entity={"node_id": "w"}, payload={"status": status}))
    reducer.apply(self.event("run_terminal", run_id="r-term", task_id="t-term", actor="router",
                              seq=8, payload={"terminal_status": "succeeded"}))
    with self.assertRaises(StateTransitionError):
        reducer.apply(self.event("node_status_changed", run_id="r-term", task_id="t-term",
                                  actor="worker", seq=9, entity={"node_id": "w"}, payload={"status": "ready"}))
    self.assertEqual(run.graph.nodes["w"].state, NodeState.PASSED)  # 되돌아가지 않음
```

### 4.6 API 호환성 비용

- 행동 축소. terminal 이후에도 계속 event를 흘려보내던(예: 늦게 도착한
  heartbeat/progress를 무시하지 않고 그냥 넘기던) 호출자는 이제 예외를 받는다.
  이건 정확히 원하는 결과다 — 다만 **호출자가 "terminal 이후 event는 정상적으로
  발생할 수 있다"고 가정하고 있었다면, 그 호출자는 예외를 잡아서 로그만 남기고
  무시하도록 바꿔야 한다.** 이 문서는 그 책임을 reducer 밖(예: writer 또는
  orchestrator)으로 넘기라고 명시적으로 권한다 — reducer는 여전히 fail-closed를
  지키고, "terminal 이후 늦게 도착한 event를 어떻게 조용히 버릴지"는 별도
  계층의 정책이다.
- `verdict_recorded`/`platform_verdict_recorded`도 같은 가드를 받으므로,
  현재 테스트 중 이 두 이벤트를 terminal 이후에 보내는 테스트는 없다 —
  회귀 없음.

---

## 5. R3 — node ID의 단일 출처는 `entity.node_id`다

### 5.1 문제

`reducer.py:274-276`:

```python
entity = _mapping(event["entity"], "entity")
node_id = payload.get("node_id", entity.get("node_id"))
node_id = _nonempty_string(node_id, "node_id")
```

`payload.get("node_id", ...)`가 `entity.get("node_id")`보다 **먼저** 선택된다.
즉 `payload.node_id`가 있으면 `entity.node_id`는 완전히 무시된다.

### 5.2 반례 (Codex probe 4.2-5 재확인)

그래프에 `worker`만 있는 상태에서 `entity.node_id="ghost"`,
`payload.node_id="worker"`, `status="ready"`를 보내면 **event는 거부되지 않고
"worker" node가 `ready`로 바뀐다.** envelope을 읽는 사람은 "ghost가 바뀌었다"고
생각하지만 실제로 바뀐 건 worker다 — entity가 사건의 진짜 대상을 가리키지
못한다.

### 5.3 규칙 R3

> **`entity.node_id`가 유일한 canonical 출처다.** `node_status_changed`는
> `entity.node_id`가 비어있지 않은 문자열일 것을 요구한다(현재도 이미 다른
> 경로로 요구되긴 하지만 명시적으로 우선순위를 고정한다). `payload.node_id`는
> **선택 필드**로 남겨두되, 존재한다면 `entity.node_id`와 **정확히 같아야** 한다.
> 다르면 거부한다. `payload.node_id`가 아예 없으면 그냥 `entity.node_id`를
> 쓴다.
>
> 이 규칙은 "payload에 node_id를 아예 못 넣게 금지"하는 더 엄격한 대안보다
> 약간 관대하다 — 일부 producer가 편의상 payload에도 ID를 중복 기입하는
> 관행이 있을 수 있기 때문이다. 하지만 **불일치는 절대 조용히 넘어가지
> 않는다.**

### 5.4 결정표

| `entity.node_id` | `payload.node_id` | 결과 |
|---|---|---|
| `"worker"` | (없음) | 허용, `worker` 사용 |
| `"worker"` | `"worker"` | 허용, `worker` 사용 |
| `"worker"` | `"ghost"` | 거부 (불일치) |
| (없음/빈 문자열) | 아무 값 | 거부 (entity.node_id 필수) |

### 5.5 최소 테스트

```python
def test_node_status_changed_rejects_entity_payload_node_id_mismatch(self):
    task = Task("task-node", "run", run_id="run-node", graph_version=1)
    run = Run("run-node", graph_version=1)
    run.graph.add_node(Node("worker", NodeKind.WORKER, "Worker"))
    reducer = StateReducer(task, run)
    reducer.apply(self.event("run_created", run_id="run-node", task_id="task-node", actor="router", seq=1))
    reducer.apply(self.event("graph_published", run_id="run-node", task_id="task-node", actor="router", seq=2))
    with self.assertRaises(StateTransitionError):
        reducer.apply(self.event("node_status_changed", run_id="run-node", task_id="task-node",
                                  actor="worker", seq=3, entity={"node_id": "ghost"},
                                  payload={"node_id": "worker", "status": "ready"}))
    self.assertEqual(run.graph.nodes["worker"].state, NodeState.PENDING)  # 안 바뀜
```

### 5.6 API 호환성 비용

- `entity.node_id`를 아예 안 보내고 `payload.node_id`만 보내던 호출자가
  있다면 이제 거부된다. `test_core.py`를 보면 24개 테스트 전부 이미
  `entity={"node_id": ...}` 형태로 호출하고 있어(예: `test_reducer_node_status_uses_transition_guard`,
  `test_node_status_changed_updates_canonical_run_graph`) 기존 테스트 스위트에
  대한 영향은 없다.
- `payload.node_id`를 중복 기입하되 항상 `entity.node_id`와 같은 값을 쓰던
  호출자는 영향 없음.
- **관련 관찰 (이번 P1-C에는 포함하지 않음)**: 같은 "이중 출처" 패턴이
  `platform_verdict_recorded`(`reducer.py:312`)에도 있다 —
  `payload.get("platform", event.get("platform"))`가 봉투 최상위 `platform`
  필드와 payload를 같은 방식으로 섞는다. 이번 계약은 `node_id`만 다룬다고
  명시적으로 범위를 좁혔으므로(§6 참고) `platform` 필드는 후속 검토 항목으로만
  남긴다.

---

## 6. R4 — Run 없는 호환 경로는 node 신원을 보증할 수 없으므로, `node_status_changed`를 아예 받지 않는다

### 6.1 문제

`StateReducer(Task(...))`처럼 `run=None`으로 생성하면 `self.run.graph.nodes`가
없다. `node_status_changed`(`reducer.py:266-289`)의 unknown-node 검사는
`if self.run is not None:` 블록 안에서만 이뤄진다 — `run`이 없으면 아무 검사도
없이 `transition_node(self.node_statuses, node_id, status)`
(`compiler.py:521-536`)로 직행한다. `transition_node`는 `statuses.get(node_id,
NodeState.PENDING)`으로 **모르는 node_id를 즉석에서 PENDING으로 만들어낸다**.

### 6.2 반례 (Codex probe 4.2-6 재확인)

```python
reducer = StateReducer(Task("t-no-run", "probe"))  # run=None
reducer.apply(canonical_event("node_status_changed", entity={"node_id": "ghost"},
                              payload={"status": "ready"}))
# ACCEPT_OK — "ghost"라는 이름은 어디에도 선언된 적이 없는데 카드가 생겨난다.
```

### 6.3 규칙 R4 — 그리고 왜 "가짜 명단을 만드는" 대안을 쓰지 않았는가

> **`self.run is None`이면 `node_status_changed`는 무조건 거부한다.** "Run 없이도
> node 상태를 옮길 수 있다"는 현재의 호환 기능 자체를 없앤다.
>
> 대안으로 "`run`이 없어도 `node_created` 이벤트로 알려진 node 목록을 따로
> 쌓아두자"는 방법을 검토했지만 채택하지 않았다. 이유는 두 가지다.
>
> 1. **오늘 코드에는 `node_created`를 처리하는 분기가 아예 없다**
>    (`reducer.py:18-25`의 `EVENT_TYPES`에는 있지만 `apply()`의 `elif` 체인에는
>    없음 — Claude §4.6 관찰과 동일). `Run`이 있는 정상 경로에서도 마찬가지로
>    node 목록은 `node_created` event replay가 아니라 **호출자가 `Run.graph`를
>    미리 채워서** 얻는다(`compile_topology`가 대표적 예). 즉 "이벤트로 node
>    인벤토리를 새로 만드는" 기능은 Run 경로에도 없는 기능이다. Run 없는
>    경로에만 그 기능을 새로 얹으면, 오히려 두 경로(Run 있음/없음)가 서로
>    다른 방식으로 node 인벤토리를 관리하게 되어 "일관된 규칙"이라는 이번
>    설계 목표에 어긋난다.
> 2. Run 없는 경로가 애초에 어떤 용도로 쓰이는지 코드/문서 어디에도 명시돼
>    있지 않다. 유일한 근거는 `tests/test_core.py`의
>    `test_reducer_node_status_uses_transition_guard`뿐이며, 이 테스트의
>    이름과 내용을 보면 **의도는 "NODE_TRANSITIONS 상태 기계 가드가 정상
>    동작하는지"를 확인하는 것**이지 "임의 문자열을 node로 인정해야 한다"가
>    아니다. 같은 상태 기계 가드는 `compiler.transition_node`를 직접 호출하는
>    `test_node_state_table_and_terminal_immutability`에서 **Run/StateReducer
>    없이 이미 독립적으로 검증되고 있다.** 따라서 R4가 이 한 테스트를
>    깨뜨려도, 그 테스트가 지키려던 실제 가치(전이 가드 자체)는 다른 테스트가
>    이미 담보한다 — 최소 비용으로 닫을 수 있는 구멍이라는 뜻이다.

### 6.4 결정표

| `self.run` | node_status_changed | 결과 |
|---|---|---|
| `Run` 있음, node가 graph에 존재 | 유효한 상태 전이 | 허용 (기존과 동일) |
| `Run` 있음, node가 graph에 없음 | 아무 상태 | 거부 (기존과 동일, Fix-5부터 이미 막혀 있음) |
| `Run` 없음 (`None`) | 아무 상태, 아무 node_id | **거부 (신규 — 기존엔 허용)** |

### 6.5 최소 테스트

```python
def test_node_status_changed_requires_run(self):
    reducer = StateReducer(Task("t-no-run", "probe"))  # run=None
    with self.assertRaises(StateTransitionError):
        reducer.apply(self.event("node_status_changed", payload={"status": "ready"},
                                  entity={"node_id": "ghost"}))
```

기존 `test_reducer_node_status_uses_transition_guard`는 R4 적용 시 **깨진다.**
이 테스트는 그대로 두지 말고, `Run`을 명시적으로 만들어 같은 전이 순서를
검증하도록 다시 써야 한다(구현 단계의 작업이며, 이 계약 문서는 소스/테스트를
수정하지 않는다는 지시에 따라 여기서는 수정하지 않는다).

### 6.6 API 호환성 비용 — 이 규칙이 네 개 중 가장 비싸다

- **기존 테스트 하나가 명시적으로 깨진다**
  (`test_reducer_node_status_uses_transition_guard`). 이건 이 문서의 다른 세
  규칙과 다른 점이다 — R1/R2/R3는 기존 24개 테스트를 그대로 통과시키면서
  새 반례만 막지만, R4는 **기존에 의도적으로 통과하도록 짜인 테스트 하나를
  깨야만** 구멍을 닫을 수 있다. 구현 담당자는 이 테스트를 "Run을 만들어서
  같은 전이 순서를 검증"하는 형태로 다시 써야 하고, 그 리라이트가 이번
  하드닝 작업의 일부여야 한다.
- Run 없이 reducer를 쓰던 모든 실제 호출자(오늘은 테스트 코드가 유일하게
  확인된 사용처)는 이제 반드시 `Run` 객체를 만들어서 넘겨야 한다. `Run`을
  최소로 만드는 비용은 `Run(run_id, graph_version)` 생성자 호출 한 줄이라
  크지 않다.
- `verdict_recorded`, `platform_verdict_recorded`는 애초에 `node_id`를 참조하지
  않으므로 Run 없이도 계속 동작한다 — R4는 `node_status_changed` 분기 하나에만
  적용된다.

---

## 7. 나머지 필수 항목 — P1 네 개는 아니지만 반드시 다뤄야 하는 것들

### 7.1 빈 graph

`_execution_nodes`가 빈 튜플을 돌려주면 "열린 node가 없다"는 조건이 공허하게
참이 되어 `run_terminal(succeeded)`가 통과한다(Codex P2-1 / Claude §4.3).

**규칙 R5(권장, P2)**: succeeded는 `_execution_nodes(run)`이 최소 1개 이상을
요구한다. 0개면 `StateTransitionError`.

```text
if status is TerminalStatus.SUCCEEDED:
    nodes = self._execution_nodes(run)
    if not nodes:
        raise StateTransitionError("succeeded run requires at least one execution node")
    self._require_execution_nodes_terminal(run)  # R1 강화판
```

12살 요약: 아무도 뛰지 않은 경주에 "우승!" 도장을 찍을 수는 없다.

이걸 P1이 아니라 P2로 두는 이유: 오늘 이 상태에 도달하는 유일한 방법은
호출자가 `Run.graph`에 node를 하나도 안 넣고 직접 `Run` 객체를 만드는
것뿐이다(§4.6 관찰과 동일 — `node_created` event로 그래프를 채우는 경로가
없다). `compile_topology`는 항상 최소 router+worker+observer를 만들므로
실전 경로에서는 도달 불가능하다. 그래도 reducer 자체의 계약만 보면 명시적
방어가 없으므로 닫는 걸 권한다 — 비용이 세 줄짜리 가드라 저렴하다.

**지나친 확장 경고**: "빈 run을 명시적으로 허용하려면 `run_terminal` payload에
`empty_scope: true` 같은 새 필드를 추가하자"는 유혹이 들 수 있다. **하지
말 것을 권한다.** 오늘 그런 유스케이스가 실제로 필요하다는 근거(코드, 테스트,
EVENT_PROTOCOL 문장 어디에도)가 없다. 필요해지면 그때 스키마를 확장해도
늦지 않다.

### 7.2 observer와 모든 NodeKind — succeeded 판정에서의 취급표

| NodeKind | succeeded에 필요한 상태 (R1 적용 후) | 근거 |
|---|---|---|
| `router` | `passed` | `_execution_nodes`는 observer만 제외하므로 router도 실행 대상 |
| `worker` | `passed` | 동일 |
| `verifier` | `passed` (verifier **자신의 실행**이 끝났다는 뜻이지, 그 verifier가 낸 verdict 내용과는 별개 — §7.4 참고) | 동일 |
| `human_gate` | `passed` (node 상태일 뿐, 실제 `approve` verdict가 있었는지는 별개 — §7.4 참고) | 동일 |
| `platform_gate` | `passed` | 동일 |
| `observer` | 무관 — succeeded 판정에서 완전히 제외 | `_execution_nodes`가 명시적으로 제외(`reducer.py:187-197`), Fix-5부터 확정된 설계이며 이번 계약에서 변경하지 않음 |

### 7.3 failed/cancelled/rejected/blocked/inconclusive의 Run 레벨 의미

| `TerminalStatus` | node 상태 요구사항 | 의미 |
|---|---|---|
| `succeeded` | 전 실행 node `passed` (R1) + 최소 1개 이상 (R5) | "실제로 다 통과했다" |
| `failed` | 없음 (기존 abort semantics 유지) | "진행 중에 중단했고, 이유는 실패다" — 중간에 pending node가 남아 있어도 됨 |
| `cancelled` | 없음 | "누군가 의도적으로 멈췄다" |
| `rejected` | 없음 (신규 명시, 기존 코드는 이미 이렇게 동작함) | "gate가 이 Run 자체를 거부했다" — 예: human_gate가 승인하지 않고 전체를 reject |
| `blocked` | 없음 | "외부 자원/승인 문제로 더 진행 불가" |
| `inconclusive` | 없음 | "판단할 증거가 부족해서 끝냈다" |

이 표의 핵심 판단: **오직 succeeded만 "완주 증명"이 필요하고, 나머지 다섯
`terminal_status`는 전부 "중단 계열"이라 node 상태를 요구하지 않는다.** 이건
새로 만든 구분이 아니라 현재 코드(`reducer.py:262-264`에서 `if status is
TerminalStatus.SUCCEEDED:`일 때만 검사)가 이미 암묵적으로 따르고 있는 설계를
R1을 적용한 뒤에도 그대로 유지하겠다는 뜻이다.

### 7.4 verdict와 node 상태의 연결 (P2, 관찰 — 이번 4개 P1에는 포함하지 않음)

Claude §4.2가 발견한 것: `human_gate` node가 `node_status_changed`만으로
`passed`까지 이동할 수 있고, 그 사이 `verdict_recorded(actor="human_gate",
verdict="approve")`가 단 한 번도 없어도 succeeded가 통과한다. 원인은
`self.verdicts`(verdict_recorded가 쌓는 리스트, `reducer.py:290-310`)가
`node_id`와 전혀 연결되지 않은 단순 배열이기 때문이다. `verifier`와
`platform_gate`도 구조적으로 동일한 문제를 갖는다 — `platform_verdict_recorded`가
쌓는 `self.platform_verdicts`도 특정 node_id를 가리키지 않는다.

**이번 계약이 이 항목을 P1로 올리지 않는 이유**: 두 검수 보고서 모두 이걸
"Fix-5 이전부터 있던 구조"라고 확인했고, `IMPLEMENTATION_PLAN.md`나
`EVENT_PROTOCOL.md` 어디에도 "verdict가 특정 node_id에 귀속돼야 한다"는 문장이
명시돼 있지 않다(§6의 "terminal이고 gate 조건이 충족될 때만"이라는 문장은
있지만 그 "gate 조건"이 정확히 어떤 데이터로 판정되는지는 명시하지 않음).
새 P1로 만들려면 **먼저 계약 문서(EVENT_PROTOCOL.md)에 "verdict는 node_id에
귀속된다"는 문장이 필요하고, 그건 이번 하드닝 계약이 아니라 EVENT_PROTOCOL
자체의 스키마 확장**이다.

**권장 후속 작업(P2, 지금 하지 않음)**: `Verdict.node_id: str | None` 필드를
추가하고, `verdict_recorded`가 `entity.node_id`를 받아 `self.verdicts`에
`(node_id, verdict)` 쌍으로 저장하도록 하고, succeeded 판정 시 `human_gate`/
`verifier` 종류의 node는 "상태가 passed"뿐 아니라 "그 node_id로 기록된
verdict가 pass/approve"까지 요구하도록 확장한다. 이건 R1보다 스키마 변경
폭이 크므로(payload/entity 스키마에 새 필드 추가, EVENT_PROTOCOL.md 수정
필요) 이번 계약에서는 **의도적으로 범위 밖에 둔다.**

### 7.5 관찰: `NodeState.REJECTED`는 현재 도달 불가능하다

`compiler.py:500-518`의 `NODE_TRANSITIONS`를 값(target) 기준으로 훑어보면
`NodeState.REJECTED`를 target으로 갖는 전이가 **하나도 없다**
(`RUNNING → {AWAITING_VERIFICATION, FAILED, CANCELLED, STALE, OUTCOME_UNKNOWN,
BLOCKED}`, `AWAITING_VERIFICATION → {PASSED, FAILED, INCONCLUSIVE, BLOCKED}` 등
어디에도 `REJECTED`가 없음). 그런데 `reducer.py:38-41`의 `_TERMINAL_NODE_STATES`는
`REJECTED`를 마치 도달 가능한 것처럼 포함하고 있다.

이건 이번 4개 P1에 속하지 않는 **별개의 사전 존재 결함**이다(R1이 요구하는
"전부 passed" 규칙에서는 애초에 REJECTED가 목록에 있든 없든 succeeded 판정에
영향이 없으므로 R1과 충돌하지 않는다). 기록만 해 둔다: `EVENT_PROTOCOL.md`의
`node_status` enum에는 `rejected`가 있지만, 실제로 그 값에 도달하는 전이가
설계돼 있지 않다. `AWAITING_VERIFICATION → REJECTED`(verifier의 `reject`
verdict에 대응) 같은 전이를 추가할지는 이번 계약의 범위가 아니다.

### 7.6 replay/order/id/version/digest — I02(reducer)와 I03(writer)의 책임 경계

Codex P2-2가 정확히 짚은 것: `validate_event_envelope`(`reducer.py:64-103`)는
`digest`/`prev_digest`의 **모양**(정규식)만 검사하고, seq 단조 증가, 같은
`event_id`/`producer_event_id`의 중복 반영 방지, digest 체인의 실제 연결은
검사하지 않는다. 같은 heartbeat 객체를 두 번 넣거나, `seq=9` 다음에 `seq=1`을
넣거나, 같은 `event_id`에 다른 payload를 넣어도 reducer는 막지 않는다.

**이번 계약이 명시하는 경계**:

| 책임 | 담당 | 근거 |
|---|---|---|
| envelope 필드 존재/타입/모양(정규식) 검사 | reducer (I02), `validate_event_envelope` | 이미 구현됨 |
| node/task/run 상태 전이가 계약을 지키는지 (R1~R5 포함) | reducer (I02), `StateReducer.apply` | 이 문서의 범위 |
| seq 단조 증가, `event_id`/`producer_event_id` 중복 제거, digest 체인 연결(`prev_digest`가 실제 이전 event의 `digest`와 같은지) | **writer (I03, single writer, EVENT_PROTOCOL §7)** | `EVENT_PROTOCOL.md` §7: "writer가 monotonic seq, prev_digest, digest를 붙인다", "같은 producer_event_id 또는 event_id는 한 번만 반영한다" |
| 손상된 tail quarantine, tmp→ready rename 원자성 | writer (I03) | `EVENT_PROTOCOL.md` §7.6 |

**결론**: replay/순서/중복 방지는 이번 4개 P1에 포함되지 않는다 — reducer가
"이미 신뢰할 수 있게 정렬되고 중복 제거된 event 스트림"을 받는다고 가정하는
것이 I02의 명시적 전제이고, 그 전제를 실제로 지키는 건 아직 존재하지 않는
Stage 3 writer(I03)의 몫이다. **이번 계약에서 reducer에 seq/중복 검사를
추가하는 건 지나친 확장이다** — writer가 없는 상태에서 reducer에 부분적인
중복 방지를 넣으면, "reducer만 쓰면 안전하다"는 잘못된 인상을 주고, 나중에
진짜 writer가 붙었을 때 두 계층에서 서로 다른 규칙으로 중복을 판정하는
불일치 위험만 늘어난다.

---

## 8. 지나친 확장 목록 — 이번에 하지 말아야 할 것

1. **R1을 확장해서 `rework_of` 체인 자동 대체 판정을 구현하는 것** (§3.6) —
   오늘 어떤 코드 경로도 `RevisionController`가 만든 그래프를 `Run`에
   연결하지 않는다. 지금 만들면 쓰이지 않는 그래프 순회 로직만 늘어난다.
2. **Run 없는 경로를 위해 `node_created` 기반 섀도 인벤토리를 새로 만드는
   것** (§6.3) — Run 있는 경로도 `node_created`로 그래프를 채우지 않으므로,
   Run 없는 경로에만 그 기능을 얹으면 두 경로가 서로 다른 규칙을 갖게 된다.
   대신 R4처럼 그 경로 자체를 없애는 게 더 작고 일관된 규칙이다.
3. **빈 graph 문제를 payload 스키마 확장(`empty_scope` 플래그)으로 푸는 것**
   (§7.1) — 실제 유스케이스 없이 스키마부터 늘리지 않는다.
4. **verdict-node 연결을 이번 계약에서 구현하는 것** (§7.4) — 이건
   `EVENT_PROTOCOL.md` 스키마 확장이 선행돼야 하는 별도 작업이다.
5. **reducer에 seq 단조성/중복 event 검사를 추가하는 것** (§7.6) — 이건
   I03 writer의 책임이고, reducer에 일부만 넣으면 두 계층이 서로 다른 규칙을
   갖게 된다.
6. **`NodeState.REJECTED` 도달 전이를 이번에 추가하는 것** (§7.5) — 관찰로만
   남기고, 실제 verdict→node 상태 연결(§7.4)이 설계된 뒤에 함께 다루는 게
   맞다. 지금 따로 손대면 verdict 연결과 두 번 겹치는 변경이 된다.
7. **R2의 terminal 가드를 `run`이 없는 경우까지 확장하는 것** — R2는
   `self.run.is_terminal`을 전제로 한다. `run=None`인 reducer는애초에 R4로
   `node_status_changed` 자체가 막히므로, "terminal 개념이 없는 Task-only
   reducer에 별도의 terminal 가드를 만드는" 작업은 불필요하다.

---

## 9. 네 개 P1을 모두 닫는 최소 변경 요약

| 규칙 | 파일:위치 | 변경 크기 | 기존 테스트 영향 |
|---|---|---|---|
| R1 | `reducer.py:38-41` (`_TERMINAL_NODE_STATES` 대신 succeeded 전용 `{PASSED}` 체크), `199-206` | 한 상수/조건 교체 | 없음 (기존 24개 그대로 통과) |
| R2 | `reducer.py:215` `apply()` 최상단에 `is_terminal` 가드 한 줄 | 가드 1개 | 없음 |
| R3 | `reducer.py:274-276` node_id 선택 순서를 entity 우선 + 불일치 거부로 교체 | 조건 2~3줄 | 없음 |
| R4 | `reducer.py:266-289` node_status_changed 분기 시작 부분에 `if self.run is None: raise` | 가드 1줄 | **`test_reducer_node_status_uses_transition_guard` 1개 리라이트 필요** |

R1~R3는 기존 24개 테스트를 하나도 깨지 않고 새 반례만 막는다. R4만
유일하게 기존 테스트 하나의 의도(재작성)를 요구하며, 그 이유와 대안 부재는
§6.3에 명시했다. 넷 다 각각 3~5줄 이내의 국소 변경이며, 서로 다른 코드
블록을 건드리므로 병렬로 구현해도 충돌하지 않는다.

VERDICT(이 계약 문서 자체에 대한 자기 평가): 이 네 규칙을 모두 구현하면
Codex/Claude 두 검수자가 이번 라운드에 낸 새 P1 네 개가 전부 닫힌다. §7의
P2/P3 항목(빈 graph, verdict-node 연결, replay/seq)은 이번 P1 목록에
속하지 않으므로 별도 후속 라운드에서 다루도록 남긴다.
