import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "docs" / "GRAPHORI_LEARNING_GAME.html"


class LearningGameContractTests(unittest.TestCase):
    def setUp(self):
        self.html = GAME.read_text(encoding="utf-8")

    def test_teaches_planning_owned_async_dashboard(self):
        for phrase in (
            "학습용 관제",
            "오프라인",
            "기획팀",
            "비동기",
            "학습용 PULSE",
            "window.setInterval(syncLearningPulse, 1800)",
            "실제 CLI는 worker 1개",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)

    def test_teaches_graph_parallelism_and_fan_in(self):
        for phrase in (
            "기획팀 / ROUTER",
            "정보조사팀 / RESEARCH",
            "구현팀 / WORKER",
            "검증팀 / VERIFIER",
            "fan-in",
            "parallel_started",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)

    def test_opens_completion_explanation_with_real_evidence(self):
        for phrase in (
            "실제 산출물 · 읽기 쉬운 완료 보고",
            "terminal_status = succeeded",
            '"event_count": 10',
            '"learning-success"',
            '"replay_verified": true',
            '"independent_verdict": "pending"',
            "코드 diff 대신",
            "run_completed",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)

    def test_event_labels_wrap_without_colliding_with_explanations(self):
        for phrase in ("grid-template-columns: minmax(0, 9rem) minmax(0, 1fr)", "overflow-wrap: anywhere", ".event-copy { min-width: 0"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)

    def test_interactive_controls_expose_truth_and_selection(self):
        for phrase in (
            'role="log"',
            'aria-atomic="true"',
            'data-mode="actual" aria-pressed="false"',
            'data-upgrade="parallel" aria-pressed="false"',
            "현재는 worker 하나",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)
        self.assertNotIn("fonts.googleapis.com", self.html)
        self.assertNotIn("이제 네가 작업 지시자가 되어 보세요", self.html)

    def test_game_uses_scene_tabs_and_finished_pixel_sprites(self):
        for phrase in (
            'role="tablist"',
            'data-tab-panel="map"',
            'data-tab-panel="office"',
            'data-tab-panel="check"',
            'company-roaming',
            'graphori-human-team-v4.png',
            'function renderMessenger',
            'function renderTabs',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)

    def test_office_selection_explains_role_without_leaving_the_scene(self):
        for phrase in (
            'id="office-context"',
            "function renderOfficeContext",
            "def.output",
            "def.evidence",
            'matchMedia("(prefers-reduced-motion: reduce)")',
            "if (reducedMotion.matches) return;",
            'event.key === "ArrowRight"',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)

    def test_learning_game_uses_suit_and_structure_aware_office_paths(self):
        tokens = (ROOT / "tokens.css").read_text(encoding="utf-8")
        self.assertIn('--font-ui: "SUIT", sans-serif', tokens)
        self.assertNotIn("IBM Plex Sans KR", tokens)
        self.assertIn("const GAME_WALKWAY_POINTS =", self.html)
        self.assertIn("GAME_WALKWAY_POINTS[name]", self.html)
        self.assertNotIn('class="company-foreground"', self.html)
        self.assertIn("const GAME_ROOM_BOUNDS =", self.html)
        self.assertNotIn('center: ["50%", "50%"]', self.html)
        self.assertIn("is-sleeping", self.html)
        self.assertIn("is-resting", self.html)
        self.assertNotIn("../dashboard/assets/", self.html)


if __name__ == "__main__":
    unittest.main()
