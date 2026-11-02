#!/usr/bin/env python3
"""Render round zone-capture stickers for a quest onto one A4 sheet: <city>-stickers.pdf.

Usage:
    python3 build_stickers.py path/to/quest.json [--big 3] [--small 2]

Print on A4 sticker paper and cut along the thin circles. Every zone gets a row:
`--big` stickers of 18 mm (they cover the "sticker" circle on the zone card; a spare goes
in the collection) and `--small` stickers of 10 mm (for the zone on the city map).
Black and white: ring, "CLAIMED" on top, the zone number below, the zone emoji in grey.
"""
import argparse
import json
import tempfile
from pathlib import Path

from build_quest import LABELS, esc, find_chrome, run_chrome, set_language

BIG, SMALL, GAP = 18, 10, 4  # mm


def big_sticker(zi, z, uid):
    """An 18 mm sticker: double ring, the claimed word along the top, zone number along the bottom."""
    r = BIG / 2
    top, bottom = f"t{uid}", f"b{uid}"
    return f"""<svg class="st" viewBox="0 0 {BIG} {BIG}" style="width:{BIG}mm;height:{BIG}mm">
  <defs>
    <path id="{top}" d="M {r-5.9},{r} A 5.9 5.9 0 0 1 {r+5.9},{r}"/>
    <path id="{bottom}" d="M {r-7.3},{r} A 7.3 7.3 0 0 0 {r+7.3},{r}"/>
  </defs>
  <circle class="cut" cx="{r}" cy="{r}" r="{r-.05}"/>
  <circle class="ring" cx="{r}" cy="{r}" r="{r-.7}"/>
  <circle class="ring2" cx="{r}" cy="{r}" r="{r-3.7}"/>
  <text class="arc"><textPath href="#{top}" startOffset="50%">{esc(LABELS['claimed'])}</textPath></text>
  <text class="arc"><textPath href="#{bottom}" startOffset="50%">★ {esc(LABELS['zone'].upper())} {zi} ★</textPath></text>
  <text class="emoji" x="{r}" y="{r+1.9}">{esc(z.get('emoji', '🏳️'))}</text>
</svg>"""


def small_sticker(zi):
    """A 10 mm sticker for the city map: a black disc with the zone number, like the map's badges."""
    r = SMALL / 2
    return f"""<svg class="st" viewBox="0 0 {SMALL} {SMALL}" style="width:{SMALL}mm;height:{SMALL}mm">
  <circle class="cut" cx="{r}" cy="{r}" r="{r-.05}"/>
  <circle class="disc" cx="{r}" cy="{r}" r="{r-.6}"/>
  <text class="num" x="{r}" y="{r+1.9}">{zi}</text>
</svg>"""


CSS = f"""
@page {{ size: A4 portrait; margin: 10mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Noto Sans", "DejaVu Sans", Arial, sans-serif; }}
.row {{ display: flex; align-items: center; gap: {GAP}mm; height: {BIG + GAP}mm; }}
.name {{ width: 52mm; font-size: 8pt; color: #555; }}
.name b {{ color: #000; }}
.cut {{ fill: #fff; stroke: #999; stroke-width: .12; }}
.ring {{ fill: none; stroke: #000; stroke-width: .8; }}
.ring2 {{ fill: none; stroke: #000; stroke-width: .25; }}
.arc {{ font-size: 2.1px; font-weight: bold; letter-spacing: .15px; text-anchor: middle; fill: #000; }}
.emoji {{ font-size: 5.6px; text-anchor: middle; filter: grayscale(1) brightness(.8) contrast(1.6); }}
.disc {{ fill: #000; }}
.num {{ font-size: 5.4px; font-weight: bold; text-anchor: middle; fill: #fff; }}
.hint {{ font-size: 7pt; color: #777; margin-top: 2mm; }}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quest")
    ap.add_argument("--big", type=int, default=3, help="18 mm stickers per zone")
    ap.add_argument("--small", type=int, default=2, help="10 mm stickers per zone")
    a = ap.parse_args()
    path = Path(a.quest)
    q = json.loads(path.read_text())
    set_language(q)
    rows = []
    for zi, z in enumerate(q["zones"], 1):
        stickers = [big_sticker(zi, z, f"{zi}_{k}") for k in range(a.big)] + [small_sticker(zi) for _ in range(a.small)]
        rows.append(f'<div class="row"><div class="name"><b>{zi}</b> · {esc(z["name"])}</div>{"".join(stickers)}</div>')
    if len(q["zones"]) * (BIG + GAP) > 277:
        print("WARNING: too many zones for one A4 sheet; the rest spills onto a second page")
    hint = "Печатать на A4 бумаге-наклейке в 100 % масштабе, вырезать по тонким кругам." if q.get("language", "ru") == "ru" \
        else "Print on A4 sticker paper at 100 % scale; cut along the thin circles."
    doc = f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(rows)}<div class="hint">{hint}</div></body></html>'
    city = path.parent.name
    pdf = path.parent / f"{city}-stickers.pdf"
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
