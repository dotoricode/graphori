# Graphori event protocol

> 상태: canonical, schema version 1; PR3 journal/replay execution semantics implemented

## 1. 12살도 이해하는 설명

Graphori는 “누가 무엇을 언제 했는지”를 한 줄짜리 영수증으로 남긴다. 영수증이
모이면 현재 카드 상태를 다시 계산할 수 있다. 일꾼들이 같은 공책에 동시에 쓰면
글자가 겹칠 수 있으므로 각자 작은 봉투(tmp)를 만들고, 한 명의 기록 담당자만
봉투를 열어 순서 번호를 붙인다.

“살아 있음”, “실제로 조금 진행함”, “검사를 통과함”은 서로 다른 영수증이다.
그래서 연결만 된 캐릭터가 일을 끝낸 것처럼 보이지 않는다. 토큰 수를 보고받지
못했다면 0이 아니라 모름으로 남긴다.

## 2. Canonical enum

모든 저장값은 소문자 snake_case다. UI의 `PASS`, `REVISE`, `APPROVE`는 표시용이다.

```text
node_kind       = router | worker | verifier | observer | human_gate | platform_gate
edge_kind       = requires | requires_gate | verifies | observes | rework_of
mode            = fast | standard | critical
risk_level      = 0 | 1 | 2 | 3
verification    = none | automatic | targeted | fresh_full | adversarial
node_status     = pending | ready | assigned | running | awaiting_verification |
                  queued | stale | outcome_unknown | passed | failed | cancelled |
                  blocked | rejected | inconclusive
attempt_status  = planned | dispatched | running | succeeded | failed | cancelled |
                  timed_out | lost | outcome_unknown
verdict         = pending | pass | revise | approve | reject | inconclusive
liveness        = connected | heartbeat_recent | stale | dead | unknown
progress        = none | reported | advanced | blocked | unknown
usage_status    = known | estimate | unknown
platform_status = pass | fail | not_verified | blocked | deferred
terminal_status = succeeded | failed | cancelled | rejected | blocked | inconclusive
```

`pass`는 Verifier의 검사 결과, `approve`는 Human Gate의 결정이다. Worker는 verdict를
발행하지 않는다. `rework_of`는 실행 edge가 아니라 history relation이다.

## 3. Event envelope

각 줄은 하나의 완전한 UTF-8 JSON object다.

```json
{
  "schema_version": 1,
  "event_id": "evt_<uuid>",
  "producer_event_id": "producer:<id>:<local-seq>",
  "run_id": "run_<id>",
  "graph_version": 4,
  "seq": 91,
  "occurred_at": "2026-08-09T00:00:00Z",
  "recorded_at": "2026-08-09T00:00:01Z",
  "actor": {"role": "verifier", "role_id": "role_<id>"},
  "type": "verdict_recorded",
  "entity": {"node_id": "node_<id>", "task_id": "task_<id>", "attempt_id": "attempt_<id>"},
  "payload": {"verdict": "pass", "evidence_ids": ["ev_<id>"]},
  "usage": {"status": "unknown"},
  "platform": "windows",
  "prev_digest": "sha256:<hex>",
  "digest": "sha256:<hex>"
}
```

`seq`, `recorded_at`, `prev_digest`, `digest`는 writer가 채운다. Producer가 제출하는
값은 `schema_version`, IDs, actor, type, entity, payload, optional usage/platform다.
실제 사용량은 provider가 보고한 경우에만 `known`; 호출 전 예측은 `estimate`가
아니라 별도 `predicted_usage`로 기록한다.

## 4. Node/edge/attempt 전이

### 4.1 Node

```text
pending -> ready                  (모든 requires가 충족)
ready -> assigned                 (role assignment 기록)
assigned -> running               (attempt dispatched + heartbeat/started)
running -> awaiting_verification  (worker_finished)
running -> failed|cancelled|stale|outcome_unknown
awaiting_verification -> passed   (verifier pass 또는 automatic check)
awaiting_verification -> failed   (검사 실패)
awaiting_verification -> inconclusive (evidence 부족/플랫폼 미검증)
failed -> ready                   (새 revision만; 같은 node 재실행 금지)
stale -> outcome_unknown          (reconcile 전)
outcome_unknown -> ready          (새 attempt가 명시적으로 생성될 때만)
모든 비정상 상태 -> blocked       (gate 또는 resource 이유 기록)
```

