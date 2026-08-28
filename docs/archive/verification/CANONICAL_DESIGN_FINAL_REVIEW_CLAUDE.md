# Canonical 문서 최종 검수: TEAM_TOPOLOGY / architecture 4종 / decisions 4종 / IMPLEMENTATION_PLAN / MANIFEST

검수일: 2026-08-09 (Asia/Seoul)
검수자: Claude (독립 검수 세션 — 이번 canonical 문서 작성자와 분리)
검수 방법: 정적 문서·링크·해시·상태 전이 대조(S, E1). **구현·수정하지 않았다. 코드와 문서를 한 줄도 고치지 않았다.**

검수 대상:

- `TEAM_TOPOLOGY.md` (repo root)
- `docs/architecture/GRAPHORI_ARCHITECTURE.md`, `EVENT_PROTOCOL.md`, `DASHBOARD_CONTRACT.md`, `PORTABILITY_CONTRACT.md` (4개 물리 파일 + `TEAM_TOPOLOGY.md`을 포함해 architecture 계열 5개 문서)
- `docs/decisions/0001~0004` (4개)
- `docs/IMPLEMENTATION_PLAN.md`
- 이전 REVISE 보고서 2건: `docs/verification/DESIGN_COMPARISON_CLAUDE.md`, `docs/verification/DESIGN_EVIDENCE_REVIEW_LUNA.md`
- `docs/evidence/doctori/MANIFEST.md` (+ 실제 evidence 원본/복사본 7개 파일의 SHA-256 재계산)

---

## 0. 최종 판정

> **APPROVE**

두 REVISE 보고서가 요구한 MUST 10개(Claude 비교 검수) + P0 4개/P1 5개(Luna 증거 검수), 총 19개 항목 전부를 canonical 문서에서 실제 문구와 상태 전이로 확인했다. 문서 간 링크는 15개 문서, 40여 개 상대경로 링크 전부 대상 파일이 실제로 존재한다. macOS는 모든 위치에서 예외 없이 `deferred/unknown`으로만 표기되고 `pass`로 격상된 곳이 없다. 대시보드 자산은 "저장소에서 직접 제작한 original pixel art만" 사용하도록 명시되어 있고 외부/AI 생성물을 원본으로 가장하는 것을 금지한다. `docs/evidence/doctori/MANIFEST.md`의 SHA-256 7건은 원본·복사본을 재해시한 결과와 100% 일치했다. IMPLEMENTATION_PLAN은 이미 확정된 canonical 규칙만 순서대로 실행 계획으로 옮겼을 뿐, 새 설계 결정을 스스로 만들지 않았고 §3에서 hash-chain/다중 writer/PTY/macOS PASS 선언을 명시적으로 금지한다.

경미하고 차단 대상이 아닌 관찰 2건만 8장에 기록한다.

---

## 1. 12살도 이해하는 요약

전에 두 명의 검사 선생님(Claude 검수, Luna 검수)이 설계도 두 장을 보고 "잘했어요, 그런데 다시 해와요(REVISE)"라고 했어요. 문제가 19개나 있었거든요: "옛날 도둑 잡은 증거 쪽지가 없다", "검사하는 로봇이 일을 끝내는 문 하나가 아예 없다", "위험한 정도를 재는 자가 세 개라서 서로 다른 답이 나온다", "검사반장이 한 명뿐이면 어떡하냐는 질문에 답이 없다" 같은 것들이요.

이번에 새로 그린 설계도 다섯 장(`TEAM_TOPOLOGY`, 건축 계약 4장)과 결정 카드 4장, 실행 순서표 1장을 다 읽어봤어요. 그리고 지난번 문제 19개를 하나씩 번호를 매겨서 "이번엔 정말 고쳤나?"를 확인했어요.

**결과는 좋아요.** 19개 문제 전부 새 문서 안에 구체적인 문장으로 답이 있었어요.

