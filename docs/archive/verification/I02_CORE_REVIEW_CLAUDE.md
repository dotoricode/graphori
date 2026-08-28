# I02 portable core 독립 검수 (Claude)

> 검수 대상: `src/graphori_core/*`, `tests/test_core.py`, `pyproject.toml`
> 기준 문서: `TEAM_TOPOLOGY.md`, `docs/architecture/GRAPHORI_ARCHITECTURE.md`,
> `docs/architecture/EVENT_PROTOCOL.md`, `docs/architecture/PORTABILITY_CONTRACT.md`,
> `docs/decisions/0001~0004`, `docs/IMPLEMENTATION_PLAN.md`,
> `docs/verification/I02_CORE_BUILD_REPORT_LUNA.md`
> 검수자: Claude (독립, 구현 파일 미수정)
> 실행 환경: Windows, Python 3.12.1 (`requires-python >=3.11` 충족)
> macOS: 실행하지 않음. `deferred/unknown`.

## 0. 결론

**REVISE.** stdlib-only/enum 형태는 대체로 준수하지만, 문서가 명시한 핵심 불변식
3건이 실제 코드에서 깨져 있고(재현 확인됨), reducer는 정상 canonical 이벤트
다수에서 크래시한다. 테스트가 이 경로들을 전혀 건드리지 않아 통과 상태로
보고되었다.

## 1. 재실행 결과

```text
$ python --version
Python 3.12.1
$ python -m unittest discover -s tests -v
test_critical_verifiers_are_independent_and_same_attempt_forbidden ... ok
test_cycle_rejection_excludes_history_edges ... ok
test_platform_partial_scope_preserves_windows_and_macos ... ok
test_revise_escalates_on_fourth_revise ... ok
test_three_mode_fixtures ... ok
test_unknown_usage_is_not_zero ... ok

Ran 6 tests in 0.001s
OK
```

보고서(`I02_CORE_BUILD_REPORT_LUNA.md`)의 결과와 일치한다(테스트 6개 전부
pass). 그러나 아래에서 보이듯 통과하는 6개 테스트는 모두 해피패스이며, 실제
불변식 위반은 테스트되지 않은 경로에서 발생한다.

`import` 점검: `grep -E "import orca|anthropic|openai|subprocess" src/graphori_core`
결과 0건. `orca`/`Claude`/`OpenAI` SDK, OS별 프로세스 API import 없음을 확인했다
(stdlib-only 요건 충족).

## 2. P0 — 핵심 불변식 위반 (재현됨)

### P0-1. reducer가 worker 작성 verdict를 조용히 승인함

`src/graphori_core/reducer.py:26-29`

```python
elif event_type == "verdict_recorded":
    verdict = VerdictKind(str(payload.get("verdict")))
    actor_role = str(payload.get("actor_role", "verifier"))
    if actor_role == "worker":
        raise StateTransitionError("worker cannot publish a verdict")
```

`EVENT_PROTOCOL.md` §3의 envelope 예시는 actor 정보를 `event["actor"]["role"]`
에 둔다(`payload` 안이 아니다). 그런데 reducer는 `payload.get("actor_role", ...)`
만 읽고, 이 키가 없으면 기본값을 `"verifier"`로 가정한다. 정상 스펙을 따르는
실제 이벤트(`actor.role=worker`, `payload`에는 `actor_role` 없음)를 넣으면
가드가 전혀 발동하지 않는다. `GRAPHORI_ARCHITECTURE.md` 기술 부록 A의
"`worker`는 verdict를 만들 수 없고, `verifier` 또는 `human_gate`만 verdict를
만든다"는 canonical 불변식이 코드 경로에서 실제로 강제되지 않는다.

재현:

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, reduce_event
t = Task('t','x')
event = {'type':'verdict_recorded','actor':{'role':'worker'},'payload':{'verdict':'pass'}}
r = reduce_event(t, event)
print(r.verdicts)   # -> [<VerdictKind.PASS: 'pass'>]  (예외 없이 통과)
"
```

부가로 `actor_role`을 `"worker"`가 아닌 다른 값(예: `"router"`, `"observer"`)으로
주면 그 역시 통과한다. 문서는 "verifier 또는 human_gate만" 허용하는데 구현은
"worker만 아니면" 허용이라 화이트리스트가 아니라 블랙리스트로 되어 있다.

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, reduce_event
t = Task('t2','x')
event = {'type':'verdict_recorded','actor':{'role':'router'},'payload':{'verdict':'approve'}}
print(reduce_event(t, event).verdicts)  # -> [<VerdictKind.APPROVE: 'approve'>]
"
```

