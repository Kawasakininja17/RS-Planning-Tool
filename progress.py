"""
RS3 Planner - progress over time
================================

Works out what the Progress screen shows, from the XP snapshots saved on every
fetch (see snapshots.py): max cape progress per day, XP gained lately, and one
skill's XP per day. Nothing here draws (that's app.py) and nothing fetches:
everything comes from files already on disk.

A "snapshot" in this file is a dict:
  {"when": datetime, "total_xp": 194520179, "skills": {"Mining": 10125809.0, ...}}

Functions that care about "today" take it as an argument, so the tests can use
made-up dates instead of the real clock.
"""

import datetime
import json

from players import player_dir
from rs3_planner import SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL


# ---------------------------------------------------------------------------
# Reading the snapshot files
# ---------------------------------------------------------------------------

def read_snapshots(username):
    """
    Every readable snapshot for this player, oldest first, and how many files
    were skipped because they couldn't be read. Never raises: a broken file is
    skipped and counted, so the screen can say so instead of crashing.
    """
    folder = player_dir(username) / "snapshots"
    try:
        paths = sorted(folder.glob("*.json"))   # a missing folder simply has no files
    except OSError:   # the folder exists but can't be listed
        return [], 0
    snapshots, skipped = [], 0
    for path in paths:
        snapshot = read_one(path)
        if snapshot is None:
            skipped += 1
        else:
            snapshots.append(snapshot)
    snapshots.sort(key=lambda s: s["when"])   # by the time inside, not the file name
    return snapshots, skipped


def is_number(value):
    """True for 12 or 12.5. (Python counts True/False as numbers too; a snapshot never holds them.)"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def read_one(path):
    """One snapshot file as a snapshot dict, or None if it can't be read or isn't in the expected shape."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        when = datetime.datetime.fromisoformat(record["fetched_at"])
        total_xp, skills = record["total_xp"], record["skills"]
    except (OSError, ValueError, KeyError, TypeError):
        # OSError: the file can't be opened. ValueError: not UTF-8, not JSON, or not a date-time.
        # KeyError: a field is missing. TypeError: the JSON isn't an object, or a field has the wrong type.
        return None
    if when.tzinfo is not None:
        return None   # snapshots are saved in local time with no time zone; a mix couldn't be sorted
    if not is_number(total_xp) or not isinstance(skills, dict):
        return None
    if not all(is_number(xp) for xp in skills.values()):
        return None
    # Keep only skills this program knows (a future new skill is ignored, as elsewhere).
    known = {name: xp for name, xp in skills.items() if name in SKILL_NAMES}
    return {"when": when, "total_xp": total_xp, "skills": known}


# ---------------------------------------------------------------------------
# Max cape, and one point per day for the charts
# ---------------------------------------------------------------------------

def target_xp(name):
    """XP for 99 in this skill (Invention uses the steeper elite curve)."""
    return XP_FOR_99_ELITE if name == "Invention" else XP_FOR_99_NORMAL


def max_cape_xp(skills):
    """
    Max cape progress by XP, the same rule as Home's Max cape card: each skill
    counts only up to its 99 amount. Returns {"done", "needed", "to_go", "percent"},
    or None if any of the 29 skills is missing (better no number than a wrong one).
    """
    needed = done = 0
    for name in SKILL_NAMES:
        if name not in skills:
            return None
        needed += target_xp(name)
        done += min(skills[name], target_xp(name))
    return {"done": done, "needed": needed, "to_go": needed - done, "percent": done / needed * 100}


def last_per_day(snapshots):
    """The last snapshot of each day, oldest day first (the charts' points)."""
    by_day = {}
    for snapshot in snapshots:   # oldest first, so a later one of the same day replaces an earlier one
        by_day[snapshot["when"].date()] = snapshot
    return [by_day[day] for day in sorted(by_day)]


def max_cape_points(snapshots):
    """[(date, XP still to go for max cape)], one per day; days we can't work out are left out."""
    points = []
    for snapshot in last_per_day(snapshots):
        cape = max_cape_xp(snapshot["skills"])
        if cape is not None:
            points.append((snapshot["when"].date(), cape["to_go"]))
    return points


def skill_points(snapshots, skill):
    """[(date, XP in this skill)], one per day; days whose snapshot lacks the skill are left out."""
    return [(s["when"].date(), s["skills"][skill]) for s in last_per_day(snapshots) if skill in s["skills"]]


# ---------------------------------------------------------------------------
# Words and numbers for the screen
# ---------------------------------------------------------------------------

def since_text(when, today):
    """'since 08:39' when that was today, else 'since 15:33, 5 Oct'."""
    if when.date() == today:
        return f"since {when:%H:%M}"
    return f"since {when:%H:%M}, {when.day} {when:%b}"


