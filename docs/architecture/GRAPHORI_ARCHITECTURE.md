# Graphori canonical architecture

> 상태: canonical, 구현 전 설계
> 날짜: 2026-08-14 (Asia/Seoul)
> 범위: portable core, ports/adapters, 동적 작업 그래프와 독립 검증

## 1. 12살도 이해하는 큰 그림

Graphori는 숙제를 여러 장의 카드로 나눠 로봇 일꾼에게 맡기는 공책이다. 카드에는
“무엇을 해야 하는지”, “누가 확인해야 하는지”, “끝났다는 증거가 무엇인지”가 적힌다.
카드를 만든 대장은 직접 코드를 고치지 않고, 일꾼을 고르고 결과를 모아 다음 카드를
열어 준다.

Orca는 공책 자체가 아니라 좋은 연필과 우편함을 제공하는 선택적 어댑터다. Orca가
없어도 일반 Windows 터미널에서 핵심 공책은 동작해야 한다. macOS는 설계상 지원
경계에 포함하지만 실제 실행 증거를 얻기 전까지 승인하지 않는다.

화면의 캐릭터는 실제 사건이 있을 때만 움직인다. 살아 있다는 신호, 실제 일이
진행됐다는 신호, 검사가 통과했다는 판정은 서로 다른 불빛이다. 70%라는 숫자를
예쁘게 만들려고 캐릭터를 움직이지 않는다.

## 2. canonical 결정

1. 대시보드와 계획에는 `planning`, `research`, `design`, `implementation`,
   `verification` 다섯 논리 팀 ID를 유지한다. 팀은 Agent 수가 아니며, 이번 Run에
   필요하지 않으면 `omitted`로 기록한다. 실제 Worker, Verifier, Human Gate는
   필요한 수만 동적으로 만든다.
2. 하나의 graph version의 scheduling edge는 DAG다. `revise`는 옛 노드로 돌아가는
   화살표가 아니라 새 revision node를 만들고 `rework_of` history 관계를 추가한다.
3. portable core가 Run/Task/Attempt/이벤트/판정을 소유한다. 외부 도구는 ports를
   구현하는 adapters다.
4. 모든 producer는 자기 임시 파일을 만들고 `inbox/tmp -> inbox/ready`로 rename한다.
   canonical writer 하나만 ready 파일을 읽어 sequence와 hash를 부여한다.
5. `usage`가 없으면 0이 아니라 `unknown`이다. 예측, 실제 사용량, 가격 추정과
   실제 청구를 섞지 않는다.
6. platform verdict는 플랫폼·fixture·evidence_id별로 따로 기록한다. Windows
   `pass`가 macOS `pass`가 되지 않는다.
7. 현재 사용자와 대화하는 주 에이전트가 기획팀이자 오케스트레이터다. 짧고
   분리 이득이 없는 작업은 현재 세션이 직접 처리할 수 있다. 추가 Agent는 예상
   순시간 이득과 독립 검증 경계가 있을 때만 만든다.
8. 보통 MVP 작업은 새 구현 담당자 한 명이 진행하고, 확인자는 마일스톤·공개
   API·보안·파괴적 변경·높은 불확실성일 때만 추가한다. 예산 기반 자동 Fast
   Mode는 활성 정책이 아니다. 근거는
   [`0006-v2-adaptive-execution-policy.md`](../decisions/0006-v2-adaptive-execution-policy.md)이며,
   [`0004-token-aware-fast-mode.md`](../decisions/0004-token-aware-fast-mode.md)는
   superseded다.

## 3. 경계: core / ports / adapters

### 3.1 Portable core가 소유하는 것

- versioned schema와 canonical enum
- Run, graph version, node, edge, role assignment, Attempt, Gate의 불변식
- risk classifier와 Fast/Standard/Critical 선택
- ready 계산, WIP/fan-in 큐, REVISE 상한(1회)
- 단일 writer에 제출하는 event command와 replay projection
- liveness/progress/verdict, platform partial verdict, usage 상태
- evidence manifest의 경로 규칙·digest 연결

Core는 `orca`, PowerShell, zsh, POSIX signal, SQLite, browser API를 import하지 않는다.

### 3.2 Ports

| Port | core가 묻는 질문 | 기본 adapter |
|---|---|---|
| `EventStore` | 사건을 안전하게 제출·재생할 수 있나? | stdlib JSONL writer |
| `ProcessSupervisor` | 비대화형 child를 시작·취소·종료할 수 있나? | generic Windows; POSIX deferred |
| `AgentRunner` | worker를 어떤 명령으로 실행하나? | generic terminal, Orca optional |
| `Clock` | 현재 시간과 freshness를 어떻게 재나? | monotonic + UTC stdlib |
| `EvidenceStore` | 산출물 digest와 manifest를 어디에 보관하나? | bounded local files |
| `Notifier` | snapshot/replay를 어디로 보내나? | CLI; SSE 후속 |
| `HumanGate` | 승인자가 결정을 내렸나? | CLI; Orca optional |
| `UsageProvider` | provider usage를 보고했나? | provider adapter; 없으면 unknown |

### 3.3 Adapters

Generic adapter는 OS 명령, PID, 파일 경로, stdout/stderr를 core 계약으로 변환한다.
Orca adapter는 `orca orchestration`의 Run/Task/Dispatch/heartbeat/worker_done을
호출하고, 결과를 core event로 번역할 뿐 상태의 최종 권위가 아니다. Orca가 내려가도
이미 기록된 core journal과 CLI replay는 계속 읽을 수 있어야 한다.

