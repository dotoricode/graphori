# 설계 비교 검수: TEAM_GRAPH_ANALYSIS / PORTABILITY_AND_DEPENDENCY / LIVE_GAME_DASHBOARD → SOL안 / Claude 대안 / Fast 모드

검수일: 2026-08-09 (Asia/Seoul)
검수자: Claude (독립 검수 — 설계 문서 작성자와 분리된 세션)
범위: 아래 6개 문서의 근거 추적 비교 검수. **구현하지 않았다. 코드를 한 줄도 만들지 않았다.**

- (연구) `docs/research/TEAM_GRAPH_ANALYSIS.md` — 이하 **R1**
- (연구) `docs/research/PORTABILITY_AND_DEPENDENCY.md` — 이하 **R2**
- (연구) `docs/research/LIVE_GAME_DASHBOARD.md` — 이하 **R3**
- (설계) `docs/design/PROPOSED_ARCHITECTURE_SOL.md` — 이하 **SOL**
- (설계) `docs/design/ALTERNATIVE_ARCHITECTURE_CLAUDE.md` — 이하 **CLAUDE안**
- (설계) `docs/design/MODEL_ROUTING_AND_FAST_MODE.md` — 이하 **ROUTING**

인용은 `문서약어:줄번호` 형식으로 표기했다(예: `SOL:428`). 모든 인용 줄번호는 이 검수 세션이 각 파일을 직접 읽은 결과이며, 재현하려면 해당 파일의 그 줄을 열면 된다.

---

## 0. 최종 판정

> **REVISE**
> (APPROVE 아님)

이유는 4장 이하에 근거와 함께 있다. 짧게 말하면: 두 설계안(SOL, CLAUDE안)은 세 연구 문서의 핵심 원칙(Orca는 어댑터, 검증 독립성, 거짓 progress 금지, OS별 판정 분리)을 **일관되게** 반영했다는 점에서 합격점이지만, (1) 이 설계 전체의 empirical 근거인 F01 결함 기록이 **이 저장소 안에서 추적 불가능**하고, (2) 두 설계안 사이에 **위험도 분류 체계가 세 갈래로 갈라져 있으며 통합되지 않았고**, (3) 동적 그래프가 없애려는 SPOF(단일 승인권자, 단일 감사 인력)가 **이름만 바뀐 채 재발할 위험을 어느 설계도 구체적으로 막지 않았고**, (4) 두 설계안이 서로 다른 곳에서 서로 다른 강점을 보이는데 최종안이 어느 것을 계승할지 결정되지 않았다. 구현 이전에 이 4가지를 명시적으로 해소해야 한다.

---

## 1. 12살도 이해하는 설명

미션 보드(Doctori)를 새로 그리는 설계도가 세 장 왔어요. 그런데 설계도를 그리기 전에 먼저 세 개의 "왜 이렇게 그려야 하나" 조사 보고서가 있었어요. 이 검수는 "설계도 세 장이 조사 보고서 세 장이 말한 걸 제대로 따랐는지" 그리고 "설계도 두 장이 서로 싸우는 부분은 없는지"를 확인하는 일이에요.

확인해보니 좋은 소식과 나쁜 소식이 있어요.

**좋은 소식**: 두 설계도(SOL, Claude) 모두 조사 보고서가 강조한 중요한 규칙들 — "클럽하우스(Orca)가 없어도 공책(이벤트 기록)만으로 돌아가야 한다", "숨쉬기(살아있음)와 걸음(진짜 진행)을 헷갈리면 안 된다", "자기가 만든 걸 자기가 검사하면 안 된다", "Windows에서 통과했다고 macOS도 통과한 게 아니다" — 를 잘 따랐어요. 이 부분은 통과예요.

**나쁜 소식**: 세 가지 문제가 있어요.

1. **미션 보드가 옛날에 실제로 도둑을 세 번 잡았다는 이야기의 증거 쪽지들이 이 학교(저장소) 어디에도 없어요.** 조사 보고서(R1)는 "옛날에 F01이라는 미션에서 도둑을 세 번 실제로 잡았다"고 말하면서 그 증거가 적힌 쪽지 7장의 이름을 대요. 그런데 이 학교 서랍 어디를 봐도 그 쪽지가 없어요. 그래서 "팀을 4개로 줄여도 안전하다"는 주장이 진짜인지 아직 확인할 수 없어요.
2. **"이 미션이 얼마나 위험한지" 재는 자가 세 개나 있는데, 서로 눈금이 달라요.** SOL 설계도의 자, Claude 설계도의 자, 그리고 Fast 모드 설계도의 자가 서로 다른 이름과 다른 계산법을 써요. 같은 미션을 셋에 넣으면 서로 다른 답이 나올 수 있어요. 하나로 합쳐야 해요.
3. **"검사하는 사람이 딱 한 명뿐이면 어떡하지?"라는 질문에 아직 아무도 답을 안 했어요.** 원래 문제는 "검사반장님 한 명이 아프면 아무도 도장을 못 찍는다"는 거였는데, 새 설계도 두 장 다 "능력 있는 사람 아무나"라고만 하고 "최소 몇 명은 항상 있어야 하는지", "그 사람이 없으면 누가 대신하는지"를 안 정했어요.

