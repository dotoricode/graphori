# Graphori 제안 아키텍처 SOL

> 상태: **비교를 위한 설계 초안**  
> 작성일: 2026-08-09  
> 범위: 설계만 다룬다. 이 문서는 구현, 라이브러리 선정 확정, 기존 팀 개편의 즉시 실행을 승인하지 않는다.  
> 근거: `docs/research/TEAM_GRAPH_ANALYSIS.md`, `docs/research/PORTABILITY_AND_DEPENDENCY.md`, `docs/research/LIVE_GAME_DASHBOARD.md`

## 1. 먼저 읽는 쉬운 설명

### 1.1 Graphori는 무엇을 맡는가

Graphori를 여러 로봇 일꾼이 함께 푸는 퀘스트 게임이라고 생각하자. 퀘스트마다 어려움과 위험이 다르다. 맞춤법 하나를 고치는 일에 일곱 팀이 모두 줄을 설 필요는 없다. 반대로 보안 울타리나 Windows/macOS 파일 경계를 바꾸는 일은 한 로봇이 만들고 스스로 “맞다”고 말하게 해서는 안 된다.

그래서 Graphori에는 영원히 같은 이름으로 존재하는 고정 팀이 없다. 퀘스트가 생기면 다음을 보고 필요한 역할을 그때 만든다.

- 무엇을 바꾸는가
- 틀렸을 때 얼마나 위험한가
- 어떤 작업이 먼저 끝나야 하는가
- 다른 운영체제에서 실제 확인해야 하는가
- 사람만 내릴 수 있는 결정이 있는가

쉬운 문서 작업이면 작성자 하나와 자동 확인만 쓴다. 보통 코드 작업이면 작성자와 검증자를 분리한다. 보안·재현성·운영체제 경계 작업이면 작성자, 독립 검증자, 새 환경에서 공격해 보는 감사자, 증거를 지키는 역할까지 만든다. 일이 끝나면 그 역할도 끝난다.

### 1.2 Orca는 집이 아니라 어댑터다

Graphori의 핵심을 전자제품이라고 하면 Orca는 좋은 멀티탭이다. Orca는 에이전트를 시작하고, 메시지를 보내고, 예쁜 화면에 상태를 표시하는 일을 잘한다. 하지만 멀티탭이 없어졌다고 전자제품의 두뇌까지 사라져서는 안 된다.

Graphori의 진짜 기억은 Graphori가 소유한 사건 원장에 남는다. “퀘스트를 만들었다”, “일꾼을 배정했다”, “검증이 실패했다”, “사용자가 A를 골랐다” 같은 사건을 지우지 않고 차례대로 기록한다. 현재 상태와 대시보드는 이 기록을 다시 읽어 계산한다.

- Orca가 있으면 Orca adapter가 Graphori의 명령을 Orca Run/Task/Dispatch로 옮기고 결과를 다시 사건으로 가져온다.
- Orca가 없으면 generic terminal adapter가 macOS나 Windows에서 평범한 자식 프로세스를 실행한다.
- 어느 쪽을 쓰더라도 퀘스트, 위험, 검증, 사용자 결정의 뜻은 같다.

Orca의 데이터와 Graphori 원장을 둘 다 “진짜 원본”으로 두지 않는다. 두 시계가 조금만 어긋나도 누가 맞는지 알 수 없기 때문이다. **Graphori 원장이 유일한 업무 진실이고, Orca는 실행 장치이자 projection**이다.

### 1.3 대장은 무엇을 하고 무엇을 하지 않는가

오케스트레이터는 직접 벽돌을 쌓는 사람이 아니라 공사 순서를 관리하는 현장판이다. 다음 일을 한다.

- 일을 작은 노드로 나누고 선행 관계를 잇는다.
- 위험도를 매기고 필요한 역할과 독립성 규칙을 정한다.
- 준비된 일만 배정하고, 막힌 이유를 기록한다.
- 결과와 증거를 모아 다음 검증 또는 사용자 결정을 연다.
- 실패·중단·재시작 뒤에도 사건 원장에서 상태를 복구한다.

반대로 오케스트레이터는 저장소 파일을 직접 고치거나, 작성자 대신 테스트하거나, 자기 판단을 독립 검증이라고 부르지 않는다. heartbeat를 진행으로 꾸미거나 Windows 통과를 macOS 통과로 바꾸지도 않는다.

### 1.4 살아 있는 게임판은 사실만 움직인다

대시보드의 캐릭터가 걷는다고 실제 일이 진행되는 것은 아니다. 화면은 네 가지를 따로 보여 준다.

1. 연결이 열려 있는가
2. 최근 heartbeat가 왔는가
3. 실제 작업 단계가 바뀌었는가
4. 결과가 성공·실패·검수 대기로 정해졌는가

heartbeat만 오면 “살아 있음, 새 진행 없음”이다. 진행 사건이 오면 한 번만 짧게 움직인다. 신호가 오래되거나 스트림이 끊기면 즉시 멈춘다. 70% 같은 숫자는 완료 단계 수처럼 설명 가능한 근거가 있을 때만 바뀐다.

사람의 결정이 필요하면 대시보드에 퀘스트 카드가 열린다. 사용자가 버튼을 누른 순간을 결정 완료로 꾸미지 않는다. 서버가 결정을 원장에 기록한 뒤에만 다음 작업이 열린다.

### 1.5 팀 수 제안 — 다음 비교에서 바뀔 수 있는 초안

**비교용 초안은 “상시 고정 팀 0개, 고위험 작업의 최대 동시 실행 팀 4개”다.** 오케스트레이터와 사용자는 이 네 팀에 포함하지 않는다.

네 역할군은 다음과 같다.

