"""Tests for players.py. Every test uses a temporary folder, never the real data/players/."""

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


if __name__ == "__main__":
    unittest.main()
