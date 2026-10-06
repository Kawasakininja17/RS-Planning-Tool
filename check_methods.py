#!/usr/bin/env python3
"""
RS3 Planner - check the data files
==================================

Checks every data file for missing fields or broken values:
  data/methods.json  - hand-typed training and money methods (step 2)
  data/unlocks.json  - the big unlocks for the quest path (step 4)
  data/quests.json   - quest requirements fetched from the wiki (step 4)
then prints the methods as a table.

How to run (from the project folder):
    python3 check_methods.py

If anything is wrong, it lists each problem and exits with an error code,
so a mistake in the file can't slip through quietly.
"""

import datetime   # to check that dates are real dates
import json       # to read the methods file
import re         # to check the shape of unlock ids
import sys        # to exit with an error code when problems are found
from pathlib import Path   # to find the data file next to this script

# Reuse the skill-name list from step 1, so the names live in one place.
from rs3_planner import SKILL_NAMES

DATA_DIR = Path(__file__).parent / "data"
METHODS_FILE = DATA_DIR / "methods.json"
UNLOCKS_FILE = DATA_DIR / "unlocks.json"
QUESTS_FILE = DATA_DIR / "quests.json"

# Every method must have exactly these fields.
REQUIRED_FIELDS = [
    "type", "name", "skill", "min_level", "max_level",
    "xp_per_hour_low", "xp_per_hour_high", "gp_per_hour", "gp_after_tax",
    "minutes_between_clicks", "requirements", "unverified",
    "source_url", "checked_date", "notes",
]

WIKI_PREFIX = "https://runescape.wiki/w/"


# ---------------------------------------------------------------------------
# Small helpers for checking types
# ---------------------------------------------------------------------------

def is_whole_number(value):
    # In Python, True/False count as numbers, so rule them out explicitly.
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value):
    return (isinstance(value, (int, float))) and not isinstance(value, bool)


def is_list_of_text(value):
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


# ---------------------------------------------------------------------------
# Checking one method
# ---------------------------------------------------------------------------

