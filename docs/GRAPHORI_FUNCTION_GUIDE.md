# Graphori 현재 기능 안내

> 이 문서는 Graphori를 처음 보는 사람도 실제로 실행해 보고, 화면에 보이는 말이
> 무엇을 뜻하는지 이해하도록 만든 안내서입니다. 어려운 단어가 나오면 바로 아래에서
> 쉬운 말로 다시 설명합니다.

## 1. Graphori는 무엇인가요?

Graphori는 큰 일을 작은 작업 카드로 나누고, 각 카드의 결과와 확인 과정을 기록하는
도구입니다.

열두 살에게 말하면 이렇게 설명할 수 있습니다.

> 큰 레고 성을 만들 때 한 친구가 설계도만 그리고, 다른 친구가 블록을 찾고, 또 다른
> 친구가 성을 만들 수 있습니다. 마지막에는 만든 친구가 아니라 다른 친구가 성을
> 흔들어 튼튼한지 확인합니다. Graphori는 이 카드와 친구들의 순서, 결과, 확인 도장을
> 기록하는 작업 지도입니다.

Graphori가 최종적으로 만들고 싶은 경험은 두 부분입니다.

1. 작업 중에는 기획팀이 대시보드를 계속 켜 두고 여러 작업의 상태를 모읍니다.
2. 작업이 끝나면 작업 지시자가 코드 diff를 모두 읽지 않아도 목표, 구조, 결과,
   확인 근거를 이해하도록 설명합니다.

여기서 꼭 구분해야 할 것이 있습니다.

| 표시 | 뜻 |
| --- | --- |
| **지금 실행 가능** | 현재 저장소의 CLI로 바로 실행되고, 결과를 확인할 수 있습니다. |
| **코어 계약·테스트** | 그래프 규칙과 역할을 코드로 검사할 수 있지만, 현재 기본 CLI가 여러 실제 세션을 자동으로 시작한다는 뜻은 아닙니다. |
| **설계 예시** | Graphori가 앞으로 여러 팀을 움직일 때의 모양을 보여 주는 학습용 흐름입니다. |
| **아직 안 됨** | 현재 실행 경로가 제공하지 않는 기능입니다. 화면이 있다고 해서 실제 기능이라고 생각하면 안 됩니다. |

이 문서와 [학습 게임](GRAPHORI_LEARNING_GAME.html)은 이 네 가지를 일부러 색과 문장으로
나누어 보여 줍니다.

## 2. 현재 실행할 수 있는 기능

### 2.1 일반 터미널 명령 실행 — 지금 실행 가능

Graphori는 먼저 안전한 일반 터미널 작업을 실행합니다. 명령을 긴 문자열로 몰래
실행하지 않고, 프로그램 이름과 인자를 각각 전달합니다.

```sh
repo_root="$(pwd -P)"
python3 -m src.graphori_core.cli \
  --root "$repo_root" \
  --run-id run-demo \
  run -- python3 -c 'print("hello from Graphori")'
```

실행할 때 Graphori는 다음을 지킵니다.

- 작업 폴더는 `--root` 안으로 제한합니다.
- 자식 프로그램에 넘길 환경 변수는 허용 목록으로 제한합니다.
- 이름이 `TOKEN`, `PASSWORD`, `API_KEY`처럼 보이는 비밀 환경 변수는 버립니다.
- 표준 출력과 표준 오류를 정해진 크기까지만 모읍니다.
- 시간이 너무 오래 걸리면 자식 프로세스 무리 전체를 종료하려고 합니다.
- 성공했는지 실패했는지, 시간 초과였는지, 출력이 잘렸는지를 결과에 남깁니다.

현재 기본 CLI의 중요한 한계는 **한 번의 실행에 `worker` 노드 하나를 만든다**는
점입니다. 이 명령 하나가 기획팀·정보조사팀·설계팀·구현팀·검증팀을 각각 실제
세션으로 자동 실행한다는 뜻은 아닙니다.

### 2.2 사건 공책(JSONL journal) — 지금 실행 가능

Graphori는 작업 중 일어난 일을 한 줄짜리 JSON 기록으로 남깁니다. 이것을
`journal`이라고 부릅니다.

공책에는 대략 이런 사건이 순서대로 들어갑니다.

