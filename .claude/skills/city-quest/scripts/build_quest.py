#!/usr/bin/env python3
"""Render a city quest (quest.json) into quest.md, quest.html, quest.pdf and quest-map.png.

Usage:
    python3 build_quest.py path/to/quest.json [--out-dir DIR] [--name quest]

The PDF is A4 landscape; every sheet holds two A5 portrait cards (cut along the
dashed line). Card order: cover, rules, map, zone cards, collection, scorecard,
certificate, then parent pages on their own sheets. With "campaign": true the
base cards come first and every zone gets its own sheet (zone map + challenges).
Designed to print well in black and white. Zone maps are drawn from
OpenStreetMap data (Overpass API, cached in ~/.cache/city-quest/streets) with
bold street names on top; the overview map uses OpenStreetMap tiles (cached in
~/.cache/city-quest/tiles). Both need internet on the first build.

Text that does not fit a card is shrunk; if it still does not fit, the card is
reported as overflowing (exit code 2).
"""
import argparse
import base64
import heapq
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

TYPES = {
    "spot": ("🔍", "Найди и посчитай"),
    "trail": ("🧭", "Тропа"),
    "taste": ("🍽️", "Попробуй"),
    "photo": ("📸", "Фото-задание"),
    "build": ("🧱", "Построй"),
    "collect": ("🎒", "Собери"),
    "ride": ("🚋", "Поездка"),
    "talk": ("🗣️", "Скажи по-местному"),
    "move": ("🏃", "Движение"),
    "duel": ("⚔️", "Дуэль"),
    "quiz": ("❓", "Угадай"),
    "measure": ("📏", "Измерь и посчитай"),
}

LABELS = {
    "zone": "Зона",
    "day": "День",
    "claimed": "ЗАХВАЧЕНО",
    "sticker": "наклейка",
    "boss": "Босс зоны",
    "coins_needed": "Нужно монет",
    "rules": "Как играть",
    "map": "Карта завоевания",
    "map_hint": "Зона захвачена — раскрась её или наклей на неё наклейку!",
    "collection": "Моя коллекция",
    "collection_hint": "Собирай штампы, наклейки, билетики и сокровища из каждой зоны.",
    "treasure": "Сокровище",
    "scorecard": "Счёт",
    "zone_col": "Зона",
    "coins_col": "Монеты",
    "boss_col": "Босс",
    "claimed_col": "Захвачена",
    "duels": "Дуэли",
    "kid": "Я",
    "parents": "Родители",
    "total": "Всего монет",
    "spent": "Потрачено монет",
    "certificate": "Сертификат",
    "certificate_title": "Покоритель города",
    "certificate_text": "Настоящим подтверждается, что этот отважный путешественник",
    "certificate_text2": "захвачено зон:",
    "medal": "медаль",
    "date": "Дата",
    "signature": "Подпись",
    "team": "Команда",
    "parent_pages": "Для родителей",
    "answers": "Ответы и подсказки",
    "parent_zone": "для родителей",
    "measures": "Мои мерки (измерь дома рулеткой):",
    "plan": "План",
    "curses": "Проклятия города",
    "perks": "Что купить за монеты",
    "hotel": "Старт",
    "shopping": "Взять с собой / купить",
    "notes": "Заметки",
    "bookings": "Билеты и бронирование",
    "b_when": "Когда",
    "b_where": "Где",
    "b_how": "Как",
    "b_cost": "Цена",
    "ranks": "Звание в конце дня",
    "ranks_hint": "Сколько монет осталось в конце дня — такое и звание:",
    "rank_line": "Моё звание",
    "sources": "Источники",
    "map_link": "карта",
}

# Wording for a girl (`players.gender`: "f"); the defaults above are masculine or neutral.
LABELS_F = {
    "certificate_title": "Покорительница города",
    "certificate_text": "Настоящим подтверждается, что эта отважная путешественница",
}

# Built-in labels for an English quest (`"language": "en"`); the quest's own `labels` still win.
LABELS_EN = {
    "zone": "Zone", "day": "Day", "claimed": "CLAIMED", "sticker": "sticker", "boss": "Zone boss",
    "coins_needed": "Coins needed", "rules": "How to play", "map": "Conquest map",
    "map_hint": "Zone claimed: colour it in or put a sticker on it!", "collection": "My collection",
    "collection_hint": "Collect stamps, stickers, tickets and treasures from every zone.",
    "treasure": "Treasure", "scorecard": "Score", "zone_col": "Zone", "coins_col": "Coins", "boss_col": "Boss",
    "claimed_col": "Claimed", "duels": "Duels", "kid": "Me", "parents": "Parents", "total": "Total coins",
    "spent": "Coins spent", "certificate": "Certificate", "certificate_title": "Conqueror of",
    "certificate_text": "This certifies that this brave traveller", "certificate_text2": "zones claimed:",
    "medal": "medal", "date": "Date", "signature": "Signature", "team": "Team", "parent_pages": "For parents",
    "answers": "Answers and hints", "parent_zone": "for parents", "measures": "My measures (measure at home with a tape):",
    "plan": "Plan", "curses": "City curses", "perks": "What coins buy", "hotel": "Start",
    "shopping": "Bring / buy", "notes": "Notes", "bookings": "Tickets and bookings", "b_when": "When",
    "b_where": "Where", "b_how": "How", "b_cost": "Price", "ranks": "End-of-day rank",
    "ranks_hint": "The coins left at the end of the day give your rank:", "rank_line": "My rank",
    "sources": "Sources", "map_link": "map",
}
TYPE_NAMES_EN = {
    "spot": "Find and count", "trail": "Trail", "taste": "Taste", "photo": "Photo task", "build": "Build",
    "collect": "Collect", "ride": "Ride", "talk": "Speak like a local", "move": "Move", "duel": "Duel",
    "quiz": "Guess", "measure": "Measure and count",
}

TILE_URL = os.environ.get("CITY_QUEST_TILES", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
TILE_CACHE = Path.home() / ".cache" / "city-quest" / "tiles"
ATTRIBUTION = "© OpenStreetMap contributors"
MAP_W, MAP_H = 450, 580  # CSS px, fits the inside of an A5 card


def esc(s):
    return html.escape(str(s or ""))


def is_duel(t):
    return bool(t.get("duel")) or t.get("type") == "duel"


def coins_text(t, default=1):
    """A task's coins; a duel's `coins` are paid for playing and a win adds one more."""
    n = int(t.get("coins", default))
    return f"🪙×{n}+1" if is_duel(t) else f"🪙×{n}"


def coins_html(n):
    return f'<span class="coins">🪙×{int(n)}</span>' if n else ""


def task_coins_html(t, default=1):
    return f'<span class="coins">{coins_text(t, default)}</span>'


def gmaps(lat, lon):
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


def zone_tasks(z):
    """Challenges plus the boss, each with its stop label (e.g. '2.3')."""
    return list(z.get("challenges", [])) + ([z["boss"]] if z.get("boss") else [])


def walking_order(z):
    """Tasks in the order they are visited; a task's optional "order" overrides its list position."""
    tasks = zone_tasks(z)
    return sorted(tasks, key=lambda t: t.get("order", tasks.index(t) + 1))


def task_label(zi, ti, z):
    return "👑" if z.get("boss") and ti == len(zone_tasks(z)) else f"{zi}.{ti}"


# ---------------------------------------------------------------- map


def merc(lat, lon, z):
    n = 256 * 2 ** z
    lat_r = math.radians(lat)
    return (lon + 180) / 360 * n, (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n


def fetch_tile(z, x, y):
    path = TILE_CACHE / str(z) / str(x) / f"{y}.png"
    if not path.exists():
        url = TILE_URL.format(z=z, x=x, y=y)
        req = urllib.request.Request(url, headers={"User-Agent": "city-quest-skill/1.0 (family trip booklet)"})
        data = urllib.request.urlopen(req, timeout=20).read()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return path.read_bytes()


def map_points(sel):
    """Zones without stops (placed by their own lat/lon) and all stops of the selected (zi, zone) pairs."""
    zones, stops = [], []
    for zi, z in sel:
        if z.get("lat") is not None:
            zones.append((zi, z))
        for ti, t in enumerate(zone_tasks(z), 1):
            if t.get("lat") is not None:
                stops.append((task_label(zi, ti, z), zi, t))
    return zones, stops


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for pt in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], pt) <= 0:
            lower.pop()
        lower.append(pt)
    for pt in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], pt) <= 0:
            upper.pop()
        upper.append(pt)
    return lower[:-1] + upper[:-1]


def spread(points, min_d, rounds=40, fixed=()):
    """Nudge points (lists [x, y]) apart in place until no two are closer than min_d.

    Points in `fixed` (e.g. the start marker) do not move but push others away.
    """
    for _ in range(rounds):
        moved = False
        for a in points:
            for f in fixed:
                dx, dy = a[0] - f[0], a[1] - f[1]
                d = math.hypot(dx, dy)
                if d < min_d + 4:
                    if d < 1e-6:
                        dx, dy, d = 0.0, 1.0, 1.0
                    a[0] += dx / d * (min_d + 4 - d); a[1] += dy / d * (min_d + 4 - d)
                    moved = True
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                a, b = points[i], points[j]
                dx, dy = b[0] - a[0], b[1] - a[1]
                d = math.hypot(dx, dy)
                if d < min_d:
                    if d < 1e-6:
                        dx, dy, d = 1.0, 0.0, 1.0
                    push = (min_d - d) / 2
                    a[0] -= dx / d * push; a[1] -= dy / d * push
                    b[0] += dx / d * push; b[1] += dy / d * push
                    moved = True
        if not moved:
            break


