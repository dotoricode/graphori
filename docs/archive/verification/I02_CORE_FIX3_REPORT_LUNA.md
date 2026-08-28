# I02 portable core revision-3 자동 수정 보고서

작성일: 2026-08-09 (Asia/Seoul)

이번 라운드는 두 최종 검수에서 남은 좁은 문제와 I02 acceptance의 Run 투영을
닫는 작업이었다. 12살도 이해할 수 있게 말하면, 기록 봉투의 주소와 도장을
정확히 확인하고, 다시 하기 화살표가 빙글빙글 돌지 않게 막고, 실행 카드가
시작·그래프 공개·끝남 순서를 기억하도록 고쳤다.

## Finding → 코드 → 테스트 → 결과

### 1. 사건 봉투의 식별자와 지문

- Finding: `actor.role_id`가 빠져도 통과했고, `producer_event_id`가 `None`이며
  `digest`와 `prev_digest`가 `bad`, 정수, 잘못된 hex여도 통과했다.
- 코드: `reducer.py`의 `validate_event_envelope`가 actor의 `role`과 `role_id`,
  producer ID를 모두 non-empty 문자열로 검사한다. 두 digest는
  `sha256:` 접두사 뒤 정확히 64개의 hex 문자만 허용한다. canonical 문서에는
  genesis용 `null` sentinel이 정의되어 있지 않으므로 `seq=0`이어도
  `prev_digest=null`을 허용하지 않는다. 실제 해시 계산과 chain 저장은
  Stage3 범위로 남겼다. `canonical_event` fixture는 role ID와 두 개의
  정확한 sha256 형식 값을 만든다.
- 테스트: `test_canonical_digest_producer_and_actor_identifiers_fail_closed`가
  None, 빈 값, `bad`, 정수, 짧은 digest, 잘못된 hex, role_id 누락을 모두
  거부하고, genesis `seq=0 + prev_digest=None`도 거부하는지 확인한다.
- 결과: 잘못된 봉투는 모두 `StateTransitionError`로 fail-closed 된다.

### 2. rework history 순환과 revision 원자성

- Finding: self-loop만 막혔고 2개 이상 노드가 서로 가리키는 history cycle은
  통과했다. 원본 node가 없을 때 revision 기록이 조용히 생략될 수도 있었다.
- 코드: `compiler.py`의 `validate_graph`가 scheduling edge와 별도로 모든
  `rework_of` edge를 DFS로 검사한다. `RevisionController.record`는 task의
  현재 원본/revision node가 graph에 있는지 먼저 확인하고, 없으면
  `GraphValidationError`를 내며 task·controller·graph를 바꾸지 않는다.
- 테스트: `test_rework_history_long_cycles_and_missing_original_are_rejected_atomically`가
  2-node와 3-node cycle, 없는 원본 revision을 검사하고 예외 뒤 상태가
  그대로인지 확인한다. 기존 정상 3회 revision chain과 4회째 human gate
  테스트도 유지된다.
- 결과: history의 길이 1, 2, 3 이상 cycle과 없는 원본이 모두 거부된다.
  `requires`/`requires_gate` scheduling DAG 규칙은 그대로 유지된다.

### 3. Run과 GraphVersion 최소 projection

- Finding: `run_created`, `graph_published`, `run_terminal`이 봉투만 통과하고
  Run/graph 상태를 보존하지 않았다. `RunState`와 canonical
  `terminal_status` enum도 서로 다른 terminal 값을 가지고 있었다.
- 코드: `StateReducer`가 optional `Run`과 `GraphVersion` projection을 갖고
  세 사건을 순서대로 처리한다. Run ID, Task의 run ID, entity의 run ID와
  graph version을 가능한 범위에서 서로 비교한다. graph version은 뒤로
  갈 수 없고, terminal은 graph 공개 뒤에만 가능하며, terminal 상태를 다시
  다른 값으로 바꿀 수 없다. canonical `TerminalStatus`를 terminal의 권위
  값으로 선택했고 `RunState`는 planned/running lifecycle만 표현한다.
  terminal 때에는 `Run.terminal_status`와 `Run.state`에 같은
  `TerminalStatus`를 저장한다.
- 테스트: `test_run_graph_and_terminal_projection_is_ordered_and_fail_closed`가
  `run_created → graph_published → run_terminal` 정상 경로, terminal 역전,
  graph version regression, run ID 불일치를 검사한다.
  `test_run_projection_rejects_reverse_event_order_and_version_mismatch`가
  terminal 선행과 entity/run ID 및 graph version 불일치를 검사한다.
- 결과: 최소 projection이 run ID, graph version, terminal status를 보존하며
  불법 순서·불일치·version regression은 fail-closed 된다.

## 검증 결과

Windows Python 3.12 환경에서 실행했다.

```text
python -m unittest discover -s tests -v
Ran 19 tests ... OK

python -m compileall -q src tests
exit code 0

git diff --check
exit code 0

python -m pip install . --no-deps --target <temporary Windows directory>
python -c "import graphori_core"
install/import OK
```

기존 15개 테스트를 유지했고 새 회귀 테스트 4개를 추가했다. core import는
stdlib와 같은 패키지 내부 모듈만 사용하며 Orca, adapter, dashboard, journal,
PROCESS를 수정하지 않았다. macOS는 이 Windows host에서 실행하지 않았으므로
판정은 계속 `deferred/unknown`이다.

## 남은 위험

- Stage3 JSONL writer의 실제 hash 계산, monotonic sequence, idempotency,
  replay/dedup, crash-tail quarantine는 아직 구현하지 않았다.
- 실제 Windows process/file adapter와 macOS adapter는 후속 단계다.
- 이벤트별 모든 payload 의미 검증, platform fixture 전체의 완료 정책,
  dashboard와 Orca adapter도 후속 단계다.

따라서 이번 보고서의 Windows portable-core 판정은 통과지만, macOS나 Stage3
기능까지 통과했다고 확대해서 말하지 않는다.
