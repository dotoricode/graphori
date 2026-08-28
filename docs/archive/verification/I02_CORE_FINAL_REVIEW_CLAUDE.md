최종 판정: **REVISE** (범위는 매우 좁음 — 새 P0는 0건, 새 P1 1건 + P2 1건만 남음)

# I02 portable core revision-2 최종 재검수 보고서 (Claude, 적대적 관점)

> 12살에게 설명: 이번 공책(revision-2)은 지난번 제가 찾은 "문 세 개"(카드 상태
> 되돌리기, 증거 없는 통과, 이름만 바꾼 가짜 검사자)를 전부 진짜로 막았어요.
> 그런데 새로 아주 세게 두드려 보니 딱 한 군데, "영수증에 도장(digest)이
> 찍혀 있어야 한다"고 규칙을 써놓고 정작 도장 칸에 "없음(None)"이라고 써도
> 봐주는 틈이 남아 있었어요. 그리고 "다시 하기 기록(rework_of)"이 한 바퀴 빙
> 돌아 제자리로 오는 경우까지는 확인하지 않는 틈도 하나 있었어요. 둘 다 지난번
> 문제들보다는 훨씬 작고, 이전에 열려 있던 큰 문은 전부 닫혔습니다.

- 검수자: Claude (독립, 구현/테스트 파일 미수정, 읽기 전용 `python -c` one-liner와
  `unittest`/`compileall`/`pip install`만 실행)
- 검수 대상: `src/graphori_core/*`, `tests/test_core.py`, `pyproject.toml`, `.gitignore`
- 기준 문서: `docs/architecture/GRAPHORI_ARCHITECTURE.md`, `docs/architecture/EVENT_PROTOCOL.md`,
  `docs/architecture/PORTABILITY_CONTRACT.md`, `TEAM_TOPOLOGY.md`, `docs/IMPLEMENTATION_PLAN.md`
- 비교 대상: `docs/verification/I02_CORE_REREVIEW_CODEX.md`(Codex R1~R6),
  `docs/verification/I02_CORE_REREVIEW_CLAUDE.md`(Claude 이전 §2.1~§2.5),
  `docs/verification/I02_CORE_FIX2_REPORT_LUNA.md`
- 실행 환경: Windows(PowerShell/Git Bash), Python 3.12.1 (`requires-python >=3.11` 충족)
- macOS: **실행하지 않음.** 모든 macOS 판정은 `deferred/unknown`이다.
- PROCESS.md, 구현 파일, 테스트 파일은 이번 검수에서 수정하지 않았다. 이 보고서만
  새로 작성했다.

## 0. 실행 결과 요약 (직접 실행)

```text
$ python --version
Python 3.12.1

$ python -m unittest discover -s tests -v
Ran 15 tests in 0.002s
OK

$ python -m compileall -q src tests
(종료 코드 0)

$ git status --short
?? .gitignore ?? README.md ?? TEAM_TOPOLOGY.md ?? docs/ ?? graphori/
?? pyproject.toml ?? src/ ?? tests/
(이번 검수로 만든 변경 없음 — git diff --check 종료 코드 0)

$ python -m pip install . --no-deps --target <임시폴더> -q
$ PYTHONPATH=<임시폴더> python -c "import graphori_core"
install+import OK

$ AST로 src/graphori_core/*.py import 전수 조사
compiler.py: __future__, dataclasses, enum, typing (+ sibling .models)
models.py:   __future__, dataclasses, enum, typing
reducer.py:  __future__, dataclasses, typing (+ sibling .models, .compiler)
__init__.py: (없음, sibling만)
```

15개 테스트 전부 통과, `compileall` 성공, `pip install --target`으로 설치한 뒤
`PYTHONPATH` 없이도 `import graphori_core`가 성공했다. stdlib 이외 import는 0건.
macOS는 이 Windows 작업 환경에서 실행할 수 없으므로 `deferred/unknown`.

## 1. 이전 P0 3건 / P1 1건 / Codex R1~R6 재공격 결과

