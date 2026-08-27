# I02 Core Fix-5 독립 검수 보고서 (Codex)

검수일: 2026-08-09
환경: Windows, Python 3.12.1
검수자: Codex 독립 검수자
범위: `docs/architecture/EVENT_PROTOCOL.md`, Fix-4 검수 보고서 2개, `I02_CORE_FIX5_REPORT_LUNA.md`, `src/graphori_core` 전체, `tests` 전체

이번 검수에서는 소스와 테스트를 고치지 않았다. 새로 만든 파일은 이 보고서 하나뿐이다.

## 1. 12살도 이해하는 결론

Run은 작업 카드 여러 장을 한 묶음으로 모아 놓은 것이다. 카드가 아직 `pending`이나 `running`이면 묶음 전체에 “성공” 도장을 찍으면 안 된다.

Fix-5는 이 핵심 문제를 고쳤다. `Run.graph`의 카드 상태와 reducer의 호환용 상태표가 같이 바뀌고, `observer`를 빼고 `router`, `worker`, `verifier`, `human_gate`, `platform_gate`가 끝나지 않았으면 성공을 거절한다. 실패와 취소는 “중단되어 끝남”이라는 기존 뜻을 그대로 지켰다.

하지만 새로 확인한 안전 문제 때문에 최종 승인은 보류한다.

- 이미 terminal이 된 Run도 뒤늦은 `node_status_changed`로 그래프를 다시 바꿀 수 있다.
- 그래프가 있는 경우에도 `entity.node_id`를 `payload.node_id`가 덮어써서 unknown node 검사를 우회할 수 있다.
- Run이 없는 호환 경로에서는 이름만 있는 unknown node를 새로 만들 듯 받아들인다.

## 2. 읽은 계약과 코드

- `EVENT_PROTOCOL.md` §4.1: node 전이와 terminal 상태 의미
- `EVENT_PROTOCOL.md` §6: 모든 필수 scope가 terminal이고 gate 조건이 맞을 때만 Run `succeeded`
- `EVENT_PROTOCOL.md` §7: writer가 monotonic `seq`, `prev_digest`, `digest`를 붙이고 중복 event를 한 번만 반영
- `I02_CORE_POST_FIX4_REVIEW_CODEX.md`, `I02_CORE_POST_FIX4_REVIEW_CLAUDE.md`: 이전 Run 순서/ID/version 우회와 pending 성공 허용 문제
- `I02_CORE_FIX5_REPORT_LUNA.md`: Fix-5 목표, observer 제외, graph/map 동기화, failed/cancelled 보존
- `src/graphori_core/models.py`, `compiler.py`, `reducer.py`, `__init__.py` 전체
- `tests/test_core.py` 전체(24개)

핵심 코드 확인 위치는 다음과 같다.

- `reducer.py:187-206`: `observer`를 제외한 실행 node를 terminal 집합과 비교
- `reducer.py:266-289`: graph node를 확인하고 map과 graph를 함께 변경
- `reducer.py:251-265`: Run terminal 기록
- `compiler.py:498-536`: node 전이와 terminal node 불변성

## 3. Windows 기본 검증

실행한 명령과 결과:

```text
python --version
Python 3.12.1

python -m unittest discover -s tests -v
Ran 24 tests in 0.009s
OK

python -m compileall -q src tests
COMPILEALL_OK

python -m pip install . --no-deps --target <새 Windows 임시 폴더> -q
python -c "import graphori_core; from graphori_core import StateReducer, Run, Node"
PACKAGE_IMPORT_OK <임시 폴더>\graphori_core\__init__.py

git diff --check
exit 0
```

저장소의 기존 파일은 모두 아직 Git에 추적되지 않은 초기 상태라 `git diff --check`는 추적 파일 차이를 보고하지 않았다. 검수 중 source/test 파일에는 쓰기 작업을 하지 않았고, compileall이 만든 cache 외에 구현 파일을 바꾸지 않았다.

macOS는 이 Windows 환경에서 실행하지 못했으므로 `deferred/unknown`이다.

## 4. 독립 adversarial probe

아래 probe는 `tests/test_core.py`에 추가하지 않고 inline Python으로 직접 실행했다. `REJECT_OK`는 기대한 거절, `ACCEPT_OK`는 기대한 통과이다.

### 4.1 성공 조건과 terminal node 집합

| 공격 | 결과 |
|---|---|
| pending `router` + `succeeded` | `REJECT_OK` |
| pending `worker` + `succeeded` | `REJECT_OK` |
| pending `verifier` + `succeeded` | `REJECT_OK` |
| pending `human_gate` + `succeeded` | `REJECT_OK` |
| pending `platform_gate` + `succeeded` | `REJECT_OK` |
| pending `observer`만 있는 graph + `succeeded` | `ACCEPT_OK` — observer 제외 정책대로 동작 |
| `stale`, `outcome_unknown`, `queued`, `ready`, `running` node + `succeeded` | 모두 `REJECT_OK` |
| `passed`, `failed`, `cancelled`, `blocked`, `rejected`, `inconclusive` node + `succeeded` | 모두 `ACCEPT_OK` — 현재 코드의 terminal 집합 의미와 일치 |
| 빈 graph + `succeeded` | `ACCEPT_OK` — 아래 P2 |