그래서 점수는 "잘했어요, 그런데 다시 해와요(REVISE)"예요. 큰 틀은 맞는데, 실제로 만들기 전에 이 세 가지를 먼저 정해야 안전해요.

---

## 2. 문서 지도 (요약, 근거 추적용)

| 문서 | 한 줄 요약 | 핵심 주장 |
|---|---|---|
| R1 | F01 고정 7역할 파이프라인의 그래프 분석 | 운영 그래프는 cycle을 가짐(`R1:204-206`), WIP·비용 미측정(`R1:264-286`), SPOF 5종(`R1:329-337`), 결론은 "고정/동적 중 하나를 지금 고를 근거 부족"(`R1:28-33`) |
| R2 | Orca 없이 돌아가는 이식성 조사 | 포트-앤-어댑터, JSONL 이벤트 로그, Orca는 선택적 미러(`R2:15,58`), Windows/macOS 프로세스·PTY 차이(`R2:196-219`) |
| R3 | 살아있는 대시보드 조사 | liveness/progress/result 3신호 분리, 거짓 progress 금지(`R3:20-22,209-244`) |
| SOL | Portable Core 아키텍처 | 8개 포트, versioned WorkGraph, 위험도별 역할 생성, 이벤트 저널 단일 writer lease(`SOL:426-436`), 팀 수 "상시 0개 + 최대 4개"는 명시적 초안(`SOL:61-74,792-811`) |
| CLAUDE안 | 위험도가 그래프를 만드는 대안 | 4노드(Work/Verify/Observe/Decision) + 5엣지, risk_class 7종, 세 신호(liveness/progress/verdict), **반대 논거 6개**·**실패 조건 7개**를 문서 안에 직접 명시(`CLAUDE안:497-578`) |
| ROUTING | 모델 라우팅/Fast 모드 정책 | Luna 우선·Sol 제한·Sonnet 우선, `routing_pressure` 점수로 Fast/Standard/Critical 결정(`ROUTING:74-99`), 연구 문서만 인용하고 SOL/CLAUDE안은 인용하지 않음(`ROUTING:31-39`) |

---

## 3. 근거 추적 결과 — 가장 심각한 단일 문제

**R1의 모든 수치 근거(고정 결함 3건, checkpoint 18개, 독립 감사 20단계, Windows APPROVE)는 다음 7개 문서를 인용한다(`R1:39-45`):**

```
WORK_DURATION_ANALYSIS.md
PROCESS.md
decisions/0003-two-model-mutual-oversight.md
decisions/0005-orchestrator-delegation-only.md
verification/F01_FINAL_CROSS_MODEL_ACCEPTANCE.md
verification/F01_WINDOWS_FINAL_APPROVAL.md
verification/F01_JUNCTION_TEAM2_REAUDIT.md
```

이 검수 세션이 저장소 전체를 검색한 결과, **위 7개 파일 중 어느 것도 이 저장소에 존재하지 않는다.** 이 저장소는 커밋이 하나도 없는 새 저장소이고(`git log` 결과 "does not have any commits yet"), 파일 시스템에도 `docs/design`과 `docs/research` 6개 파일 외에는 아무것도 없다.

이것이 뜻하는 바:

- R1이 "동적 그래프를 실험할 가치가 있다"고 조심스럽게 내린 결론(`R1:28-33`)은 **이 저장소 기준으로는 검증 불가능한 1차 근거 위에 서 있다.**
- SOL과 CLAUDE안은 둘 다 이 감사받지 못한 결함 기록(고정 ELF 경로, AST 절대경로 15,533건, junction 탈출)을 팀 수 축소(7 → 최대 4)의 **핵심 정당화 근거**로 재인용한다(`SOL:71-72`, `CLAUDE안:16,168-169,450-454`). 근거 문서가 없으면 이 정당화는 "그럴듯한 이야기"이지 "확인된 사실"이 아니다.
- R3은 이 문제를 스스로 인정한다: "현재 작업 저장소에는 Doctori verification 문서가 없어 원문을 직접 대조할 수 없었다"(`R3:9-10`). 즉 R3은 자기 문서 안에서 이미 이 한계를 밝혔는데, R1·SOL·CLAUDE안은 같은 한계를 명시적으로 밝히지 않고 F01 수치를 확정된 사실처럼 계속 인용한다.

