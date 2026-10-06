"""Tests for progress.py: reading snapshots, max cape per day, gains and the skill list.
Made-up snapshots for "Some Player"; the file tests use a temporary folder, never the
real data/players/."""

import datetime
import json
import random
import tempfile
import unittest
from pathlib import Path

import players
from account import read_account, skill_rows
from progress import (
    default_skill, gain_lines, last_per_day, max_cape_points, max_cape_xp, read_snapshots, set_aside_future,
    signed_xp, since_text, skill_gain_since_first, skill_order, skill_points, skills_moved,
)
from rs3_planner import SKILL_NAMES, xp_needed_for_99
from snapshots import save_snapshot

NAME = "Some Player"
TODAY = datetime.date(2026, 10, 20)   # so "7 days before" is 13 Oct

# XP for max cape: 28 skills x 13,034,431 + Invention's elite 99, 36,073,511.
NEEDED = 401_037_579


def skills(**changes):
    """All 29 skills at 1,000,000 XP (below 99 everywhere), with some changed: skills(Mining=2_000_000)."""
    xp = {name: 1_000_000.0 for name in SKILL_NAMES}
    xp.update(changes)
    return xp


def snap(day, hour, minute=0, total=0, **changes):
    """One snapshot, as progress.py hands them out, on a day in October 2026."""
    return {"when": datetime.datetime(2026, 10, day, hour, minute), "total_xp": total,
            "skills": skills(**changes)}


def record(fetched_at="2026-10-05T09:00:00", total_xp=1234, skills_xp=None):
    """A snapshot file's contents, in the shape snapshots.save_snapshot writes."""
    return {"username": NAME, "fetched_at": fetched_at, "total_xp": total_xp,
            "skills": {"Attack": 10.5} if skills_xp is None else skills_xp}


class ReadSnapshotsTests(unittest.TestCase):
    """read_snapshots, with players.PLAYERS_DIR pointed at an empty temporary folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = players.PLAYERS_DIR
        players.PLAYERS_DIR = Path(self.tmp.name)
        self.folder = players.PLAYERS_DIR / "some+player" / "snapshots"

    def tearDown(self):
        players.PLAYERS_DIR = self.original
        self.tmp.cleanup()

    def write(self, filename, contents):
        """Put a file in Some Player's snapshots folder: a dict or list as JSON, or raw bytes."""
        self.folder.mkdir(parents=True, exist_ok=True)
        data = contents if isinstance(contents, bytes) else json.dumps(contents).encode("utf-8")
        (self.folder / filename).write_bytes(data)

    def test_no_folder_means_no_snapshots(self):
        self.assertEqual(read_snapshots(NAME), ([], 0))

    def test_oldest_first_by_the_time_inside(self):
        # The file names are in the opposite order on purpose: the time inside decides.
        self.write("a.json", record(fetched_at="2026-10-05T15:00:00", total_xp=2))
        self.write("b.json", record(fetched_at="2026-10-05T09:00:00", total_xp=1))
        snapshots, skipped = read_snapshots(NAME)
        self.assertEqual([s["total_xp"] for s in snapshots], [1, 2])
        self.assertEqual(skipped, 0)

    def test_reads_back_what_save_snapshot_writes(self):
        profile = {"totalxp": 1234, "skillvalues": [{"id": 0, "xp": 105}]}
        save_snapshot(NAME, profile, datetime.datetime(2026, 10, 5, 9, 0))
        snapshots, skipped = read_snapshots(NAME)
        self.assertEqual(skipped, 0)
        self.assertEqual(snapshots, [{"when": datetime.datetime(2026, 10, 5, 9, 0),
                                      "total_xp": 1234, "skills": {"Attack": 10.5}}])

    def test_broken_files_are_skipped_and_counted(self):
        self.write("good.json", record())
        self.write("not-json.json", b"{oops")
        self.write("not-utf8.json", b"\xff\xfe\x00")
        self.write("a-list.json", [1, 2, 3])
        self.write("no-skills.json", {"fetched_at": "2026-10-05T10:00:00", "total_xp": 5})
        self.write("bad-date.json", record(fetched_at="yesterday"))
        self.write("time-zone.json", record(fetched_at="2026-10-05T10:00:00+00:00"))
        self.write("text-total.json", record(total_xp="lots"))
        self.write("text-xp.json", record(skills_xp={"Attack": "lots"}))
        self.write("true-total.json", record(total_xp=True))
        snapshots, skipped = read_snapshots(NAME)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(skipped, 9)

    def test_not_a_number_values_are_skipped(self):
        # Python's JSON reader accepts NaN and Infinity; a damaged file could hold them.
        self.write("nan-total.json", b'{"fetched_at": "2026-10-05T10:00:00", "total_xp": NaN, "skills": {"Attack": 1}}')
        self.write("inf-xp.json", b'{"fetched_at": "2026-10-05T11:00:00", "total_xp": 5, "skills": {"Attack": Infinity}}')
        self.assertEqual(read_snapshots(NAME), ([], 2))

    def test_unknown_skill_names_are_ignored(self):
        self.write("a.json", record(skills_xp={"Attack": 5, "Sailing": 7}))
        snapshots, _ = read_snapshots(NAME)
        self.assertEqual(snapshots[0]["skills"], {"Attack": 5})

    def test_other_files_in_the_folder_are_not_read(self):
        self.write("notes.txt", b"hello")
        self.assertEqual(read_snapshots(NAME), ([], 0))


