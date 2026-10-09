#!/usr/bin/env python3
"""
RS3 Planner - browser app (NiceGUI)
===================================

Shows the planner in your browser. All the planning logic lives in the
existing files; this one only draws it:
  rs3_planner.py   fetching RuneMetrics, XP-to-99 list
  account.py       levels from XP
  check_methods.py loading and checking the data files
  plan_session.py  paths A, B and C (build_plan, path_lines)
  quest_path.py    quest chains and tonight's quest
  snapshots.py     saving an XP snapshot on every fetch
  progress.py      the Progress screen's numbers (from the saved snapshots)
  players.py       which player: folders, answers, the remembered player
  player_cache.py  the in-memory store of fetched players

Choose a player on the /player screen (any public RuneScape name). Each name
is fetched once while the app runs, and again only when you press Refresh.

Start it (from the project folder):
    .venv/bin/python app.py
then open http://127.0.0.1:8080 in your browser. Stop it with Ctrl+C.

It listens on 127.0.0.1 only, so other devices on your network can't reach it.
It also answers only to the names 127.0.0.1 and localhost, and refuses requests
that other websites start (see host_lock.py), so web pages can't use it.

As the Windows app (a bundle made by tools/build_exe.py) it saves data in the
user's own app-data folder, uses port 8095 and opens the browser by itself
(see bundle.py). Run from the project folder, none of that changes.
"""

import copy
import datetime
import re
import webbrowser   # the Windows app opens an already-running copy in the browser
from multiprocessing import freeze_support
from pathlib import Path

from fastapi.middleware.trustedhost import TrustedHostMiddleware   # refuses requests for any other name
from fastapi.responses import RedirectResponse   # sends a page to /player when no player is chosen
from nicegui import app, native, run, ui

from account import level_table, skill_rows
from bundle import (
    LAST_PORT, PREFERRED_PORT, choose_port, is_bundled, planner_answers, stop, user_data_dir, version_text,
)
from check_methods import load_methods, load_quest_files
from host_lock import OriginLock, allowed_origins
from plan_session import also_text, build_plan, path_lines, split_ruled_out
from player_cache import entry_for, fetch_safely, needs_fetch, record_failure, record_success
from progress import (
    default_skill, gain_lines, max_cape_points, max_cape_xp, read_snapshots, set_aside_future, signed_xp,
    since_text, skill_gain_since_first, skill_order, skill_points, skills_moved,
)
from players import (
    check_name, folder_name, known_players, read_answers, read_current, save_answer, save_current,
)
from quest_path import (
    chain_rows, difficulty_name, eligible_by_difficulty, goal_for, goal_progress, other_requirements,
    ranked_doable, save_last_goal, skill_gaps, started_quests, unlock_count, useful_to_start,
)
from rs3_planner import (
    INVENTION_ID, SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL, xp_needed_for_99,
)
from snapshots import save_snapshot

HERE = Path(__file__).parent
HOST = "127.0.0.1"   # this computer only - never 0.0.0.0
PORT = 8080
ALLOWED_HOSTS = [HOST, "localhost"]   # the names this app answers to; anything else is refused
NO_VALUE = "—"       # shown when a value is missing; never a made-up number

HOUR_CHOICES = [1, 2, 3, 5, 8]
DEFAULT_HOURS = 5
# Click chips -> the planner's "most minutes between clicks" setting.
# "1-2 min" means you may be away up to 2 minutes, so it maps to 2.
CLICK_CHOICES = [(1, "1 min"), (2, "1–2 min"), (5, "5+ min")]
DEFAULT_MINUTES = 2
PATH_NAMES = [("A", "Finish something"), ("B", "Max XP"), ("C", "Gold")]

# The data files are loaded once at start-up. If one is broken, the checker
# prints what's wrong and the app stops, just like the terminal version.
METHODS = load_methods()
UNLOCKS, QUESTS = load_quest_files()

PASSWORD_NOTE = "Only your public RuneMetrics name. Never enter a password."
IRONMAN_NOTE = ("Ironman accounts aren't supported yet. Plans may suggest training or "
                "money methods an ironman can't use.")

# Every unlock id in methods.json -> its wording, for the "Your answers" list.
UNLOCK_TEXTS = {u["id"]: u["text"] for m in METHODS for u in m["requirements"]["unlocks"]}

# Live account data, one entry per player (see player_cache.py). Each name is
# fetched once while the app runs, and again only on Refresh.
CACHE = {}

# The player every screen shows. A dict so functions can change it without "global".
# None until someone picks a player on the /player screen.
CURRENT = {"name": read_current()}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

async def fetch_player(name):
    """
    Fetch one player from RuneMetrics into CACHE and save a snapshot.
    Returns their cache entry. If the fetch fails, "error" says why and any
    older stats are kept.
    """
    # Shown in the terminal, handy for checking the cache works. flush=True writes it
    # out straight away, even when the output goes to a log file instead of a terminal.
    print(f"Fetching {name} from RuneMetrics", flush=True)
    # run.io_bound runs the slow download in the background so the page doesn't freeze.
    result = await run.io_bound(fetch_safely, name)
    if result is None:   # the app is shutting down
        return entry_for(CACHE, name)
    profile, account, error = result
    if error:
        return record_failure(CACHE, name, error)
    now = datetime.datetime.now()
    entry = record_success(CACHE, name, profile, account, now)
    save_snapshot(entry["name"], profile, now)
    return entry