**판정**: 이것은 세 설계 문서 사이의 "충돌"이 아니라 그보다 상위의 문제 — **근거 사슬의 첫 고리가 이 저장소 안에서 끊겨 있다.** 다음 단계로 넘어가기 전에 반드시:
1. 7개 F01 문서가 실제로 어딘가(다른 저장소, 이전 세션)에 존재하는지 확인하고 이 저장소로 가져오거나,
2. 존재하지 않는다면 R1·SOL·CLAUDE안의 "3개 결함", "18 checkpoint", "20단계" 수치를 "미검증 주장(unverified claim)"으로 재표기해야 한다.

---

## 4. 같은 결론 (세 문서가 일치하는 지점)

이 항목들은 R1/R2/R3과 SOL/CLAUDE안이 서로 다른 표현으로도 같은 결론에 도달했다는 뜻이며, 재작업 대상이 아니다.

| # | 결론 | 근거 |
|---|---|---|
| 1 | Orca는 core의 소유자가 아니라 선택적 미러 어댑터다 | `R2:34,58`, `SOL:96-100,724`(0개 import 요구), `CLAUDE안:302-327`("orca 바이너리가 전혀 등장하지 않습니다") |
| 2 | 영구 고정 팀 대신 위험도 기반으로 역할을 그때그때 만든다 | `R1:32-33`("동적 그래프를 실험할 가치"), `SOL:61-74`, `CLAUDE안:10-28` |
| 3 | 작성자는 자기 결과의 독립 검증자가 될 수 없다 | `R1:65-67`, `SOL:344-352`, `CLAUDE안:121-124`, `ROUTING:290-293` |
| 4 | liveness(생존)·progress(진행)·result/verdict(판정)는 절대 하나로 합치지 않는다 | `R3:123-132,209-236`, `SOL:559-568`, `CLAUDE안:277-300` |
| 5 | 근거(basis) 없는 progress 숫자는 움직이지 않는다 | `R3:22,237-244`, `SOL:562`, `CLAUDE안:293-295` |
| 6 | Windows PASS는 macOS PASS가 아니다. OS별 판정을 분리 보관한다 | `R1:333-337`(SPOF 표의 macOS 행), `SOL:634`(`PlatformVerdict`), `CLAUDE안:237-240`(`blocked-by` T8) |
| 7 | REVISE는 실패가 아니라 유용한 신호다. `REVISE=0`을 목표로 삼지 않는다 | `R1:414-416`, `SOL:93`(비목표) |
| 8 | 사용자 결정 타임아웃은 자동 승인이 아니다 | `R3:326,332-334`, `SOL:497`("timeout 기본값은 자동 승인 아닌 expired") |
| 9 | 이 6개 문서 전부 "설계 전용, 구현 아님"을 명시한다 | 각 문서 서두 |

---

## 5. 충돌 (문서 간 실제로 어긋나는 지점)

### C1. JSONL 다중 프로세스 동시 append가 "안전하다"는 R2의 주장은 근거가 없고, SOL은 이를 사실상 뒤집는다

- R2: "이 방식이 좋은 이유: 한 줄씩 이어 붙이기만 하면 되니까 **여러 프로그램이 동시에 써도 안전하고**(각자 한 줄씩 append)... (근거: 부록 C)"(`R2:153`)
- 그런데 R2 부록 C.1(`R2:317-321`)이 실제로 말하는 것은 "각 줄이 독립적인 JSON 문서라 스트리밍·부분 읽기·파일 분할이 쉽다"는 **포맷 설명일 뿐, 여러 프로세스의 동시 쓰기 원자성은 다루지 않는다.** 즉 `R2:153`의 "(근거: 부록 C)" 표기는 **인용이 자기 주장을 실제로 뒷받침하지 못하는 오표기**다. Windows와 POSIX의 append 원자성 보장 범위가 다르다는 사실은 R2 자신의 7장·부록 D가 이미 경고하는 내용과도 모순된다.
- SOL은 이 위험을 정확히 인지하고 정반대 규칙을 세운다: "여러 worker가 하나의 파일에 직접 동시에 append하지 않는다. 그 방식의 atomicity와 잠금 의미가 Windows와 macOS에서 같다고 보장할 수 없기 때문이다... canonical journal은 lease를 가진 단일 writer만 쓴다. producer는... `inbox/tmp`에 쓴 뒤 `inbox/ready`로 rename한다."(`SOL:428-431`)
- CLAUDE안은 이 문제 자체를 다루지 않는다. `EventLog: append(event)` 포트(`CLAUDE안:308`)는 동시성 의미를 명시하지 않으며, R2의 낙관적 가정을 그대로 물려받을 위험이 있다.

**판정**: SOL이 맞다. **MUST**: 최종 설계는 R2의 "안전하다" 문장을 폐기하고 SOL의 단일 writer lease + `tmp/ready` rename 패턴(또는 동등한 방식)을 채택해야 한다. CLAUDE안을 채택 후보로 쓰려면 이 규칙을 명시적으로 이식해야 한다.

