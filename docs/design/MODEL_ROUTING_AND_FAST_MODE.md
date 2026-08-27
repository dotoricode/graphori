# Graphori 모델 라우팅과 Fast 모드 정책

상태: 설계 전용. 구현하지 않는다.

이 문서는 Graphori가 **비용과 속도**를 관리하는 규칙을 정한다. 답의 품질을
모델 이름 하나로 보장한다고 말하지 않으며, 위험한 일은 반드시 더 깊은 확인을
거치게 한다.

## 1. 12살도 이해하는 설명

모델은 자전거와 자동차처럼 서로 다른 일꾼이다.

- **GPT-5.6 Luna**는 빠르고 값싼 기본 일꾼이다. 먼저 이 일꾼에게 부탁한다.
- **GPT-5.6 Sol**은 아주 어려운 퍼즐이나 위험한 결정을 맡는 강한 일꾼이다.
  그냥 “더 좋아 보인다”는 이유로 쓰지 않는다.
- **Claude Sonnet**은 Claude를 쓰는 검토 일꾼의 기본값이다. Claude를 골랐다면
  먼저 Sonnet을 시도하고, Sonnet으로 부족하다는 근거가 있을 때만 다른 Claude
  등급을 검토한다.

작업마다 먼저 네 가지를 묻는다.

1. 틀리면 얼마나 크게 다칠까? (**위험도**)
2. 우리가 얼마나 잘 알고 있을까? (**불확실성**)
3. 고치는 곳이 한 군데일까, 여러 곳일까? (**변경 범위**)
4. 일을 여러 갈래로 나누면 빨라질까? (**병렬성**)

마지막으로 남은 토큰 예산도 본다. 토큰은 모델에게 읽고 쓰게 하는 글자 조각의
수이고, 많이 쓰면 시간이 늘고 비용도 늘 수 있다. 단, 토큰 수를 모르면 `0`으로
간주하지 않는다. **모름은 모름으로 기록하고, 보수적인 작은 한도를 사용한다.**

## 1.1 세 연구 보고서에서 가져온 제약

이 정책은 다음 조사 결과를 비용·속도 규칙으로만 번역한다.

| 연구 보고서 | 관찰 | 이 정책의 결과 |
|---|---|---|
| [`LIVE_GAME_DASHBOARD.md`](../research/LIVE_GAME_DASHBOARD.md) | 연결됨, heartbeat, 실제 progress를 서로 구분해야 하며, 가짜 진행을 만들면 안 됨 | 모델 호출 성공이나 연결만으로 완료하지 않는다. 실제 사용량·진행·결과를 별도 기록하고, 신호가 stale이면 새 병렬 작업을 만들지 않는다. |
| [`PORTABILITY_AND_DEPENDENCY.md`](../research/PORTABILITY_AND_DEPENDENCY.md) | dispatch별 토큰 사용량은 실행 결과에서 기록할 수 있지만, 환경에 따라 usage가 없을 수 있음 | 예상/실제 토큰을 분리하고 `unknown`을 보수적으로 처리한다. Orca가 없어도 정책의 비용 원장은 유지되어야 한다. |
| [`TEAM_GRAPH_ANALYSIS.md`](../research/TEAM_GRAPH_ANALYSIS.md) | 7개 고정 역할, 주 경로 18 checkpoint, 독립 감사 최소 4회·20단계, 역할별 토큰·비용·실행시간은 미측정 | 단순 작업은 Fast로 hand-off와 중복을 줄이고, 보안·재현성·cross-model edge는 독립 검토를 유지한다. 병렬성은 실제 측정 전까지 보수적으로 제한한다. |

## 2. 기본 원칙

1. **Luna 우선:** 모든 작업은 Luna 후보로 시작한다. 단, 아래의 Critical 강제
   조건에 걸리면 이 원칙보다 안전 규칙이 먼저다.
2. **Sol 제한:** Sol은 `어려운 합성` 또는 `고위험`일 때만 쓴다. 단순한 문서
   수정이나 반복 작업을 Sol로 올리지 않는다.
3. **Claude Sonnet 우선:** Claude 검토가 필요하면 Sonnet을 먼저 선택한다. 더
   비싼 Claude 등급으로 자동 점프하지 않는다.
4. **안전 우선:** 보안 경계, 비밀정보, 파괴적 변경, 외부 공개, 법률·의료·금융
   판단은 Fast를 사용할 수 없다.
