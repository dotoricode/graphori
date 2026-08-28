# I07 독립 검증 보고서

검증 날짜: 2026-08-10 (Windows)

## 결론

**VERDICT: APPROVE (Windows 범위)**

I07은 Orca가 없어도 Graphori 핵심 기능이 흔들리지 않도록 만든 선택 기능입니다. 실제 검증에서 핵심 코드는 Orca를 직접 import하지 않았고, SQLite나 어댑터 내부 파일을 직접 열지 않았습니다. macOS는 이 컴퓨터에서 실행하지 않았으므로 **deferred/unknown**으로 남깁니다.

## 다시 해 본 검사

- 최신 커밋: `19533df`
- Windows unittest: **116/116 통과**
- `python -m compileall -q src tests`: 통과
- 격리 import: `python -I`에서 `src`만 명시해 `graphori_core` import 성공
- 독립 probe: **25개 모두 통과**
- core journal 불변 probe: 잘못된 ready JSON은 quarantine으로 이동하고 기존 journal은 그대로였음

probe는 명시적 argv, timeout, 없는 실행 파일, nonzero 종료, malformed JSON, unknown field, 필수 field 누락, stdout byte bound, run/task/dispatch/heartbeat/worker_done/gate/progress 정규화, idempotency, `adapter_unavailable`/quarantine, 연결·disconnected fixture 동일 projection을 확인했습니다. core의 Orca import와 어댑터의 SQLite/file 직접 접근도 없었습니다.

## 실제 Orca CLI 근거

모든 호출은 상태를 바꾸지 않는 read-only 호출입니다.

- `orca status --json`: 성공, runtime `ready`, `reachable: true`, Orca `1.4.177`
- 없는 run `run_i07_nonexistent_20260810`: `run_not_found`, 종료 코드 1
- 그 run의 task 조회: 역시 `run_not_found`, 종료 코드 1

## 진행률

I07을 독립 검증했으므로 전체 진행률은 **7/9 = 77.8%**로 올립니다. macOS 실제 실행과 다음 단계는 아직 완료로 세지 않습니다.
