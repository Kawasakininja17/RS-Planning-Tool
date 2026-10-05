# Design: choosing a player (the "username screen")

2026-10-05 · approved in chat, step by step

## Goal

Anyone who downloads RS3 Planner can type their public RuneScape name and the
whole app (Home, plans, later screens) plans for that player. It is not a
login: the app only ever asks for a public RuneMetrics name, never a password
or anything private.

## Decisions (made with Chris on 2026-10-05)

| Question | Decision |
|---|---|
| Who uses it, where? | Each person runs their own copy on their own computer. Server stays on 127.0.0.1. One person per copy. |
| Requirements RuneMetrics can't check (e.g. a smithing autoheater) | The method stays in the plan with a "Check: needs X" line and **I have it / I don't** buttons. The answer is saved per player. "I don't" blocks the method, like today's `missing` list. |
| Ironman accounts | Not supported in this round. The app and README say so plainly (wording below). RuneMetrics' profile reply has no ironman field (checked 2026-10-05), so this would need a player setting later. |
| Which player is shown | One "current player" for the whole app, remembered across restarts (approach A). Fetched data is cached per name. |

## 1. Splitting `data/methods.json`: wiki facts vs player facts

`methods.json` holds wiki facts only. The `missing` field is removed and replaced
by two requirement types:

- `requirements.skills`: extra level checks beyond `min_level`, e.g. `{"Mining": 99}`.
  Checked live against RuneMetrics for any player.
- `requirements.unlocks`: things RuneMetrics can't see, as a list of
  `{"id": "smithing-autoheater", "text": "<the wiki's wording>"}`.

Also:
- `notes` and `unverified` lose every sentence about Hels ("you have 101", "you
  said on 2026-10-04 ..."). `unverified` items become general assumptions behind
  the rate ("the 117k rate assumes all mattock upgrades").
- `about` no longer names Hels.
- No wiki number changes.

How today's `missing` entries move:

| Method | Today (`missing`) | After |
|---|---|---|
| Forging elder rune platebodies | Smithing autoheater, "you don't own one" | unlock `smithing-autoheater`; Hels answers `false` |
| Mining banite | Mining cape (needs 99 Mining) | `requirements.skills: {"Mining": 99}` |
| Harvesting vibrant energy | Archaeology 98, Invention 86, Divine Conversion relic | unlock `divine-conversion-relic`, text: needs 98 Archaeology, 86 Invention and 85 Divination (all boostable) to unlock, per the wiki's Divine Conversion page. The wiki gives no level requirement for using it once unlocked, so the levels are not separate checks. Hels answers `false`. |
| Gravitron research debris | (none; "assistant qualification" sat in `other`) | unlock `assistant-qualification`; Hels answers `true` |

Per-player answers live in `data/players/<folder>/answers.json`, e.g.
`{"smithing-autoheater": false, "divine-conversion-relic": false, "assistant-qualification": true}`.

Planner behaviour for each unlock:
- no answer: not blocked; warning "Check: needs <text>"
- `false`: blocked with reason "you said you don't have: <text>"
- `true`: nothing shown

`check_methods.py` validates the new fields: every unlock needs a unique,
non-empty id and text, and `skills` must use real skill names and levels 1–120.

## 2. Players, state and the username screen

### New module `players.py`
Everything about "a player" lives in one place:
- `folder_name(name)`: lower case, spaces → `+`. `+` can't appear in a RuneScape
  name, so two players never share a folder. Hyphens and underscores are kept
  (the wiki's Display name page: underscores are not treated as spaces).
- `player_dir(name)` → `data/players/<folder>/`
- `read_current()` / `save_current(name)` → `data/players/current.txt`
- `read_answers(name)` / `save_answer(name, unlock_id, value)` → `answers.json`
- `check_name(text)` → `(cleaned_name, problem)`. Rules (wiki Display name page):
  trimmed; 1–12 characters; letters, digits, spaces, hyphens, underscores only.
  Leading `-`/`_` is NOT rejected: the wiki says new names can't start with one,
  so older names may.

`data/players/` is git-ignored as a whole.

### Per-player folder contents
```
data/players/hels+glasglo/
    answers.json
    last_goal          (was .last_goal in the project root)
    snapshots/         (was data/snapshots/; the 8 existing files are all Hels's)
```

### App state (`app.py`)
- The fixed `USERNAME` and single `STATE` become `CACHE = {name: {profile, account,
  fetched_at, error}}` plus the current player's name.
- Each name is fetched once per app run. Refresh re-fetches the current player only.
- On start-up: if `current.txt` names a player, fetch them (as today). If not, every
  page sends you to `/player`.
- The name shown is the one RuneMetrics returns (`profile["name"]`), so capitals are right.

### Screen `/player`
- Title, one text box ("RuneScape name"), crimson **Look up** button.
- Notices: "Only your public RuneMetrics name. Never enter a password." and
  "Ironman accounts aren't supported yet. Plans may suggest training or money
  methods an ironman can't use."
- Recent players: one tappable row per folder in `data/players/` (shows the name
  saved in that player's latest snapshot).
- Look up: `check_name` first (no fetch for invalid input). Then fetch in the background
  with the existing `load_profile`/`load_quests`. Failure (private, unknown, no internet):
  show the message in a crimson panel and keep the current player unchanged. Success:
  save as current, save a snapshot to their folder, go to Home.

### Other screens
- Home: player name with a **Switch player** button.
- AFK plan: each unanswered unlock shows "Check: needs X" with I have it / I don't.
  Tapping saves the answer and redraws the plan.

### Terminal scripts
- `rs3_planner.py`, `plan_session.py`: `--user` if given, otherwise the remembered
  current player, otherwise ask. "Hels Glasglo" is no longer hard-coded as the default.
- `quest_path.py`: the last goal is read from and saved to the player's folder.

## 3. Build order and proof

Each step is a stop: show proof, commit, wait for Chris.

**1a. Data split.** `players.py` (answers part), new `methods.json` fields,
`check_methods.py`, `plan_session.py`, Hels's `answers.json`.
Proof: save `plan_session.py` output for Hels before the change for these
combinations, then diff after:
`--hours 5 --minutes 2 --session afk`, `--hours 1 --minutes 1 --session afk`,
`--hours 8 --minutes 5 --session afk`, `--hours 5 --minutes 2 --session active --goal 1`.
Paths A–C must be identical; the ruled-out list must name the same methods; only
the wording of some reasons may change, and each changed line is shown to Chris.
`python3 check_methods.py` passes.

**1b. Per-player folders.** Move snapshots and `last_goal`; `snapshots.py` writes
to the player folder; `current.txt`; terminal scripts use the remembered player.
Proof: checksums of the 8 snapshots match before and after the move; a fresh fetch
writes into `data/players/hels+glasglo/snapshots/`.

**1c. The app.** Cache, `/player`, Switch player, unlock buttons.
Proof in the built-in browser, with screenshots:
- Hels's Home matches the sanity values (live data permitting).
- An invalid name (e.g. 13 characters) is rejected without a fetch.
- A non-existent name shows RuneMetrics' error and Hels stays current.
- A second public player (the name Chris gave in chat; not written into the repo) loads; switching back to Hels needs no
  new fetch (server log).
- "I don't" on an unlock blocks the method and appears in `answers.json`.
- A private profile is tested only if one can be found; otherwise reported as untested.

## Out of scope

Ironman support, network access, the Skills, Quests and Progress screens (each
gets its own design round), and the parked ideas in HANDOFF.md.
