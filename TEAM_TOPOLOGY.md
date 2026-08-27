# Graphori team topology contract

> 상태: canonical, 구현 전 설계

## 1. 12살도 이해하는 설명

Graphori에는 늘 같은 반 친구들이 앉아 있지 않다. 새 숙제가 오면 Router가
필요한 역할 카드를 만들고, 일이 끝나면 그 카드들은 사라진다. 그래서 “고정팀
7개”를 유지하는 대신, 숙제의 위험도에 맞게 작은 팀을 만들고 독립 검사자와
승인자를 따로 둔다.

보통 숙제는 한 명이 새로 맡아서 처음부터 끝까지 한다. 확인하는 친구는 매번
부르지 않는다. 중요한 고비(마일스톤)를 넘었거나, 다른 사람이 쓰는 공개
기능이거나, 보안이 걸렸거나, 되돌릴 수 없는 일이거나, 뭘 해야 할지 잘
모르겠는 어려운 일일 때만 확인자 한 명을 부른다. 이 확인자는 되도록 원래
만든 사람과 다른 종류의 모델을 쓴다. 위험한 숙제는 여러 갈래로 조사한 뒤,
만든 사람과 다른 사람이 모아 확인하고 사람이 마지막 결정을 한다. 이 기본
정책은 [`docs/decisions/0005-mvp-simple-single-verifier.md`](docs/decisions/0005-mvp-simple-single-verifier.md)에
있다. Graphori Fast Mode(예산만으로 자동으로 빠른 경로를 고르는 흐름,
[`0004`](docs/decisions/0004-token-aware-fast-mode.md))는 지금 활성 정책이
아니다.

## 2. 역할은 다섯 종류, 고정팀은 0개

| 역할 | 하는 일 | 할 수 없는 일 |
|---|---|---|
| Router | graph version, risk, mode, assignment 생성·우선순위 계산 | 산출물 직접 수정·verdict 생성 |
| Worker | 할당된 작업 수행, 산출물·evidence 제출 | 자기 결과의 독립 승인 |
| Verifier | fresh/targeted/automatic 검사, pass/revise 기록 | 검사 대상과 같은 attempt 승인 |
| Observer | 사건을 읽고 freshness·progress·usage를 계산 | scheduling, 산출물 수정, verdict |
| Human Gate | revise 상한, 외부 효과, partial platform 결과 결정 | 자동으로 timeout을 approve로 바꾸기 |

역할 인스턴스는 Run 안에서만 존재한다. `role_id`, `run_id`, `task_id`, capability,
provider/model, checkout, 독립성 차원을 기록한다. “팀 수”는 영구 조직도가 아니라
동시에 활성인 역할 인스턴스 수다.

## 3. 세 가지 그래프

Fast/Standard/Critical은 위험을 가늠하는 참고 개념으로만 남는다([ADR
0005](docs/decisions/0005-mvp-simple-single-verifier.md) 결정 1). 활성
정책에서 실제로 쓰는 그래프 모양 이름은 **normal**, **reviewed(마일스톤/
위험)**, **critical** 세 가지뿐이다. **기본값은 확인자 없이 진행하는
normal이다.** 아래 조건 중 하나에 해당할 때만 reviewed 또는 critical
그래프로 올라간다: 의미 있는 마일스톤 완료, 공개 API 변경, 보안 관련 변경,
되돌리기 어려운 파괴적 변경, 불확실성이 큰 결정.

### normal(기본, 확인자 없음)

`Router → Worker → Observer`

작은 변경, 문서 수정, 위 조건에 해당하지 않는 보통의 MVP 작업이다. Worker
스스로 결과와 evidence를 기록하고, 별도 확인자를 즉시 부르지 않는다. `risk_level
<= 1`이고 핵심 uncertainty·외부 효과가 없으며 예측 사용량이 known일 때 이
경로를 쓴다.

### reviewed(마일스톤 또는 위험)

`Router → Worker → fresh Verifier → Observer`

마일스톤 완료, 공개 API 변경처럼 확인이 필요하지만 Critical hard trigger는
없는 경우다. fresh 검증자는 작성 attempt/provider/model/checkout과 달라야
하고, 가능하면 구현 담당자와 다른 모델 계열을 쓴다. `revise`면 새 revision을
한 번만(fix + recheck 1회) 자동으로 만든다. 그래도 `revise`면 자동으로 더
반복하지 않고 Human Gate로 넘긴다.

### critical

`Router → Worker → fresh Verifier → Human Gate → Observer`

보안·경로·개인정보·파괴적 외부 효과, 핵심 unknown, 어려운 합성, fresh 독립
검증이 필요한 경우다. **기본적으로 병렬 대안 branch는 만들지 않는다.**
사용자가 직접 요청했거나 evidence가 정말 독립적으로 필요한 예외 상황에서만
`{Worker*} → Fan-in Verifier`처럼 branch를 병렬화한다. Fan-in은 priority
내림차순, 같은 priority는 생성 순서 오름차순이며, capability pool이 가득
차면 새 작업을 숨기지 않고 `queued`와 예상 대기를 보인다.

## 4. 독립성, 승인자, 백업

- 확인이 실제로 필요한 순간(마일스톤, 공개 API, 보안, 파괴적 변경, 높은
  불확실성)에는 독립 Verifier pool의 최소 정원이 1명이다. 고정된 상시
  Verifier 팀은 두지 않는다. Worker를 Verifier로 겸직하지 않는다. 후보가
  아무도 없으면 `blocked(reason=independent_verifier_unavailable)`로 Human
  Gate에 보낸다. Critical(보안·경로·개인정보·파괴적 외부 효과)만 예외로
  독립 pool 최소 2명을 유지하는 안전장치가 그대로 남는다([ADR
  0005](docs/decisions/0005-mvp-simple-single-verifier.md) 3장). 한 명만
  가용하면 Critical은 실행을 멈추고
  `blocked(reason=independent_pool_unavailable)`로 Human Gate에 보낸다.