### P0-2. reducer가 canonical `node_status` 값 대부분에서 크래시함

`src/graphori_core/reducer.py:21-23`

```python
if event_type == "node_status_changed" or event_type == "task_status_changed":
    target = TaskState(str(payload.get("state")))
    transition_task(self.task, target)
```

`node_status_changed` 이벤트의 `payload.state`는 `EVENT_PROTOCOL.md`의
`node_status` enum(`pending|ready|assigned|running|awaiting_verification|
queued|stale|outcome_unknown|passed|failed|cancelled|blocked|rejected|
inconclusive`)이어야 하는데, reducer는 이를 `models.TaskState`
(`planned|ready|running|succeeded|failed|blocked|escalated`)로 강제 변환한다.
두 enum의 값 집합이 다르므로 `passed`, `pending`, `assigned`,
`awaiting_verification`, `queued`, `stale`, `outcome_unknown`, `cancelled`,
`rejected`, `inconclusive` 같은 정상 canonical 값을 담은 진짜 이벤트를 넣으면
`ValueError`가 발생한다.

재현:

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, reduce_event
t = Task('t','x')
for state in ['passed','pending','assigned','awaiting_verification','queued',
              'stale','outcome_unknown','cancelled','rejected','inconclusive']:
    try:
        reduce_event(t, {'type':'node_status_changed','payload':{'state': state}})
        print(state, 'OK')
    except Exception as e:
        print(state, 'ERROR', e)
"
# 10개 값 모두 "ValueError: '<value>' is not a valid TaskState"
```

Node 수준 이벤트를 Task 수준 enum으로 잘못 변환하고 있으므로, 정상적인
`node_status_changed` 이벤트 흐름을 reducer가 대부분 처리하지 못한다.

### P0-3. Standard/Critical topology가 verifier와 worker의 동일 identity를 거부하지 않음

`src/graphori_core/compiler.py:173-221`, 특히 191-216

`compile_topology`는 Critical 분기에서 `independent_verifier(normal, adversarial)`
만 호출해 두 verifier 사이의 독립성만 검사한다. `worker_role`과 verifier
role(들) 사이의 독립성은 어디에서도 검사하지 않는다. `GRAPHORI_ARCHITECTURE.md`
§4 "Verifier는 작성 Worker와 attempt/provider/model/checkout 중 최소 한 차원
이상 달라야 한다"와 `TEAM_TOPOLOGY.md` §4 "Worker를 Verifier로 겸직하지
않는다"를 위반한다. Standard 분기는 독립성 검사 호출 자체가 없다.

재현 (Critical에서도 재현됨 — 두 verifier끼리는 다르지만 normal verifier가
worker와 완전히 동일):

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, compile_topology, Risk, Role, NodeKind
worker_like = Role('role_worker', NodeKind.VERIFIER, 'worker', '', '', '')
other = Role('role_verifier_adversarial', NodeKind.VERIFIER, 'adversarial-verifier', 'provider-b', 'model-b', 'checkout-b')
task = Task('t-crit', 'boundary', risk=Risk.CRITICAL)
topo = compile_topology(task, verifier_roles=(worker_like, other))
w, vn = topo.roles['worker'], topo.roles['verifier_normal']
print((w.identity, w.provider, w.model, w.checkout))
print((vn.identity, vn.provider, vn.model, vn.checkout))
print('identical:', (w.identity,w.provider,w.model,w.checkout) == (vn.identity,vn.provider,vn.model,vn.checkout))
# -> identical: True, 예외 없이 CompiledTopology 반환됨
"
```

Standard 모드도 동일하게 재현된다(verifier_roles로 worker와 동일 Role을
넘기면 그대로 컴파일된다). `verify_attempt()` 자체(빌더/검증자 attempt 비교
함수)는 올바르게 동작하지만(§3 참고), `compile_topology`가 role 배정 시점에
동일한 검사를 적용하지 않아 애초에 독립적이지 않은 topology가 "정상"으로
생성될 수 있다.

## 3. P1

### P1-1. usage_status 기본값이 "known"이라 미기록 사용량이 known으로 둔갑

`src/graphori_core/compiler.py:36`(`RiskInput.usage_status: str = "known"`),
`compiler.py:73`(`usage_status=str(metadata.get("usage_status", "known"))`)

