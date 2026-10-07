"""Tests for tools/open_planner.py (what the app icon runs).

Nothing here starts or stops a real service, reads the real log, shows a real
notification or opens a browser: a FakeDesktop records what would have happened.
"""

import datetime
import io
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))   # the scripts in tools/ aren't on the import path by default

import open_planner

CLICK_TIME = datetime.datetime(2026, 10, 7, 12, 0, 0)


class FakeDesktop:
    """Stands in for open_planner.Desktop and writes down every call."""

    def __init__(self, answers=(), log=(), failing=()):
        self.replies = list(answers)    # what answers() returns, in turn; False once used up
        self.log = list(log)            # what log_lines() returns
        self.failing = set(failing)     # systemctl actions that fail, e.g. {"start"}
        self.calls = []
        self.log_since = None

    def answers(self):
        self.calls.append(("answers",))
        return self.replies.pop(0) if self.replies else False

    def systemctl(self, *args):
        self.calls.append(("systemctl",) + args)
        if args[0] in self.failing:
            return False, f"{args[0]} went wrong"
        return True, ""

    def log_lines(self, since):
        self.log_since = since
        return list(self.log)

    def notify(self, title, body):
        self.calls.append(("notify", title, body))

    def open_browser(self):
        self.calls.append(("browser",))

    def sleep(self, seconds):
        self.calls.append(("sleep", seconds))

    def now(self):
        return CLICK_TIME

    def named(self, name):
        """Only the calls of one kind, e.g. named("systemctl")."""
        return [call for call in self.calls if call[0] == name]


class SettingsTests(unittest.TestCase):
    def test_host_and_port_match_app_py(self):
        text = (PROJECT / "app.py").read_text(encoding="utf-8")
        host = re.search(r'^HOST = "([^"]+)"', text, re.MULTILINE).group(1)
        port = int(re.search(r"^PORT = (\d+)", text, re.MULTILINE).group(1))
        self.assertEqual((open_planner.HOST, open_planner.PORT), (host, port))

    def test_app_url(self):
        self.assertEqual(open_planner.app_url(), "http://127.0.0.1:8080")

    def test_full_log_line(self):
        self.assertEqual(open_planner.full_log_line(), "Full log: journalctl --user -u rs3-planner")


class WaitTests(unittest.TestCase):
    def test_answering_at_once_needs_no_waiting(self):
        sleeps = []
        self.assertTrue(open_planner.wait_for_app(lambda: True, sleeps.append))
        self.assertEqual(sleeps, [])

    def test_never_answering_waits_twenty_seconds_in_half_seconds(self):
        sleeps = []
        self.assertFalse(open_planner.wait_for_app(lambda: False, sleeps.append))
        self.assertEqual(sleeps, [0.5] * 40)