### C2. 위험도를 재는 자가 세 개이고, 서로 통합되지 않았다

| 문서 | 위험 분류 체계 | 값의 모양 |
|---|---|---|
| SOL | `RiskLevel = low\|medium\|high\|critical` + 별도 `RiskTag` 집합(security_boundary, privacy, reproducibility, cross_platform, destructive, external_side_effect, cost, ambiguity, visual_only) | 등급(순서형) × 태그(집합형), 서로 직교 |
| CLAUDE안 | `risk_class = docs-only \| low-risk-change \| feature-change \| security-boundary \| reproducibility \| cross-model \| external-blocked` | 하나의 flat enum — "변경 규모"(docs-only, feature-change)와 "위험 영역"(security-boundary, reproducibility)이 같은 값 안에 섞여 있음 |
| ROUTING | `risk/uncertainty/scope/synthesis/parallelism` 각 0~3 점수 → `routing_pressure` 가중합 → Fast/Standard/Critical 3단계 | 연속 점수 → 3단계 |

(근거: `SOL:178-181`, `CLAUDE안:341,378-403`, `ROUTING:63-99`)

세 체계는 값의 모양도, 단계 수도, 무엇을 축으로 삼는지도 다르다. 예를 들어 "보안 경계를 건드리지만 한 파일만 고치는 문서형 변경"은 CLAUDE안의 flat enum에서는 `docs-only`와 `security-boundary` 중 어디로 가야 하는지 규칙에 없고(둘 다 해당하는데 enum은 하나만 고를 수 있음), SOL의 직교 모델에서는 `level=high`+`tag=security_boundary`로 자연스럽게 표현된다. 반대로 ROUTING의 5축 점수는 SOL/CLAUDE안의 값과 이름조차 겹치지 않아, 같은 작업이 "SOL 기준 high"이면서 "ROUTING 기준 Standard"로 서로 다르게 판정될 수 있는데 이를 맞춰줄 매핑 함수가 어디에도 없다.

더 근본적으로, ROUTING(`ROUTING:31-39`)은 R1/R2/R3 세 연구 문서만 인용하고 **SOL과 CLAUDE안을 한 번도 인용하지 않는다.** 세 설계 문서가 서로 다른 시점/다른 저자로 독립 작성되었다는 정황(`CLAUDE안:4`: "다른 설계자의 초안을 보지 않고 작성")과 맞물려, 위험 분류가 **세 번 따로 발명**되었다.

**판정**: **MUST**. 구현에 들어가기 전에 하나의 위험 분류 체계(또는 세 체계 사이의 명시적이고 테스트 가능한 매핑 함수)를 정의해야 한다. 그렇지 않으면 "검증 깊이"(SOL/CLAUDE안이 결정)와 "모델/비용"(ROUTING이 결정)이 같은 작업에 대해 서로 다른 심각도 인식을 가진 채로 운영되어, 위험한 작업이 비용 정책 쪽에서는 Fast로 새어나갈 수 있다.

### C3. CLAUDE안의 rework 다이어그램은 SOL이 명시적으로 금지한 "실행 그래프 cycle"을 시각적으로 만든다

- SOL은 명시적이다: "한 graph version 안에서 scheduler가 따르는 edge는 반드시 acyclic이다... `REVISE`가 나오면 새 Task revision 또는 새 fix Task를 만들고... 각 확정 graph version의 scheduling edge는 DAG다."(`SOL:283,294`)
- CLAUDE안의 노드 데이터 계약에는 `rework_of = node_id | null` 필드가 있어(`CLAUDE안:350`) 텍스트상으로는 "새 노드를 만들고 과거를 가리킨다"는 SOL과 같은 의도로 읽을 수 있다. 그런데 실제 Mermaid 다이어그램은 이를 다르게 그린다:

```
W["WorkNode 오타/문서 수정"] -->|dependency| V["VerifyNode ..."]
V -->|rework: REVISE, changed_scope=diff| W
```
(`CLAUDE안:178-182`, 위험한 일 토폴로지도 동일 패턴: `CLAUDE안:202-213`)

여기서 `V -->|rework| W`는 **같은 노드 라벨 `W`로 되돌아가는 화살표**이며, 다이어그램만 보면 실행 그래프 자체에 cycle이 있는 것처럼 읽힌다. `rework_of` 필드가 "사실은 새 노드"라는 것을 명시하는 문장이 다이어그램 옆에 없다. R1이 이미 "사람과 검증의 운영 그래프는 cycle을 가진다"(`R1:206`)고 관찰했고, SOL은 이를 "확정 graph version은 DAG, 운영 이력만 cycle처럼 보인다"로 정확히 해소했는데, CLAUDE안은 같은 해소를 텍스트(노드 계약)에서는 하고 다이어그램(사람이 실제로 읽는 부분)에서는 하지 않았다.

