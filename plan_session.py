#!/usr/bin/env python3
"""
RS3 Planner - Steps 3 and 4: the session planner
================================================

Asks how long you can play, how often you can click, and whether the session
is AFK or active. Reads your live RuneMetrics data, filters data/methods.json
down to what you can do right now, and picks three paths:

  A: finish something  - the ready method for the skill furthest through its current level
  B: max XP            - the ready training method with the most XP per hour
  C: gold              - the ready money method with the most gp per hour

Active sessions also get the quest path (see quest_path.py): pick a big goal
from a menu, see its full quest chain, and get tonight's quest.

How to run (from the project folder):
    python3 plan_session.py                      (it asks you the questions)
    python3 plan_session.py --hours 5 --minutes 2 --session afk
    python3 plan_session.py --session active --goal 1
    python3 plan_session.py --user "Some Player"
"""

import argparse   # reads options like --hours 5 from the command line
import math       # floor() for the why line's percentage
import sys        # stops with a clear message if the answers file is broken
import textwrap   # wraps long notes onto several lines

from account import level_from_xp, level_progress, level_table, read_account
from check_methods import load_methods, load_quest_files
from players import cli_player, read_answers
from quest_path import choose_goal, print_quest_path
from rs3_planner import load_profile, load_quests

DEFAULT_HOURS = 5
DEFAULT_MINUTES = 2

# The two reasons that mean "you'll never use this method again". They are written
# by check_method_for_session and recognised by split_ruled_out, so both use these
# names: rewording one can't quietly stop the other from finding it.
ALREADY_120 = "already 120"
OUTGROWN = "you've outgrown this"


# ---------------------------------------------------------------------------
# Filtering: can you do this method right now?
# ---------------------------------------------------------------------------

def check_method_for_session(method, account, max_minutes, answers):
    """
    Returns (blocked_reasons, warnings, unanswered).
    No blocked reasons = you can do it now. Warnings are worth knowing but don't block.
    unanswered = unlocks RuneMetrics can't see that the player hasn't said yes or no to.
    answers = {unlock id: True/False} from players.read_answers().
    """
    blocked, warnings, unanswered = [], [], []
    skills = method["skill"].split("/")

    # Levels, checked live against your XP.
    for skill in skills:
        level = account["skills"][skill]["level"]
        if level < method["min_level"]:
            blocked.append(f"needs {skill} {method['min_level']} (you have {level})")
    # Level band: the wiki's rates are for min_level..max_level. Past max_level in
    # EVERY skill the method trains, you've outgrown it. (A two-skill method stays
    # while either skill is still inside the band.) null = no upper limit.
    top = method["max_level"]
    if top is not None:
        levels = [(skill, account["skills"][skill]["level"]) for skill in skills]
        if all(level > top for _, level in levels):
            have = " and ".join(f"{skill} {level}" for skill, level in levels)
            blocked.append(f"{OUTGROWN} ({have}; this method's rates are "
                           f"for levels {method['min_level']}–{top})")
    # Extra levels some methods need beyond min_level (e.g. 99 Mining for a mining cape).
    for skill, level in method["requirements"]["skills"].items():
        have = account["skills"][skill]["level"]
        if have < level:
            blocked.append(f"needs {skill} {level} (you have {have})")

    # Quests, checked live against RuneMetrics.
    for quest in method["requirements"]["quests"]:
        if quest not in account["completed_quests"]:
            blocked.append(f"quest not done: {quest}")

    # Unlocks RuneMetrics can't see: the player's own answers decide.
    for unlock in method["requirements"]["unlocks"]:
        answer = answers.get(unlock["id"])
        if answer is False:
            blocked.append(f"you said you don't have: {unlock['text']}")
        elif answer is None:
            unanswered.append(unlock)

    # Click time. A known time shorter than your limit means too much clicking.
    minutes = method["minutes_between_clicks"]
    if minutes is None:
        warnings.append("click time unknown (the wiki doesn't give one)")
    elif minutes < max_minutes:
        blocked.append(f"needs a click every {minutes:g} min; your limit is {max_minutes:g}")

    # Training only makes sense while a skill it trains still has a next level.
    # The XP tables stop at 120, so a method is finished once ALL its skills are 120.
    if method["type"] == "training" and all(level_progress(account, s) is None for s in skills):
        blocked.append(ALREADY_120)

    if method["gp_after_tax"] is False:
        warnings.append("gp figure is BEFORE Grand Exchange tax (the wiki gives no after-tax figure)")
    warnings.extend(f"assumes: {item}" for item in method["unverified"])
    return blocked, warnings, unanswered


