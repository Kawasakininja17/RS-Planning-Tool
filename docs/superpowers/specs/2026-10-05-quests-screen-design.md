# Design: the Quests screen and choosing the big goal

2026-10-05 · approved in chat, part by part

## Goal

The bottom nav's **Quests** button opens a real screen showing the player's big
goal: tonight's quest, the skills still short, the quest chain with statuses,
and the quests they can start now. The big goal is chosen in the app,
remembered per player, and shared with the terminal. Today the app is fixed to
Plague's End (`BIG_GOAL_QUEST` in `app.py`).

## Decisions (made with Chris on 2026-10-05)

| Question | Decision |
|---|---|
| Hels can start 109 quests (49 Novice, 33 Intermediate, 20 Experienced, 3 Master, 1 Grandmaster, 3 Special; RuneMetrics, 2026-10-05). How to show them? | Show the ones on one of the 8 unlock chains (16 for Hels), best first. A **Show all** button opens the full list on the same page, grouped by difficulty. |
| What follows the chosen goal? | Home's Big goal card **and** the Active plan, not only the Quests screen. Home's card counts skill gaps across the **whole chain** (see below). |
| Where is the goal chosen? | Its own screen, `/quests/goal`, opened by a **Change goal** button on the Quests screen. |
| Quests marked "started" in RuneMetrics | Shown in an **In progress** panel (Hels has 4, none on an unlock chain). |
| Where the choice is saved | The file the terminal already uses: `data/players/<folder>/last_goal`. Picking in the app changes the terminal's default, and the other way round. |

Why the whole-chain count on Home: today the card counts only the final
quest's own requirements ("4 of 10 required skills below 75"). For other goals
that undercounts badly: for "Superheat Form and Crystal Mask" the final quest
says 2 skills short, but its 42-quest chain is 7 skills short. For Prifddinas
both counts are 4.

## 1. What the screens show

### Quests screen (`/quests`)

Top to bottom, inside the usual one-column page with the bottom nav ("Quests" lit):

1. Title **Quests**, the player's name, and "Stats updated …" (as on Skills).
2. **Big goal** panel: the unlock's name (e.g. "Prifddinas") as subtitle; "via Plague's End";
   the `unlocks` line from `data/unlocks.json`; "1 of 15 quests done" with a bar
   (done ÷ chain length); a **Change goal** button.
3. **Tonight's quest** (crimson frame) and **Also on the way**: exactly what the
   Active plan shows today (same helper, see part 2).
4. **Skills short for this chain**: exactly what the Active plan shows today (same helper).
5. **Quest chain**: every quest in `full_chain` order (prerequisites first).
   - Done: one short muted line, "Plague City · Done".
   - Others: the title; "Grandmaster · Long" (difficulty · length); a status line:
     "Ready now", "Started", "Started: <reasons>", or "Blocked: <reasons>", where reasons
     are `quest_state`'s own wording joined with "; " (e.g. "waiting on Biohazard; needs Ranged 75 (you have 73)").
6. **Other requirements (check these yourself)**: each line "<text> (for <quest>)".
   Hidden when there are none.
7. **Start now**: quests RuneMetrics says you can start that lie on any unlock chain,
   best first. Each: the title, then "Novice · Short · helps 2 of 8 unlocks".
   If none: "No quest on your unlock chains can be started right now."
   Under it, a **Show all N you can start** button (hidden when N is 0) that opens,
   on the same page, every eligible not-started quest grouped by difficulty
   (a small label per group, e.g. "Novice (49)", then the titles). The button then
   reads **Hide the full list**. No reload, no refetch.
8. **In progress**: each started quest's title and difficulty. Hidden when there are none.

### Change goal screen (`/quests/goal`)

- ← Back (to `/quests`), title **Big goal**.
- One wide button per unlock, in `unlocks.json` order. Two lines: the unlock's name,
  then "1 of 15 quests done · 4 skills short" (or "· no skills short"). The current
  goal is highlighted (glacial, like a selected chip).
- Tapping one saves it to `last_goal` and returns to `/quests`. If saving fails, a
  notice says "Couldn't save your goal choice" and the screen stays.

### Home's Big goal card

- Label "Big goal"; subtitle: the unlock's name (e.g. "Prifddinas"); muted lines:
  "via Plague's End", "1 of 15 quests done in its chain", and
  "4 skills short for its chain" ("1 skill short …" for one; "No skills short for its chain" for none).

### Active plan

Uses the chosen goal. Its wording is unchanged, so for a player whose goal is
Prifddinas it reads exactly as today:
"5 hours · big goal: Prifddinas (Plague's End)", "Skills still short for Plague's End".

### Which goal

`goal_for` (part 2): the player's `last_goal` if it names one of the unlocks,
otherwise the first unlock in `unlocks.json` (Prifddinas), as the terminal menu does.

## 2. How it is built

### `quest_path.py`: new functions (pure, testable)

