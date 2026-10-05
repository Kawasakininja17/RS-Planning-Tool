"""
RS3 Planner - account helpers
=============================

Shared by plan_session.py (the path picker) and quest_path.py (the quest path):
turning XP into levels, and turning raw RuneMetrics data into an easy lookup.
"""

import math   # floor() for the XP formula

from rs3_planner import INVENTION_ID, SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL


# ---------------------------------------------------------------------------
# Levels from XP
# ---------------------------------------------------------------------------

def xp_for_level(level):
    """
    XP needed for a level, using the formula on the RuneScape Wiki
    "Experience" page. Checked against every level 2-120 on the wiki's
    Experience/Table page (all 119 matched).
    """
    points = sum(math.floor(n + 300 * 2 ** (n / 7)) for n in range(1, level))
    return math.floor(points / 4)


# LEVEL_XP[0] is level 1, LEVEL_XP[98] is level 99, LEVEL_XP[119] is level 120.
LEVEL_XP = [xp_for_level(level) for level in range(1, 121)]


def level_from_xp(xp):
    """The highest level (1-120) whose XP requirement this XP has reached."""
    level = 1
    for index, needed in enumerate(LEVEL_XP):
        if xp >= needed:
            level = index + 1
    return level


# ---------------------------------------------------------------------------
# Reading the account
# ---------------------------------------------------------------------------

def read_account(profile, quest_data):
    """
    Turn the raw RuneMetrics data into something easy to look things up in:
      skills: {"Mining": {"xp": 10125809.0, "level": 96}, ...}
      completed_quests: a set of quest titles
      quests: {"Plague City": {...RuneMetrics record...}, ...}
    """
    skills = {}
    for skill in profile["skillvalues"]:
        if skill["id"] >= len(SKILL_NAMES):
            continue   # a skill this program doesn't know yet
        name = SKILL_NAMES[skill["id"]]
        xp = skill["xp"] / 10   # RuneMetrics stores XP multiplied by 10
        if skill["id"] == INVENTION_ID:
            # Invention uses the elite XP curve, which the formula above doesn't
            # cover. RuneMetrics' own level is reliable below 99, so use it.
            level = skill["level"]
        else:
            level = level_from_xp(xp)
        skills[name] = {"xp": xp, "level": level}

    quests = {q["title"]: q for q in quest_data.get("quests", [])}
    completed = {title for title, q in quests.items() if q.get("status") == "COMPLETED"}
    return {"skills": skills, "completed_quests": completed, "quests": quests}


def xp_to_99(account, skill_name):
    target = XP_FOR_99_ELITE if skill_name == "Invention" else XP_FOR_99_NORMAL
    return max(0, target - account["skills"][skill_name]["xp"])


def xp_to_level(account, skill_name, level):
    """XP still needed to reach a level (0 if already there)."""
    return max(0, LEVEL_XP[level - 1] - account["skills"][skill_name]["xp"])


# ---------------------------------------------------------------------------
# The Skills screen's list
# ---------------------------------------------------------------------------

def skill_rows(account):
    """
    One row per skill for the Skills screen, ready to draw:
      {"name", "level_text", "xp", "xp_left", "fraction", "done"}
    fraction is how full the progress bar is (XP so far / XP for 99, at most 1).
    Unfinished skills come first, closest to 99 first; finished ones (99+)
    follow, most XP first.
    """
    rows = []
    for name, skill in account["skills"].items():
        target = XP_FOR_99_ELITE if name == "Invention" else XP_FOR_99_NORMAL
        xp_left = xp_to_99(account, name)
        level_text = str(skill["level"])
        if name == "Invention" and xp_left == 0:
            # We have no elite-curve table past 99, and RuneMetrics' level isn't
            # trusted there, so don't claim an exact level.
            level_text = "99+"
        rows.append({
            "name": name,
            "level_text": level_text,
            "xp": skill["xp"],
            "xp_left": xp_left,
            "fraction": min(1.0, skill["xp"] / target),
            "done": xp_left == 0,
        })
    unfinished = sorted((r for r in rows if not r["done"]), key=lambda r: r["xp_left"])
    done = sorted((r for r in rows if r["done"]), key=lambda r: r["xp"], reverse=True)
    return unfinished + done
