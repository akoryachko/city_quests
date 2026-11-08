#!/usr/bin/env python3
"""Turn a child's cut-out into a clean colouring-book line portrait (head and shoulders), as SVG.

Runs on this machine only (MediaPipe face landmarks + hair/skin/clothes segmentation, OpenCV);
the photo is not uploaded anywhere.

Usage (in the cover venv, see SKILL.md):
    ~/.cache/city-quest/venv/bin/python line_portrait.py covers/<slug>/kid-cutout.png covers/<slug>/kid-lines.svg

Lines: the outline of the figure, the hairline and a few hair strands, the jaw/neck and collar
(from the segmentation), eyebrows, eyes with irises and highlights, nose and smile (from the
face landmarks). Every line is smoothed into curves, so it looks drawn rather than traced.
Models are cached in ~/.cache/city-quest/models (downloaded on first use).
"""
import argparse
import os
import urllib.request
from pathlib import Path

import cv2
import numpy as np

MODELS = Path.home() / ".cache" / "city-quest" / "models"
URLS = {
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
    "selfie_multiclass.tflite": "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite",
}

# face mesh indices
BROW_L, BROW_R = [70, 63, 105, 66, 107], [300, 293, 334, 296, 336]
EYE_L_UP, EYE_L_LO = [33, 246, 161, 160, 159, 158, 157, 173, 133], [33, 7, 163, 144, 145, 153, 154, 155, 133]
EYE_R_UP, EYE_R_LO = [362, 398, 384, 385, 386, 387, 388, 466, 263], [362, 382, 381, 380, 374, 373, 390, 249, 263]
NOSE = [98, 2, 327]
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
JAW = [361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132]
MOUTH_IN = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]
LIP_LO = [146, 91, 181, 84, 17, 314, 405, 321, 375]


def model(name):
    p = MODELS / name
    if not p.exists():
        MODELS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URLS[name], p)
    return str(p)


