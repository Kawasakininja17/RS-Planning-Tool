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
