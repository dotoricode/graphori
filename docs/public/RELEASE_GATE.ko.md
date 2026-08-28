# 공개 전환 조건

Graphori는 **로컬 검증 + `gh` 공개** 절차를 사용합니다. GitHub Actions는 비활성화하며 공개 조건에 포함하지 않습니다.

## 필수 로컬 명령

깨끗한 이력의 후보 clone 또는 연결된 worktree에서 다음을 실행합니다.

```bash
python3.11 scripts/verify_public_release.py --output <새로운-산출물-폴더>
```

전체 unit test, compile 검사, 문서 index, Skill validator, dashboard smoke, 현재 파일과 Git 전체 이력 개인정보 감사, Gitleaks tree·history 검사, wheel/sdist 생성, Twine metadata, 격리된 Runtime·Solo 설치, `pip-audit`, CycloneDX SBOM, SHA-256 생성이 모두 성공해야 합니다.

이 검사기는 package를 배포하거나 GitHub 저장소를 만들거나 visibility를 바꾸거나 산출물을 업로드하지 않습니다.

## 공개 근거의 경계

- 기록된 로컬 명령은 macOS의 Python 3.11과 3.14에서 실행했습니다. [VERIFICATION.ko.md](VERIFICATION.ko.md)를 참고하세요. 이 결과만으로 전용 이식성 검사를 통과한 것은 아닙니다.
- Windows 설치와 Windows Job Object 동작은 실험적이며 검증 완료라고 주장하지 않습니다.
- Actions를 사용하지 않으므로 CodeQL, OpenSSF Scorecard, OIDC provenance는 근거로 주장하지 않습니다.
- Gitleaks, `pip-audit`, SBOM, 산출물 해시, 깨끗한 이력 검사와 로컬 테스트 결과가 릴리스 근거입니다.

사용자에게 보이는 정확한 경계는 [LIMITATIONS.ko.md](LIMITATIONS.ko.md)에 적습니다.

## 깨끗한 이력으로 공개하는 순서

기존 개발 저장소는 그대로 공개하지 않았습니다. 내보낸 공개 저장소는 현재 public이지만, 현재 이력 감사에는 noreply가 아닌 작성자 식별값 1개가 남아 있습니다. 명시적으로 승인된 이력 처리 결정 전에는 전체 릴리스 검사를 통과했다고 주장하지 않습니다.

1. `scripts/export_public_tree.py`로 검토한 트리만 내보냅니다.
2. noreply 작성자로 새로운 `main` 이력을 만듭니다.
3. 새 저장소에서 `scripts/verify_public_release.py`를 실행합니다.
4. `gh`로 개발 저장소는 private 보관소로 남기고, 깨끗한 저장소만 `dotoricode/graphori`로 옮긴 뒤 Actions를 비활성화하고 public으로 변경합니다.
5. GitHub가 지원하는 범위에서 vulnerability alert, automated security fix, secret scanning, push protection, private vulnerability reporting을 `gh api`로 활성화합니다.

개발 저장소의 branch, tag, pull request, Actions artifact, 과거 release는 공개 저장소로 옮기지 않습니다.
