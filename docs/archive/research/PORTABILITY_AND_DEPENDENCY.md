# graphori 이식성 조사: Orca 없이도 굴러가게 만들기

> 조사 성격: **설계 단계 전용 조사 문서입니다. 아무 코드도 구현하지 않았습니다.**
> 조사일: 2026-08-09
> 목표: Orca 안에서는 기능이 풍부하게 동작하지만, 일반 macOS 터미널이나 Windows PowerShell 터미널에서도 핵심 기능이 그대로 동작하는 구조를 설계하기 위한 근거 자료.

---

## 0. 이 문서는 무엇인가요? (쉬운 설명)

graphori는 여러 AI 에이전트(로봇 일꾼)를 동시에 굴려서 코드를 만들게 하는 프로그램이 될 예정이에요. 지금 이 프로그램은 "Orca"라는 특별한 프로그램(고급 IDE) 안에서 실행되고 있어요.

Orca 안에는 "오케스트레이션(orchestration)"이라는 아주 편리한 기능들이 이미 만들어져 있어요. 일꾼들끼리 메시지를 주고받고, 할 일을 나눠주고, 완료됐는지 확인하고, 심지어 웹 브라우저까지 대신 조작해줘요.

문제는 이거예요: **이 편리한 기능들은 전부 Orca라는 앱이 켜져 있어야만 동작해요.** 만약 나중에 graphori를 그냥 macOS 터미널이나 Windows PowerShell에서, Orca 없이 실행하고 싶다면 어떻게 될까요? 지금 구조로는 아무것도 안 돌아가요.

그래서 이 문서는 이렇게 물어봐요:
- Orca가 주는 편리한 기능들을 하나하나 뜯어보면 몇 개나 될까?
- 그중에서 graphori가 **진짜로 꼭 필요한** 기능은 뭘까?
- Orca 없이 **똑같은 역할**을 하는 더 간단한 방법이 있을까?
- 있다면, 그 간단한 방법을 기본으로 삼고 Orca는 "있으면 더 좋은 보너스"로 만들 수 있을까?

결론부터 말하면: **가능합니다.** Orca의 기능 대부분은 "일꾼에게 일을 시키고, 살아있는지 확인하고, 끝났는지 알려주고, 기록을 남기는" 매우 단순한 원리 위에 서 있어요. 이 원리는 파일 하나(글 목록처럼 한 줄씩 기록하는 파일)와 평범한 프로그램 실행만으로도 충분히 흉내 낼 수 있어요. 반대로 "Orca 안에 있는 브라우저를 대신 조작하기"처럼 Orca라는 앱 자체가 있어야만 가능한 기능도 있어요. 이런 건 처음부터 "덤"으로 취급해야 해요.

---

## 1. 큰 그림: 콘센트와 전자제품 비유

전자제품(TV, 청소기)을 생각해보세요. 좋은 제품은 "표준 220V 콘센트"에도 꽂히고, "자동차 시가잭"에도 꽂혀요. 제품 안의 진짜 기능(TV가 화면을 보여주는 것)은 전기가 어디서 오는지와 상관없이 똑같이 동작해야 해요. 대신 "콘센트 어댑터"만 바꿔 끼우면 되죠.

graphori도 똑같이 만들 수 있어요.

- **진짜 알맹이(핵심 로직)**: "할 일을 여러 조각으로 나누고, 일꾼에게 맡기고, 진행 상황을 기록하고, 끝난 걸 확인한다" — 이건 어디서 실행되든 똑같아야 해요.
- **콘센트 어댑터(포트-앤-어댑터, ports and adapters)**: 이 알맹이가 "일꾼을 시작시켜라", "지금 살아있는지 확인해라", "결과를 저장해라" 같은 요청을 밖으로 내보내면, 그 요청을 실제로 처리하는 방법은 환경마다 다르게 꽂을 수 있어요.
  - Orca 어댑터: `orca` CLI를 호출해서 Orca가 대신 처리하게 함 (브라우저 조작, 예쁜 대시보드까지 포함)
  - 일반 터미널 어댑터: 그냥 운영체제의 기본 명령어(프로세스 실행, 파일 쓰기)만 사용

이 설계 방식은 새로 발명한 게 아니라, 소프트웨어 업계에서 "헥사고날 아키텍처(육각형 구조)" 또는 "포트-앤-어댑터"라고 부르는, 2005년에 Alistair Cockburn이 정리한 아주 오래되고 검증된 방법이에요. (근거: 부록 B)

---

## 2. Orca 오케스트레이션 기능, 하나씩 뜯어보기 (쉬운 설명)

실제로 이 컴퓨터에 설치된 `orca` 프로그램을 열어서, 어떤 명령어들이 있는지 전부 확인했어요. 그 결과를 사람이 이해하기 쉬운 말로 옮기면 이래요.

| Orca 용어 | 쉬운 설명 |
|---|---|
| **Run** | "이번 작업 전체를 담는 우편함" 같은 거예요. 여러 메시지와 할 일이 이 우편함 하나에 모여요. |
| **Task** | "해야 할 일 하나". 다른 Task가 먼저 끝나야 시작할 수 있는 "선행 조건(deps)"도 걸 수 있어요. 상태는 대기중 → 준비됨 → 맡겨짐 → 완료/실패/막힘, 이렇게 바뀌어요. |
| **Dispatch** | "이 Task를 이 일꾼에게 맡겼다"는 영수증. Task 하나를 누구에게 맡겼는지 정확히 기록해요. |
| **Message (send/check/reply/ask/inbox)** | 일꾼들끼리 편지를 주고받는 기능. "질문(question)"을 보내면 대장이 "답장(reply)"을 해줘요. 여러 명에게 한 번에 보낼 수도 있어요(`@all`, `@idle` 같은 단체 주소). |
| **worker_done** | 일꾼이 "저 다 했어요! 성공/실패했어요!"라고 딱 한 번 보고하는 마지막 편지예요. |
| **heartbeat** | 일꾼이 "저 아직 살아서 일하고 있어요"라고 주기적으로 보내는 짧은 신호예요. |
| **decision_gate (Gate)** | 여러 일 중 하나가 "이 갈림길에서 대장이 결정해줘야 다음으로 넘어갈 수 있어요"라고 멈춰서 기다리는 것. |
| **Terminal** | 일꾼이 실제로 명령어를 치는 "가짜 화면(PTY)"이에요. 여기에 글자를 보내고, 화면 내용을 읽고, "다 조용해졌는지(tui-idle)" 확인할 수 있어요. |
| **Browser** | Orca 안에 내장된 브라우저 창을 대신 클릭하고 타이핑해주는 기능이에요. 마우스 좌표가 아니라 "이 버튼(e3)"처럼 접근성 트리 이름으로 찾아서 클릭해요. |

