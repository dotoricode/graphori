# Graphori dashboard contract

> 상태: canonical, 구현 완료

## Live Office v2 canonical projection

The server returns the same `CanonicalRunProjection` used by Engine snapshot,
`graphori status`, and `graphori replay`. `DashboardStore` does not reduce events
or decide Node, verdict, progress, gate, or team state. It adds only transient
connection age, which is excluded from `projection_digest`. Snapshot schema
version 3 includes the published plan, five logical teams, Nodes, edges,
attempts, actors, assignments, gates, route health, timing, execution, and
verification.

The browser owns only presentation state:

```text
journal → StateReducer → CanonicalRunProjection
                       ├→ graphori status/replay
                       └→ Dashboard snapshot/SSE
                                      → actor assignment
                         → office action
                         → pathfinding + renderer
```

Spatial truth is stored in `docs/dashboard/world/office-map.json`. Every route uses the navigation graph, every work action terminates at an interaction anchor, and room transitions pass through declared doors. Random screen-coordinate movement is outside the contract.

The default viewport has no KPI cards. Liveness, last event, and verified progress each have one persistent location. Room, actor, journal, payload, and evidence details are visible only on demand.

## 1. 12살도 이해하는 설명

대시보드는 게임판처럼 보이지만 점수를 마음대로 올리는 게임이 아니다. 캐릭터가
자리를 옮기는 것은 실제 배정·상태·progress 사건이 있을 때뿐이고, 검사가 끝나야 판정
배지가 붙는다. 연결이 끊기면 캐릭터를 멈추고 `stale`이라고 보여 준다.

사용자는 현재 퀘스트와 결정 게이트를 보고, 필요한 질문에 답하거나 승인한다.
빨강/초록 색만 보지 않아도 되도록 글자와 아이콘을 함께 쓴다. 그림은 직접 만든
original pixel art만 사용하며 외부 게임 asset을 복사하지 않는다.

## 2. 전송: SSE snapshot/replay

기본 transport는 HTTP Server-Sent Events다. 연결 직후 서버는 `snapshot` 하나를
보낸다. 이후 `Last-Event-ID` 또는 `since_seq`가 있으면 journal projection에서
누락된 replay를 순서대로 보내고, 그 뒤 live event를 보낸다.

```text
GET /runs/{run_id}/events?since_seq=91
event: snapshot
id: 120
data: {"schema_version":3,"run_id":"...","projection_digest":"...","snapshot_seq":120,"nodes":[...]}

event: event
id: 121
data: {"type":"progress_reported", ...}
```

snapshot은 연결된 시점의 최신 projection이고, replay는 반드시 journal `seq` 오름차순이다.
gap이나 hash mismatch면 서버는 `replay_gap`을 보내고 새 snapshot을 요구한다.
WebSocket은 양방향 상호작용이 실제 병목으로 측정된 뒤 선택 adapter로 추가한다.

## 3. Heartbeat와 freshness

화면은 세 시계를 따로 보여 준다.

| 신호 | 계산 | 화면 문장 |
|---|---|---|
| liveness | 마지막 heartbeat/연결 | “연결됨”, “stale”, “죽었는지 모름” |
| progress | 실제 checkpoint/digest 변화 | “2개 산출물 갱신” |
| verdict | verifier/gate 사건 | “검사 대기”, “PASS”, “REVISE” |

freshness threshold는 설정값이며 표준 사실로 고정하지 않는다. 기본 표시 규칙은
heartbeat가 임계값을 넘으면 `stale`, 두 번 연속 누락이면 `dead/unknown` 후보로
보이고, reconcile 전에는 실패 배지를 붙이지 않는 것이다. reconnect + snapshot/replay
검증이 끝나면 확정 상태로 복귀한다. 캐릭터는 stale 동안 freeze한다.

## 4. Progress basis와 sprite motion

하단 progress에는 반드시 basis를 함께 쓴다: `completed_nodes / terminal_required_nodes`,
예: `4/9 nodes (44%, basis=required_nodes)`. 작업 수가 바뀌면 graph version과
분모를 함께 바꾼다. heartbeat 수, 연결 시간, 화면 frame 수는 progress basis가
아니다.

실제 사건별 모션 규칙:

| 사건 | 모션 | 금지 |
|---|---|---|
| `heartbeat` | 캐릭터 이동 없음; HUD freshness만 갱신 | 걷기·완료 상승 |
| `progress_reported` + 새 digest/checkpoint | 해당 node로 한 칸 이동 | fake loop |
| `worker_finished` | 작업대에 도착, 검증 대기 | PASS 배지 |
| `verdict_recorded(pass)` | 검증자에게서 PASS stamp | worker가 스스로 stamp |
| `verdict_recorded(revise)` | 새 revision 퀘스트 생성, 옛 node 고정 | 같은 node로 되돌아가는 cycle |
| `stale_marked` | sprite freeze + stale 아이콘 | 계속 걷기 |
| `gate_created` | 잠긴 gate 표시 | optimistic approve |

각 위치 이동은 node의 이전 semantic state와 새 state의 차이에 묶고 한 상태 전이에
한 번만 재생한다. 팀장과 팀원은 각자 독립적인 상태 머신을 가지며, 한 사람의 이동이
다른 사람을 함께 끌고 가지 않는다. 대기 캐릭터의 random roam과 sleep은 금지한다. 환경의 모니터·LED처럼
데이터 의미가 없는 ambient animation은 캐릭터 상태와 분리하며 진행률을 바꾸지 않는다.