# ---------------------------------------------------------------------------
# Picking paths A, B and C
# ---------------------------------------------------------------------------

def closest_skill(method, account):
    """
    Of the method's skills that still have a next level, the one furthest through
    its current level, as account.level_progress() describes it. On an exact tie the
    skill named first wins (max() keeps the first). check_method_for_session has
    already ruled out methods whose skills are all at 120, so there is always one.
    """
    progress = [level_progress(account, s) for s in method["skill"].split("/")]
    return max((p for p in progress if p is not None), key=lambda p: p["fraction"])


def closest_first(method):
    """Path A's order: furthest through its level first; on a tie, the faster method."""
    return (-method["_closest"]["fraction"], -method["xp_per_hour_low"])


def pick_paths(ready):
    """Pick A, B and C from the ready methods. A path is None if nothing fits."""
    training = [m for m in ready if m["type"] == "training"]
    money = [m for m in ready if m["type"] == "money"]

    # A: the skill furthest through its current level; if two tie, the faster method wins.
    path_a = min(training, key=closest_first, default=None)

    # B: most XP per hour, judged on the low end of each range so a wide,
    # optimistic range can't win on its best case. Prefer something other than A.
    others = [m for m in training if m is not path_a] or training
    path_b = max(others, key=lambda m: (m["xp_per_hour_low"], m["xp_per_hour_high"]), default=None)

    # C: most gp per hour.
    path_c = max(money, key=lambda m: m["gp_per_hour"], default=None)

    return path_a, path_b, path_c


RUNNER_UPS = 2   # how many "Also good" methods each path shows


def runner_ups(ready, picks, count=RUNNER_UPS):
    """
    For paths A, B and C: the next `count` best ready methods, ranked by that
    path's own rule (the same rules as pick_paths). No method appears twice on the
    page: a picked method is never a runner-up, and A's list is filled first, then
    B's, then C's, each skipping methods already listed above it (the next best one
    takes its place). Path A's list also shows different skills: a method whose
    skill is already shown under A is skipped. Returns [list for A, list for B,
    list for C].
    """
    others = [m for m in ready if not any(m is p for p in picks)]
    training = [m for m in others if m["type"] == "training"]
    money = [m for m in others if m["type"] == "money"]
    # sorted() keeps the methods file's order for ties, like min()/max() in pick_paths.
    # Path A shows different skills: keep only the first (best) method for each skill,
    # and none for the skill A's own pick already shows.
    path_a = picks[0]
    shown_skills = {path_a["_closest"]["skill"]} if path_a else set()
    by_closest = []
    for method in sorted(training, key=closest_first):
        if method["_closest"]["skill"] not in shown_skills:
            by_closest.append(method)
            shown_skills.add(method["_closest"]["skill"])
    by_xp = sorted(training, key=lambda m: (m["xp_per_hour_low"], m["xp_per_hour_high"]), reverse=True)
    by_gp = sorted(money, key=lambda m: m["gp_per_hour"], reverse=True)

    listed = []   # methods already shown under an earlier path
    lists = []
    for ranked in (by_closest, by_xp, by_gp):
        fresh = [m for m in ranked if not any(m is shown for shown in listed)][:count]
        listed.extend(fresh)
        lists.append(fresh)
    return lists


def also_text(method):
    """
    One runner-up in a line, e.g. 'Choking ivy · Woodcutting · 86,000–126,000 XP/hr'.
    Dots, not brackets: 16 method names already contain brackets ("Mining banite
    (training)") and 9 contain a colon ("Bonfire: oak logs"), but none a dot.
    """
    if method["type"] == "money":
        rate = f"{method['gp_per_hour']:,} gp/hr"
    elif method["xp_per_hour_low"] == method["xp_per_hour_high"]:
        rate = f"{method['xp_per_hour_low']:,} XP/hr"
    else:
        rate = f"{method['xp_per_hour_low']:,}–{method['xp_per_hour_high']:,} XP/hr"
    return f"{method['name']} · {method['skill']} · {rate}"


def percent_text(fraction):
    """
    e.g. 0.83949 -> '83.9%'. Rounded DOWN, so a level never shows 100.0% before it's
    reached. The computer's arithmetic can leave an exact 20% as 19.99999999999997%,
    so it is first tidied to 6 decimal places, then rounded down.
    """
    return f"{math.floor(round(fraction * 1000, 6)) / 10:.1f}%"


def xp_left_text(xp_left):
    """
    e.g. 1188.2 -> '1,188'. Used by both path A's why line and level_change_text's
    "XP away", so the two lines on one path never disagree. Less than half an XP
    would round to '0', which reads as "already there": say 'under 1'.
    """
    text = f"{xp_left:,.0f}"
    return "under 1" if text == "0" else text