- Human Gate authority pool도 최소 2명이다. 승인자는 Worker, Verifier, Router와
  identity/provider/model/checkout을 공유하지 않는다.
- 현재 holder가 heartbeat를 잃으면 2번째 pool member가 takeover한다. 둘 다 없으면
  timeout 후 자동 승인하지 않고 `blocked`를 유지한다.
- 후보가 독립성 조건을 만족하지 못하면 Router가 배정하지 않고 `assignment_rejected`
  event를 남긴다. ROUTING의 `reviewer_model_id`도 이 규칙을 통과해야 한다.
- 감사자와 승인자의 assignment는 원 작업 완료·revision 생성보다 먼저 journal에
  기록된다. 결과를 본 뒤 독립성을 바꿀 수 없다.

## 5. WIP, parallelism, fan-in

`active_wip`는 한 Run/시스템에서 현재 running인 역할 인스턴스 수이고,
`task_parallelism`은 한 Task graph에서 독립 branch 수다. 서로 다른 숫자다.

- [ADR 0005](docs/decisions/0005-mvp-simple-single-verifier.md) 이후 평소
  active WIP 기본값은 1(구현 담당자 한 명)이다. 정말로 서로 독립적인 작업이
  동시에 필요하다고 명시적으로 정당화된 경우에만 일시적으로 2로 늘리고,
  끝나면 다시 1로 돌아온다. task parallelism에는 고정된 기본 branch 수를
  두지 않는다. branch는 서로 완전히 독립적이고 명시적으로 정당화된 경우에만
  만들고, 그 외에는 단일 Worker/Verifier 흐름을 쓴다.
- capability별 queue는 `priority = risk_level*10 + age_band`로 정렬한다. 같은
  priority는 FIFO다. 높은 위험이 영원히 굶지 않도록 age_band는 일정 시간마다
  1씩 오른다.
- fan-in은 모든 `requires` edge가 terminal successful이거나 명시적으로
  `inconclusive` 처리된 뒤에만 열린다. 하나의 branch가 `failed`면 자동으로 성공으로
  합치지 않고 rework 또는 gate로 보낸다.
- shared checkout/file을 동시에 쓰는 branch는 병렬로 만들지 않는다.

## 6. REVISE 상한과 자동 에스컬레이션

한 논리 작업의 `revise_count`는 0에서 시작해 `verdict=revise`마다 1 증가한다.
[ADR 0005](docs/decisions/0005-mvp-simple-single-verifier.md) 이후 상한은
1회다. 1회째 revise(fix + recheck 한 번)까지만 새 revision을 자동으로 만들 수
있다. 1회를 넘기려는 revise는 새 Worker를 자동 생성하지 않고
`human_gate_required(reason=revise_limit)`로 전환한다. Gate는 범위 축소, 추가
evidence, 다른 실행 환경, 중단 중 하나를 선택한다.

Attempt의 timeout/retry는 이 revise 수와 다르다. 일시적 process 오류의 retry가
검증 revise를 소모하지 않는다는 점을 event에 명확히 적는다.

## 7. 실패·롤백 조건

다음 중 하나면 현재 topology 채택을 중단하고 Human Gate에서 재평가한다.

- seeded defect의 false negative가 허용 한도를 초과함
- 독립성 위반 또는 same-attempt review가 한 번이라도 검출됨
- risk classifier의 입력/결과 또는 usage 계측이 없는 상태로 배포하려 함
- classifier의 fresh 표본 정확도를 100개 작업 또는 30일 중 빠른 주기로 감사하지 못함
- revise가 1회 상한을 우회하거나 rework history가 scheduling cycle로 기록됨
- generic/Orca adapter가 같은 fixture에 대해 원인 모르게 다른 terminal 결과를 냄
- 사용자가 liveness/progress/verdict 세 신호를 구분할 수 없다는 접근성 테스트 실패

## 8. 기술 부록 A. 생성 규칙

| 입력 | 생성 역할 | 필수 조건 |
|---|---|---|
| docs-only | Worker(확인자 없음, normal) | 자동 verifier를 강제하지 않는다; 필요하면 reviewed로 승격 |
| low-risk change | Worker + fresh Verifier 선택 | known evidence 또는 reviewed 승격 |
| feature/change | Worker + fresh independent Verifier | fresh evidence, reviewed |
| security-boundary/reproducibility | Worker + fresh Verifier + Human Gate | critical, 독립 pool ≥2; 병렬 branch는 정당화된 예외에서만 |
| external-blocked | Observer + Human Gate | 실행하지 않고 `blocked` evidence 기록 |

Flat `risk_class`는 저장하지 않고 위 표의 `risk_level`, `risk_tags`,
`verification_depth`, `mode`로 분해한다. `routing_pressure`는 보조 계산값이다.

## 기술 부록 B. 증거 링크

이 topology는 고정 역할 7개와 18 checkpoint를 기록한 [`TEAM_GRAPH_ANALYSIS.md`](docs/research/TEAM_GRAPH_ANALYSIS.md),
상호 독립 감시를 결정한 [`0003-two-model-mutual-oversight.md`](docs/evidence/doctori/decisions/0003-two-model-mutual-oversight.md),
delegation-only를 결정한 [`0005-orchestrator-delegation-only.md`](docs/evidence/doctori/decisions/0005-orchestrator-delegation-only.md)를
참고하되, 해당 관찰은 E1이다. F01 원문 보존과 digest는 [`MANIFEST.md`](docs/evidence/doctori/MANIFEST.md)에서 확인한다.
