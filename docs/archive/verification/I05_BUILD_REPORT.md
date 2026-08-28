# I05 구현 보고서 — generic terminal adapter

> 작성자: 구현 담당자 1명(단독). 이 보고서는 자체 점검 결과이며 승인(approve)이
> 아니다. [ADR 0005](../../decisions/0005-mvp-simple-single-verifier.md)에 따라
> 이 milestone 완료 뒤 별도 확인자가 스케줄될 수 있다. **독립 검증 전이므로
> 전체 진행률은 그대로 4/9로 유지한다.**

## 1. 12살도 이해하는 설명

지금까지는 "공책에 사건을 적는 규칙"(I03)과 "그 규칙이 진짜 맞는지 확인하는
시험"(I04)만 만들었다. 이번에는 그 공책에 적을 진짜 "일꾼을 부르고 지켜보는
사람"(ProcessSupervisor)을 만들었다.

일꾼을 부를 때 지키는 약속은 이렇다.

- 일꾼에게 시킬 일은 "명령어를 문자열로 이어붙이지 않고" 항상 목록으로
  또박또박 준다(`["python", "-c", "print(1)"]`처럼). 문자열로 주면 바로
  거절한다. 나쁜 사람이 문자열 안에 몰래 다른 명령을 숨길 수 있기 때문이다.
- 일꾼이 일할 방(작업 폴더, cwd)은 우리가 정한 "작업 공간" 밖으로 못
  나간다. `..`로 나가려 하거나, 완전히 다른 드라이브 경로를 주거나, 대소문자만
  다른 이름으로 헷갈리려 하거나, junction(가짜 문)으로 몰래 밖을 가리키면
  전부 거절한다.
- 일꾼에게 주는 환경 변수(env)는 "줘도 되는 목록"(allowlist)에 있는 것만
  최소로 준다. 그 목록에 있어도 이름이 `SECRET`, `TOKEN`, `PASSWORD`,
  `API_KEY`처럼 비밀번호 냄새가 나면 절대 안 준다. 실제로 이 컴퓨터의 진짜
  환경변수로 시험해 보니 `GEMINI_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`
  같은 진짜 비밀 이름들이 자동으로 걸러졌다.
- 일꾼이 화면에 너무 많이 쏟아내면(무한 출력) 정해진 바이트 수·줄 수만 받고
  나머지는 버린다. 그래도 일꾼 프로그램이 멈추거나 죽지 않게 계속 읽어서
  버려준다(파이프가 막히지 않게).
- 시간 제한(timeout)을 넘기면 일꾼만 죽이는 게 아니라 그 일꾼이 몰래 낳은
  "손자 프로세스"까지 다 같이 끝낸다. Windows에서는 "Job Object"라는
  운영체제 기능을 먼저 쓴다. 이 기능이 실패하면 조용히 숨기지 않고
  "이번엔 실패해서 `taskkill /T /F`로 대신 껐다"고 정직하게 기록으로 남긴다.
- macOS/Linux용 코드(POSIX process group)도 같이 준비해 뒀지만, 이 컴퓨터는
  Windows라서 그 코드는 아직 실제로 확인 못 했다. 그래서 "macOS도 통과했다"고
  절대 말하지 않는다.
- 화면이나 마우스를 흉내내는 PTY/GUI/브라우저 자동화는 이번 범위가 아니다.

이 일꾼 부르는 사람(`ProcessSupervisor`) 위에, "한 번의 시도(attempt)를
시작부터 끝까지 진행시키는 사람"(`AgentRunner`)과 "지금 몇 시인지 재는
사람"(`Clock`)을 붙였다. 마지막으로 Orca 없이도 터미널에서 바로 쓸 수 있는
명령줄 도구(`graphori-cli` = `python -m graphori_core.cli`)를 만들어서, 일을
시키고(`run`), 지금 상태를 보고(`status`), 기록을 다시 읽어서 확인하는
(`replay`) 것까지 전부 Orca 없이 된다.

## 2. 무엇을 만들었나

새 파일(모두 `src/graphori_core` 아래, 외부 라이브러리 없이 표준 라이브러리와
`ctypes`만 사용):

- `clock.py`: `Clock` port와 기본 구현 `SystemClock`(UTC 문자열 + monotonic
  시간). journal의 `_default_clock`과 같은 시간 형식을 쓴다.
