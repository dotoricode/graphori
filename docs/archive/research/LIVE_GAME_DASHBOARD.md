# LIVE GAME DASHBOARD 조사: 여러 에이전트를 한눈에 보는 살아 있는 게임판

- 조사일: 2026-08-09
- 단계: 설계 전용 조사. 구현, 기존 게임 자산 복제, 특정 제품의 화면 복제는 하지 않는다.
- 대상: 여러 에이전트 터미널·세션·팀의 실제 상태를 한 화면에서 보고, 사용자가 직접 명령·검수·결정을 내리는 대시보드
- 읽는 순서: `쉬운 설명` → `설계 후보` → `기술 부록` → `출처와 검증 질문`

> **검증 문서의 범위**
>
> 현재 작업 저장소에는 Doctori verification 문서가 없어 원문을 직접 대조할 수 없었다. 아래의 “현재 문제”는 요청에 명시된 검증 관찰을 입력으로 삼았다: **70%에 고정됨**, **2초 polling이 실제로 살아 있는지 알기 어려움**, **가짜 작업 모션**, **배경과 맞지 않는 캐릭터**, **게시판 위치 불일치**, **낡고 투박한 UI**. 제품의 원문 검증 보고서가 제공되면 각 항목에 실제 캡처·재현 단계·결과를 추가해야 한다.

## 1. 한 줄 결론

이 대시보드는 “작은 게임”이 아니라 **실제 사건(event)을 보여 주는 관측판**이어야 한다. 캐릭터가 걷거나 일하는 모습은 애니메이션 타이머가 아니라 서버가 보낸 사건과 살아 있는 신호에만 묶는다.

가장 유력한 설계 후보는 다음과 같다.

1. 서버의 현재 상태를 한 번 받는 **snapshot**으로 시작한다.
2. 이후에는 **SSE(Server-Sent Events)**로 상태·진행·heartbeat 사건을 받는다. 버튼 명령은 일반 HTTPS 요청으로 보내고 결과를 사건으로 되돌려 받는다.
3. 연결 여부, heartbeat의 신선함, 실제 진행 여부, 작업 결과를 서로 다른 값으로 그린다.
4. 사건이 오면 짧은 모션을 한 번 재생한다. heartbeat가 끊기거나 스트림이 닫히면 모션은 즉시 멈춘다.
5. 숫자 70%는 서버 사건이나 명시된 계산 근거가 없으면 움직이지 않는다. 보이지 않는 작업을 시각 효과로 채우지 않는다.