- "증거 쪽지가 없다" → 이제 `MANIFEST.md`에 쪽지 7장의 지문(SHA-256)이 있고, 제가 직접 원본과 복사본을 다시 확인해봤는데 지문이 완전히 똑같았어요.
- "검사 끝내는 문이 없다" → 이제 `running -> awaiting_verification`이라는 문이 생겼어요.
- "자가 세 개다" → 이제 하나로 합치는 표가 있어요.
- "검사반장 한 명 문제" → 이제 "최소 2명, 한 명이 사라지면 다른 한 명이 대신한다"는 규칙이 있어요.

또 확인해야 할 세 가지도 다 지켰어요: 모든 문서의 macOS 부분은 항상 "아직 모름/미룸"이라고만 써 있고 절대 "통과"라고 쓴 곳이 없었어요. 그림 재료는 "우리가 직접 그린 것만" 쓴다고 정확히 적혀 있어요. 그리고 "실제로 만드는 순서표"(IMPLEMENTATION_PLAN)는 아직 정해지지 않은 걸 미리 정하지 않고, 이미 정해진 규칙만 순서대로 나열했어요.

그래서 이번 점수는 "**통과(APPROVE)**"예요. 아주 작은 메모 두 개만 남겼는데, 다시 해오라고 할 만큼 큰 문제는 아니에요.

---

## 2. 방법과 한계

- 정적 텍스트·링크·SHA-256만 대조했다(S, E1). 코드 실행, macOS 실행, portable core 구현, dashboard 실제 렌더링은 이 검수의 범위가 아니며 canonical 문서들도 스스로 미구현이라고 명시한다(`GRAPHORI_ARCHITECTURE.md:125`, `IMPLEMENTATION_PLAN.md:3`).
- "해결됐다"는 판정은 (a) 문제를 유발한 문구가 폐기되었고 (b) 대체하는 구체적 규칙·상태 전이·수치가 canonical 문서에 실제로 존재함을 뜻한다. 단순히 "고려하겠다"는 서술은 FAIL로 처리했다 — 이번 검수에서는 그런 사례가 없었다.
- 인용은 `파일:줄` 형식이며, 모든 줄 번호는 이 세션이 파일을 직접 읽은 결과다.

---

## 3. DESIGN_COMPARISON_CLAUDE.md — MUST 10개 항목별 PASS/FAIL