def signed_xp(xp):
    """A whole number with commas and a sign: '+726,291', '−1,500', '+0'."""
    xp = round(xp)
    return f"+{xp:,}" if xp >= 0 else f"−{-xp:,}"


# ---------------------------------------------------------------------------
# XP gained lately
# ---------------------------------------------------------------------------

def gain_between(start, end):
    """(total XP gained, max cape XP gained or None) from one snapshot to a later one."""
    start_cape, end_cape = max_cape_xp(start["skills"]), max_cape_xp(end["skills"])
    cape = None if start_cape is None or end_cape is None else end_cape["done"] - start_cape["done"]
    return end["total_xp"] - start["total_xp"], cape


def today_start(snapshots, today):
    """Where Today starts: the last snapshot from before today, else the first one from today."""
    earlier = [s for s in snapshots if s["when"].date() < today]
    if earlier:
        return earlier[-1]
    return next(s for s in snapshots if s["when"].date() == today)


def week_start(snapshots, today):
    """The last snapshot dated 7 or more days before today, or None if none is that old."""
    cutoff = today - datetime.timedelta(days=7)
    older = [s for s in snapshots if s["when"].date() <= cutoff]
    return older[-1] if older else None


def gain_line(name, start, newest):
    total, cape = gain_between(start, newest)
    return {"name": name, "state": "gain", "start": start, "total": total, "max_cape": cape}


def no_gain_line(name, state):
    return {"name": name, "state": state, "start": None, "total": None, "max_cape": None}


def gain_lines(snapshots, today):
    """
    The Gained panel's lines, in order: Today, Last 7 days, Since first snapshot.
    Each compares the newest snapshot with an older start snapshot. Today is always
    there, as a gain or as "none_today" (no snapshot from today) or "only_one"
    (nothing to compare with). The other two are left out when there's nothing that
    old, nothing to compare, or when they'd start at the same snapshot as the shown
    line above them (so no number is repeated).
    """
    if not snapshots:
        return []
    newest = snapshots[-1]
    lines = []
    shown_start = None   # the start of the nearest shown line above that has one

    if newest["when"].date() != today:
        lines.append(no_gain_line("Today", "none_today"))
    else:
        start = today_start(snapshots, today)
        if start is newest:
            lines.append(no_gain_line("Today", "only_one"))
        else:
            lines.append(gain_line("Today", start, newest))
            shown_start = start

    for name, start in (("Last 7 days", week_start(snapshots, today)),
                        ("Since first snapshot", snapshots[0])):
        if start is None or start is newest or start is shown_start:
            continue
        lines.append(gain_line(name, start, newest))
        shown_start = start
    return lines


def skills_moved(snapshots, today):
    """
    (start snapshot, [(skill, XP gained)]): the skills that went up from the start
    to the newest snapshot, biggest first. The start is the Last 7 days start, else
    the first snapshot. (None, []) when there are fewer than 2 snapshots.
    """
    if len(snapshots) < 2:
        return None, []
    newest = snapshots[-1]
    start = week_start(snapshots, today)
    if start is None or start is newest:
        start = snapshots[0]
    moved = []
    for name in SKILL_NAMES:
        if name in start["skills"] and name in newest["skills"]:
            xp = newest["skills"][name] - start["skills"][name]
            if xp > 0:
                moved.append((name, xp))
    moved.sort(key=lambda pair: pair[1], reverse=True)   # biggest first; ties keep the skill order
    return start, moved


# ---------------------------------------------------------------------------
# The One skill panel
# ---------------------------------------------------------------------------

def skill_order(skills):
    """
    Skill names for the dropdown, in the Skills screen's order: not yet 99 first,
    smallest XP left first; then 99+ skills, most XP first.
    """
    def xp_left(name):
        return max(0, target_xp(name) - skills[name])

    names = [name for name in SKILL_NAMES if name in skills]
    unfinished = sorted((n for n in names if xp_left(n) > 0), key=xp_left)
    done = sorted((n for n in names if xp_left(n) == 0), key=lambda n: skills[n], reverse=True)
    return unfinished + done


def default_skill(snapshots, today):
    """The skill the dropdown opens on: the one that moved most, else the one closest to 99."""
    if not snapshots:
        return None
    _, moved = skills_moved(snapshots, today)
    if moved:
        return moved[0][0]
    order = skill_order(snapshots[-1]["skills"])
    return order[0] if order else None


def skill_gain_since_first(snapshots, skill):
    """XP this skill gained from the first snapshot to the newest, or None if it can't be worked out."""
    if len(snapshots) < 2:
        return None
    first, newest = snapshots[0]["skills"], snapshots[-1]["skills"]
    if skill not in first or skill not in newest:
        return None
    return newest[skill] - first[skill]
