# Graphori 학습 게임 교육학 연구

> 조사일: 2026-08-11 (Asia/Seoul)
> 목적: Graphori의 동작 과정을 12살도 이해할 수 있는 HTML 학습 게임으로 가르칠 때 사용할 교육학 근거와 설계 판단을 정리한다.
> 범위: retrieval practice/active recall, scaffolding, cognitive load, feedback, worked examples, dual coding/multimedia learning, mastery/spacing, learner agency/game-based learning.

이 문서는 연구 노트입니다. 실제 게임 구현은 별도의 GRAPHORI_LEARNING_GAME.html에 반영했으며, 이 문서는 연구에서 직접 확인한 것과 Graphori에 적용한 설계 추론을 구분해 보존합니다.

## 1. 먼저 결론

Graphori 학습 게임은 “예쁜 픽셀 캐릭터를 구경하는 게임”이 아니라 다음 질문을 직접 풀어 보는 게임이어야 한다.

> **누가 어떤 일을 맡고, 어떤 일은 동시에 할 수 있으며, 무엇이 실제 완료를 증명하는가?**

가장 안전한 학습 구조는 다음의 짧은 반복이다.

```text
1. 먼저 예상한다        (기억에서 꺼내기)
2. 작은 힌트를 받는다    (발판)
3. 실제 실행 예시를 본다 (worked example)
4. 다시 직접 선택한다    (적용/전이)
5. 왜 맞고 틀렸는지 안다 (설명형 피드백)
6. 조금 뒤에 다시 푼다   (간격 반복과 숙달 확인)
```

연구가 직접 지지하는 것은 위 학습 활동들이다. **픽셀 아트, 캐릭터 모션, 점수, 배지 자체가 학습을 보장한다는 근거는 이 조사에서 찾지 않았다.** 따라서 게임 요소는 학습 활동을 시작하게 하고 상태를 기억하기 쉽게 만드는 껍데기로 사용하되, 학습 판정은 설명·예측·적용 결과로 해야 한다.

## 2. Graphori에서 무엇을 배워야 하는가

### 2.1 12살에게 설명하는 Graphori

| Graphori 말 | 12살에게 하는 말 |
| --- | --- |
| 그래프(graph) | 큰 숙제를 작은 카드와 화살표로 그린 지도다. |
| 노드(node) | 한 팀이 맡은 작은 할 일 카드다. |
| Router / 기획팀 | 큰 숙제를 카드로 나누고, 어떤 카드가 먼저 열릴지 정하는 관제탑이다. |
| Worker / 작업팀 | 자기 카드의 일을 실제 파일과 명령으로 만든다. |
| Verifier / 검증팀 | 만든 친구와 다른 친구가 다시 시험한다. |
| `requires` 화살표 | 앞 카드가 끝나야 다음 카드가 열리는 기다림 표시다. |
| 병렬 작업 | 서로 기다릴 필요 없는 카드 여러 장을 동시에 푸는 것이다. |
| fan-in | 여러 카드의 결과를 한곳에 모아 다음 카드를 여는 것이다. |
| dashboard | 여러 방에서 일어나는 일을 한눈에 보는 실시간 관제 지도다. |
| journal | 누가 언제 무엇을 했는지 적는 지워지지 않는 공책이다. |
| replay | 공책을 처음부터 다시 읽어 같은 상태가 나오는지 확인하는 것이다. |
| `worker_finished` | “내가 작업을 끝냈다”는 제출이다. |
| verifier `pass` / Human Gate `approve` | “다른 확인 절차까지 통과했다”는 도장이다. |
| 완료 보고 | 코드 diff를 읽지 않아도 목표·구조·결과·근거를 이해하는 설명이다. |

핵심 오해는 반드시 따로 가르쳐야 한다.

```text
프로그램이 끝남        ≠ 검증까지 끝남
heartbeat가 옴         ≠ 실제 작업이 진행됨
캐릭터가 움직임        ≠ 진행률이 올라감
대시보드가 켜짐        ≠ 작업 결과가 생김
```

### 2.2 현재 저장소에서 실제로 실행되는 범위

학습 게임이 제품의 현재 기능을 과장하지 않으려면 “설계상 가능한 것”과 “현재 CLI에서 실제로 실행되는 것”을 분리해야 한다.

