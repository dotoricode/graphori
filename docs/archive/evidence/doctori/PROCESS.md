# Doctori 작업 과정

이 문서는 Doctori가 어떤 순서로 만들어지고 있는지 쉽게 설명하는 안내판입니다.
확인하지 않은 일은 완료라고 쓰지 않습니다.

## 무엇을 만들고 있나요?

Doctori는 Android 앱의 연결을 찾아 주는 도구입니다. Kotlin이나 Java의 함수가
JNI를 거쳐 C/C++ 코드와 연결되고, 빌드 결과인 AAR과 `.so` 파일까지 이어지는지
증거를 모아 설명합니다. 증거가 부족하면 “모름”이라고 표시합니다.

첫 범위는 Android Kotlin/Java ↔ JNI ↔ C/C++ ↔ Gradle/CMake ↔ AAR/ELF입니다.
iOS, 실행 중 추적, 자동 코드 수정, 웹 콘솔은 첫 범위에 넣지 않습니다.

## 처음 세운 계획

1. Doctori의 목표와 베끼지 않기 규칙을 정합니다.
2. 필요한 도구, 라이선스, 위험한 가정을 조사합니다.
3. 증거를 저장하는 방법과 Android JNI 연결 방법을 설계합니다.
4. 두 검증팀이 같은 중요한 결과를 각각 다시 읽고 문제를 찾습니다.
5. 가장 작은 F01 실험을 만들어 빌드, 분석, 저장, 질문, 재실행을 확인합니다.
6. F01이 같은 결과를 다시 내면 그다음 실험을 차례로 추가합니다.

## 중간에 바뀐 계획

- 임시 이름을 Doctori로 정리했습니다.
- iOS, 런타임 추적, 자동 수정, 웹 화면은 Android 증거 기능 뒤로 미뤘습니다.
- Platty의 코드·프롬프트·스키마·명령어·비공개 동작은 복사하지 않고, 공개된 문제를 독립적으로 다시 설계합니다.
- 첫 native 분석은 별도 LLVM을 직접 만들기보다 선택한 Android NDK 안의 Clang을 찾는 방향으로 정했습니다.
- `jvm.library_load`는 사용하고 `native.depends_on`은 첫 범위에서 미룹니다.
- 테스트를 못 찾았다는 사실만으로 “테스트 없음”이라고 결론내리지 않습니다.
- 장기 회사 환경은 MacBook 중심의 macOS 우선 gate로 두되, 현재 세션은
  `Decision 0006` (not published)과
  `WINDOWS_CURRENT_SESSION.md` (not published)에 따라
  Windows에서 먼저 구현·중간 검증합니다. macOS는 회사 MacBook 또는 macOS CI를
  확보할 때까지 `status=deferred`, `confidence=unknown`으로 남깁니다.
- 설계가 통과되기 전에는 F01 구현을 시작하지 않는 문턱을 추가했습니다.

## 지금 상태

Windows current gate는 실제 실행과 두 모델 확인까지 끝났다. Claude Code 독립
재감사는 **PASS**였고, Codex의 Windows 최종 교차 승인은 **APPROVE**였다.
이 판정은 Windows에만 적용한다. macOS는 아직 실행하지 않았으므로
`deferred/unknown`이다. 따라서 F01 구현 마일스톤은 macOS 확인 전까지
`reviewing`으로 유지한다.

## 진행률은 어떻게 정하나요?

화면의 전체 진행률은 사람이 임의로 적은 숫자를 그대로 보여 주지 않습니다. 팀과
마일스톤의 상태를 읽어 아래 규칙으로 매번 다시 계산합니다.

- `done`(완료)은 100점입니다.
- `reviewing`(검토 중)은 70점입니다.
- `working`(작업 중)은 50점입니다.
- `planned`(예정), `deferred`(미룸), `unknown`(모름)은 0점입니다. 아직 하지
  않았거나 확인하지 못한 일을 완료처럼 세지 않습니다.
- 마일스톤 평균에 60%, 팀 평균에 40%를 곱해 더합니다. 한쪽 자료가 없으면
  있는 쪽의 평균만 사용합니다.

따라서 `dashboard/process.json`에는 `overallProgress` 숫자를 저장하지 않습니다.
팀이나 마일스톤 상태를 바꾸면 `updatedAt`도 같은 변경 시각으로 함께 바꿉니다.
Windows F01 게이트가 성공해도 macOS 게이트를 실행하지 않았다면 macOS는
`deferred` 또는 `unknown`이고, 전체 화면은 100%가 될 수 없습니다.

