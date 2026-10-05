"""Tests for player_cache.py: the app's in-memory store of fetched players. No network."""

import datetime
import unittest

import player_cache
from account import LEVEL_XP
from rs3_planner import SKILL_NAMES

WHEN = datetime.datetime(2026, 10, 5, 10, 0)

# A tiny RuneMetrics-shaped reply: every skill at level 50, RuneMetrics' own capitals.
PROFILE = {"name": "Hels Glasglo", "totalxp": 0,
           "skillvalues": [{"id": i, "xp": LEVEL_XP[49] * 10, "level": 50} for i in range(len(SKILL_NAMES))]}
QUESTS = {"quests": []}


class FakeRuneMetrics(unittest.TestCase):
    """Replaces the two download functions for each test, so nothing goes online."""

    def setUp(self):
        self.originals = player_cache.load_profile, player_cache.load_quests
        player_cache.load_profile = lambda name: PROFILE
        player_cache.load_quests = lambda name: QUESTS

    def tearDown(self):
        player_cache.load_profile, player_cache.load_quests = self.originals


class SpellingTests(FakeRuneMetrics):
    def test_other_spelling_is_found_under_runemetrics_name(self):
        # RuneMetrics answers "hels-glasglo" with "Hels Glasglo" (checked live 2026-10-05).
        cache = {}
        profile, account, _ = player_cache.fetch_safely("hels-glasglo")
        player_cache.record_success(cache, "hels-glasglo", profile, account, WHEN)
        entry = player_cache.entry_for(cache, "Hels Glasglo")
        self.assertEqual(entry["name"], "Hels Glasglo")
        self.assertIsNotNone(entry["account"])

    def test_both_spellings_need_no_second_fetch(self):
        cache = {}
        profile, account, _ = player_cache.fetch_safely("hels-glasglo")
        player_cache.record_success(cache, "hels-glasglo", profile, account, WHEN)
        self.assertFalse(player_cache.needs_fetch(cache, "hels-glasglo"))
        self.assertFalse(player_cache.needs_fetch(cache, "Hels Glasglo"))

    def test_unknown_player_needs_fetch(self):
        self.assertTrue(player_cache.needs_fetch({}, "Some Player"))


class FailureTests(FakeRuneMetrics):
    def test_plain_runemetrics_message_is_kept(self):
        def private(name):
            raise SystemExit("Could not load profile: This player's RuneMetrics profile is set to private.")
        player_cache.load_profile = private
        self.assertEqual(player_cache.fetch_safely("Some Player"),
                         (None, None, "Could not load profile: This player's RuneMetrics profile is set to private."))

    def test_unexpected_network_error_becomes_a_message(self):
        def dropped(name):
            raise ConnectionResetError("connection reset by peer")
        player_cache.load_profile = dropped
        profile, account, error = player_cache.fetch_safely("Some Player")
        self.assertEqual((profile, account), (None, None))
        self.assertIn("Something unexpected went wrong", error)
        self.assertIn("ConnectionResetError", error)

    def test_odd_reply_becomes_a_message(self):
        player_cache.load_profile = lambda name: {"name": "Some Player"}   # no "skillvalues"
        profile, account, error = player_cache.fetch_safely("Some Player")
        self.assertIsNone(account)
        self.assertIn("Something unexpected went wrong", error)

    def test_failure_keeps_older_stats(self):
        cache = {}
        profile, account, _ = player_cache.fetch_safely("Hels Glasglo")
        player_cache.record_success(cache, "Hels Glasglo", profile, account, WHEN)
        player_cache.record_failure(cache, "Hels Glasglo", "no internet")
        entry = player_cache.entry_for(cache, "Hels Glasglo")
        self.assertEqual(entry["error"], "no internet")
        self.assertIs(entry["account"], account)


if __name__ == "__main__":
    unittest.main()