| # | MUST (이전 REVISE 요구) | 판정 | 해소한 실제 문구·상태 전이 |
|---|---|---|---|
| 1 | F01 근거 추적 복구 또는 미검증 주장으로 강등 | **PASS** | `MANIFEST.md`에 7개 원문의 SHA-256 표(1–16행). 이 검수가 원본·복사본을 재해시해 7건 모두 일치 확인(3장). `GRAPHORI_ARCHITECTURE.md:104-110` "F01 수치와 결함은 설계 근거가 아니라 보존된 프로젝트 관찰(E1)이다" — 강등 문구 실재. |
| 2 | 이벤트 저널 동시쓰기 규칙(단일 writer lease + tmp→ready) 채택 | **PASS** | `EVENT_PROTOCOL.md:145-153` 7단계 절차 명시, 7번째 항목이 "동시 append가 안전하다는 이전 조사 문장을 폐기한다"를 직접 선언. `GRAPHORI_ARCHITECTURE.md:31-32`(결정 4) 동일 규칙 재확인. |
| 3 | 위험 분류 체계(SOL/CLAUDE/ROUTING) 통합 또는 매핑 | **PASS** | `GRAPHORI_ARCHITECTURE.md:94-95` 매핑표: SOL `risk_level+risk_tags`를 저장값으로, ROUTING 5축은 `routing_scores` 부속 필드로, CLAUDE `risk_class`는 표시용 label로 강등. `ADR 0002` 기술 부록에 동일 내용 재확인. |
| 4 | rework 다이어그램의 시각적 cycle 표기 수정 | **PASS** | `EVENT_PROTOCOL.md:22` `edge_kind`에 `rework_of` 별도 분류, `:93-96` "`rework_of`는 새 node가 옛 node를 가리키는 history 관계이며 readiness 계산에 사용하지 않는다", `:85` node 전이 `failed -> ready (새 revision만; 같은 node 재실행 금지)` — 실제 상태 전이로 cycle을 배제. |
| 5 | 독립 감사자/게이트 승인권자 최소 인원(≥2) + 대체 정책 | **PASS** | `TEAM_TOPOLOGY.md:59-65` "독립 Verifier pool의 최소 정원은 2명/identity... 현재 holder가 heartbeat를 잃으면 2번째 pool member가 takeover한다. 둘 다 없으면 timeout 후 자동 승인하지 않고 `blocked`를 유지한다." — 최소 인원, 대체, timeout≠자동승인 모두 명문화. |
| 6 | fan-in 대기열/우선순위 정책 | **PASS** | `TEAM_TOPOLOGY.md:78-80` `priority = risk_level*10 + age_band`, 동일 priority는 FIFO, `age_band`는 시간마다 상승해 굶주림 방지. `GRAPHORI_ARCHITECTURE.md:120-121` 부록 A에 동일 규칙 재확인. |
| 7 | 검증 REVISE 루프 상한(예: CLAUDE안의 `reworkCountSince>2`) 이식 | **PASS** | `TEAM_TOPOLOGY.md:88-91` `revise_count` 0에서 시작, 3회까지 자동 순환, 3회 초과 시 `human_gate_required(reason=revise_limit)`로 전환 — canonical에 명시적 상한과 전이가 있다. |
| 8 | OS 프로세스 감독 포트(SOL의 `ProcessSupervisor` 계승) | **PASS** | `PORTABILITY_CONTRACT.md:39-46` `ProcessSupervisor` port(`start/poll/terminate/kill/collect`), Windows Job Object·POSIX process group 규칙 구체화. `GRAPHORI_ARCHITECTURE.md:59` ports 표에도 등재. |
| 9 | ROUTING의 `reviewer_model_id`와 독립성 제약 상호 참조 | **PASS** | `TEAM_TOPOLOGY.md:66-67` "ROUTING의 `reviewer_model_id`도 이 규칙을 통과해야 한다." `ADR 0004`(`docs/decisions/0004-token-aware-fast-mode.md:18`) "독립 reviewer_model_id는 TEAM_TOPOLOGY의 independence constraint를 반드시 통과한다" — 양방향 교차 참조 확인. |
| 10 | 명시적 롤백/실패 트리거 채택(CLAUDE안 §5 수준) | **PASS** | `TEAM_TOPOLOGY.md:96-106` "실패·롤백 조건" 7개 항목, 각 조건 발생 시 "현재 topology 채택을 중단하고 Human Gate에서 재평가한다"는 상태 전이 명시. |

**SHOULD(권고, 미해결이어도 차단 아님) 확인**: 4개 항목(포트/노드 계층 분리, verdict 타입 강제, classifier 감사 주기 구체화, WIP/parallelism 분리) 모두 canonical 문서에 반영됨을 확인했다 — 예: `TEAM_TOPOLOGY.md:73-74` WIP/parallelism 분리, `IMPLEMENTATION_PLAN.md:90` "100개 작업 또는 30일 중 빠른 주기로 seeded-defect 표본을 감사한다"(표본 크기 자체는 미확정, 8장에 경미 관찰로 기록).

---

## 4. DESIGN_EVIDENCE_REVIEW_LUNA.md — P0/P1 항목별 PASS/FAIL

