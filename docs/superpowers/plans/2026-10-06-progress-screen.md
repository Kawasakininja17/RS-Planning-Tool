# Progress Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The bottom nav's Progress button opens a screen that charts the current player's saved snapshots: XP to go for max cape per day, XP gained lately (Today / Last 7 days / Since first snapshot, plus the skills that moved), and one chosen skill's XP per day.

**Architecture:** A new `progress.py` does all the reading, grouping and sums from the snapshot files (pure, tested with `unittest`); `app.py` only draws, with one `line_chart` helper around NiceGUI's bundled `ui.echart`. The screen reads files only: it never fetches.

**Tech Stack:** Python 3.14 standard library (logic, tests via `unittest`), NiceGUI 3.17.1 in `.venv/` (`ui.echart` = ECharts 6, bundled, offline).

**Spec:** `docs/superpowers/specs/2026-10-06-progress-screen-design.md`

## Global Constraints

- Public data only. No new RuneMetrics calls in the app; the Progress screen never fetches.
- Never show made-up numbers: a missing value shows "—" (`NO_VALUE`) or the line is hidden.
- Server stays on `HOST = "127.0.0.1"`. Everything works offline: no CDN, no internet requests from any page.
- Look: existing colours in `static/app.css` only (forest `#0E1712`, panel `#16241B`, border `#2E4636`, parchment `#F0E8D6`, muted `#B9C3B2`, glacial `#A8DCEB`); one column, max 480px, tap targets ≥44px, ~10px corners, no gradients, no emoji. Buttons always via the `button()` helper.
- No other players' names in the repo (docs, tests, commits). Tests use "Some Player".
- Code is simple and commented in plain words, matching the existing files.
- Tests: `python3 -m unittest discover -s tests -v` from the project folder (101 before this plan). Tests never touch the network or the real `data/players/`.
- Scratch work goes in `W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen` (git-ignored by `.superpowers/sdd/.gitignore`), never `/tmp`.
- Stop and wait for Chris after Task 1 (step 3a), Task 2 (step 3b) and Task 3 (step 3c). Commit after each task; never push without asking. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- If any step errors, stop that task, explain (what failed, the error in plain words, likely cause, what's done, what's left, the proper fix) and wait for Chris.

## Review Focus

1. **No live stats loaded** (RuneMetrics down or the start-up fetch failed) while snapshot files exist → Progress still shows everything from the files; the One skill line drops the level ("Woodcutting · 28,718,588 XP"). Pinned in Task 3 (browser check with the frozen profile hidden) and by `levels = {}` when `entry["account"]` is `None`.
2. **The newest snapshot is dated after today** (computer clock was wrong once) → "Today: no snapshot yet", the other lines still measured, no crash. Pinned in Task 1 (`test_a_newest_snapshot_dated_after_today`).
3. **The browser's time zone shifts a chart date to the day before** → dates are sent as local noon ("2026-10-05T12:00:00"). Pinned in Task 3 (browser check: axis and tooltip dates equal the snapshot dates).
4. **XP that goes down between two snapshots** (a RuneMetrics hiccup) → shown honestly as "−10", no crash. Pinned in Task 1 (`test_xp_going_down_shows_as_a_negative_gain`, `test_signed_xp`).
5. **A snapshot missing a skill** (an older file, or a skill RuneMetrics left out) → that day is left out of the charts and "toward max cape" shows "—". Pinned in Task 1 (`test_a_day_missing_a_skill_is_left_out`, `test_max_cape_unknown_when_a_snapshot_lacks_a_skill`) and Task 2 (`NO_VALUE` in `max_cape_panel` and `gained_panel`).

## File map

| File | Change | Responsibility |
|---|---|---|
| `progress.py` | create | Read snapshot files; max cape XP; one point per day; gain lines; skills that moved; skill order; default skill; text helpers `since_text`, `signed_xp` |
| `tests/test_progress.py` | create | Tests for all of the above (37 tests) |
| `app.py` | modify | `/progress` page, nav button, panels, `line_chart`, `numbers_toggle` |
| `static/app.css` | modify | `.chart`, the skill dropdown and its menu |
| `README.md` | modify | Progress in "Using the app"; drop "kept for a future Progress screen" |

Scratch only (never committed): `$W/frozen/` (RuneMetrics replies), `$W/run_frozen.py`, `$W/before/` and `$W/after/` (throwaway project copies), `$W/*.txt` (page texts, sanity values), and an `rs3-frozen` entry in the git-excluded `.claude/launch.json`.

---

### Task 1: The logic, frozen replies and "before" page texts (step 3a)

**Files:**
- Create: `progress.py`
- Test: `tests/test_progress.py`

**Interfaces:**
- Consumes: `players.player_dir(name) -> Path` (reads `players.PLAYERS_DIR` on every call); `rs3_planner.SKILL_NAMES` (29 names), `XP_FOR_99_NORMAL` (13,034,431), `XP_FOR_99_ELITE` (36,073,511); `snapshots.save_snapshot` (file shape `{"username", "fetched_at", "total_xp", "skills"}`).
- Produces (used by Tasks 2 and 3). A *snapshot* is `{"when": datetime, "total_xp": number, "skills": {name: number}}`.
  - `read_snapshots(username) -> (list[snapshot], int)`
  - `max_cape_xp(skills: dict) -> dict | None` with keys `done, needed, to_go, percent`
  - `last_per_day(snapshots) -> list[snapshot]`
  - `max_cape_points(snapshots) -> list[(date, float)]`
  - `skill_points(snapshots, skill: str) -> list[(date, float)]`
  - `since_text(when: datetime, today: date) -> str`
  - `signed_xp(xp: number) -> str`
  - `gain_lines(snapshots, today: date) -> list[dict]` with keys `name, state, start, total, max_cape`; `state` in `"gain" | "none_today" | "only_one"`
  - `skills_moved(snapshots, today: date) -> (snapshot | None, list[(str, float)])`
  - `skill_order(skills: dict) -> list[str]`
  - `default_skill(snapshots, today: date) -> str | None`
  - `skill_gain_since_first(snapshots, skill: str) -> float | None`

(`skill_gain_since_first` is the spec's "gain from the first snapshot to the newest" for the One skill panel's one-day text, given a name.)

