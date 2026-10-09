# Design: path A picks the skill closest to its next level

2026-10-09 · approved in chat, part by part

## Goal

Path A ("Finish something") on the AFK plan today shows the ready training method for the
skill closest to 99. Reaching 99 is a long road, so path A rarely changes from one session to
the next. After this change path A shows the skill **furthest through its current level**
(the next level-up within reach), and its two "Also good" alternatives are the next two
skills by the same measure.

Levels past 99 now count for every path, up to 120, so a maxed skill's next level can be a
goal too. Invention gets its own (elite) XP table so it can take part like any other skill.

## Decisions (made with Chris on 2026-10-09)

| Question | Decision |
|---|---|
| "Closest" by what? | **Furthest through the current level**: (XP − XP for current level) ÷ (XP for next level − XP for current level). Fair to low and high skills alike; fewest-XP and soonest-level-up both nearly always pick the lowest skills. Tie: the faster method (higher low-end XP/hr) wins, as today. |
| Skills at 99 and above? | **Count, for every path.** The "already 99" rule goes. Path B and its "Also good" may change because of this, on purpose. |
| A skill at 120? | **Training methods are ruled out as finished** (no next level). Its money methods stay available to path C, as money methods already are today. |
| Invention? | **Type in the elite XP table now**, from the wiki, so Invention works like every other skill. |
| Alternatives | **Different skills.** Path A's pick and its two alternatives are three different skills, each with its best ready method. |
| Two-skill methods (Ranged/Defence) | **The skill furthest through its level counts**, and the why line names it. |
| Name | **Keep "Finish something"** (app `A · Finish something`, terminal `PATH A: finish something`). Only the why line changes. |
| Terminal (`plan_session.py`) | **Changes the same way** (it shares `build_plan`). |
| How to build | **Approach 1: level knowledge in `account.py`**, the planner asks it. |

Rejected: all of it inside `plan_session.py` (the elite curve would live apart from the rest
of the level code, and `read_account` would still disagree about Invention's level), and
working out progress inside `read_account` (puts a planner-only field on the data every
screen and the cache use).

### Facts checked (2026-10-09)

Read as page text in the built-in browser:

- **RuneScape Wiki, Experience/Table** (runescape.wiki/w/Experience/Table): has a separate
  "Elite skills" table, levels 1–120 (plus virtual levels 121–150). Level 99 is
  **36,073,511** XP (matches `XP_FOR_99_ELITE`), level 120 is **80,618,654** XP.
- **RuneScape Wiki, Skills, "Elite skills"** (runescape.wiki/w/Skills#Elite_skills):
  "Elite skills have a level range from 1 to 120"; Invention is the only one. The same page
  gives each skill's real top level (99, 110 or 120).
- **RuneScape Wiki, Experience** (runescape.wiki/w/Experience): "Virtual levelling can be
  enabled to visually display levels above 99 for all skills." So "levels past 99" for a skill
  whose real top is 99 or 110 are virtual levels, as asked.

From the code and data (2026-10-09, at commit `aee3672`):

- No method in `data/methods.json` trains Invention (the word appears only in notes), and no
  quest or unlock in `data/quests.json` / `data/unlocks.json` needs it. Making the level
  helpers curve-aware therefore changes nothing on screen today.
- `gap_to_99` takes `min()` over skills still under 99. If a method for a 99+ skill reached it,
  that list would be empty and Python would raise an error. The new function replaces it.
- `level_change_text` and `xp_to_level` use the normal table for every skill, so they would
  be wrong for Invention. Both become curve-aware.
- Path A only ranks skills that have a **ready** training method; skills with no method in
  `methods.json` (e.g. Summoning, Attack, Slayer) can't be picked, however close they are.

## 1. `account.py`: the level knowledge

- **`ELITE_LEVEL_XP`**: a new list of 120 whole numbers, the XP needed for Invention levels
  1–120, typed in from the wiki's Experience/Table elite table (exact page text, read in the
  built-in browser at build time). A comment names the page and the date. Same layout as
  `LEVEL_XP`: `ELITE_LEVEL_XP[0]` is level 1, `[98]` is level 99, `[119]` is level 120.
- **`level_table(skill)`**: returns `ELITE_LEVEL_XP` for `"Invention"`, `LEVEL_XP` for any
  other skill. Every level calculation below goes through it.
- **`level_from_xp(xp, skill=None)`**: as today, but with the right table for `skill`.
  Leaving `skill` out uses the normal table, so every existing caller is unchanged.
- **`xp_to_level(account, skill, level)`**: uses `level_table(skill)`. (Used by the Quests
  screen; no quest needs Invention, so nothing visible changes.)
- **`read_account`**: Invention's level is now worked out from its XP with the elite table,
  like every other skill, instead of taken from RuneMetrics' own level (which isn't trusted
  past 99). Below 99 the two should agree; this is checked on frozen data (section 5). The
  Skills screen still shows "99+" for Invention at 99 or above (its existing rule in
  `skill_rows`); showing the real level there is out of scope.
- **`level_progress(account, skill)`**: returns
  `{"skill", "level", "next_level", "fraction", "xp_left"}` where `fraction` is how far
  through the current level the skill is (0 to just under 1) and `xp_left` is the XP still
  needed for `next_level`. Returns `None` for a skill at 120 (there is no next level).

## 2. `plan_session.py`: the planner

- **The 120 rule.** `ALREADY_99 = "already 99"` becomes `ALREADY_120 = "already 120"`. A
  **training** method gets this reason only when `level_progress` is `None` for **every**
  skill it trains. Money methods are not affected (as today). `split_ruled_out` counts it as
  finished, as before.
