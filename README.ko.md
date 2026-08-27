# Graphori

[![skills.sh에서 설치](https://skills.sh/b/dotoricode/graphori)](https://skills.sh/dotoricode/graphori)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

코딩 작업을 단계로 나누고, 다른 에이전트를 쓰는 게 이득일 때만 넘기고, 직접 돌린
검사로 완료를 판단하는 Agent Skill입니다. 에이전트가 "다 했다"고 말하는 걸 근거로
삼지 않습니다.

![Graphori의 도토리 운영 엔지니어 도리](assets/brand/hero.png)

[English](README.md) · [신뢰 모델](docs/public/TRUST.ko.md) · [한계](docs/public/LIMITATIONS.ko.md) · [보안](SECURITY.md)

## 왜 만들었나

필요한지 따져보기 전에 에이전트부터 여럿 띄우면 작은 작업에서 토큰만 나간다.
실패도 그럴듯한 요약문 뒤에 묻힌다.

Graphori는 한 세션에서 시작해서, 쪼개는 비용보다 이득이 큰 지점에서만 나눈다.
단계마다 그 단계를 판정한 명령이 남는다. 그래서 완료는 검사가 통과했다는 뜻이다.

## 설치

쓰는 도구에 맞춰 고른다. 둘 다 도구 안에서 실행하는 명령이다.

### Claude Code

```text
/plugin marketplace add dotoricode/graphori
/plugin install graphori@graphori
```

Claude Code를 재시작한 뒤:

```text
/graphori:graphori plan, implement, and verify this task end to end. 한국어로 답해줘.
```

### Codex

```sh
codex plugin marketplace add dotoricode/graphori
codex plugin add graphori@graphori
```

새 세션을 열고:

```text
$graphori:graphori plan, implement, and verify this task end to end. 한국어로 답해줘.
```

Skill이 설치되는 곳은 Claude Code가 `~/.claude/skills`, Codex가 `~/.agents/skills`다.
`npx skills`, `gh`와 셸 스크립트, 프로젝트 단위 설치 같은 다른 경로는
[INSTALL.md](docs/public/INSTALL.md)에 정리해 뒀다.

## 선택 사항인 런타임

Skill만으로 동작한다. `graphori` CLI, append-only journal, replay, resume이
필요할 때만 Python 런타임을 얹으면 된다.

```sh
gh repo clone dotoricode/graphori -- --depth 1
cd graphori
./scripts/install_graphori.sh --mode runtime --dry-run   # 출력만 하고 아무것도 안 바꿈
./scripts/install_graphori.sh --mode runtime
graphori doctor
```

변경을 계획하고 실행하려면 이렇게 한다. 경로에 공백이 있어도 인자가 쪼개지지
않도록 루트는 변수에 담아 따옴표로 감싼다.

```sh
repo_root="$(pwd -P)"
graphori run "파서에 docstring 추가" \
  --root "$repo_root" \
  --write-scope src/parser.py \
  --verify-command python -m unittest tests.test_parser
```

Windows PowerShell에서는:

```powershell
$root = (Get-Location).Path
graphori plan "파서에 docstring 추가" --root $root
```

`--write-scope`가 건드릴 수 있는 범위를 묶는다. 판정 근거는 `--verify-command`다.
안 주면 작업 공간을 보고 기본값을 고른다. 단위 테스트, 없으면 `compileall`,
그것도 아니면 `git diff --check` 순이다. 직접 고른 검사보다는 약하다.

## 측정한 것

두 번째 AI 리뷰어를 두면 작은 작업이 더 안전해질 거라고 봤다. 통제된 비교에서는
첫 패스가 놓친 걸 하나도 못 찾았고, 비용은 두 배였다. v2에서 뺐다.

| 항목 | v1 방식 | v2 | 변화 |
| --- | ---: | ---: | ---: |
| 숨긴 검사 통과 | 4/4 | 4/4 | 같음 |
| 범위 위반 | 0 | 0 | 같음 |
| 두 번째 AI가 찾은 문제 | 0 | 해당 없음 | — |
| AI 호출 수 | 8 | 4 | −50% |
| 완료 시간 중앙값 | 48.5초 | 32.1초 | −34% |
| 신규 입력 토큰 | 170,784 | 65,905 | −61% |

각 조건 4회, Python 작업 2종, Codex만 사용했다. v1 쪽은 커밋 `93c5fcf`에서
설계를 복원한 것이지 과거 실행을 재생한 게 아니다. 표본이 작으니 당신의
코드베이스에서도 이렇게 나온다는 뜻으로 읽으면 곤란하다.

보관된 산출물로 직접 다시 계산할 수 있다.

```sh
python benchmarks/v1_v2/verify_results.py
```

[방법](benchmarks/v1_v2/PROTOCOL.md) · [보고서](benchmarks/v1_v2/REPORT.md) · [원자료](benchmarks/v1_v2/raw-results.json)

기본값을 정한 라우팅 실험이 셋 더 있다. 전부 기능을 켜지 않기로 한 음성 결과다.

| 실험 | 표본 | 결과 |
| --- | ---: | --- |
| [Direct Codex + Claude 기준선](docs/archive/research/RRC-04_DIRECT_ROUTE_BASELINE.md) | 24 | 24/24 통과 — 두 경로 다 유지 |
| [Ponytail 자동 선택](docs/archive/research/RRC-05A_PONYTAIL_EFFECTIVENESS.md) | 22 | 어느 조합에서도 이득 없음 — 미적용 |
| [TDD 자동 선택](docs/archive/research/RRC-05B_TDD_EFFECTIVENESS.md) | 24 | Codex에서 오히려 해로움 — 수동으로 남김 |

Direct·v1·v2를 함께 비교하는 더 넓은 프로토콜은 [`benchmarks/`](benchmarks/)에
공개해 뒀지만, 계획했던 72회 실험은 아직 돌리지 않았다. 그 결과로 주장하는 건 없다.

## 이건 아니다

Graphori는 샌드박스가 아니다. 사용자가 승인한 provider는 파일을 고치고 명령을
실행할 수 있다. 위험한 작업이라면 write scope를 좁게 잡고, 버전 관리를 쓰고,
사람이 검토해야 한다.

설치 전에 알아 둘 한계가 몇 가지 더 있다.

- 검사는 그 명령이 확인하는 범위까지만 증명한다.
- 긴 실행 중에 provider 진행 상황이 안 보일 수 있다. heartbeat는 살아 있다는
  뜻이지 진행 중이라는 뜻이 아니다.
- Skill 자동 선택은 일부러 꺼 뒀다. 위 측정이 그 이유다.
- `0.1.0`은 이 공개 소스 라인을 여는 버전이다. `v0.9.0-beta.1` 같은 이전 태그는
  공개 소스 이전 것이라 여기에 해당하지 않는다. 안정 API는 아직 없다.
- Orca 연동은 선택 adapter로 있고 지금은 꺼져 있다.

## 지원 플랫폼

| | Skill | CLI `plan`, `doctor` | CLI `run`, `resume` |
| --- | --- | --- | --- |
| Windows | 지원 | 지원 | 지원, 실행 확인 |
| Linux | 지원 | 지원 | 지원, 실행 확인 |
| macOS | 지원 | 지원 | 구현됨, 실행 미확인 |

journal은 배타 advisory lock을 잡아서 writer 둘이 섞이지 못하게 한다. POSIX에서는
`flock`, Windows에서는 `msvcrt.locking`을 쓴다. 둘 다 없는 환경이라면 보호 없이
돌리는 대신 fail-closed로 멈춘다.

macOS는 Linux와 같은 POSIX 경로를 탄다. 다만
[portability contract](docs/architecture/PORTABILITY_CONTRACT.md)가 macOS 호스트에서
fixture를 돌리기 전까지 `deferred/unknown`으로 묶어 두고 있다. 표에 "지원"이 아니라
"구현됨"이라고 적은 이유다.

테스트는 397개다. Windows + Python 3.12에서 마지막으로 돌렸을 때 전부 통과했고
5개를 건너뛰었다. 건너뛰는 개수는 환경마다 다르다. macOS 전용 도구가 없거나,
symlink 생성 권한이 없거나, live provider 테스트를 켜지 않은 경우 빠진다.

## 릴리즈 검사

이 저장소는 GitHub Actions를 쓰지 않는다. 공개 전에 메인테이너가 로컬에서
fail-closed 게이트를 돌린다.

```sh
python3.11 scripts/verify_public_release.py --output build/release-artifacts
```

테스트, 시크릿·의존성 감사, 패키지 빌드, 격리 설치, SBOM 생성, 해시까지 한 번에
한다. 배포하거나 히스토리를 다시 쓰는 일은 하지 않는다. 절차와 각 단계가 남겨야
하는 증거는 [RELEASE_GATE.ko.md](docs/public/RELEASE_GATE.ko.md)에 정리돼 있다.
산출물 자체는 `build/release-artifacts`에 쓰이고 커밋하지 않는다.

## 문서

- [제품 안내](docs/public/README.ko.md) — 여기서 시작
- [아키텍처](docs/architecture/GRAPHORI_ARCHITECTURE.md), [이벤트 프로토콜](docs/architecture/EVENT_PROTOCOL.md)
- [결정 기록](docs/decisions/README.md) — 지금 기본값이 왜 이런지
- [v1에서 v2까지](docs/public/HISTORY.ko.md)
- [기여 안내](CONTRIBUTING.md) · [행동 강령](CODE_OF_CONDUCT.md) · [변경 이력](CHANGELOG.md)
- [docs/archive/](docs/archive/README.md) — 근거 보존용 빌드·리뷰 기록

## 라이선스

MIT. [LICENSE](LICENSE) 참고.
