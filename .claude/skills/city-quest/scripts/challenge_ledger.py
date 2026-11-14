#!/usr/bin/env python3
"""Challenge ledger: which challenge types and library patterns the quests use, how they
were rated, and which patterns to try next.

Everything is derived, nothing is stored: it reads
  library/patterns.json      the challenge library (written by the challenge-scout agent)
  */quest.json               the quests; a challenge may carry "pattern": "<id>"; the quest
                             may carry "family": "<slug>" (missing = "home")
  */feedback.json            ratings from the quest-feedback skill

Usage (from the repository root):
  challenge_ledger.py                       report: type balance per quest, pattern use, ratings
  challenge_ledger.py --family home         only that family's quests
  challenge_ledger.py --suggest --age 7 --places stairs,church --exclude-needs drawing
                                            patterns this family hasn't used, best first
  challenge_ledger.py --check               validate the library, pattern ids and feedback
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LIB = ROOT / "library" / "patterns.json"

TYPES = ["spot", "trail", "taste", "photo", "build", "collect", "ride", "talk", "move",
         "measure", "duel", "quiz"]
CORE = ["spot", "trail", "taste", "photo", "build", "collect", "ride", "talk", "move",
        "measure", "duel"]  # types a full quest or campaign should have at least once
PLACES = set("""square street stairs bridge canal river harbour church tower statue fountain
facade gate museum museum-room market shop cafe park playground garden station tram bus boat
train windmill castle wall cemetery viewpoint beach zoo farm library any""".split())
PROOF = {"count", "photo", "word", "point", "object", "time", "parent-sees"}
MODES = {"solo", "co-op", "duel"}
ORIGINS = {"found", "invented", "own"}
STATUSES = {"new", "used", "retired"}
NEEDS_FIXED = set("""camera stopwatch staff opening-hours ticket daylight dark rain-free drawing
writing paper crayon chalk string coin cash getting-wet climbing talking-to-strangers crowd quiet
found-materials""".split())
HEAVY_SHARE = 0.30  # a type above this share of a quest is flagged


def load_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def load_patterns():
    data = load_json(LIB, {"patterns": []})
    return data.get("patterns", [])


def quests():
    """Yield (city, quest) for every main quest.json (translations are skipped)."""
    for p in sorted(ROOT.glob("*/quest.json")):
        yield p.parent.name, load_json(p)


def items(quest):
    """Yield (number, challenge) for every challenge and boss, numbered like the cards."""
    for zi, z in enumerate(quest.get("zones", []), 1):
        for ci, c in enumerate(z.get("challenges", []), 1):
            yield f"{zi}.{ci}", c
        if z.get("boss"):
            yield f"{zi}.B", z["boss"]


def feedback(city):
    """Return {number: {rating, comment, title}} for a city's feedback.json."""
    fb = load_json(ROOT / city / "feedback.json", {}) or {}
    out = {}
    for zone in fb.get("zones", {}).values():
        for r in zone.get("challenges", []):
            if r.get("rating") is not None:
                out[r["n"]] = r
    return out


def collect(family=None):
    main_type = {p["id"]: (p.get("types") or [None])[0] for p in load_patterns()}
    rows = []  # one per challenge
    for city, q in quests():
        fam = q.get("family", "home")
        if family and fam != family:
            continue
        fb = feedback(city)
        for n, c in items(q):
            r = fb.get(n)
            # a rating only counts if the title still matches (the quest may have changed)
            if r and r.get("title") and r["title"] != c.get("title"):
                r = None
            rows.append({
                "city": city, "family": fam, "n": n, "type": c.get("type") or main_type.get(c.get("pattern")),
                "duel": bool(c.get("duel")) or c.get("type") == "duel",
                "title": c.get("title", ""), "pattern": c.get("pattern"),
                "rating": r.get("rating") if r else None,
                "comment": r.get("comment") if r else None,
            })
    return rows


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x):
    return "–" if x is None else f"{x:.1f}"


