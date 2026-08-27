Exit code: 0
Wall time: 0.9 seconds
Output:
# I02 portable core revision-3 최종 독립 검수 보고서 (Codex)

검수일: 2026-08-09 (Windows, Python 3.12)

## 한눈에 보는 판정

**REVISE**입니다. 이전에 보고된 P0/P1 중 actor 권한, 증거 없는 verdict,
node terminal 역전, Fast 조건, 독립성 우회, revision history cycle은 실제 코드와
회귀 테스트에서 닫혔습니다. 그러나 이번 독립 검수에서 I02 계약에 해당하는 새 P1
세 건을 찾았습니다. `run_terminal`이 아직 끝나지 않은 작업을 성공으로 만들고,
Run이 주입된 경우 `run_created`를 건너뛸 수 있으며, 첫 사건의 Task ID가 다른데도
Run에 묶입니다.

macOS는 이 Windows 환경에서 실행할 수 없으므로 **deferred/unknown**입니다.

## Finding 1 — P1: 끝나지 않은 노드가 있어도 Run 성공을 허용함

### 증거

`docs/architecture/EVENT_PROTOCOL.md` §6은 모든 필수 scope가 terminal이고 gate
조건이 충족될 때만 Run이 `succeeded`가 된다고 정합니다. 그런데
`src/graphori_core/reducer.py:201-213`의 `run_terminal` 처리는
`graph_published` 여부와 terminal 값만 보고 node 상태나 gate 완료를 확인하지
않습니다.

### 실행 명령

```powershell
@'
import sys
sys.path.insert(0, 'src')
from graphori_core import *
t=Task('t','x',run_id='r',graph_version=1)
r=Run('r',1)
r.graph.add_node(Node('n',NodeKind.WORKER,'pending'))
p=StateReducer(t,r)
p.apply(canonical_event('run_created',run_id='r',task_id='t',graph_version=1))
p.apply(canonical_event('graph_published',run_id='r',task_id='t',graph_version=1))
p.apply(canonical_event('run_terminal',run_id='r',task_id='t',graph_version=1,
                       payload={'terminal_status':'succeeded'}))
print('PENDING_NODE_TERMINAL_ACCEPTED', r.terminal_status.value)
'@ | python -
```

### 결과

`PENDING_NODE_TERMINAL_ACCEPTED succeeded`가 출력되었습니다. 노드가 `pending`인
상태에서도 성공 projection이 만들어집니다.

### 판정

**P1 OPEN — I02 계약 위반.** Run terminal projection은 모든 필수 노드의 terminal
상태와 gate 조건을 확인한 뒤에만 성공을 기록해야 합니다. Stage3 writer나 실제
hash-chain의 미구현 문제가 아니므로 후속 단계 residual로 내릴 수 없습니다.

## Finding 2 — P1: 주입된 Run에서는 `run_created` 없이 graph를 공개할 수 있음

### 증거

`StateReducer.__post_init__`(`reducer.py:133-144`)가 이미 `Run`을 받으면 projection을
준비하지만, `run_created`를 보았다는 표시를 세우지 않습니다. 이후
`reducer.py:187-200`은 `self.run is not None`이면 `graph_published`를 받아들입니다.
따라서 요구된 `run_created → graph_published → run_terminal` 순서가 초기 Run 주입
경로에서 깨집니다.

### 실행 명령

```powershell
@'
import sys
sys.path.insert(0, 'src')
from graphori_core import *
t=Task('t','x',run_id='r',graph_version=1)
p=StateReducer(t, Run('r',1))
p.apply(canonical_event('graph_published',run_id='r',task_id='t',graph_version=1))
print('A_ACCEPTED graph_published_without_run_created', p.graph_version)
'@ | python -
```

### 결과

`A_ACCEPTED graph_published_without_run_created`가 출력되었습니다.

### 판정

**P1 OPEN — I02 순서 불변식 위반.** 초기 Run 객체를 주입해도 해당 projection에
`run_created`가 없으면 `graph_published`를 거부해야 합니다. 정상 순서 테스트가
있다는 사실만으로 역순/생략 경로가 닫힌 것은 아닙니다.

