#!/usr/bin/env python3
"""Render round zone-capture stickers for one or more quests onto A4: a PDF for sticker paper.

Usage:
    python3 build_stickers.py path/to/quest.json [more/quest.json …] [--big 3] [--small 2] [--medal 1] [--out FILE]

Print in colour on A4 sticker paper at 100 % scale and cut along the thin grey circles.
Every zone gets a block: `--big` stickers of 18 mm (they cover the "sticker" circle on the
zone card; a spare goes in the collection) and `--small` stickers of 10 mm (for the zone on
the city map). Each zone has its own colour, the same as in the colour booklet; the big sticker shows "CLAIMED" on top, the zone
number below and the zone emoji in the middle. Every quest also gets `--medal` 32 mm city stickers
for the medal circle on the certificate: a gold medal, "CONQUEROR OF <city>" around it, a dot
for every zone in its colour and the cover emoji under a crown. And `--rank-medal` pairs of 30 mm stickers
for a real gold sports medal (the empty 30 mm disc on its front and back): polished gold to the edge with
the text engraved, front = the top rank of the city ("АДМИРАЛ / АМСТЕРДАМА") around an emblem (anchor for
sea ranks, else a crown; "medal_emblem" in quest.json overrides: anchor, crown, star), back = "CONQUEROR /
OF <city>", a compass rose and the zone count. Several quests share the sheet to save paper; to print only
the medals for several cities: --big 0 --small 0 --medal 0.
Default output: <folder>/<city>-stickers.pdf for one quest, ./stickers.pdf for several.
"""
import argparse
import json
import math
import tempfile
from pathlib import Path

from build_quest import LABELS, ZONE_COLOURS, esc, find_chrome, run_chrome, set_language, tint

BIG, SMALL, MEDAL, GAP = 18, 10, 32, 3  # mm
RANK = 30      # mm: the empty disc on a standard 50 mm sports medal (front and back)
BLEED = 0.6    # mm of gold beyond the cut, so a slightly-off cut never shows white

# the gold of a polished medal, and its "engraved" ink
GOLD = [("0", "#fde58a"), ("0.3", "#f3c83a"), ("0.62", "#e8b41f"), ("1", "#f7d660")]
ENGRAVE, SHINE = "#8c6408", "#fff1b3"
MEDAL_TEXT = {
    "ru": {"conqueror": "ПОКОРИТЕЛЬ", "zones": "ЗОН"},
    "en": {"conqueror": "CONQUEROR", "zones": "ZONES"},
}


def big_sticker(zi, z, uid):
    """An 18 mm sticker: coloured ring, the claimed word along the top, zone number along the bottom."""
    r = BIG / 2
    ring = ZONE_COLOURS[(zi - 1) % len(ZONE_COLOURS)]
    top, bottom = f"t{uid}", f"b{uid}"
    return f"""<svg class="st" viewBox="0 0 {BIG} {BIG}" style="width:{BIG}mm;height:{BIG}mm">
  <defs>
    <path id="{top}" d="M {r-5.9},{r} A 5.9 5.9 0 0 1 {r+5.9},{r}"/>
    <path id="{bottom}" d="M {r-7.3},{r} A 7.3 7.3 0 0 0 {r+7.3},{r}"/>
  </defs>
  <circle class="cut" cx="{r}" cy="{r}" r="{r-.05}"/>
  <circle cx="{r}" cy="{r}" r="{r-.4}" fill="{ring}"/>
  <circle cx="{r}" cy="{r}" r="{r-3.5}" fill="{tint(ring)}" stroke="#fff" stroke-width=".35"/>
  <text class="arc"><textPath href="#{top}" startOffset="50%">{esc(LABELS['claimed'])}</textPath></text>
  <text class="arc"><textPath href="#{bottom}" startOffset="50%">★ {esc(LABELS['zone'].upper())} {zi} ★</textPath></text>
  <text class="emoji" x="{r}" y="{r+1.9}">{esc(z.get('emoji', '🏳️'))}</text>
</svg>"""


