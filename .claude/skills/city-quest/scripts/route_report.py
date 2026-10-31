#!/usr/bin/env python3
"""Walking-route report for a quest: what each walk between stops is like.

For every walk between consecutive stops (and, on a one-day trip, from the start
point and between zones) it prints the distance and kid walking time, what the
way runs along (main roads, quiet streets, car-free paths, water, parks), and the
landmarks and points of interest passed on the way or a short detour away.
The quest reviewer reads it to judge whether the walks are spread out, pleasant
and worth walking; parents' "~4 km, 2 h" logistics can come from it too.

Usage: route_report.py <city>/quest.json [--out FILE]   (default: <city>/quest-routes.md)

Uses the renderer's OpenStreetMap street data and routing (cached in
~/.cache/city-quest/streets) plus a points-of-interest query (cached in
~/.cache/city-quest/poi).
"""
import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_quest import (OVERPASS_URLS, fetch_streets, metres, task_label, walk_graph, walk_route,  # noqa: E402
                         walking_order, zone_tasks)

POI_CACHE = Path.home() / ".cache" / "city-quest" / "poi"
KID_KMH = 3.0           # a 7-year-old's walking pace with stops to look around
NEAR = 35               # m: a point of interest this close to the way is passed
DETOUR = 120            # m: this far off the way is a short detour worth mentioning
AT_STOP = 40            # m: points this close to a stop are the stop itself
SAME, SHORT, LONG = 60, 150, 1500  # m: same spot; hardly a walk; long, needs something on the way
MAIN = {"motorway", "trunk", "primary", "secondary", "tertiary"}
QUIET = {"residential", "living_street", "unclassified", "service"}
CAR_FREE = {"pedestrian", "footway", "path", "cycleway", "steps", "track"}

# what counts as a landmark or point of interest, with a short kind label
POI_TAGS = [
    ("tourism", "attraction|museum|artwork|viewpoint|gallery|zoo|theme_park"),
    ("historic", "."),
    ("amenity", "place_of_worship|fountain|clock"),
    ("man_made", "windmill|lighthouse|watermill|crane|tower|water_tower"),
    ("leisure", "playground|park|garden|bandstand"),
    ("building", "church|cathedral|chapel|windmill"),
    ("memorial", "."),
    ("bridge:name", "."),
]


def fetch_pois(s, w, n, e):
    """Named landmarks and points of interest in a bounding box (cached), as [(lat, lon, name, kind)]."""
    key = "_".join(f"{v:.3f}" for v in (s, w, n, e))
    path = POI_CACHE / f"{key}.json"
    if not path.exists():
        bb = f"{s:.5f},{w:.5f},{n:.5f},{e:.5f}"
        parts = "".join(f'nwr["{k}"~"^({v})"]({bb});' if v != "." else f'nwr["{k}"]({bb});' for k, v in POI_TAGS)
        query = f"[out:json][timeout:90];({parts});out center tags;"
        data = urllib.parse.urlencode({"data": query}).encode()
        for attempt in range(4):
            req = urllib.request.Request(OVERPASS_URLS[attempt % len(OVERPASS_URLS)], data=data,
                                         headers={"User-Agent": "city-quest-skill/1.0 (family trip booklet)"})
            try:
                raw = urllib.request.urlopen(req, timeout=120).read()
                json.loads(raw)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    pois = []
    for el in json.loads(path.read_text())["elements"]:
        tags = el.get("tags", {})
        lat, lon = el.get("lat") or el.get("center", {}).get("lat"), el.get("lon") or el.get("center", {}).get("lon")
        if lat is None:
            continue
        kind = next((f"{k}={tags[k]}" if v != "." else k for k, v in POI_TAGS if k in tags), "")
        if kind.startswith("bridge:name"):
            kind = "bridge"
        name = tags.get("name") or tags.get("bridge:name") or ""
        if not name and not kind.startswith(("tourism=artwork", "leisure=playground", "amenity=fountain", "historic")):
            continue  # unnamed parks, churches, towers are noise; unnamed art, playgrounds and old things are not
        pois.append((lat, lon, name or f"(unnamed {kind.split('=')[-1]})", kind))
    return pois