SSE가 명령까지 양방향으로 처리해야 하거나 매우 짧은 지연의 협업 입력이 필요하면 WebSocket을 대안으로 검토한다. 연결할 수 없는 환경에는 long polling을 fallback으로 두되, “요청이 성공했다”를 “에이전트가 진행 중이다”로 해석하지 않는다. [RFC 6202](https://www.rfc-editor.org/rfc/rfc6202.html)는 짧은 polling이 빈 응답에도 왕복을 만들고, long polling은 이벤트·상태·timeout 때까지 요청을 유지한다고 설명한다. [HTML Standard의 SSE 규격](https://html.spec.whatwg.org/dev/server-sent-events.html)은 재연결과 `Last-Event-ID`를 정의하고, [RFC 6455](https://www.rfc-editor.org/rfc/rfc6455)는 WebSocket의 양방향 메시지와 Ping/Pong을 정의한다.

## 2. 12살도 이해하는 화면 이야기

### 2.1 화면에 필요한 여섯 가지 상태

각 에이전트 카드에는 색 하나만 쓰지 말고 **말·아이콘·모양·시간**을 함께 보여 준다.

| 상태 | 쉬운 뜻 | 화면에서 보일 것 | 움직임 |
|---|---|---|---|
| 작업 중 | 지금 실제 작업을 하고 있고 최근 신호가 왔다 | `작업 중`, 현재 단계, 마지막 사건 시각 | 진행 사건이 올 때만 짧게 1회 |
| 대기 | 살아 있지만 다음 일을 기다린다 | `대기`, 마지막 heartbeat 시각 | 정지. 대기 중 걷기 루프 금지 |
| 검수 | 사람의 결정이나 승인을 기다린다 | `검수 필요`, 질문, 선택지 | 질문 사건 때만 강조 |
| 멈춤/신호 오래됨 | 화면이 최근 소식을 받지 못했다 | `신호 오래됨`, 몇 초 전 | 즉시 정지 + amber 경고 |
| 실패 | 작업이 실패했거나 실패 사건을 받았다 | `실패`, 원인, 재시도/로그 | 정지. 오류 강조는 한 번 |
| 오프라인 | 연결을 닫았거나 세션이 끝났다 | `오프라인`, 종료 시각 | 정지 |

“초록색 점이 켜져 있다”는 말만으로는 작업 중인지 알 수 없다. **연결이 열림**은 우편함이 열려 있다는 뜻이고, **heartbeat**는 에이전트가 아직 응답한다는 뜻이며, **진행 사건**은 실제로 한 단계가 바뀌었다는 뜻이다. 이 셋을 합치면 또다시 70% 고정 같은 오해가 생긴다.

### 2.2 공간 배치 후보

한 화면의 큰 구조는 다음처럼 고정한다.

```text
┌─────────────────────────────────────────────────────────┐
│ LIVE BOARD   전체 신호: 정상/오래됨   마지막 사건 12:04:31 │
├──────────┬──────────────────────────────┬───────────────┤
│ 팀/필터  │        에이전트 마을·그리드      │ 선택 카드      │
│          │  [agent] [agent] [agent]       │ 상태           │
│ 작업중 3 │  [agent] [검수] [실패]          │ 마지막 사건     │
│ 검수 1   │  게시판/퀘스트 보드(고정 위치)     │ 사건 타임라인   │
│ 오래됨 1 │                              │ 명령/결정       │
├──────────┴──────────────────────────────┴───────────────┤
│ 최근 사건: 진행됨 · 검수 요청 · 연결 끊김 · 재연결 · 실패     │
└─────────────────────────────────────────────────────────┘
```

- **상단 HUD**: 전체 연결과 데이터 신선함만 표시한다. 작업률을 여기에 섞지 않는다.
- **중앙 월드/그리드**: 캐릭터는 선택된 카드와 1:1로 연결한다. 화면 장식용 NPC는 실제 에이전트로 오해되지 않게 별도 표기한다.
- **오른쪽 검사판**: 선택한 에이전트의 상태, 마지막 heartbeat, 마지막 진행 사건, 현재 작업, trace/run 링크, 명령을 보여 준다.
- **하단 사건 레일**: 가장 최근의 실제 사건만 보여 주며, 새 사건이 오면 위로 쌓인다. heartbeat를 매번 사람에게 알리는 알림으로 만들지 않는다.
- **게시판**: 데이터가 늘어도 좌표를 바꾸지 않는 고정 anchor다. 게시판을 “남는 빈 공간”에 자동 배치하면 이전 검증의 위치 불일치가 다시 생긴다.

## 3. 현재 문제를 설계 규칙으로 번역하기

| 검증 관찰 | 왜 나쁜가 | 설계 규칙 | 확인 방법 |
|---|---|---|---|
| 70%에 고정 | 숫자가 진짜 진행인지 장식인지 구별할 수 없다 | 서버가 보낸 `progress` 또는 계산 가능한 단계 수가 있을 때만 변경. 근거와 시각을 함께 표시 | 사건 replay로 0→25→70→100 확인; 사건 없을 때 고정 확인 |
| 2초 polling이 살아 있는지 모름 | 응답 성공·캐시·연결 유지가 에이전트 진행을 보장하지 않는다 | `transport`, `heartbeat`, `progress`, `result`를 별도 필드로 표시 | 네트워크를 끊고 시계·상태·모션이 stale로 바뀌는지 확인 |
| 가짜 작업 모션 | 사용자가 실제 작업이 계속된다고 믿는다 | 모션은 사건+heartbeat watchdog의 허가가 있을 때만 재생 | heartbeat만 보내고 이동이 없는지, heartbeat 중단 즉시 멈추는지 확인 |
| 배경과 맞지 않는 캐릭터 | 화면이 한 세계처럼 보이지 않고 에이전트 식별이 어려워진다 | 공통 base grid, palette, 광원, ground plane, scale, anchor를 먼저 정한다 | 모든 캐릭터를 같은 배경 위에서 비교 |
| 게시판 위치 불일치 | 사용자가 기능을 찾을 때마다 눈을 탐색해야 한다 | 게시판은 고정 좌표·고정 크기·고정 제목을 가진다 | 화면 크기와 필터 변경 뒤에도 anchor 확인 |
| 낡고 투박한 UI | 픽셀아트가 정보 계층을 해결해 주지 않는다 | 현대 HUD의 계층(현재 상태→신선함→진행→명령)을 픽셀 스타일 위에 적용 | 5초 안에 작업/오래됨/검수/실패를 찾는 사용성 테스트 |

## 4. 실시간 통신 후보 조사

### 4.1 비교

| 방법 | 강점 | 약점 | 이 화면에서의 역할 후보 |
|---|---|---|---|
| SSE | HTTP 기반, 서버→브라우저 단방향 사건 스트림, 자동 재연결, `id`/`Last-Event-ID`로 누락 회복 가능 | 클라이언트→서버 채널이 별도이고 브라우저·도메인당 연결 수를 살펴야 함 | 기본 후보: snapshot + SSE + HTTPS 명령 |
| WebSocket | 한 연결에서 양방향 메시지, 협업 입력·명령에 적합 | 재연결·순서·인증·backpressure·heartbeat 계약을 애플리케이션이 더 많이 설계해야 함 | 명령과 사건을 같은 저지연 채널로 묶어야 할 때 |
| Long polling | 일반 HTTP만으로 가능, 방화벽·구형 환경에 유리 | 매 요청 오버헤드, timeout·중복·재시도·부하 관리가 필요 | SSE/WS가 막힐 때 fallback 또는 초기 조사용 |
| 2초 일반 polling | 이해하기 쉽고 구현이 단순 | “2초마다 응답”이 실제 이벤트·heartbeat·진행을 뜻하지 않음. 캐시와 지연을 숨길 수 있음 | 최후의 fallback. freshness와 revision 없이는 사용하지 않음 |

MDN은 SSE를 `text/event-stream`으로 전달하며 이벤트 블록이 빈 줄로 끝난다고 설명한다. SSE 연결이 닫히면 기본적으로 다시 연결하고, `id`가 있으면 재연결 요청에 마지막 ID가 사용된다. 단, SSE 연결이 열려 있다는 사실 자체는 최근 이벤트가 들어왔다는 뜻이 아니다. [MDN SSE 사용법](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events), [HTML Standard SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html)을 근거로 이 구분을 화면 데이터 모델에 넣는다.

RFC 6455의 Ping은 keepalive 또는 상대가 응답하는지 확인하는 용도로 사용할 수 있고, Pong은 요청의 payload를 되돌린다. WebSocket을 쓰더라도 브라우저 UI에는 `transportConnected`, `lastHeartbeatAt`, `lastProgressAt`를 별도로 내보내는 애플리케이션 사건이 필요하다. [RFC 6455 §5.5.2–5.5.3](https://www.rfc-editor.org/rfc/rfc6455.html#section-5.5.2)을 참조한다.

### 4.2 추천 연결 흐름

```text
브라우저 ── GET snapshot ───────────────▶ projection API
브라우저 ◀─ snapshot(revision=41) ────── projection API
브라우저 ── GET /events (SSE) ─────────▶ event gateway
브라우저 ◀─ heartbeat(id=42) ─────────── event gateway
브라우저 ◀─ progress(id=43) ──────────── event gateway
브라우저 ── POST command ───────────────▶ command API
브라우저 ◀─ command.accepted(id=44) ─── event gateway
브라우저 ◀─ command.completed(id=45) ── event gateway
```

초기 snapshot과 사건의 `revision`이 이어지지 않으면 화면은 낡은 snapshot 위에 새 사건을 올릴 수 있다. 따라서 `snapshotRevision=41` 다음에는 42부터 받는지 확인하고, 빠진 ID가 있으면 stream을 재연결하거나 snapshot을 다시 받는다.

## 5. 진짜로 “살아 있음”을 보여 주는 데이터 모델

### 5.1 네 가지 시계

한 에이전트에 다음 시각을 저장한다.

```text
lastEventObservedAt   = 브라우저가 사건을 받은 시각
lastEventOccurredAt   = 서버/에이전트에서 사건이 발생한 시각
lastHeartbeatAt       = 에이전트가 살아 있다고 확인된 마지막 시각
lastProgressAt        = 실제 단계가 바뀐 마지막 시각
```

화면에서 “마지막 사건 3초 전”은 `observedAt` 기준으로, “에이전트가 5초 전까지 응답”은 `heartbeatAt` 기준으로, “진행이 2분 동안 없음”은 `progressAt` 기준으로 보여 준다. 출처 시각과 관측 시각을 구별하라는 생각은 OpenTelemetry Logs의 `Timestamp`(사건 발생 시각)와 `ObservedTimestamp`(수집 시스템이 본 시각) 모델과 맞닿아 있다. [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/), [OpenTelemetry Events semantic conventions](https://opentelemetry.io/docs/specs/semconv/general/events/)을 참고한다.

### 5.2 연결·생존·진행은 다르다

```text
transportConnected:  네트워크 채널이 열려 있는가?
heartbeatFresh:      에이전트의 최근 heartbeat가 허용 시간 안인가?
progressFresh:       작업 단계 사건이 최근에 왔는가?
resultKnown:          성공/실패/검수 결과가 확정되었는가?
```

Kubernetes도 liveness와 readiness를 서로 다른 목적으로 정의한다. liveness는 프로세스가 죽었거나 deadlock인지, readiness는 요청을 받아도 되는지 판단한다. 이 구분을 대시보드에 적용하면 “연결됨=작업 중”이라는 잘못된 표현을 피할 수 있다. [Kubernetes Liveness, Readiness, and Startup Probes](https://kubernetes.io/docs/concepts/workloads/pods/probes/)는 특히 “프로그램이 실행되지만 progress하지 않는 deadlock”을 liveness와 구분해 설명한다.

### 5.3 freshness 정책 후보

heartbeat 간격을 서버가 `H`로 알려 준다고 가정한다. 실제 숫자는 운영 환경에서 측정해 정한다.

```text
fresh:  age(lastHeartbeatAt) ≤ 2H + networkJitter
stale:  2H + jitter < age ≤ 4H + jitter
dead:   age > 4H + jitter 또는 stream close/error
```

이것은 표준이 아니라 **설계 후보**다. 숨은 `setInterval(2000)`보다 계약된 heartbeat 간격과 서버 revision이 검증 가능하다. 네트워크 지연·브라우저 절전·탭 비활성화 때문에 경계값에 유예를 둔다. [Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API)처럼 탭이 보이는지 여부도 별도 진단 값으로 기록하되, 숨은 탭에서 받은 오래된 응답을 새 이벤트로 간주하지 않는다. `stale`은 “실패 확정”이 아니라 “최근 신호를 못 봄”이며, `dead`도 서버가 명시한 종료 사건과 구분한다.

## 6. 사건(event)과 projection

### 6.1 사건 envelope 후보

```json
{
  "id": "run-17:000043",
  "type": "agent.progressed",
  "schemaVersion": 1,
  "occurredAt": "2026-08-09T03:04:31.200Z",
  "observedAt": "2026-08-09T03:04:31.420Z",
  "sequence": 43,
  "revision": 43,
  "runId": "run-17",
  "agentId": "agent-a",
  "teamId": "team-red",
  "traceId": "…",
  "payload": {
    "step": "검수 자료 모으기",
    "completed": 3,
    "total": 5,
    "progress": 60
  }
}
```

필수에 가까운 필드: `id`, `type`, `schemaVersion`, `occurredAt`, `sequence/revision`, 대상 ID, payload. `observedAt`은 서버가 아니라 클라이언트가 기록할 수도 있다. 개인정보나 비밀 명령 내용을 사건 레일에 그대로 노출하지 않고, 안전한 요약과 권한 검사를 둔다.

권장 사건 종류:

- `agent.registered`, `agent.started`, `agent.paused`, `agent.waiting`
- `agent.heartbeat`
- `agent.progressed` (단계가 실제로 바뀐 경우)
- `agent.tool_started`, `agent.tool_finished`
- `agent.review_requested`, `agent.decision_recorded`
- `agent.failed`, `agent.stopped`, `agent.finished`
- `command.accepted`, `command.rejected`, `command.cancelled`
- `stream.reconnected`, `stream.gap_detected`

`heartbeat`는 생존 확인용이라 progress를 올리지 않는다. `progressed`가 실제 수치와 기준을 포함하지 못하면 70% 바를 움직이지 않는다.

### 6.2 event-sourced projection은 무엇인가

원본 사건을 저장하고 그 순서로 현재 카드를 계산하는 **projection**을 사용하면, 화면의 상태를 다시 재생할 수 있다. 사용자는 “왜 70%인가?”를 마지막 progress 사건과 계산 근거에서 확인한다.

```text
snapshot(revision 41)
  + heartbeat(42)       → live=true, progress unchanged
  + progressed(43, 60)  → progress=60, motion=one-shot
  + review_requested(44)→ status=review, motion=one-shot
  + stream gap          → stale=true, replay/snapshot 요청
```

클라이언트 projection은 순서를 보장하고 중복 ID를 무시하며, 이미 지난 `revision`은 적용하지 않는다. 사건이 너무 늦게 도착하면 `occurredAt`과 `observedAt`을 둘 다 보여 주거나 “늦게 도착한 사건”으로 표시한다.

### 6.3 리셋·중복·순서 뒤바뀜

- 같은 `id`가 다시 오면 한 번만 적용한다.
- `sequence`가 건너뛰면 임시로 `syncing`을 보이고 누락 사건 replay를 요청한다.
- 종료 사건 뒤의 오래된 progress는 무시한다.
- 서버 시계와 클라이언트 시계가 다를 수 있으므로 freshness 계산은 클라이언트가 받은 시각과 서버 heartbeat의 TTL 계약을 함께 사용한다.
- SSE가 끊긴 뒤 `Last-Event-ID`를 보내 재개한다. 서버가 replay를 보장하지 않으면 snapshot을 다시 받고 revision을 맞춘다. [HTML Standard의 Last-Event-ID 규칙](https://html.spec.whatwg.org/multipage/server-sent-events.html#last-event-id)을 근거로 한다.

## 7. 애니메이션 진실 표(truth table)

핵심 규칙은 **사건이 있을 때만 움직이고, heartbeat가 끊기면 즉시 멈추는 것**이다. heartbeat는 “걸어라” 명령이 아니라 모션 watchdog의 생존 조건이다.

| 실제 신호 | 상태 | 캐릭터/아이콘 | 숫자·바 | 사건 레일 |
|---|---|---|---|---|
| 연결 직후, 아직 사건 없음 | 연결 중 | 정지 프레임 + 작은 연결 아이콘 | `—`, 계산하지 않음 | 연결 시작 1회 |
| heartbeat만 도착 | 대기 또는 기존 상태 유지 | heartbeat 순간 1회 미세 pulse 가능, 반복 루프 금지 | 그대로 | heartbeat를 매번 큰 알림으로 만들지 않음 |
| `progressed` 도착 + heartbeat fresh | 작업 중 | 해당 사건에 맞는 1회 burst/짧은 이동 | payload 근거가 있을 때만 갱신 | 진행 사건 1건 |
| tool started/finished 도착 | 작업 중/단계 전환 | 사건에 맞는 1회 모션 | 단계·시간을 갱신 | 도구 사건 |
| heartbeat 중단 또는 stream error | 신호 오래됨 | **현재 프레임에서 즉시 정지** | 마지막 확정값 유지, `stale` 배지 | 연결 오류 1회 |
| review requested 도착 | 검수 | 정지 + 검수 배지 강조 1회 | 진행값 고정 | 질문과 선택지 |
| failed 도착 | 실패 | 정지 + 오류 아이콘 1회 | 실패 전 마지막 확정값 | 실패 원인 |
| finished 도착 | 완료 | 완료 효과 1회 후 정지 | 100%는 사건에 근거할 때만 | 완료 사건 |
| 오래된 사건이 늦게 도착 | 사건 지연 | 모션 재생 금지 또는 “늦게 도착” 1회 표시 | revision 규칙에 따라 무시/재동기화 | 지연 표시 |

모션 허가의 설계 식은 다음처럼 표현할 수 있다.

```text
motionAllowed =
  authoritativeEventForMotion
  AND heartbeatAge ≤ staleThreshold
  AND streamState != {closed, error, stale}
  AND NOT prefersReducedMotion
```

`authoritativeEventForMotion`은 서버 사건이 발행한 짧은 `motionToken` 또는 사건 타입으로 만든다. 단순 CSS `animation: walk 2s infinite`를 카드의 상태와 함께 켜 두지 않는다. heartbeat가 중단되면 watchdog은 다음 렌더 틱(목표 1 frame)에서 모션 클래스를 제거하고, `stale` 배지를 보인다. 네트워크 종료 이벤트를 받지 못한 경우에도 freshness timer가 모션을 끝낸다.

### 7.1 가짜 진행 금지 규칙

- AI가 “생각 중”이라는 문장만 보냈다면 progress가 아니다.
- 70%라는 숫자가 반복되어도 새 `progressed` 사건·근거가 없으면 숫자를 변경하지 않는다.
- 시간에 따라 자동으로 올라가는 progress bar는 사용하지 않는다. 예상 시간은 실제 측정값과 구분해 `예상`으로 표시한다.
- “작업 중”은 `started` 후 heartbeat가 fresh일 때만 유지한다.
- heartbeat가 계속 와도 progress 사건이 없으면 “살아 있음, 진행 새로 없음”으로 표시한다.

## 8. 모던 게임 HUD와 픽셀아트 후보

### 8.1 HUD의 정보 우선순위

게임 HUD 연구는 HUD가 플레이어와 시스템 사이의 상호작용을 담당하고, 정보가 시선과 수행에 영향을 준다는 점을 보여 준다. 한국 연구의 eye-tracking 기반 [HUD Recognition Analysis of Expert Game User](https://journal.kci.go.kr/kkits/archive/articleView?artiId=ART001782257)와 FPS 정보 표시를 비교한 [An empirical comparison of first-person shooter information displays](https://www.sciencedirect.com/science/article/pii/S1875952117300435)를 참고한다. 이 자료는 특정 게임을 복제하라는 뜻이 아니라, 정보가 화면에 놓인 위치·형태·주의 비용을 검증해야 한다는 근거로 사용한다.

우선순위는 다음과 같다.

1. 지금 위험한가? (`실패`, `신호 오래됨`)
2. 누가 사람을 기다리는가? (`검수`)
3. 최근 실제로 무엇이 바뀌었나? (`마지막 사건`)
4. 작업은 어느 단계인가? (`진행`)
5. 내가 무엇을 할 수 있나? (`중지`, `재시도`, `승인`, `질문 답하기`)

픽셀 장식은 이 우선순위를 가리지 않아야 한다. 배경 파티클, 흔들리는 장식, 자동으로 걷는 NPC는 관측 사실과 섞이지 않도록 숨기거나 정적 장식으로 둔다.

### 8.2 배경-캐릭터 일치 체크리스트

기존 자산을 복제하지 않고 원본 픽셀아트를 만든다는 전제에서 다음 스타일 계약을 만든다.

- logical pixel grid: 모든 캐릭터·타일·아이콘이 같은 기준 그리드 사용
- palette: 배경·캐릭터·상태 색이 공유하는 제한 팔레트와 상태 전용 accent를 정의
- light direction: 그림자와 하이라이트가 같은 방향
- ground plane: 발 위치가 같은 바닥선/타일에 닿음
- scale: 캐릭터의 머리·몸·타일 크기 비율 고정
- outline: 외곽선 두께와 색의 규칙 고정
- anchor: sprite의 발/중심/선택 링 위치를 metadata로 고정
- density: 배경이 복잡하면 캐릭터 실루엣을 단순하게 유지

“배경과 안 맞는 캐릭터”는 더 예쁜 캐릭터를 추가해서 해결하지 않는다. 먼저 하나의 16×16 또는 32×32 기준 grid에 배경 타일, 상태 아이콘, 캐릭터 실루엣을 놓고 값(밝기)과 scale을 비교한다.

### 8.3 픽셀-perfect 렌더링

CSS `image-rendering`은 확대 시 픽셀 경계를 보존하기 위한 힌트다. MDN의 [Crisp pixel art look](https://developer.mozilla.org/en-US/docs/Games/Techniques/Crisp_pixel_art_look)과 [image-rendering](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/image-rendering), W3C [CSS Images Module Level 3](https://www.w3.org/TR/css-images-3/)를 근거로 한다.

설계 후보:

- 작은 논리 화면(예: 320×180)을 정의한 뒤 정수 배율로 확대한다.
- `image-rendering: pixelated`를 시도하되 브라우저별 차이를 screenshot으로 확인한다.
- 1 CSS px 단위의 fractional translate, 흐릿한 transform, 자동 보간을 피한다.
- 텍스트는 가능하면 DOM 텍스트로 두고, 픽셀아트는 아이콘·배경·캐릭터에 사용한다. WCAG는 이미지 속 텍스트보다 실제 텍스트를 선호한다([WCAG 2.2 1.4.5](https://www.w3.org/TR/WCAG22/#images-of-text)).
- 사용자가 화면을 확대하거나 고대비를 켜도 의미 있는 텍스트와 focus가 사라지지 않게 한다.

### 8.4 원본 asset pipeline 후보

기존 게임 화면을 추출하거나 복제하지 않고, 새로 만든 원본만 사용한다.

```text
style brief → palette/grid sheet → .aseprite source
  → named tags (idle, event-burst, alert, review)
  → PNG atlas + JSON frame metadata
  → visual review (grid/scale/contrast/license)
  → versioned asset manifest + checksum
```

[Aseprite sprite-sheet 문서](https://www.aseprite.org/docs/sprite-sheet/)는 여러 프레임을 한 sprite sheet로 내보내는 방법과 texture atlas 개념을 설명하고, [Aseprite CLI 문서](https://www.aseprite.org/docs/cli/)는 명령줄에서 PNG와 JSON atlas를 만드는 방식을 설명한다. 출처 파일(`.aseprite`), export 설정, 팔레트, 작가/라이선스 기록을 함께 보관해 나중에 어느 프레임이 어느 사건인지 추적한다.

프레임 이름 예:

```text
agent_base_idle_01       # 자동 반복이 아닌 정지 프레임 후보
agent_event_progress_01  # progressed 사건 뒤 1회
agent_event_review_01    # review_requested 사건 뒤 1회
agent_event_failure_01   # failed 사건 뒤 1회
agent_state_stale        # 신호 오래됨 정지 프레임
```

## 9. 사용자가 직접 참여하는 퀘스트·결정 게이트

### 9.1 퀘스트 카드

에이전트가 사람을 기다릴 때 일반 알림보다 **퀘스트 카드**가 의도를 분명히 한다.

```text
QUEST 014 · 데이터 소스 선택
왜: 두 소스의 결과가 달라 다음 단계로 갈 수 없음
근거: 사건 43, 마지막 확인 12:04:31
선택: [소스 A 사용] [소스 B 사용] [추가 조사]
기한: 없음 / 만료 시 자동 중지
```

퀘스트는 실제 `review_requested` 사건에만 생성한다. 선택을 누르면 `decision.pending`으로 바뀌고, 서버가 `decision.recorded`를 보내기 전에는 완료로 꾸미지 않는다.

### 9.2 decision gate 규칙

- 무엇을 결정해야 하는지, 왜 필요한지, 사용 가능한 선택지를 한 문장으로 쓴다.
- 위험하거나 되돌리기 어려운 행동은 확인 dialog를 사용한다.
- 선택한 뒤에는 `pending` 상태를 보여 주고, 승인·거부·충돌을 서버 사건으로 확정한다.
- 가능한 경우 실행 전 예상 효과와 실행 후 실제 결과를 분리한다.
- 자동 실행을 사용자 승인처럼 꾸미지 않는다.

WAI-ARIA Authoring Practices의 [alertdialog 패턴](https://www.w3.org/WAI/ARIA/apg/patterns/alertdialog/)은 중요한 메시지와 응답을 함께 요구하는 대화상자에서 이름·설명·초점 이동을 정의한다. W3C 문서는 dialog가 열릴 때 focus를 내부의 활성 요소로 옮기고 닫힌 뒤 이전 위치로 돌아가야 한다고 안내한다. [ARIA18](https://www.w3.org/WAI/WCAG22/Techniques/aria/ARIA18)도 오류와 수정 방법을 함께 알리는 패턴을 설명한다.

### 9.3 optimistic UI의 제한

되돌릴 수 있는 로컬 선택(예: 필터, 패널 열기)은 즉시 반영해도 된다. 하지만 에이전트 중지, 재시도, 승인, 파일 변경처럼 실제 시스템을 바꾸는 행동은 다음 세 상태를 유지한다.

```text
사용자 클릭 → command.pending (버튼 비활성/취소 가능)
             → command.accepted (서버가 접수)
             → command.completed 또는 command.rejected (사건이 진실)
```

서버가 거부하면 이전 화면으로 되돌리고 이유를 보여 준다. optimistic 상태가 실제 서버 사건보다 오래 남지 않도록 TTL과 reconciliation을 둔다.

## 10. 접근성 및 모션 안전

### 10.1 의미를 색깔에만 맡기지 않기

WCAG 2.2는 일반 텍스트 대비를 4.5:1 이상(큰 텍스트는 3:1)으로 요구하고, 비텍스트 UI 구성요소에도 충분한 대비를 요구한다. [WCAG 2.2 1.4.3 Contrast](https://www.w3.org/TR/WCAG22/#contrast-minimum)와 [1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast/)를 확인한다.

- 작업/검수/실패/오래됨은 색 + 단어 + 아이콘 + 모양으로 표시한다.
- 카드의 border, focus ring, 상태 아이콘은 배경 위에서 구별돼야 한다.
- 색맹 모드에서도 상태가 달라 보여야 한다.
- 선택된 카드와 keyboard focus는 항상 화면에 보인다. Microsoft Xbox 접근성 지침도 focus가 화면 밖이나 보이지 않는 요소로 이동하지 않아야 한다고 설명한다([XAG 113](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/113)).

### 10.2 reduced motion

사용자의 운영체제에 `prefers-reduced-motion: reduce`가 설정되어 있으면 반복 모션과 큰 전환을 줄인다. [MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion)은 이 media query가 접근성 설정을 읽어 적은 모션 규칙을 적용한다고 설명한다. WCAG 2.2의 [2.2.2 Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide)는 자동으로 움직이는 콘텐츠에 중지·숨김 방법을 요구할 수 있음을 설명한다.

후보 정책:

- reduced motion에서는 event burst를 정적 highlight와 텍스트로 바꾼다.
- heartbeat pulse도 끄고 “마지막 heartbeat 3초 전” 텍스트만 남긴다.
- 깜빡임으로 실패를 표현하지 않는다.
- 사용자 설정으로 `모든 캐릭터 모션 끄기`를 제공한다.
- 사건 수신과 상태 갱신은 모션을 꺼도 그대로 유지한다.

## 11. 검증용 시나리오(구현 전 설계 acceptance)

현재 구현 결과가 아니라, 다음을 만들었을 때 통과해야 하는 조사 기준이다.

| 시나리오 | 입력 | 기대 결과 |
|---|---|---|
| 70% 고정 방지 | progress 25, 60만 발행 | 바는 25→60만 바뀌고 각 근거 시각 표시 |
| heartbeat만 생존 | 5초마다 heartbeat, progress 없음 | `살아 있음/진행 새로 없음`; progress와 걷기 루프 없음 |
| heartbeat 중단 | 마지막 heartbeat 뒤 네트워크 차단 | 모션 즉시 정지, stale 배지, 마지막 확정값 유지 |
| 연결만 열림 | SSE open 후 사건 20초 없음 | `연결됨`과 `신선함`을 분리. 작업 중으로 표시하지 않음 |
| progress 사건 | `agent.progressed` 1건 | 모션 1회, 끝나면 정지. 서버 사건 없는 반복 모션 없음 |
| 실패 | `agent.failed` | 정지, 실패 이유와 재시도 명령 표시 |
| 검수 | `review_requested` | 고정된 검수판/게시판에 질문, keyboard focus 이동 |
| 재연결 | 42 이후 연결 끊김, `Last-Event-ID: 42` | 43부터 재생 또는 snapshot 재동기화, 중복 없음 |
| 순서 뒤바뀜 | 44가 43보다 먼저 도착 | revision 규칙으로 보류/재정렬, 잘못된 progress 금지 |
| 명령 거절 | 사용자 승인 클릭 후 서버 reject | pending→rejected, UI rollback, 이유 표시 |
| reduced motion | OS reduce motion | 모션 대신 상태·텍스트·정적 강조 |
| 반응형 | 창 크기·필터·세션 수 변경 | 게시판 위치와 카드 focus anchor 고정 |
| 접근성 | 키보드·스크린리더·고대비 | 상태 이름, live status, focus, 대비 확인 |

### 11.1 핵심 telemetry

관측판 자체도 관측 가능해야 한다.

- `stream_connect_attempts`, `stream_reconnects`, `stream_errors`
- `event_received_total`, `event_duplicate_total`, `event_gap_total`
- `event_lag_ms = observedAt - occurredAt`
- `snapshot_revision`, `last_applied_revision`
- `heartbeat_age_ms`, `progress_age_ms`, `stale_duration_ms`
- `motion_started_from_event_total`, `motion_suppressed_stale_total`
- `command_pending_ms`, `command_rejected_total`

OpenTelemetry는 trace·metric·log를 서로 다른 질문에 답하는 신호로 설명한다. [Observability primer](https://opentelemetry.io/docs/concepts/observability-primer/)는 reliability가 단순히 서비스가 살아 있는지가 아니라 사용자가 기대한 결과를 얻는지와 관련 있다고 말한다. 따라서 `stream connected` metric만 보고 dashboard를 “정상”으로 채우지 말고, 실제 progress/result 사건과 함께 traceId/runId를 연결한다.

## 12. 결정 후보와 열린 질문

### 권장 기본안

**HTTP snapshot + SSE 사건 스트림 + HTTPS 명령 + event-sourced projection**을 1순위로 둔다.

- 서버→브라우저 사건이 주 흐름이라 SSE와 잘 맞는다.
- 명령은 보안·권한·재시도 정책을 일반 요청으로 분리하기 쉽다.
- `id`/`Last-Event-ID`로 재연결을 설계할 수 있다.
- event envelope와 projection을 공유하면 WebSocket이나 polling fallback으로 바꿔도 화면의 의미가 변하지 않는다.

### WebSocket을 선택할 조건

- 사용자가 지속적으로 입력을 보내고 서버도 즉시 응답해야 한다.
- 한 연결에서 명령·사건·협상 상태를 처리할 운영 이유가 있다.
- Ping/Pong과 애플리케이션 heartbeat, 재연결·순서·backpressure를 명시할 팀 역량이 있다.

### 조사 뒤 결정해야 할 것

1. heartbeat의 실제 발행 주기 `H`, stale/dead threshold, 브라우저 절전 정책
2. 사건 replay 보존 기간과 권한별 필터
3. progress의 의미: 단계 개수, 작업량, 시간 추정 중 무엇인지
4. 여러 세션이 같은 에이전트 ID를 재사용할 때의 generation ID
5. 실패/취소/재시도의 최종 상태와 idempotency key
6. 원본 픽셀아트의 grid, 팔레트, sprite atlas 도구, 라이선스 기록 형식
7. keyboard navigation 순서와 screen-reader 문장
8. 실제 Doctori verification 문서의 캡처·재현 단계·성공 기준

## 기술 부록 A. 상태 머신 후보

```text
BOOT
 ├─ snapshot_ok → CONNECTED_IDLE
 └─ snapshot_error → SYNC_ERROR

CONNECTED_IDLE
 ├─ heartbeat → ALIVE_IDLE
 ├─ started/progressed → WORKING
 ├─ review_requested → REVIEW
 ├─ failed → FAILED
 └─ stream_error/timeout → STALE

ALIVE_IDLE
 ├─ progressed → WORKING
 ├─ review_requested → REVIEW
 ├─ stopped → STOPPED
 └─ heartbeat timeout → STALE

WORKING
 ├─ heartbeat → WORKING (모션을 재시작하지 않음)
 ├─ progressed → WORKING (사건마다 1회)
 ├─ review_requested → REVIEW
 ├─ finished → FINISHED
 ├─ failed → FAILED
 └─ heartbeat timeout/stream_error → STALE

REVIEW
 ├─ decision_recorded → WORKING 또는 FINISHED
 ├─ review_cancelled → ALIVE_IDLE
 └─ heartbeat timeout → STALE_REVIEW

STALE / STALE_REVIEW
 ├─ reconnect + snapshot/replay_ok → 해당 확정 상태
 ├─ failed → FAILED
 └─ explicit stopped/expired → STOPPED 또는 OFFLINE
```

상태 머신은 “최근 서버 사건”과 “freshness policy”의 교차 결과다. heartbeat가 한 번 왔다고 `WORKING`으로 바꾸지 않는다.

## 기술 부록 B. 화면 view-model 후보

```ts
type Freshness = "fresh" | "stale" | "dead";
type AgentStatus = "working" | "waiting" | "review" | "failed" | "finished" | "offline";

type AgentProjection = {
  agentId: string;
  sessionId: string;
  teamId: string;
  status: AgentStatus;
  freshness: Freshness;
  transport: "connecting" | "open" | "closed" | "error";
  progress: { value: number; basis: string; revision: number } | null;
  lastEvent: { id: string; type: string; occurredAt: string; observedAt: string } | null;
  lastHeartbeatAt: string | null;
  lastProgressAt: string | null;
  pendingCommand: { id: string; label: string } | null;
  review: { question: string; choices: string[] } | null;
  motion: { token: string; untilMs: number } | null;
};
```

여기서 `transport`, `freshness`, `status`, `progress`는 일부러 각각 존재한다. 하나의 `isActive` boolean으로 합치면 2초 polling 문제를 다시 만든다.

## 기술 부록 C. 화면 문장 후보

- `작업 중 · 최근 진행 사건 4초 전 · heartbeat 2초 전`
- `살아 있음 · 진행 사건 없음 48초 · 마지막 확정 70%`
- `신호 오래됨 · 마지막 heartbeat 14초 전 · 재연결 중`
- `검수 필요 · “어느 데이터 소스를 사용할까요?”`
- `실패 · 권한 없음 · 재시도 또는 로그 열기`
- `완료 · 100% (agent.finished 사건 기준)`

이 문장들은 색을 보지 못해도 상태를 알려 준다. heartbeat가 너무 자주 바뀌어 screen reader가 시끄러워지지 않도록 `aria-live="polite"`에는 상태 전환·진행 사건만 요약하고, heartbeat 시각은 일반 텍스트로 갱신한다. WCAG의 status message 정의와 [4.1.3 Status Messages](https://www.w3.org/WAI/WCAG21/Understanding/status-messages.html)를 참고한다.

## 출처 및 근거 수준

### 표준·브라우저 공식 문서

- [WHATWG HTML Standard — Server-sent events](https://html.spec.whatwg.org/dev/server-sent-events.html): SSE 인터페이스, event stream, 재연결, Last-Event-ID
- [MDN — Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events): `text/event-stream`, custom event, reconnect, 브라우저 제약
- [IETF RFC 6202 — Long Polling and Streaming in Bidirectional HTTP](https://www.rfc-editor.org/rfc/rfc6202.html): short polling·long polling의 latency·overhead·timeout 이슈
- [IETF RFC 6455 — The WebSocket Protocol](https://www.rfc-editor.org/rfc/rfc6455.html): 양방향 메시지, Ping/Pong, keepalive 의미
- [MDN — Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API): 탭 가시성과 백그라운드 상태를 진단 값으로 분리
- [W3C CSS Images Module Level 3](https://www.w3.org/TR/css-images-3/): `image-rendering`과 `pixelated`
- [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/): 대비, 모션, 키보드, status message, 이미지 속 텍스트
- [WAI-ARIA APG — Alert and Message Dialogs](https://www.w3.org/WAI/ARIA/apg/patterns/alertdialog/): 결정 게이트의 dialog·focus 원칙

### 공식 플랫폼·도구 문서

- [Kubernetes — Liveness, Readiness, and Startup Probes](https://kubernetes.io/docs/concepts/workloads/pods/probes/): 생존·준비·진행 정체를 분리하는 운영 모델
- [OpenTelemetry — Observability primer](https://opentelemetry.io/docs/concepts/observability-primer/): reliability와 signals
- [OpenTelemetry — Logs data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/): Timestamp와 ObservedTimestamp
- [OpenTelemetry — Events semantic conventions](https://opentelemetry.io/docs/specs/semconv/general/events/): 사건을 별도 timestamp/severity/occurrence로 표현하는 기준
- [Aseprite — Sprite sheets](https://www.aseprite.org/docs/sprite-sheet/), [CLI](https://www.aseprite.org/docs/cli/): 원본 sprite sheet/atlas export pipeline 후보
- [Microsoft Xbox Accessibility Guideline 113](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/113): 게임 UI focus가 항상 보이는지 검증

### 연구·신뢰 가능한 게임 UI 자료

- [HUD Recognition Analysis of Expert Game User](https://journal.kci.go.kr/kkits/archive/articleView?artiId=ART001782257): eye-tracking으로 게임 HUD 정보 인지 특성 조사
- [An empirical comparison of first-person shooter information displays](https://www.sciencedirect.com/science/article/pii/S1875952117300435): HUD·diegetic·spatial 표시의 수행 비교
- [Entertainment Computing — HUDS](https://www.csit.carleton.ca/~rteather/pdfs/Entertainment-Computing-HUDS.pdf): 게임 HUD에 시각화 원리를 적용한 연구 검토
- [GDC 2024 — Making Games Accessible with Indie](https://media.gdcvault.com/gdc2024/Slides/GDC%2Bslide%2Bpresentations/MMacLean_MakingGamesAccesible_GDC2024v3.0.pdf): 게임 접근성 실무 발표 자료

출처를 적용한 부분과 자체 제안은 구분한다. 표준 문서는 동작·접근성 요구의 근거이고, event-sourced projection, freshness 임계값, truth table, HUD 배치는 위 자료와 사용자 문제를 바탕으로 한 이 설계의 제안이다. 임계값 `2H/4H`, 논리 해상도, 카드 배치는 실제 traffic·기기·사용자 테스트로 검증해야 한다.
