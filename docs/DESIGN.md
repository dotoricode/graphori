# Graphori Interface Design

## Durable visual world

Graphori uses a white work-order language around an original pixel management-game world. Ink text, cobalt activity, signal orange warnings, and restrained green proof states remain functional rather than decorative. Surfaces are separated by spacing and quiet depth; visible container borders, neon glow, decorative gradients, tiled grid overlays, pill labels, and generic AI-dashboard cards are not part of the system.

One locally bundled SUIT variable font is shared by the dashboard and the learning game. Hierarchy comes from sentence-case copy, weight, scale, and generous spacing rather than multiple display faces or tracked all-caps labels.

## Dashboard mode: Live Office v2

> Graphori Dashboard is not a dashboard containing an office. The office itself is the dashboard.

`docs/dashboard/index.html` is a real-time operations simulation backed by journal projection. At a 1440×900 desktop viewport the Office world owns at least 75% of the available surface and is never placed inside a content card or narrow page. Persistent chrome is limited to a slim live HUD, one clickable event bar, and one verified-progress footer. KPI cards and persistent session lists do not exist.

The entry gate and live surface are two states of the same Office world. The dark curtain disappears in place; it never navigates to a second dashboard. SSE and the initial snapshot start before entry. Run identity and liveness appear once in the HUD, the latest event appears once in the event bar, and verified progress appears once in the footer.

The world contains eleven distinct people: five team leads and six members. Leads represent team coordination and never impersonate a real session. Members receive stable assignments from actual projected nodes; an unassigned member explicitly shows “no actual node assigned.” A room, lead, member, or event opens the same on-demand inspector. The path from person to node to event to producer, payload, digest, and evidence remains available without making those details persistent chrome.

Room signs show the team name and one truthful summary line (`N working`, `blocked`, `complete`, or no assignment) without becoming floating status cards. Significant journal events may produce short, attached dialogue: at most two bubbles on desktop and one on mobile, visible for 3–5 seconds, with a ten-second per-actor cooldown. Dialogue never runs on a timer or heartbeat and never claims information absent from the event, node task, status, or verdict. The Inspector is a fixed overlay drawer above the Office; opening it never changes the world stage position or size.

Character art uses a 48 px visible-body width inside a 96×128 logical frame. Placement is defined by the shared `(48, 120)` foot anchor and each frame's visible alpha bounds; generated source image height never controls world scale. Every actor owns a separate six-state sheet (`idle`, `walk`, `work`, `talk`, `blocked`, `complete`), and all 66 frames must pass artifact, foot-anchor, and frame-bleed QA before runtime use.

`world/office-map.json` is the spatial and interaction contract. It owns room polygons, walkable polygons, blocked furniture, doors, navigation nodes and edges, actor anchors, environmental interactions, z zones, and foreground slices. `OfficeNavigator` performs A* pathfinding on that graph. Actors never choose arbitrary screen coordinates, never cross rooms without a door, and perform work only at an interaction anchor. Waiting people stay at authored idle anchors. Work events move members to work anchors and activate room equipment; passed returns them to idle; blocked stops with a problem signal; stale freezes and desaturates them. Ambient life comes from equipment state, not random roaming.

The client is split at deep module seams:

- `dashboard-state.js` turns a snapshot into truthful teams and assignments.
- `dashboard-stream.js` owns snapshot, SSE, replay-gap, and reconnect behavior.
- `office-navigation.js` hides graph validation and A* routing behind `route()`.
- `office-actions.js` maps semantic status to an authored interaction anchor.
- `office-runtime.js` directs independent actor state machines.
- `office-renderer.js` projects the world without knowing journal semantics.
- `office-inspector.js` owns room, person, event, and journal evidence details.

### Live Office v2 UI contract

- Office scene is at least 75% of a 1440×900 default viewport.
- Persistent bordered panels: at most one; persistent KPI cards: zero.
- Liveness is shown once in the HUD; progress once in the footer; last event once in the event bar.
- Session detail and verdict are visible only after selecting a person, room, or event.
- Gate UI interrupts only when a real gate exists.
- Random actor movement: zero. Actors outside walkable areas: zero. Actors crossing blocked furniture: zero.
- Forbidden: map inside a content card, large unused page margins, duplicated metrics, random waiting movement, sleep as decoration, floating room cards, unexplained gauges, and a card per team.

## Learning mode: experience and read

`docs/GRAPHORI_LEARNING_GAME.html` is an offline interactive flipbook. The learner opens one scene at a time through tabs: the work order, graph map, pixel office, event footprints, questions, and final debrief. Each scene has a next action so the learner can follow the story without a long wall of content. The learner sees the request, presses one clear action, watches the graph fork, selects nodes, compares the design simulation with actual CLI evidence, and receives a three-part debrief: what happened, how it was structured, and why the evidence is trustworthy.

The graph stage uses a dark ink field with flat nodes and real connector lines. The office stage reuses the bright modern company map and the same five human employees. Selecting a character keeps the office scene open and exposes that role's current state, node, output, and evidence directly below the floor. Work, room-bound movement, rest, sleep, and speech explain planning, research, design, implementation, and verification before the learner reads the graph. The page distinguishes current one-worker CLI behavior from the five-role target simulation in copy, labels, event modes, and the final evidence drawer.

## Interaction and motion

- Primary actions are rectangular filled controls with a clear disabled state and keyboard focus ring.
- Selection is shown through a color field or focus ring, never a decorative outline around every tile.
- Motion explains state: sprite-sheet walking frames, room-to-room paths, and role-specific speech communicate the job; reduced-motion mode stops route beats and smooth scrolling while retaining color and text state.
- No animation changes layout, and no repeating decorative background consumes rendering time.

## Responsive rules

- Both surfaces keep a 320px minimum and clip accidental horizontal overflow.
- Grids collapse at 900px and 700px; the office remains one scaled map so room-to-room paths keep their meaning.
- Controls remain at least 44px tall, copy wraps with `overflow-wrap: anywhere`, and the graph's parallel lane stacks on narrow screens.
- Real content remains visible at 320px, 375px, 414px, and 768px without relying on a hover state.

## Truth and evidence

The current baseline is a single generic worker with journal, status/replay verification, dashboard snapshot/SSE, and an optional adapter. Five role teams and true fan-out/fan-in are the intended architecture and are labeled as design simulation until implemented. The visual system must never make simulated activity look like production evidence.