| 원 finding | 위치 | 이번 공격 방법 | 판정 |
|---|---|---|---|
| Claude §2.1 [P0] Node 상태 역방향/부활 (cancelled/failed/passed/rejected/inconclusive → running/ready) | `compiler.py` `NODE_TRANSITIONS`/`transition_node`, `reducer.py` `node_status_changed` | pending→ready→assigned→running→awaiting_verification→passed 정상 경로 확인 후, 5개 종단 상태 각각에서 `running`/`ready`로 되돌리기 10가지 시도 | **CLOSED** — 10가지 전부 `StateTransitionError` (§2 참고) |
| Claude §2.2 [P0] 증거 없는 pass 통과 | `reducer.py` verdict 검증 | `evidence_ids` 없음/`[]`/문자열/`[""]`/`[" "]`/`[None]`/`[123]`/`None` 8가지 + `pass`/`approve` 각각 | **CLOSED** — 8가지 전부 `StateTransitionError` (§2 참고) |
| Claude §2.3 [P0] identity만 바꾼 독립성 우회 (Fast/Standard/Critical/Human Gate) | `compiler.py` `_independent`/`_assert_verifier_independent`/`_validate_gate_pool` | identity만 다르고 provider/model/checkout/session/worktree 완전 동일 재사용(4곳), provider만/model만/checkout만/session만/worktree만 다른 부분 우회(worker-verifier, critical 2verifier, human gate) 전부 | **CLOSED** — 시도한 20여 가지 조합 전부 `IndependenceError` (§2, §3 참고) |
| Claude §2.4 [P1] `rework_of` self-loop | `compiler.py` `RevisionController.record` | revision 1→2→3 체인과 4번째 escalation 재현 | **CLOSED** — `task:revision-1→task`, `revision-2→revision-1`, `revision-3→revision-2`로 정확히 이전 노드를 가리킴, self-loop 없음. **단, 새 변형 발견**(§2-B, 길이 2 이상 순환은 미검증) |
| Claude §2.5 [P2] fan-in `.role`이 문자열로 오염 | `compiler.py` `_node` 호출 | `verifier_fanin.role`과 `metadata['fan_in']` 확인 | **CLOSED** — `role=None`, `metadata['fan_in']=True` 확인 |
| Codex R1 identity/checkout 부분 충돌 | `compiler.py` `_independence_key`(구) | 위 §2.3와 동일 공격 | **CLOSED** — 단일 `_independent()`로 교체되어 부분 충돌도 차단 |
| Codex R2 `rework_of` self-loop | 상동 | 상동 | **CLOSED** (§2-B 새 변형 제외) |
| Codex R3 Fast의 local/reversible 미표현 | `compiler.py` `RiskInput`/`compile_risk` | `local_only`/`reversible` 누락·`None`·`False`·비bool 값 주입 | **CLOSED** — 모두 Standard로 강등 (§4 boundary 표 참고) |
| Codex R4 canonical event envelope 미검증 | `reducer.py` `validate_event_envelope` | 필수 필드 12개 개별 제거, 타입 오염, `seq` 음수/문자열, `unknown/noncanonical type` | **부분 CLOSED, 새 변형 OPEN** — 필드 "존재" 검사는 전부 막지만 `digest`/`producer_event_id`/`prev_digest`가 `None`이면 통과 (§2-A) |
| Codex R5 node transition 미검사 | `compiler.py` `NODE_TRANSITIONS` | §2.1과 동일 | **CLOSED** |
| Codex R6 platform verdict가 fixture별 미보존 | `reducer.py` `platform_verdicts`/`platform_summary` | 같은 platform에 서로 다른 `fixture_id`/`snapshot_id` 2건씩 기록 후 덮어쓰기 여부 확인 | **CLOSED** — 두 fixture 모두 `platform_summary()["platform_verdicts"]["windows"]["verdicts"]`에 남음 (§3 참고) |

**요약: 이전에 열려 있던 P0 3건, P1 1건, Codex R1~R6 중 5건은 완전히 닫혔고, 나머지
2건(R2 rework_of, R4 envelope)은 원래 지적한 형태는 닫혔지만 더 좁은 새 변형이
남아 있다.**

## 2. 이번 재검수에서 새로 발견한 결함

### 2-A. [P1] `digest`/`producer_event_id`/`prev_digest`가 "있기만 하면" 통과 — 값이 `None`이어도 막지 않음

