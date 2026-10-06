# Design: the Progress screen

2026-10-06 · approved in chat, part by part

## Goal

The bottom nav's **Progress** button (the last "coming soon") opens a screen
charting the current player's saved snapshots over time. Its main job is to answer
**"Am I closing on max cape?"**; it also shows **what was gained lately** and
**how one skill has grown**. It reads only the snapshot files the app and terminal
already write on every fetch (`snapshots.py`); it never fetches.

## Decisions (made with Chris on 2026-10-06)

| Question | Decision |
|---|---|
| What is the screen for? | Main job: closing on max cape. Also: recent gains, and one skill's growth. Pace and forecasts are left out. |
| Which number does the main chart follow? | **XP still to go for max cape**, counting each skill only up to its 99 amount (Invention: elite 99), the same rule as Home's Max cape card. Total XP is shown as a plain number, not charted. |
| Many snapshots on one day | Charts use **one point per day: the last snapshot of that day**. |
| Thin data | 0 snapshots: a short panel saying none are saved yet. 1 day only: no charts (a line needs 2 points); numbers instead. Charts appear from the 2nd day on. |
| Gain spans | **Today**, **Last 7 days**, **Since first snapshot**, each labelled with its real start time. |
| Picking a skill | A **dropdown** of all 29 skills (closest to 99 first); it opens on the skill that gained the most in the last 7 days. |
| Chart library | **`ui.echart`** (ECharts 6, bundled inside NiceGUI, Apache 2.0). |

Why max cape and not total XP: on 2026-10-05 Hels's total rose by 726,291 XP, but
nearly all of it was Woodcutting, already past 99. Her max cape progress moved only
from 32.8542% to 32.8550% (the 3,235 Fletching XP). A total-XP chart would have
shown a big climb; the max cape chart shows the honest, nearly flat line.

### Chart libraries checked (NiceGUI 3.17.1 in `.venv/`, 2026-10-06)

| Element | Offline? | Verdict |
|---|---|---|
| `ui.echart` | Yes: ECharts 6 is bundled in `nicegui/elements/echart/dist/` (about 1.7 MB) and served by the app itself. Its only network fetch is an optional theme address, which we don't use. | **Chosen.** Apache 2.0; hover tooltips; styled from Python with a settings dictionary. |
| `ui.plotly` | Yes: plotly.js 3 bundled (4.6 MB). | Not chosen: four times the download, and a toolbar and dark styling to override. MIT licence. |
| `ui.highchart` | Not installed; needs the separate `nicegui-highcharts` package. | Ruled out: an extra dependency under a licence NiceGUI's own code calls "restrictive". |
| `ui.pyplot`, `ui.line_plot` | Need matplotlib, which isn't installed. | Ruled out: a new dependency, and flat pictures with no hover. |

## 1. What the screen shows

`/progress`, inside the usual one-column page, with **Progress** lit in the bottom nav.
Pages with no player chosen redirect to `/player`. The screen works from the
snapshot files alone, so it still shows everything saved when RuneMetrics is down
and no live stats are loaded.

### Header