```text
run_created              작업 접수
graph_published          작업 지도 공개
node_status_changed      worker 준비
attempt_dispatched       명령 전달
node_status_changed      worker 배정
node_status_changed      worker 실행 중
worker_finished          프로그램 결과 수집
node_status_changed      검증 대기
node_status_changed      성공 또는 실패
run_terminal             전체 실행 종료
```

각 줄에는 앞 줄의 지문 같은 `prev_digest`와 자기 지문 `digest`가 연결됩니다.
그래서 중간 줄이 몰래 바뀌면 재생할 때 알아챌 수 있습니다. 복사해 붙여 넣은 같은
사건은 한 번만 받아들이고, 이상한 사건은 격리 폴더로 보냅니다.

### 2.3 상태 보기 — 지금 실행 가능

명령이 끝난 뒤에도 새 프로세스에서 공책을 다시 읽어 상태를 만들 수 있습니다.

```sh
python3 -m src.graphori_core.cli \
  --root "$repo_root" \
  --run-id run-demo \
  status --json
```

여기서 보는 것은 “기억해 둔 화면”이 아니라 journal에서 다시 계산한 결과입니다.
따라서 CLI를 종료했다가 다시 실행해도 같은 기록으로 상태를 만들 수 있습니다.

### 2.4 재생 검증 — 지금 실행 가능

```sh
python3 -m src.graphori_core.cli \
  --root "$repo_root" \
  --run-id run-demo \
  replay --verify --json
```

`replay`는 공책을 처음부터 읽고, `--verify`는 같은 공책을 한 번 더 읽어 두 결과가
같은지 비교합니다. 이 검사는 “화면이 그럴듯하게 움직였는가?”가 아니라
“저장된 사건으로 다시 계산해도 같은 결과가 나오는가?”를 묻습니다.

### 2.5 실행 상태 대시보드 — 지금 실행 가능

대시보드 서버는 journal을 원본으로 읽어 화면에 보여 줍니다.

```sh
python3 scripts/dashboard_server.py --root "$repo_root"
```

브라우저에서 <http://127.0.0.1:8765/>를 열면 됩니다.

대시보드는 다음 두 통로를 제공합니다.

- `GET /runs/{run_id}/snapshot`: 지금까지 기록된 전체 상태를 한 번에 가져옵니다.
- `GET /runs/{run_id}/events`: SSE로 새 사건을 순서대로 받습니다.

대시보드에는 서로 다른 세 개의 시계가 있습니다.

| 시계 | 쉬운 뜻 | 무엇으로 바뀌나요? |
| --- | --- | --- |
| liveness | “관제탑과 연락이 되나요?” | heartbeat와 연결 상태 |
| progress | “새 결과물이 생겼나요?” | progress 사건과 새 checkpoint |
| verdict | “검사자가 합격 도장을 찍었나요?” | verifier 또는 gate의 `pass`/`approve` |

heartbeat가 계속 온다고 진행률을 올리지 않습니다. 캐릭터가 깜빡인다고 성공한 것도
아닙니다. 현재 대시보드의 완료 수는 검증 사건과 통과한 terminal node를 기준으로
계산합니다.

기본 CLI의 `run-demo`는 worker 하나만 만들기 때문에 이 대시보드에 실제로는 그
worker 사건이 나타납니다. 화면에 기획·조사·설계·검증 팀이 모두 보이는 학습 장면은
Graphori의 목표 구조를 이해하기 위한 **설계 시뮬레이션**입니다.

### 2.6 Orca 연결 adapter — 선택 기능

`src/graphori_adapters/orca/adapter.py`에는 Orca CLI의 응답을 읽어 Graphori가 쓰는
형태로 정리하는 adapter가 있습니다. Orca가 없는 일반 환경에서도 core와 generic
terminal 경로는 동작해야 합니다.

이 adapter는 “Orca가 있으니 자동으로 여러 Claude Code/Codex 팀을 실행한다”는 보장이
아닙니다. 외부 응답이 없거나 필수 필드가 없으면 실패를 숨기지 않고
`adapter_unavailable` 같은 근거를 남기는 경계 adapter입니다.

## 3. 실제로 사용했을 때의 결과

다음은 저장소에서 실제로 실행한 두 경우를 짧게 보여 준 것입니다. `attempt_id`,
시간, journal 경로는 실행할 때마다 달라지므로 핵심 값만 적었습니다.

### 3.1 성공한 명령

```sh
python3 -m src.graphori_core.cli \
  --root "$repo_root" \
  --run-id learning-success \
  run -- python3 -c 'print("Graphori worker created result")'
```