**판정**: **SHOULD**. CLAUDE안을 최종안에 포함하려면 모든 rework 다이어그램 옆에 "이 화살표는 새 revision 노드를 가리키며 같은 node_id를 재실행하지 않는다"는 문장을 SOL 수준으로 명시해야 한다. 스케줄러 구현자가 다이어그램만 보고 "같은 노드를 재실행"으로 구현하면 SOL이 막으려던 정확히 그 문제(무한 루프 가능한 실행 cycle)가 재발한다.

---

## 6. 빠진 것 (두 설계안 모두 또는 한쪽만 놓친 것)

| # | 빠진 것 | SOL | CLAUDE안 | 왜 중요한가 |
|---|---|---|---|---|
| M1 | 독립 감사자/게이트 승인권자의 **최소 인원수**와 **대체(backup) 정책** | 없음 | 없음 (스스로 열린 질문으로 인정: `CLAUDE안:591-593` "gate_authority를 누가/어떻게 정의하고 교체하는가... SPOF 문제를 어떻게 완화할 것인가") | R1의 원래 SPOF 지적(`R1:333-337`, R-V1/R-V2)이 "능력+독립성 조건을 만족하는 아무나"로만 재정의되었을 뿐, 실제로 그 풀의 크기가 1명이면 승인 대기가 무한정 걸리거나 독립성 조건을 어기고 승인해야 하는 상황이 그대로 재발한다 |
| M2 | 같은 능력을 요구하는 고위험 작업 여러 개가 **동시에** 몰릴 때의 대기열/우선순위 정책 | `SOL:330`("같은 capability의 독립 Task는... 한 역할 인스턴스가 순차 처리")까지만 언급, FIFO인지 위험도 가중인지 불명 | 언급 없음 | fan-in 병목이 "고정 R-V2 한 명"에서 "제한된 capability pool"로 자리만 옮길 수 있다 |
| M3 | 검증용 REVISE 루프의 **반복 상한과 자동 에스컬레이션** | 없음(공격/실행 실패의 retry 상한은 있으나 `SOL:660` 이는 attempt crash 재시도이지 검증 REVISE 루프가 아님) | 있음: `reworkCountSince(work) > 2` 시 DecisionNode 소환(`CLAUDE안:385-386`) | SOL 단독 채택 시 verification 루프가 상한 없이 반복될 위험을 CLAUDE안만큼 명시적으로 막지 못함 |
| M4 | OS별 프로세스 종료(정상 종료 → grace → 강제 종료, Windows Job Object) 전담 포트 | 있음: `ProcessSupervisor` 포트(`SOL:140`), 14.2/14.3에서 OS별 규칙 구체화(`SOL:611-624`) | 없음: 4개 포트(EventLog/AgentRunner/Notifier/EvidenceStore, `CLAUDE안:308-312`)에 프로세스 감독이 빠져 있고, 이 위험을 스스로 반대 논거 4번에서 인정만 함(`CLAUDE안:519-526`) | R2가 부록 D 전체를 할애해 SIGTERM/TerminateProcess/Job Object 차이를 경고했는데(`R2:196-219,353-367`) CLAUDE안 단독 채택 시 이 위험이 설계 단계에서 다뤄지지 않음 |
| M5 | ROUTING의 리뷰어(`reviewer_model_id`)가 SOL/CLAUDE안의 독립성 제약(`notSameAttemptAs`/`must_differ_from`)을 반드시 만족하도록 하는 상호 참조 | 없음 | 없음 | Standard 모드의 "targeted review 1회"(`ROUTING:108`)가 같은 attempt/세션에서 수행돼도 ROUTING 문서만 보면 막을 방법이 없다. C2(위험도 3분열)와 함께 발생하면 검증 독립성이 조용히 깨질 수 있다 |
| M6 | risk classifier(`classify()`) 자체를 주기적으로 감사하는 **구체적 절차**(주기, 표본 크기) | 없음 | 실패 조건으로만 언급(`CLAUDE안:560-564`: "정기적으로 fresh-full 무작위 샘플 재검증을 하지 않는다면 이 설계를 도입하면 안 됩니다") — 감시 대상은 정의했지만 절차 자체는 미정 | classify()가 틀리면 전체 위험 완화가 무의미해지는데, "감사해야 한다"만 있고 "언제 몇 개를" 표본추출할지는 어디에도 없음 |
| M7 | "WIP(동시 활성 역할 수)"와 "parallelism(한 작업 안의 병렬 갈래 수)"의 명확한 구분 | `active_wip`(시스템 전역, `SOL:706`)만 사용 | 없음 | ROUTING의 `parallelism` 점수(0~3, `ROUTING:69`)는 한 작업 내부의 독립 갈래 수를 재는 축인데, SOL의 WIP cap=4(`SOL:734`)는 시스템 전체에서 동시에 살아있는 역할 인스턴스 수다. 두 "동시성" 개념이 이름이 겹치면서도(병렬/WIP) 서로 다른 스코프를 재고 있어 구현자가 하나의 숫자로 착각하고 합칠 위험이 있다 |