### 4.2 Edge

`requires`와 `requires_gate`만 scheduling readiness를 막는다. `verifies`와
`observes`는 관계를 표시한다. `rework_of`는 새 node가 옛 node를 가리키는 history
관계이며 readiness 계산에 사용하지 않는다. graph version을 publish할 때 cycle
검사를 통과하지 못하면 `graph_rejected`를 기록하고 publish하지 않는다.

### 4.3 Attempt

```text
planned -> dispatched -> running -> succeeded|failed|cancelled|timed_out|lost
lost|timed_out -> outcome_unknown (외부 결과를 모름)
outcome_unknown -> terminal(unknown) 또는 새 retry attempt
```

retry는 새 `attempt_id`, `retry_of`, 이유와 budget reserve를 갖는다. worker_done이
두 번 오면 첫 terminal outcome만 유효하고 두 번째는 `duplicate_ignored`다.

`rework_created`는 실패한 기존 node를 되살리지 않는다. 새 worker revision과 새
verifier revision을 만들고 각각 이전 node를 `rework_of`로 가리킨다. 자동 retry와
자동 rework는 각각 1회가 기본 상한이며, rework 상한을 넘으면 Human Gate를 연다.

## 5. Liveness, progress, verdict

- `liveness`: 마지막 heartbeat와 연결 상태. 연결됨은 일을 했다는 뜻이 아니다.
- `progress`: 실제 output digest, checkpoint, event count 등 관찰 가능한 변화.
  heartbeat만으로 `advanced`를 만들지 않는다.
- `verdict`: Verifier/Human Gate의 명시적 판정. progress나 worker exit code로
  자동 `pass`를 만들지 않는다.

Heartbeat가 threshold를 넘으면 `stale_marked`를 내고, `dead`로 바로 실패시키지
않는다. reconcile이 같은 attempt의 종료 사건을 찾으면 terminal로 복구하고,
찾지 못하면 `outcome_unknown`으로 두어 중복 실행을 막는다.

## 6. Terminal과 partial platform verdict

Run은 모든 필수 scope가 terminal이고 gate 조건이 충족될 때만 `succeeded`다.

### I02 Hardening 계약 (portable reducer)

I02 reducer는 `run_created -> graph_published -> run_terminal` 순서를 지키며,
Run이 terminal이 된 뒤에는 모든 상태 변경 event를 fail-closed로 거부한다.
`succeeded`는 observer를 제외한 active execution node가 하나 이상이고 그
노드가 모두 `passed`일 때만 허용한다. `failed`, `cancelled`, `rejected`,
`blocked`, `inconclusive`는 성공이 아닌 Run 종료다. `failed`와 `cancelled`는
기존 중단(abort) 의미를 보존하고, `rejected`에는 reason 또는 evidence,
`blocked`에는 blocked node 또는 `blocking_reason`, `inconclusive`에는
inconclusive node 또는 `inconclusive_reason`가 있어야 한다.

`node_status_changed`의 노드 ID는 `entity.node_id`만 canonical source다.
entity ID가 없거나 payload에만 ID가 있으면 거부하고, payload ID가 있으면
entity ID와 정확히 같아야 한다. Graph-backed Run에서는 graph에 없는 ID를
거부한다. Run이 없는 legacy 호환 경로는 생성 시 미리 `node_statuses`에
등록된 ID만 상태를 바꿀 수 있으며, 새 node나 Run lifecycle/success
projection을 만들 수 없다.

`node_status_changed`, `verdict_recorded`, `platform_verdict_recorded`는
실제 `run_created`와 `graph_published` 뒤에만 허용한다. node/edge topology는
publish 시 snapshot으로 봉인한다. publish 뒤 외부에서 node/edge 구조를
바꾸면 다음 reducer 적용이 거부되며, node state는 reducer event로만
동기화된다.

| Run terminal status | 의미 | 허용 조건 |
|---|---|---|
| `succeeded` | 실제 실행이 성공함 | active execution node ≥ 1, 모두 `passed` |
| `failed` | 실행 실패로 중단됨 | lifecycle 순서만 충족하면 됨 |
| `cancelled` | 사용자가 실행을 취소함 | lifecycle 순서만 충족하면 됨 |
| `rejected` | graph/assignment/gate가 실행을 거부함 | reason 또는 evidence 필요 |
| `blocked` | 자원/승인 문제로 진행할 수 없음 | blocked node 또는 blocking reason 필요 |
| `inconclusive` | 증거 부족으로 결론을 낼 수 없음 | inconclusive node 또는 reason 필요 |