def small_sticker(zi):
    """A 10 mm sticker for the city map: a disc in the zone's colour with its number."""
    r = SMALL / 2
    ring = ZONE_COLOURS[(zi - 1) % len(ZONE_COLOURS)]
    return f"""<svg class="st" viewBox="0 0 {SMALL} {SMALL}" style="width:{SMALL}mm;height:{SMALL}mm">
  <circle class="cut" cx="{r}" cy="{r}" r="{r-.05}"/>
  <circle cx="{r}" cy="{r}" r="{r-.4}" fill="{ring}" stroke="#fff" stroke-width=".3"/>
  <text class="num" x="{r}" y="{r+1.9}">{zi}</text>
</svg>"""


def medal_sticker(q, uid):
    """A 32 mm sticker for the certificate's medal circle: the whole city claimed."""
    r = MEDAL / 2
    n = len(q["zones"])
    city = q.get("city_local_name") or q["city"] if q.get("language", "ru") == "ru" else q["city"]
    top, bottom = f"mt{uid}", f"mb{uid}"
    dots = "".join(
        f'<circle cx="{r + 9.7 * math.sin(2 * math.pi * k / n):.2f}" cy="{r - 9.7 * math.cos(2 * math.pi * k / n):.2f}" r="1"'
        f' fill="{ZONE_COLOURS[k % len(ZONE_COLOURS)]}" stroke="#fff" stroke-width=".25"/>'
        for k in range(n))
    emoji = q.get("cover", {}).get("emoji", "🏰")
    size = 8 if len(emoji) <= 2 else 3.6
    return f"""<svg class="st" viewBox="0 0 {MEDAL} {MEDAL}" style="width:{MEDAL}mm;height:{MEDAL}mm">
  <defs>
    <path id="{top}" d="M {r-12},{r} A 12 12 0 0 1 {r+12},{r}"/>
    <path id="{bottom}" d="M {r-14.1},{r} A 14.1 14.1 0 0 0 {r+14.1},{r}"/>
    <radialGradient id="g{uid}" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#f6d66b"/><stop offset="1" stop-color="#b7860f"/></radialGradient>
  </defs>
  <circle class="cut" cx="{r}" cy="{r}" r="{r-.05}"/>
  <circle cx="{r}" cy="{r}" r="{r-.4}" fill="url(#g{uid})"/>
  <circle cx="{r}" cy="{r}" r="{r-1.1}" fill="none" stroke="#fff6d8" stroke-width=".25" stroke-dasharray=".5 .5"/>
  <circle cx="{r}" cy="{r}" r="11.3" fill="#fff8e1" stroke="#8a6300" stroke-width=".4"/>
  <text class="marc"><textPath href="#{top}" startOffset="50%">{esc(LABELS['conqueror'])}</textPath></text>
  <text class="marc"><textPath href="#{bottom}" startOffset="50%">★ {esc(city.upper())} ★</textPath></text>
  {dots}
  <text class="emoji" x="{r}" y="{r-3}" style="font-size:4.6px">👑</text>
  <text class="emoji" x="{r}" y="{r+size*.38+1.6}" style="font-size:{size}px">{esc(emoji)}</text>
  <text class="mnum" x="{r}" y="{r+7.6}">{n}/{n}</text>
</svg>"""


def top_rank(q):
    ranks = q.get("rules", {}).get("ranks") or []
    return max(ranks, key=lambda r: r.get("min", 0))["name"] if ranks else LABELS["conqueror"]


