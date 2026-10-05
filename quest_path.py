"""
RS3 Planner - Step 4: the quest path
====================================

Used by plan_session.py for "active" sessions. For one big goal (an unlock
from data/unlocks.json) it shows:
  - the full quest chain, prerequisites first, with your progress on each quest
  - the skill levels still needed anywhere in that chain
  - tonight's pick: the best quest you can start now

Quest requirements come from data/quests.json (fetched from the wiki by
tools/fetch_quest_data.py). Your progress and levels come live from RuneMetrics.
"""

import textwrap
from account import xp_to_level
from players import player_dir
from rs3_planner import DIFFICULTY_NAMES, available_quests

# Quest lengths as the wiki writes them, shortest first.
LENGTH_ORDER = ["very short", "short", "short to medium", "medium", "medium to long",
                "long", "long to very long", "very long"]


def length_rank(length):
    """Position in LENGTH_ORDER; unknown lengths sort last."""
    text = length.strip().lower()
    return LENGTH_ORDER.index(text) if text in LENGTH_ORDER else len(LENGTH_ORDER)


# ---------------------------------------------------------------------------
# Chains and progress
# ---------------------------------------------------------------------------

def full_chain(title, quests):
    """Every quest needed for `title`, prerequisites first and `title` last."""
    order = []

    def visit(quest_title):
        if quest_title in order:
            return
        for required in quests[quest_title]["quest_requirements"]:
            visit(required)
        order.append(quest_title)

    visit(title)
    return order


def quest_state(title, quests, account):
    """
    Returns (state, reasons). state is one of:
      done     - completed
      started  - in progress
      ready    - you can start it now
      blocked  - reasons says why
    """
    record = account["quests"].get(title, {})
    status = record.get("status")
    if status == "COMPLETED":
        return "done", []

    reasons = []
    waiting = [q for q in quests[title]["quest_requirements"] if q not in account["completed_quests"]]
    if waiting:
        reasons.append("waiting on " + ", ".join(waiting))
    for skill, level in quests[title]["skill_requirements"].items():
        have = account["skills"][skill]["level"]
        if have < level:
            reasons.append(f"needs {skill} {level} (you have {have})")
    # RuneMetrics knows things the wiki's box may not list, so it gets a vote too.
    if not reasons and not record.get("userEligible", False):
        reasons.append("RuneMetrics says you're not eligible yet")

    if status == "STARTED":
        return "started", reasons
    return ("blocked", reasons) if reasons else ("ready", [])


def skill_gaps(chain, quests, account):
    """
    For the unfinished part of a chain: {skill: (level needed, your level, XP to go, [quests])}.
    Only the highest level needed for each skill is kept.
    """
    gaps = {}
    for title in chain:
        if title in account["completed_quests"]:
            continue
        for skill, level in quests[title]["skill_requirements"].items():
            have = account["skills"][skill]["level"]
            if have >= level:
                continue
            if skill not in gaps or level > gaps[skill][0]:
                gaps[skill] = (level, have, xp_to_level(account, skill, level), [title])
            elif level == gaps[skill][0]:
                gaps[skill][3].append(title)
    return dict(sorted(gaps.items(), key=lambda item: item[1][2]))   # smallest XP gap first


def goal_progress(unlock, quests, account):
    chain = full_chain(unlock["final_quest"], quests)
    done = sum(1 for t in chain if t in account["completed_quests"])
    return chain, done


# ---------------------------------------------------------------------------
# Choosing the big goal
# ---------------------------------------------------------------------------

def read_last_goal(username):
    """The big goal this player picked last time, or None."""
    try:
        return (player_dir(username) / "last_goal").read_text(encoding="utf-8").strip() or None
    except (OSError, ValueError):
        # Missing or unreadable (OSError), or not valid text (UnicodeDecodeError is a
        # ValueError): treat it as "nothing saved" rather than crash.
        return None


