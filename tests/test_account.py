"""The level knowledge (XP tables, level_progress) and the Skills screen's list."""

import unittest
from pathlib import Path

from account import (
    ELITE_LEVEL_XP, LEVEL_XP, level_from_xp, level_progress, level_table, read_account,
    skill_rows, xp_to_99, xp_to_level,
)
from rs3_planner import INVENTION_ID, SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL


def make_account(xp_by_skill):
    """
    A pretend account in the same shape read_account() makes. Skills not named
    get 0 XP. Every level comes from XP, Invention's from its own elite table,
    like the real code.
    """
    skills = {}
    for name in SKILL_NAMES:
        xp = xp_by_skill.get(name, 0.0)
        skills[name] = {"xp": xp, "level": level_from_xp(xp, name)}
    return {"skills": skills, "completed_quests": set(), "quests": {}}


# Made-up numbers for "Some Player", shaped like a real mid-game account.
SOME_PLAYER = {
    "Thieving": 41_839_229.4,
    "Fishing": 27_939_799.2,
    "Necromancy": 16_399_363.1,
    "Invention": 14_292_017.8,
    "Mining": 10_125_808.8,
    "Defence": 7_086_345.4,
    "Slayer": 234_499.5,
}


class SkillRowsTests(unittest.TestCase):
    def setUp(self):
        self.account = make_account(SOME_PLAYER)
        self.rows = skill_rows(self.account)
        self.by_name = {row["name"]: row for row in self.rows}

    def test_every_skill_once(self):
        self.assertEqual(sorted(row["name"] for row in self.rows), sorted(SKILL_NAMES))

    def test_unfinished_skills_closest_to_99_first(self):
        unfinished = [row for row in self.rows if not row["done"]]
        self.assertEqual(unfinished[0]["name"], "Mining")
        self.assertEqual(unfinished[1]["name"], "Defence")
        lefts = [row["xp_left"] for row in unfinished]
        self.assertEqual(lefts, sorted(lefts))

    def test_done_skills_at_the_bottom_most_xp_first(self):
        names = [row["name"] for row in self.rows]
        self.assertEqual(names[-3:], ["Thieving", "Fishing", "Necromancy"])
        self.assertTrue(all(row["done"] for row in self.rows[-3:]))

    def test_xp_left_matches_xp_to_99(self):
        for row in self.rows:
            self.assertEqual(row["xp_left"], xp_to_99(self.account, row["name"]))
        self.assertEqual(self.by_name["Mining"]["xp_left"], XP_FOR_99_NORMAL - 10_125_808.8)

    def test_level_past_99_comes_from_xp(self):
        # RuneMetrics' own "level" can't be trusted past 99; ours comes from XP.
        self.assertEqual(self.by_name["Thieving"]["level_text"], "110")
        self.assertEqual(self.by_name["Mining"]["level_text"], "96")

    def test_invention_uses_the_elite_curve(self):
        # 14.3M XP would be 99 on the normal curve, but on the elite curve it is 79
        # (and 99 needs 36,073,511).
        invention = self.by_name["Invention"]
        self.assertFalse(invention["done"])
        self.assertEqual(invention["level_text"], "79")
        self.assertEqual(invention["xp_left"], XP_FOR_99_ELITE - 14_292_017.8)

    def test_invention_past_99_shows_99_plus(self):
        # The Skills screen has always said "99+" here (40M XP is elite level 101);
        # showing the exact level would be a separate change.
        rows = skill_rows(make_account({"Invention": 40_000_000.0}))
        invention = next(row for row in rows if row["name"] == "Invention")
        self.assertTrue(invention["done"])
        self.assertEqual(invention["level_text"], "99+")

    def test_bar_is_share_of_99_and_never_past_full(self):
        self.assertAlmostEqual(self.by_name["Mining"]["fraction"], 10_125_808.8 / XP_FOR_99_NORMAL)
        self.assertAlmostEqual(self.by_name["Invention"]["fraction"], 14_292_017.8 / XP_FOR_99_ELITE)
        self.assertEqual(self.by_name["Thieving"]["fraction"], 1.0)