- 위치: `src/graphori_core/reducer.py:68-70`

```python
for optional in ("producer_event_id", "prev_digest", "digest"):
    if optional in event and event[optional] is not None:
        _nonempty_string(event[optional], optional)
```

- 문제: 이 세 필드는 `_REQUIRED_ENVELOPE`(25-29줄)에 들어 있어 **키 자체가 없으면**
  거부된다. 그런데 값이 `None`이면 `event[optional] is not None` 조건이 거짓이
  되어 `_nonempty_string` 검사를 건너뛰고 그대로 통과한다. 즉 "필수 필드"라고
  선언해 놓고 실제로는 "키가 있고 값이 뭐든 상관없음(None 포함)"과 같다.
- 계약 위반: `EVENT_PROTOCOL.md` §3 "`seq`, `recorded_at`, `prev_digest`, `digest`는
  writer가 채운다"와 `GRAPHORI_ARCHITECTURE.md` 폐기 매핑 표 "MVP에서는 단일 writer,
  sequence, digest, idempotency, crash-tail 격리까지만 한다"는 문장은 digest가
  실제 해시 문자열로 채워짐을 전제한다. `digest`(이 사건 자신의 지문)와
  `producer_event_id`(중복 방지 key)는 절대 비어 있으면 안 되는데, `None`으로
  기록된 사건이 reducer 검증을 통과한다.
- 재현 명령 (읽기 전용):

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, StateReducer, canonical_event
ev = canonical_event('node_status_changed', payload={'status':'ready'}, entity={'node_id':'n'})
ev['digest'] = None
ev['producer_event_id'] = None
ev['prev_digest'] = None
r = StateReducer(Task('t','x'))
r.apply(ev)
print('accepted despite digest/producer_event_id/prev_digest all None')
"
```

- 실제 결과: 예외 없이 accepted. `digest`를 실제 문자열로 바꾸면(`'x'*10` 등)
  아무 문제 없이 accept되던 것과 동일하게 통과 — 즉 이 필드들은 사실상 검증되지
  않는 것과 같다.
- 기대 결과: `digest`, `producer_event_id`는 값이 `None`이어도 `_nonempty_string`을
  적용해 거부해야 한다. `prev_digest`는 genesis(run의 첫 사건)에 한해 `None`을
  허용할지 문서에서 명시적으로 정하고, 그 경우가 아니면 마찬가지로 거부해야 한다.
- Windows: 재현됨(FAIL). macOS: `deferred/unknown`(코드 경로상 플랫폼 무관 문제로
  보이나 확인 전이라 단정하지 않음).
- 영향 범위: 이 필드는 오직 single writer만 채우는 값이라(§EVENT_PROTOCOL 7),
  실제로 이 틈을 악용하려면 이미 writer를 우회해 journal에 직접 쓸 수 있는
  권한이 필요하다. 따라서 verdict 위조나 독립성 우회처럼 "권한 없는 행위자가
  바로 악용 가능한" P0급은 아니지만, "필수 필드 검증"이라는 이름의 방어가 실제로는
  방어하지 못한다는 점에서 R4의 재발이며 P1로 분류한다.

### 2-B. [P2] `rework_of` 길이 2 이상 순환은 `validate_graph`가 잡지 못함

- 위치: `src/graphori_core/compiler.py:162-203`(`validate_graph`)
- 문제: 167-168줄은 `edge.source == edge.target`인 **자기 자신 순환(길이 1)**만
  막는다. 184-203줄의 실제 cycle 탐지(DFS)는 `REQUIRES`/`REQUIRES_GATE` edge로만
  adjacency를 만들고(186줄), `REWORK_OF`는 제외한다. 그 결과 `A rework_of B`,
  `B rework_of A`처럼 self-loop는 아니지만 실질적인 순환인 history는 통과한다.
- 계약 위반: `validate_graph`의 docstring 자체가 "Validate references, **history
  invariants**, verification paths, and DAG edges"라고 선언한다. `rework_of`가
  readiness 계산에서 제외되는 것(EVENT_PROTOCOL §4.2)과 "이력이 순환하면 안 된다"는
  것은 별개 요구인데, 후자를 검사하지 않는다.
- 재현 명령:

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Graph, Node, NodeKind, Edge, EdgeKind, validate_graph
g = Graph()
g.add_node(Node('A', NodeKind.WORKER, 'a'))
g.add_node(Node('B', NodeKind.WORKER, 'b'))
g.add_edge(Edge('A','B', EdgeKind.REWORK_OF))
g.add_edge(Edge('B','A', EdgeKind.REWORK_OF))
validate_graph(g)
print('2-node rework_of cycle A->B->A accepted')
"
```

