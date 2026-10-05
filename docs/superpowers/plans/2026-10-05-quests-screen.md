# Quests Screen and Big Goal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The bottom nav's Quests button opens a screen for the player's big goal (tonight's quest, skills short, the chain with statuses, quests to start now, quests in progress), and the big goal is chosen in the app, saved per player and shared with the terminal.

**Architecture:** New pure functions in `quest_path.py` do all the deciding (which goal, chain rows, useful/eligible/started quests); `app.py` only draws. The goal is stored in the existing per-player `last_goal` file, so the app and the terminal share it. The Active plan's quest panels become helpers shared with the new Quests screen.

**Tech Stack:** Python 3.14 standard library (terminal scripts, tests via `unittest`), NiceGUI 3.17.1 in `.venv/` (browser app).

**Spec:** `docs/superpowers/specs/2026-10-05-quests-screen-design.md`

## Global Constraints

- Public data only (RuneMetrics + RuneScape Wiki). Nothing may touch the game client. No new RuneMetrics calls in the app: every screen uses the data already loaded.
- Never show made-up numbers: a missing value shows "—" (`NO_VALUE`) or the line is hidden.
- Server stays on `HOST = "127.0.0.1"`.
- Look: existing colours/classes in `static/app.css` only; one column, max 480px, tap targets ≥44px, ~10px corners, no gradients, no emoji. Buttons always via the `button()` helper (`color=None`).
- No other players' names in the repo (docs, tests, commits). Tests use "Some Player" and made-up quest names.
- Code is simple and commented in plain words, matching the existing files.
- Tests: `python3 -m unittest discover -s tests -v` from the project folder. Tests never touch the network or the real `data/players/`.
- Data check after any data edit: `python3 check_methods.py`.
- Stop and wait for Chris after Task 1 (step 2a), Task 2 (step 2b) and Task 3 (step 2c). Commit after each task; never push without asking. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- If any step errors, stop that task, explain (what failed, the error in plain words, likely cause, what's done, what's left, the proper fix) and wait for Chris.

## Review Focus

1. **A chain quest RuneMetrics doesn't list** (wiki title differs from RuneMetrics' title) → the quest still appears, difficulty shows "—" (not "?"), status is RuneMetrics' "not eligible" reason, no crash. Pinned in Task 1 (`chain_rows` gives `"?"` and the reason) and Task 3 (`difficulty_text` maps `"?"` → "—").
2. **`last_goal` names an unlock no longer in `unlocks.json`** (renamed or removed) → falls back to the first unlock. Pinned in Task 1 (`goal_for` test).
3. **Two players with different goals** → each sees their own goal after Switch player. Pinned in Task 1 (`goal_for` per-player test).
4. **Goal changed in the terminal while the app runs** → the next page load shows it (no stale copy in memory). Pinned in Task 3 browser check (pages call `goal_for` on every load).
5. **A player with nothing eligible, nothing started and no other requirements** → those panels hide or say so; no crash. Pinned in Task 1 (empty-account tests) and Task 3 (`if not ...: return` in the panel helpers).

## File map

| File | Change | Responsibility |
|---|---|---|
| `quest_path.py` | modify | New: `goal_for`, `quest_rank`, `chain_rows`, `other_requirements`, `useful_to_start`, `eligible_by_difficulty`, `started_quests`; repairs to `read_last_goal` / `save_last_goal`; `ranked_doable` and `print_quest_path` reuse the new pieces |
| `tests/test_quest_path.py` | modify | Tests for all of the above |
| `data/unlocks.json` | modify | Two `why_it_matters` lines made neutral |
| `app.py` | modify | `current_goal()`, Home card, shared panel helpers, `/quests`, `/quests/goal`, nav |
| `static/app.css` | modify | Two-line goal buttons |
| `README.md` | modify | Quests screen and choosing the goal |

## Scratch setup used by the proofs

`SCR` = `/tmp/claude-1000/-home-chris-baron-Repos-RS-Planning-Tool/9722696a-efe4-4596-a97a-65d3ffd8c745/scratchpad`
(the session scratch folder, outside the project). `BASE` = `5bd5281`, the commit before any code change
(its code is identical to the pushed `85be203`). Copies made with `git archive` contain only tracked files,
so no real player data comes along unless a step copies it on purpose, into the scratch copy only.

---

### Task 1: Quest logic, repairs and wording (step 2a)

**Files:**
- Modify: `quest_path.py`
- Modify: `data/unlocks.json` (two `why_it_matters` strings)
- Test: `tests/test_quest_path.py`