def current_entry():
    """The current player's cache entry (empty until fetched), or None if no player is chosen."""
    name = CURRENT["name"]
    if not name:
        return None
    return entry_for(CACHE, name)


def current_goal():
    """The current player's big goal: their saved choice (shared with the terminal's
    menu), else the first unlock. Read fresh each time, so a change made in the
    terminal shows on the next page load."""
    return goal_for(UNLOCKS, CURRENT["name"])


async def fetch_current_on_startup():
    if CURRENT["name"]:
        await fetch_player(CURRENT["name"])

app.on_startup(fetch_current_on_startup)


# ---------------------------------------------------------------------------
# Numbers for the Home screen (all from existing functions)
# ---------------------------------------------------------------------------

def max_cape_numbers(profile):
    """Max cape progress by XP: each skill's XP capped at its 99 amount."""
    gaps = xp_needed_for_99(profile)   # the same list the terminal prints
    needed = done = 0
    for skill in profile["skillvalues"]:
        if skill["id"] >= len(SKILL_NAMES):
            continue
        target = XP_FOR_99_ELITE if skill["id"] == INVENTION_ID else XP_FOR_99_NORMAL
        needed += target
        done += min(skill["xp"] / 10, target)   # RuneMetrics stores XP x10
    return {
        "done": done,
        "needed": needed,
        "to_go": sum(xp for _, xp in gaps),
        "at_99": len(SKILL_NAMES) - len(gaps),
        "closest": gaps[:3],
    }


def big_goal_numbers(goal, account):
    """Progress on a big goal: quests done in its chain, and skills short anywhere in it."""
    chain, done = goal_progress(goal, QUESTS, account)
    return {"chain": len(chain), "done": done, "short": len(skill_gaps(chain, QUESTS, account))}


def skills_short(count):
    """'no skills short', '1 skill short' or '4 skills short'."""
    if count == 0:
        return "no skills short"
    return f"{count} skill short" if count == 1 else f"{count} skills short"


# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

def button(*args, **kwargs):
    """A button with no built-in colour, so app.css alone decides how it looks.
    (NiceGUI's default colour='primary' would paint every button blue.)"""
    return ui.button(*args, color=None, **kwargs)


def icon(name, size=22):
    """Inline a Lucide icon from static/icons (ISC licence file sits next to them)."""
    svg = (HERE / "static" / "icons" / f"{name}.svg").read_text(encoding="utf-8")
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S).strip()
    svg = svg.replace('width="24"', f'width="{size}"').replace('height="24"', f'height="{size}"')
    ui.html(svg, sanitize=False).classes("icon")   # our own trusted file, so no sanitising


def panel(crimson=False):
    return ui.column().classes("panel" + (" crimson-frame" if crimson else ""))


def bar(fraction, thin=False):
    fraction = max(0.0, min(1.0, fraction))
    with ui.element("div").classes("bar" + (" thin" if thin else "")):
        ui.element("div").classes("bar-fill").style(f"width: {fraction * 100:.1f}%")


# Bottom nav buttons that have a screen; the others say "coming soon".
NAV_TARGETS = {"Home": "/", "Skills": "/skills", "Quests": "/quests", "Progress": "/progress"}


def bottom_nav(active):
    with ui.element("div").classes("bottom-nav"):
        with ui.element("div").classes("bottom-nav-inner"):
            for name in ("Home", "Skills", "Quests", "Progress"):
                target = NAV_TARGETS.get(name)
                if target:
                    action = lambda t=target: ui.navigate.to(t)
                else:
                    action = lambda n=name: ui.notify(f"{n}: coming soon")
                button(name, on_click=action).props("flat no-caps").classes(
                    "nav-btn" + (" active" if name == active else ""))


def back_button(target):
    button("← Back", on_click=lambda: ui.navigate.to(target)).props("unelevated no-caps").classes("btn-quiet")


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


# ---------------------------------------------------------------------------
# Screen 1: Home
# ---------------------------------------------------------------------------

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

        # Max cape card
        cape = max_cape_numbers(profile)
        with panel():
            ui.label("Max cape").classes("label")
            ui.label(f"{cape['done'] / cape['needed'] * 100:.1f}%").classes("big-number")
            bar(cape["done"] / cape["needed"])
            ui.label(f"{cape['done']:,.0f} of {cape['needed']:,.0f} XP").classes("muted")
            ui.label(f"{cape['to_go']:,.0f} to go").classes("heading")
            ui.label(f"{cape['at_99']} of {len(SKILL_NAMES)} skills at 99").classes("muted")

        # Closest to 99
        with panel():
            ui.label("Closest to 99").classes("label green")
            for name, xp_left in cape["closest"]:
                skill = account["skills"][name]
                target = XP_FOR_99_ELITE if name == "Invention" else XP_FOR_99_NORMAL
                with ui.row().classes("row-line"):
                    ui.label(f"{name} {skill['level']}").classes("heading")
                    ui.label(f"{xp_left:,.0f} XP left").classes("muted")
                bar(skill["xp"] / target, thin=True)

        # Big goal (the one chosen on the Quests screen)
        goal = current_goal()
        numbers = big_goal_numbers(goal, account)
        with panel():
            ui.label("Big goal").classes("label")
            ui.label(goal["name"]).classes("subtitle")
            ui.label(f"via {goal['final_quest']}").classes("muted")
            ui.label(f"{numbers['done']} of {numbers['chain']} quests done in its chain").classes("muted")
            short = skills_short(numbers["short"]) + " for its chain"
            ui.label(short[0].upper() + short[1:]).classes("muted")

        with button(on_click=lambda: ui.navigate.to("/play")).props("unelevated no-caps").classes("btn-crimson"):
            with ui.row().classes("items-center gap-3"):
                icon("sword", 24)
                ui.label("Ready to play")

    bottom_nav("Home")


