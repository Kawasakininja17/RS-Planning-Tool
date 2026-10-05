"""Tests for unlock answers and extra levels in plan_session.check_method_for_session."""

import copy
import unittest

from account import LEVEL_XP
from plan_session import check_method_for_session
from rs3_planner import SKILL_NAMES

AUTOHEATER = {"id": "smithing-autoheater", "text": "Smithing autoheater"}

METHOD = {
    "type": "training", "name": "Forging", "skill": "Smithing", "min_level": 90,
    "max_level": None,
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


def with_levels(account, **levels):
    """Change some skills' levels (and XP to match) in an account from make_account()."""
    for skill, level in levels.items():
        account["skills"][skill] = {"xp": float(LEVEL_XP[level - 1]), "level": level}
    return account


def banded(skill="Woodcutting", low=30, high=59):
    """A method whose wiki rates are for levels low-high. Its one unlock is answered 'yes' below."""
    method = copy.deepcopy(METHOD)
    method.update(skill=skill, min_level=low, max_level=high)
    return method


YES = {"smithing-autoheater": True}
OUTGROWN = "you've outgrown this"


class MaxLevelTests(unittest.TestCase):
    def test_inside_band_offered(self):
        blocked, _, _ = check_method_for_session(banded(), with_levels(make_account(), Woodcutting=45), 5, YES)
        self.assertEqual(blocked, [])

    def test_at_top_of_band_still_offered(self):
        blocked, _, _ = check_method_for_session(banded(), with_levels(make_account(), Woodcutting=59), 5, YES)
        self.assertEqual(blocked, [])

    def test_one_past_band_is_outgrown(self):
        blocked, _, _ = check_method_for_session(banded(), with_levels(make_account(), Woodcutting=60), 5, YES)
        self.assertEqual(blocked, ["you've outgrown this (Woodcutting 60; this method's rates are for levels 30–59)"])

    def test_no_max_level_never_outgrown(self):
        method = banded()
        method["max_level"] = None
        blocked, _, _ = check_method_for_session(method, with_levels(make_account(), Woodcutting=98), 5, YES)
        self.assertEqual(blocked, [])

    def test_two_skill_method_offered_while_one_skill_inside(self):
        method = banded("Ranged/Defence", 70, 80)
        account = with_levels(make_account(), Ranged=75, Defence=92)
        blocked, _, _ = check_method_for_session(method, account, 5, YES)
        self.assertFalse(any(OUTGROWN in reason for reason in blocked))

    def test_two_skill_method_outgrown_when_both_past(self):
        method = banded("Ranged/Defence", 70, 80)
        account = with_levels(make_account(), Ranged=85, Defence=92)
        blocked, _, _ = check_method_for_session(method, account, 5, YES)
        self.assertIn("you've outgrown this (Ranged 85 and Defence 92; this method's rates are for levels 70–80)",
                      blocked)


if __name__ == "__main__":
    unittest.main()