- 실제 결과: 예외 없이 accepted.
- 실제 악용 가능성: `RevisionController.record()`(현재 유일한 revision 생성
  경로)는 매번 새 `revision-N` id를 순증가로 만들기 때문에 정상 경로로는 순환을
  만들 수 없다. 즉 이번 결함은 `validate_graph`를 직접 호출하는 다른 producer나
  손상된 데이터를 통해서만 도달 가능하며, 지금 저장소에는 그런 다른 producer가
  없다. 그래서 P0가 아니라 P2로 분류하되, `validate_graph`가 스스로 약속한
  "history invariants" 계약의 빈틈이므로 남겨둔다.
- Windows: 재현됨. macOS: `deferred/unknown`.

### 2-C. [관찰, P3] `RevisionController.record()`가 원본 노드가 그래프에 없으면 이력을 조용히 생략한다

- 위치: `src/graphori_core/compiler.py:429-447`
- 문제: `old_node`가 `graph.nodes`에 없으면(예: revision을 만들기 전에 원본
  `task_id` 노드를 그래프에 추가하지 않은 경우) 새 revision 노드는 만들어지지만
  `rework_of` edge는 예외 없이 그냥 생략된다.
- 재현: `RevisionController().record('revise', Task('t2','x'), Graph())` →
  `t2:revision-1` 노드는 생기지만 `rework_of` edge는 0개.
- 판단: `compile_topology()`가 만드는 그래프는 워커 노드 id가 `"worker"`이고
  `RevisionController`가 가정하는 노드 id는 `task.task_id`라서, 두 메커니즘이
  같은 그래프 안에서 함께 쓰인 예가 이 저장소에 없다(연결부 자체가 아직 없음).
  실행 결함이라기보다 두 컴포넌트가 아직 통합되지 않은 상태의 residual gap이다.
  통합 시점에는 "원본이 없으면 예외"로 fail-closed하게 만들 필요가 있다.

## 3. 검증 evidence 세부 확인 (요청 항목별)

### 3.1 evidence_ids / actor 위조 / platform pass 필수값

```text
평가 대상            결과
evidence_ids 없음      blocked
evidence_ids []        blocked
evidence_ids "ev1"     blocked (list 아님)
evidence_ids [""]      blocked
evidence_ids [" "]     blocked
evidence_ids [None]    blocked
evidence_ids [123]     blocked
evidence_ids None      blocked
payload.actor_role 위조 (worker가 'verifier' 자칭)  blocked
actor 필드 자체 누락                                blocked
platform pass, evidence_id 없음                     blocked
platform pass, evidence_id는 있지만 fixture/snapshot 둘 다 없음  blocked
platform pass, fixture는 있지만 evidence_id 없음    blocked
platform pass, evidence_id/fixture_id가 빈 문자열   blocked
```

전부 CLOSED. `reducer.py:130-149`(verdict), `:151-173`(platform)이 fail-closed로
동작한다.

### 3.2 이름/차원별 독립성 우회 (Fast/Standard/Critical/Human Gate)

