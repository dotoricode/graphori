# I02 portable core revision-2 수정 보고서

작성일: 2026-08-09 (Asia/Seoul)

이 보고서는 두 재검수 보고서에서 찾은 문제를 실제 코드와 회귀 테스트로 다시 닫은 기록이다. 쉽게 말해, 이미 끝난 작업을 몰래 다시 살아나게 하거나, 증거 없이 합격시키거나, 서로 같은 작업 환경을 다른 검사자처럼 꾸미는 길을 막았다.

## Finding → 수정 위치 → 회귀 테스트

| Finding | 수정 위치 | 회귀 테스트 |
|---|---|---|
| 끝난 Node가 `running`/`ready`로 되돌아감 | `src/graphori_core/compiler.py`의 `NODE_TRANSITIONS`, `transition_node`; `reducer.py`의 `node_status_changed` | `test_node_state_table_and_terminal_immutability`, `test_reducer_node_status_uses_transition_guard` |
| `verdict_recorded`가 증거 없이 합격할 수 있음 | `src/graphori_core/reducer.py`의 verdict 검증 | 빈 배열, 문자열, 빈 문자열, `None`, 잘못된 actor 역할을 모두 거부하는 `test_verdict_authority_evidence_and_actor_fail_closed` |
| payload의 `actor_role`로 권한을 위조할 수 있음 | reducer는 `event.actor.role`만 읽음 | 같은 테스트의 payload 위조 공격 |
| 플랫폼 결과가 같은 플랫폼의 다른 fixture/snapshot을 덮어씀 | `PlatformVerdict`에 `fixture_id`/`snapshot_id` 추가; reducer가 플랫폼+단위 키로 보존 | `test_platform_verdict_preserves_fixture_snapshot_units` |
| identity만 바꾸거나 provider/model/checkout/session/worktree 중 일부만 바꿔 독립처럼 보임 | `compiler.py`의 단일 `_independent` 함수와 Router/Human Gate 검사 | `test_independence_rejects_partial_identity_and_resource_bypasses`, `test_critical_standard_and_gate_independence` |
| Critical 검사자끼리 같은 provider+model을 사용함 | Critical verifier와 Human Gate 비교에 provider+model 규칙 추가 | `test_critical_standard_and_gate_independence` |
| verifier fan-in의 `Node.role`에 문자열이 들어감 | `compiler.py`에서 `fan_in`은 metadata로만 표현하고 `role=None` 유지 | `test_compile_metadata_and_verification_edges` |
| revision-1이 원본 대신 자기 자신을 가리키고, history self-loop가 허용됨 | `RevisionController.record`가 새 revision을 만들기 전에 이전 노드를 저장; `validate_graph`가 모든 history self-loop/누락 대상을 거부 | `test_revision_history_is_chain_and_fourth_revise_escalates`, `test_validate_graph_requires_verification_path_and_history_rules` |
| 네 번째 revise가 새 작업을 더 만들 수 있음 | 네 번째부터 revision node 대신 Human Gate signal/escalation 생성 | `test_revision_history_is_chain_and_fourth_revise_escalates` |
| Fast가 usage/안전 정보가 빠져도 선택됨 | `RiskInput`에 `local_only`, `reversible`을 tri-state로 추가; Fast는 known/low/uncertainty=0/no external/local_only/reversible을 모두 요구 | `test_fast_boundaries_are_fail_closed`, `test_three_mode_fixtures_require_explicit_fast_metadata` |
| 요청한 mode가 Critical 위험을 낮춤 | `compile_topology`가 Critical 결과를 항상 Critical로 고정 | `test_fast_boundaries_are_fail_closed` |
| event envelope가 빠진 값/잘못된 타입/음수 seq를 통과시킴 | `validate_event_envelope`, `canonical_event`; schema/id/run/graph/seq/timestamp/actor/entity/payload/digest를 fail-closed 검사 | `test_canonical_event_envelope_rejects_missing_bad_and_negative_fields` |
| 문서에 없는 `task_status_changed`가 이벤트처럼 남음 | `EVENT_TYPES`를 `EVENT_PROTOCOL.md` 목록에 맞춤 | `test_unknown_event_and_noncanonical_task_status_are_rejected` |
| worker→verifier 검증 관계가 단순 requires로만 보임 | graph에 scheduling `REQUIRES`와 별도의 canonical `VERIFIES` 관계를 함께 기록하고 `validate_graph`가 검증 경로 확인 | `test_compile_metadata_and_verification_edges`, `test_validate_graph_requires_verification_path_and_history_rules` |

## 실행 결과

Windows PowerShell에서 다음을 실행했다.

```text
python -m unittest discover -s tests -v
Ran 15 tests ... OK

python -m compileall -q src tests
exit code 0

git diff --check
exit code 0

git check-ignore -v src/graphori_core/__pycache__/models.cpython-*.pyc tests/__pycache__/test_core.cpython-*.pyc
.gitignore:1:__pycache__/

python -m pip install . --no-deps --target <Windows Temp>
python -c "import graphori_core"
graphori_core
```

패키지를 임시 대상 폴더에 설치한 뒤 `import graphori_core`가 성공했다. core에는 Python 표준 라이브러리와 같은 패키지 내부 모듈만 있고 Orca/Claude/OpenAI SDK, subprocess, OS 전용 API를 추가하지 않았다. macOS 실행은 이 Windows 작업 환경에서 할 수 없으므로 `deferred/unknown`이다.

## 남은 위험과 범위 밖 항목

- Stage3 journal, dashboard, PROCESS.md, adapters는 수정하지 않았다.
- Run 전체 journal/reducer, WIP/fan-in queue, Human Gate takeover/heartbeat 같은 후속 단계 기능은 아직 이 I02 범위의 구현이 아니다.
- canonical 문서의 macOS 실제 실행 증거는 없으며 `deferred/unknown`으로 남긴다.
- event reducer는 canonical persisted envelope를 받도록 엄격해졌다. 새 producer는 `canonical_event`와 같은 필수 envelope를 만들어야 한다.