class EliteTableTests(unittest.TestCase):
    def test_120_levels_each_needing_more_xp(self):
        self.assertEqual(len(ELITE_LEVEL_XP), 120)
        self.assertEqual(ELITE_LEVEL_XP[0], 0)
        self.assertTrue(all(a < b for a, b in zip(ELITE_LEVEL_XP, ELITE_LEVEL_XP[1:])))

    def test_matches_the_figures_we_already_trust(self):
        self.assertEqual(ELITE_LEVEL_XP[98], XP_FOR_99_ELITE)   # 36,073,511
        self.assertEqual(ELITE_LEVEL_XP[119], 80_618_654)        # level 120, from the wiki

    def test_level_table_picks_by_skill(self):
        self.assertIs(level_table("Invention"), ELITE_LEVEL_XP)
        self.assertIs(level_table("Mining"), LEVEL_XP)
        self.assertIs(level_table(None), LEVEL_XP)

    def test_level_from_xp_without_a_skill_uses_the_normal_curve(self):
        self.assertEqual(level_from_xp(XP_FOR_99_NORMAL), 99)
        self.assertEqual(level_from_xp(XP_FOR_99_NORMAL - 0.1), 98)

    def test_level_from_xp_for_invention_uses_the_elite_curve(self):
        self.assertEqual(level_from_xp(XP_FOR_99_ELITE, "Invention"), 99)
        self.assertEqual(level_from_xp(XP_FOR_99_ELITE - 0.1, "Invention"), 98)
        self.assertEqual(level_from_xp(14_292_017.8, "Invention"), 79)
        self.assertEqual(level_from_xp(14_292_017.8, "Mining"), 99)   # same XP, normal curve

    def test_xp_to_level_for_invention(self):
        account = make_account({"Invention": 14_292_017.8})
        self.assertAlmostEqual(xp_to_level(account, "Invention", 80), 14_672_812 - 14_292_017.8)


class LevelProgressTests(unittest.TestCase):
    def test_start_of_a_level(self):
        progress = level_progress(make_account({"Mining": float(LEVEL_XP[95])}), "Mining")   # exactly 96
        self.assertEqual(progress, {"skill": "Mining", "level": 96, "next_level": 97,
                                    "fraction": 0.0, "xp_left": LEVEL_XP[96] - LEVEL_XP[95]})

    def test_part_way_through(self):
        width = LEVEL_XP[96] - LEVEL_XP[95]   # XP from 96 to 97
        progress = level_progress(make_account({"Mining": LEVEL_XP[95] + 0.25 * width}), "Mining")
        self.assertEqual((progress["level"], progress["next_level"]), (96, 97))
        self.assertAlmostEqual(progress["fraction"], 0.25)
        self.assertAlmostEqual(progress["xp_left"], 0.75 * width)

    def test_last_xp_before_the_next_level(self):
        progress = level_progress(make_account({"Mining": LEVEL_XP[96] - 0.1}), "Mining")
        self.assertEqual(progress["level"], 96)
        self.assertLess(progress["fraction"], 1)
        self.assertAlmostEqual(progress["xp_left"], 0.1)

    def test_level_119_points_at_120(self):
        progress = level_progress(make_account({"Woodcutting": float(LEVEL_XP[118])}), "Woodcutting")
        self.assertEqual((progress["level"], progress["next_level"]), (119, 120))
        self.assertEqual(progress["xp_left"], LEVEL_XP[119] - LEVEL_XP[118])

    def test_level_120_has_no_next_level(self):
        self.assertIsNone(level_progress(make_account({"Woodcutting": float(LEVEL_XP[119])}), "Woodcutting"))
        self.assertIsNone(level_progress(make_account({"Woodcutting": 200_000_000.0}), "Woodcutting"))

    def test_invention_uses_the_elite_table(self):
        progress = level_progress(make_account({"Invention": 14_292_017.8}), "Invention")
        self.assertEqual((progress["level"], progress["next_level"]), (79, 80))
        self.assertAlmostEqual(progress["xp_left"], 14_672_812 - 14_292_017.8)
        self.assertAlmostEqual(progress["fraction"],
                               (14_292_017.8 - 13_937_496) / (14_672_812 - 13_937_496))


class ReadAccountTests(unittest.TestCase):
    def test_levels_come_from_xp_invention_on_its_own_table(self):
        # RuneMetrics' own "level" is deliberately wrong here (50): it must be ignored.
        profile = {"skillvalues": [{"id": i, "xp": 0, "level": 50} for i in range(len(SKILL_NAMES))]}
        profile["skillvalues"][INVENTION_ID]["xp"] = 142_920_178   # RuneMetrics' x10: 14,292,017.8 XP
        profile["skillvalues"][SKILL_NAMES.index("Mining")]["xp"] = 142_920_178
        account = read_account(profile, {"quests": []})
        self.assertEqual(account["skills"]["Invention"]["level"], 79)
        self.assertEqual(account["skills"]["Mining"]["level"], 99)


class AppLevelTableTests(unittest.TestCase):
    """app.py can't be imported here (it starts NiceGUI), so read it as text."""

    def test_app_picks_each_skills_own_xp_table(self):
        # The Quests screen's "skills still short" bar must use the skill's own table
        # (Invention's is the elite one), never the normal LEVEL_XP for every skill.
        text = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
        self.assertFalse("LEVEL_XP" in text, "app.py still uses the normal-only LEVEL_XP table")
        self.assertTrue("/ level_table(skill)[level - 1]" in text, "the bar doesn't use level_table(skill)")


if __name__ == "__main__":
    unittest.main()
