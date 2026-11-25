#!/usr/bin/env python3
"""Yuki Toon Studio: paste a script, get a thick-outline cartoon explainer (Yuki + cast) with your own voice.

    python generate_toon.py scripts/sample.txt --tts voicestudio        # your cloned voice (voice/ref.*), the same engine as the main Yuki system
    python generate_toon.py scripts/sample.txt --tts kokoro             # the free Kokoro voice matched to yours
    python generate_toon.py scripts/sample.txt --tts babble             # offline test sound (no speech) - checks animation + lip-sync
    python generate_toon.py scripts/sample.txt --preview out/prev       # one still per shot + contact sheet, no voice
    python generate_toon.py scripts/sample.txt --audio my-voice.mp3     # your own recording (cut into sentences at your pauses)
"""
import argparse, json, subprocess, sys, time
from multiprocessing import get_context
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_R = {}


def _init(r):
    _R["r"] = r


def _job(i):
    return _R["r"].frame(i)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("--tts", default="kokoro", choices=["voicestudio", "kokoro", "gemini", "edge", "clone", "babble", "none"])
    ap.add_argument("--voice", default=None)
    ap.add_argument("--ref", default=None)
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--energy", type=float, default=1.2)
    ap.add_argument("--audio", default=None)
    ap.add_argument("--audio-dir", default=None)
    ap.add_argument("--format", default="long", choices=["long", "short"])
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--captions", action="store_true")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--max-sentences", type=int)
    ap.add_argument("--out")
    ap.add_argument("--shard", default=None, help="i/N: only voice every Nth sentence starting at i, then stop (used by parallel machines)")
    ap.add_argument("--count", action="store_true", help="print the number of sentences and exit")
    ap.add_argument("--preview", default=None)
    a = ap.parse_args()

    from toonlab import director, audio as A, voice as V, render as R
    W, H = (1280, 720) if a.format == "long" else (720, 1280)
    match = {}
    mp = HERE / "voice" / "match.json"
    if mp.exists():
        try:
            match = json.loads(mp.read_text())
        except Exception:
            match = {}
    if a.tts == "kokoro":
        a.voice = a.voice or match.get("kokoro_voice") or "af_bella"
        a.speed = float(match.get("speed", 1.0)) * 1.1
    elif a.tts == "gemini":
        import os
        a.voice = a.voice or os.environ.get("YUKI_GEMINI_VOICE") or "Leda"
        a.speed = 1.1
    else:
        a.voice = a.voice or match.get("voice") or "en-US-AriaNeural"
        a.speed = 1.0
    a.pitch, a.rate, a.expressive = "+0Hz", "-4%", True
    a.exaggeration, a.cfg = 0.5, 0.5
    if a.tts in ("clone", "voicestudio") and not a.ref:
        for ext in ("wav", "mp3", "m4a", "ogg", "flac"):
            if (HERE / "voice" / f"ref.{ext}").exists():
                a.ref = str(HERE / "voice" / f"ref.{ext}")
                break
    name = Path(a.script).stem
    out = Path(a.out or HERE / "output" / f"{name}.mp4")
    tmp = HERE / ".work" / name
    tmp.mkdir(parents=True, exist_ok=True)

    text = Path(a.script).read_text(encoding="utf-8")
    title, sents = director.parse(text)
    if a.max_sentences:
        sents = sents[: a.max_sentences]
    director.analyze(sents, a.seed)
    print(f"{len(sents)} sentences", flush=True)
    if a.count:
        return
    a.shard = None if not a.shard else tuple(int(x) for x in a.shard.split("/"))

    if a.preview:
        pv = Path(a.preview); pv.mkdir(parents=True, exist_ok=True)
        t = A.LEAD
        for s in sents:
            s["t0"] = t; s["t1"] = t + len(s["spoken"].split()) / 2.6 + 0.3; t = s["t1"] + A.gap_after(s)
        shots = director.make_shots(sents, a.seed, a.format)
        fps = a.fps
        n = int((t + 1) * fps)
        vis = np.full(n, 2, np.int8); amp = np.full(n, 0.7, np.float32)
        r = R.Renderer(shots, sents, vis, amp, fps, W, H, a.seed, a.captions)
        from PIL import Image
        for j, sh in enumerate(shots):
            tt = sh["t0"] + min(1.4, (sh["t1"] - sh["t0"]) * 0.75)
            data = r.frame(int(tt * fps))
            Image.frombytes("RGBA", (W, H), data).convert("RGB").save(pv / f"shot_{j + 1:02d}_{sh['kind']}.png")
        json.dump([{k: v for k, v in s.items() if k not in ("icons",)} | {"icons": [x[2] for x in s["icons"]]} for s in shots], open(pv / "plan.json", "w"), indent=1, default=str)
        print(f"{len(shots)} shots -> {pv}")
        return

    audio = A.synth_all(sents, a, tmp)
    if a.shard:
        print(f"shard {a.shard[0] + 1}/{a.shard[1]} voiced", flush=True)
        return
    total = A.timeline(sents, audio)
    shots = director.make_shots(sents, a.seed, a.format)
    track, voice_t = A.mix(sents, audio, shots, total, music=not a.no_music)
    fps = a.fps
    nfr = int(total * fps)
    vis, amp = V.viseme_track(voice_t, nfr + 2, fps)
    r = R.Renderer(shots, sents, vis, amp, fps, W, H, a.seed, a.captions)
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = tmp / "track.wav"
    A.write_wav(wav, track)
    vid = tmp / "video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(vid)], stdin=subprocess.PIPE)
    import os
    nw = a.workers or max(1, (os.cpu_count() or 2))
    ctx = get_context("fork")
    t0 = time.time()
    with ctx.Pool(nw, initializer=_init, initargs=(r,)) as pool:
        for k, fr in enumerate(pool.imap(_job, range(nfr), chunksize=6)):
            ff.stdin.write(fr)
            if k % 120 == 0:
                print(f"  frame {k}/{nfr}  ({k / max(1e-6, time.time() - t0):.1f} fps)", flush=True)
    ff.stdin.close(); ff.wait()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True)
    print(f"done: {out}  ({total:.1f}s)")


if __name__ == "__main__":
    main()
