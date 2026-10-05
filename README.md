# RS3 Planner

A small personal planning tool for RuneScape 3. It reads a player's **public**
RuneMetrics data and shows:

- How much XP each skill still needs to reach 99, smallest gap first, plus the total.
- Quests the player can start right now (eligible but not yet started), with difficulty.

It only reads public web pages. It never touches or controls the game client.

## Requirements

- Python 3 (already included on most Linux systems).
- An internet connection.
- The terminal scripts need nothing else. The browser app needs NiceGUI,
  installed into a virtual environment (below).

## Browser app

A phone-friendly page with Home, Ready to play and your plan.

**One-time setup** (creates `.venv/`, the project's private Python toolbox,
and installs NiceGUI into it, not into your system):

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

**Start it** (from this folder):

```bash
.venv/bin/python app.py
```

Then open **http://127.0.0.1:8080** in your browser. Stop it with Ctrl+C in the terminal.

- It only listens on this computer (127.0.0.1), so other devices on your network can't reach it.
- It fetches RuneMetrics once when it starts, and again only when you press **Refresh**.
- Every fetch saves a snapshot to `data/snapshots/` (kept out of git) for a future Progress screen.
- Fonts (Uncial Antiqua, Cinzel, Alegreya; SIL Open Font License) and icons (Lucide; ISC licence)
  are bundled in `static/`, with their licences, so it works offline.
- All numbers come from the same code as the terminal scripts.

## How to run the terminal version

Open a terminal in this folder, then:

```bash
python3 rs3_planner.py
```

That uses the default player, **Hels Glasglo**. To look up someone else, put
the name after the script, in quotes:

```bash
python3 rs3_planner.py "Some Player"
```

## Training and money methods

`data/methods.json` is a hand-checked list of AFK training and money methods.
Every number comes from the RuneScape Wiki page named in its `source_url`.
`null` means the wiki didn't give that value. To check the file and see it as a table:

```bash
python3 check_methods.py
```

Run this after every edit to `methods.json`. It names any missing field,
typo or broken value, and the line of any JSON syntax error.

## Planning a session

```bash
python3 plan_session.py
```

It asks three questions (press Enter to keep the default in brackets):
how many hours you have, the most minutes you can go between clicks, and
whether the session is AFK (1) or active (2). You can also give the answers up front:

```bash
python3 plan_session.py --hours 5 --minutes 2 --session afk
```

It reads your live account, keeps only the methods you can do right now,
and suggests three paths:

- **A, finish something:** the skill closest to 99 that has a ready method
- **B, max XP:** the most XP per hour (judged on the low end of each range)
- **C, gold:** the most gp per hour

Methods whose click time the wiki doesn't give are kept, but marked
"click time unknown". Everything ruled out is listed at the end with the reason.

When you unlock something listed under `missing` in `data/methods.json`,
delete that line. Levels and quests are checked automatically.

A `^` after a gp figure in `check_methods.py` means the wiki only gives it
before Grand Exchange tax; the planner warns when it compares such a figure
with after-tax ones.

## The quest path (active sessions)

An active session first shows a menu of big goals (from `data/unlocks.json`)
with your progress on each. Type a number; Enter keeps your last choice.
You can also pick it up front: `--goal 1` or `--goal "Prifddinas"`.

For the chosen goal it shows the full quest chain (prerequisites first) with
the status of each quest, the skill levels still needed, other requirements
to check yourself, and **tonight's quest**: the ready quest that helps the
most of your big unlocks, then the shortest, then the easiest.

Quest requirements live in `data/quests.json`, fetched from the wiki. To
refresh them (for example after adding an unlock to `data/unlocks.json`):

```bash
python3 tools/fetch_quest_data.py
```

## Checking the data files

```bash
python3 check_methods.py
```

checks all three data files (methods, unlocks, quests) and stops with a clear
list of problems if anything is broken. Run it after every edit.

## Good to know

- **Private profiles:** if the player's RuneMetrics profile is private (or the
  name is misspelled), the script prints a short message and stops. It won't crash.
- **Invention** uses the harder "elite" XP curve, so its 99 needs 36,073,511 XP
  instead of 13,034,431.
- The RuneMetrics web addresses are unofficial. If Jagex changes them, this
  script may stop working until it is updated.
