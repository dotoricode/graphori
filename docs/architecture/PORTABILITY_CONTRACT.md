# Graphori portability contract

> 상태: canonical, 구현 전

## 1. 12살도 이해하는 설명

Graphori의 핵심은 콘센트가 아니라 장난감 자체다. Orca라는 멋진 콘센트에 꽂을 수도
있고, 일반 Windows 터미널에 꽂을 수도 있다. 콘센트가 바뀌어도 카드·사건·검사
규칙은 같아야 한다.

처음 MVP는 Python 표준 라이브러리만 사용한다. Orca adapter는 있으면 좋지만
필수품이 아니다. 플랫폼 판정은 같은 fixture를 실제 환경에서 실행한 기록으로만
올린다.

## 2. 지원 경계

| 환경 | 범위 | 현재 판정 |
|---|---|---|
| Windows PowerShell | generic process/file adapter, junction/symlink fixture | 설계; F01 증거는 별도 제품의 Windows 관찰(E1) |
| macOS zsh | core와 generic adapter | `pass(scope=macos-26.5.2-x86_64, python=3.11/3.14)` |
| Orca | optional Run/Task/Dispatch/heartbeat/worker_done adapter | Orca 로컬 관찰; 일반 보장 아님 |

이 표는 플랫폼 판정을 합치지 않는다. `complete(scope=windows, exclusions=[macos])`
만 허용하고 전체 `approve`로 축약하지 않는다.

## 3. 실제 portable 계약

- Python 3.x stdlib 우선: `subprocess`, `pathlib`, `json`, `hashlib`, `queue`,
  `threading`, `http.server`만 MVP 허용. 외부 dependency는 adapter 또는 후속 단계다.
- worker 실행은 non-interactive command + 명시적 argv + cwd + env allowlist다.
  shell 문자열 재조합을 기본으로 삼지 않는다.
- stdout/stderr는 bounded capture와 UTF-8 decode 오류 정책을 가진다. exit code,
  timeout, signal/termination 결과는 attempt event에 기록한다.
- 모든 기록은 run root 아래에만 쓴다. 사용자 이름, 절대 경로, secret은 evidence에
  저장하지 않고 placeholder/relative path로 normalize한다.

## 4. 프로세스와 종료

`ProcessSupervisor` port는 공통적으로 `start(argv,cwd,env)`, `poll`, `terminate(grace)`,
`kill`, `collect`를 제공한다.

- Windows: 가능하면 Job Object로 child tree를 묶고, 정상 종료 요청→grace→강제
  종료 순서를 기록한다. `TerminateProcess`는 마지막 수단이다.
- macOS: POSIX process group에 signal을 보내고 grace 후 kill한다. macOS 26.5.2
  x86_64 fixture에서 자식 프로세스 종료까지 확인했다.
- interactive PTY/ConPTY, tmux, GUI/browser 자동화는 core MVP가 아니다.

## 5. 경로·symlink·junction 규칙

1. 사용자가 지정한 run root를 절대 경로로 resolve하고 허용된 root 아래인지 확인한다.
2. 파일을 쓰기 전에 생성 예정 부모와 최종 경로를 `realpath`/reparse-aware 방식으로
   다시 검사한다.
3. Windows junction/reparse point와 POSIX symlink가 허용 root 밖을 가리키면 거절한다.
4. pre-existing path가 link인 경우 create directories/write가 시작되기 전에 실패한다.
5. `..`, drive-relative path, UNC path, case-collision을 canonical relative path로
   정규화하고 충돌이면 거절한다.
6. `inbox/tmp -> ready` rename은 같은 filesystem에서만 한다. cross-device 이동은
   원자적이라고 주장하지 않고 복사+fsync+검증 절차를 별도 구현한다.
7. run root 밖에 생성된 marker 파일의 digest와 목록은 fixture에서 그대로인지 확인한다.

F01 원문에서 AST 사용자 절대 경로 누출, 고정 ELF 경로, junction을 통한 프로젝트
밖 쓰기가 과거 REVISE로 기록되었고, 최신 Windows 재감사에서 차단되었다. Graphori는
그 결론을 “우리 adapter가 통과했다”로 복사하지 않는다. 같은 공격 fixture를 실행한
뒤에만 platform verdict를 기록한다.

## 6. Orca optional adapter

Orca adapter는 다음 mapping만 책임진다.

| Core | Orca 호출/관찰 |
|---|---|
| Run | `run-create`, `run-use`, `run-show` |
| Task | `task-create`, deps/status projection |
| Attempt | dispatch/worker-start/read |
| heartbeat | orchestration heartbeat message |
| worker finish | worker_done outcome/evidence |
| gate | decision gate 또는 CLI fallback |

Orca가 없는 경우 generic adapter가 동일한 core event를 만든다. Orca의 SQLite 내부
파일을 core가 직접 읽지 않는다. Orca version/command capability는 adapter startup
evidence에 기록하며, 실패하면 `adapter_unavailable`이지 core 상태 corruption이 아니다.

## 6.1 PR11C cold resume과 doctor

- `graphori resume`은 새 plan을 만들지 않고, 기록된 RunSpec/RunPlan/process command를
  cold replay한다. terminal Run은 절대 dispatch하지 않는다.
- 재시작 당시 dispatched/running attempt는 `outcome_unknown`으로 기록한다. 이 상태는
  retry 대상이 아니므로 pending/ready Node만 scheduler가 다시 고려한다.
- journal identity, plan digest, workspace, pinned Skill snapshot 또는 process command가
  불명확하거나 달라지면 fail-closed한다. 기존 journal을 migration/rewrite하지 않는다.
- `graphori doctor`는 읽기 전용이다. directory 생성, writer lock, journal recovery 없이
  provider, journal, Skill 계약 및 RunSpec/RunPlan/journal/skill-lock schema 호환성을
  한국어로 보고한다.

## 7. 기술 부록 A. adapter acceptance

각 fixture 결과는 `{platform, fixture, verdict, evidence_id, command, host, hash}`다.

- Windows generic: process tree 종료, path escape, symlink/junction, case collision,
  JSONL tmp→ready, replay/idempotency.
- macOS generic: `scripts/verify_macos_portability.py`가 process tree 종료, path
  escape, POSIX symlink, case collision, JSONL tmp→ready, replay/idempotency를
  실행한다. macOS 26.5.2 x86_64에서 Python 3.11·3.14로 `pass`했다.
- Orca: Orca adapter가 없거나 꺼진 상태에서 core CLI replay가 성공한 뒤, Orca를
  연결해 동일 event projection을 비교한다.
- provider usage: provider가 보고하지 않는 fixture에서는 `usage.status=unknown`이
  유지된다.

## 기술 부록 B. 이전 조사와 증거

이식성 분류·Orca 로컬 관찰은 [`PORTABILITY_AND_DEPENDENCY.md`](../archive/research/PORTABILITY_AND_DEPENDENCY.md),
보존된 7개 원문과 SHA-256은 [`MANIFEST.md`](../archive/evidence/doctori/MANIFEST.md),
F01 junction 재감사는 [`F01_JUNCTION_TEAM2_REAUDIT.md`](../archive/evidence/doctori/verification/F01_JUNCTION_TEAM2_REAUDIT.md)다.
모두 구현 전 설계 또는 Doctori의 E1 증거이며 Graphori adapter의 실행 PASS를 의미하지 않는다.
