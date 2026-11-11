#!/usr/bin/env python3
"""Build a personalised binder cover in the explorer style: front and back, either as two A5
halves of one A4 landscape sheet (default) or, with "size", each face on its own A4 page.

Usage:
    python3 build_cover.py covers/<slug>/cover.json

cover.json (private, lives in the git-ignored covers/ folder):
    {
      "name": "Маша",                        # big on the front
      "subtitle": "Паспорт\\nпокорителя городов",  # optional title; a second line comes out smaller
      "lang": "ru",                          # language of the city names (ru, en)
      "figure": "kid-contour.svg",           # contour_portrait.py (default), line_portrait.py svg, kid-sketch.png or kid-sticker.png,
      "figure_kind": "",                     #   or any finished drawing on white paper with "figure_kind": "drawing"
      "motto": "Ищи, считай, находи —\\nгород твой!",
      "size": [190, 220],                    # optional: width, height of each face in mm (the binder's pocket);
                                             #   each face then gets its own A4 portrait page, with crop marks
      "back_size": [190, 228],               # optional, with "size": the back's own size when its pocket differs
      "spine": 30,                           # optional, with "size": spine width in mm, or [width, height]; a 3rd page with the title
      "icons": ["✈️", "🧭", "🚂", "⛵", "🏰", "🗼", "📷", "🎒"],   # 3rd-6th: stamps, last: luggage tag
      "map": {
        "main": "europe",                    # a region of references/cities.json
        "inset": "netherlands",              # optional: a region drawn in the magnifier
        "add": [{"en": "Paris", "ru": "Париж", "lat": 48.86, "lon": 2.35}],
        "drop": ["Athens"],                  # English names to leave out
        "labels": true,                      # city names next to the circles; false for the *-all regions
        "quests": true                       # add every <repo>/*/quest.json city that is missing
      }
    }

Writes next to cover.json: cover.html, cover.pdf (A4 landscape: back left, front right, dashed
cut line in the middle; with "size": page 1 the front, page 2 the back, each centred on A4 portrait
with crop marks and 2 mm bleed) and cover.png (preview). The back shows the region with an empty circle
per city: the child colours it in or puts a sticker on it after conquering the city.
Country shapes come from world-atlas (Natural Earth, public domain), cached in
~/.cache/city-quest/world.
"""
import argparse
import base64
import html
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # the city_quests repository
CACHE = Path.home() / ".cache" / "city-quest" / "world"
esc = html.escape

INK, RUST, PAPER, LAND, SEA = "#4a2f17", "#7a3b12", "#fbf1da", "#dcb983", "#f3e4c4"
FONTS = "https://fonts.googleapis.com/css2?family=Amatic+SC:wght@700&family=Neucha&display=block"

# ---------------------------------------------------------------- geography

_topo = {}