# ---------------------------------------------------------------------------
# Screen 2: Ready to play
# ---------------------------------------------------------------------------

@ui.page("/play", title="Ready to play - RS3 Planner")
def play_page():
    if current_entry() is None:
        return RedirectResponse("/player")
    choice = {"hours": DEFAULT_HOURS, "session": "afk", "minutes": DEFAULT_MINUTES}

    def pick(key, value):
        choice[key] = value
        options.refresh()

    @ui.refreshable
    def options():
        with panel():
            ui.label("How long can you play?").classes("label")
            with ui.row().classes("gap-2"):
                for hours in HOUR_CHOICES:
                    button(f"{hours}h", on_click=lambda h=hours: pick("hours", h)).props(
                        "unelevated no-caps").classes("chip" + (" selected" if choice["hours"] == hours else ""))

        with panel():
            ui.label("What kind of session?").classes("label")
            with ui.row().classes("w-full gap-3 no-wrap"):
                for key, title, icons in (("afk", "AFK", ["hourglass"]), ("active", "Active", ["sword", "shield"])):
                    selected = " selected" if choice["session"] == key else ""
                    with button(on_click=lambda k=key: pick("session", k)).props(
                            "unelevated no-caps").classes("choice" + selected):
                        with ui.row().classes("gap-1"):
                            for name in icons:
                                icon(name, 28)
                        ui.label(title)

        if choice["session"] == "afk":
            with panel():
                ui.label("Most time between clicks").classes("label")
                with ui.row().classes("gap-2"):
                    for minutes, text in CLICK_CHOICES:
                        button(text, on_click=lambda m=minutes: pick("minutes", m)).props(
                            "unelevated no-caps").classes("chip" + (" selected" if choice["minutes"] == minutes else ""))

    with ui.column().classes("page"):
        back_button("/")
        ui.label("Ready to play").classes("title")
        options()

        def show_plan():
            ui.navigate.to(f"/plan?hours={choice['hours']}&session={choice['session']}&minutes={choice['minutes']}")

        with button(on_click=show_plan).props("unelevated no-caps").classes("btn-crimson"):
            with ui.row().classes("items-center gap-3"):
                icon("swords", 24)
                ui.label("Show my plan")

    bottom_nav("")


# ---------------------------------------------------------------------------
# Screen: Skills
# ---------------------------------------------------------------------------

@ui.page("/skills", title="Skills - RS3 Planner")
def skills_page():
    entry = current_entry()
    if entry is None:   # nobody chosen yet: go and pick a player
        return RedirectResponse("/player")

    with ui.column().classes("page"):
        ui.label("Skills").classes("title")
        ui.label(entry["name"]).classes("subtitle")
        ui.label(updated_text(entry)).classes("muted")

        if entry["account"] is None:
            no_data_panel(entry)
            bottom_nav("Skills")
            return

        # The order and numbers come from account.skill_rows (tested in tests/test_account.py).
        rows = skill_rows(entry["account"])
        unfinished = [row for row in rows if not row["done"]]
        done = [row for row in rows if row["done"]]

        if unfinished:
            with panel():
                ui.label("To 99").classes("label")
                for row in unfinished:
                    skill_row(row, f"{row['xp_left']:,.0f} XP left")
        if done:
            with panel():
                ui.label("Done").classes("label green")
                for row in done:
                    skill_row(row, "Done")

    bottom_nav("Skills")


def skill_row(row, right_text):
    """One skill: name and level on the left, XP left (or Done) on the right, a bar, then its XP."""
    with ui.row().classes("row-line"):
        ui.label(f"{row['name']} {row['level_text']}").classes("heading")
        ui.label(right_text).classes("muted" + (" done-text" if row["done"] else ""))
    bar(row["fraction"], thin=True)
    ui.label(f"{row['xp']:,.0f} XP").classes("muted small")


# ---------------------------------------------------------------------------
# Screen: Quests
# ---------------------------------------------------------------------------

STATUS_WORDS = {"ready": "Ready now", "started": "Started", "blocked": "Blocked"}


def difficulty_text(title, account):
    """The quest's difficulty, or — when RuneMetrics doesn't list the quest."""
    name = difficulty_name(title, account)
    return NO_VALUE if name == "?" else name