### 완료

- 제품 목표, 범위, clean-room 규칙을 문서화했습니다.
- 조사 문서와 Evidence Core·Android Bridge 설계를 작성했습니다.
- 두 모델의 독립 상호감시 방식과 장기 macOS 우선 정책을 기록했습니다.
- 설계 2팀의 F01 감사가 **REVISE**였고, 설계 1팀이 지적 사항을 문서에
  반영했습니다.
- 설계 2팀이 수정본을 독립 재검토한 결과 **PASS**로 판정했습니다
  (`docs/design/F01_IMPLEMENTATION_ACCEPTANCE.md`). 지적됐던 4개 결함
  모두 CLOSED로 확인됐습니다.
- SQLite 스키마와 대표 질의의 문법 검사를 통과했습니다.

### 진행 중

- 기획팀이 다음 구현 순서와 작업 상태를 관리하고 있습니다.
- F01 구현은 Windows current gate에서 확인했지만, macOS 실행 전이라 최종
  완료가 아닌 `reviewing`입니다.

### 아직 남음

- 회사 MacBook 또는 macOS CI에서 F01 전체 단계를 실행해야 합니다.
- 그 전까지 macOS는 `deferred`/`unknown`이며 Windows 성공을 macOS 성공으로
  표현하지 않습니다.
- F01이 통과한 뒤에만 F02 이후 실험과 추가 extractor를 시작합니다.

### 막힘과 주의점

현재 문서에 기록된 별도 기술적 막힘은 없습니다. F01 Windows 경로는 실제 실행과
두 모델 확인을 마쳤지만, macOS 실행 증거는 아직 없습니다. 따라서 Windows 결과를
macOS 결과나 F01 전체 완료로 넓혀 말하지 않습니다. 검색 결과나 모델의 추측은
증거가 아닙니다.

## 1팀과 2팀의 상호감시

1팀은 Codex, 2팀은 Claude Code를 사용합니다. 두 팀은 일을 반으로 나누는 팀이
아니라 같은 중요한 결과를 서로 독립적으로 확인하는 감시 쌍입니다.

한 팀이 먼저 문서를 만들 수 있지만 다른 팀이 같은 문서와 근거를 다시 확인하기
전에는 최종 승인하지 않습니다. 두 팀의 판단이 다르면 한쪽을 몰래 지우지 않고
두 의견을 모두 기획팀에 보내 근거를 비교합니다. F01 구현 때도 작성한 모델과
검토하는 모델을 따로 둡니다.

## 운영체제 순서

장기 제품 정책과 최종 회사 gate는 MacBook 중심의 macOS 우선입니다. 그러나
현재 세션은 Mac에 접근할 수 없으므로 Decision 0006에 따라 Windows에서 먼저
구현·중간 검증합니다. Windows 실행 결과에는 `host_os=windows`를 기록하고,
macOS를 실행하지 못한 항목은 `status=deferred`, `confidence=unknown`으로
남깁니다. 제품 코드와 일반 명령은 PowerShell이나 Windows 전용 경로에
의존하지 않아야 하며, 나중에 같은 fixture/commit으로 회사 Mac 또는 macOS CI
gate를 별도로 실행합니다.

## 중요한 진실 한 줄

F01은 Windows에서 실제로 빌드·분석·저장·질의·replay까지 실행했고, Claude
독립 재감사 PASS와 Codex Windows APPROVE를 받았습니다. 이것은 Windows
current gate의 승인이지 macOS 승인이나 F01 전체 최종 완료가 아닙니다.
전체 진행률은 상태에서 자동 계산하고, macOS는 계속 `deferred/unknown`으로
표시합니다.

## Dashboard v3 독립 검수 결과

2026-08-08 검증팀 (Team 1)이 Orca 안에서 열린 `http://127.0.0.1:43117/dashboard/`
를 다시 확인했습니다. 큰 화면의 따뜻한 픽셀 분위기, 여섯 방의 3×2 배치, 팀별
키보드·문서·돋보기 모션, `process.json` 진행률, 오래된 데이터 경고는 확인했습니다.
하지만 약 571 CSS px 폭으로 좁히면 `검증팀 (Team 1)`과 `검증팀 (Team 2)`가 둘 다
`검증팀 (Tea…)`처럼 잘려 눈으로 구별되지 않았습니다. 이 첫 검수의 판정은
**REVISE**였습니다. 재확인 시각은 `2026-08-08T21:28:12+09:00` (한국 시간)이며,
더 좁은 320px 화면과 기본 데스크톱에서 `검증 1팀`·`검증 2팀`, 여섯 방 3×2,
가로 넘침 없음을 다시 확인했습니다. 따라서 현재 대시보드 v3의 독립 최종 판정은
**PASS**이며, 자세한 근거는
``docs/verification/DASHBOARD_V3_VISUAL_REVIEW.md`` (not published)에 있습니다.

