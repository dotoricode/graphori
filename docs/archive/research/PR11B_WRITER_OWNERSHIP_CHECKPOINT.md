# PR11B writer ownership checkpoint

## 범위

PR11B는 canonical JSONL journal의 single-writer 전제를 OS process 경계까지 확장한다.
ready inbox producer는 기존 tmp→ready 원자 rename을 유지하며 ownership lock을 요구하지
않는다. lock은 canonical append/recovery를 수행하는 `JournalWriter`에만 적용한다.

## 선택한 경계

- lock scope: `.graphori/runs/<run_id>/journal/.writer.lock`
- lock primitive: Python stdlib의 POSIX `fcntl.flock`, non-blocking exclusive
- unsupported platform: writer를 열지 않고 fail-closed
- contention: 두 번째 writer는 journal을 읽거나 ready event를 append하기 전에 한국어 ownership 오류로 실패
- crash: flock은 process exit에서 OS가 해제하며 persistent stale-owner marker를 해석하지 않는다

동일 root의 다른 `run_id`는 lock inode가 달라 병렬 writer를 허용한다.

## Dogfooding result

- run: `run-pr11b-dogfood`
- graph: coordinator → implementation → independent verification
- implementation route: Direct Codex, `gpt-5.6-terra`, medium
- total elapsed: about 19m 37s, including one verifier-requested rework
- final dogfood state: blocked because the rework changed
  `docs/architecture/EVENT_PROTOCOL.md` outside the declared write scope
- observed safety behavior: verification failure created rework instead of silently
  succeeding, and the later write-scope violation stopped the run

The blocked dogfood run was not rewritten as a success. Coordinator review then
fixed two concrete gaps found by the exercise:

1. The crash fixture now retains the writer object until `os._exit`, so it proves
   operating-system lock release instead of accidentally relying on `__del__`.
2. Product sidecars (`run-spec.json` and `run-plan.json`) are persisted only after
   writer ownership is acquired. A losing contender therefore changes neither the
   canonical journal nor its adjacent run metadata.

## Verification

- focused writer/product/provider/engine tests: 62 passed, 2 skipped
- full suite: 372 passed, 6 skipped
- compileall: passed
- `git diff --check`: passed
