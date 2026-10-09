# Windows App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A one-folder Windows build of the RS3 Planner (a zip with `RS3 Planner.exe`) that clan members start by double-clicking, built on GitHub's Windows machines after a full rehearsal on Chris's Linux PC.

**Architecture:** A new standard-library module `bundle.py` answers the questions that only matter inside a PyInstaller bundle (am I bundled, where does this user's data go, which build is this, is RS3 Planner already on port 8095, which port to use). `players.py` uses it for `PLAYERS_DIR`; `app.py` uses it in a new start-up function, keeping the source run exactly as today (8080, no browser). `tools/build_exe.py` runs NiceGUI's `nicegui-pack` with an exact allowlist of data files, checks the result, guards against player data and zips it; `tools/smoke_test_exe.py` starts the built app and checks it from outside. A manual-only GitHub workflow runs tests, build and smoke test on Windows and keeps the zip as an artifact; releases are made by hand.

**Tech Stack:** Python 3.14; NiceGUI 3.17.1 (app venv `.venv/` and build venv `.venv-build/`); PyInstaller 6.22.3 and Pillow 12.3.0 (build venv only); `rsvg-convert` from Ubuntu's `librsvg2-bin` (icon, once); GitHub Actions (`windows-2025`, `actions/checkout@v7.0.1`, `actions/setup-python@v7.0.0`, `actions/upload-artifact@v7.0.2`); standard library `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-09-windows-exe-design.md`

## Global Constraints

- Run from source (service, terminal, tests), nothing changes: `PORT = 8080`, `show=False`, player data in `data/players/`, the same two locks. `tools/open_planner.py` and `tools/install_desktop.py` are not touched.
- In a bundle: data in `%LOCALAPPDATA%\RS3 Planner` (Windows) or `$XDG_DATA_HOME/rs3-planner`, default `~/.local/share/rs3-planner` (Linux); port `8095` preferred, else `native.find_open_port(8095, 8999)`; already running on 8095 → open the browser there and exit; `show=True`; version line printed at start.
- The bundle gets exactly `data/methods.json`, `data/quests.json`, `data/unlocks.json` (to `data/`), `static/` (to `static/`) and the version file. Never the `data/` folder, never `data/players/`.
- Program name `RS3 Planner`, zip `RS3-Planner-<YYYY-MM-DD>.zip`, contents folder `_internal`, icon `static/icons/app-icon.ico` made from `app-icon.svg`.
- Browser tab, no `--windowed`, no native window, one folder (`--onedir`), unsigned.
- Installs only into `.venv-build/` (never `.venv/`, never system-wide). System changes are Chris's to make: Chris runs `sudo apt install librsvg2-bin`.
- `bundle.py`, `tools/build_exe.py`, `tools/smoke_test_exe.py` and all tests use the standard library only. Tests never import `app.py`, NiceGUI or PyInstaller, never use the internet, never touch real player files or the real home folder.
- Code simple and commented in plain words, matching the existing files. Text checks on `app.py` use `assertTrue`/`assertFalse` with a short message, matched at a line's start.
- Tests: `python3 -m unittest discover -s tests -v` (240 before this plan). Data check: `python3 check_methods.py` (81 methods).
- Scratch: `W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe` (git-ignored), never `/tmp`. Scratch copies of player data are deleted at the end of the task that made them.
- Chris's service holds 8080: never stop, restart or reinstall `rs3-planner` without asking. Claude's frozen source copies use 8091; bundles and the bundle/source comparison use 8095. Tell Chris whenever a preview server is running, and that the bundle opens tabs in Chris's own browser by itself.
- RuneMetrics: Task 2 freezes one profile + one quests reply; Task 5 makes four live player fetches (two runs of Hels Glasglo, two of the second test name). No other fetches.
- No other player's name in the repo, commits, builds or messages. Scratch copies hold only `hels+glasglo`. Tests use "Some Player". The second public test name is asked from Chris in Task 5 and used only live. Before any push: count (never print) other players' folder names in the unpushed diff and commit messages.
- Publishing (push, release) only on Chris's yes, each time. `gh` is not installed: releases are made by Chris on GitHub's website.
- Stop and wait for Chris after each task. Commit after each task (title line, blank line, body, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Use absolute paths in commands (a `cd` changes the session's folder).
- If any step errors or a check doesn't match, stop that task, explain (what failed, the error in plain words, likely cause, what's done, what's left, the proper fix) and wait for Chris.

## Review Focus

1. **A RuneScape name Windows refuses as a folder name** ("Con", "Aux", "Nul", "Prn", "Com1"–"Com9", "Lpt1"–"Lpt9", per Microsoft's "Naming Files, Paths, and Namespaces") → that player must still work on Windows. `folder_name` adds a `+` to such names (`aux+`); no real name can end in `+`. **Not in the spec: found while planning, Chris to approve or drop.** Pinned in Task 1 (`test_windows_reserved_names_get_a_plus`, `test_reserved_name_player_can_save`).
2. **A Windows user folder with spaces or accents** (`C:\Users\José Ñúñez\AppData\Local`) → data is saved there. Pinned in Task 1 (`test_windows_folder_with_spaces_and_accents`) and in the smoke test's scratch folder `build/smoke data é` (Tasks 4–6).
3. **Port 8095 held by another web program**, or one that hangs or answers garbage → never mistaken for RS3 Planner; the app takes the next free port and says which. Pinned in Task 1 (`ReadPageTests`, `PlannerAnswersTests`) and Task 5 Step 6 (a real program on 8095).
4. **A missing, blank or garbled version file** → "RS3 Planner (version unknown)", no crash. Pinned in Task 1 (`VersionTextTests`).
5. **Files a build leaves behind** (`build/`, `dist/`, `RS3 Planner.spec`, `.venv-build/`) → never committed and never make the version say "uncommitted changes". Pinned in Task 3 Step 1 (`git check-ignore`), Task 5 Step 2 (a version line without "uncommitted changes", the build's output kept outside the project) and Task 5 Step 3 (`git status --short` empty after a build).

## File map

| File | Change | Responsibility |
|---|---|---|
| `bundle.py` | create | `APP_NAME`, `PREFERRED_PORT`, `LAST_PORT`, `VERSION_FILE`, `is_bundled`, `stop`, `user_data_dir`, `version_text`, `read_page`, `planner_answers`, `choose_port` |
| `players.py` | modify | `default_players_dir()` → `PLAYERS_DIR`; `WINDOWS_RESERVED` in `folder_name` |
| `app.py` | modify | Docstring; imports; `switch_on_locks(port)`, `start_port()`, `say_running()`; the main guard |
| `tests/test_bundle.py` | create | Unit tests for `bundle.py`; text checks on `app.py`'s start-up |
| `tests/test_players.py` | modify | Reserved names; `default_players_dir` |
| `tests/test_host_lock.py` | modify | The two lock-wiring checks follow the move into `switch_on_locks(port)` |
| `.gitignore` | modify | `build/`, `dist/`, `.venv-build/`, `/RS3 Planner.spec` |
| `requirements-build.txt` | create | The build toolbox, pinned |
| `static/icons/app-icon.png`, `app-icon.ico` | create | The swords icon for Windows |
| `tools/build_exe.py` | create | Build, check, guard, zip |
| `tools/smoke_test_exe.py` | create | Start the built app and check it from outside |
| `tests/test_build_exe.py` | create | Unit tests for `build_exe.py`'s pure parts |
| `.github/workflows/build-windows.yml` | create | Manual Windows build on GitHub |
| `README.md` | modify | "Windows app (for clan members)", "Building the Windows app" |

Scratch only (never committed), in `$W`: `frozen/`, `data_template/`, `run_frozen.py`, `ws_check.py`, `before/`, `after/`, `src/`, `xdg*/`, `*.sha`, `artifact/`. `.claude/launch.json` (git-excluded) gets temporary entries, removed when the task that added them ends.

---

### Task 1: `bundle.py`, and `players.py` uses it

**Files:**
- Create: `bundle.py`, `tests/test_bundle.py`
- Modify: `players.py` (docstring, imports, `folder_name`, `PLAYERS_DIR`), `tests/test_players.py`

**Interfaces:**
- Consumes: nothing from the project.
- Produces (used by Tasks 2, 4, 5):
  - `APP_NAME = "RS3 Planner"`, `PREFERRED_PORT = 8095`, `LAST_PORT = 8999`, `VERSION_FILE: Path` (beside `bundle.py`)
  - `is_bundled() -> bool`
  - `stop(message: str) -> NoReturn` (prints; in a bundle waits for Enter; `sys.exit(1)`)
  - `user_data_dir(env=None, platform=None, home=None) -> Path`
  - `version_text(path: Path = VERSION_FILE) -> str | None`
  - `read_page(url: str, timeout: float = 2) -> str | None`
  - `planner_answers(port: int, fetch=read_page) -> bool`
  - `choose_port(answers, find_free, preferred: int = PREFERRED_PORT) -> tuple[bool, int]`
  - `players.default_players_dir() -> Path`, `players.WINDOWS_RESERVED: set[str]`

- [ ] **Step 1: Write the failing tests for `bundle.py`**

Create `tests/test_bundle.py`:

```python
"""Tests for bundle.py (running as the Windows app).

Nothing here uses the internet or the real home folder: the outside world is
passed in as fakes. The read_page tests use tiny servers on 127.0.0.1 only.
"""

import io
import socket
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import bundle

PROJECT = Path(__file__).resolve().parent.parent
HOME = Path("/home/fake")   # never the real home folder


class IsBundledTests(unittest.TestCase):
    def test_tests_run_from_source(self):
        self.assertFalse(bundle.is_bundled())

    def test_bundle_has_frozen_and_meipass(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "_MEIPASS", "/fake/_internal", create=True):
            self.assertTrue(bundle.is_bundled())

    def test_frozen_alone_is_not_a_pyinstaller_bundle(self):
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertFalse(bundle.is_bundled())


class StopTests(unittest.TestCase):
    def test_from_source_it_prints_and_exits_without_waiting(self):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("builtins.input") as asked, \
                self.assertRaises(SystemExit) as stopped:
            bundle.stop("Something went wrong.")
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(out.getvalue(), "Something went wrong.\n")
        asked.assert_not_called()

    def test_in_a_bundle_it_waits_for_enter(self):
        with redirect_stdout(io.StringIO()), mock.patch.object(bundle, "is_bundled", return_value=True), \
                mock.patch("builtins.input") as asked, self.assertRaises(SystemExit):
            bundle.stop("Something went wrong.")
        asked.assert_called_once_with("Press Enter to close.")

    def test_in_a_bundle_with_no_keyboard_it_still_exits(self):
        with redirect_stdout(io.StringIO()), mock.patch.object(bundle, "is_bundled", return_value=True), \
                mock.patch("builtins.input", side_effect=EOFError), self.assertRaises(SystemExit) as stopped:
            bundle.stop("Something went wrong.")
        self.assertEqual(stopped.exception.code, 1)


class UserDataDirTests(unittest.TestCase):
    def test_windows_uses_localappdata(self):
        env = {"LOCALAPPDATA": r"C:\Users\Some Player\AppData\Local"}
        self.assertEqual(bundle.user_data_dir(env, "win32", HOME),
                         Path(r"C:\Users\Some Player\AppData\Local") / "RS3 Planner")

    def test_windows_folder_with_spaces_and_accents(self):
        env = {"LOCALAPPDATA": "C:\\Users\\José Ñúñez\\AppData\\Local"}
        self.assertEqual(bundle.user_data_dir(env, "win32", HOME),
                         Path("C:\\Users\\José Ñúñez\\AppData\\Local") / "RS3 Planner")

    def test_windows_without_localappdata_stops_with_a_message(self):
        for env in ({}, {"LOCALAPPDATA": ""}):
            out = io.StringIO()
            with redirect_stdout(out), self.assertRaises(SystemExit) as stopped:
                bundle.user_data_dir(env, "win32", HOME)
            self.assertEqual(stopped.exception.code, 1)
            self.assertIn("LOCALAPPDATA", out.getvalue())

    def test_linux_uses_xdg_data_home(self):
        self.assertEqual(bundle.user_data_dir({"XDG_DATA_HOME": "/x/data"}, "linux", HOME),
                         Path("/x/data/rs3-planner"))

    def test_linux_unset_or_empty_uses_local_share(self):
        for env in ({}, {"XDG_DATA_HOME": ""}):
            self.assertEqual(bundle.user_data_dir(env, "linux", HOME),
                             HOME / ".local" / "share" / "rs3-planner")

    def test_other_systems_stop_with_a_message(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            bundle.user_data_dir({}, "darwin", HOME)
        self.assertIn("Windows and Linux only", out.getvalue())


class VersionTextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "version.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_line_without_its_line_break(self):
        self.file.write_text("RS3 Planner 2026-10-12 (ea96c3c)\n", encoding="utf-8")
        self.assertEqual(bundle.version_text(self.file), "RS3 Planner 2026-10-12 (ea96c3c)")

    def test_no_file_means_none(self):
        self.assertIsNone(bundle.version_text(self.file))

    def test_blank_file_means_none(self):
        self.file.write_text("  \n", encoding="utf-8")
        self.assertIsNone(bundle.version_text(self.file))

    def test_garbled_file_means_none(self):
        self.file.write_bytes(b"\xff\xfe\x00garbage")
        self.assertIsNone(bundle.version_text(self.file))

    def test_from_source_there_is_no_version_file(self):
        self.assertEqual(bundle.VERSION_FILE, Path(bundle.__file__).parent / "version.txt")
        self.assertIsNone(bundle.version_text())


class OneShotServer:
    """A tiny server on 127.0.0.1 (this computer only) that answers one connection
    with `reply`, or says nothing at all when reply is None."""

    def __init__(self, reply):
        self.reply = reply
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))   # 0: any free port
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:   # closed before anyone connected
            return
        with conn:
            conn.recv(4096)
            if self.reply is None:
                time.sleep(1)   # silent until the caller has given up
            else:
                conn.sendall(self.reply)

    def close(self):
        self.sock.close()


class ReadPageTests(unittest.TestCase):
    def ask(self, reply, timeout=2):
        server = OneShotServer(reply)
        try:
            return bundle.read_page(f"http://127.0.0.1:{server.port}/player", timeout=timeout)
        finally:
            server.close()

    def test_a_real_page_is_read(self):
        page = self.ask(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n"
                        b"<title>Choose player - RS3 Planner</title>")
        self.assertIn("<title>Choose player - RS3 Planner</title>", page)

    def test_garbage_means_none(self):
        self.assertIsNone(self.ask(b"garbage\r\n\r\n"))

    def test_silence_means_none(self):
        self.assertIsNone(self.ask(None, timeout=0.3))

    def test_nothing_listening_means_none(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        # The port was free a moment ago and nothing listens on it now.
        self.assertIsNone(bundle.read_page(f"http://127.0.0.1:{port}/player"))


class PlannerAnswersTests(unittest.TestCase):
    def test_rs3_planner_page(self):
        asked = []

        def fetch(url):
            asked.append(url)
            return "<html><head><title>Choose player - RS3 Planner</title></head></html>"

        self.assertTrue(bundle.planner_answers(8095, fetch))
        self.assertEqual(asked, ["http://127.0.0.1:8095/player"])

    def test_another_programs_page(self):
        self.assertFalse(bundle.planner_answers(8095, lambda url: "<title>Media server</title>"))

    def test_nothing_answers(self):
        self.assertFalse(bundle.planner_answers(8095, lambda url: None))

    def test_the_name_outside_the_title_does_not_count(self):
        page = "<title>My notes</title><p>RS3 Planner</p>"
        self.assertFalse(bundle.planner_answers(8095, lambda url: page))


class ChoosePortTests(unittest.TestCase):
    def test_already_running_on_8095(self):
        def find_free(first, last):
            raise AssertionError("no port search when RS3 Planner already runs")

        self.assertEqual(bundle.choose_port(lambda port: True, find_free), (True, 8095))

    def test_8095_free(self):
        searched = []

        def find_free(first, last):
            searched.append((first, last))
            return first

        self.assertEqual(bundle.choose_port(lambda port: False, find_free), (False, 8095))
        self.assertEqual(searched, [(8095, 8999)])

    def test_8095_taken_by_another_program(self):
        self.assertEqual(bundle.choose_port(lambda port: False, lambda first, last: 8096), (False, 8096))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest tests.test_bundle 2>&1 | tail -3`
Expected: `ModuleNotFoundError: No module named 'bundle'` (an import error counts as the failing run).

- [ ] **Step 3: Write `bundle.py`**

Create `bundle.py` in the project folder:

```python
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
```

- [ ] **Step 4: Run the `bundle.py` tests**

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest tests.test_bundle -v 2>&1 | tail -4`
Expected: `Ran 28 tests`, `OK`.

- [ ] **Step 5: Prove the tests can fail**

Break the code on purpose, one change at a time, and restore it after each:
1. In `planner_answers`, change `TITLE.search(page) is not None` to `"RS3 Planner" in page`. Expected: `test_the_name_outside_the_title_does_not_count` fails.
2. In `read_page`, change the `except` line to `except (OSError, ValueError):`. Expected: `test_garbage_means_none` fails (with an error).
3. In `user_data_dir`, change `if not base:` (the Windows one) to `if base is None:`. Expected: `test_windows_without_localappdata_stops_with_a_message` fails.

Run after each: `python3 -m unittest tests.test_bundle 2>&1 | tail -3`. After restoring all three: `Ran 28 tests`, `OK`, and the three lines read exactly as in Step 3.

- [ ] **Step 6: Write the failing tests for `players.py`**

In `tests/test_players.py`:

1. Below `from pathlib import Path` add `from unittest import mock`, and below `import players` add:

```python

PROJECT = Path(__file__).resolve().parent.parent
```

2. In `class FolderNameTests`, after `test_hyphen_underscore_and_space_stay_different`, add:

```python
    def test_windows_reserved_names_get_a_plus(self):
        # Windows refuses these as folder names (Microsoft, "Naming Files, Paths, and Namespaces").
        for name in ("Con", "PRN", "aux", "Nul", "Com1", "com9", "LPT1", "lpt9"):
            self.assertEqual(players.folder_name(name), name.lower() + "+")

    def test_names_that_only_look_reserved_are_unchanged(self):
        for name, folder in (("Con Man", "con+man"), ("Com10", "com10"), ("Auxy", "auxy"), ("Com0", "com0")):
            self.assertEqual(players.folder_name(name), folder)
```

3. In `class AnswersTests`, after `test_file_lives_in_player_folder`, add:

```python
    def test_reserved_name_player_can_save(self):
        players.save_answer("Aux", "smithing-autoheater", True)
        self.assertTrue((players.PLAYERS_DIR / "aux+" / "answers.json").is_file())
        self.assertEqual(players.read_answers("Aux"), {"smithing-autoheater": True})
```

4. Before `if __name__ == "__main__":` add:

```python
class DefaultPlayersDirTests(unittest.TestCase):
    """Where players' folders live: data/players/, or the user's own folder in a bundle."""

    def test_from_source_it_is_data_players(self):
        with mock.patch.object(players, "is_bundled", return_value=False):
            self.assertEqual(players.default_players_dir().resolve(), (PROJECT / "data" / "players").resolve())

    def test_in_a_bundle_it_is_the_user_data_folder(self):
        with mock.patch.object(players, "is_bundled", return_value=True), \
                mock.patch.object(players, "user_data_dir", return_value=Path("/fake/RS3 Planner")):
            self.assertEqual(players.default_players_dir(), Path("/fake/RS3 Planner/players"))

    def test_the_tests_themselves_run_from_source(self):
        self.assertEqual(players.default_players_dir().resolve(), (PROJECT / "data" / "players").resolve())
```

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest tests.test_players 2>&1 | tail -3`
Expected: `FAILED` (errors: `players` has no `is_bundled` / `default_players_dir`; failures: the reserved-name tests).

- [ ] **Step 7: Change `players.py`**

1. In the module docstring, after the line `data/players/current.txt remembers the player the app showed last.` add:

```

In the Windows app (a bundle, see bundle.py) the same folders live in the
user's own app-data folder instead, e.g. %LOCALAPPDATA%\RS3 Planner\players\.
```

2. Below `from pathlib import Path` add:

```python

from bundle import is_bundled, user_data_dir
```

3. Replace the line `PLAYERS_DIR = Path(__file__).parent / "data" / "players"` with:

```python
def default_players_dir():
    """
    Where players' folders live: data/players/ next to this file, as always.
    In a bundle (the Windows app) that would be inside the app itself, which every
    new version replaces, so it's the user's own app-data folder instead (bundle.py).
    """
    if is_bundled():
        return user_data_dir() / "players"
    return Path(__file__).parent / "data" / "players"


PLAYERS_DIR = default_players_dir()
```

4. Below `NAME_CHARACTERS = re.compile(r"[A-Za-z0-9 _-]+")` add:

```python

# Names Windows refuses for a file or folder (Microsoft's "Naming Files, Paths, and
# Namespaces" page). Every one of them is also a valid RuneScape name.
WINDOWS_RESERVED = ({"con", "prn", "aux", "nul"}
                    | {f"com{n}" for n in range(1, 10)} | {f"lpt{n}" for n in range(1, 10)})
```

5. Replace the whole `folder_name` function with:

```python
def folder_name(name):
    """
    'Hels Glasglo' -> 'hels+glasglo'.
    A '+' can never be part of a RuneScape name, so two players never share a
    folder. Hyphens and underscores are kept: the wiki's Display name page says
    an underscore is not the same as a space.
    A name Windows refuses as a folder (like 'Aux') gets a '+' at the end: 'aux+'.
    No real name ends in '+' (it stands for a space, and names never end in one),
    so this can't clash with another player.
    """
    folder = name.strip().lower().replace(" ", "+")
    if folder in WINDOWS_RESERVED:
        folder += "+"
    return folder
```

- [ ] **Step 8: Run all tests and the data check**

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 274 tests`, `OK` (240 + 28 + 6).
Run: `python3 check_methods.py | tail -2` → no problems, 81 methods.
Run: `python3 -c "import players; print(players.PLAYERS_DIR.resolve() == (players.Path.cwd() / 'data' / 'players').resolve())"` → `True`.

- [ ] **Step 9: Prove the new player tests can fail**

1. In `folder_name`, comment out the two `if folder in WINDOWS_RESERVED:` lines. Expected: `test_windows_reserved_names_get_a_plus` and `test_reserved_name_player_can_save` fail.
2. In `default_players_dir`, change `if is_bundled():` to `if True:`. Expected: `test_from_source_it_is_data_players` and `test_the_tests_themselves_run_from_source` fail. (Test runs never write anything: the first player-file test redirects `PLAYERS_DIR` to a temporary folder, and these tests only compare paths.)

Restore both; `python3 -m unittest discover -s tests 2>&1 | tail -3` → `Ran 274 tests`, `OK`.

- [ ] **Step 10: Commit**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git add bundle.py tests/test_bundle.py players.py tests/test_players.py
git commit -F - <<'EOF'
Windows app: bundle.py, and players live in the user's folder in a bundle

bundle.py answers what only matters inside the Windows app: is this a
bundle, where this user's data goes (%LOCALAPPDATA%\RS3 Planner, or
$XDG_DATA_HOME/rs3-planner), which build it is, whether RS3 Planner
already answers on port 8095, and which port to use. players.py takes
PLAYERS_DIR from it in a bundle; from source nothing changes. Names
Windows refuses as folders (Con, Aux, Com1...) get a '+' at the end.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git log --oneline -1
```

Stop and report to Chris (in particular Review Focus 1, the reserved-name change, which is not in the spec).

---

### Task 2: `app.py` start-up, and proof that nothing changed for the source app

**Files:**
- Modify: `app.py` (docstring, imports, the "Start" section and the main guard)
- Modify: `tests/test_host_lock.py` (`AppWiringTests`, two tests)
- Modify: `tests/test_bundle.py` (add `AppStartTests`)

**Interfaces:**
- Consumes (Task 1): `PREFERRED_PORT`, `LAST_PORT`, `choose_port`, `is_bundled`, `planner_answers`, `stop`, `user_data_dir`, `version_text` from `bundle`; `native.find_open_port(start_port, end_port)` from NiceGUI.
- Produces: `app.switch_on_locks(port)`, `app.start_port() -> int | None`, `app.say_running()`. The bundle's console lines: the version line (or `RS3 Planner (version unknown)`), `Your saved data: <folder>`, `RS3 Planner is already running: opening it in your browser.`, `Port 8095 is used by another program, so RS3 Planner uses port <n>.`, `RS3 Planner is running. Keep this window open; close it to stop the app.` (Task 4's smoke test looks for the first, second and third.)

- [ ] **Step 1: Freeze RuneMetrics replies and the player data (once)**

Check the remembered player first, without printing anyone else's name:

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
python3 -c "print(open('data/players/current.txt').read().strip() == 'Hels Glasglo')"
```

Expected: `True`. If `False`, stop and ask Chris (the copies must use only `hels+glasglo`).

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
cd /home/chris-baron/Repos/RS-Planning-Tool
git check-ignore -v $W/x
mkdir -p $W/frozen $W/data_template/players/hels+glasglo
cp .superpowers/sdd/host-lock/run_frozen.py .superpowers/sdd/host-lock/ws_check.py $W/
python3 -c "import json; from rs3_planner import load_profile, load_quests; json.dump(load_profile('Hels Glasglo'), open('$W/frozen/profile.json', 'w')); json.dump(load_quests('Hels Glasglo'), open('$W/frozen/quests.json', 'w'))"
python3 -c "import json; print(len(json.load(open('$W/frozen/profile.json'))['skillvalues']))"
cp -r data/players/hels+glasglo/answers.json data/players/hels+glasglo/last_goal data/players/hels+glasglo/snapshots $W/data_template/players/hels+glasglo/
echo "Hels Glasglo" > $W/data_template/players/current.txt
ls $W $W/frozen $W/data_template/players/hels+glasglo
```

Expected: `.superpowers/sdd/.gitignore:1:*` for the check; `29`; `data_template frozen run_frozen.py ws_check.py`; `profile.json quests.json`; `answers.json last_goal snapshots`. A private-profile message, a traceback or a number other than 29: stop and report.

- [ ] **Step 2: The "before" copy and its page texts**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
cd /home/chris-baron/Repos/RS-Planning-Tool
rm -rf $W/before && mkdir -p $W/before
git archive HEAD | tar -x -C $W/before
sed -i 's/^PORT = 8080$/PORT = 8091/' $W/before/app.py
grep -n "^PORT" $W/before/app.py
cp -r $W/data_template/players $W/before/data/players
ls $W/before/data/players
```

Expected: `PORT = 8091`; `current.txt  hels+glasglo`.

Add two entries to `"configurations"` in `.claude/launch.json` (keep `rs3-planner-gui` as it is):

```json
{
  "name": "rs3-exe-before",
  "runtimeExecutable": "/home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python",
  "runtimeArgs": ["/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/run_frozen.py",
                  "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/before",
                  "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/frozen", "app.py"],
  "port": 8091
},
{
  "name": "rs3-exe-after",
  "runtimeExecutable": "/home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python",
  "runtimeArgs": ["/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/run_frozen.py",
                  "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/after",
                  "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/frozen", "app.py"],
  "port": 8091
}
```

`preview_start {name: "rs3-exe-before"}`; tell Chris it is running on 8091. `preview_logs`: one `Fetching Hels Glasglo from RuneMetrics`, no traceback. For each of these 9 addresses under `http://127.0.0.1:8091`, `navigate` there, then run with `javascript_tool`:

`/player`, `/`, `/play`, `/plan?hours=5&session=afk&minutes=2`, `/plan?hours=5&session=active&minutes=2`, `/skills`, `/quests`, `/quests/goal`, `/progress`

```js
await new Promise(r => setTimeout(r, 1500));
const key = location.pathname + location.search;
const text = document.querySelector('main').innerText;
localStorage.setItem('before ' + key, text);
const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)));
`${[...bytes].map(b => b.toString(16).padStart(2, '0')).join('')}  ${text.length}  ${key}`
```

Write the 9 result lines to `$W/before.sha` with the Write tool. Any `null` or empty text: stop and report. Then `preview_stop`.

- [ ] **Step 3: Write the failing tests**

1. In `tests/test_host_lock.py`, replace the two methods `test_host_lock_is_switched_on_before_ui_run` and `test_origin_lock_is_switched_on_with_port` with:

```python
    def test_host_lock_is_switched_on_before_ui_run(self):
        line = "app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS, www_redirect=False)"
        # Inside switch_on_locks, at a line's start: a commented-out line doesn't count.
        self.assertTrue(re.search(r"(?m)^    " + re.escape(line), self.text), "the Host lock must be switched on")
        self.assertLess(self.text.index(line), self.text.index("ui.run("))

    def test_origin_lock_is_switched_on_with_the_chosen_port(self):
        line = "app.add_middleware(OriginLock, allowed_origins=allowed_origins(ALLOWED_HOSTS, port))"
        self.assertTrue(re.search(r"(?m)^    " + re.escape(line), self.text),
                        "the Origin lock must be built from the port the app really uses")
        self.assertLess(self.text.index(line), self.text.index("ui.run("))
```

2. In `tests/test_bundle.py`, add `import re` to the imports (after `import io`), and before `if __name__ == "__main__":` add:

```python
class AppStartTests(unittest.TestCase):
    """app.py can't be imported here (it starts NiceGUI), so read it as text."""

    def setUp(self):
        self.text = (PROJECT / "app.py").read_text(encoding="utf-8")

    def test_freeze_support_comes_first_in_the_main_guard(self):
        # Comment lines may sit between the guard and the call; no other line may.
        self.assertTrue(re.search(r'(?m)^if __name__ in \{"__main__", "__mp_main__"\}:\n(?:    #.*\n)*    freeze_support\(\)',
                                  self.text), "freeze_support() must be the first statement under the main guard")

    def test_from_source_the_port_stays_8080(self):
        self.assertTrue(re.search(r"(?m)^PORT = 8080$", self.text), "PORT must stay 8080")
        self.assertTrue(re.search(r"(?m)^    if not is_bundled\(\):\n        return PORT$", self.text),
                        "start_port() must return PORT when not bundled")

    def test_only_the_bundle_opens_the_browser(self):
        line = 'ui.run(host=HOST, port=port, title="RS3 Planner", dark=True, reload=False, show=is_bundled())'
        self.assertTrue(re.search(r"(?m)^ +" + re.escape(line), self.text),
                        "ui.run must use the chosen port and open the browser only in a bundle")

    def test_locks_follow_the_chosen_port(self):
        self.assertTrue(re.search(r"(?m)^        switch_on_locks\(port\)$", self.text),
                        "the locks must be switched on with the chosen port")
```

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest tests.test_host_lock tests.test_bundle 2>&1 | tail -3`
Expected: `FAILED (failures=6)` (the two changed lock tests and the four new ones).

- [ ] **Step 4: Change `app.py`**

1. Module docstring: after the line `that other websites start (see host_lock.py), so web pages can't use it.` add:

```

As the Windows app (a bundle made by tools/build_exe.py) it saves data in the
user's own app-data folder, uses port 8095 and opens the browser by itself
(see bundle.py). Run from the project folder, none of that changes.
```

2. Imports. Replace `import re` with:

```python
import re
import webbrowser   # the Windows app opens an already-running copy in the browser
from multiprocessing import freeze_support
```

Replace `from nicegui import app, run, ui` with `from nicegui import app, native, run, ui`. Below `from account import level_table, skill_rows` add:

```python
from bundle import (
    LAST_PORT, PREFERRED_PORT, choose_port, is_bundled, planner_answers, stop, user_data_dir, version_text,
)
```

3. Replace everything from the line `# Two locks in front of every page and live connection (they must be added before` to the end of the file with:

```python
def switch_on_locks(port):
    """
    Two locks in front of every page and live connection (they must be added before
    ui.run). Requests addressed to any other name are refused, which stops "DNS
    rebinding" web pages; requests started by another website are refused too.
    The second lock is built from the port the app really uses.
    """
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS, www_redirect=False)
    app.add_middleware(OriginLock, allowed_origins=allowed_origins(ALLOWED_HOSTS, port))


def start_port():
    """
    The port to listen on, or None when this copy shouldn't start.
    From the project folder: PORT (8080), exactly as always.
    As the Windows app (a bundle): 8095, or the first free port after it when
    another program has 8095. If RS3 Planner already runs on 8095 (a second
    double-click), the browser is opened there instead and None is returned.
    """
    if not is_bundled():
        return PORT
    print(version_text() or "RS3 Planner (version unknown)", flush=True)
    folder = user_data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    print(f"Your saved data: {folder}", flush=True)
    try:
        already_running, port = choose_port(planner_answers, native.find_open_port)
    except OSError:   # NiceGUI's search found no free port at all
        stop(f"RS3 Planner found no free port between {PREFERRED_PORT} and {LAST_PORT}, so it can't start.")
    if already_running:
        print("RS3 Planner is already running: opening it in your browser.", flush=True)
        webbrowser.open(f"http://{HOST}:{port}/")
        return None
    if port != PREFERRED_PORT:
        print(f"Port {PREFERRED_PORT} is used by another program, so RS3 Planner uses port {port}.", flush=True)
    return port


def say_running():
    """Shown in the Windows app's black window once the app answers."""
    print("RS3 Planner is running. Keep this window open; close it to stop the app.", flush=True)


app.add_static_files("/static", HERE / "static")
# "?v=..." is the stylesheet's last-change time: when the file changes, the address
# changes, so browsers fetch the new version instead of an old cached copy.
CSS_VERSION = int((HERE / "static" / "app.css").stat().st_mtime)
ui.add_head_html(f'<link rel="stylesheet" href="/static/app.css?v={CSS_VERSION}">', shared=True)

if __name__ in {"__main__", "__mp_main__"}:
    # First: in the Windows app, NiceGUI's helper processes start this same program,
    # and this call makes them do their job instead of starting the whole app again
    # (PyInstaller's "Common Issues and Pitfalls" page). Run from source it does nothing.
    freeze_support()
    port = start_port()
    if port is not None:
        switch_on_locks(port)
        if is_bundled():
            app.on_startup(say_running)
        try:
            ui.run(host=HOST, port=port, title="RS3 Planner", dark=True, reload=False, show=is_bundled())
        except KeyboardInterrupt:
            # Ctrl+C is the normal way to stop the app; say so instead of printing a traceback.
            print("\nRS3 Planner stopped.")
```

- [ ] **Step 5: Run the tests, the data check and a parse check**

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest discover -s tests 2>&1 | tail -3` → `Ran 278 tests`, `OK`.
Run: `python3 check_methods.py | tail -2` → no problems, 81 methods.
Run: `.venv/bin/python -c "import ast; ast.parse(open('app.py').read())" && echo parses` → `parses`.

- [ ] **Step 6: Prove the new text checks can fail**

1. Swap the two lines `freeze_support()` and `port = start_port()` in the main guard. Expected: `test_freeze_support_comes_first_in_the_main_guard` fails.
2. Comment out `        switch_on_locks(port)` (put `# ` after the indent). Expected: `test_locks_follow_the_chosen_port` fails.
3. In `switch_on_locks`, change `allowed_origins(ALLOWED_HOSTS, port)` to `allowed_origins(ALLOWED_HOSTS, PORT)`. Expected: `test_origin_lock_is_switched_on_with_the_chosen_port` fails.

Restore each; `python3 -m unittest discover -s tests 2>&1 | tail -3` → `Ran 278 tests`, `OK`.

- [ ] **Step 7: The "after" copy: same 9 page texts, and the locks**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
cd /home/chris-baron/Repos/RS-Planning-Tool
rm -rf $W/after && mkdir -p $W/after
git ls-files -z | xargs -0 tar -cf - | tar -x -C $W/after
cp bundle.py $W/after/
sed -i 's/^PORT = 8080$/PORT = 8091/' $W/after/app.py
grep -n "^PORT\|switch_on_locks(port)" $W/after/app.py
cp -r $W/data_template/players $W/after/data/players
```

Expected: `PORT = 8091` and `switch_on_locks(port)`.

`preview_start {name: "rs3-exe-after"}`; tell Chris. `preview_logs`: one `Fetching Hels Glasglo from RuneMetrics`, no traceback, and **no** `Your saved data` line (the source copy isn't a bundle). For the same 9 addresses under `http://127.0.0.1:8091`:

```js
await new Promise(r => setTimeout(r, 1500));
const key = location.pathname + location.search;
const before = localStorage.getItem('before ' + key);
const after = document.querySelector('main').innerText;
const keep = t => t.split('\n').filter(l => !l.startsWith('Stats updated') && !/snapshots? · last/.test(l)).join('\n');
const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(after)));
const hash = [...bytes].map(b => b.toString(16).padStart(2, '0')).join('');
const gone = before === null ? [] : before.split('\n').filter(l => !after.split('\n').includes(l));
const added = before === null ? [] : after.split('\n').filter(l => !before.split('\n').includes(l));
const verdict = before === null ? 'NO BEFORE' : keep(before) === keep(after) ? 'same'
  : 'DIFFERENT: removed [' + gone.join(' | ') + '] added [' + added.join(' | ') + ']';
`${hash}  ${after.length}  ${key}  ${verdict}  socket=${window.socket?.connected}`
```

Write the 9 lines to `$W/after.sha`. Expected: all `same`, `socket=true`. Anything else: stop and report.

Then the lock checks on the after copy:

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
B=http://127.0.0.1:8091
echo "1 own name:";           curl -s -o /dev/null -w "%{http_code}\n" $B/
echo "2 rebinding name:";     curl -s -w "  %{http_code}\n" --resolve evil.example:8091:127.0.0.1 http://evil.example:8091/
echo "3 foreign Origin:";     curl -s -w "  %{http_code}\n" -H "Origin: http://evil.example" $B/
echo "4 own Origin:";         curl -s -o /dev/null -w "%{http_code}\n" -H "Origin: http://127.0.0.1:8091" $B/
echo "5 websocket, foreign:"; python3 $W/ws_check.py 8091 http://evil.example
echo "6 websocket, own:";     python3 $W/ws_check.py 8091 http://127.0.0.1:8091
```

Expected: 1 `200`; 2 `Invalid host header  400`; 3 `Refused: this request came from another website.  403`; 4 `200`; 5 `HTTP/1.1 403 Forbidden`; 6 `HTTP/1.1 101 Switching Protocols`. `preview_stop`.

- [ ] **Step 8: Chris's service untouched, and clean up**

```bash
systemctl --user is-active rs3-planner
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/player
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
rm -rf $W/before $W/after
ls $W
```

Expected: `active`; `200`; `before.sha after.sha data_template frozen run_frozen.py ws_check.py` (`data_template` and `frozen` are kept for Task 5's lock checks and are deleted there). Remove the two `rs3-exe-*` entries from `.claude/launch.json`.

- [ ] **Step 9: Commit**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git add app.py tests/test_host_lock.py tests/test_bundle.py
git commit -F - <<'EOF'
Windows app: start-up for a bundle; the source app is unchanged

In a bundle, app.py prints the version line and where data is saved,
uses port 8095 (or the next free port, or opens an already-running copy
instead), builds both locks from that port and opens the browser.
freeze_support() comes first, as PyInstaller requires. Run from source
it still uses 8080 with no browser: the 9 screens read the same as
before on frozen RuneMetrics replies, and the lock checks still refuse.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git log --oneline -1
```

Stop and report to Chris. The service runs the old code until restarted; ask whether to restart it (Restart on the icon), then check `/player` answers 200 on 8080 again.

---

### Task 3: The build toolbox and the icon

**Files:**
- Create: `requirements-build.txt`, `static/icons/app-icon.png`, `static/icons/app-icon.ico`
- Modify: `.gitignore`

**Interfaces:**
- Produces (used by Tasks 4–6): `.venv-build/` with NiceGUI 3.17.1, PyInstaller 6.22.3, Pillow 12.3.0; `static/icons/app-icon.ico` (16–256 px).

- [ ] **Step 1: `.gitignore` and `requirements-build.txt`**

Append to `.gitignore`:

```
# The Windows app's build (tools/build_exe.py): its toolbox, work files and output
.venv-build/
build/
dist/
/RS3 Planner.spec
```

Create `requirements-build.txt`:

```
# The build toolbox for the Windows app (tools/build_exe.py). Install it into its
# own venv, never into .venv/ (the app's):
#   python3 -m venv .venv-build
#   .venv-build/bin/pip install -r requirements-build.txt
nicegui==3.17.1
pyinstaller==6.22.3
pillow==12.3.0
```

Check: `cd /home/chris-baron/Repos/RS-Planning-Tool && git check-ignore -v .venv-build/x build/x dist/x "RS3 Planner.spec"` → four lines, each naming `.gitignore`.

- [ ] **Step 2: Create the build toolbox**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
python3 -m venv .venv-build
.venv-build/bin/pip install -r requirements-build.txt
.venv-build/bin/python -c "import nicegui, PyInstaller, PIL; print(nicegui.__version__, PyInstaller.__version__, PIL.__version__)"
.venv/bin/pip freeze | grep -ic pyinstaller
```

Expected: `3.17.1 6.22.3 12.3.0`; `0` (the app's own `.venv/` is untouched). An install error: stop and report.

- [ ] **Step 3: Chris installs the SVG converter**

Ask Chris to run this in a terminal (it needs Chris's password; it installs GNOME's command-line SVG converter, `rsvg-convert`, from Ubuntu's own package `librsvg2-bin`, confirmed on packages.ubuntu.com for 26.04 "resolute"):

```bash
sudo apt install librsvg2-bin
```

Then check: `command -v rsvg-convert && rsvg-convert --version` → a path and a version.

- [ ] **Step 4: Make the PNG and the .ico**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
rsvg-convert --width=256 --height=256 --keep-aspect-ratio --output=static/icons/app-icon.png static/icons/app-icon.svg
.venv-build/bin/python -c "from PIL import Image; Image.open('static/icons/app-icon.png').save('static/icons/app-icon.ico')"
.venv-build/bin/python -c "from PIL import Image; i = Image.open('static/icons/app-icon.ico'); print(i.format, sorted(i.ico.sizes()))"
```

Expected: `ICO [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]` (Pillow's default sizes, per its "Image file formats" page). Look at `static/icons/app-icon.png` with the Read tool: crossed swords in parchment on the dark green rounded square, matching the SVG.

- [ ] **Step 5: Commit**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git add .gitignore requirements-build.txt static/icons/app-icon.png static/icons/app-icon.ico
git status --short
git commit -F - <<'EOF'
Windows app: build toolbox and the swords icon as .ico

requirements-build.txt pins NiceGUI 3.17.1, PyInstaller 6.22.3 and
Pillow 12.3.0 for a separate .venv-build/ (the app's .venv/ is
untouched). The icon is app-icon.svg drawn at 256x256 by rsvg-convert,
saved by Pillow as a .ico with sizes 16 to 256. The build's toolbox,
work files and output are kept out of git.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git log --oneline -1
```

Expected `git status --short` before the commit: exactly the four files, staged. Stop and report to Chris.

---

### Task 4: The build script, its guard, and the smoke test

**Files:**
- Create: `tools/build_exe.py`, `tools/smoke_test_exe.py`, `tests/test_build_exe.py`

**Interfaces:**
- Consumes: `bundle.PREFERRED_PORT`, `bundle.planner_answers` (smoke test); `static/icons/app-icon.ico` (Task 3); NiceGUI's `nicegui-pack` command in the running Python's scripts folder.
- Produces (used by Tasks 5–6):
  - `python tools/build_exe.py` → `dist/RS3 Planner/` (with `RS3 Planner[.exe]`, `Start here.txt`, `_internal/`), `dist/bundle-contents.txt`, `dist/RS3-Planner-<date>.zip`; exit 0 only when every check passed.
  - `python tools/smoke_test_exe.py` → exit 0 only when every check passed; logs in `build/smoke-logs/`.
  - `build_exe.version_line(date, commit, changed) -> str`, `forbidden_paths(paths) -> list[str]`, `name_forms(folder) -> set[str]`, `names_to_look_for(folders, public) -> list[str]`, `count_name_hits(root, files, forms) -> tuple[int, int]`, `DATA_FILES`, `MUST_HAVE`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_build_exe.py`:

```python
"""Tests for tools/build_exe.py's checks (the parts that don't build anything).

Nothing here runs PyInstaller, git or the network; files are made in a
temporary folder. The only player name used is "Some Player".
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))   # the scripts in tools/ aren't on the import path by default

import build_exe


class VersionLineTests(unittest.TestCase):
    def test_clean_build(self):
        self.assertEqual(build_exe.version_line("2026-10-12", "ea96c3c", False),
                         "RS3 Planner 2026-10-12 (ea96c3c)")

    def test_uncommitted_changes_are_marked(self):
        self.assertEqual(build_exe.version_line("2026-10-12", "ea96c3c", True),
                         "RS3 Planner 2026-10-12 (ea96c3c, uncommitted changes)")


class WhatGoesInTests(unittest.TestCase):
    def test_only_the_three_data_files_and_static(self):
        # Never the data/ folder itself: that would bring data/players/ along.
        self.assertEqual(build_exe.DATA_FILES, [
            ("data/methods.json", "data"),
            ("data/quests.json", "data"),
            ("data/unlocks.json", "data"),
            ("static", "static"),
        ])


class ForbiddenPathTests(unittest.TestCase):
    def test_player_files_are_caught(self):
        paths = [
            "_internal/data/methods.json",
            "_internal/data/players/current.txt",
            "_internal/data/players/some+player/answers.json",
            "_internal/x/snapshots/2026-10-05_0900.json",
            "_internal/last_goal",
            "_internal/Players/x.txt",
        ]
        self.assertEqual(build_exe.forbidden_paths(paths), paths[1:])

    def test_the_real_bundle_files_pass(self):
        paths = ["RS3 Planner.exe", "Start here.txt", "_internal/data/methods.json", "_internal/data/quests.json",
                 "_internal/data/unlocks.json", "_internal/static/app.css", "_internal/version.txt",
                 "_internal/nicegui/static/echarts.min.js"]
        self.assertEqual(build_exe.forbidden_paths(paths), [])


class NameSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_name_forms(self):
        self.assertEqual(build_exe.name_forms("some+player"), {"some+player", "some player"})

    def test_forms_already_public_are_skipped(self):
        public = b"readme ... some+player ... more text"
        self.assertEqual(build_exe.names_to_look_for(["some+player"], public), ["some player"])

    def test_hits_are_counted_ignoring_case_and_never_printed(self):
        (self.root / "a.txt").write_bytes(b"hello SOME PLAYER")
        (self.root / "b.bin").write_bytes(b"\x00\x01\x02")
        (self.root / "c.txt").write_bytes(b"some+player and some player")
        files = sorted(self.root.iterdir())
        out = io.StringIO()
        with redirect_stdout(out):
            result = build_exe.count_name_hits(self.root, files, ["some player", "some+player"])
        self.assertEqual(result, (2, 2))   # 2 names found, in 2 files
        self.assertEqual(out.getvalue(), "")

    def test_names_in_file_paths_count_too(self):
        (self.root / "some+player.json").write_bytes(b"{}")
        files = sorted(self.root.iterdir())
        self.assertEqual(build_exe.count_name_hits(self.root, files, ["some+player"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
```

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest tests.test_build_exe 2>&1 | tail -3`
Expected: `ModuleNotFoundError: No module named 'build_exe'`.

- [ ] **Step 2: Write `tools/build_exe.py`**

```python
#!/usr/bin/env python3
"""
RS3 Planner - build the app version (the Windows .exe, or a Linux rehearsal)
============================================================================

Packs app.py, the code it uses, NiceGUI, the three data files and static/ into
one folder with its own copy of Python, using NiceGUI's own packing tool
(nicegui-pack, built on PyInstaller). Then it checks the result and zips it.

Run it with the build toolbox's Python, from the project folder:
    .venv-build/bin/python tools/build_exe.py      (Linux, see requirements-build.txt)
    python tools/build_exe.py                      (GitHub's Windows machine)

The result, in dist/:
    RS3 Planner/                the app folder: RS3 Planner(.exe), Start here.txt, _internal/
    RS3-Planner-<date>.zip      the same folder, zipped, to share
    bundle-contents.txt         every file inside the app folder

A bundle runs only on the kind of system it was built on: a Windows .exe must
be built on Windows (PyInstaller's "Supporting Multiple Operating Systems").

Player data (data/players/) is never given to the packer, and step 5 stops the
build if any player file or player name shows up inside anyway. Names are never
printed, only counted.

Standard library only (it runs nicegui-pack as a separate program).
"""

import datetime
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
APP_NAME = "RS3 Planner"
ICON = PROJECT / "static" / "icons" / "app-icon.ico"
STAGE = PROJECT / "build" / "version-file"     # the version file is written here before packing
DIST = PROJECT / "dist"
APP_DIR = DIST / APP_NAME
CONTENTS_LIST = DIST / "bundle-contents.txt"
PLAYERS_DIR = PROJECT / "data" / "players"     # only read to know which names to search for
REPO_URL = "https://github.com/Kawasakininja17/RS-Planning-Tool"

# Exactly what goes in besides the code: (source in the project, folder inside the bundle).
# Never the data/ folder itself: that would bring data/players/ along.
DATA_FILES = [
    ("data/methods.json", "data"),
    ("data/quests.json", "data"),
    ("data/unlocks.json", "data"),
    ("static", "static"),
]
# Files that must be inside the app folder afterwards. "_internal" is PyInstaller's
# folder for everything except the program itself ("Run-time Information" page).
MUST_HAVE = [
    "_internal/data/methods.json",
    "_internal/data/quests.json",
    "_internal/data/unlocks.json",
    "_internal/static/app.css",
    "_internal/version.txt",
]
# A path containing any of these is player data: the build stops.
FORBIDDEN = ["players", "current.txt", "answers.json", "last_goal", "snapshots"]

START_HERE = """\
{version}

Starting it
  Double-click "RS3 Planner.exe" in this folder. A black window opens, then the
  planner opens in your web browser. Keep the black window open while you use
  the planner; close it to stop the app. Starting it again while it runs just
  opens it in your browser again.

  Extract the whole zip first: the program needs the "_internal" folder beside it.

Windows may warn you
  Windows may show a warning before the first start, because this program is
  new and isn't signed by a company. That doesn't mean it's harmful. The code
  is public: {repo}

Your data
  Your players, answers and stats history are kept in your own app-data folder,
  %LOCALAPPDATA%\\RS3 Planner (the black window shows the full path). To update,
  delete this folder and extract the new zip: your data stays where it is.

The planner only reads public data (RuneMetrics and the RuneScape Wiki), never
touches the game, and never asks for a password: only your public RuneScape name.
"""


# ---------------------------------------------------------------------------
# The checks (tested in tests/test_build_exe.py)
# ---------------------------------------------------------------------------

def version_line(date, commit, changed):
    """'RS3 Planner 2026-10-12 (ea96c3c)'. With uncommitted changes it says so, so a
    rehearsal build can never pass for one made from a commit."""
    note = f"{commit}, uncommitted changes" if changed else commit
    return f"{APP_NAME} {date} ({note})"


def forbidden_paths(paths):
    """The paths (relative, as text) that look like player data."""
    return [path for path in paths if any(word in path.lower() for word in FORBIDDEN)]


def name_forms(folder):
    """The two ways a player folder's name is written: 'some+player' and 'some player'."""
    return {folder, folder.replace("+", " ").strip()}


def names_to_look_for(folders, public):
    """
    The name forms to search the bundle for. Forms already in `public` (every
    git-tracked file's bytes, lower case) are left out: they are published
    already, so finding them in the bundle reveals nothing new.
    """
    forms = set()
    for folder in folders:
        forms |= {form for form in name_forms(folder) if form.encode("utf-8") not in public}
    return sorted(forms)


def count_name_hits(root, files, forms):
    """
    How many of the name forms appear in the files (their bytes or their path
    under `root`, ignoring case): (names found, files with a hit). Only counts,
    never the names themselves. PyInstaller compresses the code archive, so this
    covers files copied as they are (the data files, static/); the code itself
    comes from the public repo, which is checked for names before every push.
    """
    needles = [form.encode("utf-8") for form in forms]
    found, hit_files = set(), 0
    for path in files:
        data = path.read_bytes().lower() + b"\n" + path.relative_to(root).as_posix().lower().encode("utf-8")
        hits = {needle for needle in needles if needle in data}
        found |= hits
        hit_files += bool(hits)
    return len(found), hit_files


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------

def fail(message):
    print(f"\nBuild stopped: {message}", flush=True)
    sys.exit(1)


def step(title):
    print(f"\n{title}", flush=True)


def run(command):
    """Run a command in the project folder and return its output; stop the build if it fails."""
    result = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"{' '.join(command)} failed:\n{(result.stdout + result.stderr).strip()}")
    return result.stdout


def public_text():
    """Every git-tracked file's bytes, lower case: what is already published."""
    names = [name for name in run(["git", "ls-files", "-z"]).split("\0") if name]
    return b"\n".join((PROJECT / name).read_bytes().lower() for name in names if (PROJECT / name).is_file())


def pack(version_file):
    """Run NiceGUI's packing tool, as its documentation shows, with exactly our data files."""
    scripts = sysconfig.get_path("scripts")   # where this Python keeps its commands (bin/ or Scripts\)
    env = dict(os.environ)
    # The same as "activating" the toolbox: nicegui-pack starts PyInstaller by name
    # ("python -m PyInstaller" on Linux, "pyinstaller" on Windows), so this Python's
    # own copies must be found first.
    env["PATH"] = scripts + os.pathsep + env.get("PATH", "")
    tool = shutil.which("nicegui-pack", path=env["PATH"])
    if tool is None:
        fail("nicegui-pack isn't installed in this Python. Install requirements-build.txt first.")
    command = [tool, "--onedir", "--clean", "--noconfirm", "--name", APP_NAME, "--icon", str(ICON)]
    for source, place in DATA_FILES:
        command += ["--add-data", f"{PROJECT / source}{os.pathsep}{place}"]
    command += ["--add-data", f"{version_file}{os.pathsep}.", "app.py"]
    # nicegui-pack ignores PyInstaller's result (it always ends as if all went well),
    # so step 4 checks what was really made.
    subprocess.run(command, cwd=PROJECT, env=env)


def main():
    step("1. Checking the data files")
    run([sys.executable, "check_methods.py"])
    print("   data files OK")

    step("2. Writing the version line")
    date = datetime.date.today().isoformat()
    commit = run(["git", "rev-parse", "--short", "HEAD"]).strip()
    changed = bool(run(["git", "status", "--porcelain"]).strip())
    version = version_line(date, commit, changed)
    STAGE.mkdir(parents=True, exist_ok=True)
    version_file = STAGE / "version.txt"
    version_file.write_text(version + "\n", encoding="utf-8")
    print(f"   {version}")

    step("3. Packing with nicegui-pack (this takes a few minutes)")
    pack(version_file)

    step("4. Checking the app folder")
    program = APP_DIR / (APP_NAME + (".exe" if sys.platform == "win32" else ""))
    if not program.is_file():
        fail(f"{program} wasn't made. Read PyInstaller's messages above.")
    missing = [path for path in MUST_HAVE if not (APP_DIR / path).is_file()]
    if missing:
        fail("missing inside the app folder: " + ", ".join(missing))
    (APP_DIR / "Start here.txt").write_text(START_HERE.format(version=version, repo=REPO_URL),
                                            encoding="utf-8", newline="\r\n")
    print(f"   {program.name} and the data files are there; Start here.txt added")

    step("5. Checking no player data is inside")
    files = sorted(path for path in APP_DIR.rglob("*") if path.is_file())
    paths = [path.relative_to(APP_DIR).as_posix() for path in files]
    CONTENTS_LIST.write_text("\n".join(paths) + "\n", encoding="utf-8")
    bad = forbidden_paths(paths)
    if bad:
        fail(f"{len(bad)} file(s) look like player data (see {CONTENTS_LIST.name}).")
    folders = sorted(d.name for d in PLAYERS_DIR.iterdir() if d.is_dir()) if PLAYERS_DIR.is_dir() else []
    if folders:
        forms = names_to_look_for(folders, public_text())
        names, hit_files = count_name_hits(APP_DIR, files, forms)
        print(f"   searched {len(files)} files for {len(forms)} player name forms not already public: {names} found")
        if names:
            fail(f"{names} player name form(s) found in {hit_files} file(s) inside the app folder.")
    else:
        print("   no data/players/ here, so no player names to search for")
    print(f"   {len(files)} files, none of them player data (list: {CONTENTS_LIST.name})")

    step("6. Zipping")
    archive = shutil.make_archive(str(DIST / f"RS3-Planner-{date}"), "zip", root_dir=DIST, base_dir=APP_NAME)
    print(f"   {archive}")
    print(f"\nDone: {version}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the build tests**

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest tests.test_build_exe -v 2>&1 | tail -3` → `Ran 9 tests`, `OK`.

- [ ] **Step 4: Prove they can fail**

1. In `forbidden_paths`, change `path.lower()` to `path`. Expected: `test_player_files_are_caught` fails (`Players` is missed).
2. In `count_name_hits`, remove `+ b"\n" + path.relative_to(root).as_posix().lower().encode("utf-8")`. Expected: `test_names_in_file_paths_count_too` fails.
3. Add `("data", "data"),` as the first item of `DATA_FILES`. Expected: `test_only_the_three_data_files_and_static` fails.

Restore each; `Ran 9 tests`, `OK`.

- [ ] **Step 5: Write `tools/smoke_test_exe.py`**

```python
#!/usr/bin/env python3
"""
RS3 Planner - smoke test for the built app
==========================================

Starts the app that tools/build_exe.py made and checks it from outside:
  - it answers on port 8095 as RS3 Planner, prints its version line, and makes
    its data folder in a scratch folder (never the real one; the scratch path
    has a space and an accent, like many Windows user folders);
  - the host lock still refuses other names and other websites;
  - a second copy notices the first, says so and ends;
  - nothing was fetched from RuneMetrics (a fresh start has no player yet).
Then it stops the app. Run it with any Python 3, from the project folder:
    python3 tools/smoke_test_exe.py
Exit code 0 means every check passed. The app's output is kept in build/smoke-logs/.

The app opens a browser tab by itself, twice (the second copy opens the first),
exactly as it would for a clan member.

Standard library only.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))   # to reuse bundle.py's "is RS3 Planner answering?" check
from bundle import PREFERRED_PORT, planner_answers   # noqa: E402

APP_DIR = PROJECT / "dist" / "RS3 Planner"
APP = APP_DIR / ("RS3 Planner.exe" if sys.platform == "win32" else "RS3 Planner")
SCRATCH = PROJECT / "build" / "smoke data é"
DATA_FOLDER = SCRATCH / ("RS3 Planner" if sys.platform == "win32" else "rs3-planner")
LOGS = PROJECT / "build" / "smoke-logs"
BASE = f"http://127.0.0.1:{PREFERRED_PORT}"
START_WAIT = 90   # seconds: a first start can be slow (e.g. a virus scan of the new files)

failures = []


def check(what, passed, detail=""):
    print(f"  {'PASS' if passed else 'FAIL'}  {what}" + (f"  ({detail})" if detail and not passed else ""), flush=True)
    if not passed:
        failures.append(what)


def status(path, headers=None):
    """(HTTP status, body) for one request to the app, never through a proxy."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(BASE + path, headers=headers or {})
    try:
        with opener.open(request, timeout=10) as reply:
            return reply.status, reply.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def websocket_first_line(origin):
    """Open the app's live connection with this Origin; the server's first answer line."""
    handshake = (f"GET /_nicegui_ws/socket.io/?EIO=4&transport=websocket HTTP/1.1\r\n"
                 f"Host: 127.0.0.1:{PREFERRED_PORT}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n"
                 f"Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                 f"Origin: {origin}\r\n\r\n")
    with socket.create_connection(("127.0.0.1", PREFERRED_PORT), timeout=5) as conn:
        conn.sendall(handshake.encode("ascii"))
        return conn.recv(4096).decode("latin-1").splitlines()[0]


def read_log(name):
    return (LOGS / name).read_text(encoding="utf-8", errors="replace")


def main():
    if not APP.is_file():
        sys.exit(f"No built app at {APP}: run tools/build_exe.py first.")
    if planner_answers(PREFERRED_PORT) or status_answers():
        sys.exit(f"Something already answers on port {PREFERRED_PORT}: stop it first.")
    shutil.rmtree(SCRATCH, ignore_errors=True)
    shutil.rmtree(LOGS, ignore_errors=True)
    SCRATCH.mkdir(parents=True)
    LOGS.mkdir(parents=True)
    env = dict(os.environ, LOCALAPPDATA=str(SCRATCH), XDG_DATA_HOME=str(SCRATCH))

    print(f"Starting {APP.name} (data in a scratch folder)", flush=True)
    with open(LOGS / "first.log", "w", encoding="utf-8") as log:
        first = subprocess.Popen([str(APP)], cwd=APP_DIR, env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + START_WAIT
        while not planner_answers(PREFERRED_PORT) and time.monotonic() < deadline and first.poll() is None:
            time.sleep(1)
        check(f"answers on {PREFERRED_PORT} as RS3 Planner", planner_answers(PREFERRED_PORT),
              "see build/smoke-logs/first.log")
        if failures:
            return
        log_text = read_log("first.log")
        check("prints its version line", "RS3 Planner 20" in log_text)
        check("prints where data is saved", "Your saved data: " in log_text)
        check("made its data folder in the scratch folder", DATA_FOLDER.is_dir(), str(DATA_FOLDER))
        check("Choose player page: 200", status("/player")[0] == 200)
        check("another name (rebinding): 400",
              status("/player", {"Host": f"evil.example:{PREFERRED_PORT}"})[0] == 400)
        check("another website's page request: 403", status("/player", {"Origin": "http://evil.example"})[0] == 403)
        check("another website's live connection: 403", " 403 " in websocket_first_line("http://evil.example"))
        check("its own live connection: 101",
              " 101 " in websocket_first_line(f"http://127.0.0.1:{PREFERRED_PORT}"))

        try:
            with open(LOGS / "second.log", "w", encoding="utf-8") as log:
                second = subprocess.run([str(APP)], cwd=APP_DIR, env=env, stdin=subprocess.DEVNULL,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=60)
            ended = second.returncode
        except subprocess.TimeoutExpired:   # subprocess.run has already stopped it
            ended = "still running after 60 seconds"
        check("a second copy ends by itself", ended == 0, f"exit code {ended}")
        check("a second copy says it's already running", "already running" in read_log("second.log"))
        check("nothing fetched from RuneMetrics", "Fetching " not in read_log("first.log"))
    finally:
        first.terminate()
        try:
            first.wait(timeout=20)
        except subprocess.TimeoutExpired:
            first.kill()
    check("stopped", not planner_answers(PREFERRED_PORT))


def status_answers():
    """True if anything at all accepts a connection on the port."""
    try:
        with socket.create_connection(("127.0.0.1", PREFERRED_PORT), timeout=2):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    main()
    if failures:
        print(f"\n{len(failures)} check(s) failed. The app's output is in build/smoke-logs/.")
        sys.exit(1)
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print("\nEvery check passed.")
```

- [ ] **Step 6: Run all tests**

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest discover -s tests 2>&1 | tail -3` → `Ran 287 tests`, `OK` (278 + 9).
Run: `python3 -c "import ast; [ast.parse(open(f).read()) for f in ('tools/build_exe.py', 'tools/smoke_test_exe.py')]" && echo parses` → `parses`.

- [ ] **Step 7: Commit**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git add tools/build_exe.py tools/smoke_test_exe.py tests/test_build_exe.py
git status --short
git commit -F - <<'EOF'
Windows app: build script with a player-data guard, and a smoke test

tools/build_exe.py checks the data, writes the version line, runs
nicegui-pack with only the three data files, static/ and the version
file, checks the program and files were really made (nicegui-pack
ignores PyInstaller's errors), lists every file, stops if any looks
like player data or holds a player name (counted, never printed), adds
Start here.txt and zips it. tools/smoke_test_exe.py starts the built
app on a scratch data folder and checks the port, the locks, a second
copy and that nothing was fetched.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git log --oneline -1
```

Expected `git status --short` before the commit: the three files only. Stop and report to Chris.

---

### Task 5: The Linux rehearsal

No repository files change in this task (unless a check fails: then stop and report). Scratch: `$W`.

- [ ] **Step 1: Chris's service before**

```bash
systemctl --user is-active rs3-planner
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/player
```

Expected: `active`; `200`.

- [ ] **Step 2: Build**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
cd /home/chris-baron/Repos/RS-Planning-Tool
git status --short
.venv-build/bin/python tools/build_exe.py > $W/build-output.txt 2>&1; echo "exit $?"
```

Run it in the background (it can take several minutes) and wait for it. The output goes to the git-ignored scratch folder: a file in the project folder would make the build's own `git status` report "uncommitted changes". Then read the end: `tail -25 $W/build-output.txt`.

Expected: `git status --short` empty before building; `exit 0`; the version line `RS3 Planner <today> (<commit>)` **without** "uncommitted changes" (Review Focus 5); `searched N files for M player name forms not already public: 0 found`; `Done:`. A failure: stop and report (counts only, never names).

- [ ] **Step 3: Look inside the bundle**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
ls "dist/RS3 Planner"
ls dist
wc -l < dist/bundle-contents.txt
grep -ciE "players|snapshots|answers\.json|last_goal|current\.txt" dist/bundle-contents.txt
grep -E "^_internal/(data/|static/app\.css|version\.txt)" dist/bundle-contents.txt
cat "dist/RS3 Planner/_internal/version.txt"
python3 -c "import zipfile; z = zipfile.ZipFile(next(__import__('pathlib').Path('dist').glob('RS3-Planner-*.zip'))); n = z.namelist(); print(len(n), n[0])"
git status --short
```

Expected: `RS3 Planner  Start here.txt  _internal`; the zip, `bundle-contents.txt` and the app folder; a file count; `0`; the three `_internal/data/*.json`, `_internal/static/app.css`, `_internal/version.txt`; the version line; the zip's entry count (the contents count plus folder entries) starting with `RS3 Planner/`; `git status --short` still empty (Review Focus 5).

- [ ] **Step 4: Smoke test**

Tell Chris first: two browser tabs will open in Chris's own browser by themselves (the app, then the second copy opening it).

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 tools/smoke_test_exe.py`
Expected: every line `PASS` (13 checks), `Every check passed.` Any `FAIL`: stop and report, with `build/smoke-logs/*.log` read first (they hold no player names: no player was chosen).

- [ ] **Step 5: Add the comparison entries to `.claude/launch.json`**

```json
{
  "name": "rs3-bundle",
  "runtimeExecutable": "/usr/bin/env",
  "runtimeArgs": ["XDG_DATA_HOME=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/xdg",
                  "/home/chris-baron/Repos/RS-Planning-Tool/dist/RS3 Planner/RS3 Planner"],
  "port": 8095
},
{
  "name": "rs3-source-8095",
  "runtimeExecutable": "/home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python",
  "runtimeArgs": ["/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/src/app.py"],
  "port": 8095
},
{
  "name": "rs3-bundle-fresh",
  "runtimeExecutable": "/usr/bin/env",
  "runtimeArgs": ["XDG_DATA_HOME=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/xdg-fresh",
                  "/home/chris-baron/Repos/RS-Planning-Tool/dist/RS3 Planner/RS3 Planner"],
  "port": 8095
},
{
  "name": "port-squatter-8095",
  "runtimeExecutable": "/usr/bin/python3",
  "runtimeArgs": ["-m", "http.server", "8095", "--bind", "127.0.0.1",
                  "--directory", "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/empty"],
  "port": 8095
},
{
  "name": "rs3-bundle-clash",
  "runtimeExecutable": "/usr/bin/env",
  "runtimeArgs": ["XDG_DATA_HOME=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/xdg-clash",
                  "/home/chris-baron/Repos/RS-Planning-Tool/dist/RS3 Planner/RS3 Planner"],
  "port": 8096
}
```

- [ ] **Step 6: Port 8095 held by another program (Review Focus 3)**

```bash
mkdir -p /home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe/empty
```

`preview_start {name: "port-squatter-8095"}` (a plain Python web server showing an empty folder). Then `preview_start {name: "rs3-bundle-clash"}`; tell Chris both run and that a tab may open in Chris's browser. `preview_logs` for the bundle: the version line, `Your saved data: .../xdg-clash/rs3-planner`, `Port 8095 is used by another program, so RS3 Planner uses port 8096.`, `RS3 Planner is running...`, no traceback. Check:

```bash
python3 -c "import sys; sys.path.insert(0, '/home/chris-baron/Repos/RS-Planning-Tool'); import bundle; print(bundle.planner_answers(8095), bundle.planner_answers(8096))"
```

Expected: `False True`. `preview_stop` both; `rm -rf $W/xdg-clash $W/empty`.

- [ ] **Step 7: Bundle and source read the same (live, one after the other on 8095)**

Prepare the two copies from the same player-data template (Task 2):

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
cd /home/chris-baron/Repos/RS-Planning-Tool
rm -rf $W/xdg $W/src && mkdir -p $W/xdg/rs3-planner $W/src
cp -r $W/data_template/players $W/xdg/rs3-planner/players
git ls-files -z | xargs -0 tar -cf - | tar -x -C $W/src
sed -i 's/^PORT = 8080$/PORT = 8095/' $W/src/app.py
grep -n "^PORT" $W/src/app.py
cp -r $W/data_template/players $W/src/data/players
ls $W/xdg/rs3-planner/players $W/src/data/players
```

Expected: `PORT = 8095`; both list `current.txt  hels+glasglo`.

Ask Chris to confirm Hels Glasglo isn't being played right now (the account's XP must not move between the two runs).

1. `preview_start {name: "rs3-bundle"}`; tell Chris. `preview_logs`: the version line, `Your saved data: .../xdg/rs3-planner`, one `Fetching Hels Glasglo from RuneMetrics`, `RS3 Planner is running...`, no traceback.
2. For the 9 addresses of Task 2 Step 2, under `http://127.0.0.1:8095`, run Task 2 Step 2's "before" script (it stores `before <address>` in localStorage). Write the 9 lines to `$W/bundle.sha`.
3. Run the lock checks of Task 2 Step 7 against 8095 (replace every `8091` with `8095`). Same expected results.
4. `preview_stop`. `preview_start {name: "rs3-source-8095"}`; tell Chris. `preview_logs`: one `Fetching Hels Glasglo from RuneMetrics`, no traceback, no `Your saved data` line.
5. For the same 9 addresses under `http://127.0.0.1:8095`, run Task 2 Step 7's "after" script. Write the lines to `$W/source.sha`. `preview_stop`.
6. Did the XP stay the same between the two fetches?

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
python3 - "$W" <<'EOF'
import json, sys
from pathlib import Path
w = Path(sys.argv[1])
newest = lambda folder: json.loads(max(folder.glob("*.json")).read_text())["skillvalues"]
a = newest(w / "xdg/rs3-planner/players/hels+glasglo/snapshots")
b = newest(w / "src/data/players/hels+glasglo/snapshots")
print("same XP" if a == b else "XP MOVED")
EOF
```

Expected: `same XP`, and every line in `$W/source.sha` `same`, `socket=true`. `XP MOVED`: the comparison doesn't count; tell Chris and redo Step 7 later (two more fetches). Any `DIFFERENT` with `same XP`: stop and report the removed/added lines.

- [ ] **Step 8: Saved data survives closing and reopening**

Ask Chris for the second public test name. Use it only live in the app; never write it in a file, command, commit or message.

1. `rm -rf $W/xdg-fresh`. `preview_start {name: "rs3-bundle-fresh"}`; tell Chris. `navigate` to `http://127.0.0.1:8095/`: it shows Choose player with no Recent players.
2. Type the name, press **Look up** → Home shows that player's stats.
3. `/play` → AFK, 5 h, 1–2 min → **Show my plan**. If a "Check: needs …" offers **I have it**, press it once and note which unlock (by its wording on screen, not the player).
4. `/quests` → **Change goal** → pick a goal different from the one shown; note its name.
5. `preview_stop`. Check the files exist, counting only:

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
P=$W/xdg-fresh/rs3-planner/players
test -s $P/current.txt && echo "current.txt saved"
find $P -name answers.json | wc -l
find $P -name last_goal | wc -l
find $P -path "*/snapshots/*.json" | wc -l
```

Expected: `current.txt saved`; `1` (or `0` if no "I have it" was offered); `1`; `1`.

6. `preview_start {name: "rs3-bundle-fresh"}` again. `/` shows the same player (not Choose player); `/quests` shows the goal chosen in 4; the plan's **Your answers** lists the answer from 3. Snapshot count is now `2`. `preview_stop`.

- [ ] **Step 9: Clean up, and Chris's service after**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
cd /home/chris-baron/Repos/RS-Planning-Tool
rm -rf $W/xdg $W/xdg-fresh $W/src $W/frozen $W/data_template build dist
ls $W
git status --short
systemctl --user is-active rs3-planner
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/player
```

Expected: only scripts, `*.sha` and `build-output.txt` left in `$W`; `git status --short` empty; `active`; `200`. Remove the five entries added in Step 5 from `.claude/launch.json`. Stop and report to Chris (nothing to commit).

---

### Task 6: README and the GitHub workflow; the first Windows build

**Files:**
- Create: `.github/workflows/build-windows.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `requirements-build.txt` (Task 3), `tools/build_exe.py` and `tools/smoke_test_exe.py` (Task 4).
- Produces: a manual workflow "Build Windows app" whose run keeps two artifacts: `RS3-Planner-<date>.zip` and `bundle-contents.txt`.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/build-windows.yml`:

```yaml
# Builds the Windows app on one of GitHub's Windows machines, checks it, and
# keeps the zip on this run's page (download needs a GitHub sign-in; kept 30 days).
# Runs only when someone with write access presses "Run workflow" on the Actions
# tab. It can't publish anything: releases are made by hand (README, "Building
# the Windows app").
name: Build Windows app

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  build:
    runs-on: windows-2025
    steps:
      - name: Get the code
        uses: actions/checkout@v7.0.1
        with:
          persist-credentials: false

      - name: Set up Python 3.14
        uses: actions/setup-python@v7.0.0
        with:
          python-version: "3.14"

      - name: Install the build toolbox
        run: python -m pip install -r requirements-build.txt

      - name: Run the tests
        run: python -m unittest discover -s tests -v

      - name: Build the app
        run: python tools/build_exe.py

      - name: Smoke-test the app
        run: python tools/smoke_test_exe.py

      - name: Keep the zip
        uses: actions/upload-artifact@v7.0.2
        with:
          path: dist/RS3-Planner-*.zip
          archive: false
          if-no-files-found: error
          retention-days: 30

      - name: Keep the contents list
        uses: actions/upload-artifact@v7.0.2
        with:
          path: dist/bundle-contents.txt
          archive: false
          if-no-files-found: error
          retention-days: 30
```

(`archive: false` uploads the file as it is, named after the file, per `upload-artifact`'s own `action.yml`; the zip is not zipped a second time.)

- [ ] **Step 2: README**

1. In `README.md`, directly above `## Install`, add:

```markdown
## Windows app (for clan members)

No Python needed: a ready-to-run Windows version is on the
[Releases page](https://github.com/Kawasakininja17/RS-Planning-Tool/releases).

1. Download `RS3-Planner-<date>.zip` from the newest release.
2. Extract the whole zip (right-click it, **Extract All…**). Don't run the
   program from inside the zip: it needs the `_internal` folder beside it.
3. Open the extracted `RS3 Planner` folder and double-click **RS3 Planner.exe**.
   A black window opens, then the planner opens in your web browser.
4. Windows may warn you first, because the program is new and isn't signed by a
   company. That doesn't mean it's harmful; the code is all on this page.
5. Keep the black window open while you use the planner. Close it to stop the
   app. Double-clicking again while it runs just opens it in the browser.

Your players, answers and stats history are saved in your own Windows folder
`%LOCALAPPDATA%\RS3 Planner` (the black window shows the full path), not in the
app's folder. To update: delete the old `RS3 Planner` folder and extract the new
zip; your data stays. If the black window shows a problem, it waits for you to
read it: press Enter to close it.
```

2. Directly above `## Tests` (in the tinkerers' part), add:

````markdown
## Building the Windows app

The Windows app is this same program packed by NiceGUI's `nicegui-pack` (built on
PyInstaller) into one folder with its own Python. A Windows program can only be
built on Windows, so GitHub builds it: on the repository's **Actions** tab, pick
**Build Windows app**, then **Run workflow**. It runs the tests, `tools/build_exe.py`
and `tools/smoke_test_exe.py` on a Windows machine and keeps the zip and its contents
list on the run's page. Releases are made by hand from that zip.

The same build runs on Linux (for trying it out; it makes a Linux program), with its
own toolbox so the app's `.venv/` stays as it is:

```bash
python3 -m venv .venv-build
```

```bash
.venv-build/bin/pip install -r requirements-build.txt
```

```bash
.venv-build/bin/python tools/build_exe.py
```

```bash
python3 tools/smoke_test_exe.py
```

`tools/build_exe.py` packs only `data/methods.json`, `data/quests.json`,
`data/unlocks.json` and `static/`, never `data/players/`, and stops if any player
file or name ends up inside. The Windows icon (`static/icons/app-icon.ico`) was made
once from `app-icon.svg` with `rsvg-convert` (Ubuntu package `librsvg2-bin`) and Pillow.
````

- [ ] **Step 3: Tests and commit**

Run: `cd /home/chris-baron/Repos/RS-Planning-Tool && python3 -m unittest discover -s tests 2>&1 | tail -3` → `Ran 287 tests`, `OK`.

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git add .github/workflows/build-windows.yml README.md
git commit -F - <<'EOF'
Windows app: README sections and the manual GitHub build

.github/workflows/build-windows.yml runs only on "Run workflow": on a
Windows machine with Python 3.14 it installs requirements-build.txt,
runs the tests, the build and the smoke test, and keeps the zip and
its contents list for 30 days. Read-only permissions: it can't publish.
The README explains the Windows app for clan members and how to build it.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git log --oneline -1
```

- [ ] **Step 4: Before pushing: names check, and Chris's OK**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git log --oneline origin/main..HEAD
n=0; for d in data/players/*/; do f=$(basename "$d"); [ "$f" = "hels+glasglo" ] && continue; s=${f//+/ }; if git log -p origin/main..HEAD | grep -qiF -e "$f" -e "$s"; then n=$((n+1)); fi; done; echo "other players named in unpushed commits: $n"
```

Expected: the commits from Tasks 1–4 and 6 (and the spec and plan commits); `other players named in unpushed commits: 0`. Ask Chris whether to push. Only on Chris's yes: `git push`. If the push fails, test with `ssh -T git@github.com` first and report.

- [ ] **Step 5: The first Windows build**

Ask Chris to start it: on `https://github.com/Kawasakininja17/RS-Planning-Tool/actions`, click **Build Windows app**, then **Run workflow** (branch `main`) and **Run workflow** again. Then follow it read-only through GitHub's public API (no sign-in needed for a public repo's run status):

```bash
curl -s "https://api.github.com/repos/Kawasakininja17/RS-Planning-Tool/actions/runs?per_page=1" | python3 -c "import json, sys; r = json.load(sys.stdin)['workflow_runs'][0]; print(r['id'], r['name'], r['status'], r['conclusion'])"
```

When it reports `completed`, list each step's result:

```bash
RUN=<the id printed above>
curl -s "https://api.github.com/repos/Kawasakininja17/RS-Planning-Tool/actions/runs/$RUN/jobs" | python3 -c "import json, sys; [print(s['conclusion'], s['name']) for j in json.load(sys.stdin)['jobs'] for s in j['steps']]"
```

Expected: `completed success`, and every step `success`. A failed step: stop. Ask Chris to open the run, click the failed step, and save its log text to `$W/failed-step.txt`; read it and report (if it's the tests on Windows, report each failing test separately and wait: none are skipped quietly).

- [ ] **Step 6: Check what was built**

Ask Chris to download both artifacts from the run's page (**Artifacts** at the bottom; needs Chris's GitHub sign-in) into `$W/artifact/`. Then:

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
cd /home/chris-baron/Repos/RS-Planning-Tool
ls $W/artifact
python3 - "$W/artifact" <<'EOF'
import sys, zipfile
from pathlib import Path
sys.path.insert(0, "tools")
import build_exe
folder = Path(sys.argv[1])
paths = (folder / "bundle-contents.txt").read_text(encoding="utf-8").splitlines()   # names have spaces
print("files listed:", len(paths))
print("look like player data:", len(build_exe.forbidden_paths(paths)))
print("program and data present:", all(p in paths for p in ["RS3 Planner.exe", "Start here.txt", *build_exe.MUST_HAVE]))
z = zipfile.ZipFile(next(folder.glob("RS3-Planner-*.zip")))
inside = {n.removeprefix("RS3 Planner/") for n in z.namelist() if not n.endswith("/")}
print("zip matches the list:", inside == set(paths))
print(z.read("RS3 Planner/_internal/version.txt").decode().strip())
EOF
```

Expected: the two files; a file count; `look like player data: 0`; `program and data present: True`; `zip matches the list: True`; `RS3 Planner <date> (<pushed commit>)` without "uncommitted changes".

Stop and report to Chris.

---

### Task 7: The pre-release and the clan check

- [ ] **Step 1: Chris makes the pre-release (GitHub website)**

Give Chris these steps (`gh` isn't installed, so this is done on the website; it publishes the zip for anyone, which Chris approved in principle and decides on now):

1. `https://github.com/Kawasakininja17/RS-Planning-Tool/releases` → **Draft a new release**.
2. **Choose a tag** → type `v<date>` (the date in the zip's name) → **Create new tag on publish**, target `main`.
3. Title: `RS3 Planner <date>`.
4. Notes (paste):

```
First test version of the Windows app. No Python needed.

1. Download RS3-Planner-<date>.zip below.
2. Extract the whole zip, open the "RS3 Planner" folder, double-click "RS3 Planner.exe".
3. Windows may warn you first: the program is new and unsigned. The code is all on this page.
4. Keep the black window open while you use it; close it to stop.

Your data is saved in %LOCALAPPDATA%\RS3 Planner, so it stays when you update.
```

5. Attach the zip from `$W/artifact/`.
6. Tick **Set as a pre-release**. **Publish release**.

- [ ] **Step 2: Check it downloads without signing in**

```bash
curl -s "https://api.github.com/repos/Kawasakininja17/RS-Planning-Tool/releases" | python3 -c "import json, sys; r = json.load(sys.stdin)[0]; print(r['tag_name'], r['prerelease']); [print(a['name'], a['size'], a['browser_download_url']) for a in r['assets']]"
curl -s -L -o /dev/null -w "%{http_code} %{size_download}\n" "<the browser_download_url printed above>"
```

Expected: `v<date> True`; the zip's name and size; `200 <the same size>` (no sign-in was used).

- [ ] **Step 3: The message for the clan member**

Give Chris this text to send (Chris fills in the link):

```
Could you test the RS3 Planner Windows app for me? About 10 minutes.
Link: <release page link>

1. Download the zip WITHOUT signing in to GitHub (tell me if it asks you to).
2. If Windows warns you, write down the exact words and which button got you past it.
3. Extract the whole zip, open the "RS3 Planner" folder, double-click "RS3 Planner.exe".
   Does your browser open the planner?
4. Type your RuneScape name and press Look up. Does a plan show on "Ready to play"?
5. Close the black window. Double-click the .exe again: are you still chosen?
6. Double-click the .exe twice quickly: do you end up with one planner, or an error?
7. Before extracting, try double-clicking the .exe inside the zip. What happens?
8. Read me the first line in the black window (it starts with "RS3 Planner").
```

Wait for Chris to bring back the answers. Record the exact warning wording (step 2) for Task 8. Any failed point: stop and work through it with Chris before anything else.

---

### Task 8: The real release

**Files:**
- Modify: `tools/build_exe.py` (`START_HERE`'s warning paragraph), `README.md` (step 4 of the Windows app section)

- [ ] **Step 1: Put the recorded warning wording into `Start here.txt` and the README**

Replace the paragraph under `Windows may warn you` in `START_HERE` (and step 4 in the README's Windows section) with the clan member's exact words and button names from Task 7 Step 3, keeping the sentences that it's new and unsigned and that the code is public. If the clan check found other problems, they come first, each discussed with Chris.

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3` → `Ran 287 tests`, `OK`. Commit:

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git add tools/build_exe.py README.md
git commit -F - <<'EOF'
Windows app: the warning's real wording in Start here.txt and README

Taken from the clan member's check of the first pre-release.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 2: Push (Chris's OK), build, check**

Repeat Task 6 Step 4 (names check, Chris's yes, push), Step 5 (Chris runs the workflow; all steps `success`) and Step 6 (artifact checks, into a fresh `$W/artifact/`).

- [ ] **Step 3: Chris publishes the release**

As Task 7 Step 1, with: tag `v<new date>` (if it's the same day as the pre-release, `v<date>.2`), title `RS3 Planner <date>`, the new zip, **Set as a pre-release** unticked and **Set as the latest release** ticked. Chris decides whether to delete the earlier pre-release. Check with Task 7 Step 2's commands: `prerelease` is `False` and the zip downloads (`200`).

- [ ] **Step 4: Tidy up**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/windows-exe
rm -rf $W/artifact
ls $W
git -C /home/chris-baron/Repos/RS-Planning-Tool status --short
```

Expected: only scratch scripts and notes left; `git status --short` empty. Stop and report to Chris.