이 컴퓨터에서 직접 확인해보니, Orca의 이 모든 기능은 사실 **Orca 앱이 켜져 있고, `orca orchestration` 명령이 살아있는 런타임에 원격 호출(RPC)을 보내는** 방식으로 동작해요. Orca가 안 켜져 있으면 `orca status` 자체가 실패하고, 그러면 어떤 orchestration 명령도 못 써요. (근거: 부록 A)

또한 Orca는 실제로 자기 상태를 **SQLite 데이터베이스 파일**(`orchestration.db`)에 저장하고 있었어요. 파일의 맨 앞부분을 열어보니 "SQLite format 3"라는 표시가 그대로 찍혀 있었어요. 터미널에서 나온 출력물은 `output.log`라는 순수 텍스트 파일 + `meta.json`이라는 작은 설명 파일 두 개로 나눠서 저장하고 있었고요. 이건 저희가 이 문서에서 제안할 "일반 터미널 어댑터" 설계와 원리가 거의 똑같아요 — Orca조차 결국 "파일 몇 개 + 작은 데이터베이스"로 상태를 저장하는 거예요. 다른 점은 그 파일들을 **Orca 앱 자신만** 읽고 쓸 수 있고, 밖에서는 `orca` CLI를 거쳐야만 접근할 수 있다는 점이에요.

---

## 3. graphori에게 정말 필요한 건 뭘까?

기능을 뜯어보니, 사실 이 기능들은 두 가지로 나뉘어요.

### (A) "일꾼 관리"의 본질 — 어디서든 있어야 하는 것
- 할 일을 조각내고 순서를 정한다 (Task, 선행 조건)
- 조각을 일꾼에게 맡긴다 (Dispatch)
- 일꾼이 살아있는지 안다 (heartbeat)
- 일꾼이 끝났는지, 성공했는지 안다 (worker_done)
- 일꾼을 취소할 수 있다
- 무슨 일이 있었는지 기록이 남는다 (evidence, 로그)
- 얼마나 토큰(비용)을 썼는지 안다
- 진행 상황을 한눈에 볼 수 있다 (대시보드)

이건 **Orca가 없어도** 반드시 있어야 하는, graphori의 진짜 알맹이예요. 이 중 어느 것도 "Orca 앱이 켜져 있어야만" 가능한 문제가 아니에요. 그냥 "여러 프로그램이 동시에 돌아가는데 서로 소통하고 기록을 남기는" 문제일 뿐이고, 이건 컴퓨터가 생긴 이래로 계속 풀어온 아주 흔한 문제예요.

### (B) "Orca이기 때문에 가능한" 보너스
- Orca 안에 내장된 브라우저를 자동으로 클릭/타이핑
- Orca IDE의 사이드바에 예쁘게 그려지는 시각적 상태
- Git worktree(작업 폴더 분신)를 Orca가 자동으로 만들어주는 것
- 여러 대의 컴퓨터(다른 Orca 서버)에 원격으로 일꾼을 보내는 것

이건 Orca라는 특정 앱의 UI/런타임과 강하게 묶여 있어서, Orca가 없는 환경에서는 아예 존재할 수 없는 기능이에요. 이런 건 "있으면 좋은 것"으로 분류하고, 없어도 graphori의 핵심 동작은 절대 망가지면 안 돼요.

---

## 4. 기능별 의존도 표 (Core / Orca 전용 / 일반 터미널 대체 / 선택적 보너스)

아래 표가 이 문서의 핵심 결론이에요. 4단계로 나눴어요.

- **core 필수**: Orca가 있든 없든 graphori 알맹이가 무조건 가지고 있어야 하는 개념/데이터. (구현체가 아니라 "포트")
- **Orca adapter**: Orca 환경에서 그 개념을 구현하는 방법
- **generic terminal adapter**: macOS/Windows 순정 터미널에서 그 개념을 구현하는 방법
- **optional enhancement**: 있으면 좋지만 없어도 core 동작에 지장 없는 것

| # | 기능 | core 필수 개념 | Orca adapter | generic terminal adapter | optional enhancement |
|---|---|---|---|---|---|
| 1 | Run | 작업 묶음 식별자(run_id) + 이벤트 로그 | `orca orchestration run-create/-use/-list/-show` (RPC, `orchestration.db`) | 로컬 디렉터리 `.graphori/runs/<run_id>/` + `events.jsonl` | Orca 사이드바 시각화 |
| 2 | Task / DAG | task_id, spec, deps(선행조건), status 상태기계 | `task-create/-list/-update` | 이벤트 로그에서 파생되는 상태(`task_created`, `task_status_changed`), 필요하면 SQLite로 캐시 | GitHub Actions 워크플로 매트릭스로 DAG 시각화 |
| 3 | Dispatch | "task_id + 실행 주체" 바인딩 1건 | `dispatch`, `worker-start/-show/-read` | 로컬 프로세스 PID + 로그 경로를 이벤트로 기록 | 원격 서버로 위임(`--on <env>`) |
| 4 | 메시지(send/reply/ask) | 발신자→수신자, 타입, 스레드 | `orchestration send/check/reply/ask/inbox` | 같은 `events.jsonl`에 append + 파일 변경 감시(폴링 또는 OS 파일워처) | SSE/WebSocket으로 실시간 푸시 |
| 5 | worker_done | 정확히 1회, outcome(성공/실패) 필수 | `send --type worker_done --outcome ...` | 이벤트 append `{"type":"worker_done","outcome":...}` + 종료 코드 검증 | — |
| 6 | heartbeat | task_id/dispatch_id + timestamp | `send --type heartbeat` | 이벤트 append 또는 `control/<id>.heartbeat` 파일의 mtime 갱신 | — |
| 7 | decision_gate | 사람/대장의 결정 대기 상태 | `gate-create/-resolve/-list` | 이벤트 `gate_created` + `gate_resolve` (blocking read) | — |
| 8 | Terminal(PTY) | 자식 프로세스 입출력 캡처, 종료 감지 | Orca 내장 PTY, `terminal read/send/wait` | 일반 프로세스 실행 + stdout/stderr 파일 리다이렉션. 사람이 직접 볼 화면이 필요할 때만 진짜 PTY(node-pty/ConPTY) 사용 | tmux/zellij 세션으로 여러 창 동시 관찰 |
| 9 | Browser 자동화 | (선택 기능, core 아님) | Orca 내장 브라우저 접근성 스냅샷 | 없음 — 필요하면 표준 Playwright/CDP를 별도 어댑터로 붙임 | — |
| 10 | Cancellation(취소) | "이 dispatch를 멈춰라" 신호 | `worker-stop`, `worker-abandon` | `control/<dispatch_id>.cancel` 신호 파일 생성(원자적 rename) 후 프로세스에 종료 신호 전달 | — |
| 11 | Token usage(토큰 사용량) | dispatch별 누적 토큰/비용 | 에이전트 CLI가 출력하는 usage JSON을 orchestration이 받아 기록 | 에이전트 CLI(Claude Code, Codex) stdout의 usage 필드를 파싱해 이벤트로 append | 비용 대시보드 그래프 |
| 12 | Evidence(증거/산출물) | dispatch가 만든 파일/로그의 위치와 요약 | `--files-modified`, `--report-path` | `.graphori/runs/<run_id>/evidence/<dispatch_id>/` 디렉터리 + 이벤트에 경로 기록 | — |
| 13 | Dashboard(대시보드) | 현재 Run/Task/Dispatch 상태를 사람이 볼 수 있게 | Orca IDE UI | `events.jsonl`을 읽어 상태를 재구성하는 CLI(`graphori status`) 또는 정적 HTML + SSE | 웹 대시보드(WebSocket 실시간 갱신) |

