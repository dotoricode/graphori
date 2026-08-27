# I02 Hardening Contract (Codex)

작성일: 2026-08-09  
범위: I02 portable core의 `Run`, `Graph`, `StateReducer` 계약  
목적: 구현하기 전에 “언제 성공이고, 언제 거절하는가”를 테스트 가능한 문장으로 고정한다.

이 문서는 소스와 테스트를 대신하지 않는다. 구현자는 이 문서의 MUST/REJECT와 최소 테스트를 코드로 옮긴다. 기존 `StateReducer`, `Run`, `Node`, `NodeKind`, `canonical_event`, `StateTransitionError`의 호출 모양은 가능한 한 유지한다.

## 1. 먼저 발견한 문제와 판단 과정

12살에게 설명하면 Run은 여러 작업 카드를 한 묶음으로 모은 상자다. 상자에 “성공” 스티커를 붙이려면 아직 안 끝난 카드가 없어야 하고, 실패한 카드만 남아 있어도 성공이라고 부르면 안 된다.

읽은 자료를 맞춰 보면서 다음 순서로 판단했다.

1. `EVENT_PROTOCOL.md`는 실행 대상이 끝나고 gate 조건도 맞아야 `succeeded`라고 한다. 현재 리듀서의 `terminal` 집합은 `failed`, `cancelled`, `blocked`, `rejected`, `inconclusive`도 포함하므로, “끝남”과 “성공함”을 혼동할 수 있다.
2. `reducer.py`는 `observer`를 실행 대상에서 제외한다. 이 정책은 유지하되, 다른 다섯 종류(`router`, `worker`, `verifier`, `human_gate`, `platform_gate`)는 모두 실행 대상이라고 명시한다.
3. 현재 `node_status_changed`는 `payload.node_id`를 먼저 선택한다. 따라서 `entity.node_id=ghost`, `payload.node_id=worker` 같은 모순된 사건이 통과한다. canonical ID는 `entity.node_id` 하나로 고정해야 한다.
4. Run이 없는 호환 경로에서 `transition_node`는 이름만 있으면 기본 `pending` 노드를 새로 만든 것처럼 취급한다. 그래프를 모르는 리듀서가 모르는 카드를 성공 판정에 넣거나 바꾸면 안 되므로, 이미 등록된 ID만 제한적으로 허용한다.
5. 현재 terminal Run에 `node_status_changed`를 계속 적용할 수 있다. terminal은 그 시점의 결론이므로, 그 뒤의 상태 사건은 모두 거절해야 한다.
6. 실행 대상이 0개이면 “모든 카드가 끝났다”는 검사가 빈 목록에서 우연히 참이 된다. 일을 하나도 하지 않은 것을 성공으로 기록하지 않도록 기본값은 거절한다.

따라서 이 문서의 추천안은 **성공은 `passed`인 현재 실행 대상만으로 증명하고, terminal 뒤에는 모든 사건을 잠그며, Run 없는 경로는 등록된 ID만 다루는 것**이다.

## 2. 용어와 불변식

### 2.1 실행 대상

`observer`가 아닌 모든 그래프 노드는 실행 대상이다. 즉 다음은 모두 포함한다.

| `NodeKind` | 실행 대상인가 | 성공 때 요구 |
|---|---:|---|
| `router` | MUST 포함 | active node가 `passed` |
| `worker` | MUST 포함 | active node가 `passed` |
| `verifier` | MUST 포함 | 검증 통과 후 `passed` |
| `human_gate` | MUST 포함 | 승인 근거 후 `passed` |
| `platform_gate` | MUST 포함 | 해당 platform pass 근거 후 `passed` |
| `observer` | 성공 집계에서 REJECT(제외) | 성공/실패 여부와 무관하게 관찰 상태 허용 |

### 2.2 active execution node

재작업 그래프를 망가뜨리지 않기 위해 `rework_of`의 **target**은 이전 revision으로 보고 active 집계에서 제외한다. `RevisionController`가 만드는 방향(`new -> old`)과 일치한다. 따라서 다음은 성공 예시다.

```text
worker-1 = failed
worker-1:revision-1 -rework_of-> worker-1
worker-1:revision-1 = passed
```

