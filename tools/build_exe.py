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
