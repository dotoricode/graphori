# 제한 사항

- Direct provider에는 각자 설치·로그인된 CLI가 필요합니다. Graphori는 model이나 계정을 제공하지 않습니다.
- generic verifier는 받은 command만 보고합니다. 통과는 그 command의 근거일 뿐 일반적인 정확성 주장이 아닙니다.
- locale은 표시만 바꿉니다. canonical identifier는 영어이며 digest에는 번역 label이 들어가지 않습니다.
- journal replay는 저장 파일이 존재하고 읽힌다고 가정합니다. 안전하지 않은 resume는 의도적으로 거부합니다.
- dashboard와 학습 게임은 설명용 UI이지 외부 provider가 활성이라는 증거가 아닙니다.
- 72회 세 조건 benchmark와 더 작은 과거 비교를 공개합니다. 72회 비교는 production 저장소가 아니라 작은 deterministic Python fixture 4종을 사용했으므로 특정 코드베이스에서 Graphori가 더 낫다는 증거는 아닙니다.
- 공개 릴리스 근거는 로컬 검사기가 만듭니다. 이 저장소는 GitHub Actions를 사용하지 않습니다.
- generic adapter 전용 검사는 macOS 26.5.2 x86_64 한 대에서 Python 3.11·3.14로 통과했습니다. 이 결과는 해당 환경의 근거이며 모든 macOS 버전과 CPU를 보장하지 않습니다. Linux 릴리스 검사는 통과했다고 주장하지 않으며, Windows 설치와 Job Object 동작은 실험적 범위입니다.
- Actions를 쓰지 않으므로 CodeQL, OpenSSF Scorecard, OIDC 빌드 증명은 이번 릴리스 범위에 없습니다. 공개 근거의 경계는 Gitleaks, `pip-audit`, SBOM, 산출물 해시와 재현 가능한 로컬 명령입니다.