**Interfaces:**
- Consumes: existing `full_chain(title, quests)`, `quest_state(title, quests, account)`, `unlock_count(title, unlocks, quests)`, `length_rank(length)`, `difficulty_name(title, account)`, `players.player_dir(name)`, `rs3_planner.available_quests(quest_data)`, `rs3_planner.DIFFICULTY_NAMES`.
- Produces (used by Tasks 2 and 3):
  - `goal_for(unlocks, username) -> dict` (an unlock)
  - `save_last_goal(username, name) -> bool`
  - `quest_rank(title, unlocks, quests, account) -> tuple`
  - `chain_rows(goal, quests, account) -> list[dict]` with keys `title, state, reasons, difficulty, length`
  - `other_requirements(chain, quests, account) -> list[tuple[str, str]]` as `(text, title)`
  - `useful_to_start(unlocks, quests, account) -> list[str]`
  - `eligible_by_difficulty(account) -> list[tuple[str, list[str]]]`
  - `started_quests(account) -> list[str]`

- [ ] **Step 1: Freeze RuneMetrics replies and save the terminal "before" output**

The quests reply for Hels is already saved as `$SCR/hels_quests_2026-10-05.json`. Fetch one profile reply (one read-only RuneMetrics call) and make a clean copy of the project at `BASE`:

```bash
SCR=/tmp/claude-1000/-home-chris-baron-Repos-RS-Planning-Tool/9722696a-efe4-4596-a97a-65d3ffd8c745/scratchpad
mkdir -p $SCR/frozen $SCR/before
mv $SCR/hels_quests_2026-10-05.json $SCR/frozen/quests.json
cd ~/Repos/RS-Planning-Tool
python3 -c "import json; from rs3_planner import load_profile; json.dump(load_profile('Hels Glasglo'), open('$SCR/frozen/profile.json', 'w'))"
git archive 5bd5281 | tar -x -C $SCR/before
mkdir -p $SCR/before/data/players/hels+glasglo
cp data/players/hels+glasglo/answers.json $SCR/before/data/players/hels+glasglo/
```

Create `$SCR/run_frozen.py` (scratch only, never in the repo):

```python
"""
Run a COPY of RS3 Planner on frozen RuneMetrics replies (scratch only).
    python run_frozen.py <copy folder> <frozen folder> <script> [script arguments...]
The script's RuneMetrics downloads are replaced by the saved replies, so live
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

import rs3_planner   # patched BEFORE the script imports load_profile / load_quests from it
rs3_planner.load_profile = lambda name: json.load(open(os.path.join(frozen_dir, "profile.json")))
rs3_planner.load_quests = lambda name: json.load(open(os.path.join(frozen_dir, "quests.json")))

if script == "app.py":
    from nicegui import ui
    real_run = ui.run
    ui.run = lambda *args, **kwargs: real_run(*args, **{**kwargs, "port": 8091})

runpy.run_path(script, run_name="__main__")
```

Save the terminal "before":

```bash
python3 $SCR/run_frozen.py $SCR/before $SCR/frozen plan_session.py --user "Hels Glasglo" --hours 5 --minutes 2 --session active --goal 1 > $SCR/terminal_before.txt
tail -30 $SCR/terminal_before.txt
```

Expected: the session plan followed by "QUEST PATH - big goal: Prifddinas … Progress: 1 of 15 quests done" and "TONIGHT'S QUEST". No traceback.

- [ ] **Step 2: Confirm the tests' folder redirect reaches the goal file code**

`read_last_goal`/`save_last_goal` call `players.player_dir`, which reads `players.PLAYERS_DIR` at call time:

```bash
grep -n "def player_dir" -A 1 players.py
grep -n "player_dir" quest_path.py
```

Expected: `return PLAYERS_DIR / folder_name(name)` and quest_path using `player_dir(username)` (not a saved path). So setting `players.PLAYERS_DIR` in a test redirects every goal file. If this is not what you see, stop and report.

- [ ] **Step 3: Write the failing tests**

Replace `tests/test_quest_path.py` with:

```python
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
```

- [ ] **Step 4: Run the tests to see them fail**