5. **병렬성은 공짜가 아니다:** 독립된 갈래만 병렬로 실행한다. 병렬로 생기는
   추가 입력 토큰, 합성 토큰, 검토 토큰을 예산에 미리 넣는다.
6. **증거 없는 숫자는 진실이 아니다:** 예상 토큰·실제 토큰·가격을 구분한다.
   추정값을 실제 사용량처럼 표시하지 않는다.
7. **완료는 비용만으로 결정하지 않는다:** 결과, 검토, 산출물, 실패 원인을 함께
   기록한다. 비용이 싸도 검수 조건을 건너뛰지 않는다.

## 3. 작업을 점수로 표현하기

라우터는 작업 시작 전에 다음 값을 `0`~`3`으로 기록한다. 점수는 정답이 아니라
자동 선택을 위한 설명 가능한 신호다.

| 신호 | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| 위험도 `risk` | 읽기/초안, 실패해도 되돌릴 수 있음 | 로컬 문서·일반 코드 변경 | 여러 파일·빌드·운영 영향 | 보안/개인정보/비밀/파괴적 변경/외부 공개/고위험 판단 |
| 불확실성 `uncertainty` | 요구와 근거가 명확 | 작은 빈칸 하나 | 자료가 부족하거나 서로 다름 | 핵심 사실을 모름, 새 문제, 결론이 크게 갈림 |
| 변경 범위 `scope` | 한 문단·한 파일 | 한 컴포넌트 | 여러 파일·모듈·계약 | 여러 시스템·팀·공개 인터페이스 |
| 합성 난도 `synthesis` | 복사·분류·짧은 요약 | 한 근거의 변환 | 여러 근거를 맞춰야 함 | 서로 다른 근거를 새 결론으로 합치는 어려운 설계 |
| 병렬성 `parallelism` | 순서가 꼭 필요 | 독립 갈래 2개 | 독립 갈래 3~4개 | 큰 fan-out/fan-in 또는 여러 결과의 어려운 합성 |

값을 계산할 근거가 없으면 `unknown`으로 둔다. 특히 위험도 또는 외부 효과가
`unknown`이면 Fast를 금지한다. “모른다”는 “안전하다”가 아니기 때문이다.

라우터는 다음 **압력 점수**를 보조 신호로 계산한다. `budget_pressure`는 예상
총 토큰이 남은 예산에서 차지하는 비율이며, 토큰을 모르면 `unknown`이다.

```text
routing_pressure = 3*risk
                 + 2*uncertainty
                 + 2*scope
                 + 2*synthesis
                 + 1*parallelism
                 + 3*budget_pressure_band
```

`budget_pressure_band`는 0(20% 이하), 1(20% 초과~60% 이하), 2(60% 초과)로
표현한다. 점수는 하드 안전 규칙을 덮어쓰지 않는다. 다음 경계는 자동 선택의
기본값이다.

| 압력 점수 | 자동 후보 | 추가 조건 |
|---:|---|---|
| 0~7 | Fast | Fast 진입 조건을 모두 만족하고 predicted tokens가 known이어야 함 |
| 8~15 | Standard | 병렬성 2 이상이면 branch·합성 예산을 먼저 예약 |
| 16 이상 | Critical | Sol 후보와 독립 검토를 평가 |

`risk=3`, 외부 효과 unknown, 또는 Fast 금지 목록의 항목은 점수와 관계없이
Critical이다. `predicted_tokens=unknown`이면 점수의 예산 항은 unknown으로
남기고 Fast를 선택하지 않는다. 점수만으로 위험을 낮춰 보이지 않게 하는 것은
허용하지 않는다.

## 4. Fast·Standard·Critical 모드

모드는 속도 버튼이지 품질 면제 버튼이 아니다.