## Finding 3 — P1: 첫 Run 사건의 Task ID가 달라도 받아들임

### 증거

`reducer.py:150-161`의 `_validate_context`는 Run 또는 Task가 이미 연결된 경우에만
`entity.task_id`를 비교합니다. 아직 Run이 없는 첫 `run_created`에서는 비교하지
않고, `reducer.py:163-169`의 `_ensure_run`이 사건의 Run ID를 Task에 바로 씁니다.
그래서 실제 Task가 `task-real`인데 사건 entity가 `task-other`여도 잘못된 binding이
생깁니다.

### 실행 명령

```powershell
@'
import sys
sys.path.insert(0, 'src')
from graphori_core import *
t=Task('task-real','x')
p=StateReducer(t)
p.apply(canonical_event('run_created',run_id='r',task_id='task-other',graph_version=1))
print('B_ACCEPTED mismatched_first_entity_task_id task=', t.task_id, 'bound_run=', t.run_id)
'@ | python -
```

### 결과

`B_ACCEPTED mismatched_first_entity_task_id task= task-real bound_run= r`가
출력되었습니다. 사건의 `entity.task_id`와 projection의 Task ID가 다른데도 사건이
적용됐습니다.

### 판정

**P1 OPEN — I02 ID 불변식 위반.** 첫 사건도 `entity.task_id == Task.task_id`를
확인한 다음 Run을 연결해야 합니다. 이 검사를 하지 않으면 다른 작업의 사건이
현재 Task에 들어갈 수 있습니다.

## 이전 P0/P1 재검증

### Finding → 증거 → 실행 명령 → 결과 → 판정

- **verdict 권한/evidence:** `reducer.py:225-245`가 worker/router와 잘못된
  verifier/Human Gate 조합을 거부하고, evidence ID가 비어 있으면 거부합니다.
  `python -m unittest discover -s tests -v`의
  `test_verdict_authority_evidence_and_actor_fail_closed`가 통과했습니다.
  **CLOSED.**
- **node 전이/terminal 역전:** `compiler.py:498-536`의 전이표가 종단 상태를
  되살리는 전이를 막고, reducer도 같은 guard를 사용합니다. 모든 Run terminal 값
  (`succeeded`, `failed`, `cancelled`, `rejected`, `blocked`, `inconclusive`)을 다른
  값으로 바꾸는 직접 공격도 모두 `StateTransitionError`였습니다. **CLOSED.**
- **Fast/risk:** usage 누락·unknown, local/reversible 누락, 외부 효과, hard trigger와
  Critical 강등 금지 테스트가 통과했습니다. **CLOSED.**
- **독립 검증자:** identity/provider/model/checkout/session/worktree를 하나씩
  바꾸는 부분 공유 공격이 모두 거부됐고, Critical verifier/Human Gate pool도
  공유 자원을 거부했습니다. **CLOSED.**
- **revision 1/2/3+ cycle, 방향, 없는 원본, 원자성:** 직접 실행 결과는
  `revision-1 -> original`, `revision-2 -> revision-1`,
  `revision-3 -> revision-2`입니다. 2-node와 3-node cycle 및 최신 원본을 지운
  revision은 `GraphValidationError`로 거부됐고, 실패 전후 Task/controller/Graph가
  같았습니다. **CLOSED.**

## 사건 봉투와 genesis

### Finding → 증거 → 실행 명령 → 결과 → 판정

`validate_event_envelope`(`reducer.py:52-90`)는 `actor.role_id`와
`producer_event_id`를 비어 있지 않은 문자열로 요구하고, `digest`와 `prev_digest`를
정확한 `sha256:` + 64개 hex 문자로 검사합니다. `seq=0`에
`prev_digest=None`을 넣는 genesis 공격도 거부됩니다. 해당 반례들은
`test_canonical_digest_producer_and_actor_identifiers_fail_closed`에서 모두
통과했습니다. **형식 검사는 CLOSED.**

