# ADR 0003: 사건에만 반응하는 진실한 대시보드

- 상태: accepted (canonical)
- 날짜: 2026-08-09

## 1. 12살도 이해하는 설명

게임판 캐릭터는 실제로 일한 만큼만 움직인다. “살아 있다”는 heartbeat, “조금
진행했다”는 digest/checkpoint, “검사 통과”는 verifier verdict로 각각 표시한다.
연결이 끊기면 캐릭터는 멈추고 stale이라고 알려 준다.

## 2. 결정

SSE는 연결 직후 snapshot을 보내고 `Last-Event-ID`/seq부터 replay한 뒤 live event를
보낸다. Projection은 event journal의 reducer 하나로 계산한다. Progress는
`completed/required`와 basis를 공개한다. 사건 없는 timer motion, optimistic approve,
heartbeat를 progress로 세는 표현은 금지한다. original pixel art와 reduced-motion,
색 외 텍스트/아이콘을 필수로 한다.

## 기술 부록

`stale_marked` 뒤 reconnect snapshot/replay 검증 전에는 freeze한다. platform verdict는
같은 화면에 Windows `pass`, macOS `deferred`로 함께 보인다. 근거:
[`DASHBOARD_CONTRACT.md`](../architecture/DASHBOARD_CONTRACT.md),
[`LIVE_GAME_DASHBOARD.md`](../research/LIVE_GAME_DASHBOARD.md), F01 보존 링크는
[`F01_WINDOWS_FINAL_APPROVAL.md`](../evidence/doctori/verification/F01_WINDOWS_FINAL_APPROVAL.md)다.