class MaxCapeTests(unittest.TestCase):
    def test_all_below_99_counts_everything(self):
        cape = max_cape_xp(skills())
        self.assertEqual(cape["needed"], NEEDED)
        self.assertEqual(cape["done"], 29_000_000)
        self.assertEqual(cape["to_go"], 372_037_579)
        self.assertAlmostEqual(cape["percent"], 7.2312425, places=6)

    def test_xp_past_99_is_capped(self):
        # Woodcutting counts only up to 13,034,431; Invention up to its elite 99, 36,073,511.
        cape = max_cape_xp(skills(Woodcutting=20_000_000, Invention=40_000_000))
        self.assertEqual(cape["done"], 27_000_000 + 13_034_431 + 36_073_511)
        self.assertEqual(cape["to_go"], 324_929_637)

    def test_invention_below_elite_99_is_not_capped(self):
        # 20M is past the normal 99, but below Invention's elite 99, so all of it counts.
        cape = max_cape_xp(skills(Invention=20_000_000))
        self.assertEqual(cape["done"], 28_000_000 + 20_000_000)

    def test_xp_to_go_matches_homes_card_exactly(self):
        # XP comes in tenths, so XP to go often ends in .5; adding the same numbers in
        # another order can round it the other way. Progress must add them up exactly
        # as Home's card does (rs3_planner.xp_needed_for_99), on many made-up accounts.
        rng = random.Random(7)
        for _ in range(2000):
            profile = {"skillvalues": [{"id": i, "xp": rng.randrange(0, 200_000_000), "level": 1}
                                       for i in range(len(SKILL_NAMES))]}
            xp = {SKILL_NAMES[s["id"]]: s["xp"] / 10 for s in profile["skillvalues"]}
            home = sum(gap for _, gap in xp_needed_for_99(profile))
            self.assertEqual(max_cape_xp(xp)["to_go"], home)

    def test_a_missing_skill_gives_none(self):
        xp = skills()
        del xp["Mining"]
        self.assertIsNone(max_cape_xp(xp))


class PerDayTests(unittest.TestCase):
    def test_last_snapshot_of_each_day_in_date_order(self):
        morning, evening, next_day = snap(5, 9), snap(5, 15), snap(6, 10)
        self.assertEqual(last_per_day([morning, evening, next_day]), [evening, next_day])

    def test_max_cape_points(self):
        points = max_cape_points([snap(5, 15), snap(6, 10, Mining=1_500_000)])
        self.assertEqual(points, [(datetime.date(2026, 10, 5), 372_037_579),
                                  (datetime.date(2026, 10, 6), 371_537_579)])

    def test_skill_points(self):
        points = skill_points([snap(5, 15), snap(6, 10, Mining=1_200_000)], "Mining")
        self.assertEqual(points, [(datetime.date(2026, 10, 5), 1_000_000),
                                  (datetime.date(2026, 10, 6), 1_200_000)])

    def test_points_are_whole_numbers_rounded_like_the_labels(self):
        # The labels use Python's ',.0f', which rounds a .5 to the even number; the
        # chart's hover text must show the same number, so points arrive already whole.
        points = skill_points([snap(5, 15, Mining=28_718_588.5), snap(6, 10, Mining=28_718_589.5)], "Mining")
        self.assertEqual([value for _, value in points], [28_718_588, 28_718_590])
        self.assertTrue(all(isinstance(value, int) for _, value in points))
        cape_points = max_cape_points([snap(5, 15, Mining=1_000_000.5), snap(6, 10)])
        self.assertTrue(all(isinstance(value, int) for _, value in cape_points))

    def test_a_day_missing_a_skill_is_left_out(self):
        broken = snap(6, 10)
        del broken["skills"]["Mining"]
        snapshots = [snap(5, 15), broken, snap(7, 9)]
        self.assertEqual([day.day for day, _ in max_cape_points(snapshots)], [5, 7])
        self.assertEqual([day.day for day, _ in skill_points(snapshots, "Mining")], [5, 7])


