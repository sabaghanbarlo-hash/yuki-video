#!/usr/bin/env python3
"""python make_thumbnail.py scripts/my-video.txt --out output/my-video.jpg   (frame from the video + big title)"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab.thumbnail import make_thumbnail

ap = argparse.ArgumentParser()
ap.add_argument("script"); ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--style", default=None)
ap.add_argument("--mode", default=None)       # accepted and ignored (older workflow versions)
a = ap.parse_args()
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
make_thumbnail(Path(a.script).read_text(encoding="utf-8"), a.out, a.seed, a.style)
print("wrote", a.out)
