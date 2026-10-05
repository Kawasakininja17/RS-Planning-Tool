"""Tests for unlock answers and extra levels in plan_session.check_method_for_session."""

import copy
import unittest

from account import LEVEL_XP
from plan_session import also_text, build_plan, check_method_for_session, pick_paths, runner_ups, split_ruled_out
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


def ready_method(name, gap=None, low=None, high=None, gp=None, skill="Mining"):
    """A method as build_plan leaves it once it is ready (training ones carry _gap)."""
    return {"name": name, "type": "money" if gp is not None else "training", "skill": skill,
            "_gap": gap, "xp_per_hour_low": low, "xp_per_hour_high": high if high is not None else low,
            "gp_per_hour": gp}


class RunnerUpTests(unittest.TestCase):
    def setUp(self):
        # Closest to 99 (A): t1, then t5, t3, t2, t4. Most XP (B, low end): t2, t3, t4, t1, t5.
        self.t1 = ready_method("t1", gap=100, low=10)
        self.t2 = ready_method("t2", gap=200, low=50)
        self.t3 = ready_method("t3", gap=300, low=40)
        self.t4 = ready_method("t4", gap=400, low=30)
        self.t5 = ready_method("t5", gap=150, low=5)
        self.g1 = ready_method("g1", gp=900)
        self.g2 = ready_method("g2", gp=700)
        self.g3 = ready_method("g3", gp=800)
        self.ready = [self.t1, self.t2, self.t3, self.t4, self.t5, self.g1, self.g2, self.g3]

    def test_each_path_gets_its_next_two_by_its_own_rule(self):
        picks = pick_paths(self.ready)
        self.assertEqual([m["name"] for m in picks], ["t1", "t2", "g1"])   # pick_paths unchanged
        also = runner_ups(self.ready, picks)
        self.assertEqual([[m["name"] for m in path] for path in also],
                         [["t5", "t3"], ["t3", "t4"], ["g3", "g2"]])

    def test_a_pick_is_never_repeated_as_a_runner_up(self):
        picks = pick_paths(self.ready)
        for path in runner_ups(self.ready, picks):
            self.assertFalse(any(m is p for m in path for p in picks))

    def test_fewer_than_two_is_fine(self):
        ready = [self.t1, self.t2, self.g1, self.g2]
        also = runner_ups(ready, pick_paths(ready))
        self.assertEqual([[m["name"] for m in path] for path in also], [[], [], ["g2"]])

    def test_nothing_ready(self):
        self.assertEqual(runner_ups([], pick_paths([])), [[], [], []])

    def test_build_plan_includes_them(self):
        plan = build_plan([copy.deepcopy(METHOD)], make_account(95), 5, YES)
        self.assertEqual(plan["also"], [[], [], []])


class AlsoTextTests(unittest.TestCase):
    def test_training_with_a_range(self):
        method = ready_method("Choking ivy", low=86000, high=126000, skill="Woodcutting")
        self.assertEqual(also_text(method), "Choking ivy (Woodcutting, 86,000–126,000 XP/hr)")

    def test_training_with_one_figure(self):
        method = ready_method("Overgrown idols", low=100000, skill="Woodcutting")
        self.assertEqual(also_text(method), "Overgrown idols (Woodcutting, 100,000 XP/hr)")

    def test_money(self):
        method = ready_method("Blessing extra fine sand", gp=3452400, skill="Prayer")
        self.assertEqual(also_text(method), "Blessing extra fine sand (Prayer, 3,452,400 gp/hr)")


class SplitRuledOutTests(unittest.TestCase):
    def test_finished_or_outgrown_are_counted_not_listed(self):
        # Any "already 99" or "outgrown" reason is enough: you'll never use that
        # method, so its other reasons (like a missing quest) don't matter.
        outgrown = "you've outgrown this (Mining 96; this method's rates are for levels 30–40)"
        ruled_out = [
            ({"name": "m1"}, ["already 99"]),
            ({"name": "m2"}, [outgrown]),
            ({"name": "m3"}, ["already 99", outgrown]),
            ({"name": "m4"}, ["needs Mining 90 (you have 62)"]),
            ({"name": "m5"}, ["already 99", "quest not done: Family Crest"]),
            ({"name": "m6"}, [outgrown, "quest not done: New Foundations"]),
        ]
        blocked, finished = split_ruled_out(ruled_out)
        self.assertEqual([m["name"] for m, _ in blocked], ["m4"])
        self.assertEqual(finished, 5)

    def test_nothing_ruled_out(self):
        self.assertEqual(split_ruled_out([]), ([], 0))


if __name__ == "__main__":
    unittest.main()
