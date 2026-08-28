# Graphori PR #2 작업 기록

마지막 갱신: 2026-08-10 (Asia/Seoul)

## 처음 계획

1. `origin/main`에서 새 브랜치를 만들고 사용자 변경을 보호한다.
2. canonical Graphori skill과 Codex/Claude 설치기를 만든다.
3. 문서 폴더마다 한국어 README 색인을 만들고 개인 절대 경로를 없앤다.
4. journal 근거를 쓰는 snapshot publisher와 active/idle/completed 상태를 dashboard에 연결한다.
5. 임시 HOME 설치, skill validator, 문서 색인, 기존 회귀, compileall, dashboard smoke를 실행한다.
6. CI에서 Windows와 macOS 설치·색인 검사를 실행하고 PR #2를 검토 가능하게 만든다.

## 바뀐 계획

기존 dashboard의 검증 기반 진행률을 유지하면서 `updatedAt`, 마지막 heartbeat, 마지막 이벤트를 snapshot에 추가한다. 화면은 기존 어두운 terminal/pixel HUD를 유지하고, viewer와 dashboard 모두 명시적인 foreground/background 색을 사용한다. Orca 탭을 닫거나 Orca를 필수 의존성으로 만들지 않는다.

## 현재 상태

- 구현 브랜치: `feat/installable-skills-and-doc-indexes`
- 기준: `origin/main` merge commit `7ec8d21` (PR #1 반영)
- 완료: canonical skill, Windows/POSIX installer, 문서 색인 validator, snapshot publisher, dashboard 상태 필드
- 완료: 임시 HOME와 실제 사용자 설치 검증, 전체 회귀와 hosted CI 확인
- 완료: PR #2를 Ready for review로 전환
- 남은 일: maintainer review와 merge 결정

## 검사를 기록하는 방법

검사 결과는 성공한 명령과 실제 숫자만 적는다. macOS 로컬 실행처럼 직접 하지 못한 검사는 `deferred`로 남기며 CI 성공과 섞지 않는다.

```text
python scripts/validate_docs_indexes.py
python skills/graphori/scripts/validate_skill.py skills/graphori
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts graphori
python scripts/dashboard_smoke.py
git diff --check
```

최종 검증 뒤에는 대시보드에 새 run을 열 수 있도록 정확한 명령과 run id를 `I10_INSTALLABLE_SKILL_BUILD.md`에 적는다. 기존 Orca 탭과 서버는 작업 중 닫지 않는다.

## PR #2 완료 결과

- 최신 구현 SHA: `f3513f76c254500a300464748d72f7a0804f6c54`
- PR: `https://github.com/dotoricode/graphori/pull/2`
- hosted run `31327819856`: Windows 3.11, Windows 3.12, macOS 모두 success
- hosted run `31327821989`: Windows 3.11, Windows 3.12, macOS 모두 success
- 상태: Ready for review

## I10 두 가지 수정 결과

독립 검증에서 다시 고치라고 한 것은 두 가지뿐이었습니다. 첫째, README와 최신 quickstart에서 `--root .`를 없애고, Windows는 `$root = (Get-Location).Path`, POSIX는 `repo_root="$(pwd -P)"`를 먼저 저장하도록 바꿨습니다. 둘째, 저장소 바깥의 `build\ci-artifacts\README.md`를 정확히 확인한 뒤 PowerShell로 그 파일 하나를 지웠습니다.

이 문서 약속을 지키는지 `tests/test_quickstart_docs.py`가 자동으로 검사합니다. 설치기, skill, 문서 색인, 전체 테스트, compileall, dashboard smoke, diff 검사를 모두 다시 실행하고, Windows 3.11·3.12와 macOS hosted CI가 최신 SHA에서 성공한 뒤 최종 SHA를 아래에 적습니다.

- I10 수정 보고서: `docs/archive/verification/I10_FIX_REPORT.md`
- 최신 SHA: `226ecef1f24380107a3fa61faacbce26306354da`
- PR: `https://github.com/dotoricode/graphori/pull/2`
- CI: `https://github.com/dotoricode/graphori/actions/runs/31329340506`, `https://github.com/dotoricode/graphori/actions/runs/31329338640` (Windows 3.11·3.12, macOS 모두 success)