- Title **Progress**, the player's name.
- "20 snapshots · last 15:33, 5 Oct" (readable snapshots; the newest one's time).
- If any snapshot file couldn't be read: "1 snapshot file couldn't be read and was skipped."
  ("N snapshot files couldn't be read and were skipped." for more than one.)

### No snapshots

Instead of the panels below, one panel: **"No snapshots saved yet"**, then
"One is saved each time stats are fetched (at start-up and on Refresh)."

### Max cape panel

- Label "Max cape"; big number: the newest snapshot's max cape %, one decimal
  ("32.9%"), as on Home.
- "269,276,641 XP to go", then "Total XP 194,520,179" (RuneMetrics' `total_xp`).
- **Chart: XP to go for max cape, one point per day** (see part 2, *Charts*). A falling
  line means closing in.
- With fewer than 2 days of points: no chart; the muted line
  "A chart appears once you have snapshots from 2 different days."
- **Show the numbers** button (under the chart, only when the chart shows): opens the
  day-by-day values on the same page, newest first, e.g. "5 Oct · 269,276,641 to go".
  The button then reads **Hide the numbers**. Nothing is fetched.
- If the newest snapshot lacks any of the 29 skills, the % and "to go" show "—"; a day
  whose snapshot lacks a skill is left out of the chart.

### Gained panel

Label "Gained". Up to three lines, in this order. Each compares the **newest snapshot**
with an older **start snapshot** and shows:
"**Today:** +726,291 XP · +3,235 toward max cape · since 08:39".

- XP = difference in `total_xp`; "toward max cape" = difference in capped XP (part 2,
  `max_cape_xp`). Either shows "—" if it can't be worked out. Numbers are whole, with
  commas, signed ("+" or "−").
- The start is written "since 08:39" when it is today, else "since 15:33, 5 Oct".

| Line | Start snapshot | Special states |
|---|---|---|
| Today | The last snapshot from before today; if none, the first snapshot from today. | No snapshot from today: "Today: no snapshot yet". The start would be the newest snapshot itself (the only one): "Today: only one snapshot so far". |
| Last 7 days | The last snapshot dated 7 or more days before today. | None that old: line left out. |
| Since first snapshot | The very first snapshot. | — |

- Last 7 days and Since first snapshot are **left out when their start is the same snapshot
  as the start of the nearest shown line above that has one** (no repeated numbers), or
  when their start is the newest snapshot itself. (Today never disappears; it uses its
  special states instead.) The end of every line is the newest snapshot, even when that
  isn't from today; the header shows its time.
  For Hels's real files on 2026-10-05 all three would start at 08:39, so only Today shows.

Below the lines, the label **"Skills that moved since <start>"** (same start wording),
then one line per skill that went up, biggest first: "Woodcutting +723,057".
The start is the Last 7 days start, or the first snapshot if none is that old. Skills
that didn't go up are not listed. If none moved: "No skill has moved since <start>."
Hidden entirely when there is only one snapshot.

### One skill panel

- Label "One skill"; a dropdown of all 29 skills in `skill_order` (closest to 99 first,
  finished skills last), opening on `default_skill`.
- Above the chart: "Woodcutting 99 · 28,718,588 XP". The level is the live one from
  `account.skill_rows` (so Invention past 99 reads "99+"); with no live stats loaded the
  level is left off: "Woodcutting · 28,718,588 XP". The XP is the newest snapshot's.
- **Chart: that skill's XP, one point per day.** Same 2-day rule and **Show the numbers**
  button ("5 Oct · 28,718,588 XP").
- With fewer than 2 days: "+723,057 XP since 08:39" (gain from the first snapshot to the
  newest, same start wording); with only one snapshot: "Only one snapshot so far."
- Choosing another skill redraws only this panel. Nothing is fetched.

## 2. How it is built

### `progress.py` (new): the logic, no drawing

Every function takes plain data (and `today`, a date) as input, so tests can use made-up
snapshots and dates instead of the real clock. A **snapshot** is
`{"when": datetime, "total_xp": number, "skills": {skill name: XP}}`.

| Function | Returns |
|---|---|
| `read_snapshots(username)` | `(snapshots, skipped)`: every readable `*.json` in `player_dir(username) / "snapshots"`, sorted by `fetched_at` (oldest first), and how many files were skipped. A file is skipped if it isn't valid UTF-8 JSON, `fetched_at` isn't an ISO date-time, `total_xp` isn't a number, or `skills` isn't a dict of numbers. Skill names not in `SKILL_NAMES` are ignored. A missing folder gives `([], 0)`. Never raises. |
| `max_cape_xp(skills)` | `{"done", "needed", "to_go", "percent"}`: each skill's XP capped at its 99 amount (`XP_FOR_99_ELITE` for Invention, `XP_FOR_99_NORMAL` otherwise), summed over the 29 skills. `None` if any of the 29 is missing. |
| `last_per_day(snapshots)` | The last snapshot of each calendar day of `when`, oldest day first. |
| `max_cape_points(snapshots)` | `[(date, XP to go)]` from `last_per_day`, leaving out days where `max_cape_xp` is `None`. |
| `skill_points(snapshots, skill)` | `[(date, XP)]` from `last_per_day`, leaving out days whose snapshot lacks the skill. |
| `since_text(when, today)` | "since 08:39" when `when` is today, else "since 15:33, 5 Oct". |
| `gain_lines(snapshots, today)` | The Gained panel's lines, in order, after the leave-out rules: each `{"name", "state", "start", "total", "max_cape"}`. `state` is `"gain"`, `"none_today"` or `"only_one"`; `start` is the start snapshot (or `None`); `total` and `max_cape` are the differences (or `None` when not `"gain"`, or when not computable). |
| `skills_moved(snapshots, today)` | `(start, [(skill, XP gained)])`: the start snapshot (the Last 7 days start, else the first snapshot) and the gains up to the newest, biggest first, only gains above 0, only skills in both snapshots. `(None, [])` when there are fewer than 2 snapshots. |
| `skill_order(skills)` | Skill names: not yet 99 first, by XP left to 99 (smallest first); then 99+ skills, most XP first. The same order as `account.skill_rows`. |
| `default_skill(snapshots, today)` | The first skill in `skills_moved`, else the first in `skill_order` of the newest snapshot. |

### `app.py`: drawing only

- New page `/progress`; `NAV_TARGETS` gains `"Progress": "/progress"`, so no nav button
  says "coming soon" any more (the `ui.notify` fallback stays for safety).
- The page calls `read_snapshots(CURRENT["name"])` on each visit (small files; read fresh
  so a new fetch shows straight away) and `datetime.date.today()` for `today`.
- The level text uses `skill_rows(entry["account"])` when the account is loaded.
- The dropdown is `ui.select` with the dark outlined look of the name box on Choose player;
  the One skill panel is a `ui.refreshable`, as on Ready to play.
- **Show the numbers** uses the same visibility toggle as Quests' "Show all".

### Charts: one helper, `line_chart(points, value_word)`

Builds the `ui.echart` settings for both charts. `points` is `[(date, value)]`;
`value_word` is "to go" or "XP" for the tooltip.

- **Date axis** (ECharts `type: "time"`), so missing days show as gaps with true spacing.
  Each date is sent as a local noon time string ("2026-10-05T12:00:00") so the browser's
  time zone can't shift it to the previous day.
- **Value axis zooms to the data** (`scale: true`); axis labels shortened in the browser
  ("269.3M", "723k").
- **Marks:** 2px line in glacial `#A8DCEB`, 8px dot markers with a 2px ring in the panel
  colour `#16241B`; no area fill; no legend (one line; the panel label names it).
- **Chrome:** transparent background (the panel shows through); axis text muted `#B9C3B2`
  in Alegreya (bundled font); gridlines solid 1px `#2E4636`; no toolbar.
- **Tooltip** on hover: "5 Oct · 269,276,641 to go"; background `#16241B`, border `#2E4636`,
  text parchment `#F0E8D6`.
- Two small JavaScript formatters (number shortening, tooltip text) are passed as strings
  in the settings, NiceGUI's documented way (a key starting with ":"). Each is commented.

### `static/app.css`

- `.chart`: full panel width and a fixed height that **includes** the axis labels
  (about 220px), so no scrollbar appears inside the panel.
- Dark styling for the skill dropdown. Existing colours only.

### What does not change

- No new RuneMetrics calls; when and how snapshots are saved (`snapshots.py`) is untouched.
- Home, Skills, Quests, Ready to play and the plans look and work exactly as before.
- The terminal scripts.

## 3. Testing and proof

### Automatic tests (`tests/test_progress.py`)

Standard library only, no network, never the real `data/players/`: made-up snapshots for
**"Some Player"** in a temporary folder, with `players.PLAYERS_DIR` pointed at it
(`player_dir` reads `PLAYERS_DIR` on every call; re-check this against the final code
before the first run).

- `read_snapshots`: oldest first by `fetched_at`; missing folder → `([], 0)`; broken JSON,
  non-UTF-8 bytes and missing fields each skipped and counted; unknown skill names ignored;
  a file written by the real `save_snapshot` reads back the same.
- `max_cape_xp`: capped at 99; Invention's elite 99; a missing skill → `None`; exact numbers
  worked out by hand for a made-up account. (The tests can't import `app.py`: it needs
  NiceGUI, and the tests run on plain `python3`. Agreement with Home's card is checked in
  the browser instead, see below.)
- `last_per_day`, `max_cape_points`, `skill_points`: last of each day; date order; days
  missing data left out.
- `since_text`: today vs another day.
- `gain_lines`: Today from yesterday's last snapshot; Today when all are from today;
  7-day start is the last snapshot 7+ days old; repeated starts left out; "none_today";
  "only_one"; no snapshots → `[]`.
- `skills_moved`: only gains above 0, biggest first, correct start; one snapshot → empty.
- `skill_order`: same order as `account.skill_rows` for the same made-up account.
- `default_skill`: most-moved skill; falls back to the first in `skill_order`.

Run the whole suite after every change (101 tests today).

### Proof that the other screens don't change

The old frozen replies were deleted when the last session tidied up, so:

1. Step 3a makes **one** live fetch of Hels (profile and quests, one request each) and saves
   the replies in `.superpowers/sdd/progress-screen/frozen/` (git-ignored).
2. A small `run_frozen.py` (scratch, not in the repo) runs a throwaway copy of the project
   on port 8091 that reads those replies instead of RuneMetrics. It must patch the names the
   app actually calls: `player_cache.load_profile` and `player_cache.load_quests` (imported
   by name from `rs3_planner`). The copy gets its own `data/players/` with a **copy** of
   Hels's snapshots; the real folder is never touched.
3. Page text of Home, Skills, Quests and the AFK plan (5 h, 2 min) is saved **before**
   `app.py` changes and **after** each app step. The diff must be empty.

The copy's start-up fetch writes a snapshot dated the day it runs, so the copy has **two
days** of Hels's data: the charts get tested on real numbers.

### Checks in the built-in browser (on the copy)

- **Offline:** the page's network requests all go to 127.0.0.1; none to the internet.
- **Phone width (375px):** layout, no clipped axis labels, no scrollbar inside a chart; screenshot.
- **Colour:** the dataviz skill's validator on the glacial line against `#16241B` in dark mode.
- **Same rule as Home:** Progress's max cape % and "XP to go" equal Home's Max cape card
  exactly (the copy's newest snapshot and Home's live stats come from the same fetch).
- Dropdown switching; Show the numbers; dates on the axis match the snapshot dates;
  the one-day and zero-snapshot states (a made-up player folder in the copy).

### Sanity values (Hels's real files, 20 snapshots, all 2026-10-05, 08:39–15:33)

Max cape 32.8550% ("32.9%") and 269,276,641 to go at 15:33 (269,279,876 at 08:39);
total XP 194,520,179; first to last: +726,291 total XP, +3,235 toward max cape;
skills moved: Woodcutting +723,057, Fletching +3,235. The frozen copy's values for
its new day are recorded when the replies are frozen.

### Steps (stop and wait for Chris after each; commit each; never push without asking)

1. **3a: the logic.** `progress.py` with its tests (tests first); freeze the replies and
   rebuild `run_frozen.py`; save the before page texts. Nothing visible changes.
2. **3b: the screen with numbers.** `/progress`, the nav button, header, no-snapshots panel,
   Max cape panel (number only), Gained panel, Skills that moved. Other-screens proof.
3. **3c: the charts.** `line_chart`, both charts, the dropdown, Show the numbers, CSS;
   offline, phone-width and colour checks; other-screens proof again; README (Progress
   section; drop "kept for a future Progress screen"). Delete the throwaway copy afterwards.