class Surroundings:
    """Which bits of a walk run along water or through green, from the cached street data."""

    def __init__(self, elements, cell=0.0005):
        self.cell, self.water, self.green = cell, {}, {}
        for el in elements:
            tags = el.get("tags", {})
            kind = ("water" if tags.get("natural") == "water" or tags.get("waterway") == "riverbank" else
                    "green" if tags.get("leisure") in ("park", "garden") or tags.get("landuse") in ("grass", "forest", "meadow", "recreation_ground", "village_green")
                    or tags.get("natural") == "wood" else None)
            if not kind:
                continue
            lines = [el.get("geometry", [])] + [m.get("geometry", []) for m in el.get("members", [])]
            index = self.water if kind == "water" else self.green
            for line in lines:
                pts = [(p["lat"], p["lon"]) for p in line or [] if p]
                for a, b in zip(pts, pts[1:]):
                    for c in self._cells(a, b):
                        index.setdefault(c, []).append((a, b))

    def _cells(self, a, b):
        c = self.cell
        return {(int(la // c), int(lo // c)) for la in (a[0], b[0]) for lo in (a[1], b[1])}

    def near(self, pt, index, r):
        c = self.cell
        ci, cj = int(pt[0] // c), int(pt[1] // c)
        for i in (ci - 1, ci, ci + 1):
            for j in (cj - 1, cj, cj + 1):
                for a, b in index.get((i, j), ()):
                    if seg_dist(pt, a, b) <= r:
                        return True
        return False


def seg_dist(p, a, b):
    """Metres from point p to segment ab (flat-earth)."""
    k = math.cos(math.radians(p[0]))
    ax, ay, bx, by, px, py = a[1] * k, a[0], b[1] * k, b[0], p[1] * k, p[0]
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1e-18)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy) * 111320


def samples(path, step=15):
    """Points every ~step metres along a path, each with the length it stands for."""
    out = []
    for a, b in zip(path, path[1:]):
        d = metres(a, b)
        n = max(1, int(d // step))
        out += [((a[0] + (b[0] - a[0]) * (i + 0.5) / n, a[1] + (b[1] - a[1]) * (i + 0.5) / n), d / n, (a, b)) for i in range(n)]
    return out


def describe_leg(path, seg_class, surr, pois, stop_pts):
    """Share of the walk per surrounding, and points of interest passed / a short detour away."""
    pts = samples(path)
    total = sum(w for _, w, _ in pts) or 1
    share = {"main road": 0, "quiet street": 0, "car-free": 0, "along water": 0, "park/green": 0}
    for pt, w, seg in pts:
        cls = seg_class.get(seg, "")
        share["main road" if cls in MAIN else "car-free" if cls in CAR_FREE else "quiet street"] += w
        if surr.near(pt, surr.water, 30):
            share["along water"] += w
        if surr.near(pt, surr.green, 15):
            share["park/green"] += w
    passed, detour, done = [], [], set()
    for lat, lon, name, kind in pois:
        if (name, kind) in done:  # one object mapped twice (a node and an area)
            continue
        done.add((name, kind))
        if any(metres((lat, lon), s) <= AT_STOP for s in stop_pts):
            continue
        d = min((metres((lat, lon), pt) for pt, _, _ in pts), default=1e9)
        if d <= NEAR:
            passed.append((name, kind))
        elif d <= DETOUR:
            detour.append((name, kind, d))
    return {k: v / total for k, v in share.items()}, passed, detour


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quest_json")
    ap.add_argument("--out", help="report file; default: quest-routes.md next to the quest")
    a = ap.parse_args()
    src = Path(a.quest_json).resolve()
    q = json.loads(src.read_text(encoding="utf-8"))
    campaign = bool(q.get("campaign"))
    hotel = q.get("hotel") or {}

    # the walks: per zone in a campaign; the whole day from the start point otherwise
    walks = []  # (heading, [(label, task)])
    day_stops = [("start", {"title": hotel.get("name", "start"), "lat": hotel["lat"], "lon": hotel["lon"]})] if hotel.get("lat") and not campaign else []
    for zi, z in enumerate(q["zones"], 1):
        labels = {id(t): task_label(zi, ti, z).replace("👑", f"{zi}.👑") for ti, t in enumerate(zone_tasks(z), 1)}
        stops = [(labels[id(t)], t) for t in walking_order(z) if t.get("lat") is not None]
        if campaign:
            walks.append((f"Zone {zi} · {z['name']}", stops))
        else:
            day_stops += stops
    if not campaign:
        walks.append(("The day", day_stops))

    all_pts = [(t["lat"], t["lon"]) for _, st in walks for _, t in st]
    if len(all_pts) < 2:
        sys.exit("fewer than two stops with coordinates")
    out = [f"# Walking routes · {q.get('city', src.parent.name)}", "",
           f"Kid pace {KID_KMH:g} km/h. *Passed* = within {NEAR} m of the way; *detour* = {NEAR}–{DETOUR} m off it. "
           f"⚠ marks: walks of {SAME}–{SHORT} m or over {LONG} m, main roads over 30 %, more than half on streets "
           "already walked. Rides (`leg`) are not walked.", ""]
    for heading, stops in walks:
        lats, lons = [t["lat"] for _, t in stops], [t["lon"] for _, t in stops]
        if len(stops) < 2:
            continue
        m_lat, m_lon = max(0.25 * (max(lats) - min(lats)), 0.003), max(0.25 * (max(lons) - min(lons)), 0.005)
        bbox = (min(lats) - m_lat, min(lons) - m_lon, max(lats) + m_lat, max(lons) + m_lon)
        elements = fetch_streets(*bbox)
        g = walk_graph(elements)
        seg_class = {}
        for el in elements:
            hw = el.get("tags", {}).get("highway")
            geom = [(round(p["lat"], 7), round(p["lon"], 7)) for p in el.get("geometry", []) if p] if hw else []
            for x, y in zip(geom, geom[1:]):
                seg_class[(x, y)] = seg_class[(y, x)] = hw
        surr = Surroundings(elements)
        pois = fetch_pois(*bbox)
        stop_pts = [(t["lat"], t["lon"]) for _, t in stops]
        out += [f"## {heading}", ""]
        total, warn, seen, walked = 0.0, [], set(), set()
        for (la, ta), (lb, tb) in zip(stops, stops[1:]):
            title = f"**{la} → {lb}** {ta.get('title', '')} → {tb.get('title', '')}"
            if tb.get("leg"):
                out += [f"- {title}: by {tb['leg']}, not walked", ""]
                continue
            r = walk_route(g, (ta["lat"], ta["lon"]), (tb["lat"], tb["lon"]))
            if r is None:
                out += [f"- {title}: ⚠ no walking connection found", ""]
                warn.append(f"{la}→{lb} unconnected")
                continue
            path, names, d = r
            total += d
            share, passed, detour = describe_leg(path, seg_class, surr, pois, stop_pts)
            segs = {frozenset(s) for s in zip(path, path[1:])}
            again = sum(metres(*s) for s in zip(path, path[1:]) if frozenset(s) in walked) / (d or 1)
            walked |= segs
            flags = []
            if d < SAME:
                flags.append("· same spot")
            elif d < SHORT:
                flags.append("⚠ hardly a walk")
            if d > LONG:
                flags.append("⚠ long")
            if share["main road"] > 0.3:
                flags.append(f"⚠ {share['main road']:.0%} main road")
            if d > LONG and not passed:
                flags.append("⚠ nothing to see on the way")
            if again > 0.5 and d > SHORT:
                flags.append(f"⚠ {again:.0%} on streets already walked")
            warn += [f"{la}→{lb} {f[2:]}" for f in flags if f.startswith("⚠")]
            streets = ", ".join(n for n, m in sorted(names.items(), key=lambda x: -x[1]) if m >= 25)
            surround = ", ".join(f"{k} {v:.0%}" for k, v in share.items() if v >= 0.05)
            out.append(f"- {title}: {d:.0f} m, ~{d / 1000 / KID_KMH * 60:.0f} min {' '.join(flags)}")
            out.append(f"  - along: {surround or '—'}")
            if streets:
                out.append(f"  - streets: {streets}")
            fresh = [p for p in passed if p[0] not in seen]
            seen |= {p[0] for p in passed}
            out.append(f"  - passed ({len(passed)}): " + ("; ".join(f"{n} [{k}]" for n, k in fresh[:25]) or "—")
                       + (f" (+{len(passed) - len(fresh)} seen before)" if len(fresh) < len(passed) else ""))
            near = sorted(detour, key=lambda x: x[2])
            if near:
                out.append(f"  - short detour ({len(near)}): " + "; ".join(f"{n} [{k}] {dd:.0f} m" for n, k, dd in near[:12]))
            out.append("")
        out += [f"**Total walked: {total / 1000:.1f} km, ~{total / 1000 / KID_KMH * 60:.0f} min** (plus time at the stops)."
                + (f" Flags: {'; '.join(warn)}." if warn else ""), ""]
    target = Path(a.out) if a.out else src.parent / f"{src.stem.split('.')[0]}-routes.md"
    target.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"Wrote {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