| # | P0/P1 (이전 REVISE 요구) | 판정 | 해소한 실제 문구·상태 전이 |
|---|---|---|---|
| P0-1 | 프로젝트 고유 F01 원문이 저장소에 없음 | **PASS** | `MANIFEST.md` 7개 파일 SHA-256 표 + "요청된 7개 파일이 모두 존재하며... 일치한다"(19–20행). 이 검수가 재해시로 재확인(3장). |
| P0-2 | 대안 상태 머신에 WorkNode 완료 전이 없음 | **PASS** | `EVENT_PROTOCOL.md:79-81` "running -> awaiting_verification (worker_finished)", "running -> failed\|cancelled\|stale\|outcome_unknown" — canonical 상태 머신에 완료·실패·취소 전이가 모두 존재한다. |
| P0-3 | `docs-only` 검증 깊이 표기 충돌(`none` vs 자동 VerifyNode) | **PASS** | `GRAPHORI_ARCHITECTURE.md:96` "폐기. canonical은 `docs-only -> automatic verifier`다. 사람이 검토하지 않았다는 뜻이지 검사가 없다는 뜻이 아니다." `ADR 0002` 기술 부록 동일 재확인. |
| P0-4 | portable MVP/macOS가 실행으로 검증되지 않음 | **PASS(표기 규칙으로서)** | 모든 canonical 문서가 macOS를 `deferred/unknown`으로만 표기(6장에서 grep 전건 확인). 실제 실행 검증 자체는 이번 문서 작업의 범위가 아니며 문서들도 이를 주장하지 않는다(`IMPLEMENTATION_PLAN.md:1-9,55-56`). |
| P1-1 | enum/edge 계약 혼용(`PASS/APPROVE`, `dependency/blocked-by/requires`) | **PASS** | `EVENT_PROTOCOL.md:16-37` 단일 소문자 canonical enum 선언, "UI의 `PASS`, `REVISE`, `APPROVE`는 표시용이다"(18행). `GRAPHORI_ARCHITECTURE.md:97-98` 매핑표가 이전 혼용 용어를 각각 `requires/rework_of/observes/verifies/requires_gate`로 고정. |
| P1-2 | stale/dead 복귀 전이 불완전 | **PASS** | `EVENT_PROTOCOL.md:86-87,117-119` `stale -> outcome_unknown`, `outcome_unknown -> ready`(새 attempt 명시적 생성 시만), "reconcile이... 종료 사건을 찾으면 terminal로 복구하고, 찾지 못하면 `outcome_unknown`으로 두어 중복 실행을 막는다." `DASHBOARD_CONTRACT.md:48-49` reconnect+replay 검증 후 확정 상태 복귀. |
| P1-3 | 대안 의사코드가 `edges`/`merge_node` 미정의로 닫혀있지 않음 | **PASS(상위 문서 대체로 해소)** | 해당 미완성 의사코드는 옛 `ALTERNATIVE_ARCHITECTURE_CLAUDE.md`에만 존재하며, canonical 문서(`GRAPHORI_ARCHITECTURE.md` §4, `EVENT_PROTOCOL.md` §4)가 동일 규칙을 완결된 규칙·표·전이로 대체했다. 옛 문서 자체는 수정되지 않았으나 canonical 문서가 이를 명시적으로 폐기·대체한다(`GRAPHORI_ARCHITECTURE.md:90-101` "이전 초안의 폐기와 매핑"). |
| P1-4 | JSONL 동시 append "안전" 주장과 SOL 규칙 불일치 | **PASS** | 3번 항목과 동일 근거(`EVENT_PROTOCOL.md:152-153`, `GRAPHORI_ARCHITECTURE.md:100`). |
| P1-5 | usage 없을 때 unknown 유지 계약이 필수처럼 보임 | **PASS** | `EVENT_PROTOCOL.md:156-164` `usage.status`가 `known/estimate/unknown`으로 명시, "출력 문자 수로 token을 역산하지 않는다." `ADR 0004:14` "모든 Attempt는 `usage.status = known \| estimate \| unknown`을 기록한다." |

---

## 5. 링크 무결성 검사

검수 대상 13개 canonical 문서(TEAM_TOPOLOGY, architecture 4개, decisions 4개, IMPLEMENTATION_PLAN, 두 REVISE 보고서, MANIFEST)의 모든 상대경로 마크다운 링크를 추출해 대상 파일 존재를 확인했다.

