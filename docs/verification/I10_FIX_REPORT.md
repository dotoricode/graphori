# I10 수정 보고서

이 문서는 I10 독립 검증에서 **REVISE**로 남은 두 가지 문제만 고친 기록입니다. 기존 `I10_INSTALLABLE_SKILL_REVIEW.md`의 결론과 다른 검토 항목은 바꾸지 않았습니다.

## 무엇을 고쳤나요?

1. README와 최신 quickstart의 명령을 고쳤습니다.
   - Windows PowerShell은 `$root = (Get-Location).Path`로 현재 폴더의 절대 경로를 저장합니다.
   - macOS/Linux는 `repo_root="$(pwd -P)"`로 물리적 절대 경로를 저장합니다.
   - 두 운영체제 모두 `--root`에 저장한 변수를 따옴표 규칙에 맞게 사용합니다.
   - 그래서 다른 폴더에서 복사해 실행해도 `--root .` 때문에 실패하지 않습니다.
2. 이 약속이 다시 깨지지 않도록 `tests/test_quickstart_docs.py`를 추가했습니다. 테스트는 변수 선언, 절대 경로 사용, POSIX 따옴표, `--root .` 금지를 확인합니다.
3. 검증자가 찾은 저장소 밖 파일 `build\ci-artifacts\README.md`를 다시 확인했습니다. 실제 사용자 폴더 이름은 이 저장소 문서에 남기지 않았습니다.
   - `Resolve-Path -LiteralPath`로 정확한 파일을 찾았습니다.
   - build 트리의 유일한 파일인지 확인했습니다(1개).
   - 기준 blob과 크기 414바이트, Git blob hash `cfd0ae00e7080f0dc5043bbf8621de647f74dcd3`가 같음을 확인했습니다.
   - PowerShell에서 그 파일 하나만 삭제했고, 비어 있던 `ci-artifacts` 부모 폴더만 함께 지웠습니다. 다른 파일은 지우지 않았습니다.
4. 예전 검증 문서에 남아 있던 실제 사용자 경로도 placeholder로 바꾸고, `tests/test_personal_paths.py`를 추가했습니다. 이 테스트는 현재 사용자의 이름이나 Windows/macOS 개인 경로가 문서에 다시 들어오면 실패합니다.

## 설치 폴더 확인

실제 Codex와 Claude 설치 폴더에 빈 `assets` 잔여가 있는지 확인했습니다. 빈 잔여가 있으면 공식 PowerShell installer의 `-Force -Target both`로 다시 설치하고, 백업과 다른 skill 보존을 확인합니다. 이번 작업은 설치기 코드를 바꾸지 않으며, 설치 검사는 `scripts/test_installers.py --kind powershell`로 재실행합니다.

## 확인할 명령

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts graphori
python graphori/scripts/validate_skill.py graphori
python scripts/validate_docs_indexes.py
python scripts/test_installers.py --kind powershell
python scripts/dashboard_smoke.py
git diff --check
python -m unittest tests.test_personal_paths -v
```

## 최종 CI 증거

최신 수정 커밋 `226ecef1f24380107a3fa61faacbce26306354da`에서 다음 hosted CI가 모두 `success`였습니다.

- [Actions run 31329340506](https://github.com/dotoricode/graphori/actions/runs/31329340506): Windows 3.11, Windows 3.12, macOS
- [Actions run 31329338640](https://github.com/dotoricode/graphori/actions/runs/31329338640): Windows 3.11, Windows 3.12, macOS
- [PR #2](https://github.com/dotoricode/graphori/pull/2)
