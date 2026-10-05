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

Start it (from the project folder):
    .venv/bin/python app.py
then open http://127.0.0.1:8080 in your browser. Stop it with Ctrl+C.

It listens on 127.0.0.1 only, so other devices on your network can't reach it.
"""

import copy
import datetime
import re
from pathlib import Path

from nicegui import app, run, ui

from account import LEVEL_XP, read_account
from check_methods import load_methods, load_quest_files
from plan_session import build_plan, path_lines
from quest_path import difficulty_name, goal_progress, ranked_doable, skill_gaps, unlock_count
from rs3_planner import (
    DEFAULT_USERNAME, INVENTION_ID, SKILL_NAMES, XP_FOR_99_ELITE, XP_FOR_99_NORMAL,
    load_profile, load_quests, xp_needed_for_99,
)
from snapshots import save_snapshot

HERE = Path(__file__).parent
HOST = "127.0.0.1"   # this computer only - never 0.0.0.0
PORT = 8080
USERNAME = DEFAULT_USERNAME
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

# Live account data, filled by refresh(). Fetched on start-up and on Refresh only.
STATE = {"profile": None, "account": None, "fetched_at": None, "error": None}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_account():
    """Fetch profile and quests with the existing step 1 functions."""
    return load_profile(USERNAME), load_quests(USERNAME)


async def refresh():
    """Fetch from RuneMetrics, update STATE and save a snapshot. Returns True on success."""
    try:
        # run.io_bound runs the slow download in the background so the page doesn't freeze.
        result = await run.io_bound(fetch_account)
    except SystemExit as err:
        # The existing fetch code stops with a plain message on errors; show it instead.
        STATE["error"] = str(err)
        return False
    if result is None:   # the app is shutting down
        return False
    profile, quest_data = result
    now = datetime.datetime.now()
    STATE.update(profile=profile, account=read_account(profile, quest_data), fetched_at=now, error=None)
    save_snapshot(USERNAME, profile, now)
    return True

app.on_startup(refresh)


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


def updated_text():
    when = STATE["fetched_at"]
    return f"Stats updated {when:%H:%M}, {when.day} {when:%b}" if when else f"Stats updated {NO_VALUE}"


def no_data_panel():
    """Shown when there are no stats yet (e.g. RuneMetrics couldn't be reached)."""
    with panel():
        ui.label("No stats loaded").classes("heading")
        ui.label(STATE["error"] or "RuneMetrics hasn't answered yet.").classes("muted")


async def on_refresh(button):
    button.disable()
    ui.notify("Fetching your stats from RuneMetrics…")
    await refresh()
    ui.navigate.reload()


# ---------------------------------------------------------------------------
# Screen 1: Home
# ---------------------------------------------------------------------------

@ui.page("/", title="RS3 Planner")
def home_page():
    with ui.column().classes("page"):
        ui.label("RS3 Planner").classes("title")
        ui.label(USERNAME).classes("subtitle")
        with ui.row().classes("row-line centered"):
            ui.label(updated_text()).classes("muted")
            refresh_button = button("Refresh").props("unelevated no-caps").classes("btn-quiet")
            refresh_button.on_click(lambda: on_refresh(refresh_button))

        if STATE["error"] and STATE["account"]:
            with panel(crimson=True):
                ui.label("Last refresh failed - showing older stats").classes("label")
                ui.label(STATE["error"]).classes("muted")

        account, profile = STATE["account"], STATE["profile"]
        if account is None:
            no_data_panel()
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

    with ui.column().classes("page"):
        back_button("/play")
        account = STATE["account"]
        if account is None:
            no_data_panel()
        elif session == "afk":
            afk_plan(account, hours, minutes)
        else:
            active_plan(account, hours)
    bottom_nav("")


def afk_plan(account, hours, minutes):
    ui.label("Your AFK plan").classes("title")
    ui.label(f"{hours:g} hours · a click at most every {minutes:g} min").classes("muted")

    # The same function the terminal uses; a copy so each visit starts fresh.
    plan = build_plan(copy.deepcopy(METHODS), account, minutes)
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
# Start
# ---------------------------------------------------------------------------

app.add_static_files("/static", HERE / "static")
# "?v=..." is the stylesheet's last-change time: when the file changes, the address
# changes, so browsers fetch the new version instead of an old cached copy.
CSS_VERSION = int((HERE / "static" / "app.css").stat().st_mtime)
ui.add_head_html(f'<link rel="stylesheet" href="/static/app.css?v={CSS_VERSION}">', shared=True)

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host=HOST, port=PORT, title="RS3 Planner", dark=True, reload=False, show=False)
