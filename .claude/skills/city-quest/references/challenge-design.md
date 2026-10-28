# Designing challenges for a young child

The player is a child of about 5–10 travelling with their parents; age,
gender (for Russian wording), reading level, languages and likes come from
the family profile. The defaults below assume about 7: can read short
sentences (the cards are in Russian) but tires of long text, counts confidently
up to ~30, loves competing with parents, and has maybe 2–3 hours of walking
energy before needing food or a playground. Every challenge should be doable
in 2–10 minutes, be checkable by a parent on the spot, and be fun even if they
fails.

## Contents
1. Challenge types and good examples
2. Ideas borrowed from JetLag: The Game
3. Volume and balance
4. Facts, answers and research
5. Safety and respect
6. Writing in Russian

## 1. Challenge types

| type | What it is | Good examples |
|---|---|---|
| `spot` | Find / count something visible | Count lions on a fountain; find 3 doors of different colours; spot the year on a building |
| `trail` | Riddle that leads to the next landmark — this is what moves the family through the zone | "Go where the tower with a golden ship points to the sky"; follow street signs with a symbol |
| `taste` | Try a local dish/snack, rate it | Name the dish in the local language + Russian; one per day minimum |
| `photo` | A specific, creative photo | Perspective trick (holding a tower); copy a statue's pose; something in the flag's colours |
| `build` | Make something on the spot, tied to what they see, from varied materials: found (sticks, bark, stones), bought there (a LEGO Pick & Build box at the store), or food (assemble a local snack from bought parts and take a bite) | Shelter of fallen sticks that stands alone for 10 s; stick-and-bark boat that floats 10 s; herring bun the kid assembles; tower at the LEGO store's demo table |
| `collect` | Get a flat souvenir for the "Моя коллекция" card | Candy wrapper, museum stamp, ticket, sugar packet, leaf, postcard, sticker from a shop |
| `ride` | A ride on local or historic transport, with a task during it | Check in with the transport card themselves; count stops; spot the river from the tram; steam-tram ride and find the conductor's whistle; ferry crossing — wave to 3 boats |
| `talk` | Use a local word/phrase | "Say 'Grazie' 3 times today" — Latin script + Cyrillic transcription. In a language the kid speaks (Dutch): no transcription; make the kid the team's interpreter instead: they order the snack or ask at the museum desk and translate what was said. Only where staff are reliably present (shops, stalls, cafés, ticket desks) — not at city farms or unstaffed sights |
| `move` | Physical / route mini-game; ⏱ time pressure (title starts with ⏱) to burn off steam, mostly at playgrounds | Slide 10 times in 3 minutes; touch 20 trees in 3 minutes; jump the stepping stones 5 times in a minute; run up the roof stairs, then beat your record; walk a kerb like a tightrope |
| `duel` | Kid vs parents head-to-head | Who spots it first; guess-the-number closest wins; count red vs blue bikes |
| `measure` | Measure with their body, then calculate or compare | Pace the smallest house, then the big one opposite: how many small ones fit? Time the tower lift and compare with the kid's own time for one floor of stairs ("the lift is N times faster"); time 100 m along a canal → how long for the whole canal; palms between two places on a city model |
| `quiz` | Guess with 2–3 options — use sparingly | Only when the answer is checked on the spot (a sign, an exhibit) |