- `process_supervisor.py`: `ProcessSupervisor` port의 generic 구현.
  - `_validate_argv`: 문자열(shell 명령)을 받으면 즉시 거절, 명시적 argv
    목록만 허용.
  - `resolve_workspace_path`: cwd/경로를 항상 workspace root 상대경로로만
    받고, 기존 `paths.safe_join`(I03에서 만든 `..`/절대/UNC/대소문자충돌/
    symlink·junction 차단 로직)을 그대로 재사용한다. 두 번째 진리를 새로
    만들지 않았다.
  - `build_child_env`: env allowlist 필터 + 이름 기반 secret 패턴
    (`SECRET|TOKEN|PASSWORD|API_KEY|...`) 필터. allowlist에 있어도 이름이
    secret처럼 보이면 뺀다(방어적 이중 검사).
  - `_BoundedReader`: `readline` 대신 고정 크기 `read` 청크로 stdout/stderr를
    읽어서, 줄바꿈 없는 무한 출력에도 바이트 상한을 확실히 지킨다. 상한을
    넘으면 그 뒤로도 계속 읽어서 버리기만 해서 파이프가 막히지 않게 한다.
  - `_kill_tree_windows` / `_kill_tree_posix`: timeout이 나면 Windows는 Job
    Object 우선(`_win_job.py`), 실패하면 `taskkill /PID <pid> /T /F`로
    대체하고 어떤 방법을 썼는지, Job Object가 왜 실패했는지를
    `tree_kill_method`/`tree_kill_evidence`에 정직하게 남긴다. POSIX는
    `os.setsid`/`killpg`로 구현은 돼 있지만, 이 코드 경로는 Windows
    host에서는 절대 실행되지 않고 실제로 시험된 적도 없다.
- `_win_job.py`: `ctypes`로 `kernel32.dll`의 `CreateJobObjectW`,
  `SetInformationJobObject`(`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`),
  `AssignProcessToJobObject`, `TerminateJobObject`를 감싼 얇은 wrapper.
  `sys.platform == "win32"`일 때만 import된다.
- `agent_runner.py`: `AgentRunner`가 기존 `compiler.transition_attempt`
  (I02에서 만든 Attempt 상태표)만 이용해서 `PLANNED -> DISPATCHED -> RUNNING
  -> SUCCEEDED|FAILED` 또는 `-> TIMED_OUT -> OUTCOME_UNKNOWN`으로 옮긴다.
  새 상태표를 만들지 않았다. stdout/stderr 원문은 절대 이벤트 payload에
  안 넣고 SHA-256 digest만 넣는다(경로/시크릿이 evidence에 남지 않는다는
  PORTABILITY_CONTRACT 3절 규칙).
- `cli.py`(+ `__main__.py`): `python -m graphori_core.cli --root <workspace>
  --run-id <id> run -- <argv...>` / `status` / `replay` 세 명령. `run`은
  `run_created -> graph_published -> node_status_changed(ready/assigned/
  running) -> attempt_dispatched -> [실제 프로세스 실행] -> worker_finished
  -> node_status_changed(awaiting_verification/passed|failed) ->
  run_terminal`을 실제 tmp→ready→journal 경로로 기록한다. `status`/`replay`는
  **별도 프로세스 실행에서도** 저장된 journal만 읽어서 같은 결과를 재현한다
  (메모리 상태에 의존하지 않는다). adapter의 graph는 항상 worker 노드 1개짜리
  최소 그래프이고, `EVENT_PROTOCOL.md` 4.2절대로 topology는 이벤트로 만들지
  않고 compiler(=CLI)가 결정적으로 재구성한다.

기존 `paths.py`, `journal.py`, `reducer.py`, `compiler.py`, `models.py`,
`evidence.py`는 수정하지 않고 그대로 재사용했다.

## 3. 테스트 (모두 표준 `unittest`, `tests/` 아래)

| 파일 | 확인하는 것 |
|---|---|
| `test_process_supervisor.py` (신규, 16개) | 정상 종료(exit 0), nonzero exit, argv 문자열/빈 목록 거절, cwd 탈출(`..`, 절대경로, **실제 Windows junction**, 대소문자 충돌) 거절, 정상 상대 cwd 허용, env allowlist가 실제 자식 프로세스 환경에도 적용되고 secret 이름은 allowlist에 있어도 빠짐, stdout 바이트 상한/줄 수 상한이 행 없이도 잘림, **실제 timeout 뒤 부모+손자 프로세스가 모두 죽는지 Windows `tasklist`로 확인**, workspace 밖 marker 파일이 경로 탈출 시도와 timeout kill 뒤에도 내용이 바뀌지 않음 |
| `test_agent_runner.py` (신규, 4개) | 성공 시 `SUCCEEDED`, 실패 시 `FAILED`, timeout 시 `TIMED_OUT -> OUTCOME_UNKNOWN` 상태 전이, worker_finished payload에 원문 대신 SHA-256 digest만 들어감 |
| `test_cli.py` (신규, 7개) | `run -> status -> replay` 전체 왕복(성공/실패/timeout), replay `--verify`로 두 번 replay해도 같은 digest, 같은 run-id로 두 번 `run`하면 거절, 출력 잘림/env allowlist가 CLI 요약에도 보임, `python -m graphori_core.cli` 실제 서브프로세스 실행 |
| 기존 78개(test_core, test_journal_*, test_paths_security, test_evidence_store, test_platform_and_failure_contract, test_docs_viewer) | 전부 회귀 없이 그대로 통과 |