이때 active node는 최신 revision 하나다. 실패한 node에 대체 revision이 없으면 그 실패 node가 active로 남는다. rework chain이 끊기거나 cycle/두 개의 최신 대체가 생기면 성공 판정 전에 `GraphValidationError`로 거절한다.

구현자는 최소한 다음을 보장해야 한다.

- `observer`는 active 집합에 넣지 않는다.
- `rework_of`로 대체된 이전 node는 active 집합에 넣지 않는다.
- active 집합은 `StateReducer.node_statuses`라는 별도 목록이 아니라 `Run.graph`에서 계산한다.

## 3. Run terminal 상태표

모든 `run_terminal`은 먼저 `run_created -> graph_published`가 적용된 Run에서만 가능하다. 이미 `terminal_status`가 있으면 상태를 바꿀 수 없다.

| Run terminal status | 성공/중단의 의미 | node 요구조건 | MUST / REJECT | 오류 유형 | 최소 테스트 |
|---|---|---|---|---|---|
| `succeeded` | 작업을 실제로 모두 성공 | active execution node가 1개 이상이고 **모두 `passed`**. 필요한 verifier/gate 근거도 있어야 함. observer는 무시 | 조건 하나라도 부족하면 REJECT | `SucceededScopeError` (`StateTransitionError` 하위) | pending/failed/각 NodeKind는 거절, passed worker는 통과, observer-only는 거절 |
| `failed` | 실행 실패로 Run을 닫음 | 없음. 아직 `pending`/`running`인 sibling이 있어도 허용 | lifecycle 조건만 맞으면 MUST 허용. `reason`은 SHOULD 기록 | `StateTransitionError` | pending worker가 있어도 failed 통과 |
| `cancelled` | 사용자가 실행을 취소해 닫음 | 없음. 미실행 node가 있어도 허용 | lifecycle 조건만 맞으면 MUST 허용. `reason`은 SHOULD 기록 | `StateTransitionError` | pending worker가 있어도 cancelled 통과 |
| `rejected` | graph/assignment/gate가 실행을 받아들이지 않음 | 실행 node 상태는 요구하지 않지만 `reason` 또는 rejection evidence가 1개 이상이어야 함 | 근거가 없으면 REJECT | `TerminalEvidenceError` (`StateTransitionError` 하위) | graph에 node가 없어도 reason 있는 rejected 통과, 근거 없는 rejected 거절 |
| `blocked` | 지금은 진행할 수 없어 닫음 | active node 중 하나가 `blocked` **또는** run-level `blocking_reason`이 non-empty | 둘 다 없으면 REJECT | `TerminalEvidenceError` | blocked node/명시적 blocking reason 각각 통과, 둘 다 없으면 거절 |
| `inconclusive` | 증거가 부족해 결론을 확정하지 못함 | active node 중 하나가 `inconclusive` **또는** run-level `inconclusive_reason`이 non-empty | 둘 다 없으면 REJECT | `TerminalEvidenceError` | inconclusive node/명시적 reason 각각 통과, 둘 다 없으면 거절 |

`failed`와 `cancelled`에 node 완료를 요구하지 않는 것은 기존 abort 의미를 보존하기 위한 의도적인 선택이다. 반대로 `succeeded`는 “끝났음”이 아니라 “성공했음”을 뜻하므로 `failed`, `cancelled`, `blocked`, `rejected`, `inconclusive` node만 남은 경우를 성공으로 인정하지 않는다.

### 3.1 `succeeded`의 정확한 규칙

`run_terminal(payload.terminal_status="succeeded")`는 다음을 모두 MUST 만족한다.

1. graph가 publish되었다.
2. graph topology가 publish 때와 같다.
3. active execution node가 1개 이상이다. 빈 graph 또는 observer만 있는 graph는 기본적으로 성공이 아니다.
4. 모든 active execution node의 상태가 `NodeState.PASSED`다.
5. verifier는 `verdict_recorded(verdict="pass")`와 non-empty evidence를 가져야 한다.
6. human gate는 matching `verdict_recorded(verdict="approve")`와 non-empty evidence를 가져야 한다.
7. platform gate는 matching `platform_verdict_recorded(status="pass")`와 fixture 또는 snapshot 및 evidence를 가져야 한다.
8. 실패/취소/거절/차단/불확실 node가 active로 남아 있지 않다. 이전 node가 `rework_of`로 명확히 대체된 경우에만 예외다.

