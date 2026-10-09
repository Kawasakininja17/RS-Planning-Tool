"""
RS3 Planner - players
=====================

Everything about "which player" lives here, so the rest of the code never
has to know where a player's files are kept.

Each player gets a folder under data/players/ (kept out of git):
    data/players/hels+glasglo/
        answers.json   "I have it" / "I don't" answers for unlocks RuneMetrics can't see
        last_goal      the big goal picked last time in the terminal menu
        snapshots/     XP snapshots, one per fetch

data/players/current.txt remembers the player the app showed last.

In the Windows app (a bundle, see bundle.py) the same folders live in the
user's own app-data folder instead, e.g. %LOCALAPPDATA%\\RS3 Planner\\players\\.
"""

import json
import re
import sys
from pathlib import Path

from bundle import is_bundled, user_data_dir


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

# Name rules from the RuneScape Wiki "Display name" page: at most 12 characters;
# letters, numbers, spaces, hyphens and underscores. (New names can't START with
# - or _, but older names may, so that isn't rejected.)
MAX_NAME_LENGTH = 12
NAME_CHARACTERS = re.compile(r"[A-Za-z0-9 _-]+")

# Names Windows refuses for a file or folder (Microsoft's "Naming Files, Paths, and
# Namespaces" page). Every one of them is also a valid RuneScape name.
WINDOWS_RESERVED = ({"con", "prn", "aux", "nul"}
                    | {f"com{n}" for n in range(1, 10)} | {f"lpt{n}" for n in range(1, 10)})


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

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


def player_dir(name):
    return PLAYERS_DIR / folder_name(name)


# ---------------------------------------------------------------------------
# Answers: "I have it" / "I don't" for unlocks RuneMetrics can't see
# ---------------------------------------------------------------------------

def read_answers(name):
    """
    {unlock id: True or False}. No file yet means nothing answered: {}.
    A broken file raises ValueError with a plain message, so a typo made
    while hand-editing is reported instead of silently ignored.
    """
    path = player_dir(name) / "answers.json"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        answers = json.loads(text)
    except json.JSONDecodeError as err:
        raise ValueError(f"{path} isn't valid JSON: {err.msg} (line {err.lineno}). "
                         "Fix it or delete it to start over.") from None
    if not isinstance(answers, dict) or not all(isinstance(v, bool) for v in answers.values()):
        raise ValueError(f"{path} must look like {{\"unlock-id\": true}}, with only true or false as answers.")
    return answers


def save_answer(name, unlock_id, has_it):
    """Save one answer. has_it: True, False, or None to forget the answer."""
    answers = read_answers(name)
    if has_it is None:
        answers.pop(unlock_id, None)
    else:
        answers[unlock_id] = has_it
    folder = player_dir(name)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "answers.json").write_text(json.dumps(answers, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")


# ---------------------------------------------------------------------------
# Checking a typed name (before asking RuneMetrics anything)
# ---------------------------------------------------------------------------

def check_name(text):
    """Returns (cleaned name, None) if the name could be real, or (None, problem in plain words)."""
    name = (text or "").strip()
    if not name:
        return None, "Type a RuneScape name first."
    if len(name) > MAX_NAME_LENGTH:
        return None, f"RuneScape names are at most {MAX_NAME_LENGTH} characters; that one has {len(name)}."
    if not NAME_CHARACTERS.fullmatch(name):
        return None, "RuneScape names only use letters, numbers, spaces, hyphens (-) and underscores (_)."
    return name, None


# ---------------------------------------------------------------------------
# The current player (the one the app shows)
# ---------------------------------------------------------------------------

def read_current():
    """The remembered player's name, or None if none has been chosen yet."""
    try:
        name = (PLAYERS_DIR / "current.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return name or None


def save_current(name):
    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    (PLAYERS_DIR / "current.txt").write_text(name + "\n", encoding="utf-8")


def known_players():
    """
    Every player with at least one snapshot, A-Z. The name comes from their newest
    snapshot, so it has RuneMetrics' own capitals. (Snapshot file names start with
    the date and time, so the newest is the last one alphabetically.)
    """
    names = []
    for snapshots in sorted(PLAYERS_DIR.glob("*/snapshots")):
        newest = max(snapshots.glob("*.json"), default=None)
        if newest is None:
            continue
        try:
            names.append(json.loads(newest.read_text(encoding="utf-8"))["username"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            continue   # an unreadable snapshot just leaves that player off the list
    return sorted(names, key=str.lower)


# ---------------------------------------------------------------------------
# Terminal scripts: which player?
# ---------------------------------------------------------------------------

def cli_player(given=None):
    """
    The name typed on the command line if any, otherwise the remembered player,
    otherwise ask. Stops with a clear message if no valid name can be found.
    """
    if given:
        name, problem = check_name(given)
        if problem:
            sys.exit(f"Error: {problem}")
        return name
    remembered = read_current()
    if remembered:
        return remembered
    while True:
        try:
            text = input("RuneScape name: ")
        except EOFError:   # no keyboard attached
            sys.exit('Error: no player chosen. Give a name, e.g. --user "Some Player".')
        name, problem = check_name(text)
        if name:
            return name
        print(f"  {problem}")
