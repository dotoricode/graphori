최종 판정: REVISE

# I02 휴대형 핵심 엔진 재검수 보고서 (Codex)

검수일: 2026-08-09 (Asia/Seoul)  
검수 환경: Windows PowerShell, Python 3.12.1  
macOS: 실행할 수 없으므로 모든 결과를 `deferred/unknown`으로 남긴다.  
범위: 요청받은 architecture 문서 3개, `docs/IMPLEMENTATION_PLAN.md`, 최초 Codex/Claude 보고서, Luna 수정 보고서, `src/graphori_core` 전체, `tests/test_core.py`, `pyproject.toml`, `.gitignore`.

## 한눈에 보는 결론

Luna가 고친 중요한 문제들은 대부분 실제 코드와 회귀 테스트에서 닫혔다. 특히 usage가 없을 때 Fast로 보내지 않기, Critical을 Standard로 낮추지 않기, worker가 verdict를 쓰지 못하게 하기, node와 task 상태를 나누기, 4번째 revise에서 Human Gate로 보내기는 확인했다.

하지만 정상 계약을 지키지 못하는 문제가 남아 있다. 독립성을 “네 가지 값이 모두 같을 때만” 검사해서 identity 하나만 겹쳐도 통과하고, revision의 `rework_of`가 이전 node가 아니라 자기 자신을 가리키며, Fast의 local/reversible 조건과 event envelope를 표현·검사하지 않는다. 따라서 현재는 APPROVE할 수 없다.

## Finding별 판정

`CLOSED`는 코드와 테스트로 닫혔다는 뜻이다. `OPEN`은 아래의 재현 방법으로 아직 문제가 보인다는 뜻이다.

| 최초 finding | 판정 | 이번에 확인한 내용 |
|---|---|---|
| Claude P0-1: worker/router가 verdict 작성 가능 | CLOSED | `reducer.py:66-82`가 envelope의 `actor.role`을 읽고 `verifier`/`human_gate`만 허용한다. worker의 `pass`, router의 `approve`, verifier의 `approve`를 모두 거부하는 회귀 테스트가 있다. |
| Claude P0-2: node status를 TaskState로 처리 | CLOSED | `reducer.py:52-65`가 `NodeState`로만 변환하고 `node_statuses`에 저장한다. `tests/test_core.py:143-155`가 14개 canonical node status와 잘못된 status를 검사한다. |
| Claude P0-3 / Codex P1-03: worker와 verifier 독립성 | OPEN (P1) | 같은 네 값이 모두 같을 때는 거부하지만, identity만 같고 provider/model/checkout이 다르면 허용한다. 계약은 identity와 checkout을 다른 독립 역할 사이에서 공유하지 않도록 한다. |
| Claude P1-1 / Codex P1-01: 빠진 usage를 known으로 처리 | CLOSED | `RiskInput` 기본값과 Task metadata 누락 기본값이 모두 `unknown`이다(`compiler.py:28-52, 64-79`). |
| Claude P1-2 / Codex P1-01: unknown usage를 무조건 Critical | CLOSED | unknown만 있으면 Standard이고, 외부 효과·critical tag 같은 hard trigger가 있을 때만 Critical이다(`compiler.py:100-132`). |
| Codex P1-02: 명시적 Standard가 Critical을 낮춤 | CLOSED | `compiler.py:217-221`이 결과가 Critical이면 선택 mode를 강제로 Critical로 올린다. Critical graph에 두 verifier와 Human Gate가 남는다. |
| Claude P1-3: ESCALATED가 막힘 | CLOSED | `compiler.py:368-377`에서 ESCALATED 후 `READY` 또는 `BLOCKED`를 표현할 수 있다. |
| Claude P1-4: Human Gate authority 독립성 검사 없음 | OPEN (P1) | 최소 2명과 네 값 전체가 다름은 검사하지만 identity 하나만 겹치는 경우는 허용한다(`compiler.py:286-297`). 또한 Router에 Role/identity가 배정되지 않아 Router와의 충돌을 compile-time에 검사할 수 없다. |
| Claude P1-5: Run 엔티티 없음 | CLOSED (범위 제한) | `models.py:269-289`에 `GraphVersion`과 `Run`이 있고 Task에도 `run_id`, `graph_version`이 있다. 단, 값의 유효성 검사는 별도 OPEN finding인 envelope/graph 계약 문제에 포함한다. |
| Claude P1-6 / Codex P1-05: unknown event를 조용히 무시 | CLOSED (unknown type) | 빈 type과 알 수 없는 type은 `reducer.py:35-42`에서 명시적으로 거부한다. payload가 object가 아니거나 status/verdict가 틀려도 거부한다. |
| Claude P1-7: 테스트가 happy path 위주 | OPEN (P1) | 12개로 늘었고 이전 P0 대부분을 잡지만, identity 부분 충돌, revision 자기 연결, Fast local/reversible 누락, envelope 누락, node illegal transition을 잡는 회귀 테스트는 없다. |
| Claude P1-8 / Codex P2-03: `.gitignore` 없음 | CLOSED | `.gitignore:1-5`가 `__pycache__`, `*.pyc`, build 산출물을 무시하며 `git check-ignore`로 확인했다. |
| Claude P2-1: enum 대소문자 alias 중복 | CLOSED | `models.py:18-32`의 TaskMode/Risk는 canonical 소문자 값만 가진다. |
| Claude P2-2 / Codex P1-06 일부: verification metadata 누락 | CLOSED (metadata만) | Fast=`automatic`, Standard=`targeted`, Critical=`fresh_full`/`adversarial`가 node metadata에 기록된다(`compiler.py:228-264`). |
| Claude P2-3: DISPATCHED에서 cancel 불가 | CLOSED | `compiler.py:391-399`에서 DISPATCHED→CANCELLED를 허용한다. |
| Codex P1-04: revision node/history 없음 | OPEN (P1) | 새 node와 4번째 Human Gate는 생겼지만 첫 3개의 `rework_of`가 각각 자기 자신을 가리킨다. 이전 node history 계약을 충족하지 않는다. |
| Codex P2-01: Critical fan-in metadata 중첩 | CLOSED | `verifier_fanin.metadata["fan_in"]`가 실제로 `True`이며 테스트도 확인한다. |
| Codex P2-02: 음성 계약 테스트 부족 | OPEN (P1) | 12개로 개선됐지만 아래 OPEN 결함들의 반례를 아직 테스트하지 못한다. |