def split_ruled_out(ruled_out):
    """
    Returns (blocked, finished_count). Methods you've finished the skill for
    ("already 120") or outgrown are just counted, whatever other reasons they
    have: you'll never use them, so a missing quest doesn't matter. Everything
    else (levels too low, quests, your answers, click time) is listed.
    """
    blocked, finished = [], 0
    for method, reasons in ruled_out:
        if any(r == ALREADY_120 or r.startswith(OUTGROWN) for r in reasons):
            finished += 1
        else:
            blocked.append((method, reasons))
    return blocked, finished


def build_plan(methods, account, max_minutes, answers):
    """
    Sort every method into "ready" or "ruled out", then pick paths A, B and C
    with a one-line reason each. Used by main() here and by the browser app (app.py).
    answers = {unlock id: True/False} from players.read_answers().
    Returns {"ready": [...], "ruled_out": [(method, reasons)], "paths": [(title, method, why)],
             "also": [runner-ups for A, for B, for C]}.
    """
    ready, ruled_out = [], []
    for method in methods:
        blocked, warnings, unanswered = check_method_for_session(method, account, max_minutes, answers)
        method["_warnings"] = warnings
        method["_unanswered"] = unanswered
        if blocked:
            ruled_out.append((method, blocked))
        else:
            if method["type"] == "training":
                method["_closest"] = closest_skill(method, account)
            ready.append(method)

    path_a, path_b, path_c = pick_paths(ready)

    if path_a:
        closest = path_a["_closest"]
        why_a = (f"{closest['skill']} is {percent_text(closest['fraction'])} of the way to "
                 f"{closest['next_level']} ({xp_left_text(closest['xp_left'])} XP left): "
                 "the furthest of your skills with a ready method.")
    else:
        why_a = ""
    why_b = "Highest XP/hr of your ready training methods (judged on the low end of each range)."
    why_c = "Highest gp/hr of your ready money methods."
    # Warn when the ranking compares before-tax and after-tax figures.
    tax_bases = {m["gp_after_tax"] for m in ready if m["type"] == "money"}
    if len(tax_bases) > 1:
        before = [m["name"] for m in ready if m["type"] == "money" and m["gp_after_tax"] is False]
        why_c += (" CAUTION: this ranking mixes before-tax and after-tax figures; "
                  f"after tax, {', '.join(before)} would earn less than shown.")

    return {
        "ready": ready,
        "ruled_out": ruled_out,
        "paths": [("PATH A: finish something", path_a, why_a),
                  ("PATH B: max XP", path_b, why_b),
                  ("PATH C: gold", path_c, why_c)],
        "also": runner_ups(ready, [path_a, path_b, path_c]),   # "Also good" under each path
    }


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def level_change_text(account, skill, xp_low, xp_high):
    """e.g. 'Mining 96 -> 96-97 (97 is 566,820 XP away)'. Uses the skill's own XP table."""
    now = account["skills"][skill]
    table = level_table(skill)
    start_level = now["level"]
    low_level = level_from_xp(now["xp"] + xp_low, skill)
    high_level = level_from_xp(now["xp"] + xp_high, skill)
    after = str(low_level) if low_level == high_level else f"{low_level}-{high_level}"
    text = f"{skill} {start_level} -> {after}"
    if start_level < len(table):
        to_next = table[start_level] - now["xp"]   # table[start_level] is the next level
        text += f" ({start_level + 1} is {xp_left_text(to_next)} XP away)"
    return text


def rate_text(low, high, unit):
    return f"{low:,} {unit}" if low == high else f"{low:,}-{high:,} {unit}"


def path_lines(method, account, hours):
    """
    The rate and "what N hours gets you" lines for one path, as (label, text) pairs.
    Labels: "Rate", "<N> hours", "Also", or "" for a continuation line.
    Used by print_path() here and by the browser app (app.py).
    """
    lines = []
    skills = method["skill"].split("/")
    if method["gp_per_hour"] is not None:
        gp = method["gp_per_hour"]
        lines.append(("Rate", f"{gp:,} gp/hr"))
        lines.append((f"{hours:g} hours", f"about {gp * hours:,.0f} gp"))
    if method["xp_per_hour_low"] is not None:
        low, high = method["xp_per_hour_low"], method["xp_per_hour_high"]
        if method["gp_per_hour"] is None:
            lines.append(("Rate", rate_text(low, high, "XP/hr")))
        gain_low, gain_high = low * hours, high * hours
        gained = f"+{gain_low:,.0f} XP" if low == high else f"+{gain_low:,.0f} to +{gain_high:,.0f} XP"
        label = f"{hours:g} hours" if method["gp_per_hour"] is None else "Also"
        if len(skills) == 1:
            lines.append((label, f"{gained} -> {level_change_text(account, skills[0], gain_low, gain_high)}"))
        else:
            lines.append((label, f"{gained} in total. The wiki doesn't say how it splits; "
                                 "if all of it went into one skill:"))
            for skill in skills:
                lines.append(("", level_change_text(account, skill, gain_low, gain_high)))
    return lines