검증 또는 gate event가 node와 연결되지 않은 기존 기록은 성공 근거로 세지 않는다. 기존 `Verdict` 생성자의 인자는 바꾸지 않고, canonical event에서는 `entity.node_id`로 연결한다. `verdicts` 기존 list를 쓰는 호출은 유지하되 새 성공 판정은 node별 증거 projection을 사용한다.

### 3.2 빈 graph의 의미

추천안은 `active execution node == 0`인 graph의 `succeeded`를 REJECT하는 것이다. 이것은 “할 일이 없어서 성공”이 아니라 “성공을 증명할 일이 등록되지 않음”이다. 오류는 `EmptyExecutionScopeError` (`SucceededScopeError` 또는 `StateTransitionError` 하위)로 고정한다.

대안은 `payload.empty_run=true`와 승인된 명시적 정책을 둬 빈 실행을 성공으로 기록하는 것이다. 이 대안은 현재 public API와 event protocol에 정책 필드가 없으므로 I02에서는 채택하지 않는다. 빈 Run을 일부러 닫으려면 `cancelled`, `rejected`, `blocked`, `inconclusive` 중 실제 의미에 맞는 terminal을 쓴다.

## 4. Node ID와 graph membership 계약

`node_status_changed`에서 `entity.node_id`가 canonical ID다. payload는 보조 복사본일 뿐이며 우선권을 가질 수 없다.

| entity.node_id | payload.node_id | 판정 | 오류 유형 |
|---|---|---|---|
| 없음/빈 값 | 없음 | REJECT: node identity가 없음 | `MissingNodeIdentityError` |
| 없음/빈 값 | 값 있음 | REJECT: payload만으로 node를 정할 수 없음 | `MissingNodeIdentityError` |
| 값 있음 | 없음 | MUST 허용(기존 canonical event 호환) | 없음 |
| 값 있음 | 같은 값 | MUST 허용 | 없음 |
| 값 있음 | 다른 값 | MUST REJECT, 어느 값도 적용하지 않음 | `NodeIdentityConflictError` |

두 값이 모두 있을 때 비교는 문자열의 정확한 일치로 한다. 공백을 잘라 서로 같다고 만들지 않는다. 두 값 중 하나가 빈 문자열이면 “없음”으로 보고 위 표를 적용한다.

Run graph가 있으면 canonical ID가 `Run.graph.nodes`에 반드시 존재해야 한다. 존재하지 않는 ID는 payload가 우연히 유효한 ID를 가리켜도 `UnknownNodeError`로 REJECT한다. event를 적용한 뒤 graph와 compatibility map 중 어느 것도 바뀌면 안 된다.

graph membership 자체는 `graph_published`에서 고정한다.

- publish 전: compiler가 graph를 구성할 수 있다.
- publish 후: `node_created`, `edge_created` 및 직접적인 topology 변경은 REJECT한다. 상태 변경만 허용한다.
- terminal 후: 상태/토폴로지 변경 event를 모두 REJECT한다.

정상적인 graph-backed Run의 `node_status_changed`, `verdict_recorded`,
`platform_verdict_recorded`도 `run_created`와 `graph_published`가 모두 적용된 뒤에만
허용한다. 즉 출생(`run_created`) 전이나 graph 발표 전의 상태 변경은 REJECT한다.
Run 없는 legacy 경로에서 미리 등록한 map을 바꾸는 좁은 예외는 §5에만 적용되며,
그 예외가 정상 Run lifecycle을 만든 것으로 간주되지는 않는다.

현재 `Graph`가 mutable인 public API를 고려한 구현 선택은 두 가지다. 추천은 reducer가 publish 시 node ID와 edge 구조의 immutable snapshot을 저장하고 모든 apply/terminal 전에 비교하는 것이다. 더 강한 대안은 publish 후 `Graph.add_node/add_edge` 자체를 sealed error로 만드는 것이며, 이는 직접 graph를 조립하는 기존 호출을 깨뜨릴 수 있어 후속 버전으로 미룬다. 어느 선택이든 terminal 사건 뒤의 `node_status_changed`는 반드시 `RunAlreadyTerminalError`로 거절되어야 한다.

