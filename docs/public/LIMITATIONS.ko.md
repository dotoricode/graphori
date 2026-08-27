# 제한 사항

- Direct provider에는 각자 설치·로그인된 CLI가 필요합니다. Graphori는 model이나 계정을 제공하지 않습니다.
- generic verifier는 받은 command만 보고합니다. 통과는 그 command의 근거일 뿐 일반적인 정확성 주장이 아닙니다.
- locale은 표시만 바꿉니다. canonical identifier는 영어이며 digest에는 번역 label이 들어가지 않습니다.
- journal replay는 저장 파일이 존재하고 읽힌다고 가정합니다. 안전하지 않은 resume는 의도적으로 거부합니다.
- dashboard와 학습 게임은 설명용 UI이지 외부 provider가 활성이라는 증거가 아닙니다.
- 이 베타에는 공개 성능 수치가 없습니다. benchmark protocol은 결과가 아니라 scaffold입니다.
- 공개 릴리스 근거는 로컬 검사기가 만듭니다. 이 저장소는 GitHub Actions를 사용하지 않습니다.
- 현재 공개 베타 검사는 macOS의 Python 3.11과 3.12에서 실행했습니다. Windows 전용 설치와 Job Object 동작은 검증 완료 주장이 아니라 실험적 지원입니다.
- Actions를 쓰지 않으므로 CodeQL, OpenSSF Scorecard, OIDC 빌드 증명은 이번 릴리스 범위에 없습니다. 공개 근거의 경계는 Gitleaks, `pip-audit`, SBOM, 산출물 해시와 재현 가능한 로컬 명령입니다.