- [ ] **Step 1: Check the starting point and the test folder redirect**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git status --short
grep -n "def player_dir" -A 1 players.py
```

Expected: no output from `git status --short`; then `return PLAYERS_DIR / folder_name(name)`. That line reads the module's `PLAYERS_DIR` each time it runs, so the tests' `players.PLAYERS_DIR = Path(tmp)` sends every read and write into the temporary folder. If either is different, stop and report.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_progress.py`:

```python
"""Tests for progress.py: reading snapshots, max cape per day, gains and the skill list.
Made-up snapshots for "Some Player"; the file tests use a temporary folder, never the
real data/players/."""

import datetime
import json
import tempfile
import unittest
from pathlib import Path

import players
from account import read_account, skill_rows
from progress import (
    default_skill, gain_lines, last_per_day, max_cape_points, max_cape_xp, read_snapshots,
    signed_xp, since_text, skill_gain_since_first, skill_order, skill_points, skills_moved,
)
from rs3_planner import SKILL_NAMES
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
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `python3 -m unittest tests.test_progress -v`
Expected: an import error, `ModuleNotFoundError: No module named 'progress'`.

- [ ] **Step 4: Write `progress.py`**

```python
"""
RS3 Planner - progress over time
================================

Works out what the Progress screen shows, from the XP snapshots saved on every
fetch (see snapshots.py): max cape progress per day, XP gained lately, and one
skill's XP per day. Nothing here draws (that's app.py) and nothing fetches:
everything comes from files already on disk.

A "snapshot" in this file is a dict:
  {"when": datetime, "total_xp": 194520179, "skills": {"Mining": 10125809.0, ...}}

Functions that care about "today" take it as an argument, so the tests can use
made-up dates instead of the real clock.
"""

import datetime
import json

from players import player_dir
from rs3_planner import SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL


# ---------------------------------------------------------------------------
# Reading the snapshot files
# ---------------------------------------------------------------------------

def read_snapshots(username):
    """
    Every readable snapshot for this player, oldest first, and how many files
    were skipped because they couldn't be read. Never raises: a broken file is
    skipped and counted, so the screen can say so instead of crashing.
    """
    folder = player_dir(username) / "snapshots"
    try:
        paths = sorted(folder.glob("*.json"))   # a missing folder simply has no files
    except OSError:   # the folder exists but can't be listed
        return [], 0
    snapshots, skipped = [], 0
    for path in paths:
        snapshot = read_one(path)
        if snapshot is None:
            skipped += 1
        else:
            snapshots.append(snapshot)
    snapshots.sort(key=lambda s: s["when"])   # by the time inside, not the file name
    return snapshots, skipped


def is_number(value):
    """True for 12 or 12.5. (Python counts True/False as numbers too; a snapshot never holds them.)"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def read_one(path):
    """One snapshot file as a snapshot dict, or None if it can't be read or isn't in the expected shape."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        when = datetime.datetime.fromisoformat(record["fetched_at"])
        total_xp, skills = record["total_xp"], record["skills"]
    except (OSError, ValueError, KeyError, TypeError):
        # OSError: the file can't be opened. ValueError: not UTF-8, not JSON, or not a date-time.
        # KeyError: a field is missing. TypeError: the JSON isn't an object, or a field has the wrong type.
        return None
    if when.tzinfo is not None:
        return None   # snapshots are saved in local time with no time zone; a mix couldn't be sorted
    if not is_number(total_xp) or not isinstance(skills, dict):
        return None
    if not all(is_number(xp) for xp in skills.values()):
        return None
    # Keep only skills this program knows (a future new skill is ignored, as elsewhere).
    known = {name: xp for name, xp in skills.items() if name in SKILL_NAMES}
    return {"when": when, "total_xp": total_xp, "skills": known}


# ---------------------------------------------------------------------------
# Max cape, and one point per day for the charts
# ---------------------------------------------------------------------------

def target_xp(name):
    """XP for 99 in this skill (Invention uses the steeper elite curve)."""
    return XP_FOR_99_ELITE if name == "Invention" else XP_FOR_99_NORMAL


def max_cape_xp(skills):
    """
    Max cape progress by XP, the same rule as Home's Max cape card: each skill
    counts only up to its 99 amount. Returns {"done", "needed", "to_go", "percent"},
    or None if any of the 29 skills is missing (better no number than a wrong one).
    """
    needed = done = 0
    for name in SKILL_NAMES:
        if name not in skills:
            return None
        needed += target_xp(name)
        done += min(skills[name], target_xp(name))
    return {"done": done, "needed": needed, "to_go": needed - done, "percent": done / needed * 100}


def last_per_day(snapshots):
    """The last snapshot of each day, oldest day first (the charts' points)."""
    by_day = {}
    for snapshot in snapshots:   # oldest first, so a later one of the same day replaces an earlier one
        by_day[snapshot["when"].date()] = snapshot
    return [by_day[day] for day in sorted(by_day)]


def max_cape_points(snapshots):
    """[(date, XP still to go for max cape)], one per day; days we can't work out are left out."""
    points = []
    for snapshot in last_per_day(snapshots):
        cape = max_cape_xp(snapshot["skills"])
        if cape is not None:
            points.append((snapshot["when"].date(), cape["to_go"]))
    return points


def skill_points(snapshots, skill):
    """[(date, XP in this skill)], one per day; days whose snapshot lacks the skill are left out."""
    return [(s["when"].date(), s["skills"][skill]) for s in last_per_day(snapshots) if skill in s["skills"]]


# ---------------------------------------------------------------------------
# Words and numbers for the screen
# ---------------------------------------------------------------------------

def since_text(when, today):
    """'since 08:39' when that was today, else 'since 15:33, 5 Oct'."""
    if when.date() == today:
        return f"since {when:%H:%M}"
    return f"since {when:%H:%M}, {when.day} {when:%b}"


def signed_xp(xp):
    """A whole number with commas and a sign: '+726,291', '−1,500', '+0'."""
    xp = round(xp)
    return f"+{xp:,}" if xp >= 0 else f"−{-xp:,}"


# ---------------------------------------------------------------------------
# XP gained lately
# ---------------------------------------------------------------------------