@ui.page("/quests", title="Quests - RS3 Planner")
def quests_page():
    entry = current_entry()
    if entry is None:   # nobody chosen yet: go and pick a player
        return RedirectResponse("/player")

    with ui.column().classes("page"):
        ui.label("Quests").classes("title")
        ui.label(entry["name"]).classes("subtitle")
        ui.label(updated_text(entry)).classes("muted")

        account = entry["account"]
        if account is None:
            no_data_panel(entry)
            bottom_nav("Quests")
            return

        goal = current_goal()
        numbers = big_goal_numbers(goal, account)
        with panel():
            ui.label("Big goal").classes("label")
            ui.label(goal["name"]).classes("subtitle")
            ui.label(f"via {goal['final_quest']}").classes("muted")
            ui.label(goal["unlocks"]).classes("muted small")
            ui.label(f"{numbers['done']} of {numbers['chain']} quests done").classes("muted")
            bar(numbers["done"] / numbers["chain"])   # a chain always holds at least the final quest
            button("Change goal", on_click=lambda: ui.navigate.to("/quests/goal")).props(
                "unelevated no-caps").classes("btn-quiet")

        tonight_panels(goal, account)
        skills_short_panel(goal, account, "Skills short for this chain")
        chain_panel(goal, account)
        other_requirements_panel(goal, account)
        start_now_panel(account)
        in_progress_panel(account)

    bottom_nav("Quests")


def chain_panel(goal, account):
    """Every quest in the goal's chain, prerequisites first, with its status."""
    with panel():
        ui.label("Quest chain").classes("label green")
        for row in chain_rows(goal, QUESTS, account):
            if row["state"] == "done":
                ui.label(f"{row['title']} · Done").classes("muted small")
                continue
            ui.label(row["title"]).classes("heading")
            ui.label(f"{difficulty_text(row['title'], account)} · {row['length']}").classes("muted small")
            status = STATUS_WORDS[row["state"]]
            if row["reasons"]:
                status += ": " + "; ".join(row["reasons"])
            ui.label(status).classes("muted small" + (" done-text" if row["state"] == "ready" else ""))


def other_requirements_panel(goal, account):
    """The wiki's other requirements in the chain. Hidden when there are none."""
    chain, _ = goal_progress(goal, QUESTS, account)
    lines = other_requirements(chain, QUESTS, account)
    if not lines:
        return
    with panel():
        ui.label("Other requirements (check these yourself)").classes("label")
        for text, title in lines:
            ui.label(f"{text} (for {title})").classes("muted small")


def start_now_panel(account):
    """Quests you can start that lead to an unlock, plus a Show all button for the rest."""
    useful = useful_to_start(UNLOCKS, QUESTS, account)
    groups = eligible_by_difficulty(account)
    total = sum(len(titles) for _, titles in groups)
    with panel():
        ui.label("Start now").classes("label green")
        if not useful:
            ui.label("No quest on your unlock chains can be started right now.").classes("muted")
        for title in useful:
            ui.label(title).classes("heading")
            ui.label(f"{difficulty_text(title, account)} · {QUESTS[title]['length']} · "
                     f"helps {unlock_count(title, UNLOCKS, QUESTS)} of {len(UNLOCKS)} unlocks").classes("muted small")
        if not total:
            return

        show_text = f"Show all {total} you can start"
        toggle = button(show_text).props("unelevated no-caps").classes("btn-quiet")
        # The full list is drawn now but hidden; the button shows or hides it (nothing is fetched).
        full_list = ui.column().classes("w-full gap-1")
        with full_list:
            for name, titles in groups:
                ui.label(f"{name} ({len(titles)})").classes("label")
                for title in titles:
                    ui.label(title).classes("muted small")
        full_list.set_visibility(False)

        def flip():
            showing = not full_list.visible
            full_list.set_visibility(showing)
            toggle.set_text("Hide the full list" if showing else show_text)

        toggle.on_click(flip)


def in_progress_panel(account):
    """Quests RuneMetrics says you've started. Hidden when there are none."""
    started = started_quests(account)
    if not started:
        return
    with panel():
        ui.label("In progress").classes("label")
        for title in started:
            with ui.row().classes("row-line"):
                ui.label(title).classes("heading")
                ui.label(difficulty_text(title, account)).classes("muted")


# ---------------------------------------------------------------------------
# Screen: Change goal
# ---------------------------------------------------------------------------

@ui.page("/quests/goal", title="Big goal - RS3 Planner")
def goal_page():
    entry = current_entry()
    if entry is None:   # nobody chosen yet: go and pick a player
        return RedirectResponse("/player")

    def choose(unlock):
        # The same file the terminal's goal menu uses, so both agree.
        if save_last_goal(CURRENT["name"], unlock["name"]):
            ui.navigate.to("/quests")
        else:
            ui.notify("Couldn't save your goal choice")

    with ui.column().classes("page"):
        back_button("/quests")
        ui.label("Big goal").classes("title")

        account = entry["account"]
        if account is None:
            no_data_panel(entry)
            bottom_nav("Quests")
            return

        current = current_goal()
        with panel():
            ui.label("Choose your big goal").classes("label")
            for unlock in UNLOCKS:
                numbers = big_goal_numbers(unlock, account)
                selected = " selected" if unlock["name"] == current["name"] else ""
                with button(on_click=lambda u=unlock: choose(u)).props("unelevated no-caps").classes(
                        "chip wide goal-choice" + selected):
                    with ui.column().classes("gap-0"):
                        ui.label(unlock["name"]).classes("goal-name")
                        ui.label(f"{numbers['done']} of {numbers['chain']} quests done · "
                                 f"{skills_short(numbers['short'])}").classes("goal-progress")

    bottom_nav("Quests")


