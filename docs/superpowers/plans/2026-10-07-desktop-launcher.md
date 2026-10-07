# Desktop Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chris opens the RS3 Planner without a terminal: a user service starts the app in the background at login, and an **RS3 Planner** icon (swords on forest) opens it in the browser, with Restart and Stop on right-click.

**Architecture:** Two standard-library scripts in `tools/`. `open_planner.py` is what the icon runs (open / `--restart` / `--stop`); everything it does outside itself goes through a small `Desktop` class so the tests can use a fake. `install_desktop.py` builds the systemd unit and the `.desktop` launcher as text (pure functions, tested), writes them into the home folder, and turns the service on through an injectable command runner. `app.py` does not change.

**Tech Stack:** Python 3.14 standard library (`subprocess`, `urllib.request`, `argparse`, `unittest`); systemd user services (systemd 259); freedesktop Desktop Entry launchers (GNOME on Wayland, Ubuntu 26.04); `notify-send`, `xdg-open`, `journalctl`.

**Spec:** `docs/superpowers/specs/2026-10-07-desktop-launcher-design.md`

## Global Constraints

- `app.py`, every screen and the data files do not change. The app keeps `HOST = "127.0.0.1"`, `PORT = 8080`, one fetch per app run plus Refresh.
- Standard library only in the new scripts and tests; nothing new in `requirements.txt`.
- Service name and log tag: `rs3-planner`. Files written: `~/.config/systemd/user/rs3-planner.service` and `~/.local/share/applications/rs3-planner.desktop`. Nothing system-wide, no sudo.
- A project path containing `%`, `\` or a line break is refused with: "Rename the project folder so its path has no %, \ or line break, then run the install again."
- Icon: Lucide's swords (lucide-static v1.52.0, ISC) in parchment `#F0E8D6` on a rounded forest panel `#16241B` with border `#2E4636`. No gradients, no emoji.
- Tests never touch the real home folder, never run `systemctl`, `journalctl`, `notify-send` or `xdg-open`, never use the network, never touch the real `data/players/`. Tests use "Some Player" if a name is ever needed (none is).
- Code is simple and commented in plain words, matching the existing files.
- Tests: `python3 -m unittest discover -s tests -v` from the project folder (146 before this plan). Data check: `python3 check_methods.py` (81 methods).
- Scratch work goes in `W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/desktop-launcher` (git-ignored by `.superpowers/sdd/.gitignore`), never `/tmp`. Throwaway copies are deleted afterwards.
- Installing is Chris's action: Claude never runs `tools/install_desktop.py` without `--show`, and never runs `systemctl --user enable/start/stop/restart rs3-planner` without Chris's OK.
- While the service holds port 8080, Claude's own app copies use port 8091.
- Stop and wait for Chris after each task. Commit after each task; never push without asking. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- If any step errors, stop that task, explain (what failed, the error in plain words, likely cause, what's done, what's left, the proper fix) and wait for Chris.

## Review Focus