## 이번 재검수에서 발견한 OPEN 결함

### R1. 독립성 검사가 identity/checkout 공유를 놓침 — P1

위치: `src/graphori_core/compiler.py:193-201, 286-305`.

`_independence_key` 전체 tuple이 완전히 같을 때만 충돌로 본다. 따라서 worker가 identity `worker`를 쓰고 verifier가 identity `worker`, provider `other-provider`를 써도 Standard compile이 성공한다. Critical에서도 worker와 normal verifier가 같은 identity이거나 두 verifier가 같은 identity여도 나머지 값이 다르면 성공한다. Human Gate pool도 같은 약점을 가진다.

재현 명령:

```text
@'
import sys
sys.path.insert(0, 'src')
from graphori_core import *
v = Role('v', NodeKind.VERIFIER, 'worker', 'other-provider', 'm', 'c')
print(compile_topology(Task('t', 'x', metadata={'usage_status':'known'}),
                       mode=TaskMode.STANDARD, verifier_roles=(v,)).graph.nodes.keys())
'@ | python -
```

관찰 결과: 예외 없이 `router`, `worker`, `verifier`, `observer` graph가 만들어졌다. 계약상 identity 또는 checkout을 공유하는 독립 verifier/authority는 `IndependenceError`로 거부되어야 한다.

### R2. `rework_of`가 자기 자신을 가리킴 — P1

위치: `src/graphori_core/compiler.py:350-365`.

`record()`가 revise 횟수를 먼저 증가시킨 뒤 새 node와 같은 `task:revision-N`을 `old_node`로 계산한다. 그래서 실제 edge는 다음처럼 된다.

```text
task:revision-1 -> task:revision-1 (rework_of)
task:revision-2 -> task:revision-2 (rework_of)
task:revision-3 -> task:revision-3 (rework_of)
```

현재 테스트는 edge 개수만 세므로 이 결함을 통과시킨다. `rework_of`가 readiness cycle에서 제외되는 것은 맞지만, “새 node가 옛 node를 가리킨다”는 history는 보존되지 않는다. 4번째 revise가 `human_gate_required`가 되는 것 자체는 확인했다.