| Function | Returns |
|---|---|
| `goal_for(unlocks, username)` | The unlock dict for the player's saved goal, else `unlocks[0]`. |
| `quest_rank(title, unlocks, quests, account)` | The sort key used for "best first": (most unlocks helped, shortest, easiest). Lifted out of `ranked_doable` unchanged; `ranked_doable` then calls it. |
| `chain_rows(goal, quests, account)` | A list, in `full_chain` order, of `{"title", "state", "reasons", "difficulty", "length"}`; `state`/`reasons` from `quest_state`, `difficulty` from `difficulty_name`, `length` from `quests.json`. |
| `other_requirements(chain, quests, account)` | A list of `(text, title)` for unfinished quests in the chain, in chain order. `print_quest_path` calls it instead of building the list inline. |
| `useful_to_start(unlocks, quests, account)` | Titles RuneMetrics marks `userEligible` and `NOT_STARTED` that are in any unlock's `full_chain`, sorted by `quest_rank`. |
| `eligible_by_difficulty(account)` | `[(difficulty name, [titles]), ...]` in `DIFFICULTY_NAMES` order (Novice … Grandmaster, then Special), empty groups left out. A difficulty code not in `DIFFICULTY_NAMES` (none today: RuneMetrics sent only 0–4 and 250 on 2026-10-05) gets its own group at the end, named "Unknown (<code>)" as the terminal prints it. Built from `rs3_planner.available_quests({"quests": list(account["quests"].values())})`, so it is the same list and order the terminal prints. |
| `started_quests(account)` | Titles with RuneMetrics status `STARTED`, sorted by name. |

### `quest_path.py`: two repairs

- `read_last_goal` also returns `None` on `ValueError`. A non-UTF-8 file raises
  `UnicodeDecodeError`, which is a `ValueError`, not an `OSError`, and would crash the screen today.
- `save_last_goal` returns `True` when saved, `False` when not. The terminal ignores the result, as before.

### `app.py`

- `BIG_GOAL_QUEST` and `GOAL` are removed. A helper `current_goal()` returns
  `goal_for(UNLOCKS, CURRENT["name"])`; Home, the Active plan and the Quests screens use it.
- `big_goal_numbers(account)` becomes `big_goal_numbers(goal, account)`, returning
  chain length, quests done and the number of skills short across the chain (`len(skill_gaps(...))`).
- The Active plan's Tonight's quest / Also on the way panels and its skills-short
  panel move into two helpers, `tonight_panels(goal, account)` and
  `skills_short_panel(goal, account, title)`, used by both the Active plan and the
  Quests screen. (`title` lets the Active plan keep "Skills still short for Plague's End"
  while Quests says "Skills short for this chain".)
- New pages `/quests` and `/quests/goal`; `bottom_nav`'s Quests button opens `/quests`.
  Pages with no player chosen redirect to `/player`; no stats → the usual "No stats loaded" panel.
- The Show all list uses NiceGUI's visibility toggle; nothing is fetched.

### `static/app.css`

One style for the two-line goal buttons (a wide chip whose content stacks name over
progress, left-aligned, ≥44px tall). Existing colours only.

### `data/unlocks.json`

Two `why_it_matters` lines that speak to one player's own plan become neutral.
No wiki fact changes.

| Unlock | Before | After |
|---|---|---|
| Vibrant energy money method | Your Path C question; it also needs the Divine Conversion relic | This money method also needs the Divine Conversion relic |
| Lletya animica mine | A third light animica mine for Path A | A third light animica mine |

Run `python3 check_methods.py` after the edit.

### What does not change

- No new RuneMetrics calls: every screen uses the data already loaded for the player.
- The terminal's printed output (see the proof in part 3).
- `full_chain`, `quest_state`, `skill_gaps`, `goal_progress`, `ranked_doable`'s results.

## 3. Testing and proof

### Automatic tests (`tests/test_quest_path.py`)

Standard library only, no network, never the real `data/players/`. A small
made-up quest tree and a made-up "Some Player" account.

- `goal_for`: saved goal found; unknown saved name → first unlock; non-UTF-8 file → first unlock; nothing saved → first unlock.
- `save_last_goal` returns `True` normally and `False` when the folder can't be written.
- `chain_rows`: prerequisites first; done / ready / started / blocked with the right reasons.
- `useful_to_start`: only eligible + not started + on a chain; best first; a subset of `eligible_by_difficulty`'s titles.
- `eligible_by_difficulty`: group order; groups add up to the full eligible list; empty groups left out.
- `started_quests`, `other_requirements`: expected entries.
- `quest_rank`: `ranked_doable` gives the same order as before for the made-up tree.

Before the first (failing) run of any test that redirects `players.PLAYERS_DIR`,
check that the code it calls honours the redirect (lesson from the last session).

### Proof that refactors change nothing

RuneMetrics replies for Hels are frozen in the session scratch folder (the quests
reply is saved; one profile reply is saved alongside it), so live XP changes
don't muddy the diffs.

- **Terminal:** `plan_session.py --session active --goal 1` with the frozen replies,
  output saved before and after. The diff must be empty.
- **App:** a throwaway copy of the project in the scratch folder, on another port,
  fed the frozen replies, with its own `data/players/` (the real one is never touched).
  Page text of Home and the Active plan saved before and after. The only allowed
  difference is the Big goal card's new wording.
- **Sanity values for Hels** (frozen data): Prifddinas 1 of 15 quests done; 4 skills short;
  Tonight's quest unchanged; 109 eligible; 16 on unlock chains; 4 in progress.

### Steps (stop and wait for Chris after each; commit each; never push without asking)

1. **2a: the logic.** The new `quest_path.py` functions with tests, the two repairs,
   the `unlocks.json` wording, the terminal proof. Nothing visible changes in the app.
2. **2b: the goal in the app.** `current_goal()`, Home's card, the shared panel helpers
   in the Active plan. App proof.
3. **2c: the new screens.** `/quests`, `/quests/goal`, the nav button, phone-width
   (375px) check, README. Live check: choose another goal in the app and confirm the
   terminal's menu defaults to it; then set Hels's goal back to Prifddinas (the only
   change to real player files, reported when done).