## 4. 실행한 명령과 결과 (Windows, `python -m unittest`)

```
> python -m compileall -q src tests
(경고/에러 없음)

> python -m unittest discover -s tests -v
...
Ran 105 tests in 13.7s
OK
```

전체 105개 테스트 모두 통과했다(기존 78개 + 새로 만든 27개: process_supervisor
16 + agent_runner 4 + cli 7).

```
> (임시 폴더에 pip install --target으로 격리 설치)
> python -I -c "import sys; sys.path.insert(0, '<격리 폴더>'); import graphori_core;
    from graphori_core import ProcessSupervisor, AgentRunner, SystemClock; ..."
isolated import ok <class 'graphori_core.process_supervisor.ProcessSupervisor'>
                   <class 'graphori_core.agent_runner.AgentRunner'>
```

`python -I`(격리 모드, PYTHONPATH·user site 전부 무시)로 격리된 설치 폴더에서
import가 성공했다. 저장소 경로는 `sys.path`에 전혀 없었다.

```
> git diff --check
(에러 없음, LF/CRLF 자동변환 안내만 있음)
```

## 5. Windows에서 확인한 실제 증거 (adversarial fixture 포함)

- **정상 종료**: `python -c "sys.exit(0)"` → `exit_code=0`, `timed_out=False`.
- **nonzero 종료**: `sys.exit(7)` → `exit_code=7`.
- **timeout + tree kill**: 부모 프로세스가 손자 프로세스를 낳고 둘 다
  120초씩 자게 만든 뒤 `timeout_seconds=2.5`로 강제 종료. 손자가 자기 PID를
  파일에 남긴 뒤, 종료 후 실제 Windows `tasklist /FI "PID eq <pid>"`로 그
  PID가 더 이상 없는 것을 확인했다(부모만 죽고 손자는 살아남는 흔한 실패를
  실제로 걸러냄). `tree_kill_method`는 이 환경에서 `job_object`로 기록됐다
  (Job Object가 정상적으로 만들어지고 assign됨).
- **cwd/경로 탈출**: `..`, `a/../../escape`, 존재하는 절대 경로(workspace
  밖 임시폴더)를 cwd로 주면 모두 `PathSecurityError`로 거절됨.
- **Windows junction 탈출**: `mklink /J`로 workspace 안에 junction을 만들어
  밖의 폴더를 가리키게 한 뒤 그 junction을 cwd로 요청 → 거절됨(관리자 권한
  불필요, 실제 fixture로 확인, "deferred" 아님).
- **대소문자 충돌**: workspace에 `Work` 폴더가 있을 때 cwd로 `work`을
  요청하면 거절됨(같은 폴더로 착각할 수 있는 이름 충돌 차단).
