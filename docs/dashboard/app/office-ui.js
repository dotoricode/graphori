import { ACTOR_DEFINITIONS, actionForNode, teamForNode } from "./office-director.js";
import { catalogLabel, language, t } from "./i18n.js";

const TEAM_LABELS = new Map([
  ["plan", t("planTeam")],
  ["research", t("researchTeam")],
  ["design", t("designTeam")],
  ["implement", t("implementTeam")],
  ["verify", t("verifyTeam")],
]);

const STATE_LABELS = new Map([
  ["idle", t("idle")],
  ["work", t("work")],
  ["talk", t("talk")],
  ["blocked", t("blocked")],
  ["complete", t("complete")],
]);

function safeTime(value) {
  if (!value) return "--:--:--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "--:--:--" : date.toLocaleTimeString(language === "ko" ? "ko-KR" : "en-GB", { hour12: false });
}

function durationLabel(milliseconds) {
  if (!Number.isFinite(milliseconds)) return t("unknown");
  const total = Math.max(0, Math.round(milliseconds / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return minutes ? t("minutesSeconds", { minutes, seconds }) : t("seconds", { seconds });
}

function localized(table, key, fallback) {
  return catalogLabel(table, key, fallback);
}

function criterionStatusLabel(status) {
  return ({
    PROVEN: t("proven"),
    NOT_PROVEN: t("notProven"),
    FAILED: t("failed"),
    NOT_APPLICABLE: t("notApplicable"),
  })[status] || t("notProven");
}

function actorDisplayName(definition) {
  if (language === "ko") return definition.name;
  return `${TEAM_LABELS.get(definition.team)} ${definition.kind === "lead" ? t("lead") : t("member")}`;
}

function detailRow(label, value, monospace = false) {
  const row = document.createElement("div");
  row.className = "inspector-row";
  const term = document.createElement("span");
  term.textContent = label;
  const detail = document.createElement("strong");
  detail.textContent = value || t("none");
  detail.classList.toggle("is-mono", monospace);
  row.append(term, detail);
  return row;
}

class OfficeUI {
  constructor(elements) {
    this.elements = elements;
    this.snapshot = null;
    this.selection = null;
    elements.inspectorClose.addEventListener("click", () => this.closeInspector());
    elements.eventTicker.addEventListener("click", () => this.openEvent());
    elements.graphSummary.addEventListener("click", () => this.openGraph());
    this.clockTimer = window.setInterval(() => {
      if (document.visibilityState === "visible") elements.clock.textContent = safeTime(new Date().toISOString());
    }, 1000);
    elements.clock.textContent = safeTime(new Date().toISOString());
  }

  update(snapshot) {
    this.snapshot = snapshot;
    const event = snapshot.recentEvents?.at(-1) || snapshot.lastEvent || {};
    const progress = snapshot.provider_progress || { state: "unknown", percent: null };
    this.elements.eventTime.textContent = safeTime(event.updatedAt || snapshot.updatedAt);
    this.elements.eventType.textContent = event.type || "run_created";
    this.elements.eventSummary.textContent = event.summary || t("waitingEvent");
    this.elements.progressLabel.textContent = typeof progress.percent === "number"
      ? t("providerProgress", { percent: progress.percent }) : t("providerUnknown");
    this.elements.progressFill.style.width = typeof progress.percent === "number"
      ? `${Math.max(0, Math.min(100, progress.percent))}%` : "0%";
    if (this.selection?.kind === "event") this.openEvent();
  }

  open(selection) {
    this.selection = selection;
    if (selection.kind === "actor") this.#openActor(selection.actor);
    else if (selection.kind === "team") this.#openTeam(selection.team);
  }

  #show(kicker, title, rows) {
    this.elements.inspectorKicker.textContent = kicker;
    this.elements.inspectorTitle.textContent = title;
    this.elements.inspectorBody.replaceChildren(...rows);
    this.elements.inspector.hidden = false;
  }

  #openActor(actor) {
    const node = actor.assignment;
    const rows = [
      detailRow(t("team"), TEAM_LABELS.get(actor.definition.team)),
      detailRow(t("role"), actor.definition.kind === "lead" ? t("coordination") : t("contributor")),
      detailRow(t("current"), STATE_LABELS.get(actor.state) || actor.state),
    ];
    if (node) {
      rows.push(detailRow(t("currentTask"), node.title || node.current_task || t("noDescription")));
      rows.push(detailRow(t("status"), localized(this.snapshot?.presentation?.statuses, node.status, node.status)));
      rows.push(detailRow(t("model"), node.requested_model || node.model || t("notUsed")));
      rows.push(detailRow(t("effort"), localized(this.snapshot?.presentation?.efforts, node.requested_effort || node.effort, t("notApplicable"))));
      rows.push(detailRow(t("route"), localized(this.snapshot?.presentation?.routes, node.selected_route || node.adapter || node.provider)));
      rows.push(detailRow("Skill", (node.skills || []).map((skill) => skill.name || skill.skill_id).join(", ") || t("notUsed")));
      rows.push(detailRow(t("workerRun"), node.execution?.status || t("noRecord"), true));
      rows.push(detailRow(t("verification"), node.verification?.status || node.verdict || "not_started", true));
      rows.push(detailRow(t("verificationSource"), node.verification_source || "not_recorded", true));
      if (node.criteria?.length) rows.push(detailRow(t("criteria"), node.criteria.map((item) => `${item.criterion_id}: ${criterionStatusLabel(item.status)}`).join(", ")));
      rows.push(detailRow(t("elapsed"), durationLabel(node.activity?.elapsed_ms ?? node.timing?.total_ms)));
      rows.push(detailRow(t("progress"), typeof node.provider_progress?.percent === "number" ? `${node.provider_progress.percent}%` : t("unknown")));
      rows.push(detailRow(t("taskId"), node.node_id || node.id, true));
      rows.push(detailRow(t("dependencies"), (node.dependencies || []).join(", ") || t("none"), true));
      rows.push(detailRow(t("evidence"), (node.evidence_ids || []).join(", ") || t("none"), true));
      const recent = [...(this.snapshot?.recentEvents || [])].reverse().find((event) => event.node_id === node.id);
      if (recent) rows.push(detailRow(t("recentEvent"), `${recent.type} · ${safeTime(recent.updatedAt)}`, true));
    } else {
      rows.push(detailRow("Node", actor.definition.kind === "lead" ? t("teamOnly") : t("unassigned")));
    }
    this.#show(t("worker"), actorDisplayName(actor.definition), rows);
  }

  #openTeam(team) {
    const nodes = (this.snapshot?.nodes || []).filter((node) => {
      return teamForNode(node) === team;
    });
    const states = nodes.map(actionForNode);
    const blocked = states.filter((state) => state === "blocked").length;
    const working = states.filter((state) => state === "work").length;
    const current = blocked ? t("needsReviewCount", { count: blocked })
      : working ? t("workingCount", { count: working })
        : nodes.length && states.every((state) => state === "complete") ? t("workComplete") : t("idle");
    const people = ACTOR_DEFINITIONS.filter((actor) => actor.team === team);
    const lead = people.find((actor) => actor.kind === "lead");
    const recent = [...(this.snapshot?.recentEvents || [])].reverse().find((event) => {
      const node = nodes.find((candidate) => candidate.id === event.node_id);
      return node || teamForNode({ role: event.role }) === team;
    });
    const canonicalTeam = (this.snapshot?.teams || []).find((item) => teamForNode({ team_id: item.team_id }) === team);
    const rows = [
      detailRow(t("current"), localized(this.snapshot?.presentation?.statuses, canonicalTeam?.status, current)),
      detailRow(t("graphAgents"), t("workers", { count: canonicalTeam?.agent_count || 0 })),
      detailRow(t("characterPool"), t("visualOnly", { count: people.length })),
      detailRow(t("lead"), `${lead ? actorDisplayName(lead) : t("teamLead")} · ${working || blocked ? t("coordinating") : t("checking")}`),
    ];
    if (canonicalTeam?.status === "omitted" && canonicalTeam.reason) {
      rows.splice(1, 0, detailRow(t("omissionReason"), localized(
        this.snapshot?.presentation?.omission_reasons,
        canonicalTeam.reason,
        canonicalTeam.reason,
      )));
    }
    if (recent) rows.push(detailRow(t("recentEvent"), `${recent.type} · ${safeTime(recent.updatedAt)}`, true));
    nodes.slice(0, 4).forEach((node) => rows.push(detailRow(node.id, node.current_task || node.status, true)));
    this.#show(t("team"), TEAM_LABELS.get(team), rows);
  }

  openGraph() {
    this.selection = { kind: "graph" };
    const rows = [
      detailRow("Plan", `v${this.snapshot?.plan_version || 1}`, true),
      detailRow("Plan digest", this.snapshot?.plan_digest, true),
      detailRow("Graph digest", this.snapshot?.graph_digest, true),
      detailRow(t("graphAgents"), t("workers", { count: this.snapshot?.actual_agent_count || 0 })),
    ];
    (this.snapshot?.teams || []).forEach((team) => {
      rows.push(detailRow(localized(this.snapshot?.presentation?.teams, team.team_id, team.display_name), `${localized(this.snapshot?.presentation?.statuses, team.status, team.status)} · ${team.active_node_count}/${team.total_node_count}`));
    });
    (this.snapshot?.edges || []).forEach((edge) => {
      rows.push(detailRow(edge.type, `${edge.from} → ${edge.to}`, true));
    });
    if (!(this.snapshot?.edges || []).length) rows.push(detailRow("Graph", t("independentRoot")));
    (this.snapshot?.gates || []).filter((gate) => gate.status === "pending").forEach((gate) => {
      rows.push(detailRow("Gate", `${gate.node_id} · ${gate.kind} · pending`, true));
    });
    this.#show(t("executionGraph"), "Canonical Graph", rows);
  }

  openEvent() {
    const event = this.snapshot?.recentEvents?.at(-1) || this.snapshot?.lastEvent;
    if (!event) return;
    this.selection = { kind: "event" };
    const rows = [
      detailRow(t("time"), safeTime(event.updatedAt || this.snapshot.updatedAt)),
      detailRow("Event", event.type, true),
      detailRow("Node", event.node_id, true),
      detailRow("Producer", event.producer?.role || event.role, true),
      detailRow(t("description"), event.summary || t("noDescription")),
      detailRow("Evidence", (event.evidence_ids || []).join(", ") || t("none"), true),
    ];
    this.#show(t("recentEvent"), event.type || "Event", rows);
  }

  closeInspector() {
    this.selection = null;
    this.elements.inspector.hidden = true;
  }
}

export { OfficeUI, safeTime };
