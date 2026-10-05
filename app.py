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
  players.py       which player: folders, answers, the remembered player

Choose a player on the /player screen (any public RuneScape name). Each name
is fetched once while the app runs, and again only when you press Refresh.

Start it (from the project folder):
    .venv/bin/python app.py
then open http://127.0.0.1:8080 in your browser. Stop it with Ctrl+C.

It listens on 127.0.0.1 only, so other devices on your network can't reach it.
"""

import copy
import datetime
import re
from pathlib import Path

from fastapi.responses import RedirectResponse   # sends a page to /player when no player is chosen
from nicegui import app, run, ui

from account import LEVEL_XP, read_account
from check_methods import load_methods, load_quest_files
from plan_session import build_plan, path_lines
from players import (
    check_name, folder_name, known_players, read_answers, read_current, save_answer, save_current,
)
from quest_path import difficulty_name, goal_progress, ranked_doable, skill_gaps, unlock_count
from rs3_planner import (
    INVENTION_ID, SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL,
    load_profile, load_quests, xp_needed_for_99,
)
from snapshots import save_snapshot

HERE = Path(__file__).parent
HOST = "127.0.0.1"   # this computer only - never 0.0.0.0
PORT = 8080
BIG_GOAL_QUEST = "Plague's End"
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
GOAL = next(u for u in UNLOCKS if u["final_quest"] == BIG_GOAL_QUEST)

PASSWORD_NOTE = "Only your public RuneMetrics name. Never enter a password."
IRONMAN_NOTE = ("Ironman accounts aren't supported yet. Plans may suggest training or "
                "money methods an ironman can't use.")

# Live account data, one entry per player, keyed by folder_name() so "hels glasglo"
# and "Hels Glasglo" share one entry. Each name is fetched once while the app runs,
# and again only on Refresh, so we don't hammer the unofficial RuneMetrics API.
CACHE = {}

# The player every screen shows. A dict so functions can change it without "global".
# None until someone picks a player on the /player screen.
CURRENT = {"name": read_current()}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def blank_entry(name):
    return {"name": name, "profile": None, "account": None, "fetched_at": None, "error": None}


def fetch_account(name):
    """Fetch profile and quests with the existing step 1 functions."""
    return load_profile(name), load_quests(name)


async def fetch_player(name):
    """
    Fetch one player from RuneMetrics into CACHE and save a snapshot.
    Returns their cache entry. If the fetch fails, "error" says why and any
    older stats are kept.
    """
    entry = CACHE.setdefault(folder_name(name), blank_entry(name))
    # Shown in the terminal, handy for checking the cache works. flush=True writes it
    # out straight away, even when the output goes to a log file instead of a terminal.
    print(f"Fetching {name} from RuneMetrics", flush=True)
    try:
        # run.io_bound runs the slow download in the background so the page doesn't freeze.
        result = await run.io_bound(fetch_account, name)
    except SystemExit as err:
        # The existing fetch code stops with a plain message on errors; keep it to show.
        entry["error"] = str(err)
        return entry
    if result is None:   # the app is shutting down
        return entry
    profile, quest_data = result
    now = datetime.datetime.now()
    # RuneMetrics sends the name with its proper capitals; use that from now on.
    entry.update(name=profile.get("name", name), profile=profile,
                 account=read_account(profile, quest_data), fetched_at=now, error=None)
    save_snapshot(entry["name"], profile, now)
    return entry


def current_entry():
    """The current player's cache entry (empty until fetched), or None if no player is chosen."""
    name = CURRENT["name"]
    if not name:
        return None
    return CACHE.setdefault(folder_name(name), blank_entry(name))


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


def big_goal_numbers(account):
    chain, done = goal_progress(GOAL, QUESTS, account)
    required = QUESTS[BIG_GOAL_QUEST]["skill_requirements"]
    below = [s for s, level in required.items() if account["skills"][s]["level"] < level]
    levels = set(required.values())
    return {"chain": len(chain), "done": done, "below": len(below), "required": len(required),
            "level": levels.pop() if len(levels) == 1 else None}


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


