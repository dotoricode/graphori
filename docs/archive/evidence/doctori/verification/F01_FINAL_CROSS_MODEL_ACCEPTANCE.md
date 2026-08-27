# F01 최종 교차 승인 보고서

확인 날짜: 2026-08-09 (Asia/Seoul)

작성자: 검증 1팀(Codex)

## 결론

**Windows current gate: REVISE**

두 팀이 처음 지적한 세 가지 문제는 고쳐졌다. 두 새 실행 폴더의 숫자도 서로
맞고, 핵심 증거가 망가졌다는 흔적도 없다. 그러나 프로젝트 밖 폴더를 막는 검사가
너무 늦게 실행되고, 원본 AST 파일에 사용자 컴퓨터의 절대 경로가 남아 있어
안전한 게시를 아직 승인할 수 없다.

이 판정은 **Windows current gate에만 적용**한다. macOS는 실행하지 않았으므로
계속 `deferred/unknown`이며, F01 전체 완료를 뜻하지 않는다.

## 중간 확인

### 1. 첫 REVISE의 세 가지 확인

| 처음 문제 | 확인 결과 |
| --- | --- |
| ELF 주소가 늘 첫 폴더를 가리킴 | 해결됨. `Analyzer.kt:281-286`이 실제 `runDir`를 사용한다. 두 새 폴더의 event 주소도 각각 자기 폴더를 가리킨다. |
| 새 폴더의 정확한 5단계와 최종 보고서가 부족함 | 해결됨. 수정 보고서와 Claude 재감사에 `preflight → analyze → ingest → query → replay`의 정확한 명령이 있고, 두 새 폴더 모두 `windows-gate-report.json`이 있다. |
| `.cxx` 캐시가 무시되지 않음 | 해결됨. `.gitignore:7`의 `**/.cxx/`가 실제 CMake cache를 무시한다. `git ls-files`에도 `.cxx` 파일은 없다. |

### 2. 두 새 실행 폴더의 결과

`build/f01-fix`와 `build/f01-team2-fix-audit`의 보고서, event, query, AST,
AAR/ELF, replay 파일을 직접 대조했다.

현재 코드의 `F01AcceptanceTest`도 직접 실행해 `BUILD SUCCESSFUL`을 확인했다.
다만 이 테스트는 아래 안전성 문제를 검사하지 않으므로, 성공만으로 gate를
승인할 수는 없다.

| 확인 항목 | `build/f01-fix` | `build/f01-team2-fix-audit` | 판정 |
| --- | ---: | ---: | --- |
| event 줄 수 | 23 | 23 | 일치 |
| query `path_count` | 1 | 1 | 일치 |
| AST golden / required fields | passed / passed | passed / passed | 일치 |
| AST normalized SHA | `bedbba80...e08030fa` | `bedbba80...e08030fa` | 일치 |
| AAR SHA | `7fcfd08e...2ef6effc` | `7fcfd08e...2ef6effc` | 일치 |
| ELF/target SHA | `71107e47...a1aa1807` | `71107e47...a1aa1807` | 일치 |
| ELF locator | 자기 폴더의 `blobs/sha256/...` | 자기 폴더의 `blobs/sha256/...` | 해결됨 |
| first/replay export rows | 52 / 52 | 52 / 52 | 일치 |
| replay SHA | `a5eceeed...3e425d` / 동일 | `10323a79...d2eb90` / 동일 | 일치 |
| byte / row / mismatch | `true` / `true` / 0 | `true` / `true` / 0 | 통과 |

폴더 이름이 다르기 때문에 두 실행의 replay SHA가 서로 다른 것은 정상이다.
중요한 것은 각 폴더 안에서 first와 replay가 바이트까지 같은지이다. query에는
Kotlin 함수, JNI 이름, AAR의 arm64 ELF가 한 경로로 연결되어 있었다.

## 안전성 확인과 남은 문제

### 프로젝트 밖 `run-dir` 거부

`elfLocatorPath()`에는 프로젝트 밖이면 멈추는 검사가 있다. Claude 재감사의
수동 실행에서도 `analyze`가 그 오류를 냈다. 하지만 이 검사는 실행의 맨 앞이
아니다.

