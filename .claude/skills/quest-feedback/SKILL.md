---
name: quest-feedback
description: Collect the family's feedback on a city-quest zone, several zones or a whole city after they played it — each challenge and boss rated 1–5 with an optional comment, plus a word on the zone — and store it in <city>/feedback.json, where the challenge ledger and the challenge library use it to pick better challenges next time. Durable lessons go into the family profile. Use whenever the user says "feedback on zone 3", "rate Amsterdam zone 2", "we did zone 5 today", "how did Hoorn go", or comes back from a trip and talks about how a quest went.
---

# Quest feedback

The user played part of a quest and wants to say how it went. Ratings make the next quest
better: `challenge_ledger.py` averages them per challenge type and per library pattern, and
the planner uses that to choose challenges.

## 1. Find what to rate

- From the request, take the city and the zone number(s) or "all". If the city is missing
  and only one quest has zones the user could mean, assume it and say so; otherwise ask.
- Read `<city>/quest.json` (the main language) and `<city>/feedback.json` if it exists.
  A zone's items are its challenges in order (`1.1`, `1.2`…) and its boss (`1.B`), numbered
  as on the cards.
- If a zone was rated before, show the old ratings and ask whether to update them.

## 2. Ask

Show one compact list per zone, in the booklet's language for titles (as on the card),
with the type, and ask for all of it in one reply:

```
Zone 1 — Западные острова (5 + boss)
 1.1 [spot]    Сосчитай кошек на складе
 1.2 [move]    ⏱ 20 деревьев
 1.3 [taste]   Селёдка!
 1.4 [photo]   Фотоохота по островам
 1.B [measure] Самый узкий дом
Rate each 1–5 (5 = loved it), with a word on any you like, e.g.
"1.1 4, 1.2 5 he ran it twice, 1.3 2 too fishy, 1.4 -, 1.B 3 too easy".
"-" = didn't do it. Then: anything about the zone as a whole (route, length, map,
time, what he talked about afterwards)?
```

Accept any reasonable shape: "all 4 except 1.3 2", a few words per item, or a voice-note
style paragraph. Ask once more only for items you can't place. A skipped item is fine: record
`"done": false` and why if they said, which is also useful (closed, rained, no time).

## 3. Store

Write `<city>/feedback.json` (create it, or update only the zones rated now):

```json
{
  "city": "amsterdam",
  "zones": {
    "1": {
      "rated": "2026-11-14",
      "played": "2026-11-09",
      "comment": "Route a bit long; loved the islands",
      "challenges": [
        {"n": "1.1", "title": "<title exactly as in quest.json>", "type": "spot",
         "pattern": "<id if the challenge has one>", "rating": 4, "comment": "", "done": true}
      ]
    }
  }
}
```

The title is copied exactly: the ledger ignores a rating whose challenge was later replaced.
Then run `python3 .claude/skills/city-quest/scripts/challenge_ledger.py --check` and fix any
problem it reports for this file. The file is git-ignored (comments may be personal),
like the family profile.

## 4. Learn

- **Library**: for each rated challenge with a `pattern`, if it rated 1–2 with a reason that
  is about the mechanic itself (not the weather or the place), add the reason to that
  pattern's `fit_notes` in `library/patterns.json`; if a pattern rated 1–2 twice, set its
  `status` to `retired`. A 5 with a comment that says why is worth a line in `fit_notes`
  too ("kids love racing parents up the stairs").
- **Profile**: add durable lessons (a like, a dislike, too long, too easy) to the family's
  profile under "Lessons from past trips", one dated line per review, the way the existing
  lines read. The quest's `family` field says which profile: missing or `home` →
  `family-profile.md`, otherwise `profiles/<family>.md`.
- **Not the quest**: feedback is for improving future cities, not for correcting zones
  the family has already played. Don't offer to change the rated quest; turn each comment
  into a general lesson (library `fit_notes`, profile) that the next city's planning will
  use. Only touch the quest when the user asks.

## 5. Report

Show the zone's average, the best and worst item with the reason, the general lessons taken
for future cities, what was written where,
and one line on what the ledger now says about the type balance (run it without flags and
pick the line that matters).
