const DEMO_STEPS = [
  {
    after: 0,
    nodes: [{ id: "demo-plan", role: "planner", status: "running", current_task: "작업 지도를 만들고 있습니다." }],
    event: { type: "run_created", node_id: "demo-plan", role: "planner", summary: "기획팀이 작업 지도를 열었습니다." },
  },
  {
    after: 5200,
    nodes: [
      { id: "demo-plan", role: "planner", status: "running", current_task: "팀에 작업을 배정하고 있습니다." },
      { id: "demo-research", role: "researcher", status: "running", current_task: "관련 자료와 근거를 조사합니다." },
    ],
    event: { type: "node_status_changed", node_id: "demo-research", role: "researcher", summary: "정보조사팀이 자료 확인을 시작했습니다." },
  },
  {
    after: 10600,
    nodes: [
      { id: "demo-plan", role: "planner", status: "running", current_task: "진행 상황을 조정하고 있습니다." },
      { id: "demo-research", role: "researcher", status: "passed", current_task: "조사 결과를 정리했습니다.", verdict: "pass" },
      { id: "demo-design", role: "designer", status: "running", current_task: "구현 구조를 설계합니다." },
    ],
    event: { type: "node_status_changed", node_id: "demo-design", role: "designer", summary: "설계팀이 구조를 그리기 시작했습니다." },
  },
  {
    after: 16000,
    nodes: [
      { id: "demo-plan", role: "planner", status: "running", current_task: "병렬 구현을 조정하고 있습니다." },
      { id: "demo-research", role: "researcher", status: "passed", current_task: "조사 결과를 전달했습니다.", verdict: "pass" },
      { id: "demo-design", role: "designer", status: "passed", current_task: "설계가 준비됐습니다.", verdict: "pass" },
      { id: "demo-implement-a", role: "worker", status: "running", current_task: "이벤트 projection을 구현합니다." },
      { id: "demo-implement-b", role: "worker", status: "running", current_task: "환경 상태 표시를 구현합니다." },
    ],
    event: { type: "node_status_changed", node_id: "demo-implement-a", role: "worker", summary: "구현팀 두 명이 서로 다른 작업을 시작했습니다." },
  },
  {
    after: 22400,
    nodes: [
      { id: "demo-plan", role: "planner", status: "running", current_task: "검증 결과를 기다리고 있습니다." },
      { id: "demo-research", role: "researcher", status: "passed", current_task: "조사 완료", verdict: "pass" },
      { id: "demo-design", role: "designer", status: "passed", current_task: "설계 완료", verdict: "pass" },
      { id: "demo-implement-a", role: "worker", status: "awaiting_verification", current_task: "구현 결과를 제출했습니다." },
      { id: "demo-implement-b", role: "worker", status: "awaiting_verification", current_task: "환경 상호작용을 제출했습니다." },
      { id: "demo-verify", role: "verifier", status: "running", current_task: "실제 동작과 근거를 검증합니다." },
    ],
    event: { type: "verification_started", node_id: "demo-verify", role: "verifier", summary: "검증팀이 결과 검증을 시작했습니다." },
  },
  {
    after: 28800,
    terminal_status: "succeeded",
    nodes: [
      { id: "demo-plan", role: "planner", status: "passed", current_task: "모든 팀의 작업이 끝났습니다.", verdict: "pass" },
      { id: "demo-research", role: "researcher", status: "passed", current_task: "조사 완료", verdict: "pass" },
      { id: "demo-design", role: "designer", status: "passed", current_task: "설계 완료", verdict: "pass" },
      { id: "demo-implement-a", role: "worker", status: "passed", current_task: "구현 완료", verdict: "pass" },
      { id: "demo-implement-b", role: "worker", status: "passed", current_task: "환경 상호작용 완료", verdict: "pass" },
      { id: "demo-verify", role: "verifier", status: "passed", current_task: "검증 통과", verdict: "pass" },
    ],
    event: { type: "verdict_recorded", node_id: "demo-verify", role: "verifier", summary: "검증팀이 작업 결과를 승인했습니다." },
  },
];

function demoSnapshot(step, sequence) {
  const now = new Date().toISOString();
  const events = DEMO_STEPS.slice(0, sequence + 1).map((entry, index) => ({
    ...entry.event,
    seq: index + 1,
    updatedAt: now,
    producer: { role: entry.event.role, role_id: `${entry.event.role}-demo` },
    evidence_ids: entry.event.type === "verdict_recorded" ? ["demo-evidence-1"] : [],
  }));
  const completed = step.nodes.filter((node) => node.status === "passed" && node.verdict === "pass").length;
  return {
    schema_version: 2,
    run_id: "demo-office",
    state: step.terminal_status ? "completed" : "active",
    terminal_status: step.terminal_status || null,
    connection: { status: "fresh" },
    liveness: { status: "heartbeat_recent", age_seconds: 0 },
    heartbeat: { status: "heartbeat_recent", updatedAt: now, age_seconds: 0 },
    progress: { completed, required: step.nodes.length, percent: Math.round(completed * 100 / step.nodes.length) },
    nodes: step.nodes,
    recentEvents: events,
    lastEvent: events.at(-1),
    updatedAt: now,
  };
}

class DemoOfficeSequence {
  constructor(onSnapshot) {
    this.onSnapshot = onSnapshot;
    this.timers = [];
  }

  start(fixedStep = null) {
    this.stop();
    if (Number.isInteger(fixedStep)) {
      const index = Math.max(0, Math.min(DEMO_STEPS.length - 1, fixedStep));
      this.onSnapshot(demoSnapshot(DEMO_STEPS[index], index));
      return;
    }
    DEMO_STEPS.forEach((step, index) => {
      const timer = window.setTimeout(() => this.onSnapshot(demoSnapshot(step, index)), step.after);
      this.timers.push(timer);
    });
  }

  stop() {
    this.timers.forEach((timer) => window.clearTimeout(timer));
    this.timers = [];
  }
}

export { DEMO_STEPS, DemoOfficeSequence, demoSnapshot };
