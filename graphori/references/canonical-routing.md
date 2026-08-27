# Canonical 문서 찾기

문서 전체를 복사하지 말고 요청에 필요한 canonical 문서만 읽는다. 모든 경로는 저장소 루트 기준이다.

| 주제 | 먼저 읽을 문서 |
|---|---|
| 전체 구조와 노드 | `docs/architecture/GRAPHORI_ARCHITECTURE.md` |
| 이벤트 순서와 상태 | `docs/architecture/EVENT_PROTOCOL.md` |
| snapshot, SSE, stale, 진행률 | `docs/architecture/DASHBOARD_CONTRACT.md` |
| Windows/macOS portability | `docs/architecture/PORTABILITY_CONTRACT.md` |
| 현재 단계와 범위 | `docs/IMPLEMENTATION_PLAN.md` |
| MVP, WIP=1, single verifier, revise 제한 | `docs/decisions/0005-mvp-simple-single-verifier.md` |
| 설계 비교나 검증 결과 | 필요한 경우에만 `docs/design/*.md`, `docs/verification/*.md` |

`docs/decisions/0004-token-aware-fast-mode.md`는 과거 아이디어다. Graphori 표준 모드의 기본값으로 Fast Mode를 선택하지 않는다. 실제 실행 결과가 없는 문서는 계획 또는 제안으로 표시하고 성공 근거로 사용하지 않는다.