def countries(res="50m"):
    """Country polygons as lists of rings of (lon, lat)."""
    if res in _topo:
        return _topo[res]
    p = CACHE / f"countries-{res}.json"
    if not p.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-{res}.json", p)
    t = json.loads(p.read_text())
    (sx, sy), (tx, ty) = t["transform"]["scale"], t["transform"]["translate"]
    arcs = []
    for arc in t["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts += a[1:] if pts else a
        return pts

    polys = []
    for g in t["objects"]["countries"]["geometries"]:
        if g.get("id") == "010":  # Antarctica
            continue
        if g["type"] == "Polygon":
            polys.append([ring(r) for r in g["arcs"]])
        elif g["type"] == "MultiPolygon":
            polys += [[ring(r) for r in p] for p in g["arcs"]]
    _topo[res] = polys
    return polys


def laea(lon0, lat0):
    """Lambert azimuthal equal-area around (lon0, lat0), in km."""
    l0, p0 = math.radians(lon0), math.radians(lat0)

    def f(lon, lat):
        l, p = math.radians(lon), math.radians(lat)
        k = math.sqrt(2 / (1 + math.sin(p0) * math.sin(p) + math.cos(p0) * math.cos(p) * math.cos(l - l0)))
        return 6371 * k * math.cos(p) * math.sin(l - l0), -6371 * k * (math.cos(p0) * math.sin(p) - math.sin(p0) * math.cos(p) * math.cos(l - l0))
    return f


def equal_earth(lon, lat):
    A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
    th = math.asin(math.sqrt(3) / 2 * math.sin(math.radians(lat)))
    x = 2 * math.sqrt(3) * math.radians(lon) * math.cos(th) / (3 * (9 * A4 * th ** 8 + 7 * A3 * th ** 6 + 3 * A2 * th ** 2 + A1))
    return x, -(A4 * th ** 9 + A3 * th ** 7 + A2 * th ** 3 + A1 * th)


def path_d(polys, f, keep=None):
    out = []
    for poly in polys:
        if keep and not any(keep(lo, la) for r in poly for lo, la in r[::3]):
            continue
        for r in poly:
            if max(p[0] for p in r) - min(p[0] for p in r) > 180:
                # across the antimeridian (Russia's Chukotka, Fiji): keep all longitudes on one side, so the
                # outline doesn't jump across the whole map; the far end just runs off the map's edge
                r = [(lo + 360 if lo < 0 else lo, la) for lo, la in r]
            out.append("M" + "L".join("%.1f,%.1f" % f(*p) for p in r) + "Z")
    return "".join(out)


def fit(bbox, box):
    """Projection for bbox [w, s, e, n] scaled into box (x, y, w, h); returns f(lon, lat) -> (x, y)."""
    w, s, e, n = bbox
    P = laea((w + e) / 2, (s + n) / 2)
    edge = [(lo, la) for lo in (w, e) for la in range(int(s), int(n) + 1)] + [(lo, la) for la in (s, n) for lo in range(int(w), int(e) + 1)]
    xs, ys = zip(*(P(*p) for p in edge))
    x0, y0, W, H = box
    k = min(W / (max(xs) - min(xs)), H / (max(ys) - min(ys)))
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    def f(lo, la):
        x, y = P(lo, la)
        return x0 + W / 2 + k * (x - cx), y0 + H / 2 + k * (y - cy)
    return f


def inside(bbox, c):
    w, s, e, n = bbox
    return w <= c["lon"] <= e and s <= c["lat"] <= n


def quest_cities():
    out = []
    for qj in sorted(ROOT.glob("*/quest.json")):
        q = json.loads(qj.read_text(encoding="utf-8"))
        pts = [(t["lat"], t["lon"]) for z in q["zones"] for t in z.get("challenges", []) + [z.get("boss") or {}] if isinstance(t, dict) and t.get("lat")]
        if pts:
            out.append({"en": q["city"], "lat": sum(p[0] for p in pts) / len(pts), "lon": sum(p[1] for p in pts) / len(pts)})
    return out


def city_lists(cfg):
    regions = json.loads((HERE.parent / "references" / "cities.json").read_text(encoding="utf-8"))
    m = cfg.get("map", {})
    main = regions[m.get("main", "europe")]
    inset = regions.get(m.get("inset")) if m.get("inset") else None
    pool = main["cities"] + (inset["cities"] if inset else []) + m.get("add", [])
    if m.get("quests", True):
        known = {c["en"] for c in pool}
        pool += [c for c in quest_cities() if c["en"] not in known]
    drop = set(m.get("drop", []))
    pool = [c for c in pool if c["en"] not in drop]
    lang = cfg.get("lang", "ru")
    for c in pool:
        c["label"] = c.get(lang) or c["en"]
    in_inset = [c for c in pool if inset and inside(inset["bbox"], c)]
    in_main = [c for c in pool if c not in in_inset]  # back_map keeps those that fall inside the map frame
    return main, inset, in_main, in_inset

# ---------------------------------------------------------------- drawing

def place_labels(cities, f, r, fs, bounds, avoid=(), labels=True):
    """Empty circles, optionally with labels placed around them, avoiding each other (greedy)."""
    xy = [f(c["lon"], c["lat"]) for c in cities]
    for i in range(len(cities)):
        for j in range(i):
            if math.hypot(xy[i][0] - xy[j][0], xy[i][1] - xy[j][1]) < 2 * r + 3:
                print(f"NOTE: circles touch: {cities[i]['en']} / {cities[j]['en']}")
    if not labels:
        return "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{PAPER}" stroke="{RUST}" stroke-width="{r*0.24:.1f}"/>' for x, y in xy)
    boxes = [(x - r, y - r, x + r, y + r) for x, y in (f(c["lon"], c["lat"]) for c in cities)] + list(avoid)
    out = []
    if not callable(bounds):
        bx0, by0, bx1, by1 = bounds
        bounds = lambda b: b[0] >= bx0 and b[2] <= bx1 and b[1] >= by0 and b[3] <= by1
    for c in sorted(cities, key=lambda c: -len(c["label"])):
        x, y = f(c["lon"], c["lat"])
        w, h = fs * 0.58 * len(c["label"]) + fs * 0.2, fs * 0.9  # Neucha prints wider than half an em per letter
        g = r + fs * 0.2
        cands = [(x + g, y + h * 0.35, "start"), (x - g, y + h * 0.35, "end"), (x, y - g - h * 0.1, "middle"), (x, y + g + h * 0.8, "middle"),
                 (x + g * 0.8, y - g * 0.8, "start"), (x - g * 0.8, y - g * 0.8, "end"), (x + g * 0.8, y + g + h * 0.5, "start"), (x - g * 0.8, y + g + h * 0.5, "end")]
        best = None
        others = [p for p in xy if p != (x, y)]
        for k, (tx, ty, anc) in enumerate(cands):
            lx = tx if anc == "start" else tx - w if anc == "end" else tx - w / 2
            box = (lx, ty - h * 0.8, lx + w, ty + h * 0.2)
            if not bounds(box):
                continue
            hits = sum(1 for b in boxes if not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]))
            # ambiguity: another circle closer to the label than its own circle reads as the wrong city
            gap = lambda px, py: math.hypot(max(box[0] - px, 0, px - box[2]), max(box[1] - py, 0, py - box[3]))
            own = gap(x, y)
            amb = sum(1 for px, py in others if gap(px, py) < own + r * 0.6)
            score = hits * 10 + amb * 3 + k * 0.1
            if best is None or score < best[0]:
                best = (score, tx, ty, anc, box, hits)
        if best:
            best = best[:5] if not best[5] else best[:5]
        if best:
            boxes.append(best[4])
            if best[0] >= 10:
                print(f"NOTE: label overlaps: {c['en']}")
        else:
            print(f"NOTE: no room for the label: {c['en']}")
        out.append((c, x, y, best))
    svg = []
    for c, x, y, best in out:
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{PAPER}" stroke="{RUST}" stroke-width="{r*0.2:.1f}"/>')
        if best:
            _, tx, ty, anc, _ = best
            svg.append(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anc}" font-size="{fs:.1f}" fill="{INK}" paint-order="stroke" stroke="{PAPER}" '
                       f'stroke-width="{fs*0.22:.1f}" stroke-linejoin="round">{esc(c["label"])}</text>')
    return "".join(svg)


