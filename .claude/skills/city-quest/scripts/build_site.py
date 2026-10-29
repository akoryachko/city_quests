#!/usr/bin/env python3
"""Render every city quest into a static website for reading on a phone during the walk.

Usage:
    python3 build_site.py [--root DIR] [--out DIR]

--root is the folder that holds one sub-folder per city with a quest.json
(default: the current folder). --out is where the site goes (default:
<root>/site). A city's translations (quest.en.json next to quest.json) become
the same pages in that language. Page layout, relative links only, so the
site works from any sub-path, e.g. example.com/quests/:

    index.html                        opens the last used (or main) language
    maps/<city>/                      map pictures, shared by all languages
    <lang>/index.html                 the cities
    <lang>/<city>/index.html          cover, overview map, zone tiles (kid)
    <lang>/<city>/parent/             day plans, bookings, shopping, tips
    <lang>/<city>/hunt/               the city-wide hunt (campaigns with a hunt)
    <lang>/<city>/zone-N/             the zone's challenges and map (kid)
    <lang>/<city>/zone-N/parent/      the zone's answers, stories and bookings

Every page has a sticky bar with the way back up, a kid/parent switch for the
same zone, a language switch and a rules button that opens the rules over the
page without losing the scroll position. Places and map pins open Google Maps.
Cards come from build_quest.py, so the site says the same as the booklet. Maps
and pin positions are the files build_quest.py writes next to quest.json; run
it first for a city whose maps are missing.

The out folder is wiped and rebuilt, but only when it is empty or was made by
this script (it carries a .city-quests-site marker).
"""
import argparse
import copy
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_quest as bq  # noqa: E402
from build_quest import LABELS, TYPES, esc  # noqa: E402

MARKER = ".city-quests-site"

WEB_LABELS = {
    "ru": {
        "cities": "Городские квесты",
        "kid": "🧒 Ребёнку",
        "parent": "👨‍👩‍👦 Родителям",
        "rules_btn": "📜 <span class=\"t\">Правила</span>",
        "zones": "Зоны",
        "all_answers": "Ответы по зонам",
        "no_map": "Карты нет: сначала запусти build_quest.py для этого города.",
    },
    "en": {
        "cities": "City quests",
        "kid": "🧒 Kid",
        "parent": "👨‍👩‍👦 Parents",
        "rules_btn": "📜 <span class=\"t\">Rules</span>",
        "zones": "Zones",
        "all_answers": "Answers per zone",
        "no_map": "No map yet: run build_quest.py for this city first.",
    },
}

