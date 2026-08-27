# ADR 0004: 토큰을 아는 Fast 모드

- 상태: superseded by [0005](0005-mvp-simple-single-verifier.md) (2026-08-09)
- 날짜: 2026-08-09

> 이 ADR의 자동 Fast Mode 라우팅(예산 기반으로 Fast를 자동 선택하는 부분)은
> [0005](0005-mvp-simple-single-verifier.md)에서 현재 활성 정책이 아니라고
> 결정됐다. 아래 내용은 기록으로 남기고 삭제하지 않는다. 현재 무엇을 하는지는
> 반드시 0005를 함께 읽는다.

## 1. 12살도 이해하는 설명

토큰은 일을 시키는 데 쓰는 글자 조각이다. 얼마나 썼는지 모르면 0으로 계산하지
않는다. 모르는 작업을 빠른 버튼으로 보내지 않고 Standard 조사나 Critical 검토로
올린다.

## 2. 결정

모든 Attempt는 `usage.status = known | estimate | unknown`을 기록한다. predicted,
actual, unit price와 실제 청구를 분리한다. Fast는 낮은 위험·작은 범위·외부 효과
없음·predicted usage known·budget 조건을 모두 만족할 때만 허용한다. 위험 3,
핵심 unknown, 보안/경로/파괴적 변경, 독립 검토가 필요하면 Critical이다. 독립
reviewer_model_id는 TEAM_TOPOLOGY의 independence constraint를 반드시 통과한다.

## 3. 기술 부록

라우팅 보조 점수는 `3*risk + 2*uncertainty + 2*scope + 2*synthesis + parallelism`
과 budget band다. 점수는 hard trigger를 덮지 않는다. 가격은 실행 시 catalog
snapshot과 `price_checked_at`을 기록하며 문서의 달러 값은 정책 상수가 아니다.
근거: [`MODEL_ROUTING_AND_FAST_MODE.md`](../design/MODEL_ROUTING_AND_FAST_MODE.md),
[`EVENT_PROTOCOL.md`](../architecture/EVENT_PROTOCOL.md),
[`DESIGN_EVIDENCE_REVIEW_LUNA.md`](../verification/DESIGN_EVIDENCE_REVIEW_LUNA.md).