| 범위 | 현재 근거 | 학습 게임에서의 표현 |
| --- | --- | --- |
| 실제 명령 실행 | [`src/graphori_core/cli.py`](../../../src/graphori_core/cli.py)의 generic terminal adapter가 비대화형 명령 한 번을 실행한다. | Worker가 실제 명령을 실행하고 출력을 제출하는 장면으로 보여 준다. |
| 성공·실패 기록 | CLI가 `worker_finished`, 노드 상태, `run_terminal`을 JSONL journal에 기록한다. | 초록색 캐릭터보다 `exit_code`와 event를 먼저 보여 준다. |
| hash-chain journal과 replay | [`src/graphori_core/journal.py`](../../../src/graphori_core/journal.py)가 사건을 순서와 digest로 보존하고 replay한다. README의 실제 예시는 `event_count = 10`, `replay_verified = true`다. | 공책의 한 줄을 클릭하고 “다시 읽어도 같은가?”를 확인하게 한다. |
| status와 snapshot/dashboard | [`src/graphori_core/dashboard.py`](../../../src/graphori_core/dashboard.py)가 journal을 읽어 snapshot을 만들고 SSE로 snapshot/replay/heartbeat를 보낸다. | 대시보드는 작업 후 결과판이 아니라 진행 중인 관제판으로 설명한다. |
| 역할 그래프 모델 | [`src/graphori_core/compiler.py`](../../../src/graphori_core/compiler.py)는 Router, Worker, Verifier, Human Gate를 포함한 topology를 컴파일하고 독립성·위험·DAG 규칙을 검사한다. | “역할을 나누는 원리”를 가르친다. |
| generic CLI의 실제 topology | CLI 파일의 설명대로 현재 generic adapter의 실행 그래프는 의도적으로 **한 개 Worker 노드**다. | 기획·조사·구현·검증 캐릭터는 전체 설계 개념을 가르치는 시각 모델로 표시하고, CLI가 항상 네 세션을 자동 실행한다고 말하지 않는다. |
| 아직 기본 지원하지 않는 범위 | README는 여러 구현자의 동시 WIP, interactive PTY/GUI/browser 자동화, 독립 verifier의 완성된 자동 팀 실행을 기본 지원 범위 밖으로 명시한다. | “현재 된다”와 “앞으로 확장할 수 있다”를 카드 색이나 문장으로 구분한다. |

실제 실행 결과를 학습에 쓰는 좋은 예는 다음과 같다.

```json
{
  "terminal_status": "succeeded",
  "exit_code": 0,
  "event_count": 10,
  "replay_verified": true,
  "node_verdict": "pending"
}
```

이 결과의 뜻은 “명령은 성공했고 기록은 다시 읽혔지만, 독립 검증 도장은 아직 없다”이다. 즉, **작업 프로세스의 성공과 사람이 신뢰할 수 있는 완료를 구분하는 실제 산출물**이다. 자세한 원문 예시는 [`README.md`](../../README.md)의 “실제 실행 결과”와 현재 참여형 게임 [`docs/GRAPHORI_LEARNING_GAME.html`](../../GRAPHORI_LEARNING_GAME.html)에 있다.

## 3. 연구를 고른 기준

### 3.1 출처 등급

- **P — Primary**: 저자가 직접 수행한 실험 또는 실제 교실 연구.
- **F — Foundational**: 개념을 처음 제안하거나 원래의 실험적 틀을 만든 논문.
- **S — Synthesis / official**: 메타분석·이론 종합·공식 기관 보고서. 유용하지만 개별 실험의 직접 증거처럼 쓰지 않는다.

이번 문서는 검색 결과를 요약한 2차 블로그를 근거로 삼지 않고, 논문 원문/저자 원고·PubMed·ERIC·미국 교육부 연구기관·National Academies 링크를 우선했다. 모든 설계 주장은 아래에서 **“연구가 직접 말하는 것”**과 **“Graphori에 대한 우리 추론”**으로 나눈다.

## 4. 원리별 조사 결과와 Graphori 적용

### 4.1 Retrieval practice / active recall: 보기 전에 기억에서 꺼내기

**연구가 직접 말하는 것**