## 5. Run 없는 `StateReducer` 호환 경로

기존 public constructor인 `StateReducer(task, run=None)`은 당장 없애지 않는다. 다만 graph가 없는 리듀서가 모르는 node를 만들어 내는 동작은 금지한다.

### 추천 제한 정책

1. `run is None`이어도 envelope 형식, task/run ID 일치, 일반 node state transition 검사는 한다.
2. `node_status_changed`는 첫 event를 적용하기 전에 이미 `node_statuses` map에 등록된 ID만 허용한다. 등록되지 않은 ID는 map에 자동 추가하지 않고 `UnknownNodeError`로 REJECT한다.
3. 첫 적용 뒤 새로운 key를 event가 암묵적으로 만들 수 없다. 호환 caller가 미리 넣은 key만 legacy inventory로 취급한다.
4. Run 없는 경로에서는 graph membership과 active execution 집합을 알 수 없으므로 `run_terminal(succeeded)`를 허용하지 않는다. 정상적인 Run 성공 판정은 graph를 가진 `StateReducer(task, run)` 경로로만 한다.
5. `task.run_id`가 이미 있어도 Run graph가 자동으로 생기는 것으로 보지 않는다. task ID는 node inventory가 아니다.

이렇게 하면 기존에 map을 미리 채워 사용하던 좁은 호환 caller는 살고, `StateReducer(Task(...))`에 `ghost`만 보내는 P1 반례는 닫힌다. 더 엄격한 대안은 Run 없는 모든 `node_status_changed`를 금지하는 것이지만, 기존 public API 사용처를 깨뜨릴 가능성이 있어 채택하지 않는다.

최소 테스트:

- 빈 map에 `entity.node_id="ghost"`를 보내면 `UnknownNodeError`, map은 여전히 빈 map이어야 한다.
- `node_statuses={"legacy": PENDING}`를 미리 둔 경로에서 `legacy`를 `ready`로 바꾸는 것은 허용한다.
- Run 없는 경로에서 `run_terminal(succeeded)`는 `NoRunProjectionError` 또는 `SucceededScopeError`로 거절한다.

## 6. terminal 이후 event 계약

terminal event가 성공/실패/취소/거절/차단/불확실 중 하나로 한 번 적용되면 Run은 닫힌다. 그 뒤에는 `run_terminal`만이 아니라 **모든 event type**을 REJECT한다. 여기에는 `heartbeat`, `progress_reported`, `node_status_changed`, `verdict_recorded`, `platform_verdict_recorded`, `graph_published`, `node_created`, `edge_created`, `retry_created`, `reconciled`, `duplicate_ignored`, `idempotency_conflict`, `event_quarantined`도 포함한다.

- REJECT 이유: terminal 당시의 결론과 graph snapshot을 사후에 바꾸지 않기 위해서다.
- 오류: `RunAlreadyTerminalError` (`StateTransitionError` 하위). envelope 형식 자체가 틀리면 그 형식 오류를 먼저 낸다.
- 상태 보존: 거절된 event는 graph, map, verdict, platform verdict를 한 글자도 바꾸지 않는다.
- 같은 terminal event를 다시 보내는 것도 REJECT한다. exact duplicate를 조용히 버리는 일은 I03 writer가 reducer에 넘기기 전에 `duplicate_ignored`로 처리한다.

대안으로 audit-only event(`duplicate_ignored`, `event_quarantined`)를 terminal 뒤에도 저장만 허용할 수 있다. 그러나 I02 reducer가 이를 실제 상태 event와 섞으면 “모든 event 금지”를 검사하기 어렵다. 추천안은 I02 projection에는 보내지 않고 I03 journal에만 남기는 분리다.

## 7. node state와 terminal Run의 관계