def place_label(text, zstops, obstacles, W, H):
    """Pick a spot around a zone's stops where its label covers the fewest stops."""
    half = 4 * len(text)  # rough half-width of a 13px bold label
    xs, ys = [x for x, _ in zstops], [y for _, y in zstops]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    candidates = [(cx, min(ys) - 30), (cx, max(ys) + 40), (min(xs) - half - 22, cy + 5),
                  (max(xs) + half + 22, cy + 5), (cx, cy + 5)]
    best = None
    for k, (x, y) in enumerate(candidates):
        x = min(max(x, half + 6), W - half - 6)
        y = min(max(y, 16), H - 8)
        hits = sum(1 for ox, oy in obstacles if abs(ox - x) < half + 12 and -24 < oy - y < 16)
        score = hits * 10 + k  # prefer earlier candidates when equally clear
        if best is None or score < best[0]:
            best = (score, x, y)
    return best[1], best[2]


OVERPASS_URLS = os.environ.get("CITY_QUEST_OVERPASS", "https://overpass-api.de/api/interpreter https://overpass.kumi.systems/api/interpreter").split()
STREET_CACHE = Path.home() / ".cache" / "city-quest" / "streets"
# road classes: (casing width px, label priority; lower is labelled first)
ROADS = {
    "motorway": (8, 0), "trunk": (8, 0), "primary": (7, 0), "secondary": (6.5, 1), "tertiary": (6, 1),
    "unclassified": (5, 2), "residential": (5, 2), "living_street": (5, 2), "pedestrian": (5, 2),
    "service": (3, 3), "footway": (2, 4), "cycleway": (2, 4), "path": (2, 4), "steps": (2, 4), "track": (2, 4),
}
STREET_FONT = 11  # px; the zone map is printed at ~0.27 mm per px


def fetch_streets(s, w, n, e):
    """OpenStreetMap streets, water, green areas, buildings and rails in a bounding box (cached)."""
    key = "_".join(f"{v:.3f}" for v in (s, w, n, e))
    path = STREET_CACHE / f"{key}.json"
    if not path.exists():
        bb = f"{s:.5f},{w:.5f},{n:.5f},{e:.5f}"
        query = f"""[out:json][timeout:90];(
          way["highway"~"^({'|'.join(ROADS)})$"]({bb});
          way["natural"="water"]({bb}); relation["natural"="water"]({bb});
          way["waterway"="riverbank"]({bb});
          way["leisure"~"^(park|garden|playground|pitch)$"]({bb}); relation["leisure"="park"]({bb});
          way["landuse"~"^(grass|forest|meadow|recreation_ground|village_green|farmland)$"]({bb});
          relation["landuse"~"^(forest|grass)$"]({bb}); way["natural"="wood"]({bb}); relation["natural"="wood"]({bb});
          way["building"]({bb});
          way["railway"~"^(rail|tram|light_rail)$"]({bb});
        );out geom;"""
        data = urllib.parse.urlencode({"data": query}).encode()
        for attempt in range(4):  # public Overpass servers are often busy: retry, alternating servers
            url = OVERPASS_URLS[attempt % len(OVERPASS_URLS)]
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "city-quest-skill/1.0 (family trip booklet)"})
            try:
                raw = urllib.request.urlopen(req, timeout=120).read()
                json.loads(raw)  # don't cache an error page
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return json.loads(path.read_text())["elements"]


