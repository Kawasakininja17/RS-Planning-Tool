"""Tests for the new requirements.skills / requirements.unlocks fields in check_methods.py."""

import copy
import unittest

from check_methods import check_method, check_unlock_ids_match

VALID = {
    "type": "training", "name": "Test method", "skill": "Mining", "min_level": 90,
    "max_level": None,
    "xp_per_hour_low": 1000, "xp_per_hour_high": 2000,
    "gp_per_hour": None, "gp_after_tax": None, "minutes_between_clicks": None,
    "requirements": {
        "quests": [], "other": [],
        "skills": {"Mining": 99},
        "unlocks": [{"id": "smithing-autoheater", "text": "Smithing autoheater"}],
    },
    "unverified": [], "source_url": "https://runescape.wiki/w/Mining",
    "checked_date": "2026-10-04", "notes": "",
}


def method_with(**requirement_changes):
    method = copy.deepcopy(VALID)
    method["requirements"].update(requirement_changes)
    return method


def mentions(problems, text):
    return any(text in problem for problem in problems)


class CheckMethodTests(unittest.TestCase):
    def test_valid_method_has_no_problems(self):
        self.assertEqual(check_method(copy.deepcopy(VALID), 1), [])

    def test_old_missing_field_is_rejected(self):
        method = copy.deepcopy(VALID)
        method["missing"] = []
        self.assertIn("Method #1 (Test method): unknown field 'missing' (typo?)", check_method(method, 1))

    def test_requirements_need_all_four_keys(self):
        method = copy.deepcopy(VALID)
        del method["requirements"]["unlocks"]
        self.assertTrue(mentions(check_method(method, 1), "exactly 'quests', 'other', 'skills' and 'unlocks'"))

    def test_unknown_skill_in_skills(self):
        self.assertTrue(mentions(check_method(method_with(skills={"Minning": 99}), 1), "unknown skill 'Minning'"))

    def test_skill_level_out_of_range(self):
        self.assertTrue(mentions(check_method(method_with(skills={"Mining": 121}), 1), "from 1 to 120"))

    def test_unlock_needs_id_and_text(self):
        self.assertTrue(mentions(check_method(method_with(unlocks=[{"id": "x"}]), 1), "exactly 'id' and 'text'"))

    def test_unlock_id_format(self):
        bad = [{"id": "Smithing Autoheater", "text": "Smithing autoheater"}]
        self.assertTrue(mentions(check_method(method_with(unlocks=bad), 1), "lower-case words joined by hyphens"))

    def test_unlock_text_not_empty(self):
        bad = [{"id": "smithing-autoheater", "text": "  "}]
        self.assertTrue(mentions(check_method(method_with(unlocks=bad), 1), "text must be non-empty"))

    def test_same_unlock_twice_in_one_method(self):
        twice = [{"id": "a", "text": "A"}, {"id": "a", "text": "A"}]
        self.assertTrue(mentions(check_method(method_with(unlocks=twice), 1), "listed twice"))


class MaxLevelCheckTests(unittest.TestCase):
    """max_level: the top of the level band the wiki's rates are for (None = no top)."""

    def with_max(self, value):
        method = copy.deepcopy(VALID)   # min_level is 90
        method["max_level"] = value
        return check_method(method, 1)

    def test_missing_is_a_problem(self):
        method = copy.deepcopy(VALID)
        del method["max_level"]
        self.assertIn("Method #1 (Test method): missing field 'max_level'", check_method(method, 1))

    def test_null_is_fine(self):
        self.assertEqual(self.with_max(None), [])

    def test_at_or_above_min_level_is_fine(self):
        self.assertEqual(self.with_max(90), [])
        self.assertEqual(self.with_max(97), [])

    def test_below_min_level_is_a_problem(self):
        self.assertIn("Method #1 (Test method): max_level (89) is below min_level (90)", self.with_max(89))

    def test_not_a_whole_number_or_out_of_range(self):
        for bad in ("97", 97.5, True, 0, 121):
            self.assertTrue(mentions(self.with_max(bad), "max_level must be a whole number from 1 to 120, or null"),
                            f"{bad!r} should be refused")


class UnlockIdsMatchTests(unittest.TestCase):
    def test_same_id_same_text_is_fine(self):
        methods = [method_with(unlocks=[{"id": "a", "text": "A"}]), method_with(unlocks=[{"id": "a", "text": "A"}])]
        self.assertEqual(check_unlock_ids_match(methods), [])

    def test_same_id_different_text_is_a_problem(self):
        methods = [method_with(unlocks=[{"id": "a", "text": "A"}]), method_with(unlocks=[{"id": "a", "text": "B"}])]
        self.assertEqual(check_unlock_ids_match(methods), ["Unlock id 'a' has different text in different methods"])


if __name__ == "__main__":
    unittest.main()