node 자체의 terminal 상태는 `passed`, `failed`, `cancelled`, `blocked`, `rejected`, `inconclusive`다. `stale`, `outcome_unknown`, `queued`, `ready`, `running`, `pending`, `assigned`, `awaiting_verification`는 성공 시 active로 남아 있으면 안 된다.

`compiler.py`의 기존 terminal immutability를 유지한다.

- terminal node는 다른 상태로 바꿀 수 없다.
- 실패 node를 다시 `ready`로 되살리지 않는다.
- rework는 새 node와 `rework_of` relation으로 표현한다.
- `node_status_changed`는 graph node와 `node_statuses` map을 같은 사건에서 함께 갱신한다.

이 규칙은 Run terminal 상태와 node 상태를 구분한다. 예를 들어 pending worker가 있어도 `run_terminal(failed)`는 “중단되어 끝남”이므로 허용되지만, 같은 worker만 남은 상태에서 `run_terminal(succeeded)`는 `SucceededScopeError`다.

## 8. I02와 I03의 책임 경계

“순서”에는 두 종류가 있다. lifecycle 의미 순서는 I02가 보고, journal 숫자 순서와 hash 사슬은 I03가 본다.

| 항목 | I02 reducer가 MUST 책임질 것 | I03 single-writer가 MUST 책임질 것 |
|---|---|---|
| replay | 같은 node state 재적용은 no-op 호환 허용; lifecycle duplicate와 terminal 재적용은 REJECT | 같은 event ID/producer event ID를 한 번만 journal에 반영하고, 동일 payload면 `duplicate_ignored`, 다른 payload면 `idempotency_conflict` |
| order | `run_created -> graph_published -> run_terminal`, node transition, terminal lock | `seq` monotonic/중복/누락, writer가 reducer에 seq 순서대로 전달 |
| ID | envelope의 run/task ID와 Run/Task 일치, node entity/payload 일치, graph membership | `event_id`, `producer_event_id` 전역/Run별 idempotency와 충돌 payload |
| version | graph version 양의 정수, 현재 Run version과 일치, publish version regression 금지 | journal에서 version별 저장/조회와 writer 동시성 관리 |
| digest | `prev_digest`/`digest`가 `sha256:<64 hex>` 모양인지 확인 가능 | 실제 canonical bytes hash, prev chain, genesis, JSONL 순서, quarantine |
| event 형식 | schema 1, 필수 envelope field, known type 검사 | 저장 전 완전한 envelope 작성, tmp→ready→journal 원자성 |
| terminal 뒤 | 모든 적용 event를 REJECT하고 상태 불변 보장 | terminal 뒤 도착한 event를 journal 정책에 따라 quarantine/audit하되 reducer에는 투입하지 않음 |

따라서 I02의 직접 `StateReducer.apply()` 테스트는 seq가 1, 9, 1인지로 hash chain이 안전하다고 주장하지 않는다. 실제 seq/id/digest 보장은 I03 writer 통합 테스트의 책임이다. 반대로 I03 writer가 올바른 숫자를 붙였더라도 I02가 reverse lifecycle, 다른 run ID, conflicting node ID를 받아 주면 안 된다.

## 9. 오류 분류와 public API 호환

구현자는 새 오류를 도입하더라도 기존 `StateTransitionError`에서 상속해야 한다. 그러면 기존 caller의 `except StateTransitionError`가 계속 작동한다.

| 오류 class/code (추천) | 뜻 |
|---|---|
| `StateTransitionError/invalid_lifecycle` | event 순서, graph version, terminal 중복/변경 위반 |
| `RunAlreadyTerminalError/run_already_terminal` | terminal 뒤 모든 event |
| `SucceededScopeError/succeeded_scope_not_closed` | active node가 passed가 아님 |
| `EmptyExecutionScopeError/empty_execution_scope` | 성공 판정에 execution node가 0개 |
| `TerminalEvidenceError/terminal_evidence_missing` | rejected/blocked/inconclusive 근거 부족 |
| `MissingNodeIdentityError/node_id_missing` | entity node ID 없음 또는 payload만 있음 |
| `NodeIdentityConflictError/node_id_conflict` | entity와 payload ID가 다름 |
| `UnknownNodeError/unknown_node` | graph 또는 사전 등록 map에 없는 node |
| `NoRunProjectionError/no_run_projection` | graph 없는 경로에서 Run 성공 판정 시도 |
| `GraphValidationError` | rework cycle, publish snapshot 불일치 등 graph 자체 오류 |

