#!/usr/bin/env python3
"""Cut a child out of a photo for the binder cover (private: writes only into the cover folder).

Usage (rembg lives in its own venv, see SKILL.md):
    ~/.cache/city-quest/venv/bin/python prepare_photo.py PHOTO covers/<slug> [--name kid]

Writes into covers/<slug>/:
    <name>-cutout.png    the child without background, cropped to the figure
    <name>-sticker.png   the same with a thick white sticker outline (the photo version of the front)
    <name>-sketch.png    the child as a sepia ink drawing on light paper (the default front)
The original photo is not copied.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("folder")
    ap.add_argument("--name", default="kid")
    ap.add_argument("--model", default="birefnet-portrait", help="rembg model (birefnet-portrait is best for people)")
    a = ap.parse_args()
    from rembg import new_session, remove

    out = Path(a.folder)
    out.mkdir(parents=True, exist_ok=True)
    im = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")
    im.thumbnail((2000, 3000))  # ~300 dpi for a figure up to 17 cm tall
    cut = remove(im, session=new_session(a.model))
    box = cut.getbbox()
    cut.crop(box).save(out / f"{a.name}-cutout.png")

    # sticker: a white outline ~1.5 % of the height around the figure
    small = cut.crop(box)
    pad = max(8, small.height // 60)
    canvas = Image.new("RGBA", (small.width + 2 * pad, small.height + 2 * pad), (0, 0, 0, 0))
    canvas.paste(small, (pad, pad))
    alpha = canvas.getchannel("A").point(lambda v: 255 if v > 60 else 0)
    k = pad // 2 * 2 + 1
    grown = alpha.resize((alpha.width // 4, alpha.height // 4)).filter(ImageFilter.MaxFilter(k // 4 * 2 + 1)).resize(alpha.size).filter(ImageFilter.GaussianBlur(2)).point(lambda v: 255 if v > 100 else 0)
    white = Image.new("RGBA", canvas.size, (255, 255, 255, 255))
    white.putalpha(grown)
    white.alpha_composite(canvas)
    white.save(out / f"{a.name}-sticker.png")

    sketch(cut.crop(box)).save(out / f"{a.name}-sketch.png")
    print(f"Wrote {out}/{a.name}-cutout.png, -sticker.png, -sketch.png")


def sketch(cut, ink=(74, 47, 23), paper=(251, 241, 218)):
    """Pencil/ink drawing: colour dodge of the greyscale with its blurred negative, plus the outline."""
    import numpy as np
    cut = cut.copy()
    cut.thumbnail((1400, 2100))
    a = np.asarray(cut.getchannel("A"), float) / 255
    g = np.asarray(cut.convert("L").filter(ImageFilter.GaussianBlur(1.4)), float)
    g = g * a + 255 * (1 - a)
    blur = np.asarray(Image.fromarray((255 - g).astype("uint8")).filter(ImageFilter.GaussianBlur(7)), float)
    d = np.clip(g * 255 / (255 - blur + 1), 0, 255)
    dark = np.clip(((1 - d / 255) ** (1 / 3) - 0.22) / 0.55, 0, 1)
    mask = Image.fromarray((a * 255).astype("uint8"))
    edge = np.asarray(mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1)), float) / 255
    line = np.maximum(dark, edge) * (a > 0.05)
    # paper inside the figure so whatever is behind it does not show through, ink on top
    rgb = np.empty(g.shape + (3,))
    for c in range(3):
        rgb[..., c] = paper[c] * (1 - line) + ink[c] * line
    alpha = np.clip(np.maximum(a * 0.92, line), 0, 1)
    out = np.dstack([rgb, alpha * 255]).astype("uint8")
    return Image.fromarray(out, "RGBA")


if __name__ == "__main__":
    main()
