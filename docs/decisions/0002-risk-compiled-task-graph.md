# ADR 0002: 위험도에서 컴파일하는 작업 그래프

- 상태: accepted (canonical)
- 날짜: 2026-08-09

> **현재 MVP 정책(ADR 0005가 일부 대체함):** 이 문서의 예전 REVISE 자동
> 상한 3회, 기본 WIP 4, 고정 verifier/team 관련 문구는 현재 MVP의 기본값이
> 아니다. ADR 0005가 이 세 부분을 부분 대체한다. 지금은 자동 수정 1회만
> 허용하고, 두 번째 REVISE는 Human Gate로 올리며, 평소 WIP는 Worker 1명이고
> 필요한 때에만 verifier를 만든다. 아래의 3회·WIP 4는 과거 설계 기록일 뿐이다.

## 1. 12살도 이해하는 설명

모든 숙제에 같은 숫자의 친구를 붙이지 않는다. 쉬운 숙제는 빠르게 자동 확인하고,
위험한 숙제는 다른 친구의 검사와 사람의 결정을 추가한다. 다시 고칠 때는 옛 카드를
지우지 않고 새 카드를 만든다.

## 2. 결정

Router는 `risk_level + risk_tags + routing_scores`를 계산해 Fast/Standard/Critical
subgraph를 만든다. 고정팀은 0개이며, Worker/Verifier/Observer/Human Gate는 Run에
동적으로 생성된다. scheduling edge는 항상 DAG이고 `rework_of`는 history다.
Verifier pool과 gate authority pool은 각각 최소 2명이며, 독립성 위반 후보는 배정하지
않는다. **현재 활성 MVP에서는 한 논리 작업의 REVISE 자동 루프를 1회만 허용하고,
두 번째 REVISE부터 Human Gate다(ADR 0005 §9).** 예전 3회 상한은 기록값이며
현재 실행 정책이 아니다.

## 3. 선택 이유

기존 연구의 18 checkpoint와 **과거 기록에 남은 3회 결함 발견**은 고정팀이 항상
안전하다는 증거가 아니라, 독립 검증은 필요하고 불필요한 대기는 줄일 수 있다는
E1 관찰이다. 이 3회는 현재 자동 상한을 뜻하지 않는다. 두
REVISE 보고서가 지적한 위험 분류 3분열, fan-in queue, 감사자 SPOF, rework cycle을
하나의 컴파일 규칙으로 닫는다.

## 기술 부록

`docs-only`는 `automatic verifier`를 포함한다(`verification_depth=automatic`).
Flat `risk_class`는 표시용으로만 매핑한다. `active_wip`와 `task_parallelism`을
분리한다. **기본 Run WIP 4와 branch 2/3/4는 현재 MVP가 아닌 과거 실험 전
운영값이다.** 현재 MVP의 기본 WIP는 ADR 0005 §10의 Worker 1명이다. 근거:
[`TEAM_TOPOLOGY.md`](../TEAM_TOPOLOGY.md), [`TEAM_GRAPH_ANALYSIS.md`](../archive/research/TEAM_GRAPH_ANALYSIS.md),
[`DESIGN_COMPARISON_CLAUDE.md`](../archive/verification/DESIGN_COMPARISON_CLAUDE.md).
