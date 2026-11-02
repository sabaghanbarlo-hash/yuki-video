"""Scene previews without recording any voice: one still per scene (+ plan.json) so the web page can show what will be made."""
import json
from pathlib import Path
from . import pipeline as P
from .compose import Compositor
import numpy as np


def make_preview(text, args, outdir, size=(640, 360)):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    plan = P.build_plan(text, args.seed, args.style, args.max_scenes)
    from . import media as M
    M.prefetch(plan, "local", cache_dir=".work/media", local_dir=Path(__file__).resolve().parent.parent / "media")   # previews use your own files or drawings
    total = P.timeline(plan, P.estimate_durations(plan))
    P.caption_plan(plan)
    amp = np.full(int(total * P.FPS) + 5, 0.4, np.float32)
    comp = Compositor(plan, amp, amp)
    meta = P._plan_json(plan)
    for sc, mj in zip(plan["scenes"], meta["scenes"]):
        shot = sc["shots"][min(len(sc["shots"]) - 1, 0)]
        t = shot["t0"] + min(2.2, (shot["t1"] - shot["t0"]) * 0.6)
        fr = int(t * P.FPS)
        im = comp.frame(fr).convert("RGB").resize(size)
        f = f"scene-{sc['idx']:02d}.jpg"
        im.save(outdir / f, quality=82)
        mj["image"] = f
        print(f"  preview {sc['idx']}: {sc['style']}/{sc['env']}", flush=True)
    meta["total"] = round(total, 1)
    (outdir / "plan.json").write_text(json.dumps(meta, indent=1))
    print(f"preview written to {outdir} ({total:.0f}s estimated)")