def check_method(method, position):
    """Return a list of problems found in one method (empty list = all good)."""
    label = f"Method #{position} ({method.get('name', 'no name')})"
    problems = []

    # 1. Missing or unexpected fields.
    for field in REQUIRED_FIELDS:
        if field not in method:
            problems.append(f"{label}: missing field '{field}'")
    for field in method:
        if field not in REQUIRED_FIELDS:
            problems.append(f"{label}: unknown field '{field}' (typo?)")
    if problems:
        return problems   # the checks below assume every field exists

    # 2. Text fields.
    if method["type"] not in ("training", "money"):
        problems.append(f"{label}: type must be 'training' or 'money'")
    if not isinstance(method["name"], str) or not method["name"].strip():
        problems.append(f"{label}: name must be non-empty text")
    if not isinstance(method["notes"], str):
        problems.append(f"{label}: notes must be text")

    # 3. Skill: one skill, or several joined by "/" (like "Ranged/Defence").
    if not isinstance(method["skill"], str):
        problems.append(f"{label}: skill must be text")
    else:
        for skill in method["skill"].split("/"):
            if skill not in SKILL_NAMES:
                problems.append(f"{label}: unknown skill '{skill}'")

    # 4. Levels. min_level is where the method starts; max_level is the top of the
    #    level band the wiki's rates were quoted for (null = no upper limit), and
    #    still counts as inside it. Where the wiki writes ranges (Mining, smelting,
    #    bonfires) they're copied as written, so neighbours share an edge level and
    #    both are offered there. Where it gives only starting levels (Fort Forinthry,
    #    pickpocketing), each band ends one level before the next method starts.
    if not is_whole_number(method["min_level"]) or not 1 <= method["min_level"] <= 120:
        problems.append(f"{label}: min_level must be a whole number from 1 to 120")
    top = method["max_level"]
    if top is not None and (not is_whole_number(top) or not 1 <= top <= 120):
        problems.append(f"{label}: max_level must be a whole number from 1 to 120, or null")
    elif top is not None and is_whole_number(method["min_level"]) and top < method["min_level"]:
        problems.append(f"{label}: max_level ({top}) is below min_level ({method['min_level']})")

    # 5. XP and GP. null (None in Python) means "the wiki didn't say".
    low, high, gp = method["xp_per_hour_low"], method["xp_per_hour_high"], method["gp_per_hour"]
    for field in ("xp_per_hour_low", "xp_per_hour_high", "gp_per_hour"):
        value = method[field]
        if value is not None and not is_whole_number(value):
            problems.append(f"{label}: {field} must be a whole number or null")
    if is_whole_number(low) and is_whole_number(high) and low > high:
        problems.append(f"{label}: xp_per_hour_low is bigger than xp_per_hour_high")
    if (low is None) != (high is None):
        problems.append(f"{label}: set both XP values or neither")
    if is_whole_number(low) and low <= 0:
        problems.append(f"{label}: XP per hour must be above 0")
    # Training methods need XP; money methods need GP.
    if method["type"] == "training" and low is None:
        problems.append(f"{label}: training methods need XP per hour")
    if method["type"] == "money" and gp is None:
        problems.append(f"{label}: money methods need gp_per_hour")
    # gp_after_tax says whether the wiki's gp figure is after Grand Exchange tax.
    if gp is None and method["gp_after_tax"] is not None:
        problems.append(f"{label}: gp_after_tax must be null when gp_per_hour is null")
    if gp is not None and not isinstance(method["gp_after_tax"], bool):
        problems.append(f"{label}: gp_after_tax must be true or false when there is a gp figure")

    # 6. Minutes between clicks: a positive number, or null.
    minutes = method["minutes_between_clicks"]
    if minutes is not None and (not is_number(minutes) or minutes <= 0):
        problems.append(f"{label}: minutes_between_clicks must be a positive number or null")

    # 7. Requirements. "skills" are extra levels the planner checks live;
    #    "unlocks" are things RuneMetrics can't see, which each player answers.
    reqs = method["requirements"]
    if not isinstance(reqs, dict) or set(reqs) != {"quests", "other", "skills", "unlocks"}:
        problems.append(f"{label}: requirements must have exactly 'quests', 'other', 'skills' and 'unlocks'")
    else:
        for key in ("quests", "other"):
            if not is_list_of_text(reqs[key]):
                problems.append(f"{label}: requirements.{key} must be a list of text")
        problems.extend(check_skill_levels(reqs["skills"], f"{label}: requirements.skills"))
        problems.extend(check_unlock_list(reqs["unlocks"], label))
    if not is_list_of_text(method["unverified"]):
        problems.append(f"{label}: unverified must be a list of text")

    # 8. Source and date.
    problems.extend(check_source_and_date(method, label))
    return problems


def check_source_and_date(entry, label):
    """Every entry in every data file needs a wiki source and a real date."""
    problems = []
    if not isinstance(entry["source_url"], str) or not entry["source_url"].startswith(WIKI_PREFIX):
        problems.append(f"{label}: source_url must be a RuneScape Wiki page ({WIKI_PREFIX}...)")
    try:
        checked = datetime.date.fromisoformat(entry["checked_date"])
        if checked > datetime.date.today():
            problems.append(f"{label}: checked_date is in the future")
    except (TypeError, ValueError):
        problems.append(f"{label}: checked_date must be a date like 2026-10-04")
    return problems


def check_fields(entry, required, label):
    """Report missing and unexpected fields."""
    problems = [f"{label}: missing field '{f}'" for f in required if f not in entry]
    problems += [f"{label}: unknown field '{f}' (typo?)" for f in entry if f not in required]
    return problems