def save_last_goal(username, name):
    """Remember the big goal. Returns True if saved, False if not.
    (The terminal ignores the answer; the app tells you when saving failed.)"""
    try:
        folder = player_dir(username)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "last_goal").write_text(name + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def goal_for(unlocks, username):
    """This player's big goal: their saved choice, else the first unlock (as the terminal menu does)."""
    last = read_last_goal(username)
    for unlock in unlocks:
        if unlock["name"] == last:
            return unlock
    return unlocks[0]


def choose_goal(unlocks, quests, account, username, preset=None):
    """
    Pick the big goal. `preset` (from --goal) can be a menu number or an unlock name.
    Otherwise show a menu; Enter keeps the last choice.
    """
    names = [u["name"] for u in unlocks]
    if preset:
        if preset.isdigit() and 1 <= int(preset) <= len(unlocks):
            return unlocks[int(preset) - 1]
        for unlock in unlocks:
            if preset.lower() in (unlock["name"].lower(), unlock["final_quest"].lower()):
                return unlock
        print(f"  '{preset}' isn't one of the unlocks; showing the menu instead.")

    last = read_last_goal(username)
    default = names.index(last) + 1 if last in names else 1

    print("\nBig goals:")
    for number, unlock in enumerate(unlocks, start=1):
        chain, done = goal_progress(unlock, quests, account)
        gaps = skill_gaps(chain, quests, account)
        gap_text = f", {len(gaps)} skill(s) short" if gaps else ""
        print(f"  {number}. {unlock['name']:<34} {done}/{len(chain)} quests done{gap_text}")

    while True:
        try:
            answer = input(f"Pick a big goal [{default}]: ").strip()
        except EOFError:
            answer = ""
        if not answer:
            choice = default
            break
        if answer.isdigit() and 1 <= int(answer) <= len(unlocks):
            choice = int(answer)
            break
        print(f"  Please type a number from 1 to {len(unlocks)}.")
    save_last_goal(username, unlocks[choice - 1]["name"])
    return unlocks[choice - 1]


# ---------------------------------------------------------------------------
# Tonight's pick
# ---------------------------------------------------------------------------

def unlock_count(title, unlocks, quests):
    """How many of the big unlocks this quest is on the way to."""
    return sum(1 for u in unlocks if title in full_chain(u["final_quest"], quests))


def quest_rank(title, unlocks, quests, account):
    """Sort key for "best first": on the way to the most unlocks, then shortest, then easiest."""
    difficulty = account["quests"].get(title, {}).get("difficulty", 999)
    return (-unlock_count(title, unlocks, quests), length_rank(quests[title]["length"]), difficulty)


def ranked_doable(goal, unlocks, quests, account):
    """
    Every quest you can do now, best first. Returns (titles, on_goal_path).
    Rank: on the way to the most unlocks, then shortest, then easiest.
    Quests on the big goal's path come first; others only if none are ready.
    (Also used by the browser app for "Tonight's quest" and "also on the way".)
    """
    def rank(title):
        return quest_rank(title, unlocks, quests, account)

    def doable(titles):
        return [t for t in titles if quest_state(t, quests, account)[0] in ("ready", "started")]

    # sorted() keeps ties in a fixed order (chain order here, name order below).
    on_path = doable(full_chain(goal["final_quest"], quests))
    if on_path:
        return sorted(on_path, key=rank), True
    elsewhere = doable(sorted({t for u in unlocks for t in full_chain(u["final_quest"], quests)}))
    if elsewhere:
        return sorted(elsewhere, key=rank), False
    return [], False


def pick_tonight(goal, unlocks, quests, account):
    """Best quest to do tonight. Returns (title, on_goal_path) or (None, False)."""
    titles, on_path = ranked_doable(goal, unlocks, quests, account)
    return (titles[0], on_path) if titles else (None, False)


# ---------------------------------------------------------------------------
# Lists for the Quests screen
# ---------------------------------------------------------------------------

def chain_rows(goal, quests, account):
    """The goal's chain, prerequisites first, one dict per quest:
    {"title", "state", "reasons", "difficulty", "length"} (state/reasons as quest_state gives them)."""
    rows = []
    for title in full_chain(goal["final_quest"], quests):
        state, reasons = quest_state(title, quests, account)
        rows.append({"title": title, "state": state, "reasons": reasons,
                     "difficulty": difficulty_name(title, account), "length": quests[title]["length"]})
    return rows


def other_requirements(chain, quests, account):
    """The wiki's other requirements for the unfinished quests in a chain, as (text, quest) pairs."""
    return [(text, title) for title in chain if title not in account["completed_quests"]
            for text in quests[title]["other_requirements"]]


def useful_to_start(unlocks, quests, account):
    """Quests RuneMetrics says you can start (eligible, not started) that lead to
    one of the big unlocks, best first (ties in name order)."""
    on_chains = {t for u in unlocks for t in full_chain(u["final_quest"], quests)}
    titles = sorted(t for t, q in account["quests"].items()
                    if t in on_chains and q.get("userEligible") is True and q.get("status") == "NOT_STARTED")
    return sorted(titles, key=lambda t: quest_rank(t, unlocks, quests, account))


def eligible_by_difficulty(account):
    """Every quest you can start now, grouped: [("Novice", [titles]), ...].
    Same list as the terminal's (available_quests). Known difficulties come first in
    the usual order; a code RuneMetrics never sent before gets its own group at the end."""
    eligible = available_quests({"quests": list(account["quests"].values())})
    groups = {}
    for q in eligible:   # already sorted by difficulty, then name
        code = q["difficulty"]
        groups.setdefault(DIFFICULTY_NAMES.get(code, f"Unknown ({code})"), []).append(q["title"])
    known = [(name, groups[name]) for name in DIFFICULTY_NAMES.values() if name in groups]
    unknown = [(name, titles) for name, titles in groups.items() if name not in DIFFICULTY_NAMES.values()]
    return known + unknown


def started_quests(account):
    """Quests RuneMetrics marks as started, in name order."""
    return sorted(t for t, q in account["quests"].items() if q.get("status") == "STARTED")


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def difficulty_name(title, account):
    code = account["quests"].get(title, {}).get("difficulty")
    return DIFFICULTY_NAMES.get(code, "?")


def print_quest_path(goal, unlocks, quests, account):
    chain, done = goal_progress(goal, quests, account)

    print(f"QUEST PATH - big goal: {goal['name']}")
    print(textwrap.fill(f"Unlocks: {goal['unlocks']}", width=100,
                        initial_indent="  ", subsequent_indent="           "))
    print(f"  Why it matters: {goal['why_it_matters']}")
    print(f"  Progress: {done} of {len(chain)} quests done\n")

    print(f"  {'Quest':<30}{'Difficulty':<14}{'Length':<20}Status")
    for title in chain:
        state, reasons = quest_state(title, quests, account)
        status = {"done": "done", "started": "STARTED", "ready": "READY NOW", "blocked": "blocked"}[state]
        if reasons:
            status += ": " + "; ".join(reasons)
        print(f"  {title:<30}{difficulty_name(title, account):<14}{quests[title]['length']:<20}{status}")

    gaps = skill_gaps(chain, quests, account)
    print("\n  Skill levels still needed for this chain:")
    if not gaps:
        print("    none - your levels already cover every quest in it")
    for skill, (level, have, xp, needed_by) in gaps.items():
        print(f"    {skill} {have} -> {level}: {xp:,.0f} XP  (for {', '.join(needed_by)})")

    other = other_requirements(chain, quests, account)
    if other:
        print("\n  Other requirements (check these yourself):")
        for text, title in other:
            print(f"    {text}  (for {title})")
    print("  Levels are as the wiki lists them; some may be boostable - see each quest's page.")

    title, on_path = pick_tonight(goal, unlocks, quests, account)
    print("\nTONIGHT'S QUEST")
    if title is None:
        print("  Nothing in your unlock chains is ready right now.")
        return
    count = unlock_count(title, unlocks, quests)
    where = "on the way to your big goal" if on_path else f"not on the {goal['name']} path (nothing there is ready)"
    print(f"  {title} - {difficulty_name(title, account)}, {quests[title]['length']}")
    print(f"  Why: {where}; helps {count} of your {len(unlocks)} unlocks; "
          "ranked by unlocks helped, then shortest, then easiest.")
    print(f"  Source: {quests[title]['source_url']}")
