# 로컬 검증 기록

실제로 실행한 명령만 기록합니다. 특정 플랫폼 전체를 지원한다는 주장은 아닙니다.

## 2026-08-28 · 공개 릴리스 후속 후보

- 트리: `7ef9ade`
- 환경: macOS 26.5.2, x86_64
- Python 3.14.6: `python -m unittest discover -s tests` — 413개 통과,
  6개 건너뜀.
- Python 3.11.15: product-entry 검사 15개, local-release 검사 6개 통과.
- 영문 최상위 도움말, 영문 입력으로 자동 선택한 plan 도움말, 한국어 도움말,
  임시 작업 폴더에서 실행한 영문 `graphori plan` smoke가 모두 성공했습니다.
- Markdown 137개 문서 index를 확인했습니다. 보관된 benchmark 8행은 숨은 검사
  8건 통과, 범위 위반 0건으로 다시 계산됐습니다.
- Gitleaks는 현재 트리와 도달 가능한 커밋 17개에서 유출을 찾지 못했습니다.

아래에 적은 이력 개인정보 감사 문제 때문에 전체 릴리스 검사는 여전히 중단됩니다.
패키지나 release는 배포하지 않았습니다.

## 2026-08-28 · ready 순서 병합

- 트리: 공개 `main`의 `4a1d5e3`
- 환경: macOS 26.5.2, x86_64
- Python 3.14.6: `python -m unittest discover -s tests` — 410개 통과,
  6개 건너뜀.
- Python 3.11.15: `python3.11 -m unittest discover -s tests -p
  'test_journal_*.py'` — journal 검사 26개 통과.
- ordering/concurrency 검사 묶음을 10회 연속 실행해 모두 통과했습니다.

그보다 앞선 Python 3.11 전체 로컬 검사에서는 테스트 406개와 compile, 문서 index,
Skill, dashboard smoke까지 통과했습니다. 이후 공개 이력에 noreply가 아닌 작성자
식별값 1개가 있어 Git 이력 개인정보 감사에서 중단됐습니다. 그 뒤의 Gitleaks,
패키지 생성·설치·감사, SBOM, 해시 단계는 이 기록의 통과 항목으로 주장하지 않습니다.

## 근거의 경계

위 명령은 이식성 계약의 프로세스 트리 종료·경로 이탈·심볼릭 링크 전용 검사를
충족하지 않습니다. 따라서 macOS 플랫폼 판정은 보류입니다. Linux 릴리스 검사는
통과했다고 주장하지 않으며, Windows 설치와 Job Object 동작은 실험적 범위입니다.
