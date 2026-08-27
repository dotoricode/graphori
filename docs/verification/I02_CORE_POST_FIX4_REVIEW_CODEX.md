# I02 portable core revision-4 최종 검수 보고서 (Codex)

검수일: 2026-08-09
환경: Windows, Python 3.12.1

## 한눈에 보는 결과

revision-4의 새 lifecycle 방어는 잘 작동했습니다. 시작표(`run_created`) 없이
그래프를 공개하거나 실행을 끝내는 길, 첫 사건의 ID가 서로 다른 길, 중복·역순
사건은 모두 막혔습니다.

하지만 아직 P1 문제가 하나 남았습니다. 끝나지 않은 노드가 있는데도
`run_terminal(succeeded)`가 성공합니다. 이 문제는 I02의 Run 성공 조건에 관한
것이며, Stage3 writer 문제가 아니므로 지금은 **REVISE**입니다.

## Finding 1 — P1: 끝나지 않은 노드가 있어도 성공 처리됨

### 증거

`EVENT_PROTOCOL.md` §6은 Run이 성공하려면 필요한 모든 노드가 끝나고 gate 조건도
맞아야 한다고 말합니다. 그런데 현재 `StateReducer`의 `run_terminal`은
`run_created`와 `graph_published`가 있었는지, 그리고 terminal 이름이 맞는지만
확인합니다. 그래프 안에 아직 `pending`인 worker가 있는지는 확인하지 않습니다.

### 실행 명령

```powershell
@'
import sys
sys.path.insert(0, 'src')
from graphori_core import *
from graphori_core.reducer import canonical_event, StateReducer

t = Task('t-pending', 'x', run_id='r-pending', graph_version=1)
r = Run('r-pending', 1)
r.graph.add_node(Node('n', NodeKind.WORKER, 'pending'))
p = StateReducer(t, r)
p.apply(canonical_event('run_created', run_id='r-pending', task_id='t-pending',
                        graph_version=1, actor_role='router', seq=1))
p.apply(canonical_event('graph_published', run_id='r-pending', task_id='t-pending',
                        graph_version=1, actor_role='router', seq=2))
p.apply(canonical_event('run_terminal', run_id='r-pending', task_id='t-pending',
                        graph_version=1, actor_role='router', seq=3,
                        payload={'terminal_status': 'succeeded'}))
print('terminal_status=', r.terminal_status.value)
'@ | python -
```

### 결과

```text
terminal_status= succeeded
```

`pending` 노드가 그대로인데도 성공이 기록되었습니다. 기대 결과는
`StateTransitionError`로 거부하는 것입니다.

### 판정

**OPEN P1 — I02 범위의 수정 필요.** 성공 terminal을 기록하기 전 필요한 노드와
gate가 모두 terminal인지 확인해야 합니다. 현재 revision-4 보고서의 범위가
lifecycle 순서·ID·version guard뿐이라 이 결함은 아직 닫히지 않았습니다.

## revision-4 공통 lifecycle 반례

별도 파일을 만들지 않고 inline Python으로 직접 실행했습니다. 예외가 나와야 하는
경우는 모두 `StateTransitionError`가 나왔고, 정상 순서는 통과했습니다.

| 확인한 경우 | 결과 |
|---|---|
| 미리 넣은 `Run`이 있어도 `run_created` 전 `graph_published` 차단 | 차단 |
| 미리 넣은 `Run`이 있어도 `run_created` 전 `run_terminal` 차단 | 차단 |
| `Task.run_id`만 미리 있어도 두 사건 모두 차단 | 차단 |
| 첫 `run_created`의 `entity.task_id` 불일치 | 차단 |
| 첫 사건의 entity/envelope `run_id` 불일치 | 차단 |
| 첫 사건의 entity/envelope `graph_version` 불일치 | 차단 |
| 첫 사건의 Task/Run graph version 불일치 | 차단 |
| Task와 Run의 생성자 `run_id` 불일치 | 차단 |
| `run_created → graph_published → run_terminal` 정상 순서 | 통과 |
| `run_created` 중복·재개(reopen) | 차단 |
| `graph_published` 중복·terminal 뒤 역전 | 차단 |
| graph version regression | 차단 |
| terminal 선행·중복·상태 변경·다른 Run ID | 차단 |

이 lifecycle 묶음의 출력은 다음과 같습니다.

```text
PASS 3 BLOCKED 65 ALL_ADDITIONAL_COUNTEREXAMPLES_OK
```

## 이전 P0/P1 회귀 재확인

21개 테스트만 믿지 않고, 과거 보고서의 주요 실패 입력을 다시 만들어 실행했습니다.

| 과거 항목 | 직접 결과 |
|---|---|
| terminal node에서 `ready/running/assigned/pending`로 부활 | 16가지 전부 차단 |
| 증거 없는 verdict pass | 7가지 전부 차단 |
| worker/router/observer 권한 위조, 잘못된 verifier·gate verdict | 전부 차단 |
| identity/provider/model/checkout/session/worktree 부분 공유 | 전부 차단 |
| Critical verifier provider+model 공유 | 차단 |
| Human Gate pool 크기 1 또는 checkout 공유 | 차단 |
| `rework_of` self-loop와 2/3/4-node cycle | 전부 차단 |
| revision 원본 누락 시 변경 | 차단되고 상태도 그대로 |
| digest/prev_digest 잘못된 형식과 producer ID/role ID 누락 | 전부 차단 |
| platform pass 증거·fixture·snapshot 누락 | 차단 |
| unknown event와 Task/Attempt terminal 부활 | 전부 차단 |
| revision 1→2→3 방향과 4번째 Human Gate escalation | 정상 확인 |

추가 회귀 명령의 결과는 다음과 같습니다.

```text
PASS prior-direct-regressions blocked= 13
```

## Windows 실행 증거

```text
python --version
Python 3.12.1

python -m unittest discover -s tests -v
Ran 21 tests ... OK

python -m compileall -q src tests
exit 0

git diff --check
exit 0

python -m pip install . --no-deps --target <temporary-directory>
성공

설치 target을 PYTHONPATH로 둔 python -c "import graphori_core"
성공 — 임시 설치 경로의 graphori_core import 확인
```

core의 AST import도 확인했습니다. `models.py`, `compiler.py`, `reducer.py`,
`__init__.py` 모두 외부 패키지 import가 없었습니다. 따라서 stdlib-only 경계는
지켜졌습니다.

macOS는 이 Windows 환경에서 실행할 수 없어 `deferred/unknown`입니다.

## 범위 구분과 잔여 위험

I02에 남은 P1은 pending/gate 상태를 확인하지 않는 Run 성공 projection입니다.
`PROCESS`, `dashboard`, `adapter`와 `docs/PROCESS_VIEW.html`은 이번 검수 대상에서
건드리지 않았습니다.

Stage3 범위인 실제 JSONL single-writer, SHA-256 chain 계산, monotonic sequence,
중복 dedup, crash-tail quarantine은 아직 구현·검증하지 않았습니다. 이것들은
이번 REVISE의 직접 원인이 아니라 후속 단계의 residual입니다.

이번 검수에서는 `src`, `tests`, `PROCESS` 구현을 수정하지 않고 이 보고서만
작성했습니다.

VERDICT: REVISE
