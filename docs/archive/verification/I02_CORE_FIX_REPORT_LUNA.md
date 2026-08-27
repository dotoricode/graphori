# I02 CORE 교차검수 수정 보고서

작성일: 2026-08-09 (Asia/Seoul)  
범위: `src/graphori_core/*`, `tests/*`, `.gitignore`, 본 보고서  
PROCESS 문서는 수정하지 않았으며, stdlib-only portable core와 Windows 실행만 검증했다. macOS 실행은 원 검수 범위대로 `deferred/unknown`이다.

## Finding → 수정 파일/줄 → 회귀 테스트

| 검수 finding | 수정 | 검증 테스트 |
|---|---|---|
| Codex P1-01/P1-02, Claude P1-1/P1-2: usage 누락/unknown을 Critical 또는 known으로 오판 | `src/graphori_core/compiler.py:26-29, 83-128` — 기본 usage를 unknown으로 하고, unknown은 최소 Standard investigation, budget/고위험/외부효과/critical risk는 Critical hard trigger로 유지 | `test_unknown_usage_is_not_zero`, `test_risk_cannot_be_downgraded_and_fast_requires_known_safe_context` |
| Codex P1-03, Claude P0-3: worker와 verifier 및 verifier 간 identity/provider/model/checkout 독립성 누락 | `src/graphori_core/compiler.py:191-203, 205-290` — Fast/Standard/Critical compile-time 사전 검사와 Critical normal/adversarial branch를 추가 | `test_compile_metadata_and_all_independence_constraints`, `test_critical_verifiers_are_independent_and_same_attempt_forbidden` |
| Codex P1-05, Claude P0-1/P1-6: actor 권한, unknown event, malformed payload/status | `src/graphori_core/reducer.py:12-111` — envelope `actor.role`만 사용하고 verifier/human_gate만 허용, worker/router의 pass/approve 거부, unknown/missing/invalid 명시적 reject | `test_reducer_verdict_authority_and_unknown_events` |
| Claude P0-2: node_status_changed를 TaskState로 처리 | `src/graphori_core/reducer.py:52-65`, `src/graphori_core/models.py:62-79` — task/node 상태를 분리하고 canonical NodeState 14종을 보존 | `test_node_and_task_status_are_distinct_and_validated` |
| Codex P1-04/P2-01, Claude P1-3/P1-5: revision node/history, Run/graph version, Gate 최소 엔티티 부재 | `src/graphori_core/models.py:268-291`, `src/graphori_core/compiler.py:320-355` — GraphVersion/Run/Gate를 추가하고 1~3회 새 revision node + `rework_of`, 4회 TaskState.ESCALATED + Human Gate signal 생성 | `test_revision_nodes_history_and_human_gate`, `test_cycle_rejection_excludes_history_edges` |
| Codex P1-06/P2-02, Claude P2-2: canonical enum와 verification metadata 누락 | `src/graphori_core/models.py:122-145`, `src/graphori_core/compiler.py:227-258` — VerificationKind/ProgressState/TerminalStatus를 추가하고 Fast automatic, Standard targeted, Critical fresh_full/adversarial metadata를 명시 | `test_compile_metadata_and_all_independence_constraints`, `test_three_mode_fixtures` |
| Claude P1-4: Human Gate authority pool 독립성 미검사 | `src/graphori_core/compiler.py:287-300` — 최소 2개 authority pool과 execution role과의 독립성을 검사 | `test_compile_metadata_and_all_independence_constraints` |
| Claude P1-7/P2-3: transition 및 platform verdict 검증 부족 | `src/graphori_core/compiler.py:357-399`, `src/graphori_core/reducer.py:87-99` — task/attempt 상태 전이와 pass evidence 필수 검증, failed node 직접 READY 회귀 금지 | `test_transition_guards_and_platform_validation` |
| Codex P2-03/Claude P1-8: 첫 커밋 캐시/빌드 산출물 오염 | `.gitignore:1-5` — `__pycache__/`, `*.pyc`, `build/`, `dist/`, `*.egg-info/` 추가 | 파일 규칙 검토 및 전체 테스트 실행 |
| Claude P2-1: 대소문자 enum alias 중복 | `src/graphori_core/models.py:18-31` — TaskMode/Risk alias 제거, canonical 소문자 직렬화 1개만 유지 | `test_three_mode_fixtures`, enum 목록/직렬화 검토 |

## 실행 결과

Windows PowerShell에서 다음 명령을 실행했다.

```text
python -m unittest discover -s tests -v
```

실제 결과:

```text
Ran 12 tests in 0.003s
OK
```

추가로 `python -m compileall -q src tests`도 종료 코드 0으로 완료했다. 구현에는 Orca/Claude/OpenAI SDK, OS-specific process API, journal/dashboard/adapter가 포함되지 않는다.