# ---------------------------------------------------------------------------
# Screen: Progress
# ---------------------------------------------------------------------------

@ui.page("/progress", title="Progress - RS3 Planner")
def progress_page():
    entry = current_entry()
    if entry is None:   # nobody chosen yet: go and pick a player
        return RedirectResponse("/player")

    # Only the saved snapshot files (see progress.py): this screen never fetches,
    # so it still works when RuneMetrics is down. Read fresh on every visit.
    snapshots, skipped = read_snapshots(CURRENT["name"])
    today = datetime.date.today()
    snapshots, future = set_aside_future(snapshots, today)   # only from a wrong computer clock

    with ui.column().classes("page"):
        ui.label("Progress").classes("title")
        ui.label(entry["name"]).classes("subtitle")
        if snapshots:
            ui.label(snapshot_count_text(snapshots)).classes("muted")
        if skipped:
            ui.label(skipped_text(skipped)).classes("muted small")
        if future:
            ui.label(future_text(future)).classes("muted small")

        if not snapshots:
            with panel():
                ui.label("No snapshots saved yet").classes("heading")
                ui.label("One is saved each time stats are fetched (at start-up and on Refresh).").classes("muted")
            bottom_nav("Progress")
            return

        max_cape_panel(snapshots)
        gained_panel(snapshots, today)
        one_skill_panel(entry, snapshots, today)

    bottom_nav("Progress")


def snapshot_count_text(snapshots):
    """'20 snapshots · last 15:33, 5 Oct'."""
    newest = snapshots[-1]["when"]
    count = f"{len(snapshots)} snapshot" + ("" if len(snapshots) == 1 else "s")
    return f"{count} · last {newest:%H:%M}, {newest.day} {newest:%b}"


def skipped_text(skipped):
    if skipped == 1:
        return "1 snapshot file couldn't be read and was skipped."
    return f"{skipped} snapshot files couldn't be read and were skipped."


def future_text(future):
    if future == 1:
        return "1 snapshot is dated in the future and was set aside."
    return f"{future} snapshots are dated in the future and were set aside."


# Chart colours: the same values as static/app.css. ECharts draws on a canvas,
# which can't read CSS, so they are written out here.
CHART_PANEL = "#16241B"     # --panel: the dots' ring and the tooltip background
CHART_GRID = "#2E4636"      # --frame-outer: gridlines and the date axis
CHART_TEXT = "#B9C3B2"      # --muted: axis labels
CHART_TIP_TEXT = "#F0E8D6"  # --parchment: tooltip text
CHART_LINE = "#A8DCEB"      # --glacial: the line and its dots
CHART_FONT = "Alegreya, Georgia, serif"
ONE_DAY_MS = 24 * 60 * 60 * 1000   # one day in milliseconds, how ECharts measures time

# Small pieces of browser code (JavaScript) for ECharts. NiceGUI runs a settings
# value as code when its key starts with ":" (see ui.echart's documentation).
MONTHS_JS = "['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']"
# Date axis labels: "5 Oct".
DATE_LABEL_JS = f"value => {{ const d = new Date(value); return d.getDate() + ' ' + {MONTHS_JS}[d.getMonth()]; }}"
# Value axis labels: whole numbers with commas, "269,276,000".
NUMBER_LABEL_JS = "value => Math.round(value).toLocaleString('en-GB')"


def tooltip_js(value_word):
    """Hover text, '5 Oct · 269,276,641 to go'. value_word is our own fixed text ('to go' or 'XP')."""
    return ("params => { const p = params[0]; const d = new Date(p.value[0]); "
            f"return d.getDate() + ' ' + {MONTHS_JS}[d.getMonth()] + ' · ' + "
            f"Math.round(p.value[1]).toLocaleString('en-GB') + ' {value_word}'; }}")