- **`closest_skill(method, account)`** replaces `gap_to_99`: of the method's skills that
  still have a next level, the one with the highest `fraction` (on an exact tie, the one
  named first in the method's `skill`). Returns that skill's `level_progress` result.
  `build_plan` stores it on each ready training method as `method["_closest"]` (replacing
  `method["_gap"]`). The 120 rule means every ready training method has at least one such
  skill, so this never runs on an empty list.
- **`pick_paths`, path A**: the ready training method with the highest
  `_closest["fraction"]`; on a tie, the higher `xp_per_hour_low` wins. Paths B and C keep
  their rules (B still prefers a method other than A).
- **`runner_ups`, path A's list**: the remaining training methods in the same order, skipping
  any method already picked for A, B or C, and any method whose `_closest["skill"]` is already
  shown under A (A's pick or an earlier alternative). So A shows three different skills. If a
  skill's only ready method is already picked for another path, the next skill takes its
  place. B's and C's lists keep their own rules and still skip methods already listed above
  them.
- **`percent_text(fraction)`**: one decimal place, **rounded down** (so 99.96% shows as
  `99.9%`, never `100.0%`).
- **Why line for A**, e.g.:
  `Defence is 83.9% of the way to 93 (109,284 XP left): the furthest of your skills with a ready method.`
  B's and C's why lines don't change.
- **`xp_left_text(xp_left)`** (added 2026-10-09 after the before/after check): the why
  line's "XP left" is rounded exactly like the "N hours" line's "XP away" just above it,
  so the two never disagree (rounding up had shown 1,189 under a line saying 1,188). When
  that rounding would show `0`, it says `under 1` instead.
- **`level_change_text`**: uses `level_table(skill)` and `level_from_xp(…, skill)`, so the
  "what N hours gets you" line is right for Invention too. Its wording doesn't change.
- **Module docstring** (line 10): `A: finish something  - the ready method for the skill furthest through its current level`.
- Titles stay as they are: `PATH A: finish something` here and `PATH_NAMES` in `app.py`.

## 3. Wording elsewhere

- **`app.py`** "Why not the others?": `Also skipped: N you've finished (99) or outgrown.`
  becomes `… finished (120) or outgrown.` and its docstring follows.
- **`README.md`** ~147 (app) and ~257 (terminal): path A is "the skill furthest through its
  current level that has a method you can do now" (app) / "… that has a ready method"
  (terminal). ~264: "methods you've finished (99)" becomes "(120)".
- **`SPEC.md`**: the AFK path table is a dated example from 3 October, worked out with the old
  rule, so it stays as a record. One line goes under it: *Since 9 October 2026, path A picks
  the skill furthest through its current level; see
  docs/superpowers/specs/2026-10-09-path-a-next-level-design.md.*

## 4. What does not change

Home (including its "Closest to 99" panel), Choose player, Ready to play, the Active plan,
Skills, Quests, Big goal and Progress; paths B's and C's ranking rules; `data/` files; the
icon, installer and service; the host lock.

Paths B and C may still show different methods than before, for two reasons only: methods for
skills at 99–119 (today: Overgrown idols, Ghostly sole) are ready again, and A's new pick or
alternatives may take or free a method under the "no method twice" rule. Both are shown in the
before/after check.

## 5. Testing and proof

**Unit tests** (standard library only, no network, no real player files):

- `tests/test_account.py`: `ELITE_LEVEL_XP` has 120 entries, each larger than the one before,
  and `[98] == XP_FOR_99_ELITE`; `level_table`; `level_from_xp` with and without a skill
  (including Invention at an elite boundary); `xp_to_level` for Invention; `level_progress`
  at the start, middle and last XP of a level, at 119, at 120 (`None`), and for Invention;
  `read_account` works Invention's level out from XP.
- `tests/test_plan_session.py`:
  - path A's pick by fraction, with the faster-method tie rule;
  - alternatives from three different skills, including when a skill's only method is
    already B's pick;
  - a two-skill method counted by its further-through skill;
  - a method for a skill at 105 is ready (was "already 99");
  - every skill at 120 → `ALREADY_120`, and `split_ruled_out` counts it;
  - `percent_text` rounds down;
  - the why line, matched at the start of the line (`assertRegex(text, r"(?m)^" + re.escape(line))`).

  The existing `RunnerUpTests` move to the new rule. Their made-up methods all train "Mining"
  today, which the different-skills rule would collapse, so each gets its own skill and a
  `_closest` fraction in the same order as today's gaps; B's and C's expectations stay the same.
- Whole suite after every change. For the new tests, break the code on purpose once or twice
  to prove they can fail, then restore it.

**Frozen before/after** (scratch in `.superpowers/sdd/path-a/`, reusing
`.superpowers/sdd/host-lock/run_frozen.py`; deleted copies afterwards):

1. Freeze RuneMetrics replies once (one profile, one quests fetch) for the player in
   `data/players/current.txt`.
2. "Before" copy via `git archive` of the last commit before code changes; "after" copy from
   the finished work. Each runs in turn on port 8091 (`PORT` changed inside the copy).
3. Compare page text of Choose player, Home, Ready to play, AFK plan (5 h, 2 min), Active
   plan, Skills, Quests, Big goal and Progress. Only the two clock lines ("Stats updated
   HH:MM", "N snapshots · last HH:MM") are ignored, and their difference is shown.
4. **Expected differences:** path A's method, why line and "Also good"; "Why not the others?"
   (count and "(120)"); possibly B's pick or "Also good" (reasons in section 4). Each is shown
   to Chris line by line. **Any other difference is a failure:** stop and explain.
5. The same before/after diff of the terminal planner's output (5 h, 2 min, AFK).
6. On the frozen data: Invention's level from XP vs RuneMetrics' own level, both reported.

**Live:** after the commits, Chris presses Restart on the icon (the service is never touched
without asking), then the live app on 8080 is read in the built-in browser.
