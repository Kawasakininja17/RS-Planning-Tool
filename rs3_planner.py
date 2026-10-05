#!/usr/bin/env python3
"""
RS3 Planner - Step 1
====================

Reads a player's PUBLIC RuneMetrics data from the RuneScape website and prints:
  1. How much XP each skill still needs to reach level 99 (smallest first).
  2. Which quests the player can start right now (eligible but not started).

Only standard Python is used, so nothing needs to be installed.
This script only READS public web pages. It never touches the game client.

How to run:
    python3 rs3_planner.py                    (the player you last chose in the app, or it asks)
    python3 rs3_planner.py "Some Player"      (any other name, in quotes)
"""

import json             # turns the website's text replies into Python data
import sys              # lets us read the name typed on the command line
import urllib.error     # the kinds of errors a web request can raise
import urllib.parse     # makes names safe to put in a web address
import urllib.request   # downloads web pages

from players import cli_player   # which player: typed name, remembered player, or ask

# ---------------------------------------------------------------------------
# Settings and fixed game facts
# ---------------------------------------------------------------------------

PROFILE_URL = "https://apps.runescape.com/runemetrics/profile/profile?user={name}&activities=20"
QUESTS_URL = "https://apps.runescape.com/runemetrics/quests?user={name}"

# RuneMetrics gives skills as numbers. This list turns number -> name.
# The position in the list IS the id: SKILL_NAMES[0] is "Attack", etc.
# Order checked against the RuneScape Wiki "Application programming interface"
# page (RuneMetrics section), which lists 0 Attack ... 28 Necromancy.
SKILL_NAMES = [
    "Attack",        # 0
    "Defence",       # 1
    "Strength",      # 2
    "Constitution",  # 3
    "Ranged",        # 4
    "Prayer",        # 5
    "Magic",         # 6
    "Cooking",       # 7
    "Woodcutting",   # 8
    "Fletching",     # 9
    "Fishing",       # 10
    "Firemaking",    # 11
    "Crafting",      # 12
    "Smithing",      # 13
    "Mining",        # 14
    "Herblore",      # 15
    "Agility",       # 16
    "Thieving",      # 17
    "Slayer",        # 18
    "Farming",       # 19
    "Runecrafting",  # 20
    "Hunter",        # 21
    "Construction",  # 22
    "Summoning",     # 23
    "Dungeoneering", # 24
    "Divination",    # 25
    "Invention",     # 26
    "Archaeology",   # 27
    "Necromancy",    # 28
]

INVENTION_ID = 26

# XP needed for level 99.
XP_FOR_99_NORMAL = 13_034_431     # most skills
XP_FOR_99_ELITE = 36_073_511      # Invention uses the harder "elite" XP curve

# Quest difficulty numbers -> readable names.
DIFFICULTY_NAMES = {
    0: "Novice",
    1: "Intermediate",
    2: "Experienced",
    3: "Master",
    4: "Grandmaster",
    250: "Special",   # used for quest series
}

# Friendly explanations for error codes RuneMetrics may send back.
PROFILE_ERRORS = {
    "PROFILE_PRIVATE": "This player's RuneMetrics profile is set to private.",
    "NO_PROFILE": "No RuneMetrics profile was found. Check the spelling, "
                  "or the profile may be private.",
    "NOT_A_MEMBER": "RuneMetrics has no data for this player (not a member).",
}


# ---------------------------------------------------------------------------
# Downloading
# ---------------------------------------------------------------------------