1. 제작자: 조사·설계·변경을 한 흐름으로 소유한다.
2. 검증자: 변경 범위와 계약을 표적 검증한다.
3. 독립 감사자: 다른 세션·context와 필요 시 다른 모델/호스트에서 fresh run과 공격 검증을 한다.
4. 증거·플랫폼 담당자: 증거 완전성, 해시, 실행 환경, OS별 결과를 보존한다. 승인권은 없다.

작은 일은 1개, 보통 일은 2개, 고위험 일은 3~4개만 활성화한다. 현재 7개 고정 역할은 Windows 승인까지 18 checkpoint와 독립 감사 최소 20단계를 만들었지만, 독립 감사들은 고정 ELF 경로, AST 절대경로 15,533건, junction 경계 탈출이라는 실제 결함 세 가지를 찾았다. 따라서 한 팀으로 합치는 것은 안전 근거를 버리고, 일곱 팀을 항상 유지하는 것은 대기와 hand-off를 유지한다. 최대 4개는 작성과 승인의 분리, fresh 독립 감사, 증거 보존을 남기면서 기획·조사·분석을 별도 상시 hand-off로 만들지 않는 중간안이다.

이 수는 최종 조직 결정이 아니다. 다음 비교 단계에서 결함 탐지율, false negative, 리드타임, 대기시간, 재작업률, 비용, 역할 부재 시 복구 가능성을 측정한 뒤 3개 또는 5개로 바뀔 수 있는 **명시적 초안**이다.

## 2. 설계 목표와 비목표

### 2.1 목표

- Orca 설치나 실행 여부와 관계없이 같은 core 규칙으로 Run을 수행한다.
- 고정 roster가 아니라 작업 DAG와 위험 정책으로 역할 인스턴스를 생성한다.
- 작성과 독립 승인을 구조적으로 분리한다.
- 모든 상태 변경을 append-only 사건으로 재현할 수 있다.
- 사용자 결정, 외부 자원 대기, 실패를 서로 다른 상태로 보존한다.
- 동일 원장에서 CLI, 웹 dashboard, Orca UI projection을 만든다.
- Windows와 macOS의 경로·프로세스·셸·파일시스템 차이를 adapter 뒤에 둔다.

### 2.2 비목표

- Orca의 내부 데이터베이스나 비공개 구현을 복제하지 않는다.
- PTY, 픽셀아트, 브라우저 자동화를 core 필수 기능으로 만들지 않는다.
- 모든 작업에 두 모델 또는 두 검증자를 강제하지 않는다.
- `REVISE` 수를 0으로 만드는 것을 성공 지표로 삼지 않는다.
- 이 문서에서 특정 언어, 프레임워크, 메시지 브로커를 확정하지 않는다.

## 3. 아키텍처 경계

```text
사용자 / CLI / Dashboard
          │ command, decision
          ▼
┌───────────────────────────────────────────────────────┐
│ Portable Core                                         │
│ command handler · work DAG · risk/role policy          │
│ state machines · evidence policy · projection reducer  │
└───────┬──────────────┬───────────────┬────────────────┘
        │ ports        │ events        │ effects
        ▼              ▼               ▼
 Event Journal     Evidence Store   Runner / Supervisor
        │              │               │
    ┌───┴────┐     ┌───┴────┐     ┌────┴──────────────┐
    │ local  │     │ local  │     │ generic terminal │
    │ store  │     │/remote │     │ Orca adapter     │
    └────────┘     └────────┘     │ CI adapter       │
                                  └───────────────────┘
        │ canonical events
        ├────────► CLI projection
        ├────────► snapshot + SSE dashboard projection
        └────────► optional Orca projection
```

### 3.1 Portable Core가 소유하는 것

- ID, 타입, 상태 전이, 불변식
- Task scheduling DAG와 graph version
- 위험 분류와 역할 합성 정책
- 독립성·승인·재검증 정책
- 명령의 유효성 판단과 사건 생성
- 사건 replay와 projection reducer
- 재시도, circuit breaker, gate, 취소의 의미

Core 소스와 공개 타입에는 `orca`, PTY handle, PowerShell, POSIX signal 같은 이름이 나타나지 않아야 한다. 외부 실행기는 capability와 opaque external reference로만 보인다.

### 3.2 Port

| Port | Core가 요구하는 의미 |
|---|---|
| `EventJournal` | 사건을 정확한 순서로 append하고 sequence 이후 replay |
| `AgentRunner` | 명세와 직접 argv/env/cwd를 받아 비대화형 attempt 시작 |
| `ProcessSupervisor` | 생존 확인, 정상 종료 요청, grace 뒤 강제 종료, process tree 정리 |
| `EvidenceStore` | 증거 blob과 manifest 저장, hash 검증, 읽기 |
| `DecisionInbox` | 인증된 사용자 결정 수신 |
| `Clock` / `IdSource` | 테스트 가능한 시각과 충돌 없는 ID 제공 |
| `ProjectionPublisher` | revision을 가진 snapshot/event stream 게시 |
| `PlatformProbe` | 실제 OS·arch·도구·capability 사실 제공 |

### 3.3 Adapter

- `generic-terminal`: 직접 프로세스 실행, 파일/SQLite journal, 로컬 evidence, OS별 process supervisor
- `orca`: Run/Task/Dispatch/message/gate를 core 의미로 번역하고 Orca 결과를 수신
- `ci`: 비대화형 runner와 artifact API를 같은 port로 번역
- `dashboard-http`: snapshot, SSE, 명령 HTTP, decision 입력
- `browser-automation`, `interactive-pty`, `tmux/zellij`: capability가 있을 때만 붙는 선택 기능

Adapter가 없다는 이유로 core 의미를 낮추지 않는다. 예를 들어 Orca gate가 없으면 core gate가 사라지는 것이 아니라 generic `DecisionInbox`가 맡는다.