def print_path(title, method, why, account, hours, also=()):
    print(title)
    if method is None:
        print("  Nothing in methods.json fits this session.\n")
        return

    print(f"  Method:  {method['name']} ({method['skill']})")
    for label, text in path_lines(method, account, hours):
        if label in ("Rate", "Also"):
            print(f"  {label}:    {text}")
        elif label == "":
            print(f"           {text}")
        else:
            print(f"  {label}: {text}")

    print(f"  Why:     {why}")
    if also:   # the next best methods for this path, for a choice
        print(textwrap.fill("; ".join(also_text(m) for m in also), width=100,
                            initial_indent="  Also good: ", subsequent_indent=" " * 13))
    for warning in method["_warnings"]:
        print(f"  Watch:   {warning}")
    for unlock in method["_unanswered"]:
        print(f"  Check:   needs {unlock['text']} (not answered yet; answer in the browser app)")
    # The notes hold the caveats behind the numbers, so always show them.
    print(textwrap.fill(method["notes"], width=100,
                        initial_indent="  Notes:   ", subsequent_indent=" " * 11))
    print(f"  Source:  {method['source_url']}")
    print()


def ask_number(question, default):
    """Ask for a positive number; Enter keeps the default."""
    while True:
        try:
            answer = input(f"{question} [{default:g}]: ").strip()
        except EOFError:   # no keyboard attached (e.g. run from another script)
            return default
        if not answer:
            return default
        try:
            value = float(answer)
        except ValueError:
            print("  Please type a number, like 5 or 1.5.")
            continue
        if value > 0:
            return value
        print("  Please type a number above 0.")


def ask_session_type(default="afk"):
    """AFK or active. Asked by number, because both words start with 'a'."""
    options = {"1": "afk", "2": "active"}
    default_number = "1" if default == "afk" else "2"
    while True:
        try:
            answer = input(f"Session type: 1 = AFK, 2 = active [{default_number}]: ").strip()
        except EOFError:
            return default
        if not answer:
            return default
        if answer in options:
            return options[answer]
        print("  Please type 1 or 2.")


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Pick three AFK paths for one session.")
    parser.add_argument("--user", help="RuneScape name (default: the player you last chose in the app)")
    parser.add_argument("--hours", type=float, help="hours available")
    parser.add_argument("--minutes", type=float, help="most minutes you can go between clicks")
    parser.add_argument("--session", choices=["afk", "active"], help="AFK shows paths A-C; active adds the quest path")
    parser.add_argument("--goal", help="big goal for active sessions: menu number or unlock name")
    args = parser.parse_args()
    username = cli_player(args.user)

    # Ask only for what wasn't given on the command line.
    hours = args.hours if args.hours and args.hours > 0 else ask_number("Hours available", DEFAULT_HOURS)
    max_minutes = (args.minutes if args.minutes and args.minutes > 0
                   else ask_number("Most minutes you can go between clicks", DEFAULT_MINUTES))
    session = args.session or ask_session_type()

    methods = load_methods()   # stops here if methods.json has problems
    account = read_account(load_profile(username), load_quests(username))
    try:
        answers = read_answers(username)
    except ValueError as err:
        sys.exit(f"Error: {err}")

    goal = None
    if session == "active":
        unlocks, quests = load_quest_files()   # stops here if the quest files have problems
        goal = choose_goal(unlocks, quests, account, username, preset=args.goal)

    plan = build_plan(methods, account, max_minutes, answers)

    print(f"\nSession plan for {username}: {hours:g} hours, a click at most every {max_minutes:g} minutes, "
          f"{session} session")
    print(f"{len(plan['ready'])} of {len(methods)} methods fit this session.\n")

    for (title, method, why), also in zip(plan["paths"], plan["also"]):
        print_path(title, method, why, account, hours, also)

    print("Ruled out for this session:")
    for method, reasons in plan["ruled_out"]:
        print(f"  - {method['name']}: {'; '.join(reasons)}")

    if goal is not None:
        print()
        print_quest_path(goal, unlocks, quests, account)


if __name__ == "__main__":
    main()
