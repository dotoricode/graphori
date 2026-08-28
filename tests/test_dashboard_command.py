import argparse
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import sys


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import product_cli


class FakeServer:
    server_address = ("127.0.0.1", 43210)

    def __init__(self):
        self.served = False
        self.closed = False

    def serve_forever(self):
        self.served = True

    def server_close(self):
        self.closed = True


class DashboardCommandTests(unittest.TestCase):
    def _journal(self, root: Path, run_id: str) -> Path:
        path = root / ".graphori" / "runs" / run_id / "journal" / "journal.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("{}\n", encoding="utf-8")
        return path

    def test_latest_run_selects_most_recent_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            older = self._journal(root, "run-older")
            newer = self._journal(root, "run-newer")
            older.touch()
            newer.touch()
            older_stat = older.stat()
            newer_stat = newer.stat()
            os.utime(older, (older_stat.st_atime - 10, older_stat.st_mtime - 10))
            os.utime(newer, (newer_stat.st_atime, newer_stat.st_mtime))
            self.assertEqual(product_cli._latest_dashboard_run(root), "run-newer")

    def test_dashboard_serves_latest_run_and_opens_browser(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._journal(root, "run-dashboard")
            server = FakeServer()
            args = argparse.Namespace(root=root, run_id=None, port=0, no_open=False,
                                      locale="ko")
            output = io.StringIO()
            with (
                patch.object(product_cli, "create_server", return_value=server) as create,
                patch.object(product_cli.webbrowser, "open", return_value=True) as open_browser,
                redirect_stdout(output),
            ):
                self.assertEqual(product_cli.cmd_dashboard(args), 0)
            create.assert_called_once_with(
                root.resolve(), host="127.0.0.1", port=0,
                static_dir=product_cli._dashboard_static_dir(),
            )
            open_browser.assert_called_once_with(
                "http://127.0.0.1:43210/?run=run-dashboard"
            )
            self.assertTrue(server.served)
            self.assertTrue(server.closed)
            self.assertIn("표시할 작업: run-dashboard", output.getvalue())

    def test_no_open_and_missing_run_are_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            server = FakeServer()
            args = argparse.Namespace(root=root, run_id=None, port=0, no_open=True,
                                      locale="ko")
            with (
                patch.object(product_cli, "create_server", return_value=server),
                patch.object(product_cli.webbrowser, "open") as open_browser,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(product_cli.cmd_dashboard(args), 0)
            open_browser.assert_not_called()

            missing = argparse.Namespace(
                root=root, run_id="run-missing", port=0, no_open=True, locale="ko",
            )
            # Assert the condition, not one language's wording for it.
            with self.assertRaises(ValueError) as caught:
                product_cli.cmd_dashboard(missing)
            self.assertEqual(caught.exception.key, "dashboard_run_missing")
            traversal = argparse.Namespace(
                root=root, run_id="../outside", port=0, no_open=True, locale="ko",
            )
            with self.assertRaisesRegex(ValueError, "invalid path component"):
                product_cli.cmd_dashboard(traversal)

    def test_parser_exposes_dashboard_command(self):
        args = product_cli.build_parser().parse_args([
            "dashboard", "--root", "/tmp/example", "--run-id", "run-1", "--no-open",
        ])
        self.assertIs(args.func, product_cli.cmd_dashboard)
        self.assertEqual(args.run_id, "run-1")
        self.assertTrue(args.no_open)


if __name__ == "__main__":
    unittest.main()
