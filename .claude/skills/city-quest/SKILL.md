---
name: city-quest
description: Plan a city trip with the user and turn it into a printable "Conquer the City" quest booklet for a family with a young child (about 5–10): interview about dates, times, transport and the kinds of experiences they want, research real landmarks, then build kid-sized challenges (find & count, riddles leading to the next landmark, local food, photo/build/collect tasks, rides on local transport, kid-vs-parent duels) with coins, curses, a street map, sticker spots and spoiler-free parent pages. Writes quest.md + <city>-quest.pdf (A4 landscape, two A5 cards per sheet) into city_quests/<city>/ and remembers family preferences between trips. Use whenever the user mentions a city quest, a scavenger or treasure hunt for a trip, keeping their kid entertained while sightseeing, a game-show-style game for a city, planning a day out in a city with the kid, or says "make a quest for <city>", even if they don't say "skill" or "booklet".
---

# City Quest

Turn a trip to a city into a game the whole family plays: the family team
"conquers" the city zone by zone by completing challenges, with a few
kid-vs-parent duels for rivalry. The booklet is printed on A4 landscape and
cut into A5 cards — one card per zone that the kid carries.

This is a conversation, not a one-shot generator. The parents usually have not
been to the city, so the quest is also their guide: a short interview up front
and a plan check before writing the cards make the day work much better than
guessing.

## Files

Paths below are relative to the repository root (the `city_quests` folder
that holds this skill in `.claude/skills/city-quest/`).

- Family profile: `family-profile.md` —
  who plays, likes/dislikes, format and transport preferences, lessons from
  past trips. Read it first; keep it up to date (see step 7). It is private
  and git-ignored; `family-profile.example.md` shows the shape. Quests for
  another family (friends) use `profiles/<family-slug>.md` (also git-ignored), and
  their `quest.json` gets `"family": "<family-slug>"`; no `family` means the home
  family's `family-profile.md`.
- Challenge library: `library/` (see `library/README.md`) — reusable challenge
  **patterns** from the web and from past quests, with the places they fit, ages
  (4–14) and what they need. The `challenge-scout` agent fills it;
  `scripts/challenge_ledger.py` reports which types and patterns each quest used and
  how the family rated them (`<city>/feedback.json`, written by the `quest-feedback`
  skill, git-ignored).
- Output: `<city-slug>/` (slug =
  lowercase English city name: `hoorn`, `new-york`), holding `quest.json` and
  the rendered files. `quest.json` is in the profile's main booklet language;
  every other booklet language in the profile gets a full translation next to
  it, `quest.<lang>.json` (e.g. `quest.en.json`). Past quests there are good references for what
  families liked.

**Privacy.** The quests are committed to a public repository (and may be
published as web pages), while the profile is not. Use the profile to shape
the quest (age, wording, likes, language), but never copy identifying details
into `quest.json` or the notes: no names, home address or street, house
number, school, or "our house" tasks — not even in passing in a story
("the gate next to our house" gives the neighbourhood away). Start a home-city campaign at a public
place (a main station or square) and use public landmarks for "find X from
the tower" tasks. Keep the kid's age and gender out of the visible text
except through the wording itself.

## Workflow

### 1. Read the profile and the city folder

Read the family profile. If the quest is for another family, use (or create)
`profiles/<family-slug>.md` instead and ask about it the same way; their
likes, dislikes and age rule the quest, not the home family's.

- **No profile yet** (first run, or a fresh clone): before planning, set it
  up with the user in one or two AskUserQuestion rounds: the kid's age and
  gender (for the wording), the booklet language and the languages the kid
  speaks, printing (colour or black-and-white, phone), likes and dislikes
  (e.g. museums, LEGO, trains, food, drawing, collecting stamps), how they
  get around, and the home city if any. Write `family-profile.md` from the
  template at the end of this file (`family-profile.example.md` in the repo
  root is a filled example).
- **Profile with gaps**: compare it with the template; ask only about the
  missing fields that matter for this trip (fold them into the step 2
  interview), then fill them in.

Map the profile onto the quest: `players.gender` (`"m"` or `"f"`),
`language` (the main booklet language), the other booklet languages
(translations, step 6) and the wording rules in `references/challenge-design.md` §6.

Check the city folder. If it already holds a quest, ask whether to **update**
it (edit its `quest.json`) or plan a **new trip** next to it (render with
`--name quest-YYYY-MM` so nothing is overwritten).