Run: `python3 -m unittest tests.test_quest_path -v`
Expected: `ImportError: cannot import name 'chain_rows' from 'quest_path'` (the new functions don't exist yet).

- [ ] **Step 5: Repair the goal-file functions and add `goal_for`**

In `quest_path.py`, replace `read_last_goal` and `save_last_goal` with:

```python
def read_last_goal(username):
    """The big goal this player picked last time, or None."""
    try:
        return (player_dir(username) / "last_goal").read_text(encoding="utf-8").strip() or None
    except (OSError, ValueError):
        # Missing or unreadable (OSError), or not valid text (UnicodeDecodeError is a
        # ValueError): treat it as "nothing saved" rather than crash.
        return None


def save_last_goal(username, name):
    """Remember the big goal. Returns True if saved, False if not.
    (The terminal ignores the answer; the app tells you when saving failed.)"""
    try:
        folder = player_dir(username)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "last_goal").write_text(name + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def goal_for(unlocks, username):
    """This player's big goal: their saved choice, else the first unlock (as the terminal menu does)."""
    last = read_last_goal(username)
    for unlock in unlocks:
        if unlock["name"] == last:
            return unlock
    return unlocks[0]
```

- [ ] **Step 6: Lift the ranking out of `ranked_doable`**

In `quest_path.py`, add above `ranked_doable`:

```python
def quest_rank(title, unlocks, quests, account):
    """Sort key for "best first": on the way to the most unlocks, then shortest, then easiest."""
    difficulty = account["quests"].get(title, {}).get("difficulty", 999)
    return (-unlock_count(title, unlocks, quests), length_rank(quests[title]["length"]), difficulty)
```

and in `ranked_doable` replace the inner `def rank(title): ...` (three lines) with:

```python
    def rank(title):
        return quest_rank(title, unlocks, quests, account)
```

- [ ] **Step 7: Add the chain and list functions**

In `quest_path.py`, change the import line `from rs3_planner import DIFFICULTY_NAMES` to:

```python
from rs3_planner import DIFFICULTY_NAMES, available_quests
```

and add a new section after `pick_tonight`:

```python
# ---------------------------------------------------------------------------
# Lists for the Quests screen
# ---------------------------------------------------------------------------

def chain_rows(goal, quests, account):
    """The goal's chain, prerequisites first, one dict per quest:
    {"title", "state", "reasons", "difficulty", "length"} (state/reasons as quest_state gives them)."""
    rows = []
    for title in full_chain(goal["final_quest"], quests):
        state, reasons = quest_state(title, quests, account)
        rows.append({"title": title, "state": state, "reasons": reasons,
                     "difficulty": difficulty_name(title, account), "length": quests[title]["length"]})
    return rows


def other_requirements(chain, quests, account):
    """The wiki's other requirements for the unfinished quests in a chain, as (text, quest) pairs."""
    return [(text, title) for title in chain if title not in account["completed_quests"]
            for text in quests[title]["other_requirements"]]


def useful_to_start(unlocks, quests, account):
    """Quests RuneMetrics says you can start (eligible, not started) that lead to
    one of the big unlocks, best first (ties in name order)."""
    on_chains = {t for u in unlocks for t in full_chain(u["final_quest"], quests)}
    titles = sorted(t for t, q in account["quests"].items()
                    if t in on_chains and q.get("userEligible") is True and q.get("status") == "NOT_STARTED")
    return sorted(titles, key=lambda t: quest_rank(t, unlocks, quests, account))


def eligible_by_difficulty(account):
    """Every quest you can start now, grouped: [("Novice", [titles]), ...].
    Same list as the terminal's (available_quests). Known difficulties come first in
    the usual order; a code RuneMetrics never sent before gets its own group at the end."""
    eligible = available_quests({"quests": list(account["quests"].values())})
    groups = {}
    for q in eligible:   # already sorted by difficulty, then name
        code = q["difficulty"]
        groups.setdefault(DIFFICULTY_NAMES.get(code, f"Unknown ({code})"), []).append(q["title"])
    known = [(name, groups[name]) for name in DIFFICULTY_NAMES.values() if name in groups]
    unknown = [(name, titles) for name, titles in groups.items() if name not in DIFFICULTY_NAMES.values()]
    return known + unknown


def started_quests(account):
    """Quests RuneMetrics marks as started, in name order."""
    return sorted(t for t, q in account["quests"].items() if q.get("status") == "STARTED")
```

- [ ] **Step 8: Let `print_quest_path` use `other_requirements`**

In `print_quest_path`, replace:

```python
    other = [(t, o) for t in chain if t not in account["completed_quests"]
             for o in quests[t]["other_requirements"]]
    if other:
        print("\n  Other requirements (check these yourself):")
        for title, text in other:
            print(f"    {text}  (for {title})")
```

with:

```python
    other = other_requirements(chain, quests, account)
    if other:
        print("\n  Other requirements (check these yourself):")
        for text, title in other:
            print(f"    {text}  (for {title})")
```

- [ ] **Step 9: Run the tests**

Run: `python3 -m unittest tests.test_quest_path -v` → all pass.
Run: `python3 -m unittest discover -s tests -v` → all pass (58 before this task plus the new ones). Report any failure by name.

- [ ] **Step 10: Neutral wording in `data/unlocks.json`**

Change exactly these two strings (nothing else):
- `"Your Path C question; it also needs the Divine Conversion relic"` → `"This money method also needs the Divine Conversion relic"`
- `"A third light animica mine for Path A"` → `"A third light animica mine"`

Run: `python3 check_methods.py > /dev/null && echo ok` → `ok`.

- [ ] **Step 11: Terminal proof**

```bash
mkdir -p $SCR/after && rm -rf $SCR/after/* && cd ~/Repos/RS-Planning-Tool
git ls-files -z | xargs -0 tar -c | tar -x -C $SCR/after      # working-tree copy of tracked files
mkdir -p $SCR/after/data/players/hels+glasglo && cp data/players/hels+glasglo/answers.json $SCR/after/data/players/hels+glasglo/
python3 $SCR/run_frozen.py $SCR/after $SCR/frozen plan_session.py --user "Hels Glasglo" --hours 5 --minutes 2 --session active --goal 1 > $SCR/terminal_after.txt
diff $SCR/terminal_before.txt $SCR/terminal_after.txt && echo "no difference"
```

Expected: `no difference`. (The terminal prints only the chosen goal's "Why it matters" line; goal 1 is Prifddinas, whose wording did not change.) Any difference: stop and report.

- [ ] **Step 12: Commit and stop**

```bash
git add quest_path.py tests/test_quest_path.py data/unlocks.json
git commit -F - <<'EOF'
Quest logic for the Quests screen; goal file repairs; neutral unlock wording

goal_for, quest_rank, chain_rows, other_requirements, useful_to_start,
eligible_by_difficulty and started_quests in quest_path.py. read_last_goal
survives a garbled file; save_last_goal says whether it saved.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

Stop. Tell Chris what changed, the test count, and the terminal proof result. Wait.

---

### Task 2: The chosen goal in the app (step 2b)

**Files:**
- Modify: `app.py` (imports; constants `BIG_GOAL_QUEST`/`GOAL`; `big_goal_numbers`; Home's Big goal card; `active_plan`)

**Interfaces:**
- Consumes: `goal_for(unlocks, username) -> dict`, plus existing `goal_progress`, `skill_gaps`, `ranked_doable`, `unlock_count`, `difficulty_name`.
- Produces (used by Task 3), all in `app.py`:
  - `current_goal() -> dict`
  - `big_goal_numbers(goal, account) -> {"chain": int, "done": int, "short": int}`
  - `skills_short(count) -> str` ("no skills short" / "1 skill short" / "4 skills short")
  - `tonight_panels(goal, account) -> None`
  - `skills_short_panel(goal, account, title) -> None`

`app.py` can't be unit-tested (it starts NiceGUI on import), so this task is proved by before/after page text on frozen data.

- [ ] **Step 1: Save the app "before" text**

Add this configuration to the git-excluded `.claude/launch.json` (inside `"configurations"`):

```json
{
  "name": "rs3-frozen",
  "runtimeExecutable": "/home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python",
  "runtimeArgs": ["<SCR>/run_frozen.py", "<SCR>/before", "<SCR>/frozen", "app.py"],
  "port": 8091
}
```

(with `<SCR>` written out in full). `$SCR/before` is the `BASE` copy from Task 1 with only `answers.json` copied in; also give it the current player so it opens on Home:

```bash
echo "Hels Glasglo" > $SCR/before/data/players/current.txt
```

Start it with the preview tool (`preview_start {name: "rs3-frozen"}`), then for each page read the text with
`javascript_tool`: `document.querySelector('main').innerText`, and save it with the Write tool:
- `http://localhost:8091/` → `$SCR/app_before_home.txt`
- `http://localhost:8091/plan?hours=5&session=active&minutes=2` → `$SCR/app_before_active.txt`

Stop the preview (`preview_stop`). Check the preview log shows exactly one "Fetching Hels Glasglo from RuneMetrics" (that "fetch" reads the frozen files).

- [ ] **Step 2: Replace the fixed goal with `current_goal()`**

In `app.py`:

1. Import line: `from quest_path import difficulty_name, goal_progress, ranked_doable, skill_gaps, unlock_count`
   becomes `from quest_path import difficulty_name, goal_for, goal_progress, ranked_doable, skill_gaps, unlock_count`.
2. Delete `BIG_GOAL_QUEST = "Plague's End"` and `GOAL = next(u for u in UNLOCKS if u["final_quest"] == BIG_GOAL_QUEST)`.
3. After `current_entry()`, add:

```python
def current_goal():
    """The current player's big goal: their saved choice (shared with the terminal's
    menu), else the first unlock. Read fresh each time, so a change made in the
    terminal shows on the next page load."""
    return goal_for(UNLOCKS, CURRENT["name"])
```

4. Replace `big_goal_numbers` with:

```python
def big_goal_numbers(goal, account):
    """Progress on a big goal: quests done in its chain, and skills short anywhere in it."""
    chain, done = goal_progress(goal, QUESTS, account)
    return {"chain": len(chain), "done": done, "short": len(skill_gaps(chain, QUESTS, account))}


def skills_short(count):
    """'no skills short', '1 skill short' or '4 skills short'."""
    if count == 0:
        return "no skills short"
    return f"{count} skill short" if count == 1 else f"{count} skills short"
```

5. Replace Home's Big goal card (from `# Big goal` to the `level_text` label) with:

```python
        # Big goal (the one chosen on the Quests screen)
        goal = current_goal()
        numbers = big_goal_numbers(goal, account)
        with panel():
            ui.label("Big goal").classes("label")
            ui.label(goal["name"]).classes("subtitle")
            ui.label(f"via {goal['final_quest']}").classes("muted")
            ui.label(f"{numbers['done']} of {numbers['chain']} quests done in its chain").classes("muted")
            short = skills_short(numbers["short"]) + " for its chain"
            ui.label(short[0].upper() + short[1:]).classes("muted")
```

- [ ] **Step 3: Split the Active plan into shared helpers**

Replace the whole `active_plan` function with:

```python
def active_plan(account, hours):
    goal = current_goal()
    ui.label("Your active plan").classes("title")
    ui.label(f"{hours:g} hours · big goal: {goal['name']} ({goal['final_quest']})").classes("muted")
    tonight_panels(goal, account)
    skills_short_panel(goal, account, f"Skills still short for {goal['final_quest']}")


def tonight_panels(goal, account):
    """Tonight's quest and the next one on the way (Active plan and Quests screen)."""
    titles, on_path = ranked_doable(goal, UNLOCKS, QUESTS, account)   # same ranking as the terminal

    with panel(crimson=True):
        ui.label("Tonight's quest").classes("label")
        if not titles:
            ui.label("Nothing in your unlock chains is ready right now.").classes("muted")
        else:
            tonight = titles[0]
            ui.label(tonight).classes("subtitle")
            ui.label(f"{difficulty_name(tonight, account)} · {QUESTS[tonight]['length']}").classes("muted")
            where = "On the way to your big goal" if on_path else "Not on your big goal's path (nothing there is ready)"
            ui.label(f"{where}; helps {unlock_count(tonight, UNLOCKS, QUESTS)} of your "
                     f"{len(UNLOCKS)} unlocks.").classes("muted small")

    if len(titles) > 1:
        also = titles[1]
        with panel():
            ui.label("Also on the way").classes("label green")
            ui.label(also).classes("heading")
            ui.label(f"{difficulty_name(also, account)} · {QUESTS[also]['length']}").classes("muted")


def skills_short_panel(goal, account, title):
    """Skill levels still needed anywhere in the goal's chain, smallest gap first."""
    chain, _ = goal_progress(goal, QUESTS, account)
    gaps = skill_gaps(chain, QUESTS, account)
    with panel():
        ui.label(title).classes("label")
        if not gaps:
            ui.label("None - your levels already cover the whole chain.").classes("muted")
        for skill, (level, have, xp_left, _) in gaps.items():
            with ui.row().classes("row-line"):
                ui.label(f"{skill} {have} → {level}").classes("heading")
                ui.label(f"{xp_left:,.0f} XP left").classes("muted")
            bar(account["skills"][skill]["xp"] / LEVEL_XP[level - 1], thin=True)
```

- [ ] **Step 4: Check nothing still uses the old constants, run the tests**

```bash
grep -n "BIG_GOAL_QUEST\|\bGOAL\b" app.py || echo "none left"
python3 -c "import ast; ast.parse(open('app.py').read())" && echo "syntax ok"
python3 -m unittest discover -s tests -v
```

Expected: `none left`, `syntax ok`, all tests pass.

- [ ] **Step 5: App proof**

Make the "after" copy from the working tree and capture the same two pages:

```bash
rm -rf $SCR/after && mkdir -p $SCR/after && cd ~/Repos/RS-Planning-Tool
git ls-files -z | xargs -0 tar -c | tar -x -C $SCR/after
mkdir -p $SCR/after/data/players/hels+glasglo
cp data/players/hels+glasglo/answers.json $SCR/after/data/players/hels+glasglo/
echo "Hels Glasglo" > $SCR/after/data/players/current.txt
```

In `.claude/launch.json` change the `rs3-frozen` argument `<SCR>/before` to `<SCR>/after`. Start the preview, save `app_after_home.txt` and `app_after_active.txt` the same way, stop the preview. Then:

```bash
diff <(grep -v "^Stats updated" $SCR/app_before_home.txt) <(grep -v "^Stats updated" $SCR/app_after_home.txt)
diff $SCR/app_before_active.txt $SCR/app_after_active.txt && echo "active plan: no difference"
```

Expected Home difference — only the Big goal card:
- before: `Plague's End` / `1 of 15 quests done in its chain` / `4 of 10 required skills below 75`
- after: `Prifddinas` / `via Plague's End` / `1 of 15 quests done in its chain` / `4 skills short for its chain`

Expected Active plan: `active plan: no difference`. Anything else: stop and report.

- [ ] **Step 6: Commit and stop**

```bash
git add app.py
git commit -F - <<'EOF'
App: big goal comes from the player's saved choice; shared quest panels

Home's Big goal card and the Active plan use the goal saved in last_goal
(shared with the terminal), defaulting to the first unlock. Home counts
skills short across the whole chain.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

Stop. Tell Chris the before/after result. Wait.

---

### Task 3: Quests screen, Change goal screen, nav, README (step 2c)

**Files:**
- Modify: `app.py` (imports, `bottom_nav`, new helpers and two pages)
- Modify: `static/app.css`
- Modify: `README.md`

**Interfaces:**
- Consumes: from Task 1 `chain_rows`, `other_requirements`, `useful_to_start`, `eligible_by_difficulty`, `started_quests`, `save_last_goal`; from Task 2 `current_goal`, `big_goal_numbers`, `skills_short`, `tonight_panels`, `skills_short_panel`; existing `NO_VALUE`, `panel`, `bar`, `button`, `back_button`, `updated_text`, `no_data_panel`, `current_entry`, `bottom_nav`.
- Produces: pages `/quests` and `/quests/goal`.

- [ ] **Step 1: Imports and the nav**

Import line becomes:

```python
from quest_path import (
    chain_rows, difficulty_name, eligible_by_difficulty, goal_for, goal_progress, other_requirements,
    ranked_doable, save_last_goal, skill_gaps, started_quests, unlock_count, useful_to_start,
)
```

Replace `bottom_nav` with:

```python
# Bottom nav buttons that have a screen; the others say "coming soon".
NAV_TARGETS = {"Home": "/", "Skills": "/skills", "Quests": "/quests"}


def bottom_nav(active):
    with ui.element("div").classes("bottom-nav"):
        with ui.element("div").classes("bottom-nav-inner"):
            for name in ("Home", "Skills", "Quests", "Progress"):
                target = NAV_TARGETS.get(name)
                if target:
                    action = lambda t=target: ui.navigate.to(t)
                else:
                    action = lambda n=name: ui.notify(f"{n}: coming soon")
                button(name, on_click=action).props("flat no-caps").classes(
                    "nav-btn" + (" active" if name == active else ""))
```

- [ ] **Step 2: The Quests screen**

Add after the Skills screen section:

```python
# ---------------------------------------------------------------------------
# Screen: Quests
# ---------------------------------------------------------------------------

STATUS_WORDS = {"ready": "Ready now", "started": "Started", "blocked": "Blocked"}


def difficulty_text(title, account):
    """The quest's difficulty, or — when RuneMetrics doesn't list the quest."""
    name = difficulty_name(title, account)
    return NO_VALUE if name == "?" else name


@ui.page("/quests", title="Quests - RS3 Planner")
def quests_page():
    entry = current_entry()
    if entry is None:   # nobody chosen yet: go and pick a player
        return RedirectResponse("/player")

    with ui.column().classes("page"):
        ui.label("Quests").classes("title")
        ui.label(entry["name"]).classes("subtitle")
        ui.label(updated_text(entry)).classes("muted")

        account = entry["account"]
        if account is None:
            no_data_panel(entry)
            bottom_nav("Quests")
            return

        goal = current_goal()
        numbers = big_goal_numbers(goal, account)
        with panel():
            ui.label("Big goal").classes("label")
            ui.label(goal["name"]).classes("subtitle")
            ui.label(f"via {goal['final_quest']}").classes("muted")
            ui.label(goal["unlocks"]).classes("muted small")
            ui.label(f"{numbers['done']} of {numbers['chain']} quests done").classes("muted")
            bar(numbers["done"] / numbers["chain"])   # a chain always holds at least the final quest
            button("Change goal", on_click=lambda: ui.navigate.to("/quests/goal")).props(
                "unelevated no-caps").classes("btn-quiet")

        tonight_panels(goal, account)
        skills_short_panel(goal, account, "Skills short for this chain")
        chain_panel(goal, account)
        other_requirements_panel(goal, account)
        start_now_panel(account)
        in_progress_panel(account)

    bottom_nav("Quests")


def chain_panel(goal, account):
    """Every quest in the goal's chain, prerequisites first, with its status."""
    with panel():
        ui.label("Quest chain").classes("label green")
        for row in chain_rows(goal, QUESTS, account):
            if row["state"] == "done":
                ui.label(f"{row['title']} · Done").classes("muted small")
                continue
            ui.label(row["title"]).classes("heading")
            ui.label(f"{difficulty_text(row['title'], account)} · {row['length']}").classes("muted small")
            status = STATUS_WORDS[row["state"]]
            if row["reasons"]:
                status += ": " + "; ".join(row["reasons"])
            ui.label(status).classes("muted small" + (" done-text" if row["state"] == "ready" else ""))


def other_requirements_panel(goal, account):
    """The wiki's other requirements in the chain. Hidden when there are none."""
    chain, _ = goal_progress(goal, QUESTS, account)
    lines = other_requirements(chain, QUESTS, account)
    if not lines:
        return
    with panel():
        ui.label("Other requirements (check these yourself)").classes("label")
        for text, title in lines:
            ui.label(f"{text} (for {title})").classes("muted small")


def start_now_panel(account):
    """Quests you can start that lead to an unlock, plus a Show all button for the rest."""
    useful = useful_to_start(UNLOCKS, QUESTS, account)
    groups = eligible_by_difficulty(account)
    total = sum(len(titles) for _, titles in groups)
    with panel():
        ui.label("Start now").classes("label green")
        if not useful:
            ui.label("No quest on your unlock chains can be started right now.").classes("muted")
        for title in useful:
            ui.label(title).classes("heading")
            ui.label(f"{difficulty_text(title, account)} · {QUESTS[title]['length']} · "
                     f"helps {unlock_count(title, UNLOCKS, QUESTS)} of {len(UNLOCKS)} unlocks").classes("muted small")
        if not total:
            return

        show_text = f"Show all {total} you can start"
        toggle = button(show_text).props("unelevated no-caps").classes("btn-quiet")
        # The full list is drawn now but hidden; the button shows or hides it (nothing is fetched).
        full_list = ui.column().classes("w-full gap-1")
        with full_list:
            for name, titles in groups:
                ui.label(f"{name} ({len(titles)})").classes("label")
                for title in titles:
                    ui.label(title).classes("muted small")
        full_list.set_visibility(False)

        def flip():
            showing = not full_list.visible
            full_list.set_visibility(showing)
            toggle.set_text("Hide the full list" if showing else show_text)

        toggle.on_click(flip)


def in_progress_panel(account):
    """Quests RuneMetrics says you've started. Hidden when there are none."""
    started = started_quests(account)
    if not started:
        return
    with panel():
        ui.label("In progress").classes("label")
        for title in started:
            with ui.row().classes("row-line"):
                ui.label(title).classes("heading")
                ui.label(difficulty_text(title, account)).classes("muted")
```

- [ ] **Step 3: The Change goal screen**

```python
# ---------------------------------------------------------------------------
# Screen: Change goal
# ---------------------------------------------------------------------------

@ui.page("/quests/goal", title="Big goal - RS3 Planner")
def goal_page():
    entry = current_entry()
    if entry is None:   # nobody chosen yet: go and pick a player
        return RedirectResponse("/player")

    def choose(unlock):
        # The same file the terminal's goal menu uses, so both agree.
        if save_last_goal(CURRENT["name"], unlock["name"]):
            ui.navigate.to("/quests")
        else:
            ui.notify("Couldn't save your goal choice")

    with ui.column().classes("page"):
        back_button("/quests")
        ui.label("Big goal").classes("title")

        account = entry["account"]
        if account is None:
            no_data_panel(entry)
            bottom_nav("Quests")
            return

        current = current_goal()
        with panel():
            ui.label("Choose your big goal").classes("label")
            for unlock in UNLOCKS:
                numbers = big_goal_numbers(unlock, account)
                selected = " selected" if unlock["name"] == current["name"] else ""
                with button(on_click=lambda u=unlock: choose(u)).props("unelevated no-caps").classes(
                        "chip wide goal-choice" + selected):
                    with ui.column().classes("gap-0"):
                        ui.label(unlock["name"]).classes("goal-name")
                        ui.label(f"{numbers['done']} of {numbers['chain']} quests done · "
                                 f"{skills_short(numbers['short'])}").classes("goal-progress")

    bottom_nav("Quests")
```

- [ ] **Step 4: CSS for the two-line goal buttons**

Append to `static/app.css` after the `.q-btn.chip.wide` rules:

```css
/* Change goal screen: a wide chip with the goal's name over its progress, left-aligned. */
.q-btn.chip.goal-choice { min-height: 60px; padding: 8px 14px; text-align: left; }
.goal-choice .goal-name { font-family: "Cinzel", serif; font-weight: 700; font-size: 16px; }
.goal-choice .goal-progress { font-family: "Alegreya", Georgia, serif; font-weight: 400; font-size: 14px; color: var(--muted); }
.q-btn.chip.goal-choice.selected .goal-progress { color: var(--glacial); }
```

- [ ] **Step 5: Tests and syntax**

```bash
python3 -c "import ast; ast.parse(open('app.py').read())" && echo "syntax ok"
python3 -m unittest discover -s tests -v
```

- [ ] **Step 6: Frozen copy: screens, numbers and phone width**

Refresh `$SCR/after` from the working tree (as in Task 2 Step 5) and start `rs3-frozen` (still pointing at `after`).
Check, at 375px wide (`resize_window` mobile), reading text with `get_page_text` and taking screenshots:

- Nav **Quests** opens `/quests` and is lit; **Progress** still says "coming soon".
- Big goal: "Prifddinas", "via Plague's End", "1 of 15 quests done".
- Tonight's quest and Skills short panels match the Active plan (`$SCR/app_after_active.txt`).
- Quest chain: 15 entries, in `full_chain("Plague's End")` order; 1 done.
- Start now: 16 quests; **Show all 109 you can start** opens a list whose group counts are Novice (49), Intermediate (33), Experienced (20), Master (3), Grandmaster (1), Special (3); the button then reads **Hide the full list**, and tapping it hides the list.
- In progress: 4 quests (All Fired Up, The Fremennik Trials, The Giant Dwarf, The Tale of the Muspah).
- No sideways scroll: `document.documentElement.scrollWidth === window.innerWidth` on `/quests` and `/quests/goal`.
- **Change goal** → 8 buttons, Prifddinas highlighted; each line's numbers match the terminal menu, printed on the copy with
  `printf "\n" | python3 $SCR/run_frozen.py $SCR/after $SCR/frozen plan_session.py --user "Hels Glasglo" --hours 5 --minutes 2 --session active | grep -A 10 "Big goals:"`
  (the blank line answers the menu with Enter, keeping the default).
- Tap **Superheat Form and Crystal Mask** → back on `/quests` showing it (2026-10-05 data: "8 of 42 quests done"); Home's card shows it (2026-10-05 data: "7 skills short for its chain"); the Active plan header names it.
- In the copy: `cat $SCR/after/data/players/hels+glasglo/last_goal` → `Superheat Form and Crystal Mask`, and the same menu command shows `Pick a big goal [3]`.
- Terminal → app: `printf "6\n" | python3 $SCR/run_frozen.py $SCR/after $SCR/frozen plan_session.py --user "Hels Glasglo" --hours 5 --minutes 2 --session active > /dev/null` (picks Elder wisps), then reload `/quests` → it shows "Elder wisps (Elder Halls)".
- Browser console has no errors; preview log shows one "Fetching" line.

Stop the preview, reset the viewport (`resize_window` desktop). All of this happened in the scratch copy; the real `data/players/` is untouched.

- [ ] **Step 7: Live check with the real app (one RuneMetrics fetch)**

Start `rs3-planner-gui` (its one start-up fetch is the only RuneMetrics call in this step). Open Quests, tap Change goal, choose **Lunar spells and the astral rift**, confirm `/quests` shows it, and confirm the real file the terminal menu reads:

```bash
cat data/players/hels+glasglo/last_goal
```

Expected: `Lunar spells and the astral rift` (the menu's default then comes from this file, as proved on the copy in Step 6; no terminal run here, so no second fetch). Then set the goal back: Change goal → **Prifddinas**, and confirm the same command prints `Prifddinas`. Tell Chris this file was changed and restored. Stop the preview.

- [ ] **Step 8: README**

In `README.md`, replace the Browser app's first paragraph with:

```markdown
A phone-friendly page with Home, Ready to play, your plan, **Skills** (all 29
skills with level, XP and XP left to 99, closest first, with finished skills at
the bottom) and **Quests** (your big goal: tonight's quest, the skills still short,
the whole quest chain with statuses, the quests you can start now and the ones in progress).
```

and add under "## The quest path (active sessions)", after its first paragraph:

```markdown
In the browser app, choose the big goal on the Quests screen (**Change goal**).
The app and the terminal share the choice (`data/players/<player>/last_goal`),
so picking a goal in one makes it the default in the other. Home's Big goal card
and the Active plan follow it.
```

- [ ] **Step 9: Remove the scratch launch config, final checks, commit and stop**

Remove the `rs3-frozen` entry from `.claude/launch.json` (leave `rs3-planner-gui`). Then:

```bash
python3 -m unittest discover -s tests -v
python3 check_methods.py > /dev/null && echo "data ok"
git status --short
git diff | grep -niE "glasglo" || echo "no player name in the diff"
git add app.py static/app.css README.md
git commit -F - <<'EOF'
App: Quests screen and Change goal screen

The Quests nav button opens the big goal: tonight's quest, skills short,
the chain with statuses, other requirements, quests to start now (with
Show all), and quests in progress. Change goal saves the choice in
last_goal, shared with the terminal.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

Stop. Tell Chris what changed, how it was checked, and ask before pushing.