```text
공격 시나리오                                              결과
identity만 다르고 나머지(provider/model/checkout/session/worktree) 전부 동일  blocked (모든 모드)
identity 동일, provider만 다름                              blocked (identity 동일 자체로 즉시 차단)
identity 다름, provider만 공유(나머지 다름) — worker 실제값 매칭   blocked
identity 다름, model만 공유                                 blocked
identity 다름, checkout만 공유                               blocked
identity 다름, session만 공유                                blocked
identity 다름, worktree만 공유                               blocked
Critical 두 verifier: provider+model만 공유                  blocked
Critical 두 verifier: checkout만 공유                        blocked
Critical 두 verifier: session만 공유                         blocked
Critical 두 verifier: worktree만 공유                        blocked
Human Gate pool: worker와 checkout 공유                      blocked
Human Gate pool: worker와 provider+model 공유                blocked
Human Gate pool 내부 identity 공유                            blocked
Human Gate pool 크기 1                                       blocked
Human Gate pool에 human_gate가 아닌 역할 포함                 blocked
Human Gate가 router_role='router'로 위장                     blocked
완전 독립(모든 차원 다름) verifier/gate                       정상 통과 (false positive 없음)
```

17가지 우회 시도 전부 CLOSED. 정상 케이스(완전 독립)가 거부되지 않는 것도 확인해
과잉 차단(false positive) 없음을 확인했다.

### 3.3 기본 topology 생성 확인

`verifier_roles`/`human_gate_roles`를 아예 넘기지 않았을 때도 Fast(`router,worker,
verifier,observer`), Standard(`router,worker,verifier,observer`),
Standard+Human Gate(`+human_gate`), Critical(`router,worker,verifier_normal,
verifier_adversarial,verifier_fanin,human_gate,observer`) 그래프가 모두 정상
생성됨을 확인했다. 기본 자동 생성 Role(`automatic-verifier`, `targeted-verifier`,
`normal-verifier`, `adversarial-verifier`, `human-gate-0/1`)은 서로 다른
provider/model/checkout을 갖도록 미리 설계되어 있어 독립성 검사를 자연히 통과한다.
worker의 provider/model/checkout을 공격자가 metadata로 이 기본값과 완전히
동일하게 맞춰도(`worker_provider=auto-provider` 등) identity가 다르면 여전히
"완전 동일 triple" 조건에만 걸려 차단됨을 확인했다(`standard_worker_verifier`
컨텍스트는 provider+model+checkout **세 값 모두** 같아야 차단하므로, 공격자가
세 값을 전부 일치시키면 오히려 스스로 차단당한다).

### 3.4 revision 1→원본, 2→1, 3→2, 4번째 gate, cycle 검사, history edge 예외

```text
revision-1 -> task (원본)
revision-2 -> task:revision-1
revision-3 -> task:revision-2
4번째 revise -> RevisionAction.ESCALATED, task.state=escalated,
                human_gate 노드에 metadata signal='human_gate_required' 부여
validate_graph(graph)  # 정상 체인은 예외 없이 통과
```

체인·4번째 gate·self-loop(길이 1) 예외는 CLOSED. 길이 2 이상 순환은 §2-B에서
OPEN으로 남김.

### 3.5 Fast 필드 누락/None/false, usage/uncertainty/external/high-risk 경계값

```text
base(known+local_only=True+reversible=True+external_effect=False) -> fast
usage_status 누락/None                 -> standard
local_only 누락/None/False/"true"(문자열)/1(정수) -> standard (진짜 bool True만 인정)
reversible  누락/None/False/"true"(문자열)/1(정수) -> standard
external_effect 누락/None/"false"(문자열) -> standard (진짜 bool False만 인정)
uncertainty=1 -> standard, uncertainty=2 -> critical
risk_level 0..4, -1 -> low/medium/high/critical/critical/low (음수는 clamp)
external_effect=True -> critical
tags=('high-risk',)/('HIGH-RISK',)/('high_risk',) -> critical (대소문자·구분자 무관)
tags=('unknown-tag',) -> critical 아님 (일반 태그는 hard trigger 아님, 정상)
budget_ok=False -> critical
usage_status='KNOWN'/' known '/'known ' -> known으로 정규화(대소문자·공백 무시, fast 가능)
usage_status=True/1/0/[]/{} -> unknown 취급 (fail-closed)
```

전부 CLOSED. tri-state(`None`/`False`/비bool)가 전부 "Fast 불가"로 fail-closed
처리됨을 재확인했다(Codex R3, Claude 이전 §2 boundary 표와 동일 결론 재현).

### 3.6 envelope 필수 필드 제거·타입 오염·seq 음수·digest/producer id 누락·unknown type