### 2. Interview

Ask about what changes the plan, in one or two AskUserQuestion rounds
(up to 4 questions each, multi-select where it fits). Skip anything the
request or the profile already answers, and say in one line which profile
preferences you are assuming so the user can correct them.

What matters, roughly in order:
1. **When**: date (or season), arrival and departure times / how many hours.
   Opening days, markets, seasonal rides and daylight all depend on it.
   Never assume the weekday: ask which days they actually go out (many
   families have busy Saturdays and go on Sundays). Then check every venue
   for those days.
   For the home city or a long stay, ask whether it is one day or a
   **campaign** of many outings (see campaign mode in step 5).
2. **Getting there and around**: arrival point (station, car park, hotel) and
   how to move inside the city — walking, tram/bus/metro, ferry, bike. Rides
   on local or historic transport can themselves be challenges.
3. **Experiences wanted / not wanted** this time, e.g. museum hunts (find &
   collect inside a museum), historic train/tram/boat rides, shops with play
   value (LEGO store, toy or candy shop), playgrounds and parks, food tasting,
   harbour/boats, towers and views, markets. Offer the options that this city
   actually has; the profile lists the family's usual likes.
4. **Pace and budget**: walking distance the kid manages, paid attractions
   OK or not, rough budget.
5. **Must-sees** or places to avoid; where they are staying.

### 3. Research

Use web search to collect, for the trip date and time window
(including the profile's standing challenges, e.g. a LEGO Store for the
LEGO passport in the visited city):
- landmarks and kid-friendly spots matching the wanted experiences, and how
  they cluster into walkable areas;
- opening days/hours, closures, renovations, seasonal events and timetables
  (historic rides, ferries); mark anything you could not confirm;
- concrete, checkable details for spot/quiz challenges (what is on a facade,
  how many statues, heights, legends) — only use facts you actually read;
- 2–4 local dishes/snacks a child is likely to try and where to get them;
- local transport options and tickets if rides are wanted;
- coordinates for every stop and the start point. Geocode with OpenStreetMap
  Nominatim, one request per second, with a User-Agent:
  `curl -s -A "city-quest-skill/1.0" "https://nominatim.openstreetmap.org/search?format=json&limit=1&q=<urlencoded place, city>"`.