`GRAPHORI_ARCHITECTURE.md` §2.5 "`usage`가 없으면 0이 아니라 `unknown`이다"
원칙과 반대로, `Task.metadata`에 `usage_status`를 아예 넣지 않으면 risk
compiler는 이를 `"known"`으로 간주한다. 사용량을 측정/보고하지 않은 평범한
Task가 기본값만으로 Fast 자격을 얻는다.

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, compile_risk
t = Task('t1', 'some task')   # metadata 없음
r = compile_risk(t)
print(r.mode, r.hard_triggers)   # -> fast ()  usage_unknown 트리거가 전혀 없음
"
```

### P1-2. usage unknown이면 무조건 Critical — ADR0004의 "Standard 조사 또는 Critical 검토" 선택지가 코드에 없음

`compiler.py:100-101`(`if str(raw.usage_status).lower() == "unknown": triggers.append("usage_unknown")`),
`compiler.py:106-108`(트리거가 하나라도 있으면 항상 `Risk.CRITICAL/TaskMode.CRITICAL`)

`ADR 0004` 12살 설명: "모르는 작업을 빠른 버튼으로 보내지 않고 **Standard
조사나 Critical 검토**로 올린다." 그러나 구현은 `usage_status=="unknown"`을
다른 hard trigger(`security-boundary`, `personal-data` 등)와 동일하게 처리해
무조건 Critical(정상 verifier 2인 + adversarial + Human Gate fan-in 전체)로
승격시킨다. score=0인 완전히 사소한 작업도 usage 하나만 unknown이면 Critical
전체 그래프가 강제된다.

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import RiskInput, compile_risk
r = compile_risk(RiskInput(risk_level=0, uncertainty=0, scope=0, synthesis=0,
                            parallelism=0, usage_status='unknown'))
print(r.risk, r.mode, r.hard_triggers, r.score)
# -> critical critical ('usage_unknown',) 0
"
```

`tests/test_core.py:86`의 `test_unknown_usage_is_not_zero`가 이 동작(무조건
Critical)을 그대로 assert하고 있어, 의도된 설계인지 실수인지 테스트만으로는
구분되지 않는다. 문서 문구와 다르므로 설계 의도를 확인하고, Standard 승격
경로를 추가하거나 문서를 갱신해야 한다.

### P1-3. `TaskState.ESCALATED`가 막다른 상태라 Human Gate 재개/축소를 표현할 수 없음

`compiler.py:267-274`

```python
TASK_TRANSITIONS = {
    ...
    TaskState.SUCCEEDED: frozenset(), TaskState.ESCALATED: frozenset(),
}
```

`TEAM_TOPOLOGY.md` §6: "3회를 넘기려는 revise는... `human_gate_required`로
전환한다. Gate는 범위 축소, 추가 evidence, 다른 실행 환경, 중단 중 하나를
선택한다." 즉 ESCALATED 이후 Gate 결정에 따라 재개(READY) 또는 중단
(BLOCKED/FAILED) 등으로 전이할 수 있어야 하는데, `TASK_TRANSITIONS`는
`ESCALATED`를 `SUCCEEDED`와 동일하게 종단(빈 frozenset)으로 막아 놓았다.
`transition_task`로는 Gate의 어떤 결정도 표현할 수 없다.

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, TaskState
from graphori_core.compiler import transition_task, StateTransitionError
t = Task('t','x'); t.state = TaskState.ESCALATED
try:
    transition_task(t, TaskState.READY)
except StateTransitionError as e:
    print('blocked:', e)
"
```

### P1-4. Human Gate authority 독립성 검사 함수가 없음

`TEAM_TOPOLOGY.md` §4: "Human Gate authority pool도 최소 2명이다. 승인자는
Worker, Verifier, Router와 identity/provider/model/checkout을 공유하지 않는다."
`compiler.py`에는 `independent_verifier`(verifier-verifier 전용)만 있고,
Human Gate 후보를 Worker/Verifier/Router와 비교하는 대응 함수가 없다.
`compile_topology`도 `gate_role`을 고정 식별자(`"human-gate"`, provider/model/
checkout 공란)로만 생성하고 외부에서 주입하거나 독립성을 검사할 경로가 없다.

### P1-5. `Run` 엔티티가 models.py에 전혀 없음

`docs/IMPLEMENTATION_PLAN.md:23` (2단계): "Run/graph/node/edge/attempt/reducer/
risk compiler를 구현한다." `GRAPHORI_ARCHITECTURE.md` §3.1도 core가 소유하는
것으로 "Run, graph version, node, edge, ..."을 나란히 명시한다. 그러나
`src/graphori_core/models.py`에는 `Task`/`Attempt`/`Node`/`Edge`/`Graph`만 있고
`Run`, `run_id`, `graph_version` 필드/클래스가 전혀 없다(`grep -rn "class Run"`
0건). `I02_CORE_BUILD_REPORT_LUNA.md`도 구현 목록에 Run을 언급하지 않아, 2단계
acceptance 대비 누락이 자체 보고서에도 드러나지 않는다.

### P1-6. reducer가 미지의 이벤트 타입을 전부 조용히 무시함

`reducer.py:18-34` (`apply` 메서드) — `if/elif` 3개 분기 외에는 `else`가
없고 그대로 `return self`한다. 오탈자(`"verdict_recordedd"` 등)나 스펙에
정의된 다른 canonical 타입(`heartbeat`, `retry_created`, `idempotency_conflict`
등, `EVENT_PROTOCOL.md` 기술 부록 A)이 들어와도 예외/로그 없이 그냥 지나간다.

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Task, reduce_event
t = Task('t','x')
r = reduce_event(t, {'type':'verdict_recrded','payload':{'verdict':'pass'}})
print(r.verdicts)  # -> [] (오류/경고 없음)
"
```

