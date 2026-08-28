import { AnchorRegistry } from "./office-occupancy.js";

const NS = "http://www.w3.org/2000/svg";

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(NS, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function pointList(polygon) {
  return polygon.map(([x, y]) => `${x},${y}`).join(" ");
}

function polygonElement(item, className) {
  return svgElement("polygon", { points: pointList(item.polygon), class: className, "data-geometry": item.id });
}

function doorLine(item) {
  return svgElement("line", {
    x1: item.portal[0][0],
    y1: item.portal[0][1],
    x2: item.portal[1][0],
    y2: item.portal[1][1],
    class: "debug-door debug-door-portal",
    "data-geometry": item.id,
    "vector-effect": "non-scaling-stroke",
  });
}

function circleElement(item, className, radius) {
  return svgElement("circle", { cx: item.x, cy: item.y, r: radius, class: className, "data-geometry": item.id });
}

function label(text, x, y, className = "debug-label") {
  const element = svgElement("text", { x, y, class: className });
  element.textContent = text;
  return element;
}

function arrowDefs() {
  const defs = svgElement("defs");
  const marker = svgElement("marker", {
    id: "debug-arrow",
    viewBox: "0 0 10 10",
    refX: 9,
    refY: 5,
    markerWidth: 5,
    markerHeight: 5,
    orient: "auto-start-reverse",
  });
  marker.append(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#27d9df" }));
  defs.append(marker);
  return defs;
}

function facingEnd(interaction) {
  const delta = 22;
  const directions = {
    up: [0, -delta],
    down: [0, delta],
    left: [-delta, 0],
    right: [delta, 0],
  };
  const [dx, dy] = directions[interaction.facing] || [0, -delta];
  return { x: interaction.x + dx, y: interaction.y + dy };
}

function renderGeometry(svg, map) {
  const fragment = document.createDocumentFragment();
  fragment.append(arrowDefs());
  map.walkable.forEach((item) => fragment.append(polygonElement(item, "debug-walkable")));
  map.blocked.forEach((item) => fragment.append(polygonElement(item, "debug-blocked")));
  map.zZones.forEach((item) => fragment.append(polygonElement(item, "debug-z-zone")));
  Object.values(map.rooms).forEach((item) => {
    fragment.append(polygonElement(item, "debug-room"));
    fragment.append(label(item.label, item.labelPoint.x, item.labelPoint.y));
  });
  map.doors.forEach((item) => {
    fragment.append(doorLine(item));
    fragment.append(label(item.id, item.portal[0][0] + 8, item.portal[0][1] - 8, "debug-door-label"));
  });
  Object.values(map.anchors).filter((item) => !item.debugOnly).forEach((item) => {
    fragment.append(circleElement(item, "debug-anchor", 8));
    fragment.append(label(item.id, item.x + 10, item.y + 18, "debug-anchor-label"));
  });
  Object.values(map.interactions).forEach((item) => {
    fragment.append(circleElement(item, "debug-interaction", 6));
    const end = facingEnd(item);
    fragment.append(svgElement("line", { x1: item.x, y1: item.y, x2: end.x, y2: end.y, class: "debug-facing" }));
    fragment.append(label(`${item.id} · ${item.action}`, item.x + 10, item.y - 10, "debug-point-label"));
  });
  svg.replaceChildren(fragment);
  svg.dataset.renderedGeometry = String(svg.querySelectorAll("polygon, circle, line").length);
}

function spritePosition(sprite) {
  const x = sprite.column * 100 / 7;
  const y = sprite.row * 100 / 4;
  return { x: `${x}%`, y: `${y}%` };
}

function renderActors(layer, map, onSelect) {
  const fragment = document.createDocumentFragment();
  map.debugActors.forEach((actor) => {
    const point = map.anchors[actor.anchor];
    const position = spritePosition(actor.sprite);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "debug-actor";
    button.dataset.actor = actor.id;
    button.dataset.anchor = actor.anchor;
    button.style.setProperty("--actor-x", `${point.x}px`);
    button.style.setProperty("--actor-y", `${point.y}px`);
    button.style.setProperty("--sprite-x", position.x);
    button.style.setProperty("--sprite-y", position.y);
    button.setAttribute("aria-label", `${actor.label}, ${actor.anchor}`);
    button.setAttribute("aria-pressed", "false");
    button.innerHTML = `<span class="debug-actor-sprite" aria-hidden="true"></span><span class="debug-actor-id">${actor.label}<small>@${actor.anchor}</small></span>`;
    button.addEventListener("click", () => onSelect(actor.id));
    fragment.append(button);
  });
  layer.replaceChildren(fragment);
  layer.dataset.renderedActors = String(layer.childElementCount);
}

function renderMarkers(svg, map) {
  const fragment = document.createDocumentFragment();
  Object.values(map.debugActorFeet).forEach((item) => {
    fragment.append(circleElement(item, "debug-actor-radius", map.actorRadius));
    fragment.append(circleElement(item, "debug-foot", 3.5));
  });
  svg.replaceChildren(fragment);
}

function clearPaths(svg) {
  svg.querySelectorAll("[data-active-route]").forEach((element) => element.remove());
}

function drawPath(svg, path, destination, routeId = "path") {
  const polyline = svgElement("polyline", {
    points: pointList(path.map(({ x, y }) => [x, y])),
    class: "debug-path",
    "data-active-route": routeId,
    "vector-effect": "non-scaling-stroke",
  });
  const marker = circleElement({ id: destination.id, x: destination.x, y: destination.y }, "debug-destination", 12);
  marker.dataset.activeRoute = routeId;
  svg.append(polyline, marker);
}

function pathKeyframes(path) {
  let travelled = 0;
  const lengths = path.slice(1).map((point, index) => {
    const previous = path[index];
    const length = Math.hypot(point.x - previous.x, point.y - previous.y);
    travelled += length;
    return length;
  });
  let completed = 0;
  return path.map((point, index) => {
    if (index > 0) completed += lengths[index - 1];
    return {
      left: `${point.x}px`,
      top: `${point.y}px`,
      offset: travelled === 0 ? 1 : completed / travelled,
    };
  });
}

function renderDebugWorld({ geometrySvg, markerSvg, actorLayer, map, navigator, controls }) {
  const occupancy = new AnchorRegistry(map);
  map.debugActors.forEach((actor) => occupancy.reserve(actor.id, actor.anchor));
  renderGeometry(geometrySvg, map);
  renderMarkers(markerSvg, map);

  const actors = new Map(map.debugActors.map((actor) => [actor.id, actor]));
  const destinations = new Map(Object.values(map.interactions).map((item) => [item.id, item]));

  map.debugActors.forEach((actor) => controls.source.append(new Option(actor.label, actor.id)));
  Object.values(map.interactions).forEach((item) => controls.destination.append(new Option(item.id, item.id)));

  function selectActor(id) {
    controls.source.value = id;
    actorLayer.querySelectorAll("[data-actor]").forEach((element) => {
      element.setAttribute("aria-pressed", String(element.dataset.actor === id));
    });
  }

  function trace() {
    const actor = actors.get(controls.source.value);
    const destination = destinations.get(controls.destination.value);
    if (!actor || !destination) return;
    const targetAnchor = map.anchors[destination.anchor];
    const path = navigator.route(actor.node, `${destination.anchor}-node`);
    const doorIds = navigator.doorIds(path);
    clearPaths(markerSvg);
    drawPath(markerSvg, path, { id: destination.id, x: targetAnchor.x, y: targetAnchor.y });
    selectActor(actor.id);
    controls.result.value = `${path.length}개 지점 · ${actor.label} → ${destination.id}${doorIds.length ? ` · ${doorIds.join(" → ")}` : ""}`;
    markerSvg.dataset.pathNodes = String(path.length);
    return { actor, destination, path };
  }

  async function play() {
    const route = trace();
    if (!route || route.path.length < 2) return;
    const actorElement = actorLayer.querySelector(`[data-actor="${route.actor.id}"]`);
    if (!actorElement) return;
    controls.play.disabled = true;
    controls.result.value = `이동 중 · ${route.actor.label} → ${route.destination.id}`;
    const animation = actorElement.animate(pathKeyframes(route.path), {
      duration: Math.max(4000, route.path.length * 650),
      easing: "linear",
      fill: "forwards",
    });
    try {
      await animation.finished;
      actorElement.style.left = `${route.path.at(-1).x}px`;
      actorElement.style.top = `${route.path.at(-1).y}px`;
      animation.cancel();
      controls.result.value = `이동 완료 · ${route.actor.label} → ${route.destination.id}`;
    } finally {
      controls.play.disabled = false;
    }
  }

  function traceRequiredRoutes() {
    const required = [
      ["planning-lead", "verification-console-a"],
      ["research-member-a", "engineering-desk-a"],
      ["design-member-a", "plan-console-a"],
    ];
    clearPaths(markerSvg);
    let nodeCount = 0;
    required.forEach(([actorId, destinationId], index) => {
      const actor = actors.get(actorId);
      const destination = destinations.get(destinationId);
      const targetAnchor = map.anchors[destination.anchor];
      const path = navigator.route(actor.node, `${destination.anchor}-node`);
      nodeCount += path.length;
      drawPath(
        markerSvg,
        path,
        { id: destination.id, x: targetAnchor.x, y: targetAnchor.y },
        `required-${index + 1}`,
      );
    });
    controls.result.value = `필수 방 이동 3개 · 실제 A* ${nodeCount}개 지점`;
    markerSvg.dataset.pathNodes = String(nodeCount);
    markerSvg.dataset.pathRoutes = "3";
  }

  function bindDebugToggles() {
    controls.toggles.forEach((input) => {
      const apply = () => {
        document.body.dataset[`debug${input.dataset.debugToggle.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())}`]
          = String(input.checked);
      };
      input.addEventListener("change", apply);
      apply();
    });
  }

  renderActors(actorLayer, map, selectActor);
  bindDebugToggles();
  selectActor(map.debugActors[0].id);
  controls.trace.addEventListener("click", trace);
  controls.play.addEventListener("click", play);
  controls.source.addEventListener("change", () => selectActor(controls.source.value));
  controls.presets.addEventListener("click", (event) => {
    const routeSet = event.target.closest("[data-route-set]");
    if (routeSet) {
      traceRequiredRoutes();
      return;
    }
    const button = event.target.closest("[data-route]");
    if (!button) return;
    const [actorId, destinationId] = button.dataset.route.split(":");
    controls.source.value = actorId;
    controls.destination.value = destinationId;
    trace();
  });
  controls.legendToggle.addEventListener("click", () => {
    const collapsed = controls.legend.classList.toggle("is-collapsed");
    controls.legendToggle.textContent = collapsed ? "범례 펼치기" : "범례 접기";
    controls.legendToggle.setAttribute("aria-expanded", String(!collapsed));
  });
  trace();
}

export { renderDebugWorld };