**Pick challenge patterns first.** Run the ledger for this family and the
library suggestions for the kid's age, leaving out what the profile dislikes
(map dislikes onto the README's `needs`, e.g. drawing):

```bash
S=.claude/skills/city-quest/scripts
python3 $S/challenge_ledger.py --family <slug>
python3 $S/challenge_ledger.py --family <slug> --suggest --age <age> --exclude-needs drawing
```

If the library is thin (under ~50 patterns) or a type the family needs has few
patterns, run the **`challenge-scout`** agent first (in parallel with the
researchers is fine), with the city named so it also collects that city's own
kids' trails into `library/cities/<city>.json`. From the suggestions, take the
types that are missing or rated well, and the place kinds those patterns need
(stairs, a fountain, a market…): put them in each researcher's brief.

Run the **`city-researcher`** agent (`.claude/agents/city-researcher.md`)
once per zone or area, in parallel: brief each with the city and area, the
outing day and time window, the kid's age, the family's likes and dislikes
(from the profile, without personal details), what is already planned and the
wanted patterns with the place kinds they need, so it looks for places that fit.
Each returns 8–12 candidate stops with checkable details, stories, hours,
coordinates and the nicest walking connections; pick from them, verify
anything flagged as unconfirmed, and keep the bulky research out of this
conversation. A one-zone day trip can be researched directly. The interview
and plan check stay in this conversation. Keep the URLs; they go into
`sources`.

### 4. Propose the plan

Before writing any cards, show a compact plan: zones in walking order with
their stops, the boss of each, rides, food stops, timing per zone, total
walking distance, and anything unconfirmed. Ask if it fits; adjust. This is
the cheapest moment to change direction.

Base the walking figures on the route report rather than guesses: write the
stops with coordinates into a draft `quest.json` (titles are enough) and run

```bash
python3 .claude/skills/city-quest/scripts/route_report.py <folder>/quest.json
```

It writes `<folder>/quest-routes.md`: per walk between stops the distance and
kid walking time, what the way runs along (main road, quiet street, car-free,
water, park), the landmarks passed and those a short detour away, and ⚠ flags
(hardly a walk, long, main road, streets walked twice). Reroute or move stops
for the flags, and use passed landmarks: they make good tasks, stories for
the parents, or a reason to take a nicer street.

### 5. Design the game and write quest.json

Read `references/challenge-design.md` before writing challenges — it covers
types, volume, coins, game mechanics, safety and Russian style —
and `references/game-patterns.md` for more game mechanics to vary them.
In short: ~2 zones per full day, 3–5 challenges + a boss per zone, mixed
types, one duel and one trail per zone, one taste per day, and
`coins_to_claim` ≈ 60–70 % of the zone total. Respect the profile's likes and
dislikes (e.g. no drawing tasks if the kid dislikes drawing).

Write `<output folder>/quest.json` following `references/example-quest.json`
(the Hoorn quest; copy its structure, not its facts). Fields worth knowing:

- `colour`: `true` when the family prints in colour: every zone gets its own colour (the same
  as its stickers) on its cards and maps, maps show blue water and green parks; text stays black
  on white. Leave it out for black-and-white printing.
- `hotel`: the start point (`name`, `emoji` e.g. 🚉 for a station, `lat`, `lon`).
- `zones[]`: `name`, `emoji`, `day`, `coins_to_claim`, `story` (1–2 sentences
  of legend/fun fact for the kid), `parent_story` (background for the
  parents), `challenges[]`, `boss`, `logistics` (`where`, `hours`,
  `cost`, `food`, `toilets`). Zone `lat`/`lon` only if no challenge has coordinates.
- challenge / boss fields: `type` (spot, trail, taste, photo, build, collect,
  ride, talk, move, measure, duel, quiz), `title`, `text`, `coins`, `pattern`
  (the library pattern id it uses; if it's a new mechanic of our own, add it to
  `library/patterns.json` with `origin: "own"`, and set a used pattern's `status` to
  `used`; same in the translations), optional
  `duel: true` (for a duel, `coins` is what the kid gets for playing; a win
  adds one more, printed as «🪙×2+1»), `optional: true` (for extras that may not happen, e.g. an
  unbooked boat ride), `answer` (short, for checking), `facts` (the story of
  the place for the parents, see challenge-design §4), and for anything tied to a spot
  `place` + `lat` + `lon`. Challenges are numbered 1.1, 1.2… on the cards and
  the map, in list order; list them in walking order, with the boss last (see
  challenge-design §1: never mid-route, and tasks inside a paid venue in one run).
  `"order": 3.5` puts a challenge between stops 3 and 4 on the route line if needed. A stop
  reached by ferry, tram or another ride gets `"leg": "ferry"` (or `"tram"`…):
  it is not checked for a walking connection. A `tram`, `train`, `rail`, `metro` or
  `steam tram` leg is drawn along the real tracks (OpenStreetMap) with a 🚋 on the line and a 🚪
  flag on the boarding stop. A ride to another town (more than 1.5 km from the walking stops)
  leaves the city map and its legend and shows on its zone map, which then uses map tiles
  (towns, roads, tracks) and has no 🚪 flags (at that scale they can't show which door). Give a stop at the far end coordinates even when the task happens
  on board or on the platform, so the zone map shows where the ride goes. A `trail`
  challenge's place is hidden from the kid (it is the riddle's answer).
  A photo hunt lists its targets in `spots` (`[{"lat", "lon", "name"}]`): each is drawn on the zone
  map as a camera icon without a name, so the kid sees which way to go; the card can then
  name the places. `name` is the target's words exactly as in the task text: on the website
  they become a Google Maps link to the spot.
  `"via": [{"lat", "lon"}…]` on a task makes the walk to it pass these points in order
  (a quieter street, a loop instead of walking the same street twice, past hunt targets);
  the route report and the map routing follow it.
- `rules`: `steps`, `perks` (`cost`, `text`), `curse_intro`, `curses`, and
  optional `nav_bonus` (coins per zone when the kid navigates all its stops alone;
  printed as 🧭 dots on the zone's coin line and added to the rank check).
- `parent`: `days[]` (`day`, `plan` — include times and transport), `bookings[]`,
  `shopping`, `tips`.
- `parent.bookings[]`: one entry for **everything that needs a ticket,
  reservation or ride** (trains, museums, tours, boats, special events, also
  optional ones): `what`, `status` (e.g. «бронировать заранее», «без брони»,
  «уточнить»), `when`, `where` (address / boarding point), `how` (explicit
  steps: which site or app, which button, what to choose, how to pay, whom to
  call), `cost` (adult/child; say when a price is unconfirmed), `link`. The
  parents should be able to book everything from this card alone.
  In a campaign, put a booking that belongs to one zone in that zone's own
  `bookings[]` (same fields): it prints on the zone's parent card, so
  everything for an outing is in one place. `parent.bookings` keeps only
  what belongs to no zone (a transport pass).
- `rules.ranks[]` (`min`, `name`, `text`): end-of-day rank for unspent coins,
  printed on the rules card and the certificate.
- **Campaign mode** — the family's home city or any place explored over many
  outings (zones conquered in any order, ~2 per outing): set
  `"campaign": true`. Then the overview map shows only numbered zone areas
  around the home point (`hotel`, emoji 🏠), each zone gets its own sheet
  (close-up map with stops and route on the left, challenges on the right) so
  parents print just the next outing's sheets, and the scorecard gets a date
  column. Per zone add `getting_there` (one kid-readable line, e.g. "⛴️ Паром
  F7 от Pontsteiger"). Add a city-wide `hunt` (`emoji`, `title`, `hint`,
  `items[]` with `text`, `boxes`, `coins`; each box prints as an 8 mm star like every checkbox, so the
  kid can tick it or cover it with an 8 mm star sticker; round circles are only coins). Rank counts coins **earned**:
  override `labels.ranks_hint` and `labels.total` accordingly. Use
  `parent.days[]` for suggested outings (zone pairs, best weekday, season
  dates) with `labels.day` = «Вылазка». Example: `amsterdam/quest.json` in
  the output folder.
- **A map for every zone (required).** Every zone gets its own sheet: its
  close-up map on the left, its challenges on the right (a day trip keeps its
  city map with the whole route up front; zone 1's route starts at the start
  point). The kid must be able to find every stop of a zone from its map:
  - Stops spread over streets: the street map with the walking route (default).
  - The whole zone in one building or site (a museum, a LEGO hall, a zoo, a
    tram or boat ride): look for the place's own plan or map (floor plan,
    site map, line map) on its website or in a search for "<place> plattegrond / floor
    plan / map". If you find a usable one, save it next to quest.json and set
    the zone's `map_image` (file name) and `map_source` (whose plan it is);
    it prints instead of the street map. Check it is legible at A5 and that
    publishing it on the family website is fine (prefer the venue's freely
    offered visitor plan; credit it).
  - No plan found: give the zone's first stop the coordinates of the
    **entrance** (or boarding point). When all stops of a zone are within
    ~80 m, the build shows a couple of streets around it and flags the
    entrance with a 🚪 door flag.
  `"zone_maps": false` leaves the per-zone sheets out (only on request).
- `players`: `kid_name`, `team_name` (empty → blanks to fill by hand).
- `measures`: the kid's body measures used by `measure` challenges, e.g.
  `["Шаг", "Рост", "Руки в стороны", "Ладонь"]` → blanks on the hunt card
  (or the rules card), with `labels.measures` as the heading. **Keep the list and the
  challenges in step:** after writing or changing challenges, check every measure is used
  by at least one challenge or boss (in its text or answer: pace with steps, compare with
  height, a palm count, the stairs time) and every body measure a challenge needs is in
  the list. Remove a measure nothing uses (a blank the kid fills in for nothing), and add
  one a challenge relies on; same in the translations.
- Optional `labels` / `type_labels` override UI text (built-in labels are
  Russian, masculine; `players.gender: "f"` switches the built-in
  labels to feminine). Write kid-facing text in the profile's gender, and
  prefer neutral forms where they read naturally («Задание выполнено»,
  «Видишь лодку — кричи…») so a quest can be reused by another family.

Answers and logistics never appear on the kid's cards; they are printed on
separate parent pages at the end, so keep spoilers there.

**Review before showing.** When the draft is complete (and after a big
change), run the **`quest-reviewer`** agent (`.claude/agents/quest-reviewer.md`)
with the quest's path. It did not write the draft, so it isn't anchored on it:
it reads the profile and its lessons, the design rules and a fresh route
report, checks the quest from the kid's and the parents' side and returns
prioritised fixes. Apply the clear ones, put real trade-offs to the user, then
build. Logistics distances and times (`where`) come from the route report.

### 6. Build and check

```bash
python3 .claude/skills/city-quest/scripts/build_quest.py <folder>/quest.json [--name quest]
```

This writes `quest.md` (full content with Google Maps links, phone-readable),
`quest-map.png` (used by the markdown), `quest.html` and `<city>-quest.pdf`
(e.g. `hoorn-quest.pdf`), plus the double-sided binder book `<city>-quest-book.pdf` (see below). Street
maps are drawn from OpenStreetMap data (Overpass API, cached in
`~/.cache/city-quest/streets`) with bold black street names on top, so the
kid can navigate by them. Stops are joined by straight lines, but the build
also finds the walk between them over the street network: the view includes
every street of the way, those streets are named first (more names in a
smaller font where space allows), and the map zooms out when they cannot all
be named. The build prints the walking distance per zone, a NOTE for streets
that still have no name, and a WARNING when two stops have no walking
connection on the map (wrong coordinates, or a ferry/tram leg that needs
`"leg"`) — fix every such warning, otherwise the kid cannot navigate it; a campaign's city overview uses OSM tiles. The
first build of a new area takes a few minutes (busy public servers are
retried). The map fits the view to the stops, outlines each zone around its
stops and draws the route. The build also prints the coin economy
(sure coins, zone claim shares, perks and ranks next to the suggested values)
and a `WARNING: economy` line for anything out of range — fix those;
`build_quest.py <folder>/quest.json --economy` runs only this check, instantly,
after any change to coins, perks or ranks. Card text is auto-sized; exit code 2
lists cards that still overflow — shorten those texts (or split a big zone
into two) and rebuild. The coin dots at the foot of a zone card must not touch the
"coins needed" label: the build shortens the label to "13 🏁" (then moves it to its own
line) when the row is full, and exits 2 with `COIN LINE` if the dots still touch — give
that zone fewer coins (a row holds about 25 dots, navigation dots included) and rebuild. Look at the
foot of the zone with the most coins on the rendered PDF.

**Ring binder.** The family files the kid's cards in a ring binder, so every kid sheet
with challenges (zone cards, and the map cards that share their sheet) must show where to
punch: each card keeps a 14 mm margin at the cut edge, and two punch spots are drawn in that
margin (6 mm circles 80 mm apart as ISO 838, centres 9 mm from the cut, centred on the card's
height), so the holes land in the same place on every card and never through text, a map or
a sticker circle. Parent pages have no punch spots. `build_quest.py` draws them; check them
on the rendered zone cards, and keep any new card type inside the margin.

**Book for the binder.** The build also writes `<city>-quest-book.pdf` (`<city>-quest-book.en.pdf`
for a translation): the kid's cards only, no parent pages, imposed for double-sided printing so
that, filed in the binder, the pages read in order and every zone opens as one spread. Page
order: cover, rules, map (hunt), the zones, collection, scorecard, certificate; a zone with a
map card starts on a left-hand page (its map left, its challenges right, the next zone's map on
the back of those challenges), with a notes page as filler where needed and at the end (pages
come in fours). Every page has a small page number in the hole margin. So that nothing is left
on a page once it is cut and punched, the book draws no dashed line or circles: the cut is two
light-grey dots on the middle line (at ¼ and ¾ of the height), and each hole is only its left and
right edge as two light-grey dots 5.5 mm apart (0.5 mm inside the 6 mm hole, so the punch takes
them). Print it double-sided, **flip on the short edge**. Each sheet holds four pages in a row
(sheet k: pages 4k−3 to 4k): cut it through the two dots, the right half comes first, the left
half turned over goes behind it. So the family cuts one sheet at a time with scissors, and can
print or reprint just the sheets it needs (pages 13–16 are sheet 4). Keep this order when adding card types: front matter before the zones, back
matter after.

**Translations.** When the profile lists more than one booklet language,
translate the finished `quest.json` into `quest.<lang>.json` for each other
language, after the main text is final (and again after every change): the
same structure, list order, coordinates and coins; only text changes, with
`"language"` set (built-in labels exist for `ru` and `en`; translate the
`labels` overrides too). Kid text stays short and playful in that language;
keep the profile's rules (e.g. no transcription for languages the kid speaks).
Check with a script that the two files have the same keys, list lengths and
non-text values, then build each file:
`build_quest.py <folder>/quest.en.json` writes `quest.en.md`, `<city>-quest.en.pdf` and `<city>-quest-book.en.pdf`. The website publishes only the main languages unless `build_site.py --langs ru,en` names more. Map
pictures show only numbers and local street names, so every language shares
the main quest's (`quest-map*.png`, `quest-pins.json`).

**Stickers.** `python3 .claude/skills/city-quest/scripts/build_stickers.py <folder>/quest.json [other/quest.json …]`
writes a colour A4 sheet of round zone-capture stickers for sticker paper (`<city>-stickers.pdf`,
or `stickers.pdf` for several quests on one sheet): per zone 2 × 18 mm (they cover the sticker
circle on the zone card), one colour per zone with no cut line (cut along the colour's edge; a little oversize covers
the card's circle better), plus two 32 mm
gold city medals for the certificate's medal circle (no cut line either, gold 0.6 mm past the edge), and two front + back pairs of 30 mm stickers
for a real gold sports medal (its empty 30 mm discs): the city's top rank («АДМИРАЛ АМСТЕРДАМА»)
around an engraved picture of the city on the front, «ПОКОРИТЕЛЬ АМСТЕРДАМА», a compass rose and the zone count
on the back, printed as polished gold with engraved text and a 0.6 mm gold bleed past the white
dotted cut line, so they look like part of the medal. `--big`/`--medal`/`--rank-medal` change the counts (`--small 2` adds 10 mm
number stickers); `--big 0 --medal 0` prints only the medal stickers, for every quest
named, on one sheet (e.g. when a city is finished). Every quest draws its city for the medal front:
`"medal_art"` in quest.json (and its translations), a small SVG line drawing of the city's best-known
sight in a ±7.5 unit box around 0,0 (≈ mm), e.g. Hoorn's Hoofdtoren with a ship over waves, Amsterdam's
canal-house gables with the three crosses; outlines `fill="none"`, small solid shapes `stroke="none"`.
Render it zoomed (`pdftoppm -r 400`) and check it reads as that city and stays inside the inner ring.
Without it the front falls back to `"medal_emblem"` (anchor, crown, star).

**Website.** `python3 .claude/skills/city-quest/scripts/build_site.py`
renders every city and language into the git-ignored `site/` folder (`--out
DIR` for another place, e.g. the family's website); it uses the maps and pin
positions from the booklet build, so build the booklets first. The README has
the commands for trying it locally.

Then look at the result: view `quest-map.png`, and render the zone cards with
`pdftoppm -r 70 -png -f 2 -l 3 <city>-quest.pdf <scratchpad>/page`, to catch an odd
route, overlapping labels or crowded cards.

Tell the user where the files are, the zones with timing, and anything to
verify on the spot. Mention that sheets are cut along the dashed line (kid cards keep a
14 mm margin at the cut with drawn punch spots for the ring binder), parent pages are the last sheets,
that `<city>-quest-book.pdf` is the kid's part as a double-sided book (flip on the short edge; cut each
sheet on its own: right half first, the left half turned over behind it; the back of each sheet is drawn 1 mm to the right so
it meets its front on the family printer, whose duplex is off by that much), and
stickers come from `build_stickers.py`.

### 7. Remember

Update the family profile whenever you learn something durable: a new like or
dislike, a format preference, how a past quest went ("too many challenges",
"loved the tram"). Add the trip to the trip log with a one-line outcome. If
the user comes back after a trip, ask how it went and record the lessons —
they are what makes the next city better. To rate challenges ("feedback on zone 1"),
use the **`quest-feedback`** skill: it stores 1–5 ratings and comments in
`<city>/feedback.json`, which the ledger uses to choose challenges next time. Don't store one-off trip details
there; those live in the city's `quest.json`.

## Profile template

```markdown
# Family profile for city quests

## Players
- Kid: age (or birth year, so it stays right), boy/girl (wording), name on booklet or not, languages spoken
- Parents: who plays
- Home city (for campaigns), without the address

## Booklet
- Languages: the main one (quest.json) and any translations; printing (colour / black-and-white); phone use

## Likes
## Dislikes
## Standing challenges (e.g. LEGO passport stamps)
## Getting around
## Format preferences
## Lessons from past trips
## Trip log
- YYYY-MM-DD · City · length · one-line outcome
```