def emblem(kind):
    """Monochrome emblems drawn as engraving, centred on 0,0, about 13 units tall."""
    if kind == "anchor":
        return ('<circle cx="0" cy="-5.6" r="1.25" fill="none"/><path d="M0,-4.35V6.2M-3.1,-2.7H3.1"/>'
                '<path d="M-5,2.2Q-4.6,6.6 0,6.9Q4.6,6.6 5,2.2" fill="none"/><path d="M-5,2.2l-1.1,1.6l2.3,-.1zM5,2.2l1.1,1.6l-2.3,-.1z"/>')
    if kind == "crown":
        return '<path d="M-5.5,3.5L-6,-3L-2.8,0L0,-4.8L2.8,0L6,-3L5.5,3.5Z" fill="none"/><path d="M-5.5,5.6H5.5"/><circle cx="0" cy="-6.2" r=".9"/>'
    return '<path d="M0,-6L1.8,-1.9L6.3,-1.9L2.7,0.9L4,5.3L0,2.7L-4,5.3L-2.7,0.9L-6.3,-1.9L-1.8,-1.9Z" fill="none"/>'


def rose():
    pts = []
    for i in range(8):
        a = math.radians(i * 45)
        L = 6.2 if i % 2 == 0 else 3.8
        tip = (L * math.sin(a), -L * math.cos(a))
        l = (1.1 * math.sin(a - math.pi / 2), -1.1 * math.cos(a - math.pi / 2))
        pts.append(f"M0,0L{l[0]:.2f},{l[1]:.2f}L{tip[0]:.2f},{tip[1]:.2f}Z")
    return f'<circle r="7" fill="none" stroke-dasharray=".5 .45"/><path d="{"".join(pts)}" fill="none"/><circle r=".9"/>'


def engraved(body, uid, x, y, scale=1.0):
    """Draw body twice: a light highlight just below-right, then the dark engraving: looks stamped into the gold."""
    g = f'<g transform="translate({x},{y}) scale({scale})">{body}</g>'
    return (f'<g transform="translate(.16,.16)" fill="{SHINE}" stroke="{SHINE}" stroke-width=".55" stroke-linecap="round" stroke-linejoin="round">{g}</g>'
            f'<g fill="{ENGRAVE}" stroke="{ENGRAVE}" stroke-width=".55" stroke-linecap="round" stroke-linejoin="round">{g}</g>')