### R3. Fast의 local/reversible 조건을 입력으로 표현하지 않음 — P1

위치: `src/graphori_core/compiler.py:28-52, 64-88, 114-132`.

`RiskInput`에 `local` 또는 `reversible` 필드가 없고, mapping/Task metadata에서 이 값을 읽지도 않는다. 따라서 명시적으로 `local=False, reversible=False`를 넣어도 무시하고, `usage_status=known`·낮은 위험·불확실성 0이면 Fast를 반환한다. 사용자가 요구한 “known + low + local + reversible + 불확실성 없음일 때만 Fast”를 현재 API가 보장할 수 없다.

재현:

```text
@'
import sys
sys.path.insert(0, 'src')
from graphori_core import compile_risk
print(compile_risk({'usage_status':'known', 'local':False, 'reversible':False}).mode)
'@ | python -
```

관찰 결과: `fast`.

### R4. canonical event envelope를 검사하거나 모델링하지 않음 — P1

위치: `src/graphori_core/reducer.py:35-42`; 관련 모델 `src/graphori_core/models.py:156-298`.

reducer는 type과 payload 모양만 확인하고 `schema_version`, `event_id`, `producer_event_id`, `run_id`, `graph_version`, `occurred_at`, `actor`, `entity` 같은 EVENT_PROTOCOL 필수 envelope를 확인하지 않는다. 예를 들어 `{'type':'heartbeat'}`가 그대로 허용된다. Run/GraphVersion dataclass가 추가된 것은 좋지만, canonical event를 담는 타입이나 필수 필드 검증은 아직 없다.

재현:

```text
@'
import sys
sys.path.insert(0, 'src')
from graphori_core import StateReducer, Task
print(StateReducer(Task('t','x')).apply({'type':'heartbeat'}))
'@ | python -
```

관찰 결과: 예외 없이 reducer가 반환된다. 잘못된 event envelope는 projection에 들어가기 전에 명시적으로 거부되어야 한다.

### R5. node transition 자체를 검사하지 않음 — P2

위치: `src/graphori_core/reducer.py:52-65`.

NodeState enum 값은 확인하지만 현재 상태에서 다음 상태로 갈 수 있는지는 확인하지 않는다. 새 node에 곧바로 `passed`를 넣은 뒤 같은 node를 `running`으로 바꾸는 것도 성공한다. EVENT_PROTOCOL의 `pending → ready → ... → passed` 순서를 보장하지 못한다. task transition은 `compiler.py:368-388`에서 검사하지만 node transition은 별도 표가 없다.

### R6. platform verdict가 fixture별로 보존되지 않음 — P2

위치: `src/graphori_core/models.py:189-194`, `src/graphori_core/reducer.py:28-31, 87-100`.

PORTABILITY_CONTRACT는 `{platform, fixture, verdict, evidence_id, ...}`를 fixture별로 기록하라고 한다. 현재 `PlatformVerdict`에는 fixture가 없고 reducer dict key도 platform 하나뿐이다. 같은 Windows에서 fixture A의 pass를 기록한 뒤 fixture B의 fail을 기록하면 A의 evidence가 덮어진다. 이번 보고서에서 실행한 결과도 마지막 값만 `windows: fail`로 남았다.

## 목표별 확인표