def check_skill_levels(skills, label):
    """A {skill: level} block: real skill names, whole-number levels from 1 to 120."""
    if not isinstance(skills, dict):
        return [f"{label} must be {{skill: level}}"]
    problems = []
    for skill, level in skills.items():
        if skill not in SKILL_NAMES:
            problems.append(f"{label}: unknown skill '{skill}'")
        if not is_whole_number(level) or not 1 <= level <= 120:
            problems.append(f"{label}: {skill} level must be a whole number from 1 to 120")
    return problems


# Unlock ids: lower-case words joined by hyphens, e.g. "smithing-autoheater".
UNLOCK_ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def check_unlock_list(unlocks, label):
    """requirements.unlocks: [{"id": "smithing-autoheater", "text": "..."}], each id once."""
    if not isinstance(unlocks, list):
        return [f"{label}: requirements.unlocks must be a list"]
    problems, seen = [], set()
    for position, unlock in enumerate(unlocks, start=1):
        where = f"{label}: unlock #{position}"
        if not isinstance(unlock, dict) or set(unlock) != {"id", "text"}:
            problems.append(f"{where} must have exactly 'id' and 'text'")
            continue
        if not isinstance(unlock["id"], str) or not UNLOCK_ID.fullmatch(unlock["id"]):
            problems.append(f"{where}: id must be lower-case words joined by hyphens, like 'smithing-autoheater'")
        elif unlock["id"] in seen:
            problems.append(f"{where}: id '{unlock['id']}' is listed twice")
        else:
            seen.add(unlock["id"])
        if not isinstance(unlock["text"], str) or not unlock["text"].strip():
            problems.append(f"{where}: text must be non-empty text")
    return problems


def check_unlock_ids_match(methods):
    """One answer covers every method with that unlock id, so the id must mean the same everywhere."""
    problems, texts = [], {}
    for method in methods:
        reqs = method.get("requirements") if isinstance(method, dict) else None
        unlocks = reqs.get("unlocks") if isinstance(reqs, dict) else None
        for unlock in unlocks if isinstance(unlocks, list) else []:
            if not (isinstance(unlock, dict) and isinstance(unlock.get("id"), str)
                    and isinstance(unlock.get("text"), str)):
                continue   # check_unlock_list already reports these
            if texts.setdefault(unlock["id"], unlock["text"]) != unlock["text"]:
                problems.append(f"Unlock id '{unlock['id']}' has different text in different methods")
    return problems


# ---------------------------------------------------------------------------
# Checking the quest files (step 4)
# ---------------------------------------------------------------------------

QUEST_FIELDS = ["title", "length", "quest_requirements", "skill_requirements",
                "other_requirements", "source_url", "checked_date"]
UNLOCK_FIELDS = ["name", "final_quest", "unlocks", "why_it_matters", "source_url", "checked_date"]


def check_quests(quests):
    problems = []
    titles = [q.get("title") for q in quests if isinstance(q, dict)]
    known = set(titles)
    for position, quest in enumerate(quests, start=1):
        label = f"Quest #{position} ({quest.get('title', 'no title') if isinstance(quest, dict) else '?'})"
        if not isinstance(quest, dict):
            problems.append(f"{label}: is not a {{...}} block")
            continue
        field_problems = check_fields(quest, QUEST_FIELDS, label)
        if field_problems:
            problems.extend(field_problems)
            continue
        if not isinstance(quest["title"], str) or not quest["title"].strip():
            problems.append(f"{label}: title must be non-empty text")
        if not isinstance(quest["length"], str) or not quest["length"].strip():
            problems.append(f"{label}: length must be non-empty text")
        for key in ("quest_requirements", "other_requirements"):
            if not isinstance(quest[key], list) or not all(isinstance(x, str) and x.strip() for x in quest[key]):
                problems.append(f"{label}: {key} must be a list of text")
        # Every required quest must have its own entry, or the chain would have a hole.
        for required in quest["quest_requirements"]:
            if required not in known:
                problems.append(f"{label}: requires '{required}', which isn't in the file")
        skills = quest["skill_requirements"]
        if not isinstance(skills, dict):
            problems.append(f"{label}: skill_requirements must be {{skill: level}}")
        else:
            for skill, level in skills.items():
                if skill not in SKILL_NAMES:
                    problems.append(f"{label}: unknown skill '{skill}'")
                if not is_whole_number(level) or not 1 <= level <= 120:
                    problems.append(f"{label}: {skill} level must be a whole number from 1 to 120")
        problems.extend(check_source_and_date(quest, label))

    for title in sorted({t for t in titles if titles.count(t) > 1}):
        problems.append(f"Duplicate quest: {title}")

    # A quest can't (indirectly) require itself, or following the chain would never end.
    requirements = {q["title"]: q.get("quest_requirements", []) for q in quests
                    if isinstance(q, dict) and "title" in q}
    def loops_back(start, current, seen):
        for nxt in requirements.get(current, []):
            if nxt == start:
                return True
            if nxt not in seen:
                seen.add(nxt)
                if loops_back(start, nxt, seen):
                    return True
        return False
    for title in requirements:
        if loops_back(title, title, set()):
            problems.append(f"{title}: its requirements loop back to itself")
    return problems