1. **The app was started from a terminal when the installer runs** → the installer writes nothing and says to stop it with Ctrl+C first (otherwise the service fails three times on the busy port and gives up). Pinned in Task 2 (`test_a_terminal_copy_answering_blocks_the_install`); a re-install while the *service* is answering still goes ahead (`test_reinstall_while_the_service_runs_goes_ahead`).
2. **A data file was broken, Chris fixes it and clicks the icon within a minute** → it starts (the opener clears Ubuntu's "start request repeated too quickly" lock with `reset-failed` first). Pinned in Task 1 (`test_reset_failed_comes_before_start`) and live in Task 4.
3. **The browser keeps the opener's output open**, so the opener hangs and then wrongly reports "Couldn't open the browser" → `xdg-open` is run with its output sent to `DEVNULL`, never captured. Pinned in Task 1 (`test_open_browser_does_not_capture_output`).
4. **The project folder was moved and the installer run again** → both files are replaced with the new path and the service is restarted so the new path takes effect. Pinned in Task 2 (`test_a_changed_file_is_replaced_and_said_so`, the `restart` command in `test_install_writes_two_files_and_turns_the_service_on`).
5. **Lines from an earlier, normal run appear in a "didn't start" notification** → only lines logged since this click are quoted, at most the last 3. Pinned in Task 1 (`test_never_answering_notifies_with_the_last_three_app_lines`, which checks the `since` time).

## File map

| File | Change | Responsibility |
|---|---|---|
| `tools/open_planner.py` | create | What the icon runs: constants (`SERVICE`, `LOG_TAG`, `HOST`, `PORT`), `app_url`, `app_answers`, `service_active`, `wait_for_app`, `full_log_line`, the `Desktop` class, `open_app`, `restart_app`, `stop_app`, `start_and_open`, `main` |
| `tests/test_open_planner.py` | create | Opener tests with a `FakeDesktop` |
| `static/icons/app-icon.svg` | create | The launcher icon |
| `tools/install_desktop.py` | create | `path_problem`, `systemd_quote`, `desktop_quote`, `service_text`, `desktop_text`, `service_path`, `desktop_path`, `write_file`, `run_command`, `install`, `remove`, `show`, `main` |
| `tests/test_install_desktop.py` | create | Installer tests with a fake runner and a scratch home folder |
| `README.md` | modify | New section "Start it without a terminal (Linux)" under *Install* |

Scratch only (never committed): `$W/check/` (generated files for the official checkers), `$W/odd/` (a project path with special characters), `$W/broken/` (a throwaway copy with a broken `methods.json`), `$W/live_failure.py`.

---

### Task 1: The opener (`tools/open_planner.py`)

**Files:**
- Create: `tools/open_planner.py`
- Test: `tests/test_open_planner.py`

**Interfaces:**
- Consumes: nothing from the project (it must not import `app.py`).
- Produces (used by Task 2):
  - constants `SERVICE = "rs3-planner"`, `LOG_TAG = "rs3-planner"`, `HOST = "127.0.0.1"`, `PORT = 8080`, `WAIT_SECONDS = 20`, `CHECK_EVERY = 0.5`, `PROJECT` (Path), `ICON` (Path)
  - `app_url() -> str`
  - `app_answers() -> bool`
  - `service_active() -> bool`
  - `wait_for_app(answers: callable, sleep: callable, seconds=WAIT_SECONDS) -> bool`
  - `full_log_line() -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_open_planner.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_open_planner -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'open_planner'`.

- [ ] **Step 3: Write the opener**

Create `tools/open_planner.py`:

```python
#!/usr/bin/env python3
"""
RS3 Planner - what the app icon runs (Linux)
============================================

The RS3 Planner icon (installed by tools/install_desktop.py) runs this file:
    open_planner.py            open the app in the browser, starting it first if needed
    open_planner.py --restart  restart the app (e.g. after editing data/methods.json), then open it
    open_planner.py --stop     stop the app until the icon is clicked or the next login

The app itself runs in the background as the user service "rs3-planner". This
file only starts, restarts or stops that service and opens the browser. If the
app doesn't start, it shows a desktop notification with the app's own last
messages instead of an empty browser page.

Standard library only. Everything it does outside itself (asking the app,
systemctl, the log, notifications, the browser, waiting) goes through the
Desktop class, so the tests can use a fake one.
"""

import argparse
import datetime
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ICON = PROJECT / "static" / "icons" / "app-icon.svg"

SERVICE = "rs3-planner"   # the background service's name (tools/install_desktop.py writes it)
LOG_TAG = "rs3-planner"   # the tag on the app's own lines in the log (SyslogIdentifier in the service)
HOST = "127.0.0.1"        # must match HOST in app.py (a test checks)
PORT = 8080               # must match PORT in app.py (a test checks)

WAIT_SECONDS = 20         # how long to wait for the app to answer after starting it
CHECK_EVERY = 0.5         # seconds between checks while waiting


def app_url():
    """The app's address. Built when asked (not stored), so a test can change HOST or PORT."""
    return f"http://{HOST}:{PORT}"


def full_log_line():
    """The last line of every problem notification: where the whole log is."""
    return f"Full log: journalctl --user -u {SERVICE}"


def app_answers():
    """
    True if the app (or anything else) answers at its address within 2 seconds.
    Any reply counts, even an error page; a refused connection or a timeout doesn't.
    """
    # No proxy: the app is on this computer, so never ask a proxy server for it.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(app_url(), timeout=2):
            return True
    except urllib.error.HTTPError:   # it answered, with an error page
        return True
    except OSError:                  # refused, timed out, or no network at all
        return False


def service_active():
    """True if the background service is running right now."""
    try:
        result = subprocess.run(["systemctl", "--user", "is-active", "--quiet", SERVICE], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def wait_for_app(answers, sleep, seconds=WAIT_SECONDS):
    """
    Ask answers() every CHECK_EVERY seconds, for up to `seconds`.
    True as soon as the app answers; False if it never does.
    """
    for _ in range(round(seconds / CHECK_EVERY)):
        if answers():
            return True
        sleep(CHECK_EVERY)
    return answers()


class Desktop:
    """Everything the opener does outside itself, on the real computer.
    The tests use a FakeDesktop with the same methods instead."""

    def answers(self):
        return app_answers()

    def systemctl(self, *args):
        """Run `systemctl --user <args>`. Returns (worked, message)."""
        command = ["systemctl", "--user", *args]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, f"Couldn't run {' '.join(command)}: {error}"
        return result.returncode == 0, (result.stderr or result.stdout).strip()

    def log_lines(self, since):
        """The app's own log lines since `since` (a datetime), oldest first.
        Empty if there are none or the log can't be read."""
        command = ["journalctl", "--user", "-t", LOG_TAG, "--since", since.strftime("%Y-%m-%d %H:%M:%S"),
                   "-o", "cat", "-q", "--no-pager"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def notify(self, title, body):
        """A desktop notification. If that's impossible, print the message instead."""
        command = ["notify-send", "--app-name=RS3 Planner", f"--icon={ICON}", title, body]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            print(f"{title}\n{body}")

    def open_browser(self):
        """Open the app in the default browser."""
        # The output goes to DEVNULL, never captured: a browser started by xdg-open
        # can keep captured output open until it closes, which would freeze this script.
        try:
            subprocess.run(["xdg-open", app_url()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            self.notify("Couldn't open the browser", f"Open {app_url()} yourself.")

    def sleep(self, seconds):
        time.sleep(seconds)

    def now(self):
        return datetime.datetime.now()


def start_and_open(desktop, action):
    """
    Start or restart the service (action "start" or "restart"), wait for the app,
    then open the browser. If it doesn't answer in time: a notification instead,
    with the app's own last messages since this click.
    """
    clicked = desktop.now()
    # After 3 failed starts Ubuntu refuses more for a minute; this clears that,
    # so a click right after fixing a broken data file works.
    desktop.systemctl("reset-failed", SERVICE)
    worked, message = desktop.systemctl(action, SERVICE)
    if worked and wait_for_app(desktop.answers, desktop.sleep):
        desktop.open_browser()
        return
    lines = [] if worked else [message]
    lines += desktop.log_lines(clicked)[-3:]
    lines.append(full_log_line())
    desktop.notify("RS3 Planner didn't start", "\n".join(lines))


def open_app(desktop):
    """The icon's click: open the app if it answers, else start it first."""
    if desktop.answers():
        desktop.open_browser()
    else:
        start_and_open(desktop, "start")


def restart_app(desktop):
    """Right-click > Restart RS3 Planner."""
    start_and_open(desktop, "restart")


def stop_app(desktop):
    """Right-click > Stop RS3 Planner."""
    worked, message = desktop.systemctl("stop", SERVICE)
    if worked:
        desktop.notify("RS3 Planner stopped", "Click its icon to start it again.")
    else:
        desktop.notify("RS3 Planner couldn't be stopped", f"{message}\n{full_log_line()}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open the RS3 Planner (what its app icon runs).")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--restart", action="store_true", help="restart the app, then open it")
    choice.add_argument("--stop", action="store_true", help="stop the app")
    args = parser.parse_args(argv)
    desktop = Desktop()
    if args.stop:
        stop_app(desktop)
    elif args.restart:
        restart_app(desktop)
    else:
        open_app(desktop)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the new tests, then the whole suite**

Run: `python3 -m unittest tests.test_open_planner -v`
Expected: 18 tests, all PASS.

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: `Ran 164 tests` … `OK` (146 + 18).

- [ ] **Step 5: Commit**

```bash
git add tools/open_planner.py tests/test_open_planner.py
git commit -m "Desktop launcher: the opener the app icon runs (open, restart, stop)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Stop and wait for Chris**

Explain in plain words what the opener does, how the fake desktop lets the tests run without touching anything real, and the test count. Wait for his OK before Task 2.

---

### Task 2: The icon and the installer (`tools/install_desktop.py`)

**Files:**
- Create: `static/icons/app-icon.svg`
- Create: `tools/install_desktop.py`
- Test: `tests/test_install_desktop.py`

**Interfaces:**
- Consumes (from Task 1, `tools/open_planner.py`): `SERVICE`, `LOG_TAG`, `app_url()`, `app_answers()`, `service_active()`, `wait_for_app(answers, sleep, seconds=WAIT_SECONDS)`, `WAIT_SECONDS`.
- Produces:
  - `class InstallError(Exception)`
  - `path_problem(project: Path) -> str | None`
  - `systemd_quote(path) -> str`, `desktop_quote(path) -> str`
  - `service_text(project: Path) -> str`, `desktop_text(project: Path) -> str`
  - `service_path(home: Path) -> Path`, `desktop_path(home: Path) -> Path`
  - `install(project, home, run=run_command, answers=app_answers, active=service_active, sleep=time.sleep) -> list[str]`
  - `remove(home, run=run_command) -> list[str]`
  - `show(project, home) -> list[str]`
  - `main(argv=None)`

- [ ] **Step 1: Create the icon**

Create `static/icons/app-icon.svg` (the paths are copied from `static/icons/swords.svg`; 24 × 7 = 168 px, centred in 256 with a 44 px margin):

```svg
<!-- @license lucide-static v1.52.0 - ISC -->
<!-- RS3 Planner app icon: Lucide "swords" (see LICENSE-lucide.txt) in parchment on the app's forest panel. -->
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect x="8" y="8" width="240" height="240" rx="48" fill="#16241B" stroke="#2E4636" stroke-width="8"/>
  <g transform="translate(44 44) scale(7)" fill="none" stroke="#F0E8D6" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
    <path d="m13 19 6-6"/>
    <path d="M14.5 17.5 3.586 6.586A2 2 0 013 5.172V3h2.172a2 2 0 011.414.586L17.5 14.5"/>
    <path d="m14.828 6.172 2.586-2.586A2 2 0 0118.828 3H21v2.172a2 2 0 01-.586 1.414l-2.586 2.586"/>
    <path d="m16 16 4 4"/>
    <path d="m19 21 2-2"/>
    <path d="m5 14 4 4"/>
    <path d="m5 21-2-2"/>
    <path d="M7.5 16.5 4 20"/>
  </g>
</svg>
```

Check it is well-formed XML:
Run: `python3 -c "import xml.etree.ElementTree as E; E.parse('static/icons/app-icon.svg'); print('ok')"`
Expected: `ok`

- [ ] **Step 2: Write the failing tests**

Create `tests/test_install_desktop.py`:

```python
"""Tests for tools/install_desktop.py.

Every test writes into a temporary "home" folder, never the real one, and a
FakeRun writes down the systemctl commands instead of running them.
"""

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))   # the scripts in tools/ aren't on the import path by default

import install_desktop
from install_desktop import InstallError

PLAIN = Path("/home/someone/RS-Planning-Tool")
SPACES = Path("/home/someone/My Games/RS Tool")
ODD = Path("/home/someone/a\"b$c`d'e")   # a double quote, dollar, backtick and single quote


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
        self.assertEqual(install_desktop.systemd_quote(ODD), r'''"/home/someone/a\"b$$c`d'e"''')

    def test_desktop_quote_plain(self):
        self.assertEqual(install_desktop.desktop_quote(PLAIN), '"/home/someone/RS-Planning-Tool"')

    def test_desktop_quote_odd(self):
        # Quote rule: \" \$ \`  then the file's string rule doubles every backslash.
        self.assertEqual(install_desktop.desktop_quote(ODD), r'''"/home/someone/a\\"b\\$c\\`d'e"''')


class PathProblemTests(unittest.TestCase):
    def test_ordinary_paths_are_fine(self):
        for path in (PLAIN, SPACES, ODD):
            self.assertIsNone(install_desktop.path_problem(path))

    def test_percent_backslash_and_line_break_are_refused(self):
        for bad in ("%", "\\", "\n"):
            message = install_desktop.path_problem(Path(f"/home/someone/a{bad}b"))
            self.assertEqual(message, "Rename the project folder so its path has no %, \\ or line break, "
                                      "then run the install again.")


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
        self.assertEqual(len(run.commands), 3)

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_install_desktop -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'install_desktop'`.

- [ ] **Step 4: Write the installer**

Create `tools/install_desktop.py`:

```python
#!/usr/bin/env python3
"""
RS3 Planner - start the app without a terminal (Linux)
======================================================

Run once from the project folder (no sudo needed):
    python3 tools/install_desktop.py           install, or update after moving the folder
    python3 tools/install_desktop.py --show    show the two files it would write; change nothing
    python3 tools/install_desktop.py --remove  undo the install (data/ is never touched)

It writes two small files into your own home folder:
  ~/.config/systemd/user/rs3-planner.service
      a "user service": Ubuntu starts the app in the background at every login
      (and stops it at logout), and restarts it after a crash
  ~/.local/share/applications/rs3-planner.desktop
      the RS3 Planner icon in your app list; it runs tools/open_planner.py,
      with Restart and Stop on right-click

then turns the service on with systemctl. Standard library only.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from open_planner import (
    LOG_TAG, SERVICE, WAIT_SECONDS, app_answers, app_url, service_active, wait_for_app,
)

PROJECT = Path(__file__).resolve().parent.parent
UNIT = f"{SERVICE}.service"

# Refused rather than quoted (see the spec): systemd's manual doesn't say whether "%"
# is special in WorkingDirectory=, and a "\" needs four backslashes in a launcher.
REFUSED_CHARACTERS = ("%", "\\", "\n", "\r")
REFUSED_MESSAGE = ("Rename the project folder so its path has no %, \\ or line break, "
                   "then run the install again.")
NO_VENV_MESSAGE = ("There's no .venv/bin/python in the project folder yet. Do the README's "
                   "one-time setup first (Install, step 2), then run the install again.")
BUSY_MESSAGE = (f"Something is already answering at {app_url()}, most likely the app started "
                "from a terminal. Stop it (Ctrl+C in that terminal), then run the install again.")


class InstallError(Exception):
    """A problem the person has to fix; the message says what to do."""


def path_problem(project):
    """Why this project folder's path can't be used, or None if it's fine."""
    if any(character in str(project) for character in REFUSED_CHARACTERS):
        return REFUSED_MESSAGE
    return None


def systemd_quote(path):
    """One path as a single quoted word on a systemd ExecStart= line.
    (systemd.syntax(7) "Quoting": \\" for a double quote; systemd.service(5): $$ for a dollar.)"""
    text = str(path).replace('"', '\\"').replace("$", "$$")
    return f'"{text}"'


def desktop_quote(path):
    """One path as a single quoted argument on a launcher's Exec= line.
    (Desktop Entry spec, "The Exec key": a backslash before " ` and $, then
    the file's general string rule doubles every backslash.)"""
    text = str(path)
    for character in ('"', "`", "$"):
        text = text.replace(character, "\\" + character)
    text = text.replace("\\", "\\\\")
    return f'"{text}"'


def venv_python(project):
    return project / ".venv" / "bin" / "python"


def service_path(home):
    return home / ".config" / "systemd" / "user" / UNIT


def desktop_path(home):
    return home / ".local" / "share" / "applications" / f"{SERVICE}.desktop"


def service_text(project):
    """The user service file's contents for this project folder."""
    command = f"{systemd_quote(venv_python(project))} {systemd_quote(project / 'app.py')}"
    return f"""\
# RS3 Planner: runs the browser app in the background.
# Written by tools/install_desktop.py; run it again (or with --remove) instead of editing this.
[Unit]
Description=RS3 Planner (browser app on {app_url()})
# Give up after 3 failed starts within 60 seconds (for example, a broken data file).
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
WorkingDirectory={project}
ExecStart={command}
# Send the app's messages to the log straight away.
Environment=PYTHONUNBUFFERED=1
# Tag the app's own messages, so the icon can find them in the log.
SyslogIdentifier={LOG_TAG}
# Start it again 5 seconds after a crash.
Restart=on-failure
RestartSec=5

[Install]
# For a user service, this means: start at login.
WantedBy=default.target
"""


def desktop_text(project):
    """The launcher (app icon) file's contents for this project folder."""
    run = f"{desktop_quote(venv_python(project))} {desktop_quote(project / 'tools' / 'open_planner.py')}"
    return f"""\
# RS3 Planner app icon. Written by tools/install_desktop.py.
[Desktop Entry]
Type=Application
Name=RS3 Planner
Comment=Plan your RuneScape 3 sessions (opens in your browser)
Icon={project / 'static' / 'icons' / 'app-icon.svg'}
Exec={run}
Terminal=false
Categories=Game;
Actions=restart;stop;

[Desktop Action restart]
Name=Restart RS3 Planner
Exec={run} --restart

[Desktop Action stop]
Name=Stop RS3 Planner
Exec={run} --stop
"""


def write_file(path, text):
    """Write one file. Returns what happened, as a line to print."""
    if path.exists():
        if path.read_text(encoding="utf-8") == text:
            return f"Already up to date: {path}"
        path.write_text(text, encoding="utf-8")
        return f"Replaced (it was different): {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return f"Written: {path}"


def run_command(args):
    """Run one command. If it fails, raise InstallError with its own message."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InstallError(f"Couldn't run {' '.join(args)}: {error}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise InstallError(f"This command failed: {' '.join(args)}\n{detail}")


def install(project, home, run=run_command, answers=app_answers, active=service_active, sleep=time.sleep):
    """
    Write both files, then turn the service on and wait for the app.
    Returns the lines to print. Raises InstallError (having written nothing,
    unless it says otherwise) when something must be fixed first.
    """
    problem = path_problem(project)
    if problem:
        raise InstallError(problem)
    if not venv_python(project).exists():
        raise InstallError(NO_VENV_MESSAGE)
    if answers() and not active():
        raise InstallError(BUSY_MESSAGE)

    lines = [write_file(service_path(home), service_text(project)),
             write_file(desktop_path(home), desktop_text(project))]
    try:
        run(["systemctl", "--user", "daemon-reload"])        # reread the settings
        run(["systemctl", "--user", "enable", UNIT])         # start it at every login
        run(["systemctl", "--user", "restart", UNIT])        # start it now (or again, with new settings)
    except InstallError as error:
        raise InstallError(f"{error}\nThe two files were written, but the app wasn't turned on.")

    if wait_for_app(answers, sleep):
        lines.append(f"The app is running: {app_url()} (or click the RS3 Planner icon).")
    else:
        lines.append(f"The app didn't answer within {WAIT_SECONDS} seconds. "
                     f"Its log: journalctl --user -u {SERVICE}")
    lines.append("To undo: python3 tools/install_desktop.py --remove")
    return lines


def remove(home, run=run_command):
    """Turn the service off and delete both files. Returns the lines to print."""
    service, launcher = service_path(home), desktop_path(home)
    if not service.exists() and not launcher.exists():
        return ["Nothing to remove: RS3 Planner wasn't installed."]
    lines = []
    if service.exists():
        run(["systemctl", "--user", "disable", "--now", UNIT])   # stop it, and not at login any more
        service.unlink()
        lines.append(f"Removed: {service}")
        run(["systemctl", "--user", "daemon-reload"])
    if launcher.exists():
        launcher.unlink()
        lines.append(f"Removed: {launcher}")
    lines.append("Your data/ folder (answers, goals, snapshots) was not touched.")
    return lines


def show(project, home):
    """Both files and where they would go. Writes and runs nothing."""
    problem = path_problem(project)
    if problem:
        raise InstallError(problem)
    return [f"Would write {service_path(home)}:", "", service_text(project),
            f"Would write {desktop_path(home)}:", "", desktop_text(project),
            "Nothing was changed. Run without --show to install."]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start the RS3 Planner at login, with an app icon (Linux).")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--show", action="store_true", help="show the two files; change nothing")
    choice.add_argument("--remove", action="store_true", help="undo the install")
    args = parser.parse_args(argv)
    home = Path.home()
    try:
        if args.show:
            lines = show(PROJECT, home)
        elif args.remove:
            lines = remove(home)
        else:
            lines = install(PROJECT, home)
    except InstallError as error:
        sys.exit(str(error))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the new tests, then the whole suite**

Run: `python3 -m unittest tests.test_install_desktop -v`
Expected: 23 tests, all PASS.

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: `Ran 187 tests` … `OK` (164 + 23).

Run: `python3 check_methods.py | tail -2`
Expected: the usual summary, 81 methods, no problems.

- [ ] **Step 6: Check the generated files with Ubuntu's own checkers (scratch only, nothing installed)**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/desktop-launcher
mkdir -p "$W/check"
python3 - <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, "tools")
import install_desktop as d
W = Path("/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/desktop-launcher")
# 1. The real project folder.
(W / "check" / "rs3-planner.service").write_text(d.service_text(d.PROJECT), encoding="utf-8")
(W / "check" / "rs3-planner.desktop").write_text(d.desktop_text(d.PROJECT), encoding="utf-8")
# 2. A scratch project whose path has a space, ", $, ' and `; its python is a link to the real one.
odd = W / "odd" / "My \"RS\" $tool 'x' `y`"
(odd / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
link = odd / ".venv" / "bin" / "python"
if not link.exists():
    link.symlink_to(d.PROJECT / ".venv" / "bin" / "python")
(odd / "app.py").touch()
(odd / "tools").mkdir(exist_ok=True)
(odd / "tools" / "open_planner.py").touch()
(W / "odd" / "rs3-planner.service").write_text(d.service_text(odd), encoding="utf-8")
(W / "odd" / "rs3-planner.desktop").write_text(d.desktop_text(odd), encoding="utf-8")
print("written")
EOF
systemd-analyze --user verify "$W/check/rs3-planner.service"; echo "verify exit=$?"
desktop-file-validate "$W/check/rs3-planner.desktop"; echo "validate exit=$?"
systemd-analyze --user verify "$W/odd/rs3-planner.service"; echo "verify odd exit=$?"
desktop-file-validate "$W/odd/rs3-planner.desktop"; echo "validate odd exit=$?"
```

Expected: `written`, then four `exit=0` lines with no error text. (`desktop-file-validate` may print *hints*; anything marked `error` is a failure. If any check reports an error: stop, show Chris the exact output, explain, and wait.)

Then confirm how the launcher's `Exec` line is read back, using GLib's own parser through the system Python (read-only; skip with a note if `gi` is not installed):

```bash
/usr/bin/python3 - <<'EOF'
import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib
W = "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/desktop-launcher"
for name in ("check", "odd"):
    key_file = GLib.KeyFile()
    key_file.load_from_file(f"{W}/{name}/rs3-planner.desktop", GLib.KeyFileFlags.NONE)
    exec_line = key_file.get_string("Desktop Entry", "Exec")      # string rule undone
    ok, argv = GLib.shell_parse_argv(exec_line)                  # quoting rule undone
    print(name, argv)
EOF
```

Expected: for `check`, `['/home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python', '/home/chris-baron/Repos/RS-Planning-Tool/tools/open_planner.py']`; for `odd`, two arguments whose text contains exactly `My "RS" $tool 'x' `y`` (the original folder name, unchanged).

- [ ] **Step 7: Commit**

```bash
git add static/icons/app-icon.svg tools/install_desktop.py tests/test_install_desktop.py
git commit -m "Desktop launcher: the installer (service at login, app icon) and the swords icon

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 8: Stop and wait for Chris**

Show him `python3 tools/install_desktop.py --show` (the two files for his real folder) and the four checker results. Explain each line of both files in plain words. Do not install. Wait for his OK before Task 3.

---

### Task 3: README section

**Files:**
- Modify: `README.md` (new section after "### Updating later", before "## Using the app")

**Interfaces:**
- Consumes: the commands and behaviour from Tasks 1 and 2.
- Produces: nothing used by code.

- [ ] **Step 1: Add the section**

Insert this block in `README.md` directly before the line `## Using the app`:

````markdown
### Start it without a terminal (Linux)

On Linux you can have the app start by itself in the background each time you
log in, with an **RS3 Planner** icon (crossed swords) in your app list that opens
it in your browser. After the one-time setup above, run this once from the
project folder:

```bash
python3 tools/install_desktop.py
```

It adds two small settings files to your own account (no password needed) and
starts the app. To see those two files first, without changing anything:

```bash
python3 tools/install_desktop.py --show
```

- **Open it:** click the **RS3 Planner** icon. You can pin it to the dock
  (right-click it, then **Pin to Dash**). If the app isn't running, the icon
  starts it first.
- **Restart:** right-click the icon, then **Restart RS3 Planner**. Do this after
  editing `data/methods.json` (the app reads it only when it starts). A restart
  also fetches fresh stats.
- **Stop:** right-click the icon, then **Stop RS3 Planner**. It stays stopped
  until you click the icon again or next log in.
- It stops when you log out and starts again when you log in.
- If it doesn't start, a notification says why. The full log:
  `journalctl --user -u rs3-planner`
- The terminal way (`.venv/bin/python app.py`) still works, but only one copy can
  use the app's address. If the terminal says "address already in use", choose
  **Stop** on the icon first.
- Moved the project folder? Run the install again from the new folder. The
  folder's path must not contain `%`, `\` or a line break.

To remove it (your answers, goals and snapshots in `data/` stay):

```bash
python3 tools/install_desktop.py --remove
```
````

- [ ] **Step 2: Check the README still reads in order and nothing else changed**

Run: `git diff --stat README.md && grep -n "^##\|^###" README.md | head -20`
Expected: only additions in `README.md`; the new heading `### Start it without a terminal (Linux)` sits between `### Updating later` and `## Using the app`. The "Good to know" line about 127.0.0.1 is unchanged.

- [ ] **Step 3: Run the whole suite**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: `Ran 187 tests` … `OK`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "README: start it without a terminal (Linux)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Stop and wait for Chris**

Ask him to read the new section. Then give him the install command for Task 4 and wait.

---

### Task 4: Chris installs; live checks

**Files:** none changed (scratch only). If any check fails, stop and explain; a fix becomes its own step with Chris's approval.

**Interfaces:**
- Consumes: everything above.
- Produces: proof that it works on the real PC.

- [ ] **Step 1: Before Chris installs: nothing is on port 8080**

Run: `ss -ltn | grep ':8080' || echo "port 8080 free"`
Expected: `port 8080 free`. If something is listening, tell Chris what (`ss -ltnp | grep 8080`) and wait.

- [ ] **Step 2: Chris installs**

Give Chris this command to run himself, from the project folder, in his terminal:

```bash
python3 tools/install_desktop.py
```

Expected output: two `Written:` lines, `The app is running: http://127.0.0.1:8080 (or click the RS3 Planner icon).`, and the undo line. If it prints anything else: stop and explain. Note for Chris: starting the service fetches the remembered player from RuneMetrics once, as a normal start does.

- [ ] **Step 3: Read-only checks**

```bash
systemctl --user is-active rs3-planner
systemctl --user is-enabled rs3-planner
ss -ltn | grep ':8080'
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://127.0.0.1:8080/
journalctl --user -t rs3-planner -n 5 -o cat --no-pager
```

Expected: `active`; `enabled`; one line `127.0.0.1:8080` (no `0.0.0.0`, no other address); an HTTP reply (`200`, or `307` towards `/player`); the app's own start-up lines (e.g. "Fetching … from RuneMetrics").

Then open `http://127.0.0.1:8080` in the built-in browser with `preview_start` (`url`, not the `rs3-planner-gui` config, which would try to start a second copy on 8080) and confirm Home loads with the current player and "Stats updated" time.

- [ ] **Step 4: The icon**

Chris opens the app grid, finds **RS3 Planner** with the swords icon, and clicks it: the browser opens on the app. Then right-click → **Restart RS3 Planner**: the browser opens again after a moment, and `journalctl --user -t rs3-planner -n 3 -o cat --no-pager` shows a new start. Then right-click → **Stop RS3 Planner**: the "RS3 Planner stopped" notification appears, and:

```bash
systemctl --user is-active rs3-planner; systemctl --user is-failed rs3-planner
```

Expected: `inactive` and `inactive` (a clean stop, not `failed`). Then Chris clicks the icon once more: the app starts and the browser opens.

(With Chris's explicit OK, Claude may do these clicks with desktop control instead; otherwise Chris does them and reports.)

- [ ] **Step 5: Live failure test (never touches Chris's service or data)**

Make a throwaway copy with a broken data file, and a scratch script that runs the opener's real log reading and notification against a temporary service `rs3-planner-test` on port 8091:

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/desktop-launcher
rm -rf "$W/broken" && mkdir -p "$W/broken"
cd /home/chris-baron/Repos/RS-Planning-Tool
cp -r app.py account.py check_methods.py plan_session.py player_cache.py players.py progress.py \
      quest_path.py rs3_planner.py snapshots.py static "$W/broken/"
mkdir -p "$W/broken/data" && cp data/methods.json data/unlocks.json data/quests.json "$W/broken/data/"
sed -i 's/^PORT = 8080/PORT = 8091/' "$W/broken/app.py"
printf '{ this is not JSON\n' > "$W/broken/data/methods.json"
cat > "$W/live_failure.py" <<'EOF'
"""Scratch only: the opener's real log reading and notification, against a throwaway service."""
import subprocess, sys
sys.path.insert(0, "/home/chris-baron/Repos/RS-Planning-Tool/tools")
import open_planner

W = "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/desktop-launcher"
PYTHON = "/home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python"
open_planner.SERVICE = "rs3-planner-test"
open_planner.LOG_TAG = "rs3-planner-test"
open_planner.PORT = 8091

class TestDesktop(open_planner.Desktop):
    """The real Desktop, except that "start" launches a temporary service
    (gone once it stops) running the broken copy."""
    def systemctl(self, *args):
        if args[0] == "start":
            command = ["systemd-run", "--user", "--collect", "--unit=rs3-planner-test",
                       "--property=SyslogIdentifier=rs3-planner-test", f"--working-directory={W}/broken",
                       PYTHON, f"{W}/broken/app.py"]
            result = subprocess.run(command, capture_output=True, text=True)
            return result.returncode == 0, (result.stderr or result.stdout).strip()
        return super().systemctl(*args)

open_planner.start_and_open(TestDesktop(), "start")
EOF
.venv/bin/python "$W/live_failure.py"
```

Expected: after about 20 seconds, the notification **"RS3 Planner didn't start"** appears (Chris confirms he sees it), its text includes `check_methods.py`'s message about `methods.json` (the JSON syntax error and its line), and the last line reads `Full log: journalctl --user -u rs3-planner-test`. Then:

```bash
systemctl --user status rs3-planner-test 2>&1 | head -2
systemctl --user is-active rs3-planner
```

Expected: the test service is gone ("could not be found"); Chris's `rs3-planner` is unaffected.

- [ ] **Step 6: Clean up the scratch copies**

```bash
rm -rf /home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/desktop-launcher
```

- [ ] **Step 7: Final checks and report**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -3` → `Ran 187 tests` … `OK`.
Run: `python3 check_methods.py | tail -2` → 81 methods, no problems.
Run: `git status --short` → clean.

Report to Chris what was verified and how. Ask before pushing.