def line_chart(points, value_word):
    """
    A one-line chart of [(date, value)] in the app's colours (ui.echart: ECharts,
    bundled with NiceGUI, so it works offline). One line, so no legend: the panel's
    label says what it is. The date axis keeps real spacing, so a week without
    snapshots shows as a gap. The value axis zooms to the data, or a small change
    on 269M would be invisible.
    """
    # Each date at local midnight, where ECharts puts its day labels, so every dot
    # sits on its own date. The time is written out ("T00:00:00", no time zone) so
    # the browser reads it as local time; a bare "2026-10-05" could be read as UTC
    # and land on the day before.
    data = [[f"{day:%Y-%m-%d}T00:00:00", value] for day, value in points]
    options = {
        "backgroundColor": "transparent",   # the panel shows through
        "animation": False,
        "textStyle": {"fontFamily": CHART_FONT, "color": CHART_TEXT},
        "grid": {"left": 8, "right": 16, "top": 16, "bottom": 8, "containLabel": True},
        "xAxis": {
            "type": "time",
            "minInterval": ONE_DAY_MS,   # never two labels on the same day
            "axisLine": {"lineStyle": {"color": CHART_GRID}},
            "axisTick": {"show": False},
            "splitLine": {"show": False},
            "axisLabel": {"color": CHART_TEXT, "hideOverlap": True, ":formatter": DATE_LABEL_JS},
        },
        "yAxis": {
            "type": "value",
            "scale": True,   # zoom to the data instead of starting at 0
            "minInterval": 1,   # ticks at least 1 XP apart, so no label repeats ("0, 0, 1")
            "splitLine": {"lineStyle": {"color": CHART_GRID, "width": 1, "type": "solid"}},
            "axisLabel": {"color": CHART_TEXT, ":formatter": NUMBER_LABEL_JS},
        },
        "tooltip": {
            "trigger": "axis",
            "backgroundColor": CHART_PANEL,
            "borderColor": CHART_GRID,
            "textStyle": {"color": CHART_TIP_TEXT, "fontFamily": CHART_FONT},
            "axisPointer": {"type": "line", "lineStyle": {"color": CHART_GRID}},
            ":formatter": tooltip_js(value_word),
        },
        "series": [{
            "type": "line",
            "data": data,
            "symbol": "circle",
            "symbolSize": 8,
            "clip": False,   # dots at the very ends stay whole
            "lineStyle": {"color": CHART_LINE, "width": 2},
            "itemStyle": {"color": CHART_LINE, "borderColor": CHART_PANEL, "borderWidth": 2},
        }],
    }
    return ui.echart(options).classes("chart")


def numbers_toggle(points, value_word):
    """'Show the numbers': the chart's values as a list, newest first (nothing is fetched)."""
    show_text = "Show the numbers"
    toggle = button(show_text).props("unelevated no-caps").classes("btn-quiet")
    # Drawn now but hidden; the button shows or hides it.
    numbers = ui.column().classes("w-full gap-0")
    with numbers:
        for day, value in reversed(points):
            ui.label(f"{day.day} {day:%b} · {value:,.0f} {value_word}").classes("muted small")
    numbers.set_visibility(False)

    def flip():
        showing = not numbers.visible
        numbers.set_visibility(showing)
        toggle.set_text("Hide the numbers" if showing else show_text)

    toggle.on_click(flip)


def max_cape_panel(snapshots):
    """Max cape now (the same rule as Home's card), and XP still to go per day."""
    newest = snapshots[-1]
    cape = max_cape_xp(newest["skills"])   # None if the snapshot lacks a skill
    with panel():
        ui.label("Max cape").classes("label")
        ui.label(f"{cape['percent']:.1f}%" if cape else NO_VALUE).classes("big-number")
        ui.label(f"{cape['to_go']:,.0f} XP to go" if cape else f"{NO_VALUE} XP to go").classes("heading")
        ui.label(f"Total XP {newest['total_xp']:,.0f}").classes("muted")
        points = max_cape_points(snapshots)   # the last snapshot of each day
        if len(points) >= 2:   # a line needs two points
            line_chart(points, "to go")
            numbers_toggle(points, "to go")
        else:
            ui.label("A chart appears once you have snapshots from 2 different days.").classes("muted small")


def gained_panel(snapshots, today):
    """XP gained Today / Last 7 days / Since first snapshot, then the skills that moved."""
    with panel():
        ui.label("Gained").classes("label green")
        for line in gain_lines(snapshots, today):
            if line["state"] == "none_today":
                ui.label(f"{line['name']}: no snapshot yet").classes("muted")
                continue
            if line["state"] == "only_one":
                ui.label(f"{line['name']}: only one snapshot so far").classes("muted")
                continue
            cape = NO_VALUE if line["max_cape"] is None else signed_xp(line["max_cape"])
            ui.label(line["name"]).classes("heading")
            ui.label(f"{signed_xp(line['total'])} XP · {cape} toward max cape · "
                     f"{since_text(line['start']['when'], today)}").classes("muted")

        start, moved = skills_moved(snapshots, today)
        if start is None:   # only one snapshot: nothing to compare
            return
        since = since_text(start["when"], today)
        ui.label(f"Skills that moved {since}").classes("label")
        if not moved:
            ui.label(f"No skill has moved {since}.").classes("muted small")
        for skill, xp in moved:
            with ui.row().classes("row-line"):
                ui.label(skill).classes("heading")
                ui.label(f"{signed_xp(xp)} XP").classes("muted")


