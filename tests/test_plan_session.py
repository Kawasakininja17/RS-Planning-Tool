"""Tests for unlock answers and extra levels in plan_session.check_method_for_session."""

import copy
import re
import unittest

from account import level_table
from plan_session import (
    ALREADY_120, OUTGROWN, also_text, build_plan, check_method_for_session, closest_skill,
    level_change_text, percent_text, pick_paths, runner_ups, split_ruled_out,
)
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
    """Every skill at the start of the same level (each on its own XP table), no quests done."""
    skills = {name: {"xp": float(level_table(name)[level - 1]), "level": level} for name in SKILL_NAMES}
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
        account["skills"][skill] = {"xp": float(level_table(skill)[level - 1]), "level": level}
    return account


def part_way(account, skill, level, extra_xp):
    """Put a skill at a level plus some XP into it (extra_xp must stay below the next level)."""
    account["skills"][skill] = {"xp": level_table(skill)[level - 1] + extra_xp, "level": level}
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


def ready_method(name, fraction=None, low=None, high=None, gp=None, skill="Mining"):
    """A method as build_plan leaves it once it is ready (training ones carry _closest)."""
    method = {"name": name, "type": "money" if gp is not None else "training", "skill": skill,
              "xp_per_hour_low": low, "xp_per_hour_high": high if high is not None else low,
              "gp_per_hour": gp}
    if gp is None:
        method["_closest"] = {"skill": skill, "fraction": fraction}
    return method


class RunnerUpTests(unittest.TestCase):
    def setUp(self):
        # Path A (furthest through its level): t1, then t5, t2, t3, t4. Most XP (B, low end):
        # t2, t3, t4, t1, t5. Each trains its own skill, so A's different-skills rule
        # removes nothing here.
        self.t1 = ready_method("t1", fraction=0.9, low=10, skill="Mining")
        self.t2 = ready_method("t2", fraction=0.7, low=50, skill="Smithing")
        self.t3 = ready_method("t3", fraction=0.6, low=40, skill="Cooking")
        self.t4 = ready_method("t4", fraction=0.5, low=30, skill="Firemaking")
        self.t5 = ready_method("t5", fraction=0.8, low=5, skill="Divination")
        self.g1 = ready_method("g1", gp=900)
        self.g2 = ready_method("g2", gp=700)
        self.g3 = ready_method("g3", gp=800)
        self.ready = [self.t1, self.t2, self.t3, self.t4, self.t5, self.g1, self.g2, self.g3]

    def test_each_path_gets_its_next_two_by_its_own_rule(self):
        picks = pick_paths(self.ready)
        self.assertEqual([m["name"] for m in picks], ["t1", "t2", "g1"])   # pick_paths unchanged
        also = runner_ups(self.ready, picks)
        # B's own order is t3, t4, t5, but t3 and t5 are already under A, so B gets only t4.
        self.assertEqual([[m["name"] for m in path] for path in also],
                         [["t5", "t3"], ["t4"], ["g3", "g2"]])

    def test_a_shows_each_skill_once(self):
        t6 = ready_method("t6", fraction=0.85, low=1, skill="Mining")      # same skill as A's pick t1
        t7 = ready_method("t7", fraction=0.75, low=2, skill="Divination")  # same skill as t5
        ready = self.ready + [t6, t7]
        picks = pick_paths(ready)
        self.assertEqual([m["name"] for m in picks], ["t1", "t2", "g1"])
        also = runner_ups(ready, picks)
        self.assertEqual([m["name"] for m in also[0]], ["t5", "t3"])
        # Skipped under A, so B may still offer t7.
        self.assertEqual([m["name"] for m in also[1]], ["t4", "t7"])

    def test_skill_whose_best_method_is_bs_pick_shows_its_next_one(self):
        x1 = ready_method("x1", fraction=0.85, low=100, skill="Hunter")   # fastest: B's pick
        x2 = ready_method("x2", fraction=0.85, low=3, skill="Hunter")
        ready = self.ready + [x1, x2]
        picks = pick_paths(ready)
        self.assertEqual([m["name"] for m in picks], ["t1", "x1", "g1"])
        self.assertEqual([m["name"] for m in runner_ups(ready, picks)[0]], ["x2", "t5"])

    def test_skill_whose_only_method_is_bs_pick_gives_way(self):
        t2 = ready_method("t2", fraction=0.85, low=50, skill="Smithing")  # 2nd closest, but B's pick
        ready = [self.t1, t2, self.t3, self.t4, self.t5, self.g1, self.g2, self.g3]
        picks = pick_paths(ready)
        self.assertEqual([m["name"] for m in picks], ["t1", "t2", "g1"])
        self.assertEqual([m["name"] for m in runner_ups(ready, picks)[0]], ["t5", "t3"])

    def test_a_runner_up_is_never_repeated_under_another_path(self):
        # A is filled first, then B, then C: a method already listed is skipped.
        also = runner_ups(self.ready, pick_paths(self.ready))
        names = [m["name"] for path in also for m in path]
        self.assertEqual(len(names), len(set(names)))

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
        self.assertEqual(also_text(method), "Choking ivy · Woodcutting · 86,000–126,000 XP/hr")

    def test_training_with_one_figure(self):
        method = ready_method("Overgrown idols", low=100000, skill="Woodcutting")
        self.assertEqual(also_text(method), "Overgrown idols · Woodcutting · 100,000 XP/hr")

    def test_money(self):
        method = ready_method("Blessing extra fine sand", gp=3452400, skill="Prayer")
        self.assertEqual(also_text(method), "Blessing extra fine sand · Prayer · 3,452,400 gp/hr")

    def test_a_name_with_brackets_gets_no_second_pair(self):
        method = ready_method("Mining banite (training)", low=84240, high=104520)
        self.assertEqual(also_text(method), "Mining banite (training) · Mining · 84,240–104,520 XP/hr")


