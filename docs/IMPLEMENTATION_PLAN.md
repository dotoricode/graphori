# Graphori implementation plan

> Historical development plan. The public beta replaced the GitHub Actions stage with the local verifier documented in `docs/public/RELEASE_GATE.md`.

> 상태: 계획만 작성함. 이 문서 작업에서는 구현·실행하지 않는다.

## 1. 12살도 이해하는 순서

먼저 규칙 공책을 만들고, 작은 장난감으로 공책이 맞는지 확인한다. 그 다음 실제
일꾼을 연결하고, 마지막에 게임판과 Orca를 붙인다. Windows에서 실제로 확인한 뒤
macOS에서도 같은 시험을 해야 한다. 시험하지 않은 플랫폼은 통과라고 쓰지 않는다.

## 2. 단계와 acceptance

### 1단계 — skill-creator init / 작업 공간 준비

`skill-creator` 흐름으로 Graphori 전용 skill/AGENTS 지침을 초기화하되, core가
portable Python만 import하는 규칙과 문서 계약 링크를 먼저 넣는다.

Acceptance: init 결과가 저장소에 재현 가능한 명령과 변경 목록을 남기고, core에서
Orca import가 0건이며 구현 단계의 owner가 지정된다.

### 2단계 — portable Python stdlib core

Run/graph/node/edge/attempt/reducer/risk compiler를 구현한다. canonical enum은
[`EVENT_PROTOCOL.md`](architecture/EVENT_PROTOCOL.md)를 그대로 사용하고, revision은
새 node로만 만든다. `docs-only -> observer`(자동 verifier 강제 없음), REVISE
1회([ADR 0005](decisions/0005-mvp-simple-single-verifier.md)), WIP·fan-in
queue, critical independence pool ≥2(필요할 때만)를 포함한다.

Acceptance: in-memory fixture 세 가지(normal/unreviewed, reviewed, critical)가
동일한 graph와 terminal projection을 만들고, scheduling cycle·same-attempt
verifier·revise 2회가 거절된다.

### 3단계 — JSONL journal / evidence

single writer, `inbox/tmp -> inbox/ready`, sequence/digest, idempotency,
quarantine/crash-tail recovery를 구현한다. SQLite는 read cache일 때만 선택한다.

Acceptance: producer 10개가 동시에 tmp를 만들고 writer가 순서·중복·충돌을
결정적으로 처리한다. replay snapshot digest가 같고 잘린 마지막 줄을 격리한다.

### 4단계 — contract tests

stdlib unittest로 state transition, usage known/estimate/unknown, partial platform
verdict, path boundary, process termination, WIP/fan-in, stale/reconcile을 fixture화한다.

Acceptance: Windows runner에서 전체 suite가 재현되고, 실패 fixture는 자동 PASS로
승격되지 않는다. macOS는 실행 host가 없으면 `deferred/unknown` 보고서를 만든다.

### 5단계 — generic terminal adapter

`ProcessSupervisor`, `AgentRunner`, `Clock`, `EvidenceStore`, CLI status/replay를
붙인다. argv/cwd/env allowlist, bounded output, Windows Job Object와 POSIX process
group 규칙을 adapter에 둔다. PTY/GUI는 제외한다.

Acceptance: Windows에서 child 정상 종료·timeout·tree kill, path escape,
symlink/junction/case collision, 외부 marker 불변을 실제로 확인한다. macOS에서는
같은 명령과 fixture가 실행되기 전까지 platform verdict를 승인하지 않는다.

### 6단계 — dashboard

SSE snapshot/replay/Last-Event-ID, reducer view model, heartbeat freshness, truthful
sprite motion, stale freeze, quest와 Human Gate UI를 만든다. original pixel art만
제작하고 reduced-motion/accessibility를 포함한다.

Acceptance: heartbeat만으로 percent가 변하지 않고, progress digest 한 번이 motion
한 번을 만들며, replay 재연결 때 중복 모션이 없다. Windows pass + macOS deferred가
함께 보인다.

### 7단계 — Orca optional adapter

Orca Run/Task/Dispatch/heartbeat/worker_done/gate를 core port에 연결한다. Orca
장애 시 generic CLI replay가 계속 동작하도록 한다. Orca SQLite 내부를 core가
직접 읽지 않는다.

Acceptance: Orca 연결/미연결 양쪽에서 같은 fixture projection이 같고, adapter 오류가
core corruption이 아닌 `adapter_unavailable` event가 된다.

### 8단계 — GitHub Actions

Windows job을 필수로 두고 Python 버전 matrix, unit/contract tests, artifact digest,
dashboard smoke를 실행한다. macOS runner job은 연결될 때 같은 fixture를 실행하고,
없으면 `deferred` artifact만 올린다. secret과 사용자 절대 경로를 artifact에서 제거한다.

Acceptance: PR에서 Windows evidence manifest가 생성되고 `platform × fixture ×
verdict × evidence_id` 표와 run URL이 남는다. macOS가 실행되지 않은 workflow는
전체 approve를 만들지 않는다.

### 9단계 — 독립 감사와 Human Gate

Verifier와 Human Gate 후보를 별도 identity/provider/model/checkout으로 배정하고,
100개 작업 또는 30일 중 빠른 주기로 seeded-defect 표본을 감사한다. false negative,
independence violation, usage 없는 배포, adapter divergence, revise 상한 우회는
rollback trigger다.

Acceptance: 독립 감사자의 fresh report와 승인자의 gate event가 모두 journal에
있고, 1회 revise 뒤 자동 작업이 더 생기지 않는다. 미검증 OS는 scope exclusion으로
남는다.

## 3. 금지된 선행 작업

구현 전에 전체 hash-chain/epoch fencing, 다중 writer append, PTY/Browser 자동화,
정확한 provider 가격 상수, macOS PASS를 먼저 만들거나 주장하지 않는다. SOL의
대형 acceptance는 portable MVP에서 최소 journal·replay·idempotency로 축소한다.

## 4. 근거와 산출물

이 계획은 [`GRAPHORI_ARCHITECTURE.md`](architecture/GRAPHORI_ARCHITECTURE.md),
[`TEAM_TOPOLOGY.md`](TEAM_TOPOLOGY.md), [`0005-mvp-simple-single-verifier.md`](decisions/0005-mvp-simple-single-verifier.md),
[`PORTABILITY_CONTRACT.md`](architecture/PORTABILITY_CONTRACT.md),
두 REVISE 보고서([`Luna`](archive/verification/DESIGN_EVIDENCE_REVIEW_LUNA.md),
[`Claude`](archive/verification/DESIGN_COMPARISON_CLAUDE.md))의 MUST/P0/P1을 반영한다.
F01 원문 7개는 [`MANIFEST.md`](archive/evidence/doctori/MANIFEST.md)에 SHA-256으로 보존된다.
그 원문은 Graphori 구현 통과가 아니라 Doctori 관찰 evidence다.

## 기술 부록

단계 완료를 선언할 때에는 `stage_id`, `acceptance_id`, `platform`, `fixture`,
`verdict`, `evidence_id`, `command`, `artifact_sha256`을 함께 기록한다. 한 단계의
문서 작성 완료는 다음 단계의 구현 acceptance를 대신하지 않는다. `docs/PROCESS.md`
의 9단계 표가 이 계획의 진행률 기준이며, 현재는 `0/9`다.
