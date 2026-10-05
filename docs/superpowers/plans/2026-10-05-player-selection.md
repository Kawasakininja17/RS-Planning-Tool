# Choosing a Player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Anyone running their own copy of RS3 Planner can type a public RuneScape name and the whole app plans for that player, with per-player answers, snapshots and settings.

**Architecture:** A new `players.py` owns everything about "a player" (folder, answers, current player, name checks). `data/methods.json` keeps only wiki facts; things RuneMetrics can't see become `requirements.unlocks` that each player answers. `app.py` replaces its single `STATE` with a per-name `CACHE` and one remembered current player, and gains a `/player` screen.

**Tech Stack:** Python 3.14 standard library (terminal scripts, tests via `unittest`), NiceGUI 3.17.1 in `.venv/` (browser app).

**Spec:** `docs/superpowers/specs/2026-10-05-player-selection-design.md`

## Global Constraints

- Public data only (RuneMetrics + RuneScape Wiki). Nothing may touch the game client.
- Never ask for a password or anything private; only the public RuneMetrics name.
- Never show made-up numbers: missing → "—" or hide the line. No wiki number in `methods.json` changes.
- Server stays on `HOST = "127.0.0.1"`.
- Look: existing colours/classes in `static/app.css` only; one column, max 480px, tap targets ≥44px, ~10px corners, no gradients, no emoji. Buttons always via the `button()` helper (`color=None`).
- Ironman notice, word for word: "Ironman accounts aren't supported yet. Plans may suggest training or money methods an ironman can't use."
- Password notice, word for word: "Only your public RuneMetrics name. Never enter a password."
- Folder name: lower case, spaces → `+` (e.g. `data/players/hels+glasglo/`). `data/players/` is git-ignored.
- Name rules (wiki Display name page): trimmed; 1–12 characters; letters, digits, spaces, hyphens, underscores. Leading `-`/`_` allowed.
- Code is simple and commented in plain words, matching the existing files.
- Stop and wait for Chris after Task 3 (step 1a), Task 5 (step 1b) and Task 8 (step 1c). Commit after each task; never push without asking.
- Tests: `python3 -m unittest discover -s tests -v` from the project folder (standard library, nothing to install). Tests never touch the network or the real `data/players/`.

## Review Focus

1. **Same player typed differently** ("  hels glasglo ") → same folder, same cache entry, no second fetch. Pinned in Task 2 (`folder_name`) and Task 4 (`check_name` strips).
2. **Hand-edited or broken `answers.json`** → a clear message naming the file, not a crash. Pinned in Task 2 (`read_answers` raises `ValueError`) and handled in Task 3 (terminal) and Task 7 (app panel).
3. **"I don't" tapped by mistake** → can be undone from "Your answers". Pinned in Task 2 (`save_answer(..., None)` forgets) and Task 7 (browser check).
4. **Remembered player can't be fetched at start-up** (no internet, profile made private) → Home shows the error and Switch player still works. Browser check in Task 6.
5. **A failed lookup while another player is current** → current player and `current.txt` unchanged. Browser check in Task 6.

## File map

| File | Change | Responsibility |
|---|---|---|
| `players.py` | create | Player folders, answers, current player, name checks, known players, terminal name choice |
| `tests/test_players.py` | create | Tests for `players.py` |
| `tests/test_check_methods.py` | create | Tests for the new method fields |
| `tests/test_plan_session.py` | create | Tests for unlock answers and extra levels in the planner |
| `tests/test_snapshots.py` | create | Snapshot goes to the player folder |
| `tests/test_quest_path.py` | create | Last goal is per player |
| `data/methods.json` | modify | Wiki facts only; `missing` → `requirements.skills` / `requirements.unlocks` |
| `check_methods.py` | modify | Validate and print the new fields |
| `plan_session.py` | modify | Use answers; `--user` / remembered player |
| `quest_path.py` | modify | Last goal in the player folder |
| `snapshots.py` | modify | Snapshots in the player folder |
| `rs3_planner.py` | modify | No hard-coded default player |
| `app.py` | modify | Cache, current player, `/player`, Switch player, unlock answers |
| `static/app.css` | modify | Text box and wide chip styles |
| `.gitignore` | modify | `data/players/` replaces `data/snapshots/` and `.last_goal` |
| `README.md` | modify | Choosing a player, answers, ironman note, tests |