---

## 7. 과도한 것 (지금 단계에서 만들 필요가 없는 것)

1. **SOL의 이벤트 저널 해시 체인 + coordinator epoch/lease 완전 구현**(`SOL:390-408, 638-644`)은 파일럿(§19 비교 실험, `SOL:792-803`) 전에 필요한 최소 기능이 아니다. R1 스스로 "구현을 지금 하자는 뜻이 아니라 다음 설계의 입력·출력 형식을 미리 합의하자는 뜻"(`R1:503-504`)이라고 밝혔는데, SOL의 Acceptance 18.3(`SOL:736-742`, 동시 producer, 변조 탐지, crash 복구)은 이미 상당히 분산시스템급 요구사항이다. 위험도 기반 역할 생성이라는 **핵심 가설조차 아직 seeded-defect 실험으로 검증되지 않은 시점**(`SOL:758`)에 tamper-evident 해시 체인까지 먼저 짓는 것은 순서가 바뀐 것이다. → **DEFER**: 파일럿에는 append+replay+idempotency만 있는 최소 저널로 충분하다.
2. CLAUDE안의 `EventEnvelope`에 준하는 정교함이 SOL 대비 부족한 것은 오히려 적절하다 — 이 항목은 "빠진 것"이 아니라 SOL의 과잉을 상대적으로 드러내는 참고점으로만 기록한다.
3. ROUTING §6.3의 구체적 달러 가격표(`ROUTING:208-228`)는 문서 스스로 "정책 상수가 아니다... 가격표는 스냅샷일 뿐"이라고 정확히 선을 그었다(`ROUTING:211-213`). 과도하지 않고 올바르게 처리된 사례로 기록한다(참고용, 재작업 불필요).

---

## 8. 실패 조건 비교 — SOL에는 없고 CLAUDE안에는 있다

CLAUDE안은 "5. 실패 조건 — 이 설계를 되돌리거나 멈춰야 하는 신호"라는 전용 섹션을 갖고 있다(`CLAUDE안:541-578`, 7개 항목: false negative 발생, 독립성 위반 감지, 계측 데이터 없는 배포, classifier 정확도 미측정, rework 무한 루프, 어댑터 간 결과 불일치, 사용자가 3신호 화면을 무시). SOL에는 이에 대응하는 전용 섹션이 없다 — SOL의 §18 Acceptance criteria(`SOL:718-790`)는 "설계가 완료됐다고 부를 수 있는 조건"이지, "채택 후 운영 중 이 신호가 보이면 7역할 기준선으로 되돌려야 한다"는 롤백 트리거가 아니다.

**판정**: **MUST**. 최종안이 SOL의 구조를 계승하더라도, CLAUDE안 §5 수준의 명시적 롤백/실패 트리거 목록을 반드시 채택해야 한다. R1이 이미 "근거가 부족하다"(`R1:28`)고 경고했고 3장에서 확인했듯 F01 근거 자체도 이 저장소에서 추적 불가능한 상태이므로, 파일럿 도중 "이 설계가 틀렸다"는 신호를 조기에 포착할 명시적 조건 없이 그대로 굴리는 것은 특히 위험하다.

---

## 9. 공격적 검증 8개 항목 (요청된 체크리스트)

