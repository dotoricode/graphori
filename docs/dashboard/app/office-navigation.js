function distance(left, right) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

function pointInPolygon(point, polygon) {
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
    const [currentX, currentY] = polygon[index];
    const [previousX, previousY] = polygon[previous];
    if ((currentY > point.y) !== (previousY > point.y)
      && point.x < ((previousX - currentX) * (point.y - currentY)) / ((previousY - currentY) || Number.EPSILON) + currentX) {
      inside = !inside;
    }
  }
  return inside;
}

function distanceToSegment(point, left, right) {
  const dx = right.x - left.x;
  const dy = right.y - left.y;
  if (!dx && !dy) return distance(point, left);
  const ratio = Math.max(0, Math.min(1,
    ((point.x - left.x) * dx + (point.y - left.y) * dy) / (dx * dx + dy * dy)));
  return distance(point, { x: left.x + ratio * dx, y: left.y + ratio * dy });
}

function clearanceFromPolygon(point, polygon) {
  if (pointInPolygon(point, polygon)) return 0;
  return Math.min(...polygon.map(([x, y], index) => {
    const [previousX, previousY] = polygon[index ? index - 1 : polygon.length - 1];
    return distanceToSegment(point, { x, y }, { x: previousX, y: previousY });
  }));
}

function segmentClearOfActors(left, right, actors, minimumDistance) {
  if (!actors?.length) return true;
  const length = distance(left, right);
  const samples = Math.max(1, Math.ceil(length / 3));
  for (let index = 0; index <= samples; index += 1) {
    const ratio = index / samples;
    const point = {
      x: left.x + (right.x - left.x) * ratio,
      y: left.y + (right.y - left.y) * ratio,
    };
    if (actors.some((actor) => distance(point, actor) < minimumDistance)) return false;
  }
  return true;
}

class OfficeNavigator {
  constructor(map) {
    this.map = map;
    this.nodes = map.navigation.nodes;
    this.graph = new Map(Object.keys(this.nodes).map((id) => [id, []]));
    map.navigation.edges.forEach(([left, right]) => {
      if (!this.graph.has(left) || !this.graph.has(right)) throw new Error(`Unknown navigation edge: ${left} → ${right}`);
      this.#assertSafeSegment(left, right);
      this.graph.get(left).push(right);
      this.graph.get(right).push(left);
    });
  }

  #assertSafeSegment(leftId, rightId) {
    const left = this.nodes[leftId];
    const right = this.nodes[rightId];
    const doorId = left.door && left.door === right.door ? left.door : null;
    const directDoorEdge = Boolean(doorId && left.portalNode && right.portalNode);
    const portalEdge = Boolean(left.portalNode || right.portalNode);
    const length = distance(left, right);
    const samples = Math.max(1, Math.ceil(length / 4));

    for (let index = 0; index <= samples; index += 1) {
      const ratio = index / samples;
      const point = {
        x: left.x + (right.x - left.x) * ratio,
        y: left.y + (right.y - left.y) * ratio,
      };
      const walkable = this.map.walkable.some((area) => pointInPolygon(point, area.polygon));
      const blocked = this.map.blocked.some((area) => pointInPolygon(point, area.polygon));
      const clearance = Math.min(...this.map.blocked.map((area) => clearanceFromPolygon(point, area.polygon)));
      if ((!walkable && !portalEdge) || (!directDoorEdge && blocked) || (!portalEdge && clearance < this.map.actorRadius)) {
        throw new Error(`Unsafe navigation edge: ${leftId} → ${rightId}`);
      }
    }
  }

  route(startNode, destinationNode, { actors = [], minimumDistance = this.map.minimumActorDistance } = {}) {
    if (!this.nodes[startNode] || !this.nodes[destinationNode]) throw new Error("Unknown route endpoint");
    const open = new Set([startNode]);
    const cameFrom = new Map();
    const score = new Map([[startNode, 0]]);
    const estimate = new Map([[startNode, distance(this.nodes[startNode], this.nodes[destinationNode])]]);

    while (open.size) {
      const current = [...open].sort((left, right) => (estimate.get(left) ?? Infinity) - (estimate.get(right) ?? Infinity))[0];
      if (current === destinationNode) return this.#points(this.#reconstruct(cameFrom, current));
      open.delete(current);
      this.graph.get(current).forEach((neighbor) => {
        if (!segmentClearOfActors(this.nodes[current], this.nodes[neighbor], actors, minimumDistance)) return;
        const tentative = (score.get(current) ?? Infinity) + distance(this.nodes[current], this.nodes[neighbor]);
        if (tentative >= (score.get(neighbor) ?? Infinity)) return;
        cameFrom.set(neighbor, current);
        score.set(neighbor, tentative);
        estimate.set(neighbor, tentative + distance(this.nodes[neighbor], this.nodes[destinationNode]));
        open.add(neighbor);
      });
    }
    throw new Error(`No office route: ${startNode} → ${destinationNode}`);
  }

  doorIds(path) {
    const result = [];
    path.forEach((point) => {
      if (point.door && point.door !== result.at(-1)) result.push(point.door);
    });
    return result;
  }

  #reconstruct(cameFrom, current) {
    const path = [current];
    while (cameFrom.has(current)) {
      current = cameFrom.get(current);
      path.unshift(current);
    }
    return path;
  }

  #points(ids) {
    return ids.map((id) => ({ id, ...this.nodes[id] }));
  }
}

export { OfficeNavigator, segmentClearOfActors };