def check_unlocks(unlocks, quest_titles):
    problems = []
    names = [u.get("name") for u in unlocks if isinstance(u, dict)]
    for position, unlock in enumerate(unlocks, start=1):
        label = f"Unlock #{position} ({unlock.get('name', 'no name') if isinstance(unlock, dict) else '?'})"
        if not isinstance(unlock, dict):
            problems.append(f"{label}: is not a {{...}} block")
            continue
        field_problems = check_fields(unlock, UNLOCK_FIELDS, label)
        if field_problems:
            problems.extend(field_problems)
            continue
        for key in ("name", "final_quest", "unlocks", "why_it_matters"):
            if not isinstance(unlock[key], str) or not unlock[key].strip():
                problems.append(f"{label}: {key} must be non-empty text")
        if unlock["final_quest"] not in quest_titles:
            problems.append(f"{label}: final quest '{unlock['final_quest']}' isn't in quests.json "
                            "(run tools/fetch_quest_data.py)")
        problems.extend(check_source_and_date(unlock, label))
    for name in sorted({n for n in names if names.count(n) > 1}):
        problems.append(f"Duplicate unlock name: {name}")
    return problems


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def short(number):
    """Write big numbers compactly: 124072 -> '124k', 3741015 -> '3.74M'."""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    if number >= 1_000:
        return f"{number / 1_000:.0f}k"
    return str(number)


def xp_text(method):
    low, high = method["xp_per_hour_low"], method["xp_per_hour_high"]
    if low is None:
        return "-"
    return short(low) if low == high else f"{short(low)}-{short(high)}"


def print_table(methods):
    header = f"{'Type':<9}{'Method':<43}{'Skill':<15}{'Lvl':>6}  {'XP/hr':>10}  {'GP/hr':>7}  {'Click':>5}  Unlocks"
    print(header)
    print("-" * len(header))
    for m in methods:
        name = m["name"] if len(m["name"]) <= 41 else m["name"][:40] + "…"
        gp = short(m["gp_per_hour"]) if m["gp_per_hour"] is not None else "-"
        if m["gp_after_tax"] is False:
            gp += "^"   # marks a before-tax figure
        click = f"{m['minutes_between_clicks']:g}m" if m["minutes_between_clicks"] is not None else "?"
        unlocks = m["requirements"]["unlocks"]
        ready = "ok" if not unlocks else f"{len(unlocks)} to confirm"
        if m["unverified"]:
            ready += "*"
        band = f"{m['min_level']}-{m['max_level']}" if m["max_level"] is not None else f"{m['min_level']}+"
        print(f"{m['type']:<9}{name:<43}{m['skill']:<15}{band:>6}  {xp_text(m):>10}  {gp:>7}  {click:>5}  {ready}")
    print()
    print("Lvl: the level band the wiki's rates are for ('90+' = no upper limit).")
    print("Click: '?' = the wiki doesn't say.   Unlocks: how many things each player confirms in the app")
    print("(RuneMetrics can't see them); * = the rate also assumes something public data can't confirm.")
    print("Levels and quests are checked live by plan_session.py.")
    print("GP/hr: ^ = the wiki's figure is before Grand Exchange tax; the others are after tax.")