| # | 항목 | SOL | CLAUDE안 | 종합 판정 |
|---|---|---|---|---|
| 1 | **그래프 cycle** | 명시적으로 acyclic 강제, rework는 history edge로 분리(`SOL:283,294`) — **PASS** | 노드 계약(`rework_of`)은 새 노드 의도이나 다이어그램이 같은 node로 회귀해 시각적 cycle 생성(`CLAUDE안:178-182`) — **REVISE 필요 (C3)** | 최종안은 SOL의 명시적 언어를 채택해야 함 |
| 2 | **WIP** | `active_wip`/`ready_wip` 지표 + WIP cap=4 명시(`SOL:706,734`) — **PASS(초안 수준)** | 시스템 전역 WIP 개념 없음, 작업 내부 fan-out만 규정 — **부분 결여** | M7 참고. WIP와 parallelism 스코프 구분 필요 |
| 3 | **fan-in 병목** | fan-in 판정 규칙은 있으나(`SOL:309`) capability pool 대기열/우선순위 정책 없음 — **부분 결여** | fan-in 구조(V1,V2→D)는 명시했으나(`CLAUDE안:202-213`) 대기열 정책 없음 — **부분 결여** | M2. 두 설계 모두 미해결 — **MUST 보완** |
| 4 | **거짓 progress** | 3신호 분리 + one-shot motion 규칙 명시(`SOL:559-568`) — **PASS** | 3신호(liveness/progress/verdict) 분리, verdict를 Verify/Decision 전용으로 타입 수준에서 강제(`CLAUDE안:277-300`) — **PASS (SOL보다 구조적으로 한 단계 더 강함)** | 둘 다 R3 원칙을 충실히 구현. CLAUDE안의 타입 강제를 SHOULD로 채택 권고 |
| 5 | **Orca 없는 실행** | 8포트, 0 Orca import Acceptance(`SOL:724`) — **PASS** | 4포트, "orca 바이너리가 전혀 등장하지 않습니다"(`CLAUDE안:319`) — **PASS, 단 포트가 R2가 지적한 위험 전부를 덮지 못함(M4)** | SOL 포트 목록이 더 완전함 |
| 6 | **Windows/macOS** | OS별 규칙 구체(§14.2/14.3), acceptance fixture 명시(junction, symlink, case collision, `SOL:611-624,778`) — **PASS** | 반대 논거에서 위험만 인정, 구체적 해법·fixture 없음, 스스로 "열린 질문"으로 남김(`CLAUDE안:519-526,597-598`) — **미해결, 자기 인정** | **MUST**: 어떤 그래프 모델을 채택하든 SOL §14/§18.8을 그대로 가져와야 함 |
| 7 | **사용자 gate** | 트리거 조건, 필수 필드, 상태기계, timeout≠자동승인 모두 명시(`SOL:499-519,490-497`) — **PASS**, 단 gate_authority 교체/백업 정책은 없음(M1) | DecisionNode로 개념은 동일하게 존재(`CLAUDE안:129-132`)하나 상태기계·타임아웃 규칙이 SOL만큼 세밀하지 않고, gate_authority 교체 문제를 스스로 미해결로 남김(`CLAUDE안:591-593`) | 두 설계 모두 M1 미해결 — **MUST 보완** |
| 8 | **검증 독립성** | `independence` 4개 boolean 필드 + 6개 불변식(`SOL:344-352`) — **PASS** | `independence_constraint{must_differ_from, must_differ_dim}` 로 표현력은 동등, 노드 타입 자체로 자기검증을 구조적으로 차단(`CLAUDE안:341,121-124`) — **PASS** | 둘 다 원칙은 통과. ROUTING과의 배선 누락(M5)이 실제 구현에서 이 원칙을 깰 수 있는 유일한 구멍 |

---

## 10. 최종 구조가 선택해야 할 항목: MUST / SHOULD / DEFER

### MUST (구현 착수 전 반드시 해소)

1. **F01 근거 추적 복구 또는 강등**: 7개 인용 문서(`R1:39-45`)를 저장소에 확보하거나, 확보 못하면 R1/SOL/CLAUDE안의 F01 수치(결함 3건, checkpoint 18개 등)를 "미검증 주장"으로 재표기한다. (3장)
2. **이벤트 저널 동시쓰기 규칙**: R2의 "다중 프로세스 동시 append는 안전하다"는 문장을 폐기하고, SOL의 단일 writer lease + `inbox/tmp→ready` rename 패턴(`SOL:428-436`)을 최종안의 유일한 규칙으로 채택한다. (C1)
3. **위험 분류 체계 통합**: SOL의 `RiskLevel×RiskTag`, CLAUDE안의 `risk_class`, ROUTING의 5축 점수 중 하나를 골라 통일하거나, 세 값 사이의 명시적 변환 함수를 정의하고 세 문서 모두 이를 상호 참조하도록 갱신한다. (C2)
4. **rework 다이어그램의 cycle 표기 수정**: CLAUDE안의 모든 rework 화살표 옆에 "새 revision 노드"임을 SOL 수준으로 명시한다. (C3)
5. **독립 감사자/게이트 승인권자 최소 인원 및 대체 정책**: 최소 풀 크기(예: ≥2)와 부재 시 대체·에스컬레이션 규칙을 정의한다. 정의 없이는 R1이 지적한 SPOF가 이름만 바뀐 채 재발한다. (M1, 체크리스트 7)
6. **fan-in 대기열/우선순위 정책**: 동일 capability의 고위험 작업이 몰릴 때 처리 순서(FIFO vs 위험 가중)를 정의한다. (M2, 체크리스트 3)
7. **검증 REVISE 루프 상한**: SOL에 CLAUDE안의 `reworkCountSince > 2 → DecisionNode` 규칙(또는 동등 규칙)을 이식한다. (M3)
8. **OS 프로세스 감독 포트**: 최종안이 CLAUDE안의 4포트만 쓰기로 하더라도, SOL의 `ProcessSupervisor`에 준하는 포트와 §14.2/14.3, §18.8 fixture를 반드시 흡수한다. (M4, 체크리스트 6)
9. **ROUTING과 독립성 제약의 상호 참조**: `reviewer_model_id` 선택이 SOL/CLAUDE안의 `independence_constraint`를 항상 만족하도록 ROUTING 문서에 명시적 규칙을 추가한다. (M5)
10. **명시적 롤백/실패 트리거 채택**: 최종안이 SOL 구조를 계승하더라도 CLAUDE안 §5(`CLAUDE안:541-578`) 수준의 실패 조건 목록을 반드시 포함한다. (8장)

