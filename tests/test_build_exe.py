"""Tests for tools/build_exe.py's checks (the parts that don't build anything).

Nothing here runs PyInstaller, git or the network; files are made in a
temporary folder. The only player name used is "Some Player".
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))   # the scripts in tools/ aren't on the import path by default

import build_exe


class VersionLineTests(unittest.TestCase):
    def test_clean_build(self):
        self.assertEqual(build_exe.version_line("2026-10-12", "ea96c3c", False),
                         "RS3 Planner 2026-10-12 (ea96c3c)")

    def test_uncommitted_changes_are_marked(self):
        self.assertEqual(build_exe.version_line("2026-10-12", "ea96c3c", True),
                         "RS3 Planner 2026-10-12 (ea96c3c, uncommitted changes)")


class WhatGoesInTests(unittest.TestCase):
    def test_only_the_three_data_files_and_static(self):
        # Never the data/ folder itself: that would bring data/players/ along.
        self.assertEqual(build_exe.DATA_FILES, [
            ("data/methods.json", "data"),
            ("data/quests.json", "data"),
            ("data/unlocks.json", "data"),
            ("static", "static"),
        ])


class ForbiddenPathTests(unittest.TestCase):
    def test_player_files_are_caught(self):
        paths = [
            "_internal/data/methods.json",
            "_internal/data/players/current.txt",
            "_internal/data/players/some+player/answers.json",
            "_internal/x/snapshots/2026-10-05_0900.json",
            "_internal/last_goal",
            "_internal/Players/x.txt",
        ]
        self.assertEqual(build_exe.forbidden_paths(paths), paths[1:])

    def test_the_real_bundle_files_pass(self):
        paths = ["RS3 Planner.exe", "Start here.txt", "_internal/data/methods.json", "_internal/data/quests.json",
                 "_internal/data/unlocks.json", "_internal/static/app.css", "_internal/version.txt",
                 "_internal/nicegui/static/echarts.min.js"]
        self.assertEqual(build_exe.forbidden_paths(paths), [])


class NameSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_name_forms(self):
        self.assertEqual(build_exe.name_forms("some+player"), {"some+player", "some player"})

    def test_forms_already_public_are_skipped(self):
        public = b"readme ... some+player ... more text"
        self.assertEqual(build_exe.names_to_look_for(["some+player"], public), ["some player"])

    def test_hits_are_counted_ignoring_case_and_never_printed(self):
        (self.root / "a.txt").write_bytes(b"hello SOME PLAYER")
        (self.root / "b.bin").write_bytes(b"\x00\x01\x02")
        (self.root / "c.txt").write_bytes(b"some+player and some player")
        files = sorted(self.root.iterdir())
        out = io.StringIO()
        with redirect_stdout(out):
            result = build_exe.count_name_hits(self.root, files, ["some player", "some+player"])
        self.assertEqual(result, (2, 2))   # 2 names found, in 2 files
        self.assertEqual(out.getvalue(), "")

    def test_names_in_file_paths_count_too(self):
        (self.root / "some+player.json").write_bytes(b"{}")
        files = sorted(self.root.iterdir())
        self.assertEqual(build_exe.count_name_hits(self.root, files, ["some+player"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