## 4. 동적 그래프의 쉬운 규칙

Router가 입력을 읽고 risk×tag와 점수를 계산한다. Fast/Standard/Critical
분류는 참고 개념으로 남고, 그 결과에 따라 [ADR
0006](../decisions/0006-v2-adaptive-execution-policy.md)의 세 가지 실제 그래프
모양(normal/reviewed/critical) 중 하나를 만든다.

- normal(기본, 확인자 없음): `router -> worker -> observer`
- reviewed(마일스톤/위험): `router -> worker -> fresh verifier -> observer`
- critical: `router -> worker -> fresh verifier -> human gate -> observer`;
  Verifier는 작성 Worker와 attempt/provider/model/checkout 중 최소 한 차원
  이상 달라야 한다. 기본적으로 병렬 대안 branch는 만들지 않으며, 사용자가
  직접 요청했거나 evidence가 정말 독립적으로 필요한 예외에서만 fan-in
  형태로 병렬화한다.

Observer는 모든 모드에서 사건을 읽지만 결과를 쓰거나 verdict를 만들지 않는다.
Router도 결과 파일을 직접 수정하지 않는다. Worker가 `done`을 보낸 뒤에만 Verifier가
시작된다. Verifier의 `revise`는 최대 1회이며 그 revise 뒤에도 다시 `revise`면
자동으로 다음 작업을 만들지 않고 Human Gate에서 승인·범위축소·중단을 선택한다.

## 5. 이전 초안의 폐기와 매핑

| 이전 주장 | canonical 처리 |
|---|---|
| SOL의 `RiskLevel × RiskTag`와 ROUTING 5축을 각각 독립 운영 | SOL의 직교 `risk_level(0..3) + risk_tags`를 저장하고 ROUTING의 `risk/uncertainty/scope/synthesis/parallelism`은 `routing_scores` 부속 필드로 매핑한다. hard trigger가 우선한다. |
| Claude안의 flat `risk_class` | 표시용 label로만 유지한다. `docs-only`는 `risk_level=0`, `verification_depth=automatic`으로, `security-boundary`는 tag와 hard trigger로 변환한다. |
| `docs-only = verification_depth=none`와 자동 VerifyNode 동시 표기 | 폐기. canonical은 `docs-only -> observer`(확인자를 자동으로 강제하지 않음)다. 확인이 필요하면 reviewed로 승격해 fresh verifier를 붙인다. |
| `PASS/APPROVE/REVISE` 혼용 | 저장값은 소문자 `pass/revise/approve/...`; UI에서만 대문자 표기한다. |
| `dependency`, `blocked-by`, `requires` 혼용 | scheduling은 `requires`; history는 `rework_of`; observation은 `observes`; 검증은 `verifies`; gate는 `requires_gate`로 고정한다. |
| rework edge가 같은 W로 돌아가는 그림 | 폐기. 새 `task_revision_id`를 만들고 옛 ID를 `rework_of`로 기록한다. scheduling DAG에는 cycle이 없다. |
| 여러 worker의 JSONL 직접 append가 안전 | 폐기. single writer + tmp→ready만 허용한다. |
| SOL의 처음부터 완전한 hash-chain/epoch 구현 | MVP에서는 단일 writer, sequence, digest, idempotency, crash-tail 격리까지만 한다. 강한 fencing/hash chain은 후속 gate다. |

## 6. 근거와 판정의 경계

F01 수치와 결함은 설계 근거가 아니라 보존된 프로젝트 관찰(E1)이다. 원문 7개와
SHA-256은 [`docs/evidence/doctori/MANIFEST.md`](../evidence/doctori/MANIFEST.md)에
연결되어 있다. 특히 세 원문은 [`F01_FINAL_CROSS_MODEL_ACCEPTANCE.md`](../evidence/doctori/verification/F01_FINAL_CROSS_MODEL_ACCEPTANCE.md),
[`F01_WINDOWS_FINAL_APPROVAL.md`](../evidence/doctori/verification/F01_WINDOWS_FINAL_APPROVAL.md),
[`F01_JUNCTION_TEAM2_REAUDIT.md`](../evidence/doctori/verification/F01_JUNCTION_TEAM2_REAUDIT.md)다.
Windows 승인 범위와 macOS `deferred/unknown`은 서로 바꾸지 않는다.

## 기술 부록 A. 불변식 요약

- `schema_version`은 major 변경 때 증가한다.
- graph version의 scheduling edge에는 cycle이 없어야 한다.
- terminal Attempt 뒤에는 같은 `attempt_id`로 실행을 다시 하지 않는다.
- `worker`는 verdict를 만들 수 없고, `verifier` 또는 `human_gate`만 verdict를 만든다.
- 서로 다른 Role은 동일한 identity와 checkout을 독립 검증자로 재사용할 수 없다.
- active WIP(시스템 전체)와 task parallelism(한 task 내부 branch 수)은 필드를 분리한다.
- 같은 capability의 fan-in 대기는 `priority desc, created_seq asc`로 정렬하고, 오래된
  항목은 priority를 올리되 독점하지 않는다. pool이 0이면 Human Gate에 escalated 한다.

## 기술 부록 B. 비목표

현재 문서는 구현·macOS 실행·provider usage 수집·SSE 성능 통과를 주장하지 않는다.
그 acceptance는 [`docs/IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md)에 둔다.
