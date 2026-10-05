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
from rs3_planner import DIFFICULTY_NAMES

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
    """The big goal this player picked last time in the menu, or None."""
    try:
        return (player_dir(username) / "last_goal").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def save_last_goal(username, name):
    try:
        folder = player_dir(username)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "last_goal").write_text(name + "\n", encoding="utf-8")
    except OSError:
        pass   # remembering the choice is a convenience, not essential


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


def ranked_doable(goal, unlocks, quests, account):
    """
    Every quest you can do now, best first. Returns (titles, on_goal_path).
    Rank: on the way to the most unlocks, then shortest, then easiest.
    Quests on the big goal's path come first; others only if none are ready.
    (Also used by the browser app for "Tonight's quest" and "also on the way".)
    """
    def rank(title):
        difficulty = account["quests"].get(title, {}).get("difficulty", 999)
        return (-unlock_count(title, unlocks, quests), length_rank(quests[title]["length"]), difficulty)

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

    other = [(t, o) for t in chain if t not in account["completed_quests"]
             for o in quests[t]["other_requirements"]]
    if other:
        print("\n  Other requirements (check these yourself):")
        for title, text in other:
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