def compass(size, c1=RUST, c2="#c9772f"):
    pts = []
    for i in range(8):
        a = math.radians(i * 45)
        L = 0.48 if i % 2 == 0 else 0.3
        tip = (50 + L * 100 * math.sin(a), 50 - L * 100 * math.cos(a))
        l = (50 + 7 * math.sin(a - math.pi / 2), 50 - 7 * math.cos(a - math.pi / 2))
        r = (50 + 7 * math.sin(a + math.pi / 2), 50 - 7 * math.cos(a + math.pi / 2))
        pts.append(f'<path d="M50,50L{l[0]:.1f},{l[1]:.1f}L{tip[0]:.1f},{tip[1]:.1f}Z" fill="{c1}"/><path d="M50,50L{r[0]:.1f},{r[1]:.1f}L{tip[0]:.1f},{tip[1]:.1f}Z" fill="{c2}"/>')
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}"><circle cx="50" cy="50" r="46" fill="{SEA}" fill-opacity=".7" stroke="{c1}" stroke-width="1.5"/>'
            f'<circle cx="50" cy="50" r="40" fill="none" stroke="{c1}" stroke-width=".6" stroke-dasharray="2,2"/>' + "".join(pts) +
            f'<circle cx="50" cy="50" r="4" fill="{c2}" stroke="{c1}"/><text x="50" y="9" font-size="9" text-anchor="middle" fill="{c1}" font-weight="700">N</text></svg>')