## 4. 명령과 사건의 분리

명령은 “해 달라”는 요청이고, 사건은 “실제로 일어났다”는 기록이다.

```text
Command: StartAttempt(task-7, role=independent-verifier)
Effect:  adapter가 외부 실행을 시도
Event:   AttemptStarted(... externalRef=opaque)
또는     AttemptStartFailed(... reason=...)
```

대시보드 버튼을 눌렀다는 사실만으로 `TaskSucceeded`를 만들 수 없다. 외부 효과의 결과를 확인한 뒤 사건을 기록한다. 외부 호출 직후 core가 죽을 수 있으므로 모든 effect는 `idempotencyKey`와 `correlationId`를 가진다.

## 5. 핵심 타입 초안

아래 표기는 언어 중립적인 설계 타입이다.

```text
RunId, GraphId, TaskId, TaskRevision, AttemptId
RoleInstanceId, GateId, EvidenceId, EventId, CommandId

RiskLevel = low | medium | high | critical
RiskTag = security_boundary | privacy | reproducibility | cross_platform
        | destructive | external_side_effect | cost | ambiguity | visual_only

VerificationDepth = none | automatic | targeted | fresh_full | adversarial
Verdict = pass | revise | inconclusive
PlatformVerdict = { platform: PlatformKey, verdict, evidenceIds[] }

PlatformKey = {
  os: windows | macos | linux,
  version: string,
  arch: string,
  shell?: string             # 관측 정보일 뿐 command 의미가 아님
}
```

```text
WorkGraph = {
  graphId,
  runId,
  version,
  nodes: TaskNode[],
  edges: WorkEdge[],
  createdFromEvent,
  policyVersion
}

TaskNode = {
  taskId,
  revision,
  kind: research | design | change | verify | audit | evidence | platform_gate,
  spec,
  inputArtifacts[],
  expectedOutputs[],
  risk: RiskProfile,
  requiredCapabilities[],
  requiredVerification,
  requiredPlatforms[],
  state,
  retryPolicy
}

RiskProfile = {
  level,
  tags[],
  rationale[],
  blastRadius,
  reversibility,
  uncertainty,
  policyVersion
}
```

```text
RoleRequirement = {
  roleKind: maker | verifier | independent_auditor | evidence_steward | platform_executor,
  capabilities[],
  independence: {
    notSameAttemptAs[],
    notSameSessionAs[],
    differentModelRequired: boolean,
    freshWorkspaceRequired: boolean,
    requiredPlatform?: PlatformKey
  }
}

RoleInstance = {
  roleInstanceId,
  requirement,
  assigneeRef,             # adapter-neutral opaque identity
  lifecycle: proposed | assigned | active | released,
  createdForTask,
  expiresAt?
}
```

```text
Attempt = {
  attemptId,
  taskId,
  taskRevision,
  roleInstanceId,
  attemptNo,
  retryOf?,
  coordinatorEpoch,
  externalRef?,
  lifecycle,
  freshness,
  startedAt?,
  endedAt?,
  outcome?,
  evidenceIds[]
}

AttemptLifecycle = created | starting | running | cancelling
                 | succeeded | failed | lost | abandoned
Freshness = unknown | fresh | stale | dead
```

`lifecycle`과 `freshness`를 합치지 않는다. 실행 중이지만 heartbeat가 stale일 수 있고, 프로세스가 끝났지만 완료 사건이 유실되어 outcome이 unknown일 수 있다.

## 6. 작업 graph와 edge

### 6.1 scheduling DAG

한 graph version 안에서 scheduler가 따르는 edge는 반드시 acyclic이다.

| Edge | 의미 | scheduler 영향 |
|---|---|---|
| `requires` | 선행 Task가 terminal success여야 함 | 준비 상태를 막음 |
| `requires_evidence` | 특정 evidence policy가 충족돼야 함 | 준비/완료를 막음 |
| `requires_gate` | 인증된 gate resolution 필요 | 사용자 대기 상태로 만듦 |
| `requires_resource` | OS host, credential, budget 같은 외부 자원 필요 | resource-blocked로 만듦 |
| `verifies` | 검증 Task가 대상 revision을 검증 | 대상의 최종 승인 조건 |
| `observes` | 분석/projection용 읽기 관계 | scheduling에 영향 없음 |

`rework_of`와 `supersedes`는 과거를 설명하는 history edge다. 실패한 노드로 뒤쪽 화살표를 그려 cycle을 만들지 않는다. `REVISE`가 나오면 새 Task revision 또는 새 fix Task를 만들고, 시간 방향으로 `rework_of=<old revision>`을 붙인다. 따라서 운영 이력은 피드백을 표현하지만 각 확정 graph version의 scheduling edge는 DAG다.

### 6.2 ready 계산

Task는 다음을 모두 만족할 때만 `ready`다.

```text
all requires predecessors succeeded
AND all required evidence policies satisfied
AND all required gates resolved with an allowed choice
AND required resources available
AND no active attempt for the same task revision
AND graph version is current
```

fan-out은 정책이 요구한 독립 검증만 만든다. fan-in은 보고서 문장 대신 evidence ID, 실행 환경, hash, verdict를 모아 판정한다.

### 6.3 graph 변경

- graph는 versioned immutable snapshot이다.
- 작업 추가·재작업·gate 삽입은 `GraphRevised` 사건으로 새 version을 만든다.
- 이미 시작된 attempt는 자신이 받은 graph version을 유지한다.
- 새 version이 입력 계약을 무효화하면 기존 attempt를 취소하거나 결과를 `superseded`로 격리한다.
- cycle, 존재하지 않는 node, 자기 검증 edge, 충족 불가능한 platform 요구는 활성화 전에 거부한다.

## 7. 위험 기반 역할 생성 정책

