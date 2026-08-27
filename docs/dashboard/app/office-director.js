const TEAM_BY_ROLE = new Map([
  ["planner", "plan"],
  ["planning", "plan"],
  ["router", "plan"],
  ["research", "research"],
  ["researcher", "research"],
  ["design", "design"],
  ["designer", "design"],
  ["worker", "implement"],
  ["implementation", "implement"],
  ["implementer", "implement"],
  ["verifier", "verify"],
  ["verification", "verify"],
  ["reviewer", "verify"],
]);

const VISUAL_TEAM_BY_ID = new Map([
  ["planning", "plan"],
  ["research", "research"],
  ["design", "design"],
  ["implementation", "implement"],
  ["verification", "verify"],
]);

const TERMINAL_STATES = new Set(["passed", "approved", "completed", "succeeded"]);
const BLOCKED_STATES = new Set(["blocked", "failed", "rejected", "cancelled", "inconclusive"]);
const WORKING_STATES = new Set(["assigned", "running", "awaiting_verification", "verifying"]);

const ACTOR_DEFINITIONS = [
  { id: "planning-lead", team: "plan", kind: "lead", name: "기획팀장", idle: "plan-lead-idle", work: "plan-lead-work", interaction: "plan-console-a" },
  { id: "planning-member-a", sprite: "planning-member", team: "plan", kind: "member", name: "기획 담당", idle: "plan-member-idle", work: "plan-member-work", interaction: "plan-console-b" },
  { id: "research-lead", team: "research", kind: "lead", name: "정보조사팀장", idle: "research-lead-idle", work: "research-lead-work", interaction: "research-table-a" },
  { id: "research-member-a", sprite: "research-member", team: "research", kind: "member", name: "조사 담당", idle: "research-member-idle", work: "research-member-work", interaction: "research-table-b" },
  { id: "design-lead", team: "design", kind: "lead", name: "설계팀장", idle: "design-lead-idle", work: "design-lead-work", interaction: "design-desk-a" },
  { id: "design-member-a", sprite: "design-member", team: "design", kind: "member", name: "설계 담당", idle: "design-member-idle", work: "design-member-work", interaction: "design-desk-b" },
  { id: "engineering-lead", team: "implement", kind: "lead", name: "구현팀장", idle: "engineering-lead-idle", work: "engineering-lead-work", interaction: "engineering-desk-lead" },
  { id: "engineering-member-a", sprite: "engineer-a", team: "implement", kind: "member", name: "Engineer A", idle: "engineering-member-a-idle", work: "engineering-member-a-work", interaction: "engineering-desk-a" },
  { id: "engineering-member-b", sprite: "engineer-b", team: "implement", kind: "member", name: "Engineer B", idle: "engineering-member-b-idle", work: "engineering-member-b-work", interaction: "engineering-desk-b" },
  { id: "verification-lead", team: "verify", kind: "lead", name: "검증팀장", idle: "verification-lead-idle", work: "verification-lead-work", interaction: "verification-console-a" },
  { id: "verification-member-a", sprite: "verification-member", team: "verify", kind: "member", name: "검증 담당", idle: "verification-member-idle", work: "verification-member-work", interaction: "verification-console-b" },
];

function teamForNode(node) {
  const canonical = VISUAL_TEAM_BY_ID.get(String(node.team_id || "").toLowerCase());
  if (canonical) return canonical;
  const role = String(node.role || "").toLowerCase();
  if (TEAM_BY_ROLE.has(role)) return TEAM_BY_ROLE.get(role);
  const identity = `${node.id || ""} ${node.current_task || ""}`.toLowerCase();
  if (/research|조사|자료/.test(identity)) return "research";
  if (/design|설계|architecture/.test(identity)) return "design";
  if (/verify|검증|review|qa/.test(identity)) return "verify";
  if (/plan|기획|route/.test(identity)) return "plan";
  return "implement";
}

function actionForNode(node) {
  const status = String(node?.status || "pending").toLowerCase();
  if (BLOCKED_STATES.has(status)) return "blocked";
  if (TERMINAL_STATES.has(status) || ["pass", "approve"].includes(node?.verdict)) return "complete";
  if (WORKING_STATES.has(status)) return "work";
  return "idle";
}

function projectOffice(snapshot) {
  const nodesByTeam = new Map(["plan", "research", "design", "implement", "verify"].map((team) => [team, []]));
  (snapshot?.nodes || []).forEach((node) => nodesByTeam.get(teamForNode(node)).push(node));
  nodesByTeam.forEach((nodes) => nodes.sort((left, right) => String(left.id).localeCompare(String(right.id))));
  const canonicalAssignments = new Set((snapshot?.assignments || []).map((item) => item.node_id));
  const hasCanonicalAssignments = Number(snapshot?.schema_version || 0) >= 3;
  const teamProjection = new Map((snapshot?.teams || []).map((team) => [
    VISUAL_TEAM_BY_ID.get(team.team_id), team,
  ]));

  const actors = ACTOR_DEFINITIONS.map((definition) => ({
    ...definition,
    sprite: definition.sprite || definition.id,
    state: "idle",
    node: null,
    anchor: definition.idle,
  }));

  for (const team of nodesByTeam.keys()) {
    const teamActors = actors.filter((actor) => actor.team === team);
    const lead = teamActors.find((actor) => actor.kind === "lead");
    const members = teamActors.filter((actor) => actor.kind === "member");
    const nodes = nodesByTeam.get(team);
    const assignedNodes = hasCanonicalAssignments
      ? nodes.filter((node) => canonicalAssignments.has(node.node_id || node.id))
      : nodes;
    assignedNodes.forEach((node, index) => {
      const target = members[index] || members.at(-1);
      if (!target) return;
      target.node = node;
      target.state = actionForNode(node);
      target.anchor = target.state === "idle" ? target.idle : target.work;
    });
    if (lead && nodes.length) {
      const states = nodes.map(actionForNode);
      lead.state = states.includes("blocked") ? "blocked"
        : states.includes("work") ? "talk"
          : states.every((state) => state === "complete") ? "complete" : "idle";
      // Leads coordinate the team; they never impersonate a node by taking a member's work position.
      lead.anchor = lead.idle;
      const canonicalTeam = teamProjection.get(team);
      lead.teamSummary = canonicalTeam
        ? `${canonicalTeam.status} · ${canonicalTeam.active_node_count}/${canonicalTeam.total_node_count}`
        : `${nodes.length} node${nodes.length === 1 ? "" : "s"}`;
    } else if (lead && teamProjection.has(team)) {
      const canonicalTeam = teamProjection.get(team);
      lead.teamSummary = canonicalTeam.status;
    }
  }
  return { actors, nodesByTeam, teamsByVisualId: teamProjection };
}

export { ACTOR_DEFINITIONS, actionForNode, projectOffice, teamForNode };