def gain_between(start, end):
    """(total XP gained, max cape XP gained or None) from one snapshot to a later one."""
    start_cape, end_cape = max_cape_xp(start["skills"]), max_cape_xp(end["skills"])
    cape = None if start_cape is None or end_cape is None else end_cape["done"] - start_cape["done"]
    return end["total_xp"] - start["total_xp"], cape


def today_start(snapshots, today):
    """Where Today starts: the last snapshot from before today, else the first one from today."""
    earlier = [s for s in snapshots if s["when"].date() < today]
    if earlier:
        return earlier[-1]
    return next(s for s in snapshots if s["when"].date() == today)


def week_start(snapshots, today):
    """The last snapshot dated 7 or more days before today, or None if none is that old."""
    cutoff = today - datetime.timedelta(days=7)
    older = [s for s in snapshots if s["when"].date() <= cutoff]
    return older[-1] if older else None


def gain_line(name, start, newest):
    total, cape = gain_between(start, newest)
    return {"name": name, "state": "gain", "start": start, "total": total, "max_cape": cape}


def no_gain_line(name, state):
    return {"name": name, "state": state, "start": None, "total": None, "max_cape": None}


def gain_lines(snapshots, today):
    """
    The Gained panel's lines, in order: Today, Last 7 days, Since first snapshot.
    Each compares the newest snapshot with an older start snapshot. Today is always
    there, as a gain or as "none_today" (no snapshot from today) or "only_one"
    (nothing to compare with). The other two are left out when there's nothing that
    old, nothing to compare, or when they'd start at the same snapshot as the shown
    line above them (so no number is repeated).
    """
    if not snapshots:
        return []
    newest = snapshots[-1]
    lines = []
    shown_start = None   # the start of the nearest shown line above that has one

    if newest["when"].date() != today:
        lines.append(no_gain_line("Today", "none_today"))
    else:
        start = today_start(snapshots, today)
        if start is newest:
            lines.append(no_gain_line("Today", "only_one"))
        else:
            lines.append(gain_line("Today", start, newest))
            shown_start = start

    for name, start in (("Last 7 days", week_start(snapshots, today)),
                        ("Since first snapshot", snapshots[0])):
        if start is None or start is newest or start is shown_start:
            continue
        lines.append(gain_line(name, start, newest))
        shown_start = start
    return lines


def skills_moved(snapshots, today):
    """
    (start snapshot, [(skill, XP gained)]): the skills that went up from the start
    to the newest snapshot, biggest first. The start is the Last 7 days start, else
    the first snapshot. (None, []) when there are fewer than 2 snapshots.
    """
    if len(snapshots) < 2:
        return None, []
    newest = snapshots[-1]
    start = week_start(snapshots, today)
    if start is None or start is newest:
        start = snapshots[0]
    moved = []
    for name in SKILL_NAMES:
        if name in start["skills"] and name in newest["skills"]:
            xp = newest["skills"][name] - start["skills"][name]
            if xp > 0:
                moved.append((name, xp))
    moved.sort(key=lambda pair: pair[1], reverse=True)   # biggest first; ties keep the skill order
    return start, moved


# ---------------------------------------------------------------------------
# The One skill panel
# ---------------------------------------------------------------------------

def skill_order(skills):
    """
    Skill names for the dropdown, in the Skills screen's order: not yet 99 first,
    smallest XP left first; then 99+ skills, most XP first.
    """
    def xp_left(name):
        return max(0, target_xp(name) - skills[name])

    names = [name for name in SKILL_NAMES if name in skills]
    unfinished = sorted((n for n in names if xp_left(n) > 0), key=xp_left)
    done = sorted((n for n in names if xp_left(n) == 0), key=lambda n: skills[n], reverse=True)
    return unfinished + done


def default_skill(snapshots, today):
    """The skill the dropdown opens on: the one that moved most, else the one closest to 99."""
    if not snapshots:
        return None
    _, moved = skills_moved(snapshots, today)
    if moved:
        return moved[0][0]
    order = skill_order(snapshots[-1]["skills"])
    return order[0] if order else None


def skill_gain_since_first(snapshots, skill):
    """XP this skill gained from the first snapshot to the newest, or None if it can't be worked out."""
    if len(snapshots) < 2:
        return None
    first, newest = snapshots[0]["skills"], snapshots[-1]["skills"]
    if skill not in first or skill not in newest:
        return None
    return newest[skill] - first[skill]
```

- [ ] **Step 5: Run the new tests to see them pass**

Run: `python3 -m unittest tests.test_progress -v`
Expected: 37 tests, all `ok`, then `OK`.

- [ ] **Step 6: Run the whole suite**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -4`
Expected: `Ran 138 tests` and `OK`.

- [ ] **Step 7: Check the logic on Hels's real files (read-only)**

This only reads `data/players/hels+glasglo/snapshots/`; nothing is written.

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
python3 - <<'EOF'
import datetime
from progress import gain_lines, max_cape_xp, read_snapshots, skills_moved
snaps, skipped = read_snapshots("Hels Glasglo")
today = datetime.date.today()
print(len(snaps), "snapshots,", skipped, "skipped; newest", snaps[-1]["when"])
cape = max_cape_xp(snaps[-1]["skills"])
print(f"{cape['percent']:.4f}%  {cape['to_go']:,.0f} to go  total {snaps[-1]['total_xp']:,}")
for line in gain_lines(snaps, today):
    print(line["name"], line["state"], line["start"] and line["start"]["when"], line["total"], line["max_cape"])
start, moved = skills_moved(snaps, today)
print("moved since", start["when"], [(name, round(xp)) for name, xp in moved])
EOF
```

Expected, if the newest real snapshot is still 5 Oct 15:33 and today is 6 Oct: `20 snapshots, 0 skipped`; `32.8550%  269,276,641 to go  total 194,520,179`; `Today none_today None None None`; `Since first snapshot gain 2026-10-05 08:39:35 726291 3235.0…` (a value of about 3,235); moved `[('Woodcutting', 723057), ('Fletching', 3235)]`. If the real app has been run today (a newer snapshot exists), the numbers will differ: write down what you see and report it instead.

- [ ] **Step 8: Freeze RuneMetrics replies (one live fetch)**

One read-only call to each RuneMetrics endpoint for Hels. `load_profile`/`load_quests` only download; they don't save a snapshot.

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen
mkdir -p $W/frozen
cd /home/chris-baron/Repos/RS-Planning-Tool
python3 - <<'EOF'
import json
from rs3_planner import load_profile, load_quests
W = "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/frozen"
with open(f"{W}/profile.json", "w", encoding="utf-8") as f:
    json.dump(load_profile("Hels Glasglo"), f)
with open(f"{W}/quests.json", "w", encoding="utf-8") as f:
    json.dump(load_quests("Hels Glasglo"), f)
EOF
ls -la $W/frozen
```

