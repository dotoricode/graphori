# I02 Core Hardening 1 — Claude 독립 검수 보고서

작성일: 2026-08-09
작성자: fresh Claude Sonnet 5, 독립 adversarial 검증자

**독립성 선언**: 이 검수는 `docs/design/I02_HARDENING_CONTRACT_CLAUDE.md`,
`docs/design/I02_HARDENING_CONTRACT_CODEX.md`, `docs/architecture/EVENT_PROTOCOL.md`,
`docs/verification/I02_CORE_HARDENING1_REPORT_LUNA.md`, `src/graphori_core/*.py`,
`tests/test_core.py`만 읽고 작성했다. 같은 라운드에 다른 fresh 검수자가 썼을 수도
있는 동급 검수 문서는 찾아보지도, 읽지도 않았다. `src/`, `tests/`,
`EVENT_PROTOCOL.md`, `docs/PROCESS.md`, dashboard 관련 파일은 전혀 수정하지
않았다 — 이 문서 하나만 새로 썼다.

---

## 0. 12살에게 설명하는 요약

이 프로젝트는 "성공했습니다!" 도장을 아무 때나 찍지 못하게 막는 시스템(Graphori)의
핵심 부품(reducer)을 고치는 중이다. 지난 라운드에 검수자 두 명(Codex, Claude)이
각자 이 부품을 두드려 보고 구멍 네 개를 찾았다:

1. 선수가 완전히 실패했는데도 "경기 성공!" 도장을 찍을 수 있었다.
2. 도장을 찍은 뒤에도 몰래 결과판을 다시 만질 수 있었다.
3. 영수증에 적힌 이름과 실제로 바뀐 카드가 다를 수 있었다.
4. 팀 명단이 없을 때는 아무 이름이나 만들어서 카드를 인정할 수 있었다.

이번에 Luna라는 구현자가 이 네 구멍을 막는 코드를 짰다. 나는 그 코드를 **믿지
않고 직접 두드려 보는 사람**이다. 이번 보고서에서 한 일은 이렇다:

- 기존 시험(테스트) 32개를 Windows에서 다시 돌려서 전부 통과하는지 확인했다.
- 코드가 "컴파일"(문법 오류 없이 읽히는지) 되는지 확인했다.
- 이 코드를 아예 새 깨끗한 컴퓨터(가상환경)에 설치해서, 외부 프로그램 없이
  혼자서도 잘 동작하는지 확인했다.
- 이번에 바뀐 파일들에 눈에 안 보이는 실수(줄바꿈 문자, 끝 공백, 이상한 문자)가
  있는지 확인했다.
- **내가 직접 설계한 37개의 새로운 함정 질문**(기존 시험과 겹치지 않는 것들)을
  코드에 던져서, 네 구멍이 진짜로 막혔는지, 그리고 막다가 실수로 **멀쩡한 경우까지
  잘못 막지는 않았는지**(오탐, false positive) 확인했다.

결론부터 말하면: **네 구멍은 실제로 다 막혔고, 37개의 새 함정 질문 중 단 하나도
실패하지 않았다.** 다만 코드가 "이래야 한다"고 미리 적어 둔 두 계약 문서
(Codex/Claude 초안) 중 하나와 완성된 코드가 살짝 다르게 동작하는 부분을 하나
찾았는데, 이건 "더 위험해진" 방향이 아니라 "더 조심스러워진" 방향이라 안전
문제는 아니다. 아래에 그 이유를 자세히 적었다.

---

## 1. 검증 범위와 읽은 자료

읽은 것 (전체):
- `docs/design/I02_HARDENING_CONTRACT_CLAUDE.md` (지난 라운드 Claude 계약안)
- `docs/design/I02_HARDENING_CONTRACT_CODEX.md` (지난 라운드 Codex 계약안)
- `docs/architecture/EVENT_PROTOCOL.md` (canonical 프로토콜, I02 하드닝 계약 섹션 포함)
- `docs/verification/I02_CORE_HARDENING1_REPORT_LUNA.md` (구현자 보고서)
- `src/graphori_core/models.py`, `compiler.py`, `reducer.py`, `__init__.py` (전체)
- `tests/test_core.py` (32개 테스트 전체)

