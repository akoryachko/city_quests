#!/usr/bin/env python3
"""Render round zone-capture stickers for one or more quests onto A4: a PDF for sticker paper.

Usage:
    python3 build_stickers.py path/to/quest.json [more/quest.json …] [--big 3] [--small 2] [--out FILE]

Print in colour on A4 sticker paper at 100 % scale and cut along the thin grey circles.
Every zone gets a block: `--big` stickers of 18 mm (they cover the "sticker" circle on the
zone card; a spare goes in the collection) and `--small` stickers of 10 mm (for the zone on
the city map). Each zone has its own colour; the big sticker shows "CLAIMED" on top, the zone
number below and the zone emoji in the middle. Several quests share the sheet to save paper.
Default output: <folder>/<city>-stickers.pdf for one quest, ./stickers.pdf for several.
"""
import argparse
import json
import tempfile
from pathlib import Path

from build_quest import LABELS, esc, find_chrome, run_chrome, set_language

BIG, SMALL, GAP = 18, 10, 3  # mm
# (ring, tint) per zone: saturated enough to tell 12 zones apart, dark enough for white digits
COLOURS = [("#1f6fb2", "#dcebf7"), ("#d1495b", "#f9dfe2"), ("#e0a100", "#fbf0cc"), ("#2e9e5b", "#dbf1e3"),
           ("#7b4fb8", "#ebe2f6"), ("#e3702b", "#fbe5d6"), ("#138a8a", "#d5eeee"), ("#b5397f", "#f5dcea"),
           ("#5b7f1e", "#e7efd6"), ("#3d4fb5", "#dfe2f6"), ("#a0522d", "#f2e2d8"), ("#2f8fcf", "#daedf8")]


def big_sticker(zi, z, uid):
    """An 18 mm sticker: coloured ring, the claimed word along the top, zone number along the bottom."""
    r = BIG / 2
    ring, tint = COLOURS[(zi - 1) % len(COLOURS)]
    top, bottom = f"t{uid}", f"b{uid}"
    return f"""<svg class="st" viewBox="0 0 {BIG} {BIG}" style="width:{BIG}mm;height:{BIG}mm">
  <defs>
    <path id="{top}" d="M {r-5.9},{r} A 5.9 5.9 0 0 1 {r+5.9},{r}"/>
    <path id="{bottom}" d="M {r-7.3},{r} A 7.3 7.3 0 0 0 {r+7.3},{r}"/>
  </defs>
  <circle class="cut" cx="{r}" cy="{r}" r="{r-.05}"/>
  <circle cx="{r}" cy="{r}" r="{r-.4}" fill="{ring}"/>
  <circle cx="{r}" cy="{r}" r="{r-3.5}" fill="{tint}" stroke="#fff" stroke-width=".35"/>
  <text class="arc"><textPath href="#{top}" startOffset="50%">{esc(LABELS['claimed'])}</textPath></text>
  <text class="arc"><textPath href="#{bottom}" startOffset="50%">★ {esc(LABELS['zone'].upper())} {zi} ★</textPath></text>
  <text class="emoji" x="{r}" y="{r+1.9}">{esc(z.get('emoji', '🏳️'))}</text>
</svg>"""


def small_sticker(zi):
    """A 10 mm sticker for the city map: a disc in the zone's colour with its number."""
    r = SMALL / 2
    ring, _ = COLOURS[(zi - 1) % len(COLOURS)]
    return f"""<svg class="st" viewBox="0 0 {SMALL} {SMALL}" style="width:{SMALL}mm;height:{SMALL}mm">
  <circle class="cut" cx="{r}" cy="{r}" r="{r-.05}"/>
  <circle cx="{r}" cy="{r}" r="{r-.4}" fill="{ring}" stroke="#fff" stroke-width=".3"/>
  <text class="num" x="{r}" y="{r+1.9}">{zi}</text>
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
.num {{ font-size: 5.4px; font-weight: bold; text-anchor: middle; fill: #fff; }}
.hint {{ font-size: 7pt; color: #777; margin-top: 3mm; }}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quests", nargs="+")
    ap.add_argument("--big", type=int, default=3, help="18 mm stickers per zone")
    ap.add_argument("--small", type=int, default=2, help="10 mm stickers per zone")
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
        sections.append(f'<h2>{esc(q.get("title", q.get("city", "")))}</h2><div class="grid">{"".join(blocks)}</div>')
    hint = "Печатать в цвете на A4 бумаге-наклейке в 100 % масштабе, вырезать по тонким серым кругам." if lang == "ru" \
        else "Print in colour on A4 sticker paper at 100 % scale; cut along the thin grey circles."
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
