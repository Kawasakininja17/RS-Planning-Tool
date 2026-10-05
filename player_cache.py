"""
RS3 Planner - the in-memory store of fetched players
====================================================

The browser app keeps each player's RuneMetrics data here while it runs, so a
name is fetched once and again only on Refresh (we don't hammer the unofficial
RuneMetrics API). Kept apart from app.py so the automatic tests can check it
without starting the browser app.

The cache is a plain dict: {folder_name(player): entry}, where an entry is
    {"name", "profile", "account", "fetched_at", "error"}
"""

from account import read_account
from players import folder_name
from rs3_planner import load_profile, load_quests


def blank_entry(name):
    return {"name": name, "profile": None, "account": None, "fetched_at": None, "error": None}


def entry_for(cache, name):
    """This player's entry, created empty if they haven't been fetched yet."""
    return cache.setdefault(folder_name(name), blank_entry(name))


def needs_fetch(cache, name):
    """True if we have no stats for this name yet (so RuneMetrics must be asked)."""
    entry = cache.get(folder_name(name))
    return entry is None or entry["account"] is None


def fetch_safely(name):
    """
    Download one player's profile and quests (slow; the app runs this in the background).
    Returns (profile, account, None) on success, or (None, None, error message).
    Never raises, so the screen can always show what went wrong instead of freezing.
    """
    try:
        profile, quest_data = load_profile(name), load_quests(name)
        return profile, read_account(profile, quest_data), None
    except SystemExit as err:
        # The existing fetch code stops with a plain message on errors; keep it to show.
        return None, None, str(err)
    except Exception as err:
        # Anything else: a connection dropped halfway, or a reply in a shape we don't know.
        return None, None, (f"Something unexpected went wrong talking to RuneMetrics "
                            f"({type(err).__name__}). Try again in a moment.")


def record_failure(cache, name, message):
    """Keep the error to show; any older stats for this player stay as they were."""
    entry = entry_for(cache, name)
    entry["error"] = message
    return entry


def record_success(cache, name, profile, account, when):
    """Store freshly fetched stats and return the player's entry."""
    entry = entry_for(cache, name)
    # RuneMetrics sends the name with its proper capitals; use that from now on.
    entry.update(name=profile.get("name", name), profile=profile, account=account,
                 fetched_at=when, error=None)
    # RuneMetrics accepts other spellings ("hels-glasglo", "Hels_Glasglo") and answers
    # with the real name, so file the entry under the real name too. Otherwise the
    # app, which then asks for "Hels Glasglo", wouldn't find these stats.
    cache[folder_name(entry["name"])] = entry
    return entry
