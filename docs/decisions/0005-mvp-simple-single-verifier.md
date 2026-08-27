# ADR 0005: MVP 단순 단일 작업자 + 필요할 때만 확인자

- 상태: accepted (일부 superseded)
- 날짜: 2026-08-09
- 관계: [0004](0004-token-aware-fast-mode.md)를 대체한다(supersedes).

> 2026-08-14: verifier topology, planning ownership, and delegation-only
> portions are superseded by
> [ADR 0006](0006-v2-adaptive-execution-policy.md). Historical rationale and
> the one-recheck limit remain applicable.

## 1. 12살도 이해하는 설명

숙제를 할 때마다 확인하는 친구를 새로 부르지 않는다. 보통 숙제는 한 명이
새로 맡아서 끝까지 한다. 정말 큰 고비(마일스톤)를 넘었거나, 다른 사람이 쓰는
공개 기능이거나, 보안이 걸렸거나, 되돌릴 수 없는 일이거나, 뭘 해야 할지 잘
모르겠는 어려운 일일 때만 확인하는 친구를 한 명 부른다. 그 확인자는 가능하면
원래 만든 사람과 다른 종류의 모델을 쓴다. 확인자가 "다시 해와"라고 한 번
말하면 딱 한 번만 고치고 다시 보여준다. 그래도 안 되면 사람이 결정한다.

일을 시키는 대장(오케스트레이터)은 여전히 코드를 직접 고치지 않는다. 일을
나눠 주고, 결과를 모으고, 사람에게 보고만 한다.

## 2. 결정

1. **Graphori Fast Mode(ADR 0004의 예산 기반 자동 Fast 라우팅)는 현재 활성
   정책에서 끈다.** Fast/Standard/Critical 위험 분류 자체는 참고 개념으로
   남지만, 예산·usage 조건만으로 자동으로 Fast 경로를 선택해 확인을 건너뛰는
   흐름은 쓰지 않는다.
2. **보통 MVP 작업은 새 구현 담당자(Worker) 한 명이 처음부터 끝까지 진행한다.**
   고정된 design1/design2 팀이나 verification1/verification2 팀을 만들지
   않는다.
3. **확인자(Verifier)는 다음 중 하나일 때만 만든다**: (a) 의미 있는
   마일스톤 완료, (b) 공개 API 변경, (c) 보안 관련 변경, (d) 되돌리기 어려운
   파괴적 변경, (e) 불확실성이 큰 결정. 작은 변경마다 매번 확인자를 붙이지
   않는다.
4. 확인자를 부를 때는 가능하면 구현 담당자와 **다른 모델 계열**을 쓴다.
5. **대안 설계를 나란히 만드는 병렬 설계는 기본적으로 하지 않는다.** 사용자가
   직접 요청했거나, 정말 위험도가 높고 아직 풀리지 않은 결정이 있을 때만
   예외로 병렬 설계를 만든다.
6. **기본 모델 라우팅**: 구현 작업은 GPT-5.6 Luna medium을 기본으로 쓴다.
   가끔 필요한 독립 확인자는 Claude Sonnet medium을 기본으로 쓴다. high는
   정말 중요하고 위험한 작업에만 쓴다.
7. **오케스트레이터는 계속 위임만 한다.** 저장소를 직접 구현하거나 테스트를
   실행하지 않는다. ([`GRAPHORI_ARCHITECTURE.md`](../architecture/GRAPHORI_ARCHITECTURE.md)
   의 canonical 결정 7을 유지한다.)
8. **`docs/PROCESS.md` 기록은 다음 때만 추가한다**: 요청이 받아들여졌을 때,
   계획이 크게 바뀌었을 때, 막힘(blocker)이나 Human Gate가 생겼을 때,
   마일스톤이 끝났을 때, 전체 작업이 끝났을 때. 작은 변경마다 기록을 추가하지
   않는다.
9. **fix + recheck는 한 번까지만 자동으로 한다.** 확인자가 `revise`를 한 번
   내면 그 한 번만 고쳐서 다시 확인받는다. 그래도 `revise`면 자동으로 또
   고치지 않고 Human Gate로 넘긴다. (기존 [`TEAM_TOPOLOGY.md`](../../TEAM_TOPOLOGY.md)
   의 3회 상한을 1회로 낮춘다.)
10. **평소 active WIP는 Worker 1명이 기본값이다.** 정말로 서로 독립적인
    작업이 동시에 필요할 때만 일시적으로 2로 늘린다. 그 외 시간에는 다시
    1로 돌아온다.
11. Orca는 여전히 선택적 어댑터다. Orca 없이도 핵심 흐름은 동작해야 한다.
    이 결정은 Orca 독립성을 바꾸지 않는다.

## 3. 이 결정이 바꾸지 않는 것

- Critical 등급(보안·경로·개인정보·파괴적 외부 효과)에서 독립 검증자 pool
  최소 2명, Worker와 Verifier 겸직 금지 같은 안전장치는 그대로 유지한다.
  다만 이런 독립 pool은 실제로 Critical/마일스톤 확인이 필요한 순간에만
  동원한다.
- `usage.status = known | estimate | unknown` 구분, platform verdict 분리,
  single writer 저널 규칙은 ADR 0004와 [`GRAPHORI_ARCHITECTURE.md`](../architecture/GRAPHORI_ARCHITECTURE.md)
  그대로 유지한다.

## 4. 기술 부록

- 이 결정은 아직 구현되지 않은 `core`/`runtime`/`dashboard`의 향후 기본
  정책이며, [`docs/IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md)의
  진행 상태(현재 1/9)를 바꾸지 않는다.
- 근거: 사용자 결정(2026-08-09), [`TEAM_TOPOLOGY.md`](../../TEAM_TOPOLOGY.md),
  [`0004-token-aware-fast-mode.md`](0004-token-aware-fast-mode.md).