- 10살 안팎의 초등학생 88명을 대상으로 한 세 실험에서, 단어를 다시 읽는 것보다 기억에서 꺼내는 연습을 한 아이들이 나중의 자유 회상·재인 검사에서 더 좋은 결과를 보였다. 이 연구는 아이들의 retrieval practice 효과를 직접 측정했다. ([Karpicke, Blunt, & Smith, 2016, *Frontiers in Psychology*](https://doi.org/10.3389/fpsyg.2016.00350))
- 대학생의 외국어 단어 연구에서도 이미 맞힌 뒤 다시 읽는 것보다 다시 시험해 보는 것이 지연된 회상에 더 큰 이점을 주었다. 다만 이 연구의 참여자는 대학생이고 Graphori가 아니다. ([Karpicke & Roediger, 2008, *Science*](https://doi.org/10.1126/science.1152408))
- 미국 Institute of Education Sciences의 초등학생용 Guided Retrieval Practice 프로젝트는 빈칸·단서 회상·자유 회상을 **지원이 많은 단계에서 지원이 적은 단계로** 진행하도록 설계한다. 기관 설명도 어린 학습자는 안내·지원·scaffolding 없이 성공적인 retrieval을 하기 어렵다고 명시한다. ([IES/NCER project description](https://nces.ed.gov/use-work/awards/computer-based-guided-retrieval-practice-elementary-school-children))

**Graphori에 대한 우리 추론**

- 화면에 Graphori 설명을 먼저 전부 보여 주지 말고, “기획팀 대시보드가 먼저 켜질까, 작업이 먼저 시작될까?”를 먼저 묻는다.
- `parallel_started`, `worker_finished`, `verdict_recorded(pass)` 카드를 순서대로 놓게 한다.
- 선택형만 쓰지 말고 “왜 `worker_finished`만으로 완료가 아니라고 생각하나요?” 같은 짧은 입력·문장 완성도 한 번 넣는다.
- 처음에는 `requires` 화살표와 후보 3개를 보여 주고, 익숙해지면 화살표 일부와 선택지를 줄인다.

**한계와 안전장치**

- 직접 연구의 자료는 단어·교과 내용이다. Graphori의 비동기 실행 구조를 배웠다는 증거는 아니다.
- 아이가 아무 단서 없이 자유 회상을 못 했다고 “모른다”고 판정하면 안 된다. 먼저 단서 회상, 그다음 부분 빈칸, 마지막에 자유 설명 순서로 난도를 올린다.
- 캐릭터를 클릭한 횟수나 퀴즈를 빨리 끝낸 시간은 retrieval 성공의 증거가 아니다.

### 4.2 Scaffolding: 처음에는 손잡이를 주고, 익숙해지면 뺀다

**연구가 직접 말하는 것**

- Wood, Bruner, Ross의 고전 논문은 초보자가 혼자 하기 어려운 문제를 튜터가 어떻게 돕는지 다룬 scaffolding의 기초 출처다. 이 원 논문 자체는 Graphori UI를 시험한 연구가 아니다. ([Wood, Bruner, & Ross, 1976, PubMed record](https://pubmed.ncbi.nlm.nih.gov/932126/))
- IES의 Guided Retrieval Practice 설계는 핵심 단어 찾기·질문·빈칸·단서 회상·자유 회상을 단계적으로 배열하고, retrieval 지원을 점차 줄이는 구체적인 프로그램 계획을 제시한다. ([IES/NCER project description](https://nces.ed.gov/use-work/awards/computer-based-guided-retrieval-practice-elementary-school-children))
- 초등학교 교실의 세 실험을 보고한 논문은 어린이가 대학생에게 효과적인 무지원 자유 회상을 그대로 수행하기 어려워했으며, 질문 지도가 있는 방식이 더 적합하다는 방향을 보고한다. ([Karpicke et al., 2014, *Journal of Applied Research in Memory and Cognition*](https://doi.org/10.1016/j.jarmac.2014.07.008))

**Graphori에 대한 우리 추론**

힌트 버튼을 세 단계로 만든다.

1. `단어 힌트`: “기획팀”, “기다림”, “검사”처럼 핵심 단어만 보여 준다.
2. `부분 지도`: 노드 일부와 `requires` 화살표를 보여 준다.
3. `worked example`: 실제 event 두세 줄을 보여 주고 다음 한 줄을 고르게 한다.

정답을 알려 주는 대신, “이 카드가 열리려면 어떤 카드가 먼저 끝나야 할까?”처럼 다음 생각을 유도한다. 같은 문제를 다시 풀 때는 1단계 힌트만 남기고 2·3단계 힌트를 숨긴다.

**한계와 안전장치**

- scaffolding은 “항상 많은 설명을 보여 주기”가 아니다. 계속 답을 대신 주면 학습자가 스스로 구조를 만들 기회가 줄어든다.
- 힌트 사용을 실패 점수로 벌하지 않는다. 대신 같은 개념을 더 적은 힌트로 다시 풀었는지를 본다.
- 어떤 힌트가 실제로 도움이 되는지는 Graphori 사용자 시험으로 확인해야 한다. 위 연구에서 바로 정해지는 힌트 문구는 없다.

### 4.3 Cognitive load: 한 번에 너무 많은 것을 들게 하지 않기

**연구가 직접 말하는 것**

- Sweller의 문제 해결 실험·이론 논문은 초보자가 `means–ends analysis`처럼 답을 찾는 데 많은 인지 자원을 쓰면, 문제 해결에 필요한 schema를 배우는 데 쓸 자원이 줄어들 수 있다고 설명한다. ([Sweller, 1988, *Cognitive Science*](https://doi.org/10.1207/S15516709COG1202_4))
- 멀티미디어 학습 이론은 말과 그림을 처리하는 경로가 각각 제한된 용량을 가지며, 학습은 두 표현 사이의 의미 있는 연결을 만들 때 일어난다고 제안한다. 이는 원 실험 하나의 결과가 아니라 이론·연구 종합이다. ([Mayer & Moreno, 2003, *Educational Psychologist*](https://doi.org/10.1207/S15326985EP3801_6))

**Graphori에 대한 우리 추론**

- 한 화면에 모든 JSONL event, 모든 캐릭터, 전체 diff, 긴 설명을 동시에 쏟지 않는다.
- `목표 → 그래프 지도 → 현재 event → 실제 산출물 → 검증 도장`처럼 한 장면에 한 질문만 둔다.
- 큰 장식 제목보다 짧은 문장, 한 가지 폰트, 충분한 여백을 사용한다. 사용자가 앞서 지적한 겹치는 글자와 지나치게 큰 제목 문제도 인지 부하를 늘릴 수 있는 화면 문제로 취급한다.
- 대시보드의 모션은 사건이 발생했을 때만 재생한다. 단순 heartbeat는 “살아 있음” pulse만 보여 주고 progress를 올리지 않는다. 이는 교육 연구의 결론이라기보다 Graphori의 상태 의미를 보존하는 제품 추론이다.

**한계와 안전장치**

- 인지 부하는 이 문서에서 직접 측정하지 않았다. “깔끔해 보인다”와 “인지 부하가 낮다”는 같은 말이 아니다.
- 정보가 적다고 항상 좋은 것은 아니다. `worker_finished`와 `verdict`처럼 구분에 꼭 필요한 정보는 남겨야 한다.
- 아이콘·픽셀 아트가 정보를 전달하지 않고 장식만 되면 화면을 복잡하게 만들 수 있다.

### 4.4 Feedback: “틀렸어”가 아니라 다음 생각을 알려 주기

**연구가 직접 말하는 것**

- 7–9살 아동 75명을 무작위로 나눈 수학 문제 해결 실험에서, 컴퓨터의 즉시 피드백은 낮은 사전 지식과 높은 사전 지식 집단 모두의 mastery와 transfer를 돕는 결과를 보였다. 단순 정답 표시가 아니라 문제 해결 중의 안내라는 맥락이다. ([Fyfe & Rittle-Johnson, 2016, *Journal of Experimental Child Psychology*](https://doi.org/10.1016/j.jecp.2016.03.009); [author/ERIC full text](https://files.eric.ed.gov/fulltext/ED566264.pdf))
- 같은 논문은 피드백이 항상 좋은 것은 아니며, 사전 지식·시점·내용에 따라 중립적이거나 부정적일 수 있다고 논의한다. 더 넓은 피드백 문헌의 메타분석도 평균 효과만 보고 모든 피드백을 같은 처치로 볼 수 없다고 결론낸다. ([Kluger & DeNisi, 1996, meta-analysis](https://doi.org/10.1037/0033-2909.119.2.254); [Wisniewski, Zierer, & Hattie, 2020, meta-analysis](https://doi.org/10.3389/fpsyg.2019.03087))

**Graphori에 대한 우리 추론**

오답 피드백은 다음 네 가지를 포함한다.

```text
무엇을 골랐나       → “구현팀을 검증팀보다 먼저 완료로 표시했어요.”
무엇이 문제인가     → “worker_finished는 제출이지 verifier pass가 아니에요.”
어떤 증거가 있는가  → “현재 event에는 worker_finished만 있어요.”
다음에 뭘 해볼까    → “검증 event 카드를 뒤에 놓아 보세요.”
```

정답을 고르면 짧게 이유를 설명하고, 틀리면 실패 캐릭터나 빨간 화면으로 창피를 주지 않는다. 같은 개념의 새 예제를 한 번 더 주어 수정된 생각을 사용하게 한다.

**한계와 안전장치**

- 즉시 피드백이 답을 외우게만 만들 수 있으므로, 정답을 본 뒤 바로 끝내지 말고 잠시 후 새 그래프에 적용하게 한다.
- “속도가 빠르다”, “캐릭터가 많이 움직였다”, “점수가 높다”를 feedback으로 쓰지 않는다. 목표와 관련된 구조·증거에만 피드백한다.
- 위 아동 연구는 수학 문제이고, Graphori의 설명 피드백 효과는 아직 검증되지 않았다.

### 4.5 Worked examples: 완성된 한 판을 보고 다음 판을 직접 만들기

**연구가 직접 말하는 것**

- Sweller와 Cooper는 Year 9·Year 11·대학생을 포함한 다섯 실험에서 대수 문제 해결 지식과 worked example을 이용한 습득 절차를 연구했다. 논문의 문제의식은 초보자가 답을 찾는 search에만 매달리지 않고 문제 해결 schema를 배울 수 있게 하는 것이다. ([Sweller & Cooper, 1985, *Cognition and Instruction*](https://doi.org/10.1207/S1532690XCI0201_3); [article record with abstract](https://oamonitor.ireland.openaire.eu/rpo/rcsi/search/publication?pid=10.1207%2Fs1532690xci0201_3))
- 지원이 많은 예제가 초보자에게만 유리할 수 있고, 이미 아는 학습자에게는 문제를 직접 푸는 편이 나을 수 있다는 expertise-reversal 연구가 있다. ([Kalyuga, Ayres, Chandler, & Sweller, 2003, *Educational Psychologist*](https://doi.org/10.1207/S15326985EP3801_4))

**Graphori에 대한 우리 추론**

첫 번째 미션에는 실제 산출물의 축약된 worked example을 보여 준다.

```text
run_created
  → graph_published
  → attempt_dispatched
  → worker_finished(exit_code=0)
  → run_terminal(succeeded)
```

그다음 화면에서 학습자가 다음 중 하나를 직접 완성한다.

- 어떤 카드가 병렬로 시작될 수 있는가?
- `worker_finished` 뒤에 어떤 검증 사건이 필요한가?
- `replay_verified=true`는 무엇을 확인한 값인가?

처음에는 모든 단계에 설명을 붙이고, 다음 미션에서는 가운데 event 하나를 비워 completion problem으로 만든다.

**한계와 안전장치**

- worked example 연구의 내용은 대수이고 Graphori가 아니다. “예제를 보여 주면 Graphori를 배운다”는 직접 결론을 내리지 않는다.
- 초보자와 경험자를 같은 화면으로 묶지 않는다. `처음 배우기` 모드에는 완성 예제, `익숙함` 모드에는 빈칸·새 사례를 준다.
- 예제를 읽은 뒤 반드시 새 그래프에 적용하는 문제를 넣어 단순 복사를 줄인다.

### 4.6 Dual coding / multimedia learning: 그림과 말이 같은 관계를 가리키게 하기

**연구가 직접 말하는 것**

- Mayer와 Anderson의 두 실험은 자전거 펌프 애니메이션을 본 대학생에게 말 설명을 그림과 함께 제시했을 때, 설명을 그림보다 먼저 준 조건보다 펌프의 작동을 응용하는 문제 해결이 나아지는지를 시험했다. 핵심은 그림이 있다는 사실보다 **말과 그림이 같은 움직임·원인 관계를 동시에 가리키는가**이다. ([Mayer & Anderson, 1991, *Journal of Educational Psychology*](https://doi.org/10.1037/0022-0663.83.4.484); [author-hosted full-text copy](https://www.researchgate.net/publication/232454397_Animations_Need_Narrations_An_Experimental_Test_of_a_Dual-Coding_Hypothesis))
- 이 연구는 “그림만 보여 주면 된다”거나 “애니메이션은 언제나 좋다”고 말하지 않는다. 연구자들도 애니메이션의 결과가 일관되지 않았던 당시 연구 상황과 words–pictures의 연결 필요성을 설명한다.

**Graphori에 대한 우리 추론**

- `fan-in` 장면에서 여러 색의 선이 한 카드로 모일 때, 옆의 짧은 문장도 “여러 결과를 모아 다음 일을 연다”라고 같은 관계를 말하게 한다.
- 키보드를 치는 캐릭터는 실제 `attempt_dispatched`나 `worker_finished` event와 맞춰 보여 준다. 사건이 없는데 계속 타이핑하는 애니메이션은 교육 정보가 아니다.
- 픽셀 아트는 팀의 역할을 기억시키는 표지로 쓰고, event 설명·화살표·짧은 문장과 연결한다. 장식용 캐릭터를 많이 넣어 화면을 가리지 않는다.

**한계와 안전장치**

- 원 실험은 성인 대학생·자전거 펌프라는 다른 주제다. Graphori에 대한 직접 효과는 없다.
- “dual coding”을 이유로 화면에 글과 그림을 무조건 더하지 않는다. 서로 같은 내용을 가리킬 때만 두 표현을 함께 쓴다.
- 소리나 복잡한 영상은 필수가 아니다. 무음·키보드 사용자도 같은 관계를 텍스트와 시각 연결로 이해할 수 있어야 한다.

### 4.7 Spacing과 mastery: 한 번 맞혔다고 끝내지 않기

**연구가 직접 말하는 것**

- 5–7살 어린이 36명이 과학 개념 수업을 한 번에 몰아서, 묶어서, 또는 시간 간격을 두고 받은 실험에서 spaced 조건이 단순·복잡한 개념의 일반화에서 더 좋은 결과를 보였다. 마지막 수업 뒤 한 주가 지난 검사에서도 이점이 나타났다. ([Vlach & Sandhofer, 2012, *Child Development*, NIH author manuscript](https://escholarship.org/content/qt3hr316z2/qt3hr316z2_noSplash_704ab46ed60e380990f100906a949a0a.pdf); [DOI](https://doi.org/10.1111/j.1467-8624.2012.01781.x))
- 실제 5학년 교실에서 39명의 아이가 낯선 영어 단어를 배운 연구에서도 일주일 간격 학습이 몰아 학습보다 5주 뒤 장기 회상에서 좋았다. ([Sobel, Cepeda, & Kapler, 2011, *Applied Cognitive Psychology*](https://doi.org/10.1002/acp.1747); [author manuscript](https://www.yorku.ca/ncepeda/publications/SCK2011.pdf))
- Bloom의 mastery 원 논문은 먼저 “무엇을 mastery라고 부를지”를 정하고, 학습 시간·수업의 질·학습자의 이해를 고려해야 한다고 주장한다. 이는 Graphori의 숫자 기준을 직접 정해 주는 실험 결과가 아니다. ([Bloom, 1968, ERIC record](https://eric.ed.gov/?id=ED053419); [full text PDF](https://files.eric.ed.gov/fulltext/ED053419.pdf))
- 더 넓은 spacing 문헌의 메타분석은 최적 간격이 학습 뒤 얼마나 오래 기억해야 하는지와 함께 달라진다고 보고한다. 따라서 모든 사람에게 “정확히 10분 뒤” 같은 고정 규칙을 연구 사실처럼 쓰지 않는다. ([Cepeda et al., 2006, *Psychological Bulletin*](https://pubmed.ncbi.nlm.nih.gov/16719566/))

**Graphori에 대한 우리 추론**

학습 게임의 한 세션 안에서 끝내지 않고 다음처럼 다시 만난다.

```text
첫 판: 대시보드가 먼저 켜지는 이유
조금 뒤: 새로운 노드 지도로 병렬/순차 판단
다음 방문: worker 성공과 verifier pass 구분
마지막: 실제 Graphori 산출물을 어린이 말로 설명
```

제품의 임시 mastery 기준은 다음과 같이 제안한다. 이것은 **연구가 정한 숫자가 아니라 Graphori용 설계 가설**이다.

1. 한 번은 힌트를 받아 정확히 설명한다.
2. 간격을 둔 뒤 힌트 없이 같은 개념을 회상한다.
3. 모양이 다른 새 그래프에 적용한다.

세 가지를 통과해야 “이 카드를 기억했다”가 아니라 “이 구조를 이해하고 새 상황에 쓸 수 있다”고 표시한다. 한 번의 정답이나 캐릭터의 완료 pose만으로 mastery 배지를 주지 않는다.

**한계와 안전장치**

- 짧은 브라우저 게임 한 번으로 장기 학습을 증명할 수 없다.
- 간격은 사용자의 일정과 재방문 가능성을 고려해 조절해야 한다. 로컬 저장 기능을 넣더라도 개인정보나 학습 기록을 원격으로 보내는 것은 별도 동의 없이는 하지 않는다.
- mastery 기준은 실제 사용자 시험에서 난이도와 오답 유형을 보고 조정해야 한다.

### 4.8 Learner agency와 game-based learning: 선택은 주되 목표를 잃지 않기

**연구가 직접 말하는 것**

- 7·8학년 여학생 1,110명을 42개 체육 수업에서 choice/no-choice 조건에 무작위 배정한 연구에서는 선택권을 받은 집단의 상황적·맥락적 동기와 자율성 관련 지표가 더 높았다. 그러나 이는 체육 활동의 선택 연구이며 Graphori 학습 성취를 직접 측정한 것이 아니다. ([Prusak et al., 2004, *Journal of Teaching in Physical Education*](https://doi.org/10.1123/jtpe.23.1.19))
- 반대로 228명이 참여한 자기 통제형 피드백 연구에서는 연습 중 선택을 주는 것만으로 motor learning advantage가 나타나지 않았다. 선택은 자동으로 학습을 개선하는 버튼이 아니다. ([Carter et al., 2022, *Psychonomic Bulletin & Review*](https://doi.org/10.3758/s13423-022-02170-5))
- National Academies의 공식 합의 보고서는 학습을 학습자·맥락·문화와 함께 다루며, 학교와 성인 학습 환경을 설계할 때 동기와 기술의 맥락을 별개 장식으로 보지 않는다. 이 보고서는 Graphori 게임의 효과를 실험한 자료가 아니라 고신뢰 종합 자료다. ([National Academies, *How People Learn II*, 2018](https://doi.org/10.17226/24783))

**Graphori에 대한 우리 추론**

학습 목표를 건너뛸 수 없는 작은 선택권을 준다.

- 먼저 볼 노드를 선택한다: `기획`, `조사`, `구현`, `검증`.
- 힌트 수준을 선택한다: `단어`, `부분 지도`, `완성 예시`.
- 결과 설명 방식을 선택한다: `카드 순서`, `이벤트 공책`, `캐릭터 대화`.
- 마지막에는 어떤 방식을 골라도 새 그래프를 예측하고 설명해야 한다.

점수·배지·레벨은 “몇 번 클릭했나”가 아니라 “새 사례를 설명했나”에 붙인다. game-based learning을 독립적인 치료법처럼 주장하지 않고, retrieval·feedback·spacing을 반복하게 하는 동기·탐색 층으로 사용한다.

**한계와 안전장치**

- 자유도가 너무 높으면 12살 학습자는 핵심 구조를 건너뛰거나 장식만 탐색할 수 있다.
- 선택권이 동기를 높였다는 연구와 학습 성취를 높이지 못했다는 연구가 함께 있으므로, 선택권을 학습 효과의 증거로 보고하지 않는다.
- 픽셀 아트 캐릭터는 실제 event와 연결된 경우에만 의미가 있다. “재미있었다”와 “Graphori를 설명할 수 있다”를 별도 측정한다.

## 5. HTML에 적용할 권장 학습 루프

| 순서 | 학습자에게 보이는 행동 | 가르치는 Graphori 개념 | 적용 근거 | 통과 신호 |
| --- | --- | --- | --- | --- |
| 1. 미션 | “세 팀이 큰 숙제를 빨리 끝내야 한다”를 읽는다. | 전체 목표 | cognitive load, scaffolding | 목표를 한 문장으로 고른다. |
| 2. 예측 | 대시보드와 작업 시작 중 무엇이 먼저인지 고른다. | 기획팀 대시보드의 비동기 시작 | retrieval | 설명을 보기 전에 선택한다. |
| 3. 지도 만들기 | `requires` 카드를 순서대로, 독립 카드를 나란히 놓는다. | 병렬성·의존성·fan-in | retrieval, scaffolding | 새 카드 1개를 올바른 위치에 둔다. |
| 4. 완성 예시 | `learning-success`의 실제 event와 JSON을 한 줄씩 읽는다. | 실행·journal·replay | worked example, dual coding | 각 event가 하는 일을 연결한다. |
| 5. 캐릭터 관찰 | 실제 event가 발생한 팀만 타이핑·읽기·검사 모션을 한다. | dashboard는 liveness/progress/verdict를 구분 | multimedia, cognitive load | 모션을 보고 사건을 추측한다. |
| 6. 설명 피드백 | 오답의 원인·증거·다음 행동을 본다. | `worker_finished` ≠ `verdict pass` | feedback | 같은 개념의 새 문제를 다시 푼다. |
| 7. 선택 탐험 | 원하는 팀·힌트·표현 방식을 고른다. | learner agency | choice research, 단 제한적 적용 | 자유 탐험 뒤 필수 전이 문제로 돌아온다. |
| 8. 간격 재방문 | 다른 모양의 graph를 다음 세션에서 푼다. | 기억 유지·일반화 | spacing, mastery | 힌트 없이 설명하고 새 사례에 적용한다. |
| 9. 완료 보고 | 목표·구조·실제 산출물·검증 상태를 어린이 말로 설명한다. | diff 없이 작업 이해 | retrieval, transfer | “무엇을 왜 어떻게 확인했는가”를 말한다. |

### 5.1 현재 HTML에서 다음에 보강할 부분

현재 [`GRAPHORI_LEARNING_GAME.html`](../../GRAPHORI_LEARNING_GAME.html)은 시작·일시정지·한 사건씩 진행·초기화, event stream, 노드 지도, 실제 산출물 카드와 퀴즈를 이미 갖고 있다. 연구를 반영할 때 우선순위는 다음과 같다.

1. 퀴즈를 단순한 “정답 버튼”에서 `순서 예측 → 짧은 설명 → 새 사례 적용`으로 확장한다.
2. `dashboard pulse`와 작업 event를 분리해, heartbeat를 progress로 오해하지 않게 한다.
3. 각 정답 뒤에 `왜 그런지`와 `어떤 실제 event가 증거인지`를 보여 준다.
4. 첫 실행에는 worked example을 쓰고, 두 번째 실행부터 일부 event를 빈칸으로 만든다.
5. 완료 판정은 클릭 수·애니메이션 종료가 아니라 간격을 둔 회상과 전이 문제로 만든다.

이 문서는 위 변경을 구현했다는 뜻이 아니다. 이번 요청의 범위는 교육학 조사와 근거 저장이다.

## 6. 학습 효과를 확인하는 방법

게임을 만들었다고 학습 효과가 증명되는 것은 아니다. 최소한 다음 세 종류를 따로 측정해야 한다.

### 6.1 즉시 회상

게임 직후 자료를 숨기고 다음을 묻는다.

- `requires`와 병렬 작업의 차이는 무엇인가?
- `worker_finished`와 verifier `pass`는 어떻게 다른가?
- heartbeat가 오면 무엇을 알 수 있고, 무엇은 알 수 없는가?

### 6.2 전이 문제

처음 보지 못한 모양의 graph를 주고 다음을 묻는다.

- 어떤 노드를 동시에 시작할 수 있는가?
- 어느 노드가 fan-in을 기다려야 하는가?
- exit code가 0이어도 왜 검증 대기일 수 있는가?

전이 문제는 게임 장면을 외운 것이 아니라 구조를 이해했는지 보는 우리 측정 가설이다. 위 교육 연구들이 각자 다른 교과 문제에서 recall 또는 transfer를 사용한 점에서 영감을 받았지만, Graphori용으로 직접 검증된 기준은 아니다.

### 6.3 지연 회상

다음 방문 때 캐릭터나 색을 바꾸고, 문장을 줄인 뒤 같은 구조를 다시 설명하게 한다. 즉시 점수보다 지연 회상·새 사례 적용을 더 중요한 결과로 기록한다.

### 6.4 기록하지 않을 것

- 페이지에 머문 시간만으로 학습했다고 판단하지 않는다.
- 캐릭터 클릭 수, 애니메이션 재생 횟수, 배지 개수만으로 성공 처리하지 않는다.
- 사용자가 연구 참여에 동의하지 않았다면 개인별 학습 결과를 외부 서버로 보내지 않는다.

## 7. 연구가 직접 말하지 않는 것

다음 문장들은 이 조사로는 말할 수 없다.

- “Graphori의 네 팀 병렬 실행이 모든 작업을 비약적으로 빠르게 한다.”
- “픽셀 아트 캐릭터가 있으면 12살이 Graphori를 더 잘 배운다.”
- “애니메이션이 글보다 항상 우수하다.”
- “한 번의 정답이면 mastery다.”
- “선택권·점수·배지가 학습 성취를 자동으로 높인다.”
- “대학생·대수·단어 암기 연구의 효과가 Graphori 코드 학습에도 그대로 이전된다.”

이 문서에서 그런 기능을 제안할 때는 모두 **Graphori용 설계 추론 또는 검증해야 할 가설**로 표시했다.

## 8. 다음 개선의 판단 기준

앞으로 HTML을 고칠 때는 다음 순서로 판단한다.

1. 이 변경이 학습자가 직접 기억에서 꺼내거나 새 사례에 적용하게 하는가?
2. 캐릭터·색·움직임이 실제 Graphori event와 연결되는가?
3. 한 화면의 정보량을 줄이면서도 `liveness / progress / verdict`를 구분하게 하는가?
4. 오답 뒤에 다음 생각을 할 수 있는 설명이 있는가?
5. 초보자에게는 발판을 주고, 익숙한 사람에게는 발판을 줄이는가?
6. 한 번의 플레이가 아니라 간격을 둔 재방문을 지원하는가?
7. 클릭·속도·배지 대신 회상·설명·전이를 평가하는가?

이 일곱 질문 중 “아니오”가 많으면 게임을 더 화려하게 만드는 것보다 학습 루프를 먼저 고친다.

## 9. 출처 목록

### 직접 실험·교실 연구

- Karpicke, J. D., Blunt, J. R., & Smith, M. A. (2016). *Retrieval-Based Learning: Positive Effects of Retrieval Practice in Elementary School Children*. [DOI / Frontiers in Psychology](https://doi.org/10.3389/fpsyg.2016.00350)
- Karpicke, J. D., Blunt, J. R., et al. (2014). *Retrieval-based learning: The need for guided retrieval in elementary school children*. [DOI](https://doi.org/10.1016/j.jarmac.2014.07.008)
- Fyfe, E. R., & Rittle-Johnson, B. (2016). *The benefits of computer-generated feedback for mathematics problem solving*. [DOI](https://doi.org/10.1016/j.jecp.2016.03.009) · [ERIC full text](https://files.eric.ed.gov/fulltext/ED566264.pdf)
- Mayer, R. E., & Anderson, R. B. (1991). *Animations Need Narrations: An Experimental Test of a Dual-Coding Hypothesis*. [DOI](https://doi.org/10.1037/0022-0663.83.4.484)
- Sweller, J., & Cooper, G. A. (1985). *The Use of Worked Examples as a Substitute for Problem Solving in Learning Algebra*. [DOI](https://doi.org/10.1207/S1532690XCI0201_3)
- Vlach, H. A., & Sandhofer, C. M. (2012). *Distributing Learning Over Time: The Spacing Effect in Children’s Acquisition and Generalization of Science Concepts*. [DOI](https://doi.org/10.1111/j.1467-8624.2012.01781.x) · [NIH author manuscript](https://escholarship.org/content/qt3hr316z2/qt3hr316z2_noSplash_704ab46ed60e380990f100906a949a0a.pdf)
- Sobel, H. S., Cepeda, N. J., & Kapler, I. V. (2011). *Spacing Effects in Real-World Classroom Vocabulary Learning*. [DOI](https://doi.org/10.1002/acp.1747) · [author manuscript](https://www.yorku.ca/ncepeda/publications/SCK2011.pdf)
- Prusak, K. A., et al. (2004). *The Effects of Choice on the Motivation of Adolescent Girls in Physical Education*. [DOI](https://doi.org/10.1123/jtpe.23.1.19)
- Carter, M. J., et al. (2022). *Exercising choice over feedback schedules during practice is not advantageous for motor learning*. [DOI](https://doi.org/10.3758/s13423-022-02170-5)

### 기초 이론·종합 연구·공식 기관 자료

- Wood, D., Bruner, J. S., & Ross, G. (1976). *The Role of Tutoring in Problem Solving*. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/932126/)
- Sweller, J. (1988). *Cognitive Load During Problem Solving: Effects on Learning*. [DOI](https://doi.org/10.1207/S15516709COG1202_4)
- Kalyuga, S., Ayres, P., Chandler, P., & Sweller, J. (2003). *The Expertise Reversal Effect*. [DOI](https://doi.org/10.1207/S15326985EP3801_4)
- Mayer, R. E., & Moreno, R. (2003). *Nine Ways to Reduce Cognitive Load in Multimedia Learning*. [DOI](https://doi.org/10.1207/S15326985EP3801_6)
- Karpicke, J. D., & Roediger, H. L. (2008). *The Critical Importance of Retrieval for Learning*. [DOI](https://doi.org/10.1126/science.1152408)
- Roediger, H. L., & Karpicke, J. D. (2006). *Test-Enhanced Learning: Taking Memory Tests Improves Long-Term Retention*. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/16507066/)
- Cepeda, N. J., et al. (2006). *Distributed Practice in Verbal Recall Tasks: A Review and Quantitative Synthesis*. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/16719566/)
- Kluger, A. N., & DeNisi, A. (1996). *The Effects of Feedback Interventions on Performance*. [DOI](https://doi.org/10.1037/0033-2909.119.2.254)
- Bloom, B. S. (1968). *Learning for Mastery*. [ERIC record](https://eric.ed.gov/?id=ED053419) · [full text PDF](https://files.eric.ed.gov/fulltext/ED053419.pdf)
- Institute of Education Sciences / NCER. *Computer-Based Guided Retrieval Practice for Elementary School Children*. [Official project page](https://nces.ed.gov/use-work/awards/computer-based-guided-retrieval-practice-elementary-school-children)
- National Academies of Sciences, Engineering, and Medicine. (2018). *How People Learn II: Learners, Contexts, and Cultures*. [Official report](https://doi.org/10.17226/24783)

## 10. 조사 후 남은 검증 과제

1. 실제 12살 또는 그에 가까운 학습자가 Graphori event를 얼마나 회상·전이하는지 사전/직후/지연 검사로 확인한다.
2. 픽셀 아트 모션이 개념 기억을 돕는지, 단지 시선을 끄는지 비교한다.
3. `순서 예측`, `짧은 설명`, `새 graph 적용` 중 어떤 상호작용이 가장 이해하기 쉬운지 usability test를 한다.
4. 힌트 3단계가 실제로 발판의 점진적 제거가 되는지, 아니면 답을 너무 쉽게 알려 주는지 확인한다.
5. Graphori의 실제 multi-session 실행기가 구현될 때까지는 HTML의 팀 장면을 “제품의 현재 CLI가 자동 실행하는 사실”과 혼동하지 않도록 계속 표시한다.
