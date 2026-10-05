"""Tests for quest_path.py: the big goal, chain rows and the quest lists.
Made-up quests and a made-up player; the goal-file tests use a temporary folder."""

import tempfile
import unittest
from pathlib import Path

import players
from account import LEVEL_XP
from quest_path import (
    chain_rows, eligible_by_difficulty, full_chain, goal_for, other_requirements, quest_rank,
    ranked_doable, read_last_goal, save_last_goal, started_quests, useful_to_start,
)
from rs3_planner import SKILL_NAMES


def quest(length, needs=(), skills=None, other=()):
    """One quests.json-style entry."""
    return {"length": length, "quest_requirements": list(needs), "skill_requirements": skills or {},
            "other_requirements": list(other), "source_url": "https://runescape.wiki/", "checked_date": "2026-10-05"}


# A small made-up quest tree. Charlie needs Bravo and Kilo; Bravo needs Alpha and Ranged 75.
QUESTS = {
    "Alpha": quest("Short"),
    "Bravo": quest("Medium", needs=["Alpha"], skills={"Ranged": 75}, other=["A rope"]),
    "Kilo": quest("Long"),
    "Charlie": quest("Long", needs=["Bravo", "Kilo"]),
    "India": quest("Short", needs=["Kilo"]),
    "Lima": quest("Very short"),
    "Delta": quest("Very short", other=["A lantern"]),
}

UNLOCKS = [
    {"name": "Charlie city", "final_quest": "Charlie"},
    {"name": "India isle", "final_quest": "India"},
    {"name": "Lima lake", "final_quest": "Lima"},
    {"name": "Delta door", "final_quest": "Delta"},
]


def record(title, status, difficulty, eligible):
    """One RuneMetrics quest record."""
    return {"title": title, "status": status, "difficulty": difficulty, "userEligible": eligible}


def make_account(records, level=73):
    """Every skill at the same level, plus the given RuneMetrics quest records."""
    skills = {name: {"xp": float(LEVEL_XP[level - 1]), "level": level} for name in SKILL_NAMES}
    quests = {r["title"]: r for r in records}
    completed = {t for t, r in quests.items() if r["status"] == "COMPLETED"}
    return {"skills": skills, "completed_quests": completed, "quests": quests}


# "Some Player": Alpha done, Delta started, Kilo and Lima ready; Echo, Foxtrot and Golf
# are eligible but on no unlock chain (Golf has a difficulty code RuneMetrics never sent).
SOME_PLAYER = make_account([
    record("Alpha", "COMPLETED", 0, True),
    record("Bravo", "NOT_STARTED", 2, False),
    record("Kilo", "NOT_STARTED", 1, True),
    record("Charlie", "NOT_STARTED", 3, False),
    record("India", "NOT_STARTED", 1, False),
    record("Lima", "NOT_STARTED", 0, True),
    record("Delta", "STARTED", 1, True),
    record("Echo", "NOT_STARTED", 0, True),
    record("Foxtrot", "NOT_STARTED", 250, True),
    record("Golf", "NOT_STARTED", 7, True),
    record("Hotel", "COMPLETED", 0, True),
])

NOBODY = make_account([])   # a player with no quest records at all


