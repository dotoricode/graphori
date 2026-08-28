# Graphori 설계 증거 독립 검수 — Luna

## 1. 검수 범위와 판정

검수일: 2026-08-09 (Asia/Seoul)

검수 대상은 다음 세 설계 문서와 이들이 직접 인용하는 세 조사 보고서다.

- `docs/design/PROPOSED_ARCHITECTURE_SOL.md` (SOL 설계)
- `docs/design/MODEL_ROUTING_AND_FAST_MODE.md` (모델 라우팅 설계)
- `docs/design/ALTERNATIVE_ARCHITECTURE_CLAUDE.md` (대안 설계)
- `docs/research/TEAM_GRAPH_ANALYSIS.md`
- `docs/research/PORTABILITY_AND_DEPENDENCY.md`
- `docs/research/LIVE_GAME_DASHBOARD.md`

요청자가 역할을 지정하지 않았으므로, 실제 구현·운영에 이 설계를 사용할 앱 개발자와 서버 개발자 관점으로 추론했다. 검수는 정적 문서·링크·계약 대조(S, E1)만 수행했으며, 구현하거나 실행하지 않았다. 따라서 `E`가 필요한 build/run/OS 판정은 `PASS`가 아니라 `NOT VERIFIED`로 둔다.

## 2. 최종 판정

**REVISE**

### 결과 게이트

- **Critical gate:** P0 `FAIL`이 있다. 특히 대안 상태 머신은 WorkNode를 완료시키는 전이가 없어 현재 표기 그대로는 DAG가 진행되지 않는다.
- **검증 커버리지:** 문서·출처·계약의 정적 대조만 확인했다. 구현 실행, 재현 fixture, macOS 실행, provider usage 로그는 0건이므로 실행이 필요한 항목의 확인 커버리지는 0이다.
- **확인된 통과:** 문서가 설계 전용임을 밝히고, Windows 승인과 macOS `deferred/unknown`을 구분하며, 토큰 미측정값을 `unknown`으로 기록해야 한다는 원칙은 정적 문장으로 확인됐다. 이는 구현·실행 통과를 의미하지 않는다.
- **미검증 목록:** macOS 및 Windows의 실제 generic adapter 실행, journal 동시성·재생·복구, risk classifier 탐지율, 상태 전이, CLI usage 수집, dashboard/SSE·접근성, portable MVP build/run.

## 3. 핵심 발견

### P0-1 — 프로젝트 고유 주장의 원문 증거가 저장소에 없다

`TEAM_GRAPH_ANALYSIS.md`는 `WORK_DURATION_ANALYSIS.md`, ADR `0003/0005`, 세 verification 문서를 F01의 근거로 인용한다(37–45행). 그러나 현재 저장소에서 이 링크 대상은 모두 누락되어 있다. 그 결과 세 설계 문서의 “7개 역할·18 checkpoint·세 결함(ELF 경로, AST 절대경로, junction)·최종 Windows 승인”은 원문과 hash/실행 로그로 독립 대조할 수 없고, 조사 보고서의 요약을 다시 인용하는 E1 수준에 머문다.

영향: 역할 수를 4개로 줄이거나 targeted 검증을 허용하는 핵심 근거가 재현되지 않는다. “실제 결함을 찾아냈다”는 표현을 구현 안전성의 증거처럼 사용하면 잘못된 승인으로 이어질 수 있다.

수정안: 누락된 원문을 복구하거나, 최소한 각 주장에 `source_path`, revision/hash, 수집 시각, 실행 명령, host OS, 원시 결과를 포함한 evidence manifest를 추가한다. 원문을 복구하기 전에는 해당 값들을 “프로젝트 관찰 요약(E1)”으로 낮추고, 설계 선택의 승인 근거로 사용하지 않는다.

### P0-2 — 대안 상태 머신에는 WorkNode의 완료 전이가 없다

`ALTERNATIVE_ARCHITECTURE_CLAUDE.md`의 상태 머신은 `RUNNING`에서 `verdict_recorded(PASS/APPROVE) → DONE`을 **verify/decision 노드에만** 허용한다(473–489행). WorkNode는 verdict를 만들 수 없다고 명시되어 있으므로 WorkNode의 `worker_done`, `finished`, `failed`, `cancelled` 전이가 없다. 그런데 작은 작업 토폴로지는 `WorkNode → VerifyNode` dependency를 요구하고(173–195행), dependency는 앞 노드가 끝나야 뒤 노드가 시작한다고 정의한다(138–150행).

