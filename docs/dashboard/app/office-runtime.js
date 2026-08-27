import { OfficeNavigator } from "./office-navigation.js";
import { projectOffice } from "./office-director.js";

const STATE_FRAME = new Map([
  ["idle", 0],
  ["moving", 1],
  ["work", 2],
  ["talk", 3],
  ["blocked", 4],
  ["complete", 5],
]);

const TEAM_LABELS = new Map([
  ["plan", "기획팀"],
  ["research", "정보조사팀"],
  ["design", "설계팀"],
  ["implement", "구현팀"],
  ["verify", "검증팀"],
]);

const DIALOGUE_EVENTS = new Set([
  "run_created",
  "node_assigned",
  "node_started",
  "node_status_changed",
  "progress_reported",
  "blocked",
  "failed",
  "verification_started",
  "verdict_recorded",
  "run_terminal",
]);

const LEAD_DIALOGUE = new Map([
  ["plan", "작업을 나눠 시작하겠습니다."],
  ["research", "자료 확인을 시작합니다."],
  ["design", "설계 작업을 시작합니다."],
  ["implement", "구현 작업을 나눠 시작합니다."],
  ["verify", "검증을 시작합니다."],
]);

function teamStatus(team) {
  if (!team) return { state: "idle", label: "상태 정보 없음" };
  const status = String(team.status || "standby").toLowerCase();
  if (status === "blocked") {
    return { state: "blocked", label: `${Math.max(1, team.total_node_count || 0)}건 막힘` };
  }
  if (status === "active") {
    return { state: "work", label: `${team.agent_count || 0}명 작업 중` };
  }
  if (status === "complete") return { state: "complete", label: "작업 완료" };
  if (status === "omitted") return { state: "idle", label: "계획에서 생략" };
  return { state: "idle", label: "차례를 기다리는 중" };
}

function concise(text, limit = 34) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  return normalized.length > limit ? `${normalized.slice(0, limit - 1)}…` : normalized;
}

function eventKey(event) {
  if (!event) return "none";
  return String(event.seq ?? event.digest ?? `${event.type}:${event.node_id}:${event.updatedAt || ""}`);
}

function dialogueForEvent(snapshot, projection) {
  const event = snapshot?.recentEvents?.at(-1) || snapshot?.lastEvent;
  if (!event || !DIALOGUE_EVENTS.has(String(event.type || "").toLowerCase())) return null;
  const primary = projection.actors.find((actor) => actor.kind === "member" && actor.node?.id === event.node_id)
    || projection.actors.find((actor) => actor.kind === "lead" && actor.team === "plan");
  if (!primary) return null;
  const teamLead = projection.actors.find((actor) => actor.kind === "lead" && actor.team === primary.team);
  let line = primary.node?.current_task || event.summary || "작업 상태를 확인하고 있어요.";
  if (primary.state === "blocked") line = "작업이 막혔어요. 확인이 필요해요.";
  else if (event.type === "verification_started") line = "결과와 근거를 확인할게요.";
  else if (event.type === "verdict_recorded") line = "검증을 통과했어요.";
  else if (event.type === "run_created") line = "작업 지도를 열게요.";
  return {
    key: eventKey(event),
    critical: ["blocked", "failed", "verdict_recorded", "run_terminal"].includes(event.type),
    primary: { actorId: primary.id, text: concise(line) },
    lead: teamLead && teamLead.id !== primary.id && primary.state === "work"
      ? { actorId: teamLead.id, text: LEAD_DIALOGUE.get(primary.team) }
      : null,
  };
}

function pathKeyframes(path) {
  let total = 0;
  const lengths = path.slice(1).map((point, index) => {
    const previous = path[index];
    const distance = Math.hypot(point.x - previous.x, point.y - previous.y);
    total += distance;
    return distance;
  });
  let traversed = 0;
  return path.map((point, index) => {
    if (index) traversed += lengths[index - 1];
    return { left: `${point.x}px`, top: `${point.y}px`, offset: total ? traversed / total : 1 };
  });
}

