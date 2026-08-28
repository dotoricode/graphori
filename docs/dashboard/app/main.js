import { DashboardStream } from "./dashboard-stream.js";
import { DemoOfficeSequence } from "./demo-office.js";
import { renderDebugWorld } from "./debug-world.js";
import { OfficeNavigator } from "./office-navigation.js";
import { OfficeRuntime } from "./office-runtime.js";
import { OfficeUI } from "./office-ui.js";
import { WorldStage } from "./world-stage.js";
import { language, t } from "./i18n.js";

const params = new URLSearchParams(window.location.search);
const debugEnabled = params.get("debug-world") === "1";
const demoEnabled = params.get("demo") === "1";
const requestedDemoStep = params.has("demo-step") ? Number(params.get("demo-step")) : null;
const requestedRun = params.get("run") || params.get("run_id") || "";
document.documentElement.lang = language;

function localizeStaticDocument() {
  const text = (selector, key) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = t(key);
  };
  text("#active-run", "waitingConnection");
  text("#graph-summary", "graphSummary");
  text("#transport-state", "ready");
  text("#connect-panel > p", "connectHelp");
  text('label[for="run-id"]', "runId");
  text("#connect-form button", "connect");
  text('#connect-panel a[href="?demo=1"]', "demo");
  text("#connect-status", "waitingRun");
  text("#event-summary", "waitingEvent");
  text("#progress-label", "verifyZero");
  text("#inspector-close", "close");
  text("#inspector-kicker", "worker");
  text("#inspector-title", "selectedInfo");
}
localizeStaticDocument();

const elements = {
  viewport: document.getElementById("office-viewport"),
  world: document.getElementById("office-world"),
  debugGeometry: document.getElementById("debug-geometry"),
  debugActors: document.getElementById("debug-actors"),
  debugMarkers: document.getElementById("debug-markers"),
  actors: document.getElementById("actor-layer"),
  environment: document.getElementById("environment-layer"),
  rooms: document.getElementById("room-sign-layer"),
  legend: document.getElementById("debug-legend"),
  legendToggle: document.getElementById("toggle-debug-ui"),
  pathInspector: document.getElementById("path-inspector"),
  pathSource: document.getElementById("path-source"),
  pathDestination: document.getElementById("path-destination"),
  pathTrace: document.getElementById("trace-path"),
  pathPlay: document.getElementById("play-path"),
  pathResult: document.getElementById("path-result"),
  pathPresets: document.querySelector(".path-presets"),
  debugToggles: document.querySelectorAll("[data-debug-toggle]"),
  panel: document.getElementById("connect-panel"),
  form: document.getElementById("connect-form"),
  input: document.getElementById("run-id"),
  status: document.getElementById("connect-status"),
  hud: document.getElementById("live-hud"),
  footer: document.getElementById("live-footer"),
  activeRun: document.getElementById("active-run"),
  graphSummary: document.getElementById("graph-summary"),
  transport: document.getElementById("transport-state"),
  clock: document.getElementById("office-clock"),
  eventTicker: document.getElementById("event-ticker"),
  eventTime: document.getElementById("event-time"),
  eventType: document.getElementById("event-type"),
  eventSummary: document.getElementById("event-summary"),
  progressLabel: document.getElementById("progress-label"),
  progressFill: document.getElementById("progress-fill"),
  inspector: document.getElementById("office-inspector"),
  inspectorClose: document.getElementById("inspector-close"),
  inspectorKicker: document.getElementById("inspector-kicker"),
  inspectorTitle: document.getElementById("inspector-title"),
  inspectorBody: document.getElementById("inspector-body"),
};

let officeMap;
let stage;
let stream;
let runtime;
let officeUI;
let demo;

function setTransport(label, kind = "normal") {
  elements.transport.textContent = label;
  elements.transport.prepend(document.createElement("i"));
  elements.transport.classList.toggle("is-error", kind === "error");
}

function enterLive(runId, mode) {
  document.body.dataset.uiState = "live";
  elements.panel.hidden = true;
  elements.hud.hidden = false;
  elements.footer.hidden = false;
  elements.activeRun.textContent = runId;
  setTransport(mode === "demo" ? "DEMO" : t("connected"));
}

function connect(runId) {
  const normalized = runId.trim();
  if (!normalized) {
    elements.status.textContent = t("enterRun");
    elements.input.focus();
    return;
  }
  enterLive(normalized, "real");
  stream.connect(normalized);
}

function startDemo() {
  stream.stop();
  enterLive("demo-office", "demo");
  demo.start(Number.isInteger(requestedDemoStep) ? requestedDemoStep : null);
}

async function initialize() {
  const response = await fetch("./world/office-map.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`office map ${response.status}`);
  officeMap = await response.json();
  stage = new WorldStage(elements.viewport, elements.world, officeMap.world);
  stage.start();
  officeUI = new OfficeUI(elements);
  runtime = new OfficeRuntime({
    map: officeMap,
    viewport: elements.viewport,
    worldElement: elements.world,
    actorLayer: elements.actors,
    environmentLayer: elements.environment,
    roomLayer: elements.rooms,
    onSelect: (selection) => officeUI.open(selection),
  });

  if (debugEnabled) {
    const navigator = new OfficeNavigator(officeMap);
    renderDebugWorld({
      geometrySvg: elements.debugGeometry,
      markerSvg: elements.debugMarkers,
      actorLayer: elements.debugActors,
      map: officeMap,
      navigator,
      controls: {
        source: elements.pathSource,
        destination: elements.pathDestination,
        trace: elements.pathTrace,
        play: elements.pathPlay,
        result: elements.pathResult,
        presets: elements.pathPresets,
        legend: elements.legend,
        legendToggle: elements.legendToggle,
        toggles: elements.debugToggles,
      },
    });
    elements.legend.hidden = false;
    elements.pathInspector.hidden = false;
    document.body.dataset.debugWorld = "true";
    document.body.dataset.debugReady = "true";
  }

  stream = new DashboardStream({
    onSnapshot: (snapshot) => {
      setTransport("LIVE");
      officeUI.update(snapshot);
      runtime.applySnapshot(snapshot).catch((error) => setTransport(t("displayError", { message: error.message }), "error"));
    },
    onTransport: (state) => {
      if (state === "connected") setTransport("LIVE");
      else if (state === "reconnecting") setTransport(t("reconnecting"), "error");
      else setTransport(t("connected"));
    },
  });
  demo = new DemoOfficeSequence((snapshot) => {
    officeUI.update(snapshot);
    runtime.applySnapshot(snapshot).catch((error) => setTransport(t("displayError", { message: error.message }), "error"));
  });

  elements.form.addEventListener("submit", (event) => {
    event.preventDefault();
    connect(elements.input.value);
  });

  if (demoEnabled) startDemo();
  else if (requestedRun) {
    elements.input.value = requestedRun;
    connect(requestedRun);
  }
}

initialize().catch((error) => {
  elements.status.textContent = t("loadError", { message: error.message });
  setTransport(t("error"), "error");
});
