# Graphori

[![skills.sh에서 설치](https://skills.sh/b/dotoricode/graphori)](https://skills.sh/dotoricode/graphori)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

코딩 작업을 의존성 그래프로 바꾸고, 어디를 동시에 돌릴지 스스로 판단하고,
단계마다 모델을 골라 붙이는 Agent Skill입니다.

![Graphori의 도토리 운영 엔지니어 도리](assets/brand/hero.png)

[English](README.md) · [설치](docs/public/INSTALL.md) · [신뢰 모델](docs/public/TRUST.ko.md) · [한계](docs/public/LIMITATIONS.ko.md)

## 무엇이 문제였나

동시에 해도 되는 일이 대개 순서대로 처리된다. 어느 단계가 서로 독립인지 적어 둔
계획이 없기 때문이다.

물론 직접 시키면 된다. "이 셋을 병렬로 조사하고 나서 구현해"라고 쓰면 웬만한
에이전트는 해낸다. 그런데 그 순간부터 계획을 짜는 사람은 당신이다. 뭘 쪼갤지,
뭘 기다리게 할지, 누구에게 맡길지 정해야 하고, 작업이 바뀔 때마다 그 고민을
처음부터 다시 한다.

Graphori는 그 판단을 에이전트 쪽으로 옮긴다. 당신은 결과를 설명하고, 그래프는
Graphori가 만든다. 무엇을 같이 돌릴지는 그 그래프가 정한다.

## 쓰면 무슨 일이 일어나나

에이전트 안에서 평소 말투로 시킨다.

```text
/graphori:graphori 공개 API에 rate limiting 넣고 테스트까지 붙여줘
```

그러면 네 가지가 일어난다.

**목록이 아니라 그래프를 짠다.** 단계마다 의존 관계가 명시된 노드가 된다. 서로
엮이지 않은 노드는 같이 돌 수 있고, 앞 결과가 필요한 노드는 기다린다. 당신이
병렬로 해달라고 해서 병렬이 되는 게 아니라, 두 노드가 서로를 건드리지 않는다고
그래프가 말하니까 병렬이 된다.

**필요 없는 단계는 뺀다.** 한 줄 고치는 일에 조사 단계를 붙이지 않는다. 할 일이
없는 팀은 이유와 함께 "이번엔 빠짐"으로 표시돼서, 실행 전에 계획에서 보인다.

**노드마다 모델을 고른다.** 기계적인 수정과 설계 판단에 같은 모델을 쓸 이유가
없으니 같은 모델을 주지 않는다.

**확인하기 전에는 끝났다고 하지 않는다.** 구현 노드마다 검증 노드가 붙고, 실제
명령을 돌린다. "완료"는 그 명령이 통과했다는 뜻이다.

## 다섯 개 팀

Graphori는 다섯 역할을 두고 계획한다. 노드는 하나의 팀에 속하고, 실행마다
필요한 팀만 쓴다.

| 팀 | 하는 일 | 언제 나오나 |
| --- | --- | --- |
| **운영실** | 그래프를 짜고 역할을 배정하고 결과를 모은다. 당신의 에이전트 세션이 이 역할이다. | 항상 |
| **조사팀** | 변경이 딛고 설 사실을 모은다. 외부 자료거나, 지금 코드가 어떻게 생겼는지. | 그렇게 적었을 때 (`조사`, `리서치`, `research`, `문서 확인`) |
| **설계팀** | 코드를 쓰기 전에 접근 방법을 정한다. | 그렇게 적었을 때 (`설계`, `design`, `architecture`) + 변경 요청 |
| **제작팀** | 선언된 write scope 안에서 변경을 쓴다. | 대부분 |
| **품질관리팀** | 검사를 돌리고 독립 판정을 남긴다. | 뭔가를 구현했을 때마다 |

어떤 팀이 나오는지는 당신이 쓴 말에서 단어를 찾아 정한다. 계획기가 작업을 이해해서
판단하는 게 아니다. "rate limit 옵션을 조사하고 구현해줘"라고 하면 조사 단계가 붙고,
"오타 고쳐줘"는 안 붙는다. 알아 둘 만한 이유가 있다 — 필요하면 그렇게 적어서 부를 수
있다는 뜻이다.

제작과 검증은 항상 별개 노드에 별개 역할이라 자기 일에 자기가 도장을 찍지 못한다.
다만 그 분리는 계획기가 그래프를 그렇게 짜서 생긴다. 이벤트 계층은 판정이 검증자에게서
왔는지만 확인하지, 그 검증자가 작업자와 다른 주체인지까지 대조하지는 않는다.

작은 수정이면 운영실·제작팀·품질관리팀만 쓰고, 그렇다고 말한다.

```text
조사팀 · 이번에는 필요 없음
이 요청에는 외부 조사가 필요하지 않습니다.
```

## 병렬로 돌릴지 어떻게 정하나

쪼개는 건 공짜가 아니다. 둘로 나누면 시작 비용이 두 번 들고, 맥락을 양쪽에 넘겨야
하고, 끝에서 합쳐야 한다. 그래서 쪼개는 쪽이 이길 때만 쪼갠다.

```
이득 = (순서대로 돌렸을 때 걸리는 시간)
     − (가장 긴 노드 + 각 노드 시작 비용 + 인계 + 병합)

이득이 max(30초, 순차 시간의 15%) 이상일 때만 나눈다
```

그 선을 못 넘으면 한 세션에서 계속한다. 나눠서 아끼는 시간보다 나누느라 드는
비용이 크기 때문이다. 기본 동시 실행은 2개고, 그래프에 정말 독립적인 일이 더
많으면 늘릴 수 있다.

이게 원래는 당신이 매번 머릿속으로 하던 계산이다.

## 모델은 어떻게 고르나

노드마다 요구 수준을 분류하고, 분류마다 최소 점수가 있다. 그 선을 넘고 필요한
능력을 갖춘 모델만 남긴 다음, 그중 **가장 빠른** 것을 쓴다.

| 노드 종류 | 최소 coding index |
| --- | ---: |
| 단순 작업 | 42 |
| 범위가 좁은 구현 | 48 |
| 일반·복잡한 구현 | 56 |
| 설계 | 56 |
| 검증 | 56 |
| 핵심 종합 | 64 |

점수는 [Artificial Analysis Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents)
v1.3 스냅샷에서 온다. 나중에 라우팅 판단을 재생할 수 있도록 저장소에 고정해 뒀다.

| 모델 | 제공자 | effort별 coding index | 승인 등급 |
| --- | --- | --- | --- |
| `gpt-5.6-luna` | Codex | medium 42 · high 51 | 일반 |
| `gpt-5.6-terra` | Codex | medium 48 · high 56 · xhigh 57 | 일반 |
| `gpt-5.6-sol` | Codex | medium 61 · high 64 · xhigh 65 | **프리미엄** |
| `claude-sonnet-5` | Claude Code | 스냅샷에 없음 — 아래 참고 | 일반 |
| `claude-opus-5` | Claude Code | medium 62 · high 63 · xhigh 67 | **프리미엄** |

점수 위에 규칙 세 개가 얹힌다.

**빠른 쪽이 이기되, 쓰던 경로에 이점을 준다.** 조건을 만족하는 것 중 예상 소요 시간이
가장 짧은 걸 고른다. 기준선만 넘으면 되는 노드에 한참 넘는 모델을 쓴다고 더 좋아지지
않는다. 예외가 하나 있는데, 경로가 왔다 갔다 하지 않도록 이미 선호하는 모델이 있으면
경쟁 모델은 10%보다 더 빨라야 그 자리를 뺏는다.

**일반 등급이 먼저다.** `gpt-5.6-sol`과 `claude-opus-5`는 게이트가 걸려 있다.
후보군에 일반 등급 모델이 하나도 없을 때만 고려되고, 그때도 멈춰서 물어본다. 받은
승인은 그 노드, 그 모델 계열, 그 effort 상한, 그 write scope에만 묶인다. 나머지
실행에 재사용되지 않는다.

**점수 없는 모델은 없다고 적는다.** `claude-sonnet-5`는 고정 스냅샷에 항목이 없다.
숫자를 빌려오는 대신 점수 없는 모델도 후보로 받아들이는데 — 조사·설계·검증에는 항상,
구현에는 점수 있는 후보가 하나도 없을 때만 — 그 노드는
`BENCHMARK_PARTIAL_PROVIDER_ONLY`와 부분 신뢰도로 기록된다. 즉 기준선을 넘지 않고
선택되는 경우가 있고, 그럴 때는 점수를 지어내는 대신 계획에 그렇다고 적는다.

제공자 CLI가 없거나 로그인이 안 돼 있으면 노드를 실패시키지 않고 쓸 수 있는
경로로 넘기면서 이유를 남긴다.

## 뭐가 좋아지나

직접 프롬프트로 시키는 것과 비교하면,

- 결과만 설명하면 된다. 쪼개는 건 더 이상 당신 일이 아니다.
- 병렬은 이득이 있을 때 일어난다. 당신이 기억해서 시킬 때가 아니라.
- 필요 없는 단계는 이유와 함께 빠지니 계획이 짧고, 돌기 전에 근거가 보인다.

기본값으로 여러 명을 띄우는 오케스트레이터와 비교하면,

- 작은 일은 한 세션에서 끝난다. 통제된 비교에서 아무것도 못 찾던 두 번째 AI
  리뷰어를 빼자 AI 호출이 절반이 됐다.
- 완료는 검사 통과지, 모델이 됐다고 말한 게 아니다.
- 라우팅 판단, 판정, 검사가 전부 append-only 로컬 journal에 남아 다시 재생된다.

## 설치

에이전트 안에서 실행한다. 다른 경로와 자세한 설명은 [INSTALL.md](docs/public/INSTALL.md)에 있다.

### Claude Code

```text
/plugin marketplace add dotoricode/graphori
/plugin install graphori@graphori
```

재시작한 뒤 `/graphori:graphori <할 일>`.

### Codex

```sh
codex plugin marketplace add dotoricode/graphori
codex plugin add graphori@graphori
```

새 세션에서 `$graphori:graphori <할 일>`.

Skill만 있으면 된다. `graphori` 명령줄, journal 재생, 이어서 실행이 필요하면 별도
Python 런타임을 얹을 수 있는데 선택 사항이고 [INSTALL.md](docs/public/INSTALL.md)에
정리해 뒀다.

## 무엇을 측정했나

### 공개 72회 비교

Direct, v1 방식, Graphori v2를 작은 deterministic Python 과제 4종에서 각 조합당
3회 실행했다. Codex와 Claude 결과는 섞지 않았다. 같은 provider·과제 안에서는 시작
파일, model, effort, 공개·숨은 검사와 write scope가 모두 같았다.

TTUR은 새 fixture를 만든 시점부터 provider 작업, 공개 검사와 숨은 검사를 모두 마칠
때까지의 wall time이다.

**Codex · `gpt-5.6-terra`, medium · 조건별 12회**

| 항목 | Direct | v1 방식 | Graphori v2 |
| --- | ---: | ---: | ---: |
| 성공한 실행 | 12/12 | 12/12 | 12/12 |
| 숨은 검사 | 36/36 | 36/36 | 36/36 |
| 완료 보고와 실제 결과 일치 | 12/12 | 12/12 | 12/12 |
| 허용 범위 밖 파일 변경 | 0 | 0 | 0 |
| 재작업 | 0 | 0 | 0 |
| AI 세션 | 12 | 24 | 12 |
| TTUR 중앙값 | 29.059초 | 54.683초 | 34.823초 |
| 전체 입력 토큰 | 967,834 | 1,614,763 | 1,080,869 |
| 캐시된 입력 토큰 | 800,512 | 1,330,688 | 905,984 |
| 신규 입력 토큰 | 167,322 | 284,075 | 174,885 |
| 출력 토큰 | 11,905 | 19,714 | 15,109 |
| Provider가 보고한 비용 | 알 수 없음 | 알 수 없음 | 알 수 없음 |

**Claude · `claude-sonnet-5`, medium · 조건별 12회**

| 항목 | Direct | v1 방식 | Graphori v2 |
| --- | ---: | ---: | ---: |
| 성공한 실행 | 12/12 | 12/12 | 12/12 |
| 숨은 검사 | 36/36 | 36/36 | 36/36 |
| 완료 보고와 실제 결과 일치 | 12/12 | 12/12 | 12/12 |
| 허용 범위 밖 파일 변경 | 0 | 0 | 0 |
| 재작업 | 0 | 0 | 0 |
| AI 세션 | 12 | 24 | 12 |
| TTUR 중앙값 | 22.723초 | 55.287초 | 23.866초 |
| 전체 입력 토큰 | 1,413,288 | 2,819,151 | 1,413,366 |
| 캐시된 입력 토큰 | 1,228,242 | 2,426,808 | 1,228,245 |
| 신규 입력 토큰 | 185,046 | 392,343 | 185,121 |
| 출력 토큰 | 14,659 | 33,394 | 14,534 |
| Provider가 보고한 비용 | $1.1322 | $2.3883 | $1.1313 |

v1 방식과 비교하면 Graphori v2는 AI 세션을 50% 줄였고 TTUR 중앙값은 Codex에서
36.3%, Claude에서 56.8% 줄었다. Direct와 비교하면 deterministic 검증과 journal의
대가가 보인다. v2 TTUR은 Codex에서 19.8%, Claude에서 5.0% 더 길었다. Claude의
토큰과 provider 보고 비용은 Direct와 사실상 같았고, Codex 전체 입력은 11.7% 많았다.
즉 작은 작업에서 orchestration이 Direct보다 빠르다는 결과가 아니다.

실제 production 저장소가 아니라, 같은 입력을 정해진 Python 검사로 판정하는 작은
fixture다. provider·조건별 `n=12`다. [방법](benchmarks/three_arm/PROTOCOL.ko.md) ·
[보고서](benchmarks/three_arm/REPORT.ko.md) ·
[원자료 JSONL](benchmarks/three_arm/raw-results.jsonl) ·
[계산 결과](benchmarks/three_arm/results.json)

### 이전 기본값 결정 실험

그보다 앞선 세 실험이 지금 기본값을 정했다. 셋 다 "하지 마라"였고, 기본값이 그
결과를 따른다.

**두 번째 AI 리뷰어가 첫 번째가 놓친 걸 잡아내나?** Python 작업 2종, 각 조건 4회,
Codex만. 아무것도 못 찾았고 AI 호출만 두 배였다. 그래서 v2는 기본으로 쓰지 않는다.

| 항목 | 두 번째 리뷰어 있음 | 없음 | 변화 |
| --- | ---: | ---: | ---: |
| 숨긴 검사 통과 | 4/4 | 4/4 | 같음 |
| 완료 보고와 실제 결과 일치 | 4/4 | 4/4 | 같음 |
| 허용 범위 밖 파일 변경 | 0 | 0 | 같음 |
| 리뷰어가 찾은 문제 | 0 | 해당 없음 | — |
| AI 호출 수 | 8 | 4 | −50% |
| 완료 시간 중앙값 | 48.5초 | 32.1초 | −34% |
| 전체 입력 토큰 | 567,584 | 333,681 | −41% |
| 캐시된 입력 토큰 | 396,800 | 267,776 | −33% |
| 신규 입력 토큰 | 170,784 | 65,905 | −61% |
| 출력 토큰 | 4,960 | 3,309 | −33% |
| Provider 비용 | 기록 안 됨 | 기록 안 됨 | 알 수 없음 |

표본이 작다. v1 방식은 비공개 개발 이력의 당시 문서로 재현한 비교군이며, 과거
실행을 재생한 결과가 아니다. 당신의 코드베이스에서도 이렇게 나온다는 뜻은 아니다.
보관된 산출물로 직접 다시 계산할 수 있다.

```sh
python benchmarks/v1_v2/verify_results.py
```

[방법](benchmarks/v1_v2/PROTOCOL.md) · [보고서](benchmarks/v1_v2/REPORT.md) · [원자료](benchmarks/v1_v2/raw-results.json)

**다른 Agent Skill을 노드에 자동으로 붙여야 하나?** Graphori는 외부 Skill을 단계에
바인딩할 수 있다. 시험 대상으로 `ponytail`과 `tdd`를 썼는데, 둘 다 Graphori의
일부가 아니라 외부 Skill이다. 자동 바인딩은 어느 조합에서도 이득이 없었고, Codex
에서 TDD Skill은 결과를 오히려 나쁘게 만들었다. 그래서 **자동 선택은 꺼져 있다.**
필요하면 직접 지정해서 붙이면 된다.

| 실험 | 표본 | 결과 |
| --- | ---: | --- |
| [두 Direct 경로가 믿을 만한가?](docs/archive/research/RRC-04_DIRECT_ROUTE_BASELINE.md) | 24 | 24/24 통과, 범위 위반 없음 — 둘 다 유지 |
| [`ponytail` 자동 바인딩?](docs/archive/research/RRC-05A_PONYTAIL_EFFECTIVENESS.md) | 22 | 어느 조합에서도 이득 없음 — 미적용 |
| [`tdd` 자동 바인딩?](docs/archive/research/RRC-05B_TDD_EFFECTIVENESS.md) | 24 | Codex에서 해로움 — 미적용 |

## 알아 둘 한계

- Graphori는 샌드박스가 아니다. 승인한 provider는 파일을 고치고 명령을 실행할 수
  있다. write scope를 좁게 잡고 버전 관리를 쓸 것.
- 검사는 그 명령이 확인하는 범위까지만 증명한다.
- heartbeat는 provider가 살아 있다는 뜻이지 진행 중이라는 뜻이 아니다.
- `0.9.0-beta.1`은 베타고 이름이 그렇게 말하고 있다. 안정 API는 없고, 패키지
  레지스트리에 올린 것도 아직 없다.
- Orca 연동은 선택 adapter로 있고 지금은 꺼져 있다.
- macOS generic adapter 전용 검사는 macOS 26.5.2 x86_64와 Python 3.11·3.14에서
  통과했다. 프로세스 트리 종료, 경로·심볼릭 링크 이탈, 대소문자 충돌, journal 공개,
  replay, idempotency와 실제 generic adapter lifecycle을 확인했다. 이는 기록된 Mac
  한 대의 결과이지 모든 Mac을 보장하지 않는다. Linux 릴리스 검사는 통과했다고
  주장하지 않으며, Windows 설치와 Job Object 동작은 실험적 범위다.

## 문서

- [제품 안내](docs/public/README.ko.md) — 여기서 시작
- [아키텍처](docs/architecture/GRAPHORI_ARCHITECTURE.md), [이벤트 프로토콜](docs/architecture/EVENT_PROTOCOL.md)
- [결정 기록](docs/decisions/README.md) — 지금 기본값이 왜 이런지
- [기여 안내](CONTRIBUTING.md) · [행동 강령](CODE_OF_CONDUCT.md) · [변경 이력](CHANGELOG.md) · [보안](SECURITY.md)
- [docs/archive/](docs/archive/README.md) — 근거 보존용 빌드·리뷰 기록

## 라이선스

MIT. [LICENSE](LICENSE) 참고.