따라서 Fix-5의 원래 P1인 “끝나지 않은 실행 node가 있어도 성공”은 재현되지 않았다. 다만 `failed` node가 terminal이라는 이유로 Run `succeeded`도 허용되는 것은 현재 `EVENT_PROTOCOL.md`의 “terminal이면 됨” 문장에는 맞지만, 향후 “성공은 모든 실행 node가 passed여야 함”으로 계약을 좁힐 때 재검토해야 한다(P3).

### 4.2 graph/map 동기화와 unknown node

1. 미리 만든 `Run.graph.nodes["n"]` 상태를 `ready`로 두었다. reducer 생성 직후 `node_statuses["n"]`도 `ready`였다.
2. 호환 map만 `pending`으로 일부러 어긋나게 만든 뒤 `node_status_changed(assigned)`를 보냈다.
3. 결과는 `Run.graph.nodes["n"] == assigned`, `node_statuses["n"] == assigned`였다. prebuilt graph/map divergence는 이 경로에서 막혔다.
4. graph에 없는 `ghost`를 `entity.node_id`로 보내면 `REJECT_OK`였다.
5. 그러나 `entity.node_id=ghost`, `payload.node_id=worker`로 보내면 `ACCEPTED`이고 worker가 `ready`가 됐다. `reducer.py:274-276`에서 payload 값을 먼저 선택하기 때문이다.
6. `Run` 없이 `StateReducer(Task(...))`에 `entity.node_id=ghost`를 보내면 `ACCEPT_OK`였다. 구현 보고서도 이 호환 경로는 바꾸지 않았다고 말하지만, unknown node fail-closed 요구와는 맞지 않는다.

### 4.3 terminal 불변성, 실패, 취소

- pending worker가 있어도 `run_terminal(failed)`와 `run_terminal(cancelled)`는 각각 통과했다.
- 두 번째 failed/cancelled terminal event는 `Run terminal status cannot be changed or duplicated`로 거절됐다.
- 그러나 worker를 `passed`로 두고 Run을 `succeeded`로 끝낸 다음 observer에 `node_status_changed(ready)`를 보내면 예외 없이 통과했고 graph 상태가 `pending -> ready`로 바뀌었다. Run의 `terminal_status` 값은 그대로지만 terminal snapshot의 graph가 바뀌므로 terminal immutability 위반이다.

### 4.4 duplicate, replay, order, ID, version, digest

기존 lifecycle 검사는 정상 동작했다.

| 공격 | 결과 |
|---|---|
| `run_created` 전 `graph_published` 또는 `run_terminal` | 거절 |
| 다른 `task_id`, `run_id`, graph version | 거절 |
| lifecycle event 중복, terminal 상태 변경 | 거절 |
| `heartbeat` 같은 event object를 그대로 replay | 통과 |
| `seq=9` 뒤 `seq=1` | 통과 |
| 같은 `event_id`에 다른 payload | 통과 |
| 같은 모양의 `prev_digest`와 `digest`를 재사용 | 통과 |

`validate_event_envelope()`는 ID와 digest의 **모양**만 검사하고 실제 중복표, seq 순서, digest chain을 검사하지 않는다. 이는 `EVENT_PROTOCOL.md` §7의 writer 책임이며 Stage 3 writer가 아직 없는 I02 범위 밖이라는 점을 함께 기록한다. 따라서 Fix-5 승인 자체를 막는 새 P1로 세지는 않지만, 실제 writer 없이 replay 방어가 완성됐다고 말할 수는 없다(P2).

## 5. Finding 분류

### P1-1 OPEN — terminal Run의 graph가 나중에 바뀜

재현: `run_terminal(succeeded)` 통과 후 `node_status_changed`를 같은 reducer에 적용하면 통과하고 `Run.graph.nodes`가 변경된다.

영향: 이미 끝났다는 Run의 기록을 나중에 바꿀 수 있다. replay 시점에 따라 terminal Run의 graph snapshot이 달라질 수 있고, 성공 판단 뒤에 상태를 바꾸어 기록을 흐릴 수 있다.

기대: `run.terminal_status is not None`이면 상태를 바꾸는 node event를 거절하거나, 최소한 terminal projection을 불변 snapshot으로 보존해야 한다. `run_terminal` 중복만 막는 현재 guard로는 충분하지 않다.

판정: **OPEN P1**.

### P1-2 OPEN — node ID 두 곳의 불일치로 unknown 검사 우회

재현: graph에는 `worker`만 넣고 `entity.node_id=ghost`, `payload.node_id=worker`, status `ready`를 보냈다. event가 거절되지 않고 worker 상태가 바뀌었다.

