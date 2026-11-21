#!/usr/bin/env python3
"""python make_thumbnail.py scripts/my-video.txt --out output/my-video.jpg   (frame from the video + big title)
   python make_thumbnail.py scripts/my-short.txt --out output/my-short.jpg --format short   (vertical 1080x1920 Shorts thumbnail)"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab.thumbnail import make_thumbnail

ap = argparse.ArgumentParser()
ap.add_argument("script"); ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--style", default=None)
ap.add_argument("--format", default="long", choices=["long", "short"])
ap.add_argument("--mode", default=None)       # accepted and ignored (older workflow versions)
a = ap.parse_args()
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
text = Path(a.script).read_text(encoding="utf-8")
if a.format == "short":
    from lab.thumbnail_short import make_short_thumbnail
    make_short_thumbnail(text, a.out, a.seed)
else:
    make_thumbnail(text, a.out, a.seed, a.style)
print("wrote", a.out)
