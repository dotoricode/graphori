import json
import math
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "docs" / "dashboard"
APP = DASH / "app"
WORLD_WIDTH = 1672
WORLD_HEIGHT = 941
WORLD_RATIO = WORLD_WIDTH / WORLD_HEIGHT


def polygon_points(shape):
    return shape.get("polygon", [])


def point_in_polygon(point, polygon):
    x, y = point
    hit = False
    previous = len(polygon) - 1
    for current, (current_x, current_y) in enumerate(polygon):
        previous_x, previous_y = polygon[previous]
        crosses = (current_y > y) != (previous_y > y)
        if crosses:
            edge_x = ((previous_x - current_x) * (y - current_y)
                      / ((previous_y - current_y) or 1e-9) + current_x)
            if x < edge_x:
                hit = not hit
        previous = current
    return hit


def distance_to_segment(point, left, right):
    px, py = point
    ax, ay = left
    bx, by = right
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    ratio = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + ratio * dx), py - (ay + ratio * dy))


def distance_to_polygon(point, polygon):
    return min(
        distance_to_segment(point, polygon[index - 1], polygon[index])
        for index in range(len(polygon))
    )


class DashboardWorldGateTests(unittest.TestCase):
    """Phase 1–4 gate: prove the world before any actor runtime is allowed."""

    @classmethod
    def setUpClass(cls):
        cls.html = (DASH / "index.html").read_text(encoding="utf-8")
        cls.css = (DASH / "style.css").read_text(encoding="utf-8")
        cls.entry = (DASH / "app.js").read_text(encoding="utf-8")
        cls.modules = {path.name: path.read_text(encoding="utf-8") for path in APP.glob("*.js")}
        cls.all_js = "\n".join(cls.modules.values())
        cls.office_map = json.loads((DASH / "world" / "office-map.json").read_text(encoding="utf-8"))

    def test_world_uses_one_canonical_coordinate_system(self):
        self.assertEqual(self.office_map["schema_version"], 3)
        self.assertEqual(self.office_map["world"], {"width": WORLD_WIDTH, "height": WORLD_HEIGHT})
        self.assertEqual(self.html.count('id="office-world"'), 1)
        self.assertEqual(self.html.count("office-background.webp"), 1)
        self.assertIn('width="1672"', self.html)
        self.assertIn('height="941"', self.html)
        self.assertIn("width: 1672px", self.css)
        self.assertIn("height: 941px", self.css)
        self.assertNotIn("object-fit: fill", self.css)

    def test_public_dashboard_selects_english_or_korean_at_presentation_boundary(self):
        self.assertIn('from "./i18n.js"', self.modules["main.js"])
        self.assertIn('from "./i18n.js"', self.modules["office-ui.js"])
        self.assertIn('.get("lang")', self.modules["i18n.js"])
        self.assertIn('table?.[key]?.[language]', self.modules["i18n.js"])
        self.assertNotIn('toLocaleTimeString("ko-KR"', self.modules["office-ui.js"])
        self.assertNotIn('"검증 출처"', self.modules["office-ui.js"])
        self.assertNotIn('"작업 강도"', self.modules["office-ui.js"])

    def test_uniform_transform_preserves_ratio_for_required_viewports(self):
        script = f"""
          import {{ computeWorldTransform }} from '{(APP / 'world-stage.js').as_uri()}';
          const views = [[1920,1080],[1440,900],[1280,720],[1024,768],[390,844]];
          const world = {{ width: {WORLD_WIDTH}, height: {WORLD_HEIGHT} }};
          for (const [width, height] of views) {{
            const result = computeWorldTransform(width, height, world);
            const renderedRatio = (world.width * result.scale) / (world.height * result.scale);
            if (Math.abs(renderedRatio / ({WORLD_RATIO}) - 1) > 0.005) process.exit(10);
            if (result.scaleX !== result.scale || result.scaleY !== result.scale) process.exit(11);
          }}
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_desktop_world_starts_at_the_top_and_uses_available_height(self):
        script = f"""
          import {{ computeWorldTransform }} from '{(APP / 'world-stage.js').as_uri()}';
          const world = {{ width: {WORLD_WIDTH}, height: {WORLD_HEIGHT} }};
          for (const [width, height] of [[1920,1012],[1440,832],[1280,652],[1024,700]]) {{
            const result = computeWorldTransform(width, height, world, {{ layoutMode: 'top' }});
            if (result.offsetY !== 0) process.exit(30);
            if (Math.abs(Math.max(result.renderedWidth / width, result.renderedHeight / height) - 1) > 1e-9) process.exit(31);
          }}
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_debug_world_is_real_geometry_in_the_world_stage(self):
        for token in ('id="debug-geometry"', 'id="debug-actors"', 'viewBox="0 0 1672 941"', 'id="debug-legend"'):
            self.assertIn(token, self.html)
        self.assertIn('params.get("debug-world") === "1"', self.modules["main.js"])
        self.assertIn("renderDebugWorld", self.modules["debug-world.js"])
        self.assertIn('dataset.renderedGeometry', self.modules["debug-world.js"])
        self.assertIn('dataset.debugReady = "true"', self.modules["main.js"])
        self.assertIn("debug-walkable", self.css)
        self.assertIn("debug-blocked", self.css)
        self.assertIn("debug-door", self.css)
        self.assertIn("debug-anchor", self.css)
        self.assertIn("debug-interaction", self.css)
        self.assertIn("debug-foot", self.css)

    def test_debug_scene_has_eleven_actors_and_path_inspector(self):
        self.assertEqual(len(self.office_map["debugActors"]), 11)
        self.assertIn('id="path-inspector"', self.html)
        self.assertIn('id="path-source"', self.html)
        self.assertIn('id="path-destination"', self.html)
        self.assertIn('id="play-path"', self.html)
        self.assertIn('data-route-set="required"', self.html)
        self.assertIn("class OfficeNavigator", self.modules["office-navigation.js"])
        self.assertIn("navigator.route", self.modules["debug-world.js"])
        self.assertIn("traceRequiredRoutes", self.modules["debug-world.js"])
        self.assertIn("pathKeyframes", self.modules["debug-world.js"])
        self.assertIn("controls.play.addEventListener", self.modules["debug-world.js"])
        self.assertIn("debug-actor-sprite", self.css)
        self.assertIn("debug-destination", self.css)

    def test_debug_controls_can_isolate_each_world_layer(self):
        expected = {
            "walkable", "blocked", "doors", "anchors", "anchor-names",
            "actors", "actor-names", "actor-radius", "path", "rooms",
        }
        for layer in expected:
            self.assertIn(f'data-debug-toggle="{layer}"', self.html)
        self.assertIn("bindDebugToggles", self.modules["debug-world.js"])

    def test_navigation_has_named_nodes_and_real_door_portals(self):
        navigation = self.office_map["navigation"]
        self.assertGreaterEqual(len(navigation["nodes"]), 35)
        self.assertGreaterEqual(len(navigation["edges"]), 34)
        for door in self.office_map["doors"]:
            self.assertEqual(len(door["portal"]), 2)
            self.assertNotIn("polygon", door)
            self.assertIn(door["normal"], {"north", "south", "east", "west"})
            self.assertLessEqual(
                math.dist(*door["portal"]),
                100,
                (door["id"], "portal is wider than the visible opening"),
            )
            self.assertIn(door["insideNode"], navigation["nodes"])
            self.assertIn(door["outsideNode"], navigation["nodes"])
            inside = navigation["nodes"][door["insideNode"]]
            outside = navigation["nodes"][door["outsideNode"]]
            portal_midpoint = (
                (door["portal"][0][0] + door["portal"][1][0]) / 2,
                (door["portal"][0][1] + door["portal"][1][1]) / 2,
            )
            self.assertLessEqual(
                distance_to_segment(
                    portal_midpoint,
                    (inside["x"], inside["y"]),
                    (outside["x"], outside["y"]),
                ),
                self.office_map["actorRadius"],
                (door["id"], "door edge misses the visible portal"),
            )
            edge = [door["insideNode"], door["outsideNode"]]
            reverse = list(reversed(edge))
            self.assertTrue(edge in navigation["edges"] or reverse in navigation["edges"], door["id"])

    def test_every_navigation_edge_is_sampled_inside_walkable_floor(self):
        nodes = self.office_map["navigation"]["nodes"]
        doors = {door["id"] for door in self.office_map["doors"]}
        for left_id, right_id in self.office_map["navigation"]["edges"]:
            left, right = nodes[left_id], nodes[right_id]
            length = math.hypot(right["x"] - left["x"], right["y"] - left["y"])
            samples = max(1, math.ceil(length / 4))
            edge_doors = {left.get("door"), right.get("door")} & doors
            for index in range(samples + 1):
                ratio = index / samples
                point = (
                    left["x"] + (right["x"] - left["x"]) * ratio,
                    left["y"] + (right["y"] - left["y"]) * ratio,
                )
                walkable = any(point_in_polygon(point, area["polygon"]) for area in self.office_map["walkable"])
                blocked = any(point_in_polygon(point, area["polygon"]) for area in self.office_map["blocked"])
                in_door = any(
                    door["id"] in edge_doors
                    and (
                        distance_to_segment(point, *door["portal"]) <= self.office_map["actorRadius"]
                        or (
                            {left_id, right_id} == {door["insideNode"], door["outsideNode"]}
                        )
                    )
                    for door in self.office_map["doors"]
                )
                in_door = in_door or bool(left.get("portalNode") or right.get("portalNode"))
                self.assertTrue(walkable or in_door, (left_id, right_id, point, "not walkable"))
                clearance = min(
                    0 if point_in_polygon(point, area["polygon"]) else distance_to_polygon(point, area["polygon"])
                    for area in self.office_map["blocked"]
                )
                self.assertFalse(blocked, (left_id, right_id, point, "blocked"))
                portal_approach = (
                    (left.get("portalNode") and right.get("portalApproach"))
                    or (right.get("portalNode") and left.get("portalApproach"))
                )
                if not in_door and not portal_approach:
                    self.assertGreaterEqual(
                        clearance,
                        self.office_map["actorRadius"],
                        (left_id, right_id, point, "inside expanded blocked geometry"),
                    )

    def test_required_cross_room_paths_use_both_room_doors(self):
        script = f"""
          import {{ OfficeNavigator }} from '{(APP / 'office-navigation.js').as_uri()}';
          import fs from 'node:fs';
          const map = JSON.parse(fs.readFileSync('{(DASH / 'world' / 'office-map.json').as_posix()}', 'utf8'));
          const navigator = new OfficeNavigator(map);
          const checks = [
            ['plan-lead-idle-node', 'verification-member-work-node', ['plan-door-in', 'plan-door-out', 'verify-door-out', 'verify-door-in']],
            ['research-member-idle-node', 'engineering-member-a-work-node', ['research-door-in', 'research-door-out', 'implement-door-out', 'implement-door-in']],
            ['design-member-idle-node', 'plan-lead-work-node', ['design-door-in', 'design-door-out', 'plan-door-out', 'plan-door-in']],
          ];
          for (const [start, end, expected] of checks) {{
            const ids = navigator.route(start, end).map((point) => point.id);
            if (!expected.every((id) => ids.includes(id))) process.exit(20);
          }}
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_same_room_route_preserves_endpoints_and_never_takes_a_large_detour(self):
        script = f"""
          import {{ OfficeNavigator }} from '{(APP / 'office-navigation.js').as_uri()}';
          import fs from 'node:fs';
          const map = JSON.parse(fs.readFileSync('{(DASH / 'world' / 'office-map.json').as_posix()}', 'utf8'));
          const navigator = new OfficeNavigator(map);
          const path = navigator.route('plan-lead-idle-node', 'plan-lead-work-node');
          const start = map.debugActorFeet['planning-lead'];
          const destination = map.anchors['plan-lead-work'];
          const distance = (left, right) => Math.hypot(left.x - right.x, left.y - right.y);
          const length = path.slice(1).reduce((sum, point, index) => sum + distance(path[index], point), 0);
          const direct = distance(start, destination);
          if (distance(path[0], start) > 2) process.exit(50);
          if (distance(path.at(-1), destination) > 2) process.exit(51);
          if (length > direct * 1.25) process.exit(52);
          if (path[0].id !== 'plan-lead-idle-node') process.exit(53);
          if (path.at(-1).id !== 'plan-lead-work-node') process.exit(54);
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_cross_room_routes_report_door_ids_in_order(self):
        script = f"""
          import {{ OfficeNavigator }} from '{(APP / 'office-navigation.js').as_uri()}';
          import fs from 'node:fs';
          const map = JSON.parse(fs.readFileSync('{(DASH / 'world' / 'office-map.json').as_posix()}', 'utf8'));
          const navigator = new OfficeNavigator(map);
          const route = navigator.route('plan-lead-idle-node', 'verification-member-work-node');
          const doors = navigator.doorIds(route);
          if (JSON.stringify(doors) !== JSON.stringify(['door-plan-south', 'door-verify-west'])) process.exit(60);
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_all_required_routes_preserve_actor_start_and_anchor_destination(self):
        script = f"""
          import {{ OfficeNavigator }} from '{(APP / 'office-navigation.js').as_uri()}';
          import fs from 'node:fs';
          const map = JSON.parse(fs.readFileSync('{(DASH / 'world' / 'office-map.json').as_posix()}', 'utf8'));
          const navigator = new OfficeNavigator(map);
          const actors = new Map(map.debugActors.map((actor) => [actor.id, actor]));
          const checks = [
            ['planning-lead', 'verification-member-work', ['door-plan-south', 'door-verify-west']],
            ['research-member-a', 'engineering-member-a-work', ['door-research-west', 'door-implement-south']],
            ['design-member-a', 'plan-lead-work', ['door-design-west', 'door-plan-south']],
          ];
          const distance = (left, right) => Math.hypot(left.x - right.x, left.y - right.y);
          for (const [actorId, anchorId, expectedDoors] of checks) {{
            const actor = actors.get(actorId);
            const foot = map.debugActorFeet[actorId];
            const destination = map.anchors[anchorId];
            const path = navigator.route(actor.node, `${{anchorId}}-node`);
            if (distance(path[0], foot) > 2) process.exit(70);
            if (distance(path.at(-1), destination) > 2) process.exit(71);
            if (JSON.stringify(navigator.doorIds(path)) !== JSON.stringify(expectedDoors)) process.exit(72);
          }}
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_interaction_destination_nodes_end_at_the_authored_anchor(self):
        nodes = self.office_map["navigation"]["nodes"]
        for interaction in self.office_map["interactions"].values():
            anchor = self.office_map["anchors"][interaction["anchor"]]
            node = nodes[f'{interaction["anchor"]}-node']
            self.assertEqual((node["x"], node["y"]), (anchor["x"], anchor["y"]), interaction["id"])

    def test_all_geometry_stays_inside_the_world(self):
        groups = ("rooms", "walkable", "blocked", "zZones")
        for group in groups:
            items = self.office_map[group].values() if isinstance(self.office_map[group], dict) else self.office_map[group]
            for item in items:
                for x, y in polygon_points(item):
                    self.assertGreaterEqual(x, 0, (group, item.get("id"), x, y))
                    self.assertLessEqual(x, WORLD_WIDTH, (group, item.get("id"), x, y))
                    self.assertGreaterEqual(y, 0, (group, item.get("id"), x, y))
                    self.assertLessEqual(y, WORLD_HEIGHT, (group, item.get("id"), x, y))
        for collection in ("anchors", "interactions", "debugActorFeet"):
            for item in self.office_map[collection].values():
                self.assertGreaterEqual(item["x"], 0)
                self.assertLessEqual(item["x"], WORLD_WIDTH)
                self.assertGreaterEqual(item["y"], 0)
                self.assertLessEqual(item["y"], WORLD_HEIGHT)

    def test_authored_feet_and_destinations_never_start_inside_furniture(self):
        for collection in ("anchors", "debugActorFeet"):
            for item in self.office_map[collection].values():
                if item.get("debugOnly"):
                    continue
                point = (item["x"], item["y"])
                self.assertTrue(
                    any(point_in_polygon(point, area["polygon"]) for area in self.office_map["walkable"]),
                    (collection, item["id"], "not walkable"),
                )
                self.assertFalse(
                    any(point_in_polygon(point, area["polygon"]) for area in self.office_map["blocked"]),
                    (collection, item["id"], "inside blocked geometry"),
                )
                clearance = min(
                    0 if point_in_polygon(point, area["polygon"]) else distance_to_polygon(point, area["polygon"])
                    for area in self.office_map["blocked"]
                )
                self.assertGreaterEqual(
                    clearance,
                    self.office_map["actorRadius"],
                    (collection, item["id"], "inside expanded blocked geometry"),
                )

    def test_debug_actors_have_unique_anchors_and_visible_foot_separation(self):
        actors = self.office_map["debugActors"]
        anchors = [actor["anchor"] for actor in actors]
        self.assertEqual(len(anchors), len(set(anchors)))

        sprite_width = self.office_map["actorSprite"]["displayWidth"]
        minimum_distance = self.office_map["minimumActorDistance"]
        self.assertGreaterEqual(minimum_distance, sprite_width * .7)
        feet = self.office_map["debugActorFeet"]
        for index, left in enumerate(actors):
            left_foot = feet[left["id"]]
            anchor = self.office_map["anchors"][left["anchor"]]
            self.assertEqual(
                (left_foot["x"], left_foot["y"]),
                (anchor["x"], anchor["y"]),
                left["id"],
            )
            for right in actors[index + 1:]:
                right_foot = feet[right["id"]]
                distance = math.hypot(
                    right_foot["x"] - left_foot["x"],
                    right_foot["y"] - left_foot["y"],
                )
                self.assertGreaterEqual(
                    distance,
                    minimum_distance,
                    (left["id"], right["id"], distance),
                )

    def test_anchor_registry_enforces_capacity_and_minimum_distance(self):
        self.assertIn("office-occupancy.js", self.modules)
        script = f"""
          import {{ AnchorRegistry }} from '{(APP / 'office-occupancy.js').as_uri()}';
          import fs from 'node:fs';
          const map = JSON.parse(fs.readFileSync('{(DASH / 'world' / 'office-map.json').as_posix()}', 'utf8'));
          const registry = new AnchorRegistry(map);
          registry.reserve('planning-lead', 'plan-lead-idle');
          let capacityRejected = false;
          try {{ registry.reserve('planning-member-a', 'plan-lead-idle'); }} catch {{ capacityRejected = true; }}
          if (!capacityRejected) process.exit(40);
          let distanceRejected = false;
          try {{ registry.reserve('planning-member-a', 'plan-member-too-close'); }} catch {{ distanceRejected = true; }}
          if (!distanceRejected) process.exit(41);
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_path_is_one_readable_non_scaling_polyline(self):
        debug_js = self.modules["debug-world.js"]
        self.assertEqual(debug_js.count('svgElement("polyline"'), 1)
        self.assertIn('"vector-effect": "non-scaling-stroke"', debug_js)
        self.assertIn("stroke-width: 2.5", self.css)
        self.assertNotIn("marker-end", self.css.split(".debug-path", 1)[1].split("}", 1)[0])

    def test_runtime_navigation_rejects_unsafe_sampled_edges(self):
        navigation_js = self.modules["office-navigation.js"]
        self.assertIn("#assertSafeSegment", navigation_js)
        self.assertIn("Math.ceil(length / 4)", navigation_js)
        self.assertIn("clearance < this.map.actorRadius", navigation_js)

    def test_actor_radius_is_rendered_for_every_debug_actor(self):
        self.assertIn("debug-actor-radius", self.css)
        self.assertIn('"debug-actor-radius"', self.modules["debug-world.js"])
        self.assertIn("map.minimumActorDistance", self.modules["office-occupancy.js"])

    def test_actor_radius_matches_the_authored_logical_body_width(self):
        logical_width = self.office_map["actorSprite"]["logicalWidth"]
        ratio = self.office_map["actorRadius"] / logical_width
        self.assertGreaterEqual(ratio, .3)
        self.assertLessEqual(ratio, .4)

    def test_each_door_center_is_walkable_and_clear_of_blocked_geometry(self):
        for door in self.office_map["doors"]:
            self.assertEqual(door["fromRoom"], door["room"])
            self.assertEqual(door["toRoom"], "corridor")
            center = (
                (door["portal"][0][0] + door["portal"][1][0]) / 2,
                (door["portal"][0][1] + door["portal"][1][1]) / 2,
            )
            self.assertTrue(
                any(point_in_polygon(center, area["polygon"]) for area in self.office_map["walkable"]),
                (door["id"], "center is not walkable"),
            )
            self.assertFalse(
                any(point_in_polygon(center, area["polygon"]) for area in self.office_map["blocked"]),
                (door["id"], "center intersects blocked geometry"),
            )

    def test_actor_runtime_is_semantic_and_contains_no_legacy_roaming(self):
        self.assertIn("office-runtime.js", self.modules)
        self.assertIn("office-director.js", self.modules)
        self.assertIn("projectOffice", self.modules["office-director.js"])
        self.assertIn("applySnapshot", self.modules["office-runtime.js"])
        for token in ("random", "wander", "roam", "sleep", "safe rectangle", "atlas-row"):
            self.assertNotIn(token, self.all_js.lower())
        self.assertIn('id="actor-layer"', self.html)
        self.assertNotIn("office-people-atlas.png", self.html + self.css + self.all_js)

    def test_runtime_character_manifest_has_eleven_six_state_sheets(self):
        manifest = json.loads((DASH / "characters" / "runtime" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["cell"], {"width": 96, "height": 128})
        self.assertEqual(manifest["visibleBodyWidth"], 48)
        self.assertEqual(manifest["footAnchor"], {"x": 48, "y": 120})
        self.assertEqual(manifest["states"], ["idle", "walk", "work", "talk", "blocked", "complete"])
        self.assertEqual(len(manifest["actors"]), 11)
        for actor_id, actor in manifest["actors"].items():
            self.assertEqual(set(actor["frames"]), set(manifest["states"]), actor_id)
            self.assertTrue((DASH / actor["sheet"].replace("./", "")).is_file(), actor_id)

    def test_all_sixty_six_frames_pass_artifact_anchor_and_bleed_qa(self):
        report = json.loads(
            (DASH / "qa" / "character-art" / "runtime" / "character-sprite-report.json")
            .read_text(encoding="utf-8")
        )
        self.assertTrue(report["summary"]["pass"], report["summary"]["failures"])
        self.assertEqual(report["summary"]["actorCount"], 11)
        self.assertEqual(report["summary"]["frameCount"], 66)
        for states in report["actors"].values():
            for checks in states.values():
                self.assertTrue(checks["artifactPass"])
                self.assertTrue(checks["footAnchorPass"])
                self.assertTrue(checks["frameBleedPass"])

    def test_director_keeps_unassigned_members_idle_and_leads_non_node(self):
        script = f"""
          import {{ projectOffice }} from '{(APP / 'office-director.js').as_uri()}';
          const snapshot = {{ nodes: [
            {{ id: 'worker-1', role: 'worker', status: 'running', current_task: 'Build projection' }}
          ] }};
          const projected = projectOffice(snapshot).actors;
          const lead = projected.find((actor) => actor.id === 'engineering-lead');
          const first = projected.find((actor) => actor.id === 'engineering-member-a');
          const second = projected.find((actor) => actor.id === 'engineering-member-b');
          if (lead.node !== null || lead.state !== 'talk' || lead.anchor !== lead.idle) process.exit(80);
          if (first.node?.id !== 'worker-1' || first.state !== 'work') process.exit(81);
          if (second.node !== null || second.state !== 'idle') process.exit(82);
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_canonical_projection_controls_team_and_actual_agent_assignment(self):
        script = f"""
          import {{ projectOffice, teamForNode }} from '{(APP / 'office-director.js').as_uri()}';
          const snapshot = {{
            schema_version: 3,
            teams: [
              {{ team_id: 'research', status: 'active', active_node_count: 1, total_node_count: 1 }},
              {{ team_id: 'design', status: 'standby', active_node_count: 0, total_node_count: 1 }},
            ],
            nodes: [
              {{ node_id: 'r1', id: 'r1', team_id: 'research', role: 'worker', status: 'running' }},
              {{ node_id: 'd1', id: 'd1', team_id: 'design', role: 'worker', status: 'pending' }},
            ],
            assignments: [{{ node_id: 'r1', actor_id: 'role_worker_r1', active: true }}],
          }};
          const projection = projectOffice(snapshot);
          const research = projection.actors.find((actor) => actor.id === 'research-member-a');
          const design = projection.actors.find((actor) => actor.id === 'design-member-a');
          if (teamForNode(snapshot.nodes[0]) !== 'research') process.exit(83);
          if (research.node?.node_id !== 'r1' || research.state !== 'work') process.exit(84);
          if (design.node !== null || design.state !== 'idle') process.exit(85);
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_inspector_uses_canonical_graph_execution_and_verification_fields(self):
        self.assertIn('id="graph-summary"', self.html)
        ui = self.modules["office-ui.js"]
        for token in (
            "requested_model", "selected_route", "node.execution?.status",
            "node.verification?.status", "node.dependencies", "node.evidence_ids",
            "snapshot?.edges", "snapshot?.gates", "actual_agent_count",
        ):
            self.assertIn(token, ui)

    def test_production_debug_layers_cannot_intercept_actor_clicks(self):
        self.assertIn('.debug-layer {', self.css)
        self.assertIn('display: none', self.css)
        self.assertIn('body[data-debug-world="true"] .debug-layer { display: block; }', self.css)

    def test_runtime_navigation_avoids_stationary_actors_without_direct_fallback(self):
        runtime = self.modules["office-runtime.js"]
        navigation = self.modules["office-navigation.js"]
        self.assertIn("#movementPlan", runtime)
        self.assertIn("Actor-safe movement plan is unavailable", runtime)
        self.assertIn("segmentClearOfActors", navigation)
        self.assertNotIn("transition(start, destination)", runtime)

    def test_dialogue_is_event_driven_truthful_and_bounded(self):
        runtime = self.modules["office-runtime.js"]
        self.assertIn("DIALOGUE_EVENTS", runtime)
        self.assertIn("dialogueForEvent", runtime)
        self.assertIn("event.node_id", runtime)
        self.assertIn("current_task", runtime)
        self.assertIn("10000", runtime)
        self.assertIn("4600", runtime)
        for token in ("Math.random", "setInterval", "heartbeat"):
            self.assertNotIn(token, runtime)

    def test_room_signs_expose_one_truthful_status_line(self):
        runtime = self.modules["office-runtime.js"]
        self.assertIn("teamStatus", runtime)
        self.assertIn("projection.teamsByVisualId.get(team)", runtime)
        self.assertNotIn("teamStatus(projection.actors", runtime)
        self.assertIn("명 작업 중", runtime)
        self.assertIn("건 막힘", runtime)
        self.assertIn("작업 완료", runtime)
        self.assertIn("button.querySelector(\"small\")", runtime)

    def test_inspector_is_overlay_and_does_not_resize_world(self):
        inspector_rule = self.css[self.css.index(".office-inspector {"):]
        inspector_rule = inspector_rule[:inspector_rule.index("}")]
        self.assertIn("position: fixed", inspector_rule)
        self.assertNotIn("width: calc", inspector_rule)
        self.assertNotIn("margin", inspector_rule)

    def test_live_ui_is_office_first_without_kpi_cards(self):
        self.assertIn('id="live-footer"', self.html)
        self.assertIn('id="event-ticker"', self.html)
        self.assertIn('id="office-inspector"', self.html)
        self.assertNotIn("status-card", self.html)
        self.assertNotIn("kpi", self.html.lower())
        design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8").lower()
        self.assertIn("persistent kpi cards: zero", design)

    def test_connect_and_live_are_distinct_states(self):
        self.assertIn('data-ui-state="connect"', self.html)
        self.assertIn('id="connect-panel"', self.html)
        self.assertIn("max-width: 420px", self.css)
        self.assertIn('params.get("demo") === "1"', self.modules["main.js"])
        self.assertIn('panel.hidden = true', self.modules["main.js"])
        self.assertNotIn("entry-curtain", self.html + self.css + self.all_js)

    def test_desktop_stage_is_one_viewport_without_page_scroll(self):
        self.assertIn("height: 100dvh", self.css)
        self.assertIn("overflow: hidden", self.css)
        self.assertNotIn("min-height: 100svh", self.css)
        self.assertNotIn("fullPage", self.all_js)
        self.assertIn("--hud-height", self.css)
        self.assertIn("--stage-gap", self.css)
        self.assertIn("layoutMode: \"top\"", self.modules["world-stage.js"])

    @unittest.skipUnless(shutil.which("sips"), "sips image probe is macOS-only")
    def test_background_asset_matches_canonical_world(self):
        completed = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(DASH / "world" / "office-background.webp")],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn(f"pixelWidth: {WORLD_WIDTH}", completed.stdout)
        self.assertIn(f"pixelHeight: {WORLD_HEIGHT}", completed.stdout)


if __name__ == "__main__":
    unittest.main()