class OpenTests(unittest.TestCase):
    def test_already_answering_just_opens_the_browser(self):
        desktop = FakeDesktop(answers=[True])
        open_planner.open_app(desktop)
        self.assertEqual(desktop.named("browser"), [("browser",)])
        self.assertEqual(desktop.named("systemctl"), [])

    def test_not_running_starts_waits_and_opens(self):
        # First check: not answering. Then two more "no"s while starting, then "yes".
        desktop = FakeDesktop(answers=[False, False, False, True])
        open_planner.open_app(desktop)
        self.assertEqual(desktop.named("systemctl"),
                         [("systemctl", "reset-failed", "rs3-planner"), ("systemctl", "start", "rs3-planner")])
        self.assertEqual(desktop.named("browser"), [("browser",)])
        self.assertEqual(desktop.named("notify"), [])

    def test_reset_failed_comes_before_start(self):
        desktop = FakeDesktop(answers=[False, True])
        open_planner.open_app(desktop)
        actions = [call[1] for call in desktop.named("systemctl")]
        self.assertEqual(actions, ["reset-failed", "start"])

    def test_never_answering_notifies_with_the_last_three_app_lines(self):
        log = ["Fetching Some Player from RuneMetrics", "line two", "line three", "methods.json: line 4 is broken"]
        desktop = FakeDesktop(answers=[], log=log)
        open_planner.open_app(desktop)
        self.assertEqual(desktop.named("browser"), [])
        self.assertEqual(len(desktop.named("sleep")), 40)   # the fake clock makes this instant
        title, body = desktop.named("notify")[0][1:]
        self.assertEqual(title, "RS3 Planner didn't start")
        self.assertEqual(body, "line two\nline three\nmethods.json: line 4 is broken\n"
                               "Full log: journalctl --user -u rs3-planner")
        self.assertEqual(desktop.log_since, CLICK_TIME)     # only lines logged since this click

    def test_never_answering_with_no_app_lines_shows_only_the_full_log_line(self):
        desktop = FakeDesktop(answers=[], log=[])
        open_planner.open_app(desktop)
        self.assertEqual(desktop.named("notify")[0][2], "Full log: journalctl --user -u rs3-planner")

    def test_a_failing_start_shows_its_message_and_does_not_wait(self):
        desktop = FakeDesktop(answers=[False], failing={"start"})
        open_planner.open_app(desktop)
        self.assertEqual(desktop.named("sleep"), [])
        self.assertEqual(desktop.named("notify")[0][2],
                         "start went wrong\nFull log: journalctl --user -u rs3-planner")


class RestartAndStopTests(unittest.TestCase):
    def test_restart_restarts_then_opens(self):
        desktop = FakeDesktop(answers=[True])
        open_planner.restart_app(desktop)
        self.assertEqual(desktop.named("systemctl"),
                         [("systemctl", "reset-failed", "rs3-planner"), ("systemctl", "restart", "rs3-planner")])
        self.assertEqual(desktop.named("browser"), [("browser",)])

    def test_stop_stops_and_says_so(self):
        desktop = FakeDesktop()
        open_planner.stop_app(desktop)
        self.assertEqual(desktop.named("systemctl"), [("systemctl", "stop", "rs3-planner")])
        self.assertEqual(desktop.named("notify"),
                         [("notify", "RS3 Planner stopped", "Click its icon to start it again.")])

    def test_a_failing_stop_says_so(self):
        desktop = FakeDesktop(failing={"stop"})
        open_planner.stop_app(desktop)
        title, body = desktop.named("notify")[0][1:]
        self.assertEqual(title, "RS3 Planner couldn't be stopped")
        self.assertEqual(body, "stop went wrong\nFull log: journalctl --user -u rs3-planner")


class RealDesktopTests(unittest.TestCase):
    """The real Desktop class, with subprocess.run replaced so nothing actually runs."""

    def test_missing_notify_send_prints_instead_of_crashing(self):
        output = io.StringIO()
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("notify-send")), redirect_stdout(output):
            open_planner.Desktop().notify("RS3 Planner stopped", "Click its icon to start it again.")
        self.assertEqual(output.getvalue(), "RS3 Planner stopped\nClick its icon to start it again.\n")

    def test_open_browser_does_not_capture_output(self):
        with mock.patch("subprocess.run") as run:
            open_planner.Desktop().open_browser()
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["xdg-open", "http://127.0.0.1:8080"])
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)

    def test_log_lines_reads_only_the_app_tag_since_the_click(self):
        reply = subprocess.CompletedProcess([], 0, stdout="first\n\nsecond\n", stderr="")
        with mock.patch("subprocess.run", return_value=reply) as run:
            lines = open_planner.Desktop().log_lines(CLICK_TIME)
        self.assertEqual(lines, ["first", "second"])
        self.assertEqual(run.call_args[0][0],
                         ["journalctl", "--user", "-t", "rs3-planner", "--since", "2026-10-07 12:00:00",
                          "-o", "cat", "-q", "--no-pager"])

    def test_unreadable_log_gives_no_lines(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("journalctl")):
            self.assertEqual(open_planner.Desktop().log_lines(CLICK_TIME), [])


if __name__ == "__main__":
    unittest.main()
