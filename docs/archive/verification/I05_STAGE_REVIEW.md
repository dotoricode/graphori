# I05 독립 검증 보고서

검증일: 2026-08-10 (Windows PowerShell)

## 결론

**VERDICT: APPROVE** (Windows 범위만)

I05는 명령을 안전하게 실행하고, 결과를 기록하고, 다시 읽는 작은 문입니다. 이 문을 최신 코드와 계약에 맞춰 따로 확인했습니다. Windows에서는 모든 확인을 통과했습니다. macOS는 실행하지 않았으므로 `deferred/unknown`으로 남깁니다.

## 읽은 내용

- `I05_BUILD_REPORT.md`
- canonical 5단계 계약: 명시적 argv, 안전한 cwd, 환경 변수 allowlist, 출력 제한, timeout 때 전체 자식 종료
- `process_supervisor.py`, `_win_job.py`, `agent_runner.py`, `cli.py`
- 관련 unittest와 `PORTABILITY_CONTRACT.md`, `EVENT_PROTOCOL.md`

## 실행 결과

- `python -m compileall -q src tests`: 통과
- `python -m unittest discover -s tests -v`: **105개 통과, 실패 0개**
- 별도 임시 workspace에서 adversarial probe: **29개 통과, 실패 0개**

## 29개 probe에서 확인한 것

1. shell 문자열 argv 거부
2. 빈 argv 거부
3. `..` 탈출 거부
4. 중첩 `a/../../x` 탈출 거부
5. 절대 cwd 거부
6. Windows drive 경로 거부
7. UNC 경로 거부
8. 대소문자 충돌 거부
9. 실제 Windows junction 탈출 거부
10. workspace 안의 정상 cwd 허용
11. allowlist 안전 변수 전달
12. allowlist 밖 변수 제거
13. allowlist에 넣어도 secret 이름 제거
14. 실제 자식 환경에서 secret key가 보이지 않음
15–18. stdout/stderr byte cap과 line cap이 걸리고 멈추지 않음
19–20. 정상 종료와 nonzero 종료 구분
21. timeout 표시
22. tree-kill 방식과 근거가 정직함
23. 실제 grandchild PID가 종료 뒤 `tasklist`에 없음
24. workspace 밖 marker 파일 hash 불변
25–27. CLI `run`, `status`, `replay --verify`
28. replay digest가 두 번 같음
29. 같은 run-id 두 번째 실행 거부

timeout tree probe에서는 실제 `parent -> grandchild`를 만들었습니다. Windows에서 `tree_kill_method=job_object` 또는 정직한 `taskkill_fallback`만 허용했고, 이번 실행은 Job Object 경로를 사용했으며 grandchild PID가 `tasklist`에 남지 않았습니다.

## 범위와 남은 확인

Windows Job Object의 생성·할당·종료가 실제로 사용되는 것을 확인했습니다. Job Object를 쓸 수 없을 때는 `taskkill /T /F`로 바꾸고 evidence에 실패 이유를 남기는 코드도 확인했습니다. macOS POSIX process-group 경로는 이 Windows 컴퓨터에서 실행하지 않았으므로 PASS라고 쓰지 않습니다.

이 보고서는 구현 코드를 바꾸지 않았습니다. 다음 단계는 별도 macOS/CI에서 같은 fixture를 실행하는 것입니다.