def metres(a, b):
    """Distance between two (lat, lon) points; flat-earth is fine inside a city."""
    dy = (a[0] - b[0]) * 111320
    dx = (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def walk_graph(elements):
    """Walkable street graph {(lat, lon): [(node, metres, street name)]}, without small disconnected bits.

    Overpass "out geom" has no node ids, but ways meet at identical coordinates. Every big
    connected part is kept: banks joined only by a ferry are separate parts of one map.
    """
    g = {}
    for el in elements:
        tags = el.get("tags", {})
        if tags.get("highway") not in ROADS or tags["highway"] in ("motorway", "trunk") or tags.get("foot") == "no":
            continue
        if tags.get("access") in ("private", "no") and tags.get("foot") not in ("yes", "designated"):
            continue
        geom = [(round(n["lat"], 7), round(n["lon"], 7)) for n in el.get("geometry", []) if n]
        for a, b in zip(geom, geom[1:]):
            d = metres(a, b)
            g.setdefault(a, []).append((b, d, tags.get("name", "")))
            g.setdefault(b, []).append((a, d, tags.get("name", "")))
    parts, seen = [], set()
    for start in g:
        if start in seen:
            continue
        part, todo = {start}, [start]
        while todo:
            for m, _, _ in g[todo.pop()]:
                if m not in part:
                    part.add(m)
                    todo.append(m)
        seen |= part
        parts.append(part)
    biggest = max((len(p) for p in parts), default=0)
    keep = set().union(*(p for p in parts if len(p) >= max(50, 0.05 * biggest)), set())
    return {n: e for n, e in g.items() if n in keep}


def walk_route(g, a, b, snap=150):
    """Shortest walk between two (lat, lon) points over the street graph: (points, {name: metres}, metres) or None."""
    if not g:
        return None
    na, nb = (min(g, key=lambda n: metres(n, x)) for x in (a, b))
    if metres(na, a) > snap or metres(nb, b) > snap:
        return None
    dist, prev, todo = {na: 0.0}, {}, [(metres(na, nb), 0.0, na)]
    while todo:
        _, d, n = heapq.heappop(todo)
        if n == nb:
            break
        if d > dist[n]:
            continue
        for m, w, name in g[n]:
            if d + w < dist.get(m, float("inf")):
                dist[m], prev[m] = d + w, (n, w, name)
                heapq.heappush(todo, (d + w + metres(m, nb), d + w, m))
    if nb not in dist:
        return None
    path, names, n = [nb], {}, nb
    while n != na:
        n, w, name = prev[n]
        path.append(n)
        if name:
            names[name] = names.get(name, 0) + w
    return path[::-1], names, dist[nb]


def join_chains(lines):
    """Join polylines (lists of points) that share end points into longer ones."""
    chains = [list(l) for l in lines if len(l) > 1]
    merged = True
    while merged:
        merged = False
        for i in range(len(chains)):
            for j in range(len(chains)):
                if i == j or not chains[i] or not chains[j]:
                    continue
                a, b = chains[i], chains[j]
                if a[-1] == b[0]:
                    a += b[1:]
                elif a[-1] == b[-1]:
                    a += b[-2::-1]
                elif a[0] == b[-1]:
                    chains[i] = b + a[1:]
                elif a[0] == b[0]:
                    chains[i] = b[::-1] + a[1:]
                else:
                    continue
                chains[j] = []
                merged = True
    return [c for c in chains if c]


def street_layers(elements, p, W, H, obstacles, uid, route_names=()):
    """SVG for the map below the zone areas (land, water, roads) and the street names on top.

    `obstacles` are (x, y, r) circles that street names keep clear of (stops, zone labels).
    Streets in `route_names` (the walk between the stops) are labelled first, so the kid
    can read every street of the way.
    """
    def pts(geom):
        return [p(g["lat"], g["lon"]) for g in geom if g]

    def d(poly, close=False):
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in poly) + ("Z" if close else "")

    water, green, buildings, roads, rails = [], [], [], {}, []
    names = {}
    for el in elements:
        tags = el.get("tags", {})
        if el["type"] == "relation":
            rings = join_chains([pts(m.get("geometry", [])) for m in el.get("members", []) if m.get("geometry")])
            path = "".join(d(r, True) for r in rings)
        elif "geometry" in el:
            poly = pts(el["geometry"])
            path = d(poly, poly[0] == poly[-1])
        else:
            continue
        if tags.get("highway") in ROADS:
            roads.setdefault(tags["highway"], []).append(path)
            if tags.get("name"):
                prio = -1 if tags["name"] in route_names else ROADS.get(tags["highway"], (0, 5))[1]
                names.setdefault(tags["name"], (prio, []))[1].append(poly)
        elif "building" in tags:
            buildings.append(path)
        elif "railway" in tags:
            rails.append(path)
        elif tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
            water.append(path)
        else:
            green.append(path)
    base = [f'<rect class="land" width="{W}" height="{H}"/>',
            f'<path class="green" d="{"".join(green)}"/>', f'<path class="water" d="{"".join(water)}"/>',
            f'<path class="bldg" d="{"".join(buildings)}"/>']
    order = sorted(roads, key=lambda h: -ROADS.get(h, (1, 5))[0])
    base += [f'<path class="casing" style="stroke-width:{ROADS[h][0] + 1.6}" d="{"".join(roads[h])}"/>' for h in order if ROADS[h][0] >= 3]
    base += [f'<path class="road" style="stroke-width:{ROADS[h][0]}" d="{"".join(roads[h])}"/>' for h in order if ROADS[h][0] >= 3]
    base += [f'<path class="foot" d="{"".join(roads[h])}"/>' for h in order if ROADS[h][0] < 3]
    base.append(f'<path class="rail" d="{"".join(rails)}"/>')

    # street names: one per street (two on long ones), on a straight stretch, clear of stops and other names
    cell, grid = 16, {}

    def free(circles):
        for x, y, r in circles:
            for gx in range(int((x - r - 14) // cell), int((x + r + 14) // cell) + 1):
                for gy in range(int((y - r - 14) // cell), int((y + r + 14) // cell) + 1):
                    if any(math.hypot(x - ox, y - oy) < r + orr for ox, oy, orr in grid.get((gx, gy), [])):
                        return False
        return True

    def occupy(circles):
        for c in circles:
            grid.setdefault((int(c[0] // cell), int(c[1] // cell)), []).append(c)

    occupy(obstacles)
    defs, texts = [], []
    # route streets that found no room get a second try in a smaller font with looser rules
    named = set()
    queue = [(name, prio, polys, STREET_FONT, 0.92) for name, (prio, polys) in
             sorted(names.items(), key=lambda kv: (kv[1][0], -len(kv[0])))]
    for name, prio, polys, font, straight in queue:
        L = len(name) * font * 0.6 + 6
        placed = []
        for chain in sorted(join_chains(polys), key=lambda c: -sum(math.dist(a, b) for a, b in zip(c, c[1:]))):
            cum = [0.0]
            for a, b in zip(chain, chain[1:]):
                cum.append(cum[-1] + math.dist(a, b))
            total = cum[-1]
            if font < STREET_FONT and prio < 0 and total > 0.3 * L:
                # second try: let the name run past the ends of a short block (a canal side between bridges)
                def ext(p0, p1):
                    d = math.dist(p0, p1) or 1
                    return (p1[0] + (p1[0] - p0[0]) / d * 0.6 * L, p1[1] + (p1[1] - p0[1]) / d * 0.6 * L)
                chain = [ext(chain[1], chain[0])] + chain + [ext(chain[-2], chain[-1])]
                cum = [0.0]
                for a, b in zip(chain, chain[1:]):
                    cum.append(cum[-1] + math.dist(a, b))
                total = cum[-1]
            if total < L:
                continue
            starts = sorted(range(0, int(total - L) + 1, 10), key=lambda s0: abs(s0 + L / 2 - total / 2))
            for s0 in starts:
                def at(dist):
                    k = max(i for i in range(len(cum)) if cum[i] <= dist)
                    if k == len(chain) - 1:
                        return chain[-1]
                    t = (dist - cum[k]) / max(cum[k + 1] - cum[k], 1e-9)
                    return (chain[k][0] + t * (chain[k + 1][0] - chain[k][0]), chain[k][1] + t * (chain[k + 1][1] - chain[k][1]))
                a, b = at(s0), at(s0 + L)
                if math.dist(a, b) < straight * L:  # too curvy for a straight label
                    continue
                if any(math.dist(m, c) < 260 for m in placed for c in (a, b)):
                    break
                samples = [at(s0 + L * i / 8) for i in range(9)]
                if not all(6 < x < W - 6 and 8 < y < H - 8 for x, y in samples):
                    continue
                circles = [(x, y, font * 0.55) for x, y in samples]
                if not free(circles):
                    continue
                occupy(circles)
                if b[0] < a[0]:  # keep the text upright
                    a, b = b, a
                pid = f"{uid}s{len(defs)}"
                defs.append(f'<path id="{pid}" d="M{a[0]:.1f},{a[1]:.1f}L{b[0]:.1f},{b[1]:.1f}"/>')
                texts.append(f'<text class="sname" style="font-size:{font}px" dy="{font * 0.35:.1f}"><textPath href="#{pid}" startOffset="50%">{esc(name)}</textPath></text>')
                placed.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
                break
            if len(placed) >= 2 or (placed and total < 3 * L):
                break
        if not placed and font == STREET_FONT:
            queue.append((name, prio, polys, STREET_FONT - 2, 0.8))
        elif placed:
            named.add(name)
    missing = sorted(set(route_names) & set(names) - named)
    labels = f'<svg class="snames" viewBox="0 0 {W} {H}" width="{W}" height="{H}"><defs>{"".join(defs)}</defs>{"".join(texts)}</svg>'
    return "".join(base), labels, missing


def route_legs(sel, stops):
    """Walking paths between consecutive stops of each zone: ({id(task): [(lat, lon)…] or None}, street names).

    A task with "leg" (e.g. "ferry", "tram") is reached by transport: its leg stays a straight line.
    A walk that finds no street connection in the area is reported, so a map never asks the kid
    to navigate where the streets are not drawn.
    """
    lats, lons = [t["lat"] for _, _, t in stops], [t["lon"] for _, _, t in stops]
    if len(stops) < 2:
        return {}, set()
    m_lat = max(0.25 * (max(lats) - min(lats)), 0.003)
    m_lon = max(0.25 * (max(lons) - min(lons)), 0.005)
    try:
        g = walk_graph(fetch_streets(min(lats) - m_lat, min(lons) - m_lon, max(lats) + m_lat, max(lons) + m_lon))
    except Exception as e:
        print(f"WARNING: no street data for routing ({e}); the route is drawn as straight lines")
        return {}, set()
    with_stop = {id(t) for _, _, t in stops}
    legs, names = {}, set()
    for zi, z in sel:
        ztasks = [t for t in walking_order(z) if id(t) in with_stop]
        total = 0.0
        for a, b in zip(ztasks, ztasks[1:]):
            if b.get("leg"):
                legs[id(b)] = None
                continue
            r = walk_route(g, (a["lat"], a["lon"]), (b["lat"], b["lon"]))
            if r is None:
                print(f"WARNING: zone {zi}: no walking connection from «{a.get('title')}» to «{b.get('title')}» on the map; "
                      'check the coordinates, or mark the leg "leg": "ferry"/"tram"')
                legs[id(b)] = None
                continue
            path, leg_names, d = r
            legs[id(b)] = path
            names |= {n for n, m in leg_names.items() if m >= 25}
            total += d
            if d > 3 * metres((a["lat"], a["lon"]), (b["lat"], b["lon"])) + 200:
                print(f"NOTE: zone {zi}: the walk to «{b.get('title')}» is a {d:.0f} m detour; check the map")
        if total:
            print(f"Zone {zi}: {total / 1000:.1f} km on foot between the stops")
    return legs, names


def build_map(q, W=MAP_W, H=MAP_H, only=None, overview=False, shrink=1.0, _legs=None, pins=None):
    """Return HTML for a tile map with zone areas, numbered stops and the route.

    The view is fitted to the stops (not the start point) with a fractional zoom,
    so the walk fills the card; a start point outside the view is pinned to the edge.
    `only` limits the map to some zone numbers (a campaign's per-zone map).
    `overview` draws just the zone areas with numbered badges (a campaign's city map).
    `pins`, a dict, receives the map size and where each stop (or zone badge) is drawn,
    so a web page can put links on the map picture.
    In a campaign the route starts at the zone's first stop, not at the home point.
    """
    sel = [(zi, z) for zi, z in enumerate(q["zones"], 1) if only is None or zi in only]
    zones, stops = map_points(sel)
    if overview:  # optional extras can lie far outside a zone (e.g. a ride's departure point)
        stops = [s for s in stops if not s[2].get("optional")]
    hotel = q.get("hotel") or {}
    campaign = bool(q.get("campaign"))
    with_stops = {zi for _, zi, _ in stops}
    pts = [(z["lat"], z["lon"]) for zi, z in zones if zi not in with_stops] + [(t["lat"], t["lon"]) for _, _, t in stops]
    if hotel.get("lat") is not None and (len(pts) < 2 or overview):
        pts.append((hotel["lat"], hotel["lon"]))
    if len(pts) < 2:
        return ""
    # the walk between stops follows the streets, so every street of the way is on the map and named
    legs, route_names = {}, set()
    if not overview:
        legs, route_names = _legs or route_legs(sel, stops)
        pts += [pt for path in legs.values() if path for pt in path]
    pad = 50 if not overview else 30
    n_legend = len(sel) if overview else len(stops)
    H = min(H, 630 - 18 * math.ceil(n_legend / 2))  # leave room for the two-column legend
    xy = [merc(la, lo, 18) for la, lo in pts]
    xs, ys = [c[0] for c in xy], [c[1] for c in xy]
    k = min((W - 2 * pad) / max(max(xs) - min(xs), 1), (H - 2 * pad) / max(max(ys) - min(ys), 1), 1.5) * shrink
    zoom_f = 18 + math.log2(k)
    zoom = min(18, math.floor(zoom_f))
    scale = 2 ** (zoom_f - zoom)  # tiles are drawn at 256*scale px
    T = 256 * scale
    # shrink the map's height to the walk's shape; the card uses the rest for the stop list
    H = int(min(H, max(320, (max(ys) - min(ys)) * k + 2 * pad)))
    cx = (max(xs) + min(xs)) / 2 * k
    cy = (max(ys) + min(ys)) / 2 * k
    x0, y0 = cx - W / 2, cy - H / 2

    def p(lat, lon):
        x, y = merc(lat, lon, zoom)
        return x * scale - x0, y * scale - y0

    # zone maps are drawn from OpenStreetMap data so the street names can sit on top of everything,
    # big and black, for the kid to navigate by; the city overview uses map tiles
    streets = None
    if not overview:
        def unp(x, y):
            n = 256 * 2 ** zoom
            X, Y = (x + x0) / scale / n, (y + y0) / scale / n
            return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * Y)))), X * 360 - 180
        (n_, w_), (s_, e_) = unp(-20, -20), unp(W + 20, H + 20)
        try:
            streets = fetch_streets(s_, w_, n_, e_)
        except Exception as e:
            print(f"WARNING: street data unavailable ({e}); using map tiles")
    tiles = []
    try:
        for tx in range(int(x0 // T), int((x0 + W) // T) + 1) if streets is None else ():
            for ty in range(int(y0 // T), int((y0 + H) // T) + 1):
                b64 = base64.b64encode(fetch_tile(zoom, tx, ty)).decode()
                tiles.append(
                    f'<img src="data:image/png;base64,{b64}" style="left:{tx*T-x0:.1f}px;top:{ty*T-y0:.1f}px;width:{T+0.5:.1f}px;height:{T+0.5:.1f}px">'
                )
    except Exception as e:  # offline: fall back to a plain background
        print(f"WARNING: map tiles unavailable ({e}); drawing the map without streets")
        tiles = []

    hotel_xy = None
    if hotel.get("lat") is not None:
        hx, hy = p(hotel["lat"], hotel["lon"])
        hotel_xy = (min(max(hx, 16), W - 16), min(max(hy, 20), H - 16))

    # stop positions, pushed apart where real places are too close to tell apart
    pos = {id(t): list(p(t["lat"], t["lon"])) for _, _, t in stops}
    if not overview:
        spread(list(pos.values()), 25, fixed=[hotel_xy] if hotel_xy else [])

    svg = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">']
    route = [hotel_xy] if hotel_xy and not campaign else []
    areas, hulls = [], []
    small = " small" if overview else ""
    for zi, z in sel:
        zstops = [tuple(pos[id(t)]) for t in walking_order(z) if id(t) in pos]
        if not zstops and z.get("lat") is not None:
            zstops = [p(z["lat"], z["lon"])]
        if not zstops:
            continue
        route += zstops
        hulls.append((zi, z, zstops))
        if overview:
            # zones joined by rides would make long hulls across the city: draw a blob per stop instead
            blobs = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7"/>' for x, y in zstops)
            areas.append(f'<g class="zgroup"><g class="zarea-edge small">{blobs}</g><g class="zarea small">{blobs}</g></g>')
            continue
        # zone area: the stops' convex hull, padded by a fat round stroke; the kid colours it in
        pts_s = " ".join(f"{x:.1f},{y:.1f}" for x, y in convex_hull(zstops))
        areas.append(f'<g class="zgroup"><polygon class="zarea-edge" points="{pts_s}"/><polygon class="zarea" points="{pts_s}"/></g>')
    svg += areas
    svg.append("</svg>")
    under, svg = svg, [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">']
    if overview:
        # one numbered badge per zone at its centre, nudged apart where zones are close
        # badge on the stop nearest the zone's centre, so it sits on the zone even when stops are spread out
        badges = []
        for _, _, zs in hulls:
            mx, my = sum(x for x, _ in zs) / len(zs), sum(y for _, y in zs) / len(zs)
            badges.append(list(min(zs, key=lambda c: (c[0] - mx) ** 2 + (c[1] - my) ** 2)))
        spread(badges, 26, fixed=[hotel_xy] if hotel_xy else [])
        for (zi, z, zs), (x, y) in zip(hulls, badges):
            for bx, by in zs:  # far-flung parts of a zone get a small number of their own
                if math.hypot(bx - x, by - y) > 30:
                    svg.append(f'<text class="blobnum" x="{bx:.1f}" y="{by+3.5:.1f}">{zi}</text>')
            if pins is not None:
                pins.setdefault("pins", []).append({"zone": zi, "x": round(x, 1), "y": round(y, 1)})
            svg.append(f'<circle class="badge" cx="{x:.1f}" cy="{y:.1f}" r="12"/>')
            svg.append(f'<text class="badgenum" x="{x:.1f}" y="{y+4.5:.1f}">{zi}</text>')
    else:
        if len(route) > 1:
            svg.append('<polyline class="route" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in route) + '"/>')
        for label, zi, t in stops:
            x, y = pos[id(t)]
            if pins is not None:
                pins.setdefault("pins", []).append({"label": label, "x": round(x, 1), "y": round(y, 1), "lat": t["lat"], "lon": t["lon"]})
            svg.append(f'<circle class="stop" cx="{x:.1f}" cy="{y:.1f}" r="11"/>')
            svg.append(f'<text class="stopnum" x="{x:.1f}" y="{y+3.5:.1f}">{esc(label)}</text>')
    zlabels = []
    if not overview and len(hulls) > 1:
        obstacles = [tuple(v) for v in pos.values()] + ([hotel_xy] if hotel_xy else [])
        for zi, z, zstops in hulls:
            text = f"{zi}. {z['name']}"
            x, y = place_label(text, zstops, obstacles, W, H)
            obstacles += [(x + dx, y - 5) for dx in range(-len(text) * 4, len(text) * 4 + 1, 12)]
            svg.append(f'<text class="zlabel" x="{x:.1f}" y="{y:.1f}">{esc(text)}</text>')
            zlabels += [(x + dx, y - 5, 10) for dx in range(-len(text) * 4, len(text) * 4 + 1, 10)]
    labels = ""
    if streets is not None:  # street names last, around the stops and zone labels
        keep = [(x, y, 12) for x, y in pos.values()] + ([(*hotel_xy, 15)] if hotel_xy else []) + zlabels
        base, labels, missing = street_layers(streets, p, W, H, keep, "m" + "-".join(str(zi) for zi, _ in sel), route_names)
        # the kid must be able to read every street between the stops: zoom out until they fit (twice at most)
        missing = [n for n in missing if not re.search(r"(brug|plein|tuin|plantsoen)$", n)]
        if len(missing) > 1 and shrink > 0.75:
            if pins is not None:
                pins.clear()
            return build_map(q, W, MAP_H, only, overview, shrink * 0.85, (legs, route_names), pins)
        if missing:
            print(f"NOTE: zone map {', '.join(str(zi) for zi, _ in sel)}: no room to name {', '.join(missing)}")
        under.insert(1, base)
    if hotel_xy:
        svg.append(f'<circle class="hotel-bg" cx="{hotel_xy[0]:.1f}" cy="{hotel_xy[1]:.1f}" r="14"/>')
        svg.append(f'<text class="hotel" x="{hotel_xy[0]:.1f}" y="{hotel_xy[1]+7:.1f}">{esc(hotel.get("emoji", "🏨"))}</text>')
    svg.append("</svg>")
    attr = f'<div class="attr">{ATTRIBUTION}</div>' if tiles or streets is not None else ""
    layers = "".join(tiles) + "".join(under) + labels + "".join(svg)
    if pins is not None:
        pins.update(w=W, h=H)
    return f'<div class="map" style="width:{W}px;height:{H}px">{layers}{attr}</div>'


# ---------------------------------------------------------------- cards


def card(inner, cls="", color=None):
    style = f' style="--c:{esc(color)}"' if color else ""
    return f'<section class="card {cls}"{style}><div class="fit">{inner}</div></section>'


def cover_card(q):
    c = q.get("cover", {})
    players = q.get("players", {})
    team = esc(players.get("team_name", "")) or '<span class="blank"></span>'
    return card(
        f"""
        <div class="cover-emoji">{esc(c.get('emoji', '🏰'))}</div>
        <h1>{esc(q.get('title', q['city']))}</h1>
        <p class="subtitle">{esc(c.get('subtitle', ''))}</p>
        <p class="dates">{esc(q.get('dates', ''))}</p>
        <div class="story">{esc(c.get('story', ''))}</div>
        <div class="team">{LABELS['team']}: {team}</div>
        """,
        "cover",
        c.get("color", "#333"),
    )


def rules_card(q):
    r = q.get("rules", {})
    steps = "".join(f"<li>{esc(s)}</li>" for s in r.get("steps", []))
    legend = "".join(f'<span class="leg">{i} {esc(l)}</span>' for i, l in TYPES.values())
    perks = "".join(f"<li>{coins_html(p.get('cost'))} {esc(p.get('text'))}</li>" for p in r.get("perks", []))
    curses = "".join(f"<li>{esc(c)}</li>" for c in r.get("curses", []))
    return card(
        f"""
        <h2>📜 {LABELS['rules']}</h2>
        <ol class="steps">{steps}</ol>
        <div class="legend">{legend}</div>
        <h3>🛒 {LABELS['perks']}</h3><ul class="perks">{perks}</ul>
        {ranks_html(r)}
        <h3>🌀 {LABELS['curses']}</h3><p class="small">{esc(r.get('curse_intro', ''))}</p>
        <ol class="curses">{curses}</ol>{"" if q.get("hunt") else measures_html(q)}
        """,
        "rules",
        "#333",
    )


def stop_legend(q, only=None, links=False):
    items = []
    for zi, z in enumerate(q["zones"], 1):
        if only is not None and zi not in only:
            continue
        for ti, t in enumerate(zone_tasks(z), 1):
            if t.get("lat") is None:
                continue
            name = "???" if t.get("type") == "trail" else t.get("place") or t.get("title")
            name = esc(re.split(r"[,(]", name)[0].strip())
            if links:
                name = f'<a href="{gmaps(t["lat"], t["lon"])}">{name}</a>'
            items.append(f"<li><b>{esc(task_label(zi, ti, z))}</b> {name}</li>")
    return f'<ul class="legend-stops">{"".join(items)}</ul>' if items else ""


def rank_text(k):
    return k.get("text") or f"🪙 {k.get('min', 0)}+"


def ranks_html(r, boxes=False):
    ranks = r.get("ranks", [])
    if not ranks:
        return ""
    box = '<span class="box sm"></span> ' if boxes else ""
    items = "".join(f"<li>{box}<b>{esc(k.get('name'))}</b> — {esc(rank_text(k))}</li>" for k in ranks)
    hint = "" if boxes else f'<p class="small">{LABELS["ranks_hint"]}</p>'
    return f'<h3>🎖️ {LABELS["ranks"]}</h3>{hint}<ul class="ranks">{items}</ul>'


def zone_legend(q):
    items = "".join(f"<li><b>{zi}</b> {esc(z.get('emoji', ''))} {esc(z['name'])}</li>" for zi, z in enumerate(q["zones"], 1))
    return f'<ul class="legend-stops">{items}</ul>'


def map_card(q, map_html):
    if q.get("campaign"):
        legend = zone_legend(q) if map_html else ""
    else:
        legend = stop_legend(q) if map_html else ""
    if not map_html:
        map_html = "<ol class='zone-list'>" + "".join(
            f"<li>{esc(z.get('emoji',''))} {esc(z['name'])}</li>" for z in q["zones"]
        ) + "</ol>"
    return card(
        f"""<h2>🗺️ {LABELS['map']}</h2>{map_html}<p class="hint">{LABELS['map_hint']}</p>{legend}""",
        "mapcard",
        "#333",
    )


def zone_map_card(q, z, zi, map_html):
    """Campaign: the zone's own close-up map, printed next to its challenge card."""
    how = f'<p class="getthere">{esc(z["getting_there"])}</p>' if z.get("getting_there") else ""
    return card(
        f"""<h2>🗺️ {LABELS['zone']} {zi}: {esc(z['name'])}</h2>{how}{map_html}{stop_legend(q, {zi})}""",
        "mapcard",
        z.get("color", "#333"),
    )


def measures_html(q):
    """Blanks for the kid's own body measures (step, height, arm span…), used by measuring challenges."""
    if not q.get("measures"):
        return ""
    cells = "".join(f'<span class="ms">{esc(m)} <span class="blank short"></span></span>' for m in q["measures"])
    return f'<div class="measures"><b>📏 {LABELS["measures"]}</b> {cells}</div>'


def hunt_card(q):
    """Campaign: a city-wide hunt (bingo) the kid ticks off on every outing."""
    h = q.get("hunt") or {}
    rows = "".join(
        f'<li><span class="hunt-text">{esc(it.get("text"))} {coins_html(it.get("coins"))}</span>'
        f'<span class="hunt-boxes">{"<span class=dot></span>" * int(it.get("boxes", 1))}</span></li>'
        for it in h.get("items", [])
    )
    return card(
        f"""<h2>{esc(h.get('emoji', '🎯'))} {esc(h.get('title', ''))}</h2><p class="small">{esc(h.get('hint', ''))}</p>
        <ul class="hunt">{rows}</ul>{measures_html(q)}""",
        "hunt",
        "#333",
    )


def place_html(t, links=False):
    """📍 line under a task; a trail's place is the riddle's answer, so on screen it is only a map link."""
    if not t.get("place"):
        return ""
    link = gmaps(t["lat"], t["lon"]) if links and t.get("lat") is not None else None
    if t.get("type") == "trail":
        return f'<div class="place"><a href="{link}">📍 {LABELS["map_link"]}</a></div>' if link else ""
    text = esc(t["place"])
    return f'<div class="place">📍 <a href="{link}">{text}</a></div>' if link else f'<div class="place">📍 {text}</div>'


def challenge_li(ch, label, links=False):
    icon, _ = TYPES.get(ch.get("type"), ("⭐", ""))
    duel = ' <span class="duel-tag">⚔️</span>' if ch.get("duel") and ch.get("type") != "duel" else ""
    place = place_html(ch, links)
    return f"""<li class="ch">
      <span class="num">{esc(label)}</span><span class="icon">{icon}</span>
      <div class="body"><div class="ch-title"><b>{esc(ch.get('title'))}</b>{duel} {task_coins_html(ch)}</div>
      <div class="ch-text">{esc(ch.get('text'))}</div>{place}</div>
      <span class="box"></span></li>"""


def coin_track(z, nav=0):
    """Coin dots of a zone (a duel's win coin included), a 🏁 after the coins needed, then 🧭 dots for the navigation bonus."""
    total = sum(int(t.get("coins", 1)) + is_duel(t) for t in z.get("challenges", []))
    if z.get("boss"):
        total += int(z["boss"].get("coins", 0)) + is_duel(z["boss"])
    need = int(z.get("coins_to_claim") or 0)
    dots = []
    for k in range(1, total + 1):
        dots.append('<span class="dot"></span>')
        if k == need and k != total:
            dots.append('<span class="flag">🏁</span>')
    if nav:
        dots.append('<span class="flag">🧭</span>' + '<span class="dot"></span>' * nav)
    return f'<div class="track"><span>🪙</span>{"".join(dots)}</div>'


def zone_card(z, zi, nav=0, links=False):
    tasks = zone_tasks(z)
    n_ch = len(z.get("challenges", []))
    chs = "".join(challenge_li(c, f"{zi}.{ti}", links) for ti, c in enumerate(tasks[:n_ch], 1))
    boss_html = ""
    if z.get("boss"):
        b = z["boss"]
        place = place_html(b, links)
        boss_html = f"""<div class="boss"><div class="ch-title"><b>👑 {LABELS['boss']}: {esc(b.get('title'))}</b> {task_coins_html(b, 5)}</div>
        <div class="ch-text">{esc(b.get('text'))}</div>{place}<span class="box"></span></div>"""
    day = f" · {LABELS['day']} {esc(z['day'])}" if z.get("day") else ""
    return card(
        f"""
        <header class="zone-head">
          <span class="zemoji-big">{esc(z.get('emoji', '🏳️'))}</span>
          <div class="zh"><div class="kicker">{LABELS['zone']} {zi}{day}</div><h2>{esc(z['name'])}</h2></div>
          <div class="stamp"><div class="sticker">{LABELS['sticker']}</div>{LABELS['claimed']}</div>
        </header>
        <p class="story">{esc(z.get('story', ''))}</p>
        <ul class="challenges">{chs}</ul>
        {boss_html}
        <footer class="zone-foot">{coin_track(z, nav)}<span class="need">{LABELS['coins_needed']}: <b>{esc(z.get('coins_to_claim', ''))}</b> 🏁</span></footer>
        """,
        "zone",
        z.get("color", "#333"),
    )


def collection_card(q):
    slots = [f"{z.get('emoji','')} {z['name']}" for z in q["zones"]]
    slots += [LABELS["treasure"]] * max(0, 6 - len(slots))
    if len(slots) % 2:
        slots.append(LABELS["treasure"])
    cells = "".join(f'<div class="slot"><span>{esc(s)}</span></div>' for s in slots)
    return card(
        f"""<h2>🎒 {LABELS['collection']}</h2><p class="small">{LABELS['collection_hint']}</p>
        <div class="slots">{cells}</div>""",
        "collection",
        "#333",
    )


def scorecard_card(q):
    date = "<td></td>" if q.get("campaign") else ""
    rows = "".join(
        f"<tr><td>{esc(z.get('emoji',''))} {esc(z['name'])}</td>{date}<td></td><td>☐</td><td>☐</td></tr>"
        for z in q["zones"]
    )
    date_th = f"<th>{LABELS['date']}</th>" if q.get("campaign") else ""
    return card(
        f"""
        <h2>🏆 {LABELS['scorecard']}</h2>
        <table class="score"><tr><th>{LABELS['zone_col']}</th>{date_th}<th>{LABELS['coins_col']}</th><th>{LABELS['boss_col']}</th><th>{LABELS['claimed_col']}</th></tr>{rows}</table>
        <h3>⚔️ {LABELS['duels']}</h3>
        <table class="duels"><tr><td>{LABELS['kid']}</td><td class="tallybox"></td></tr><tr><td>{LABELS['parents']}</td><td class="tallybox"></td></tr></table>
        <div class="totals"><div>{LABELS['total']}: <span class="blank"></span></div><div>{LABELS['spent']}: <span class="blank"></span></div></div>
        """,
        "scorecard",
        "#333",
    )


def certificate_card(q):
    return card(
        f"""
        <div class="cert-frame">
          <div class="kicker">{LABELS['certificate']}</div>
          <h1>{LABELS['certificate_title']}<br>{esc(q.get('city_local_name') or q['city'])}</h1>
          <div class="medal">{LABELS['medal']}</div>
          <p>{LABELS['certificate_text']}</p>
          <p>{LABELS['certificate_text2']} <span class="blank short"></span> / {len(q['zones'])}</p>
          {f'<p>{LABELS["rank_line"]}: <span class="blank"></span></p>' if q.get('rules', {}).get('ranks') else ''}
          <div class="cert-sign"><div>{LABELS['date']}: <span class="blank"></span></div><div>{LABELS['signature']}: <span class="blank"></span></div></div>
        </div>
        """,
        "certificate",
        "#333",
    )


def parent_plan_card(q):
    p = q.get("parent", {})
    days = "".join(f"<li><b>{LABELS['day']} {esc(d.get('day'))}:</b> {esc(d.get('plan'))}</li>" for d in p.get("days", []))
    tips = "".join(f"<li>{esc(t)}</li>" for t in p.get("tips", []))
    shop = "".join(f"<li>{esc(t)}</li>" for t in p.get("shopping", []))
    hotel = q.get("hotel") or {}
    hotel_html = f"<p><b>{LABELS['hotel']}:</b> {esc(hotel.get('name', ''))}</p>" if hotel.get("name") else ""
    shop_html = f"<h3>🛍️ {LABELS['shopping']}</h3><ul>{shop}</ul>" if shop else ""
    return card(
        f"""<h2>👨‍👩‍👦 {LABELS['parent_pages']}: {LABELS['plan']}</h2>{hotel_html}
        <ul class="plan">{days}</ul>{shop_html}<h3>💡</h3><ul class="tips">{tips}</ul>""",
        "parent",
        "#333",
    )


def booking_html(b):
    rows = "".join(
        f"<tr><th>{LABELS[k]}</th><td>{esc(b.get(f))}</td></tr>"
        for k, f in (("b_when", "when"), ("b_where", "where"), ("b_how", "how"), ("b_cost", "cost")) if b.get(f)
    )
    link = f'<div class="blink"><a href="{esc(b["link"])}">{esc(b["link"])}</a></div>' if b.get("link") else ""
    status = f' <span class="bstatus">{esc(b["status"])}</span>' if b.get("status") else ""
    return f'<div class="booking"><h3>{esc(b.get("what"))}{status}</h3><table>{rows}</table>{link}</div>'


def bookings_cards(q, per_card=4):
    """Bookings that belong to no single zone; a zone's own `bookings` go on its parent card."""
    blocks = [booking_html(b) for b in q.get("parent", {}).get("bookings", [])]
    return [
        card(f"<h2>🎟️ {LABELS['bookings']}</h2>{''.join(blocks[k : k + per_card])}", "parent", "#333")
        for k in range(0, len(blocks), per_card)
    ]


def parent_zone_block(z, zi, part=None):
    """Logistics, answers and the stories behind every spot of a zone (`parent_story`, task `facts`).

    `part` limits the block to some task numbers (a long zone split over two cards); the zone
    story and logistics go with the first part.
    """
    lines = []
    for ti, t in enumerate(zone_tasks(z), 1):
        if part is not None and ti not in part:
            continue
        bits = []
        if t.get("place"):
            pl = esc(t["place"])
            bits.append(f'<a href="{gmaps(t["lat"], t["lon"])}">📍{pl}</a>' if t.get("lat") is not None else f"📍{pl}")
        if t.get("answer"):
            bits.append(f"✔ {esc(t['answer'])}")
        facts = f'<div class="facts">{esc(t["facts"])}</div>' if t.get("facts") else ""
        if bits or facts:
            lines.append(f"<li><b>{task_label(zi, ti, z)} {esc(t.get('title'))}:</b> {' — '.join(bits)}{facts}</li>")
    log = z.get("logistics", {})
    log_html = " · ".join(esc(v) for v in [log.get(k) for k in ("where", "hours", "cost", "food", "toilets")] if v)
    story = f'<p class="pstory">{esc(z["parent_story"])}</p>' if z.get("parent_story") else ""
    books = "".join(booking_html(b) for b in z.get("bookings", []))
    if part is not None and 1 not in part:
        story = log_html = books = ""
    log_p = f'<p class="log">{log_html}</p>' if log_html else ""
    return f"""<div class="pz"><h3>{esc(z.get('emoji',''))} {zi}. {esc(z['name'])}</h3>
      {story}{log_p}{books}<ul>{''.join(lines)}</ul></div>"""


PARENT_CARD_CHARS = 3000  # about what fits on an A5 parent card at a readable size


def zone_parts(z):
    """Split a zone's tasks into groups that each fit one parent card."""
    def size(t):
        return len(t.get("facts", "")) + len(t.get("answer", "")) + len(t.get("place", "")) + len(t.get("title", "")) + 40
    used = len(z.get("parent_story", "")) + sum(len(str(v)) for v in z.get("logistics", {}).values())
    used += sum(len(str(v)) + 30 for b in z.get("bookings", []) for v in b.values())
    parts, cur = [], []
    for ti, t in enumerate(zone_tasks(z), 1):
        if cur and used + size(t) > PARENT_CARD_CHARS:
            parts.append(cur)
            cur, used = [], 0
        cur.append(ti)
        used += size(t)
    return parts + [cur] if cur else parts


def parent_answer_cards(q, per_card):
    zones = list(enumerate(q["zones"], 1))
    if per_card == 1:  # one card per zone (two for a long one): the zone's name is the title
        cards = []
        for i, z in zones:
            parts = zone_parts(z)
            for k, part in enumerate(parts):
                more = f" ({k + 1}/{len(parts)})" if len(parts) > 1 else ""
                cards.append(card(f"<h2>🔑 {LABELS['zone']} {i} — {LABELS['parent_zone']}{more}</h2>" + parent_zone_block(z, i, set(part)), "parent", "#333"))
        return cards
    return [
        card(f"<h2>🔑 {LABELS['answers']}</h2>" + "".join(parent_zone_block(z, i) for i, z in zones[k : k + per_card]), "parent", "#333")
        for k in range(0, len(zones), per_card)
    ]


def notes_card():
    return card(f"<h2>✏️ {LABELS['notes']}</h2><div class='lines'></div>", "notes", "#999")


# ---------------------------------------------------------------- documents

CSS = r"""
@page { size: A4 landscape; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: "Noto Sans", "DejaVu Sans", sans-serif; color: #111; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
a { color: inherit; }
.sheet { width: 297mm; height: 210mm; display: flex; position: relative; page-break-after: always; overflow: hidden; }
.sheet:last-child { page-break-after: auto; }
.sheet::after { content: "✂"; position: absolute; left: 148.5mm; top: 0; bottom: 0; border-left: 0.4mm dashed #999; color: #999; font-size: 10pt; padding-left: 1mm; }
.card { width: 148.5mm; height: 210mm; padding: 7mm; overflow: hidden; }
.fit { height: 100%; overflow: hidden; border: 1mm solid var(--c, #333); border-radius: 6mm; padding: 5mm 5.5mm; font-size: 11pt; line-height: 1.3; display: flex; flex-direction: column; }
h1 { font-size: 2.1em; margin: .2em 0; line-height: 1.1; }
h2 { font-size: 1.45em; margin: 0 0 .35em; line-height: 1.15; }
h3 { font-size: 1.05em; margin: .6em 0 .25em; }
ul, ol { margin: .2em 0; padding-left: 1.3em; }
li { margin: .15em 0; }
.small, .hint, .log { font-size: .85em; color: #444; }
.blank { display: inline-block; min-width: 30mm; border-bottom: .3mm solid #333; height: 1em; }
.blank.short { min-width: 12mm; }
.box { display: inline-block; flex: none; width: 6mm; height: 6mm; border: .5mm solid #222; border-radius: 1.2mm; background: #fff; }
.coins { font-size: .85em; white-space: nowrap; border: .3mm solid #888; border-radius: 3mm; padding: 0 1.5mm; }
/* cover */
.cover .fit { text-align: center; justify-content: center; }
.cover-emoji { font-size: 48pt; }
.cover h1 { font-size: 2.6em; }
.subtitle { font-size: 1.2em; font-weight: bold; }
.dates { color: #555; }
.cover .story { margin: 4mm 0; font-size: 1.05em; text-align: left; }
.team { margin-top: auto; font-size: 1.1em; }
/* rules */
.legend { display: flex; flex-wrap: wrap; gap: 1mm 3mm; font-size: .85em; margin: 2mm 0; padding: 2mm; border: .3mm solid #bbb; border-radius: 3mm; }
.leg { white-space: nowrap; }
/* map */
.map { position: relative; overflow: hidden; border: .3mm solid #999; border-radius: 3mm; margin: 0 auto; background: #f4f4f4; flex: none; }
.map img { position: absolute; }
.map svg { position: absolute; left: 0; top: 0; }
.attr { position: absolute; right: 2px; bottom: 1px; font-size: 7px; color: #555; background: rgba(255,255,255,.8); padding: 0 2px; }
.route { fill: none; stroke: #222; stroke-width: 2.5; stroke-dasharray: 7 6; }
.map img { filter: grayscale(1) contrast(.75) brightness(1.12); }
.land { fill: #f7f7f7; }
.green { fill: #e6e6e6; fill-rule: evenodd; }
.water { fill: #c4c4c4; fill-rule: evenodd; }
.bldg { fill: #e9e9e9; stroke: #d6d6d6; stroke-width: .5; }
.casing { fill: none; stroke: #999; stroke-linecap: round; stroke-linejoin: round; }
.road { fill: none; stroke: #fff; stroke-linecap: round; stroke-linejoin: round; }
.foot { fill: none; stroke: #999; stroke-width: .9; stroke-dasharray: 2 2; }
.rail { fill: none; stroke: #666; stroke-width: 1.2; stroke-dasharray: 6 3; }
.sname { font-size: 11px; font-weight: bold; fill: #000; text-anchor: middle; paint-order: stroke; stroke: #fff; stroke-width: 3px; stroke-linejoin: round; }
.zarea-edge { fill: #111; stroke: #111; stroke-width: 52; stroke-linejoin: round; stroke-linecap: round; }
.zgroup { opacity: .6; }
.zarea { fill: #fff; stroke: #fff; stroke-width: 47; stroke-linejoin: round; stroke-linecap: round; }
.zlabel { font-size: 13px; font-weight: bold; text-anchor: middle; fill: #111; paint-order: stroke; stroke: #fff; stroke-width: 4px; }
.stop { fill: #111; stroke: #fff; stroke-width: 1.5; }
.stopnum { font-size: 9px; font-weight: bold; text-anchor: middle; fill: #fff; }
.zarea-edge.small { stroke-width: 24; }
.zarea.small { stroke-width: 20; }
.badge { fill: #111; stroke: #fff; stroke-width: 2; }
.blobnum { font-size: 10px; font-weight: bold; text-anchor: middle; fill: #111; }
.badgenum { font-size: 13px; font-weight: bold; text-anchor: middle; fill: #fff; }
.getthere { font-size: .85em; margin: 0 0 2mm; }
.hunt { list-style: none; padding: 0; margin: 1mm 0 0; }
.hunt li { display: flex; justify-content: space-between; align-items: center; gap: 2mm; padding: 1.2mm 0; border-bottom: .3mm dotted #bbb; }
.hunt-boxes { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 1mm; flex: none; max-width: 45%; }
.hotel { font-size: 18px; text-anchor: middle; }
.hotel-bg { fill: #fff; stroke: #111; stroke-width: 2; }
.hint { text-align: center; margin: 2mm 0 0; }
.legend-stops { list-style: none; padding: 0; margin: 2mm 0 0; columns: 2; column-gap: 4mm; font-size: .82em; }
.legend-stops li { break-inside: avoid; margin: .3mm 0; }
.legend-stops b { display: inline-block; min-width: 7mm; }
/* zone */
.zone-head { display: flex; align-items: center; gap: 3mm; border-bottom: .5mm solid #333; padding-bottom: 2mm; margin-bottom: 2mm; }
.zemoji-big { font-size: 26pt; }
.zh { flex: 1; } .zh h2 { margin: 0; }
.kicker { font-size: .8em; text-transform: uppercase; letter-spacing: .05em; color: #555; }
.stamp { font-size: .55em; font-weight: bold; text-align: center; }
.sticker { width: 18mm; height: 18mm; border: .5mm dashed #333; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #aaa; font-weight: normal; margin: 0 auto 1mm; }
.story { font-style: italic; margin: 0 0 2mm; }
.challenges { list-style: none; padding: 0; margin: 0; }
.ch { display: flex; gap: 2mm; align-items: flex-start; padding: 1.5mm 0; border-bottom: .3mm dotted #bbb; }
.ch .num { flex: none; font-size: .7em; font-weight: bold; color: #fff; background: #111; border-radius: 2mm; padding: .3mm 1.2mm; margin-top: .6mm; }
.ch .icon { font-size: 1.3em; line-height: 1; width: 6.5mm; text-align: center; }
.ch .body { flex: 1; }
.ch-text { font-size: .92em; }
.place { font-size: .78em; color: #444; }
.boss { position: relative; margin-top: 2.5mm; padding: 2mm 10mm 2mm 3mm; border: .6mm solid #111; border-radius: 3mm; background: #f2f2f2; }
.boss .box { position: absolute; right: 2.5mm; top: 2.5mm; }
.zone-foot { margin-top: auto; padding-top: 2mm; font-size: .85em; display: flex; justify-content: space-between; align-items: center; gap: 2mm; }
.track { display: flex; flex-wrap: nowrap; align-items: center; gap: .8mm; flex: 1; min-width: 0; }
.track .dot { flex: 0 1 5mm; width: auto; height: auto; min-width: 2.8mm; aspect-ratio: 1; }
.dot { width: 5mm; height: 5mm; border: .4mm solid #222; border-radius: 50%; display: inline-block; }
.flag { font-size: 1em; }
.need { white-space: nowrap; }
/* collection */
.slots { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 3mm; margin-top: 2mm; }
.slot { border: .5mm dashed #444; border-radius: 3mm; display: flex; align-items: flex-end; justify-content: center; padding: 1.5mm; font-size: .8em; color: #444; }
/* scorecard */
table { border-collapse: collapse; width: 100%; font-size: .95em; }
th, td { border: .3mm solid #999; padding: 1.5mm 2mm; text-align: left; }
.score td:nth-child(n+2), .score th:nth-child(n+2) { text-align: center; width: 18mm; }
.tallybox { height: 12mm; width: 75%; }
.totals { margin-top: auto; display: flex; flex-direction: column; gap: 3mm; font-size: 1.05em; }
/* certificate */
.certificate .fit { justify-content: center; text-align: center; }
.cert-frame { border: .8mm double #333; border-radius: 4mm; padding: 8mm 5mm; }
.medal { width: 32mm; height: 32mm; border: .6mm dashed #333; border-radius: 50%; margin: 3mm auto; display: flex; align-items: center; justify-content: center; color: #aaa; }
.cert-sign { display: flex; flex-direction: column; gap: 4mm; margin-top: 8mm; text-align: left; }
/* parent */
.parent .fit { font-size: 9.5pt; }
.pz { border-left: 1mm solid #333; padding-left: 2.5mm; margin-bottom: 3mm; }
.pz h3 { margin-top: 0; }
.pz li { margin: .5em 0; }
.facts { margin-top: .2em; color: #222; }
.pstory { margin: 0 0 .3em; font-style: italic; }
.measures { margin-top: 3mm; padding: 2mm; border: .3mm solid #bbb; border-radius: 3mm; font-size: .85em; display: flex; flex-wrap: wrap; gap: 1mm 4mm; }
.ms { white-space: nowrap; }
.pz a { text-decoration: none; border-bottom: .2mm dotted #333; }
.ranks { list-style: none; padding: 0; margin: .2em 0; }
.box.sm { width: 4mm; height: 4mm; vertical-align: middle; }
.booking { border-left: 1mm solid #333; padding-left: 2.5mm; margin-bottom: 3mm; }
.booking h3 { margin: 0 0 1mm; }
.booking table { font-size: .95em; }
.booking th { width: 14mm; vertical-align: top; border: 0; padding: .4mm 1mm .4mm 0; }
.booking td { border: 0; padding: .4mm 0; }
.bstatus { font-size: .75em; font-weight: normal; border: .3mm solid #333; border-radius: 2mm; padding: 0 1.5mm; }
.blink { font-size: .85em; word-break: break-all; }
.notes .lines { flex: 1; background: repeating-linear-gradient(#fff 0 9mm, #bbb 9mm calc(9mm + .3mm)); }
@media screen { body { background: #ddd; } .sheet { background: #fff; margin: 10mm auto; box-shadow: 0 2mm 6mm rgba(0,0,0,.2); } }
"""

FIT_JS = r"""
(function () {
  document.querySelectorAll('.fit').forEach(function (el) {
    var size = parseFloat(getComputedStyle(el).fontSize);
    var min = size * 0.72;
    // zone cards are read by the kid: grow the text to use free space
    if (el.closest('.zone, .hunt')) {
      var max = size * 1.35;
      while (el.scrollHeight <= el.clientHeight && size < max) {
        size += 0.25; el.style.fontSize = size + 'px';
      }
    }
    while (el.scrollHeight > el.clientHeight + 1 && size > min) {
      size -= 0.25; el.style.fontSize = size + 'px';
    }
    if (el.scrollHeight > el.clientHeight + 1) {
      el.closest('.card').setAttribute('data-overflow', '1');
    }
  });
  document.body.setAttribute('data-fitted', '1');
})();
"""


def page(title, body, lang="ru", script=True):
    js = f"<script>{FIT_JS}</script>" if script else ""
    return f"""<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8">
<title>{esc(title)}</title><style>{CSS}</style></head><body>{body}{js}</body></html>"""


def build_html(q, map_html, zone_maps=None):
    # zones with stories for the parents get a card each
    stories = any(z.get("parent_story") or any(t.get("facts") for t in zone_tasks(z)) for z in q["zones"])
    per_card = int(q.get("parent_zones_per_card", 1 if stories else 2))
    nav = int(q.get("rules", {}).get("nav_bonus") or 0)
    cards = [cover_card(q), rules_card(q), map_card(q, map_html)]
    if q.get("campaign"):
        # base sheets first, then one sheet per zone: its map on the left, its challenges on the right
        cards += ([hunt_card(q)] if q.get("hunt") else []) + [collection_card(q), scorecard_card(q), certificate_card(q)]
        if len(cards) % 2:
            cards.append(notes_card())
        for i, z in enumerate(q["zones"], 1):
            cards += [zone_map_card(q, z, i, (zone_maps or {}).get(i, "")), zone_card(z, i, nav)]
    else:
        cards += [zone_card(z, i, nav) for i, z in enumerate(q["zones"], 1)]
        cards += [collection_card(q), scorecard_card(q), certificate_card(q)]
    # parent pages start on their own sheet so they can be kept apart from the kid's cards
    if len(cards) % 2:
        cards.append(notes_card())
    cards += [parent_plan_card(q)] + bookings_cards(q, int(q.get("bookings_per_card", 4))) + parent_answer_cards(q, per_card)
    if len(cards) % 2:
        cards.append(notes_card())
    sheets = "".join(f'<div class="sheet">{cards[k]}{cards[k+1]}</div>' for k in range(0, len(cards), 2))
    return page(q.get("title", q["city"]), sheets, q.get("language", "ru"))


def booking_md(items):
    L = []
    for b in items:
        status = f" _({b['status']})_" if b.get("status") else ""
        L += ["", f"🎟️ **{b.get('what')}**{status}", ""]
        L += [f"- {LABELS[k]}: {b[f]}" for k, f in (("b_when", "when"), ("b_where", "where"), ("b_how", "how"), ("b_cost", "cost")) if b.get(f)]
        if b.get("link"):
            L.append(f"- {b['link']}")
        L.append("")
    return L


def build_md(q, map_png, zone_pngs=None):
    L = []
    c = q.get("cover", {})
    L += [f"# {c.get('emoji', '')} {q.get('title', q['city'])}".strip(), ""]
    if c.get("subtitle"):
        L += [f"**{c['subtitle']}**", ""]
    if q.get("dates"):
        L += [f"_{q['dates']}_", ""]
    if c.get("story"):
        L += [c["story"], ""]
    if map_png:
        L += [f"![{LABELS['map']}]({map_png})", ""]
    r = q.get("rules", {})
    L += [f"## 📜 {LABELS['rules']}", ""]
    L += [f"{n}. {s}" for n, s in enumerate(r.get("steps", []), 1)] + [""]
    if r.get("perks"):
        L += [f"### 🛒 {LABELS['perks']}", ""]
        L += [f"- 🪙×{p.get('cost')} — {p.get('text')}" for p in r["perks"]] + [""]
    if r.get("curses"):
        L += [f"### 🌀 {LABELS['curses']}", ""]
        if r.get("curse_intro"):
            L += [r["curse_intro"], ""]
        L += [f"{n}. {s}" for n, s in enumerate(r["curses"], 1)] + [""]
    if r.get("ranks"):
        L += [f"### 🎖️ {LABELS['ranks']}", "", LABELS["ranks_hint"], ""]
        L += [f"- **{k.get('name')}** — {rank_text(k)}" for k in r["ranks"]] + [""]
    h = q.get("hunt")
    if h:
        L += [f"## {h.get('emoji', '🎯')} {h.get('title', '')}", ""]
        if h.get("hint"):
            L += [h["hint"], ""]
        for it in h.get("items", []):
            coins = f" (🪙×{it['coins']})" if it.get("coins") else ""
            L.append(f"- {'☐ ' * int(it.get('boxes', 1))}{it.get('text')}{coins}")
        L.append("")
    if q.get("measures"):
        L += [f"📏 {LABELS['measures']} " + " · ".join(f"{m} ____" for m in q["measures"]), ""]
    for zi, z in enumerate(q["zones"], 1):
        day = f" · {LABELS['day']} {z['day']}" if z.get("day") else ""
        L += [f"## {z.get('emoji', '')} {LABELS['zone']} {zi}: {z['name']}{day}", ""]
        if z.get("getting_there"):
            L += [z["getting_there"], ""]
        if (zone_pngs or {}).get(zi):
            L += [f"![{LABELS['zone']} {zi}]({zone_pngs[zi]})", ""]
        if z.get("story"):
            L += [f"_{z['story']}_", ""]
        for ti, t in enumerate(zone_tasks(z), 1):
            label = task_label(zi, ti, z)
            is_boss = label == "👑"
            icon = "👑" if is_boss else TYPES.get(t.get("type"), ("⭐",))[0]
            title = f"{LABELS['boss']}: {t.get('title')}" if is_boss else t.get("title")
            duel = " ⚔️" if t.get("duel") and t.get("type") != "duel" else ""
            place = ""
            if t.get("place") and t.get("type") == "trail":  # the place is the riddle's answer: link only
                place = f" 📍 [{LABELS['map_link']}]({gmaps(t['lat'], t['lon'])})" if t.get("lat") is not None else ""
            elif t.get("place"):
                place = f" 📍 [{t['place']}]({gmaps(t['lat'], t['lon'])})" if t.get("lat") is not None else f" 📍 {t['place']}"
            num = "" if is_boss else f"{label} "
            L.append(f"- [ ] {num}{icon} **{title}**{duel} ({coins_text(t, 5 if is_boss else 1)}) — {t.get('text')}{place}")
        if z.get("coins_to_claim"):
            L += ["", f"{LABELS['coins_needed']}: **{z['coins_to_claim']}** 🏁"]
        L.append("")
    p = q.get("parent", {})
    L += ["---", "", f"## 👨‍👩‍👦 {LABELS['parent_pages']}", ""]
    hotel = q.get("hotel") or {}
    if hotel.get("name"):
        L += [f"**{LABELS['hotel']}:** {hotel['name']}", ""]
    if p.get("days"):
        L += [f"### {LABELS['plan']}", ""]
        L += [f"- **{LABELS['day']} {d.get('day')}:** {d.get('plan')}" for d in p["days"]] + [""]
    if p.get("bookings"):
        L += [f"### 🎟️ {LABELS['bookings']}", ""] + booking_md(p["bookings"])
    if p.get("shopping"):
        L += [f"### 🛍️ {LABELS['shopping']}", ""] + [f"- {s}" for s in p["shopping"]] + [""]
    if p.get("tips"):
        L += ["### 💡", ""] + [f"- {t}" for t in p["tips"]] + [""]
    L += [f"### 🔑 {LABELS['answers']}", ""]
    for zi, z in enumerate(q["zones"], 1):
        L += [f"#### {z.get('emoji', '')} {zi}. {z['name']}", ""]
        if z.get("parent_story"):
            L += [f"_{z['parent_story']}_", ""]
        log = z.get("logistics", {})
        L += [f"- {log[k]}" for k in ("where", "hours", "cost", "food", "toilets") if log.get(k)]
        L += booking_md(z.get("bookings", []))
        for ti, t in enumerate(zone_tasks(z), 1):
            bits = []
            if t.get("place"):
                bits.append(f"[{t['place']}]({gmaps(t['lat'], t['lon'])})" if t.get("lat") is not None else t["place"])
            if t.get("answer"):
                bits.append(f"✔ {t['answer']}")
            if bits or t.get("facts"):
                L.append(f"- **{task_label(zi, ti, z)} {t.get('title')}:** {' — '.join(bits)}")
                if t.get("facts"):
                    L.append(f"  {t['facts']}")
        L.append("")
    if q.get("sources"):
        L += [f"### {LABELS['sources']}", ""] + [f"- {s}" for s in q["sources"]] + [""]
    return "\n".join(L)


# ---------------------------------------------------------------- rendering


def check_ranks(q):
    """Warn when the top rank needs more than 95 % of the coins the kid can surely earn.

    Challenges marked "optional": true (unbooked rides, weather-dependent extras)
    don't count, so the top rank stays reachable without them and without spending;
    neither does a duel's win coin.
    """
    ranks = q.get("rules", {}).get("ranks", [])
    if not ranks:
        return
    sure = sum(
        int(t.get("coins", 1))
        for z in q["zones"] for t in zone_tasks(z) if not t.get("optional")
    )
    nav = int(q["rules"].get("nav_bonus") or 0) * len(q["zones"])
    sure += nav
    top = max(int(k.get("min", 0)) for k in ranks)
    print(f"Coins: {sure} without optional challenges (navigation bonus {nav}); top rank needs {top} ({top / max(sure, 1):.0%})")
    if top > 0.95 * sure:
        print(f"WARNING: top rank is out of reach at 95 % completion; lower it to <= {int(0.95 * sure)}")


def find_chrome():
    for name in [os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
        if name and shutil.which(name):
            return shutil.which(name)
    sys.exit("No Chrome/Chromium found; set CHROME=/path/to/chrome")


def run_chrome(chrome, args, profile):
    base = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
            f"--user-data-dir={profile}", "--virtual-time-budget=10000"]
    return subprocess.run(base + args, capture_output=True, text=True, timeout=180)


def set_language(q):
    """Built-in labels for the quest's language and gender, then the quest's own overrides."""
    if q.get("language") == "en":
        LABELS.update(LABELS_EN)
        for t, v in TYPE_NAMES_EN.items():
            TYPES[t] = (TYPES[t][0], v)
    elif str(q.get("players", {}).get("gender", "")).lower() in ("f", "girl", "ж"):
        LABELS.update(LABELS_F)
    LABELS.update(q.get("labels", {}))
    for t, v in q.get("type_labels", {}).items():
        TYPES[t] = (TYPES.get(t, ("⭐",))[0], v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quest_json")
    ap.add_argument("--out-dir")
    ap.add_argument("--name", help="output name; default: the file name, e.g. quest or quest.en")
    a = ap.parse_args()
    src = Path(a.quest_json).resolve()
    q = json.loads(src.read_text(encoding="utf-8"))
    set_language(q)
    a.name = a.name or src.stem
    out = Path(a.out_dir).resolve() if a.out_dir else src.parent
    out.mkdir(parents=True, exist_ok=True)

    md_path, html_path, pdf_path = (out / f"{a.name}.{e}" for e in ("md", "html", "pdf"))
    campaign = bool(q.get("campaign"))
    pins = [{}]
    map_html = build_map(q, overview=campaign, pins=pins[0])
    zone_maps = {}
    for i in range(1, len(q["zones"]) + 1) if campaign else ():
        pins.append({})
        zone_maps[i] = build_map(q, only={i}, pins=pins[-1])
    html_path.write_text(build_html(q, map_html, zone_maps), encoding="utf-8")
    # a translation (quest.en.json) shares the main quest's map pictures when they hold only numbers
    # and local street names; maps that name the zones get their own files (quest.en-map.png)
    has_text = any('class="zlabel"' in m for m in [map_html, *zone_maps.values()])
    map_name = a.name if has_text else re.sub(r"\.[a-z]{2}$", "", a.name)
    png_path = out / f"{map_name}-map.png"
    # where the stops are on each map picture, for clickable pins on the website
    names = [f"{map_name}-map.png"] + [f"{map_name}-map-{i}.png" for i in zone_maps]
    (out / f"{map_name}-pins.json").write_text(json.dumps({n: p for n, p in zip(names, pins) if p}, indent=1), encoding="utf-8")

    shots = [(map_html, png_path)] + [(m, out / f"{map_name}-map-{i}.png") for i, m in zone_maps.items()]
    chrome = find_chrome()
    with tempfile.TemporaryDirectory() as profile:
        for k, (m_html, m_png) in enumerate(shots):
            if not m_html:
                continue
            map_page = Path(profile) / f"map{k}.html"
            map_body = "<style>.map{border:0;border-radius:0} body{margin:0;background:#fff}</style>" + m_html
            map_page.write_text(page("map", map_body, script=False), encoding="utf-8")
            map_h = re.search(r'class="map" style="width:\d+px;height:(\d+)px', m_html).group(1)
            run_chrome(chrome, ["--force-device-scale-factor=2", f"--window-size={MAP_W},{map_h}",
                                f"--screenshot={m_png}", map_page.as_uri()], profile)
        dom = run_chrome(chrome, ["--dump-dom", html_path.as_uri()], profile).stdout
        res = run_chrome(chrome, ["--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", html_path.as_uri()], profile)
    if not pdf_path.exists():
        sys.exit(f"PDF render failed:\n{res.stderr[-2000:]}")
    zone_pngs = {i: f"{map_name}-map-{i}.png" for i in zone_maps if (out / f"{map_name}-map-{i}.png").exists()}
    md_path.write_text(build_md(q, png_path.name if png_path.exists() else None, zone_pngs), encoding="utf-8")

    print(f"Wrote {md_path}\nWrote {html_path}\nWrote {pdf_path}")
    if png_path.exists():
        print(f"Wrote {png_path}")
    if 'data-fitted="1"' not in dom:
        print("WARNING: could not verify card fit (layout script did not run)")
    check_ranks(q)
    over = re.findall(r'<section class="card ([a-z]+)"[^>]*data-overflow="1"[^>]*>.*?<h2[^>]*>(.*?)</h2>', dom, re.S)
    if over:
        print("OVERFLOW: these cards are too long even after shrinking; shorten their text:")
        for cls, t in over:
            print(f"  - [{cls}] {re.sub('<[^>]+>', '', t).strip()}")
        sys.exit(2)


if __name__ == "__main__":
    main()