이 기록은 F01 구현 진행 상태나 F01의 완료·진행률을 바꾸지 않습니다.

## 2026-08-09 Windows 대시보드 서버 확인

대시보드를 보여 주는 작은 서버만 다시 켰습니다. 제품 코드나 화면 코드는 바꾸지
않았습니다. 이 확인은 Windows에서만 했고, macOS 확인은 아직 하지 않았으므로
macOS 상태는 계속 `deferred`(나중에 확인)와 `unknown`(아직 모름)입니다.

- 시작 전 43117번은 예전 `python -m http.server 43117 --bind
  127.0.0.1 --directory <PROJECT_ROOT>`였습니다. 명령이
  정확히 맞는 것을 확인한 뒤에만 이 프로세스를 멈췄습니다.
- 시작 전 43118번은 PID 20176의 `dashboard/serve.py --port 43118`였습니다.
  이것도 명령이 정확히 맞는 것을 확인한 뒤에만 멈췄습니다. 43119번에는 듣고
  있는 프로세스가 없었고, 다른 포트는 건드리지 않았습니다.
- Doctori 폴더에서 `python dashboard/serve.py --port 43117`을 숨김 백그라운드로
  시작했습니다. 새 PID는 19652이고, 실제 명령줄도 이 명령과 일치합니다.
- 이제 43117번은 PID 19652가 듣고 있고, 43118번과 43119번은 듣고 있지 않습니다.
- 43117번의 `/dashboard/`와 `/dashboard/process.json`은 HTTP 200을 돌려줍니다.
  JSON 응답은 UTF-8로 읽히고 JSON으로도 정상 해석됩니다. `Cache-Control`에는
  `no-store`, `no-cache`, `must-revalidate`가 모두 들어 있습니다.
- 기존 Orca `Doctori 설명 페이지`(Explainer) 탭은 남겨 두고, Orca에
  `http://127.0.0.1:43117/dashboard/` 탭 하나만 새로 열어 활성화했습니다.
  탭이 두 개 이상 생기지 않도록 목록을 다시 확인했습니다.
- 당시 화면 검증 시점의 상태 데이터 기준으로 진행률 82%, `aria-valuenow=82`,
  막대 배율 약 `0.817`, 여섯 카드 3×2 배치, 콘솔 오류 0건, PNG 작업자
  스프라이트 로딩을 확인했습니다. 현재 화면 진행률은 상태에서 자동 계산합니다.
  자세한 서버 전후 기록은
  ``DASHBOARD_LIVE_SERVER_DEPLOY.md`` (not published)에
  적었습니다.

## F01 구현 설계 계획 기록 (2026-08-08 당시)