def bottom_nav(active):
    with ui.element("div").classes("bottom-nav"):
        with ui.element("div").classes("bottom-nav-inner"):
            for name in ("Home", "Skills", "Quests", "Progress"):
                if name == "Home":
                    action = lambda: ui.navigate.to("/")
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

        # Big goal
        goal = big_goal_numbers(account)
        with panel():
            ui.label("Big goal").classes("label")
            ui.label(BIG_GOAL_QUEST).classes("subtitle")
            ui.label(f"{goal['done']} of {goal['chain']} quests done in its chain").classes("muted")
            level_text = f"below {goal['level']}" if goal["level"] else "below their required level"
            ui.label(f"{goal['below']} of {goal['required']} required skills {level_text}").classes("muted")

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
    account = entry["account"]
    ui.label("Your AFK plan").classes("title")
    ui.label(f"{hours:g} hours · a click at most every {minutes:g} min").classes("muted")

    # The same function the terminal uses; a copy so each visit starts fresh.
    plan = build_plan(copy.deepcopy(METHODS), account, minutes, read_answers(entry["name"]))
    for (letter, name), (_, method, why) in zip(PATH_NAMES, plan["paths"]):
        with panel():
            ui.label(f"{letter} · {name}").classes("label")
            if method is None:
                ui.label("Nothing in the methods file fits this session.").classes("muted")
                continue
            ui.label(method["name"]).classes("heading")
            ui.label(method["skill"]).classes("muted small")
            for label, text in path_lines(method, account, hours):
                text = text.replace(" -> ", " → ")
                ui.label(f"{label}: {text}" if label else text).classes("" if label else "muted small")
            ui.label(why).classes("muted small")
            for warning in method["_warnings"]:
                ui.label(f"Watch: {warning}").classes("muted small")


def active_plan(account, hours):
    ui.label("Your active plan").classes("title")
    ui.label(f"{hours:g} hours · big goal: {GOAL['name']} ({BIG_GOAL_QUEST})").classes("muted")

    titles, on_path = ranked_doable(GOAL, UNLOCKS, QUESTS, account)   # same ranking as the terminal

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

    chain, _ = goal_progress(GOAL, QUESTS, account)
    gaps = skill_gaps(chain, QUESTS, account)
    with panel():
        ui.label(f"Skills still short for {BIG_GOAL_QUEST}").classes("label")
        if not gaps:
            ui.label("None - your levels already cover the whole chain.").classes("muted")
        for skill, (level, have, xp_left, _) in gaps.items():
            with ui.row().classes("row-line"):
                ui.label(f"{skill} {have} → {level}").classes("heading")
                ui.label(f"{xp_left:,.0f} XP left").classes("muted")
            bar(account["skills"][skill]["xp"] / LEVEL_XP[level - 1], thin=True)


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

    async def look_up(text):
        name, problem = check_name(text)
        if problem:   # caught here, before asking RuneMetrics anything
            show(problem, error=True)
            return
        entry = CACHE.get(folder_name(name))
        if entry is None or entry["account"] is None:   # not fetched yet this run
            look_button.disable()
            show(f"Fetching {name} from RuneMetrics…", error=False)
            entry = await fetch_player(name)
            look_button.enable()
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

app.add_static_files("/static", HERE / "static")
# "?v=..." is the stylesheet's last-change time: when the file changes, the address
# changes, so browsers fetch the new version instead of an old cached copy.
CSS_VERSION = int((HERE / "static" / "app.css").stat().st_mtime)
ui.add_head_html(f'<link rel="stylesheet" href="/static/app.css?v={CSS_VERSION}">', shared=True)

if __name__ in {"__main__", "__mp_main__"}:
    try:
        ui.run(host=HOST, port=PORT, title="RS3 Planner", dark=True, reload=False, show=False)
    except KeyboardInterrupt:
        # Ctrl+C is the normal way to stop the app; say so instead of printing a traceback.
        print("\nRS3 Planner stopped.")
