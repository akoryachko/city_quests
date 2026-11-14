# Challenge library

Ideas for quest challenges, gathered from the web and from our own quests, kept
as **patterns**: one mechanic each, written so it can be used in any city, with the
kinds of place it fits. The `city-quest` skill picks patterns from this library, and
the `city-researcher` finds real places that fit them.

| file | what | who writes it |
|---|---|---|
| `patterns.json` | the patterns (schema below) | `challenge-scout` agent |
| `search-log.json` | search terms tried, sites seen, ideas for new terms, one entry per run | `challenge-scout` agent |
| `cities/<city>.json` | city-specific finds: a museum's own kids' trail, a church's children's tour, a city rally | `challenge-scout` agent |
| *(none)* usage and ratings | made fresh each time from `*/quest.json` (each challenge's `pattern` id) and `*/feedback.json` | `challenge_ledger.py` |

Usage is never written down by hand: run the ledger script.

```bash
S=.claude/skills/city-quest/scripts
python3 $S/challenge_ledger.py                  # type balance per city, pattern use, ratings
python3 $S/challenge_ledger.py --suggest --age 7 --places stairs,church,square --exclude-needs drawing
python3 $S/challenge_ledger.py --check          # validate patterns.json and pattern ids in quests
```

## Pattern schema

```json
{
  "id": "stairs-guess-count",
  "name": "Guess the steps",
  "mechanic": "Everyone guesses how many steps a staircase has; the kid counts them on the way up; closest guess wins.",
  "example": "Paraphrase of how a source used it (never copied text).",
  "types": ["duel", "measure"],
  "tags": ["estimation"],
  "places": ["stairs", "tower"],
  "age": [5, 12],
  "difficulty": 1,
  "minutes": 5,
  "proof": ["count"],
  "needs": [],
  "mode": ["duel"],
  "variations": ["On the way down, count only the even steps", "Eyes closed for the last 10, holding the rail"],
  "fit_notes": "Only on a staircase the kid can climb; a tower with 100+ steps is the best fit.",
  "sources": [{"url": "https://…", "title": "…", "lang": "nl", "seen": "2026-11-14"}],
  "origin": "found",
  "status": "new",
  "added": "2026-11-14"
}
```

- `types`: the quest's challenge types: spot, trail, taste, photo, build, collect, ride,
  talk, move, measure, duel, quiz. The first one is the main type.
- `tags`, free, but use these where they fit: `limitation`, `estimation`, `sequence`,
  `senses` (sound/smell/touch), `role-play`, `navigation`, `memory`, `nature`, `history`,
  `language`, `maths`, `night`, `rain-ok`, `indoor`.
- `places`, from this list so the ledger can match them: `square`, `street`, `stairs`, `bridge`,
  `canal`, `river`, `harbour`, `church`, `tower`, `statue`, `fountain`, `facade`, `gate`,
  `museum`, `museum-room`, `market`, `shop`, `cafe`, `park`, `playground`, `garden`,
  `station`, `tram`, `bus`, `boat`, `train`, `windmill`, `castle`, `wall`, `cemetery`,
  `viewpoint`, `beach`, `zoo`, `farm`, `library`, `any`.
- `age`: youngest and oldest age it suits, within 4–14. The family profile gives the kid's
  age; the planner filters by it.
- `difficulty`: 1 easy, 2 medium, 3 hard (a boss: may need a retry).
- `proof`: how a parent checks it: `count`, `photo`, `word` (read off the spot), `point`,
  `object` (a collected thing), `time` (stopwatch), `parent-sees`.
- `needs`: what it takes. Nothing is off limits in the library; the **family profile**
  decides what to skip. Use: `camera`, `stopwatch`, `staff` (someone to talk to),
  `opening-hours`, `ticket`, `season-<spring|summer|autumn|winter>`, `daylight`, `dark`,
  `rain-free`, `drawing`, `writing`, `paper`, `crayon`, `chalk`, `string`, `coin`, `cash`,
  `getting-wet`, `climbing`, `talking-to-strangers`, `crowd`, `quiet`, `found-materials`.
- `mode`: `solo` (the kid alone, a parent checks), `co-op` (the whole team), `duel`.
- `origin`: `found` (from a source), `invented` (a variation the scout made up, no source
  needed), `own` (from one of our quests).
- `status`: `new` until a quest uses it, then `used`; `retired` when feedback says it
  doesn't work (keep it, so it is not added again).