**표를 읽는 법**: "core 필수" 칸에 적힌 개념만 있으면 graphori는 어디서든 동작해요. "Orca adapter"와 "generic terminal adapter"는 같은 core 개념을 서로 다른 방식으로 채워 넣는 두 가지 방법일 뿐이에요. "optional enhancement"는 둘 다 없어도 전혀 문제없는, 진짜 보너스예요.

---

## 5. orca-cli / orchestration skill이 꼭 있어야 하나요?

**결론: 부분 의존 (PARTIAL) — core 실행 로직은 NO, 특정 보너스 기능만 YES.**

이렇게 결론 낸 근거는 Orca 공식 오케스트레이션 스킬 문서의 문장을 직접 확인했기 때문이에요. 원문에는 이렇게 적혀 있어요:

> "`orca status --json` should show a running runtime. `orca` must be on PATH... The orchestration experimental feature must be enabled in Settings > Experimental. `orca orchestration` commands are RPC calls to the running Orca runtime."

이 말은 곧, orchestration 기능을 쓰려면 (1) Orca 데스크톱 앱이 실제로 켜져 있어야 하고, (2) 실험 기능이 설정에서 켜져 있어야 하고, (3) 모든 명령이 그 켜진 앱에게 원격 호출을 보내는 방식이라는 뜻이에요. 즉, **Orca 앱이 없는 환경에서는 이 명령어들이 물리적으로 존재할 수 없어요.** 이건 선택의 문제가 아니라 사실관계예요.

그래서:
- **NO (필요 없음)**: "할 일을 나누고, 맡기고, 살아있는지 확인하고, 끝났는지 기록하는" graphori의 핵심 루프. 이건 `orca` CLI나 orchestration skill 없이, 평범한 프로세스 실행 + 로그 파일만으로 완전히 구현 가능해요.
- **부분 의존 (YES, 하지만 선택적)**: Orca 안에서 실행될 때는 `orca` CLI를 통해 진짜 Orca의 Run/Task/Dispatch/message API를 그대로 사용해서 IDE 사이드바에 표시되고, Orca의 임베디드 브라우저 자동화까지 쓸 수 있게 만드는 것. 이건 "Orca adapter"라는 이름의 선택적 구현체로 존재해야 하고, 코어 로직이 이 어댑터를 직접 알아서는 안 돼요(포트-앤-어댑터 원칙, 부록 B 참고).
- **YES (Orca가 필수인 유일한 영역)**: Orca 내장 브라우저를 접근성 트리로 자동 조작하는 기능. 이건 Orca라는 Electron 앱의 웹뷰 자체가 있어야만 존재하는 기능이라, 대체재는 "표준 브라우저 자동화 도구(Playwright 등)를 별도로 붙이는 것"뿐이에요.

---

## 6. Orca 없이도 돌아가는 최소 설계안 (제안)

핵심 아이디어: **"기록"과 "신호"만 잘 설계하면 대장(coordinator) 프로그램과 일꾼(worker) 프로그램이 서로의 존재를 몰라도 협업할 수 있어요.** 이건 우체통에 편지를 넣고 나중에 열어보는 것과 같아요. 우체통(파일)만 같은 곳에 있으면, 두 사람이 언제 편지를 쓰고 읽는지는 상관없어요.

### 6.1 이벤트 기록 (모든 것의 뿌리)

`.graphori/runs/<run_id>/events.jsonl` 파일 하나에, 무슨 일이 있었는지 한 줄씩 계속 추가만 해요(지우거나 고치지 않음). 한 줄은 JSON 하나예요.

```json
{"ts":"2026-08-09T10:00:00Z","type":"task_created","run_id":"r1","task_id":"t1","spec":"..."}
{"ts":"2026-08-09T10:00:05Z","type":"dispatch_started","run_id":"r1","task_id":"t1","dispatch_id":"d1","pid":12345}
{"ts":"2026-08-09T10:00:35Z","type":"heartbeat","run_id":"r1","task_id":"t1","dispatch_id":"d1","phase":"implementing"}
{"ts":"2026-08-09T10:01:10Z","type":"worker_done","run_id":"r1","task_id":"t1","dispatch_id":"d1","outcome":"succeeded"}
```

이 방식의 이름이 바로 **"이벤트 소싱(Event Sourcing)"**이에요. "현재 상태"를 따로 저장하지 않고, "지금까지 있었던 일들"만 저장한 다음, 필요할 때 그 일들을 처음부터 순서대로 재생해서 현재 상태를 계산해요. (근거: 부록 B)

이 파일 형식의 이름은 **"JSON Lines(JSONL)"**이라고 해요. 한 줄에 JSON 값 하나씩. 이 방식이 좋은 이유: 한 줄씩 이어 붙이기만 하면 되니까 여러 프로그램이 동시에 써도 안전하고(각자 한 줄씩 append), 사람이 `tail -f`로 실시간으로 지켜볼 수도 있고, 파일 일부만 읽어도 파싱할 수 있어요. (근거: 부록 C)

### 6.2 상태 조회를 빠르게 하려면 — SQLite는 "캐시"로만

이벤트가 수만 줄 쌓이면 매번 처음부터 재생하는 게 느려질 수 있어요. 그럴 때는 SQLite 파일 하나를 "다시 만들 수 있는 캐시(read model)"로 둬요. 이벤트 로그가 진짜 원본(source of truth)이고, SQLite는 그걸 빠르게 조회하려고 미리 계산해 둔 요약본이에요. SQLite 파일이 깨지거나 지워져도 이벤트 로그만 있으면 언제든 다시 만들 수 있어요.

실제로 SQLite 공식 문서도 "한 대의 컴퓨터 안에서, 그 컴퓨터의 애플리케이션 내부 데이터로 쓰는 것"을 SQLite의 대표적인 적합한 용도로 꼽고 있고, Orca 자신도 `orchestration.db`라는 이름으로 정확히 이 방식(로컬 SQLite)을 쓰고 있어요. (근거: 부록 C)

### 6.3 하트비트(살아있음 신호)

