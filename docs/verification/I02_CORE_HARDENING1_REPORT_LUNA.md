# I02 Core Hardening 1 보고서 (Luna)

작성일: 2026-08-09

## 먼저 말할 것

이번 작업은 “성공” 카드를 너무 쉽게 붙이지 못하게 하는 안전 작업이다. 나는
이번 결과를 APPROVE라고 주장하지 않는다. 이 문서는 두 설계 문서를 읽고 만든
구현 기록이며, fresh Codex/Claude dual review를 기다린다.

## 처음 읽은 계약과 공통 결정

먼저 `I02_HARDENING_CONTRACT_CODEX.md` 227줄과
`I02_HARDENING_CONTRACT_CLAUDE.md` 483줄을 처음부터 끝까지 읽었다. 두 문서가
만난 규칙과 충돌을 다음처럼 정리했다.

| 주제 | Codex 문서 | Claude 문서 | 이번 선택과 이유 |
|---|---|---|---|
| succeeded | observer를 빼고 실행 범위를 닫아야 함 | active 실행 node가 하나 이상이고 모두 passed여야 함 | 더 닫힌 Claude 규칙인 “최소 1개 + 모두 passed”를 선택 |
| 다른 terminal | failed/cancelled는 기존 중단을 유지하고 나머지는 근거 필요 | 다섯 상태 모두 중단 의미이며 succeeded 판정에는 쓰지 않음 | abort 의미는 유지하고 rejected/blocked/inconclusive에 근거를 요구 |
| terminal 뒤 event | 모든 projection 변경 거부 | apply 처음에서 모든 event 거부 | 두 문서 공통대로 fail-closed 전역 guard 적용 |
| node ID | entity가 canonical, payload는 같을 때만 보조 | entity가 유일한 출처, 충돌 거부 | API 변경이 작고 혼동이 없는 entity 우선 규칙 적용 |
| Run 없는 경로 | 미리 등록한 map ID만 허용 | 새 node inventory를 만들지 말고 엄격히 제한 | 사용자 요청이 명시한 호환성을 지키되 pre-registered ID만 허용; Run lifecycle/success projection은 금지 |
| 빈/observer-only graph | succeeded 거부 | 최소 실행 node를 명시 | 둘 다 거부 |
| topology | publish snapshot과 비교 | 외부 변경을 잡고 reducer event로만 state 동기화 | topology와 published state snapshot을 모두 확인 |
| verdict-node 연결 | P2로 미루고 작은 API 유지 | P2 schema 확장 제안 | 이번 공통 안전 계약에 없는 schema 확장은 하지 않음 |
| seq/hash | 실제 chain은 I03 writer 책임 | reducer가 seq/hash 책임을 대신하면 안 됨 | I02는 envelope 모양만 확인하고 monotonic seq/hash writer는 I03로 문서화 |

마지막 두 줄의 선택은 “더 fail-closed이고 API 변경이 작은 쪽”이라는 지시를
따랐다. 특히 verdict에 새 `node_id` 필드를 추가하지 않아 기존 호출 모양을
보존했다.

## 구현한 것

`src/graphori_core/reducer.py`에 다음 안전문을 추가했다.

1. `succeeded`는 observer와 rework로 교체된 과거 node를 빼고 active 실행 node를
   계산한다. active node가 0개이거나 하나라도 `passed`가 아니면 Run을 바꾸지
   않고 거부한다.
2. `failed`/`cancelled`는 기존 abort 동작을 유지한다. `rejected`는 reason 또는
   evidence, `blocked`는 blocked node 또는 blocking reason, `inconclusive`는
   inconclusive node 또는 reason이 없으면 거부한다.
3. terminal Run을 본 뒤에는 `run_terminal`을 포함한 모든 event를 즉시 거부한다.
4. `node_status_changed`는 `entity.node_id`만 사용한다. entity가 없거나 payload에만
   있거나 두 ID가 다르면 거부한다. graph Run은 graph에 없는 node를 거부한다.
5. Run 없는 호환 reducer는 생성 때 넣은 `node_statuses` ID만 바꾼다. ghost ID가
   map에 자동으로 생기지 않으며, 이 경로는 Run을 만들거나 success projection을
   만들 수 없다.
6. node/verdict/platform event는 실제 `run_created`와 `graph_published` 뒤에만
   처리한다. node/edge topology event는 reducer가 만들지 않는다.
7. graph publish 때 node/edge 구조와 node state를 snapshot한다. publish 뒤 외부에서
   topology나 state를 직접 바꾸면 다음 event가 거부된다. 정상 state 변경 뒤에는
   reducer가 snapshot을 갱신한다.

`docs/architecture/EVENT_PROTOCOL.md`에도 terminal 계약표, I02/I03 책임 경계를
추가했다. PROCESS.md와 dashboard 파일은 건드리지 않았다.

## 검증 결과

Windows에서 다음을 실행했고 모두 통과했다.

- `python -m unittest discover -s tests -v`: 32 tests PASS
- adversarial sub-probe: 48개 이상 (실패 상태 10개, 빈/observer-only 2개,
  terminal 이후 event 9개, node ID 6개, lifecycle 순서 7개, snapshot 3개,
  terminal evidence 8개, rework 1개 이상)
- `python -m compileall -q src tests`: PASS
- 격리 target에 `pip install --no-deps --no-build-isolation .` 후
  `import graphori_core`: PASS
- `git diff --no-index --check`로 이번 허용 파일의 공백/patch 오류 확인: PASS

macOS 검증은 이 작업 범위에서 deferred/unknown이다. 실행하지 않았으므로
macOS 통과를 주장하지 않는다.

## 남은 위험

- I03 single writer의 실제 seq 단조 증가, event 중복/충돌, digest chain 계산은
  아직 이 reducer가 보장하지 않는다. 그것은 문서대로 I03 책임이다.
- `verdict_recorded`와 특정 verifier/human_gate node의 연결은 이번 작은 API
  pass에서 새 schema를 추가하지 않았다. 별도 합의가 필요한 P2 항목이다.
- 외부 코드가 graph 객체를 직접 바꾸면 그 변경은 이미 메모리에 들어가지만,
  reducer는 다음 event에서 fail-closed로 멈춘다. 완전한 불변 Graph API는 후속
  작업이다.

따라서 현재 결론은 “계약 구현과 검증 명령은 완료, fresh dual review 대기”이며,
APPROVE 판정은 하지 않는다.