def report(rows, patterns):
    if not rows:
        print("No quests found.")
        return
    by_city = defaultdict(list)
    for r in rows:
        by_city[(r["city"], r["family"])].append(r)

    print("## Challenge types per quest (challenges + bosses; ★ = average rating)\n")
    head = ["quest", "n"] + TYPES + ["duels"]
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for (city, fam), rs in by_city.items():
        cnt = Counter(r["type"] for r in rs)
        cells = [f"{city} ({fam})", str(len(rs))]
        for t in TYPES:
            k = cnt.get(t, 0)
            ratings = avg(r["rating"] for r in rs if r["type"] == t)
            cell = str(k) if k else "·"
            if k and k / len(rs) > HEAVY_SHARE:
                cell += " ⚠"
            if ratings is not None:
                cell += f" ★{ratings:.1f}"
            cells.append(cell)
        cells.append(str(sum(r["duel"] for r in rs)))
        print("| " + " | ".join(cells) + " |")
    print()
    for (city, fam), rs in by_city.items():
        cnt = Counter(r["type"] for r in rs)
        missing = [t for t in CORE if not cnt.get(t)
                   and not (t == "duel" and any(r["duel"] for r in rs))]
        heavy = [t for t in TYPES if cnt.get(t, 0) / len(rs) > HEAVY_SHARE]
        notes = []
        if missing:
            notes.append("missing " + ", ".join(missing))
        if heavy:
            notes.append(f"heavy (> {HEAVY_SHARE:.0%}) " + ", ".join(heavy))
        if notes:
            print(f"- {city}: " + "; ".join(notes))
    total = Counter(r["type"] for r in rows)
    print("\nAll quests: " + ", ".join(f"{t} {total[t]}" for t in TYPES if total[t]))

    linked = [r for r in rows if r["pattern"]]
    print(f"\n## Library patterns\n\n{len(patterns)} patterns in the library; "
          f"{len(linked)} of {len(rows)} challenges link to one.")
    use = defaultdict(list)
    for r in linked:
        use[r["pattern"]].append(r)
    if use:
        print("\n| pattern | used in | ★ |\n|---|---|---|")
        for pid, rs in sorted(use.items(), key=lambda kv: -len(kv[1])):
            where = ", ".join(f"{r['city']} {r['n']}" for r in rs)
            print(f"| {pid} | {where} | {fmt(avg(r['rating'] for r in rs))} |")
    st = Counter(p.get("status", "new") for p in patterns)
    if patterns:
        print("\nStatus: " + ", ".join(f"{k} {v}" for k, v in st.items()))

    rated = [r for r in rows if r["rating"] is not None]
    print(f"\n## Ratings\n\n{len(rated)} challenges rated.")
    if rated:
        low = sorted(rated, key=lambda r: r["rating"])[:5]
        high = sorted(rated, key=lambda r: -r["rating"])[:5]
        for label, rs in (("Lowest", low), ("Highest", high)):
            print(f"\n{label}:")
            for r in rs:
                c = f" — {r['comment']}" if r["comment"] else ""
                print(f"- {r['rating']}/5 {r['city']} {r['n']} [{r['type']}] {r['title']}{c}")


def pattern_ratings(rows):
    out = defaultdict(list)
    for r in rows:
        if r["pattern"] and r["rating"] is not None:
            out[r["pattern"]].append(r["rating"])
    return {k: avg(v) for k, v in out.items()}


def suggest(rows, patterns, a):
    used = {r["pattern"] for r in rows if r["pattern"]}
    ratings_all = pattern_ratings(collect())  # ratings from every family count as evidence
    type_count = Counter(r["type"] for r in rows)
    type_rating = {t: avg(r["rating"] for r in rows if r["type"] == t) for t in TYPES}
    total = max(len(rows), 1)
    places = set(a.places.split(",")) if a.places else None
    excl = set(a.exclude_needs.split(",")) if a.exclude_needs else set()
    types = set(a.types.split(",")) if a.types else None
    picks = []
    for p in patterns:
        if p.get("status") == "retired":
            continue
        if p["id"] in used and not a.include_used:
            continue
        lo, hi = (p.get("age") or [4, 14])[:2]
        if a.age is not None and not lo <= a.age <= hi:
            continue
        if excl & set(p.get("needs", [])):
            continue
        ptypes = p.get("types", [])
        if types and not types & set(ptypes):
            continue
        pplaces = set(p.get("places", []))
        if places and not (places & pplaces or "any" in pplaces):
            continue
        main = ptypes[0] if ptypes else None
        # scarce types first, then well-rated types and patterns, then found over invented
        score = 1 - type_count.get(main, 0) / total
        tr = type_rating.get(main)
        if tr is not None:
            score += (tr - 3) / 4
        pr = ratings_all.get(p["id"])
        if pr is not None:
            score += (pr - 3) / 2
        if p.get("origin") == "invented":
            score -= 0.1
        picks.append((score, p))
    picks.sort(key=lambda sp: -sp[0])
    print(f"{len(picks)} patterns fit; top {min(a.limit, len(picks))}:\n")
    print("| id | types | places | age | diff | needs | mechanic |\n|---|---|---|---|---|---|---|")
    for _, p in picks[:a.limit]:
        print(f"| {p['id']} | {','.join(p.get('types', []))} | {','.join(p.get('places', []))} "
              f"| {'–'.join(map(str, p.get('age', [])))} | {p.get('difficulty', '')} "
              f"| {','.join(p.get('needs', [])) or '–'} | {p.get('mechanic', '')} |")