오류 class를 당장 모두 공개 export하지 않아도 된다. 기존 API를 유지하려면 우선 `StateTransitionError` 메시지에 안정적인 code를 넣고, 후속 구현에서 하위 class를 추가해도 된다. 테스트는 class보다 code와 상태 불변을 우선 확인한다.

## 10. 새 P1 네 가지를 닫는 최소 회귀 테스트

아래 네 테스트는 기존 24개 테스트에 더해 I02 구현 전에 반드시 계약으로 고정한다. 각 테스트는 실패 시 exception만 보지 말고 event 전후 graph/map/terminal 상태가 변하지 않았는지도 확인한다.

| P1 | 재현 | 기대 결과 |
|---|---|---|
| P1-1 failed node가 있어도 succeeded | 유일한 worker를 `ready -> assigned -> running -> failed`로 만든 뒤 `run_terminal(succeeded)` | REJECT `succeeded_scope_not_closed`; Run terminal은 `None`, worker는 `failed` |
| P1-2 terminal 뒤 graph mutation | worker를 passed로 성공 확정한 뒤 `node_status_changed` 또는 `heartbeat` 적용. 가능하면 그 사이 새 node도 직접 추가 | 모든 event REJECT `run_already_terminal`; graph/map/terminal snapshot 불변 |
| P1-3 node ID 불일치 | graph에는 worker만 두고 `entity.node_id=ghost`, `payload.node_id=worker` | REJECT `node_id_conflict`; worker와 ghost 모두 바뀌지 않음 |
| P1-4 Run 없는 unknown node | `StateReducer(Task(...))`에 graph/map 등록 없이 `entity.node_id=ghost` 전송 | REJECT `unknown_node`; `node_statuses`에 ghost가 생기지 않음 |

추가로 상태표의 경계도 최소 확인한다.

- pending/failed/cancelled/blocked/rejected/inconclusive 각 NodeState와 succeeded를 각각 시험한다.
- observer-only와 empty graph를 분리한다. observer-only는 observer 제외 정책으로도 active가 0이므로 둘 다 기본 succeeded REJECT지만 오류 code는 `empty_execution_scope`로 같다.
- pending sibling + failed/cancelled Run terminal은 기존 의미대로 통과시킨다.
- 모든 NodeKind 중 observer만 제외되는지 확인한다.
- entity만/둘 다 같은 ID는 통과하고, payload만/둘 다 다른 ID는 거절한다.
- Run terminal 뒤 `run_terminal`, `node_status_changed`, `verdict_recorded`, `platform_verdict_recorded`, `heartbeat`를 각각 거절한다.

## 11. 구현자가 지켜야 할 짧은 체크리스트

- [ ] 성공 검사는 `_TERMINAL_NODE_STATES`를 재사용하지 않고 active node의 `PASSED`를 검사한다.
- [ ] active execution node가 0이면 succeeded를 거절한다.
- [ ] `entity.node_id`를 canonical로 사용하고 payload가 있으면 정확히 비교한다.
- [ ] graph가 있는 경로에서 unknown node를 절대로 자동 생성하지 않는다.
- [ ] Run 없는 경로는 사전 등록 ID만 제한적으로 허용하고 성공 projection은 금지한다.
- [ ] graph publish 후 topology를 고정하고, terminal 후 모든 event를 거절한다.
- [ ] failed/cancelled의 pending sibling 허용을 회귀시키지 않는다.
- [ ] lifecycle/semantic state는 I02, seq/id/digest chain은 I03라고 문서와 테스트에서 분리한다.
- [ ] 새 오류는 `StateTransitionError` 하위로 두어 기존 public API의 예외 처리를 살린다.

이 계약에서 모호했던 선택은 숨기지 않았다. 빈 graph 성공, gate의 증거 연결, Run 없는 경로, terminal 뒤 audit event는 각각 대안을 적었고, 구현 대상은 위 추천안을 따른다.