일꾼이 30초~1분마다 이벤트를 하나씩 추가하거나, `control/<dispatch_id>.heartbeat`라는 빈 파일의 "마지막 수정 시각"만 계속 갱신해요. 대장은 그 파일의 수정 시각이 너무 오래됐으면 "이 일꾼이 죽었나?"라고 의심할 수 있어요.

### 6.4 토큰 사용량

Claude Code나 Codex 같은 에이전트 CLI는 실행이 끝나면 사용한 토큰 수를 담은 결과(JSON)를 출력해요. 그 값을 그대로 이벤트로 한 줄 추가하면 끝이에요. 별도의 계량기가 필요 없어요.

### 6.5 취소(Cancellation)

대장이 `control/<dispatch_id>.cancel`이라는 신호 파일을 만들어요(임시 이름으로 만든 뒤 최종 이름으로 "원자적 이름 바꾸기"를 하는 방식 — 이건 옛날 이메일 시스템 Maildir가 쓰던 검증된 방법이에요, 근거 부록 E). 일꾼을 감독하는 작은 프로그램(래퍼)이 주기적으로 그 파일이 생겼는지 확인하다가, 생기면 운영체제에 맞는 방법으로 자식 프로세스를 종료시켜요. (macOS/Linux는 SIGTERM 신호, Windows는 프로세스 종료 API — 자세한 차이는 7장)

### 6.6 증거(Evidence)

일꾼이 만든 결과 파일들을 `.graphori/runs/<run_id>/evidence/<dispatch_id>/` 폴더에 모으고, "이런 파일들을 만들었다"는 사실을 이벤트에 경로로 남겨요.

### 6.7 대시보드

가장 간단한 버전: `graphori status`라는 명령어가 이벤트 로그를 처음부터 재생해서 지금 상태를 표로 보여줘요. 실시간으로 자동 갱신되길 원하면, 아주 가벼운 로컬 웹 서버 하나가 이벤트 로그 파일이 늘어날 때마다 브라우저에 "새 줄 왔어요"라고 알려주는 **Server-Sent Events(SSE)**를 붙이면 돼요. SSE는 브라우저가 이미 기본으로 지원하는 아주 단순한 실시간 통신 방법이라 별도 프로그램을 설치할 필요가 없어요. 양방향 실시간 통신(WebSocket)까지는 이 단계에서 필요 없어요 — 대시보드는 "보기만" 하면 되니까요. (근거: 부록 E)

### 6.8 Orca adapter는 이 위에 "덧씌우는" 방식으로

Orca 환경에서 graphori를 실행할 때는, 위 6.1~6.7에서 만든 core 이벤트를 그대로 두고, 그 이벤트가 생길 때마다 **동시에** `orca orchestration send/task-create/...` 명령도 같이 호출해주는 어댑터를 하나 추가해요. 이렇게 하면 Orca 안에서는 IDE 사이드바에도 예쁘게 뜨고, Orca 밖에서는 파일 기반 core만으로 똑같이 동작해요.

---

## 7. Windows PowerShell과 macOS/zsh, 뭐가 다른가요?

이 부분은 실제로 코드를 만들 때 실수하기 아주 쉬운 부분이라 꼭 짚어야 해요.