| 모드 | 언제 들어가는가 | 기본 모델 | 병렬성·검토 | 종료 조건 |
|---|---|---|---|---|
| **Fast** | 모든 Fast 진입 조건을 만족할 때만 | GPT-5.6 Luna, 보통 낮은 reasoning | 병렬 0~2개. 독립 갈래만. 추가 독립 검토 없음 | 산출물 생성, 값싼 확인 통과, unknown 없음, 예산 안쪽이면 완료 |
| **Standard** | Fast 조건 하나라도 부족하지만 Critical 강제 조건은 없을 때 | GPT-5.6 Luna 우선. Claude가 필요한 검토는 Sonnet 우선 | 병렬 최대 2~3개(예산이 허용할 때). targeted review 1회 | 근거와 결과가 known이고 필요한 검토가 PASS면 완료 |
| **Critical** | 고위험·어려운 합성·핵심 unknown·넓은 영향·강제 검토가 있을 때 | 고위험 또는 어려운 합성은 GPT-5.6 Sol. 그 외 Critical의 제한된 작업은 Luna 가능하나 독립 검토 필수 | 병렬은 서로 독립인 증거 수집에만. Sol 주 작업 + Claude Sonnet 독립 검토를 기본 후보로 삼음 | 독립 검토/결정 gate PASS, 실제 토큰·비용·증거가 기록되고 unknown이 해소된 뒤에만 완료 |

### 4.1 Fast 진입 조건

다음이 **전부** 참이어야 한다.

- `risk ≤ 1`, `uncertainty ≤ 1`, `scope ≤ 1`, `synthesis ≤ 1`
- 비밀·개인정보·인증·권한·파일 경계·배포·외부 메시지·파괴적 명령이 없음
- 사람 승인, 독립 cross-model 검토, fresh run이 요구되지 않음
- 예상 총 토큰을 알면 작업 예산의 20% 이하이고, 알 수 없으면 Fast 금지
- 병렬 실행 시 `branches ≤ 2`이고 결과 합성 비용까지 예산에 포함됨
- 이전 실패나 재시도가 없는 새 시도이며, 모델·가격 카탈로그를 읽을 수 있음

### 4.2 Fast가 허용되지 않는 작업

아래 중 하나라도 있으면 Fast가 아니다.

- 보안 경계, 파일 경로 경계, junction/symlink, 인증·권한, 개인정보·비밀 처리
- 파일 삭제·덮어쓰기, 외부 시스템 변경, 배포·게시·전송처럼 되돌리기 어려운 일
- 법률·의료·금융 판단 또는 안전에 직접 영향을 주는 결정
- 여러 시스템의 계약을 바꾸는 작업, 공개 API/스키마 변경
- 근거가 충돌하거나 중요한 사실이 `unknown`인 작업
- 어려운 합성, adversarial 검토, 독립 재현, cross-model 승인이 요구된 작업
- 이전 결과의 원인을 모른 채 다시 시도하는 작업
- 예상 토큰 또는 남은 토큰 예산을 알 수 없는 작업

Fast로 시작한 뒤 위 조건이 발견되면 즉시 중단하고 Standard 또는 Critical로
승격한다. 이미 만든 초안은 증거로 보존하되, 완료로 표시하지 않는다.

## 5. 자동 모델 선택 결정표

하드 안전 규칙을 먼저 적용하고, 그 다음 점수와 예산을 적용한다.

| 상황 | 모드 | 주 모델 | 최소 후속 조치 |
|---|---|---|---|
| 낮은 위험·낮은 불확실성·작은 범위 | Fast | Luna | 값싼 확인; 실패 시 Standard |
| 중간 위험 또는 중간 범위 | Standard | Luna | targeted review; 필요하면 Sonnet |
| 여러 근거를 맞추는 설계/조사 합성 | Standard 또는 Critical | Luna로 초안, 난도가 높으면 Sol | Sonnet 독립 검토 또는 지정 reviewer |
| 보안·개인정보·파괴적 변경·외부 영향 | Critical | Sol | 독립 Sonnet 검토 + 사람/결정 gate |
| 핵심 사실 unknown + 넓은 영향 | Critical | Sol | 먼저 조사/증거 수집; unknown 해소 전 완료 금지 |
| 위험은 낮지만 독립 검토 계약이 있음 | Standard | Luna | Claude를 쓰면 Sonnet 우선 |
| Claude 제공자가 명시적으로 필요함 | 현재 모드 유지 | Claude Sonnet 우선 | Sonnet 실패·능력 부족의 증거가 있을 때만 승격 |
| 병렬 갈래가 3개 이상 | Standard 또는 Critical | 각 갈래 Luna 우선 | fan-in 합성 예산·검토를 예약; 공유 파일은 병렬 금지 |
| Sol 후보 조건이 없음 | Fast/Standard | Sol 금지 | Luna 또는 Sonnet 사용 |

