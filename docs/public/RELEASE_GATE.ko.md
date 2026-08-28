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

- 기록된 로컬 명령과 generic adapter 전용 검사는 macOS 26.5.2 x86_64에서 Python 3.11·3.14로 실행했습니다. [VERIFICATION.ko.md](VERIFICATION.ko.md)를 참고하세요. 이는 해당 호스트 범위의 판정이지 모든 Mac을 보장하는 주장은 아닙니다.
- Windows 설치와 Windows Job Object 동작은 실험적이며 검증 완료라고 주장하지 않습니다.
- Actions를 사용하지 않으므로 CodeQL, OpenSSF Scorecard, OIDC provenance는 근거로 주장하지 않습니다.
- Gitleaks, `pip-audit`, SBOM, 산출물 해시, 깨끗한 이력 검사와 로컬 테스트 결과가 릴리스 근거입니다.

사용자에게 보이는 정확한 경계는 [LIMITATIONS.ko.md](LIMITATIONS.ko.md)에 적습니다.

## 깨끗한 이력으로 공개하는 순서

2026-08-28에 검토한 공개 tree를 부모가 없고 noreply 작성자인 commit `83fe5a5`로
교체했습니다. 강제 갱신 전에 그 commit만 있는 격리 저장소에서 전체 로컬 릴리스
검사를 통과했습니다. 과거 prerelease tag와 일반 원격 작업 branch 3개를 제거했습니다.
새 public clone은 noreply commit 1개만 가지며 tree/history 개인정보 감사를 통과합니다.

이는 일반 Git ref를 재작성한 결과입니다. 이미 다른 사람이 내려받은 복사본을 회수하거나
hosting cache와 병합된 PR metadata에서 과거 object identifier가 완전히 사라졌다고
보장할 수는 없습니다. Tree와 이력 Gitleaks 검사에서는 secret을 찾지 못했습니다.