## 4.1 공간·팀 계약

- 캐릭터는 `walkable`과 navigation graph로 정의된 경로에서만 이동한다.
- 벽과 가구는 `blocked` geometry를 갖고, 방 사이 이동은 `doors`를 통과한다.
- 모든 업무 행동은 `anchors`가 지정한 interaction에서 끝난다.
- 각 팀은 Lead 한 명과 Member 한 명 이상을 가진다. 구현팀은 두 명의 Member를 가진다.
- Lead는 팀 상태와 조정을 대표하고 실제 session으로 표시되지 않는다.
- Member는 실제 node가 있을 때만 작업 상태가 된다. node가 없으면 “배정된 실제 노드 없음”으로 표시한다.
- Member 수보다 node가 많으면 초과 수를 team inspector에서 `N more`로 요약한다.

## 5. 사용자 quest와 gate

퀘스트 카드에는 `quest_id`, 목적, 현재 node, mode, risk tags, progress basis,
last evidence, platform verdict, owner role, next action을 보여 준다. Gate 카드에는
질문, 영향 범위, 선택지(`approve`, `scope_reduce`, `request_evidence`, `stop`),
필수 evidence, 승인자 독립성, 만료 시 동작을 명시한다.

Gate timeout은 approve가 아니다. 권한 없는 클릭은 거절하고, 결정 후에는
`gate_resolved` event와 actor/evidence를 남긴다. 사용자는 `revise #2/3`, 남은
retry budget, WIP queue와 stale worker를 볼 수 있어야 한다.

## 6. 접근성·원본 픽셀 아트

- 색 외에 텍스트·아이콘·패턴을 사용한다: `PASS`, `REVISE`, `STALE`를 직접 쓴다.
- reduced-motion 설정에서는 sprite 이동 대신 위치 변경·텍스트 로그로 표시한다.
- keyboard focus, screen-reader label, 충분한 대비, 44px 이상 터치 target을 acceptance로 둔다.
- 모든 sprite/background/tileset은 저장소에서 직접 제작한 original pixel art만 쓴다.
  외부 게임 sprite, 상표 asset, AI 생성 결과를 원본인 것처럼 포함하지 않는다.
- 표시 중인 asset에는 license/author/source metadata를 둔다.

## 7. 기술 부록 A. View model

```json
{
  "schema_version": 3,
  "run_id": "run_1",
  "projection_digest": "sha256:...",
  "plan_digest": "sha256:...",
  "graph_digest": "sha256:...",
  "snapshot_seq": 121,
  "connection": {"status":"fresh", "last_event_id":"121"},
  "progress": {"completed":4,"required":9,"percent":44,"basis":"required_nodes"},
  "teams": [{"team_id":"planning","status":"active","agent_count":0}],
  "nodes": [{"node_id":"n1","team_id":"implementation","status":"awaiting_verification",
             "execution":{"status":"succeeded"},
             "verification":{"status":"pending"}}],
  "edges": [{"from":"n1","to":"v1","type":"verifies"}],
  "gates": [],
  "verification": {"platform_verdicts":{"windows":"pass"}}
}
```

`percent`는 canonical projection builder가 계산한 값이다. API client가 임의의 분모로 다시
계산하지 않는다.

## 8. 멈춤과 완료를 구분하는 snapshot 메타데이터

snapshot은 journal의 마지막 사건에서 `updatedAt`과 `lastEvent`를 만든다. Run
`status`는 reducer의 terminal state, open Gate, blocked/unknown Node에서 결정한다.
마지막 heartbeat의 age와 transport freshness만 Dashboard adapter가 현재 시각으로
계산하며 canonical digest에는 포함하지 않는다.

`progress.percent`는 계속 verifier verdict와 passed terminal node만 센다. 따라서
heartbeat나 입력 수락만으로 100%가 되지 않는다. `scripts/publish_snapshot.py`는
이 projection을 임시 파일에 쓴 뒤 원자적으로 교체해 재사용 가능한 snapshot을
만든다.

## 기술 부록 B. 검증 시나리오

1. heartbeat만 10회 보내도 progress와 percent가 변하지 않고 idle pulse만 난다.
2. 새 작업 상태가 오면 정의된 anchor route를 한 번 이동하고 replay 시 같은 위치 이동이 중복되지 않는다.
3. stale 뒤 reconnect snapshot/replay가 맞으면 freeze가 풀리고, gap이면 freeze를 유지한다.
4. `revise`는 새 revision quest를 만들며 같은 node cycle이 없다.
5. Windows `pass` + macOS `deferred`가 partial scope로 화면에 함께 나온다.

## 기술 부록 C. 근거 연결

세 신호·SSE·snapshot/replay·pixel art 제안은 [`LIVE_GAME_DASHBOARD.md`](../research/LIVE_GAME_DASHBOARD.md)를
기초로 한다. 연결·재생은 [`EVENT_PROTOCOL.md`](EVENT_PROTOCOL.md)의 event seq에
종속된다. F01 최신 Windows verdict와 macOS deferred는 [`F01_WINDOWS_FINAL_APPROVAL.md`](../evidence/doctori/verification/F01_WINDOWS_FINAL_APPROVAL.md),
원문 digest 목록은 [`MANIFEST.md`](../evidence/doctori/MANIFEST.md)다.
