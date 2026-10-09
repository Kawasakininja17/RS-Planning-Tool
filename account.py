"""
RS3 Planner - account helpers
=============================

Shared by plan_session.py (the path picker) and quest_path.py (the quest path):
turning XP into levels, and turning raw RuneMetrics data into an easy lookup.
"""

import math   # floor() for the XP formula

from rs3_planner import SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL


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

# Invention is an "elite" skill with its own, steeper XP curve, so it has its own
# table. Typed in from the RuneScape Wiki's "Experience/Table" page ("Elite skills"
# table), read 2026-10-09. Same layout as LEVEL_XP: [0] is level 1, [98] is level 99
# (36,073,511 XP), [119] is level 120 (the elite skill's top level).
ELITE_LEVEL_XP = [
    0, 830, 1_861, 2_902, 3_980, 5_126, 6_380, 7_787, 9_400, 11_275,   # levels 1-10
    13_605, 16_372, 19_656, 23_546, 28_134, 33_520, 39_809, 47_109, 55_535, 65_209,   # 11-20
    77_190, 90_811, 106_221, 123_573, 143_025, 164_742, 188_893, 215_651, 245_196, 277_713,   # 21-30
    316_311, 358_547, 404_634, 454_796, 509_259, 568_254, 632_019, 700_797, 774_834, 854_383,   # 31-40
    946_227, 1_044_569, 1_149_696, 1_261_903, 1_381_488,
    1_508_756, 1_644_015, 1_787_581, 1_939_773, 2_100_917,   # 41-50
    2_283_490, 2_476_369, 2_679_917, 2_894_505, 3_120_508,
    3_358_307, 3_608_290, 3_870_846, 4_146_374, 4_435_275,   # 51-60
    4_758_122, 5_096_111, 5_449_685, 5_819_299, 6_205_407,
    6_608_473, 7_028_964, 7_467_354, 7_924_122, 8_399_751,   # 61-70
    8_925_664, 9_472_665, 10_041_285, 10_632_061, 11_245_538,
    11_882_262, 12_542_789, 13_227_679, 13_937_496, 14_672_812,   # 71-80
    15_478_994, 16_313_404, 17_176_661, 18_069_395, 18_992_239,
    19_945_833, 20_930_821, 21_947_856, 22_997_593, 24_080_695,   # 81-90
    25_259_906, 26_475_754, 27_728_955, 29_020_233, 30_350_318,
    31_719_944, 33_129_852, 34_580_790, 36_073_511, 37_608_773,   # 91-100
    39_270_442, 40_978_509, 42_733_789, 44_537_107, 46_389_292,
    48_291_180, 50_243_611, 52_247_435, 54_303_504, 56_412_678,   # 101-110
    58_575_824, 60_793_812, 63_067_521, 65_397_835, 67_785_643,
    70_231_841, 72_737_330, 75_303_019, 77_929_820, 80_618_654,   # 111-120
]


def level_table(skill=None):
    """The XP table a skill uses: the elite one for Invention, the normal one otherwise."""
    return ELITE_LEVEL_XP if skill == "Invention" else LEVEL_XP


def level_from_xp(xp, skill=None):
    """
    The highest level (1-120) whose XP requirement this XP has reached.
    skill picks the table (Invention has its own); leave it out for the normal one.
    """
    level = 1
    for index, needed in enumerate(level_table(skill)):
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
        # Levels come from XP, not RuneMetrics' own "level" (unreliable past 99).
        # Invention uses its own elite table (see level_table).
        level = level_from_xp(xp, name)
        skills[name] = {"xp": xp, "level": level}

    quests = {q["title"]: q for q in quest_data.get("quests", [])}
    completed = {title for title, q in quests.items() if q.get("status") == "COMPLETED"}
    return {"skills": skills, "completed_quests": completed, "quests": quests}


def xp_to_99(account, skill_name):
    target = XP_FOR_99_ELITE if skill_name == "Invention" else XP_FOR_99_NORMAL
    return max(0, target - account["skills"][skill_name]["xp"])


def xp_to_level(account, skill_name, level):
    """XP still needed to reach a level (0 if already there)."""
    return max(0, level_table(skill_name)[level - 1] - account["skills"][skill_name]["xp"])


def level_progress(account, skill_name):
    """
    How far through its current level a skill is (used by path A of the planner):
      {"skill", "level", "next_level", "fraction", "xp_left"}
    fraction is 0 at the start of the level and just under 1 right before the next;
    xp_left is the XP still needed for next_level.
    Returns None at 120: the XP tables stop there, so there is no next level.
    """
    table = level_table(skill_name)
    level = account["skills"][skill_name]["level"]
    if level >= len(table):
        return None
    xp = account["skills"][skill_name]["xp"]
    start, end = table[level - 1], table[level]   # XP for this level, and for the next
    return {"skill": skill_name, "level": level, "next_level": level + 1,
            "fraction": (xp - start) / (end - start), "xp_left": end - xp}


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
            # The Skills screen has always shown "99+" for Invention past 99;
            # showing its exact level is a separate change.
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