핵심 결과:

```json
{
  "run_id": "learning-success",
  "terminal_status": null,
  "execution_outcome": "succeeded",
  "exit_code": 0,
  "timed_out": false,
  "stdout_truncated": false,
  "stderr_truncated": false
}
```

이어서 `status --json`을 읽으면 다음과 같습니다.

```json
{
  "event_count": 8,
  "terminal_status": null,
  "node_states": {"worker": "awaiting_verification"}
}
```

`replay --verify --json`은 사건 8개를 다시 읽고 두 번째 재생과 digest가 같아서
성공 코드(0)로 끝납니다. 이 문서에서는 그 결과를 이해하기 쉽게
`"replay_verified": true`라고 줄여 부를 수 있지만, 실제 CLI JSON의 핵심 필드는
`projection_digest`와 `events`이며 `--verify`의 종료 코드가 검증 결과입니다.

### 3.2 실패한 명령

```sh
python3 -m src.graphori_core.cli \
  --root "$repo_root" \
  --run-id learning-failure \
  run -- python3 -c 'import sys; print("problem", file=sys.stderr); sys.exit(2)'
```

핵심 결과:

```json
{
  "run_id": "learning-failure",
  "terminal_status": "failed",
  "exit_code": 2,
  "node_states": {"worker": "failed"},
  "event_count": 10
}
```

여기서 `exit_code: 2`는 **자식 명령**이 내놓은 코드입니다. Graphori의 `run` 명령
자체는 자식 실패를 알리기 위해 보통 종료 코드 1로 끝납니다. 이렇게 두 층을 나눠
기록하기 때문에 “프로그램이 실패했다”와 “Graphori 명령을 잘못 썼다”를 구분할 수
있습니다.

### 3.3 실제 결과와 화면 설명을 구분하기

| 화면에서 본 것 | 현재 의미 |
| --- | --- |
| `execution_outcome = succeeded` | 실제 자식 명령이 exit code 0으로 끝났다는 뜻입니다. 검증 완료라는 뜻은 아닙니다. |
| `worker = awaiting_verification` | 실행 결과가 수집됐고 별도의 판정이나 결정론적 검사를 기다린다는 뜻입니다. |
| `event_count = 8` | 성공한 generic 실행이 검증 전까지 기록한 실제 사건 수입니다. |
| `replay --verify` 성공 | 같은 journal을 두 번 계산해 같은 digest를 얻었다는 뜻입니다. |
| 대시보드 `progress = 0%` | 독립 verifier/gate의 합격 사건이 없다는 뜻일 수 있습니다. 실행 성공과 최종 검증 완료는 다릅니다. |
| 학습 게임의 여러 캐릭터 | Graphori의 다중 역할 구조를 배우는 시뮬레이션입니다. 현재 CLI가 자동으로 만든 여러 세션의 증거가 아닙니다. |

## 4. Graphori의 목표 구조는 어떻게 생겼나요?

코어에는 작업 위험도에 따라 그래프를 만드는 `compile_topology`가 있습니다. 이것은
작업을 어떤 역할로 연결할지 계산하고 규칙을 검사합니다.

```text
Router(기획) → Worker(실행) → Observer(관찰)
```

검사가 필요한 작업은 다음처럼 됩니다.

```text
Router → Worker → 독립 Verifier → Observer
```

아주 위험한 작업은 다음처럼 됩니다.

```text
Router → Worker → Verifier들 → Fan-in Verifier → Human Gate → Observer
```

각 역할을 쉬운 말로 보면 다음과 같습니다.

| 역할 | 하는 일 | 학교에 비유하면 |
| --- | --- | --- |
| Router | 큰 일을 카드와 순서로 나눕니다. | 반장 겸 계획표 담당 |
| Worker | 맡은 카드를 실제 파일·명령으로 바꿉니다. | 만들기 담당 |
| Verifier | 만든 사람과 다른 시선으로 다시 시험합니다. | 채점 담당 |
| Fan-in | 여러 검사 결과를 하나로 모읍니다. | 여러 심사표를 한 장으로 합치기 |
| Human Gate | 사람이 범위·증거·중단 여부를 결정합니다. | 마지막 도장을 찍는 선생님 |
| Observer | 사건, 연락 상태, 진행, 사용량을 지켜봅니다. | 관제탑 |

### 동시 작업은 왜 빠른가요?

