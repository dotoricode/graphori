# I02 portable core revision-2 최종 재검수 (Codex)

검수일: 2026-08-09 (Asia/Seoul)  
검수 환경: Windows PowerShell, Python 3.12.1  
macOS: 이 컴퓨터에서 실행할 수 없어 `deferred/unknown`  
최종 판정: **REVISE**

## 한 줄 결론

지난번에 열린 문 대부분은 잘 닫혔다. 하지만 사건 봉투의 `digest`를 `"bad"`나 `null`로 써도 통과하고, `actor.role_id`가 없어도 통과한다. 사건 기록의 진짜 주소와 지문을 확인하지 못하므로 지금은 APPROVE 도장을 찍을 수 없다.

## 검수 범위와 안전 수칙

다음 문서를 읽고 현재 코드와 비교했다.

- `docs/architecture/GRAPHORI_ARCHITECTURE.md`
- `docs/architecture/EVENT_PROTOCOL.md`
- `docs/architecture/PORTABILITY_CONTRACT.md`
- `docs/verification/I02_CORE_REREVIEW_CODEX.md`
- `docs/verification/I02_CORE_REREVIEW_CLAUDE.md`
- `docs/verification/I02_CORE_FIX2_REPORT_LUNA.md`
- `src/graphori_core` 전체
- `tests/test_core.py`

구현 파일, 테스트 파일, `PROCESS.md`는 수정하지 않았다. 이 보고서만 새로 작성했다.

## Finding 판정

### F1. Node 상태 순서와 terminal 보호 — CLOSED

위치: `src/graphori_core/compiler.py:463-501`, `reducer.py:119-129`

정상 순서는 실제로 통과한다.

```text
pending -> ready -> assigned -> running
        -> awaiting_verification -> passed
```

`passed` 뒤에 `pending`, `ready`, `running`, `failed`, `cancelled`로 되돌리는 공격은 모두 `StateTransitionError`가 났다. `failed`, `cancelled`, `rejected`, `inconclusive`도 다시 실행하지 못한다. 이전의 “Node 상태를 Task 상태처럼 처리하던 문제”는 닫혔다.

### F2. 증거 없는 verdict와 platform pass — CLOSED

위치: `src/graphori_core/reducer.py:130-173`

- verifier의 `pass`에 `evidence_ids`가 없거나 빈 목록이면 거부한다.
- `platform=windows, status=pass`에 evidence가 없으면 거부한다.
- platform pass에는 `fixture_id` 또는 `snapshot_id`도 필요하다.
- worker/router/human_gate/verifier의 잘못된 verdict 조합도 거부한다.

최소 재현 결과:

```text
verdict_recorded(pass, evidence_ids 없음) -> REJECT
platform pass, evidence_id 없음          -> REJECT
platform pass, fixture_id만 있음         -> REJECT
platform pass + fixture_id + evidence_id  -> ACCEPT
```

`payload.actor_role`를 몰래 바꿔도 실제 `event.actor.role` 권한을 우회하지 못한다.

### F3. 독립성(identity/provider/model/checkout/session/worktree) — CLOSED

위치: `src/graphori_core/compiler.py:227-250, 253-257, 356-375`

다음 공유 공격은 거부됐다.

- 같은 `identity`
- 같은 비어 있지 않은 `checkout`
- 같은 `session`
- 같은 `worktree`
- Standard에서 `provider + model + checkout`이 모두 같은 경우
- Critical에서 `provider + model`이 같은 verifier끼리의 조합
- Human Gate 후보와 worker/verifier/router의 공유 자원

`provider` 하나만 같거나 `model` 하나만 같은 경우는 다른 실행 차원이 다르면 허용됐다. 이것은 문서의 “worker와 verifier는 attempt/provider/model/checkout 중 최소 한 차원이 달라야 한다”는 규칙에 맞으며 우회가 아니다. 실제로 정상적인 자원값을 가진 사용자 지정 Fast/Standard/Critical topology는 모두 생성됐다.

자원값을 전부 비워 둔 role은 독립성을 증명할 수 없어 거부된다. 이는 안전한 fail-closed 동작이며, 기본 topology에는 영향을 주지 않는다.

