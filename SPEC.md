# RS3 Session Planner — Spec v0.1

Oct 3, 2026 · Chris Baron

## Goal and scope

The planner tells Hels Glasglo how to spend one session: given the hours available and how AFK the session is, it returns three skilling or money paths plus a quest suggestion.

- **Long-term target:** max cape (99 in every skill), about 269 million XP away.
- **Out of scope for v1:** completionist cape. It has about 102 requirements, mostly achievements the public data can't see.
- **Ground rule:** public data only (RuneMetrics and the RuneScape Wiki). Nothing that reads or controls the game client.

## Inputs

Three questions per session, plus the username once.

| Input | Example | Notes |
| --- | --- | --- |
| Username | Hels Glasglo | Set once; RuneMetrics profile must be public |
| Hours available | 5 | Drives the "what 5 hours gets you" estimate |
| Max minutes between clicks | 1–2 | A setting per session, not fixed; each method stores its real AFK time |
| Session type | AFK or active | AFK shows paths A–C; active adds the quest path |

## Data sources

Two RuneMetrics endpoints cover the account; the RuneScape Wiki covers everything about methods. Blog and guide-site numbers are not used: one claimed 12M/hr for elder rune bars where the wiki says about 3.85M at a far stronger setup.

| Source | Gives | Address |
| --- | --- | --- |
| RuneMetrics profile | XP per skill, total XP, recent activity | `apps.runescape.com/runemetrics/profile/profile?user=Hels%20Glasglo&activities=20` |
| RuneMetrics quests | Every quest: status, difficulty, quest points, `userEligible` | `apps.runescape.com/runemetrics/quests?user=Hels%20Glasglo` |
| RuneScape Wiki | XP rates, AFK times, requirements, profit at live GE prices | [runescape.wiki](https://runescape.wiki/w/Money_making_guide/Skilling) |

**Quirks the tool must handle**

- XP in `skillvalues` is stored ×10; divide before use.
- The `level` field is unreliable past 99: Fishing reads 99 with about 27.9M XP. Compute levels from XP.
- RuneMetrics counts 59 quests complete, the game screen 47. The extra are miniquests and holiday quests.
- Both endpoints are unofficial: no login, but the format can change and a private profile returns an error.
- The fetching must run on the Linux PC. A hosted web page can't call other sites.

**Existing work to borrow from:** an [RS3 server for Claude](https://github.com/Buecherfresser/rs3-mcp) (RuneMetrics, GE prices, wiki pages; stdio mode only) and the [Loadstone](https://github.com/damianpoole/loadstone) command-line tool.

## Account snapshot

Max cape needs about 269M more XP, nearly 40% above the 193.8M earned so far.

XP still needed to reach 99 (RuneMetrics, 3 October 2026), smallest first:

| Skill | XP to 99 |
| --- | --- |
| Mining | 2,908,622 |
| Defence | 5,948,086 |
| Construction | 6,783,927 |
| Archaeology | 7,084,093 |
| Smithing | 7,449,863 |
| Cooking | 7,908,860 |
| Constitution | 8,445,687 |
| Agility | 10,444,639 |
| Prayer | 10,610,246 |
| Divination | 10,769,023 |
| Firemaking | 10,788,705 |
| Crafting | 10,874,586 |
| Fletching | 11,000,623 |
| Farming | 11,786,637 |
| Ranged | 11,957,970 |
| Hunter | 12,100,178 |
| Summoning | 12,138,597 |
| Runecrafting | 12,410,112 |
| Magic | 12,468,507 |
| Herblore | 12,642,003 |
| Dungeoneering | 12,692,043 |
| Attack | 12,741,868 |
| Strength | 12,743,575 |
| Slayer | 12,799,932 |
| Invention | 21,781,493 |

Invention uses the steeper elite curve, so its 99 sits at 36.1M XP. Thieving, Fishing, Woodcutting and Necromancy are already 99+. RuneMetrics counts 59 quests complete and 4 started; 35M gp is in the bank.

## AFK paths: the 5-hour example

For 5 hours at 1–2 minutes per click, two paths are ready and the gold path is still open. Every path shows the method, what the hours get you, and why it was picked.

| Path | Skill (XP left) | Method | XP or profit per hour | 5 hours gets | Status |
| --- | --- | --- | --- | --- | --- |
| A: finish something | Mining 96 (2.9M to 99) | Light or dark animica | ~94k mostly AFK, ~124k with rockertunities | ~470–620k: about level 97 (567k away) | Ready; check no unlock needed |
| B: max XP | Ranged 73 (134k to 75), then Defence 92 | AFK combat in the Abyss | 500–600k, depends on gear | Ranged 75 in under an hour; the rest into Defence | Access confirmed (Enter the Abyss) |
| C: gold | Divination 81 | Vibrant energy (needs 60) | ~5M, unverified | — | Open |

- **Why Ranged first in B:** it closes a Plague's End requirement, so XP buys an unlock.
- **Mining feeds Smithing:** each elder rune bar takes one light animica, one dark animica and one rune bar.
- **Ruled out for C:** incandescent energy needs 95 Divination. Elder rune bars give 26 XP each and only speed up at 94 Smithing (2,000 bars/hr there); at 90 expect about 1,300 bars and roughly 35k XP per hour.
- **Speed-ups:** quest rewards and buying supplies for Herblore and Summoning use the 35M gp in the bank.

## Quest path

The quest path ranks by what a quest unlocks first, then shows difficulty and length beside it. It runs in two modes.

- **Big goal:** one long-term unlock, its full quest chain, and the skill gaps to close.
- **Tonight:** the best quest marked `userEligible` for an active session, preferring ones on the way to the big goal.

RuneMetrics already rates difficulty: 0 Novice, 1 Intermediate, 2 Experienced, 3 Master, 4 Grandmaster, 250 quest series. What each quest unlocks is not in RuneMetrics, so v1 uses a hand-picked list of about 10 big unlocks taken from the wiki.

### Worked example: Plague's End

[Plague's End](https://runescape.wiki/w/Plague%27s_End) is Grandmaster and the ninth and final Elf quest. Its reward is access to Prifddinas, plus 50k XP lamps in all 10 of the skills it requires at 75. Four of those are short:

| Skill | Level now | XP to 75 |
| --- | --- | --- |
| Dungeoneering | 62 | 868,033 |
| Herblore | 63 | 817,993 |
| Summoning | 71 | 314,587 |
| Ranged | 73 | 133,960 |

The quest chain, none started yet (the wiki's tree is cut off past Regicide, so more may hide there):

1. Plague City (eligible now)
2. Biohazard
3. Underground Pass
4. Regicide
5. Roving Elves
6. Mourning's End Part I
7. Mourning's End Part II
8. Within the Light
9. Plague's End

Also required: Making History (eligible now), Waterfall Quest, Sheep Herder, Big Chompy Bird Hunting and Catapult Construction. The Restless Ghost and Morytania access are already done. The final fight is the level-107 Dark Lord five times; the wiki recommends magic or Necromancy, and Necromancy is at 101.

## Open questions and build plan

The build starts with a small script on the Linux PC and grows one piece at a time; four facts are still missing first.

- [ ] What gear is used for combat? It decides real Abyss rates.
- [ ] Settle Path C on the wiki: vibrant energy and other AFK money at current levels.
- [ ] Confirm animica needs no extra unlock.
- [ ] Pick the first 10 big unlocks for the quest path.

**Build order**

1. Script that fetches the profile and quests, then prints XP to 99 per skill and the quests eligible now.
2. A methods file of about 10 AFK methods, typed in from the wiki: skill, level, XP/hr, minutes per click, requirements.
3. The path picker: filter methods by your levels, quests and click time, then pick paths A, B and C.
4. The quest path: big goal plus tonight's pick.

## Sources

- [Plague's End](https://runescape.wiki/w/Plague%27s_End) · [Pay-to-play Mining training](https://runescape.wiki/w/Pay-to-play_Mining_training) · [Abyss combat training](https://runescape.wiki/w/Abyss/Combat_training)
- [Smelting elder rune bars](https://runescape.wiki/w/Money_making_guide/Smelting_elder_rune_bars) · [Elder rune bar](https://runescape.wiki/w/Elder_rune_bar) · [Incandescent energy](https://runescape.wiki/w/Incad) · [Skilling money making guide](https://runescape.wiki/w/Money_making_guide/Skilling)
- [Completionist cape](https://runescape.wiki/w/Comp) · RuneMetrics data for Hels Glasglo, pulled 3 October 2026
