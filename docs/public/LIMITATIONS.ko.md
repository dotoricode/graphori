# 제한 사항

- Direct provider에는 각자 설치·로그인된 CLI가 필요합니다. Graphori는 model이나 계정을 제공하지 않습니다.
- generic verifier는 받은 command만 보고합니다. 통과는 그 command의 근거일 뿐 일반적인 정확성 주장이 아닙니다.
- locale은 표시만 바꿉니다. canonical identifier는 영어이며 digest에는 번역 label이 들어가지 않습니다.
- journal replay는 저장 파일이 존재하고 읽힌다고 가정합니다. 안전하지 않은 resume는 의도적으로 거부합니다.
- dashboard와 학습 게임은 설명용 UI이지 외부 provider가 활성이라는 증거가 아닙니다.
- 작은 과거 v1 방식/v2 비교 수치 하나를 공개합니다. 세 조건 공개 benchmark는 결과 없이 protocol만 준비돼 있습니다.
- 공개 릴리스 근거는 로컬 검사기가 만듭니다. 이 저장소는 GitHub Actions를 사용하지 않습니다.
- 전체 테스트는 macOS에서 실행했지만 프로세스 트리 종료·경로 이탈·심볼릭 링크 전용 이식성 검사는 아직 수행하지 않았습니다. 따라서 macOS 플랫폼 판정은 보류입니다. Linux 릴리스 검사는 통과했다고 주장하지 않으며, Windows 설치와 Job Object 동작은 실험적 범위입니다.
- Actions를 쓰지 않으므로 CodeQL, OpenSSF Scorecard, OIDC 빌드 증명은 이번 릴리스 범위에 없습니다. 공개 근거의 경계는 Gitleaks, `pip-audit`, SBOM, 산출물 해시와 재현 가능한 로컬 명령입니다.