class TextTests(unittest.TestCase):
    def test_since_today_shows_only_the_time(self):
        self.assertEqual(since_text(datetime.datetime(2026, 10, 20, 8, 39), TODAY), "since 08:39")

    def test_since_another_day_adds_the_date(self):
        self.assertEqual(since_text(datetime.datetime(2026, 10, 5, 15, 33), TODAY), "since 15:33, 5 Oct")

    def test_signed_xp(self):
        self.assertEqual(signed_xp(726_291), "+726,291")
        self.assertEqual(signed_xp(723_056.7), "+723,057")
        self.assertEqual(signed_xp(0), "+0")
        self.assertEqual(signed_xp(-0.4), "+0")
        self.assertEqual(signed_xp(-1_500), "−1,500")


class GainLinesTests(unittest.TestCase):
    """TODAY is 20 Oct, so the 7-day line starts at the last snapshot on or before 13 Oct."""

    def starts(self, lines):
        """Each line as (name, state, (day, hour) of its start), for easy comparing."""
        return [(line["name"], line["state"],
                 line["start"] and (line["start"]["when"].day, line["start"]["when"].hour))
                for line in lines]

    def test_no_snapshots(self):
        self.assertEqual(gain_lines([], TODAY), [])

    def test_today_starts_at_yesterdays_last_snapshot(self):
        lines = gain_lines([snap(19, 22, total=100), snap(20, 9, total=150), snap(20, 12, total=200)], TODAY)
        # Since first snapshot would start at the same 19 Oct snapshot, so it's left out.
        self.assertEqual(self.starts(lines), [("Today", "gain", (19, 22))])
        self.assertEqual(lines[0]["total"], 100)

    def test_today_when_everything_is_from_today(self):
        lines = gain_lines([snap(20, 8, total=10), snap(20, 15, total=25)], TODAY)
        self.assertEqual(self.starts(lines), [("Today", "gain", (20, 8))])
        self.assertEqual(lines[0]["total"], 15)

    def test_all_three_lines(self):
        snapshots = [snap(1, 9, total=0), snap(10, 9, total=10), snap(13, 18, total=20),
                     snap(19, 20, total=30), snap(20, 9, total=45, Mining=1_000_015)]
        lines = gain_lines(snapshots, TODAY)
        self.assertEqual(self.starts(lines), [("Today", "gain", (19, 20)),
                                              ("Last 7 days", "gain", (13, 18)),
                                              ("Since first snapshot", "gain", (1, 9))])
        self.assertEqual([line["total"] for line in lines], [15, 25, 45])
        self.assertEqual([line["max_cape"] for line in lines], [15, 15, 15])

    def test_no_snapshot_from_today(self):
        lines = gain_lines([snap(18, 9, total=0), snap(19, 9, total=7)], TODAY)
        self.assertEqual(self.starts(lines), [("Today", "none_today", None),
                                              ("Since first snapshot", "gain", (18, 9))])
        self.assertEqual(lines[1]["total"], 7)

    def test_a_newest_snapshot_dated_after_today(self):
        # The computer's clock was wrong once: the newest file says "tomorrow".
        lines = gain_lines([snap(19, 9), snap(21, 9)], TODAY)
        self.assertEqual(self.starts(lines)[0], ("Today", "none_today", None))

    def test_only_one_snapshot(self):
        self.assertEqual(self.starts(gain_lines([snap(20, 9)], TODAY)), [("Today", "only_one", None)])

    def test_seven_day_line_left_out_when_it_repeats_today(self):
        # 13 Oct is both the last snapshot before today and the last one 7+ days old.
        lines = gain_lines([snap(13, 9), snap(20, 9)], TODAY)
        self.assertEqual(self.starts(lines), [("Today", "gain", (13, 9))])

    def test_xp_going_down_shows_as_a_negative_gain(self):
        lines = gain_lines([snap(19, 9, total=100), snap(20, 9, total=90)], TODAY)
        self.assertEqual(lines[0]["total"], -10)

    def test_max_cape_unknown_when_a_snapshot_lacks_a_skill(self):
        start = snap(19, 9, total=100)
        del start["skills"]["Mining"]
        lines = gain_lines([start, snap(20, 9, total=150)], TODAY)
        self.assertEqual(lines[0]["total"], 50)
        self.assertIsNone(lines[0]["max_cape"])


