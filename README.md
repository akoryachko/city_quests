# City Quests

Printable "Conquer the City" quest booklets for family trips with a young child (about 5–10),
inspired by JetLag: The Game. The family team conquers the city zone by zone by
completing challenges: find and count historic details, riddles that lead to the
next landmark, local food, photo/build/collect tasks, rides on local transport and
kid-vs-parent duels. Coins, perks, curses, ranks, a street map with stickers and
spoiler-free parent pages are included.

The quests are made by the Claude Code skill **`city-quest`**.

## Making a quest

Open Claude Code in this folder and run:

```
/city-quest <city>
```

For example `/city-quest Utrecht`. The Amsterdam quest is a home-city
**campaign** starting at Amsterdam Centraal: 12 zones conquered in any order over many outings, each zone on
its own sheet; print just the sheets for the next outing. You can also just ask in plain words, for
example *"make a quest for our day in Utrecht next Saturday"*, and the skill
starts by itself. Anything you already know helps: date and times, how you
travel, things you have booked, must-sees.

What happens next is a conversation:

1. **Profile**: Claude reads `family-profile.md` and tells you which
   preferences it assumes. On the first run (or a fresh clone) there is none:
   Claude asks about the kid (age, boy/girl for the Russian wording,
   languages), the booklet and your likes, and creates it. Missing details are
   asked for later as they become relevant.
2. **Interview**: a few questions about the date and time window, transport,
   which experiences you want this time (museum hunts, historic rides, LEGO,
   boats, playgrounds…), pace and budget, must-sees.
3. **Research**: sights, opening hours and timetables for your date, food,
   coordinates.
4. **Plan check**: zones, stops, timing and anything unconfirmed. Adjust it
   here; it is the cheapest moment to change direction.
5. **Build**: the booklet is written and rendered.
6. **Remember**: new preferences and lessons go into the profile.

Later changes work the same way, in the same or a new session:
*"I booked the Pieten Expres at 12:00, rearrange around it"*,
*"exclude the LEGO store detour"*, *"arrive earlier"*.

## What you get

Each city gets its own folder, e.g. `hoorn/`:

| File | Use |
|---|---|
| `quest.pdf` | Print booklet: A4 landscape, two A5 cards per sheet, black-and-white friendly. Cut along the dashed line. |
| `quest.md` + `quest-map*.png` | The same quest for the phone, with Google Maps links for every stop. |
| `quest.json` | The source of the quest. Claude edits this; the other files are generated from it. |
| `quest.html` | Intermediate render, can be opened in a browser. |

Booklet order: cover → rules (coins, perks, ranks, curses) → map → one card
per zone → collection → scorecard → certificate → parent pages (day plan,
**tickets and bookings with step-by-step instructions**, then per zone the
answers, logistics and **the story behind every spot** to tell on the way).
The parent pages start on their own sheet so the kid's cards stay spoiler-free.

To play you need: a sheet of ~2 cm stickers (claiming zones on the cards and the
map), a pen, glue or tape for the collection card, a stopwatch on the phone, and
the kid's step, height and hand (plus their time for one floor of stairs) measured at
home for the measuring challenges.

## After the trip

Tell Claude how it went, for example *"Hoorn: the tram was a hit, the harbour
was too long, finished as Kapitan"*. It records the lessons in the profile
so the next city works better.

## Family profile

`family-profile.md` is private: it is git-ignored and never committed. See
`family-profile.example.md` for its shape. It holds what stays the same between trips: players and
wording, language and print format, likes and dislikes, standing challenges
(e.g. LEGO passport stamps), transport habits, lessons from past trips and a
trip log. Claude keeps it up to date; you can also edit it by hand.

The quests themselves are public and generic: they use the profile's
preferences (age, wording, likes) but no names, addresses or other personal
details, so any family can play them. Set `players.gender` to `"f"` in a
`quest.json` to switch the built-in labels to feminine wording.

## Rebuilding by hand

After editing a `quest.json` yourself:

```bash
python3 .claude/skills/city-quest/scripts/build_quest.py hoorn/quest.json
```

Exit code 2 means some card has too much text; the script names it.
Requirements: Python 3, Google Chrome or Chromium (for the PDF), and internet
access for the maps on the first build (OpenStreetMap street data and tiles;
cached in `~/.cache/city-quest/`). A new area takes a few minutes the first time.

## Where the skill lives

The skill is a project skill in `.claude/skills/city-quest/` in this repository,
so Claude Code finds it whenever it runs in this folder (also after a fresh clone):

| Path | Content |
|---|---|
| `SKILL.md` | The workflow Claude follows |
| `references/challenge-design.md` | Challenge types, volume, coin economy, JetLag mechanics, safety, Russian style |
| `references/example-quest.json` | The Hoorn quest as a structural example |
| `scripts/build_quest.py` | Renderer: quest.json → md, html, pdf, map |

The skill and the quests share one history in this repository.