### 7.1 경로(파일 위치 적는 법)
- macOS/Linux: `<home>/graphori/runs`처럼 슬래시(`/`)를 써요.
- Windows: 전통적으로 `<home>\graphori\runs`처럼 백슬래시(`\`)를 쓰지만, 요즘 Windows API나 PowerShell은 슬래시도 대부분 이해해요.
- **결론**: 문자열로 경로를 직접 조립하지 말고, 프로그래밍 언어가 제공하는 "경로 조립 함수"를 항상 써야 해요. 그래야 두 운영체제에서 똑같은 코드가 동작해요.

### 7.2 신호(Signal)와 프로세스 종료
- macOS/Linux(POSIX)에는 "신호(signal)"라는 개념이 있어요. `SIGTERM`(부드럽게 "이제 그만해줘")과 `SIGKILL`(강제로 "무조건 꺼")이 대표적이에요. `SIGTERM`은 프로그램이 받아서 뒷정리를 할 시간을 주지만, `SIGKILL`은 즉시 꺼버려서 막을 수 없어요. (근거: 부록 D)
- **Windows는 이런 신호 체계가 원래 없어요.** 대신 `TerminateProcess`라는 함수로 프로세스를 강제 종료하거나(POSIX의 SIGKILL과 비슷), 콘솔 창에 "종료 이벤트(CTRL_CLOSE_EVENT 등)"를 보내는 `GenerateConsoleCtrlEvent`로 부드러운 종료를 흉내낼 수 있어요(POSIX의 SIGTERM과 비슷하지만 완전히 같지는 않음). 여러 자식 프로세스를 한 번에 관리하려면 Windows의 "Job Object"라는 별개의 개념을 써야 해요. (근거: 부록 D)
- **결론**: "취소" 기능을 만들 때 "SIGTERM 보내기"라고 한 줄로 코드를 짜면 Windows에서는 안 돼요. 운영체제별로 종료 방법을 감싸는 작은 어댑터가 필요해요.

### 7.3 셸(명령어를 입력하는 프로그램) 차이
- macOS 기본은 zsh(bash 계열), Windows 기본은 PowerShell이에요.
- zsh/bash는 텍스트를 파이프(`|`)로 주고받는 게 기본이고, PowerShell은 진짜 .NET 객체를 파이프로 주고받아요. 그래서 같은 명령어라도 출력 형태가 완전히 달라요.
- **결론**: graphori가 셸 명령어를 직접 실행할 일이 있다면, 셸 문법에 의존하지 말고 프로그램(예: Node.js, Python)이 직접 자식 프로세스를 실행하는 표준 방법을 쓰고, 셸 스크립트를 두 벌(하나는 `.sh`, 하나는 `.ps1`) 준비하거나 아예 셸 없이 프로그램만으로 실행해야 해요. (근거: 부록 D)

### 7.3.1 대문자 인식 여부
- macOS 파일 시스템은 보통 대소문자를 구분 안 하고(기본값), Linux는 구분하고, Windows도 기본적으로 구분 안 해요. `Task.json`과 `task.json`을 같은 것으로 취급할지 다르게 취급할지 운영체제마다 달라서, 파일 이름은 항상 소문자로 통일하는 게 안전해요.

### 7.4 가짜 터미널(PTY)의 위험성
"가짜 터미널(Pseudo-terminal, PTY)"은 사람이 직접 타이핑하는 것처럼 프로그램이 다른 프로그램에게 글자를 보내고 화면을 읽어오는 기술이에요. 대화형 프로그램(예: 진짜 터미널 UI가 있는 도구)을 자동으로 조작하려면 필요해요.

- macOS/Linux는 POSIX 표준의 PTY가 운영체제 자체에 들어있어요. Python의 `pty` 모듈이 이걸 직접 감싸서 제공해요. (근거: 부록 D)
- Windows는 원래 진짜 PTY가 없었는데, 2018년(Windows 10 1809)부터 **ConPTY**라는 공식 API가 생겨서 POSIX PTY와 비슷하게 동작하게 됐어요. 그 전에는 `winpty`라는 비공식 흉내 라이브러리를 써야 했어요. (근거: 부록 D)
- **위험 요소**:
  1. PTY는 무겁고 복잡해요 — 화면 크기, 색깔 코드(ANSI escape), 커서 위치까지 다 흉내 내야 해서, 잘못 구현하면 출력이 깨지거나 멈춰요.
  2. Windows의 ConPTY와 macOS/Linux의 PTY는 세부 동작(줄바꿈 처리, 창 크기 신호)이 완전히 같지 않아요.
  3. **가장 중요한 사실**: graphori가 자동으로 돌릴 주요 에이전트 CLI인 Claude Code와 Codex는 **애초에 진짜 사람 화면(PTY)이 필요 없는 "비대화형(headless/non-interactive) 실행 모드"를 공식으로 제공해요.** Claude Code는 `-p`(또는 `--print`) 옵션으로 한 번 실행하고 결과를 바로 출력하며 끝나고, Codex는 `codex exec`으로 똑같이 동작해요. 둘 다 CI(자동화 파이프라인)에서 쓰라고 만들어진 기능이에요. (근거: 부록 G)

**결론**: graphori의 core 루프(할 일을 맡기고 결과를 받는 것)는 **PTY가 전혀 필요 없어요.** PTY는 오직 "사람이 실시간으로 에이전트의 화면을 구경하고 싶을 때"에만 쓰는 선택적 보너스 기능으로 분류해야 해요. 이렇게 하면 Windows/macOS PTY 차이라는 위험한 영역을 core에서 완전히 빼낼 수 있어요.

---

## 8. 요약

1. Orca 오케스트레이션의 알맹이는 "Task/Dispatch 상태기계 + 메시지 + 완료 보고 + 하트비트"라는 아주 단순한 원리다. 이건 파일 하나(JSONL 이벤트 로그)와 평범한 프로세스 실행만으로 완전히 재현 가능하다.
2. Orca만이 할 수 있는 진짜 고유 기능은 "Orca 내장 브라우저 자동화"와 "IDE 안의 시각적 대시보드" 정도로 매우 좁다.
3. `orca-cli`와 orchestration skill은 **core에는 NO(불필요)**, **Orca 안에서 실행될 때의 리치 어댑터로는 부분적으로 YES**다. Orca 공식 문서 자체가 이 명령들을 "켜져 있는 런타임으로의 RPC 호출"이라고 명시하고 있어서, Orca 앱이 없으면 물리적으로 쓸 수 없다는 사실이 이 결론의 근거다.
4. 최소 설계는: JSONL 이벤트 로그(source of truth, 이벤트 소싱) + 선택적 SQLite 캐시(read model) + 파일 기반 신호(하트비트/취소는 파일의 존재/수정시각으로 표현) + 선택적 SSE 대시보드. 여기에 PTY는 core에서 제외하고, 에이전트 CLI의 공식 비대화형 모드(Claude Code `-p`, Codex `exec`)를 기본 실행 방식으로 삼는다.
5. Windows와 macOS의 차이(경로, 신호/프로세스 종료, 셸, PTY)는 core 로직에서 절대 직접 다루지 않고, 운영체제별 아주 얇은 어댑터 뒤로 숨긴다.

---

## 부록 A. 기능 원장 — Orca CLI/스킬 원문 근거

이 컴퓨터에 설치된 `orca` 바이너리(`<home>/AppData/Local/Programs/orca/resources/bin/orca.exe`)와 번들 스킬 문서를 직접 조회해 확인한 1차 근거입니다.

### A.1 orca CLI 명령 트리 (2026-08-09 기준, `orca --help`)

```
Orchestration:
  orchestration run-create / run-use / run-current / run-list / run-show
  orchestration send / check / reply / ask / inbox
  orchestration task-create / task-list / task-update
  orchestration dispatch / dispatch-show
  orchestration worker-start / worker-show / worker-read / worker-stop /
                worker-abandon / worker-release / worker-retain / worker-list
  orchestration gate-create / gate-resolve / gate-list
  orchestration reset
Terminals:
  terminal list / show / read / send / wait / stop / create / rename / split / switch / focus / close
Browser:
  tab create/list/current/show/profile ; goto ; snapshot ; click ; fill ;
  keypress ; eval ; scroll ; drag
```

### A.2 Run/Task/Dispatch가 원격 호출(RPC)이라는 원문 근거 (orchestration skill guide)

> "`orca status --json` should show a running runtime. `orca` must be on PATH (`orca-ide` on Linux). The orchestration experimental feature must be enabled in Settings > Experimental. `orca orchestration` commands are RPC calls to the running Orca runtime."

즉 (1) Orca 데스크톱 런타임 프로세스가 살아있어야 하고, (2) 실험 기능 플래그가 켜져 있어야 하고, (3) 모든 명령이 그 런타임에 원격 호출을 보낸다는 뜻이다. 이 셋 중 하나라도 없으면 orchestration 명령은 성립하지 않는다.

### A.3 Run/Task/Dispatch 관계 정의 (원문)

> "A Run is the namespace/inbox, a Task is the work item, and a Dispatch assigns one Task attempt to a terminal."

Task 상태값: `pending`, `ready`, `dispatched`, `completed`, `failed`, `blocked`.

### A.4 메시지 타입 목록 (원문)

> "Message types include `status`, `dispatch`, `worker_done`, `merge_ready`, `escalation`, `handoff`, `question`, `decision_gate` (legacy/gates), and `heartbeat`."

### A.5 worker_done 계약 (원문)

> "A valid `worker_done` for the active `taskId` + `dispatchId` marks the task and dispatch completed automatically... Never encode failure only in the subject/body."

### A.6 실제 로컬 상태 저장소 확인 (직접 조회, 2026-08-09)

- `<home>/AppData/Roaming/orca/orchestration.db` — 파일 시작 16바이트가 `53 51 4C 69 74 65 20 66 6F 72 6D 61 74 20 33 00` = ASCII `"SQLite format 3\0"`. **Orca의 orchestration 상태 저장소는 SQLite다.**
- `<home>/AppData/Roaming/orca/terminal-history/<worktree-id>@@<hash>/` 폴더 아래 `output.log`(순수 append 텍스트) + `meta.json`(사이드카 메타데이터) 쌍으로 터미널 출력을 저장한다. 이는 이 문서의 6.1(JSONL 이벤트 로그)·6.2(SQLite 캐시) 설계와 원리적으로 동일한 "append 로그 + 구조화 메타데이터" 패턴이다.

### A.7 Browser 기능이 Orca 내장 웹뷰 전용임을 보여주는 근거 (원문, `orca --help`)

> "Browser Workflow: 1. Create or navigate: `orca tab create --url ...` ... 3. Interact: `orca click --element e2` ... (Returns an accessibility tree with element refs like e1, e2, e3)"

접근성 트리 기반 요소 참조(`e1`, `e2`...)는 Orca Electron 앱의 내장 웹뷰에서만 계산 가능한 값으로, 외부 브라우저나 외부 환경에서는 그대로 재사용할 수 없다.

---

## 부록 B. 아키텍처 패턴 근거

### B.1 헥사고날 아키텍처 / 포트-앤-어댑터

Alistair Cockburn이 2005년 9월 4일 발표한 "The Hexagonal (Ports & Adapters) Architecture" 기술 보고서가 원전이다. 핵심 주장: 애플리케이션은 사용자, 프로그램, 자동화 테스트, 배치 스크립트 등 무엇이 구동하든 동일하게 동작해야 하며, 실제 운영 장치·데이터베이스로부터 독립적으로 개발·테스트될 수 있어야 한다.

- 원문: https://alistair.cockburn.us/hexagonal-architecture/
- 정리 사이트: https://www.hexagonalarchitecture.org/

이 문서의 "core / Orca adapter / generic terminal adapter" 3단 구조는 이 패턴을 그대로 적용한 것이다: core는 "포트"(예: `AgentRunner`, `Notifier`, `EvidenceStore` 인터페이스)만 정의하고, 각 어댑터가 그 포트를 구현한다.

### B.2 이벤트 소싱(Event Sourcing)

Martin Fowler가 2005년 정리한 패턴으로, "객체에 가해진 모든 변경을 이벤트의 연속으로 저장하고, 각 이벤트는 append-only 저장소에 기록되며, 애플리케이션 코드는 수행된 각 동작을 나타내는 이벤트를 발생시킨다"고 정의한다.

- 원문: https://martinfowler.com/eaaDev/EventSourcing.html
- 참고(마이크로소프트 아키텍처 센터의 동일 패턴 설명): https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing

이 문서의 6.1(`events.jsonl`)이 이 패턴의 직접 구현이다. "현재 상태"가 아니라 "있었던 일"만 저장하고, 현재 상태는 재생(replay)으로 계산한다.

### B.3 CQRS와의 결합 (SQLite를 read model로 쓰는 이유)

이벤트 로그(쓰기 모델, source of truth)와 조회 전용 캐시(읽기 모델)를 분리하는 아이디어는 Event Sourcing과 함께 CQRS(Command Query Responsibility Segregation)로 널리 알려져 있다. 읽기 모델은 언제든 이벤트를 재생해 다시 만들 수 있으므로 손상되어도 안전하다. 이 문서의 6.2가 이 아이디어를 적용한 것이다.

---

## 부록 C. 저장 계층 근거 (JSONL, SQLite)

### C.1 JSON Lines(JSONL/NDJSON)

공식 사이트 jsonlines.org의 정의: "한 줄에 유효한 JSON 값 하나씩, UTF-8로 인코딩한 텍스트 형식." 파일 확장자는 `.jsonl`을 권장하며, 줄바꿈은 LF(`\n`)를 권장(대부분의 파서는 CRLF도 허용)한다. 각 줄이 독립적인 JSON 문서이므로 스트리밍 처리, 부분 읽기, 파일 분할이 쉽다는 것이 핵심 장점으로 명시되어 있다.

- 원문: https://jsonlines.org/

### C.2 SQLite의 적합한 용도

SQLite 공식 문서 "Appropriate Uses For SQLite"는 "애플리케이션 내부 데이터 저장", "하루 방문자 10만 명 이하인 저트래픽 웹사이트", "여러 클라이언트가 네트워크로 같은 DB에 SQL을 보내는 경우가 아닌 상황"을 적합한 사용처로 명시한다. 반대로 "네트워크 파일시스템을 통해 여러 프로그램이 동시에 접근"하는 경우는 클라이언트/서버 DB를 권장한다.

- 원문: https://sqlite.org/whentouse.html

이 문서가 SQLite를 "로컬 단일 프로세스용 캐시"로만 제안하는 이유가 바로 이 공식 가이드라인과 일치하며, Orca 자신도 `orchestration.db`로 동일한 방식(로컬 단일 앱 내부 저장)을 쓰고 있음을 부록 A.6에서 직접 확인했다.

---

## 부록 D. 프로세스/터미널 계층 근거 (PTY, ConPTY, 프로세스 종료, 셸 차이)

### D.1 POSIX PTY

Python 공식 문서(`pty` 모듈)는 "다른 프로세스를 시작시키고, 그 프로세스의 제어 터미널에 프로그램적으로 읽고 쓸 수 있게 하는" 기능이라고 설명하며, Linux/FreeBSD/macOS에서 테스트되었다고 명시한다.

- 원문: https://docs.python.org/3/library/pty.html

### D.2 Windows ConPTY

Microsoft 공식 블로그와 문서: "Windows Pseudoconsole(ConPTY)"는 Windows 10부터 제공되는, POSIX PTY API와 유사하게 동작하도록 설계된 공식 API다. 그 이전에는 `winpty`라는 비공식 라이브러리로 흉내를 냈다.

- 공식 블로그: https://devblogs.microsoft.com/commandline/windows-command-line-introducing-the-windows-pseudo-console-conpty/
- 공식 문서: https://learn.microsoft.com/en-us/windows/console/pseudoconsoles
- 공식 문서: https://learn.microsoft.com/en-us/windows/console/creating-a-pseudoconsole-session

Microsoft가 직접 유지하는 `node-pty` 라이브러리는 "Windows 빌드 18309 이상에서는 winpty 대신 ConPTY를 사용한다"고 명시하며, macOS/Linux/Windows를 모두 지원하는 크로스플랫폼 PTY 추상화의 실제 사례다.

- 원문: https://github.com/microsoft/node-pty

### D.3 POSIX 신호 vs Windows 프로세스 종료

Linux man-pages 공식 문서(`signal(7)`)는 SIGKILL/SIGSTOP은 잡거나 막거나 무시할 수 없고, SIGTERM은 잡거나 막거나 무시할 수 있어 "프로그램에게 정중하게 종료를 요청하는 일반적인 방법"이라고 설명한다.

- 원문: https://www.man7.org/linux/man-pages/man7/signal.7.html

Windows는 이런 신호 체계가 없다. Microsoft 공식 문서 기준 강제 종료는 `TerminateProcess` 함수로, 여러 프로세스를 묶어 관리하려면 `Job Objects`를 쓴다. 콘솔 프로세스 그룹에 종료 이벤트를 보내는 공식 함수는 `GenerateConsoleCtrlEvent`다.

- `TerminateProcess`: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess
- `Job Objects`: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- `GenerateConsoleCtrlEvent`: https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent

### D.4 PowerShell vs bash/zsh

PowerShell은 텍스트가 아니라 .NET 객체를 파이프로 주고받는 것이 근본적인 차이이며, 오류 처리도 Try/Catch/Finally 구조를 쓰는 반면 bash/zsh는 종료 코드(exit code) 기반이다. 이 차이 때문에 셸 스크립트를 한 벌만 만들어 두 운영체제에서 공유하는 것은 위험하며, 문서 7.3에서 제안한 대로 셸 문법에 의존하지 않는 프로세스 실행 방식을 core에 채택해야 한다.

---

## 부록 E. 전송/신호 계층 근거 (파일 큐, WebSocket, SSE)

### E.1 파일 기반 큐 — Maildir의 원자적 rename 패턴

Maildir는 D. J. Bernstein이 1995년 qmail을 위해 설계한 이메일 저장 형식으로, `tmp/`(쓰는 중) → `new/`(rename으로 도착 확정) 두 단계로 나눠 저장한다. POSIX 파일시스템에서 `rename()`은 원자적 연산이므로, 쓰다 만 파일이 절대 "도착한 것"으로 착각되지 않는다. 이 방식에서는 잠금(lock)이 전혀 필요 없다.

- 공식(djb) 원문: https://cr.yp.to/proto/maildir.html
- 참고: https://doc.dovecot.org/2.3/admin_manual/mailbox_formats/maildir/

이 문서 6.5의 취소 신호 파일(`control/<dispatch_id>.cancel`)은 이 패턴을 그대로 빌려온 것이다: 임시 이름으로 쓴 뒤 최종 이름으로 rename하면, 그 파일이 "존재한다"는 사실 자체가 원자적이고 신뢰할 수 있는 신호가 된다.

### E.2 WebSocket (RFC 6455)

IETF가 2011년 12월 발행한 인터넷 표준. HTTP 연결을 업그레이드해 양방향 실시간 채널을 여는 프로토콜.

- 원문: https://www.rfc-editor.org/info/rfc6455/ / https://www.ietf.org/rfc/rfc6455.txt

### E.3 Server-Sent Events (WHATWG HTML Living Standard)

서버에서 클라이언트로 단방향으로 실시간 업데이트를 보내는 표준. `EventSource` API로 브라우저가 기본 제공하며, 재연결도 자동으로 처리한다. WebSocket보다 훨씬 단순하지만 단방향이라는 제약이 있다.

- 원문: https://html.spec.whatwg.org/multipage/server-sent-events.html

**이 문서의 선택**: 대시보드는 "서버(이벤트 로그) → 사람(화면)" 단방향 갱신만 필요하므로 WebSocket이 아니라 더 단순한 SSE로 충분하다(6.7 참고). 양방향이 필요한 시점(예: 대시보드에서 직접 취소 버튼을 누르는 기능)이 오면, 그 버튼은 평범한 HTTP POST 요청 하나로 처리할 수 있어 여전히 WebSocket 없이 해결 가능하다.

---

## 부록 F. 터미널 멀티플렉서 근거 (tmux, zellij) — 선택적 보너스 계층

여러 일꾼의 화면을 사람이 동시에 관찰하고 싶을 때, macOS/Linux에서는 `tmux`(오래되고 검증된 표준)나 `zellij`(러스트로 작성된 최신 대안)로 여러 세션을 한 화면에 모아 볼 수 있다. 두 도구 모두 "세션을 떼었다 붙였다(detach/attach)" 할 수 있어 원격 작업에 유리하다.

- tmux 공식: https://github.com/tmux/tmux/wiki
- zellij 공식: https://zellij.dev/documentation/

**중요한 한계**: 두 도구 모두 Windows 네이티브 지원이 약하거나 없다(WSL 안에서는 가능). 그래서 이 문서는 tmux/zellij를 core에 절대 넣지 않는다 — 이건 "macOS/Linux 사용자를 위한 선택적 관찰 도구" 계층으로만 취급해야 하며, Windows에서는 단순히 여러 개의 별도 PowerShell 창(또는 Windows Terminal 탭)을 쓰는 것으로 대체한다.

---

## 부록 G. 에이전트 CLI/CI 근거 (GitHub Actions, Codex CLI, Claude Code CLI)

### G.1 GitHub Actions — 완전 비대화형 실행의 표준 사례

GitHub 공식 문서: `workflow_dispatch` 이벤트는 GitHub UI, GitHub CLI, REST API로 워크플로를 수동/프로그래밍 방식으로 트리거할 수 있게 하며, 입력값(inputs)을 최대 25개까지 정의할 수 있다. 이는 "사람이 화면 앞에 없어도 시작되고, 시작되면 사람 개입 없이 끝까지 실행된다"는 비대화형 실행의 표준 예시다.

- 원문: https://docs.github.com/actions/using-workflows/events-that-trigger-workflows
- 원문: https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow

**graphori와의 연결**: GitHub Actions runner 자체를 core의 "generic terminal adapter"의 한 변형(CI adapter)으로 취급할 수 있다. 어차피 core 로직이 "프로세스를 실행하고 이벤트 로그를 남기는 것"뿐이라면, 그 프로세스를 실행하는 장소가 macOS 터미널이든 GitHub Actions 러너든 상관없어야 한다.

### G.2 Codex CLI 비대화형 모드

OpenAI 공식 문서: "Non-interactive mode lets you run Codex from scripts (예: CI 작업)... `codex exec`으로 호출한다. 실행 중 진행 상황은 stderr로 스트리밍되고, 최종 에이전트 메시지만 stdout으로 출력되어 다른 도구로 파이프하기 쉽다." CI/CD에서는 `OPENAI_API_KEY`를 저장소 시크릿으로 등록해 인증한다.

- 원문: https://developers.openai.com/codex/noninteractive
- 원문(GitHub): https://github.com/openai/codex/blob/main/docs/exec.md

### G.3 Claude Code CLI 헤드리스 모드

Anthropic 공식 문서: `-p`(또는 `--print`) 플래그를 붙이면 대화형 세션을 열지 않고, 프롬프트를 명령줄로 바로 넘겨 한 번 실행하고 결과를 stdout으로 출력한 뒤 종료한다. 권한 플래그와 결합하면 완전히 비대화형이 되어 자동화, 예약 작업, 사람 입력이 불가능한 다중 에이전트 워크플로에 적합하다고 명시되어 있다.

- 원문: https://code.claude.com/docs/en/headless
- 원문: https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-headless

### G.4 대화형 vs 비대화형을 코어 설계에 반영하는 방법

두 CLI 모두 "비대화형 = 한 번 실행, stdout으로 결과, 종료 코드로 성공/실패 판정"이라는 동일한 계약을 제공한다. 이 계약이 정확히 이 문서가 core에 정의해야 하는 `AgentRunner` 포트의 최소 인터페이스와 일치한다:

```
AgentRunner.run(spec) -> { outcome: succeeded|failed, output: string, usage?: {tokens...} }
```

"대화형(interactive)" 모드(사람이 실시간으로 화면을 보며 개입)는 이 인터페이스 위에 얹는 별도의 선택적 포트(`AgentRunner.attach()` 같은)로 분리하고, 그 구현체만 PTY(부록 D)를 필요로 하게 만들면 core는 PTY 위험을 전혀 짊어지지 않는다.

---

## 부록 H. 최소 프로토콜 스펙 초안 (설계 후보, 미구현)

### H.1 디렉터리 레이아웃

```
.graphori/
  runs/
    <run_id>/
      events.jsonl          # source of truth, append-only
      index.sqlite          # 선택적 read model 캐시(재생성 가능)
      control/
        <dispatch_id>.cancel     # 존재하면 취소 요청
        <dispatch_id>.heartbeat  # mtime = 마지막 생존 신호
      evidence/
        <dispatch_id>/...        # 산출물
```

### H.2 이벤트 타입(초안)

| type | 필수 필드 | 의미 |
|---|---|---|
| `task_created` | run_id, task_id, spec, deps[] | 할 일 등록 |
| `task_status_changed` | run_id, task_id, status | 상태 전이 |
| `dispatch_started` | run_id, task_id, dispatch_id, pid | 실행 시작 |
| `heartbeat` | run_id, task_id, dispatch_id, phase | 생존 신호 |
| `usage_reported` | run_id, dispatch_id, tokens | 토큰 사용량 |
| `evidence_recorded` | run_id, dispatch_id, path, kind | 산출물 위치 |
| `worker_done` | run_id, task_id, dispatch_id, outcome | 완료 보고(1회) |
| `cancel_requested` | run_id, dispatch_id, reason | 취소 요청 |
| `gate_created` / `gate_resolved` | run_id, task_id, gate_id, question / resolution | DAG 결정 대기/해소 |

### H.3 core 포트(인터페이스) 초안

- `AgentRunner`: `run(spec) -> result`, 선택적 `attach(dispatch_id) -> stream`(PTY 필요 시에만)
- `EventLog`: `append(event)`, `replay(run_id) -> state`
- `Notifier`: `heartbeat(dispatch_id)`, `cancelRequested(dispatch_id) -> bool`
- `EvidenceStore`: `record(dispatch_id, path)`
- `Dashboard`: `subscribe(run_id) -> eventStream`(선택적, SSE로 구현 가능)

### H.4 Orca adapter 결합 지점(초안)

`EventLog.append()`가 호출될 때마다, Orca 환경이면 동일한 의미의 `orca orchestration send/task-update/...` 호출을 미러링한다. 이 미러링 자체를 core가 알 필요는 없다 — core는 `EventLog` 포트만 호출하고, 어댑터 조립(Composition Root)에서 "일반 파일 EventLog"와 "Orca-미러링 EventLog" 중 무엇을 주입할지 결정한다.

---

## 부록 I. 참고 링크 전체 목록

**아키텍처 패턴**
- Hexagonal Architecture (Alistair Cockburn, 2005): https://alistair.cockburn.us/hexagonal-architecture/
- Hexagonal Architecture 정리: https://www.hexagonalarchitecture.org/
- Event Sourcing (Martin Fowler): https://martinfowler.com/eaaDev/EventSourcing.html
- Event Sourcing pattern (Microsoft Azure Architecture Center): https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing

**저장 계층**
- JSON Lines 공식 스펙: https://jsonlines.org/
- SQLite — Appropriate Uses For SQLite: https://sqlite.org/whentouse.html
- Maildir 원자적 큐 (D. J. Bernstein 원문): https://cr.yp.to/proto/maildir.html
- Maildir 형식 참고(Dovecot): https://doc.dovecot.org/2.3/admin_manual/mailbox_formats/maildir/

**프로세스/PTY/신호**
- Python `pty` 모듈 공식 문서: https://docs.python.org/3/library/pty.html
- Windows ConPTY 소개(공식 블로그): https://devblogs.microsoft.com/commandline/windows-command-line-introducing-the-windows-pseudo-console-conpty/
- Windows Pseudoconsoles 공식 문서: https://learn.microsoft.com/en-us/windows/console/pseudoconsoles
- Windows Pseudoconsole 세션 생성: https://learn.microsoft.com/en-us/windows/console/creating-a-pseudoconsole-session
- node-pty (Microsoft, ConPTY/winpty 크로스플랫폼): https://github.com/microsoft/node-pty
- POSIX `signal(7)` man page: https://www.man7.org/linux/man-pages/man7/signal.7.html
- systemd `systemd.service(5)` man page (프로세스 감시/재시작): https://www.man7.org/linux/man-pages/man5/systemd.service.5.html
- Windows `TerminateProcess`: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess
- Windows `Job Objects`: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- Windows `GenerateConsoleCtrlEvent`: https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent

**전송/실시간**
- WebSocket RFC 6455: https://www.rfc-editor.org/info/rfc6455/
- Server-Sent Events (WHATWG HTML Living Standard): https://html.spec.whatwg.org/multipage/server-sent-events.html

**터미널 멀티플렉서**
- tmux 공식 위키: https://github.com/tmux/tmux/wiki
- zellij 공식 문서: https://zellij.dev/documentation/

**CI 및 에이전트 CLI**
- GitHub Actions — Events that trigger workflows: https://docs.github.com/actions/using-workflows/events-that-trigger-workflows
- GitHub Actions — Manually running a workflow: https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow
- OpenAI Codex CLI — Non-interactive mode: https://developers.openai.com/codex/noninteractive
- OpenAI Codex CLI — exec 문서(GitHub): https://github.com/openai/codex/blob/main/docs/exec.md
- Claude Code — Headless mode: https://code.claude.com/docs/en/headless
- Claude Code SDK — Headless: https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-headless

**Orca 1차 근거 (이 컴퓨터에서 직접 조회, 2026-08-09)**
- `orca --help`, `orca orchestration --help` 전체 출력 (로컬 CLI, 버전은 조회 시점 기준)
- `orca skills get orchestration` 전체 스킬 가이드 (로컬 CLI, 버전은 조회 시점 기준)
- `<home>/AppData/Roaming/orca/orchestration.db` 파일 헤더 직접 확인(SQLite format 3)
- `<home>/AppData/Roaming/orca/terminal-history/.../{output.log, meta.json}` 구조 직접 확인

> 주의: Orca 1차 근거는 이 컴퓨터에 설치된 특정 빌드 시점의 동작이며, 공식 웹 문서 URL이 아니라 로컬 CLI 출력이므로 버전이 바뀌면 세부 명령/필드가 달라질 수 있다. 다음 조사 때는 Orca 공식 문서 사이트가 별도로 존재하는지 확인해 URL 근거로 보강할 것을 권장한다.
