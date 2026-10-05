"""The Skills screen's list: every skill with its level, XP left to 99 and bar."""

import unittest

from account import level_from_xp, skill_rows, xp_to_99
from rs3_planner import SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL


def make_account(xp_by_skill, invention_level=1):
    """
    A pretend account in the same shape read_account() makes. Skills not named
    get 0 XP. Invention's level is given separately, because (like the real
    code) it comes from RuneMetrics, not from our normal-curve formula.
    """
    skills = {}
    for name in SKILL_NAMES:
        xp = xp_by_skill.get(name, 0.0)
        level = invention_level if name == "Invention" else level_from_xp(xp)
        skills[name] = {"xp": xp, "level": level}
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
        self.account = make_account(SOME_PLAYER, invention_level=85)
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
        # 14.3M XP would be 99 on the normal curve, but Invention needs 36,073,511.
        invention = self.by_name["Invention"]
        self.assertFalse(invention["done"])
        self.assertEqual(invention["level_text"], "85")
        self.assertEqual(invention["xp_left"], XP_FOR_99_ELITE - 14_292_017.8)

    def test_invention_past_99_shows_99_plus(self):
        # We have no elite-curve table past 99, so no exact level is claimed.
        rows = skill_rows(make_account({"Invention": 40_000_000.0}, invention_level=104))
        invention = next(row for row in rows if row["name"] == "Invention")
        self.assertTrue(invention["done"])
        self.assertEqual(invention["level_text"], "99+")

    def test_bar_is_share_of_99_and_never_past_full(self):
        self.assertAlmostEqual(self.by_name["Mining"]["fraction"], 10_125_808.8 / XP_FOR_99_NORMAL)
        self.assertAlmostEqual(self.by_name["Invention"]["fraction"], 14_292_017.8 / XP_FOR_99_ELITE)
        self.assertEqual(self.by_name["Thieving"]["fraction"], 1.0)


if __name__ == "__main__":
    unittest.main()
