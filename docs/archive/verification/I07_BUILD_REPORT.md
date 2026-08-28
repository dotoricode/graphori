# I07 빌드 보고서

## 한 일

Orca 전용 코드를 `src/graphori_adapters/orca`에 격리했습니다. 어댑터는 공개 `orca ... --json` 명령만 명시적인 argv로 실행하고, SQLite나 내부 파일은 읽지 않습니다. 연결된 결과와 저장된 fixture는 같은 Graphori canonical event로 바뀝니다.

모르는 필드는 버립니다. run/task 같은 필수 정보가 없거나 JSON이 깨지면 성공으로 꾸미지 않고 `event_quarantined`와 `adapter_unavailable` 이유를 남깁니다. 실행 실패와 시간 초과도 core journal을 건드리지 않고 호출 결과로만 남습니다.

## 확인

- fake CLI: 정상 projection, malformed JSON, nonzero 반환을 unittest로 확인했습니다.
- 실제 Windows Orca: `orca status --json`은 성공했고, `run-show`와 `task-list`는 없는 fixture ID라 `run_not_found`를 반환했습니다. 모두 read-only 호출입니다.
- 연결 결과와 fixture projection 계약 테스트를 추가했습니다.
- 독립 검증 전 진행률은 요구대로 **6/9**로 유지합니다.

## 남은 점

실제 Run/Task가 존재하는 Orca 계정에서의 성공 응답 검증은 별도 환경 검증으로 남습니다. 이 어댑터는 해당 응답이 없어도 Graphori replay를 망가뜨리지 않습니다.