### 7.1 기본 정책

| 위험 | 생성 역할 | 검증 깊이 | gate |
|---|---|---|---|
| low | maker 1 | automatic, 필요 시 표본 검증 | 없음이 기본 |
| medium | maker 1 + verifier 1 | changed-scope targeted | 정책 충돌 시 |
| high | maker 1 + independent auditor 1 + evidence steward 1 | fresh full, 해당 공격 회귀 | 외부효과/모호성 시 |
| critical | maker 1 + verifier 1 + independent auditor 1 + evidence steward/platform 1 | targeted + fresh full/adversarial | 사용자 gate 필수 |

역할 수는 작업 수와 같지 않다. 같은 capability의 독립 Task는 충돌이 없을 때 한 역할 인스턴스가 순차 처리할 수 있다. 반대로 Windows와 macOS 증거가 동시에 필요하면 같은 `platform_executor` requirement에서 서로 다른 호스트 인스턴스를 만든다.

### 7.2 위험 상승 규칙

다음 중 하나면 최소 `high`다.

- 파일 경계, symlink/junction, credential, 개인정보를 건드림
- build artifact와 evidence 주소의 재현성을 바꿈
- 다른 OS에서 결과가 달라질 수 있음
- 새 외부 쓰기, 배포, 삭제, 비용 지출이 있음
- 변경 영향 closure를 확실히 계산할 수 없음

되돌리기 어려운 외부 효과, 상충하는 두 검증 결과, 승인 정책 자체 변경은 `critical`로 올린다.

### 7.3 독립성 불변식

- maker의 attempt/session은 자기 결과의 독립 verifier가 될 수 없다.
- `fresh_full`은 원래 작업 폴더와 결과 캐시를 신뢰하지 않는 새 workspace에서 실행한다.
- 정책이 `differentModelRequired`를 요구하면 같은 모델 계열의 자기검토로 대체하지 않는다.
- evidence steward는 증거 완전성을 확인하지만 제품 verdict를 단독 승인하지 않는다.
- orchestrator는 빈 역할을 직접 대신하지 않는다.
- OS gate는 실제 해당 OS에서 수집한 증거만 만족시킨다.

## 8. 오케스트레이터 계약

### 8.1 책임

1. 입력 목표를 Task와 명시적 edge로 분해한다.
2. 위험 정책 버전과 판단 근거를 기록한다.
3. role requirement를 만들고 capability/독립성에 맞게 배정한다.
4. ready Task만 시작하고 WIP 상한을 지킨다.
5. heartbeat, progress, result, evidence를 서로 다른 사건으로 수집한다.
6. verdict가 `revise`이면 새 revision과 영향 closure를 만든다.
7. 사용자 gate와 resource block을 분리한다.
8. terminal attempt마다 release/reuse/retain 결정을 남긴다.
9. Run 종료 전에 필수 플랫폼과 검증 matrix의 빈 칸을 확인한다.
10. 사건 원장에서 복구 가능하도록 coordinator lease와 epoch를 관리한다.

### 8.2 금지사항

- 저장소 파일 작성·수정·삭제
- 자신이 배정한 작업을 대신 실행하거나 검증했다고 주장
- 작성자 결과를 독립 증거로 재사용
- `heartbeat`, 연결 열림, TUI idle을 progress 또는 success로 해석
- stale/lost를 즉시 failed로 바꾸거나 중복 retry 실행
- unresolved user gate를 자동 승인
- 사건 원장의 과거 기록 수정·삭제 또는 adapter 상태로 덮어쓰기
- Windows verdict를 macOS verdict로 승격
- Orca 장애 시 알리지 않고 generic adapter로 실행 주체 변경
- evidence hash 불일치나 누락을 경고만 남기고 PASS
- 비용·권한·파괴적 외부 효과의 승인 범위를 확대 해석

## 9. 사건 원장

### 9.1 canonical envelope

```text
EventEnvelope<T> = {
  eventId,
  schemaVersion,
  runId,
  sequence,               # run 안에서 빈틈 없는 단조 증가값
  aggregate: { type, id, version },
  type,
  occurredAt,             # 원 사건 시각
  observedAt,             # journal writer가 본 시각
  actor: { kind: user | orchestrator | worker | adapter, id },
  coordinatorEpoch,
  commandId?,
  causationId?,
  correlationId?,
  idempotencyKey?,
  payload: T,
  prevHash,
  hash
}
```

`sequence`가 ordering의 기준이다. wall clock은 설명과 지연 계산에 쓰되 순서 결정에 쓰지 않는다. `prevHash/hash`는 우발적 손상과 삭제를 탐지하기 위한 무결성 사슬이며 보안 서명을 대신하지 않는다.

### 9.2 주요 사건

```text
RunCreated, RunActivated, RunWaitingForUser, RunCompleted, RunFailed, RunCancelled
GraphCreated, GraphRevised, RiskClassified
TaskCreated, TaskReady, TaskBlocked, TaskSuperseded
RoleRequired, RoleAssigned, RoleReleased
AttemptStartRequested, AttemptStarted, AttemptHeartbeatObserved
AttemptProgressed, AttemptCancellationRequested, AttemptFinished, AttemptLost
EvidenceRecorded, EvidenceVerificationFailed
VerificationRecorded(pass|revise|inconclusive)
GateOpened, DecisionSubmitted, GateResolved, GateExpired, GateCancelled
AdapterCommandRequested, AdapterCommandAccepted, AdapterCommandFailed
StreamGapDetected, RecoveryPerformed, CoordinatorLeaseAcquired
```

### 9.3 저장 규칙

JSONL을 쓸 수 있지만 **여러 worker가 하나의 파일에 직접 동시에 append하지 않는다.** 그 방식의 atomicity와 잠금 의미가 Windows와 macOS에서 같다고 보장할 수 없기 때문이다.