이 reducer가 §1의 3개 이벤트만 다루도록 의도적으로 범위를 좁힌 것이라면
문서화가 필요하고, 그렇지 않다면 최소한 unknown-type을 명시적으로
`raise`하거나 로그를 남겨야 한다. "잘못된 payload/status를 조용히 받지 않는지"
검수 항목과 직접 관련된다.

### P1-7. 테스트가 해피패스 위주라 위 P0 3건을 전혀 잡지 못함

`tests/test_core.py`의 6개 테스트는 각각 하나의 성공 시나리오 + 부분적인
음성 케이스만 다룬다. 아래 경로는 테스트가 전혀 없다.

- `transition_task`/`transition_attempt` — 성공/실패 전이 어느 쪽도 테스트 0건.
- Standard 모드 verifier 독립성(§4) — 애초에 검사되지 않는데(P0-3) 테스트도 없음.
- `verify_attempt`의 "동일 identity, 다른 attempt_id" 분기 — 코드 자체는
  정상 동작하지만(아래 재현 참고) 전용 테스트가 없어 회귀에 취약함.
- reducer의 실패/거부 경로 — 잘못된 `verdict`, worker-verdict, 잘못된
  `node_status`, 알 수 없는 이벤트 타입 모두 테스트 없음(P0-1/P0-2/P1-6이
  이 사각지대에서 발견됨).
- `compile_risk`의 score 경계값(3, 7)과 `risk_level` 단독 값들의 조합 —
  테스트 없음.
- `Graph.add_node`/`add_edge`의 중복/누락 참조 오류 — 테스트 없음.

`verify_attempt`의 동일 identity 분기 자체는 정상 동작함을 확인함(참고용,
버그 아님):

```bash
python -c "
import sys; sys.path.insert(0,'src')
from graphori_core import Attempt, AttemptState, Role, NodeKind, verify_attempt, IndependenceError
role_a = Role('r1', NodeKind.WORKER, 'same-person', 'openai', 'gpt', 'checkout-x')
role_b = Role('r1', NodeKind.VERIFIER, 'same-person', 'openai', 'gpt', 'checkout-x')
builder = Attempt('a1', 't', role_a, AttemptState.SUCCEEDED)
verifier = Attempt('a2', 't', role_b, AttemptState.SUCCEEDED)
try:
    verify_attempt(builder, verifier)
except IndependenceError as e:
    print('correctly rejected:', e)
"
```

### P1-8. 첫 커밋 오염 위험: `.gitignore` 없음 + `__pycache__` 이미 생성됨

저장소 전체에 `.gitignore`가 없다(`find . -iname ".gitignore"` 0건, 루트/하위
어디에도 없음). 이미 `src/graphori_core/__pycache__/*.pyc`,
`tests/__pycache__/*.pyc`가 생성되어 있고 git status상 미추적 상태다. 이 상태로
`git add -A`/첫 커밋을 하면 바이트코드가 저장소에 편입된다. 최소
`__pycache__/`, `*.pyc`, `.venv/` 등을 포함하는 `.gitignore`를 커밋 전에
추가해야 한다.

## 4. P2

- **P2-1.** `models.py`의 `TaskMode`/`Risk`가 동일 문자열 값에 대문자/소문자
  이름을 중복 정의한다(예: `FAST = "fast"`와 `Fast = "fast"`). Python enum
  규칙상 이는 별개 멤버가 아니라 alias로 접혀 `list(TaskMode)`에는 3개만
  나온다(`TaskMode.Fast is TaskMode.FAST == True`로 확인). 동작상 버그는
  아니지만 불필요한 코드이며 다음에 값이 갈라지면 혼란을 유발할 수 있다.
