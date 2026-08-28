# I08 빌드 보고서

## 무엇을 만들었나요?

Graphori가 GitHub에서 자동으로 검사되도록 `.github/workflows/ci.yml`을 만들었습니다.
Windows는 Python 3.11과 3.12로 나누어 전체 unittest와 contract test, `compileall`, 대시보드 짧은 실행, skill 검사, 증거 해시를 실행합니다. macOS도 같은 portable/core/adapter/dashboard fixture와 POSIX 프로세스 종료 fixture를 실제 runner에서 실행합니다.

## 증거를 어떻게 읽나요?

`scripts/generate_ci_evidence.py`가 OS, fixture, verdict, evidence_id 표를 JSON과 한국어 Markdown으로 만듭니다. 명령은 짧은 이름만 기록하므로 사용자 컴퓨터의 절대 경로, 환경변수 값, secret, token은 들어가지 않습니다. 실패한 fixture는 `fail`로 남고 workflow도 실패합니다.

## 로컬 Windows 확인

| 검사 | 결과 |
|---|---|
| `python -m unittest discover -s tests -v` | PASS (118개) |
| `python -m compileall -q src tests scripts graphori` | PASS |
| `python scripts/dashboard_smoke.py` | PASS |
| `python graphori/scripts/validate_skill.py graphori` | PASS |
| Windows evidence manifest | PASS, 5개 fixture |

독립 검증 전 진행률은 계약에 따라 **7/9**로 유지합니다. 이 보고서는 구현자가 만든 기록이며, GitHub Actions와 독립 검증이 끝나기 전에는 I08 승인이나 전체 완료라고 말하지 않습니다.