- canonical journal은 lease를 가진 단일 writer만 쓴다.
- producer는 고유 파일명을 사용해 같은 filesystem의 `inbox/tmp`에 완전한 envelope를 쓴 뒤 `inbox/ready`로 rename한다. 기존 파일을 replace하지 않는다.
- writer가 validation, deduplication, epoch 확인 후 sequence와 hash를 부여한다.
- SQLite를 쓰는 adapter는 transaction으로 같은 의미를 보장할 수 있다.
- SQLite index와 dashboard snapshot은 언제든 journal replay로 재생성 가능한 read model이다.
- network share 위 다중 writer는 기본 지원 범위가 아니다. 원격 실행은 한 journal service로 사건을 전송한다.
- 부분 마지막 record, checksum 오류, schema 미지원 record는 조용히 무시하지 않고 격리 및 recovery 사건으로 남긴다.

### 9.4 증거 manifest

```text
EvidenceManifest = {
  evidenceId,
  producerAttemptId,
  taskRevision,
  kind,
  logicalPath,
  contentHash,
  byteLength,
  command: { executable, argv[], cwdLogical },
  exitCode,
  stdoutRef?, stderrRef?,
  platform: PlatformKey,
  toolVersions,
  environmentAllowlist,
  startedAt, finishedAt,
  redactions[]
}
```

셸 명령 문자열 대신 executable과 argv 배열을 보존한다. 비밀값은 allowlist 밖에서 수집하지 않는다. evidence 경로는 허용 root 안에서만 만들며 symlink/junction을 따라 밖으로 나가는지 파일 생성 **전**과 rename 직전에 확인한다.

## 10. 상태 기계

### 10.1 Run

```text
draft -> active
active -> waiting_for_user -> active
active -> succeeded | failed | cancelled
waiting_for_user -> failed | cancelled
```

필수 platform verdict가 `unknown/deferred`이면 전체 Run을 `succeeded`로 닫을 수 없다. 정책상 부분 완료가 허용되면 `RunCompleted(scope=windows, exclusions=[macos])`처럼 범위를 명시하고 상위 목표는 열린 상태로 둔다.

### 10.2 Task

```text
proposed -> blocked | ready
blocked -> ready | cancelled | superseded
ready -> assigned -> running
running -> waiting_gate | verifying | succeeded | failed | cancelled | superseded
waiting_gate -> running | cancelled | failed
verifying -> succeeded | rework_required | inconclusive
rework_required -> superseded       # 새 revision/task가 생성됨
inconclusive -> blocked | ready      # 증거 보완 또는 fresh retry
```

Task 성공은 마지막 worker 문장이 아니라 요구된 attempt outcome, verification, evidence, gate를 reducer가 모두 확인했을 때만 발생한다.

### 10.3 Gate와 command

```text
Gate:    open -> decision_pending -> resolved | expired | cancelled
Command: requested -> accepted -> completed | rejected | cancelled | outcome_unknown
```

사용자 클릭은 `DecisionSubmitted`일 뿐이다. 권한과 현재 graph version을 확인해 `GateResolved`가 기록되어야 downstream Task가 열린다. timeout 기본값은 자동 승인 아닌 `expired` 또는 계속 대기다.

## 11. 사용자 decision gate

다음 조건에서는 사용자 gate를 연다.

- 목표나 선택지가 서로 다른 제품 결과를 만듦
- 파괴적·되돌리기 어려운 외부 효과
- 예산 또는 시간 상한 초과
- verifier verdict가 충돌하고 정책만으로 결정할 수 없음
- credential/권한의 새 부여
- 필수 OS gate를 생략하거나 범위를 축소하려는 결정
- 위험 정책 또는 acceptance 기준 자체 변경

Gate에는 다음이 필수다.

```text
question, whyNow, options[], recommendedOption?
evidenceIds[], affectedTasks[], predictedEffects[]
reversibility, deadline?, onExpiry, requestedBy
```

선택지는 실행 결과를 가장하지 않는다. `macOS 검증 생략`을 선택하면 macOS가 PASS가 되는 것이 아니라 scope exclusion이 기록된다. 위험한 선택은 확인 dialog와 keyboard/screen-reader focus 규칙을 따른다.

## 12. 실시간 dashboard projection

### 12.1 전송

기본은 `HTTP snapshot + SSE + HTTP command`다.

```text
GET snapshot -> { runId, revision: 41, projection }
GET events?after=41 -> SSE id 42, 43, ...
POST commands -> CommandRequested
SSE -> CommandAccepted/Completed/Rejected
```

클라이언트는 중복 ID를 한 번만 적용하고, revision gap을 발견하면 `syncing`을 표시한 뒤 replay 또는 새 snapshot을 요청한다. WebSocket과 long polling은 transport adapter 후보이며 projection 의미를 바꾸지 않는다.

### 12.2 view model

```text
AgentProjection = {
  roleInstanceId,
  attemptId,
  taskId,
  lifecycle,
  transport: connecting | open | closed | error,
  freshness: unknown | fresh | stale | dead,
  progress: { completed, total, basis, revision }?,
  result: unknown | succeeded | failed | cancelled,
  lastEvent: { id, type, occurredAt, observedAt }?,
  lastHeartbeatAt?,
  lastProgressAt?,
  pendingCommand?,
  openGate?,
  motionToken?
}
```

`transport`, `freshness`, `progress`, `result`를 하나의 `active` boolean으로 합치지 않는다.

### 12.3 진실 규칙

