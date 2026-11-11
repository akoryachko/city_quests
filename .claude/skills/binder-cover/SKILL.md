---
name: binder-cover
description: Design a personalised front and back cover for a child's quest ring binder (the folder that holds the city-quest booklets), in a travel-explorer style, from the child's name and photo. Interviews the parent about the child (name, photos, favourite things), turns the photo into a contour-map portrait of the child's face (like a topographic map, in sepia and gold tones), and renders the cover — front with the name, the portrait, compass, flight path and travel stamps; back with a motto and a map of Europe (or another region) with a named empty circle for every city worth a quest, plus a magnifier on the home country — both A5 halves on one A4 landscape sheet, or each face at the binder's own size (e.g. 19 × 22 cm) on its own A4 page with crop marks. Keeps the child's photo and name private (git-ignored covers/ folder, never committed). Use whenever the user asks for a binder cover, folder cover, quest-book cover or a personalised cover with a kid's photo, even if they don't say "skill".
---

# Personalised binder cover

The quest booklets (city-quest skill) go into a ring binder. This skill makes the
binder's cover in an explorer style (parchment, sepia ink, compass rose, dotted flight
path, travel stamps):

- **Front**: the child's name (the only word), a contour-map portrait of the child's head
  (the light and shadow of the face as isolines with tinted bands, hair in gold tones, eyes,
  brows, nose and smile in ink, made from a photo), a faint world map behind, compass,
  flight path and four round stamps with icons.
- **Back**: a motto and a map of a region (Europe by default) with an **empty circle and name
  for every city worth a quest**, the home country enlarged in a magnifier. The map is meant to
  last for many trips: after conquering a city the child colours its circle in or puts a
  sticker on it. Cities of the repo's quests are added automatically if missing.

## Privacy (read first)

A child's name and photo are personal data. All of it stays on this machine:

- Work only in `covers/<slug>/` (git-ignored; check with `git check-ignore covers/x`
  before writing, add `covers/` to `.gitignore` if it is missing). The slug is any short
  word the parent is happy with; it is never committed either.
- Never copy the original photo; read it where it is. Only derived images (cut-out,
  sticker, sketch), `cover.json` and the renders live in the cover folder.
- Never write the child's name, age, school, photo path or anything personal into the
  skill, README, family profile examples, commit messages or the website. Examples in
  this skill use placeholder names.
- Don't upload the photo anywhere (no web services, no artifacts) unless the parent asks.

## 1. Interview

Ask (the AskUserQuestion tool works well):

1. **Name** as it should appear on the front, and the language of the back (city names,
   motto): `ru` or `en`.
2. **Photo**: a path or file:// link (decode `%20`). Best: full figure, plain background,
   good light, face clearly visible.
3. **Binder**: the size of the cover pockets (measure the binder). Two A5 inserts (default:
   front and back on one A4 landscape sheet, cut in the middle), or any other size up to
   ~200 × 280 mm with `"size": [width, height]` in mm (e.g. `[190, 220]`): each face gets its
   own A4 portrait page (front first), centred, with 2 mm bleed and crop marks. The layout is
   designed on A5 and adapts: positions stretch with the height, sizes and fonts grow with the
   smaller ratio, and the back map fills the wider frame with more of the region.
   When the back pocket differs from the front, give it its own `"back_size": [190, 228]`.
   For a binder with a spine pocket add `"spine": 30` (width in mm; height as the faces, or
   `[30, 217]` for its own height): a
   third page with the front's title reading upwards, a compass and a plane at the ends.
4. **Front figure**: a finished drawing of the child the parent already has (e.g. a pencil or
   watercolour portrait on white paper — the best result; set `"figure_kind": "drawing"`: it is
   multiplied onto the parchment so the white paper disappears, and its edges fade out), or one
   made here from the photo: contour-map portrait, clean line portrait, sepia pencil sketch, or
   the photo with a sticker outline. Generated portraits are simple; say so and offer the
   drawing route when likeness matters.
5. **Map**: which region (`europe`) and which home country in the magnifier
   (`netherlands`); cities to add or leave out. Regions and their cities live in
   `references/cities.json` (names in ru and en); add a region there when a family's trips
   go elsewhere. A region lists every city on the map, also outside the EU (Russia, Turkey,
   North Africa) and in otherwise empty areas; the build keeps those that fall inside the map
   frame. With names (the default) about 85 main cities and 13 in the magnifier fit;
   `europe-all` / `netherlands-all` hold ~120 and ~40 for a map without names
   (`"labels": false`, small circles).