```text
schema_version/event_id/run_id/graph_version/seq/occurred_at/recorded_at/
actor/entity/payload 개별 제거(10개)         -> 전부 blocked
schema_version="1"(문자열)/True(bool)/2(버전) -> blocked
event_id/run_id 빈 문자열                     -> blocked
graph_version=-1, seq=-1, seq="1"(문자열)      -> blocked
seq=True(bool)                                -> blocked (type()is not int로 bool 배제)
graph_version=True(bool)                      -> blocked
occurred_at 빈 문자열                          -> blocked
actor={}(role 없음)                            -> blocked
actor 키 자체 누락                             -> blocked
entity="bad"(문자열, dict 아님)                -> blocked
entity.task_id 누락/정수형                     -> blocked
payload=[](리스트, dict 아님)                  -> blocked
usage 필드가 dict 아님                         -> blocked
platform 필드가 문자열 아님                    -> blocked
unknown/noncanonical type("nonexistent_type")  -> blocked
type="" (빈 문자열)                            -> blocked
digest/producer_event_id/prev_digest = None    -> ACCEPTED (§2-A, OPEN)
digest = 정수(문자열 아님)                     -> blocked
```

digest류 3개 필드의 `None` 우회를 제외한 나머지 전부 CLOSED.

### 3.7 fan-in role 타입 계약 / VERIFIES edge 방향·경로

- `verifier_fanin.role` → `None` (Role 타입 계약 유지, 문자열 오염 없음). CLOSED.
- `verifier_fanin.metadata['fan_in']` → `True`로 정상 보존. CLOSED.
- `validate_graph`는 fan-in이 아닌 verifier의 `VERIFIES` 대상이 반드시
  `NodeKind.WORKER`여야 하고, fan-in verifier의 `VERIFIES` 대상은 반드시
  `NodeKind.VERIFIER`여야 함을 실제로 강제한다. verifier가 관계없는 노드(observer)를
  가리키거나, fan-in이 worker를 직접 가리키는 시도 모두 `GraphValidationError`로
  차단되는 것을 확인했다. CLOSED.
- 방향 자체(`verifier -> worker`, `fan_in -> normal/adversarial`, `terminal ->
  observer`)는 구현과 테스트가 일관되게 "source가 관찰/검증 행위의 주체"라는
  동일한 규칙을 따른다. `GRAPHORI_ARCHITECTURE.md` §5와 `EVENT_PROTOCOL.md` §4.2는
  edge kind의 방향을 명시적으로 못박지 않아 문서 자체가 다소 모호하다 — 이는
  이전 Claude 재검수(§3.3)에서도 지적한 P2 문서 정합성 이슈이며 이번에도 동일하게
  남아 있다(코드 결함이 아니라 문서 명확화 필요).

### 3.8 같은 platform의 여러 fixture/snapshot verdict 덮어쓰기 여부

```text
windows fixture fx-1 (pass, evidence ev-1)  -> 저장
windows snapshot snap-2 (pass, evidence ev-2) -> 저장 (fx-1과 별도 유지)
macos (deferred, evidence/fixture 없음)      -> 저장
platform_summary()["platform_verdicts"]["windows"]["verdicts"] 길이 == 2 (둘 다 보존)
scope == "windows", exclusions == ["macos"]
```

CLOSED — `PlatformVerdict` key가 `platform|fixture_id|snapshot_id` 복합 키라서
서로 다른 fixture/snapshot은 겹쳐 쓰지 않는다. 같은 `fixture_id`를 재기록하면
최신값으로 갱신되는데(예: fail→pass), 이는 writer 계층의 idempotency와 별개인
"프로젝션 최신화"로서 reducer 책임 범위 안에서는 합리적이다.

**관찰(P3)**: 같은 platform에 fixture A(pass)와 fixture B(fail)가 공존하면
`platform_summary()["exclusions"]`에는 그 platform이 나타나지 않는다(하나라도
pass가 있으면 scope에 포함). "70%를 예쁘게 만들려고 캐릭터를 움직이지 않는다"는
`GRAPHORI_ARCHITECTURE.md` 원칙에 비춰보면, 같은 platform 안에 fail fixture가
있는데도 `scope`에 해당 platform이 포함되는 것은 다소 낙관적으로 보일 수 있다.
다만 이 필드의 "부분 실패 시 platform 전체를 scope에서 뺄지"는 canonical 문서가
명시하지 않으므로 결함이 아니라 향후 설계 결정이 필요한 지점으로 남긴다.

