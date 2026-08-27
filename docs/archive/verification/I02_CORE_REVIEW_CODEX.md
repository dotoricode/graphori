# I02 portable core 독립 검수 보고서 (Codex)

- 검수일: 2026-08-09 (Asia/Seoul)
- 검수 범위: `TEAM_TOPOLOGY.md`, `docs/architecture/{GRAPHORI_ARCHITECTURE,EVENT_PROTOCOL,PORTABILITY_CONTRACT}.md`, `docs/decisions/0001~0004`, `docs/IMPLEMENTATION_PLAN.md`, `docs/verification/I02_CORE_BUILD_REPORT_LUNA.md`, `src/graphori_core/*`, `tests/test_core.py`, `pyproject.toml`
- 실행 환경: Windows PowerShell, Python 3.12.1
- macOS: 실행하지 않음. 모든 macOS 결과는 `deferred/unknown`으로 취급

## 최종 판정

**REVISE**

P0는 발견하지 못했으나 P1 계약 위반이 여러 건 있다. 기본 테스트 6개는 통과했지만, 위험 분류 우회·검수자 독립성·reducer 입력 검증·revision history 같은 정상 계약의 경계가 테스트되지 않았고 현재 구현은 이를 보장하지 않는다.

## 검증 결과

### 실행 명령

```text
python -m unittest discover -s tests -v
```

결과: `Ran 6 tests in 0.002s`, `OK`.

정적 import 검사에서는 `src/graphori_core/*.py`에 Orca/Claude/OpenAI SDK 및 OS-specific import가 없었다. 구현 import는 Python 표준 라이브러리와 sibling module뿐이며, `pyproject.toml:9`의 `requires-python = ">=3.11"` 및 `src` 패키지 탐색 설정은 계약과 부합한다. 다만 설치하지 않은 checkout 루트에서 `python -c "import graphori_core"`는 `ModuleNotFoundError`이므로 사용자는 패키지 설치 또는 `PYTHONPATH=src`가 필요하다(패키지 구조 자체의 결함으로 판정하지 않음).

### 정상 동작으로 확인한 항목

- Fast/Standard/Critical의 기본 node 구성, Critical normal/adversarial verifier와 fan-in 및 Human Gate node가 생성된다.
- `requires`/`requires_gate` scheduling cycle은 거부하고 `rework_of` cycle은 history edge로 제외한다.
- 동일 `attempt_id` 검수는 거부한다.
- REVISE 3회 뒤 4번째 호출은 `human_gate_required`가 된다.
- `Usage(unknown).total_tokens`는 `None`이며 0으로 대체되지 않는다.
- Windows pass와 macOS deferred를 각각 보존하고 pass scope/exclusion을 분리한다.

## 발견사항

### P1-01: usage unknown을 조건 없이 Critical로 분류

- 위치: `src/graphori_core/compiler.py:93-108`
- 문제: `usage_status == "unknown"`을 hard trigger로 추가해 위험도·불확실성·범위·외부효과와 무관하게 항상 `Risk.CRITICAL/TaskMode.CRITICAL`이 된다.
- 계약: ADR 0004 `docs/decisions/0004-token-aware-fast-mode.md:8-18`은 unknown을 0으로 계산하지 말되 Standard 조사 또는 Critical 검토로 보낼 수 있게 구분한다. unknown 자체를 Critical로 고정하면 문서가 허용한 Standard 경로가 사라진다.
- 재현 명령:

```text
python -c "import sys;sys.path.insert(0,'src');from graphori_core import *;r=compile_risk(RiskInput(usage_status='unknown'));print(r.risk.value,r.mode.value,r.hard_triggers)"
```

- 관찰 결과: `critical critical ('usage_unknown',)`.

### P1-02: 명시적 Standard 선택이 Critical hard trigger를 우회

- 위치: `src/graphori_core/compiler.py:173-180`
- 문제: `selected`가 `FAST`일 때만 compiler 결과로 되돌리고, 명시적 `mode=STANDARD`는 `result.mode == CRITICAL`이어도 그대로 적용한다. 결과 risk는 Critical인데 실제 graph는 Standard가 되어 deterministic compiler 결과와 topology가 불일치한다.
- 계약: ADR 0004 `:16-18`, `:22-24`의 hard trigger 우선 규칙 및 ADR 0002 `:14-18`의 risk-compiled subgraph 규칙에 위배된다.
- 재현 명령:

```text
python -c "import sys;sys.path.insert(0,'src');from graphori_core import *;t=Task('t','critical',risk=Risk.CRITICAL);x=compile_topology(t,mode=TaskMode.STANDARD);print(x.result.mode.value,x.task.mode.value,sorted(x.graph.nodes))"
```

- 관찰 결과: `critical standard ['observer', 'router', 'verifier', 'worker']`.

### P1-03: 독립성 검사에서 identity만 같고 실행 context가 다른 verifier를 허용

- 위치: `src/graphori_core/compiler.py:224-244`
- 문제: `independent_verifier`와 `verify_attempt`가 `(identity, provider, model, checkout)` 전체 tuple이 완전히 같은지만 비교한다. canonical 계약은 Worker/Verifier가 identity/provider/model/checkout을 공유하지 않아야 하므로 identity가 같으면 나머지가 달라도 거부해야 한다.
- 계약: ADR 0004 `:17-18`, `TEAM_TOPOLOGY.md:52-59`의 독립 검수자 identity 제약.
- 재현 명령:

```text
python -c "import sys;sys.path.insert(0,'src');from graphori_core import *;v1=Role('v1',NodeKind.VERIFIER,'same','p1','m1','c1');v2=Role('v2',NodeKind.VERIFIER,'same','p2','m2','c2');print(independent_verifier(v1,v2));w=Role('w',NodeKind.WORKER,'same','p1','m1','c1');verify_attempt(Attempt('a1','t',w),Attempt('a2','t',v2));print('accepted')"
```

- 관찰 결과: `True` 후 `accepted`.

### P1-04: RevisionController가 실제 revision node/rework history를 만들지 않음

- 위치: `src/graphori_core/compiler.py:247-264`; 관련 모델 부재: `src/graphori_core/models.py:171-237`
- 문제: controller는 숫자와 action만 반환한다. 3회까지 새 revision node를 만들고 `rework_of`로 옛 node를 보존해야 하는데, Task/Graph에 revision identity/history를 연결하는 동작이 없다. 따라서 caller가 같은 failed node를 다시 READY로 만들 수 있다.
- 계약: GRAPHORI_ARCHITECTURE `:20-22`, EVENT_PROTOCOL `:85-88`, ADR 0002 `:8-18`은 failed task가 새 revision에서만 ready가 되고 같은 node 재실행을 금지하며 `rework_of`는 history라고 정한다.
- 재현 명령:

```text
python -c "import sys;sys.path.insert(0,'src');from graphori_core import *;from graphori_core.compiler import transition_task; t=Task('t','x');transition_task(t,TaskState.READY);transition_task(t,TaskState.RUNNING);transition_task(t,TaskState.FAILED);transition_task(t,TaskState.READY);print(t.state.value)"
```

- 관찰 결과: `ready` (revision id 또는 `rework_of` 증거 없이 동일 Task가 재준비됨).

### P1-05: reducer가 알 수 없는 event와 actor/verdict 조합을 조용히 수용

- 위치: `src/graphori_core/reducer.py:18-34`
- 문제: `type`이 없거나 알 수 없는 event면 아무 변경 없이 성공한다. `verdict_recorded`도 `worker`만 거부하고 임의 actor를 허용하며, Human Gate가 `pass`를 발행하거나 verifier가 `approve`를 발행하는 잘못된 조합을 막지 않는다. 또한 `node_status_changed`를 TaskState로 변환해 Node event를 Task에 적용하거나 일부 정상 node status를 Task 전이로 오해한다.
- 계약: EVENT_PROTOCOL `:39-40`, `:72-89`, `:109-119`에서 verdict 주체와 node/attempt 전이를 분리하고, 잘못된 사건은 조용히 projection에 반영하지 않아야 한다.
- 재현 명령:

```text
python -c "import sys;sys.path.insert(0,'src');from graphori_core import *;r=StateReducer(Task('t','x'));r.apply({});print('missing=',r.task.state.value);r.apply({'type':'typo','payload':{'state':'s'}});print('unknown=',r.task.state.value);r.apply({'type':'verdict_recorded','payload':{'verdict':'pass','actor_role':'bogus'}});r.apply({'type':'verdict_recorded','payload':{'verdict':'pass','actor_role':'human_gate'}});print([v.value for v in r.verdicts])"
```

- 관찰 결과: `missing=planned`, `unknown=planned`, `['pass', 'pass']`.

### P1-06: canonical enum/data model이 EVENT_PROTOCOL 전체를 표현하지 못함

