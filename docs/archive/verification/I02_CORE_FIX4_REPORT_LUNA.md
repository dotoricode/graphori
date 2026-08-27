# I02 portable core revision-4 수정 보고서

작성일: 2026-08-09 (Windows, Python 3.12)

## Finding

revision-3에서는 `StateReducer`가 이미 만들어진 `Run` 객체나 `Task.run_id`를 보고
“`run_created`가 이미 처리됐다”고 잘못 생각할 수 있었습니다. 그래서 시작 사건인
`run_created` 없이도 `graph_published`와 `run_terminal`이 통과하는 길이 있었습니다.

이번 revision-4의 범위는 이 한 가지 lifecycle projection 문제입니다. `PROCESS`,
`dashboard`, `adapter`, `journal`과 Stage3의 실제 hash chain/dedup writer는 건드리지
않았습니다.

## Code

`src/graphori_core/reducer.py`를 수정했습니다.

- `_run_created_applied`라는 별도 표시를 추가했습니다. Run 객체가 있거나
  `Task.run_id`가 채워져 있어도 이 표시가 켜지지 않으면 시작 사건으로 인정하지 않습니다.
- `Task.run_id`만 보고 가짜 Run을 미리 만들던 동작을 없앴습니다. 실제 `run_created`가
  적용될 때만 Run projection을 만듭니다.
- `run_created`에서 Task ID, 알려진 Task/Run ID, graph version이 서로 맞는지 확인합니다.
  첫 사건의 Task ID가 다르면 바로 거절합니다.
- `graph_published`는 실제 `run_created` 뒤에만 허용하고, 중복·terminal 뒤의 역전·graph
  version 감소를 거절합니다.
- `run_terminal`은 `run_created`와 `graph_published` 뒤에만 허용하며, 이미 끝난 Run의
  terminal 상태 중복 또는 변경을 모두 거절합니다.

## Test

`tests/test_core.py`에 Codex/Claude가 각각 발견한 최소 재현을 합친 회귀 테스트 2개를
추가했습니다.

- 미리 넣은 `Run` 객체가 있어도 `graph_published`/`run_terminal`이 통과하지 않는지 확인
- 첫 사건의 Task ID 불일치, `run_created` 중복, `graph_published` 중복,
  `run_terminal` 중복이 모두 거절되는지 확인

실행한 명령:

```text
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
python -m pip install . --no-deps --target <temporary-directory>
python -c "import graphori_core"
```

추가로 직접 재현한 결과:

```text
FAIL_CLOSED graph_published
FAIL_CLOSED run_terminal
FAIL_CLOSED mismatched_first_task
```

## Result

기존 19개 테스트와 새 회귀 테스트 2개를 합친 총 21개가 모두 통과했습니다.
`compileall`, `git diff --check`, 임시 target 설치 및 설치 경로 import도 성공했습니다.
core는 stdlib-only이며 macOS 검증은 실행 환경이 Windows뿐이라 deferred/unknown입니다.

수정한 파일은 다음 3개입니다.

- `src/graphori_core/reducer.py`
- `tests/test_core.py`
- `docs/verification/I02_CORE_FIX4_REPORT_LUNA.md`

잔여 위험은 Stage3의 실제 JSONL writer, hash 계산/chain, monotonic sequence,
중복 dedup, crash-tail quarantine가 아직 구현 범위 밖이라는 점입니다. macOS에서의
실행 결과도 이 Windows 작업에서는 확인하지 않았습니다.