영향: 규칙을 그대로 구현하면 WorkNode가 영원히 `RUNNING`이고 VerifyNode가 시작되지 않으며, 최소 MVP의 정상 경로가 막힌다. 이는 설명상의 누락이 아니라 상태 머신과 DAG 실행 조건의 직접 모순이다.

수정안: `WorkNode`에 `worker_finished(outcome, evidence)` 및 `worker_failed(reason)`, `cancel_requested → cancelled`, `heartbeat timeout → stale/dead` 전이를 명시하고, `finished` 후 검증 대기 상태를 별도로 둔다. 노드 상태와 Task/Run 상태를 분리하고, 종료 사건 유실 시 `outcome_unknown/lost → reconcile` 경로도 SOL의 Attempt 규칙과 동일하게 정의한다.

### P0-3 — 대안 문서의 `docs-only` 검증 깊이가 서로 충돌한다

위험 분류표는 `docs-only`를 `fan-out=0`, `verification_depth=none`으로 정의한다(152–166행). 같은 문서의 작은 일 토폴로지는 WorkNode 뒤에 “자동 targeted 검사” VerifyNode를 배치하고(173–190행), 기술 부록 의사코드도 `docs-only`에 `VerifyNode(depth=none)`을 생성한다(370–380행). 즉 VerifyNode가 없다는 정책인지, 자동 lint VerifyNode가 있다는 정책인지 결정되지 않았다.

영향: 같은 입력이 어떤 그래프를 만드는지 결정적으로 재현할 수 없고, “검증을 줄였다”와 “자동 검사를 한다”의 비용·완료 조건을 구현자가 임의로 해석하게 된다.

수정안: 하나를 canonical로 선택한다. 권장안은 `docs-only = WorkNode → 자동 lint/check (depth=automatic)`로 두고, 사람이 검수하지 않았음을 명시하는 것이다. `none`은 정말 검증 노드를 생성하지 않는 경우에만 사용하며, 표·토폴로지·의사코드·acceptance test의 동일 사례를 모두 갱신한다.

### P0-4 — portable MVP와 macOS는 아직 실행으로 검증되지 않았다

세 문서는 모두 설계 전용·미구현이라고 명시한다. 조사 보고서도 현재 macOS 실행 증거가 없다고 기록한다(`TEAM_GRAPH_ANALYSIS.md` 20–26, 90행). SOL은 Windows/macOS를 별도 `PlatformVerdict`로 두고 `macos/deferred`를 전체 PASS로 만들지 않도록 했으며(634행, 754–758행), 대안도 Windows `APPROVE` 뒤 macOS gate를 `deferred/unknown`으로 남긴다(411–448행). 이 부분은 오표시 방지 원칙으로는 적절하지만, “일반 macOS 터미널에서도 핵심 기능이 그대로 동작한다”는 portability 조사 결론(5, 23행)은 실행 결과가 아니라 설계 가능성이다.

영향: Windows 문서 승인이나 로컬 정적 검토가 macOS portable MVP의 승인으로 오인될 위험이 있다. 또한 generic terminal이 실제로 process tree 종료, symlink/junction 경계, file rename, event journal, CLI usage까지 양 OS에서 동일하게 처리하는지는 알 수 없다.

수정안: 모든 문서와 대시보드에 `platform × fixture × verdict × evidence_id` 표를 둔다. macOS 호스트/CI가 없으면 `BLOCKED` 또는 `deferred/unknown`을 유지하고, 상위 Run은 `complete(scope=windows, exclusions=[macos])` 같은 부분 완료로만 기록한다. portable MVP의 1차 범위를 JSONL journal + 단일 writer + 비대화형 child process + CLI status/replay로 좁히고, SSE/Orca adapter/PTY/다중 writer는 후속 acceptance로 분리한다.

## 4. 데이터 모델·상태 머신 정합성

### P1-1 — 세 설계의 enum과 edge 계약이 canonical하지 않다

