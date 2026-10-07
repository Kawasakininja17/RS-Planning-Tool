"""Tests for tools/install_desktop.py.

Every test writes into a temporary "home" folder, never the real one, and a
FakeRun writes down the systemctl commands instead of running them.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))   # the scripts in tools/ aren't on the import path by default

import install_desktop
from install_desktop import InstallError

PLAIN = Path("/home/someone/RS-Planning-Tool")
SPACES = Path("/home/someone/My Games/RS Tool")
ODD = Path("/home/someone/a`b c")   # a backtick and a space: allowed, but need quoting


class FakeRun:
    """Stands in for run_command: records each command; can fail on one word."""

    def __init__(self, fail_on=None):
        self.commands = []
        self.fail_on = fail_on

    def __call__(self, args):
        self.commands.append(args)
        if self.fail_on in args:
            raise InstallError(f"This command failed: {' '.join(args)}\nboom")


def replies(*values):
    """A fake answers(): returns the given values in turn, then False."""
    values = list(values)
    return lambda: values.pop(0) if values else False


class QuotingTests(unittest.TestCase):
    def test_systemd_quote_plain(self):
        self.assertEqual(install_desktop.systemd_quote(PLAIN), '"/home/someone/RS-Planning-Tool"')

    def test_systemd_quote_odd(self):
        self.assertEqual(install_desktop.systemd_quote(ODD), '"/home/someone/a`b c"')

    def test_desktop_quote_plain(self):
        self.assertEqual(install_desktop.desktop_quote(PLAIN), '"/home/someone/RS-Planning-Tool"')

    def test_desktop_quote_odd(self):
        # Quote rule: \` for a backtick, then the file's string rule doubles every backslash.
        self.assertEqual(install_desktop.desktop_quote(ODD), r'''"/home/someone/a\\`b c"''')


class PathProblemTests(unittest.TestCase):
    def test_ordinary_paths_are_fine(self):
        for path in (PLAIN, SPACES, ODD):
            self.assertIsNone(install_desktop.path_problem(path))

    def test_refused_characters(self):
        # systemd won't run a program whose path has a quote, and "$" or "%" can't be
        # written safely in every place the path appears (see the spec).
        for bad in ("%", "\\", '"', "'", "$", "\n"):
            message = install_desktop.path_problem(Path(f"/home/someone/a{bad}b"))
            self.assertEqual(message, "Rename the project folder so its path has no %, \\, \", ' or $ "
                                      "or line break, then run the install again.")


class TextTests(unittest.TestCase):
    def test_service_text_plain(self):
        lines = install_desktop.service_text(PLAIN).splitlines()
        for expected in ("WorkingDirectory=/home/someone/RS-Planning-Tool",
                         'ExecStart="/home/someone/RS-Planning-Tool/.venv/bin/python" '
                         '"/home/someone/RS-Planning-Tool/app.py"',
                         "Environment=PYTHONUNBUFFERED=1", "SyslogIdentifier=rs3-planner",
                         "Restart=on-failure", "RestartSec=5", "StartLimitIntervalSec=60",
                         "StartLimitBurst=3", "WantedBy=default.target"):
            self.assertIn(expected, lines)

    def test_service_text_with_spaces(self):
        self.assertIn('ExecStart="/home/someone/My Games/RS Tool/.venv/bin/python" '
                      '"/home/someone/My Games/RS Tool/app.py"', install_desktop.service_text(SPACES))

    def test_desktop_text_plain(self):
        lines = install_desktop.desktop_text(PLAIN).splitlines()
        run = '"/home/someone/RS-Planning-Tool/.venv/bin/python" "/home/someone/RS-Planning-Tool/tools/open_planner.py"'
        for expected in ("[Desktop Entry]", "Type=Application", "Name=RS3 Planner",
                         "Icon=/home/someone/RS-Planning-Tool/static/icons/app-icon.svg",
                         f"Exec={run}", "Terminal=false", "Categories=Game;", "Actions=restart;stop;",
                         "[Desktop Action restart]", "Name=Restart RS3 Planner", f"Exec={run} --restart",
                         "[Desktop Action stop]", "Name=Stop RS3 Planner", f"Exec={run} --stop"):
            self.assertIn(expected, lines)

    def test_desktop_text_with_spaces(self):
        self.assertIn('Exec="/home/someone/My Games/RS Tool/.venv/bin/python" '
                      '"/home/someone/My Games/RS Tool/tools/open_planner.py"', install_desktop.desktop_text(SPACES))


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.home.mkdir()
        self.project = root / "RS Planning Tool"
        (self.project / ".venv" / "bin").mkdir(parents=True)
        (self.project / ".venv" / "bin" / "python").touch()

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, run=None, answers=None, active=lambda: False):
        return install_desktop.install(self.project, self.home, run=run or FakeRun(),
                                       answers=answers or replies(False, True), active=active,
                                       sleep=lambda seconds: None)

    def installed_files(self):
        return sorted(str(p.relative_to(self.home)) for p in self.home.rglob("*") if p.is_file())

    def test_install_writes_two_files_and_turns_the_service_on(self):
        run = FakeRun()
        lines = self.install(run=run)
        self.assertEqual(self.installed_files(), [".config/systemd/user/rs3-planner.service",
                                                  ".local/share/applications/rs3-planner.desktop"])
        self.assertEqual(run.commands, [["systemctl", "--user", "daemon-reload"],
                                        ["systemctl", "--user", "enable", "rs3-planner.service"],
                                        ["systemctl", "--user", "reset-failed", "rs3-planner.service"],
                                        ["systemctl", "--user", "restart", "rs3-planner.service"]])
        self.assertEqual(install_desktop.service_path(self.home).read_text(encoding="utf-8"),
                         install_desktop.service_text(self.project))
        self.assertTrue(lines[0].startswith("Written: "))
        self.assertTrue(lines[1].startswith("Written: "))
        self.assertIn("The app is running: http://127.0.0.1:8080 (or click the RS3 Planner icon).", lines)
        self.assertIn("To undo: python3 tools/install_desktop.py --remove", lines)

    def test_a_second_identical_install_says_already_up_to_date(self):
        self.install()
        lines = self.install()
        self.assertTrue(lines[0].startswith("Already up to date: "))
        self.assertTrue(lines[1].startswith("Already up to date: "))

    def test_a_changed_file_is_replaced_and_said_so(self):
        self.install()
        install_desktop.desktop_path(self.home).write_text("an older launcher\n", encoding="utf-8")
        lines = self.install()
        self.assertTrue(lines[1].startswith("Replaced (it was different): "))
        self.assertEqual(install_desktop.desktop_path(self.home).read_text(encoding="utf-8"),
                         install_desktop.desktop_text(self.project))

    def test_no_venv_writes_and_runs_nothing(self):
        (self.project / ".venv" / "bin" / "python").unlink()
        run = FakeRun()
        with self.assertRaises(InstallError) as caught:
            self.install(run=run)
        self.assertIn("one-time setup", str(caught.exception))
        self.assertEqual(self.installed_files(), [])
        self.assertEqual(run.commands, [])

    def test_a_refused_folder_name_writes_and_runs_nothing(self):
        run = FakeRun()
        with self.assertRaises(InstallError):
            install_desktop.install(Path("/home/someone/100%"), self.home, run=run,
                                    answers=replies(), active=lambda: False, sleep=lambda s: None)
        self.assertEqual(self.installed_files(), [])
        self.assertEqual(run.commands, [])

    def test_a_terminal_copy_answering_blocks_the_install(self):
        run = FakeRun()
        with self.assertRaises(InstallError) as caught:
            self.install(run=run, answers=replies(True), active=lambda: False)
        self.assertIn("Ctrl+C", str(caught.exception))
        self.assertEqual(self.installed_files(), [])
        self.assertEqual(run.commands, [])

    def test_reinstall_while_the_service_runs_goes_ahead(self):
        run = FakeRun()
        self.install(run=run, answers=replies(True, True), active=lambda: True)
        self.assertEqual(len(run.commands), 4)

    def test_a_failing_reset_failed_does_not_stop_the_install(self):
        # Clearing Ubuntu's "start repeated too quickly" lock is only a help; if it
        # fails, the restart that follows reports any real problem.
        run = FakeRun(fail_on="reset-failed")
        lines = self.install(run=run)
        self.assertEqual(run.commands[-1], ["systemctl", "--user", "restart", "rs3-planner.service"])
        self.assertIn("The app is running: http://127.0.0.1:8080 (or click the RS3 Planner icon).", lines)

    def test_a_failing_systemctl_stops_with_its_message(self):
        with self.assertRaises(InstallError) as caught:
            self.install(run=FakeRun(fail_on="enable"))
        message = str(caught.exception)
        self.assertIn("This command failed: systemctl --user enable rs3-planner.service", message)
        self.assertIn("The two files were written, but the app wasn't turned on.", message)
        self.assertEqual(len(self.installed_files()), 2)

    def test_an_app_that_never_answers_is_reported(self):
        lines = self.install(answers=replies())
        self.assertIn("The app didn't answer within 20 seconds. Its log: journalctl --user -u rs3-planner", lines)

    def test_remove_deletes_both_files_and_turns_the_service_off(self):
        self.install()
        run = FakeRun()
        lines = install_desktop.remove(self.home, run=run)
        self.assertEqual(self.installed_files(), [])
        self.assertEqual(run.commands, [["systemctl", "--user", "disable", "--now", "rs3-planner.service"],
                                        ["systemctl", "--user", "daemon-reload"]])
        self.assertTrue(lines[0].startswith("Removed: "))

    def test_remove_with_nothing_installed_finishes_cleanly(self):
        run = FakeRun()
        self.assertEqual(install_desktop.remove(self.home, run=run),
                         ["Nothing to remove: RS3 Planner wasn't installed."])
        self.assertEqual(run.commands, [])

    def test_remove_with_only_the_launcher_left_runs_no_systemctl(self):
        self.install()
        install_desktop.service_path(self.home).unlink()
        run = FakeRun()
        install_desktop.remove(self.home, run=run)
        self.assertEqual(self.installed_files(), [])
        self.assertEqual(run.commands, [])

    def test_show_writes_and_runs_nothing(self):
        lines = install_desktop.show(self.project, self.home)
        text = "\n".join(lines)
        self.assertIn(install_desktop.service_text(self.project), text)
        self.assertIn(install_desktop.desktop_text(self.project), text)
        self.assertIn(str(install_desktop.service_path(self.home)), text)
        self.assertEqual(self.installed_files(), [])


class SudoTests(unittest.TestCase):
    def test_running_with_sudo_is_refused_before_anything_happens(self):
        # With sudo, "home" would be the administrator's (/root), not Chris's.
        for argv in ([], ["--show"], ["--remove"]):
            with mock.patch("os.geteuid", return_value=0), \
                 mock.patch.object(install_desktop, "install") as install, \
                 mock.patch.object(install_desktop, "remove") as remove, \
                 mock.patch.object(install_desktop, "show") as show:
                with self.assertRaises(SystemExit) as caught:
                    install_desktop.main(argv)
            self.assertEqual(str(caught.exception), "Run this without sudo: the app is installed for "
                                                    "your own account, so no password is needed.")
            for step in (install, remove, show):
                step.assert_not_called()

    def test_without_sudo_main_goes_ahead(self):
        output = io.StringIO()
        with mock.patch("os.geteuid", return_value=1000), \
             mock.patch.object(install_desktop, "show", return_value=["shown"]) as show, \
             redirect_stdout(output):
            install_desktop.main(["--show"])
        show.assert_called_once()
        self.assertEqual(output.getvalue(), "shown\n")


if __name__ == "__main__":
    unittest.main()