def one_skill_panel(entry, snapshots, today):
    """A dropdown of skills and the chosen skill's XP per day. Choosing redraws only this panel."""
    newest = snapshots[-1]["skills"]
    names = skill_order(newest)   # closest to 99 first, like the Skills screen
    if not names:
        return
    # Levels come from the live stats (skill_rows knows Invention past 99 is "99+");
    # snapshots don't store levels. With no live stats, the level is left off.
    levels = {row["name"]: row["level_text"] for row in skill_rows(entry["account"])} if entry["account"] else {}
    choice = {"skill": default_skill(snapshots, today)}

    @ui.refreshable
    def skill_view():
        skill = choice["skill"]
        name_text = f"{skill} {levels[skill]}" if skill in levels else skill
        ui.label(f"{name_text} · {newest[skill]:,.0f} XP").classes("heading")
        points = skill_points(snapshots, skill)
        if len(points) >= 2:
            line_chart(points, "XP")
            numbers_toggle(points, "XP")
        elif len(snapshots) < 2:
            ui.label("Only one snapshot so far.").classes("muted")
        else:
            gain = skill_gain_since_first(snapshots, skill)
            gain_text = NO_VALUE if gain is None else signed_xp(gain)
            ui.label(f"{gain_text} XP {since_text(snapshots[0]['when'], today)}").classes("muted")

    def pick(event):
        choice["skill"] = event.value
        skill_view.refresh()

    with panel():
        ui.label("One skill").classes("label")
        ui.select(names, value=choice["skill"], on_change=pick).props(
            'outlined dark popup-content-class="skill-menu"').classes("skill-select")
        skill_view()


# ---------------------------------------------------------------------------
# Screens 3a and 3b: the plan
# ---------------------------------------------------------------------------

@ui.page("/plan", title="Your plan - RS3 Planner")
def plan_page(hours: float = DEFAULT_HOURS, session: str = "afk", minutes: float = DEFAULT_MINUTES):
    # Anything odd in the address falls back to the defaults.
    hours = hours if hours > 0 else DEFAULT_HOURS
    minutes = minutes if minutes > 0 else DEFAULT_MINUTES
    session = session if session in ("afk", "active") else "afk"
    if current_entry() is None:
        return RedirectResponse("/player")

    with ui.column().classes("page"):
        back_button("/play")
        entry = current_entry()
        if entry["account"] is None:
            no_data_panel(entry)
        elif session == "afk":
            afk_plan(entry, hours, minutes)
        else:
            active_plan(entry["account"], hours)
    bottom_nav("")


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
    for (letter, path_name), (_, method, why), also in zip(PATH_NAMES, plan["paths"], plan["also"]):
        with panel():
            ui.label(f"{letter} · {path_name}").classes("label")
            if method is None:
                ui.label("Nothing ready for this path: see why below.").classes("muted")
                continue
            ui.label(method["name"]).classes("heading")
            ui.label(method["skill"]).classes("muted small")
            for label, text in path_lines(method, account, hours):
                text = text.replace(" -> ", " → ")
                ui.label(f"{label}: {text}" if label else text).classes("" if label else "muted small")
            ui.label(why).classes("muted small")
            if also:   # the next best methods for this path, so there's a choice
                ui.label("Also good: " + "; ".join(also_text(m) for m in also)).classes("muted small")
            for warning in method["_warnings"]:
                ui.label(f"Watch: {warning}").classes("muted small")
            for unlock in method["_unanswered"]:
                unlock_question(name, unlock)

    your_answers(name, answers)
    ruled_out_panel(plan)


def ruled_out_panel(plan):
    """
    The methods the planner ruled out for this session, with the checker's own
    reasons. Methods you've finished the skill for or outgrown are just counted
    (split_ruled_out). Folded behind a button; hidden
    when nothing was ruled out. (The terminal still prints the full list.)
    """
    ruled_out = plan["ruled_out"]
    if not ruled_out:
        return
    blocked, finished = split_ruled_out(ruled_out)
    with panel():
        show_text = f"Why not the others? ({len(ruled_out)} ruled out)"
        toggle = button(show_text).props("unelevated no-caps").classes("btn-quiet")
        # Drawn now but hidden; the button shows or hides it (nothing is fetched).
        reasons_list = ui.column().classes("w-full gap-2")
        with reasons_list:
            for method, reasons in blocked:
                with ui.column().classes("gap-0"):
                    ui.label(method["name"]).classes("heading")
                    ui.label(method["skill"]).classes("muted small")
                    ui.label("; ".join(reasons)).classes("muted small")
            if finished:
                ui.label(f"Also skipped: {finished} you've finished (120) or outgrown.").classes("muted small")
        reasons_list.set_visibility(False)

        def flip():
            showing = not reasons_list.visible
            reasons_list.set_visibility(showing)
            toggle.set_text("Hide the list" if showing else show_text)

        toggle.on_click(flip)


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


def active_plan(account, hours):
    goal = current_goal()
    ui.label("Your active plan").classes("title")
    ui.label(f"{hours:g} hours · big goal: {goal['name']} ({goal['final_quest']})").classes("muted")
    tonight_panels(goal, account)
    skills_short_panel(goal, account, f"Skills still short for {goal['final_quest']}")


