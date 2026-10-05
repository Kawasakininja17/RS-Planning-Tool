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
"""

import json
from pathlib import Path

PLAYERS_DIR = Path(__file__).parent / "data" / "players"


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

def folder_name(name):
    """
    'Hels Glasglo' -> 'hels+glasglo'.
    A '+' can never be part of a RuneScape name, so two players never share a
    folder. Hyphens and underscores are kept: the wiki's Display name page says
    an underscore is not the same as a space.
    """
    return name.strip().lower().replace(" ", "+")


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