### SHOULD (채택을 권고하되, 없어도 설계가 당장 깨지지는 않음)

1. SOL의 8포트 목록을 구현 계약으로, CLAUDE안의 4노드 모델을 사람이 읽는 설명/문서 층위로 함께 쓴다(둘은 상호 배타적이지 않다 — CLAUDE안이 UX/서술에 더 적합, SOL이 데이터 계약에 더 적합).
2. CLAUDE안의 "verdict는 Verify/Decision 노드만 가질 수 있다"는 **타입 수준** 강제(`CLAUDE안:296-298`)를 SOL의 정책 목록식 금지(`SOL:373`)보다 우선 채택한다 — 타입 강제가 정책 문서보다 어기기 어렵다.
3. risk classifier 자체의 감사 주기(예: N건마다 또는 월 1회 seeded-defect 표본 재검증)를 CLAUDE안의 "정기적으로"라는 표현보다 구체적인 절차로 못박는다. (M6)
4. WIP(시스템 전역 동시 역할 수)와 parallelism(작업 내부 병렬 갈래 수)을 서로 다른 이름·다른 필드로 명확히 분리한다. (M7)

### DEFER (지금 결정하지 않는 것이 옳음 — 문서들도 스스로 유보했음)

1. 정확한 팀 상한 숫자(4 vs 3 vs 5) — SOL 스스로 "명시적 초안"이라 밝힘(`SOL:74,792-803`). seeded-defect 비교 실험 전에는 결정하지 않는다.
2. 정확한 freshness 임계값(2H/4H + jitter) — R3·SOL 모두 "표준이 아니라 설계 후보"라 명시(`R3:141-144`). 실제 트래픽 데이터 전에는 결정하지 않는다.
3. SOL의 해시 체인·coordinator epoch fencing의 완전한 구현 — 파일럿에는 최소 저널(append+replay+idempotency)로 충분하다. 위험도 기반 역할 생성이라는 핵심 가설이 검증된 뒤에 정교화한다. (7장)
4. ROUTING의 구체적 달러 가격 상수 — 문서 스스로 "스냅샷일 뿐"이라 명시(`ROUTING:211-213`). 실행 시점 카탈로그 조회로 대체한다.
5. Fast 모드의 저위험 자동 검증 임계값과 SOL/CLAUDE안의 `low`/`docs-only` 등급이 수치적으로 완전히 같은 경계인지 — MUST #3(위험 분류 통합)이 끝난 뒤에만 정할 수 있다.

---

## 11. 요약 (기술 판정)

- **같은 결론**: Orca=어댑터, 독립 검증, 3신호 분리, OS별 판정 분리, REVISE≠실패, 타임아웃≠자동승인 — 9개 항목 전부 세 연구 문서와 두 설계 문서가 일관된다. 이 부분은 재작업 불필요.
- **충돌**: 3건(C1 동시쓰기 안전성 오표기 vs SOL의 lease 규칙, C2 위험분류 3분열, C3 CLAUDE안 다이어그램의 시각적 cycle). 모두 실제로 구현에 영향을 주는 실질적 충돌이며 "표현 차이"가 아니다.
- **빠진 것**: 7건(M1~M7). 특히 M1(감사자/승인권자 최소 인원)과 M4(OS 프로세스 감독 포트)는 R1이 원래 지적한 문제(SPOF, 크로스플랫폼 결함)를 새 설계가 진짜로 풀었는지에 직결된다.
- **과도한 것**: SOL의 해시체인/epoch 완전 구현은 파일럿 이전 단계에서는 과잉이다. ROUTING의 가격 상수는 과잉이 아니라 올바르게 스냅샷으로 처리됐다.
- **실패 조건**: CLAUDE안에는 있고 SOL에는 없다 — 최종안은 반드시 흡수해야 한다.
- **8개 공격 검증 항목** 중 완전한 PASS는 "거짓 progress"·"Orca 없는 실행" 2개뿐이다. 나머지 6개(cycle, WIP, fan-in 병목, Windows/macOS, 사용자 gate, 검증 독립성)는 한쪽 또는 양쪽 설계에 구체적 결손이 있다.

**따라서 REVISE.** 10장의 MUST 10개 항목이 해소되고, 3장의 근거 추적 문제가 "미검증 주장"으로라도 명시적으로 재표기된 뒤에 재검수를 요청할 것을 권고한다.