def fetch_json(url):
    """
    Download a web address and return its contents as Python data.

    If anything goes wrong (no internet, website down, garbled reply),
    print a clear message and stop the program instead of crashing
    with a long technical traceback.
    """
    # Some websites refuse requests that don't say who is asking,
    # so we send a simple "User-Agent" name along with the request.
    request = urllib.request.Request(url, headers={"User-Agent": "rs3-planner/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        sys.exit(f"Error: the RuneScape website replied with HTTP {err.code} ({err.reason}).")
    except urllib.error.URLError as err:
        sys.exit(f"Error: could not reach the RuneScape website ({err.reason}). "
                 "Check your internet connection.")
    except TimeoutError:
        sys.exit("Error: the RuneScape website took too long to answer. Try again later.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        sys.exit("Error: the RuneScape website sent back something that isn't valid data.")


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def xp_needed_for_99(profile):
    """
    Return a list of (skill name, XP still needed) for every skill under 99,
    sorted with the smallest gap first.

    We work from XP only. The "level" field can't be trusted past 99
    (it can say 99 for a skill that has 27.9M XP).
    """
    gaps = []
    for skill in profile["skillvalues"]:
        skill_id = skill["id"]
        # RuneMetrics stores XP multiplied by 10, so divide it back down.
        xp = skill["xp"] / 10

        target = XP_FOR_99_ELITE if skill_id == INVENTION_ID else XP_FOR_99_NORMAL

        if xp < target:
            # If RuneScape ever adds a skill this list doesn't know, show its id.
            if skill_id < len(SKILL_NAMES):
                name = SKILL_NAMES[skill_id]
            else:
                name = f"Unknown skill #{skill_id}"
            gaps.append((name, target - xp))

    # Sort by the XP number (the second item in each pair), smallest first.
    gaps.sort(key=lambda pair: pair[1])
    return gaps


def print_skill_gaps(gaps):
    print("XP still needed to reach 99")
    print("-" * 40)
    if not gaps:
        print("Every skill is already 99 or higher. Congratulations!")
        return
    for name, xp in gaps:
        # :>14,.0f means: right-align, add commas, no decimal places.
        print(f"{name:<15}{xp:>14,.0f}")
    print("-" * 40)
    total = sum(xp for _, xp in gaps)
    print(f"{'TOTAL':<15}{total:>14,.0f}   (about {total / 1_000_000:.1f} million)")


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------

def available_quests(quest_data):
    """
    Return the quests the player is eligible for but hasn't started,
    sorted by difficulty and then alphabetically.
    """
    quests = [
        q for q in quest_data.get("quests", [])
        if q.get("userEligible") is True and q.get("status") == "NOT_STARTED"
    ]
    quests.sort(key=lambda q: (q["difficulty"], q["title"]))
    return quests


def print_quests(quests):
    print(f"Quests you can start now ({len(quests)})")
    print("-" * 40)
    if not quests:
        print("None found.")
        return
    for q in quests:
        difficulty = DIFFICULTY_NAMES.get(q["difficulty"], f"Unknown ({q['difficulty']})")
        print(f"{difficulty:<14}{q['title']}")


# ---------------------------------------------------------------------------
# Loading an account (also used by plan_session.py)
# ---------------------------------------------------------------------------

def load_profile(username):
    """Fetch a player's RuneMetrics profile, or stop with a clear message."""
    # quote() makes the name safe for a web address (a space becomes %20).
    profile = fetch_json(PROFILE_URL.format(name=urllib.parse.quote(username)))

    # A private or missing profile comes back as {"error": "..."}, not as skills.
    if "error" in profile:
        code = profile["error"]
        message = PROFILE_ERRORS.get(code, "RuneMetrics could not load this profile.")
        sys.exit(f"Could not load profile: {message} (code: {code})")
    return profile


def load_quests(username):
    """Fetch a player's quest list from RuneMetrics."""
    return fetch_json(QUESTS_URL.format(name=urllib.parse.quote(username)))


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def main():
    # The name typed after the script, or the remembered player, or ask.
    # Joining the pieces lets "python3 rs3_planner.py Hels Glasglo" work without quotes too.
    username = cli_player(" ".join(sys.argv[1:]).strip() or None)

    print(f"RuneMetrics planner for: {username}\n")

    profile = load_profile(username)
    print_skill_gaps(xp_needed_for_99(profile))
    print()

    print_quests(available_quests(load_quests(username)))


# Only run main() when this file is run directly (not when imported by another script).
if __name__ == "__main__":
    main()
