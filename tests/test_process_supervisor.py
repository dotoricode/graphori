import hashlib
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    DEFAULT_ENV_ALLOWLIST, PathSecurityError, ProcessLimits, ProcessSupervisor,
    ProcessSupervisorError, build_child_env, resolve_workspace_path,
)
from graphori_core.process_supervisor import WINDOWS  # noqa: E402

PY = sys.executable


def _pid_is_alive_windows(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True,
    )
    return str(pid) in result.stdout


def _pid_is_alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True,
    )
    return result.returncode == 0 and not result.stdout.strip().startswith("Z")


class NormalExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.supervisor = ProcessSupervisor()

    def test_normal_exit_zero(self):
        result = self.supervisor.run(
            [PY, "-c", "import sys; sys.exit(0)"], workspace_root=self.root,
        )
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)
        self.assertFalse(result.tree_kill_used)

    def test_nonzero_exit(self):
        result = self.supervisor.run(
            [PY, "-c", "import sys; sys.exit(7)"], workspace_root=self.root,
        )
        self.assertEqual(result.exit_code, 7)
        self.assertFalse(result.timed_out)

    def test_stdout_and_stderr_are_captured(self):
        result = self.supervisor.run(
            [PY, "-c", "import sys; sys.stdout.write('out-line'); sys.stderr.write('err-line')"],
            workspace_root=self.root,
        )
        self.assertEqual(result.stdout, b"out-line")
        self.assertEqual(result.stderr, b"err-line")

    def test_first_and_last_stdout_times_are_observable(self):
        result = self.supervisor.run(
            [PY, "-c", (
                "import time; print('first', flush=True); time.sleep(0.05); "
                "print('last', flush=True)"
            )],
            workspace_root=self.root,
        )
        self.assertIsNotNone(result.first_stdout_at)
        self.assertIsNotNone(result.last_stdout_at)
        self.assertLessEqual(result.started_at, result.first_stdout_at)
        self.assertLessEqual(result.first_stdout_at, result.last_stdout_at)
        self.assertLessEqual(result.last_stdout_at, result.finished_at)
        self.assertGreater(result.last_stdout_at - result.first_stdout_at, 0.01)


class ArgvAndCwdSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.supervisor = ProcessSupervisor()

    def test_argv_as_shell_string_is_rejected(self):
        with self.assertRaises(ProcessSupervisorError):
            self.supervisor.run(f"{PY} -c pass", workspace_root=self.root)

    def test_empty_argv_is_rejected(self):
        with self.assertRaises(ProcessSupervisorError):
            self.supervisor.run([], workspace_root=self.root)

    def test_cwd_traversal_outside_workspace_is_rejected(self):
        with self.assertRaises(PathSecurityError):
            self.supervisor.run([PY, "-c", "pass"], workspace_root=self.root, cwd="..")
        with self.assertRaises(PathSecurityError):
            self.supervisor.run([PY, "-c", "pass"], workspace_root=self.root,
                                cwd="a/../../escape")

    def test_absolute_cwd_is_rejected_even_if_it_exists(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        with self.assertRaises(PathSecurityError):
            self.supervisor.run([PY, "-c", "pass"], workspace_root=self.root, cwd=outside.name)

    def test_relative_cwd_inside_workspace_is_accepted(self):
        sub = self.root / "workdir"
        sub.mkdir()
        result = self.supervisor.run(
            [PY, "-c", "import os,sys; sys.stdout.write(os.getcwd())"],
            workspace_root=self.root, cwd="workdir",
        )
        self.assertEqual(Path(result.stdout.decode()).resolve(), sub.resolve())

    def test_case_collision_cwd_is_rejected(self):
        (self.root / "Work").mkdir()
        with self.assertRaises(PathSecurityError):
            resolve_workspace_path(self.root, "work")

    @unittest.skipUnless(WINDOWS, "junction fixture is Windows-only; deferred/unknown elsewhere")
    def test_junction_escape_cwd_is_rejected(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        link = self.root / "escape_link"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), outside.name],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            self.skipTest(f"deferred: could not create a junction here (rc={result.returncode})")
        self.addCleanup(lambda: link.exists() and link.rmdir())
        with self.assertRaises(PathSecurityError):
            self.supervisor.run([PY, "-c", "pass"], workspace_root=self.root, cwd="escape_link")


class EnvAllowlistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.supervisor = ProcessSupervisor()

    def test_build_child_env_drops_unlisted_and_secret_looking_names(self):
        base = {"PATH": "/bin", "HOME": "/home/x"}
        extra = {"MY_SAFE_VAR": "ok", "MY_SECRET_TOKEN": "shh", "UNLISTED_VAR": "nope"}
        allow = DEFAULT_ENV_ALLOWLIST | {"MY_SAFE_VAR", "MY_SECRET_TOKEN"}
        child, dropped = build_child_env(base_env=base, extra_env=extra, allowlist=allow)
        self.assertEqual(child.get("MY_SAFE_VAR"), "ok")
        self.assertNotIn("MY_SECRET_TOKEN", child)
        self.assertNotIn("UNLISTED_VAR", child)
        self.assertIn("MY_SECRET_TOKEN", dropped)
        self.assertIn("UNLISTED_VAR", dropped)

    def test_default_environment_allows_bytecode_suppression(self):
        child, dropped = build_child_env(
            base_env={}, extra_env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(child["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertNotIn("PYTHONDONTWRITEBYTECODE", dropped)

    def test_child_process_only_sees_allowlisted_non_secret_env(self):
        allow = DEFAULT_ENV_ALLOWLIST | {"MY_SAFE_VAR", "MY_SECRET_TOKEN"}
        env = {"MY_SAFE_VAR": "ok", "MY_SECRET_TOKEN": "shh", "MY_UNLISTED": "nope"}
        result = self.supervisor.run(
            [PY, "-c", "import os,sys; sys.stdout.write('|'.join(sorted(os.environ.keys())))"],
            workspace_root=self.root, env=env, env_allowlist=allow,
        )
        keys = set(result.stdout.decode().split("|"))
        self.assertIn("MY_SAFE_VAR", keys)
        self.assertNotIn("MY_SECRET_TOKEN", keys)
        self.assertNotIn("MY_UNLISTED", keys)
        self.assertIn("MY_SECRET_TOKEN", result.dropped_env_keys)


class BoundedCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.supervisor = ProcessSupervisor()

    def test_stdout_byte_cap_truncates_without_hanging(self):
        limits = ProcessLimits(max_stdout_bytes=100, max_stderr_bytes=1000)
        result = self.supervisor.run(
            [PY, "-c", "import sys; sys.stdout.write('A' * 200000)"],
            workspace_root=self.root, limits=limits,
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout_truncated)
        self.assertLessEqual(len(result.stdout), 100)
        self.assertEqual(result.stdout_total_bytes, 200000)

    def test_line_cap_truncates(self):
        limits = ProcessLimits(max_stdout_bytes=10_000_000, max_lines=5)
        script = "import sys\nfor i in range(1000): sys.stdout.write('line %d\\n' % i)\n"
        result = self.supervisor.run(
            [PY, "-c", script], workspace_root=self.root, limits=limits,
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout_truncated)
        self.assertLessEqual(result.stdout.count(b"\n"), 6)


class TimeoutTreeKillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.marker_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.marker_dir.cleanup)
        self.supervisor = ProcessSupervisor()

    def _write_scripts(self) -> Path:
        marker = Path(self.marker_dir.name)
        (marker / "child.py").write_text(textwrap.dedent("""
            import pathlib, sys, time
            marker_dir = pathlib.Path(sys.argv[1])
            (marker_dir / "child_running.txt").write_text("1")
            time.sleep(120)
        """), encoding="utf-8")
        (marker / "parent.py").write_text(textwrap.dedent("""
            import pathlib, subprocess, sys, time
            marker_dir = pathlib.Path(sys.argv[1])
            child = subprocess.Popen(
                [sys.executable, str(marker_dir / "child.py"), str(marker_dir)])
            (marker_dir / "child_pid.txt").write_text(str(child.pid))
            time.sleep(120)
        """), encoding="utf-8")
        return marker / "parent.py"

    def test_timeout_terminates_child_and_grandchild(self):
        script = self._write_scripts()
        limits = ProcessLimits(timeout_seconds=2.5, grace_seconds=3.0)
        result = self.supervisor.run(
            [PY, str(script), self.marker_dir.name], workspace_root=self.root, limits=limits,
        )

        self.assertTrue(result.timed_out)
        self.assertTrue(result.tree_kill_used)
        self.assertIn(result.tree_kill_method, {"job_object", "taskkill_fallback"} if WINDOWS
                       else {"process_group", "kill_fallback_no_group", "kill_fallback_group_signal_failed"})

        pid_file = Path(self.marker_dir.name) / "child_pid.txt"
        # The grandchild must have had time to start and record its pid before
        # the parent (and therefore its subtree) was terminated.
        self.assertTrue(pid_file.exists(), "grandchild never started -- test setup issue, not a kill failure")
        grandchild_pid = int(pid_file.read_text().strip())

        if WINDOWS:
            self.assertFalse(_pid_is_alive_windows(grandchild_pid),
                             "grandchild process survived the timeout kill")
        else:
            deadline = time.monotonic() + 3
            while _pid_is_alive_posix(grandchild_pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(
                _pid_is_alive_posix(grandchild_pid),
                "grandchild process survived the POSIX process-group timeout kill",
            )


class ExternalMarkerInvarianceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.outside = tempfile.TemporaryDirectory()
        self.addCleanup(self.outside.cleanup)
        self.marker = Path(self.outside.name) / "marker.txt"
        self.marker.write_text("do-not-touch")
        self.supervisor = ProcessSupervisor()

    def _digest(self) -> str:
        return hashlib.sha256(self.marker.read_bytes()).hexdigest()

    def test_marker_outside_workspace_is_unchanged_after_rejected_escape_and_timeout_kill(self):
        before = self._digest()

        with self.assertRaises(PathSecurityError):
            self.supervisor.run([PY, "-c", "pass"], workspace_root=self.root, cwd=str(self.outside.name))

        limits = ProcessLimits(timeout_seconds=1.0, grace_seconds=2.0)
        result = self.supervisor.run(
            [PY, "-c", "import time; time.sleep(60)"], workspace_root=self.root, limits=limits,
        )
        self.assertTrue(result.timed_out)

        after = self._digest()
        self.assertEqual(before, after, "marker file outside the workspace root was modified")


if __name__ == "__main__":
    unittest.main()