- 2026-08-08 시작: 설계 1팀이 F01의 빌드·분석·Evidence Ledger 저장·질의·같은 입력 재실행 설계를 작성하기 시작했습니다. 장기 macOS gate와 현재 세션 Windows 우선 예외를 구분하고, 확인하지 않은 실행 결과는 완료라고 쓰지 않습니다.
- 2026-08-08 완료: 당시 설계 단계에서 설계 1팀이 `docs/design/F01_IMPLEMENTATION.md`를 작성했습니다. 문서는 Kotlin→JNI→C/C++→Gradle/CMake→AAR/ELF→Ledger의 범위, NDK Clang 탐색, argv 실행·sandbox·timeout·출력 제한, exact scope, Windows current gate와 장기 macOS gate, 명령, 완료 조건을 정리했습니다. 실제 구현·실행 결과는 아래의 별도 실행 기록에 추가했습니다.
- 2026-08-08 감사 시작: 설계 2팀(Claude Code)이 `docs/design/F01_IMPLEMENTATION.md`를 기존 문서(EVIDENCE_CORE.md, ANDROID_BRIDGE.md, GOLDEN_TEST_PLAN.md, REVISION_ACCEPTANCE.md, MACOS_READINESS.md, WINDOWS_CURRENT_SESSION.md)와 Decision 0006에 대조하는 독립 감사를 시작했습니다. 작성한 팀의 결론을 그대로 믿지 않고 파일 경로와 명령을 직접 다시 확인했습니다.
- 2026-08-08 감사 결과: 설계 2팀이 **REVISE**로 판정했습니다(`docs/design/F01_IMPLEMENTATION_REVIEW.md`). 큰 방향은 옳지만, (1) 현재 세션 Windows 우선과 장기 macOS deferred/unknown을 Decision 0006·WINDOWS_CURRENT_SESSION.md로 명시하지 않은 점, (2) 저장소 구조와 `:doctori-analyzer` 모듈 이름이 어긋난 점, (3) NDK Clang AST adapter·필수 field·fingerprint·golden·unknown frontier 계약이 부족한 점, (4) Windows current gate의 명령·산출물·replay·완료조건이 빠진 점을 고쳐야 한다고 적었습니다. 설계 1팀의 원본 문서는 감사팀이 직접 고치지 않았습니다.
- 2026-08-08 수정 완료: 당시 설계 단계에서 설계 1팀이 위 네 가지 REVISE 지적만 근거로 `docs/design/F01_IMPLEMENTATION.md`를 수정했습니다. `doctori-analyzer/`와 `:doctori-analyzer`를 통일하고, Windows 명령·성공 산출물·byte-identical replay·실패/unknown 처리를 구체화했습니다.
- 2026-08-08 재검토 결과: 당시 설계 단계에서 설계 2팀이 수정본을 독립 재검토해 **PASS**로 판정했습니다(`docs/design/F01_IMPLEMENTATION_ACCEPTANCE.md`). 4개 결함이 CLOSED로 확인됐습니다. 이 기록은 설계 문서 판정이며, 이후 실제 F01 구현·Windows 실행은 아래 별도 기록에 남겼습니다.

## F01 구현 실행 기록 (Windows 현재 게이트)

- 2026-08-08 시작: `doctori-analyzer` Gradle 모듈, Kotlin/JVM 분석기, Android library fixture, Evidence Ledger 테스트를 만들었습니다. Gradle 8.10.2, AGP 8.7.3, Kotlin 2.0.21, JDK 17, Android SDK 34, NDK 26.3.11579264, CMake 3.22.1을 lock 파일에 적었습니다.
- 2026-08-08 확인: `gradlew.bat --version`, `:library:bundleReleaseAar`, `preflight`, `analyze`, `ingest`, `query`, `replay`가 Windows에서 성공했습니다. Kotlin `NativeApi.sum(II)I`, static JNI 이름, NDK Clang AST adapter golden, `jni/arm64-v8a/libnativebridge.so`, ELF export, SQLite path row 1개를 확인했습니다.
- 2026-08-08 확인: 첫 Ledger export와 같은 event를 다시 넣은 replay export가 SHA-256 `sha256:c7c411cd7824063c92c2367e7c3eb05c9b549d3d7d23666ab36f37d492cfc7d3`로 byte-identical이고 `replay_mismatch=0`입니다. `bridge_only` 질의의 테스트 상태는 `out_of_scope`/`test_extractor_skipped`로 남겼습니다.
- 2026-08-08 교정: 중간 실행에서 NDK 미설치, SQLite WAL을 transaction 안에서 켠 오류, 여러 SQL 문을 한 번에 실행한 오류가 각각 실패했습니다. NDK를 실제 SDK에서 설치하고 SQLite schema 실행 순서와 문장별 실행을 고친 뒤 Windows 필수 명령을 다시 실행해 성공했습니다. 이 실패들은 해결된 Windows 개발 오류이며 macOS 미실행은 실패가 아니라 `deferred`/`unknown`입니다.
- 2026-08-09 Claude Code 독립 재감사: 외부 `ast`와 `blobs/sha256` junction 공격이 파일을 만들기 전에 차단되는지 새 폴더에서 확인했고, 전체 테스트 15개와 핵심 산출물을 다시 대조해 **PASS**로 판정했습니다(`docs/verification/F01_JUNCTION_TEAM2_REAUDIT.md`).
- 2026-08-09 Codex 교차 승인: Windows current gate의 최신 결과를 **APPROVE**로 판정했습니다(`docs/verification/F01_WINDOWS_FINAL_APPROVAL.md`). 이 판정은 Windows current gate에만 적용합니다.
- 2026-08-09 남은 일: macOS는 실행하지 않았으므로 `status=deferred`, `confidence=unknown`입니다. macOS gate가 끝날 때까지 F01 구현 마일스톤은 `reviewing`이며 F01 전체 최종 완료라고 쓰지 않습니다.