def check(patterns):
    errs = []
    ids = Counter(p.get("id") for p in patterns)
    errs += [f"duplicate id {i}" for i, k in ids.items() if k > 1]
    for p in patterns:
        pid = p.get("id", "?")
        for f in ("id", "name", "mechanic", "types", "places", "age", "difficulty", "proof",
                  "needs", "mode", "origin", "status", "added"):
            if f not in p:
                errs.append(f"{pid}: missing {f}")
        for t in p.get("types", []):
            if t not in TYPES:
                errs.append(f"{pid}: unknown type {t}")
        for pl in p.get("places", []):
            if pl not in PLACES:
                errs.append(f"{pid}: unknown place {pl}")
        for x in p.get("proof", []):
            if x not in PROOF:
                errs.append(f"{pid}: unknown proof {x}")
        for x in p.get("mode", []):
            if x not in MODES:
                errs.append(f"{pid}: unknown mode {x}")
        for x in p.get("needs", []):
            if x not in NEEDS_FIXED and not x.startswith("season-"):
                errs.append(f"{pid}: unknown need {x}")
        age = p.get("age", [])
        if len(age) != 2 or not 4 <= age[0] <= age[1] <= 14:
            errs.append(f"{pid}: age must be [lo, hi] within 4–14")
        if p.get("difficulty") not in (1, 2, 3):
            errs.append(f"{pid}: difficulty must be 1, 2 or 3")
        if p.get("origin") not in ORIGINS:
            errs.append(f"{pid}: origin must be one of {sorted(ORIGINS)}")
        if p.get("status") not in STATUSES:
            errs.append(f"{pid}: status must be one of {sorted(STATUSES)}")
        if p.get("origin") == "found" and not p.get("sources"):
            errs.append(f"{pid}: found pattern without sources")
    known = set(ids)
    for city, q in quests():
        for n, c in items(q):
            if c.get("pattern") and c["pattern"] not in known:
                errs.append(f"{city} {n}: pattern {c['pattern']} not in the library")
        titles = {n: c.get("title") for n, c in items(q)}
        for n, r in feedback(city).items():
            if n not in titles:
                errs.append(f"{city}/feedback.json: {n} is not in the quest")
            elif r.get("title") and r["title"] != titles[n]:
                errs.append(f"{city}/feedback.json: {n} title changed since it was rated "
                            f"(rating ignored)")
            if not 1 <= r.get("rating", 0) <= 5:
                errs.append(f"{city}/feedback.json: {n} rating must be 1–5")
    used = {c.get("pattern") for _, q in quests() for _, c in items(q)}
    for p in patterns:
        if p["id"] in used and p.get("status") == "new":
            errs.append(f"{p['id']}: used in a quest, set status to 'used'")
    for e in errs:
        print("✗", e)
    print(f"{len(patterns)} patterns, {len(errs)} problems")
    return not errs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", help="only quests of this family (quest.json 'family', default 'home')")
    ap.add_argument("--suggest", action="store_true", help="list patterns to try next")
    ap.add_argument("--age", type=int, help="with --suggest: the kid's age")
    ap.add_argument("--places", help="with --suggest: comma-separated place kinds available")
    ap.add_argument("--types", help="with --suggest: only these challenge types")
    ap.add_argument("--exclude-needs", help="with --suggest: skip patterns needing any of these")
    ap.add_argument("--include-used", action="store_true", help="with --suggest: also used ones")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--check", action="store_true", help="validate library, ids and feedback")
    a = ap.parse_args()
    patterns = load_patterns()
    if a.check:
        sys.exit(0 if check(patterns) else 1)
    rows = collect(a.family)
    if a.suggest:
        suggest(rows, patterns, a)
    else:
        report(rows, patterns)


if __name__ == "__main__":
    main()