- 위치: `src/graphori_core/models.py:18-128`, `:130-237`
- 문제: 문서 canonical enum 중 `verification`, `progress`, `terminal_status` enum이 없고, Run/graph version/Gate/event envelope/role assignment 모델도 없다. 현재 `TaskState`/`Risk`는 문서의 별도 상태를 부분적으로 대체하지만 event schema의 필드와 전이를 타입으로 보장하지 않는다.
- 계약: EVENT_PROTOCOL `:20-40`, `:42-70`, ADR 0001 `:14-17` 및 IMPLEMENTATION_PLAN `:19-29`의 portable core 소유 범위.
- 영향: `verification=automatic|targeted|fresh_full|adversarial`, progress와 terminal status를 저장·검증할 수 없으며 reducer가 canonical event를 완전하게 재생할 수 없다.

## P2 및 품질 리스크

### P2-01: Critical fan-in marker가 중첩 metadata로 저장됨

- 위치: `src/graphori_core/compiler.py:210`
- `_node(..., metadata={"fan_in": True})` 호출 때문에 실제 값은 `{"metadata": {"fan_in": True}}`다. node/edge 자체는 fan-in 구조를 만들지만 `node.metadata["fan_in"]`를 읽는 projection은 실패한다.
- 재현 명령:

```text
python -c "import sys;sys.path.insert(0,'src');from graphori_core import *;print(compile_topology(Task('t','x',risk=Risk.CRITICAL)).graph.nodes['verifier_fanin'].metadata)"
```

### P2-02: 테스트가 happy path 중심

- 위치: `tests/test_core.py:35-96`
- 6개 테스트는 세 mode의 node 존재만 확인하고 edge 종류/방향, `requires_gate` fan-in readiness, `verifies`/`observes` semantics, hard-trigger precedence, partial-context identity collision, malformed reducer payload, Task/Attempt 전이 전체를 검증하지 않는다. 따라서 위 P1 반례들이 모두 통과했다.
- `verifies`와 `rework_of` edge는 enum/validator에는 있으나 topology/compiler가 실제로 생성하지 않으며 revision graph 계약을 테스트하지 않는다.

### P2-03: 첫 커밋 오염 위험

- 위치: 저장소 루트 `.gitignore` 없음; `src/graphori_core/__pycache__/`, `tests/__pycache__/` 존재
- 현재 `.pyc` 5개가 생성되어 있고 `.gitignore`가 없어 첫 `git add .`에서 캐시가 포함될 수 있다. `git status --short` 기준 현재 파일들은 아직 전부 untracked 상태이므로 report를 포함한 초기 커밋 전에 ignore 규칙과 정리가 필요하다.

## 계약별 요약

| 검수 항목 | 결과 |
|---|---|
| Python 3.11+ / stdlib only | PASS (Python 3.12.1에서 source import 확인) |
| Orca/Claude/OpenAI SDK import 없음 | PASS |
| enum/data model 완전성 | REVISE (P1-06) |
| risk compiler / unknown usage | REVISE (P1-01, P1-02) |
| Fast/Standard/Critical node·edge, cycle | 부분 PASS; fan-in marker/revision graph 보완 필요 |
| requires/requires_gate/rework_of 의미 | cycle exclusion은 PASS; 실제 revision history 생성은 FAIL |
| builder/same-attempt/same-identity independence | same attempt PASS; same identity FAIL (P1-03) |
| Critical normal/adversarial + Human Gate fan-in | 기본 구조 PASS; authority pool 및 metadata 보완 필요 |
| REVISE 3회/4번째 escalation | controller 단위 PASS; graph/history 연계 FAIL |
| task/attempt transition guard | 기본 illegal transition guard PASS; same failed Task 재준비 우회 FAIL |
| platform partial verdict | PASS (Windows pass/macOS deferred 보존) |
| reducer malformed payload/status | REVISE (P1-05) |
| public API/packaging | 구조 PASS; 미설치 checkout import는 설치 절차 필요 |
| 테스트가 happy path 아닌지 | REVISE (P2-02) |
| `__pycache__`/`.gitignore` | REVISE 전 정리 필요 (P2-03) |
| macOS 실행 | deferred/unknown |

## 결론

현재 구현은 portable stdlib 기반의 최소 그래프 fixture와 일부 guard를 증명하지만, 정상 계약 관점에서 위험 라우팅과 독립성·reducer·revision auditability가 닫히지 않았다. P1-01~P1-06을 수정하고 malformed/negative contract test를 추가한 뒤 Windows에서 동일 명령을 재실행해야 APPROVE 재검토가 가능하다. macOS는 실제 host/CI fixture 실행 전까지 계속 `deferred/unknown`으로 남겨야 한다.