| 목표 | 판정 | 근거 |
|---|---|---|
| Fast/Standard/Critical routing | REVISE | Critical 강등 금지, missing/unknown usage의 Standard, unknown 단독 Critical 금지는 닫혔다. 다만 R3 때문에 local/reversible을 모르는 입력이 Fast가 될 수 있다. |
| Standard/Critical 독립성 | REVISE | 같은 전체 context 충돌은 막지만 R1의 identity/checkout 부분 충돌을 막지 못한다. Critical 두 verifier와 Human Gate도 같은 문제다. |
| reducer 권한/오류 거부 | 부분 PASS | envelope actor.role 권한, unknown event, 잘못된 payload/status는 닫혔다. R4처럼 envelope 필수 필드와 일부 지원 event의 내용은 검사하지 않는다. |
| node_status/task_status 분리 | PASS (enum 수준) | `NodeState`와 `TaskState`가 분리되고 각 enum을 사용한다. R5 때문에 순서까지 포함한 완전한 전이는 아직 아니다. |
| revision 1~3 및 4번째 Gate | REVISE | node 생성과 4번째 escalation은 있으나 R2의 history 방향이 잘못됐다. |
| Run/graph_version, transition, platform, verification metadata | REVISE | Run/GraphVersion, task transition, platform pass evidence, mode별 verification metadata는 있다. event envelope와 fixture별 platform verdict, node transition이 부족하다. |
| stdlib-only/외부 의존성 | PASS (core 범위) | source import는 `__future__`, `dataclasses`, `enum`, `typing` 및 sibling module뿐이다. Orca/SDK/OS 전용 process API는 없다. |
| Windows 전체 테스트/compileall | PASS | 아래 명령 결과 참조. |
| macOS | deferred/unknown | 이 Windows 환경에서는 실행하지 않았다. |
| 취약점 회귀 테스트 품질 | REVISE | 12개로 개선됐지만 R1~R6 중 R1~R5의 주요 반례가 회귀 테스트로 고정되지 않았다. |

## 실제 실행 명령과 결과

```text
python --version
Python 3.12.1

python -m unittest discover -s tests -v
Ran 12 tests in 0.003s
OK

python -m compileall -q src tests
exit code: 0

git check-ignore -v src/graphori_core/__pycache__/models.cpython-312.pyc tests/__pycache__/test_core.cpython-312.pyc
.gitignore:1:__pycache__/  src/graphori_core/__pycache__/models.cpython-312.pyc
.gitignore:1:__pycache__/  tests/__pycache__/test_core.cpython-312.pyc
```

추가 one-liner에서 확인한 결과는 다음과 같다.

- `compile_risk(RiskInput())` → `standard`; `compile_risk(RiskInput(usage_status='known'))` → `fast`.
- `compile_risk(RiskInput(usage_status='unknown', external_effect=True))` → `critical`.
- Fast unsafe mapping(`local=False, reversible=False`) → `fast` (R3 재현).
- Standard identity 충돌, Critical worker/verifier identity 충돌, Critical verifier 간 identity 충돌, Human Gate/worker identity 충돌이 모두 예외 없이 compile됨(R1 재현).
- 세 revise 뒤 edge가 모두 자기 자신을 가리키고, 네 번째 결과는 `human_gate_required`임(R2 재현).
- worker verdict와 unknown event는 거부되고, `{'type':'heartbeat'}`는 허용됨(R4 재현).
- `passed → running` node status가 허용됨(R5 재현).
- 같은 platform의 두 fixture 입력은 마지막 verdict만 남김(R6 재현).

stdlib import 확인은 `src/graphori_core`에 대해 AST로 확인했고 결과는 Python 표준 모듈과 sibling module뿐이었다. `pyproject.toml:5-12`에는 runtime dependency가 없으며 `requires-python >=3.11`과 src layout이 있다. 다만 이 저장소에는 아직 generic process adapter가 없으므로 “Windows process tree/path fixture까지 통과”라고 확대해서 말하지 않는다.

## 남은 위험과 다음 검수 조건

1. 독립성 비교를 identity, checkout 및 계약상 필요한 각 차원에 맞게 명확히 하고 worker/verifier, verifier/verifier, Human Gate/worker/verifier/router를 compile-time에서 거부해야 한다.
2. revision 첫 생성 시 원래 node를 `rework_of`의 target으로 삼고, 다음 revision은 바로 이전 revision을 target으로 삼아야 한다. edge endpoint를 검사하는 회귀 테스트가 필요하다.
3. Fast 입력에 local/reversible 사실을 넣고 둘 중 하나라도 false/unknown이면 Fast를 금지해야 한다.
4. canonical event envelope 모델과 필수 필드 검증을 넣고, 지원한다고 선언한 event마다 payload 의미를 검증해야 한다.
5. node transition 표와 fixture별 platform verdict/evidence 저장을 추가하고 음성 테스트를 고정해야 한다.
6. Windows 결과만 PASS다. macOS는 실제 host 또는 CI에서 같은 fixture를 돌리기 전까지 `deferred/unknown`이다.

구현 파일, 테스트 파일, PROCESS.md 및 다른 문서는 수정하지 않았다. 이 보고서만 작성했다.