영향: envelope의 entity가 가리키는 카드와 실제 바뀐 카드가 다르다. 영수증을 읽는 사람은 ghost를 봤지만 reducer는 worker를 바꾼다. unknown node fail-closed와 canonical event의 일관성이 깨진다.

기대: `entity.node_id`를 필수 canonical ID로 사용하고 payload의 node ID가 있으면 두 값이 반드시 같아야 한다. 불일치 또는 entity에 ID 없음은 거절해야 한다.

판정: **OPEN P1**.

### P1-3 OPEN — Run 없는 경로에서 unknown node를 허용

재현: `StateReducer(Task("t-no-run", "probe"))`에 graph 없이 `node_status_changed(entity.node_id="ghost", status="ready")`를 보냈고 통과했다.

영향: 알려진 graph가 없다는 이유로 임의 ID를 pending에서 시작해 상태를 만든다. 현재 호환 API를 지키려는 선택은 이해되지만, 사용자가 요구한 unknown node fail-closed를 만족하지 않는다.

기대: node inventory가 없으면 상태 변경을 보류/거절하거나, 명시적으로 `node_created`를 먼저 받아 알려진 node만 허용해야 한다.

판정: **OPEN P1** (호환 경로를 유지해야 한다면 계약을 문서로 명확히 낮추고 별도 후속 범위로 승인해야 한다).

### P2-1 OPEN — 빈 graph가 성공 가능

재현: node를 하나도 넣지 않은 Run에 `run_created -> graph_published -> run_terminal(succeeded)`를 보냈고 통과했다.

영향: 실행할 일이 하나도 없는데 성공으로 보일 수 있다. 현재 문서가 empty scope를 명시적으로 금지하지 않아 P1보다는 낮게 분류한다.

기대: 최소 한 개의 필수 execution node 또는 명시적인 empty-run 계약이 있어야 한다.

판정: **OPEN P2**.

### P2-2 OPEN/DEFERRED — 일반 event replay와 seq/digest chain은 reducer에서 막지 않음

재현: 같은 heartbeat object replay, 역순 seq, 같은 event ID의 다른 payload, 같은 digest 재사용이 모두 통과했다.

영향: reducer만 직접 사용하는 호출자는 중복과 순서 뒤섞임을 감지하지 못한다.

판정: Stage 3 single-writer 경계의 **P2 잔여 위험**, macOS와 마찬가지로 writer 실행 증거는 `deferred/unknown`이다. I02 Fix-5의 in-memory node projection과는 분리해 추적해야 한다.

### P3-1 관찰 — terminal node가 failed여도 Run succeeded 허용

현재 terminal node 집합(`passed`, `failed`, `cancelled`, `blocked`, `rejected`, `inconclusive`)을 따르면 구현은 일관된다. 다만 제품 의미가 “성공한 Run”이라면 failed/rejected child를 포함한 succeeded가 어색하므로, 계약을 “모든 required node가 terminal”에서 “모든 required node가 passed 또는 허용된 gate terminal”로 구체화할지 후속 결정이 필요하다.

## 6. 이전 공통 P0/P1 판정

| 이전 공통 finding | 이번 판정 |
|---|---|
| 끝나지 않은 node가 있어도 `run_terminal(succeeded)` 허용 (Fix-4의 공통 P1) | **CLOSED** — pending/nonterminal 실행 kind 5종과 stale/outcome_unknown/queued/ready/running을 직접 넣어 모두 거절됨 |
| `node_status_changed`가 Run graph와 map을 갈라 놓음 (Fix-4의 공통 P1) | **CLOSED** — prebuilt graph를 seed하고 map을 일부러 어긋나게 해도 다음 transition 뒤 양쪽이 같은 상태 |
| prebuilt Run이 `run_created` 없이 lifecycle을 통과 | **CLOSED** — graph publish/terminal 선행 모두 거절 |
| lifecycle ID/version, 순서 역전, duplicate, terminal 변경 | **CLOSED** — 직접 재현에서 거절 |
| revision-3 이전의 verdict 권한/evidence, node terminal 부활, independence, rework cycle, envelope 형식 | **CLOSED 재확인** — 24개 unittest 전체 통과 및 기존 보고서의 반례 범위 확인 |

위 항목들이 닫혔다는 뜻은 새 P1-1~P1-3까지 닫혔다는 뜻이 아니다. 이번 Fix-5 코드에 대한 새 검수 finding은 여전히 **OPEN**이다.

## 7. 최종 판단

Fix-5가 고친 두 공통 P1은 실제 Windows 실행과 별도 공격에서 확인됐다. 하지만 terminal 이후 graph mutation과 node ID 불일치 우회는 작은 수정으로 막을 수 있는 I02 projection 안전 문제이고, unknown node fail-closed도 요구사항에 직접 적혀 있으므로 현재 상태로 승인할 수 없다.

VERDICT: REVISE