서로의 파일을 건드리지 않는 작업이라면 동시에 시작할 수 있습니다.

```text
              ┌─ 정보조사 ─┐
기획 ────────┤            ├─ 결과 합치기(fan-in) → 설계 → 구현
              └─ 설계 준비 ─┘
```

예를 들어 “공식 규칙 찾기”와 “현재 폴더 구조 읽기”는 서로 기다리지 않아도 됩니다.
둘의 카드가 모두 도착하면 다음 카드가 열립니다. 한 작업이 같은 파일을 동시에
고치면 충돌할 수 있으므로 Graphori의 계약은 그런 branch를 자동으로 병렬화하지
않습니다.

중요한 사실: 이 그림은 **코어가 지키는 그래프 규칙과 목표 구조**입니다. 현재
기본 CLI의 `run`은 이 그림 전체를 실제 여러 세션으로 실행하지 않고 한 worker
adapter 경로를 실행합니다.

## 5. 현재 기능 표

| 기능 | 상태 | 실제 근거 |
| --- | --- | --- |
| 명시적 argv로 일반 명령 실행 | 지금 실행 가능 | [`src/graphori_core/cli.py`](../src/graphori_core/cli.py), [`process_supervisor.py`](../src/graphori_core/process_supervisor.py) |
| workspace 경로·환경 변수·출력 크기 제한 | 지금 실행 가능 | [`PORTABILITY_CONTRACT.md`](architecture/PORTABILITY_CONTRACT.md)와 process supervisor |
| 성공·실패·시간 초과·트리 종료 기록 | 지금 실행 가능 | [`agent_runner.py`](../src/graphori_core/agent_runner.py), `worker_finished` payload |
| JSONL journal, 단일 writer, hash chain, 중복·깨진 사건 격리 | 지금 실행 가능 | [`journal.py`](../src/graphori_core/journal.py) |
| `status` projection | 지금 실행 가능 | [`cli.py`](../src/graphori_core/cli.py)와 reducer |
| `replay --verify` 결정성 검사 | 지금 실행 가능 | [`cli.py`](../src/graphori_core/cli.py), journal replay |
| HTTP snapshot + SSE replay | 지금 실행 가능 | [`dashboard.py`](../src/graphori_core/dashboard.py) |
| liveness / progress / verdict 분리 | 지금 실행 가능 | dashboard projection과 [`DASHBOARD_CONTRACT.md`](architecture/DASHBOARD_CONTRACT.md) |
| 위험도에 따른 Router·Worker·Verifier·Gate 그래프 컴파일 | 코어 계약·테스트 | [`compiler.py`](../src/graphori_core/compiler.py), [`TEAM_TOPOLOGY.md`](../TEAM_TOPOLOGY.md) |
| 독립 verifier와 revise 1회·Human Gate 정책 | 코어 계약·설계 | [`0005-mvp-simple-single-verifier.md`](decisions/0005-mvp-simple-single-verifier.md) |
| 여러 Claude Code/Codex 세션의 실제 동시 실행 | 아직 안 됨 | 기본 CLI가 한 worker graph를 만든다는 구현 주석 |
| interactive PTY, GUI, browser 자동화 | 아직 안 됨 | [`PORTABILITY_CONTRACT.md`](architecture/PORTABILITY_CONTRACT.md) |
| 매 실행마다 자동으로 완성 보고 게임 생성 | 아직 안 됨 | 현재 게임은 저장소 증거를 설명하는 오프라인 학습 페이지 |

## 6. 학습 게임은 어떻게 공부하게 하나요?

[Graphori 학습 게임](GRAPHORI_LEARNING_GAME.html)은 단순히 움직이는 화면을 보는
페이지가 아닙니다. 다음 순서로 참여합니다.

1. **보기**: 실제 실행 경로와 설계 시뮬레이션을 먼저 나란히 봅니다.
2. **예측하기**: 다음 사건이나 상태를 직접 고릅니다.
3. **확인하기**: 정답·오답과 함께 실제 JSON 사건을 확인합니다.
4. **설명하기**: 캐릭터 카드를 눌러 “누가 무엇을 만들고, 어떤 증거를 남기는가”를
   자기 말로 다시 연결합니다.
5. **되돌아보기**: 성공 실행과 실패 실행을 비교하고, 어떤 기능이 지금 되고 어떤
   기능이 앞으로 필요한지 선택합니다.

### 교육학을 어떻게 반영했나요?