Every challenge must need being at the place: the answer comes from
something they see, count, measure or do there. A question they could
answer at home from the card ("what was NOT stored here: cat skins or
chocolates?") is a bad challenge — turn it into a find ("find the year on the
warehouse stone; how old is it?").

**Variety is the key.** The family liked measuring ("pace the narrowest
house") and LEGO builds, then found a whole quest of them boring. Mix
kinds across the quest and keep each kind in proportion; when the family
dislikes something, reduce it rather than drop it. Rough targets for a
12-zone campaign: 1 LEGO build, ~3 other builds, 6–7 measure tasks, ~4
"guess how many" duels, ~6 ⏱ tasks, a few limitation tasks, 2–3
translator/ordering tasks.

Measure only with a purpose: the number must lead somewhere the kid can see
or feel ("how many small houses fit in the big one", "the lift is 10 times
faster than you on the stairs"). Counting for its own sake, or maths they
could do at home from the card (87 m ÷ 3, "how many dads make 6 m"), is
boring — replace it with something to find and name on the spot ("what
colour is the giant, and his ball?"). Good measure pattern: measure something small with steps/arm spans/hands → measure or look
up the big thing → compare or multiply (with a parent's help for big
numbers). Give the real number in `answer` when a source has it, otherwise
make it self-checking. Ask the family to note the child's step, height, arm span and
hand width at home (`measures` field → blanks on the hunt or rules card).

**Limitations** make a task harder or create a new one: eyes closed (holding
a parent's hand), on one foot, one hand behind the back ("count the towers
standing on one foot; foot down — start again"). They also work as curses.

Any non-duel challenge can also be marked `"duel": true` when it naturally
becomes a race. Give the kid a fair chance: parents count with one hand behind
their back, kid gets a 10-second head start, etc. — say so in the text.

The **boss** of a zone is tied to its most famous landmark and is a bit bigger:
a multi-step find, a pose/photo, a build, or a climb. A **paid venue**
(museum, tower) must hold more than one thing to do: two or three tasks
inside, or a multi-step boss — Micropia's stamp card plus a live water bear
under the microscope is the model. No drawing tasks — this
kid dislikes drawing (check the profile); kids who like collecting stamps
and stickers get one wherever a
place offers a stamp (tourist office, museum desk) or a sticker, use it.

## 2. Borrowed from JetLag: The Game, scaled down

JetLag's "Battle for America"/"Tag" games are about claiming territory by
completing challenges, with coins and curses. Adapted for a young child:

- **Claiming territory** → each zone is claimed with coins; the kid puts a sticker
  on the zone card and on the zone's area on the map. Seeing the map fill up
  is the main motivation.
- **Coins** → earned per challenge, spent on perks (hint, choosing lunch spot,
  making a parent do a curse, ice cream). Spent coins still count for claiming,
  so spending never feels like losing.
- **Curses** → light, silly, team-wide, never embarrassing in front of
  strangers or unsafe. Triggered by chance when entering a zone ("think of a
  number 1–6; 1 = curse"). 5–7 per quest, city-themed where possible.
- **Hide-and-seek style questions** → great for trails: "hotter / colder"
  guiding, "photograph the tallest thing you can see", "is the next place
  closer to the river or to the station?"
- Keep the stakes small and the mood co-op: the family plays against the city;
  duels are side quests that add rivalry without blocking progress.

## 3. Volume and balance

- **Zones**: about one per half day of sightseeing (2 per full day), plus a
  short zone for an arrival/departure afternoon. Every must-see place gets a
  zone or is the boss of one. A zone is walkable on foot in ~1.5–2.5 hours,
  landmarks within ~1 km of each other.
- **Per zone**: 3–5 challenges + 1 boss, at least 3 different types, at least
  one `duel` or duel-marked challenge, and a `trail` linking landmarks inside
  the zone or pointing to the next zone.
- **Per day**: at least one `taste`; at most one `measure` per zone on
  average; a `build` in only some zones. Every challenge must be doable on
  the spot with what is there: no carrying a LEGO set around and looking for
  a place to build.
- **Navigation bonus**: `rules.nav_bonus` (e.g. 2) gives that many coins per
  zone when the kid navigates the family to all its stops on their own; it prints
  as 🧭 dots after the zone's coins and counts as guaranteed in the rank
  check, so rescale the ranks when you add it.
- **Coins**: normal 2, harder 3, boss 6; optional/bookable extras 4–5. Set
  `coins_to_claim` to about 60–70 % of the zone's total, so a skipped or
  closed attraction does not block the claim.
- **Coin economy**: add up the coins of the whole trip (T, typically 70–90 for
  a day). Price perks so they stay tempting all day: hint ≈ 5, small choice
  ≈ 10, parent curse ≈ 15, treat ≈ T/3, souvenir ≈ T/2. Unspent coins set the
  end-of-day rank (`rules.ranks`), with steps at roughly 0, T/8, T/3, T/2 and
  2T/3 (+ all zones claimed for the top rank), so saving is as attractive as
  spending and there are never "useless" leftover coins. Hard limit: the top
  rank must be reachable when ~95 % of the guaranteed coins are earned and
  nothing is spent. Count T without challenges marked `"optional": true`
  (unbooked rides, weather-dependent extras); the build script checks this
  and warns. Maritime cities:
  Юнга → Матрос → Боцман → Капитан → Адмирал; adapt the theme to the city.
- **Campaign economy** (home city, many outings; `"campaign": true`): coins
  carry over between outings and the rank counts **all coins earned**
  (spending never lowers it), because saving for months would kill the
  perks. Plan ~25–35 coins per outing; keep the small perks (5/10/15/25),
  add a souvenir ≈ 40 and a big prize ≈ 80 for saving across outings. Rank
  steps at roughly T/7, T/3.5, T/2.2, T/1.5 and ~0.85 T (+ all zones). The
  same 95 % check applies. A city-wide `hunt` (bingo rows with coins, e.g.
  city symbols, gable stones, windmills, transport types) keeps every
  outing connected; its coins are a bonus and are not counted in the check.
- **Card length**: for text the kid reads on their own (≥ ~11pt), keep a card to
  5 challenges + boss at ≤ ~25 words each (the coin line takes one row);
  6 + boss gets too small. Fold a small task into the boss or the
  story instead (e.g. a greeting phrase into the boss). Titles 1–3 words,
  fun names ("Голуби-шпионы").

## 4. Facts, answers and research

Parents must be able to check results, and wrong "facts" ruin trust. So:

- Anything with a definite answer (heights, counts of statues, dates, what is on
  top of a tower) must come from a source you actually read; put the answer in
  `answer` and the source in `sources`.
- When you cannot verify, use self-checking challenges instead: "count the
  lions" (answer: "count together"), "guess, then check the sign".
- Check opening days/hours, closures and renovations for the trip dates, and
  seasonal things (markets, festivals, fountains off in winter). Put this in
  each zone's `logistics` and in `parent.tips`.
- For taste challenges name a concrete, kid-plausible dish and where in or near
  the zone it is sold, with a rough price.
- **Stories for the parents**: every task with a place gets `facts` — 50–100
  words in Russian: who built it, when and why, how it got its name, what it
  was used for then and now, what makes it different from similar places,
  the legend and what is really true, and one "Ребёнку: …" hook to retell.
  Each zone gets `parent_story` (2–3 sentences of background). These print on
  the parent pages, one card per zone (two for a long zone), so the parents
  can tell the story on the spot. Research them with sources like any fact;
  legends are fine when labelled as legends.

## 5. Safety and respect

- No challenges near unfenced water edges, traffic, bike lanes, or that involve
  climbing monuments.
- `talk` challenges are done with a parent next to them (shopkeepers, waiters),
  never approaching strangers alone.
- Memorials, places of worship and sites of tragedy: only quiet, respectful
  challenges (counting, noticing, a quiet "what did you feel?"). No silly
  photos or curses there.
- No purchases beyond small snacks/souvenirs (~10 € per item).

## 6. Writing in Russian

- Address the kid as «ты», the family as «мы/команда».
- Kid-facing text (cards, cover, rules): short sentences, simple words, a bit
  of playful story per zone (a legend, a funny real fact). Parent pages may
  be terse and practical.
- Foreign words: original spelling + Cyrillic transcription: «Данк у вел (Dank u wel)».
  Skip the transcription for languages the kid speaks (see the profile —
  e.g. a kid fluent in Dutch); just write the word.
- Place names: Russian form if common (Площадь Дам), otherwise local name in
  parentheses so parents can find it on Google Maps.
