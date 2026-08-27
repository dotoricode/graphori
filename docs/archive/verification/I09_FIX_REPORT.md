# I09 감사 차단 결함 수정 보고서

- 기준: `feat/mvp-demo-i05-i08`의 I09 감사 결과
- 범위: REVISE 자동 상한과 그 문서·회귀 테스트만 수정
- 상태: 수정 및 로컬 검증 완료, 독립 재검증 전이므로 진행률은 **8/9 유지**

## 처음 발견한 문제

I09 감사에서 활성 MVP 계약이 서로 다르게 적힌 것을 찾았다. ADR 0005 §9와
`docs/IMPLEMENTATION_PLAN.md` I02 acceptance는 자동 REVISE를 한 번만 허용하고
두 번째 REVISE를 Human Gate로 보내라고 하지만, ADR 0002와 실제 코드는 세 번의
자동 수정을 허용했다. 그래서 `RevisionController()`는 첫 번째와 두 번째
REVISE에도 새 revision worker node를 만들었고, 네 번째 호출에서야
`ESCALATED`가 되었다.

## 수정 내용

1. 테스트를 먼저 현재 계약으로 바꿨다. 기본 `RevisionController`에서 첫 번째
   `revise`는 `REVISED`, 두 번째는 `ESCALATED`인지 확인하고, 두 번째 호출 뒤
   `task:revision-2`와 추가 worker/rework edge가 생기지 않는지 확인한다.
2. `compiler.py`의 기본 `max_revisions`를 `1`로 바꿨다. 명시적으로 다른 값을
   전달하는 생성자 사용은 남겨 두었지만, 인자를 생략하는 Graphori MVP 기본은
   항상 1회다.
3. ADR 0002에 ADR 0005가 자동 revise 상한·WIP·고정 verifier/team 정책을
   부분 대체한다는 주석을 추가했다. 예전 3회와 WIP 4는 과거 기록일 뿐 현재
   활성 정책이 아니며, 어린이도 읽을 수 있게 현재 규칙을 다시 적었다.
4. 과거 감사 기록은 당시 실패를 증명하는 자료이므로 보존하되, 현재 테스트와
   새 보고서는 두 번째 REVISE가 Human Gate로 올라가는 표현을 사용한다.

## 명령별 검증 결과

| 명령 | 결과 |
|---|---|
| `python -m unittest tests.test_core.CoreContractTests.test_revision_limit_is_one_and_second_revise_escalates_without_new_worker` (수정 전) | **RED 재현**: 두 번째 호출이 `REVISED`여서 실패 |
| 같은 targeted unittest (수정 후) | **PASS** |
| `python -m unittest discover -s tests -v` | **PASS, 118/118** |
| `python -m compileall -q src tests scripts graphori` | **PASS** |
| `python scripts/dashboard_smoke.py` | **PASS** (`status=pass`, HTTP finite smoke) |
| `python graphori/scripts/validate_skill.py graphori` | **PASS** |
| `python scripts/generate_ci_evidence.py --platform windows --output build/ci-artifacts/ci-evidence-windows-i09-fix.json` | **PASS**, 5 fixture manifest |
| `git diff --check` | **PASS** |

실제 전체 unittest 실행은 `Ran 118 tests in 14.640s`와 `OK`를 출력했다.

독립 감사자가 새 SHA를 다시 확인하기 전에는 I09를 승인으로 올리지 않는다.
따라서 `docs/PROCESS.md`의 진행률은 수정 후에도 **8/9 (88.9%)**로 유지한다.