`risk=3`인 단순 확인이라고 해서 Sol이 모든 하위 일을 해야 하는 것은 아니다.
고위험 결과를 다루는 최종 합성·승인 경로는 Sol과 독립 검토를 사용하고, 단순한
증거 수집은 Luna로 제한할 수 있다. 반대로 `synthesis=3`이고 결과가 보안·계약에
영향을 주면 Sol을 쓴다.

### 5.1 모델 선택 의사결정 순서

1. 금지된 외부 효과나 고위험 판단이 있는가? 있으면 Critical.
2. 핵심 risk/uncertainty가 unknown인가? 외부 효과가 의심되면 Critical, 그 외에는
   Standard에서 작은 한도로 조사한다. Fast는 금지.
3. `synthesis ≥ 3` 또는 `uncertainty ≥ 2 && scope ≥ 2`인가? Sol 후보로 올린다.
4. Sol 후보가 아니면 Luna를 선택한다.
5. 독립 검토가 필요하면 Claude Sonnet을 첫 검토자로 추가한다.
6. 병렬성이 실제 wall-clock 이득을 주는지 계산한다. 추가 비용이 예산을 넘거나
   결과가 서로 의존하면 순차 실행한다.

## 6. 토큰·가격·예산 규칙

### 6.1 세 가지 값을 구분한다

| 값 | 뜻 | 없을 때의 처리 |
|---|---|---|
| `predicted_tokens` | 시작 전 예상 입력+출력+도구/합성 토큰 | `unknown`; Fast 금지, 작은 hard cap으로 Standard 조사 |
| `actual_tokens` | 제공자가 보고한 실제 입력·출력·추론 토큰 | `unknown`을 그대로 기록; 출력 글자 수로 추측하지 않음 |
| `unit_price` | 모델·캐시·긴 문맥별 현재 단가 | `unknown`; 비용을 숫자로 약속하지 않고 호출 전 중단/승인 |

예상 총 토큰은 다음을 모두 합친다.

```text
predicted_total = primary
                + sum(parallel_branches)
                + synthesis
                + review
                + retry_reserve
```

병렬 갈래를 추가하면 각 갈래의 입력 토큰과 마지막 합성 토큰도 추가한다. 한
갈래의 결과가 다른 갈래에 필요한 경우 병렬로 세지 않는다.

### 6.2 예산 한도

아래 숫자는 시작 운영값이며 제품 설정으로 바꿀 수 있다. 사용자·프로젝트가
더 작은 한도를 주면 그 한도를 따른다.

| 모드 | 제안 hard cap/시도 | 총 예산 사용 목표 | 남겨 둘 예약분 |
|---|---:|---:|---:|
| Fast | 8,000 tokens | 전체 작업 예산의 20% 이하 | 최소 1회 Standard 승격분 |
| Standard | 32,000 tokens | 전체 작업 예산의 60% 이하 | targeted review + 1회 재시도분 |
| Critical | 128,000 tokens 또는 사용자 승인 한도 | 남은 예산 안에서만 | 독립 검토 + 복구/재시도분 |

`predicted_total`이 남은 예산과 예약분을 넘으면 실행하지 않고 작은 하위 작업으로
쪼개거나 승인 질문으로 보낸다. hard cap에 가까워지면 새 병렬 갈래를 만들지
않는다. 예산은 속도를 위해 안전 검증을 삭제하는 데 쓰지 않는다.

### 6.3 현재 OpenAI 가격은 참고 스냅샷일 뿐이다