WEB_CSS = r"""
:root { --bar: #111; --bg: #fafafa; }
body { background: var(--bg); font-size: 17px; }
main { max-width: 640px; margin: 0 auto; padding: 12px 12px 40px; }
.bar { position: sticky; top: 0; z-index: 10; background: var(--bar); color: #fff; display: flex; align-items: center; gap: 8px; padding: 8px 12px; flex-wrap: wrap; }
.bar a, .bar button { color: #fff; }
.crumbs { flex: 1; min-width: 0; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.crumbs a { text-decoration: none; opacity: .8; }
.crumbs a:hover { opacity: 1; text-decoration: underline; }
.btn { font: inherit; font-size: 15px; background: transparent; border: 1px solid #fff8; border-radius: 8px; padding: 5px 10px; cursor: pointer; text-decoration: none; white-space: nowrap; }
.switch { display: flex; border: 1px solid #fff8; border-radius: 8px; overflow: hidden; }
.switch a, .switch span { font-size: 14px; padding: 5px 9px; text-decoration: none; white-space: nowrap; }
.switch span { background: #fff; color: #111; font-weight: bold; }
@media (max-width: 560px) { .crumbs { flex-basis: 100%; white-space: normal; } .switch.side { flex: 1; } .switch.side a, .switch.side span { flex: 1; text-align: center; } .switch a, .switch span { padding: 5px 6px; font-size: 13px; } .btn .t { display: none; } }
/* the booklet cards, unfolded to the screen */
.card { width: auto; height: auto; padding: 0; margin: 0 0 14px; overflow: visible; }
.fit { height: auto; overflow: visible; border-width: 3px; border-radius: 16px; padding: 14px; font-size: 17px; background: #fff; }
.parent .fit { font-size: 16px; }
.box, .stamp { display: none; }
.boss { padding-right: 3mm; }
.track { flex-wrap: wrap; }
.track .dot { flex: none; width: 14px; height: 14px; min-width: 0; }
.zone-foot { margin-top: 10px; flex-wrap: wrap; }
.place a, .legend-stops a { text-decoration: none; border-bottom: 1px dotted #333; }
.mapwrap { position: relative; width: 100%; max-width: 450px; margin: 0 auto; }
.map-img { display: block; width: 100%; height: auto; border: 1px solid #999; border-radius: 10px; }
.pin { position: absolute; width: 30px; height: 30px; transform: translate(-50%, -50%); border-radius: 50%; }
.pin:hover, .pin:focus { outline: 3px solid #f90; }
.legend-stops { columns: 1; font-size: 15px; }
.cover .fit { justify-content: flex-start; }
.cover .team { display: none; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin: 0 0 14px; padding: 0; list-style: none; }
.tiles a { display: flex; flex-direction: column; gap: 2px; height: 100%; padding: 12px; background: #fff; border: 2px solid #333; border-radius: 12px; text-decoration: none; }
.tiles .te { font-size: 28px; }
.tiles .tn { font-size: 13px; color: #555; }
.tiles .tt { font-weight: bold; line-height: 1.2; }
.links { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 14px; }
.links a { padding: 8px 12px; border: 2px solid #333; border-radius: 10px; background: #fff; text-decoration: none; }
.pager { display: flex; justify-content: space-between; gap: 8px; margin-top: 8px; }
.pager a { flex: 1; padding: 10px; border: 2px solid #333; border-radius: 10px; background: #fff; text-decoration: none; text-align: center; }
.pager .next { text-align: right; }
.muted { color: #777; }
dialog { width: min(640px, 100vw); max-width: 100vw; max-height: 100vh; margin: 0 auto; padding: 0; border: 0; border-radius: 0 0 16px 16px; }
dialog::backdrop { background: rgba(0,0,0,.5); }
dialog .dhead { position: sticky; top: 0; display: flex; justify-content: flex-end; padding: 6px; background: #fff; }
dialog .dhead button { font: inherit; font-size: 20px; border: 0; background: #eee; border-radius: 8px; width: 40px; height: 40px; cursor: pointer; }
dialog .card { margin: 0 8px 8px; }
"""

WEB_JS = r"""
(function () {
  try { localStorage.setItem('cq-lang', document.documentElement.lang); } catch (e) {}
  var d = document.getElementById('rules');
  if (!d) return;
  document.querySelectorAll('[data-rules]').forEach(function (b) {
    b.addEventListener('click', function () { d.showModal(); d.scrollTop = 0; });
  });
  d.querySelector('.dhead button').addEventListener('click', function () { d.close(); });
  d.addEventListener('click', function (e) { if (e.target === d) d.close(); });
})();
"""