def smooth(pts, sigma, closed=False):
    """Resample a polyline evenly and smooth it with a Gaussian along its length."""
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return pts
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    n = max(8, int(seg[-1] / 2))
    t = np.linspace(0, seg[-1], n)
    pts = np.c_[np.interp(t, seg, pts[:, 0]), np.interp(t, seg, pts[:, 1])]
    k = int(sigma * 3) * 2 + 1
    if k >= len(pts):
        return pts
    w = cv2.getGaussianKernel(k, sigma).ravel()
    mode = "wrap" if closed else "edge"
    pad = np.pad(pts, ((k // 2, k // 2), (0, 0)), mode=mode)
    return np.c_[np.convolve(pad[:, 0], w, "valid"), np.convolve(pad[:, 1], w, "valid")]


def path(pts, closed=False):
    """Catmull-Rom through the (simplified) points, as cubic Béziers."""
    pts = np.asarray(pts, float)
    if len(pts) > 6:
        ap = cv2.approxPolyDP(pts.astype(np.float32).reshape(-1, 1, 2), 0.8, closed).reshape(-1, 2)
        pts = ap if len(ap) >= 3 else pts
    if closed:
        pts = np.vstack([pts[-1], pts, pts[0], pts[1]])
    else:
        pts = np.vstack([pts[0], pts, pts[-1]])
    d = f"M{pts[1][0]:.1f},{pts[1][1]:.1f}"
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        c1, c2 = p1 + (p2 - p0) / 6, p2 - (p3 - p1) / 6
        d += f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d + ("Z" if closed else "")


def open_runs(contour, keep):
    """Split a closed contour into the runs of points where keep[y, x] is true."""
    runs, cur = [], []
    for x, y in contour:
        if keep[int(y), int(x)]:
            cur.append((x, y))
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        if runs and keep[int(contour[0][1]), int(contour[0][0])]:
            runs[0] = cur + runs[0]
        else:
            runs.append(cur)
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cutout")
    ap.add_argument("out_svg")
    ap.add_argument("--ink", default="#3a2414")
    ap.add_argument("--paper", default="#fffaf0")
    ap.add_argument("--strands", type=int, default=7, help="hair strand lines")
    ap.add_argument("--eyes", type=float, default=1.25, help="eye size factor (cartoon eyes are a bit bigger)")
    a = ap.parse_args()

    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision

    rgba = cv2.imread(a.cutout, cv2.IMREAD_UNCHANGED)
    alpha = rgba[..., 3]
    rgb = rgba[..., :3].astype(float) * (alpha[..., None] / 255) + 255 * (1 - alpha[..., None] / 255)
    rgb = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_BGR2RGB)

    lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=model("face_landmarker.task")), num_faces=1))
    res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    if not res.face_landmarks:
        raise SystemExit("No face found in the photo")
    H0, W0 = rgb.shape[:2]
    L = np.array([(p.x * W0, p.y * H0) for p in res.face_landmarks[0]])

    # head-and-shoulders crop around the face
    fx0, fy0 = L[:, 0].min(), L[:, 1].min()
    fx1, fy1 = L[:, 0].max(), L[:, 1].max()
    fw = fx1 - fx0
    cx = (fx0 + fx1) / 2
    x0, x1 = int(max(0, cx - 1.45 * fw)), int(min(W0, cx + 1.45 * fw))
    y0, y1 = int(max(0, fy0 - 0.75 * fw)), int(min(H0, fy1 + 1.15 * fw))
    rgb, alpha, L = rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1], L - (x0, y0)
    S = 1000 / (x1 - x0)  # work at 1000 px wide
    rgb = cv2.resize(rgb, None, fx=S, fy=S, interpolation=cv2.INTER_AREA)
    alpha = cv2.resize(alpha, (rgb.shape[1], rgb.shape[0]))
    L = L * S
    H, W = rgb.shape[:2]

    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(base_options=mpt.BaseOptions(model_asset_path=model("selfie_multiclass.tflite")), output_confidence_masks=True))
    conf = np.stack([np.squeeze(m.numpy_view()) for m in seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))).confidence_masks], -1)
    lab = conf.argmax(-1)  # 0 bg, 1 hair, 2 body skin, 3 face skin, 4 clothes, 5 other
    fg = cv2.GaussianBlur(alpha, (0, 0), 3) > 128
    lab[~fg] = 0
    lab[fg & (lab == 0)] = 4

    def clean(mask, k=9):
        m = mask.astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        m = cv2.GaussianBlur(m, (0, 0), 4)
        return m > 127

    hair, skin = clean(lab == 1), clean((lab == 2) | (lab == 3))
    if os.environ.get("LINES_DEBUG"):
        pal = np.array([[255, 255, 255], [230, 180, 60], [240, 150, 150], [250, 200, 170], [60, 60, 200], [0, 200, 0]], np.uint8)
        cv2.imwrite(os.environ["LINES_DEBUG"], cv2.cvtColor(pal[lab], cv2.COLOR_RGB2BGR))
    fgm = clean(fg, 5)
    near = lambda m, r: cv2.dilate(m.astype(np.uint8), np.ones((r, r), np.uint8)) > 0
    sil_edge = near(cv2.Canny(fgm.astype(np.uint8) * 255, 50, 150) > 0, 15)
    border = np.zeros((H, W), bool)
    border[:4, :] = border[-4:, :] = border[:, :4] = border[:, -4:] = True
    border = near(border, 12)

    lw = W * 0.011
    paths = []  # (d, width)

    def contours(mask):
        cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        return [c.reshape(-1, 2) for c in cs if cv2.contourArea(c) > W * 2]

    # outline of the whole figure, open where the crop cuts it
    for c in contours(fgm):
        for run in open_runs(c, ~border):
            if len(run) > 20:
                paths.append((path(smooth(run, 5)), lw * 1.25))
    # hairline: the hair's edge where it is not the figure's outline
    hair_edge = near(cv2.Canny(hair.astype(np.uint8) * 255, 50, 150) > 0, 15)
    for c in contours(hair):
        for run in open_runs(c, ~sil_edge & ~border):
            if len(run) > 25:
                paths.append((path(smooth(run, 6)), lw))
    # skin: jaw, neck, collar, ears — where it is neither the outline nor the hairline
    for c in contours(skin):
        for run in open_runs(c, ~sil_edge & ~hair_edge & ~border):
            if len(run) > 25:
                paths.append((path(smooth(run, 6)), lw))
    # jaw and chin from the face oval (skin meets skin there, so the segmentation has no edge)
    paths.append((path(smooth(L[JAW], 3)), lw))
    # ears: skin beside the face oval, between the brows and the nose
    oval = np.zeros((H, W), np.uint8)
    cv2.fillPoly(oval, [L[FACE_OVAL].astype(np.int32)], 1)
    band = np.zeros((H, W), bool)
    band[int(L[[70, 300], 1].min()):int(L[[2], 1].max() + 0.04 * H), :] = True
    ears = clean(skin & band & ~near(oval > 0, 7), 7)
    for c in contours(ears):
        if cv2.contourArea(c) < W * 1.2:
            continue
        for run in open_runs(c, ~sil_edge):
            if len(run) > 15:
                paths.append((path(smooth(run, 4)), lw))
        m = c.mean(0)
        ew, eh = np.ptp(c[:, 0]), np.ptp(c[:, 1])
        side = 1 if m[0] > L[1][0] else -1
        arc = np.array([m + (-side * 0.05 * ew, -0.28 * eh), m + (side * 0.18 * ew, -0.05 * eh), m + (0, 0.22 * eh)])  # a C inside the ear
        paths.append((path(smooth(arc, 1.5)), lw * 0.7))
    # jacket: the zip, straight down from the bottom of the collar's V
    neck = skin & (np.arange(H)[:, None] > L[152][1])
    cols = slice(int(L[152][0] - 0.12 * W), int(L[152][0] + 0.12 * W))
    ys, xs = np.nonzero(neck[:, cols])
    if len(ys):
        i = ys.argmax()
        vx, vy = xs[i] + cols.start, ys[i]
        zip_ = np.array([(vx, vy), (vx + 0.004 * W, (vy + H) / 2), (vx + 0.01 * W, H - 6)])
        paths.append((path(smooth(zip_, 1)), lw * 0.75))
    # a few strands inside the hair, following its strongest edges
    if a.strands:
        g = cv2.GaussianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (0, 0), 2.2)
        ed = cv2.Canny(g, 30, 80)
        inner = cv2.erode(hair.astype(np.uint8), np.ones((25, 25), np.uint8)) > 0
        ed[~inner] = 0
        cs, _ = cv2.findContours(ed, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cs = sorted((c.reshape(-1, 2) for c in cs), key=lambda c: -cv2.arcLength(c.reshape(-1, 1, 2), False))
        for c in cs[:a.strands]:
            c = c[: len(c) // 2 + 1]  # Canny contours run there and back
            if len(c) > 40:
                paths.append((path(smooth(c, 5)), lw * 0.7))

    P = lambda idx: L[idx]
    # eyebrows, eyes
    for brow in (BROW_L, BROW_R):
        paths.append((path(smooth(P(brow), 1.5)), lw * 1.2))
    feats = []
    for idx in (EYE_L_UP + EYE_L_LO + list(range(468, 473)), EYE_R_UP + EYE_R_LO + list(range(473, 478))):
        idx = sorted(set(idx))
        ec = L[idx].mean(0)
        L[idx] = ec + (L[idx] - ec) * a.eyes
    for up, lo, iris in ((EYE_L_UP, EYE_L_LO, 468), (EYE_R_UP, EYE_R_LO, 473)):
        paths.append((path(smooth(P(up), 1.2)), lw * 1.15))
        paths.append((path(smooth(P(lo)[2:-2], 1.2)), lw * 0.6))
        c = L[iris]
        r = np.mean(np.hypot(*(L[iris + 1: iris + 5] - c).T)) * 0.95
        eye_w = np.hypot(*(L[up[0]] - L[up[-1]]))
        r = min(r, eye_w * 0.27)
        feats.append(f'<circle cx="{c[0]:.1f}" cy="{c[1]:.1f}" r="{r:.1f}" fill="none" stroke="{a.ink}" stroke-width="{lw*0.7:.1f}"/>'
                     f'<circle cx="{c[0]:.1f}" cy="{c[1]:.1f}" r="{r*0.55:.1f}" fill="{a.ink}"/>'
                     f'<circle cx="{c[0]+r*0.3:.1f}" cy="{c[1]-r*0.32:.1f}" r="{r*0.22:.1f}" fill="{a.paper}"/>')
    # nose and smile
    l, t, r = L[98], L[2], L[327]
    mid = (l + r) / 2
    nose = np.array([mid + (l - mid) * 0.7, t + (0, (r[0] - l[0]) * 0.12), mid + (r - mid) * 0.7])
    paths.append((path(smooth(nose, 1.0)), lw * 0.85))
    for p0, s_ in ((l, -1), (r, 1)):  # nostril wings: little hooks
        hook = np.array([p0 + (s_ * 0.0, -0.06 * (r[0] - l[0])), p0 + (s_ * 0.06 * (r[0] - l[0]), 0.02 * (r[0] - l[0])), p0 + (0, 0.1 * (r[0] - l[0]))])
        paths.append((path(smooth(hook, 0.6)), lw * 0.7))
    feats.append(f'<path d="{path(smooth(np.vstack([P(MOUTH_IN), P(MOUTH_IN[:1])]), 1.0, True), True)}" fill="{a.paper}" stroke="{a.ink}" stroke-width="{lw:.1f}" stroke-linejoin="round"/>')
    paths.append((path(smooth(P(LIP_LO)[1:-1], 1.5)), lw * 0.6))

    body = "".join(f'<path d="{d}" fill="none" stroke="{a.ink}" stroke-width="{w:.1f}" stroke-linecap="round" stroke-linejoin="round"/>' for d, w in paths)
    fill_d = "".join(path(smooth(c, 5, True), True) for c in contours(fgm))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
           f'<path d="{fill_d}" fill="{a.paper}"/>{body}{"".join(feats)}</svg>')
    Path(a.out_svg).write_text(svg, encoding="utf-8")
    print(f"Wrote {a.out_svg} ({W}x{H})")


if __name__ == "__main__":
    main()
