# ADR 0001: portable core와 선택적 Orca adapter

- 상태: accepted (canonical)
- 날짜: 2026-08-09

## 1. 12살도 이해하는 설명

Graphori의 규칙 공책은 어디서나 읽을 수 있어야 한다. Orca는 편한 우편함을
추가하지만 공책의 주인이 아니다. Orca가 없어도 일반 터미널에서 카드·기록·검사는
계속 동작한다.

## 2. 결정

Run/Task/Attempt, graph reducer, event protocol, evidence, usage, verdict와 dashboard
view model은 Python portable core가 소유한다. Orca와 generic terminal은 ports를
구현하는 adapter다. Core module은 `orca` 명령이나 OS-specific process API를 직접
호출하지 않는다.

## 3. 선택 이유

이전 이식성 조사는 Orca의 orchestration이 RPC/앱 상태에 의존하지만, 본질은 파일·
프로세스·heartbeat·결과 기록이라고 관찰했다. 보존된 Doctori ADR 0005도 조정자는
직접 구현하지 않고 위임·종합만 하도록 했다. 그러므로 adapter 교체가 core의
판정·감사 독립성을 흔들지 않아야 한다.

## 기술 부록

필수 ports는 `EventStore`, `ProcessSupervisor`, `AgentRunner`, `Clock`,
`EvidenceStore`, `Notifier`, `HumanGate`, `UsageProvider`다. 수락 기준은 Orca 없이
core CLI replay가 동작하고, 이후 Orca 연결 결과가 같은 projection을 만드는 것이다.
근거: [`GRAPHORI_ARCHITECTURE.md`](../architecture/GRAPHORI_ARCHITECTURE.md),
[`PORTABILITY_CONTRACT.md`](../architecture/PORTABILITY_CONTRACT.md),
[`MANIFEST.md`](../archive/evidence/doctori/MANIFEST.md).