### F4. revision 이력과 4회째 gate — CLOSED

위치: `src/graphori_core/compiler.py:411-448`

3회 revise의 실제 edge는 다음과 같았다.

```text
task:revision-1 -> task
task:revision-2 -> task:revision-1
task:revision-3 -> task:revision-2
```

자기 자신을 가리키는 `rework_of` self-loop는 없었고 `validate_graph`도 통과했다. 4회째 revise는 새 작업을 만들지 않고 `human_gate_required`로 escalation됐다.

### F5. Fast 조건과 세 가지 topology — CLOSED

위치: `src/graphori_core/compiler.py:27-159`

Fast는 다음을 모두 명시해야 한다.

```text
usage_status=known
local_only=True
reversible=True
external_effect=False
uncertainty=0, low risk
```

하나라도 `False`, `None`, `unknown`, `estimate`이면 Standard 이상으로 간다. Critical 위험에 Fast를 억지로 지정해도 Critical로 유지된다. 기본 Fast/Standard/Critical graph와 사용자 지정 role을 넣은 세 graph 모두 정상 생성됐다.

### F6. canonical event 종류와 VERIFIES 경로 — CLOSED

위치: `src/graphori_core/reducer.py:16-23`, `compiler.py:298-352`

`EVENT_PROTOCOL.md`의 필수 event 23개와 `EVENT_TYPES` 23개를 집합으로 비교했을 때 빠진 것과 더 들어간 것이 모두 0개였다. `task_status_changed` 같은 문서 밖 event는 거부된다.

Fast/Standard verifier는 worker를 `requires`로 기다리면서 별도의 `verifies` edge로 검증한다. Critical은 normal/adversarial verifier가 worker를 검증하고 fan-in verifier가 두 verifier를 검증한다. 검증 경로가 없는 verifier graph는 `GraphValidationError`가 난다.

### F7. fan-in role 타입과 platform fixture/snapshot 보존 — CLOSED

위치: `src/graphori_core/compiler.py:335-339`, `models.py:193-200`, `reducer.py:151-198`

Critical의 `verifier_fanin.role`은 문자열이 아닌 `None`이고, `metadata["fan_in"]`만 `True`다. 같은 Windows에서 fixture 2개와 snapshot 1개를 기록했을 때 세 결과와 evidence가 모두 남았고, 마지막 값이 앞의 값을 덮지 않았다.

## OPEN finding

### O1. digest/prev_digest 형식 검사가 너무 약함 — OPEN (P1)

위치: `src/graphori_core/reducer.py:44-75`, 특히 68-70줄

`EVENT_PROTOCOL.md:62-63`은 `sha256:<hex>` 지문을 요구한다. 하지만 현재 validator는 값이 `null`이면 그냥 지나가고, 문자열이어도 비어 있지 않기만 하면 통과시킨다.

최소 재현:

```python
event = canonical_event("heartbeat")
event["digest"] = None       # ACCEPT
event["digest"] = "bad"     # ACCEPT
event["prev_digest"] = "bad" # ACCEPT
```

지문은 사건이 바뀌지 않았다는 확인표다. 아무 글자나 통과하면 사건 내용을 바꾼 뒤에도 정상 기록처럼 보일 수 있다. `sha256:` 접두사, 정확한 hex 길이, 첫 사건의 prev 규칙을 fail-closed로 확인해야 한다.

`seq`의 누락, 문자열 타입, 음수는 현재 거부된다. 다만 seq의 monotonic 순서와 실제 hash chain은 Stage 3 writer 기능이므로 이번 코드에는 아직 없다. 이는 O1과 구분한 후속 residual risk다.

### O2. actor.role_id를 확인하지 않음 — OPEN (P2, envelope 계약)

위치: `src/graphori_core/reducer.py:60-61`

문서 예시는 `actor: {"role": "verifier", "role_id": "role_<id>"}`다. 현재는 `{"role": "verifier"}`만 있어도 통과한다. 역할 이름만 적힌 사건은 실제 누가 썼는지 추적할 수 없으므로 `role_id`를 필수 non-empty 값으로 확인해야 한다.