읽지 않은 것 (의도적, 독립성 유지):
- 이번 라운드에 다른 fresh 검수자가 썼을 수도 있는 동급 `I02_CORE_HARDENING1_REVIEW_*`
  문서. `docs/verification/` 디렉터리 목록에서 존재 여부만 확인했고(파일 목록에
  없었다), 검색도 열람도 하지 않았다.

수정한 것: 없음. 이 보고서 파일 하나만 새로 썼다.

---

## 2. Windows 실행 증거

### 2.1 전체 unittest

```
python -m unittest discover -s tests -v
```
→ **32 tests, OK** (실패/에러 0개). Luna 보고서의 "32 tests PASS" 주장과 일치한다.

### 2.2 compileall

```
python -m compileall -q src tests
```
→ **PASS** (문법/바이트코드 컴파일 오류 없음).

### 2.3 격리 설치 (isolated install/import)

임시 디렉터리에 새 venv를 만들고, 저장소 밖에서 완전히 새 인터프리터로 설치·수입했다:

```
python -m venv <tmp>/i02_isolated_venv
<tmp-venv>/python -m pip install setuptools wheel
<tmp-venv>/python -m pip install --no-deps --no-build-isolation .
<tmp-venv>/python -c "import graphori_core; from graphori_core import StateReducer, ..."
```
→ **PASS**. `graphori_core.__all__`이 48개 심볼을 노출하고, import된 서브모듈은
`graphori_core.models`, `graphori_core.compiler`, `graphori_core.reducer` 셋뿐이다.
소스 4개 파일의 import 문을 AST로 직접 파싱해서 확인한 결과, 사용하는 외부
모듈은 `dataclasses`, `enum`, `typing`, `json`, `re`, `__future__` 뿐이다 — Orca,
OS, 네트워크, provider SDK에 대한 의존이 전혀 없다는 "portable core" 주장이
사실로 확인됐다.

12살 요약: 이 부품을 완전히 새 컴퓨터에 뚝 떼어다 붙여도 혼자 힘으로 잘 돌아간다.

### 2.4 diff hygiene