- SOL은 `VerificationDepth = none | automatic | targeted | fresh_full | adversarial`, `Verdict = pass | revise | inconclusive`로 둔다(170–192행).
- 대안은 `verification_depth = none | targeted | fresh-full`, `verdict = pending | PASS | REVISE | APPROVE | null`로 둔다(331–350행).
- 대안의 이벤트는 `verdict_recorded(PASS/REVISE)`를 쓰고(456–471행), 모델 라우팅은 `review != PASS` 및 `review_result`를 쓴다(295–355, 357–375행).
- SOL의 scheduling edge는 `requires`, `requires_evidence`, `requires_gate`, `requires_resource`, `verifies`, `observes`이고(281–309행), 대안은 `dependency`, `oversight`, `rework`, `blocked-by`, `observes`다(138–150행). `TaskNode.kind`의 `platform_gate`도 대안의 네 `node_type`에는 없다.

영향: adapter, reducer, evidence manifest가 어느 enum을 저장해야 하는지 정해지지 않아 같은 결과가 `pass/PASS/APPROVE` 또는 `fresh_full/fresh-full`로 갈라질 수 있다. 서로 다른 “대안”임을 명시할 수는 있지만, 하나를 선택해 MVP로 구현하려면 이 상태로는 계약이 아니다.

수정안: 공통 `schemaVersion`과 canonical enum을 정하고, 대안별 용어는 변환표로 명시한다. 예를 들어 내부 판정은 `pass | revise | inconclusive | approve`로 통일하고 화면 표기만 대문자로 바꾼다. `rework_of`는 history relation, `requires/verifies`는 scheduling relation처럼 관계 의미를 분리하고, `platform_gate`를 node 또는 gate/requirement 중 하나로 고정한다.

### P1-2 — stale/dead 상태의 복귀와 WorkNode/Attempt 상태가 불완전하다

대안 상태 머신은 heartbeat 부재로 `stale → dead`가 되지만(480–486행), 이후 heartbeat가 복귀했을 때 `fresh/running`으로 돌아가는 전이가 없다. 반면 SOL은 attempt `lifecycle`과 `freshness`를 분리하고, 신호 상실 후 reconcile 뒤 새 `retryOf` attempt를 만들도록 한다(255–277, 653–660행). LIVE 조사도 `STALE → reconnect + snapshot/replay_ok → 해당 확정 상태`를 정의한다(435–474행).

수정안: 노드 상태와 freshness를 분리하고, stale 상태에서 reconnect/reconcile을 통해 기존 attempt를 복구할지 새 attempt로 만들지 결정하는 규칙을 추가한다. `dead`를 곧 `failed`로 취급하지 않되, 실행 결과가 불명확하면 `outcome_unknown`으로 남겨 중복 실행을 막는다.

### P1-3 — 대안 의사코드는 최소 실행 계약으로도 닫혀 있지 않다

`external-blocked` 분기에서 `edges += [blocked-by(merge_node, ...)]`를 수행하지만 그 분기 안에서 `edges`와 `merge_node`의 생성이 정의되지 않는다(370–403행). 이는 구현 금지 요청을 위반했다는 뜻이 아니라, 현재 의사코드가 acceptance에 바로 옮길 수 있는 결정적 설계 계약이 아니라는 뜻이다.

수정안: 의사코드를 비규범적 그림으로 명시하거나, 모든 분기에서 `nodes`, `edges`, `merge_node`를 먼저 생성하고 `blocked-by`의 방향·대상·재개 조건을 정의한다. 최소 fixture 하나에 대해 입력 graph, emitted events, terminal projection을 예시로 고정한다.

### P1-4 — JSONL 동시 append의 portability 주장이 조사와 설계에서 다르다

이식성 조사 보고서는 여러 프로그램이 JSONL에 동시에 append해도 안전하다고 설명한다(140–153행). 그러나 SOL은 Windows/macOS에서 atomicity와 lock 의미가 같다고 보장할 수 없으므로 여러 worker가 직접 append하지 말고, 단일 writer와 `inbox/tmp → inbox/ready` rename을 사용하라고 정정한다(426–436행). 대안의 `EventLog.append()`는 파일 기반이라고만 하고 같은 단일 writer/epoch/dedup 계약을 고정하지 않는다(302–327행).