아래는 연구에서 직접 가져온 원칙과, 그 원칙을 Graphori 게임에 적용한 설계입니다.

| 학습 원칙 | 쉽게 말하면 | 게임에 넣은 방법 |
| --- | --- | --- |
| 인출 연습 | 읽기만 하지 말고 먼저 기억에서 꺼내 봅니다. | 다음 사건·진짜 기능·progress 의미를 먼저 선택하게 합니다. |
| 설명이 있는 피드백 | 틀렸다고만 하지 말고 왜 틀렸는지 알아야 합니다. | 선택 뒤 실제 사건과 연결된 짧은 이유를 보여 줍니다. |
| worked example | 처음에는 완성된 예를 보고 따라갑니다. | 성공 실행의 10개 사건과 JSON을 먼저 제공합니다. |
| 인지 부하 줄이기 | 한 번에 너무 많은 새 내용을 넣지 않습니다. | 실제 실행, 설계 그래프, 대시보드를 별도 카드로 나눕니다. |
| 간격 두고 다시 보기 | 한 번에 몰아서 외우기보다 나중에 다시 떠올립니다. | 일시정지·한 사건 재생·다시 시작을 제공하고 핵심 질문을 반복합니다. |
| 게임 기반 학습의 조건 | 게임 모양만으로 공부가 되는 것은 아닙니다. | 장식보다 실제 목표·선택·피드백·설명을 중심에 둡니다. |

연구 근거와 “연구가 직접 말한 것” 및 “Graphori에 적용한 설계 추론”의 구분은
[`docs/research/GRAPHORI_LEARNING_RESEARCH.md`](research/GRAPHORI_LEARNING_RESEARCH.md)에
기록했습니다.

## 7. 직접 실행하기 전 체크리스트

- [ ] 먼저 학습 게임에서 `실제 실행`과 `설계 시뮬레이션` 배지를 구분했나요?
- [ ] `run`의 자식 명령 결과와 Graphori 명령 자체의 종료 코드를 구분했나요?
- [ ] heartbeat는 연락 신호이고, verifier verdict는 합격 도장이라는 차이를 아나요?
- [ ] `status`는 화면의 기억이 아니라 journal을 다시 읽어 만든 결과임을 확인했나요?
- [ ] `replay --verify`가 성공해도 독립 검증이 끝났다는 뜻은 아니라는 점을 아나요?
- [ ] 여러 캐릭터가 나오는 장면이 현재 generic CLI의 실제 여러 세션을 뜻하지 않는다는
      안내를 읽었나요?

## 8. 다음에 개선하면 좋은 것

현재 기능과 목표 구조 사이의 가장 큰 빈칸은 “그래프를 계산하는 코어”와 “여러
실제 세션을 동시에 실행하는 adapter” 사이입니다. 다음 개선은 이 순서가 자연스럽습니다.

1. 하나의 Run 안에서 독립적인 두 branch를 실제로 실행하는 최소 adapter를 만듭니다.
2. 각 branch가 실제 `heartbeat`, `progress_reported`, `worker_finished` 사건을 보내게
   합니다.
3. 독립 Verifier가 worker 결과를 다시 실행하고 `verdict_recorded`를 남기게 합니다.
4. 실패·revise·Human Gate 흐름을 한 번의 실제 fixture로 검증합니다.
5. 실행 사건에서 완료 보고용 `WHAT / HOW / EVIDENCE` 자료를 자동으로 뽑습니다.
6. 그 자료만으로도 게임 보고서가 만들어지는지 확인합니다.

이렇게 해야 화면의 캐릭터가 “예쁘게 움직이는 그림”을 넘어서, 실제로 일한 팀의
상태를 보여 주는 도구가 됩니다.

## 참고한 저장소 문서와 연구

- [`skills/graphori/SKILL.md`](../skills/graphori/SKILL.md): Graphori 작업 규칙
- [`TEAM_TOPOLOGY.md`](../TEAM_TOPOLOGY.md): 역할과 topology 계약
- [`GRAPHORI_ARCHITECTURE.md`](architecture/GRAPHORI_ARCHITECTURE.md): core·adapter 구조
- [`EVENT_PROTOCOL.md`](architecture/EVENT_PROTOCOL.md): 사건·재생·검증 계약
- [`GRAPHORI_LEARNING_RESEARCH.md`](research/GRAPHORI_LEARNING_RESEARCH.md): 학습 설계 근거