I02의 책임은 lifecycle, ID, version, terminal 불변성과 reducer projection이다.
`seq` 단조 증가, event 중복/충돌 판정, `prev_digest`/`digest` 실제 hash
연결, JSONL single-writer와 quarantine은 I03 writer의 책임이다. I02는
envelope 필드와 digest 모양을 확인하지만 I03 writer의 순서/해시 책임을
대신하지 않는다.
Windows만 실행하고 macOS가 미실행이면:

```json
{
  "scope": "windows",
  "status": "succeeded",
  "exclusions": ["macos"],
  "platform_verdicts": {
    "windows": {"status": "pass", "evidence_id": "ev_f01_windows"},
    "macos": {"status": "deferred", "confidence": "unknown", "evidence_id": null}
  }
}
```

이를 전체 제품 `approve`나 macOS `pass`로 축약하지 않는다.

## 7. JSONL single writer 계약

디렉터리는 `.graphori/runs/<run_id>/inbox/tmp`, `inbox/ready`, `journal`, `evidence`,
`projection`이다.

1. Producer는 고유한 `producer_event_id`를 가진 UTF-8 완성 JSON 파일을 tmp에 쓴다.
2. flush/close 후 같은 파일시스템 내에서 `ready/<producer>.<seq>.json`으로 rename한다.
3. Writer 한 프로세스만 ready를 읽고 schema, run, idempotency를 검사한다.
4. writer가 monotonic `seq`, `prev_digest`, `digest`를 붙여 journal JSONL에 쓴다.
5. 같은 `producer_event_id` 또는 `event_id`는 한 번만 반영한다. 충돌 payload는
   `idempotency_conflict`로 격리하고 원 사건은 덮어쓰지 않는다.
6. 손상된 tmp/ready/JSONL tail은 `quarantine/`로 이동해 앞의 완전한 기록을 replay한다.
7. canonical writer는 Run별 `journal/.writer.lock`의 POSIX
   `flock(LOCK_EX | LOCK_NB)`를 보유한 한 프로세스뿐이다. lock 파일의 존재는
   ownership이 아니며 inode는 유지한다. 지원하지 않는 platform에서는 writer를
   열지 않고 fail-closed한다. distributed lease/epoch coordinator는 MVP 범위 밖이다.

## 8. Usage와 비용

```json
"usage": {"status":"known", "input_tokens":120, "output_tokens":90,
           "reasoning_tokens":null, "source":"provider_report"}
```

provider가 일부만 주면 모르는 필드는 null, 전체 상태는 `unknown` 또는 계약상
`estimate`다. 출력 문자 수로 token을 역산하지 않는다. `cost_status`는 `known |
estimate | unknown`이며 실제 청구와 client-side estimate를 구분한다.

## 기술 부록 A. 필수 사건 타입

`run_created`, `graph_published`, `node_created`, `edge_created`, `role_assigned`,
`assignment_rejected`, `attempt_dispatched`, `heartbeat`, `progress_reported`,
`worker_finished`, `verdict_recorded`, `gate_created`, `gate_resolved`,
`platform_verdict_recorded`, `usage_recorded`, `node_status_changed`, `retry_created`,
`rework_created`, `runtime_binding_recorded`, `runtime_resource_changed`, `routing_observed`, `stale_marked`,
`reconciled`, `duplicate_ignored`, `idempotency_conflict`, `event_quarantined`,
`run_terminal`.

## 기술 부록 B. 증거 연결

원 설계의 상태·journal 제안은 [`PROPOSED_ARCHITECTURE_SOL.md`](../design/PROPOSED_ARCHITECTURE_SOL.md),
대안의 누락된 WorkNode 완료 전이는 [`DESIGN_EVIDENCE_REVIEW_LUNA.md`](../verification/DESIGN_EVIDENCE_REVIEW_LUNA.md),
F01의 `events 23줄`, `replay_mismatch=0`, Windows 승인과 macOS 미검증은
보존 원문 [`F01_WINDOWS_FINAL_APPROVAL.md`](../evidence/doctori/verification/F01_WINDOWS_FINAL_APPROVAL.md)와
해시 표 [`MANIFEST.md`](../evidence/doctori/MANIFEST.md)에 연결된다.
