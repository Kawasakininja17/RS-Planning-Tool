# Path A: Next Level Implementation Plan

> **Changed after this plan was written (2026-10-09):** the "XP left" round-UP rule below (Global Constraints, Review Focus 1, Task 2's why-line code and `test_why_line_never_says_0_xp_left`, which expected `(1 XP left)`) was replaced during Task 3, as Chris chose. XP left is now rounded like the "N hours" line, and reads `under 1` instead of `0`. `percent_text` also tidies floating-point noise before rounding down. See the spec's `xp_left_text` section; the code and tests are the record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Path A ("Finish something") picks the skill furthest through its current level (its next level-up), with the next two skills as "Also good"; levels past 99 count up to 120; Invention gets the wiki's elite XP table.

**Architecture:** `account.py` gains the elite table and one question-answerer, `level_progress(account, skill)`; every level calculation picks its table through `level_table(skill)`. `plan_session.py` swaps "closest to 99" for `closest_skill` (stored as `method["_closest"]`), the "already 99" rule for "already 120", and gives path A three different skills. The app and the terminal both use `build_plan`, so both follow; only one app line and some docs change wording.

**Tech Stack:** Python 3.14; standard library `unittest` for tests; NiceGUI 3.17.1 in `.venv/` only for the before/after copies; the built-in browser for page texts.

**Spec:** `docs/superpowers/specs/2026-10-09-path-a-next-level-design.md`

## Global Constraints

- "Closest" = furthest through the current level: `(xp − table[level−1]) ÷ (table[level] − table[level−1])`. Tie: higher `xp_per_hour_low` wins.
- A **training** method is ruled out as finished (`ALREADY_120 = "already 120"`) only when **every** skill it trains is at 120. Money methods are never ruled out for level.
- Path A's pick and its two alternatives are three **different** skills (the skill that counts is `method["_closest"]["skill"]`). No method appears twice on the page (A's list first, then B's, then C's).
- Two-skill methods count by the skill furthest through its level; on an exact tie, the skill named first.
- Titles stay: `PATH A: finish something` (terminal), `("A", "Finish something")` in `PATH_NAMES` (app).
- Why line, exactly: `{skill} is {percent} of the way to {next level} ({XP left, rounded UP, with commas} XP left): the furthest of your skills with a ready method.` Percent: one decimal, rounded DOWN, e.g. `83.9%`.
- `ELITE_LEVEL_XP` numbers are wiki facts: RuneScape Wiki, Experience/Table, "Elite skills" table, read as page text in the built-in browser on 2026-10-09; re-checked against the page in Task 1.
- Home's "Closest to 99" panel, Skills, Quests, Big goal, Progress, Choose player, Ready to play and the Active plan must not change. Paths B and C keep their rules; they may show different methods only because 99–119 skills' methods return, or because A takes or frees a method.
- Code is simple and commented in plain words, matching the existing files. Tests: standard library only, no network, never touch real player files.
- Tests: `python3 -m unittest discover -s tests -v` from the project folder (209 before; 222 after Task 1; 236 after Task 2). Data check: `python3 check_methods.py` (81 methods, unchanged).
- Scratch: `W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a` (git-ignored), never `/tmp`. Copies and frozen replies are deleted at the end (they hold copies of Chris's data).
- Chris's service holds port 8080: Claude's copies use 8091. Never stop, restart or reinstall `rs3-planner` without Chris's OK. Tell Chris whenever a preview server is running.
- RuneMetrics: exactly one profile fetch and one quests fetch for the whole plan (Task 3 Step 1).
- No other player's name in the repo, commits or messages. Only the `hels+glasglo` folder is copied into scratch. Tests use no real player names. The service log is never quoted.
- Stop and wait for Chris after each task. Commit after each task; never push without asking. Commit messages: a title line, a blank line, the body, and end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- If any step errors or a check doesn't match, stop that task, explain (what failed, the error in plain words, likely cause, what's done, what's left, the proper fix) and wait for Chris.

## Review Focus

1. **A skill a fraction of an XP short of its next level** (RuneMetrics XP has tenths) → the why line must not say `100.0%` or `(0 XP left)`; it says `99.9%` and `(1 XP left)`. Pinned in Task 2 (`test_why_line_never_says_0_xp_left`).
2. **Floating-point rounding in the percentage** (e.g. a fraction of exactly 0.29 must show `29.0%`, not `28.9%`) → pinned in Task 2 (`test_keeps_exact_values`).
3. **A future Invention method** → its level, progress and "N hours gets you" line use the elite table, not the normal one. Pinned in Task 1 (`test_invention_uses_the_elite_table`, `test_level_from_xp_for_invention_uses_the_elite_curve`) and Task 2 (`test_level_change_text_uses_elite_for_invention`).
4. **A two-skill method where one skill is at 120** → stays ready and counts by the other skill (no crash, not "finished"). Pinned in Task 2 (`test_skill_at_120_is_skipped_but_the_method_stays`).
5. **A skill at 120 with a money method** → the money method stays available to path C. Pinned in Task 2 (`test_every_skill_at_120_is_finished`, last part).

## File map

| File | Change | Responsibility |
|---|---|---|
| `account.py` | modify | `ELITE_LEVEL_XP`, `level_table`, `level_from_xp(xp, skill=None)`, curve-aware `xp_to_level`, `read_account` (Invention from XP), `level_progress`; one stale comment in `skill_rows` |
| `tests/test_account.py` | modify | `make_account` works Invention out from XP; Invention expectation 85 → 79; new `EliteTableTests`, `LevelProgressTests`, `ReadAccountTests` |
| `plan_session.py` | modify | Docstring; imports; `ALREADY_120`; the 120 rule; `closest_skill`, `closest_first`; `pick_paths` A; `runner_ups` A's different skills; `percent_text`; why line; `split_ruled_out`; curve-aware `level_change_text` |
| `tests/test_plan_session.py` | modify | Curve-aware helpers; `ready_method` carries `_closest`; `RunnerUpTests` fixture; `SplitRuledOutTests` to 120; new `PathATests`, `FinishedRuleTests`, `PercentTextTests`, `WhyLineTests`, `LevelChangeTextTests` and three runner-up tests |
| `app.py` | modify | One line: `finished (99)` → `finished (120)` |
| `README.md` | modify | Lines ~147, ~257, ~264 |
| `SPEC.md` | modify | One line under the AFK path table |

Scratch only (never committed), in `$W`: `frozen/`, `data_template/`, `run_frozen.py` (copied from `.superpowers/sdd/host-lock/`), `before/` and `after/` (project copies on 8091), `before.sha`, `after.txt`, `term_before.txt`, `term_after.txt`. `.claude/launch.json` (git-excluded) gets two preview entries, removed in Task 4.

---

### Task 1: The level knowledge (`account.py`)

**Files:**
- Modify: `account.py`
- Test: `tests/test_account.py`

**Interfaces:**
- Consumes: `rs3_planner.SKILL_NAMES`, `XP_FOR_99_ELITE`, `XP_FOR_99_NORMAL` (unchanged).
- Produces (used by Task 2):
  - `ELITE_LEVEL_XP: list[int]` (120 entries; `[0]` is level 1, `[98]` level 99, `[119]` level 120)
  - `level_table(skill: str | None = None) -> list[int]` (`ELITE_LEVEL_XP` for `"Invention"`, else `LEVEL_XP`)
  - `level_from_xp(xp: float, skill: str | None = None) -> int`
  - `xp_to_level(account, skill_name: str, level: int) -> float` (now curve-aware)
  - `level_progress(account, skill_name: str) -> dict | None`, the dict being `{"skill": str, "level": int, "next_level": int, "fraction": float, "xp_left": float}`; `None` at 120.

- [ ] **Step 1: Re-check the elite numbers against the wiki page**

In the built-in browser, `navigate` to `https://runescape.wiki/w/Experience/Table`, then run with `javascript_tool`:

```js
// The elite table is the only one whose header row reads "Levels 1–30 … Levels 91–120".
const elite = [...document.querySelectorAll('table')].find(t =>
  t.rows[0].innerText.includes('Levels 1') && t.rows[0].innerText.includes('Levels 91'));
const pairs = {};
for (const r of elite.rows) {
  const c = [...r.cells].map(x => x.innerText.trim());
  for (let i = 0; i + 1 < c.length; i++)
    if (/^\d+$/.test(c[i]) && /^[\d,]+$/.test(c[i + 1]) && +c[i] >= 1 && +c[i] <= 120 && !(c[i] in pairs))
      pairs[c[i]] = +c[i + 1].replace(/,/g, '');
}
const got = Object.keys(pairs).map(Number).sort((a, b) => a - b).map(k => pairs[k]);
const want = [0,830,1861,2902,3980,5126,6380,7787,9400,11275,13605,16372,19656,23546,28134,33520,39809,47109,55535,65209,77190,90811,106221,123573,143025,164742,188893,215651,245196,277713,316311,358547,404634,454796,509259,568254,632019,700797,774834,854383,946227,1044569,1149696,1261903,1381488,1508756,1644015,1787581,1939773,2100917,2283490,2476369,2679917,2894505,3120508,3358307,3608290,3870846,4146374,4435275,4758122,5096111,5449685,5819299,6205407,6608473,7028964,7467354,7924122,8399751,8925664,9472665,10041285,10632061,11245538,11882262,12542789,13227679,13937496,14672812,15478994,16313404,17176661,18069395,18992239,19945833,20930821,21947856,22997593,24080695,25259906,26475754,27728955,29020233,30350318,31719944,33129852,34580790,36073511,37608773,39270442,40978509,42733789,44537107,46389292,48291180,50243611,52247435,54303504,56412678,58575824,60793812,63067521,65397835,67785643,70231841,72737330,75303019,77929820,80618654];
[got.length, JSON.stringify(got) === JSON.stringify(want) ? 'all 120 match' : 'MISMATCH at level ' + (got.findIndex((v, i) => v !== want[i]) + 1)]
```

Expected: `[120, "all 120 match"]`. (The table found is the one whose header row reads "Levels 1–30 … Levels 91–120", under the page's "Elite skills" heading; the normal table there has a different header.) Anything else: stop and report.

- [ ] **Step 2: Write the failing tests**

In `tests/test_account.py`:

1. Replace the docstring and imports at the top with:

```python
"""The level knowledge (XP tables, level_progress) and the Skills screen's list."""

import unittest

from account import (
    ELITE_LEVEL_XP, LEVEL_XP, level_from_xp, level_progress, level_table, read_account,
    skill_rows, xp_to_99, xp_to_level,
)
from rs3_planner import INVENTION_ID, SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL
```

2. Replace `make_account` with:

```python
def make_account(xp_by_skill):
    """
    A pretend account in the same shape read_account() makes. Skills not named
    get 0 XP. Every level comes from XP, Invention's from its own elite table,
    like the real code.
    """
    skills = {}
    for name in SKILL_NAMES:
        xp = xp_by_skill.get(name, 0.0)
        skills[name] = {"xp": xp, "level": level_from_xp(xp, name)}
    return {"skills": skills, "completed_quests": set(), "quests": {}}
```

3. In `SkillRowsTests.setUp`, change `make_account(SOME_PLAYER, invention_level=85)` to `make_account(SOME_PLAYER)`.

4. Replace `test_invention_uses_the_elite_curve` and `test_invention_past_99_shows_99_plus` with:

```python
    def test_invention_uses_the_elite_curve(self):
        # 14.3M XP would be 99 on the normal curve, but on the elite curve it is 79
        # (and 99 needs 36,073,511).
        invention = self.by_name["Invention"]
        self.assertFalse(invention["done"])
        self.assertEqual(invention["level_text"], "79")
        self.assertEqual(invention["xp_left"], XP_FOR_99_ELITE - 14_292_017.8)

    def test_invention_past_99_shows_99_plus(self):
        # The Skills screen has always said "99+" here (40M XP is elite level 101);
        # showing the exact level would be a separate change.
        rows = skill_rows(make_account({"Invention": 40_000_000.0}))
        invention = next(row for row in rows if row["name"] == "Invention")
        self.assertTrue(invention["done"])
        self.assertEqual(invention["level_text"], "99+")
```

5. Add these classes before `if __name__ == "__main__":`

```python
class EliteTableTests(unittest.TestCase):
    def test_120_levels_each_needing_more_xp(self):
        self.assertEqual(len(ELITE_LEVEL_XP), 120)
        self.assertEqual(ELITE_LEVEL_XP[0], 0)
        self.assertTrue(all(a < b for a, b in zip(ELITE_LEVEL_XP, ELITE_LEVEL_XP[1:])))

    def test_matches_the_figures_we_already_trust(self):
        self.assertEqual(ELITE_LEVEL_XP[98], XP_FOR_99_ELITE)   # 36,073,511
        self.assertEqual(ELITE_LEVEL_XP[119], 80_618_654)        # level 120, from the wiki

    def test_level_table_picks_by_skill(self):
        self.assertIs(level_table("Invention"), ELITE_LEVEL_XP)
        self.assertIs(level_table("Mining"), LEVEL_XP)
        self.assertIs(level_table(None), LEVEL_XP)

    def test_level_from_xp_without_a_skill_uses_the_normal_curve(self):
        self.assertEqual(level_from_xp(XP_FOR_99_NORMAL), 99)
        self.assertEqual(level_from_xp(XP_FOR_99_NORMAL - 0.1), 98)

    def test_level_from_xp_for_invention_uses_the_elite_curve(self):
        self.assertEqual(level_from_xp(XP_FOR_99_ELITE, "Invention"), 99)
        self.assertEqual(level_from_xp(XP_FOR_99_ELITE - 0.1, "Invention"), 98)
        self.assertEqual(level_from_xp(14_292_017.8, "Invention"), 79)
        self.assertEqual(level_from_xp(14_292_017.8, "Mining"), 99)   # same XP, normal curve

    def test_xp_to_level_for_invention(self):
        account = make_account({"Invention": 14_292_017.8})
        self.assertAlmostEqual(xp_to_level(account, "Invention", 80), 14_672_812 - 14_292_017.8)


class LevelProgressTests(unittest.TestCase):
    def test_start_of_a_level(self):
        progress = level_progress(make_account({"Mining": float(LEVEL_XP[95])}), "Mining")   # exactly 96
        self.assertEqual(progress, {"skill": "Mining", "level": 96, "next_level": 97,
                                    "fraction": 0.0, "xp_left": LEVEL_XP[96] - LEVEL_XP[95]})

    def test_part_way_through(self):
        width = LEVEL_XP[96] - LEVEL_XP[95]   # XP from 96 to 97
        progress = level_progress(make_account({"Mining": LEVEL_XP[95] + 0.25 * width}), "Mining")
        self.assertEqual((progress["level"], progress["next_level"]), (96, 97))
        self.assertAlmostEqual(progress["fraction"], 0.25)
        self.assertAlmostEqual(progress["xp_left"], 0.75 * width)

    def test_last_xp_before_the_next_level(self):
        progress = level_progress(make_account({"Mining": LEVEL_XP[96] - 0.1}), "Mining")
        self.assertEqual(progress["level"], 96)
        self.assertLess(progress["fraction"], 1)
        self.assertAlmostEqual(progress["xp_left"], 0.1)

    def test_level_119_points_at_120(self):
        progress = level_progress(make_account({"Woodcutting": float(LEVEL_XP[118])}), "Woodcutting")
        self.assertEqual((progress["level"], progress["next_level"]), (119, 120))
        self.assertEqual(progress["xp_left"], LEVEL_XP[119] - LEVEL_XP[118])

    def test_level_120_has_no_next_level(self):
        self.assertIsNone(level_progress(make_account({"Woodcutting": float(LEVEL_XP[119])}), "Woodcutting"))
        self.assertIsNone(level_progress(make_account({"Woodcutting": 200_000_000.0}), "Woodcutting"))

    def test_invention_uses_the_elite_table(self):
        progress = level_progress(make_account({"Invention": 14_292_017.8}), "Invention")
        self.assertEqual((progress["level"], progress["next_level"]), (79, 80))
        self.assertAlmostEqual(progress["xp_left"], 14_672_812 - 14_292_017.8)
        self.assertAlmostEqual(progress["fraction"],
                               (14_292_017.8 - 13_937_496) / (14_672_812 - 13_937_496))


class ReadAccountTests(unittest.TestCase):
    def test_levels_come_from_xp_invention_on_its_own_table(self):
        # RuneMetrics' own "level" is deliberately wrong here (50): it must be ignored.
        profile = {"skillvalues": [{"id": i, "xp": 0, "level": 50} for i in range(len(SKILL_NAMES))]}
        profile["skillvalues"][INVENTION_ID]["xp"] = 142_920_178   # RuneMetrics' x10: 14,292,017.8 XP
        profile["skillvalues"][SKILL_NAMES.index("Mining")]["xp"] = 142_920_178
        account = read_account(profile, {"quests": []})
        self.assertEqual(account["skills"]["Invention"]["level"], 79)
        self.assertEqual(account["skills"]["Mining"]["level"], 99)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `python3 -m unittest tests.test_account -v 2>&1 | tail -5`
Expected: an `ImportError` naming `ELITE_LEVEL_XP` (the module can't load yet).

- [ ] **Step 4: Write the code in `account.py`**

1. Imports: change `from rs3_planner import INVENTION_ID, SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL` to

```python
from rs3_planner import SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL
```

2. Replace everything from the line `# LEVEL_XP[0] is level 1, LEVEL_XP[98] is level 99, LEVEL_XP[119] is level 120.` down to the end of `level_from_xp` with:

```python
# LEVEL_XP[0] is level 1, LEVEL_XP[98] is level 99, LEVEL_XP[119] is level 120.
LEVEL_XP = [xp_for_level(level) for level in range(1, 121)]

# Invention is an "elite" skill with its own, steeper XP curve, so it has its own
# table. Typed in from the RuneScape Wiki's "Experience/Table" page ("Elite skills"
# table), read 2026-10-09. Same layout as LEVEL_XP: [0] is level 1, [98] is level 99
# (36,073,511 XP), [119] is level 120 (the elite skill's top level).
ELITE_LEVEL_XP = [
    0, 830, 1_861, 2_902, 3_980, 5_126, 6_380, 7_787, 9_400, 11_275,   # levels 1-10
    13_605, 16_372, 19_656, 23_546, 28_134, 33_520, 39_809, 47_109, 55_535, 65_209,   # 11-20
    77_190, 90_811, 106_221, 123_573, 143_025, 164_742, 188_893, 215_651, 245_196, 277_713,   # 21-30
    316_311, 358_547, 404_634, 454_796, 509_259, 568_254, 632_019, 700_797, 774_834, 854_383,   # 31-40
    946_227, 1_044_569, 1_149_696, 1_261_903, 1_381_488,
    1_508_756, 1_644_015, 1_787_581, 1_939_773, 2_100_917,   # 41-50
    2_283_490, 2_476_369, 2_679_917, 2_894_505, 3_120_508,
    3_358_307, 3_608_290, 3_870_846, 4_146_374, 4_435_275,   # 51-60
    4_758_122, 5_096_111, 5_449_685, 5_819_299, 6_205_407,
    6_608_473, 7_028_964, 7_467_354, 7_924_122, 8_399_751,   # 61-70
    8_925_664, 9_472_665, 10_041_285, 10_632_061, 11_245_538,
    11_882_262, 12_542_789, 13_227_679, 13_937_496, 14_672_812,   # 71-80
    15_478_994, 16_313_404, 17_176_661, 18_069_395, 18_992_239,
    19_945_833, 20_930_821, 21_947_856, 22_997_593, 24_080_695,   # 81-90
    25_259_906, 26_475_754, 27_728_955, 29_020_233, 30_350_318,
    31_719_944, 33_129_852, 34_580_790, 36_073_511, 37_608_773,   # 91-100
    39_270_442, 40_978_509, 42_733_789, 44_537_107, 46_389_292,
    48_291_180, 50_243_611, 52_247_435, 54_303_504, 56_412_678,   # 101-110
    58_575_824, 60_793_812, 63_067_521, 65_397_835, 67_785_643,
    70_231_841, 72_737_330, 75_303_019, 77_929_820, 80_618_654,   # 111-120
]


def level_table(skill=None):
    """The XP table a skill uses: the elite one for Invention, the normal one otherwise."""
    return ELITE_LEVEL_XP if skill == "Invention" else LEVEL_XP


def level_from_xp(xp, skill=None):
    """
    The highest level (1-120) whose XP requirement this XP has reached.
    skill picks the table (Invention has its own); leave it out for the normal one.
    """
    level = 1
    for index, needed in enumerate(level_table(skill)):
        if xp >= needed:
            level = index + 1
    return level
```

3. In `read_account`, replace the block from `xp = skill["xp"] / 10   # RuneMetrics stores XP multiplied by 10` to `level = level_from_xp(xp)` (the `if skill["id"] == INVENTION_ID:` … `else:` lines) with:

```python
        xp = skill["xp"] / 10   # RuneMetrics stores XP multiplied by 10
        # Levels come from XP, not RuneMetrics' own "level" (unreliable past 99).
        # Invention uses its own elite table (see level_table).
        level = level_from_xp(xp, name)
```

4. Replace `xp_to_level` with:

```python
def xp_to_level(account, skill_name, level):
    """XP still needed to reach a level (0 if already there)."""
    return max(0, level_table(skill_name)[level - 1] - account["skills"][skill_name]["xp"])


def level_progress(account, skill_name):
    """
    How far through its current level a skill is (used by path A of the planner):
      {"skill", "level", "next_level", "fraction", "xp_left"}
    fraction is 0 at the start of the level and just under 1 right before the next;
    xp_left is the XP still needed for next_level.
    Returns None at 120: the XP tables stop there, so there is no next level.
    """
    table = level_table(skill_name)
    level = account["skills"][skill_name]["level"]
    if level >= len(table):
        return None
    xp = account["skills"][skill_name]["xp"]
    start, end = table[level - 1], table[level]   # XP for this level, and for the next
    return {"skill": skill_name, "level": level, "next_level": level + 1,
            "fraction": (xp - start) / (end - start), "xp_left": end - xp}
```

5. In `skill_rows`, replace the two comment lines above `level_text = "99+"`:

```python
            # The Skills screen has always shown "99+" for Invention past 99;
            # showing its exact level is a separate change.
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `python3 -m unittest tests.test_account -v 2>&1 | tail -3` → `OK`.
Run: `python3 -m unittest discover -s tests 2>&1 | tail -3` → `Ran 222 tests`, `OK`.
Run: `grep -rn "INVENTION_ID" account.py` → nothing (the import is gone and nothing else used it there).

- [ ] **Step 6: Break it on purpose, then restore**

In `level_table`, change the body to `return LEVEL_XP`. Run `python3 -m unittest tests.test_account 2>&1 | tail -3` → `FAILED` (the Invention tests, among them `test_invention_uses_the_elite_table`). Restore the line, run again → `OK`.

- [ ] **Step 7: Commit**

```bash
git add account.py tests/test_account.py
git commit -F - <<'EOF'
Path A next level: the elite XP table and level_progress

account.py gains Invention's elite XP table (wiki, Experience/Table),
level_table to pick a skill's table, and level_progress (how far through
its current level a skill is; None at 120). Invention's level now comes
from its XP like every other skill. No screen changes.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

Stop and wait for Chris.

---

### Task 2: The planner (`plan_session.py`), and the wording

**Files:**
- Modify: `plan_session.py`
- Modify: `app.py:925`
- Modify: `README.md` (~147, ~257, ~264), `SPEC.md` (under the AFK path table)
- Test: `tests/test_plan_session.py`

**Interfaces:**
- Consumes (from Task 1): `level_table(skill)`, `level_from_xp(xp, skill)`, `level_progress(account, skill)`.
- Produces:
  - `ALREADY_120 = "already 120"` (replaces `ALREADY_99`)
  - `closest_skill(method, account) -> dict` (a `level_progress` result; replaces `gap_to_99`)
  - `closest_first(method) -> tuple` (path A's sort key)
  - `percent_text(fraction: float) -> str`
  - Ready training methods carry `method["_closest"]` (replaces `method["_gap"]`).

- [ ] **Step 1: Update the test helpers and existing tests**

In `tests/test_plan_session.py`:

1. Imports: replace the two `from account import LEVEL_XP` / `from plan_session import (...)` blocks with:

```python
import re

from account import LEVEL_XP, level_table
from plan_session import (
    ALREADY_120, OUTGROWN, also_text, build_plan, check_method_for_session, closest_skill,
    level_change_text, percent_text, pick_paths, runner_ups, split_ruled_out,
)
```

(`import re` goes with `import copy` and `import unittest` at the top.)

2. Replace `make_account` and `with_levels` with:

```python
def make_account(level=95):
    """Every skill at the start of the same level (each on its own XP table), no quests done."""
    skills = {name: {"xp": float(level_table(name)[level - 1]), "level": level} for name in SKILL_NAMES}
    return {"skills": skills, "completed_quests": set(), "quests": {}}
```

```python
def with_levels(account, **levels):
    """Change some skills' levels (and XP to match) in an account from make_account()."""
    for skill, level in levels.items():
        account["skills"][skill] = {"xp": float(level_table(skill)[level - 1]), "level": level}
    return account


def part_way(account, skill, level, extra_xp):
    """Put a skill at a level plus some XP into it (extra_xp must stay below the next level)."""
    account["skills"][skill] = {"xp": level_table(skill)[level - 1] + extra_xp, "level": level}
    return account
```

3. Replace `ready_method` with:

```python
def ready_method(name, fraction=None, low=None, high=None, gp=None, skill="Mining"):
    """A method as build_plan leaves it once it is ready (training ones carry _closest)."""
    method = {"name": name, "type": "money" if gp is not None else "training", "skill": skill,
              "xp_per_hour_low": low, "xp_per_hour_high": high if high is not None else low,
              "gp_per_hour": gp}
    if gp is None:
        method["_closest"] = {"skill": skill, "fraction": fraction}
    return method
```

4. Replace `RunnerUpTests.setUp` with:

```python
    def setUp(self):
        # Path A (furthest through its level): t1, then t5, t2, t3, t4. Most XP (B, low end):
        # t2, t3, t4, t1, t5. Each trains its own skill, so A's different-skills rule
        # removes nothing here.
        self.t1 = ready_method("t1", fraction=0.9, low=10, skill="Mining")
        self.t2 = ready_method("t2", fraction=0.7, low=50, skill="Smithing")
        self.t3 = ready_method("t3", fraction=0.6, low=40, skill="Cooking")
        self.t4 = ready_method("t4", fraction=0.5, low=30, skill="Firemaking")
        self.t5 = ready_method("t5", fraction=0.8, low=5, skill="Divination")
        self.g1 = ready_method("g1", gp=900)
        self.g2 = ready_method("g2", gp=700)
        self.g3 = ready_method("g3", gp=800)
        self.ready = [self.t1, self.t2, self.t3, self.t4, self.t5, self.g1, self.g2, self.g3]
```

(The existing `RunnerUpTests` expectations stay exactly as they are: `["t1", "t2", "g1"]` and `[["t5", "t3"], ["t4"], ["g3", "g2"]]`.)

5. Add these three tests to `RunnerUpTests`, after `test_each_path_gets_its_next_two_by_its_own_rule`:

```python
    def test_a_shows_each_skill_once(self):
        t6 = ready_method("t6", fraction=0.85, low=1, skill="Mining")      # same skill as A's pick t1
        t7 = ready_method("t7", fraction=0.75, low=2, skill="Divination")  # same skill as t5
        ready = self.ready + [t6, t7]
        picks = pick_paths(ready)
        self.assertEqual([m["name"] for m in picks], ["t1", "t2", "g1"])
        also = runner_ups(ready, picks)
        self.assertEqual([m["name"] for m in also[0]], ["t5", "t3"])
        # Skipped under A, so B may still offer t7.
        self.assertEqual([m["name"] for m in also[1]], ["t4", "t7"])

    def test_skill_whose_best_method_is_bs_pick_shows_its_next_one(self):
        x1 = ready_method("x1", fraction=0.85, low=100, skill="Hunter")   # fastest: B's pick
        x2 = ready_method("x2", fraction=0.85, low=3, skill="Hunter")
        ready = self.ready + [x1, x2]
        picks = pick_paths(ready)
        self.assertEqual([m["name"] for m in picks], ["t1", "x1", "g1"])
        self.assertEqual([m["name"] for m in runner_ups(ready, picks)[0]], ["x2", "t5"])

    def test_skill_whose_only_method_is_bs_pick_gives_way(self):
        t2 = ready_method("t2", fraction=0.85, low=50, skill="Smithing")  # 2nd closest, but B's pick
        ready = [self.t1, t2, self.t3, self.t4, self.t5, self.g1, self.g2, self.g3]
        picks = pick_paths(ready)
        self.assertEqual([m["name"] for m in picks], ["t1", "t2", "g1"])
        self.assertEqual([m["name"] for m in runner_ups(ready, picks)[0]], ["t5", "t3"])
```

6. In `SplitRuledOutTests.test_finished_or_outgrown_are_counted_not_listed`, change the comment's `"already 99"` to `"already 120"` and the three `"already 99"` strings in `ruled_out` to `ALREADY_120`. In `test_folds_the_reasons_the_checker_really_writes`, change `make_account(99)` to `make_account(120)` and `self.assertIn(ALREADY_99, ruled_out[1][1])` to `self.assertIn(ALREADY_120, ruled_out[1][1])`.

7. Add these classes before `if __name__ == "__main__":`

```python
class PathATests(unittest.TestCase):
    def test_furthest_through_its_level_wins(self):
        # Cooking 60 is 88% of the way to 61; Smithing 95 only 11% of the way to 96.
        account = part_way(part_way(make_account(95), "Smithing", 95, 100_000), "Cooking", 60, 25_000)
        smith = copy.deepcopy(METHOD)
        cook = copy.deepcopy(METHOD)
        cook.update(name="Cook", skill="Cooking", min_level=1)
        plan = build_plan([smith, cook], account, 5, YES)
        self.assertEqual(plan["paths"][0][1]["name"], "Cook")
        self.assertEqual(smith["_closest"]["skill"], "Smithing")

    def test_tie_goes_to_the_faster_method(self):
        slow = ready_method("slow", fraction=0.5, low=10, skill="Herblore")
        fast = ready_method("fast", fraction=0.5, low=20, skill="Mining")
        self.assertEqual(pick_paths([slow, fast])[0]["name"], "fast")

    def test_two_skill_method_counts_its_further_skill(self):
        # Ranged 73 barely started; Defence 92 is 88% of the way to 93.
        account = part_way(part_way(make_account(95), "Ranged", 73, 1_000), "Defence", 92, 600_000)
        closest = closest_skill({"skill": "Ranged/Defence"}, account)
        self.assertEqual((closest["skill"], closest["next_level"]), ("Defence", 93))
        self.assertAlmostEqual(closest["xp_left"], 78_376)   # 7,195,629 - 6,517,253 - 600,000

    def test_skill_at_120_is_skipped_but_the_method_stays(self):
        account = with_levels(make_account(95), Ranged=120, Defence=105)
        self.assertEqual(closest_skill({"skill": "Ranged/Defence"}, account)["skill"], "Defence")
        blocked, _, _ = check_method_for_session(banded("Ranged/Defence", 70, None), account, 5, YES)
        self.assertEqual(blocked, [])


class FinishedRuleTests(unittest.TestCase):
    def test_skill_past_99_is_ready_now(self):
        # Was "already 99" before; levels past 99 now count.
        account = with_levels(make_account(95), Woodcutting=105)
        blocked, _, _ = check_method_for_session(banded("Woodcutting", 81, None), account, 5, YES)
        self.assertEqual(blocked, [])

    def test_every_skill_at_120_is_finished(self):
        account = with_levels(make_account(95), Woodcutting=120, Ranged=120, Defence=120)
        for skill in ("Woodcutting", "Ranged/Defence"):
            blocked, _, _ = check_method_for_session(banded(skill, 70, None), account, 5, YES)
            self.assertEqual(blocked, [ALREADY_120])
        # A money method for a skill at 120 stays available to path C.
        money = banded("Woodcutting", 70, None)
        money.update(type="money", gp_per_hour=1_000_000)
        blocked, _, _ = check_method_for_session(money, account, 5, YES)
        self.assertEqual(blocked, [])


class PercentTextTests(unittest.TestCase):
    def test_rounds_down(self):
        self.assertEqual(percent_text(0.83949), "83.9%")
        self.assertEqual(percent_text(0.99999), "99.9%")   # never "100.0%" before the level

    def test_keeps_exact_values(self):
        self.assertEqual(percent_text(0.0), "0.0%")
        self.assertEqual(percent_text(0.5), "50.0%")
        self.assertEqual(percent_text(0.29), "29.0%")
        self.assertEqual(percent_text(0.579), "57.9%")


class WhyLineTests(unittest.TestCase):
    def why_a(self, extra_xp):
        account = part_way(make_account(95), "Smithing", 95, extra_xp)
        plan = build_plan([copy.deepcopy(METHOD)], account, 5, YES)
        self.assertEqual(plan["paths"][0][0], "PATH A: finish something")
        return plan["paths"][0][2]

    def test_why_line_for_path_a(self):
        # Smithing 95 -> 96 needs 913,019 XP; 500,000 in is 54.76%.
        line = "Smithing is 54.7% of the way to 96 (413,019 XP left): the furthest of your skills with a ready method."
        self.assertRegex(self.why_a(500_000), r"(?m)^" + re.escape(line) + "$")

    def test_why_line_never_says_0_xp_left(self):
        # 0.3 XP short: rounds up to 1 XP, and the percent rounds down.
        line = "Smithing is 99.9% of the way to 96 (1 XP left): the furthest of your skills with a ready method."
        self.assertRegex(self.why_a(913_018.7), r"(?m)^" + re.escape(line) + "$")


class LevelChangeTextTests(unittest.TestCase):
    def test_level_change_text_uses_elite_for_invention(self):
        account = make_account(95)   # Invention at the start of elite 95: 30,350,318 XP
        self.assertEqual(level_change_text(account, "Invention", 1_000_000, 2_000_000),
                         "Invention 95 -> 95-96 (96 is 1,369,626 XP away)")
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python3 -m unittest tests.test_plan_session -v 2>&1 | tail -5`
Expected: an `ImportError` naming `ALREADY_120` (the module can't load yet).

- [ ] **Step 3: Change `plan_session.py`**

1. Docstring line 10: replace `  A: finish something  - the ready method for the skill closest to 99` with

```
  A: finish something  - the ready method for the skill furthest through its current level
```

2. Imports: add `import math       # floor() and ceil() for the why line` under `import argparse ...` (keep the comment column), and replace `from account import LEVEL_XP, level_from_xp, read_account, xp_to_99` with

```python
from account import level_from_xp, level_progress, level_table, read_account
```

3. Replace the two constants' block (`# The two reasons ...` through `OUTGROWN = ...`) with:

```python
# The two reasons that mean "you'll never use this method again". They are written
# by check_method_for_session and recognised by split_ruled_out, so both use these
# names: rewording one can't quietly stop the other from finding it.
ALREADY_120 = "already 120"
OUTGROWN = "you've outgrown this"
```

4. In `check_method_for_session`, replace

```python
    # Training only makes sense for the max cape if a skill is still under 99.
    if method["type"] == "training" and all(xp_to_99(account, s) == 0 for s in skills):
        blocked.append(ALREADY_99)
```

with

```python
    # Training only makes sense while a skill it trains still has a next level.
    # The XP tables stop at 120, so a method is finished once ALL its skills are 120.
    if method["type"] == "training" and all(level_progress(account, s) is None for s in skills):
        blocked.append(ALREADY_120)
```

5. Replace `gap_to_99` with:

```python
def closest_skill(method, account):
    """
    Of the method's skills that still have a next level, the one furthest through
    its current level, as account.level_progress() describes it. On an exact tie the
    skill named first wins (max() keeps the first). check_method_for_session has
    already ruled out methods whose skills are all at 120, so there is always one.
    """
    progress = [level_progress(account, s) for s in method["skill"].split("/")]
    return max((p for p in progress if p is not None), key=lambda p: p["fraction"])


def closest_first(method):
    """Path A's order: furthest through its level first; on a tie, the faster method."""
    return (-method["_closest"]["fraction"], -method["xp_per_hour_low"])
```

6. In `pick_paths`, replace

```python
    # A: closest skill to 99; if two tie, the faster method wins.
    path_a = min(training, key=lambda m: (m["_gap"], -m["xp_per_hour_low"]), default=None)
```

with

```python
    # A: the skill furthest through its current level; if two tie, the faster method wins.
    path_a = min(training, key=closest_first, default=None)
```

7. In `runner_ups`:
   - Docstring: after `(the next best one takes its place).` add the sentence `Path A's list also shows different skills: a method whose skill is already shown under A is skipped.`
   - Replace `    by_closest = sorted(training, key=lambda m: (m["_gap"], -m["xp_per_hour_low"]))` with:

```python
    # Path A shows different skills: keep only the first (best) method for each skill,
    # and none for the skill A's own pick already shows.
    path_a = picks[0]
    shown_skills = {path_a["_closest"]["skill"]} if path_a else set()
    by_closest = []
    for method in sorted(training, key=closest_first):
        if method["_closest"]["skill"] not in shown_skills:
            by_closest.append(method)
            shown_skills.add(method["_closest"]["skill"])
```

8. Under `also_text`, add:

```python
def percent_text(fraction):
    """e.g. 0.83949 -> '83.9%'. Rounded DOWN, so a level never shows 100.0% before it's reached."""
    return f"{math.floor(fraction * 1000) / 10:.1f}%"
```

9. In `split_ruled_out`'s docstring change `("already 99")` to `("already 120")`, and in its code `r == ALREADY_99` to `r == ALREADY_120`.

10. In `build_plan`, replace `                method["_gap"] = gap_to_99(method, account)` with

```python
                method["_closest"] = closest_skill(method, account)
```

and replace the `why_a = (...)` statement with:

```python
    if path_a:
        closest = path_a["_closest"]
        # XP left is rounded UP: 0.3 XP short reads "1 XP left", never "0 XP left".
        why_a = (f"{closest['skill']} is {percent_text(closest['fraction'])} of the way to "
                 f"{closest['next_level']} ({math.ceil(closest['xp_left']):,} XP left): "
                 "the furthest of your skills with a ready method.")
    else:
        why_a = ""
```

11. Replace `level_change_text` with:

```python
def level_change_text(account, skill, xp_low, xp_high):
    """e.g. 'Mining 96 -> 96-97 (97 is 566,820 XP away)'. Uses the skill's own XP table."""
    now = account["skills"][skill]
    table = level_table(skill)
    start_level = now["level"]
    low_level = level_from_xp(now["xp"] + xp_low, skill)
    high_level = level_from_xp(now["xp"] + xp_high, skill)
    after = str(low_level) if low_level == high_level else f"{low_level}-{high_level}"
    text = f"{skill} {start_level} -> {after}"
    if start_level < len(table):
        to_next = table[start_level] - now["xp"]   # table[start_level] is the next level
        text += f" ({start_level + 1} is {to_next:,.0f} XP away)"
    return text
```

Then check nothing old is left: `grep -n "_gap\|gap_to_99\|ALREADY_99\|xp_to_99\|LEVEL_XP" plan_session.py` → nothing.

- [ ] **Step 4: Run the tests to see them pass**

Run: `python3 -m unittest tests.test_plan_session -v 2>&1 | tail -3` → `OK`.
Run: `python3 -m unittest discover -s tests 2>&1 | tail -3` → `Ran 236 tests`, `OK`.
Run: `python3 check_methods.py | tail -3` → clean, 81 methods.

- [ ] **Step 5: Break it on purpose, then restore**

1. In `runner_ups`, change `if method["_closest"]["skill"] not in shown_skills:` to `if True:`. Run `python3 -m unittest tests.test_plan_session 2>&1 | tail -3` → `FAILED` (including `test_a_shows_each_skill_once`). Restore → `OK`.
2. In `build_plan`, change `math.ceil(closest['xp_left'])` to `round(closest['xp_left'])`. Run again → `FAILED` (`test_why_line_never_says_0_xp_left`). Restore → `OK`.

- [ ] **Step 6: The wording elsewhere**

1. `app.py` line 925: change `you've finished (99) or outgrown.` to `you've finished (120) or outgrown.` (the docstring above, "Methods you've finished the skill for or outgrown", is still true and stays).
2. `README.md`:
   - `   - **A · Finish something:** your skill closest to 99 that has a method you can do now` → `   - **A · Finish something:** your skill furthest through its current level that has a method you can do now`
   - `- **A, finish something:** the skill closest to 99 that has a ready method` → `- **A, finish something:** the skill furthest through its current level that has a ready method`
   - `reason; in the app, methods you've finished (99) or outgrown are just counted.` → `reason; in the app, methods you've finished (120) or outgrown are just counted.`
3. `SPEC.md`: after the table row starting `| C: gold | Divination 81 |` and before the line starting `- **Why Ranged first in B:**`, put a blank line, then:

```markdown
Since 9 October 2026, path A picks the skill furthest through its current level; see docs/superpowers/specs/2026-10-09-path-a-next-level-design.md.
```

Run: `grep -n "closest to 99\|finished (99)" README.md app.py plan_session.py` → exactly two lines, both unchanged and not about path A: `README.md` ~142 (`the skills closest to 99`, Home's panel) and `app.py` ~804 (a comment on the Progress screen, `closest to 99 first, like the Skills screen`).
Run: `.venv/bin/python -c "import ast; ast.parse(open('app.py').read())" && echo parses` → `parses`.

- [ ] **Step 7: Commit**

```bash
git add plan_session.py tests/test_plan_session.py app.py README.md SPEC.md
git commit -F - <<'EOF'
Path A next level: pick the skill furthest through its level

Path A ("Finish something") now picks the ready training method whose
skill is furthest through its current level; its "Also good" shows the
next two skills. Levels past 99 count; a training method is finished
only when every skill it trains is 120. Why line, README and SPEC
updated; the terminal follows (same build_plan).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

Stop and wait for Chris.

---

### Task 3: Prove it on frozen data (before/after)

**Files:** none in the repo. Scratch and `.claude/launch.json` only.

**Interfaces:**
- Consumes: the plan commit (subject `Path A next level: plan`, the "before") and the Task 2 commit (the "after"); `.superpowers/sdd/host-lock/run_frozen.py`.
- Produces: the before/after report for Chris.

- [ ] **Step 1: Freeze RuneMetrics replies and copy Hels's data once**

First check `data/players/current.txt` still says `Hels Glasglo` without printing it: `python3 -c "print(open('data/players/current.txt').read().strip() == 'Hels Glasglo')"` → `True` (if `False`, stop and ask Chris). Then, the only RuneMetrics calls in this plan:

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a
cd /home/chris-baron/Repos/RS-Planning-Tool
mkdir -p $W/frozen $W/data_template/players/hels+glasglo
cp .superpowers/sdd/host-lock/run_frozen.py $W/
python3 -c "import json; from rs3_planner import load_profile, load_quests; json.dump(load_profile('Hels Glasglo'), open('$W/frozen/profile.json', 'w')); json.dump(load_quests('Hels Glasglo'), open('$W/frozen/quests.json', 'w'))"
cp -r data/players/hels+glasglo/answers.json data/players/hels+glasglo/last_goal data/players/hels+glasglo/snapshots $W/data_template/players/hels+glasglo/
echo "Hels Glasglo" > $W/data_template/players/current.txt
ls $W $W/frozen $W/data_template/players/hels+glasglo
```

Expected: `data_template frozen run_frozen.py`; `profile.json quests.json`; `answers.json last_goal snapshots`. A private-profile message or traceback: stop and report.

- [ ] **Step 2: The two copies**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a
cd /home/chris-baron/Repos/RS-Planning-Tool
BEFORE=$(git log -1 --format=%h --grep='^Path A next level: plan$')
echo "before = $BEFORE"; git log -1 --format=%s $BEFORE
rm -rf $W/before $W/after && mkdir -p $W/before $W/after
git archive $BEFORE | tar -x -C $W/before
git ls-files -z | xargs -0 tar -cf - | tar -x -C $W/after
for c in before after; do sed -i 's/^PORT = 8080$/PORT = 8091/' $W/$c/app.py; cp -r $W/data_template/players $W/$c/data/players; done
grep -n "^PORT" $W/before/app.py $W/after/app.py
grep -c "ELITE_LEVEL_XP" $W/before/account.py $W/after/account.py
ls $W/before/data/players $W/after/data/players
```

Expected: the subject `Path A next level: plan`; both `PORT = 8091`; `ELITE_LEVEL_XP` count `0` in before, more than `0` in after; each players folder lists `current.txt  hels+glasglo`.

Add two entries to `"configurations"` in the git-excluded `.claude/launch.json` (keep `rs3-planner-gui` as it is):

```json
{
  "name": "rs3-patha-before",
  "runtimeExecutable": "/home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python",
  "runtimeArgs": ["/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a/run_frozen.py",
                  "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a/before",
                  "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a/frozen", "app.py"],
  "port": 8091
},
{
  "name": "rs3-patha-after",
  "runtimeExecutable": "/home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python",
  "runtimeArgs": ["/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a/run_frozen.py",
                  "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a/after",
                  "/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a/frozen", "app.py"],
  "port": 8091
}
```

- [ ] **Step 3: The terminal planner, before and after**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a
for c in before after; do
  /home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python $W/run_frozen.py $W/$c $W/frozen plan_session.py \
    --user "Hels Glasglo" --hours 5 --minutes 2 --session afk > $W/term_$c.txt 2>&1
  echo "$c exit $?"
done
diff $W/term_before.txt $W/term_after.txt
```

Expected: both `exit 0`. The diff may only touch: the `N of 81 methods fit` line; the `PATH A` block (method, rate, hours, Why, Also good, Watch/Check/Notes/Source of the new method); the `PATH B` block only if B's pick or "Also good" moved; the `PATH C` "Also good" line only if A took or freed a method; and the "Ruled out" list (methods that were `already 99` are gone from it or have lost that reason). Anything else (e.g. a traceback, a changed PATH C pick): stop and report.

- [ ] **Step 4: Save the "before" page texts**

Start `preview_start {name: "rs3-patha-before"}` and tell Chris it is running (port 8091). Check `preview_logs`: one "Fetching Hels Glasglo from RuneMetrics", no traceback.

For each of these 9 addresses under `http://127.0.0.1:8091`, `navigate` there, then run with `javascript_tool`:

`/player`, `/`, `/play`, `/plan?hours=5&session=afk&minutes=2`, `/plan?hours=5&session=active&minutes=2`, `/skills`, `/quests`, `/quests/goal`, `/progress`

```js
await new Promise(r => setTimeout(r, 1500));
const key = location.pathname + location.search;
const text = document.querySelector('main').innerText;
localStorage.setItem('patha before ' + key, text);
const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)));
`${[...bytes].map(b => b.toString(16).padStart(2, '0')).join('')}  ${text.length}  ${key}`
```

Write the 9 result lines into `$W/before.sha` with the Write tool. Any `null` (no `main`) or empty text: stop and report. (No clicks needed: the AFK plan's ruled-out count is on the "Why not the others?" button's own text.) Stop the preview (`preview_stop`).

- [ ] **Step 5: The "after" page texts, compared**

Start `preview_start {name: "rs3-patha-after"}` and tell Chris it is running. Check `preview_logs`: one fetch line, no traceback. For the same 9 addresses (same origin, so the "before" texts are in localStorage), run:

```js
await new Promise(r => setTimeout(r, 1500));
const key = location.pathname + location.search;
const before = localStorage.getItem('patha before ' + key);
const after = document.querySelector('main').innerText;
const clock = l => l.startsWith('Stats updated') || /snapshots · last \d/.test(l);
const b = before === null ? null : before.split('\n'), a = after.split('\n');
const clocks = b === null ? '' : ' clock: ' + b.filter(clock).join(' / ') + ' -> ' + a.filter(clock).join(' / ');
const kb = b && b.filter(l => !clock(l)), ka = a.filter(l => !clock(l));
const verdict = b === null ? 'NO BEFORE' : kb.join('\n') === ka.join('\n') ? 'same'
  : 'DIFFERENT\n  - ' + kb.filter(l => !ka.includes(l)).join('\n  - ') + '\n  + ' + ka.filter(l => !kb.includes(l)).join('\n  + ');
`${key}  ${verdict}${clocks}`
```

Write the 9 results into `$W/after.txt`. Expected: `same` for every page except `/plan?hours=5&session=afk&minutes=2`, whose differences may only be path A's lines (method, skill, rate, hours, why, Also good, Watch/Check of the new method), path B's lines if its pick or "Also good" moved, path C's "Also good" if A took or freed a method, and the "Why not the others? (N ruled out)" button. Any other difference (another page, path C's pick): stop and report. Stop the preview and tell Chris.

- [ ] **Step 6: Invention's level, from XP vs RuneMetrics**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a
cd $W/after && /home/chris-baron/Repos/RS-Planning-Tool/.venv/bin/python -I -c "
import json, sys; sys.path.insert(0, '.')
from account import level_from_xp
from rs3_planner import INVENTION_ID
s = next(v for v in json.load(open('../frozen/profile.json'))['skillvalues'] if v['id'] == INVENTION_ID)
print('RuneMetrics level:', s['level'], ' from XP (elite table):', level_from_xp(s['xp'] / 10, 'Invention'), ' XP:', f\"{s['xp'] / 10:,.1f}\")
"
```

Expected: one line with both levels. Report both to Chris. If RuneMetrics says below 99 and the two differ: stop and report (the table or the code is wrong). At 99 or above a difference is expected (RuneMetrics' level isn't trusted there) and is just reported.

- [ ] **Step 7: Report to Chris**

Show Chris, without naming any other player: the terminal diff (Step 3), the AFK plan's before/after lines (Step 5), the clock lines that were ignored, and Step 6's line. Say plainly whether path B or C moved and why (a 99–119 method returned, or the no-method-twice rule). Nothing to commit. Stop and wait for Chris.

---

### Task 4: Chris's live app, and tidying up

**Files:** none in the repo. Scratch and `.claude/launch.json` only.

**Interfaces:**
- Consumes: the Task 2 commit.
- Produces: nothing.

- [ ] **Step 1: Ask Chris to restart**

Ask Chris to use **Restart** on the RS3 Planner icon, or to approve `systemctl --user restart rs3-planner`. Do nothing to the service until Chris answers. (After a restart the app fetches the current player once: expected, one fetch per run.)

- [ ] **Step 2: Read the live AFK plan**

```bash
systemctl --user is-active rs3-planner
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/skills
```

Expected: `active`, `200`. Do not quote the service log. In the built-in browser open `http://127.0.0.1:8080/plan?hours=5&session=afk&minutes=2` and read `document.querySelector('main').innerText` with `javascript_tool`: path A's label is `A · Finish something`, its why line starts with a skill name and contains `% of the way to` and `XP left): the furthest of your skills with a ready method.`, and "Also good" lists two methods of two other skills. `read_console_messages` with `onlyErrors: true` → no errors. Click nothing that saves. Report to Chris (no other player's name).

- [ ] **Step 3: Tidy up**

```bash
W=/home/chris-baron/Repos/RS-Planning-Tool/.superpowers/sdd/path-a
rm -rf $W/before $W/after $W/frozen $W/data_template
ls $W
```

Expected: `after.txt  before.sha  run_frozen.py  term_after.txt  term_before.txt` (no copies of Chris's data). Remove the `rs3-patha-before` and `rs3-patha-after` entries from `.claude/launch.json` (keep `rs3-planner-gui`). `git status --short` → clean.

- [ ] **Step 4: Ask about pushing**

Before asking, check the unpushed commits for other players' names without printing any: read the folder names in `data/players/` and print only a count of matches in `git log origin/main..HEAD -p` and in the commit messages (expected: 0 for every name other than `hels+glasglo`/`Hels Glasglo`). Tell Chris what is committed (spec, plan, Task 1, Task 2) and ask whether to push to GitHub. Push only on a yes; if a push fails, run `ssh -T git@github.com` before anything else and report.