이 저장소는 아직 **커밋이 하나도 없는 상태**다(`git log` → "does not have any
commits yet", 모든 파일이 `??` untracked). 그래서 `git diff` 기반의 "이전 커밋과
비교" 방식의 hygiene 점검은 애초에 불가능하다 — 비교할 이전 버전이 없다. 대신
다음을 직접 확인했다:

- `src/graphori_core.egg-info/`, `src/graphori_core/__pycache__/`,
  `tests/__pycache__/`가 `.gitignore`에 의해 실제로 무시되는지: `git status
  --ignored`와 `git add -A -n`(dry-run)으로 확인 → **셋 다 무시됨, 실수로
  스테이징될 위험 없음**.
- 이번 하드닝과 관련된 7개 파일(`reducer.py`, `models.py`, `compiler.py`,
  `__init__.py`, `test_core.py`, `EVENT_PROTOCOL.md`,
  `I02_CORE_HARDENING1_REPORT_LUNA.md`)을 바이트 단위로 읽어 BOM, CRLF/lone-CR,
  줄 끝 공백, 탭 문자, 파일 끝 개행 누락을 전부 검사 → **7개 파일 모두 문제
  없음**(UTF-8, LF만 사용, 끝 공백 없음, 탭 없음, 파일 끝 개행 있음).

---

## 3. 네 개 P1 규칙이 실제로 코드에 반영됐는지 확인

| 규칙 | 코드 위치 | 확인 결과 |
|---|---|---|
| R1: succeeded는 "전부 passed"만 인정 | `reducer.py`의 `_require_execution_nodes_passed`, `_execution_nodes` | 구현됨. observer 제외, rework로 대체된 옛 node 제외, 나머지가 하나라도 `PASSED`가 아니면 거부 |
| R2: terminal 이후 모든 event 거부 | `apply()` 최상단 `if self.run is not None and self.run.is_terminal: raise` | 구현됨. dispatch 이전, 모든 event type에 공통 적용 |
| R3: node ID는 `entity.node_id`가 유일한 출처 | `_canonical_node_id` | 구현됨. entity 없으면 거부, payload와 다르면 거부 |
| R4: Run 없는 경로의 node 신원 보증 | `node_status_changed` 분기의 `elif node_id not in self.node_statuses: raise` | 구현됨(단, Claude 계약의 "완전 차단"이 아니라 Codex 계약의 "사전 등록된 ID만 허용" 절충안을 택함 — Luna 보고서가 이 선택을 명시적으로 밝힘) |

R4는 두 계약이 다르게 제안한 유일한 항목이었다(Claude: 아예 다 막기 / Codex:
미리 등록된 map만 허용). Luna는 Codex 쪽을 택했고, 그 이유(사용자가 요청한
호환성 보존)를 보고서에 명시했다. 두 대안 모두 "모르는 이름으로 카드를 즉석에서
만들어내는" 원래 구멍은 막으므로, 이 선택 자체는 안전성 문제가 아니라 API
호환성 절충의 문제다.

---

## 4. 내가 새로 설계한 adversarial probe — 37개, 전부 통과

기존 32개 테스트를 그대로 재사용하지 않고, 겹치지 않는 새 시나리오를 직접
설계해서 별도 스크립트로 실행했다(`python -m unittest`가 아니라 독립 스크립트로
실행 — 기존 테스트 인프라에 기대지 않고 내가 직접 assert를 걸었다). 결과:
**37개 전부 PASS, 0개 FAIL**.

### 4.1 NodeKind 전체와 rework — 8개

- 그래프에 router/worker/verifier/human_gate/platform_gate/observer 6종을 모두
  넣고, platform_gate 하나만 `pending`으로 남겨두면 succeeded가 거부되고, 그
  하나까지 passed로 만들면 통과하는지(observer는 끝까지 pending이어도 무관한지)
  확인 — **통과**.
- observer node를 직접(이벤트 없이) `failed`로 바꿔치기해도 다음 apply에서
  "외부 변경" 감지로 거부되는지 — **통과**.
- rework로 대체된 옛 실패 node가 active 집합에서 실제로 빠지는지, 반대로
  **관계없는** 실패 node에 rework 표시가 없으면 여전히 succeeded를 막는지(즉
  "아무 rework_of나 있으면 다 봐준다"가 아닌지) — **통과**.
- 2단계 rework 체인(원본→revision-1→revision-2)에서 최신 것 하나만 active로
  잡히는지 — **통과**.
- 같은 옛 node를 두 개의 새 node가 동시에 "내가 대체했다"고 주장하면 둘 다
  active로 남는지(코드가 조용히 하나만 인정하는 식으로 데이터를 잃지 않는지) —
  **통과**.
- rework_of 간선이 자기 자신을 가리키는 비정상 입력에서도 크래시 없이 처리되는지 —
  **통과**(해당 node가 자기 자신의 대체 대상이 되어 active에서 빠짐, 예외 없음).

### 4.2 모든 terminal 결과와 근거 — 8개 + 보충 3개

- `rejected`에 빈 리스트(`evidence_ids: []`)를 넣으면 "근거 있음"으로 착각하지
  않고 거부하는지 — **통과**.
- `blocked` node가 **observer**인 경우 그 blocked 상태가 근거로 인정되지
  않는지(활성 node만 근거가 되어야 함) — **통과**.
- 존재하지 않는 문자열(`"victorious"`)을 terminal_status로 보내면 명확히
  거부되고 Run이 계속 열려 있는지 — **통과**.
- payload에 `terminal_status` 키 자체가 없을 때 — **통과**(거부).
- human_gate/platform_gate만 있는 그래프(다른 실행 node 없음)에서 succeeded가
  빈 범위로 거부되는지 여러 조합으로 — **통과**.
- (보충) `failed`/`cancelled`는 다른 node가 `pending`으로 남아 있어도 여전히
  허용되는지(중단 semantics 보존) — **통과**.
- (보충) `inconclusive`는 명시적 reason 없이 **node 상태만으로도** 인정되는지 —
  **통과**.

### 4.3 terminal 이후 모든 event — 1개(포괄적)

- `EVENT_PROTOCOL.md`에 정의된 **22개 canonical event type 전부**를 terminal
  확정 이후에 하나씩 보내서 전부 거부되는지 한 번에 검사(기존 테스트는 9개
  타입만 다룸) — **22개 전부 거부, worker node 상태와 terminal_status는 한 글자도
  안 바뀜**.

### 4.4 entity/payload node ID 조합 — 1개(11칸 표)

기존 테스트가 다루지 않은 칸까지 포함한 11가지 조합(entity 없음/빈 문자열/숫자,
payload 없음/빈 문자열/숫자/일치/불일치 등)을 표로 만들어 각각 확인 — **모두
예상대로 거부/허용됨**. 참고로 "entity는 있고 payload.node_id가 빈 문자열"인
경우는 코드가 "값이 없는 것으로 봐준다"가 아니라 **즉시 거부**한다 — 이는 Codex
계약의 표(빈 문자열=없음으로 취급)보다 더 엄격한 동작이다. 더 엄격한 쪽이므로
안전 방향의 차이이며 결함은 아니다.

### 4.5 Run-less 호환 경로 — 3개

- 사전 등록된 ID는 정상 동작하고, 등록 안 된 `"ghost"`는 거부되며 **거부된 뒤에도
  `node_statuses` map에 유령 키가 생기지 않는지**(딕셔너리 오염 여부) — **통과**.
- Run 없는 reducer에서 `run_terminal`은 `succeeded`뿐 아니라 `failed`까지도 항상
  거부되는지 — **통과**.
- 완전히 빈 reducer(`StateReducer(Task(...))`, run=None)가 `run_created` 이벤트
  하나만으로 부트스트랩될 때, 자동 생성된 Run의 그래프가 **비어 있는 채로
  시작**하는지(이벤트가 몰래 node 목록을 만들어내지 않는지) — **통과**.

### 4.6 public API 경계 안쪽 — 새로 발견한 관찰 1건

- Run 없는 `verdict_recorded`/`platform_verdict_recorded` 호출이 실제로 어떻게
  동작하는지 직접 실행해서 확인했다. **둘 다 "run_created와 graph_published가
  필요하다"는 이유로 거부된다.**

  이건 `I02_HARDENING_CONTRACT_CLAUDE.md` §6.6이 명시적으로 적어 둔 문장("R4는
  `node_status_changed` 분기 하나에만 적용된다 — `verdict_recorded`,
  `platform_verdict_recorded`는 node_id를 참조하지 않으므로 Run 없이도 계속
  동작한다")과 **다르게 동작한다.** 처음엔 이걸 새 결함으로 의심했다.

  그런데 canonical 문서인 `EVENT_PROTOCOL.md`(§6, I02 하드닝 계약 섹션)를 다시
  읽어보니, 거기엔 정반대로 이렇게 명시돼 있다: **"`node_status_changed`,
  `verdict_recorded`, `platform_verdict_recorded`는 실제 `run_created`와
  `graph_published` 뒤에만 허용한다."** 즉 세 이벤트를 동일하게 취급하라고
  canonical 문서가 못 박아 두었다. Luna의 구현은 이 canonical 문서를 정확히
  따른 것이고, Claude의 지난 계약 초안(§6.6)이 canonical 문서로 승격되지 못한
  더 느슨한 제안이었을 뿐이다.

  **결론**: 이건 결함이 아니라, 두 개의 지난 초안 계약 문서 중 하나가 최종
  canonical 문서와 어긋났던 것이고 구현은 canonical 쪽을 올바르게 따랐다. 다만
  "지난 계약 문서에 적힌 호환성 약속과 실제 동작이 다르다"는 사실 자체는
  나중에 그 계약 문서를 읽는 사람이 오해할 수 있으므로, 여기 기록만 해 둔다.

### 4.7 정상 전이와 스냅샷 동기화 — 2개

- worker node가 `pending→ready→assigned→running→awaiting_verification→passed`로
  정상적으로 움직이는 매 단계마다, `reducer.node_statuses`, `run.graph.nodes`,
  publish 시점에 저장한 스냅샷 셋이 항상 일치하는지 — **통과**.
- 이미 `passed`인 node에 같은 `passed` 상태를 다시 보내는("재전송"·idempotent
  replay) 경우 에러 없이 무시되는지(계약 문서가 명시적으로 허용한 유일한
  "재적용" 케이스) — **통과**.

### 4.8 외부 변경 탐지 — 오탐과 정탐 모두 확인 — 4개

- publish 이후 metadata를 잠깐 추가했다가 **완전히 원래대로 되돌린 경우**
  (내용까지 100% 동일), 다음 event가 "외부 변경"으로 오탐되어 거부되지
  **않는지** — **통과**(오탐 없음, 내용 비교이지 변경 이력 비교가 아님을 확인).
- publish 이후 node 라벨을 바꾸면(라벨을 바꾸는 정상 event 자체가 프로토콜에
  없으므로 이건 항상 외부 변경이다) 실제로 거부되는지 — **통과**.
- publish 이후 role 객체를 통째로 바꿔치기해도 거부되는지 — **통과**.
- publish 이후 그래프에서 node 하나를 아예 지워버려도 거부되는지 — **통과**.

### 4.9 lifecycle 순서와 I02/I03 경계 — 5개

- `graph_published`에서 graph_version이 거꾸로 가면(3→2) 거부되는지 — **통과**.
- `seq`가 9 다음에 1이 와도 reducer가 **막지 않는지** — **통과, 의도된 동작**.
  `EVENT_PROTOCOL.md`와 두 계약 문서 모두 "seq 단조 증가는 I03(writer)의
  책임"이라고 명시했으므로, I02가 이를 막지 않는 것이 정답이다. reducer가
  seq 순서를 몰래 검사하기 시작하면 오히려 "두 계층이 다른 규칙을 갖게 된다"는
  계약 문서의 경고(§8, "지나친 확장 목록")를 어기게 된다.
- 같은 `event_id`+`producer_event_id`를 가진 서로 다른 heartbeat 두 개를
  보내도 reducer가 중복 판정을 하지 않고 그냥 둘 다 반영하는지 — **통과, 의도된
  동작**(중복 제거는 I03의 책임).
- 완전히 새(run 없는) reducer가 `run_created`만 적용한 뒤 바로
  `node_status_changed`를 보내면 거부되는지(자동 생성된 빈 그래프에 아직 아무
  node도 없으므로) — **통과**.
- 중간 event(run_created가 아닌 heartbeat 등)에서도 `entity.task_id`가
  reducer의 Task와 다르면 거부되는지(genesis event만 검사하는 게 아닌지) —
  **통과**.

### 4.10 public API — 2개

- `graphori_core.__all__`이 기존 테스트가 실제로 쓰는 모든 심볼을 포함하는지,
  `StateTransitionError`가 여전히 `ValueError`의 하위 클래스라 기존
  `except StateTransitionError`/`except ValueError` 호출자가 계속 동작하는지 —
  **통과**.
- `StateReducer.apply()`가 여전히 자기 자신을 반환해 체이닝이 가능한지,
  독립 함수 `reduce_event()`가 여전히 정상 동작하는지 — **통과**.

---

## 5. 회귀(regression) 여부

37개의 새 probe와 3개의 보충 확인 모두 **기존 32개 테스트를 건드리지 않고**
별도 스크립트로 실행했다. 기존 테스트 스위트 재실행 결과도 여전히 32/32
PASS다. 즉 이번 하드닝이 **기존에 통과하던 어떤 기능도 망가뜨리지 않았다.**

---

## 6. macOS

이번 검수는 지시에 따라 **Windows에서만** 실행했다. macOS는 실행 환경이 없어
`deferred/unknown`이며, macOS에서의 통과를 주장하지 않는다. 코드 자체는 OS
전용 API를 쓰지 않으므로(§2.3의 import 분석 참고) macOS에서도 동일하게 동작할
가능성이 높지만, 이는 추정이지 실행 증거가 아니다.

---

## 7. 발견한 것 — 결함 0건, 관찰 2건

이번 검수에서 **안전성 결함(네 구멍이 다시 열리는 경우)은 발견하지 못했다.**
Luna의 구현은 R1~R4를 모두 코드로 정확히 옮겼고, 내가 던진 37개의 독립
함정에서 단 하나도 뚫리지 않았다.

기록만 해 두는 관찰 2건(둘 다 이번 라운드의 범위 밖이며, 두 계약 문서도 이미
"지금 안 한다"고 명시한 항목들이다):

1. **§4.6**: Claude 계약 초안의 "verdict/platform은 Run 없이도 동작한다"는
   문장이 최종 canonical `EVENT_PROTOCOL.md`와 어긋난다. 구현은 canonical
   문서를 정확히 따랐으므로 결함이 아니지만, 지난 계약 문서를 나중에 참고하는
   사람이 헷갈릴 수 있으니 기록해 둔다.
2. `platform_verdict_recorded`의 `platform` 필드가 여전히
   `payload.get("platform", event.get("platform"))`로 이중 출처를 갖고 있다
   (payload 쪽이 조용히 우선한다). 이건 새로 생긴 문제가 아니라 Claude 계약
   §5.6이 "이번 P1(node_id)에는 포함하지 않고 후속 검토로 남긴다"고 이미
   명시한 항목이며, 실제로 이번 라운드에서 손대지 않은 채 그대로다 — 일관성
   확인용으로만 재확인했다.

---

## 8. 종합 판단

- 지난 라운드에서 두 검수자가 찾은 4개 P1(성공/실패 혼동, terminal 이후 변경
  가능, entity/payload ID 이중 출처, Run 없는 경로의 유령 node)은 코드 레벨에서
  모두 확인 가능하게 막혔다.
- 기존 32개 테스트 전부 통과, compileall 통과, 격리 설치·수입 통과, diff
  hygiene 문제 없음(단, 저장소에 커밋 이력이 아직 없어 커밋 간 비교는
  불가능했고 파일 자체의 바이트 단위 위생만 확인했다).
- 내가 독립적으로 설계한 37개의 새 adversarial probe(모든 NodeKind와 rework,
  모든 terminal 결과와 근거, 22개 event type 전부에 대한 post-terminal 거부,
  entity/payload ID 11칸 조합, Run-less 호환, 빈/observer-only 그래프, lifecycle
  순서, 정상 전이의 스냅샷 동기화, 외부 변경 탐지의 오탐/정탐, public API,
  I02/I03 경계)가 전부 통과했고 회귀도 없었다.
- 발견한 결함은 0건이다. 관찰 2건은 모두 기존에 계약 문서가 이미 범위 밖으로
  명시한 항목이며, 이번 구현이 canonical `EVENT_PROTOCOL.md`를 정확히 따르고
  있음을 재확인하는 수준이다.
- macOS는 지시대로 deferred/unknown 상태로 남겨 두었으며, 통과를 주장하지
  않는다.

VERDICT: APPROVE
