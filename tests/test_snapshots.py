"""save_snapshot writes into the player's own folder."""

import datetime
import json
import tempfile
import unittest
from pathlib import Path

import players
from snapshots import save_snapshot

PROFILE = {"totalxp": 1234, "skillvalues": [{"id": 0, "xp": 105}, {"id": 99, "xp": 10}]}


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = players.PLAYERS_DIR
        players.PLAYERS_DIR = Path(self.tmp.name)

    def tearDown(self):
        players.PLAYERS_DIR = self.original
        self.tmp.cleanup()

    def test_goes_to_player_folder(self):
        path = save_snapshot("Hels Glasglo", PROFILE, datetime.datetime(2026, 10, 5, 9, 0))
        self.assertEqual(path, players.PLAYERS_DIR / "hels+glasglo" / "snapshots" / "2026-10-05_0900.json")
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["username"], "Hels Glasglo")
        self.assertEqual(record["skills"], {"Attack": 10.5})   # XP / 10; unknown skill 99 left out


if __name__ == "__main__":
    unittest.main()