Expected: two non-empty files. If the fetch fails, stop and report.

- [ ] **Step 9: Create `$W/run_frozen.py`** (scratch only, never in the repo)

```python
"""
Run a COPY of RS3 Planner on frozen RuneMetrics replies (scratch only).
    python run_frozen.py <copy folder> <frozen folder> <script> [script arguments...]
The copy's RuneMetrics downloads are replaced by the saved replies, so live
XP changes can't muddy a before/after comparison. The app is moved to port 8091.
"""
import json
import os
import runpy
import sys

copy_dir, frozen_dir, script = sys.argv[1], sys.argv[2], sys.argv[3]
sys.argv = [script] + sys.argv[4:]
os.chdir(copy_dir)
sys.path.insert(0, copy_dir)


def frozen(filename):
    with open(os.path.join(frozen_dir, filename), encoding="utf-8") as f:
        return json.load(f)


import rs3_planner   # patched BEFORE anything imports load_profile / load_quests from it
rs3_planner.load_profile = lambda name: frozen("profile.json")
rs3_planner.load_quests = lambda name: frozen("quests.json")

# The app calls the copies player_cache imported by name; make sure those are the frozen ones.
import player_cache
assert player_cache.load_profile is rs3_planner.load_profile, "player_cache would still fetch live"
assert player_cache.load_quests is rs3_planner.load_quests, "player_cache would still fetch live"

if script == "app.py":
    from nicegui import ui
    real_run = ui.run
    ui.run = lambda *args, **kwargs: real_run(*args, **{**kwargs, "port": 8091})

runpy.run_path(script, run_name="__main__")
```

- [ ] **Step 10: Make the "before" copy**

`git archive` copies tracked files only, so no real player data comes along except what is copied on purpose, into the copy only.

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen
cd /home/chris-baron/Repos/RS-Planning-Tool
mkdir -p $W/before
git archive HEAD | tar -x -C $W/before
mkdir -p $W/before/data/players/hels+glasglo
cp -r data/players/hels+glasglo/answers.json data/players/hels+glasglo/last_goal data/players/hels+glasglo/snapshots $W/before/data/players/hels+glasglo/
echo "Hels Glasglo" > $W/before/data/players/current.txt
ls $W/before/data/players/hels+glasglo
```

Expected: `answers.json  last_goal  snapshots`. If `cp` complains a file is missing, stop and report.

- [ ] **Step 11: Save the "before" page texts**

Add this entry inside `"configurations"` in the git-excluded `.claude/launch.json` (keep `rs3-planner-gui`):

```json
{
  "name": "rs3-frozen",
  "runtimeExecutable": "/home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python",
  "runtimeArgs": [
    "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/run_frozen.py",
    "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/before",
    "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/frozen",
    "app.py"
  ],
  "port": 8091
}
```

Start it with `preview_start {name: "rs3-frozen"}`. For each page, navigate, read the text with `javascript_tool`: `document.querySelector('main').innerText`, and save it with the Write tool:
- `http://localhost:8091/` → `$W/before_home.txt`
- `http://localhost:8091/skills` → `$W/before_skills.txt`
- `http://localhost:8091/quests` → `$W/before_quests.txt`
- `http://localhost:8091/plan?hours=5&session=afk&minutes=2` → `$W/before_afk.txt`

Check `preview_logs` shows exactly one "Fetching Hels Glasglo from RuneMetrics" (it reads the frozen files) and no traceback. Stop the preview (`preview_stop`).

- [ ] **Step 12: Record the frozen copy's sanity values**

The copy's start-up "fetch" wrote a snapshot dated today into the **copy's** snapshots folder, so the copy now has two days.

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen
cd /home/chris-baron/Repos/RS-Planning-Tool
python3 - <<'EOF' | tee $W/sanity.txt
import datetime
from pathlib import Path
import players
players.PLAYERS_DIR = Path("/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/before/data/players")
from progress import default_skill, gain_lines, max_cape_points, max_cape_xp, read_snapshots, skills_moved
snaps, skipped = read_snapshots("Hels Glasglo")
today = datetime.date.today()
print(len(snaps), "snapshots,", skipped, "skipped; newest", snaps[-1]["when"])
cape = max_cape_xp(snaps[-1]["skills"])
print(f"{cape['percent']:.1f}%  {cape['to_go']:,.0f} XP to go  total {snaps[-1]['total_xp']:,}")
for line in gain_lines(snaps, today):
    print(line["name"], line["state"], line["start"] and line["start"]["when"], line["total"], line["max_cape"])
start, moved = skills_moved(snaps, today)
print("moved since", start["when"], [(name, round(xp)) for name, xp in moved])
print("default skill", default_skill(snaps, today))
print("max cape points", [(str(day), round(v)) for day, v in max_cape_points(snaps)])
EOF
```

Expected: 21 snapshots (20 real + the copy's new one), 0 skipped; two max cape points (5 Oct and today). Check the `%` and `to go` equal the "Max cape" card in `$W/before_home.txt`. These numbers are what Tasks 2 and 3 check the screen against.

- [ ] **Step 13: Commit and stop**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git add progress.py tests/test_progress.py
git commit -F - <<'EOF'
progress.py: the Progress screen's numbers from saved snapshots

read_snapshots (skips and counts broken files), max_cape_xp (capped at 99),
one point per day, gain lines (Today / Last 7 days / Since first snapshot),
skills that moved, the skill dropdown's order and default. 37 tests.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git status --short
```

Expected: a clean `git status`. Stop: explain to Chris what was built, show the sanity values, and wait.

---

### Task 2: The Progress screen with numbers (step 3b)

