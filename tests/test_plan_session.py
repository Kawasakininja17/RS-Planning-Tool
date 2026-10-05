"""Tests for unlock answers and extra levels in plan_session.check_method_for_session."""

import copy
import unittest

from account import LEVEL_XP
from plan_session import check_method_for_session
from rs3_planner import SKILL_NAMES

AUTOHEATER = {"id": "smithing-autoheater", "text": "Smithing autoheater"}

METHOD = {
    "type": "training", "name": "Forging", "skill": "Smithing", "min_level": 90,
    "xp_per_hour_low": 150000, "xp_per_hour_high": 150000,
    "gp_per_hour": None, "gp_after_tax": None, "minutes_between_clicks": 5.0,
    "requirements": {"quests": [], "other": [], "skills": {}, "unlocks": [AUTOHEATER]},
    "unverified": [], "source_url": "https://runescape.wiki/w/Smithing",
    "checked_date": "2026-10-04", "notes": "",
}


def make_account(level=95):
    """Every skill at the same level, no quests done."""
    skills = {name: {"xp": float(LEVEL_XP[level - 1]), "level": level} for name in SKILL_NAMES}
    return {"skills": skills, "completed_quests": set(), "quests": {}}


class UnlockAnswerTests(unittest.TestCase):
    def test_unanswered_unlock_is_not_blocked_but_listed(self):
        blocked, _, unanswered = check_method_for_session(copy.deepcopy(METHOD), make_account(), 2, {})
        self.assertEqual(blocked, [])
        self.assertEqual(unanswered, [AUTOHEATER])

    def test_answer_no_blocks(self):
        blocked, _, unanswered = check_method_for_session(
            copy.deepcopy(METHOD), make_account(), 2, {"smithing-autoheater": False})
        self.assertEqual(blocked, ["you said you don't have: Smithing autoheater"])
        self.assertEqual(unanswered, [])

    def test_answer_yes_clears_it(self):
        blocked, _, unanswered = check_method_for_session(
            copy.deepcopy(METHOD), make_account(), 2, {"smithing-autoheater": True})
        self.assertEqual((blocked, unanswered), ([], []))


class ExtraLevelTests(unittest.TestCase):
    def test_extra_skill_level_blocks_when_too_low(self):
        method = copy.deepcopy(METHOD)
        method["requirements"]["skills"] = {"Mining": 99}
        blocked, _, _ = check_method_for_session(method, make_account(95), 2, {"smithing-autoheater": True})
        self.assertEqual(blocked, ["needs Mining 99 (you have 95)"])


if __name__ == "__main__":
    unittest.main()