6. **Title**: an optional `"subtitle"` such as «Паспорт покорителя». With one, it becomes the
   title at the top and the name moves under the portrait (smaller portrait); without one the
   name is at the top.
7. **Icons** (favourite things: trains, boats, castles, animals…) and the **motto**. Read
   the family profile (`family-profile.md`) for likes; no brand characters or logos.

## 2. Photo

rembg runs in its own virtual environment (once):

```bash
uv venv ~/.cache/city-quest/venv
VIRTUAL_ENV=~/.cache/city-quest/venv uv pip install "rembg[cpu]" pillow numpy mediapipe opencv-python-headless
```

```bash
~/.cache/city-quest/venv/bin/python .claude/skills/binder-cover/scripts/prepare_photo.py "<photo>" covers/<slug>
```

It writes `kid-cutout.png` (no background), `kid-sticker.png` (white sticker outline) and
`kid-sketch.png` (sepia pencil sketch). Then the contour-map portrait, from the original photo
at full resolution:

```bash
~/.cache/city-quest/venv/bin/python .claude/skills/binder-cover/scripts/contour_portrait.py "<photo>" covers/<slug>/kid-contour.svg
```

It crops tight on the head (hair, ears, a rounded neck; no clothes), smooths the face's
brightness into a "terrain" and draws its isolines with tinted bands: skin in sepia tones,
hair (found by MediaPipe segmentation) with its own levels in gold tones, then eyes, irises,
brows, nose and mouth in ink from the face landmarks. Tune `--levels` (busier or calmer) and
the colours (`--light`, `--dark`, `--hair-light`, `--hair-dark`). Render the SVG on parchment
and check the face reads as the child.

Alternatively, the clean line portrait (head and shoulders):

```bash
~/.cache/city-quest/venv/bin/python .claude/skills/binder-cover/scripts/line_portrait.py covers/<slug>/kid-cutout.png covers/<slug>/kid-lines.svg
```

It finds the face (MediaPipe face landmarks: brows, eyes and irises, nose, smile) and the
hair/skin/clothes regions (MediaPipe segmentation), and draws them as smooth strokes: the
outline, hairline and a few strands, jaw, ears, collar and zip, eyes a little enlarged
(`--eyes`, default 1.25). Models download once to `~/.cache/city-quest/models`. Render the SVG
and look: a likeness with a few clean lines beats many lines; the photo should show the face
straight on. The first run downloads the BiRefNet
portrait model (~1 GB, to `~/.u2net`). Look at the cut-out and the sketch: hair, hands and
anything the child holds kept, chairs and background gone, the face readable in the
drawing. If the cut-out is poor, try `--model isnet-general-use` or ask for a photo with a
plainer background.

## 3. cover.json and build

Write `covers/<slug>/cover.json` (fields documented at the top of
`scripts/build_cover.py`): name, lang, figure (default `kid-contour.svg`), motto, icons
(3rd–6th go on the stamps), map (main, inset, add, drop, labels, quests).

```bash
python3 .claude/skills/binder-cover/scripts/build_cover.py covers/<slug>/cover.json
```

Writes `cover.pdf` (A4 landscape: back left, front right, dashed cut line; with `size`: page 1
the front, page 2 the back), `cover.png` and `cover.html`. Country shapes (Natural Earth via world-atlas) are cached in
`~/.cache/city-quest/world`; fonts come from Google Fonts, so the build needs internet.

Check the render (`pdftoppm -r 80 -png -singlefile cover.pdf <scratchpad>/cv`, and a closer
look at the magnifier at `-r 150`): the name on one line, the face not covered, icons as
emoji (not boxes), nothing cut off. The build prints `NOTE: circles touch` for cities that
nearly overlap and `NOTE: label overlaps` where a name has no free spot; labels avoid other
names, circles and spots that sit closer to a neighbour's circle (which would read as the
wrong city). Zoom into dense areas (Benelux, central Europe, the magnifier) and drop the least
interesting city where names still collide or read ambiguously. Show the user and iterate.

## 4. Hand-off

Tell the user where the PDF is and how to print: colour, **actual size / 100 %** (not "fit to
page"), single-sided, ideally on thicker paper (160–200 g/m²). A5 halves: A4 landscape, cut along
the dashed line; the left half is the back, the right half the front. With `size`: two A4
portrait pages (front, back, and the spine if asked), each cut at its crop marks (the parchment
runs 2 mm past them). The circles (2.8 mm on the main map,
2.2 mm in the magnifier) are for colouring in with a felt-tip after each conquered city. When a quest is made for a
city not on the map, rebuild the cover so its circle appears.
