"""
RS3 Planner - XP snapshots
==========================

Every fetch from RuneMetrics saves a small record of your XP, so a later
Progress screen can chart how it changes over time.

Files go to data/snapshots/YYYY-MM-DD_HHMM.json (two fetches in the same
minute share one file; the later one wins). Snapshots stay out of git.
"""

import datetime
import json
from pathlib import Path

from rs3_planner import SKILL_NAMES

SNAPSHOT_DIR = Path(__file__).parent / "data" / "snapshots"


def save_snapshot(username, profile, when=None):
    """Write one snapshot and return its path."""
    when = when or datetime.datetime.now()
    skills = {}
    for skill in profile["skillvalues"]:
        if skill["id"] < len(SKILL_NAMES):
            skills[SKILL_NAMES[skill["id"]]] = skill["xp"] / 10   # RuneMetrics stores XP x10

    record = {
        "username": username,
        "fetched_at": when.isoformat(timespec="seconds"),
        # RuneMetrics' own total: the sum of each skill's whole XP (tenths dropped).
        "total_xp": profile["totalxp"],
        "skills": skills,
    }
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{when:%Y-%m-%d_%H%M}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path