영향: 이식성의 핵심인 sequence 연속성, hash chain, dedup, crash tail 복구가 동시 append에서 깨질 수 있다.

수정안: SOL의 단일 canonical writer 계약을 세 문서의 공통 MVP 계약으로 채택한다. producer 임시 파일의 고유 이름, ready rename, writer의 epoch·sequence·hash 부여, 부분 record 격리, replay hash를 portable fixture로 검증하기 전에는 “동시 append 안전”이라고 쓰지 않는다.

## 5. 출처가 실제 주장을 뒷받침하는지

### P0/P1 출처 이슈

1. **프로젝트 고유 F01 수치·결함:** 위 P0-1처럼 인용된 원문이 없어 원 주장에 대한 직접 증거가 없다. Team Topologies, Conway, Brooks, Little, DORA, Bazel, ChatDev 논문은 일반 원칙을 지지할 수 있지만 Graphori의 7→4 역할 안전성이나 defect detection을 증명하지 않는다. 해당 문서도 일부를 “설계용 proxy”라고 제한하지만, 설계 문서에서는 일반 원칙과 프로젝트 관측을 별도 evidence class로 표시해야 한다.
2. **Orca 로컬 관찰:** `PORTABILITY_AND_DEPENDENCY.md` 44–60, 233–285행은 특정 컴퓨터의 `orca --help`, RPC, SQLite 헤더, terminal-history를 직접 확인했다고 서술한다. 그러나 출력 로그·DB hash·orca 버전이 저장소 artifact로 남아 있지 않아 독립 검수자는 재현할 수 없다. 문서 자체도 533–539행에서 특정 설치 버전의 1차 근거라고 제한하므로 “현재 Orca의 일반 동작”이 아니라 “수집 시점의 로컬 관찰”로 표시해야 한다.
3. **CLI usage:** 조사 보고서는 Claude Code와 Codex가 실행 종료 JSON에서 토큰 수를 출력한다고 일반화한다(165–167행, 420–442행). 확인한 공식 문서에서 Codex `codex exec`는 비대화형 실행과 stdout 최종 메시지를 보장하지만 usage JSON을 보장한다고 쓰지 않는다([Codex non-interactive mode](https://developers.openai.com/codex/noninteractive)). Claude Code는 `--output-format json`에서 usage metadata를 제공할 수 있지만 비용은 client-side estimate이며 실제 청구액과 다를 수 있다고 명시한다([Claude headless](https://code.claude.com/docs/en/headless), 149–187행). 따라서 두 provider 모두 “실제 토큰을 항상 얻는다”는 출처는 아니며, provider adapter가 usage를 못 받는 경우가 정상적으로 존재한다.
4. **모델·가격:** 라우팅 문서의 GPT-5.6 Luna/Sol 이름과 API 가격($1/$6, $5/$30 per 1M input/output)은 현재 공식 OpenAI 모델 비교표와 일치한다([Models](https://developers.openai.com/api/docs/models), [Compare](https://developers.openai.com/api/docs/models/compare)). 다만 이는 `price_checked_at`이 붙은 시점의 catalog snapshot이지 설계 상수가 아니다. 문서의 매 실행 catalog 확인 규칙은 타당하다. Claude에는 숫자 가격을 고정하지 않은 점도 타당하다.
5. **SSE·접근성·관측성:** LIVE 보고서의 WHATWG/MDN/RFC/WCAG/OpenTelemetry 인용은 protocol/standard의 동작·원칙을 뒷받침하지만, `2H/4H`, 30초~1분 heartbeat, 5초 사용성, 화면 배치, motion token은 자체 설계 후보다. 보고서가 이를 후보·실제 테스트 필요라고 쓰고 있어 source/own proposal 구분은 대체로 양호하다.

### P1-5 — 토큰 수치가 없을 때의 처리

모델 라우팅 문서는 `predicted_tokens`, `actual_tokens`, `unit_price`를 분리하고 없으면 `unknown`으로 남기며(170–179, 357–375행), unknown predicted tokens이면 Fast를 금지한다. 팀 분석도 role별 token·비용·재실행 시간이 미측정이라고 기록한다. 이 원칙은 **PASS(E1, 정책 문장에 한함)**다.

다만 이식성 조사 문서의 “CLI가 사용량 JSON을 출력한다”는 문장과 대안의 `AgentRunner.run → usage` 반환 예시는 usage를 필수처럼 읽히게 한다(대안 302–312, 307–311행). actual usage가 없을 때 unknown을 유지하는 필드와 비용 추정/실청구 구분이 대안·portable MVP 계약에는 없다.

수정안: 공통 결과를 `usage: known({input, output, reasoning, source}) | unknown`으로 만들고, `cost_status = known | estimate | unknown`을 추가한다. stdout 문자 수로 token을 역산하지 않으며, provider usage가 없는 Codex/환경은 `unknown`으로 기록하고 completion 조건에서 요구되는지 모드별로 명시한다.

## 6. 문서별 규칙 판단

| 규칙/관점 | 판정 | 증거 등급 | 근거 |
|---|---|---:|---|
| 사용자·핵심 과업·성공 조건 식별 | PASS(정적 범위) | E1 | 세 설계 모두 설계 전용과 목표를 밝히고 SOL 18장의 acceptance를 제시한다. |
| 역할·환경 가정 공개 | PASS(정적 범위) | E1 | 조사 보고서는 원문 검증 문서 부재와 macOS 미실행을 명시한다. |
| 주장과 근거의 일치 | FAIL | E1 | F01 원문 artifact가 없고 CLI usage를 과장한 문장이 있다(P0-1, 출처 1–3). |
| 최소 통합 경로 | NOT VERIFIED | E1 | 구현·sample·build가 없고 설계 전용이다. |
| OS/도구 호환성 범위 | NOT VERIFIED | E1 | Windows/macOS를 분리 표기하지만 실제 OS 실행 증거가 없다. |
| 코드/상태 전이가 실제로 동작 | FAIL(대안 상태 정의) | E1 | WorkNode 완료 전이가 없어 설계대로는 작은 graph가 끝나지 않는다(P0-2). |
| 오류·재시도·중복·복구 계약 | NOT VERIFIED | E1 | SOL에 제안은 있으나 실행 fixture·로그·replay 검증이 없다. |
| 보안·경로 경계 | NOT VERIFIED | E1 | 규칙과 acceptance는 있으나 macOS/Windows fixture 실행이 없다. |
| 토큰·비용 unknown 보존 | PASS(라우팅 정책 문장) / REVISE(공통 모델) | E1 | 라우팅은 명시적 unknown이나 portable/대안 usage 계약이 필수처럼 보인다. |
| macOS를 Windows 승인으로 대체하지 않음 | PASS(표기 규칙) | E1 | SOL 634, 754–758행 및 대안 446–448행이 deferred/unknown을 유지한다. 실제 macOS 통과는 NOT VERIFIED다. |

## 7. 우선 수정 순서

1. P0-1의 누락 원문을 복구하거나 evidence manifest로 대체하고 F01 수치·결함의 evidence class를 낮춘다.
2. P0-2와 P0-3을 해결해 WorkNode 정상·실패·취소·lost 전이와 docs-only 그래프를 하나의 fixture로 고정한다.
3. SOL을 canonical schema로 삼을지 결정하고 enum, edge, node/task/run 상태의 versioned mapping을 작성한다.
4. 단일 writer/inbox/ready/epoch/hash/dedup 계약과 `usage/cost unknown` 계약을 portable MVP에 반영한다.
5. Windows와 macOS에서 같은 fixture를 실제 실행하고, OS별 `PASS/FAIL/NOT VERIFIED/BLOCKED`와 evidence ID를 각각 기록한다. macOS 실행 전에는 전체 `APPROVE`를 선언하지 않는다.
6. 그 뒤에만 risk classifier seeded-defect 탐지율, rework 비용, token/cost, SSE/dashboard와 접근성 acceptance를 측정한다.

현재 문서에는 정직한 `deferred/unknown` 및 token `unknown` 원칙이 상당 부분 들어가 있지만, 핵심 상태 전이·출처 artifact·공통 계약이 닫히지 않았다. 따라서 구현으로 넘어가기 위한 판정은 **REVISE**다.