- heartbeat는 progress를 올리지 않는다.
- `progress`는 `completed/total` 또는 명시적 basis 없이는 null이다.
- `AttemptProgressed`가 오고 heartbeat가 fresh일 때만 one-shot motion을 허용한다.
- stream error 또는 stale threshold 진입 시 다음 render frame에 motion을 멈춘다.
- finished 뒤 도착한 오래된 progress는 무시한다.
- 사건의 `occurredAt`과 UI가 본 `observedAt`을 분리한다.
- reduced-motion에서는 모션 대신 정적 강조와 문장을 사용한다.
- 중요한 상태는 색뿐 아니라 단어, 아이콘, 모양으로 표시한다.

화면의 기본 문장은 “작업 중 · 최근 진행 4초 전 · heartbeat 2초 전”, “살아 있음 · 새 진행 없음 48초”, “신호 오래됨 · 마지막 heartbeat 14초 전”처럼 사실을 분리한다.

## 13. Orca adapter

### 13.1 매핑

| Core | Orca adapter effect/observation |
|---|---|
| Run | Orca Run 생성/바인딩과 mapping 저장 |
| Task revision | Orca Task 생성; core deps를 번역 |
| Attempt | Dispatch/worker-start; external dispatch ID를 opaque mapping으로 저장 |
| heartbeat | Orca heartbeat를 검증해 `AttemptHeartbeatObserved`로 수입 |
| worker completion | task+dispatch+capability를 확인해 `AttemptFinished` 후보로 수입 |
| user/worker question | core Gate 또는 message thread와 correlation |
| projection | core 상태를 Orca UI에 best-effort mirror |

Orca의 명령 이름과 상태값은 adapter 내부 DTO다. core Task 상태를 Orca 상태 enum에 직접 맞추지 않는다.

### 13.2 권위와 정합성

- core journal이 canonical이다.
- Orca mapping은 `{coreId, externalId, adapterVersion, idempotencyKey}`를 기록한다.
- Orca가 완료라고 해도 필수 evidence와 verification이 없으면 core Task는 완료되지 않는다.
- core가 완료되었다고 해서 adapter가 보고하지 못한 사실을 숨기지 않는다. `AdapterProjectionLagged`를 기록한다.
- 외부 호출 성공 뒤 응답을 잃으면 새 Dispatch를 만들지 않고 mapping/reconciliation을 먼저 조회한다.
- Orca 버전 변경으로 capability가 사라지면 해당 effect를 `unsupported`로 실패시키며 조용히 generic mode로 전환하지 않는다.

### 13.3 Orca 전용 선택 capability

내장 브라우저 접근성 조작, IDE sidebar, remote Orca server, worktree/terminal UI는 capability negotiation 뒤에만 사용한다. 이것들이 없으면 dashboard나 핵심 scheduling의 정확성이 낮아져서는 안 된다.

## 14. generic terminal과 OS 경계

### 14.1 공통 실행 계약

- 기본 실행은 비대화형 프로세스다.
- command는 shell string이 아니라 `executable + argv[] + env allowlist + cwd`다.
- stdout/stderr, exit code, 시작/종료 시각을 캡처한다.
- PTY attach는 관찰용 선택 capability다.
- 경로는 언어의 path API로 만들며 원장에는 `/` 기반 logical path와 실제 native path metadata를 구분한다.

### 14.2 macOS

- process group에 정상 종료 요청을 하고 grace timeout 뒤 강제 종료한다.
- symlink의 최종 real path를 evidence root와 비교한다.
- 기본 파일시스템이 case-insensitive일 수 있으므로 case collision을 사전 검사한다.
- zsh 문법을 core 명령 계약으로 사용하지 않는다.

### 14.3 Windows

- 자식 tree는 Job Object와 같은 supervisor 경계로 묶는다.
- 가능한 정상 종료 신호 후 timeout에 process tree 강제 종료를 사용한다. 이를 SIGTERM과 동일하다고 가정하지 않는다.
- junction/reparse point를 포함한 최종 경로가 허용 root 밖인지 파일·디렉터리 생성 전에 검사한다.
- 드라이브 문자, UNC, 긴 경로, 예약 이름, case-insensitive 충돌을 명시적으로 다룬다.
- PowerShell object pipeline과 quoting을 core가 해석하지 않는다.

### 14.4 공통 파일 규칙

- UTF-8과 canonical JSON 직렬화를 사용하고 CRLF/LF 차이를 의미 차이로 보지 않는다.
- 파일명은 portable subset과 소문자 canonical form을 기본으로 한다.
- atomic rename은 같은 volume, 새 고유 destination이라는 조건에서만 사용한다.
- 열려 있는 파일의 rename/replace 의미가 OS마다 다르므로 replace 기반 lock-free protocol을 쓰지 않는다.
- network filesystem은 별도 adapter acceptance를 통과하기 전 지원하지 않는다.

OS별 판정은 별도 `PlatformVerdict`다. `windows/pass`, `macos/deferred`는 전체 PASS가 아니다.

## 15. 실패와 복구

### 15.1 coordinator crash / split brain

- coordinator는 lease와 단조 증가 `epoch`를 가진다.
- 새 coordinator는 lease 만료 뒤 더 높은 epoch를 얻고 journal을 replay한다.
- worker/adapter의 모든 lifecycle 사건은 배정받은 epoch를 포함한다.
- 오래된 coordinator의 명령과 사건은 거부하되 감사 사건으로 남긴다.
- gate, pending command, active attempt를 replay하여 이어 간다.

### 15.2 journal 손상

- 시작 시 sequence, schema, aggregate version, hash chain을 검사한다.
- 끝의 미완성 record는 원본을 보존한 recovery copy에 격리하고 마지막 유효 sequence부터 재개한다.
- 중간 hash 손상은 자동 덮어쓰지 않고 Run을 `blocked_integrity`로 둔다.
- read model은 삭제 후 전 replay할 수 있어야 한다.

### 15.3 worker 신호 상실