### O3. Run/GraphVersion가 구조체에만 있고 reducer와 연결되지 않음 — OPEN (P2, I02 범위 확인 필요)

위치: `src/graphori_core/models.py:275-295`, `reducer.py:103-174`

`GraphVersion`과 `Run` dataclass는 존재한다. 하지만 `StateReducer`는 `Task`만 보관하며 `run_created`, `graph_published`, `run_terminal` event를 받아도 Run 상태나 graph version을 바꾸지 않는다. 따라서 “Run이 있다”는 모델 수준은 CLOSED지만, Run terminal projection 거버넌스는 아직 없다.

이것은 Stage 3 journal, Stage 5 adapter, Stage 6 dashboard의 미구현을 새 finding으로 잡은 것이 아니다. 다만 I02 acceptance가 Run/graph/reducer를 명시하므로 I02 안의 P2 잔여로 기록한다. 범위를 뒤 단계로 옮기기로 결정하면 residual로 바꿀 수 있지만, 현재 문서 계약만으로는 완전 CLOSED라고 쓰기 어렵다.

## canonical field 줄 단위 비교

`EVENT_PROTOCOL.md:48-63`의 envelope 이름과 구현의 `_REQUIRED_ENVELOPE`(`reducer.py:25-29`)는 다음 핵심 이름이 일치한다.

```text
schema_version, event_id, producer_event_id, run_id, graph_version,
seq, occurred_at, recorded_at, actor, type, entity, payload,
prev_digest, digest
```

`usage`와 `platform`도 `canonical_event()`가 만들고 validator가 object/string인지 확인한다. 다만 O1처럼 digest의 내용 형식은 확인하지 않고, O2처럼 actor 내부의 `role_id`는 확인하지 않는다. 따라서 “필드 이름이 있다”와 “필드가 계약대로 안전하다”는 같은 말이 아니다.

## Windows 실행 증거

모두 저장소 밖의 임시 설치 대상 또는 읽기 전용 명령으로 실행했다.

```text
python --version
Python 3.12.1

python -m unittest discover -s tests -v
Ran 15 tests ... OK

python -m compileall -q src tests
exit code 0

git diff --check
exit code 0

python -m pip install . --no-deps --target <Windows Temp>
Successfully installed graphori-core-0.1.0
python -c "import graphori_core"
graphori_core
```

AST로 `src/graphori_core` import도 확인했다. 사용한 것은 Python 표준 모듈(`dataclasses`, `enum`, `typing`, `__future__`)과 서로의 내부 모듈뿐이다. `orca`, 외부 SDK, `subprocess`, OS 전용 API import는 0개였다.

`git status --short`에는 원래부터 저장소 파일들이 untracked로 보였고, 이번 검수에서 구현/테스트/PROCESS 수정은 없었다. compileall로 생긴 cache는 `.gitignore`에 걸린다.

## macOS

macOS host 또는 CI에서 실행하지 않았다. macOS 결과는 전부 `deferred/unknown`이며 Windows PASS를 macOS PASS로 넓혀 쓰지 않는다.

## 남은 위험

- O1 digest/prev_digest 형식 및 hash-chain 검증
- O2 actor.role_id와 event별 entity/payload 의미 검증
- O3 Run/GraphVersion event projection의 I02 범위 결정
- Stage 3 single-writer, monotonic seq, idempotency, crash-tail은 아직 미구현
- platform `complete_scope`는 한 fixture라도 pass하면 platform 이름을 scope에 넣으므로, 필요한 모든 fixture가 통과했는지 확인하는 정책은 후속으로 명확히 해야 한다.
- 실제 Windows process/path/symlink adapter와 macOS generic adapter는 아직 구현·검증 범위가 아니다.

## 최종 판정

**REVISE**

이전 OPEN이었던 Node terminal 역전, 증거 없는 verdict/platform pass, revision self-loop, Fast unsafe metadata, fan-in role 오염, event 종류 불일치, VERIFIES 누락, platform fixture 덮어쓰기는 모두 CLOSED다. 그러나 사건 지문을 아무 문자열이나 허용하는 O1은 I02의 canonical envelope 안전성에 직접 걸리고, O2/O3도 남아 있으므로 현재 revision-2는 APPROVE할 수 없다.
