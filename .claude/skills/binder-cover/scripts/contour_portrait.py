#!/usr/bin/env python3
"""Turn a child's photo into a contour-map portrait (like a topographic map of the face), as SVG.

The light and shadow of the face become isolines with softly tinted bands between them; eyes,
brows, nose and mouth are drawn in ink on top from the face landmarks. Cropped tight on the head,
from the full-resolution photo. Runs on this machine only (rembg, MediaPipe, OpenCV).

Usage (in the cover venv, see SKILL.md):
    ~/.cache/city-quest/venv/bin/python contour_portrait.py PHOTO covers/<slug>/kid-contour.svg [--levels 11]
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from line_portrait import (FACE_OVAL, BROW_L, BROW_R, EYE_L_LO, EYE_L_UP, EYE_R_LO, EYE_R_UP, LIP_LO, MOUTH_IN, model, path, smooth)

LIP_UP = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
NOSE_WINGS = [[48, 64, 98, 97], [278, 294, 327, 326]]


def hexmix(c1, c2, t):
    a = np.array([int(c1[i:i + 2], 16) for i in (1, 3, 5)])
    b = np.array([int(c2[i:i + 2], 16) for i in (1, 3, 5)])
    return "#%02x%02x%02x" % tuple((a + (b - a) * t).astype(int))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("out_svg")
    ap.add_argument("--levels", type=int, default=11, help="number of contour levels")
    ap.add_argument("--ink", default="#4a2f17")
    ap.add_argument("--light", default="#f6e6c4", help="band colour for the brightest parts")
    ap.add_argument("--dark", default="#c27f50", help="band colour for the darkest parts")
    ap.add_argument("--hair-light", default="#f3d590", help="band colour for the lightest hair")
    ap.add_argument("--hair-dark", default="#a8732e", help="band colour for the darkest hair")
    ap.add_argument("--neck", type=float, default=0.32, help="how much below the chin to keep, in face widths")
    a = ap.parse_args()

    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    from rembg import new_session, remove

    full = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")
    small = full.copy()
    small.thumbnail((1600, 1600))
    k = full.width / small.width
    lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=model("face_landmarker.task")), num_faces=1))
    res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(small)))
    if not res.face_landmarks:
        raise SystemExit("No face found in the photo")
    L = np.array([(p.x * small.width, p.y * small.height) for p in res.face_landmarks[0]]) * k

    # tight head crop: hair above, a little neck below
    fx0, fy0, fx1, fy1 = L[:, 0].min(), L[:, 1].min(), L[:, 0].max(), L[:, 1].max()
    fw = fx1 - fx0
    cx = (fx0 + fx1) / 2
    box = (int(max(0, cx - 0.9 * fw)), int(max(0, fy0 - 0.8 * fw)), int(min(full.width, cx + 0.9 * fw)), int(min(full.height, fy1 + (a.neck + 0.05) * fw)))
    crop = full.crop(box)
    W = 1000
    s = W / crop.width
    crop = crop.resize((W, round(crop.height * s)), Image.LANCZOS)
    L = (L - box[:2]) * s
    H = crop.height

    cut = remove(crop, session=new_session("birefnet-portrait"))
    alpha = np.asarray(cut.getchannel("A")).astype(np.uint8)
    fg = cv2.GaussianBlur(alpha, (0, 0), 3) > 128
    g = cv2.cvtColor(np.asarray(crop), cv2.COLOR_RGB2LAB)[..., 0].astype(float)
    # keep: everything above the nose (hair, ears), the face oval below it, and a rounded neck
    fwp = fw * s
    yy, xx = np.mgrid[0:H, 0:W]
    oval = np.zeros((H, W), np.uint8)
    cv2.fillPoly(oval, [L[FACE_OVAL].astype(np.int32)], 1)
    oval = cv2.dilate(oval, np.ones((int(fwp * 0.06) | 1,) * 2, np.uint8)).astype(bool)
    ncx, nhw = L[152][0], 0.24 * fwp
    nend = L[152][1] + a.neck * fwp
    t = np.clip((yy - L[152][1]) / (nend - L[152][1]), 0, 1)
    neck = (np.abs(xx - ncx) < nhw * (1 + 0.35 * t)) & (yy < nend - 0.1 * fwp * (1 - np.sqrt(np.clip(1 - ((xx - ncx) / (nhw * 1.35)) ** 2, 0, 1))))
    fg &= (yy < L[2][1]) | oval | (neck & (yy > L[152][1] - 0.2 * fwp))
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)).astype(bool)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8))
    if n > 1:
        fg = lab == 1 + stats[1:, cv2.CC_STAT_AREA].argmax()

    # the "terrain": luminance, smoothed so the isolines become broad, flowing shapes
    # local contrast first, so the hair gets isolines as well as the face
    eq = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(6, 6)).apply(g.astype(np.uint8)).astype(float)
    terr_hair = cv2.GaussianBlur(eq, (0, 0), W * 0.013)
    terr_face = cv2.GaussianBlur(g, (0, 0), W * 0.021)  # broad, calm shapes on the skin
    # hair and skin get their own levels and colours (blond hair reads as hair, not as a dark cap)
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(base_options=mpt.BaseOptions(model_asset_path=model("selfie_multiclass.tflite")), output_confidence_masks=True))
    conf = np.stack([np.squeeze(m.numpy_view()) for m in seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(np.asarray(crop)))).confidence_masks], -1)
    hair = cv2.morphologyEx(((conf.argmax(-1) == 1) & fg).astype(np.uint8), cv2.MORPH_OPEN, np.ones((11, 11), np.uint8)).astype(bool)
    sm = W * 0.006
    lw = W * 0.0022
    bands, lines, bases = [], [], []
    regions = [(fg & ~hair, a.levels, a.light, a.dark, terr_face), (hair, max(5, a.levels // 2), a.hair_light, a.hair_dark, terr_hair)]
    for region, n_lv, c_light, c_dark, terr in regions:
        if region.sum() < W * 20:
            continue
        cs, _ = cv2.findContours(region.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        rd = "".join(path(smooth(c.reshape(-1, 2), sm, True), True) for c in cs if cv2.contourArea(c) > W * 2)
        bases.append(f'<path d="{rd}" fill="{hexmix(c_light, c_dark, 0.8)}" fill-opacity=".55"/>')
        levels = np.quantile(terr[region], np.linspace(0.06, 0.95, n_lv))
        for i, lv in enumerate(levels):
            m = ((terr >= lv) & region).astype(np.uint8)  # brighter than the level
            cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            t = 1 - i / max(1, len(levels) - 1)
            d = "".join(path(smooth(c.reshape(-1, 2), sm, True), True) for c in cs if cv2.contourArea(c) > W * 0.6)
            if d:
                bands.append(f'<path d="{d}" fill="{hexmix(c_light, c_dark, t * 0.85)}" fill-opacity=".4"/>')
                lines.append(f'<path d="{d}" fill="none" stroke="{a.ink}" stroke-opacity="{0.35 + 0.35 * (i % 3 == 0):.2f}" stroke-width="{lw * (1.4 if i % 3 == 0 else 1):.1f}"/>')
    fgu = fg.astype(np.uint8)
    # silhouette: base tint and outline
    cs, _ = cv2.findContours(fgu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    sil = "".join(path(smooth(c.reshape(-1, 2), W * 0.004, True), True) for c in cs if cv2.contourArea(c) > W * 5)
    base = "".join(bases)
    outline = f'<path d="{sil}" fill="none" stroke="{a.ink}" stroke-width="{lw * 2.2:.1f}" stroke-linejoin="round"/>'

    # features in ink
    feats = []
    st = lambda d, w, extra="": feats.append(f'<path d="{d}" fill="none" stroke="{a.ink}" stroke-width="{w:.1f}" stroke-linecap="round" stroke-linejoin="round" {extra}/>')
    for brow in (BROW_L, BROW_R):
        st(path(smooth(L[brow], 2)), lw * 4)
    for up, lo, iris in ((EYE_L_UP, EYE_L_LO, 468), (EYE_R_UP, EYE_R_LO, 473)):
        eye = np.vstack([L[up], L[lo][::-1][1:-1]])
        feats.append(f'<path d="{path(smooth(eye, 1.2, True), True)}" fill="#fffaf0" stroke="{a.ink}" stroke-width="{lw * 2:.1f}"/>')
        c = L[iris]
        r = np.mean(np.hypot(*(L[iris + 1: iris + 5] - c).T))
        feats.append(f'<circle cx="{c[0]:.1f}" cy="{c[1]:.1f}" r="{r:.1f}" fill="{hexmix(a.dark, a.ink, .3)}"/><circle cx="{c[0]:.1f}" cy="{c[1]:.1f}" r="{r*.45:.1f}" fill="{a.ink}"/>'
                     f'<circle cx="{c[0]+r*.32:.1f}" cy="{c[1]-r*.32:.1f}" r="{r*.2:.1f}" fill="#fffaf0"/>')
        st(path(smooth(L[up], 1.2)), lw * 3)
    for wing in NOSE_WINGS:
        st(path(smooth(L[wing], 1)), lw * 2.2)
    st(path(smooth(L[[64, 2, 294]], 1)), lw * 1.4, 'stroke-opacity=".7"')
    mouth = np.vstack([L[LIP_UP], L[LIP_LO][::-1]])
    feats.append(f'<path d="{path(smooth(np.vstack([mouth, mouth[:1]]), 1.5, True), True)}" fill="{hexmix(a.dark, "#c0392b", .35)}" fill-opacity=".75" stroke="{a.ink}" stroke-width="{lw * 2:.1f}"/>')
    feats.append(f'<path d="{path(smooth(np.vstack([L[MOUTH_IN], L[MOUTH_IN[:1]]]), 1.0, True), True)}" fill="#fffaf0" stroke="{a.ink}" stroke-width="{lw * 1.6:.1f}"/>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
           f'{base}{"".join(bands)}{"".join(lines)}{outline}{"".join(feats)}</svg>')
    Path(a.out_svg).write_text(svg, encoding="utf-8")
    print(f"Wrote {a.out_svg} ({W}x{H})")


if __name__ == "__main__":
    main()