def tonight_panels(goal, account):
    """Tonight's quest and the next one on the way (Active plan and Quests screen)."""
    titles, on_path = ranked_doable(goal, UNLOCKS, QUESTS, account)   # same ranking as the terminal

    with panel(crimson=True):
        ui.label("Tonight's quest").classes("label")
        if not titles:
            ui.label("Nothing in your unlock chains is ready right now.").classes("muted")
        else:
            tonight = titles[0]
            ui.label(tonight).classes("subtitle")
            ui.label(f"{difficulty_name(tonight, account)} · {QUESTS[tonight]['length']}").classes("muted")
            where = "On the way to your big goal" if on_path else "Not on your big goal's path (nothing there is ready)"
            ui.label(f"{where}; helps {unlock_count(tonight, UNLOCKS, QUESTS)} of your "
                     f"{len(UNLOCKS)} unlocks.").classes("muted small")

    if len(titles) > 1:
        also = titles[1]
        with panel():
            ui.label("Also on the way").classes("label green")
            ui.label(also).classes("heading")
            ui.label(f"{difficulty_name(also, account)} · {QUESTS[also]['length']}").classes("muted")


def skills_short_panel(goal, account, title):
    """Skill levels still needed anywhere in the goal's chain, smallest gap first."""
    chain, _ = goal_progress(goal, QUESTS, account)
    gaps = skill_gaps(chain, QUESTS, account)
    with panel():
        ui.label(title).classes("label")
        if not gaps:
            ui.label("None - your levels already cover the whole chain.").classes("muted")
        for skill, (level, have, xp_left, _) in gaps.items():
            with ui.row().classes("row-line"):
                ui.label(f"{skill} {have} → {level}").classes("heading")
                ui.label(f"{xp_left:,.0f} XP left").classes("muted")
            # Each skill's own XP table (Invention's is the elite one).
            bar(account["skills"][skill]["xp"] / level_table(skill)[level - 1], thin=True)


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

    busy = {"now": False}   # True while a lookup is running

    async def look_up(text):
        if busy["now"]:   # a second tap or Enter while fetching: ignore it, one fetch is enough
            return
        name, problem = check_name(text)
        if problem:   # caught here, before asking RuneMetrics anything
            show(problem, error=True)
            return
        if needs_fetch(CACHE, name):   # not fetched yet this run
            busy["now"] = True
            look_button.disable()
            show(f"Fetching {name} from RuneMetrics…", error=False)
            try:
                entry = await fetch_player(name)
            finally:   # whatever happens, the screen must not stay stuck on "Fetching…"
                busy["now"] = False
                look_button.enable()
        else:
            entry = entry_for(CACHE, name)
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


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

def switch_on_locks(port):
    """
    Two locks in front of every page and live connection (they must be added before
    ui.run). Requests addressed to any other name are refused, which stops "DNS
    rebinding" web pages; requests started by another website are refused too.
    The second lock is built from the port the app really uses.
    """
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS, www_redirect=False)
    app.add_middleware(OriginLock, allowed_origins=allowed_origins(ALLOWED_HOSTS, port))


def start_port():
    """
    The port to listen on, or None when this copy shouldn't start.
    From the project folder: PORT (8080), exactly as always.
    As the Windows app (a bundle): 8095, or the first free port after it when
    another program has 8095. If RS3 Planner already runs on 8095 (a second
    double-click), the browser is opened there instead and None is returned.
    """
    if not is_bundled():
        return PORT
    print(version_text() or "RS3 Planner (version unknown)", flush=True)
    folder = user_data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    print(f"Your saved data: {folder}", flush=True)
    try:
        already_running, port = choose_port(planner_answers, native.find_open_port)
    except OSError:   # NiceGUI's search found no free port at all
        stop(f"RS3 Planner found no free port between {PREFERRED_PORT} and {LAST_PORT}, so it can't start.")
    if already_running:
        print("RS3 Planner is already running: opening it in your browser.", flush=True)
        webbrowser.open(f"http://{HOST}:{port}/")
        return None
    if port != PREFERRED_PORT:
        print(f"Port {PREFERRED_PORT} is used by another program, so RS3 Planner uses port {port}.", flush=True)
    return port


def say_running():
    """Shown in the Windows app's black window once the app answers."""
    print("RS3 Planner is running. Keep this window open; close it to stop the app.", flush=True)


app.add_static_files("/static", HERE / "static")
# "?v=..." is the stylesheet's last-change time: when the file changes, the address
# changes, so browsers fetch the new version instead of an old cached copy.
CSS_VERSION = int((HERE / "static" / "app.css").stat().st_mtime)
ui.add_head_html(f'<link rel="stylesheet" href="/static/app.css?v={CSS_VERSION}">', shared=True)

if __name__ in {"__main__", "__mp_main__"}:
    # First: in the Windows app, NiceGUI's helper processes start this same program,
    # and this call makes them do their job instead of starting the whole app again
    # (PyInstaller's "Common Issues and Pitfalls" page). Run from source it does nothing.
    freeze_support()
    port = start_port()
    if port is not None:
        switch_on_locks(port)
        if is_bundled():
            app.on_startup(say_running)
        try:
            ui.run(host=HOST, port=port, title="RS3 Planner", dark=True, reload=False, show=is_bundled())
        except KeyboardInterrupt:
            # Ctrl+C is the normal way to stop the app; say so instead of printing a traceback.
            print("\nRS3 Planner stopped.")
