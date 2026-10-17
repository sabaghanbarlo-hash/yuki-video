#!/usr/bin/env python3
"""Make the YouTube thumbnail for one script.   python make_thumbnail.py stories/x.txt --out output/x.jpg"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yuki.thumbnail import make  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("script")
ap.add_argument("--out", default=None)
ap.add_argument("--mode", default="explainer")
ap.add_argument("--seed", type=int, default=None)
a = ap.parse_args()
out = a.out or str(Path("output") / (Path(a.script).stem + ".jpg"))
print(json.dumps(make(a.script, out, a.mode, a.seed), ensure_ascii=False))
print("thumbnail:", out)