**Files:**
- Modify: `app.py` (docstring list; imports; `NAV_TARGETS`; new "Screen: Progress" section)

**Interfaces:**
- Consumes: from Task 1, `read_snapshots`, `max_cape_xp`, `gain_lines`, `skills_moved`, `since_text`, `signed_xp`; existing `current_entry()`, `panel()`, `bottom_nav()`, `NO_VALUE`, `RedirectResponse`.
- Produces (used by Task 3), all in `app.py`:
  - `progress_page()` at `/progress`
  - `max_cape_panel(snapshots) -> None` (Task 3 adds the chart to it)
  - `gained_panel(snapshots, today) -> None`
  - `snapshot_count_text(snapshots) -> str`, `skipped_text(skipped) -> str`

`app.py` can't be unit-tested (it starts NiceGUI on import), so this task is proved by page text on frozen data.

- [ ] **Step 1: Update the docstring and imports**

In the module docstring's list, after the `snapshots.py` line, add:

```
  progress.py      the Progress screen's numbers (from the saved snapshots)
```

After the `from player_cache import …` line, add:

```python
from progress import gain_lines, max_cape_xp, read_snapshots, signed_xp, since_text, skills_moved
```

- [ ] **Step 2: Turn on the nav button**

Replace:

```python
NAV_TARGETS = {"Home": "/", "Skills": "/skills", "Quests": "/quests"}
```

with:

```python
NAV_TARGETS = {"Home": "/", "Skills": "/skills", "Quests": "/quests", "Progress": "/progress"}
```

(The "coming soon" fallback in `bottom_nav` stays, for any future button.)

- [ ] **Step 3: Add the Progress screen**

Insert this new section just before the `# Screens 3a and 3b: the plan` section header:

```python
# ---------------------------------------------------------------------------
# Screen: Progress
# ---------------------------------------------------------------------------

@ui.page("/progress", title="Progress - RS3 Planner")
def progress_page():
    entry = current_entry()
    if entry is None:   # nobody chosen yet: go and pick a player
        return RedirectResponse("/player")

    # Only the saved snapshot files (see progress.py): this screen never fetches,
    # so it still works when RuneMetrics is down. Read fresh on every visit.
    snapshots, skipped = read_snapshots(CURRENT["name"])
    today = datetime.date.today()

    with ui.column().classes("page"):
        ui.label("Progress").classes("title")
        ui.label(entry["name"]).classes("subtitle")
        if snapshots:
            ui.label(snapshot_count_text(snapshots)).classes("muted")
        if skipped:
            ui.label(skipped_text(skipped)).classes("muted small")

        if not snapshots:
            with panel():
                ui.label("No snapshots saved yet").classes("heading")
                ui.label("One is saved each time stats are fetched (at start-up and on Refresh).").classes("muted")
            bottom_nav("Progress")
            return

        max_cape_panel(snapshots)
        gained_panel(snapshots, today)

    bottom_nav("Progress")


def snapshot_count_text(snapshots):
    """'20 snapshots · last 15:33, 5 Oct'."""
    newest = snapshots[-1]["when"]
    count = f"{len(snapshots)} snapshot" + ("" if len(snapshots) == 1 else "s")
    return f"{count} · last {newest:%H:%M}, {newest.day} {newest:%b}"


def skipped_text(skipped):
    if skipped == 1:
        return "1 snapshot file couldn't be read and was skipped."
    return f"{skipped} snapshot files couldn't be read and were skipped."


def max_cape_panel(snapshots):
    """Max cape now, from the newest snapshot (the same rule as Home's card)."""
    newest = snapshots[-1]
    cape = max_cape_xp(newest["skills"])   # None if the snapshot lacks a skill
    with panel():
        ui.label("Max cape").classes("label")
        ui.label(f"{cape['percent']:.1f}%" if cape else NO_VALUE).classes("big-number")
        ui.label(f"{cape['to_go']:,.0f} XP to go" if cape else f"{NO_VALUE} XP to go").classes("heading")
        ui.label(f"Total XP {newest['total_xp']:,.0f}").classes("muted")


def gained_panel(snapshots, today):
    """XP gained Today / Last 7 days / Since first snapshot, then the skills that moved."""
    with panel():
        ui.label("Gained").classes("label green")
        for line in gain_lines(snapshots, today):
            if line["state"] == "none_today":
                ui.label(f"{line['name']}: no snapshot yet").classes("muted")
                continue
            if line["state"] == "only_one":
                ui.label(f"{line['name']}: only one snapshot so far").classes("muted")
                continue
            cape = NO_VALUE if line["max_cape"] is None else signed_xp(line["max_cape"])
            ui.label(line["name"]).classes("heading")
            ui.label(f"{signed_xp(line['total'])} XP · {cape} toward max cape · "
                     f"{since_text(line['start']['when'], today)}").classes("muted")

        start, moved = skills_moved(snapshots, today)
        if start is None:   # only one snapshot: nothing to compare
            return
        since = since_text(start["when"], today)
        ui.label(f"Skills that moved {since}").classes("label")
        if not moved:
            ui.label(f"No skill has moved {since}.").classes("muted small")
        for skill, xp in moved:
            with ui.row().classes("row-line"):
                ui.label(skill).classes("heading")
                ui.label(f"{signed_xp(xp)} XP").classes("muted")
```