1. heartbeat timeout은 freshness를 `stale`로 만들 뿐 실패로 확정하지 않는다.
2. supervisor/adapter가 실제 process 또는 remote dispatch 상태를 확인한다.
3. 종료했지만 terminal event가 없으면 `AttemptLost(outcome=unknown)`을 기록한다.
4. 같은 attempt ID를 되살리지 않고 `retryOf`가 있는 새 attempt를 만든다.
5. 중복 실행 가능성이 남아 있으면 먼저 stop/reconcile하거나 사용자 gate를 연다.
6. retry 상한 뒤 circuit breaker가 Task를 blocked 또는 failed로 전환한다.

### 15.4 중복·순서 오류

- 같은 `eventId/idempotencyKey`는 no-op 처리하고 중복 metric을 올린다.
- 같은 attempt의 terminal outcome 두 개는 첫 유효 사건을 유지하고 충돌을 격리한다.
- 낮은 graph version의 늦은 결과는 evidence로 보존하되 현재 revision을 완료하지 못한다.
- dashboard revision gap은 재동기화 대상이지 추정으로 채울 값이 아니다.

### 15.5 evidence 실패

- 파일 누락, hash 불일치, platform metadata 없음은 `inconclusive` 또는 `revise`다.
- evidence root 밖 path, symlink/junction 탈출은 보안 실패다.
- redaction 전 원문을 dashboard나 일반 로그에 노출하지 않는다.
- 증거 재수집은 새 attempt/evidence ID를 사용하고 과거 증거를 교체하지 않는다.

### 15.6 adapter 장애

- adapter 상태를 `online | degraded | offline | incompatible`로 projection한다.
- 아직 외부 효과가 없다고 증명될 때만 다른 adapter로 재배정한다.
- 효과 여부가 `outcome_unknown`이면 reconcile 또는 사용자 결정을 먼저 한다.
- Orca projection 장애는 core Run을 손상시키지 않는다.
- 필수 Orca 전용 capability 작업은 generic으로 흉내 내지 않고 resource-blocked로 둔다.

### 15.7 취소

- 취소는 `requested -> acknowledged -> graceful stop -> forced stop` 순서다.
- 강제 종료 여부와 남은 child process를 evidence로 기록한다.
- 취소된 attempt의 늦은 success는 Task를 자동 완료하지 않는다.
- 외부 부작용의 보상 작업은 별도 Task이며 “취소했으니 원상복구”로 가정하지 않는다.

## 16. 보안과 권한

- command, decision, adapter callback은 run/task/attempt ID와 actor 권한을 검증한다.
- 사용자 gate resolution은 인증된 사용자 또는 명시적 위임 주체만 기록할 수 있다.
- worker는 자기 attempt 범위 밖 Task 상태를 바꿀 수 없다.
- journal과 evidence는 최소 권한으로 분리하고 secret을 payload에 넣지 않는다.
- dashboard 사건은 권한별로 필터하고 명령 원문 대신 안전한 요약을 노출한다.
- 외부 ID나 경로를 shell에 보간하지 않는다.
- 정책 버전과 adapter 버전을 모든 판정·mapping에 남긴다.

## 17. 관측 지표

속도만 또는 `REVISE=0`만 최적화하지 않는다.

- `task_queue_ms`, `task_run_ms`, `gate_wait_ms`, `resource_block_ms`
- `active_wip`, `ready_wip`, `critical_path_length`
- `rework_total`, `rework_by_risk`, `recovery_time_ms`
- `verification_run_total`, `fresh_full_total`, `defect_detected_total`
- seeded defect 기준 `detection_rate`, `false_negative_rate`
- `event_duplicate_total`, `event_gap_total`, `projection_lag_ms`
- `heartbeat_age_ms`, `progress_age_ms`, `stale_duration_ms`
- `adapter_error_total`, `outcome_unknown_total`, `orphan_process_total`
- `command_pending_ms`, `command_rejected_total`, `gate_expired_total`
- role별 token/cost, OS별 실행시간과 verdict coverage

Little의 법칙을 적용하려면 `arrivedAt/startedAt/finishedAt`이 실제로 쌓인 뒤 도착률과 정상상태 가정을 확인한다. 현재 자료만으로 “몇 배 빨라진다”는 수치를 약속하지 않는다.

## 18. Acceptance criteria

아래는 구현 지시가 아니라 다음 설계를 비교·검증할 때의 통과 조건이다.

### 18.1 Core 독립성

- core dependency graph에 Orca SDK/CLI 타입, PTY, PowerShell, POSIX signal import가 0개다.
- 동일 fixture를 generic Windows와 generic macOS에서 실행했을 때 adapter metadata를 제외한 normalized domain event와 최종 projection이 같다.
- Orca가 설치되지 않은 환경에서 Run 생성, DAG 실행, gate, retry, evidence, replay가 모두 가능하다.

### 18.2 DAG와 역할

- scheduling cycle, self-verification, missing node, 불가능한 platform 요구를 activation 전에 거부한다.
- low/medium/high/critical fixture가 각각 정책표의 역할과 검증 깊이를 생성한다.
- maker의 session/attempt가 독립 verifier requirement를 충족할 수 없다.
- `REVISE`는 과거 node를 수정하지 않고 새 revision과 `rework_of`를 만든다.
- WIP cap이 4일 때 다섯 번째 역할은 유실되지 않고 ready queue에 남는다.

### 18.3 사건 원장

- 여러 producer가 동시에 사건을 제출해도 canonical sequence가 연속이고 record가 섞이지 않는다.
- 동일 idempotency key를 반복 제출해도 domain effect는 한 번이다.
- writer를 record 작성 중 강제 종료한 뒤 acknowledged 사건은 유실되지 않고 미완성 tail은 격리된다.
- journal replay로 만든 projection과 저장 snapshot의 normalized hash가 같다.
- 중간 record 변조는 시작 시 탐지되고 자동 PASS하지 않는다.