2026-08-09에 확인한 공식 문서에는 GPT-5.6 Luna가 입력 `$1.00`/출력 `$6.00`,
Sol이 입력 `$5.00`/출력 `$30.00`(각 1M tokens 기준)으로 표시되어 있었다.
Luna의 cached input은 `$0.10`, Sol은 `$0.50`으로 비교 문서에 표시된다. 이는
정책 상수가 아니다. 가격, 모델 ID, 가용성, 캐시·긴 문맥 요금은 바뀔 수 있으므로
매 실행 전에 [OpenAI Models 공식 문서](https://developers.openai.com/api/docs/models),
[모델 비교표](https://developers.openai.com/api/docs/models/compare),
[OpenAI API Pricing](https://openai.com/api/pricing/)을 확인하고 `price_checked_at`을
기록한다. [GPT-5.6 Luna 문서](https://developers.openai.com/api/docs/models/gpt-5.6-luna)의
“가격은 사용 토큰 등에 따라 계산된다”는 안내도 따른다.

OpenAI의 현재 모델 안내는 복잡한 추론에는 Sol, 비용 민감·대량 작업에는 Luna를
권한다. 이 문서의 Luna 기본값과 Sol 제한은 그 방향을 Graphori의 위험·예산
규칙으로 좁힌 것이다. [최신 모델 안내](https://developers.openai.com/api/docs/guides/latest-model)
와 [GPT-5.6 출시 안내](https://openai.com/index/gpt-5-6/)를 참고한다.

Claude 가격은 이 문서에 숫자로 고정하지 않는다. Claude를 선택할 때는 연결된
제공자의 현재 가격 카탈로그와 모델 ID를 읽어 같은 계산을 적용한다. 카탈로그가
없으면 Claude 비용을 숫자로 약속하지 말고, Sonnet 호출 전 승인 또는 보수적
토큰 한도를 사용한다.

## 7. 모드 진입·탈출·승격

### 7.1 진입

- **Fast 진입:** 4.1의 모든 조건을 만족하고, 예상 비용/토큰이 예산과 예약분 안에
  있을 때만 가능하다.
- **Standard 진입:** Fast가 불가능하지만 Critical hard trigger가 없을 때다.
  unknown 입력은 조사 작업으로 좁혀야 하며 완료 판정에는 남지 않는다.
- **Critical 진입:** `risk=3`, 외부 효과가 불명확함, `uncertainty=3`과 넓은
  범위의 결합, 어려운 합성, 독립 fresh review, 사람 gate 중 하나면 된다.

### 7.2 탈출과 승격

| 현재 | 다음 상태 | 조건 |
|---|---|---|
| Fast | 완료 | 결과·근거·실제 사용량이 알려지고 cheap check PASS |
| Fast | Standard | 첫 품질 실패, 모호한 요구 발견, 예상 대비 실제 토큰 110% 초과, 도구 오류 |
| Fast | Critical | 보안/외부 영향/파괴적 변경 발견, risk 또는 핵심 uncertainty 상승 |
| Standard | 완료 | 필요한 결과와 targeted review PASS, unknown 없음 |
| Standard | Critical | 재작업 원인 불명, 범위가 시스템 경계를 넘음, 보안·고위험 결함 발견 |
| Critical | 완료 | 독립 검토 PASS, 사람 gate 조건 충족, 사용량·비용·증거 known |
| Critical | Standard/Fast | 같은 작업 안에서는 자동 강등 금지. 새 작업으로 명시적으로 재분류할 때만 가능 |

모드가 끝났다는 것은 해당 작업의 상태가 끝났다는 뜻이다. 다음 작업은 새
preflight에서 다시 분류한다.

## 8. 재시도·예산 초과·리뷰 승격

### 8.1 재시도

1. 네트워크 timeout·일시적 제공자 오류이고 내용 결함 증거가 없으면 같은 모델로
   **한 번** 재시도한다. 예약된 재시도 예산이 있을 때만 한다.
2. 같은 답의 품질 실패를 그대로 반복하지 않는다. 실패 원인을 줄여 다시 요청하고,
   Standard로 승격하며 targeted Claude Sonnet 검토를 예약한다.
3. 두 번째 실패 또는 원인 불명은 자동 재시도하지 않는다. Critical 승격, Sol 합성,
   독립 Sonnet 검토, 또는 사람 결정 중 하나를 선택한다.
4. Critical에서의 재시도도 새 호출이므로 실제 예산을 다시 확인한다. 실패했다고
   토큰이 환불되었다고 가정하지 않는다.

### 8.2 예산 초과

- 실제 토큰이 hard cap을 넘으면 즉시 새 호출과 새 병렬 갈래를 멈춘다.
- 결과가 잘렸으면 `budget_exceeded`로 표시하고 완료가 아니다.
- 실제 토큰이 unknown이면 예약된 hard cap을 사용한 것으로 보수적으로 계산한다.
  남은 예산을 늘려 잡지 않는다.
- 초과 뒤 자동 재시도·자동 Sol 전환은 금지한다. 더 큰 예산을 승인받거나,
  작업을 작은 범위로 다시 설계한다.
- 비용 단가가 unknown이면 비용을 `$0`으로 표시하지 않는다. `cost_unknown`으로
  남기고 예산 관리자에게 보낸다.

### 8.3 리뷰 승격

다음 중 하나이면 리뷰를 추가하거나 더 강한 모드로 올린다.

- 사용자가 “검수/독립 확인/교차 모델”을 요구함
- 결과가 여러 근거를 합친 설계·결정임
- 첫 결과와 증거가 맞지 않거나, 같은 질문에 결과가 흔들림
- 변경 범위가 예상보다 커짐
- 안전·보안·계약·재현성 관련 결함이 발견됨

Standard 리뷰는 가능한 한 **Claude Sonnet 독립 검토**로 시작한다. Critical은
Sol이 작성/합성하고 Sonnet이 원문 증거만으로 별도 판정하는 구성을 기본 후보로
삼는다. 검토자는 작성자의 답을 그대로 복사하지 말고 입력 증거·검토 결과·결정
이유를 따로 남긴다.

## 9. 의사코드

아래는 구현 코드가 아니라 정책을 기계가 따라 읽을 수 있게 쓴 약속이다.

```text
route(task, budget, catalog, telemetry):
    facts = classify(task)  # risk, uncertainty, scope, synthesis, parallelism
    pressure = routing_pressure(facts, budget, telemetry)
    if facts.risk == 3 or facts.external_effect in {true, unknown}:
        mode = CRITICAL
    else if facts.risk == unknown or facts.uncertainty == unknown:
        mode = STANDARD  # 외부 효과가 의심되면 위의 CRITICAL 규칙 적용
    else if difficult_synthesis(facts) or high_impact_unknown(facts):
        mode = CRITICAL
    else if pressure >= 16:
        mode = CRITICAL
    else if pressure <= 7 and fast_conditions(facts, telemetry, budget, catalog):
        mode = FAST
    else:
        mode = STANDARD

    predicted = estimate_tokens(task, telemetry)
    reserve = retry_reserve(mode) + review_reserve(mode)
    if predicted == unknown:
        if mode == FAST: mode = STANDARD
        cap = conservative_cap(mode)
        mark(predicted_tokens = unknown)
    else if predicted + reserve > budget.remaining:
        stop("budget_insufficient")

    if mode == CRITICAL and (facts.risk == 3 or difficult_synthesis(facts)):
        primary = GPT_5_6_SOL
    else:
        primary = GPT_5_6_LUNA

    if task.requires_claude or needs_independent_review(mode, facts):
        reviewer = CLAUDE_SONNET  # Sonnet first; upgrade only with evidence

    branches = choose_parallel_branches(facts, budget)
    if facts.parallelism >= 2:
        reserve(branch_cost(branches) + synthesis_cost(branches))
    if shared_mutable_state(branches) or branch_cost(branches) > budget.remaining:
        branches = sequential(branches)

    result = run(primary, cap_or(predicted, mode))
    actual = read_provider_usage(result)
    record(actual_tokens = actual or unknown,
           cost = price_from_catalog(actual, catalog) or unknown)

    if hard_cap_exceeded(actual) or actual == unknown_and_cap_reached:
        return BUDGET_EXCEEDED
    if transient_failure(result) and retry_reserve_available(mode):
        return retry_once_then_reclassify(task, mode)
    if quality_failure(result) or new_unknown(result):
        return promote_to_STANDARD_or_CRITICAL(task, result)
    if reviewer exists:
        review = run_independently(reviewer, evidence=result.evidence)
        if review != PASS:
            return promote_to_CRITICAL_or_human_gate(task, review)
    return COMPLETE only when all required facts and usage are known
```

## 10. 결정·기록 계약

각 작업은 다음을 남긴다. 이 목록은 비용 대시보드와 검토자가 같은 사실을 보게
하기 위한 설계 계약이며, 구현 형식은 정하지 않는다.

```text
task_id, run_id
mode_entered, mode_exit, promotion_reason
risk, uncertainty, scope, synthesis, parallelism
model_id, reasoning_level, reviewer_model_id?
predicted_tokens, actual_input_tokens, actual_output_tokens, actual_reasoning_tokens
unit_price, price_checked_at, estimated_cost, actual_cost, cost_status
budget_before, budget_reserved, budget_after, budget_exceeded?
retry_count, retry_reason, review_result
unknown_fields[], evidence_ids[], outcome
```

`actual_*`가 없으면 필드 값은 `unknown`이다. `unknown`을 빈 문자열, 0, 성공으로
변환하지 않는다. 모델 ID와 가격의 출처가 바뀌면 새 카탈로그 확인 시각을 남긴다.

## 11. Acceptance tests (설계 검증)

아래 테스트는 구현 완료를 주장하는 테스트가 아니라, 이 정책을 구현할 때 반드시
검증해야 할 행동이다.

| ID | 입력/상황 | 기대 결과 |
|---|---|---|
| AT-01 Luna 기본 | risk=0, uncertainty=0, scope=0, synthesis=0, 예측 2k | Fast + GPT-5.6 Luna, 완료 시 cheap check |
| AT-02 Fast 금지: 보안 | 문서 한 파일이어도 파일 경계/junction 수정 | Critical; Fast 불가; 고위험 경로는 Sol + 독립 검토 |
| AT-03 Fast 금지: 외부 효과 | 게시·배포·삭제 명령 | Critical; 실행 전 사람/결정 gate; 자동 실행 금지 |
| AT-04 Fast 금지: unknown 토큰 | 위험은 낮지만 predicted_tokens=unknown | Fast 불가; Standard의 보수적 hard cap; 비용 약속 금지 |
| AT-05 unknown 위험 | 외부 효과가 있는지 판별 불가 | Critical로 보수 처리; 조사/승인 전 완료 금지 |
| AT-06 어려운 합성 | 서로 충돌하는 4개 근거 + scope=2 | Critical; Sol 후보; Sonnet 독립 검토; Luna 단독 완료 금지 |
| AT-07 단순 고위험 하위작업 | 위험 결과에 쓰일 단순 증거 수집 | 수집은 Luna로 제한 가능; 최종 합성/승인은 Sol·검토 lane 유지 |
| AT-08 Claude 우선 | Claude 검토가 필요하고 특별 능력 요구 없음 | Claude Sonnet 선택; 더 높은 Claude 등급 자동 선택 금지 |
| AT-09 병렬 비용 | 독립 갈래 3개, 합성 1개, 예산 부족 | 병렬을 줄이거나 순차화; 예산 초과 실행 금지 |
| AT-10 공유 파일 병렬 | 두 갈래가 같은 파일을 수정 | 병렬 금지; 순차 실행 또는 범위 분리 |
| AT-11 actual unknown | 제공자가 실제 토큰을 보고하지 않음 | `actual_tokens=unknown`, hard cap 사용분으로 보수 계산, 비용 `unknown` |
| AT-12 가격 unknown | 가격 카탈로그를 읽을 수 없음 | 비용 숫자 표시 금지; 호출 중단 또는 승인된 토큰 한도만 사용 |
| AT-13 Fast 승격 | Fast 작업 중 모호한 요구가 새로 발견됨 | 즉시 중단; Standard 재분류; 초안은 완료 아님 |
| AT-14 Sol 제한 | 단순 요약·문서 서식 작업 | Sol 호출 없음; Luna 사용 |
| AT-15 일시 오류 재시도 | timeout 1회, 예산 예약 있음 | 같은 모델로 1회만 재시도; 성공해도 사용량 합산 |
| AT-16 품질 실패 | 같은 답이 틀렸고 원인 불명 | 무작정 반복 금지; Standard→Critical 승격 및 검토/사람 gate |
| AT-17 예산 초과 | actual tokens가 hard cap 초과 | 새 호출·병렬 중단; `budget_exceeded`; 자동 재시도 없음 |
| AT-18 리뷰 실패 | Sonnet이 evidence 불일치 판정 | 완료 금지; Critical 또는 사람 결정으로 승격 |
| AT-19 Critical 탈출 | Sol 결과 + 독립 Sonnet PASS + usage/cost/evidence known | Critical 완료; 같은 작업을 자동 Fast로 강등하지 않음 |
| AT-20 재분류 | 완료 후 새 작업이 작은 문서 수정으로 생성됨 | 새 preflight에서 Fast 재평가; 이전 Critical을 그대로 상속하지 않음 |

## 12. 정책 요약

`Luna → (필요할 때) Standard → (어렵거나 위험할 때) Sol + Sonnet 검토`가
기본 흐름이다. Fast는 “작고, 잘 알고, 되돌릴 수 있고, 예산을 아는 일”에만
쓴다. 모르는 값은 0이 아니며, 초과·실패·검토 거절은 더 강한 확인으로 올리는
신호다. 가격은 현재 공식 문서의 스냅샷일 뿐 언제든 변할 수 있으므로, 정책은
모델 이름이나 가격 숫자보다 `catalog 확인 → 예산 예약 → 실제 사용량 기록`의
순서를 신뢰한다.
