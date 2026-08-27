# I02 Core Fix-5 작업 보고서 (Luna)

검사일: 2026-08-09  
환경: Windows, Python 3.12.1  
범위: `src/graphori_core/reducer.py`, `tests/test_core.py` 중심

## 1. 12살도 이해하는 설명

Run은 여러 작업 카드가 모인 한 묶음이다. 카드 하나라도 아직 `pending`이나
`running`이면 묶음 전체를 “성공”이라고 도장을 찍으면 안 된다.

Fix-4까지는 카드가 남아 있어도 Run 성공 도장이 찍혔다. 또 상태 변경 영수증을
받으면 reducer 안의 작은 표만 바뀌고, 실제 `Run.graph.nodes`의 카드 상태는 그대로라서
두 표가 서로 다른 말을 할 수 있었다.

이번 Fix-5에서는 `Run.graph`를 진짜 카드판으로 정했다. `node_status_changed`가 오면
그 카드와 기존 호환용 상태 표를 함께, 같은 순서로 바꾼다. 성공할 때는 observer처럼
일을 실행하지 않는 노드를 빼고 모든 실행 대상 카드가 terminal인지 확인한다. 실패나
취소는 작업을 중단했다는 기존 뜻을 유지하므로, 남은 카드가 있어도 terminal로 기록할
수 있다.

## 2. 최초 문제

Fix-4의 마지막 독립 검토에서 다음 두 가지 P1이 남았다.

1. `pending` worker node가 `Run.graph`에 남아 있어도
   `run_terminal(succeeded)`가 받아들여졌다.
2. `node_status_changed`가 `StateReducer.node_statuses`만 바꾸고
   `Run.graph.nodes[node_id].state`는 바꾸지 않았다.

따라서 성공 판정이 실제 그래프의 작업 완료 상태를 보장하지 못했고, 같은 사건을
재생한 뒤 reducer 표와 Run graph가 달라질 수 있었다. 이 문제는 JSONL writer의
hash/seq 문제가 아니라 I02 portable in-memory projection 문제로 판단했다.

## 3. 중간 판단

- 성공(`succeeded`)에만 “모든 실행 대상 node terminal” 검사를 추가했다.
- `failed`, `cancelled`, `rejected`, `blocked`, `inconclusive`는 기존처럼 Run을
  중단/종료하는 terminal 의미를 유지했다. 따라서 pending node가 남아 있어도
  실패·취소 기록은 막지 않는다.
- `observer`는 실행 작업이 아니라 관찰 관계를 나타내므로 성공 완료 대상에서 제외했다.
  router, worker, verifier, human gate 등 나머지 canonical node kind는 실행 대상이다.
- `Run.graph`를 canonical projection으로 삼고, 기존 `node_statuses`는 호환용 색인으로
  동기화했다. 새 event field나 public schema/API는 추가하지 않았다.
- Run이 실제 graph를 가지고 있을 때 존재하지 않는 node ID를 가리키는 상태 변경은
  canonical graph에 반영할 수 없으므로 fail-closed로 거절했다. Run이 없는 기존
  reducer 사용 방식은 바꾸지 않았다.

## 4. 변경 내용

### `src/graphori_core/reducer.py`

- terminal node 상태 집합을 정의했다: `passed`, `failed`, `cancelled`, `blocked`,
  `rejected`, `inconclusive`.
- 성공 terminal 전에 graph의 실행 대상 node를 결정론적으로 검사하고, 열린 node ID를
  포함한 `StateTransitionError`를 낸다.
- Run을 가진 reducer를 만들 때 `Run.graph.nodes` 상태를 `node_statuses`에 반영한다.
- `node_status_changed`에서 graph node를 canonical source로 읽고 transition guard를
  적용한 뒤, graph node와 호환용 map을 같은 상태로 갱신한다.
- 기존 event 순서, ID/run ID/graph version 검사, duplicate 거절, terminal 불변성은
  건드리지 않았다.

### `tests/test_core.py`

다음 회귀 테스트 3개를 추가했다.

- pending 실행 대상이 있으면 succeeded를 거절한다.
- node status event 뒤 `Run.graph.nodes`와 `node_statuses`가 함께 바뀐다.
- pending node가 있어도 failed/cancelled terminal은 기존 계약대로 허용하고, 두 번째
  terminal event는 거절한다.

`PROCESS.md`는 수정하지 않았다.

## 5. Windows 검증 증거

```text
python -m unittest discover -s tests -v
Ran 24 tests ... OK

python -m compileall -q src tests
COMPILEALL_OK

python -m pip install . --no-deps --target <Windows temporary directory>
python -c "import graphori_core; from graphori_core import StateReducer, Run, Node"
PACKAGE_IMPORT_OK ...\graphori_core\__init__.py

git diff --check
DIFF_CHECK_OK

targeted adversarial probes
ADVERSARIAL_PROBES_OK
```

adversarial probe는 pending worker의 succeeded 거절, observer 제외 후 성공 허용,
graph/map 동기화, pending 상태에서 failed/cancelled 허용, terminal duplicate 거절을
직접 확인했다. 기존 unittest에는 event 순서 역전, ID/version 불일치, 중복
`run_created`/`graph_published`/`run_terminal`, terminal immutability 회귀 검사가
포함되어 있고 모두 통과했다.

## 6. 남은 위험과 판정

- 이 코어에는 여전히 Stage 3 JSONL single-writer, 실제 process adapter, dashboard,
  macOS 실행이 없다. 이번 수정은 그 범위를 넓히지 않았다.
- macOS에서는 명령을 실행하지 못했으므로 검증 상태는 **deferred/unknown**이다.
- 그래프에 어떤 node를 실행 대상에서 제외할지에 대한 더 복잡한 future policy가
  생기면 별도 계약 결정이 필요하다. 현재 구현에서는 canonical `observer`만 제외한다.
- 24개 테스트가 통과했다는 사실만으로 **APPROVE라고 주장하지 않는다**. 최종 승인은
  신선한 Codex/Claude dual review가 이 변경과 증거를 다시 읽은 뒤에만 가능하다.

현재 작업자의 판단은 **FIX 구현 완료, fresh dual review 대기**이다.