### 18.4 상태와 복구

- heartbeat timeout만으로 Task를 failed 처리하거나 retry하지 않는다.
- 완료 event 유실 fixture에서 `AttemptLost/outcome_unknown` 뒤 reconcile 없이 중복 실행하지 않는다.
- coordinator 두 개가 생겨도 낮은 epoch의 command가 거부된다.
- 재시작 뒤 열린 gate, pending command, active attempt가 같은 상태로 복구된다.
- retry와 late completion이 서로 다른 attempt ID로 구분된다.

### 18.5 독립 검증과 증거

- 고위험 boundary fixture는 fresh workspace와 공격 회귀 없이는 PASS하지 않는다.
- evidence manifest의 hash, exit code, platform, tool version 중 필수값이 없으면 `inconclusive`다.
- junction/symlink를 통한 evidence root 밖 쓰기를 파일 생성 전에 차단한다.
- Windows PASS와 macOS deferred fixture의 전체 결과는 complete PASS가 아니다.
- seeded defect 비교에서 현행 7역할 기준선보다 false negative가 악화되지 않는다는 증거가 있어야 4역할 초안을 채택한다.

### 18.6 사용자 gate

- worker나 orchestrator가 user-only gate를 resolve하려 하면 거부된다.
- 사용자 클릭 뒤 `pending`을 보이며 `GateResolved` 전에는 downstream Task가 ready가 되지 않는다.
- timeout은 자동 승인하지 않는다.
- scope 축소 결정은 제외 범위를 기록하며 제외 platform을 PASS로 표시하지 않는다.

### 18.7 Dashboard

- snapshot revision 41 뒤 SSE 42부터 적용한다.
- 중복 42는 한 번만 적용하고 44가 먼저 오면 syncing/replay를 수행한다.
- heartbeat만 5회 받아도 progress와 걷기 loop는 바뀌지 않는다.
- heartbeat stale 또는 stream error에서 모션이 다음 render frame에 멈춘다.
- 25와 60 progress 사건만 있으면 25→60만 표시하고 근거를 노출한다.
- reduced-motion, keyboard, screen reader, 고대비에서 상태와 gate를 사용할 수 있다.

### 18.8 OS와 process

- 공백·한글·유니코드·긴 경로, case collision, Windows junction, macOS symlink fixture를 통과한다.
- argv에 shell metacharacter가 있어도 shell injection 없이 그대로 전달된다.
- 정상 취소와 강제 취소 뒤 child process tree가 남지 않는다.
- CRLF/LF 차이로 같은 canonical event가 달라지지 않는다.
- 파일이 열려 있거나 rename이 실패하는 fixture에서 사건을 도착했다고 오인하지 않는다.

### 18.9 Orca adapter

- Run/Task/Attempt와 Orca Run/Task/Dispatch mapping이 재시작 뒤 유지된다.
- worker completion 중복, 응답 유실, Orca offline, unsupported version을 각각 재현한다.
- 외부 effect 여부가 불명확할 때 새 Dispatch를 만들지 않는다.
- Orca projection이 꺼져도 core replay와 generic dashboard는 동일하다.
- Orca 전용 browser/worktree capability가 없을 때 core 기능이 실패하지 않고 해당 선택 기능만 unavailable이다.

## 19. 다음 비교 단계의 결정 표

| 질문 | 7개 고정 역할 기준선과 비교할 값 | 초안 유지 조건 |
|---|---|---|
| 4개 상한이 안전한가 | seeded defect 탐지율, false negative, 보안 회귀 | 탐지율 비열화 없음 |
| hand-off가 줄었는가 | queue/gate wait, critical path, stale document | 중앙값과 꼬리 지연 개선 |
| 비용이 줄었는가 | fresh run 횟수, token, OS 실행시간 | 안전 검증을 유지한 순비용 감소 |
| SPOF가 줄었는가 | coordinator 재시작, 역할 부재, 증거 replay | 다른 주체가 원장만으로 재개 가능 |
| dashboard가 정직한가 | gap, duplicate, stale, 가짜 progress 시나리오 | 모든 진실 규칙 통과 |
| portable한가 | Windows/macOS 동일 fixture | normalized 결과 동등 |

다음 단계에서는 7개 고정 역할, 이 문서의 최대 4역할 동적안, 필요하면 3역할 축소안을 같은 seeded fixture로 비교한다. 측정 전에는 어느 안도 “최적”이라고 부르지 않는다.

## 20. 설계 결론

Graphori의 중심은 Orca도, 고정 팀 명단도, 게임 화면도 아니다. 중심은 **버전된 작업 DAG, 위험에 따른 임시 역할, 독립 검증 규칙, append-only 사건 원장, 재생 가능한 projection**이다.

Orca는 이 중심을 풍부하게 실행하고 보여 주는 좋은 선택형 adapter다. generic terminal은 최소 기능 adapter다. 둘은 같은 core 계약을 따르며 어느 adapter도 업무 진실의 소유자가 되지 않는다. 오케스트레이터는 graph와 증거를 관리하되 작업과 검증을 대신하지 않는다. 사용자는 결정 gate에서 실제 권한을 가진다. dashboard는 연결, 생존, 진행, 결과를 분리해 사실만 움직인다. Windows와 macOS 결과는 실제 실행 증거가 있을 때만 각각 닫힌다.

채택 후보는 **상시 고정 팀 0개, 최대 동시 실행 역할 4개**다. 이는 기존 독립 감사가 발견한 세 가지 중요 결함을 잊지 않으면서 7개 상시 hand-off를 줄이려는 비교용 초안이며, 다음 실험의 증거에 따라 변경한다.
