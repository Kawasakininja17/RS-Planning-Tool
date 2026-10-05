"""The terminal goal menu remembers the last goal per player."""

import tempfile
import unittest
from pathlib import Path

import players
from quest_path import read_last_goal, save_last_goal


class LastGoalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = players.PLAYERS_DIR
        players.PLAYERS_DIR = Path(self.tmp.name)

    def tearDown(self):
        players.PLAYERS_DIR = self.original
        self.tmp.cleanup()

    def test_each_player_has_their_own(self):
        save_last_goal("Hels Glasglo", "Prifddinas")
        save_last_goal("Some Player", "Fort Forinthry")
        self.assertEqual(read_last_goal("Hels Glasglo"), "Prifddinas")
        self.assertEqual(read_last_goal("Some Player"), "Fort Forinthry")
        self.assertTrue((players.PLAYERS_DIR / "hels+glasglo" / "last_goal").is_file())

    def test_nothing_saved_yet(self):
        self.assertIsNone(read_last_goal("Hels Glasglo"))


if __name__ == "__main__":
    unittest.main()
