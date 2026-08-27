# Graphori

[![skills.sh에서 Graphori 설치](https://skills.sh/b/dotoricode/graphori)](https://skills.sh/dotoricode/graphori)

![Graphori의 도토리 운영자 Dori](assets/brand/hero.png)

## 코딩 작업을 말해 주세요. Graphori가 순서를 정하고, 도움이 되는 에이전트만 맡긴 뒤, 결과를 검사합니다.

Graphori는 처음부터 에이전트 무리를 만들지 않습니다. 작은 일은 한 대화에서
처리하고, 큰 일만 의미 있는 경계로 나눕니다. 완료 여부는 에이전트의 “끝났다”는
말이 아니라 기록된 검사 결과로 판단합니다.

[English](README.md) · [신뢰 모델](docs/public/TRUST.ko.md) · [제한 사항](docs/public/LIMITATIONS.ko.md) · [보안](SECURITY.md)

## 숫자로 확인한 v1 방식과 v2 결과

처음에는 두 번째 AI가 다시 검토하면 작은 코딩 작업도 더 안전해질 것으로
예상했습니다. 이 통제된 비교에서는 새 문제를 찾지 못했습니다. v2 후보는 같은
숨은 검사 결과를 유지하면서 AI 호출을 절반만 사용했습니다.

| 지표 | v1 방식 재현판 | Graphori v2 후보 | 변화 |
| --- | ---: | ---: | ---: |
| 숨은 검사 통과 | 4/4 | 4/4 | 같음 |
| 완료 보고와 실제 결과 일치 | 4/4 | 4/4 | 같음 |
| 허용 범위 밖 파일 변경 | 0 | 0 | 같음 |
| AI 호출 | 8 | 4 | **-50.0%** |
| 가운데 완료 시간 | 48.542초 | 32.110초 | **-33.9%** |
| 전체 입력 토큰 | 567,584 | 333,681 | **-41.2%** |
| 캐시 입력 토큰 | 396,800 | 267,776 | **-32.5%** |
| 새 입력 토큰 | 170,784 | 65,905 | **-61.4%** |
| 출력 토큰 | 4,960 | 3,309 | **-33.3%** |
| 두 번째 AI가 새로 찾은 문제 | 0 | 해당 없음 | — |
| 제공사 비용 | 기록하지 않음 | 기록하지 않음 | 알 수 없음 |

작은 통제 비교입니다. 조건별 `n=4`, Python 과제 2개를 조건마다 두 번 실행했고
Codex만 사용했습니다. v1 방식은 commit `93c5fcf`의 설계를 재현했으며 과거 실행을
재생한 것이 아닙니다. 새 입력은 전체 입력에서 캐시 입력을 뺀 값입니다. 이 수치가
모든 코딩 작업의 성능을 예측하지는 않습니다.

[측정 방법](benchmarks/v1_v2/PROTOCOL.md) · [전체 보고서](benchmarks/v1_v2/REPORT.md) · [원자료](benchmarks/v1_v2/raw-results.json) · [교정 결과](benchmarks/v1_v2/results.json) · [검증기](benchmarks/v1_v2/verify_results.py)

보존한 결과는 다음 명령으로 다시 계산할 수 있습니다.

```sh
python benchmarks/v1_v2/verify_results.py
```

Direct·v1 방식·v2의 세 조건을 비교하는 더 큰 계획은 [`benchmarks/`](benchmarks/)에
공개했지만, 계획한 72회 실험은 **아직 실행하지 않았습니다.** 결과가 있는 것처럼
주장하지 않습니다.

## 다른 정량 실험으로 내린 결정

아래 실험은 위 성능표에 합산하지 않은 별도의 작업 배정 실험입니다.

| 실험 | 표본 | 결과 | 제품 결정 |
| --- | ---: | --- | --- |
| Codex·Claude 직접 실행 기준선 | 24 | 정해진 검사 24/24 통과, 범위 위반·재작업·자기보고 불일치 0 | 두 직접 실행 경로 유지 |
| Ponytail 자동 선택 | 22 | 제공사·과제 조합 4/4가 `NO_BENEFIT` | 자동 선택하지 않음 |
| TDD 자동 선택 | 24 | Codex `HARMFUL`, Claude `MANUAL_ONLY` | 자동 선택하지 않음 |

[직접 실행 기준선](docs/research/RRC-04_DIRECT_ROUTE_BASELINE.md) · [Ponytail 결과](docs/research/RRC-05A_PONYTAIL_EFFECTIVENESS.md) · [TDD 결과](docs/research/RRC-05B_TDD_EFFECTIVENESS.md)

## Agent Skill 설치

### Codex

```sh
codex plugin marketplace add dotoricode/graphori
codex plugin add graphori@graphori
codex plugin list
```

새 Codex 세션을 시작합니다. 목록에 `graphori@graphori`가 활성 상태로 보여야 합니다.

```text
$graphori:graphori 이 작업을 처음부터 끝까지 계획하고 구현한 뒤 검증해줘.
```

Codex 사용자 Skill의 공식 경로는 `~/.agents/skills`입니다. 폐기된
`~/.codex/skills` 경로에는 설치하지 않습니다.

### Claude Code

Claude Code 안에서 실행합니다.

```text
/plugin marketplace add dotoricode/graphori
/plugin install graphori@graphori
/plugin list
```

설치하거나 업데이트한 뒤 Claude Code를 다시 시작합니다. 플러그인 상세 화면에는
`graphori`와 `graphori-dashboard` Skill 두 개가 보여야 합니다.

```text
/graphori:graphori 이 작업을 처음부터 끝까지 계획하고 구현한 뒤 검증해줘.
```

Claude Code 사용자 Skill의 경로는 `~/.claude/skills`입니다.

## 플러그인 마켓을 쓰지 않고 미리 보기·설치

공개 [`skills`](https://github.com/vercel-labs/skills) CLI로 먼저 저장소에서 발견되는
Skill을 확인합니다.

```sh
npx skills add dotoricode/graphori --list
```

현재 프로젝트의 Codex에 설치:

```sh
npx skills add dotoricode/graphori --skill graphori --agent codex --copy
```

현재 프로젝트의 Claude Code에 설치:

```sh
npx skills add dotoricode/graphori --skill graphori --agent claude-code --copy
```

이 명령은 일부러 `--global`을 쓰지 않습니다. 현재 이 도구의 Codex 전역 경로가
Codex 공식 사용자 Skill 경로와 다르기 때문입니다. Node.js 22.20 이상이 필요합니다.

npm 도구 대신 `gh`와 내용을 읽을 수 있는 로컬 스크립트를 쓰려면 복사 전에 먼저
확인합니다.

```sh
gh repo clone dotoricode/graphori -- --depth 1
cd graphori
./scripts/install_graphori.sh --mode solo --target codex --dry-run
./scripts/install_graphori.sh --mode solo --target codex
```

Claude Code는 `--target codex`를 `--target claude`로 바꿉니다. 내용이 다른 Skill은
`--force` 없이 덮어쓰지 않으며, 강제 교체할 때도 날짜가 붙은 백업을 먼저 만듭니다.
Windows PowerShell에서는 `scripts/install_graphori.ps1`의 `-Mode solo`와
`-Target codex` 또는 `claude`를 사용합니다.

개인 Skill의 정확한 설치 위치는 Codex의 `~/.agents/skills/graphori`와 Claude
Code의 `~/.claude/skills/graphori`입니다.

## 선택형 Runtime

Agent Skill은 Python Runtime 없이도 작동합니다. `graphori` CLI, 정해진 명령으로
하는 검사, 로컬 업무일지 재생, 중단 뒤 재개가 필요할 때만 저장소를 받은 뒤
Runtime을 추가합니다.

```sh
gh repo clone dotoricode/graphori -- --depth 1
cd graphori
./scripts/install_graphori.sh --mode runtime --dry-run
./scripts/install_graphori.sh --mode runtime
graphori doctor --lang ko
```

설치기는 받은 소스를 현재 Python 환경에 로컬 설치합니다. 현재 환경을 바꾸고 싶지
않다면 가상 환경을 사용하세요.

```sh
repo_root="$(pwd -P)"
graphori run "작은 변경을 구현해줘" --root "$repo_root" \
  --write-scope src/example.py \
  --verify-command python -m unittest tests.test_example
```

Windows PowerShell:

```powershell
$root = (Get-Location).Path
graphori plan "작은 변경을 구현해줘" --root $root --lang ko
```

기본값은 `--lang auto`입니다. 직접 지정한 언어, 요청문 언어, 저장된 설정, 실행
환경 언어, 영어 순으로 판단합니다. 언어 정보는 화면 표시에만 쓰며 작업 계획,
업무일지, 현재 상태 요약값에는 넣지 않습니다.

## 한눈에 보는 신뢰 경계

| Agent Skill | 선택형 Runtime |
| --- | --- |
| 읽을 수 있는 Markdown과 metadata | 소스가 공개된 Python package |
| Skill 폴더 안 실행 파일 없음 | 숨겨진 daemon과 Graphori 자체 telemetry 없음 |
| 설치 전에 전체 내용 확인 가능 | 덧붙이기 전용 로컬 업무일지와 읽기 전용 재생 |
| Codex·Claude 설치 경로 분리 | 로컬 공개 검증이 package 생성·감사·설치·hash 확인 |

Graphori는 sandbox가 아닙니다. 사용자가 허용한 provider나 검사 명령은 파일을
바꾸거나 명령을 실행할 수 있습니다. 좁은 쓰기 범위, version control, 명시적 검사,
위험 작업의 사람 검토를 함께 사용하세요. [신뢰 모델](docs/public/TRUST.ko.md)에
정확한 경계를 적었습니다.

## 현재 검증 범위와 제한

- Python 3.11 이상을 지원하며 공개 push 전에 로컬 전체 검사를 실행합니다.
- Codex와 Claude Code의 native marketplace 설치를 따로 시험합니다.
- Codex·Claude Code 직접 실행을 지원하며 Orca 실행은 꺼져 있습니다.
- 긴 작업 중에는 제공사가 진행 상태를 보내지 않을 수 있습니다.
- 선택형 Skill 자동 선택은 의도적으로 꺼져 있습니다.
- 검사는 실행한 명령과 assertion이 다루는 범위만 증명합니다.
- Graphori v2는 architecture 세대 이름이고, `0.1.0`은 첫 공개 source 버전입니다.
  안정된 API를 약속하지 않습니다.

이 저장소는 GitHub Actions를 사용하지 않습니다. 관리자는 로컬에서 실패 시 닫히는
공개 검증을 실행합니다.

```sh
python3.11 scripts/verify_public_release.py --output build/release-artifacts
```

이 명령은 테스트, 비밀·dependency 감사, package 생성, 격리 설치, SBOM 생성,
hash 계산을 수행합니다. 배포·공개 전환·Git 이력 변경은 하지 않습니다.
[공개 검증 조건](docs/public/RELEASE_GATE.ko.md)에서 전체 범위를 확인할 수 있습니다.

## 문서

- [공개 제품 안내](docs/public/README.ko.md)
- [v1에서 v2까지의 이력](docs/public/HISTORY.ko.md)
- [Architecture](docs/architecture/GRAPHORI_ARCHITECTURE.md)
- [기여 안내](CONTRIBUTING.md)
- [행동 강령](CODE_OF_CONDUCT.md)
- [변경 기록](CHANGELOG.md)
- [제3자 자료 고지](THIRD_PARTY_NOTICES.md)
- 관리자 문맥: [CONTEXT.md](CONTEXT.md), [PRODUCT.md](PRODUCT.md),
  [DESIGN.md](DESIGN.md), [TEAM_TOPOLOGY.md](TEAM_TOPOLOGY.md),
  [design-qa.md](design-qa.md)
