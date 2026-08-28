# 로컬 검증 기록

실제로 실행한 명령만 기록합니다. 특정 플랫폼 전체를 지원한다는 주장은 아닙니다.

## 2026-08-28 · clean-history 전체 릴리스 검사

- 트리: 부모 없는 commit `83fe5a5`.
- 환경: macOS 26.5.2, x86_64, Python 3.11.15.
- `python3.11 scripts/verify_public_release.py --output
  build/release-artifacts-clean-history` 성공.
- 테스트 416개 통과, opt-in/platform 검사 5개 건너뜀.
- 문서 index, Skill 검사, dashboard HTTP smoke, 현재 tree와 단일 commit 이력
  개인정보 감사 통과.
- Gitleaks가 tree와 단일 commit에서 유출을 찾지 못함.
- wheel·sdist 생성, Twine metadata, 격리 Runtime 설치, Codex·Claude Skill 격리
  설치, `pip-audit`, CycloneDX SBOM, SHA-256 생성 통과.
- macOS 이식성 record 7개 통과 및 build artifact 옆에 포함.
- GitHub Actions, package 배포, artifact upload는 하지 않음.

이 검사 뒤 public `main`을 같은 commit으로 강제 갱신하고 과거 prerelease/tag와 일반
작업 branch를 제거했습니다. 새 public clone에서 tree/history 감사를 다시 통과했습니다.

## 2026-08-28 · 공개 72회 비교

- Source: `02fb61d`, Codex CLI 0.150.1, Claude Code 2.1.245.
- 실행표: provider 2 × 조건 3 × 과제 4 × 반복 3 = 72회.
- 실행 72/72와 숨은 검사 216/216 통과, 완료 보고 72/72 일치.
- Scope 위반, 재작업, infrastructure unknown: 0.
- 원자료 JSONL, deterministic 분석과 provider별 결과는
  [`benchmarks/three_arm/`](../../benchmarks/three_arm/)에 있습니다.

## 2026-08-28 · macOS 이식성 전용 검사

- 트리: `b7edaea`
- 명령: `python scripts/verify_macos_portability.py`
- 환경: macOS 26.5.2, x86_64
- Python: 3.11.15, 3.14.6
- PASS: 프로세스 트리 종료, 경로 이탈, POSIX 심볼릭 링크 이탈, 대소문자 충돌,
  JSONL tmp→ready 공개, replay, idempotency.
- PASS: 실제 generic adapter 성공, 자식 프로세스 취소, fan-in, 명시적 verdict replay
  lifecycle.
- 출력: fixture마다 `platform`, `fixture`, `verdict`, `evidence_id`, `command`,
  `host`, 자체 포함된 테스트 근거와 SHA-256 hash를 기록합니다.
- 로컬 릴리스 검사기는 이 record를 wheel, sdist, SBOM, `SHA256SUMS` 옆의
  `macos-portability.json`으로 보존합니다.
- fixture 추가 뒤 Python 3.14.6 전체 검사: 416개 통과, 5개 건너뜀.

이 결과는 기록된 호스트와 generic adapter fixture 범위의 macOS 판정만 바꿉니다.
Linux나 Windows 릴리스 지원 근거는 아닙니다.

## 2026-08-28 · 공개 릴리스 후속 후보

- 트리: `312bea4`
- 환경: macOS 26.5.2, x86_64
- Python 3.14.6: `python -m unittest discover -s tests` — 413개 통과,
  6개 건너뜀.
- Python 3.11.15: product-entry 검사 15개, local-release 검사 6개 통과.
- 영문 최상위 도움말, 영문 입력으로 자동 선택한 plan 도움말, 한국어 도움말,
  임시 작업 폴더에서 실행한 영문 `graphori plan` smoke가 모두 성공했습니다.
- Markdown 137개 문서 index를 확인했습니다. 보관된 benchmark 8행은 숨은 검사
  8건 통과, 범위 위반 0건으로 다시 계산됐습니다.
- Gitleaks는 현재 트리와 도달 가능한 커밋 17개에서 유출을 찾지 못했습니다.

당시에는 아래 이력 개인정보 문제 때문에 전체 릴리스 검사가 중단됐습니다. 위의
clean-history 기록이 그 blocker를 해소했습니다. 이 이전 실행에서 package나 release를
배포하지 않았습니다.

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

macOS 전용 검사는 위 호스트 범위에서 통과했습니다. Linux 릴리스 검사는 통과했다고
주장하지 않으며, Windows 설치와 Job Object 동작은 실험적 범위입니다.