def print_gaps(methods):
    """List every value the wiki didn't give, and every open requirement."""
    print("\nValues the wiki didn't give (null):")
    for m in methods:
        nulls = [f for f in ("minutes_between_clicks",) if m[f] is None]
        # XP is only "missing" for training methods; GP only for money methods.
        if m["type"] == "money" and m["xp_per_hour_low"] is None:
            nulls.append("xp_per_hour")
        if nulls:
            print(f"  - {m['name']}: {', '.join(nulls)}")

    print("\nExtra levels needed (checked live for each player):")
    for m in methods:
        for skill, level in m["requirements"]["skills"].items():
            print(f"  - {m['name']}: {skill} {level}")

    print("\nUnlocks each player confirms for themselves:")
    for m in methods:
        for unlock in m["requirements"]["unlocks"]:
            print(f"  - {m['name']}: {unlock['text']}")

    print("\nCan't be confirmed from public data:")
    for m in methods:
        for item in m["unverified"]:
            print(f"  - {m['name']}: {item}")


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def read_list(path, key):
    """Read a data file and return its main list, or stop with a clear message."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        sys.exit(f"Error: can't find {path}")
    except json.JSONDecodeError as err:
        # Points at the exact spot, e.g. a missing comma.
        sys.exit(f"Error: {path.name} isn't valid JSON: {err.msg} "
                 f"(line {err.lineno}, column {err.colno})")
    items = data.get(key) if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        sys.exit(f"Error: {path.name} needs a non-empty \"{key}\" list.")
    return items


def stop_if_problems(problems, path):
    if problems:
        print(f"Found {len(problems)} problem(s) in {path.name}:")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)


def load_methods():
    """
    Load data/methods.json and check it. Returns the list of methods.
    If anything is wrong, prints every problem and stops the program,
    so nothing ever runs on a broken file. (Also used by plan_session.py.)
    """
    methods = read_list(METHODS_FILE, "methods")

    problems = []
    for position, method in enumerate(methods, start=1):
        if not isinstance(method, dict):
            problems.append(f"Method #{position}: is not a {{...}} block")
            continue
        problems.extend(check_method(method, position))

    # Names must be unique so later steps can refer to a method by name.
    names = [m.get("name") for m in methods if isinstance(m, dict)]
    for name in sorted({n for n in names if names.count(n) > 1}):
        problems.append(f"Duplicate method name: {name}")
    problems.extend(check_unlock_ids_match(methods))

    stop_if_problems(problems, METHODS_FILE)
    return methods


def load_quest_files():
    """Load and check data/quests.json and data/unlocks.json. Returns (unlocks, quests by title)."""
    quests = read_list(QUESTS_FILE, "quests")
    stop_if_problems(check_quests(quests), QUESTS_FILE)
    by_title = {q["title"]: q for q in quests}
    unlocks = read_list(UNLOCKS_FILE, "unlocks")
    stop_if_problems(check_unlocks(unlocks, set(by_title)), UNLOCKS_FILE)
    return unlocks, by_title


def main():
    methods = load_methods()
    unlocks, quests = load_quest_files()
    print(f"{QUESTS_FILE.name}: {len(quests)} quests, all fields present, every required quest included, no loops.")
    print(f"{UNLOCKS_FILE.name}: {len(unlocks)} unlocks, every final quest found.")
    print(f"{METHODS_FILE.name}: {len(methods)} methods, all fields present and valid.\n")
    print_table(methods)
    print_gaps(methods)


if __name__ == "__main__":
    main()