(Each Gained line is the spec's one line split in two for phone width: the name as a heading, then "+726,291 XP · +3,235 toward max cape · since 08:39".)

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -4`
Expected: `Ran 138 tests`, `OK`.

- [ ] **Step 5: Make the "after" copy**

`git ls-files` lists tracked files; `tar` copies their current (edited) contents.

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen
cd /home/chris-baron/Repos/RS-Planning-Tool
rm -rf $W/after && mkdir -p $W/after
git ls-files -z | xargs -0 tar -cf - | tar -x -C $W/after
mkdir -p $W/after/data/players/hels+glasglo
cp -r data/players/hels+glasglo/answers.json data/players/hels+glasglo/last_goal data/players/hels+glasglo/snapshots $W/after/data/players/hels+glasglo/
echo "Hels Glasglo" > $W/after/data/players/current.txt
grep -c "progress_page" $W/after/app.py
```

Expected: `1`. In `.claude/launch.json`, change the `rs3-frozen` argument ending in `/before` to end in `/after`.

- [ ] **Step 6: Prove the other screens didn't change**

Start `preview_start {name: "rs3-frozen"}`. Save `main` text (as in Task 1 Step 11) of `/`, `/skills`, `/quests`, `/plan?hours=5&session=afk&minutes=2` to `$W/after_home.txt`, `after_skills.txt`, `after_quests.txt`, `after_afk.txt`. Then:

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen
for page in home skills quests afk; do
  diff <(grep -v "Stats updated" $W/before_$page.txt) <(grep -v "Stats updated" $W/after_$page.txt) && echo "$page: no difference"
done
```

Expected: four "no difference" lines. ("Stats updated HH:MM" is the fetch time, which differs between the two runs; nothing else may differ. The bottom nav text is the same because "Progress" was always shown.) Any difference: stop and report.

- [ ] **Step 7: Check the Progress screen against the sanity values**

Click **Progress** in the bottom nav (it must open `/progress`, not say "coming soon"). Read the page text and compare with `$W/sanity.txt`:
- "21 snapshots · last HH:MM, D Mon" (the copy's new snapshot).
- Max cape % and "XP to go" exactly equal Home's Max cape card (`$W/after_home.txt`); "Total XP" equals the frozen profile's total.
- Gained lines and "Skills that moved since …" match `sanity.txt` (rounded to whole numbers, with signs).
- `read_console_messages {onlyErrors: true}`: nothing.

- [ ] **Step 8: Check the thin-data states (in the copy only)**

The page reads files fresh on each visit, so these work without restarting. All moves are inside `$W/after`.

```bash
S=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/after/data/players/hels+glasglo
mv $S/snapshots $S/snapshots_all && mkdir $S/snapshots
```

Reload `/progress` → "No snapshots saved yet" panel; no Max cape or Gained panel.

```bash
S=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/after/data/players/hels+glasglo
cp $S/snapshots_all/2026-10-05_0839.json $S/snapshots/
```

Reload → "1 snapshot · last 08:39, 5 Oct"; "Today: no snapshot yet"; no other Gained lines; no "Skills that moved".

```bash
S=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/after/data/players/hels+glasglo
cp $S/snapshots_all/2026-10-05_*.json $S/snapshots/
printf '{oops' > $S/snapshots/broken.json
```

Reload → "20 snapshots · last 15:33, 5 Oct"; "1 snapshot file couldn't be read and was skipped."; "Today: no snapshot yet"; "Since first snapshot" +726,291 XP · +3,235 toward max cape · since 08:39, 5 Oct; Woodcutting +723,057, Fletching +3,235.

Put everything back:

```bash
S=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/after/data/players/hels+glasglo
rm -r $S/snapshots && mv $S/snapshots_all $S/snapshots
```

Stop the preview (`preview_stop`).

- [ ] **Step 9: Commit and stop**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
git add app.py
git commit -F - <<'EOF'
Progress screen: max cape now, XP gained lately, skills that moved

The Progress button opens /progress (no more "coming soon"). It reads only
the saved snapshot files, never fetches; handles no snapshots, one snapshot,
and unreadable files. Other screens unchanged (page text diffed on frozen data).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git status --short
```

Expected: a clean `git status`. Stop: explain to Chris, show a screenshot of `/progress` at phone width, and wait.

---

### Task 3: Charts, the One skill panel, CSS and README (step 3c)

**Files:**
- Modify: `app.py` (imports; chart constants; `line_chart`, `numbers_toggle`, `one_skill_panel`; `max_cape_panel`; `progress_page`)
- Modify: `static/app.css`
- Modify: `README.md`

**Interfaces:**
- Consumes: from Task 1, `max_cape_points`, `skill_points`, `skill_order`, `default_skill`, `skill_gain_since_first`; from Task 2, `progress_page`, `max_cape_panel`; existing `skill_rows(account)` (rows with `name`, `level_text`), `button()`.
- Produces: `line_chart(points, value_word) -> ui.echart`, `numbers_toggle(points, value_word) -> None`, `one_skill_panel(entry, snapshots, today) -> None`.

- [ ] **Step 1: Extend the import**

Replace the Task 2 `from progress import …` line with:

```python
from progress import (
    default_skill, gain_lines, max_cape_points, max_cape_xp, read_snapshots, signed_xp, since_text,
    skill_gain_since_first, skill_order, skill_points, skills_moved,
)
```

- [ ] **Step 2: Add the chart helpers**

Insert just above `def max_cape_panel(snapshots):`:

```python
# Chart colours: the same values as static/app.css. ECharts draws on a canvas,
# which can't read CSS, so they are written out here.
CHART_PANEL = "#16241B"     # --panel: the dots' ring and the tooltip background
CHART_GRID = "#2E4636"      # --frame-outer: gridlines and the date axis
CHART_TEXT = "#B9C3B2"      # --muted: axis labels
CHART_TIP_TEXT = "#F0E8D6"  # --parchment: tooltip text
CHART_LINE = "#A8DCEB"      # --glacial: the line and its dots
CHART_FONT = "Alegreya, Georgia, serif"
ONE_DAY_MS = 24 * 60 * 60 * 1000   # one day in milliseconds, how ECharts measures time

# Small pieces of browser code (JavaScript) for ECharts. NiceGUI runs a settings
# value as code when its key starts with ":" (see ui.echart's documentation).
MONTHS_JS = "['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']"
# Date axis labels: "5 Oct".
DATE_LABEL_JS = f"value => {{ const d = new Date(value); return d.getDate() + ' ' + {MONTHS_JS}[d.getMonth()]; }}"
# Value axis labels: whole numbers with commas, "269,276,000".
NUMBER_LABEL_JS = "value => Math.round(value).toLocaleString('en-GB')"


def tooltip_js(value_word):
    """Hover text, '5 Oct · 269,276,641 to go'. value_word is our own fixed text ('to go' or 'XP')."""
    return ("params => { const p = params[0]; const d = new Date(p.value[0]); "
            f"return d.getDate() + ' ' + {MONTHS_JS}[d.getMonth()] + ' · ' + "
            f"Math.round(p.value[1]).toLocaleString('en-GB') + ' {value_word}'; }}")


def line_chart(points, value_word):
    """
    A one-line chart of [(date, value)] in the app's colours (ui.echart: ECharts,
    bundled with NiceGUI, so it works offline). One line, so no legend: the panel's
    label says what it is. The date axis keeps real spacing, so a week without
    snapshots shows as a gap. The value axis zooms to the data, or a small change
    on 269M would be invisible.
    """
    # Each date at local noon: a plain "2026-10-05" could be read as midnight in
    # another time zone and land on the day before.
    data = [[f"{day:%Y-%m-%d}T12:00:00", value] for day, value in points]
    options = {
        "backgroundColor": "transparent",   # the panel shows through
        "animation": False,
        "textStyle": {"fontFamily": CHART_FONT, "color": CHART_TEXT},
        "grid": {"left": 8, "right": 16, "top": 16, "bottom": 8, "containLabel": True},
        "xAxis": {
            "type": "time",
            "minInterval": ONE_DAY_MS,   # never two labels on the same day
            "axisLine": {"lineStyle": {"color": CHART_GRID}},
            "axisTick": {"show": False},
            "splitLine": {"show": False},
            "axisLabel": {"color": CHART_TEXT, "hideOverlap": True, ":formatter": DATE_LABEL_JS},
        },
        "yAxis": {
            "type": "value",
            "scale": True,   # zoom to the data instead of starting at 0
            "splitLine": {"lineStyle": {"color": CHART_GRID, "width": 1, "type": "solid"}},
            "axisLabel": {"color": CHART_TEXT, ":formatter": NUMBER_LABEL_JS},
        },
        "tooltip": {
            "trigger": "axis",
            "backgroundColor": CHART_PANEL,
            "borderColor": CHART_GRID,
            "textStyle": {"color": CHART_TIP_TEXT, "fontFamily": CHART_FONT},
            "axisPointer": {"type": "line", "lineStyle": {"color": CHART_GRID}},
            ":formatter": tooltip_js(value_word),
        },
        "series": [{
            "type": "line",
            "data": data,
            "symbol": "circle",
            "symbolSize": 8,
            "clip": False,   # dots at the very ends stay whole
            "lineStyle": {"color": CHART_LINE, "width": 2},
            "itemStyle": {"color": CHART_LINE, "borderColor": CHART_PANEL, "borderWidth": 2},
        }],
    }
    return ui.echart(options).classes("chart")


def numbers_toggle(points, value_word):
    """'Show the numbers': the chart's values as a list, newest first (nothing is fetched)."""
    show_text = "Show the numbers"
    toggle = button(show_text).props("unelevated no-caps").classes("btn-quiet")
    # Drawn now but hidden; the button shows or hides it.
    numbers = ui.column().classes("w-full gap-0")
    with numbers:
        for day, value in reversed(points):
            ui.label(f"{day.day} {day:%b} · {value:,.0f} {value_word}").classes("muted small")
    numbers.set_visibility(False)

    def flip():
        showing = not numbers.visible
        numbers.set_visibility(showing)
        toggle.set_text("Hide the numbers" if showing else show_text)

    toggle.on_click(flip)
```

- [ ] **Step 3: Add the chart to the Max cape panel**

Replace the whole `max_cape_panel` function with:

```python
def max_cape_panel(snapshots):
    """Max cape now (the same rule as Home's card), and XP still to go per day."""
    newest = snapshots[-1]
    cape = max_cape_xp(newest["skills"])   # None if the snapshot lacks a skill
    with panel():
        ui.label("Max cape").classes("label")
        ui.label(f"{cape['percent']:.1f}%" if cape else NO_VALUE).classes("big-number")
        ui.label(f"{cape['to_go']:,.0f} XP to go" if cape else f"{NO_VALUE} XP to go").classes("heading")
        ui.label(f"Total XP {newest['total_xp']:,.0f}").classes("muted")
        points = max_cape_points(snapshots)   # the last snapshot of each day
        if len(points) >= 2:   # a line needs two points
            line_chart(points, "to go")
            numbers_toggle(points, "to go")
        else:
            ui.label("A chart appears once you have snapshots from 2 different days.").classes("muted small")
```

- [ ] **Step 4: Add the One skill panel**

Insert just after `gained_panel`:

```python
def one_skill_panel(entry, snapshots, today):
    """A dropdown of skills and the chosen skill's XP per day. Choosing redraws only this panel."""
    newest = snapshots[-1]["skills"]
    names = skill_order(newest)   # closest to 99 first, like the Skills screen
    if not names:
        return
    # Levels come from the live stats (skill_rows knows Invention past 99 is "99+");
    # snapshots don't store levels. With no live stats, the level is left off.
    levels = {row["name"]: row["level_text"] for row in skill_rows(entry["account"])} if entry["account"] else {}
    choice = {"skill": default_skill(snapshots, today)}

    @ui.refreshable
    def skill_view():
        skill = choice["skill"]
        name_text = f"{skill} {levels[skill]}" if skill in levels else skill
        ui.label(f"{name_text} · {newest[skill]:,.0f} XP").classes("heading")
        points = skill_points(snapshots, skill)
        if len(points) >= 2:
            line_chart(points, "XP")
            numbers_toggle(points, "XP")
        elif len(snapshots) < 2:
            ui.label("Only one snapshot so far.").classes("muted")
        else:
            gain = skill_gain_since_first(snapshots, skill)
            gain_text = NO_VALUE if gain is None else signed_xp(gain)
            ui.label(f"{gain_text} XP {since_text(snapshots[0]['when'], today)}").classes("muted")

    def pick(event):
        choice["skill"] = event.value
        skill_view.refresh()

    with panel():
        ui.label("One skill").classes("label")
        ui.select(names, value=choice["skill"], on_change=pick).props(
            'outlined dark popup-content-class="skill-menu"').classes("skill-select")
        skill_view()
```

In `progress_page`, after `gained_panel(snapshots, today)`, add:

```python
        one_skill_panel(entry, snapshots, today)
```

- [ ] **Step 5: Styles**

In `static/app.css`, after the `.name-input …` rules, add:

```css
/* Progress charts: the height includes the axis labels, so no scrollbar appears inside a panel. */
.chart { width: 100%; height: 220px; }

/* The skill dropdown on Progress: the same dark box as the name input on Choose player. */
.skill-select { width: 100%; }
.skill-select .q-field__control { background: var(--forest); border-radius: 10px; min-height: 48px; color: var(--glacial) !important; }
.skill-select .q-field__native { color: var(--parchment); font-family: "Alegreya", Georgia, serif; font-size: 17px; }
.skill-select .q-field__control:before { border-color: var(--frame-outer) !important; }
/* Its list of skills when opened. */
.skill-menu { background: var(--panel); color: var(--parchment); border: 1px solid var(--frame-outer); }
.skill-menu .q-item { min-height: 44px; font-family: "Alegreya", Georgia, serif; }
```

- [ ] **Step 6: Run the tests**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -4`
Expected: `Ran 138 tests`, `OK`.

- [ ] **Step 7: Refresh the "after" copy and check the screen**

Repeat Task 2 Step 5 (it rebuilds `$W/after` from the current files). Start `preview_start {name: "rs3-frozen"}`, open `/progress`, and check:
- **Offline:** `read_network_requests` lists only `localhost:8091` / `127.0.0.1` addresses (the ECharts file comes from `/_nicegui/…`); nothing else.
- **Console:** `read_console_messages {onlyErrors: true}` is empty.
- **Max cape chart:** two dots (5 Oct and today). Hover each dot (`computer` hover): the tooltip reads "5 Oct · 269,276,641 to go" for the first and today's date with the value from `sanity.txt` for the second. The date axis labels name the same two days.
- **Show the numbers** opens the same two values, newest first; the button then reads "Hide the numbers"; pressing it again hides them.
- **One skill:** the dropdown opens on `default skill` from `sanity.txt`; its list starts with the skill closest to 99 (Mining for Hels); choosing Woodcutting redraws with "Woodcutting 99 · … XP" and its chart; nothing is fetched (`preview_logs` shows still only one "Fetching" line).
- **Other screens:** repeat the Task 2 Step 6 diff (save the four `after_*.txt` again first). Four "no difference" lines.

- [ ] **Step 8: Check the one-day state and no live stats**

One day: with the preview still running, do the "20 files of 5 Oct + broken.json" setup from Task 2 Step 8. Reload `/progress` → no charts; "A chart appears once you have snapshots from 2 different days."; One skill: "+723,057 XP since 08:39, 5 Oct" for Woodcutting. Put the folder back as in Task 2 Step 8.

No live stats: stop the preview; hide the frozen profile so the copy's start-up fetch fails:

```bash
F=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/frozen
mv $F/profile.json $F/profile.hidden
```

Start the preview again and open `/progress`: the screen still shows all panels from the files, and the One skill line has no level ("Woodcutting · … XP" style). Home shows "No stats loaded" as before. Stop the preview and restore:

```bash
F=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen/frozen
mv $F/profile.hidden $F/profile.json
```

- [ ] **Step 9: Phone width and colour checks**

Start the preview again. `resize_window {preset: "mobile"}` (375px), reload `/progress`: no sideways scrolling; axis labels not cut off; no scrollbar inside a chart; the dropdown and buttons at least 44px tall. Take a screenshot of each panel (scroll between them). Then `resize_window {preset: "desktop"}`.

Colour check (the dataviz skill's validator; one line colour against the panel in dark mode):

```bash
node /tmp/claude-1000/bundled-skills/2.1.288/35e803706102463f0fa379168067433f/dataviz/scripts/validate_palette.js "#A8DCEB" --mode dark --surface "#16241B"
```

Expected: contrast PASS (the line against the panel). Checks about pairs of colours don't apply to a single line. If anything FAILs, stop and report. Stop the preview.

- [ ] **Step 10: README**

In `README.md`:

1. In "Using the app", after item 7 (Quests), add:

```markdown
8. **Progress** (bottom bar): how you're closing on max cape, from the stats
   snapshots saved each time stats are fetched. It shows your max cape % and the
   XP still to go (with a chart, one point per day, once you have two days),
   **Gained** today, over the last 7 days and since your first snapshot (with the
   skills that moved), and **One skill**: pick any skill to see its XP per day.
   **Show the numbers** lists the values behind a chart. Progress never fetches;
   it works from the saved files.
```

2. In "Good to know", replace:

```markdown
- Your answers, chosen goal and stat snapshots stay on your computer, in
  `data/players/<player>/` (never uploaded; kept out of git). Snapshots are kept
  for a future Progress screen.
```

with:

```markdown
- Your answers, chosen goal and stat snapshots stay on your computer, in
  `data/players/<player>/` (never uploaded; kept out of git). The snapshots are
  what the Progress screen charts.
```

3. In the intro list near the top, after the **Quests** bullet, add:

```markdown
- **Progress:** max cape progress over time, XP gained lately, and any skill's
  XP per day.
```

If any of these exact lines differs in the file, stop and report rather than guess.

- [ ] **Step 11: Commit**

```bash
cd /home/chris-baron/Repos/RS-Planning-Tool
python3 -m unittest discover -s tests 2>&1 | tail -2
git add app.py static/app.css README.md
git commit -F - <<'EOF'
Progress charts: max cape to go and one skill, per day (ECharts, offline)

line_chart draws one glacial line on a date axis that keeps real spacing,
with hover text and a "Show the numbers" list. The One skill dropdown opens
on the skill that moved most. Checked on frozen data: offline, phone width,
no live stats, one-day state; other screens unchanged. README: Progress.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git status --short
```

Expected: `OK`, then a clean `git status`.

- [ ] **Step 12: Clean up the scratch copies and stop**

The copies hold copies of Hels's answers and snapshots, so they go:

```bash
rm -rf /home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/progress-screen
ls /home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/
```

Expected: only `.gitignore` is left (`ls -a` shows it). Remove the `rs3-frozen` entry from `.claude/launch.json` (leave `rs3-planner-gui`). Confirm `data/players/hels+glasglo/` was never changed by this plan (`ls data/players/hels+glasglo/snapshots | wc -l` is the same as at the start, unless Chris ran the real app meanwhile).

Stop: explain to Chris what changed, show the phone-width screenshots, and ask before pushing.