class TempPlayersDir(unittest.TestCase):
    """Points players.PLAYERS_DIR at an empty temporary folder for each test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = players.PLAYERS_DIR
        players.PLAYERS_DIR = Path(self.tmp.name)

    def tearDown(self):
        players.PLAYERS_DIR = self.original
        self.tmp.cleanup()


class LastGoalTests(TempPlayersDir):
    def test_each_player_has_their_own(self):
        save_last_goal("Hels Glasglo", "Prifddinas")
        save_last_goal("Some Player", "Fort Forinthry")
        self.assertEqual(read_last_goal("Hels Glasglo"), "Prifddinas")
        self.assertEqual(read_last_goal("Some Player"), "Fort Forinthry")
        self.assertTrue((players.PLAYERS_DIR / "hels+glasglo" / "last_goal").is_file())

    def test_nothing_saved_yet(self):
        self.assertIsNone(read_last_goal("Hels Glasglo"))

    def test_save_says_true_when_saved(self):
        self.assertTrue(save_last_goal("Some Player", "Lima lake"))

    def test_save_says_false_when_it_cannot_write(self):
        blocker = Path(self.tmp.name) / "not-a-folder"
        blocker.write_text("a file where the players folder should be", encoding="utf-8")
        players.PLAYERS_DIR = blocker
        self.assertFalse(save_last_goal("Some Player", "Lima lake"))

    def test_garbled_file_reads_as_nothing_saved(self):
        folder = players.player_dir("Some Player")
        folder.mkdir(parents=True)
        (folder / "last_goal").write_bytes(b"\xff\xfe not text")
        self.assertIsNone(read_last_goal("Some Player"))


class GoalForTests(TempPlayersDir):
    def test_saved_goal_is_used(self):
        save_last_goal("Some Player", "Lima lake")
        self.assertEqual(goal_for(UNLOCKS, "Some Player")["final_quest"], "Lima")

    def test_nothing_saved_means_first_unlock(self):
        self.assertIs(goal_for(UNLOCKS, "Some Player"), UNLOCKS[0])

    def test_unknown_saved_name_means_first_unlock(self):
        save_last_goal("Some Player", "An unlock that was renamed")
        self.assertIs(goal_for(UNLOCKS, "Some Player"), UNLOCKS[0])

    def test_garbled_file_means_first_unlock(self):
        folder = players.player_dir("Some Player")
        folder.mkdir(parents=True)
        (folder / "last_goal").write_bytes(b"\xff\xfe not text")
        self.assertIs(goal_for(UNLOCKS, "Some Player"), UNLOCKS[0])

    def test_two_players_keep_their_own_goal(self):
        save_last_goal("Some Player", "Lima lake")
        save_last_goal("Another Player", "Delta door")
        self.assertEqual(goal_for(UNLOCKS, "Some Player")["name"], "Lima lake")
        self.assertEqual(goal_for(UNLOCKS, "Another Player")["name"], "Delta door")


class ChainRowsTests(unittest.TestCase):
    def test_prerequisites_first_with_states_and_reasons(self):
        rows = chain_rows(UNLOCKS[0], QUESTS, SOME_PLAYER)
        self.assertEqual([r["title"] for r in rows], ["Alpha", "Bravo", "Kilo", "Charlie"])
        self.assertEqual([(r["state"], r["reasons"]) for r in rows], [
            ("done", []),
            ("blocked", ["needs Ranged 75 (you have 73)"]),
            ("ready", []),
            ("blocked", ["waiting on Bravo, Kilo"]),
        ])

    def test_difficulty_and_length(self):
        bravo = chain_rows(UNLOCKS[0], QUESTS, SOME_PLAYER)[1]
        self.assertEqual((bravo["difficulty"], bravo["length"]), ("Experienced", "Medium"))

    def test_started_quest(self):
        rows = chain_rows(UNLOCKS[3], QUESTS, SOME_PLAYER)
        self.assertEqual([(r["title"], r["state"], r["reasons"]) for r in rows], [("Delta", "started", [])])

    def test_quest_runemetrics_does_not_list(self):
        # A wiki title RuneMetrics doesn't know: still shown, difficulty unknown ("?").
        rows = chain_rows(UNLOCKS[2], QUESTS, NOBODY)
        self.assertEqual(rows[0]["difficulty"], "?")
        self.assertEqual((rows[0]["state"], rows[0]["reasons"]),
                         ("blocked", ["RuneMetrics says you're not eligible yet"]))


class OtherRequirementsTests(unittest.TestCase):
    def test_unfinished_quests_only_in_chain_order(self):
        chain = full_chain("Charlie", QUESTS)
        self.assertEqual(other_requirements(chain, QUESTS, SOME_PLAYER), [("A rope", "Bravo")])

    def test_started_quest_still_counts(self):
        self.assertEqual(other_requirements(["Delta"], QUESTS, SOME_PLAYER), [("A lantern", "Delta")])

    def test_none_once_done(self):
        done = make_account([record("Bravo", "COMPLETED", 2, True)])
        self.assertEqual(other_requirements(["Bravo"], QUESTS, done), [])


class RankingTests(unittest.TestCase):
    def test_more_unlocks_beats_shorter(self):
        # Kilo helps 2 unlocks (Charlie, India) but is Long; Lima helps 1 and is Very short.
        self.assertLess(quest_rank("Kilo", UNLOCKS, QUESTS, SOME_PLAYER),
                        quest_rank("Lima", UNLOCKS, QUESTS, SOME_PLAYER))

    def test_ranked_doable_unchanged(self):
        # Pins today's behaviour before quest_rank is lifted out of ranked_doable.
        self.assertEqual(ranked_doable(UNLOCKS[0], UNLOCKS, QUESTS, SOME_PLAYER), (["Kilo"], True))
        self.assertEqual(ranked_doable(UNLOCKS[3], UNLOCKS, QUESTS, SOME_PLAYER), (["Delta"], True))


class QuestListTests(unittest.TestCase):
    def test_useful_to_start_is_eligible_not_started_and_on_a_chain_best_first(self):
        self.assertEqual(useful_to_start(UNLOCKS, QUESTS, SOME_PLAYER), ["Kilo", "Lima"])

    def test_useful_is_part_of_the_full_list(self):
        everything = {t for _, titles in eligible_by_difficulty(SOME_PLAYER) for t in titles}
        self.assertTrue(set(useful_to_start(UNLOCKS, QUESTS, SOME_PLAYER)) <= everything)

    def test_eligible_grouped_known_difficulties_first(self):
        self.assertEqual(eligible_by_difficulty(SOME_PLAYER), [
            ("Novice", ["Echo", "Lima"]),
            ("Intermediate", ["Kilo"]),
            ("Special", ["Foxtrot"]),
            ("Unknown (7)", ["Golf"]),
        ])

    def test_started(self):
        self.assertEqual(started_quests(SOME_PLAYER), ["Delta"])

    def test_empty_player(self):
        self.assertEqual(useful_to_start(UNLOCKS, QUESTS, NOBODY), [])
        self.assertEqual(eligible_by_difficulty(NOBODY), [])
        self.assertEqual(started_quests(NOBODY), [])


if __name__ == "__main__":
    unittest.main()
