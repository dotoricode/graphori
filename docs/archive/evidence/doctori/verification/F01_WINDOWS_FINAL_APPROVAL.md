# F01 Windows 최종 승인 확인

확인일: 2026-08-09  
확인 범위: Windows current gate만 확인

## 최종 판정

**APPROVE**

현재 Windows 결과는 승인한다. macOS에서는 실행하지 않았으므로 판정은 계속 **deferred/unknown**이다.

## 무엇을 확인했나

`F01_JUNCTION_FIX_REPORT.md`와 `F01_JUNCTION_TEAM2_REAUDIT.md`는 수정 뒤의 결과를 기록한다. 두 문서의 결론과 현재 코드·테스트·산출물이 서로 맞는다.

`F01_BOUNDARY_TEAM2_AUDIT.md`와 `F01_FINAL_CROSS_MODEL_ACCEPTANCE.md`의 **REVISE**는 수정 전 단계에서 발견한 문제를 기록한 역사 기록이다. 그 문서들이 말한 문제는 `ast`와 `blobs/sha256` 폴더를 검사하도록 고친 뒤의 재감사에서 해결되었으므로, 최신 결과와 모순으로 세지 않았다.

## 코드와 공격 차단 확인

- `PathBoundary.validate`는 폴더의 겉 이름만 보지 않고, junction이 가리키는 실제 폴더까지 확인한다.
- `analyze`는 Clang을 실행하거나 파일을 만들기 전에 `ast`, `blobs/sha256`, `events`를 검사한다.
- 소스 코드에서 직접 파일을 쓰는 곳은 `PathBoundary` 안에만 있다. 다른 곳은 이 안전한 함수로 쓰기를 요청한다.
- `PathBoundaryTest`만 표적으로 다시 실행했다. 6개 테스트가 모두 통과했다.
- 두 팀 문서에 기록된 Windows junction 공격도 같은 코드와 테스트에 맞으며, 외부 표시 파일은 그대로이고 외부 폴더에 AST나 ELF 파일을 만들지 못한 결과와 모순되지 않는다.

## 산출물 핵심 값 대조

`build/f01-junction-fix`를 직접 읽어 다음 값을 확인했다.

| 확인 항목 | 확인값 |
|---|---:|
| events 줄 수 | 23 |
| query `path_count` | 1 |
| AST required fields / golden | passed / passed |
| AST normalized SHA-256 | `bedbba8008040cf1c8b9df4fad0a707a791a6dc7302807ce88075572e08030fa` |
| AAR SHA-256 | `7fcfd08eef5808f114a1d558e198598a49b22d3445c579467124b51b2ef6effc` |
| ELF/target SHA-256 | `71107e47b38d1b028fb4d536e31c05308a1c5be94b57b23d754c1df7a1aa1807` |
| replay | `byte_identical=true`, `row_count_equal=true`, `replay_mismatch=0` |
| Windows report | `gate=windows-current`, `status=observed` |
| macOS report | `deferred/unknown` |

실제 파일을 다시 해시한 결과 AAR와 ELF 값도 위 값과 같았다. 이벤트 파일은 마지막 빈 줄을 제외하면 23줄이다.

## 절대 경로와 비밀값 확인

저장 후보인 run 폴더의 JSON/JSONL/TXT 및 AAR·ELF 바이트를 확인했다.

- raw AST를 포함한 텍스트 산출물에서 실제 Windows 사용자 절대 경로(`C:\\Users`, `D:\\` 등)는 **0건**이었다.
- 현재 사용자 계정 이름이나 프로젝트의 실제 절대 경로도 **0건**이었다.
- AAR와 ELF 안에서도 같은 절대 경로 패턴은 발견되지 않았다.
- 흔한 API 키, 개인 키, 액세스 토큰 형태와 `password`·`secret` 같은 비밀값 표지도 발견되지 않았다.
- `build/f01-junction-fix` 안에 남은 junction/reparse point도 없었다.

따라서 현재 Windows 산출물을 저장 대상으로 삼아도, 이번 확인 범위에서는 사용자 Windows 절대 경로나 비밀값이 남았다는 증거가 없다.

## 남은 범위

macOS 실행 증거가 없으므로 macOS gate는 승인하지 않는다. macOS에서 F01 전체 단계를 실행하기 전까지 macOS 상태는 **deferred/unknown**으로 유지한다.