def rank_medal(q, uid, side):
    """A 30 mm sticker for the empty disc of a gold sports medal: polished gold to the edge, text and emblem
    engraved, a soft darker rim like the shadow of the medal's raised edge. side: front (top rank + city)
    or back (city conquered, compass rose, zones)."""
    R = RANK / 2 + BLEED
    c = R
    lang = q.get("language", "ru")
    T = MEDAL_TEXT.get(lang, MEDAL_TEXT["en"])
    city_gen = (q.get("city_local_name") or q["city"]) if lang == "ru" else q["city"]
    n = len(q["zones"])
    if side == "front":
        rank = top_rank(q)
        top_txt = rank.upper()
        bottom_txt = city_gen.upper() if lang == "ru" else f"OF {q['city'].upper()}"
        kind = q.get("medal_emblem") or ("anchor" if any(w in rank.lower() for w in ("адмирал", "капитан", "admiral", "captain")) else "crown")
        centre = engraved(emblem(kind), uid, c, c + 0.3, 0.95)
        stars = engraved('<path d="M0,-1L.3,-.3L1,-.3L.45,.15L.65,.9L0,.45L-.65,.9L-.45,.15L-1,-.3L-.3,-.3Z"/>', uid, c - 11.6, c + 0.2) + \
            engraved('<path d="M0,-1L.3,-.3L1,-.3L.45,.15L.65,.9L0,.45L-.65,.9L-.45,.15L-1,-.3L-.3,-.3Z"/>', uid, c + 11.6, c + 0.2)
    else:
        top_txt = T["conqueror"]
        bottom_txt = city_gen.upper() if lang == "ru" else f"OF {q['city'].upper()}"
        centre = engraved(rose(), uid, c, c - 2.3, 0.62) + \
            f'<text x="{c+.14}" y="{c+5.94}" class="eng shine" style="font-size:2px">{n}/{n} {T["zones"]}</text>' \
            f'<text x="{c}" y="{c+5.8}" class="eng" style="font-size:2px">{n}/{n} {T["zones"]}</text>'
        stars = ""
    fs_top = min(3.6, 44 / max(6, len(top_txt)))
    fs_bot = min(3.2, 44 / max(6, len(bottom_txt)))
    ra, rb = 11.2, 12.4
    arcs = ""
    for txt, fs, d, off in ((top_txt, fs_top, f"M {c-ra},{c} A {ra} {ra} 0 0 1 {c+ra},{c}", 0),
                            (bottom_txt, fs_bot, f"M {c-rb},{c} A {rb} {rb} 0 0 0 {c+rb},{c}", 1)):
        pid = f"rm{uid}{side}{off}"
        arcs += f'<path id="{pid}" d="{d}" fill="none"/>'
        for cls, dx in (("eng shine", .16), ("eng", 0)):
            arcs += f'<text class="{cls}" transform="translate({dx},{dx})" style="font-size:{fs:.2f}px"><textPath href="#{pid}" startOffset="50%">{esc(txt)}</textPath></text>'
    stops = "".join(f'<stop offset="{o}" stop-color="{col}"/>' for o, col in GOLD)
    return f"""<svg class="st" viewBox="0 0 {2*R} {2*R}" style="width:{2*R}mm;height:{2*R}mm">
  <defs>
    <linearGradient id="rg{uid}{side}" x1="0" y1="0" x2="1" y2="1">{stops}</linearGradient>
    <radialGradient id="rr{uid}{side}" cx="50%" cy="50%" r="50%"><stop offset=".86" stop-color="#a87a05" stop-opacity="0"/><stop offset=".97" stop-color="#a87a05" stop-opacity=".45"/><stop offset="1" stop-color="#a87a05" stop-opacity=".6"/></radialGradient>
    <radialGradient id="rs{uid}{side}" cx="32%" cy="26%" r="45%"><stop offset="0" stop-color="#fff8d0" stop-opacity=".7"/><stop offset="1" stop-color="#fff8d0" stop-opacity="0"/></radialGradient>
  </defs>
  <circle cx="{c}" cy="{c}" r="{R}" fill="url(#rg{uid}{side})"/>
  <circle cx="{c}" cy="{c}" r="{R}" fill="url(#rs{uid}{side})"/>
  <circle cx="{c}" cy="{c}" r="{R}" fill="url(#rr{uid}{side})"/>
  <circle cx="{c}" cy="{c}" r="9.3" fill="none" stroke="{ENGRAVE}" stroke-opacity=".55" stroke-width=".25"/>
  <circle cx="{c+.12}" cy="{c+.12}" r="9.3" fill="none" stroke="{SHINE}" stroke-opacity=".8" stroke-width=".2"/>
  {arcs}{stars}{centre}
  <circle cx="{c}" cy="{c}" r="{RANK/2}" fill="none" stroke="#fff" stroke-opacity=".9" stroke-width=".08" stroke-dasharray=".6 .6"/>
</svg>"""