실제 앞 사건과의 hash 연결, monotonic sequence, idempotency는 코드가 계산하지
않습니다. 하지만 `EVENT_PROTOCOL.md` §7의 single-writer 기능이며 I02가 아니라
Stage3 범위이므로 이 검수의 실패로 세지 않습니다. 문서에는 별도의 genesis
sentinel 값이 정의되어 있지 않으므로, `seq=0`의 의미를 임의로 더 확대하지 않고
`prev_digest=None`만 fail-closed인지 확인했습니다.

## rework history

### Finding → 증거 → 실행 명령 → 결과 → 판정

`validate_graph`는 `rework_of`만 따로 DFS하여 길이 1, 2, 3 이상 cycle을 모두
막습니다. `RevisionController.record`는 원본 node가 없거나 최신 revision node가
없을 때 변경 전에 실패합니다. 기존 19개 테스트와 직접 반례가 모두 통과했으며,
source가 새 revision, target이 바로 이전 node인 체인도 확인했습니다. **CLOSED.**

## Run projection의 통과 범위

### Finding → 증거 → 실행 명령 → 결과 → 판정

정상 `run_created → graph_published → run_terminal`은 Run ID와 Task ID가 같고,
graph version regression, 다른 Run ID, terminal status 변경을 거부합니다.
`test_run_graph_and_terminal_projection_is_ordered_and_fail_closed`와
`test_run_projection_rejects_reverse_event_order_and_version_mismatch`가 통과했고,
모든 6개 terminal status의 변경 공격도 거부됐습니다. **부분 CLOSED.**

위 Finding 1~3 때문에 순서·ID·성공 조건 전체는 CLOSED가 아닙니다.

## 추가 누락 반례와 범위

`NodeState.QUEUED`는 canonical enum에 있지만 새 노드에서
`transition_node({}, 'n', NodeState.QUEUED)`가 `pending -> queued`를 거부합니다.
또한 `src`와 `tests`에 WIP capacity/ready queue 구현이나 테스트가 없고, 현재
Critical graph는 fan-in 관계만 만들 뿐 queue readiness를 계산하지 않습니다.
`IMPLEMENTATION_PLAN.md` 단계 2 acceptance와
`GRAPHORI_ARCHITECTURE.md` §3.1의 WIP/fan-in queue 요구에 비추어 **P2 OPEN
(I02 acceptance 미검증)**으로 기록합니다. 이 항목은 Stage3 JSONL writer와
혼동하지 않았습니다.

## Windows 실행 증거

| 명령 | 결과 |
|---|---|
| `python -m unittest discover -s tests -v` | **19 tests, OK** |
| `python -m compileall -q src tests` | **exit 0** |
| `python -m pip install . --no-deps --target %TEMP%\\graphori-install-review` | **wheel build/install 성공** |
| `%TEMP%\\graphori-install-review`를 `PYTHONPATH`로 설정 후 `python -c "import graphori_core"` | **exit 0**, 설치 경로에서 import 확인 |
| `git diff --check` | **exit 0** |

macOS unittest/compileall/package import는 이 Windows host에서 실행하지 않아
**deferred/unknown**입니다. 현재 작업 트리의 기존 파일들은 모두 미추적 상태로
보였고, 이번 검수에서는 구현 파일이나 테스트 파일을 수정하지 않았습니다.

## Residual risk

- Stage3: 실제 SHA-256 계산과 chain 연결, monotonic seq, duplicate/idempotency,
  crash-tail quarantine는 후속 단계입니다.
- macOS: 실행 증거가 없어 deferred/unknown입니다.
- Stage2/I02: Finding 1~3의 P1을 닫고, WIP/fan-in queue acceptance를 구현하거나
  명시적으로 범위를 결정한 뒤 재검수해야 합니다.

핵심 P1이 남아 있으므로 현재는 `APPROVE with residual`로 바꿀 수 없습니다.

VERDICT: REVISE