class SplitRuledOutTests(unittest.TestCase):
    def test_finished_or_outgrown_are_counted_not_listed(self):
        # Any "already 120" or "outgrown" reason is enough: you'll never use that
        # method, so its other reasons (like a missing quest) don't matter.
        outgrown = "you've outgrown this (Mining 96; this method's rates are for levels 30–40)"
        ruled_out = [
            ({"name": "m1"}, [ALREADY_120]),
            ({"name": "m2"}, [outgrown]),
            ({"name": "m3"}, [ALREADY_120, outgrown]),
            ({"name": "m4"}, ["needs Mining 90 (you have 62)"]),
            ({"name": "m5"}, [ALREADY_120, "quest not done: Family Crest"]),
            ({"name": "m6"}, [outgrown, "quest not done: New Foundations"]),
        ]
        blocked, finished = split_ruled_out(ruled_out)
        self.assertEqual([m["name"] for m, _ in blocked], ["m4"])
        self.assertEqual(finished, 5)

    def test_nothing_ruled_out(self):
        self.assertEqual(split_ruled_out([]), ([], 0))

    def test_folds_the_reasons_the_checker_really_writes(self):
        # The reasons come from check_method_for_session itself, not typed here,
        # so rewording a reason in one place can't quietly stop the folding.
        outgrown = copy.deepcopy(METHOD)
        outgrown.update(name="Outgrown", min_level=30, max_level=40)
        outgrown["requirements"]["quests"] = ["Family Crest"]   # a second reason, too
        finished = copy.deepcopy(METHOD)
        finished["name"] = "Finished"
        ruled_out = []
        for method, account in ((outgrown, make_account(95)), (finished, make_account(120))):
            blocked, _, _ = check_method_for_session(method, account, 2, YES)
            ruled_out.append((method, blocked))
        self.assertTrue(ruled_out[0][1][0].startswith(OUTGROWN))
        self.assertIn(ALREADY_120, ruled_out[1][1])
        self.assertEqual(split_ruled_out(ruled_out), ([], 2))