CSS = f"""
@page {{ size: A4 portrait; margin: 9mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Noto Sans", "DejaVu Sans", Arial, sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
h2 {{ font-size: 9pt; margin: 1mm 0 1mm; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; column-gap: 6mm; row-gap: 1.5mm; }}
.zone {{ break-inside: avoid; }}
.name {{ font-size: 6.5pt; color: #444; white-space: nowrap; overflow: hidden; }}
.row {{ display: flex; align-items: center; gap: {GAP}mm; }}
.cut {{ fill: #fff; stroke: #aaa; stroke-width: .12; }}
.arc {{ font-size: 2.1px; font-weight: bold; letter-spacing: .15px; text-anchor: middle; fill: #fff; }}
.emoji {{ font-size: 5.6px; text-anchor: middle; }}
.marc {{ font-size: 2.6px; font-weight: bold; letter-spacing: .2px; text-anchor: middle; fill: #4a3200; }}
.mnum {{ font-size: 2.3px; font-weight: bold; text-anchor: middle; fill: #8a6300; }}
.num {{ font-size: 5.4px; font-weight: bold; text-anchor: middle; fill: #fff; }}
.eng {{ font-family: "DejaVu Serif", "Noto Serif", serif; font-weight: bold; letter-spacing: .25px; text-anchor: middle; fill: {ENGRAVE}; }}
.eng.shine {{ fill: {SHINE}; }}
.hint {{ font-size: 7pt; color: #777; margin-top: 3mm; }}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quests", nargs="+")
    ap.add_argument("--big", type=int, default=3, help="18 mm stickers per zone")
    ap.add_argument("--small", type=int, default=2, help="10 mm stickers per zone")
    ap.add_argument("--medal", type=int, default=1, help="32 mm city stickers per quest")
    ap.add_argument("--rank-medal", type=int, default=1, help="pairs (front + back) of 30 mm stickers for a gold sports medal, per quest")
    ap.add_argument("--out", help="PDF to write")
    a = ap.parse_args()
    sections, lang = [], "ru"
    for qp in a.quests:
        path = Path(qp)
        q = json.loads(path.read_text())
        set_language(q)
        lang = q.get("language", "ru")
        blocks = []
        for zi, z in enumerate(q["zones"], 1):
            st = [big_sticker(zi, z, f"{path.parent.name}{zi}_{k}") for k in range(a.big)] + [small_sticker(zi) for _ in range(a.small)]
            blocks.append(f'<div class="zone"><div class="name"><b>{zi}</b> · {esc(z["name"])}</div><div class="row">{"".join(st)}</div></div>')
        medals = "".join(medal_sticker(q, f"{path.parent.name}_{k}") for k in range(a.medal))
        if medals:
            blocks.append(f'<div class="zone"><div class="name">🏆 {esc(LABELS["certificate"])}</div><div class="row">{medals}</div></div>')
        pairs = "".join(rank_medal(q, f"{path.parent.name}_{k}", side) for k in range(a.rank_medal) for side in ("front", "back"))
        if pairs:
            label = "🏅 медаль: лицевая сторона и оборот" if lang == "ru" else "🏅 medal: front and back"
            blocks.append(f'<div class="zone"><div class="name">{label} · {esc(top_rank(q))}</div><div class="row">{pairs}</div></div>')
        sections.append(f'<h2>{esc(q.get("title", q.get("city", "")))}</h2><div class="grid">{"".join(blocks)}</div>')
    hint = ("Печатать в цвете на A4 бумаге-наклейке в 100 % масштабе, вырезать по тонким серым кругам; "
            "золотые наклейки для медали — по белому пунктиру (30 мм), золото чуть выходит за линию.") if lang == "ru" \
        else ("Print in colour on A4 sticker paper at 100 % scale; cut along the thin grey circles; "
              "the gold medal stickers along the white dotted line (30 mm): the gold runs a little past it.")
    doc = f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(sections)}<div class="hint">{hint}</div></body></html>'
    first = Path(a.quests[0])
    pdf = Path(a.out) if a.out else (first.parent / f"{first.parent.name}-stickers.pdf" if len(a.quests) == 1 else Path("stickers.pdf"))
    pdf.unlink(missing_ok=True)
    chrome = find_chrome()
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "stickers.html"
        html_path.write_text(doc)
        run_chrome(chrome, ["--no-pdf-header-footer", f"--print-to-pdf={pdf.resolve()}", html_path.as_uri()], Path(tmp) / "profile")
    if not pdf.exists():
        raise SystemExit("PDF not written")
    print(f"Wrote {pdf}")


if __name__ == "__main__":
    main()
