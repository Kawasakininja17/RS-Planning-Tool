# Design: methods for early and mid-level accounts

2026-10-05 · approved in chat, part by part

## Goal

Any player running their own copy gets real AFK paths A, B and C, not only
late-game accounts. Today `data/methods.json` holds 12 hand-checked methods
that all need level 60 or more in their skill (several need 80–104), so a
mid-level account gets three empty paths. (Since commit `749ef50` the app at
least shows why, under "Why not the others?".)

## Decisions (made with Chris on 2026-10-05)

| Question | Decision |
|---|---|
| Which accounts and skills? | The AFK-friendly skills, at all levels: from the first AFK method a skill has up to where today's methods start. A skill counts if the wiki itself describes an AFK or low-intensity method for it. Roughly 20–30 training entries; the research decides the exact list. |
| A method used past its level band? | New optional field `max_level`. Past it the method is ruled out as "outgrown", so a wiki rate is only ever used for the band it was quoted for. |
| Low-level money methods (Path C)? | Yes, a few: only ones whose wiki page gives a gp/hr figure, each dated (the figure follows live GE prices). |
| How the data is gathered | Research first; Chris reviews a table; only approved entries go into `methods.json` (approach A). |

## Rules that keep holding

- Wiki facts only, from pages actually opened. Anything the wiki doesn't state is `null`, marked "wiki doesn't say" in the review table.
- Pages are read as their exact page text in the built-in browser. The web-fetch tool is not used for numbers: it passes pages through a summarising model that could alter a figure.
- `python3 check_methods.py` passes after every data edit.
- No new RuneMetrics calls. No other players' names in the repo (docs, tests, commits); the second test player is used only live in the app.

## 1. The data

### New field `max_level`

- Every method has `max_level`: a whole number 1–120, or `null` (no upper limit).
- When a number, it must be ≥ `min_level`.
- The 12 existing methods get `"max_level": null`, so their behaviour does not change.
- The `about` text in `methods.json` gains one sentence: `max_level` is the top of the level band the wiki's rates were quoted for (`null` = no upper limit).

### New entries

Each new method follows today's format plus `max_level`:

- `min_level` / `max_level`: the wiki's own level band for the quoted rate.
- `xp_per_hour_low` / `xp_per_hour_high` (training) or `gp_per_hour` with `gp_after_tax` (money), from the page.
- `minutes_between_clicks`: the wiki's figure in minutes if it gives one, else `null` with the reason in `notes` (the planner keeps such methods, marked "click time unknown").
- `requirements` (quests, other, skills, unlocks) as the page lists them; things RuneMetrics can't see become `requirements.unlocks` that the player answers, as today.
- `source_url`, `checked_date` (the day the page was read), `notes`, `unverified`.

## 2. The code

### `check_methods.py`

- `max_level` joins `REQUIRED_FIELDS` (unknown or missing fields are already refused).
- Problems reported in plain words:
  - not `null` and not a whole number from 1 to 120 → "<label>: max_level must be a whole number from 1 to 120, or null"
  - below `min_level` → "<label>: max_level (29) is below min_level (30)"
- The printed table shows the band in the level column: `30-59`, or `90+` when `max_level` is `null`.

### `plan_session.py`

One new check in `check_method_for_session`, beside the `min_level` check:

- A method is **outgrown** when `max_level` is a number and **every** skill it trains (`skill.split("/")`) is above `max_level`. A two-skill method stays offered while either skill is still inside the band.
- The band includes its top level: a 30–59 method is still offered at exactly 59.
- Reason, added to the blocked list: "you've outgrown this (Woodcutting 84; this method's rates are for levels 30–59)". For a two-skill method, each skill is named with its level, joined by " and ".
- It reaches the terminal's "Ruled out" list and the app's "Why not the others?" list with no app change.

### Not changed

`app.py`, `quest_path.py`, how paths A/B/C are picked (`pick_paths`), and RuneMetrics usage.

### `README.md`

One short paragraph: methods now cover early and mid levels; each has a level band, and a method you've outgrown is listed under "Ruled out" / "Why not the others?" with the reason.

## 3. Testing, the review gate and steps

### Automatic tests (written first, watched fail)

Standard library only, no network, never the real `data/players/`.

- `tests/test_check_methods.py`: `max_level` missing → problem; `null` → fine; whole number ≥ `min_level` → fine; below `min_level` → the plain message; not a whole number or outside 1–120 → problem.
- `tests/test_plan_session.py`: inside the band → offered; exactly at `max_level` → offered; one level past → ruled out with the "outgrown" wording; `null` → never outgrown; two-skill method → offered while either skill is inside the band, ruled out (both skills named) when both are past it.
- Existing test fixtures that build a method get `"max_level": None` (a fixture update, not a behaviour change).

### Proof that the existing 12 methods are unchanged

With frozen RuneMetrics replies for Hels in the session scratch folder (fetch one fresh profile and quests reply if the earlier ones are gone):
`plan_session.py --user "Hels Glasglo" --hours 5 --minutes 2 --session afk` and `--session active --goal 1`,
output saved before and after step 3a. The diff must be empty. The only allowed visible change anywhere is the
`check_methods.py` table's level column (`90` → `90+`).

### The review gate

The research produces a review table in the scratch folder, sent to Chris as a file and not committed. For each candidate:
name, type, skill, level band, XP/hr or gp/hr (and after-tax or not), click time, requirements, the exact line(s) quoted
from the wiki for every number, the page address and the date read. "Wiki doesn't say" wherever a value is `null`.
Chris keeps or strikes each entry; only kept entries go into `methods.json`.

### Live check after data entry

One RuneMetrics fetch per player per app run.

- The second test player, in the app only: paths A, B and C filled; every number shown matches the review table.
- Hels: paths unchanged, unless a new method truly beats an old one for her; if so, show Chris which and why before committing.

### Steps (stop and wait for Chris after each; commit each; never push without asking)

1. **3a: the `max_level` field.** `check_methods.py`, `plan_session.py`, tests, `null` on the 12 existing methods, `about` sentence, frozen proof. No new methods.
2. **3b: research.** Wiki pages read in the built-in browser; the review table sent to Chris. Nothing committed.
3. **3c: data entry.** Approved methods into `methods.json`; `check_methods.py` passes; live check; README paragraph.
