"""Tests for players.py. Every test uses a temporary folder, never the real data/players/."""

import json
import tempfile
import unittest
from pathlib import Path

import players


class TempPlayersDir(unittest.TestCase):
    """Points players.PLAYERS_DIR at an empty temporary folder for each test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = players.PLAYERS_DIR
        players.PLAYERS_DIR = Path(self.tmp.name)

    def tearDown(self):
        players.PLAYERS_DIR = self.original
        self.tmp.cleanup()


class FolderNameTests(unittest.TestCase):
    def test_lower_case_and_spaces_become_plus(self):
        self.assertEqual(players.folder_name("Hels Glasglo"), "hels+glasglo")

    def test_surrounding_spaces_ignored(self):
        self.assertEqual(players.folder_name("  hels glasglo "), "hels+glasglo")

    def test_hyphen_underscore_and_space_stay_different(self):
        names = {players.folder_name(n) for n in ("a b", "a-b", "a_b")}
        self.assertEqual(len(names), 3)


class AnswersTests(TempPlayersDir):
    def test_no_file_means_no_answers(self):
        self.assertEqual(players.read_answers("Hels Glasglo"), {})

    def test_save_and_read_back(self):
        players.save_answer("Hels Glasglo", "smithing-autoheater", False)
        players.save_answer("Hels Glasglo", "assistant-qualification", True)
        self.assertEqual(players.read_answers("Hels Glasglo"),
                         {"smithing-autoheater": False, "assistant-qualification": True})

    def test_file_lives_in_player_folder(self):
        players.save_answer("Hels Glasglo", "smithing-autoheater", True)
        self.assertTrue((players.PLAYERS_DIR / "hels+glasglo" / "answers.json").is_file())

    def test_none_forgets_an_answer(self):
        players.save_answer("Hels Glasglo", "smithing-autoheater", False)
        players.save_answer("Hels Glasglo", "smithing-autoheater", None)
        self.assertEqual(players.read_answers("Hels Glasglo"), {})

    def test_broken_file_gives_clear_error(self):
        folder = players.PLAYERS_DIR / "hels+glasglo"
        folder.mkdir(parents=True)
        (folder / "answers.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            players.read_answers("Hels Glasglo")
        self.assertIn("answers.json", str(caught.exception))

    def test_answer_that_is_not_true_or_false_is_an_error(self):
        folder = players.PLAYERS_DIR / "hels+glasglo"
        folder.mkdir(parents=True)
        (folder / "answers.json").write_text('{"smithing-autoheater": "yes"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            players.read_answers("Hels Glasglo")


class CheckNameTests(unittest.TestCase):
    def test_trims_spaces(self):
        self.assertEqual(players.check_name("  Hels Glasglo "), ("Hels Glasglo", None))

    def test_hyphen_underscore_and_leading_hyphen_allowed(self):
        self.assertEqual(players.check_name("-a_b-1"), ("-a_b-1", None))

    def test_empty_is_a_problem(self):
        name, problem = players.check_name("   ")
        self.assertIsNone(name)
        self.assertEqual(problem, "Type a RuneScape name first.")

    def test_none_is_a_problem(self):
        self.assertIsNone(players.check_name(None)[0])

    def test_too_long(self):
        name, problem = players.check_name("A" * 13)
        self.assertIsNone(name)
        self.assertIn("at most 12 characters", problem)

    def test_twelve_is_fine(self):
        self.assertEqual(players.check_name("A" * 12)[1], None)

    def test_odd_characters(self):
        name, problem = players.check_name("Hels@Glasglo")
        self.assertIsNone(name)
        self.assertIn("letters, numbers, spaces, hyphens (-) and underscores (_)", problem)


class CurrentPlayerTests(TempPlayersDir):
    def test_nothing_saved(self):
        self.assertIsNone(players.read_current())

    def test_save_and_read_back(self):
        players.save_current("Hels Glasglo")
        self.assertEqual(players.read_current(), "Hels Glasglo")

    def test_empty_file_means_none(self):
        (players.PLAYERS_DIR / "current.txt").write_text("\n", encoding="utf-8")
        self.assertIsNone(players.read_current())

    def test_cli_player_uses_given_name(self):
        self.assertEqual(players.cli_player(" Some Player "), "Some Player")

    def test_cli_player_rejects_bad_name(self):
        with self.assertRaises(SystemExit):
            players.cli_player("Hels@Glasglo")

    def test_cli_player_falls_back_to_current(self):
        players.save_current("Hels Glasglo")
        self.assertEqual(players.cli_player(None), "Hels Glasglo")


class KnownPlayersTests(TempPlayersDir):
    def add_snapshot(self, folder, file_name, username):
        snapshots = players.PLAYERS_DIR / folder / "snapshots"
        snapshots.mkdir(parents=True, exist_ok=True)
        (snapshots / file_name).write_text(json.dumps({"username": username}), encoding="utf-8")

    def test_names_from_newest_snapshot_sorted(self):
        self.add_snapshot("some+player", "2026-10-05_0900.json", "Some Player")
        self.add_snapshot("hels+glasglo", "2026-10-05_0800.json", "hels glasglo")
        self.add_snapshot("hels+glasglo", "2026-10-05_0900.json", "Hels Glasglo")
        self.assertEqual(players.known_players(), ["Hels Glasglo", "Some Player"])

    def test_folder_without_snapshots_is_skipped(self):
        (players.PLAYERS_DIR / "nobody").mkdir()
        self.assertEqual(players.known_players(), [])

    def test_no_players_folder_at_all(self):
        players.PLAYERS_DIR = players.PLAYERS_DIR / "does-not-exist"
        self.assertEqual(players.known_players(), [])


if __name__ == "__main__":
    unittest.main()
