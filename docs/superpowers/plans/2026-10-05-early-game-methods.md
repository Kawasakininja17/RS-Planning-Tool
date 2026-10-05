# Early and Mid-Level Methods Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Any player gets real AFK paths A, B and C: methods get a level band (`max_level`), and wiki-checked methods for early and mid levels are added after Chris reviews them.

**Architecture:** `check_methods.py` validates the new `max_level` field; `plan_session.check_method_for_session` rules a method out as "outgrown" when every skill it trains is past `max_level`. New methods are researched from the wiki's page text in the built-in browser into a review table; only entries Chris approves go into `data/methods.json`. The app needs no change: it already shows the planner's reasons.

**Tech Stack:** Python 3.14 standard library (scripts, `unittest`), NiceGUI 3.17.1 app in `.venv/` (unchanged), the built-in browser for reading wiki pages.

**Spec:** `docs/superpowers/specs/2026-10-05-early-game-methods-design.md`

## Global Constraints

- Wiki facts only, from pages actually opened. Anything the wiki doesn't state is `null`, marked "wiki doesn't say" in the review table.
- Wiki pages are read as exact page text in the built-in browser (`get_page_text`). The web-fetch tool is not used for numbers.
- `python3 check_methods.py` passes after every data edit.
- No new RuneMetrics calls in the code. Live checks: one fetch per player per app run.
- No other players' names in the repo (docs, tests, commits). The second test player is used only live in the app, never in the terminal, files or tests.
- Code simple and commented in plain words, matching the existing files.
- Tests: `python3 -m unittest discover -s tests -v`, never touching the network or the real `data/players/`.
- Stop and wait for Chris after Task 1 (3a), Task 2 (3b) and Task 3 (3c). Commit each task (Task 2 commits nothing); never push without asking. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- If a step errors, stop that task and explain (what failed, the error in plain words, likely cause, what's done, what's left, the proper fix); wait for Chris.

## Review Focus

1. **A late-game player's "Why not the others?" list grows a lot** (dozens of new methods ruled out as "outgrown" or "already 99") → still folded, each with a clear reason, no crash, no change to their paths. Pinned in Task 3 Step 6 (Hels live check: count and spot-check the reasons; paths compared with the frozen terminal run).
2. **A new method whose click time the wiki doesn't give** → kept and shown with "Watch: click time unknown (the wiki doesn't give one)", never silently dropped or given an invented time. Pinned in Task 2 (review table marks it) and Task 3 Step 6 (seen in the app).
3. **A level exactly at a band edge** (e.g. 59 for a 30–59 method, 60 for the next band) → the 30–59 method is still offered at 59, and from 60 only the next band's method. Pinned in Task 1 (`test_at_top_of_band_still_offered`, `test_one_past_band_is_outgrown`).
4. **Two-skill method with one skill past the band and the other inside it** → still offered. Pinned in Task 1 (`test_two_skill_method_offered_while_one_skill_inside`).
5. **A hand-edited `max_level` that is text, 0, 121 or below `min_level`** → `check_methods.py` names the method and the problem instead of the planner crashing. Pinned in Task 1 (`MaxLevelCheckTests`).

## File map

| File | Change | Responsibility |
|---|---|---|
| `check_methods.py` | modify | `max_level` required and validated; table shows the band |
| `plan_session.py` | modify | "outgrown" check in `check_method_for_session` |
| `tests/test_check_methods.py` | modify | `max_level` validation tests; fixture gets `max_level` |
| `tests/test_plan_session.py` | modify | outgrown tests; fixture gets `max_level` |
| `data/methods.json` | modify | Task 1: `"max_level": null` on the 12 methods + `about` sentence. Task 3: approved new methods |
| `README.md` | modify | Task 3: one paragraph on level bands and the new methods |