### 3.9 구현이 자기 구현만 따라가 canonical 문서와 어긋난 곳

- `EVENT_TYPES`(reducer.py:16-23)는 `EVENT_PROTOCOL.md` 부록 A의 23개 타입과
  정확히 일치한다(이전 Claude 재검수가 지적한 `task_status_changed` 비canonical
  타입은 제거됨). **CLOSED.**
- 하지만 `StateReducer.apply()`(110-174줄)는 `node_status_changed`,
  `verdict_recorded`, `platform_verdict_recorded`, 방어적 `task_status_changed`(비
  canonical, 별도로 거부됨) 외의 **19개 canonical 타입**(`run_created`,
  `run_terminal`, `heartbeat`, `graph_published`, `role_assigned`,
  `worker_finished`, `gate_resolved`, `usage_recorded` 등)을 envelope 통과 후
  아무 프로젝션도 만들지 않고 조용히 `self`만 반환한다. 에러는 아니지만
  "지원한다고 선언한 event마다 payload 의미를 검증해야 한다"(이전 Codex 재검수
  권고 5번)는 아직 충족되지 않았다.
- `Run`/`RunState`(models.py:147-153, 287-295)는 여전히 `StateReducer`에 전혀
  연결되지 않는다. `run_created`/`run_terminal` 이벤트를 넣어도 `Run.state`는
  바뀌지 않는다(직전 재검수 §3.4와 동일, 미해결). `RunState`
  값 집합(planned/running/succeeded/failed/blocked/escalated)도 `TerminalStatus`
  (succeeded/failed/cancelled/rejected/blocked/inconclusive)와 여전히 다르다.