def back_map(cfg, W=1360, H=1640):
    """Back cover picture, in 0.1 mm units (A5: 1360 x 1640, i.e. 136 x 164 mm)."""
    MH = H - 350                         # MH: height of the main map frame; the magnifier hangs below it
    main, inset, in_main, in_inset = city_lists(cfg)
    F = fit(main["bbox"], (0, 0, W, MH))
    land = path_d(countries(), F, keep=lambda lo, la: -30 < lo < 50 and 30 < la < 72)
    R = 255 if inset else 0
    mx, my = W * 0.36, MH + 90           # the magnifier hangs below the map: it hides only a strip of its bottom
    svg = [f'<svg viewBox="0 0 {W} {H}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" font-family="Neucha">',
           f'<defs><clipPath id="frame"><rect x="0" y="0" width="{W}" height="{MH}" rx="14"/></clipPath>',
           f'<clipPath id="lens"><circle cx="{mx}" cy="{my}" r="{R}"/></clipPath></defs>']
    grid = ""
    w, s, e, n = main["bbox"]
    for lo in range(int(w // 10 * 10), int(e) + 11, 10):
        grid += "M" + "L".join("%.1f,%.1f" % F(lo, la) for la in range(int(s) - 6, int(n) + 7))
    for la in range(int(s // 10 * 10), int(n) + 11, 10):
        grid += "M" + "L".join("%.1f,%.1f" % F(lo, la) for lo in range(int(w) - 12, int(e) + 13))
    svg += [f'<g clip-path="url(#frame)"><rect width="{W}" height="{MH}" fill="{SEA}"/>',
            f'<path d="{grid}" fill="none" stroke="#c9a77a" stroke-width="2" stroke-dasharray="8,6"/>',
            f'<path d="{land}" fill="{LAND}" stroke="{RUST}" stroke-width="1.6" stroke-linejoin="round"/></g>',
            f'<rect x="0" y="0" width="{W}" height="{MH}" rx="14" fill="none" stroke="{RUST}" stroke-width="5"/>']
    labels = cfg.get("map", {}).get("labels", True)
    r_main, r_inset = (13, 10) if labels else (10, 8)
    avoid = [(mx - R - 20, my - R - 20, mx + R + 20, my + R + 20)] if inset else []
    if inset:
        # zoom on the cities themselves; the country around them is clipped by the lens
        lons, lats = [c["lon"] for c in in_inset], [c["lat"] for c in in_inset]
        pad = 0.08 * max(max(lons) - min(lons), max(lats) - min(lats), 0.5)
        Fi = fit([min(lons) - pad, min(lats) - pad, max(lons) + pad, max(lats) + pad], (mx - R * 0.66, my - R * 0.66, R * 1.32, R * 1.32))
        # then zoom in until the outermost city sits near the rim of the lens
        far = max(math.hypot(Fi(c["lon"], c["lat"])[0] - mx, Fi(c["lon"], c["lat"])[1] - my) for c in in_inset)
        z, F0 = (1.0 if labels else R * 0.84 / far), Fi  # with names the labels need the room around the cities
        Fi = lambda lo, la, F0=F0, z=z: (mx + (F0(lo, la)[0] - mx) * z, my + (F0(lo, la)[1] - my) * z)
        iw, isb, ie, inn = inset["bbox"]
        cx, cy = F((iw + ie) / 2, (isb + inn) / 2)
        rr = max(abs(F(iw, isb)[0] - F(ie, inn)[0]), abs(F(iw, isb)[1] - F(ie, inn)[1])) * 0.62
        ins_land = path_d(countries("10m") if (CACHE / "countries-10m.json").exists() else countries(), Fi, keep=lambda lo, la: iw - 4 < lo < ie + 4 and isb - 3 < la < inn + 3)
        svg += [f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rr:.1f}" fill="none" stroke="{RUST}" stroke-width="4"/>',
                f'<line x1="{cx:.1f}" y1="{cy + rr:.1f}" x2="{mx:.1f}" y2="{my - R:.1f}" stroke="{RUST}" stroke-width="3.5" stroke-dasharray="12,9"/>']
        avoid.append((cx - rr, cy - rr, cx + rr, cy + rr))
    avoid.append((0, 0, 262, 262))  # the compass rose
    def visible(c):
        x, y = F(c["lon"], c["lat"])
        if inset and math.hypot(x - mx, y - my) < R + 24:
            return False
        return 14 < x < W - 14 and 14 < y < MH - 14 and not any(b[0] < x < b[2] and b[1] < y < b[3] for b in (avoid[1:] if inset else avoid))
    svg.append(place_labels([c for c in in_main if visible(c)], F, r_main, 27, (6, 6, W - 6, MH - 6), avoid, labels))
    svg.append(f'<g transform="translate(16,16)">{compass(230)}</g>')
    if inset:
        hx, hy = mx + R * 0.94, my + R * 0.34
        svg += [f'<line x1="{hx:.1f}" y1="{hy:.1f}" x2="{hx + R*0.5:.1f}" y2="{hy + R*0.18:.1f}" stroke="{RUST}" stroke-width="44" stroke-linecap="round"/>',
                f'<circle cx="{mx}" cy="{my}" r="{R}" fill="{SEA}"/>',
                f'<g clip-path="url(#lens)"><path d="{ins_land}" fill="{LAND}" stroke="{RUST}" stroke-width="1.6" stroke-linejoin="round"/>',
                place_labels(in_inset, Fi, r_inset, 22, labels=labels, bounds=lambda b: all(math.hypot(x - mx, y - my) < R * 0.93 for x in (b[0], b[2]) for y in (b[1], b[3]))), "</g>",
                f'<circle cx="{mx}" cy="{my}" r="{R}" fill="none" stroke="{RUST}" stroke-width="22"/>',
                f'<circle cx="{mx}" cy="{my}" r="{R - 14}" fill="none" stroke="#c9772f" stroke-width="4"/>']
    svg.append("</svg>")
    return "".join(svg)


def faded_uri(path, max_h=2000):
    """A drawing on white paper with its edges faded to white (an oval around the face): multiplied onto the
    parchment, white disappears, so the fade needs no CSS mask (masks leave hairline seams in the PDF)."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((max_h * 2, max_h))
    w, h = im.size
    cx, cy, rx, ry = w * 0.5, h * 0.46, w * 0.56, h * 0.52
    mask = Image.new("L", (w, h))
    px = mask.load()
    for y in range(h):
        dy = (y - cy) / ry
        for x in range(w):
            d = math.hypot((x - cx) / rx, dy)
            px[x, y] = int(255 * min(1, max(0, (1 - d) / 0.30)))
    im = Image.composite(im, Image.new("RGB", (w, h), "white"), mask)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def data_uri(path, max_h=1800):
    from PIL import Image
    im = Image.open(path)
    im.thumbnail((max_h * 2, max_h))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# ---------------------------------------------------------------- page

A5 = (148.5, 210)
BLEED = 2.0


def make_css(SW, SH, separate):
    """Styles for faces of SW x SH mm. Designed on A5: on another size vertical positions stretch with
    the height (ky), sizes and fonts with the smaller ratio (k); left/right anchors stay put."""
    k = min(SW / A5[0], SH / A5[1])
    ky = SH / A5[1]
    v = lambda x: f"{x * ky:.1f}mm"   # a vertical position
    z = lambda x: f"{x * k:.1f}mm"    # a size
    pt = lambda x: f"{x * k:.1f}pt"   # a font size
    if separate:
        L, T = (210 - SW) / 2, (297 - SH) / 2
        page = f"""@page {{ size: A4 portrait; margin: 0; }}
.sheet {{ width: 210mm; height: 297mm; position: relative; overflow: hidden; break-after: page; }}
.sheet:last-child {{ break-after: auto; }}
.sheet .side {{ position: absolute; left: {L:.2f}mm; top: {T:.2f}mm; }}
.bleed {{ position: absolute; left: {L - BLEED:.2f}mm; top: {T - BLEED:.2f}mm; width: {SW + 2 * BLEED:.2f}mm; height: {SH + 2 * BLEED:.2f}mm; background: #e2c793; }}
.crop {{ position: absolute; background: #000; }}"""
    else:
        page = """@page { size: A4 landscape; margin: 0; }
.sheet { width: 297mm; height: 210mm; display: flex; position: relative; overflow: hidden; }
.sheet::after { content: ""; position: absolute; left: 148.5mm; top: 0; bottom: 0; border-left: .3mm dashed rgba(0,0,0,.35); }"""
    return f"""{page}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #fff; }}
img {{ display: block; }}
.side {{ width: {SW}mm; height: {SH}mm; position: relative; overflow: hidden; color: {INK}; font-family: Neucha, sans-serif;
  background: radial-gradient(ellipse at 50% 40%, {PAPER} 0%, #f1dfb8 70%, #e2c793 100%); }}
.bgmap {{ position: absolute; opacity: .16; }}  /* placed in build(): the land touches both side edges */
.name {{ position: absolute; top: {v(12)}; left: 0; right: 0; text-align: center; font: 700 {pt(52)} "Amatic SC"; letter-spacing: 3mm; color: {RUST};
  text-shadow: .6mm .6mm 0 #f7e7c4, 1.2mm 1.2mm 0 rgba(74,47,23,.25); }}
.compass {{ position: absolute; top: {v(40)}; right: 8mm; transform: rotate(-12deg); }}
.subtitle {{ position: absolute; top: {v(33)}; left: 0; right: 0; text-align: center; font: 700 {pt(21)} "Amatic SC"; letter-spacing: .8mm; color: {INK}; }}
/* with a subtitle: the subtitle is the title at the top, the name sits under the portrait */
.sub2 {{ font-size: .6em; letter-spacing: .6mm; margin-top: -1.5mm; }}
.titled .subtitle {{ top: {v(7)}; font-size: {pt(48)}; line-height: 1; letter-spacing: 1.2mm; color: {RUST}; text-shadow: .5mm .5mm 0 #f7e7c4, 1mm 1mm 0 rgba(74,47,23,.2); }}
.titled .name {{ top: auto; bottom: {v(7)}; font-size: {pt(46)}; }}
.titled .drawing {{ bottom: {v(31)}; width: {z(80)}; }}
.sub2::before, .sub2::after {{ content: "~"; margin: 0 2.5mm; color: #c9772f; }}
.route {{ position: absolute; top: {v(36)}; left: 0; width: 100%; height: {SW * 60 / 150:.1f}mm; }}
.kid {{ position: absolute; bottom: {v(6)}; left: 50%; transform: translateX(-50%) rotate(-2deg); height: {z(132)}; filter: drop-shadow(.8mm 1.2mm 1.2mm rgba(60,30,0,.3)); }}
.head {{ position: absolute; bottom: {v(9)}; left: 50%; transform: translateX(-50%); width: {z(98)}; }}
/* a drawing on white paper: multiplied onto the parchment (white becomes parchment), edges fading out */
.drawing {{ position: absolute; bottom: {v(4)}; left: 50%; transform: translateX(-50%); width: {z(88)}; mix-blend-mode: multiply; }}
.stamp, .compass {{ z-index: 2; }}
.portrait {{ position: absolute; bottom: 0; left: 50%; transform: translateX(-50%); width: {z(112)}; }}
.stamp {{ position: absolute; width: {z(22)}; height: {z(22)}; border: .8mm dashed #a4482a; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: {pt(22)}; background: rgba(255,250,235,.55); }}
.s1 {{ top: {v(96)}; left: 6mm; transform: rotate(-14deg); }} .s2 {{ top: {v(84)}; right: 6mm; transform: rotate(10deg); }}
.s3 {{ bottom: {v(44)}; left: 4mm; transform: rotate(8deg); }} .s4 {{ bottom: {v(64)}; right: 4mm; transform: rotate(-8deg); }}
.motto {{ position: absolute; top: {v(9)}; left: 8mm; right: 8mm; text-align: center; font: 700 {pt(28)}/1.02 "Amatic SC"; color: {RUST}; }}
.spine {{ display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: {v(8)} 0; }}
.spine .title {{ flex: 1; display: flex; align-items: center; justify-content: center; writing-mode: vertical-rl; transform: rotate(180deg);
  white-space: nowrap; font: 700 {pt(56)} "Amatic SC"; letter-spacing: 1.2mm; color: {RUST}; text-shadow: .4mm .4mm 0 #f7e7c4, .8mm .8mm 0 rgba(74,47,23,.2); }}
.spine .t2 {{ font-size: .62em; margin-top: 1.5mm; }}
.spine .t2::before, .spine .t2::after {{ content: "~"; margin: 0 2.5mm; color: #c9772f; }}
.spine .icon {{ font-size: {pt(20)}; }}
.mapbox {{ position: absolute; top: {v(38)}; left: 6.25mm; right: 6.25mm; bottom: {v(8)}; }}
"""


def back_css(BW, BH):
    """The back's motto and map for a back of its own size (back_size)."""
    k, ky = min(BW / A5[0], BH / A5[1]), BH / A5[1]
    return (f".back .motto {{ top: {9 * ky:.1f}mm; font-size: {28 * k:.1f}pt; }}\n"
            f".back .mapbox {{ top: {38 * ky:.1f}mm; bottom: {8 * ky:.1f}mm; }}\n")


def placed(W, H, cls, inner):
    """An A4 portrait sheet with a W x H mm face centred on it, its bleed and crop marks."""
    L, T = (210 - W) / 2, (297 - H) / 2
    box = f"left:{L:.2f}mm;top:{T:.2f}mm;width:{W}mm;height:{H}mm"
    bleed = f"left:{L - BLEED:.2f}mm;top:{T - BLEED:.2f}mm;width:{W + 2 * BLEED:.2f}mm;height:{H + 2 * BLEED:.2f}mm"
    return f'<div class="sheet"><div class="bleed" style="{bleed}"></div><div class="side {cls}" style="{box}">{inner}</div>{crop_marks(W, H)}</div>'


def mapbox_size(SW, SH):
    """The back map's size in 0.1 mm units (matches .mapbox)."""
    ky = SH / A5[1]
    return round((SW - 12.5) * 10), round((SH - 46 * ky) * 10)


def subtitle_html(text):
    """'Паспорт\nпокорителя городов': the first line as the title, the rest smaller underneath."""
    if not text:
        return ""
    first, *rest = text.split("\n")
    more = f'<div class="sub2">{esc(" ".join(rest))}</div>' if rest else ""
    return f'<div class="subtitle">{esc(first)}{more}</div>'


def crop_marks(SW, SH):
    """Thin corner marks just outside the face (they stay clear of the bleed)."""
    L, T, R, B = (210 - SW) / 2, (297 - SH) / 2, (210 + SW) / 2, (297 + SH) / 2
    gap, n, w = BLEED + 1, 6, 0.15
    out = []
    for x in (L, R):
        for y in (T, B):
            dy = -gap - n if y == T else gap
            dx = -gap - n if x == L else gap
            out.append(f'<div class="crop" style="left:{x - w / 2:.2f}mm;top:{y + dy:.2f}mm;width:{w}mm;height:{n}mm"></div>')
            out.append(f'<div class="crop" style="left:{x + dx:.2f}mm;top:{y - w / 2:.2f}mm;width:{n}mm;height:{w}mm"></div>')
    return "".join(out)


def build(cfg, folder, chrome):
    separate = bool(cfg.get("size"))
    SW, SH = (float(x) for x in cfg["size"]) if separate else A5
    k = min(SW / A5[0], SH / A5[1])
    icons = cfg.get("icons", ["✈️", "🧭", "🚂", "⛵", "🏰", "🗼", "📷", "🎒"])
    figure = folder / cfg.get("figure", "kid-contour.svg")
    if figure.suffix == ".svg" and figure.exists():  # line portrait: head and shoulders, standing on the bottom edge
        cls = "head" if "contour" in figure.name else "portrait"
        kid = f'<img class="{cls}" src="data:image/svg+xml;base64,{base64.b64encode(figure.read_bytes()).decode()}">'
    elif cfg.get("figure_kind") == "drawing" and figure.exists():  # a finished drawing on white paper
        kid = f'<img class="drawing" src="{faded_uri(figure)}">'
    else:
        kid = f'<img class="kid" src="{data_uri(figure)}">' if figure.exists() else ""
    world = path_d(countries("110m"), lambda lo, la: (100 + equal_earth(lo, la)[0] * 37, 60 + equal_earth(lo, la)[1] * 37))
    # the faint world map: scaled so the land runs from edge to edge, centred where the A5 design had it
    # (measured on the continents and big islands; specks of islands may run off the edge)
    big = []
    for ring in world.split("M")[1:]:
        pts = [tuple(map(float, q)) for q in re.findall(r"(-?[\d.]+),(-?[\d.]+)", ring)]
        if pts and max(x for x, _ in pts) - min(x for x, _ in pts) > 4:
            big += pts
    x0, x1 = min(x for x, _ in big), max(x for x, _ in big)
    y0, y1 = min(y for _, y in big), max(y for _, y in big)
    mk = SW / (x1 - x0)                                             # mm per map unit
    mid = 0.415 * SH                                                # the land's vertical centre: clear of a big title
    bg = f"left:{-x0 * mk:.2f}mm;top:{mid - (y0 + y1) / 2 * mk:.2f}mm;width:{200 * mk:.2f}mm;height:{110 * mk:.2f}mm"
    front = f'''<svg class="bgmap" style="{bg}" viewBox="0 0 200 110"><path d="{world}" fill="{RUST}"/></svg>
<svg class="route" viewBox="0 0 150 60"><path d="M8,52 C40,8 90,0 140,22" fill="none" stroke="{RUST}" stroke-width=".9" stroke-dasharray="2.4,2"/><text x="67.3" y="12.3" font-size="11" text-anchor="middle" dominant-baseline="central" transform="rotate(33 67.3 12.3)">✈️</text></svg>
<div class="name">{esc(cfg["name"].upper())}</div>{subtitle_html(cfg.get("subtitle", ""))}<div class="compass">{compass(f"{30 * k:.1f}mm")}</div>
{"".join(f'<div class="stamp s{i+1}">{esc(c)}</div>' for i, c in enumerate(icons[2:6]))}
{kid}'''
    motto = "<br>".join(esc(l) for l in cfg.get("motto", "").split("\n"))
    BW, BH = (float(x) for x in cfg.get("back_size") or (SW, SH))
    back = f'<div class="motto">{motto}</div><div class="mapbox">{back_map(cfg, *mapbox_size(BW, BH))}</div>'
    front_div = f'<div class="side front{" titled" if cfg.get("subtitle") else ""}">{front}</div>'
    back_div = f'<div class="side back">{back}</div>'
    if separate:  # page 1 the front, page 2 the back, each centred on A4 with bleed and crop marks
        sheets = f'<div class="sheet"><div class="bleed"></div>{front_div}{crop_marks(SW, SH)}</div>' + placed(BW, BH, "back", back)
        if cfg.get("spine"):  # page 3: the spine strip, the front's title reading upwards
            sp = cfg["spine"]  # a width, or [width, height] when the spine pocket is shorter or taller than the faces
            spw, sph = (float(sp[0]), float(sp[1])) if isinstance(sp, list) else (float(sp), SH)
            first, *rest = (cfg.get("subtitle") or cfg["name"]).split("\n")
            t2 = f'<span class="t2">{esc(" ".join(rest))}</span>' if rest else ""
            sheets += placed(spw, sph, "spine", f'<div class="icon">{esc(icons[1])}</div><div class="title">{esc(first)}{t2}</div><div class="icon">{esc(icons[0])}</div>')
    else:
        sheets = f'<div class="sheet">{back_div}{front_div}</div>'
    doc = f"""<!doctype html><html lang="{esc(cfg.get('lang', 'ru'))}"><head><meta charset="utf-8"><title>{esc(cfg['name'])}</title>
<link rel="stylesheet" href="{FONTS}"><style>{make_css(SW, SH, separate)}{back_css(BW, BH) if separate else ""}</style></head><body>
{sheets}</body></html>"""
    h, pdf, png = (folder / f"cover.{e}" for e in ("html", "pdf", "png"))
    h.write_text(doc, encoding="utf-8")
    with tempfile.TemporaryDirectory() as prof:
        base = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", f"--user-data-dir={prof}", "--virtual-time-budget=15000"]
        subprocess.run(base + ["--no-pdf-header-footer", f"--print-to-pdf={pdf}", h.as_uri()], capture_output=True, timeout=180)
        size = f"794,{1123 * (2 + bool(cfg.get('spine')))}" if separate else "1123,794"  # the A4 pages one under the other
        subprocess.run(base + [f"--window-size={size}", f"--screenshot={png}", h.as_uri()], capture_output=True, timeout=180)
    if not pdf.exists():
        sys.exit("PDF render failed")
    print(f"Wrote {pdf} and {png.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cover_json")
    a = ap.parse_args()
    src = Path(a.cover_json).resolve()
    cfg = json.loads(src.read_text(encoding="utf-8"))
    chrome = next((shutil.which(n) for n in [os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"] if n and shutil.which(n)), None)
    if not chrome:
        sys.exit("No Chrome/Chromium found; set CHROME=/path/to/chrome")
    build(cfg, src.parent, chrome)


if __name__ == "__main__":
    main()
