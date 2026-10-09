"""
RS3 Planner - running as a bundle (the Windows app)
===================================================

The Windows app is this same program packed by PyInstaller (see
tools/build_exe.py) into a folder with its own copy of Python. This file
answers the questions that only matter there:

  is_bundled()       am I running from a bundle, or from the project folder?
  user_data_dir()    where does this user's saved data go? (Not inside the
                     bundle: every new version replaces that folder.)
  version_text()     which build is this? (the build writes it into the bundle)
  planner_answers()  is RS3 Planner already running on this port?
  choose_port()      which port should this copy use, if any?
  stop()             say what went wrong and wait, so the window doesn't vanish

Run from the project folder (the service, the terminal, the tests), none of
this changes anything: player data stays in data/players/ and the port 8080.

Standard library only, so the tests can load it without NiceGUI.
"""

import http.client
import os
import re
import sys
import urllib.request
from pathlib import Path

APP_NAME = "RS3 Planner"
PREFERRED_PORT = 8095   # the Windows app's usual port (the project version keeps 8080)
LAST_PORT = 8999        # the end of NiceGUI's own port search (native.find_open_port)
VERSION_FILE = Path(__file__).parent / "version.txt"   # in a bundle: beside the bundled code
TITLE = re.compile(r"<title>[^<]*RS3 Planner</title>")  # every page's title ends in "RS3 Planner"


def is_bundled():
    """True inside a PyInstaller bundle: its start-up sets sys.frozen and sys._MEIPASS
    (PyInstaller's "Run-time Information" page)."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def stop(message):
    """
    Print what went wrong and end the program. In a bundle, wait for Enter first:
    a double-clicked program's window closes the moment the program ends, and the
    message would vanish before anyone could read it.
    """
    print(message, flush=True)
    if is_bundled():
        try:
            input("Press Enter to close.")
        except EOFError:   # no keyboard attached (e.g. started by the smoke test)
            pass
    sys.exit(1)


def user_data_dir(env=None, platform=None, home=None):
    """
    The folder for this user's saved data, outside the bundle:
      Windows: %LOCALAPPDATA%\\RS3 Planner (Microsoft's per-user "LocalAppData" folder)
      Linux:   $XDG_DATA_HOME/rs3-planner, or ~/.local/share/rs3-planner when that is
               unset or empty (the freedesktop.org "XDG Base Directory" standard)
    env, platform and home are for the tests; normally the real ones are used.
    """
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else home
    if platform == "win32":
        base = env.get("LOCALAPPDATA", "")
        if not base:
            stop("RS3 Planner can't find your Windows app-data folder (LOCALAPPDATA isn't set), "
                 "so it has nowhere to save your data.")
        return Path(base) / APP_NAME
    if platform.startswith("linux"):
        base = env.get("XDG_DATA_HOME", "")
        return (Path(base) if base else home / ".local" / "share") / "rs3-planner"
    stop(f"RS3 Planner's app version runs on Windows and Linux only (this computer is {platform}).")


def version_text(path=VERSION_FILE):
    """The build's version line, e.g. 'RS3 Planner 2026-10-12 (ea96c3c)'.
    None when there is no version file (running from source), or it is blank or garbled."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return text or None


def read_page(url, timeout=2):
    """The page at `url` as text, or None if nothing usable answers within `timeout` seconds."""
    # No proxy: the app is on this computer, so never ask a proxy server for it.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=timeout) as reply:
            return reply.read(65536).decode("utf-8", errors="replace")
    except (OSError, ValueError, http.client.HTTPException):
        # Refused, timed out, an error page, or a reply that isn't a web page at all.
        return None


def planner_answers(port, fetch=read_page):
    """True only if RS3 Planner itself answers on this port: its Choose player page has
    "RS3 Planner" in its title. Another program's page, an error or silence: False.
    `fetch` is for the tests; normally read_page is used."""
    page = fetch(f"http://127.0.0.1:{port}/player")
    return page is not None and TITLE.search(page) is not None


def choose_port(answers, find_free, preferred=PREFERRED_PORT):
    """
    Which port this copy should use, as (already_running, port):
      (True, 8095)   RS3 Planner already answers on 8095: open that, don't start a second copy
      (False, 8095)  8095 is free: use it
      (False, 8096)  another program has 8095: use the first free port after it
    answers(port) is planner_answers; find_free(first, last) is NiceGUI's
    native.find_open_port. Both are passed in so the tests can use fakes.
    """
    if answers(preferred):
        return True, preferred
    return False, find_free(preferred, LAST_PORT)
