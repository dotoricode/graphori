# PR11C Orca 독립성 감사

## 분류

| 경로 | 판정 | 근거 |
| --- | --- | --- |
| Core (`graphori_core`) | 필수 Orca import 없음 | core는 ports, journal, reducer, planner와 Direct-neutral lifecycle value object만 가진다. `graphori_adapters.orca`를 import하지 않는다. |
| Product entry (`product_cli`) | 필수 Orca dependency 없음 | `graphori plan/run/resume/doctor`는 Codex, Claude Code, generic-process만 조합한다. |
| Skill (`graphori/SKILL.md`) | Orca Skill 불필요 | Graphori Skill은 현재 coordinator와 Direct Codex/Claude 계약만 기술한다. |
| Direct | Orca 불필요 | RoutedExecutionAdapter는 provider adapter mapping만 사용하며 Orca adapter를 등록하지 않는다. |
| Optional adapter | 격리됨 | `graphori_adapters.orca`만 Orca executable/protocol을 참조한다. |
| 역사/측정 문서 | 비실행 참조 | architecture/research의 Orca 언급은 호환성·측정 기록이며 runtime import 경로가 아니다. |

## PR11C 운영 규칙

`resume`은 sidecar와 canonical journal을 읽고 plan digest, workspace, process command,
pinned Skill digest를 모두 확인한다. 하나라도 불명확하면 dispatch 전에 실패한다. replay 중
in-flight attempt는 outcome_unknown으로 닫히며, terminal 및 unknown 상태는 새 dispatch 대상이
아니다. 이 과정은 journal migration이나 rewrite를 하지 않는다.

`doctor`는 `ensure_run_dirs` 또는 journal writer를 호출하지 않는다. 그래서 Orca binary/Skill이
없는 Codex-only, Claude-only, provider 없음 환경에서도 provider 조합과 local journal/schema/
skills.lock 상태를 읽기 전용으로 설명할 수 있다.

## Dogfooding and coordinator audit

- run: `run-pr11c-dogfood`
- graph: coordinator → implementation → independent verification
- route: Direct Codex, `gpt-5.6-terra`, medium
- skills: none
- elapsed: 9m 24s
- provider input usage: 2.22M total, 2.10M cached, 118.5K uncached
- Graphori result: implementation and generic verification passed

The dogfood implementation exposed two gaps during coordinator review. First,
`resume` advanced only one scheduling wave; it now continues through every newly
ready descendant until terminal state, a gate, or no safe dispatch remains, and
always releases writer ownership. Second, `doctor` initially treated any
non-terminal journal as resumable. It now consults the canonical projection and
classifies blocked, failed, cancelled, and outcome-unknown histories as requiring
review.

The no-Orca acceptance uses isolated subprocesses and covers import, plan, fake
Direct execution, journal replay, and dashboard projection. Static checks reject
imports of `graphori_adapters.orca` from `graphori_core`; product and Skill entry
paths have no Orca Skill or executable requirement.

## Conclusion

**INDEPENDENT** — Graphori Core, product entry, Skill entry, Direct Codex, Direct
Claude, replay, dashboard projection, and doctor do not require Orca. Orca remains
an optional adapter package and historical/telemetry vocabulary only.
