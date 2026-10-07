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
import os
import subprocess
import sys
import time
from pathlib import Path

from open_planner import (
    LOG_TAG, SERVICE, WAIT_SECONDS, app_answers, app_url, service_active, wait_for_app,
)

PROJECT = Path(__file__).resolve().parent.parent
UNIT = f"{SERVICE}.service"

# Refused rather than quoted (see the spec): systemd won't run a program whose path
# has a quote in it; "$" would need "$$" in some places of a service file but not
# others; systemd's manual doesn't say whether "%" is special in WorkingDirectory=;
# and a "\" needs four backslashes in a launcher.
REFUSED_CHARACTERS = ("%", "\\", '"', "'", "$", "\n", "\r")
REFUSED_MESSAGE = ("Rename the project folder so its path has no %, \\, \", ' or $ or line break, "
                   "then run the install again.")
NO_VENV_MESSAGE = ("There's no .venv/bin/python in the project folder yet. Do the README's "
                   "one-time setup first (Install, step 2), then run the install again.")
ROOT_MESSAGE = ("Run this without sudo: the app is installed for your own account, "
                "so no password is needed.")
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
    """One path as a single quoted word on a systemd ExecStart= line, so spaces are safe.
    Nothing inside needs escaping: path_problem() has already refused quotes, "$" and "%"."""
    return f'"{path}"'


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
        try:
            # After 3 failed starts (e.g. an earlier install with a broken data file) Ubuntu
            # refuses more for a minute; this clears that. Only a help: if it fails, the
            # restart below reports any real problem.
            run(["systemctl", "--user", "reset-failed", UNIT])
        except InstallError:
            pass
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
    # With sudo, Path.home() would be the administrator's home folder (/root), not yours.
    if os.geteuid() == 0:
        sys.exit(ROOT_MESSAGE)
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