- 이 두 항목은 `docs/IMPLEMENTATION_PLAN.md` 2단계 acceptance("in-memory fixture
  세 가지가 동일한 graph와 terminal projection을 만들고, scheduling cycle·
  same-attempt verifier·revise 4회가 거절된다")를 문자 그대로는 벗어나지 않으므로
  이번 REVISE의 근거로 새로 추가하지는 않되, 잔존 위험(§5)으로 다시 명시한다.

### 3.10 stdlib-only / Windows 실행 / macOS deferred

§0 참고. AST 기반 import 전수조사로 stdlib(`__future__`, `dataclasses`, `enum`,
`typing`) + sibling module 외 0건 확인. `python -m unittest`/`compileall`/
`pip install --target`/`import`를 Windows에서 직접 실행해 통과 확인. macOS는
실행하지 않았으므로 `deferred/unknown`으로 유지한다.

## 4. 부가로 발견한 사소한 관찰 (P3, 이번 REVISE의 사유는 아님)

- `NodeState.REJECTED`가 canonical enum에는 있지만 `NODE_TRANSITIONS` 표에는
  어떤 상태에서도 도달 가능한 target으로 등장하지 않는다. 즉 `transition_node`를
  통해서는 `rejected` 상태에 절대 도달할 수 없다(fail-safe 방향의 과잉 차단이라
  취약점은 아니나, 문서의 14개 canonical 값 중 하나가 사실상 죽은 값이라는 완전성
  문제).
- `compile_risk`/`_risk_input`에 `uncertainty='high'`, `scope=None`처럼 bool/int가
  아닌 metadata를 직접 넣으면 `StateTransitionError` 같은 도메인 예외가 아니라
  raw `ValueError`/`TypeError`가 그대로 올라온다. 이 경로는 검증된 event envelope가
  아니라 `Task.metadata`를 직접 구성하는 내부 API 경로라 외부 공격 표면은 아니지만,
  에러 메시지 일관성 관점에서 개선 여지가 있다.

## 5. 잔존 위험 (I02 범위 밖 또는 후속 단계)

- §2-A(digest류 `None` 통과), §2-B(rework_of 길이 2+ 순환 미검증)는 다음 검수까지
  닫아야 할 항목이다.
- Run/RunState가 reducer에 연결되지 않은 문제(§3.9)는 여러 라운드째 미해결이며,
  범위가 애매하다는 이유로 계속 미루기보다 다음 단계에서 명시적으로 스코프인지
  아닌지 결정이 필요하다.
- `EdgeKind.VERIFIES`/`OBSERVES`의 방향을 canonical 문서가 명시하지 않는 모호함은
  코드 문제가 아니라 문서 결정 사항으로 남는다(§3.7).
- macOS 실행: 여전히 `deferred/unknown`. 이번 검수도 Windows에서만 실행했다.
- `active_wip`/`task_parallelism`/fan-in queue/priority 정렬, Human Gate holder
  heartbeat/takeover는 `IMPLEMENTATION_PLAN.md` 3~9단계 범위이며 이번 2단계 core
  구현에는 없다. 없는 것 자체는 REVISE 사유가 아니다.

## 6. 재현 명령 요약 (전부 읽기 전용, 구현/테스트 파일 미수정)

```bash
python --version
python -m unittest discover -s tests -v
python -m compileall -q src tests
git status --short
git diff --check

# §2-A digest/producer_event_id/prev_digest = None 우회
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, StateReducer, canonical_event; ev=canonical_event('node_status_changed', payload={'status':'ready'}, entity={'node_id':'n'}); ev['digest']=None; ev['producer_event_id']=None; ev['prev_digest']=None; StateReducer(Task('t','x')).apply(ev); print('accepted')"

# §2-B rework_of 2노드 순환
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Graph, Node, NodeKind, Edge, EdgeKind, validate_graph; g=Graph(); g.add_node(Node('A',NodeKind.WORKER,'a')); g.add_node(Node('B',NodeKind.WORKER,'b')); g.add_edge(Edge('A','B',EdgeKind.REWORK_OF)); g.add_edge(Edge('B','A',EdgeKind.REWORK_OF)); validate_graph(g); print('cycle accepted')"

# 이전 P0 재현 (모두 blocked 확인)
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, StateReducer, canonical_event; r=StateReducer(Task('t','x')); [ (r.apply(canonical_event('node_status_changed', payload={'status':s}, entity={'node_id':'n1'})), print(s, r.node_statuses['n1'].value)) for s in ['ready','assigned','running','awaiting_verification','passed'] ]"
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, Role, NodeKind, compile_topology; v=Role('rv','_','x','',''); "  # (본문 §3.2 조합은 report 상단 표 참고, 실제 실행은 각 case별로 수행)

# 이식성
python -m pip install . --no-deps --target <tmp> -q && PYTHONPATH=<tmp> python -c "import graphori_core; print('ok')"
```

## 7. 결론

**REVISE — 그러나 범위는 크게 줄었다.** 이전 재검수 라운드에서 열려 있던 P0
3건(Node 역방향, evidence 없는 pass, identity-only 독립성 우회)과 P1
1건(rework_of self-loop), Codex R1~R6 중 5건(R1,R2,R3,R5,R6)은 이번 공격에서
전부 CLOSED로 재확인됐다. 남은 것은 새로 발견한 P1 1건(§2-A, digest류 필드의
`None` 우회 — writer 권한이 있어야 도달 가능해 P0보다는 좁음)과 P2 1건(§2-B,
`rework_of` 길이 2+ 순환을 `validate_graph`가 놓침 — 현재 유일한 생성 경로인
`RevisionController`로는 도달 불가)뿐이다. 두 항목 모두 각각 3줄 안팎의 국소
수정으로 닫을 수 있는 규모로 보이며, 지난 라운드처럼 여러 곳에 반복되는 패턴이
아니라 독립된 두 지점의 문제다. 이 두 항목을 닫고 회귀 테스트(§2-A: `digest`/
`producer_event_id`/`prev_digest`가 `None`이면 거부; §2-B: 길이 2 이상
`rework_of` 순환이 거부됨)를 추가한 뒤 동일 명령으로 재검수하면 APPROVE를 논의할
수 있는 상태라고 판단한다. macOS는 이번에도 실행하지 않았으므로 `deferred/unknown`
이며, 이 보고서의 모든 판정은 Windows 실행 결과에만 근거한다.
