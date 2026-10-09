# RS3 Planner

A small planning tool for RuneScape 3 that runs on your own computer and opens
in your web browser. Give it a public RuneScape name and it shows:

- **What to do with tonight's session:** three AFK paths (finish a skill, most
  XP, most gold) with two "also good" alternatives each, or an active plan with
  tonight's quest.
- **Skills:** all 29 skills with level, XP and XP left to 99, closest first.
- **Quests:** a big goal (like Prifddinas) with its whole quest chain, the
  skills you're still short, and the quests you can start right now.
- **Progress:** max cape progress over time, XP gained lately, and any skill's
  XP per day.

It only reads public data (RuneMetrics and the RuneScape Wiki). It never
touches or controls the game client, and it never asks for a password.

Plans assume a regular account. Ironman accounts aren't supported yet. Plans
may suggest training or money methods an ironman can't use.

## Install

### You'll need

- **Python 3.10 or newer.** Most Linux systems already have it; on a Mac or
  Windows, get it from [python.org](https://www.python.org/downloads/).
- **An internet connection** (to read RuneMetrics and to install the app's one helper, NiceGUI).
- Built and tested on Linux with Python 3.14.

### 1. Get the code

Either use git:

```bash
git clone https://github.com/Kawasakininja17/RS-Planning-Tool.git
```

```bash
cd RS-Planning-Tool
```

or, on the GitHub page, press the green **Code** button, then **Download ZIP**,
unzip it, and open a terminal in the unzipped folder.

### 2. One-time setup

This creates `.venv/`, the project's own private Python toolbox, and installs
NiceGUI into it (not into your system).

**Linux and Mac:**

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

**Windows (not tested yet):**

```bash
py -m venv .venv
```

```bash
.venv\Scripts\pip install -r requirements.txt
```

### 3. Start it

From the project folder:

**Linux and Mac:**

```bash
.venv/bin/python app.py
```

**Windows (not tested yet):**

```bash
.venv\Scripts\python app.py
```

Then open **http://127.0.0.1:8080** in your browser. To stop the app, press
**Ctrl+C** in the terminal; it says "RS3 Planner stopped."

### Updating later

If you used git, get the newest version with `git pull` in the project folder,
then run the setup's `pip install` line again (in case NiceGUI's version changed).
With a ZIP, download it again.

### Start it without a terminal (Linux)

On Linux you can have the app start by itself in the background each time you
log in, with an **RS3 Planner** icon (crossed swords) in your app list that opens
it in your browser. After the one-time setup above, run this once from the
project folder:

```bash
python3 tools/install_desktop.py
```

It adds two small settings files to your own account (no password needed) and
starts the app. To see those two files first, without changing anything:

```bash
python3 tools/install_desktop.py --show
```

- **Open it:** click the **RS3 Planner** icon. You can pin it to the dock
  (right-click it, then **Pin to Dash**). If the app isn't running, the icon
  starts it first.
- **Restart:** right-click the icon, then **Restart RS3 Planner**. Do this after
  editing `data/methods.json` or updating the app (see *Updating later*): the app
  reads its files only when it starts. A restart also fetches fresh stats.
- **Stop:** right-click the icon, then **Stop RS3 Planner**. It stays stopped
  until you click the icon again or next log in.
- It stops when you log out and starts again when you log in.
- If it doesn't start, a notification says why. The full log:
  `journalctl --user -u rs3-planner`
- The terminal way (`.venv/bin/python app.py`) still works, but only one copy can
  use the app's address. If the terminal says "address already in use", choose
  **Stop** on the icon first.
- Moved the project folder? Run the install again from the new folder. The
  folder's path must not contain `%`, `\`, `"`, `'`, `$` or a line break.

To remove it (your answers, goals and snapshots in `data/` stay):

```bash
python3 tools/install_desktop.py --remove
```

## Using the app

1. **Choose player.** The first time, type a RuneScape name and press **Look up**.
   Only the public RuneMetrics name is needed: never enter a password. The
   player's RuneMetrics profile must be public. Players you've looked up before
   appear under **Recent players**, one tap away.
2. **Home** shows max cape progress, the skills closest to 99, and your big goal.
   **Refresh** fetches fresh stats; **Switch player** goes back to step 1.
3. **Ready to play:** pick how long you can play, **AFK** or **Active**, and (for
   AFK) the most time you can go between clicks. Press **Show my plan**.
4. **Your plan (AFK)** gives three paths:
   - **A · Finish something:** your skill furthest through its current level that has a method you can do now
   - **B · Max XP:** the most XP per hour
   - **C · Gold:** the most gp per hour

   Each shows the rate, what the hours get you, and **Also good:** the next two
   best options. Some methods need things RuneMetrics can't see (like a smithing
   autoheater); the plan asks **I have it** / **I don't**, remembers your answer,
   and lets you change it under **Your answers**. **Why not the others?** explains
   every method that was ruled out.
5. **Your plan (Active)** shows tonight's quest, the next one on the way, and the
   skills still short for your big goal.
6. **Skills** (bottom bar): every skill with level, XP and XP left to 99.
7. **Quests** (bottom bar): your big goal's quest chain with the status of each
   quest, other requirements to check yourself, the quests you can start now
   (**Show all** for the full list) and the ones in progress. **Change goal**
   picks a different big goal.
8. **Progress** (bottom bar): how you're closing on max cape, from the stats
   snapshots saved each time stats are fetched. It shows your max cape % and the
   XP still to go (with a chart, one point per day, once you have two days),
   **Gained** today, over the last 7 days and since your first snapshot (with the
   skills that moved), and **One skill**: pick any skill to see its XP per day.
   **Show the numbers** lists the values behind a chart. Progress never fetches;
   it works from the saved files.

**Good to know**

- The app only listens on your own computer (127.0.0.1), so other devices on your
  network can't reach it. One person per copy.
- It also answers only when addressed as `127.0.0.1` or `localhost`, and refuses
  requests that other websites start, so a web page you visit can't use the
  planner behind your back. Such a request gets a short "Invalid host header" or
  "Refused" message instead.
- Each player is fetched from RuneMetrics once while the app runs, and again only
  when you press **Refresh**.
- Your answers, chosen goal and stat snapshots stay on your computer, in
  `data/players/<player>/` (never uploaded; kept out of git). The snapshots are
  what the Progress screen charts.
- Fonts (Uncial Antiqua, Cinzel, Alegreya; SIL Open Font License) and icons
  (Lucide; ISC licence) are bundled in `static/`, with their licences.

---

# For tinkerers: terminal scripts, data files and tests

Everything the app shows comes from the same code as these terminal scripts.
Commands below are for Linux and Mac, run from the project folder.

## How to run the terminal version

Open a terminal in this folder, then:

```bash
python3 rs3_planner.py
```

That uses the player you last chose in the app (or asks for a name). To look
up someone else, put the name after the script, in quotes:

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

Methods cover early, mid and late levels. Each has a level band (`min_level`
to `max_level`): the levels the wiki's rates were quoted for. Once you're past
a method's band in every skill it trains, the planner lists it under "Ruled out"
(in the app: **Why not the others?**) as "you've outgrown this".

How the band edges were set: where the wiki writes level ranges (Mining,
smelting bars, bonfires), they're copied as written, so neighbouring methods
share an edge level (iron 10–20, coal 20–30) and at that level both are offered;
the faster one wins. Where the wiki gives only a starting level (Fort Forinthry
buildings, pickpocketing targets), each band ends one level before the next
listed method that needs nothing extra (no quest) starts, so a missing quest
never leaves a level with nothing to do. `max_level` itself still counts as
inside the band.

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

```bash
python3 plan_session.py --user "Some Player"
```

It reads your live account, keeps only the methods you can do right now,
and suggests three paths:

- **A, finish something:** the skill furthest through its current level that has a ready method
- **B, max XP:** the most XP per hour (judged on the low end of each range)
- **C, gold:** the most gp per hour

Under each path, **Also good** names the next two best methods for that path, so
you have a choice. Methods whose click time the wiki doesn't give are kept, but
marked "click time unknown". Everything ruled out is listed at the end with the
reason; in the app, methods you've finished (120) or outgrown are just counted.

Some methods need things RuneMetrics can't see, like a smithing autoheater. The
plan shows "Check: needs …" with **I have it** / **I don't**; your answers are saved
in `data/players/<player>/answers.json` (kept out of git) and can be changed under
**Your answers**. "I don't" rules the method out. Levels and quests are checked
automatically.

A `^` after a gp figure in `check_methods.py` means the wiki only gives it
before Grand Exchange tax; the planner warns when it compares such a figure
with after-tax ones.

## The quest path (active sessions)

An active session first shows a menu of big goals (from `data/unlocks.json`)
with your progress on each. Type a number; Enter keeps your last choice
(remembered per player).
You can also pick it up front: `--goal 1` or `--goal "Prifddinas"`.

In the browser app, choose the big goal on the Quests screen (**Change goal**).
The app and the terminal share the choice (`data/players/<player>/last_goal`),
so picking a goal in one makes it the default in the other. Home's Big goal card
and the Active plan follow it.

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

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Runs the automatic checks (standard Python, nothing to install). They never use
the internet or your real player files.

## Good to know

- **Private profiles:** if the player's RuneMetrics profile is private (or the
  name is misspelled), the script prints a short message and stops. It won't crash.
- **Invention** uses the harder "elite" XP curve, so its 99 needs 36,073,511 XP
  instead of 13,034,431.
- The RuneMetrics web addresses are unofficial. If Jagex changes them, this
  script may stop working until it is updated.