`SCRATCH` below means a temporary folder outside the project (the session's scratchpad), so nothing from the proof lands in git.

---

### Task 1: Save "before" outputs on frozen data

Live RuneMetrics data can move between runs, so the proof uses saved replies: fetch Hels's profile and quests once, then make the planner read those files instead of the internet, before and after every change.

**Files:**
- Create: `$SCRATCH/offline.py`, `$SCRATCH/capture.sh`, `$SCRATCH/fixtures/*.json`, `$SCRATCH/before/*` (scratchpad only, not in the project)

- [ ] **Step 1: Save the two RuneMetrics replies**

```bash
SCRATCH=<the session's scratch folder>
mkdir -p $SCRATCH/fixtures $SCRATCH/before $SCRATCH/after
curl -s -A rs3-planner/1.0 "https://apps.runescape.com/runemetrics/profile/profile?user=Hels%20Glasglo&activities=20" > $SCRATCH/fixtures/profile.json
curl -s -A rs3-planner/1.0 "https://apps.runescape.com/runemetrics/quests?user=Hels%20Glasglo" > $SCRATCH/fixtures/quests.json
python3 -c "import json,sys; [json.load(open(f)) for f in sys.argv[1:]]; print('both valid JSON')" $SCRATCH/fixtures/*.json
```
Expected: `both valid JSON`.

- [ ] **Step 2: Write `$SCRATCH/offline.py`**

```python
"""Run plan_session.py on saved RuneMetrics replies, so before/after runs see identical data."""
import json
import runpy
import sys
from pathlib import Path

PROJECT = Path.home() / "Repos" / "RS-Planning-Tool"
FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(PROJECT))

import rs3_planner


def saved_reply(url):
    name = "quests.json" if "/quests?" in url else "profile.json"
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


rs3_planner.fetch_json = saved_reply   # load_profile/load_quests now read the saved files
sys.argv = ["plan_session.py"] + sys.argv[1:]
runpy.run_path(str(PROJECT / "plan_session.py"), run_name="__main__")
```

- [ ] **Step 3: Write `$SCRATCH/capture.sh`**

```bash
#!/bin/bash
# Usage: capture.sh <output folder>. Saves the planner and checker output for comparison.
OUT=$1
SCRATCH=$(dirname "$0")
cd ~/Repos/RS-Planning-Tool || exit 1
for combo in "5 2 afk" "1 1 afk" "8 5 afk" "5 2 active"; do
    set -- $combo
    python3 "$SCRATCH/offline.py" --user "Hels Glasglo" --hours $1 --minutes $2 --session $3 --goal 1 \
        > "$OUT/plan_${1}h_${2}m_${3}.txt" 2>&1
done
python3 check_methods.py > "$OUT/check_methods.txt" 2>&1
echo "saved to $OUT"
```

- [ ] **Step 4: Capture "before"**

Run: `bash $SCRATCH/capture.sh $SCRATCH/before && ls $SCRATCH/before && head -20 $SCRATCH/before/plan_5h_2m_afk.txt`
Expected: five files; the plan shows PATH A with Mining (light/dark animica) and the gaps match today's sanity values.

No commit (scratchpad only).

---

### Task 2: `players.py` — folders and answers

**Files:**
- Create: `players.py`, `tests/test_players.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `PLAYERS_DIR: Path`; `folder_name(name: str) -> str`; `player_dir(name: str) -> Path`; `read_answers(name: str) -> dict[str, bool]` (raises `ValueError` with a plain message if the file is broken); `save_answer(name: str, unlock_id: str, has_it: bool | None) -> None` (`None` forgets the answer).

- [ ] **Step 1: Write the failing tests** — `tests/test_players.py`

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: error `ModuleNotFoundError: No module named 'players'`.

- [ ] **Step 3: Write `players.py`**

```python
"""
RS3 Planner - players
=====================

Everything about "which player" lives here, so the rest of the code never
has to know where a player's files are kept.

Each player gets a folder under data/players/ (kept out of git):
    data/players/hels+glasglo/
        answers.json   "I have it" / "I don't" answers for unlocks RuneMetrics can't see
        last_goal      the big goal picked last time in the terminal menu
        snapshots/     XP snapshots, one per fetch
"""

import json
from pathlib import Path

PLAYERS_DIR = Path(__file__).parent / "data" / "players"


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

def folder_name(name):
    """
    'Hels Glasglo' -> 'hels+glasglo'.
    A '+' can never be part of a RuneScape name, so two players never share a
    folder. Hyphens and underscores are kept: the wiki's Display name page says
    an underscore is not the same as a space.
    """
    return name.strip().lower().replace(" ", "+")


def player_dir(name):
    return PLAYERS_DIR / folder_name(name)


# ---------------------------------------------------------------------------
# Answers: "I have it" / "I don't" for unlocks RuneMetrics can't see
# ---------------------------------------------------------------------------

def read_answers(name):
    """
    {unlock id: True or False}. No file yet means nothing answered: {}.
    A broken file raises ValueError with a plain message, so a typo made
    while hand-editing is reported instead of silently ignored.
    """
    path = player_dir(name) / "answers.json"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        answers = json.loads(text)
    except json.JSONDecodeError as err:
        raise ValueError(f"{path} isn't valid JSON: {err.msg} (line {err.lineno}). "
                         "Fix it or delete it to start over.") from None
    if not isinstance(answers, dict) or not all(isinstance(v, bool) for v in answers.values()):
        raise ValueError(f"{path} must look like {{\"unlock-id\": true}}, with only true or false as answers.")
    return answers


def save_answer(name, unlock_id, has_it):
    """Save one answer. has_it: True, False, or None to forget the answer."""
    answers = read_answers(name)
    if has_it is None:
        answers.pop(unlock_id, None)
    else:
        answers[unlock_id] = has_it
    folder = player_dir(name)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "answers.json").write_text(json.dumps(answers, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: 9 tests, `OK`.

- [ ] **Step 5: Keep player folders out of git** — add a line to `.gitignore` (the old lines go in Task 5):

```
data/players/
```

Run: `git status --short` — expected: `.gitignore`, `players.py`, `tests/` only.

- [ ] **Step 6: Commit**

```bash
git add players.py tests/test_players.py .gitignore
git commit -m "Add players.py: per-player folders and unlock answers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Wiki facts vs player answers in methods, checker and planner (step 1a)

These change together: removing `missing` from the data breaks the checker and planner until they understand the new fields.

**Files:**
- Modify: `data/methods.json`, `check_methods.py`, `plan_session.py`
- Create: `tests/test_check_methods.py`, `tests/test_plan_session.py`, `data/players/hels+glasglo/answers.json` (git-ignored)

**Interfaces:**
- Consumes: `read_answers(name)` from Task 2.
- Produces: `check_method(method, position) -> list[str]` (validates `requirements.skills` / `requirements.unlocks`); `check_unlock_ids_match(methods) -> list[str]`; `check_method_for_session(method, account, max_minutes, answers) -> (blocked, warnings, unanswered)` where `unanswered` is a list of `{"id", "text"}`; `build_plan(methods, account, max_minutes, answers)` sets `method["_unanswered"]` on every method.

- [ ] **Step 1: Write the failing checker tests** — `tests/test_check_methods.py`

```python
"""Tests for the new requirements.skills / requirements.unlocks fields in check_methods.py."""

import copy
import unittest

from check_methods import check_method, check_unlock_ids_match

VALID = {
    "type": "training", "name": "Test method", "skill": "Mining", "min_level": 90,
    "xp_per_hour_low": 1000, "xp_per_hour_high": 2000,
    "gp_per_hour": None, "gp_after_tax": None, "minutes_between_clicks": None,
    "requirements": {
        "quests": [], "other": [],
        "skills": {"Mining": 99},
        "unlocks": [{"id": "smithing-autoheater", "text": "Smithing autoheater"}],
    },
    "unverified": [], "source_url": "https://runescape.wiki/w/Mining",
    "checked_date": "2026-10-04", "notes": "",
}


def method_with(**requirement_changes):
    method = copy.deepcopy(VALID)
    method["requirements"].update(requirement_changes)
    return method


def mentions(problems, text):
    return any(text in problem for problem in problems)


class CheckMethodTests(unittest.TestCase):
    def test_valid_method_has_no_problems(self):
        self.assertEqual(check_method(copy.deepcopy(VALID), 1), [])

    def test_old_missing_field_is_rejected(self):
        method = copy.deepcopy(VALID)
        method["missing"] = []
        self.assertIn("Method #1 (Test method): unknown field 'missing' (typo?)", check_method(method, 1))

    def test_requirements_need_all_four_keys(self):
        method = copy.deepcopy(VALID)
        del method["requirements"]["unlocks"]
        self.assertTrue(mentions(check_method(method, 1), "exactly 'quests', 'other', 'skills' and 'unlocks'"))

    def test_unknown_skill_in_skills(self):
        self.assertTrue(mentions(check_method(method_with(skills={"Minning": 99}), 1), "unknown skill 'Minning'"))

    def test_skill_level_out_of_range(self):
        self.assertTrue(mentions(check_method(method_with(skills={"Mining": 121}), 1), "from 1 to 120"))

    def test_unlock_needs_id_and_text(self):
        self.assertTrue(mentions(check_method(method_with(unlocks=[{"id": "x"}]), 1), "exactly 'id' and 'text'"))

    def test_unlock_id_format(self):
        bad = [{"id": "Smithing Autoheater", "text": "Smithing autoheater"}]
        self.assertTrue(mentions(check_method(method_with(unlocks=bad), 1), "lower-case words joined by hyphens"))

    def test_unlock_text_not_empty(self):
        bad = [{"id": "smithing-autoheater", "text": "  "}]
        self.assertTrue(mentions(check_method(method_with(unlocks=bad), 1), "text must be non-empty"))

    def test_same_unlock_twice_in_one_method(self):
        twice = [{"id": "a", "text": "A"}, {"id": "a", "text": "A"}]
        self.assertTrue(mentions(check_method(method_with(unlocks=twice), 1), "listed twice"))


class UnlockIdsMatchTests(unittest.TestCase):
    def test_same_id_same_text_is_fine(self):
        methods = [method_with(unlocks=[{"id": "a", "text": "A"}]), method_with(unlocks=[{"id": "a", "text": "A"}])]
        self.assertEqual(check_unlock_ids_match(methods), [])

    def test_same_id_different_text_is_a_problem(self):
        methods = [method_with(unlocks=[{"id": "a", "text": "A"}]), method_with(unlocks=[{"id": "a", "text": "B"}])]
        self.assertEqual(check_unlock_ids_match(methods), ["Unlock id 'a' has different text in different methods"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Write the failing planner tests** — `tests/test_plan_session.py`

```python
"""Tests for unlock answers and extra levels in plan_session.check_method_for_session."""

import copy
import unittest

from account import LEVEL_XP
from plan_session import check_method_for_session
from rs3_planner import SKILL_NAMES

AUTOHEATER = {"id": "smithing-autoheater", "text": "Smithing autoheater"}

METHOD = {
    "type": "training", "name": "Forging", "skill": "Smithing", "min_level": 90,
    "xp_per_hour_low": 150000, "xp_per_hour_high": 150000,
    "gp_per_hour": None, "gp_after_tax": None, "minutes_between_clicks": 5.0,
    "requirements": {"quests": [], "other": [], "skills": {}, "unlocks": [AUTOHEATER]},
    "unverified": [], "source_url": "https://runescape.wiki/w/Smithing",
    "checked_date": "2026-10-04", "notes": "",
}


def make_account(level=95):
    """Every skill at the same level, no quests done."""
    skills = {name: {"xp": float(LEVEL_XP[level - 1]), "level": level} for name in SKILL_NAMES}
    return {"skills": skills, "completed_quests": set(), "quests": {}}


class UnlockAnswerTests(unittest.TestCase):
    def test_unanswered_unlock_is_not_blocked_but_listed(self):
        blocked, _, unanswered = check_method_for_session(copy.deepcopy(METHOD), make_account(), 2, {})
        self.assertEqual(blocked, [])
        self.assertEqual(unanswered, [AUTOHEATER])

    def test_answer_no_blocks(self):
        blocked, _, unanswered = check_method_for_session(
            copy.deepcopy(METHOD), make_account(), 2, {"smithing-autoheater": False})
        self.assertEqual(blocked, ["you said you don't have: Smithing autoheater"])
        self.assertEqual(unanswered, [])

    def test_answer_yes_clears_it(self):
        blocked, _, unanswered = check_method_for_session(
            copy.deepcopy(METHOD), make_account(), 2, {"smithing-autoheater": True})
        self.assertEqual((blocked, unanswered), ([], []))


class ExtraLevelTests(unittest.TestCase):
    def test_extra_skill_level_blocks_when_too_low(self):
        method = copy.deepcopy(METHOD)
        method["requirements"]["skills"] = {"Mining": 99}
        blocked, _, _ = check_method_for_session(method, make_account(95), 2, {"smithing-autoheater": True})
        self.assertEqual(blocked, ["needs Mining 99 (you have 95)"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run them to see them fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: `ImportError: cannot import name 'check_unlock_ids_match'`, and the planner tests fail (wrong number of arguments / unpacking).

- [ ] **Step 4: Update `check_methods.py`**

4a. Add `import re` under `import json` (comment: `# to check the shape of unlock ids`).

4b. In `REQUIRED_FIELDS`, replace `"minutes_between_clicks", "requirements", "missing", "unverified",` with `"minutes_between_clicks", "requirements", "unverified",`.

4c. Replace section "7." in `check_method` (from `# 7. Requirements and the two "what's missing" lists.` to the end of the `for key in ("missing", "unverified"):` loop) with:

```python
    # 7. Requirements. "skills" are extra levels the planner checks live;
    #    "unlocks" are things RuneMetrics can't see, which each player answers.
    reqs = method["requirements"]
    if not isinstance(reqs, dict) or set(reqs) != {"quests", "other", "skills", "unlocks"}:
        problems.append(f"{label}: requirements must have exactly 'quests', 'other', 'skills' and 'unlocks'")
    else:
        for key in ("quests", "other"):
            if not is_list_of_text(reqs[key]):
                problems.append(f"{label}: requirements.{key} must be a list of text")
        problems.extend(check_skill_levels(reqs["skills"], f"{label}: requirements.skills"))
        problems.extend(check_unlock_list(reqs["unlocks"], label))
    if not is_list_of_text(method["unverified"]):
        problems.append(f"{label}: unverified must be a list of text")
```

4d. Add these after `check_fields`:

```python
def check_skill_levels(skills, label):
    """A {skill: level} block: real skill names, whole-number levels from 1 to 120."""
    if not isinstance(skills, dict):
        return [f"{label} must be {{skill: level}}"]
    problems = []
    for skill, level in skills.items():
        if skill not in SKILL_NAMES:
            problems.append(f"{label}: unknown skill '{skill}'")
        if not is_whole_number(level) or not 1 <= level <= 120:
            problems.append(f"{label}: {skill} level must be a whole number from 1 to 120")
    return problems


# Unlock ids: lower-case words joined by hyphens, e.g. "smithing-autoheater".
UNLOCK_ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def check_unlock_list(unlocks, label):
    """requirements.unlocks: [{"id": "smithing-autoheater", "text": "..."}], each id once."""
    if not isinstance(unlocks, list):
        return [f"{label}: requirements.unlocks must be a list"]
    problems, seen = [], set()
    for position, unlock in enumerate(unlocks, start=1):
        where = f"{label}: unlock #{position}"
        if not isinstance(unlock, dict) or set(unlock) != {"id", "text"}:
            problems.append(f"{where} must have exactly 'id' and 'text'")
            continue
        if not isinstance(unlock["id"], str) or not UNLOCK_ID.fullmatch(unlock["id"]):
            problems.append(f"{where}: id must be lower-case words joined by hyphens, like 'smithing-autoheater'")
        elif unlock["id"] in seen:
            problems.append(f"{where}: id '{unlock['id']}' is listed twice")
        else:
            seen.add(unlock["id"])
        if not isinstance(unlock["text"], str) or not unlock["text"].strip():
            problems.append(f"{where}: text must be non-empty text")
    return problems


def check_unlock_ids_match(methods):
    """One answer covers every method with that unlock id, so the id must mean the same everywhere."""
    problems, texts = [], {}
    for method in methods:
        reqs = method.get("requirements") if isinstance(method, dict) else None
        unlocks = reqs.get("unlocks") if isinstance(reqs, dict) else None
        for unlock in unlocks if isinstance(unlocks, list) else []:
            if not (isinstance(unlock, dict) and isinstance(unlock.get("id"), str)
                    and isinstance(unlock.get("text"), str)):
                continue   # check_unlock_list already reports these
            if texts.setdefault(unlock["id"], unlock["text"]) != unlock["text"]:
                problems.append(f"Unlock id '{unlock['id']}' has different text in different methods")
    return problems
```

4e. In `load_methods`, after the duplicate-name loop and before `stop_if_problems`, add:

```python
    problems.extend(check_unlock_ids_match(methods))
```

4f. In `print_table`, replace the two lines starting `ready = "ok" if not m["missing"]` and `if ready == "ok" and m["unverified"]:` (and its body) with:

```python
        unlocks = m["requirements"]["unlocks"]
        ready = "ok" if not unlocks else f"{len(unlocks)} to confirm"
        if m["unverified"]:
            ready += "*"
```

and replace the two legend lines starting `print("Click: '?' = the wiki doesn't say.` with:

```python
    print("Click: '?' = the wiki doesn't say.   Unlocks: how many things each player confirms in the app")
    print("(RuneMetrics can't see them); * = the rate also assumes something public data can't confirm.")
    print("Levels and quests are checked live by plan_session.py.")
```

4g. In `print_gaps`, replace the block from `print("\nMissing for you right now:")` through its loop with:

```python
    print("\nExtra levels needed (checked live for each player):")
    for m in methods:
        for skill, level in m["requirements"]["skills"].items():
            print(f"  - {m['name']}: {skill} {level}")

    print("\nUnlocks each player confirms for themselves:")
    for m in methods:
        for unlock in m["requirements"]["unlocks"]:
            print(f"  - {m['name']}: {unlock['text']}")
```

- [ ] **Step 5: Update `plan_session.py`**

5a. Imports: add `import sys` under `import argparse` (comment: `# stops with a clear message if the answers file is broken`) and `from players import read_answers` after the `from check_methods ...` line.

5b. Replace `check_method_for_session` with:

```python
def check_method_for_session(method, account, max_minutes, answers):
    """
    Returns (blocked_reasons, warnings, unanswered).
    No blocked reasons = you can do it now. Warnings are worth knowing but don't block.
    unanswered = unlocks RuneMetrics can't see that the player hasn't said yes or no to.
    answers = {unlock id: True/False} from players.read_answers().
    """
    blocked, warnings, unanswered = [], [], []
    skills = method["skill"].split("/")

    # Levels, checked live against your XP.
    for skill in skills:
        level = account["skills"][skill]["level"]
        if level < method["min_level"]:
            blocked.append(f"needs {skill} {method['min_level']} (you have {level})")
    # Extra levels some methods need beyond min_level (e.g. 99 Mining for a mining cape).
    for skill, level in method["requirements"]["skills"].items():
        have = account["skills"][skill]["level"]
        if have < level:
            blocked.append(f"needs {skill} {level} (you have {have})")

    # Quests, checked live against RuneMetrics.
    for quest in method["requirements"]["quests"]:
        if quest not in account["completed_quests"]:
            blocked.append(f"quest not done: {quest}")

    # Unlocks RuneMetrics can't see: the player's own answers decide.
    for unlock in method["requirements"]["unlocks"]:
        answer = answers.get(unlock["id"])
        if answer is False:
            blocked.append(f"you said you don't have: {unlock['text']}")
        elif answer is None:
            unanswered.append(unlock)

    # Click time. A known time shorter than your limit means too much clicking.
    minutes = method["minutes_between_clicks"]
    if minutes is None:
        warnings.append("click time unknown (the wiki doesn't give one)")
    elif minutes < max_minutes:
        blocked.append(f"needs a click every {minutes:g} min; your limit is {max_minutes:g}")

    # Training only makes sense for the max cape if a skill is still under 99.
    if method["type"] == "training" and all(xp_to_99(account, s) == 0 for s in skills):
        blocked.append("already 99")

    if method["gp_after_tax"] is False:
        warnings.append("gp figure is BEFORE Grand Exchange tax (the wiki gives no after-tax figure)")
    warnings.extend(f"assumes: {item}" for item in method["unverified"])
    return blocked, warnings, unanswered
```

5c. In `build_plan`: change the signature to `def build_plan(methods, account, max_minutes, answers):`, add to its docstring `answers = {unlock id: True/False} from players.read_answers().`, and replace the first three lines of its loop with:

```python
        blocked, warnings, unanswered = check_method_for_session(method, account, max_minutes, answers)
        method["_warnings"] = warnings
        method["_unanswered"] = unanswered
```

5d. In `print_path`, after the `for warning in method["_warnings"]:` loop add:

```python
    for unlock in method["_unanswered"]:
        print(f"  Check:   needs {unlock['text']} (not answered yet; answer in the browser app)")
```

5e. In `main()`, after `account = read_account(...)` add:

```python
    try:
        answers = read_answers(args.user)
    except ValueError as err:
        sys.exit(f"Error: {err}")
```

and change `plan = build_plan(methods, account, max_minutes)` to `plan = build_plan(methods, account, max_minutes, answers)`.

5f. Update `app.py` so it keeps working until Task 7 rewrites this part: in `afk_plan` change
`plan = build_plan(copy.deepcopy(METHODS), account, minutes)` to
`plan = build_plan(copy.deepcopy(METHODS), account, minutes, read_answers(USERNAME))`
and add `from players import read_answers` to its imports.

- [ ] **Step 6: Run the tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests `OK` (9 players + 11 checker + 4 planner = 24).

- [ ] **Step 7: Edit `data/methods.json`** (use exact string edits; keep the file's existing formatting)

7a. `about` becomes:
`"AFK training and money methods. Every number was copied from the RuneScape Wiki page in source_url on checked_date. null means the wiki did not give that value. GP figures use live Grand Exchange prices, so they drift day to day. Facts about one player (what they own or have unlocked) are not kept here: each player's answers live in data/players/<name>/answers.json."`

7b. In **every** method: delete the `"missing": ...` entry, and inside `requirements` add `"skills"` and `"unlocks"` after `"other"`. For methods not listed in 7c, they are `"skills": {}` and `"unlocks": []` and nothing else changes. Methods: Light/dark animica, Smelting elder rune bars, Cooking beltfish (see 7c), Cooking sharks, Hall of Memories, Abyss AFK combat (see 7c), Lesser necroplasm rituals (see 7c), Pickpocketing Menaphos market guards (see 7c).

7c. The methods whose content changes (show exactly these values):

**Gravitron research debris**
```json
"requirements": {
  "quests": [],
  "other": [],
  "skills": {},
  "unlocks": [{"id": "assistant-qualification", "text": "Assistant qualification (needed to enter the Stormguard Citadel dig site)"}]
},
"unverified": [
  "All available mattock upgrades (the 117k rate assumes them)",
  "Full archaeologist's outfit (the 117k rate assumes it)"
],
```
`notes`: delete the last sentence ` You confirmed on 2026-10-04 that you have the assistant qualification and use an imcando mattock.`

**Forging elder rune platebodies**
```json
"requirements": {
  "quests": [],
  "other": [],
  "skills": {},
  "unlocks": [{"id": "smithing-autoheater", "text": "Smithing autoheater for fully AFK forging (4,000 Dungeoneering tokens; needs 35 Smithing and 35 Dungeoneering)"}]
},
```

**Cooking beltfish** — `notes`: replace `The wiki shows a loss of 17,392,564 for the whole 80-90 step, but you only have about 220k XP of it left.` with `The wiki shows a loss of 17,392,564 for the whole 80-90 step.`

**Abyss AFK combat** — `unverified`: `["Your combat gear (the rate depends on gear)"]`

**Lesser necroplasm rituals** — `notes`: replace `needs 8 Multiply III glyphs at 103 Necromancy; you have 101.` with `needs 8 Multiply III glyphs at 103 Necromancy.`

**Pickpocketing Menaphos market guards** — `notes`:
- `Crystal Mask (90 Magic; you have 67) and Light Form (needs The Light Within; not started)` → `Crystal Mask (90 Magic) and Light Form (needs The Light Within)`
- delete ` Thieving is already 110, so the XP is a bonus.`
- `Sticky Fingers relic (recommended, needs 84 Archaeology): you said on 2026-10-04 you haven't unlocked it.` → `Sticky Fingers relic (recommended, needs 84 Archaeology).`

**Mining banite**
```json
"requirements": {
  "quests": [],
  "other": [],
  "skills": {"Mining": 99},
  "unlocks": []
},
```
`notes`: append ` The guide's setup includes a mining cape (needs 99 Mining), so 99 Mining is treated as required.`

**Harvesting vibrant energy**
```json
"requirements": {
  "quests": ["The World Wakes"],
  "other": [],
  "skills": {},
  "unlocks": [{"id": "divine-conversion-relic", "text": "Divine Conversion relic (unlocking it needs 98 Archaeology, 86 Invention and 85 Divination, all boostable)"}]
},
```
`notes`: replace `assumes the Divine Conversion relic, which you don't have yet.` with `assumes the Divine Conversion relic (its requirements are from https://runescape.wiki/w/Divine_Conversion, checked 2026-10-05).`

7d. Check nothing personal is left:

Run: `grep -n "you said\|you have [0-9]\|You confirmed\|you don't own\|you don't have yet\|Hels" data/methods.json`
Expected: no output.

Run: `python3 check_methods.py`
Expected: the three "OK" lines, the table (Gravitron, Forging and Vibrant show `1 to confirm`), "Extra levels needed" lists `Mining banite: Mining 99`, "Unlocks each player confirms" lists the three unlocks.

- [ ] **Step 8: Create Hels's answers** (from what Chris said on 2026-10-04: no autoheater, assistant qualification confirmed; no Divine Conversion relic)

```bash
mkdir -p "data/players/hels+glasglo"
cat > "data/players/hels+glasglo/answers.json" <<'EOF'
{
  "assistant-qualification": true,
  "divine-conversion-relic": false,
  "smithing-autoheater": false
}
EOF
git status --short   # answers.json must NOT appear (data/players/ is ignored)
```

- [ ] **Step 9: Prove the plans didn't change**

Run: `bash $SCRATCH/capture.sh $SCRATCH/after && diff -r $SCRATCH/before $SCRATCH/after`
Expected, and nothing else:
- Every `PATH A/B/C` `Method:` line identical in all four plan files.
- `Ruled out` lists name the same methods. Reason wording changes only for: Forging (`you said you don't have: Smithing autoheater ...`), Mining banite (`needs Mining 99 (you have 96)`), Harvesting vibrant energy (one `you said you don't have: Divine Conversion relic ...` instead of three lines).
- `Notes:` / `Watch:` lines change only where 7c changed the text.
- `check_methods.txt` changes in the table's Unlocks column, legend and the two gap lists.

Show Chris every changed line, grouped as above. Any other difference: stop and report.

- [ ] **Step 10: Commit**

```bash
git add data/methods.json check_methods.py plan_session.py app.py tests/test_check_methods.py tests/test_plan_session.py
git commit -m "Separate wiki facts from player answers in methods.json

missing -> requirements.skills (checked live) and requirements.unlocks
(answered per player in data/players/<name>/answers.json).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

**STOP: step 1a done. Show Chris the diff and test results; wait.**

---

### Task 4: `players.py` — names, current player, known players

**Files:**
- Modify: `players.py`, `tests/test_players.py`

**Interfaces:**
- Produces: `MAX_NAME_LENGTH = 12`; `check_name(text: str | None) -> (str | None, str | None)` returning `(name, None)` or `(None, problem)`; `read_current() -> str | None`; `save_current(name: str) -> None`; `known_players() -> list[str]`; `cli_player(given: str | None) -> str` (terminal only; exits with a message if no valid name).

- [ ] **Step 1: Add failing tests** to `tests/test_players.py` (above the `if __name__` line; add `import json` to the imports)

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: `AttributeError: module 'players' has no attribute 'check_name'` (and similar).

- [ ] **Step 3: Add to `players.py`**

Add `import re` and `import sys` to the imports, update the docstring's folder list with a line `data/players/current.txt remembers the player the app showed last.`, and add:

```python
# Name rules from the RuneScape Wiki "Display name" page: at most 12 characters;
# letters, numbers, spaces, hyphens and underscores. (New names can't START with
# - or _, but older names may, so that isn't rejected.)
MAX_NAME_LENGTH = 12
NAME_CHARACTERS = re.compile(r"[A-Za-z0-9 _-]+")


# ---------------------------------------------------------------------------
# Checking a typed name (before asking RuneMetrics anything)
# ---------------------------------------------------------------------------

def check_name(text):
    """Returns (cleaned name, None) if the name could be real, or (None, problem in plain words)."""
    name = (text or "").strip()
    if not name:
        return None, "Type a RuneScape name first."
    if len(name) > MAX_NAME_LENGTH:
        return None, f"RuneScape names are at most {MAX_NAME_LENGTH} characters; that one has {len(name)}."
    if not NAME_CHARACTERS.fullmatch(name):
        return None, "RuneScape names only use letters, numbers, spaces, hyphens (-) and underscores (_)."
    return name, None


# ---------------------------------------------------------------------------
# The current player (the one the app shows)
# ---------------------------------------------------------------------------

def read_current():
    """The remembered player's name, or None if none has been chosen yet."""
    try:
        name = (PLAYERS_DIR / "current.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return name or None


def save_current(name):
    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    (PLAYERS_DIR / "current.txt").write_text(name + "\n", encoding="utf-8")


def known_players():
    """
    Every player with at least one snapshot, A-Z. The name comes from their newest
    snapshot, so it has RuneMetrics' own capitals. (Snapshot file names start with
    the date and time, so the newest is the last one alphabetically.)
    """
    names = []
    for snapshots in sorted(PLAYERS_DIR.glob("*/snapshots")):
        newest = max(snapshots.glob("*.json"), default=None)
        if newest is None:
            continue
        try:
            names.append(json.loads(newest.read_text(encoding="utf-8"))["username"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            continue   # an unreadable snapshot just leaves that player off the list
    return sorted(names, key=str.lower)


# ---------------------------------------------------------------------------
# Terminal scripts: which player?
# ---------------------------------------------------------------------------

def cli_player(given=None):
    """
    The name typed on the command line if any, otherwise the remembered player,
    otherwise ask. Stops with a clear message if no valid name can be found.
    """
    if given:
        name, problem = check_name(given)
        if problem:
            sys.exit(f"Error: {problem}")
        return name
    remembered = read_current()
    if remembered:
        return remembered
    while True:
        try:
            text = input("RuneScape name: ")
        except EOFError:   # no keyboard attached
            sys.exit('Error: no player chosen. Give a name, e.g. --user "Some Player".')
        name, problem = check_name(text)
        if name:
            return name
        print(f"  {problem}")
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: all `OK` (24 + 16 = 40).

- [ ] **Step 5: Commit**

```bash
git add players.py tests/test_players.py
git commit -m "players.py: name checks, current player and known players

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Per-player snapshots and last goal; no hard-coded player (step 1b)

**Files:**
- Modify: `snapshots.py`, `quest_path.py`, `plan_session.py`, `rs3_planner.py`, `app.py` (two lines, interim), `.gitignore`
- Create: `tests/test_snapshots.py`, `tests/test_quest_path.py`
- Move (git-ignored files): `data/snapshots/*.json` → `data/players/hels+glasglo/snapshots/`; `.last_goal` (if present) → `data/players/hels+glasglo/last_goal`

**Interfaces:**
- Consumes: `player_dir`, `read_current`, `save_current`, `cli_player` (Tasks 2 and 4).
- Produces: `save_snapshot(username, profile, when=None) -> Path` (now in `player_dir(username)/"snapshots"`); `read_last_goal(username)`, `save_last_goal(username, name)`; `choose_goal(unlocks, quests, account, username, preset=None)`. `rs3_planner.DEFAULT_USERNAME` is removed.

- [ ] **Step 1: Write failing tests**

`tests/test_snapshots.py`:
```python
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
```

`tests/test_quest_path.py`:
```python
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
```

Run: `python3 -m unittest discover -s tests -v`
Expected: the snapshot test fails (wrong path), the last-goal tests fail (`TypeError: read_last_goal() takes 0 positional arguments`).

- [ ] **Step 2: `snapshots.py`**

- Docstring: `Files go to data/players/<player>/snapshots/YYYY-MM-DD_HHMM.json (see players.py; ...` (keep the rest).
- Replace `from pathlib import Path` with `from players import player_dir` and delete `SNAPSHOT_DIR = ...`.
- Replace the last three lines of `save_snapshot` with:

```python
    folder = player_dir(username) / "snapshots"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{when:%Y-%m-%d_%H%M}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 3: `quest_path.py`**

- Replace `from pathlib import Path` with `from players import player_dir`; delete `LAST_GOAL_FILE = ...`.
- Replace `read_last_goal` / `save_last_goal` with:

```python
def read_last_goal(username):
    """The big goal this player picked last time in the menu, or None."""
    try:
        return (player_dir(username) / "last_goal").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def save_last_goal(username, name):
    try:
        folder = player_dir(username)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "last_goal").write_text(name + "\n", encoding="utf-8")
    except OSError:
        pass   # remembering the choice is a convenience, not essential
```

- `choose_goal`: signature `def choose_goal(unlocks, quests, account, username, preset=None):`; `last = read_last_goal(username)`; `save_last_goal(username, unlocks[choice - 1]["name"])`.

- [ ] **Step 4: `rs3_planner.py`**

- Delete `DEFAULT_USERNAME = "Hels Glasglo"` (and the blank line after it).
- Docstring "How to run": `python3 rs3_planner.py   (the player you last chose in the app, or it asks)`.
- In `main()`, add `from players import cli_player` at the top of the file's imports block and replace the username line with:

```python
    # The name typed after the script, or the remembered player, or ask.
    # Joining the pieces lets "python3 rs3_planner.py Hels Glasglo" work without quotes too.
    username = cli_player(" ".join(sys.argv[1:]).strip() or None)
```

- [ ] **Step 5: `plan_session.py`**

- Import: replace `from rs3_planner import DEFAULT_USERNAME, load_profile, load_quests` with `from rs3_planner import load_profile, load_quests` and extend the players import to `from players import cli_player, read_answers`.
- `parser.add_argument("--user", help="RuneScape name (default: the player you last chose in the app)")`.
- First line of `main()` after `args = parser.parse_args()`: `username = cli_player(args.user)`; then use `username` instead of `args.user` in `load_profile`, `load_quests`, `read_answers`, the `Session plan for` print, and pass it to `choose_goal(unlocks, quests, account, username, preset=args.goal)`.

- [ ] **Step 6: `app.py` interim (Task 6 replaces this)**

Replace `DEFAULT_USERNAME, ` in the `rs3_planner` import with nothing, add `read_current` to the players import, and change `USERNAME = DEFAULT_USERNAME` to:

```python
USERNAME = read_current()   # temporary until the player screen arrives
```

- [ ] **Step 7: Run the tests**

Run: `python3 -m unittest discover -s tests -v` → all `OK` (43).
Run: `grep -rn "DEFAULT_USERNAME\|LAST_GOAL_FILE\|SNAPSHOT_DIR" --include=*.py . | grep -v .venv` → no output.

- [ ] **Step 8: Move Hels's files and remember her as current**

```bash
cd ~/Repos/RS-Planning-Tool
(cd data/snapshots && sha256sum *.json) > $SCRATCH/snapshots_before.sha
mkdir -p "data/players/hels+glasglo/snapshots"
mv data/snapshots/*.json "data/players/hels+glasglo/snapshots/"
rmdir data/snapshots
[ -f .last_goal ] && mv .last_goal "data/players/hels+glasglo/last_goal"
printf 'Hels Glasglo\n' > data/players/current.txt
(cd "data/players/hels+glasglo/snapshots" && sha256sum *.json) | diff $SCRATCH/snapshots_before.sha - && echo "all 8 snapshots identical"
```
Expected: `all 8 snapshots identical`.

- [ ] **Step 9: `.gitignore`** — delete the lines `.last_goal` and `data/snapshots/` (keep `data/players/`).

Run: `git status --short --ignored` → `data/players/` shown as ignored (`!!`); no snapshot or answers files listed as untracked.

- [ ] **Step 10: Prove it**

Run: `bash $SCRATCH/capture.sh $SCRATCH/after_1b && diff -r $SCRATCH/after $SCRATCH/after_1b && echo "identical to step 1a"`
Expected: `identical to step 1a`.

Run: `python3 rs3_planner.py | head -3` → `RuneMetrics planner for: Hels Glasglo` (remembered player, live fetch).

Run: `python3 -c "import players; print(players.known_players())"` → `['Hels Glasglo']`.

Start the app with the preview config `rs3-planner-gui`, open Home, press Refresh, then:
`ls "data/players/hels+glasglo/snapshots" | tail -1` → a new file with today's time. Stop the app.

- [ ] **Step 11: Commit**

```bash
git add snapshots.py quest_path.py rs3_planner.py plan_session.py app.py .gitignore tests/test_snapshots.py tests/test_quest_path.py
git commit -m "Per-player folders for snapshots and last goal; no hard-coded player

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

**STOP: step 1b done. Show Chris the checksum result and test output; wait.**

---

### Task 6: App — per-player cache, current player, `/player` screen

**Files:**
- Modify: `app.py`, `static/app.css`

**Interfaces:**
- Consumes: `check_name`, `folder_name`, `known_players`, `read_current`, `save_current` (players.py); `save_snapshot(username, profile, when)`.
- Produces (inside app.py): `CACHE: dict[folder name -> entry]`, entry = `{"name", "profile", "account", "fetched_at", "error"}`; `CURRENT = {"name": str | None}`; `async fetch_player(name) -> entry`; `current_entry() -> entry | None`.

- [ ] **Step 1: Docstring and imports**

Docstring: add `  players.py       which player: folders, answers, the remembered player` to the file list, and a paragraph: `Choose a player on the /player screen (any public RuneScape name). Each name is fetched once while the app runs, and again only when you press Refresh.`

Imports become:

```python
import copy
import datetime
import re
from pathlib import Path

from fastapi.responses import RedirectResponse   # sends a page to /player when no player is chosen
from nicegui import app, run, ui

from account import LEVEL_XP, read_account
from check_methods import load_methods, load_quest_files
from plan_session import build_plan, path_lines
from players import (
    check_name, folder_name, known_players, read_answers, read_current, save_answer, save_current,
)
from quest_path import difficulty_name, goal_progress, ranked_doable, skill_gaps, unlock_count
from rs3_planner import (
    INVENTION_ID, SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL,
    load_profile, load_quests, xp_needed_for_99,
)
from snapshots import save_snapshot
```

- [ ] **Step 2: Settings and state** — delete `USERNAME = ...` and the `STATE = ...` block; after `GOAL = ...` add:

```python
PASSWORD_NOTE = "Only your public RuneMetrics name. Never enter a password."
IRONMAN_NOTE = ("Ironman accounts aren't supported yet. Plans may suggest training or "
                "money methods an ironman can't use.")

# Live account data, one entry per player, keyed by folder_name() so "hels glasglo"
# and "Hels Glasglo" share one entry. Each name is fetched once while the app runs,
# and again only on Refresh, so we don't hammer the unofficial RuneMetrics API.
CACHE = {}

# The player every screen shows. A dict so functions can change it without "global".
# None until someone picks a player on the /player screen.
CURRENT = {"name": read_current()}
```

- [ ] **Step 3: Fetching** — replace the whole "Fetching" section with:

```python
def blank_entry(name):
    return {"name": name, "profile": None, "account": None, "fetched_at": None, "error": None}


def fetch_account(name):
    """Fetch profile and quests with the existing step 1 functions."""
    return load_profile(name), load_quests(name)


async def fetch_player(name):
    """
    Fetch one player from RuneMetrics into CACHE and save a snapshot.
    Returns their cache entry. If the fetch fails, "error" says why and any
    older stats are kept.
    """
    entry = CACHE.setdefault(folder_name(name), blank_entry(name))
    print(f"Fetching {name} from RuneMetrics")   # shows in the terminal, handy for checking the cache works
    try:
        # run.io_bound runs the slow download in the background so the page doesn't freeze.
        result = await run.io_bound(fetch_account, name)
    except SystemExit as err:
        # The existing fetch code stops with a plain message on errors; keep it to show.
        entry["error"] = str(err)
        return entry
    if result is None:   # the app is shutting down
        return entry
    profile, quest_data = result
    now = datetime.datetime.now()
    # RuneMetrics sends the name with its proper capitals; use that from now on.
    entry.update(name=profile.get("name", name), profile=profile,
                 account=read_account(profile, quest_data), fetched_at=now, error=None)
    save_snapshot(entry["name"], profile, now)
    return entry


def current_entry():
    """The current player's cache entry (empty until fetched), or None if no player is chosen."""
    name = CURRENT["name"]
    if not name:
        return None
    return CACHE.setdefault(folder_name(name), blank_entry(name))


async def fetch_current_on_startup():
    if CURRENT["name"]:
        await fetch_player(CURRENT["name"])

app.on_startup(fetch_current_on_startup)
```

- [ ] **Step 4: Helpers** — `updated_text`, `no_data_panel`, `on_refresh` become:

```python
def updated_text(entry):
    when = entry["fetched_at"]
    return f"Stats updated {when:%H:%M}, {when.day} {when:%b}" if when else f"Stats updated {NO_VALUE}"


def no_data_panel(entry):
    """Shown when there are no stats yet (e.g. RuneMetrics couldn't be reached)."""
    with panel():
        ui.label("No stats loaded").classes("heading")
        ui.label(entry["error"] or "RuneMetrics hasn't answered yet.").classes("muted")


async def on_refresh(button):
    button.disable()
    ui.notify("Fetching your stats from RuneMetrics…")
    await fetch_player(CURRENT["name"])
    ui.navigate.reload()
```

- [ ] **Step 5: Home** — start of `home_page` becomes (the cards below keep their code, reading `account`/`profile` from `entry`):

```python
@ui.page("/", title="RS3 Planner")
def home_page():
    entry = current_entry()
    if entry is None:   # nobody chosen yet: go and pick a player
        return RedirectResponse("/player")

    with ui.column().classes("page"):
        ui.label("RS3 Planner").classes("title")
        with ui.row().classes("row-line centered"):
            ui.label(entry["name"]).classes("subtitle")
            button("Switch player", on_click=lambda: ui.navigate.to("/player")).props(
                "unelevated no-caps").classes("btn-quiet")
        with ui.row().classes("row-line centered"):
            ui.label(updated_text(entry)).classes("muted")
            refresh_button = button("Refresh").props("unelevated no-caps").classes("btn-quiet")
            refresh_button.on_click(lambda: on_refresh(refresh_button))

        if entry["error"] and entry["account"]:
            with panel(crimson=True):
                ui.label("Last refresh failed - showing older stats").classes("label")
                ui.label(entry["error"]).classes("muted")

        account, profile = entry["account"], entry["profile"]
        if account is None:
            no_data_panel(entry)
            bottom_nav("Home")
            return
```

- [ ] **Step 6: `/play` and `/plan`** — first lines of each page function:

```python
    if current_entry() is None:
        return RedirectResponse("/player")
```

In `plan_page`, replace `account = STATE["account"]` … with:

```python
        entry = current_entry()
        if entry["account"] is None:
            no_data_panel(entry)
        elif session == "afk":
            afk_plan(entry, hours, minutes)
        else:
            active_plan(entry["account"], hours)
```

and `afk_plan` starts `def afk_plan(entry, hours, minutes):` with `account = entry["account"]` as its first line, building the plan with `read_answers(entry["name"])` (Task 7 adds error handling and the questions).

- [ ] **Step 7: The `/player` screen** — new section before "Start":

```python
# ---------------------------------------------------------------------------
# Screen 0: choose a player
# ---------------------------------------------------------------------------

@ui.page("/player", title="Choose player - RS3 Planner")
def player_page():
    message = {"text": "", "error": False}

    @ui.refreshable
    def message_area():
        if message["text"]:
            with panel(crimson=message["error"]):
                ui.label(message["text"]).classes("muted")

    def show(text, error):
        message.update(text=text, error=error)
        message_area.refresh()

    async def look_up(text):
        name, problem = check_name(text)
        if problem:   # caught here, before asking RuneMetrics anything
            show(problem, error=True)
            return
        entry = CACHE.get(folder_name(name))
        if entry is None or entry["account"] is None:   # not fetched yet this run
            look_button.disable()
            show(f"Fetching {name} from RuneMetrics…", error=False)
            entry = await fetch_player(name)
            look_button.enable()
        if entry["account"] is None:
            # Private, unknown, or no internet: say why and keep the current player.
            show(entry["error"] or "RuneMetrics didn't answer. Try again.", error=True)
            return
        CURRENT["name"] = entry["name"]
        save_current(entry["name"])
        ui.navigate.to("/")

    with ui.column().classes("page"):
        if CURRENT["name"]:
            back_button("/")
        ui.label("Choose player").classes("title")
        with panel():
            ui.label("RuneScape name").classes("label")
            name_box = ui.input(placeholder="Your RuneScape name").props("outlined dark").classes("name-input")
            name_box.on("keydown.enter", lambda: look_up(name_box.value))
            ui.label(PASSWORD_NOTE).classes("muted small")
        message_area()
        look_button = button("Look up", on_click=lambda: look_up(name_box.value)).props(
            "unelevated no-caps").classes("btn-crimson")

        names = known_players()
        if names:
            with panel():
                ui.label("Recent players").classes("label green")
                for name in names:
                    current = CURRENT["name"] and folder_name(name) == folder_name(CURRENT["name"])
                    button(name, on_click=lambda n=name: look_up(n)).props("unelevated no-caps").classes(
                        "chip wide" + (" selected" if current else ""))

        ui.label(IRONMAN_NOTE).classes("muted small")
```

- [ ] **Step 8: CSS** — append to `static/app.css`:

```css
/* ---- Text box (player name) ---- */
.name-input { width: 100%; }
.name-input .q-field__control { background: var(--forest); border-radius: 10px; min-height: 48px; color: var(--glacial) !important; }
.name-input .q-field__native { color: var(--parchment); font-family: "Alegreya", Georgia, serif; font-size: 17px; }
.name-input .q-field__native::placeholder { color: var(--muted); opacity: 1; }
.name-input .q-field__control:before { border-color: var(--frame-outer) !important; }

/* A chip as wide as its panel, text on the left (recent players list). */
.q-btn.chip.wide { width: 100%; }
.q-btn.chip.wide .q-btn__content { justify-content: flex-start; }
```

- [ ] **Step 9: Verify in the built-in browser** (preview `rs3-planner-gui`; restart after edits)

0. `grep -n "STATE\|USERNAME" app.py` → no output (every old reference replaced); `python3 -m unittest discover -s tests -v` → all OK.
1. Home shows "Hels Glasglo" + Switch player; sanity values (live data permitting): XP to go ≈ 269M, Max cape ≈ 32.9%, 4 of 29 at 99, Mining closest, Plague's End 1 of 15, 4 of 10 below 75. Server log shows exactly one `Fetching Hels Glasglo`.
2. `/player`: type `AAAAAAAAAAAAA` (13) → crimson "at most 12 characters" message; log shows no new fetch.
3. Type `Hels@Glasglo` → characters message; no fetch.
4. Type `Zz9 Qq8 Xx7` (valid format, made up) → crimson panel with RuneMetrics' message; `cat data/players/current.txt` still `Hels Glasglo`; Back → Home still Hels. (Review Focus 5)
5. Type the second test player's name (given by Chris in chat; never written into the repo) in lower case → Home shows it with RuneMetrics' capitals; their folder under `data/players/` has one snapshot; `current.txt` holds their name.
6. Switch player → "Recent players" lists Hels Glasglo and the second test player (current one highlighted) → tap Hels → Home instantly; log shows no second `Fetching Hels Glasglo`.
7. Text box focus outline is glacial, not Quasar blue; at 375px wide nothing scrolls sideways.
8. Start-up failure (Review Focus 4): stop app, `printf 'Zz9 Qq8 Xx7\n' > data/players/current.txt`, start app → Home shows "No stats loaded" + RuneMetrics' message and Switch player works; pick Hels from Recent players. Confirm `current.txt` is back to `Hels Glasglo`.
9. Private profile: test only if a known private profile can be found; otherwise report "private-profile path untested; uses the same error display as step 4".

Screenshots of steps 1, 4, 5 and 6 for Chris.

- [ ] **Step 10: Commit**

```bash
git add app.py static/app.css
git commit -m "App: choose any public player; per-player cache and remembered player

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: App — answering unlocks on the AFK plan

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `build_plan(..., answers)` and `method["_unanswered"]` (Task 3); `read_answers`, `save_answer` (Task 2).

- [ ] **Step 1: Unlock wording lookup** — after the `IRONMAN_NOTE` lines add:

```python
# Every unlock id in methods.json -> its wording, for the "Your answers" list.
UNLOCK_TEXTS = {u["id"]: u["text"] for m in METHODS for u in m["requirements"]["unlocks"]}
```

- [ ] **Step 2: Replace `afk_plan`** with:

```python
def afk_plan(entry, hours, minutes):
    account, name = entry["account"], entry["name"]
    ui.label("Your AFK plan").classes("title")
    ui.label(f"{hours:g} hours · a click at most every {minutes:g} min").classes("muted")

    try:
        answers = read_answers(name)
    except ValueError as err:   # a broken answers.json: say so instead of crashing
        with panel(crimson=True):
            ui.label("Your answers file can't be read").classes("label")
            ui.label(str(err)).classes("muted")
        return

    # The same function the terminal uses; a copy so each visit starts fresh.
    plan = build_plan(copy.deepcopy(METHODS), account, minutes, answers)
    for (letter, path_name), (_, method, why) in zip(PATH_NAMES, plan["paths"]):
        with panel():
            ui.label(f"{letter} · {path_name}").classes("label")
            if method is None:
                ui.label("Nothing in the methods file fits this session.").classes("muted")
                continue
            ui.label(method["name"]).classes("heading")
            ui.label(method["skill"]).classes("muted small")
            for label, text in path_lines(method, account, hours):
                text = text.replace(" -> ", " → ")
                ui.label(f"{label}: {text}" if label else text).classes("" if label else "muted small")
            ui.label(why).classes("muted small")
            for warning in method["_warnings"]:
                ui.label(f"Watch: {warning}").classes("muted small")
            for unlock in method["_unanswered"]:
                unlock_question(name, unlock)

    your_answers(name, answers)


def answer_and_redraw(name, unlock_id, has_it):
    save_answer(name, unlock_id, has_it)
    ui.navigate.reload()   # redraw the plan: "I don't" may change which method is picked


def unlock_question(name, unlock):
    """'Check: needs X' with two buttons. RuneMetrics can't see this, so the player answers."""
    ui.label(f"Check: needs {unlock['text']}").classes("muted small")
    with ui.row().classes("gap-2"):
        button("I have it", on_click=lambda: answer_and_redraw(name, unlock["id"], True)).props(
            "unelevated no-caps").classes("chip")
        button("I don't", on_click=lambda: answer_and_redraw(name, unlock["id"], False)).props(
            "unelevated no-caps").classes("chip")


def your_answers(name, answers):
    """Every saved answer with a Change button, so a wrong tap can be undone."""
    saved = [(uid, has_it) for uid, has_it in sorted(answers.items()) if uid in UNLOCK_TEXTS]
    if not saved:
        return
    with panel():
        ui.label("Your answers").classes("label green")
        for uid, has_it in saved:
            ui.label(f"{'You have' if has_it else 'You don’t have'}: {UNLOCK_TEXTS[uid]}").classes("muted small")
            button("Change", on_click=lambda u=uid: answer_and_redraw(name, u, None)).props(
                "unelevated no-caps").classes("btn-quiet")
```

- [ ] **Step 3: Verify in the built-in browser** (restart the app)

1. Hels, `/plan?hours=5&session=afk&minutes=2` → same three methods as before this task; "Your answers" lists 3 answers.
2. Switch to the second test player → AFK plan: whatever is picked, any path with an unlock shows "Check: needs …" + I have it / I don't (if none of their picked methods has an unlock, say so and test step 3 on Hels after pressing Change on "smithing autoheater").
3. Tap **I don't** → page redraws, that method is no longer picked, `cat data/players/<folder>/answers.json` shows `false`; "Your answers" shows it; **Change** → it's unanswered again and the file no longer has it. (Review Focus 3)
4. Broken file (Review Focus 2): `cp` the player's answers.json aside, write `{oops` into it, reload → crimson "Your answers file can't be read" panel naming the file; restore the copy.
5. Every button ≥44px tall (javascript_tool: `getComputedStyle` height), 375px wide no sideways scroll.
6. Restore Hels's answers to `{"assistant-qualification": true, "divine-conversion-relic": false, "smithing-autoheater": false}` and confirm with `cat`.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "App: answer unlocks RuneMetrics can't see, and change answers later

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: README and final check (step 1c)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README edits**

- Intro sentence: "It reads a player's **public** RuneMetrics data" stays; add after the bullet list: `Plans assume a regular account. Ironman accounts aren't supported yet. Plans may suggest training or money methods an ironman can't use.`
- "Browser app" section, after "Then open …": 

```markdown
**Choosing a player:** the first time, the app asks for a RuneScape name. Only the
public RuneMetrics name is needed — never enter a password. Press **Switch player**
on Home to look up someone else; players you've looked up before are one tap away.
```

- Replace the bullet about snapshots with: `- Every fetch saves a snapshot to data/players/<player>/snapshots/ (kept out of git) for a future Progress screen.`
- "How to run the terminal version": replace "That uses the default player, **Hels Glasglo**." with "That uses the player you last chose in the app (or asks for a name)."
- "Planning a session": add `--user "Some Player"` to the example list, and replace the paragraph "When you unlock something listed under `missing` …" with:

```markdown
Some methods need things RuneMetrics can't see, like a smithing autoheater. The
plan shows "Check: needs …" with **I have it** / **I don't**; your answers are saved
in `data/players/<player>/answers.json` (kept out of git) and can be changed under
**Your answers**. "I don't" rules the method out. Levels and quests are checked
automatically.
```

- "The quest path": "Enter keeps your last choice" → "Enter keeps your last choice (remembered per player)".
- New section before "Good to know":

```markdown
## Tests

```bash
python3 -m unittest discover -s tests -v
```

Runs the automatic checks (standard Python, nothing to install). They never use
the internet or your real player files.
```

- [ ] **Step 2: Final full check**

Run: `python3 -m unittest discover -s tests -v` → all OK.
Run: `python3 check_methods.py` → passes.
Run: `bash $SCRATCH/capture.sh $SCRATCH/final && diff -r $SCRATCH/after_1b $SCRATCH/final && echo "terminal output unchanged since 1b"`.
Run: `git status --short --ignored` → no player files tracked; `data/players/` ignored.
Browser: Home for Hels once more (screenshot).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "README: choosing a player, answers, ironman note, tests

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

**STOP: step 1c done. Show Chris screenshots, test output and `git log`; ask before pushing.**