class SkillsMovedTests(unittest.TestCase):
    def test_one_snapshot_moves_nothing(self):
        self.assertEqual(skills_moved([snap(20, 9)], TODAY), (None, []))

    def test_only_gains_biggest_first(self):
        start = snap(13, 9)
        del start["skills"]["Archaeology"]   # missing at the start: can't say how much it moved
        newest = snap(20, 9, Mining=1_500_000, Fishing=1_100_000, Attack=900_000, Archaeology=2_000_000)
        found_start, moved = skills_moved([snap(1, 9), start, newest], TODAY)
        self.assertIs(found_start, start)   # the 7-day start
        self.assertEqual(moved, [("Mining", 500_000), ("Fishing", 100_000)])

    def test_falls_back_to_the_first_snapshot(self):
        first = snap(18, 9)
        found_start, moved = skills_moved([first, snap(20, 9, Mining=1_000_100)], TODAY)
        self.assertIs(found_start, first)
        self.assertEqual(moved, [("Mining", 100)])


class SkillOrderTests(unittest.TestCase):
    def test_same_order_as_the_skills_screen(self):
        # Every skill a different XP; Archaeology and Necromancy are past 99
        # (Invention's 13.5M isn't: its 99 is 36M).
        profile = {"skillvalues": [{"id": i, "xp": (i + 1) * 500_000 * 10, "level": 1}
                                   for i in range(len(SKILL_NAMES))]}
        account = read_account(profile, {"quests": []})
        xp = {name: skill["xp"] for name, skill in account["skills"].items()}
        self.assertEqual(skill_order(xp), [row["name"] for row in skill_rows(account)])

    def test_closest_to_99_first_and_finished_last(self):
        order = skill_order(skills(Mining=12_000_000, Fishing=20_000_000, Thieving=14_000_000))
        self.assertEqual(order[0], "Mining")
        self.assertEqual(order[-2:], ["Fishing", "Thieving"])   # finished: most XP first


class DefaultSkillTests(unittest.TestCase):
    def test_the_skill_that_moved_most(self):
        snapshots = [snap(19, 9), snap(20, 9, Fishing=1_000_050, Mining=1_000_900)]
        self.assertEqual(default_skill(snapshots, TODAY), "Mining")

    def test_closest_to_99_when_nothing_moved(self):
        snapshots = [snap(19, 9, Smithing=12_000_000), snap(20, 9, Smithing=12_000_000)]
        self.assertEqual(default_skill(snapshots, TODAY), "Smithing")

    def test_no_snapshots(self):
        self.assertIsNone(default_skill([], TODAY))


class FutureTests(unittest.TestCase):
    def test_snapshots_dated_after_today_are_set_aside(self):
        # A wrong computer clock once: files dated after today would freeze the
        # Gained panel at that date, so they are set aside and counted.
        kept, future = set_aside_future([snap(19, 9), snap(20, 23), snap(21, 9), snap(25, 1)], TODAY)
        self.assertEqual([s["when"].day for s in kept], [19, 20])
        self.assertEqual(future, 2)

    def test_nothing_to_set_aside(self):
        self.assertEqual(set_aside_future([], TODAY), ([], 0))


class SkillGainTests(unittest.TestCase):
    def test_gain_from_first_to_newest(self):
        snapshots = [snap(20, 8), snap(20, 12), snap(20, 15, Woodcutting=1_723_057)]
        self.assertEqual(skill_gain_since_first(snapshots, "Woodcutting"), 723_057)

    def test_unknown_with_one_snapshot_or_a_missing_skill(self):
        self.assertIsNone(skill_gain_since_first([snap(20, 8)], "Mining"))
        first = snap(20, 8)
        del first["skills"]["Mining"]
        self.assertIsNone(skill_gain_since_first([first, snap(20, 9)], "Mining"))


if __name__ == "__main__":
    unittest.main()