- **env allowlist**: 실제 이 개발 환경의 진짜 `os.environ`으로 시험한 결과
  `GEMINI_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `APIFY_TOKEN` 등 진짜
  존재하는 비밀 이름들이 자동으로 걸러지는 것을 실제로 확인했다. 또한
  allowlist에 일부러 `MY_SECRET_TOKEN`을 추가해도 이름 패턴 때문에 자식
  프로세스 환경에 들어가지 않는 것을 자식이 직접 `os.environ`을 출력하게
  해서 확인했다.
- **출력 잘림(truncation)**: 200,000바이트를 한 줄로 쏟아내는 프로그램을
  `max_stdout_bytes=100`으로 실행 → `stdout_truncated=True`이고 실제 받은
  바이트는 100 이하, 그런데도 프로그램은 멈추지 않고 정상 종료함(파이프
  안 막힘). 1000줄을 쏟아내는 프로그램을 `max_lines=5`로 실행해도 동일하게
  잘림.
- **외부 marker 불변**: workspace 밖에 marker 파일을 만들고 SHA-256을 미리
  잰 뒤, (1) 그 폴더를 cwd로 삼으려는 탈출 시도가 거절되고 (2) 별도의
  timeout+tree-kill 작업을 실행한 뒤에도, marker 파일의 SHA-256이 그대로임을
  확인했다.
- **CLI status/replay**: `run`으로 실제 프로세스를 실행해 10개 이벤트
  (`run_created` ~ `run_terminal`)를 journal에 기록한 뒤, 별도의 `status`
  호출이 저장된 journal만 읽어서 `terminal_status=succeeded`,
  `node_states.worker=passed`를 재현했고, `replay --verify`가 같은 journal을
  두 번 replay해서 `projection_digest`가 완전히 같음을 확인했다. 실패
  fixture(`sys.exit(5)`)와 timeout fixture 모두 `terminal_status=failed`로
  올바르게 기록됐다(nonzero exit나 timeout이 자동으로 성공이 되지 않음).
  같은 `run-id`로 두 번 `run`을 실행하면 `run_created`가 `conflict`로
  거절되어 실행되지 않는다(같은 run을 몰래 다시 여는 것을 막음).

## 6. 하지 않은 것 / 남은 한계 (정직하게 기록)

- **macOS는 여전히 `deferred/unknown`이다.** POSIX process group 코드
  (`_kill_tree_posix`)는 존재하지만 이 저장소에서는 Windows host에서만
  실행됐고, 실제로 시험된 적이 없다. 이 보고서와 코드 주석 모두 "macOS PASS"를
  주장하지 않는다. 같은 fixture를 실제 macOS/CI host에서 실행하기 전까지는
  `not_verified/deferred`로 남는다.
- **Job Object 할당에는 아주 짧은 경합 구간이 있다.** `CreateProcess`로
  자식을 만든 직후에 Job Object를 assign하기 때문에, 그 사이의 아주 짧은
  순간에 자식이 이미 손자를 낳았다면 이론적으로 그 손자가 Job에 안 묶일 수
  있다. `CREATE_SUSPENDED` + 스레드 재개 방식으로 이 구간을 없앨 수 있지만
  Python `subprocess`가 메인 스레드 핸들을 노출하지 않아 이번 MVP 범위에서는
  구현하지 않았다. 시험한 fixture(부모가 즉시 손자를 낳고 둘 다 오래 자는
  경우)에서는 이 경합이 실제로 문제가 되지 않았다.
- **PTY/ConPTY/tmux/GUI·브라우저 자동화는 이번 범위가 아니다.** 이번
  adapter는 비대화형(non-interactive) 명령만 다룬다(`stdin=DEVNULL`).
  이는 요청받은 범위이자 PORTABILITY_CONTRACT.md 4절의 명시적 제외 사항이다.
- **CLI의 graph는 항상 worker 노드 1개짜리 최소 그래프다.** router/verifier/
  human_gate 같은 여러 노드짜리 topology 컴파일(`compiler.compile_topology`)은
  CLI에 아직 연결하지 않았다. 이번 범위는 "generic terminal adapter가 실제로
  Orca 없이 프로세스를 실행하고 replay할 수 있다"는 최소 MVP다.
- **자동 재시도(retry)는 만들지 않았다.** timeout이 나면 attempt는
  `OUTCOME_UNKNOWN`으로, node/run은 `failed`로 끝난다. 다시 시도하려면
  호출자가 새 attempt/run을 명시적으로 시작해야 한다(protocol 4.3절의
  "outcome_unknown -> 새 retry attempt"는 자동이 아니라 명시적이어야 한다는
  규칙을 그대로 따른 것).
- **다중 writer/다중 coordinator는 여전히 범위 밖이다.** I03+I04에서 확인한
  단일 writer 전제를 그대로 물려받았다(변경 없음).
- 자체 점검(self-check)일 뿐 독립 검증(approve)이 아니다.

## 7. 진행률

이번 작업은 [ADR 0005](../../decisions/0005-mvp-simple-single-verifier.md)에
따라 "의미 있는 마일스톤 완료"에 해당하므로, 이 보고서 이후 별도 확인자가
스케줄될 수 있다. **독립 검증이 끝나기 전까지 전체 진행률은 그대로
4/9 = 44.4%(I01, I02, I03, I04)로 유지한다.** I05는 이번 보고서로 "구현팀
자체 점검 완료, 검증 대기" 상태이며 완료(승인)로 세지 않는다. macOS는 여전히
`deferred/unknown`이다.
