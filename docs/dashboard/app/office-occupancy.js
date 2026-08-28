function distance(left, right) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

class AnchorRegistry {
  constructor(map) {
    this.map = map;
    this.reservations = new Map();
    this.actorAnchors = new Map();
  }

  reserve(actorId, anchorId) {
    const anchor = this.map.anchors[anchorId];
    if (!anchor) throw new Error(`Unknown anchor: ${anchorId}`);
    const occupants = this.reservations.get(anchorId) || new Set();
    if (!occupants.has(actorId) && occupants.size >= (anchor.capacity ?? 1)) {
      throw new Error(`Anchor capacity exceeded: ${anchorId}`);
    }

    for (const [otherActor, otherAnchorId] of this.actorAnchors) {
      if (otherActor === actorId) continue;
      const otherAnchor = this.map.anchors[otherAnchorId];
      if (distance(anchor, otherAnchor) < this.map.minimumActorDistance) {
        throw new Error(`Actor separation violated: ${actorId} → ${anchorId}`);
      }
    }

    this.release(actorId);
    occupants.add(actorId);
    this.reservations.set(anchorId, occupants);
    this.actorAnchors.set(actorId, anchorId);
    return anchor;
  }

  release(actorId) {
    const anchorId = this.actorAnchors.get(actorId);
    if (!anchorId) return;
    const occupants = this.reservations.get(anchorId);
    occupants?.delete(actorId);
    if (!occupants?.size) this.reservations.delete(anchorId);
    this.actorAnchors.delete(actorId);
  }
}

export { AnchorRegistry };
