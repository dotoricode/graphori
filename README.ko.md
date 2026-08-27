# Graphori

![Graphori의 도토리 운영자 Dori](assets/brand/hero.png)

## 에이전트는 꼭 필요한 만큼만. 결과는 빠짐없이 검증합니다.

Graphori는 코딩 작업을 그래프로 계획하고, 필요한 에이전트만 실행한 뒤 기록된 근거로 결과를 검증합니다. 로컬 우선 업무일지는 무엇을 계획·실행·검증했는지 에이전트의 기억에 기대지 않고 다시 읽습니다. 에이전트가 항상 맞는다는 보장이나 호스팅 서비스는 아닙니다.

[English README](README.md) · [신뢰 모델](docs/public/TRUST.ko.md) · [이력과 근거](docs/public/HISTORY.ko.md) · [제한 사항](docs/public/LIMITATIONS.ko.md) · [보안](SECURITY.md)

## 공개 베타의 경계

이 베타는 Python 3.11+, 로컬 Codex/Claude Code CLI adapter, 결정론적 generic verifier, append-only run journal, 읽기 전용 replay를 지원합니다. provider·자격 증명·네트워크 접근·최종 human decision은 Graphori 권한 밖입니다. 중요한 저장소에서 사용하기 전에 [공개 제품 안내](docs/public/README.ko.md)를 읽으세요.

## 설치

먼저 실제로 수행할 일을 확인합니다.

```sh
./scripts/install_graphori.sh --mode runtime --dry-run
./scripts/install_graphori.sh --mode solo --dry-run
```

현재 Python 환경에 runtime을 설치하거나 Solo 세션용 Graphori Skill을 설치합니다.

```sh
./scripts/install_graphori.sh --mode runtime
./scripts/install_graphori.sh --mode solo --target codex
```

설치기는 코드를 업로드하거나 provider를 시작하지 않으며, 다른 Skill을 `--force` 없이 바꾸지 않습니다. runtime 명령은 현재 checkout을 로컬 `pip install` 합니다. 현재 interpreter를 바꾸고 싶지 않다면 virtual environment를 사용하세요.

## 첫 계획

```sh
repo_root="$(pwd -P)"
graphori plan "작은 변경을 구현해줘" --root "$repo_root" --lang ko
```

기본값인 `--lang auto`는 요청 언어를 먼저 보고, 판단하기 어려우면 설정값과 운영체제 언어를 차례로 봅니다. 언어는 표시 단계에만 쓰이며 작업 계획, 업무일지, 요약값에는 들어가지 않습니다. 실제 작업에는 명시적 검증 명령을 추가하세요.

프로젝트 설정은 `.graphori/config.json`, 사용자 설정은 `$XDG_CONFIG_HOME/graphori/config.json`(보통 `~/.config/graphori/config.json`)에 `{"language":"ko"}`로 둡니다. 명시한 `--lang`이 항상 우선합니다.

```sh
graphori run "작은 변경을 구현해줘" --root "$repo_root" \
  --write-scope src/example.py \
  --verify-command python -m unittest tests.test_example
```

Windows PowerShell:

```powershell
$root = (Get-Location).Path
graphori plan "작은 변경을 구현해줘" --root $root --lang ko
```

`graphori doctor`, `status`, `replay`는 로컬 상태를 확인합니다. 중단된 run은 기록된 plan과 command로만 재개하며, 이미 실행됐는지 불명확한 작업은 fail-closed로 중단합니다.

## 증거와 한계

저장소에는 v1/v2 설계·검증 기록이 있습니다. 이는 독립 성능 주장이나 benchmark가 아니라 과거의 로컬 산출물입니다. [`benchmarks/`](benchmarks/)의 세 가지 비교군 harness는 재현 가능한 실행 결과가 기록되기 전까지 결과를 제공하지 않습니다.

## 기여와 공개 안전

이 저장소는 GitHub Actions를 사용하지 않습니다. 관리자는 깨끗한 후보 저장소에서 다음 로컬 명령으로 전체 공개 조건을 검사합니다.

```sh
python3.11 scripts/verify_public_release.py --output build/release-artifacts
```

이 명령은 테스트, Git 이력·비밀 검사, package 생성, 격리 설치, SBOM과 해시 생성을 수행하지만 배포·공개 전환·이력 변경은 하지 않습니다. 정확한 범위는 [공개 전환 조건](docs/public/RELEASE_GATE.ko.md)과 [제한 사항](docs/public/LIMITATIONS.ko.md)에 적었습니다.