class Site:
    """Writes pages; every link is built from the site root, so pages at any depth link alike."""

    def __init__(self, out, langs):
        self.out, self.langs = out, langs  # langs: {lang: set of city slugs}

    def write(self, path, crumbs, body, *, lang, title, rules="", side=None, city=None):
        """A page at `path` (relative to the site root, '' for its index) with a sticky bar.

        crumbs: [(text, path or None)]; side: (kid path, parent path, on_parent) for the kid/parent switch;
        city: the slug whose translations the language switch offers (None: every language).
        """
        depth = len([p for p in path.split("/") if p])
        root = "../" * depth

        def url(p):
            return root + (p.strip("/") + "/" if p.strip("/") else "")

        W = WEB_LABELS[lang]
        trail = " › ".join(f'<a href="{url(h)}">{esc(t)}</a>' if h is not None else f"<b>{esc(t)}</b>" for t, h in crumbs)
        sw = ""
        if side:
            kid, parent, on_parent = side
            k = f'<span>{W["kid"]}</span>' if not on_parent else f'<a href="{url(kid)}">{W["kid"]}</a>'
            p = f'<span>{W["parent"]}</span>' if on_parent else f'<a href="{url(parent)}">{W["parent"]}</a>'
            sw = f'<nav class="switch side">{k}{p}</nav>'
        others = [lg for lg in self.langs if lg != lang and (city is None or city in self.langs[lg])]
        if others:
            rest = path.split("/", 1)[1] if "/" in path else ""
            items = [f"<span>{lang.upper()}</span>"] + [f'<a href="{url(lg + "/" + rest)}" hreflang="{lg}">{lg.upper()}</a>' for lg in others]
            sw += f'<nav class="switch">{"".join(items)}</nav>'
        btn = f'<button class="btn" data-rules>{W["rules_btn"]}</button>' if rules else ""
        dialog = f'<dialog id="rules"><div class="dhead"><button aria-label="close">✕</button></div>{rules}</dialog>' if rules else ""
        html = f"""<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><style>{bq.CSS}{WEB_CSS}</style></head><body>
<header class="bar"><div class="crumbs">{trail}</div>{sw}{btn}</header>
<main>{body.replace('src="@/', f'src="{root}').replace('href="@/', f'href="{root}')}</main>{dialog}<script>{WEB_JS}</script></body></html>"""
        dest = self.out / path / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")


def map_html(src, pins, alt, zone_href=None):
    """The map picture with a link on every pin: a stop opens Google Maps, a zone badge opens the zone."""
    links = []
    w, h = pins.get("w"), pins.get("h")
    for pin in pins.get("pins", []) if w and h else []:
        if "zone" in pin and zone_href:
            href, label = zone_href(pin["zone"]), str(pin["zone"])
        elif "lat" in pin:
            href, label = bq.gmaps(pin["lat"], pin["lon"]), pin["label"]
        else:
            continue
        links.append(f'<a class="pin" href="{href}" title="{esc(label)}" aria-label="{esc(label)}" '
                     f'style="left:{100 * pin["x"] / w:.2f}%;top:{100 * pin["y"] / h:.2f}%"></a>')
    return f'<div class="mapwrap"><img class="map-img" src="{src}" alt="{esc(alt)}" loading="lazy">{"".join(links)}</div>'


def pager(q, base, zi, suffix):
    """Previous / next zone links, staying on the kid or the parent side."""
    n = len(q["zones"])
    prev = f'<a href="@/{base}/zone-{zi - 1}/{suffix}">← {zi - 1}. {esc(q["zones"][zi - 2]["name"])}</a>' if zi > 1 else "<span></span>"
    nxt = f'<a class="next" href="@/{base}/zone-{zi + 1}/{suffix}">{zi + 1}. {esc(q["zones"][zi]["name"])} →</a>' if zi < n else "<span></span>"
    return f'<nav class="pager">{prev}{nxt}</nav>'


