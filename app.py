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
  player_cache.py  the in-memory store of fetched players

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

from account import LEVEL_XP, skill_rows
from check_methods import load_methods, load_quest_files
from plan_session import build_plan, path_lines
from player_cache import entry_for, fetch_safely, needs_fetch, record_failure, record_success
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
NAV_TARGETS = {"Home": "/", "Skills": "/skills", "Quests": "/quests"}


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
    for (letter, path_name), (_, method, why) in zip(PATH_NAMES, plan["paths"]):
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
            for warning in method["_warnings"]:
                ui.label(f"Watch: {warning}").classes("muted small")
            for unlock in method["_unanswered"]:
                unlock_question(name, unlock)

    your_answers(name, answers)
    ruled_out_panel(plan)


def ruled_out_panel(plan):
    """
    Every method the planner ruled out for this session, with the checker's own
    reasons (the list the terminal prints). Folded behind a button; hidden when
    nothing was ruled out.
    """
    ruled_out = plan["ruled_out"]
    if not ruled_out:
        return
    with panel():
        show_text = f"Why not the others? ({len(ruled_out)} ruled out)"
        toggle = button(show_text).props("unelevated no-caps").classes("btn-quiet")
        # Drawn now but hidden; the button shows or hides it (nothing is fetched).
        reasons_list = ui.column().classes("w-full gap-2")
        with reasons_list:
            for method, reasons in ruled_out:
                with ui.column().classes("gap-0"):
                    ui.label(method["name"]).classes("heading")
                    ui.label(method["skill"]).classes("muted small")
                    ui.label("; ".join(reasons)).classes("muted small")
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