class PathATests(unittest.TestCase):
    def test_furthest_through_its_level_wins(self):
        # Cooking 60 is 88% of the way to 61; Smithing 95 only 11% of the way to 96.
        account = part_way(part_way(make_account(95), "Smithing", 95, 100_000), "Cooking", 60, 25_000)
        smith = copy.deepcopy(METHOD)
        cook = copy.deepcopy(METHOD)
        cook.update(name="Cook", skill="Cooking", min_level=1)
        plan = build_plan([smith, cook], account, 5, YES)
        self.assertEqual(plan["paths"][0][1]["name"], "Cook")
        self.assertEqual(smith["_closest"]["skill"], "Smithing")

    def test_tie_goes_to_the_faster_method(self):
        slow = ready_method("slow", fraction=0.5, low=10, skill="Herblore")
        fast = ready_method("fast", fraction=0.5, low=20, skill="Mining")
        self.assertEqual(pick_paths([slow, fast])[0]["name"], "fast")

    def test_two_skill_method_counts_its_further_skill(self):
        # Ranged 73 barely started; Defence 92 is 88% of the way to 93.
        account = part_way(part_way(make_account(95), "Ranged", 73, 1_000), "Defence", 92, 600_000)
        closest = closest_skill({"skill": "Ranged/Defence"}, account)
        self.assertEqual((closest["skill"], closest["next_level"]), ("Defence", 93))
        self.assertAlmostEqual(closest["xp_left"], 78_376)   # 7,195,629 - 6,517,253 - 600,000

    def test_skill_at_120_is_skipped_but_the_method_stays(self):
        account = with_levels(make_account(95), Ranged=120, Defence=105)
        self.assertEqual(closest_skill({"skill": "Ranged/Defence"}, account)["skill"], "Defence")
        blocked, _, _ = check_method_for_session(banded("Ranged/Defence", 70, None), account, 5, YES)
        self.assertEqual(blocked, [])


class FinishedRuleTests(unittest.TestCase):
    def test_skill_past_99_is_ready_now(self):
        # Was "already 99" before; levels past 99 now count.
        account = with_levels(make_account(95), Woodcutting=105)
        blocked, _, _ = check_method_for_session(banded("Woodcutting", 81, None), account, 5, YES)
        self.assertEqual(blocked, [])

    def test_every_skill_at_120_is_finished(self):
        account = with_levels(make_account(95), Woodcutting=120, Ranged=120, Defence=120)
        for skill in ("Woodcutting", "Ranged/Defence"):
            blocked, _, _ = check_method_for_session(banded(skill, 70, None), account, 5, YES)
            self.assertEqual(blocked, [ALREADY_120])
        # A money method for a skill at 120 stays available to path C.
        money = banded("Woodcutting", 70, None)
        money.update(type="money", gp_per_hour=1_000_000)
        blocked, _, _ = check_method_for_session(money, account, 5, YES)
        self.assertEqual(blocked, [])


class PercentTextTests(unittest.TestCase):
    def test_rounds_down(self):
        self.assertEqual(percent_text(0.83949), "83.9%")
        self.assertEqual(percent_text(0.99999), "99.9%")   # never "100.0%" before the level

    def test_keeps_exact_values(self):
        self.assertEqual(percent_text(0.0), "0.0%")
        self.assertEqual(percent_text(0.5), "50.0%")
        self.assertEqual(percent_text(0.29), "29.0%")
        self.assertEqual(percent_text(0.579), "57.9%")


class WhyLineTests(unittest.TestCase):
    def why_a(self, extra_xp):
        account = part_way(make_account(95), "Smithing", 95, extra_xp)
        plan = build_plan([copy.deepcopy(METHOD)], account, 5, YES)
        self.assertEqual(plan["paths"][0][0], "PATH A: finish something")
        return plan["paths"][0][2]

    def test_why_line_for_path_a(self):
        # Smithing 95 -> 96 needs 913,019 XP; 500,000 in is 54.76%.
        line = "Smithing is 54.7% of the way to 96 (413,019 XP left): the furthest of your skills with a ready method."
        self.assertRegex(self.why_a(500_000), r"(?m)^" + re.escape(line) + "$")

    def test_why_line_never_says_0_xp_left(self):
        # 0.3 XP short: rounds up to 1 XP, and the percent rounds down.
        line = "Smithing is 99.9% of the way to 96 (1 XP left): the furthest of your skills with a ready method."
        self.assertRegex(self.why_a(913_018.7), r"(?m)^" + re.escape(line) + "$")


class LevelChangeTextTests(unittest.TestCase):
    def test_level_change_text_uses_elite_for_invention(self):
        account = make_account(95)   # Invention at the start of elite 95: 30,350,318 XP
        self.assertEqual(level_change_text(account, "Invention", 1_000_000, 2_000_000),
                         "Invention 95 -> 95-96 (96 is 1,369,626 XP away)")


if __name__ == "__main__":
    unittest.main()