- `Analyzer.kt:40`과 `Toolchain.kt:50`은 경로 확인 전에 `createDirectories(runDir)`를 실행한다.
- 정상 순서로 프로젝트 밖 `run-dir`를 주면 `preflight`가 먼저 manifest와 context를 만든다.
- 그 뒤 `analyze`는 AST 원본, stderr, build manifest 등을 쓰고 나서야 `elfLocatorPath()`를 호출한다.
- `replay`도 `Main.kt:56`에서 보고서를 쓰기 전에 공통 경로 검사를 하지 않는다.
- 현재 회귀 테스트(`F01AcceptanceTest.kt:40-51`)는 프로젝트 안의 두 폴더만 확인하며, 밖의 폴더나 심볼릭 링크를 테스트하지 않는다.

따라서 “오류가 난다”는 것은 확인됐지만, “밖에 아무것도 쓰지 않는다”는 것은
확인되지 않았다. `normalize()`와 `startsWith()`만으로는 프로젝트 안의 링크가
밖을 가리키는 경우도 막지 못할 수 있다. 모든 명령의 시작 부분에서 실제 경로를
확인하고, 밖이면 파일을 만들기 전에 중단하는 테스트가 필요하다.

### 사용자 절대 경로

event, query, manifest, ledger export, replay 보고서, normalized AST에는 사용자
절대 경로가 없었다. 하지만 두 새 폴더의 `ast/raw.json`에는 Clang이 만든 원본
파일 주소가 들어 있고, 각 파일에서 사용자 폴더 경로가 15,533번 발견됐다.
이 파일들은 현재 `build/` 규칙으로 Git에는 올라가지 않지만, run-dir 전체를
다른 사람에게 보내거나 게시하면 개인정보가 함께 전달된다.

원본 AST를 게시하지 않거나, 저장 전에 경로를 지워서 고정된 상대 주소로 바꾸고,
모든 산출물에 사용자 절대 경로가 없는지 검사하는 회귀 테스트를 추가해야 한다.
Claude 재감사의 “새 폴더 JSON 전체에 사용자 절대 경로가 없다”는 결론은
`ast/raw.json`을 놓쳤으므로 이 부분은 승인 근거로 사용할 수 없다.

## 기존 문서 6곳의 절대 경로 정리 범위

아래 경로들은 단순한 예시가 아니라 실제 Windows 확인 때 기록한 명령줄, 임시
캡처 주소, 또는 실제 CMake cache 검색 결과다. 보고서에는 사용자 이름이나 실제
절대 경로를 다시 쓰지 않는다.

| 문서 | 분류 | 게시 전 정리 |
| --- | --- | --- |
| `docs/PROCESS.md` | 실제 서버 명령 기록 1건 | 프로젝트 루트를 `<PROJECT_ROOT>` 또는 상대 명령으로 바꾼다. |
| `docs/verification/DASHBOARD_LIVE_SERVER_DEPLOY.md` | 실제 서버 2개 명령 기록 | 프로젝트 루트와 Python 설치 경로를 각각 `<PROJECT_ROOT>`, `<PYTHON>`으로 바꾼다. |
| `docs/verification/DASHBOARD_V3_VISUAL_REVIEW.md` | 실제 임시 캡처 주소 6건 | 캡처 파일을 게시하지 않으면 주소를 삭제하고, 필요하면 저장소 상대 경로 또는 “임시 파일 미보존”으로 바꾼다. |
| `docs/verification/DASHBOARD_VISUAL_REVIEW.md` | 실제 임시 캡처 주소 7건 | 위와 같은 방식으로 7건을 정리한다. |
| `docs/verification/F01_IMPLEMENTATION_TEAM2_AUDIT.md` | 실제 `.cxx` cache 검색 결과와 사용자 이름 언급 | 검색 명령의 사용자 부분과 절대 경로를 지우고 `fixtures/F01/library/.cxx/...` 같은 상대 경로만 남긴다. |
| `docs/verification/VALIDATION_TEAM2_DASHBOARD.md` | 실제 실행 중 서버 명령 기록 1건 | 프로젝트 루트를 `<PROJECT_ROOT>` 또는 상대 경로로 바꾼다. |

즉, 여섯 문서 모두 실제 값이며 “예시라서 그대로 게시해도 됨”으로 분류할 수
없다. 이번 구현 수정 파일을 바꾸라는 뜻은 아니며, 문서 게시 전 위 여섯 곳만
정리하면 된다.

## 최종 판단

핵심 기능 결과는 두 팀이 교차 확인했고, 첫 REVISE의 세 항목도 해결됐다.
따라서 **BLOCK은 아니다**. 다만 프로젝트 밖 쓰기 방지, 심볼릭 링크 경계,
원본 AST의 사용자 절대 경로 처리를 보완하고 다시 검사해야 하므로 현재
Windows gate는 **REVISE**다.