- 내부 상대경로 링크: **약 40개, 전부 OK**(대상 파일이 실제로 존재). MISSING 0건.
- 외부 URL(HTTP): `DESIGN_EVIDENCE_REVIEW_LUNA.md`의 4개(OpenAI/Claude 공식 문서 인용) — 대상 파일 존재 여부 검사에서 제외, 이전에도 출처 인용으로만 사용됨.
- `docs/evidence/doctori/MANIFEST.md`, `docs/verification/DESIGN_COMPARISON_CLAUDE.md`는 자체적으로 상대경로 링크를 포함하지 않는다(정상).

이전 REVISE에서 "F01 7개 문서가 저장소에 없다"고 지적한 링크들(`GRAPHORI_ARCHITECTURE.md`, `EVENT_PROTOCOL.md`, `PORTABILITY_CONTRACT.md`, `DASHBOARD_CONTRACT.md`가 각각 참조하는 `../evidence/doctori/verification/F01_*.md`, `../evidence/doctori/MANIFEST.md`)는 전부 해소되어 대상 파일이 존재한다.

---

## 6. macOS `deferred/unknown` 전건 확인

TEAM_TOPOLOGY, architecture 4개, decisions 4개, IMPLEMENTATION_PLAN, MANIFEST 전체에서 "macos" 문자열을 포함한 모든 줄을 추출했다(총 24줄). **예외 없이** 다음 중 하나의 형태로만 등장한다:

- `deferred`, `deferred/unknown`, `not_verified` (예: `EVENT_PROTOCOL.md:133`, `PORTABILITY_CONTRACT.md:20`, `MANIFEST.md:5`)
- macOS를 Windows `pass`와 명시적으로 대비시켜 합치지 않음을 선언하는 문장 (예: `GRAPHORI_ARCHITECTURE.md:36` "Windows `pass`가 macOS `pass`가 되지 않는다", `IMPLEMENTATION_PLAN.md:101` "macOS PASS를 먼저 만들거나 주장하지 않는다")

macOS가 `pass`, `approve`, `succeeded`로 단독 표기된 곳은 0건이다. **PASS.**

---

## 7. Original pixel art 전용 여부

`DASHBOARD_CONTRACT.md:13` "그림은 직접 만든 original pixel art만 사용하며 외부 게임 asset을 복사하지 않는다"와 `:89` "모든 sprite/background/tileset은 저장소에서 직접 제작한 original pixel art만 쓴다. 외부 게임 sprite, 상표 asset, AI 생성 결과를 원본인 것처럼 포함하지 않는다"가 canonical 규칙이다. `IMPLEMENTATION_PLAN.md:61` 6단계 acceptance도 "original pixel art만 제작"을 요구 조건으로 반복한다. license/author/source metadata 요구(`DASHBOARD_CONTRACT.md:91`)도 있어 추적 가능성이 있다. **PASS.**

---

## 8. 구현 계획이 설계보다 앞서가지 않는지

- `IMPLEMENTATION_PLAN.md`의 9단계 acceptance는 전부 이미 canonical architecture/decisions에서 확정된 규칙(단일 writer, REVISE 3회 상한, independence pool ≥2, WIP/fan-in, docs-only automatic verifier, macOS deferred)을 순서대로 실행에 옮기는 서술이며, 새로운 설계 값(임계값, 팀 수, 가격)을 스스로 확정하지 않는다.
- `IMPLEMENTATION_PLAN.md:98-102` "금지된 선행 작업" 절이 명시적으로 hash-chain/epoch fencing 전체 구현, 다중 writer append, PTY/Browser 자동화, 정확한 provider 가격 상수, macOS PASS 선언을 구현 전에 하지 않도록 금지한다 — 이는 `DESIGN_COMPARISON_CLAUDE.md` 10장의 DEFER 목록(해시체인, 가격 상수, 정확한 팀 상한, freshness 임계값)과 정확히 대응한다.
- `docs/PROCESS.md:112-134` "canonical 문서 단계 갱신"이 진행률을 `0/9`로 명시하고 "문서 작성 완료가 구현 acceptance를 대신하지 않는다"(`IMPLEMENTATION_PLAN.md:117`)고 스스로 선을 긋는다.