`SCR` = `/tmp/claude-1000/-home-chris-baron-Repos-RS-Planning-Tool/9722696a-efe4-4596-a97a-65d3ffd8c745/scratchpad`
(session scratch, outside the project). It holds `run_frozen.py` and `frozen/` (Hels's profile and quests replies)
from the previous plan. `BASE` = `28ace97`.

---

### Task 1: The `max_level` field (step 3a)

**Files:**
- Modify: `check_methods.py` (`REQUIRED_FIELDS`, `check_method` level checks, `print_table`)
- Modify: `plan_session.py` (`check_method_for_session`)
- Modify: `data/methods.json` (12 × `"max_level": null`, `about`)
- Test: `tests/test_check_methods.py`, `tests/test_plan_session.py`

**Interfaces:**
- Consumes: existing `check_method(method, position) -> list[str]`, `check_method_for_session(method, account, max_minutes, answers) -> (blocked, warnings, unanswered)`.
- Produces: every method dict has key `"max_level"` (`int` 1–120 ≥ `min_level`, or `None`). Blocked reason text: `"you've outgrown this (<Skill> <level>[ and <Skill> <level>]; this method's rates are for levels <min>–<max>)"` (en dash).

- [ ] **Step 1: Save the "before" outputs on frozen data**

```bash
SCR=/tmp/claude-1000/-home-chris-baron-Repos-RS-Planning-Tool/9722696a-efe4-4596-a97a-65d3ffd8c745/scratchpad
ls $SCR/frozen $SCR/run_frozen.py    # both must exist; if not, stop and report
rm -rf $SCR/before && mkdir -p $SCR/before && cd ~/Repos/RS-Planning-Tool
git archive 28ace97 | tar -x -C $SCR/before
mkdir -p $SCR/before/data/players/hels+glasglo && cp data/players/hels+glasglo/answers.json $SCR/before/data/players/hels+glasglo/
for s in afk active; do
  python3 $SCR/run_frozen.py $SCR/before $SCR/frozen plan_session.py --user "Hels Glasglo" --hours 5 --minutes 2 --session $s --goal 1 > $SCR/m_before_$s.txt
done
(cd $SCR/before && python3 check_methods.py) > $SCR/m_before_check.txt
tail -3 $SCR/m_before_afk.txt; grep -c "" $SCR/m_before_active.txt $SCR/m_before_check.txt
```

Expected: no traceback; the AFK output ends with the "Ruled out for this session" list.

- [ ] **Step 2: Write the failing tests**

In `tests/test_check_methods.py`, add `"max_level": None,` to `VALID` right after `"min_level": 90,`, and add this class before `class UnlockIdsMatchTests`:

```python
class MaxLevelCheckTests(unittest.TestCase):
    """max_level: the top of the level band the wiki's rates are for (None = no top)."""

    def with_max(self, value):
        method = copy.deepcopy(VALID)   # min_level is 90
        method["max_level"] = value
        return check_method(method, 1)

    def test_missing_is_a_problem(self):
        method = copy.deepcopy(VALID)
        del method["max_level"]
        self.assertIn("Method #1 (Test method): missing field 'max_level'", check_method(method, 1))

    def test_null_is_fine(self):
        self.assertEqual(self.with_max(None), [])

    def test_at_or_above_min_level_is_fine(self):
        self.assertEqual(self.with_max(90), [])
        self.assertEqual(self.with_max(97), [])

    def test_below_min_level_is_a_problem(self):
        self.assertIn("Method #1 (Test method): max_level (89) is below min_level (90)", self.with_max(89))

    def test_not_a_whole_number_or_out_of_range(self):
        for bad in ("97", 97.5, True, 0, 121):
            self.assertTrue(mentions(self.with_max(bad), "max_level must be a whole number from 1 to 120, or null"),
                            f"{bad!r} should be refused")
```

In `tests/test_plan_session.py`, add `"max_level": None,` to `METHOD` right after `"min_level": 90,`, then add at the end of the file (before `if __name__ == "__main__":` if present):

```python
def with_levels(account, **levels):
    """Change some skills' levels (and XP to match) in an account from make_account()."""
    for skill, level in levels.items():
        account["skills"][skill] = {"xp": float(LEVEL_XP[level - 1]), "level": level}
    return account


def banded(skill="Woodcutting", low=30, high=59):
    """A method whose wiki rates are for levels low-high. Its one unlock is answered 'yes' below."""
    method = copy.deepcopy(METHOD)
    method.update(skill=skill, min_level=low, max_level=high)
    return method


YES = {"smithing-autoheater": True}
OUTGROWN = "you've outgrown this"


class MaxLevelTests(unittest.TestCase):
    def test_inside_band_offered(self):
        blocked, _, _ = check_method_for_session(banded(), with_levels(make_account(), Woodcutting=45), 5, YES)
        self.assertEqual(blocked, [])

    def test_at_top_of_band_still_offered(self):
        blocked, _, _ = check_method_for_session(banded(), with_levels(make_account(), Woodcutting=59), 5, YES)
        self.assertEqual(blocked, [])

    def test_one_past_band_is_outgrown(self):
        blocked, _, _ = check_method_for_session(banded(), with_levels(make_account(), Woodcutting=60), 5, YES)
        self.assertEqual(blocked, ["you've outgrown this (Woodcutting 60; this method's rates are for levels 30–59)"])

    def test_no_max_level_never_outgrown(self):
        method = banded()
        method["max_level"] = None
        blocked, _, _ = check_method_for_session(method, with_levels(make_account(), Woodcutting=98), 5, YES)
        self.assertEqual(blocked, [])

    def test_two_skill_method_offered_while_one_skill_inside(self):
        method = banded("Ranged/Defence", 70, 80)
        account = with_levels(make_account(), Ranged=75, Defence=92)
        blocked, _, _ = check_method_for_session(method, account, 5, YES)
        self.assertFalse(any(OUTGROWN in reason for reason in blocked))

    def test_two_skill_method_outgrown_when_both_past(self):
        method = banded("Ranged/Defence", 70, 80)
        account = with_levels(make_account(), Ranged=85, Defence=92)
        blocked, _, _ = check_method_for_session(method, account, 5, YES)
        self.assertIn("you've outgrown this (Ranged 85 and Defence 92; this method's rates are for levels 70–80)",
                      blocked)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `python3 -m unittest tests.test_check_methods tests.test_plan_session -v 2>&1 | tail -25`
Expected failures, for the right reasons:
- check_methods tests: `unknown field 'max_level' (typo?)` makes `test_valid_method_has_no_problems` and the `MaxLevelCheckTests` fail; `test_missing_is_a_problem` fails because no "missing field 'max_level'" is reported.
- plan_session: `test_one_past_band_is_outgrown` and `test_two_skill_method_outgrown_when_both_past` fail (nothing blocks yet); the "offered" tests pass already (expected: they pin behaviour that must not break).

- [ ] **Step 4: Validate `max_level` in `check_methods.py`**

In `REQUIRED_FIELDS`, change `"type", "name", "skill", "min_level",` to:

```python
    "type", "name", "skill", "min_level", "max_level",
```

Replace the `# 4. Level.` block with:

```python
    # 4. Levels. min_level is where the method starts; max_level is the top of the
    #    level band the wiki's rates were quoted for (null = no upper limit).
    if not is_whole_number(method["min_level"]) or not 1 <= method["min_level"] <= 120:
        problems.append(f"{label}: min_level must be a whole number from 1 to 120")
    top = method["max_level"]
    if top is not None and (not is_whole_number(top) or not 1 <= top <= 120):
        problems.append(f"{label}: max_level must be a whole number from 1 to 120, or null")
    elif top is not None and is_whole_number(method["min_level"]) and top < method["min_level"]:
        problems.append(f"{label}: max_level ({top}) is below min_level ({method['min_level']})")
```

In `print_table`, change the header's `{'Lvl':>4}` to `{'Lvl':>6}`, add before the final `print(f"{m['type']...`:

```python
        band = f"{m['min_level']}-{m['max_level']}" if m["max_level"] is not None else f"{m['min_level']}+"
```

and in that print line change `{m['min_level']:>4}` to `{band:>6}`. Add one line to the legend under the table:

```python
    print("Lvl: the level band the wiki's rates are for ('90+' = no upper limit).")
```

- [ ] **Step 5: The "outgrown" check in `plan_session.py`**

In `check_method_for_session`, directly after the `for skill in skills:` min-level loop, add:

```python
    # Level band: the wiki's rates are for min_level..max_level. Past max_level in
    # EVERY skill the method trains, you've outgrown it. (A two-skill method stays
    # while either skill is still inside the band.) null = no upper limit.
    top = method["max_level"]
    if top is not None:
        levels = [(skill, account["skills"][skill]["level"]) for skill in skills]
        if all(level > top for _, level in levels):
            have = " and ".join(f"{skill} {level}" for skill, level in levels)
            blocked.append(f"you've outgrown this ({have}; this method's rates are "
                           f"for levels {method['min_level']}–{top})")
```

- [ ] **Step 6: `max_level: null` on the 12 existing methods and the `about` sentence**

```bash
cd ~/Repos/RS-Planning-Tool && python3 - <<'EOF'
import re
from pathlib import Path
p = Path("data/methods.json")
s = p.read_text(encoding="utf-8")
# After every '"min_level": N,' line, add '"max_level": null,' with the same indent.
s, count = re.subn(r'(\n(\s*)"min_level": \d+,)', r'\1\n\2"max_level": null,', s)
assert count == 12, count
old = "null means the wiki did not give that value."
assert s.count(old) == 1
s = s.replace(old, old + " max_level is the top of the level band the wiki's rates were quoted for (null = no upper limit).")
p.write_text(s, encoding="utf-8")
EOF
git diff --stat data/methods.json && python3 check_methods.py > /dev/null && echo "data ok"
```

Expected: `1 file changed, 13 insertions(+), 1 deletion(-)` and `data ok`.

- [ ] **Step 7: Run all tests**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -4`
Expected: all pass (80 before this task + 11 new = 91).

- [ ] **Step 8: Frozen proof**

```bash
rm -rf $SCR/after && mkdir -p $SCR/after && cd ~/Repos/RS-Planning-Tool
git ls-files -z | xargs -0 tar -c | tar -x -C $SCR/after
mkdir -p $SCR/after/data/players/hels+glasglo && cp data/players/hels+glasglo/answers.json $SCR/after/data/players/hels+glasglo/
for s in afk active; do
  python3 $SCR/run_frozen.py $SCR/after $SCR/frozen plan_session.py --user "Hels Glasglo" --hours 5 --minutes 2 --session $s --goal 1 > $SCR/m_after_$s.txt
  diff $SCR/m_before_$s.txt $SCR/m_after_$s.txt && echo "$s: no difference"
done
(cd $SCR/after && python3 check_methods.py) > $SCR/m_after_check.txt
diff $SCR/m_before_check.txt $SCR/m_after_check.txt | head -40
```

Expected: `afk: no difference`, `active: no difference`. The `check_methods.py` diff shows only the table header, each row's level column (`90` → `90+`, same rows, same order) and the new legend line. Anything else: stop and report.

- [ ] **Step 9: Commit and stop**

```bash
git add check_methods.py plan_session.py data/methods.json tests/test_check_methods.py tests/test_plan_session.py
git commit -F - <<'EOF'
Methods get a level band (max_level); outgrown methods are ruled out

check_methods.py requires and validates max_level (1-120 or null, not
below min_level) and shows the band. The planner rules a method out as
outgrown when every skill it trains is past max_level. The 12 existing
methods get null, so nothing changes for them.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

Stop. Tell Chris what changed, the test count and the proof. Wait.

---

### Task 2: Research and the review table (step 3b)

**Files:**
- Create (scratch only, never committed): `$SCR/review/methods-review.md`

**Interfaces:**
- Consumes: the `methods.json` format from Task 1 (every field, including `max_level`).
- Produces: the review table, one section per candidate, each with every field Task 3 needs to write a `methods.json` entry, plus the quoted wiki lines.

- [ ] **Step 1: Find the AFK-friendly skills**

In the built-in browser, open each skill's wiki training guide and read it with `get_page_text` (exact page text). Start with:
`https://runescape.wiki/w/Pay-to-play_<Skill>_training` for Woodcutting, Mining, Fishing, Divination, Cooking, Smithing,
Firemaking, Crafting, Fletching, Herblore, Runecrafting, Summoning, Farming, Hunter, Construction, Prayer, Magic, Archaeology,
Necromancy, Invention, and combat (`https://runescape.wiki/w/Combat_training` or the page the wiki links for AFK combat).
A skill is in scope if the page itself describes an AFK, low-intensity or low-click method. Record each page's address and
the line that shows AFK-ness. If a page address doesn't exist, use the page the wiki's search shows for that skill's
training and record that address. Pages the wiki doesn't have: list them in the table's "Not covered" section.

- [ ] **Step 2: Collect training candidates**

For each in-scope skill, pick the wiki's AFK/low-intensity method for each level band from that skill's first AFK
method up to the level where today's methods start (or 99 if the skill has none today). For each candidate record:
name; type `training`; skill; `min_level`; `max_level` (the band's top as the wiki states it; `null` only if the wiki gives no top);
XP/hr low and high for that band; minutes between clicks (only if the page states a time; else `null`); quest, skill and other
requirements; things RuneMetrics can't see (as `unlocks` with a proposed `id` and the wiki's wording); notes; the
exact quoted line(s) for every number; page address; date read (`2026-10-05` or the actual date).

- [ ] **Step 3: Collect a few money candidates**

Open `https://runescape.wiki/w/Money_making_guide` and the skilling money guide `https://runescape.wiki/w/Money_making_guide/Skilling`
(already used by today's file). Pick a few methods with low skill requirements (well under today's lowest money method,
Divination 60) that the page marks as low-intensity or AFK and that show a gp/hr figure. Record the same fields as Step 2 but
with `gp_per_hour`, whether the figure is after GE tax (`gp_after_tax`, as the page states), and the XP/hr only if the page gives it.

- [ ] **Step 4: Write the review table**

`$SCR/review/methods-review.md`, in this shape:

```markdown
# Proposed methods (wiki read 2026-10-05) — keep or strike each

## Summary
| # | Method | Type | Skill | Levels | XP/hr | GP/hr | Click | Keep? |
|---|---|---|---|---|---|---|---|---|
| 1 | <name> | training | Woodcutting | 30–59 | 25,000–30,000 | — | wiki doesn't say | |

## 1. <name>
- Page: <address> (read <date>)
- Levels: <min>–<max> — "<quoted line>"
- XP/hr: <low>–<high> — "<quoted line>"
- Click time: <minutes> — "<quoted line>"   (or: wiki doesn't say)
- Requirements: quests <…>; skills <…>; other <…>; to confirm in the app <…> — "<quoted line>"
- Notes: <…>

## Not covered
- <skill>: <why: no AFK method on the page / page missing>
```

- [ ] **Step 5: Send it and stop**

Send `$SCR/review/methods-review.md` to Chris (`SendUserFile`, display `attach`). Nothing is committed in this task.
Stop. Ask Chris to mark each entry keep or strike. Wait.

---

### Task 3: Data entry, live check, README (step 3c)

**Files:**
- Modify: `data/methods.json` (approved entries appended to `"methods"`)
- Modify: `README.md`

**Interfaces:**
- Consumes: the review table from Task 2 with Chris's keep/strike marks; the `max_level` field from Task 1.
- Produces: the final `methods.json`.

- [ ] **Step 1: Save Hels's frozen "before" for this task**

```bash
rm -rf $SCR/before && mkdir -p $SCR/before && cd ~/Repos/RS-Planning-Tool
git ls-files -z | xargs -0 tar -c | tar -x -C $SCR/before
mkdir -p $SCR/before/data/players/hels+glasglo && cp data/players/hels+glasglo/answers.json $SCR/before/data/players/hels+glasglo/
python3 $SCR/run_frozen.py $SCR/before $SCR/frozen plan_session.py --user "Hels Glasglo" --hours 5 --minutes 2 --session afk > $SCR/m3_before_afk.txt
```

- [ ] **Step 2: Add the approved entries**

For each entry marked keep, append one object to `"methods"` in `data/methods.json` with exactly the fields of the
existing entries (in the same order: `type, name, skill, min_level, max_level, xp_per_hour_low, xp_per_hour_high,
gp_per_hour, gp_after_tax, minutes_between_clicks, requirements {quests, other, skills, unlocks}, unverified,
source_url, checked_date, notes`), copying every value from the review table. A value the table marks "wiki doesn't say"
is `null`. Unlock texts that already exist in the file must reuse the same `id` and the same text.

- [ ] **Step 3: Check the data**

Run: `python3 check_methods.py`
Expected: no problems; the table lists 12 + the approved entries with their bands. Compare each printed row against the
review table's summary row (levels, XP/hr, GP/hr, click). Any mismatch: fix the JSON to match the table, not the other way.

- [ ] **Step 4: Run all tests**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -4` → all pass.

- [ ] **Step 5: Hels on frozen data**

```bash
rm -rf $SCR/after && mkdir -p $SCR/after && cd ~/Repos/RS-Planning-Tool
git ls-files -z | xargs -0 tar -c | tar -x -C $SCR/after
mkdir -p $SCR/after/data/players/hels+glasglo && cp data/players/hels+glasglo/answers.json $SCR/after/data/players/hels+glasglo/
python3 $SCR/run_frozen.py $SCR/after $SCR/frozen plan_session.py --user "Hels Glasglo" --hours 5 --minutes 2 --session afk > $SCR/m3_after_afk.txt
diff $SCR/m3_before_afk.txt $SCR/m3_after_afk.txt
```

Expected: paths A, B and C unchanged; the "N of M methods fit" line and the "Ruled out" list grow with the new methods
(reasons "already 99", "you've outgrown this (…)" or level/quest reasons). If a path changed, stop: show Chris which method
now wins and why, and wait for his decision before committing.

- [ ] **Step 6: Live check in the app**

Start `rs3-planner-gui` (`preview_start`). At 375px wide:
- The second test player (switch on the Choose player screen; one fetch): AFK plan 5h / 2 min — paths A, B and C filled
  (unless the review table showed none could fit); every number on screen matches the review table; any method with no
  click time shows "Watch: click time unknown (the wiki doesn't give one)".
- Hels (switch back; one fetch): paths match `$SCR/m3_after_afk.txt`; "Why not the others?" opens, its count equals the
  terminal's ruled-out count, and a few "outgrown" reasons read correctly.
- No sideways scroll; no console errors from the plan page.
Leave Hels as the current player. Stop the preview. Reset the viewport.

- [ ] **Step 7: README**

In `README.md`, under "## Training and money methods", after the paragraph that starts "Run this after every edit to `methods.json`.", add:

```markdown
Methods cover early, mid and late levels. Each has a level band (`min_level`
to `max_level`): the levels the wiki's rates were quoted for. Once you're past
a method's band in every skill it trains, the planner lists it under "Ruled out"
(in the app: **Why not the others?**) as "you've outgrown this".
```

- [ ] **Step 8: Final checks, commit and stop**

```bash
python3 -m unittest discover -s tests 2>&1 | tail -2
python3 check_methods.py > /dev/null && echo "data ok"
git diff | grep -ic "<second test player's name>" ; echo "(0 = no second player name in the diff)"
git add data/methods.json README.md
git commit -F - <<'EOF'
Methods for early and mid-level accounts (wiki-checked, reviewed)

<N> training and <M> money methods from the RuneScape Wiki, each with its
level band, added after review. README explains level bands.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

(Type the second player's name into the grep only at the terminal; never into a file.) Replace `<N>`/`<M>` with the real counts.
Stop. Tell Chris what was added, the checks, and ask before pushing.
