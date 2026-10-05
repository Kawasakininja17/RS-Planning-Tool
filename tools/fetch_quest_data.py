#!/usr/bin/env python3
"""
Fetch quest data from the RuneScape Wiki into data/quests.json
==============================================================

Starts from the final quest of every unlock in data/unlocks.json, reads each
quest's wiki page, and records:
  - length               (the "Length" row of the quest's info box)
  - quest_requirements   (only the quests DIRECTLY below it in the wiki's
                          requirement tree; the planner follows the chain itself)
  - skill_requirements   (the skill levels listed in the info box)
  - other_requirements   (non-quest lines in the tree, like "Ability to enter Morytania")
Then it does the same for every quest it found, until nothing new turns up.

Run it from the project folder when you want fresh data (it only READS the wiki):
    python3 tools/fetch_quest_data.py

Then run:  python3 check_methods.py   to make sure the result is valid.
"""

import datetime
import json
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))   # so we can reuse the skill list from rs3_planner.py
from rs3_planner import SKILL_NAMES  # noqa: E402
UNLOCKS_FILE = PROJECT / "data" / "unlocks.json"
QUESTS_FILE = PROJECT / "data" / "quests.json"
API = "https://runescape.wiki/api.php"
HEADERS = {"User-Agent": "rs3-planner/1.0 (personal planning tool; reads public quest pages)"}


class QuestPageParser(HTMLParser):
    """
    Reads a quest page's HTML and pulls out the info box facts.
    HTMLParser calls handle_starttag / handle_endtag / handle_data as it
    walks through the page, so we keep track of where we are.
    """

    def __init__(self):
        super().__init__()
        self.length = None
        self.skills = {}              # {"Agility": 75, ...}
        self.tree_root = None         # the quest's own node in the requirement tree
        self._in_length = False
        self._in_requirements = False # inside the info box "Requirements" cell
        self._in_tree = False         # inside the quest requirement tree
        self._stack = []              # open <li> nodes in the tree
        self._td_depth = 0
        self._table_depth = 0         # tables nested inside the Requirements cell
        self._requirements_done = False

    # Each tree node: {"title": page title or None, "text": visible text, "children": [...]}
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "td" and "questdetails-info" in classes:
            if attrs.get("data-attr-param") == "length" and self.length is None:
                self._in_length = True
                self.length = ""
            elif "qc-active" in classes and not self._requirements_done:
                # The main Requirements cell. Many pages have more cells further
                # down (e.g. "Full completion" levels); only the first one counts.
                self._in_requirements = True
                self._td_depth = 0   # counts cells nested INSIDE this one, not the cell itself
                self._table_depth = 0
                return
        if self._in_requirements:
            if tag == "td":
                self._td_depth += 1
            if tag == "table":
                self._table_depth += 1
                if "questreq" in classes:
                    self._in_tree = True
            # Only count levels at the top of the cell. Nested sections (like the
            # collapsed "Ironmen:" list) hold extra levels for ironman accounts only.
            if (tag == "span" and "skillreq" in classes and "data-skill" in attrs
                    and self._table_depth == 0):
                level = int(attrs["data-level"])
                skill = attrs["data-skill"]
                self.skills[skill] = max(level, self.skills.get(skill, 0))
            if self._in_tree and tag == "li":
                node = {"title": None, "text": "", "children": []}
                if self._stack:
                    self._stack[-1]["children"].append(node)
                elif self.tree_root is None:
                    self.tree_root = node
                self._stack.append(node)
            if self._in_tree and tag == "a" and self._stack and self._stack[-1]["title"] is None:
                if "selflink" in classes:
                    self._stack[-1]["title"] = "SELF"
                elif attrs.get("title"):
                    self._stack[-1]["title"] = attrs["title"]

    def handle_endtag(self, tag):
        if self._in_length and tag == "td":
            self._in_length = False
            self.length = self.length.strip()
        if self._in_requirements:
            if self._in_tree and tag == "li" and self._stack:
                self._stack.pop()
            if tag == "table":
                self._table_depth -= 1
                if self._in_tree:
                    self._in_tree = False
            if tag == "td":
                if self._td_depth == 0:
                    self._in_requirements = False   # left the Requirements cell
                    self._requirements_done = True
                else:
                    self._td_depth -= 1

    def handle_data(self, data):
        if self._in_length:
            self.length += data
        if self._in_tree and self._stack:
            self._stack[-1]["text"] += data


def fetch_page_html(title):
    params = {"action": "parse", "page": title, "prop": "text", "redirects": 1, "format": "json"}
    url = f"{API}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as response:
        data = json.load(response)
    if "error" in data:
        raise RuntimeError(f"wiki error for '{title}': {data['error'].get('info')}")
    return data["parse"]["title"], data["parse"]["text"]["*"]


def read_quest(title):
    real_title, page_html = fetch_page_html(title)
    parser = QuestPageParser()
    parser.feed(page_html)
    if parser.tree_root is None and parser.length is None:
        raise RuntimeError(f"'{real_title}' doesn't look like a quest page (no info box found)")

    quests, other = [], []
    for child in (parser.tree_root or {"children": []})["children"]:
        text = " ".join(child["text"].split()).rstrip("…").strip()
        # A line whose text is exactly its link's page name is a quest.
        # Anything else ("Ability to enter Morytania", "Started: ...") is kept as text.
        if child["title"] and child["title"] != "SELF" and text == child["title"]:
            quests.append(child["title"])
        elif text and text != "None":   # the wiki writes "None" when there are no quests
            other.append(text)

    # Some level requirements aren't skills (e.g. "combat level"); keep them as text.
    skills = {}
    for name, level in sorted(parser.skills.items()):
        if name in SKILL_NAMES:
            skills[name] = level
        else:
            other.append(f"{name[0].upper()}{name[1:]} {level}")
    return {
        "title": real_title,
        "length": parser.length,
        "quest_requirements": quests,
        "skill_requirements": skills,
        "other_requirements": other,
        "source_url": "https://runescape.wiki/w/" + urllib.parse.quote(real_title.replace(" ", "_"), safe="/'"),
        "checked_date": datetime.date.today().isoformat(),
    }


def main():
    unlocks = json.loads(UNLOCKS_FILE.read_text(encoding="utf-8"))["unlocks"]
    to_visit = [u["final_quest"] for u in unlocks]
    quests = {}

    while to_visit:
        title = to_visit.pop(0)
        if title in quests:
            continue
        try:
            quest = read_quest(title)
        except Exception as err:   # stop on any problem; partial data is never written
            sys.exit(f"Error while reading '{title}': {err}\nNothing was written.")
        quests[quest["title"]] = quest
        print(f"  {quest['title']}: {len(quest['quest_requirements'])} quest(s), "
              f"{len(quest['skill_requirements'])} skill(s), length {quest['length']!r}")
        to_visit.extend(q for q in quest["quest_requirements"] if q not in quests)
        time.sleep(0.5)   # be polite to the wiki's servers

    output = {
        "about": "Generated by tools/fetch_quest_data.py from RuneScape Wiki quest pages. "
                 "quest_requirements lists only DIRECT requirements; the planner follows the chain.",
        "quests": [quests[t] for t in sorted(quests)],
    }
    QUESTS_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {len(quests)} quests to {QUESTS_FILE.relative_to(PROJECT)}")


if __name__ == "__main__":
    main()