- **P2-2.** Fast/Standard verifier 노드에는 `EVENT_PROTOCOL.md`의
  `verification`(`none|automatic|targeted|fresh_full|adversarial`) 값이
  메타데이터로 기록되지 않는다(`compiler.py:187-195`, node label 문자열만
  존재). Critical verifier만 `verification="fresh_full"/"adversarial"`을
  metadata로 남긴다(`compiler.py:206-207`). 확인:
  `compile_topology(...).graph.nodes['verifier'].metadata` → `{}`.
- **P2-3.** `ATTEMPT_TRANSITIONS`에서 `DISPATCHED`는 `RUNNING`을 거치지 않고는
  `CANCELLED`로 갈 수 없다(`compiler.py:284-292`). 실행 시작 전에 취소된
  attempt를 표현하려면 `RUNNING`을 경유하거나 `LOST`로 우회해야 하는데,
  문서(`EVENT_PROTOCOL.md` §4.3)의 화살표 표기가 이를 명확히 배제하지 않아
  경미하게 표기한다.

## 5. 확인된 정상 동작 (참고)

- stdlib-only: `src/graphori_core/*`에 `orca`/`anthropic`/`openai`/`subprocess`
  import 없음.
- `validate_graph`가 `requires`/`requires_gate` cycle만 거부하고
  `rework_of` cycle은 허용함(§테스트 `test_cycle_rejection_excludes_history_edges`,
  코드 재검토로 재확인).
- `RevisionController`가 3회까지 REVISED, 4번째부터 ESCALATED, `revise_count`가
  3에서 더 늘지 않음(§테스트 및 코드 재확인, `TEAM_TOPOLOGY.md` §6과 일치).
  단, ESCALATED 이후 상태 전이 표현이 막혀 있다는 점은 P1-3 참고.
  ADR와 무관하게 이 카운터 자체는 문서와 정확히 일치한다.
- `verify_attempt`는 "동일 attempt" 및 "동일 identity(다른 attempt)" 두
  경우 모두 정확히 거부한다(P0-3에서 지적한 것은 `compile_topology`가 이
  함수를 role 배정 시점에 호출하지 않는다는 점이며, 함수 자체는 옳다).
- `platform_verdict_recorded` reducer 경로는 Windows `pass`/macOS `deferred`를
  동시 보존하고 `complete_scope`/`exclusions`를 문서(§6 partial verdict)와
  일치하게 계산함.
- `pyproject.toml`은 `requires-python = ">=3.11"`, 외부 dependency 없음,
  `src/` 레이아웃으로 packaging 목적에 부합함.

## 6. 재현 명령 요약

```bash
# P0-1
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, reduce_event; t=Task('t','x'); print(reduce_event(t, {'type':'verdict_recorded','actor':{'role':'worker'},'payload':{'verdict':'pass'}}).verdicts)"

# P0-2
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, reduce_event; t=Task('t','x'); reduce_event(t, {'type':'node_status_changed','payload':{'state':'passed'}})"

# P0-3
python -c "import sys; sys.path.insert(0,'src'); from graphori_core import Task, compile_topology, Risk, Role, NodeKind; w=Role('role_worker',NodeKind.VERIFIER,'worker','','',''); o=Role('x',NodeKind.VERIFIER,'adv','p','m','c'); t=compile_topology(Task('t','x',risk=Risk.CRITICAL), verifier_roles=(w,o)); print(t.roles['worker']==t.roles['verifier_normal'])"

# 실행 환경 확인
python --version
python -m unittest discover -s tests -v
find . -iname ".gitignore"
```

## 7. 총평 및 요구사항

- **REVISE.** P0-1/P0-2/P0-3은 각각 "verdict는 verifier/human_gate만",
  "canonical node_status 처리", "Critical/Standard verifier 독립성"이라는
  이번 검수의 필수 확인 항목 그 자체이며 모두 재현 가능한 결함이다.
- P1-1/P1-2는 ADR 0004의 "usage unknown → Standard 조사 또는 Critical 검토"
  문구와 실제 코드(무조건 Critical, 게다가 미기록 시 기본 known)가 어긋난다.
  설계 의도를 명확히 하고 문서 또는 코드 중 하나를 수정해야 한다.
- P1-7이 지적하듯 현재 테스트 스위트는 6개 모두 통과하지만 핵심 실패
  경로를 검증하지 않아 "OK"가 안전하다는 신호가 되지 못한다. 재검수 시
  P0/P1 각각에 대한 회귀 테스트 추가를 요청한다.
- macOS는 실행하지 않았으므로 `deferred/unknown`이며, 이 보고서의 판정은
  Windows 실행 결과에만 근거한다.
