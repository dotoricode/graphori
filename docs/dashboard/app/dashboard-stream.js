class DashboardStream {
  constructor({ onSnapshot, onTransport }) {
    this.onSnapshot = onSnapshot;
    this.onTransport = onTransport;
    this.source = null;
    this.run = null;
    this.generation = 0;
    this.reconnectAttempt = 0;
    this.reconnectTimer = null;
  }

  async connect(runId) {
    this.stop();
    this.generation += 1;
    const generation = this.generation;
    this.run = runId;
    this.onTransport("connecting");
    this.#open(generation);
    try {
      await this.#fetch(generation);
    } catch (_) {
      if (generation === this.generation) this.#reconnect(generation);
    }
  }

  stop() {
    this.source?.close();
    this.source = null;
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }

  async #fetch(generation) {
    const response = await fetch(`/runs/${encodeURIComponent(this.run)}/snapshot`, { cache: "no-store" });
    if (!response.ok) throw new Error(`snapshot ${response.status}`);
    const snapshot = await response.json();
    if (generation !== this.generation) return;
    this.onSnapshot(snapshot);
  }

  #open(generation) {
    this.source = new EventSource(`/runs/${encodeURIComponent(this.run)}/events`);
    this.source.onopen = () => {
      if (generation !== this.generation) return;
      this.reconnectAttempt = 0;
      this.onTransport("connected");
    };
    this.source.addEventListener("snapshot", (event) => {
      if (generation !== this.generation) return;
      this.onTransport("connected");
      this.onSnapshot(JSON.parse(event.data));
    });
    ["event", "heartbeat"].forEach((name) => this.source.addEventListener(name, () => {
      if (generation !== this.generation) return;
      this.onTransport("connected");
      this.#fetch(generation).catch(() => {});
    }));
    this.source.addEventListener("replay_gap", () => this.#reconnect(generation));
    this.source.onerror = () => this.#reconnect(generation);
  }

  #reconnect(generation) {
    if (generation !== this.generation || this.reconnectTimer) return;
    this.source?.close();
    this.onTransport("reconnecting");
    this.reconnectAttempt += 1;
    const delay = Math.min(8000, 900 * (2 ** Math.min(this.reconnectAttempt, 3)));
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      if (generation !== this.generation) return;
      this.#open(generation);
      this.#fetch(generation).catch(() => this.#reconnect(generation));
    }, delay);
  }
}

export { DashboardStream };
