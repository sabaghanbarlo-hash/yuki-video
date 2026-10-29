"""YouTube thumbnail from the script: a striking frame from the video itself + the title in big outlined letters."""
import re
import numpy as np
from PIL import Image, ImageDraw
from . import pipeline as P
from . import overlays as O
from .compose import Compositor

W, H = 1280, 720


def punch(title):
    t = re.sub(r"[#*_]+", "", title).strip()
    words = t.split()
    if len(words) > 7:
        words = words[:7]
    # break into two or three lines of similar length
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + len(w) > 16:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines[:3])


def make_thumbnail(text, out, seed=0, style=None):
    plan = P.build_plan(text, seed, style, None)
    total = P.timeline(plan, P.estimate_durations(plan))
    P.caption_plan(plan)
    amp = np.full(int(total * P.FPS) + 5, 0.0, np.float32)
    comp = Compositor(plan, amp, amp)
    bodies = [s for s in plan["scenes"] if s["kind"] == "body"]
    best = None
    for sc in bodies[:5]:
        n = sum(1 for a in sc["shots"][0]["actors"] if a["k"] in ("entity", "prop", "human", "char")) + (0 if sc["style"] == "voxel" else 2)
        if best is None or n > best[0]:
            best = (n, sc)
    sc = best[1]
    sh = sc["shots"][0]
    t = sh["t0"] + min(2.4, (sh["t1"] - sh["t0"]) * 0.7)
    comp.stage(sc["idx"]).no_labels = True
    im = comp.scene_frame(sc["idx"], t).convert("RGBA")
    # punch up: saturation + a dark gradient on the left for the title
    from PIL import ImageEnhance
    im = ImageEnhance.Color(im.convert("RGB")).enhance(1.25).convert("RGBA")
    g = np.zeros((H, W, 4), np.uint8)
    x = np.linspace(0, 1, W)[None, :]
    g[..., 3] = (np.clip(1.15 - x * 1.3, 0, 1) * 210).astype(np.uint8)
    g = np.repeat(g[:, :1, :], 1, axis=1) if False else g
    im.alpha_composite(Image.fromarray(g, "RGBA"))
    title = punch(plan["title"] or sc["text"][:60])
    lines = title.split("\n")
    size = 118 if max(len(l) for l in lines) <= 12 else 100
    y = int(H * 0.5 - len(lines) * size * 0.62)
    for i, l in enumerate(lines):
        col = O.ACCENTS[0] if i == len(lines) - 1 else (255, 255, 255)
        t_im = O.outlined(l, size, col, (18, 14, 40), sw=9)
        O.paste(im, t_im, 48, y + int(i * size * 1.12))
    O.paste(im, O.chip_img("YUKI LAB", O.ACCENTS[1], 34), 52, 44)
    im.convert("RGB").save(out, quality=90)
    return out
