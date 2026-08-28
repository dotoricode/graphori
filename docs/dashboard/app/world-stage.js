function computeWorldTransform(viewportWidth, viewportHeight, world, options = {}) {
  const scale = Math.min(viewportWidth / world.width, viewportHeight / world.height);
  const renderedWidth = world.width * scale;
  const renderedHeight = world.height * scale;
  const layoutMode = options.layoutMode || "top";
  return {
    scale,
    scaleX: scale,
    scaleY: scale,
    offsetX: (viewportWidth - renderedWidth) / 2,
    offsetY: layoutMode === "top" ? 0 : (viewportHeight - renderedHeight) / 2,
    renderedWidth,
    renderedHeight,
  };
}

class WorldStage {
  constructor(viewport, worldElement, world) {
    this.viewport = viewport;
    this.worldElement = worldElement;
    this.scrollSpace = worldElement.parentElement;
    this.world = world;
    this.options = { layoutMode: "top" };
    this.observer = new ResizeObserver(() => this.layout());
  }

  start() {
    this.observer.observe(this.viewport);
    this.layout();
  }

  stop() {
    this.observer.disconnect();
  }

  layout() {
    const rect = this.viewport.getBoundingClientRect();
    const mobilePan = rect.width <= 700;
    const compactDesktop = !mobilePan && rect.height >= 700 && rect.width / rect.height < this.world.width / this.world.height;
    const transform = mobilePan
      ? {
        scale: rect.height / this.world.height,
        scaleX: rect.height / this.world.height,
        scaleY: rect.height / this.world.height,
        offsetX: 0,
        offsetY: 0,
        renderedWidth: this.world.width * rect.height / this.world.height,
        renderedHeight: rect.height,
      }
      : computeWorldTransform(rect.width, rect.height, this.world, {
        ...this.options,
        layoutMode: compactDesktop ? "center" : this.options.layoutMode,
      });
    this.worldElement.style.setProperty("--world-scale", String(transform.scale));
    this.worldElement.style.setProperty("--world-offset-x", `${transform.offsetX}px`);
    this.worldElement.style.setProperty("--world-offset-y", `${transform.offsetY}px`);
    this.worldElement.dataset.worldScale = String(transform.scale);
    this.worldElement.dataset.renderedWidth = String(transform.renderedWidth);
    this.worldElement.dataset.renderedHeight = String(transform.renderedHeight);
    this.scrollSpace.style.width = `${mobilePan ? transform.renderedWidth : rect.width}px`;
    this.scrollSpace.style.height = `${mobilePan ? transform.renderedHeight : rect.height}px`;
    this.viewport.classList.toggle("is-mobile-pan", mobilePan);
    if (mobilePan) {
      window.requestAnimationFrame(() => {
        if (!this.viewport.dataset.initialPanApplied) {
          this.viewport.scrollLeft = Math.max(0, (transform.renderedWidth - rect.width) / 2);
          this.viewport.dataset.initialPanApplied = "true";
        }
      });
    } else {
      delete this.viewport.dataset.initialPanApplied;
      this.viewport.scrollLeft = 0;
    }
  }
}

export { WorldStage, computeWorldTransform };
