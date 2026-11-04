"""Build assets/icons from the Twemoji graphics (CC-BY 4.0, https://github.com/jdecked/twemoji) and the Emojibase keyword data (MIT).
One-off helper (the result is committed): npm pack @twemoji/svg emojibase-data ; unpack ; python tools/build_icons.py <svg_dir> <en_data.json> <messages.json>"""
import json, subprocess, sys
from pathlib import Path

svg_dir, data_f, msg_f = map(Path, sys.argv[1:4])
out = Path(__file__).resolve().parent.parent / "assets" / "icons"
out.mkdir(parents=True, exist_ok=True)
groups = {g["order"]: g["key"] for g in json.load(open(msg_f))["groups"]}
index = {}
for e in json.load(open(data_f)):
    g = groups.get(e.get("group"), "")
    if g in ("flags", "component") or "200D" in e["hexcode"] or e.get("group") is None:
        continue
    hx = e["hexcode"].lower().replace("-fe0f", "").replace("fe0f", "")
    cand = [hx, e["hexcode"].lower(), hx.replace("-", "-")]
    src = next((svg_dir / f"{c}.svg" for c in cand if (svg_dir / f"{c}.svg").exists()), None)
    if src is None:
        continue
    dst = out / f"{hx}.png"
    if not dst.exists():
        subprocess.run(["rsvg-convert", "-w", "160", "-h", "160", "-o", str(dst), str(src)], check=True)
    index[hx] = [e["label"], e.get("tags", []), g]
json.dump(index, open(out / "index.json", "w"), separators=(",", ":"), ensure_ascii=False)
print(len(index), "icons")