class OfficeRuntime {
  constructor({ map, viewport, worldElement, actorLayer, environmentLayer, roomLayer, onSelect }) {
    this.map = map;
    this.viewport = viewport;
    this.worldElement = worldElement;
    this.actorLayer = actorLayer;
    this.environmentLayer = environmentLayer;
    this.roomLayer = roomLayer;
    this.onSelect = onSelect;
    this.navigator = new OfficeNavigator(map);
    this.actors = new Map();
    this.snapshot = null;
    this.pendingSnapshot = null;
    this.applying = false;
    this.dialogueKey = null;
    this.dialogueCooldown = new Map();
    this.dialogueTimers = new Set();
    this.motionAllowed = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.#renderRooms();
  }

  #renderRooms() {
    const fragment = document.createDocumentFragment();
    Object.values(this.map.rooms).forEach((room) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "room-sign";
      button.dataset.team = room.id;
      button.innerHTML = `<span>${room.label}</span><small>배정된 작업 없음</small>`;
      button.style.left = `${room.labelPoint.x}px`;
      button.style.top = `${room.labelPoint.y}px`;
      button.addEventListener("click", () => this.onSelect({ kind: "team", team: room.id, snapshot: this.snapshot }));
      fragment.append(button);
    });
    this.roomLayer.replaceChildren(fragment);
  }

  #updateRooms(projection) {
    Object.keys(this.map.rooms).forEach((team) => {
      const button = this.roomLayer.querySelector(`[data-team="${team}"]`);
      const status = teamStatus(projection.teamsByVisualId.get(team));
      button.dataset.state = status.state;
      button.querySelector("small").textContent = status.label;
      button.setAttribute("aria-label", `${TEAM_LABELS.get(team)}, ${status.label}`);
    });
  }

  #createActor(actor) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "office-actor";
    button.dataset.actor = actor.id;
    button.dataset.team = actor.team;
    button.dataset.kind = actor.kind;
    button.innerHTML = '<span class="actor-dialogue" aria-hidden="true"></span><span class="office-actor-sprite" aria-hidden="true"></span>';
    button.addEventListener("click", () => this.onSelect({ kind: "actor", actor: this.actors.get(actor.id), snapshot: this.snapshot }));
    this.actorLayer.append(button);
    return {
      definition: actor,
      element: button,
      anchor: actor.idle,
      node: `${actor.idle}-node`,
      state: "idle",
      assignment: null,
      animation: null,
    };
  }

  #clearDialogue() {
    this.dialogueTimers.forEach((timer) => window.clearTimeout(timer));
    this.dialogueTimers.clear();
    this.actors.forEach((actor) => {
      actor.element.classList.remove("is-speaking", "is-primary-speaker");
      actor.element.querySelector(".actor-dialogue").textContent = "";
    });
  }

  #showDialogue(actorId, text, primary, critical) {
    const actor = this.actors.get(actorId);
    if (!actor || !text) return;
    const now = Date.now();
    if (!critical && now - (this.dialogueCooldown.get(actorId) || 0) < 10000) return;
    this.dialogueCooldown.set(actorId, now);
    actor.element.querySelector(".actor-dialogue").textContent = text;
    actor.element.classList.add("is-speaking");
    actor.element.classList.toggle("is-primary-speaker", primary);
    const timer = window.setTimeout(() => {
      actor.element.classList.remove("is-speaking", "is-primary-speaker");
      actor.element.querySelector(".actor-dialogue").textContent = "";
      this.dialogueTimers.delete(timer);
    }, primary ? 4600 : 3200);
    this.dialogueTimers.add(timer);
  }

  #updateDialogue(snapshot, projection) {
    const dialogue = dialogueForEvent(snapshot, projection);
    if (!dialogue || dialogue.key === this.dialogueKey) return;
    this.dialogueKey = dialogue.key;
    this.#clearDialogue();
    if (dialogue.lead && !window.matchMedia("(max-width: 700px)").matches) {
      this.#showDialogue(dialogue.lead.actorId, dialogue.lead.text, false, dialogue.critical);
    }
    const primaryDelay = dialogue.lead && !window.matchMedia("(max-width: 700px)").matches ? 1800 : 0;
    const timer = window.setTimeout(() => {
      this.#showDialogue(dialogue.primary.actorId, dialogue.primary.text, true, dialogue.critical);
      this.dialogueTimers.delete(timer);
    }, primaryDelay);
    this.dialogueTimers.add(timer);
  }

  #applyFrame(runtimeActor, state) {
    const sprite = runtimeActor.element.querySelector(".office-actor-sprite");
    const frame = STATE_FRAME.get(state) ?? 0;
    sprite.style.setProperty("--sprite-sheet", `url("./characters/runtime/${runtimeActor.definition.sprite}/sheet.png")`);
    sprite.style.setProperty("--sprite-frame", String(frame));
    runtimeActor.element.dataset.state = state;
    runtimeActor.element.classList.toggle("is-active", ["work", "talk"].includes(state));
    runtimeActor.element.classList.toggle("is-blocked", state === "blocked");
    runtimeActor.element.classList.toggle("is-complete", state === "complete");
  }

  #setPosition(runtimeActor, anchorId) {
    const anchor = this.map.anchors[anchorId];
    runtimeActor.element.style.left = `${anchor.x}px`;
    runtimeActor.element.style.top = `${anchor.y}px`;
    runtimeActor.element.style.zIndex = String(Math.round(anchor.y));
  }

  async #move(runtimeActor, targetAnchor, path) {
    if (runtimeActor.anchor === targetAnchor) return;
    const targetNode = `${targetAnchor}-node`;
    const horizontalDirection = path.at(-1).x - path[0].x;
    runtimeActor.element.classList.toggle("is-facing-left", horizontalDirection < -2);
    runtimeActor.animation?.cancel();
    this.#applyFrame(runtimeActor, "moving");
    if (!this.motionAllowed || document.visibilityState === "hidden") {
      this.#setPosition(runtimeActor, targetAnchor);
    } else {
      const animation = runtimeActor.element.animate(pathKeyframes(path), {
        duration: Math.max(900, path.length * 230),
        easing: "linear",
        fill: "forwards",
      });
      runtimeActor.animation = animation;
      try {
        await animation.finished;
      } catch (_) {
        return;
      }
      this.#setPosition(runtimeActor, targetAnchor);
      animation.cancel();
    }
    runtimeActor.anchor = targetAnchor;
    runtimeActor.node = targetNode;
  }

  #movementPlan(moves) {
    const occupied = new Map([...this.actors].map(([id, actor]) => [id, this.map.anchors[actor.anchor]]));

    const search = (remaining, positions, plan) => {
      if (!remaining.length) return plan;
      for (let index = 0; index < remaining.length; index += 1) {
        const move = remaining[index];
        const obstacles = [...positions]
          .filter(([id]) => id !== move.runtimeActor.definition.id)
          .map(([, point]) => point);
        let path;
        try {
          path = this.navigator.route(
            move.runtimeActor.node,
            `${move.actor.anchor}-node`,
            { actors: obstacles },
          );
        } catch (_) {
          continue;
        }
        const nextPositions = new Map(positions);
        nextPositions.set(move.runtimeActor.definition.id, this.map.anchors[move.actor.anchor]);
        const nextRemaining = remaining.filter((_, candidate) => candidate !== index);
        const result = search(nextRemaining, nextPositions, [...plan, { ...move, path }]);
        if (result) return result;
      }
      return null;
    };

    const result = search(moves, occupied, []);
    if (!result) throw new Error("Actor-safe movement plan is unavailable");
    return result;
  }

  #focusActiveActor(projection) {
    if (!this.viewport.classList.contains("is-mobile-pan")) return;
    const latestNodeId = this.snapshot?.recentEvents?.at(-1)?.node_id;
    const active = projection.actors.find((actor) => actor.node?.id === latestNodeId)
      || projection.actors.find((actor) => actor.kind === "member" && ["work", "blocked"].includes(actor.state));
    if (!active) return;
    const anchor = this.map.anchors[active.anchor];
    const scale = Number(this.worldElement.dataset.worldScale || 1);
    const focus = () => {
      const target = anchor.x * scale - this.viewport.clientWidth / 2;
      this.viewport.scrollTo({
        left: Math.max(0, Math.min(this.viewport.scrollWidth - this.viewport.clientWidth, target)),
        behavior: this.motionAllowed ? "smooth" : "auto",
      });
    };
    focus();
    window.setTimeout(focus, 80);
  }

  #updateEnvironment(projection) {
    const active = new Map();
    projection.actors.forEach((actor) => {
      if (actor.kind === "member" && ["work", "blocked", "complete"].includes(actor.state)) {
        active.set(actor.interaction, actor.state);
      }
    });
    const fragment = document.createDocumentFragment();
    Object.values(this.map.interactions).forEach((interaction) => {
      const state = active.get(interaction.id) || "idle";
      const marker = document.createElement("span");
      marker.className = "environment-state";
      marker.dataset.interaction = interaction.id;
      marker.dataset.action = interaction.action;
      marker.dataset.state = state;
      marker.style.left = `${interaction.x}px`;
      marker.style.top = `${interaction.y - 34}px`;
      fragment.append(marker);
    });
    this.environmentLayer.replaceChildren(fragment);
  }

  applySnapshot(snapshot) {
    this.pendingSnapshot = snapshot;
    if (this.applying) return Promise.resolve();
    return this.#drainSnapshots();
  }

  async #drainSnapshots() {
    this.applying = true;
    try {
      while (this.pendingSnapshot) {
        const snapshot = this.pendingSnapshot;
        this.pendingSnapshot = null;
        await this.#applySnapshot(snapshot);
      }
    } finally {
      this.applying = false;
    }
  }

  async #applySnapshot(snapshot) {
    this.snapshot = snapshot;
    const projection = projectOffice(snapshot);
    const latestEvent = snapshot?.recentEvents?.at(-1) || snapshot?.lastEvent;
    const latestEventKey = eventKey(latestEvent);
    if (latestEventKey !== this.dialogueKey) this.#clearDialogue();
    if (!this.actors.size) {
      projection.actors.forEach((actor) => {
        const runtimeActor = this.#createActor(actor);
        this.actors.set(actor.id, runtimeActor);
        this.#setPosition(runtimeActor, actor.idle);
        this.#applyFrame(runtimeActor, "idle");
      });
    }
    this.#updateRooms(projection);
    const moves = [];
    for (const actor of projection.actors) {
      const runtimeActor = this.actors.get(actor.id);
      runtimeActor.definition = actor;
      runtimeActor.assignment = actor.node;
      runtimeActor.element.setAttribute(
        "aria-label",
        `${actor.name}, ${TEAM_LABELS.get(actor.team)}, ${actor.state === "work" ? "작업 중" : actor.state}`,
      );
      if (runtimeActor.anchor !== actor.anchor) {
        moves.push({ actor, runtimeActor });
      } else {
        runtimeActor.state = actor.state;
        this.#applyFrame(runtimeActor, actor.state);
      }
    }
    for (const move of this.#movementPlan(moves)) {
      await this.#move(move.runtimeActor, move.actor.anchor, move.path);
      move.runtimeActor.state = move.actor.state;
      this.#applyFrame(move.runtimeActor, move.actor.state);
    }
    this.#updateEnvironment(projection);
    this.#updateDialogue(snapshot, projection);
    if (!dialogueForEvent(snapshot, projection)) this.dialogueKey = latestEventKey;
    this.#focusActiveActor(projection);
  }
}

export { OfficeRuntime, STATE_FRAME, dialogueForEvent, pathKeyframes, teamStatus };
