#!/usr/bin/env python3
"""python make_toon_thumbnail.py scripts/x.txt --out output/x.jpg [--format short]: new-look Yuki + big title."""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skia
from toonlab import gfx, director
from toonlab.yuki import YUKI, State, draw_character

ap = argparse.ArgumentParser(); ap.add_argument("script"); ap.add_argument("--out", required=True)
ap.add_argument("--format", default="long"); ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()
text = Path(a.script).read_text(encoding="utf-8")
title, sents = director.parse(text)
title = (title or (sents[0]["text"] if sents else "Yuki's Mind Lab")).strip()
W, H = (1280, 720) if a.format == "long" else (1080, 1920)
s = gfx.surface(W, H); cv = s.getCanvas()
cv.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeLinear([(0, 0), (0, H)], [skia.Color(255, 233, 205), skia.Color(255, 205, 170)])))
faces = ["shocked", "excited", "curious", "smug", "worried"]
face = faces[sum(map(ord, title)) % len(faces)]
st = State(face=face, vis=2, amp=.8, parts="bust", t=1.0, pose="thumbs", prev="thumbs")
if a.format == "long":
    draw_character(cv, YUKI, W * 0.76, H * 0.4, 1.45, st)
    box = W * 0.52; x = W * 0.07; align = "left"; size = 104
else:
    draw_character(cv, YUKI, W * 0.5, H * 0.74, 2.6, st)
    box = W * 0.86; x = W * 0.07; align = "left"; size = 130
lines = gfx.wrap_text(title.upper(), "bold", size, box)
while len(lines) > 4 and size > 50:
    size -= 8; lines = gfx.wrap_text(title.upper(), "bold", size, box)
y = H * (0.2 if a.format == "long" else 0.1)
for ln in lines:
    gfx.draw_text(cv, ln, x, y, "bold", size, (255, 255, 255), ow=9, ink=(42, 34, 48), align=align)
    y += size * 1.12
gfx.draw_text(cv, "YUKI'S MIND LAB", x, H * (0.9 if a.format == "long" else 0.95), "bold", 40, (226, 88, 52), ow=5, ink=(255, 255, 255), align=align)
from PIL import Image
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Image.fromarray(gfx.to_rgb(s)).save(a.out, quality=90)
print("wrote", a.out)