def build_city(site, q, lang, slug, maps, pins, prefix="quest"):
    """All pages of one city in one language.

    `maps`: published map names; `pins`: their pin positions; `prefix`: the map files' name (quest or quest.en).
    """
    W = WEB_LABELS[lang]
    city = q.get("city_local_name") or q["city"]
    title = q.get("title", city)
    rules = bq.rules_card(q)
    nav = int(q.get("rules", {}).get("nav_bonus") or 0)
    zones = q["zones"]
    base = f"{lang}/{slug}"
    page = dict(lang=lang, rules=rules, city=slug)
    home = (W["cities"], f"{lang}/")

    def zone_href(i):
        return f"@/{base}/zone-{i}/"

    def mapsrc(name):
        return f"@/maps/{slug}/{name}"

    # city home (kid)
    tiles = "".join(
        f'<li><a href="{zone_href(i)}"><span class="te">{esc(z.get("emoji", ""))}</span>'
        f'<span class="tn">{LABELS["zone"]} {i}</span><span class="tt">{esc(z["name"])}</span></a></li>'
        for i, z in enumerate(zones, 1)
    )
    hunt = q.get("hunt")
    links = f'<div class="links"><a href="@/{base}/hunt/">{esc(hunt.get("emoji", "🎯"))} {esc(hunt.get("title", ""))}</a></div>' if hunt else ""
    overview = ""
    if f"{prefix}-map.png" in maps:
        legend = bq.zone_legend(q) if q.get("campaign") else bq.stop_legend(q, links=True)
        pic = map_html(mapsrc(f"{prefix}-map.png"), pins.get(f"{prefix}-map.png", {}), title, zone_href)
        overview = bq.card(f"<h2>🗺️ {LABELS['map']}</h2>{pic}{legend}", "mapcard", "#333")
    body = bq.cover_card(q) + f"<h2>{W['zones']}</h2><ul class='tiles'>{tiles}</ul>" + links + overview
    site.write(base, [home, (city, None)], body, title=title, side=(base, f"{base}/parent", False), **page)

    # city parent page
    zone_links = "".join(
        f'<li><a href="@/{base}/zone-{i}/parent/"><span class="te">{esc(z.get("emoji", ""))}</span>'
        f'<span class="tn">{LABELS["zone"]} {i}</span><span class="tt">{esc(z["name"])}</span></a></li>'
        for i, z in enumerate(zones, 1)
    )
    body = bq.parent_plan_card(q) + "".join(bq.bookings_cards(q, 100)) + f"<h2>🔑 {W['all_answers']}</h2><ul class='tiles'>{zone_links}</ul>"
    site.write(f"{base}/parent", [home, (city, base), (LABELS["parent_pages"], None)], body,
               title=f"{title} · {LABELS['parent_pages']}", side=(base, f"{base}/parent", True), **page)

    # city-wide hunt
    if hunt:
        site.write(f"{base}/hunt", [home, (city, base), (hunt.get("title", ""), None)], bq.hunt_card(q),
                   title=f"{title} · {hunt.get('title', '')}", side=(f"{base}/hunt", f"{base}/parent", False), **page)

    # zones
    for i, z in enumerate(zones, 1):
        zname = f"{z.get('emoji', '')} {i}. {z['name']}"
        zpath = f"{base}/zone-{i}"
        how = f'<p class="getthere">{esc(z["getting_there"])}</p>' if z.get("getting_there") else ""
        zmap = f"{prefix}-map-{i}.png"
        if q.get("campaign"):
            inner = (map_html(mapsrc(zmap), pins.get(zmap, {}), z["name"]) + bq.stop_legend(q, {i}, links=True)
                     if zmap in maps else f'<p class="muted">{W["no_map"]}</p>')
            zone_map = bq.card(f"<h2>🗺️ {LABELS['map']}</h2>{how}{inner}", "mapcard", z.get("color", "#333"))
        else:
            zone_map = bq.card(how, "mapcard", z.get("color", "#333")) if how else ""
        body = bq.zone_card(z, i, nav, links=True) + zone_map + pager(q, base, i, "")
        site.write(zpath, [home, (city, base), (zname, None)], body,
                   title=f"{title} · {LABELS['zone']} {i}", side=(zpath, f"{zpath}/parent", False), **page)

        block = bq.parent_zone_block(z, i)
        body = bq.card(f"<h2>🔑 {LABELS['zone']} {i} — {LABELS['parent_zone']}</h2>{how}{block}", "parent", "#333") + pager(q, base, i, "parent/")
        site.write(f"{zpath}/parent", [home, (city, base), (zname, zpath), (LABELS["parent_pages"], None)], body,
                   title=f"{title} · {LABELS['zone']} {i} · {LABELS['parent_pages']}", side=(zpath, f"{zpath}/parent", True), **page)
    return title, q.get("cover", {}).get("emoji", "🏰"), q.get("dates", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    out = Path(a.out).resolve() if a.out else root / "site"
    if out.exists() and any(out.iterdir()) and not (out / MARKER).exists():
        sys.exit(f"{out} is not empty and was not made by this script; pick an empty or new folder")

    # every quest file: quest.json is the main language, quest.<lang>.json its translations
    quests = []  # (slug, lang, quest, folder)
    for qj in sorted(root.glob("*/quest*.json")):
        if not re.fullmatch(r"quest(\.[a-z]{2})?\.json", qj.name):
            continue
        q = json.loads(qj.read_text(encoding="utf-8"))
        lang = q.get("language", "ru")
        if lang not in WEB_LABELS:
            print(f"SKIP {qj}: no website labels for language {lang!r} (add them to WEB_LABELS)")
            continue
        quests.append((qj.parent.name, lang, q, qj.parent, qj.name == "quest.json"))
    if not quests:
        sys.exit(f"No */quest.json under {root}")
    main_langs = [lang for _, lang, _, _, is_main in quests if is_main]
    primary = max(set(main_langs), key=main_langs.count)
    order = [primary] + sorted({lang for _, lang, *_ in quests} - {primary})
    langs = {lg: {slug for slug, lang, *_ in quests if lang == lg} for lg in order}

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / MARKER).write_text("made by build_site.py; this folder is wiped on every build\n", encoding="utf-8")
    site = Site(out, langs)

    # map pictures: shared by a city's languages, unless a translation has its own (quest.en-map.png)
    published = {}
    for slug, _, _, folder, _ in quests:
        if slug in published:
            continue
        published[slug] = set()
        for png in folder.glob("quest*-map*.png"):
            (out / "maps" / slug).mkdir(parents=True, exist_ok=True)
            shutil.copy2(png, out / "maps" / slug / png.name)
            published[slug].add(png.name)

    labels0, types0 = copy.deepcopy(LABELS), copy.deepcopy(TYPES)
    cities = {lg: [] for lg in order}
    for slug, lang, q, folder, is_main in quests:
        LABELS.clear(); LABELS.update(labels0)
        TYPES.clear(); TYPES.update(types0)
        bq.set_language(q)
        own = f"quest.{lang}"
        prefix = own if not is_main and (folder / f"{own}-pins.json").exists() else "quest"
        pins_file = folder / f"{prefix}-pins.json"
        pins = json.loads(pins_file.read_text(encoding="utf-8")) if pins_file.exists() else {}
        cities[lang].append((slug,) + build_city(site, q, lang, slug, published[slug], pins, prefix))
        print(f"Built {lang}/{slug}: {len(q['zones'])} zones")

    for lg in order:
        tiles = "".join(
            f'<li><a href="@/{lg}/{slug}/"><span class="te">{esc(e)}</span><span class="tt">{esc(t)}</span><span class="tn">{esc(d)}</span></a></li>'
            for slug, t, e, d in cities[lg]
        )
        site.write(lg, [(WEB_LABELS[lg]["cities"], None)], f"<ul class='tiles'>{tiles}</ul>", lang=lg, title=WEB_LABELS[lg]["cities"])
    # the site's front door: the language used last on this device, else the main one
    picks = " · ".join(f'<a href="{lg}/">{esc(WEB_LABELS[lg]["cities"])} ({lg.upper()})</a>' for lg in order)
    (out / "index.html").write_text(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(WEB_LABELS[primary]['cities'])}</title>
<script>var l, all = {json.dumps(order)}; try {{ l = localStorage.getItem('cq-lang'); }} catch (e) {{}}
location.replace((all.indexOf(l) >= 0 ? l : all[0]) + '/');</script></head>
<body style="font-family:sans-serif;padding:16px">{picks}</body></html>""", encoding="utf-8")
    print(f"Wrote {out} ({', '.join(order)})")


if __name__ == "__main__":
    main()