**결론: PASS. 구현 계획은 설계를 앞서가지 않는다.**

---

## 9. MANIFEST.md 해시 재검증

이 검수 세션이 7개 evidence 파일의 SHA-256을 원본(`doctori` 저장소)과 복사본(`graphori/docs/evidence/doctori`) 양쪽에서 직접 재계산했다.

| 파일 | 재계산 결과 |
|---|---|
| `WORK_DURATION_ANALYSIS.md` | 원본=복사본=MANIFEST 기록값, 일치 |
| `PROCESS.md` | 일치 |
| `decisions/0003-two-model-mutual-oversight.md` | 일치 |
| `decisions/0005-orchestrator-delegation-only.md` | 일치 |
| `verification/F01_FINAL_CROSS_MODEL_ACCEPTANCE.md` | 일치 |
| `verification/F01_WINDOWS_FINAL_APPROVAL.md` | 일치 |
| `verification/F01_JUNCTION_TEAM2_REAUDIT.md` | 일치 |

`EVENT_PROTOCOL.md:179`가 인용한 "`events 23줄`, `replay_mismatch=0`" 수치도 `F01_WINDOWS_FINAL_APPROVAL.md`(32,38,42행)에서 직접 확인되어 인용이 정확하다. **PASS.**

---

## 10. 경미 관찰 (차단 아님, REVISE 근거 아님)

1. **architecture 문서 개수 표기**: `docs/architecture/` 폴더에는 물리 파일이 4개(`GRAPHORI_ARCHITECTURE`, `EVENT_PROTOCOL`, `DASHBOARD_CONTRACT`, `PORTABILITY_CONTRACT`)뿐이며, 5번째는 저장소 루트의 `TEAM_TOPOLOGY.md`가 architecture 계열 문서로 상호 링크되어 채운다. 폴더 구조상 자연스러운 배치이며 내용상 문제는 없다.
2. **옛 설계 초안(SOL/CLAUDE안/ROUTING)의 헤더가 "canonical" 승계를 스스로 표시하지 않음**: `docs/design/*.md` 3개 파일은 여전히 "비교를 위한 설계 초안"/"설계 전용 문서"라는 원래 헤더를 갖고 있고, 새 canonical 문서를 향한 역참조가 파일 자체에는 없다. canonical 문서들은 이 옛 문서들을 "폐기·매핑"으로 명확히 대체했으므로(`GRAPHORI_ARCHITECTURE.md:90-101`) 내용 충돌은 없으나, 옛 문서를 단독으로 읽는 독자가 최신 상태를 오인할 여지는 남는다. 구현/수정 금지 지침에 따라 이번 검수에서는 손대지 않았다.
3. **risk classifier 감사 표본 크기 미확정**: 감사 주기(100개 작업 또는 30일)는 확정됐으나 표본 크기(몇 건을 뽑는지)는 아직 미정이다. 이는 이전 REVISE의 SHOULD 항목(M6)이었고 MUST가 아니므로 APPROVE를 막지 않는다.

---

## 11. 최종 판정

**APPROVE.**

이전 두 REVISE 보고서가 제기한 MUST 10개 + P0 4개 + P1 5개, 총 19개 항목 전부가 canonical 문서 안에서 실제 문구·표·상태 전이로 확인되었고 FAIL은 0건이다. 링크 무결성, macOS `deferred/unknown` 표기, original pixel art 전용 규칙, 구현 계획의 선행성 없음, evidence manifest의 해시 정합성도 모두 PASS다. 10장의 경미 관찰 2건은 구현 착수를 막을 이유가 되지 않는다.
