#!/usr/bin/env python3
"""Yuki Lab: paste a script, get a finished animated science video (narration, scenes, subtitles, sound) as an MP4.

    python generate.py scripts/sample.txt --tts gemini           # natural, emotional Gemini voice (needs GEMINI_API_KEY); falls back to Kokoro
    python generate.py scripts/sample.txt                        # Kokoro voice matched to yours (voice/match.json)
    python generate.py scripts/sample.txt --tts edge             # Microsoft voices (needs internet)
    python generate.py scripts/sample.txt --tts clone            # your cloned voice (voice/ref.*), slow on CPU
    python generate.py scripts/sample.txt --audio my-voice.mp3   # your own narration recording (cut into sentences automatically)
    python generate.py scripts/sample.txt --tts babble           # offline test sound (not speech) - checks the whole pipeline
    python generate.py scripts/sample.txt --preview out/prev     # scene stills + plan.json, no voice needed (fast)
    python generate.py scripts/sample.txt --style voxel          # force one look: flat | voxel | toon | collage (default: chosen per scene)
    python generate.py scripts/collage-sample.txt --style collage  # Yuki in a corner, a picture every few seconds (see README)

Script format: see README.md. Everything but the words is optional: the director chooses places, looks, characters and
camera moves from what the script is about.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("--tts", default="kokoro", choices=["gemini", "kokoro", "voicestudio", "edge", "clone", "babble", "none"])
    ap.add_argument("--voice", default=None, help="voice name (default: the voice matched to yours in voice/match.json)")
    ap.add_argument("--pitch", default=None)
    ap.add_argument("--rate", default=None)
    ap.add_argument("--energy", type=float, default=1.2, help="delivery strength: 0.7 calm, 1.2 lively (default), 1.6 over the top")
    ap.add_argument("--flat-voice", action="store_true")
    ap.add_argument("--ref", default=None, help="voice sample for --tts clone (default: voice/ref.*)")
    ap.add_argument("--exaggeration", type=float, default=0.5)
    ap.add_argument("--steps", type=int, default=16, help="Voice Studio quality steps (more = better, slower)")
    ap.add_argument("--cfg", type=float, default=0.5)
    ap.add_argument("--audio", default=None, help="one recording of the whole narration (mp3/wav/m4a); used instead of a synthetic voice")
    ap.add_argument("--audio-dir", default=None, help="folder with 001.wav, 002.wav ... one recording per sentence")
    ap.add_argument("--style", default=None, choices=["flat", "voxel", "toon", "collage"], help="force one visual style for every scene (collage = Yuki + changing pictures)")
    ap.add_argument("--media", default="drawn", choices=["auto", "ai", "stock", "local", "drawn"], help="collage pictures: auto (yours > AI > stock > drawn), ai, stock, local (media/ folder only) or drawn (offline)")
    ap.add_argument("--seed", type=int, default=0, help="change it to get a different arrangement of the same script")
    ap.add_argument("--max-scenes", type=int)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out")
    ap.add_argument("--preview", default=None, help="write a still of every scene + plan.json into this folder and stop")
    ap.add_argument("--export-beats", action="store_true", help="list the numbered sentences (to record them yourself) and stop")
    args = ap.parse_args()

    match = {}
    mp = HERE / "voice" / "match.json"
    if mp.exists():
        try:
            match = json.loads(mp.read_text())
        except Exception:
            match = {}
    if args.tts == "gemini":
        import os
        args.voice = args.voice or os.environ.get("YUKI_GEMINI_VOICE") or "Leda"          # a Gemini voice name (Leda, Aoede, Sulafat ...)
        args.speed = float(match.get("speed", 1.0)) * 1.1
    elif args.tts == "kokoro":
        args.voice = args.voice or match.get("kokoro_voice") or "af_bella"
        args.speed = float(match.get("speed", 1.0)) * 1.1
    else:
        args.voice = args.voice or match.get("voice") or "en-US-AriaNeural"
    args.pitch = args.pitch or match.get("pitch") or "+0Hz"
    args.rate = args.rate or match.get("rate") or "-4%"
    args.expressive = not args.flat_voice
    if args.tts in ("clone", "voicestudio") and not args.ref:
        for ext in ("wav", "mp3", "m4a", "ogg", "flac"):
            if (HERE / "voice" / f"ref.{ext}").exists():
                args.ref = str(HERE / "voice" / f"ref.{ext}")
                break

    text = Path(args.script).read_text(encoding="utf-8")
    name = Path(args.script).stem
    out = Path(args.out or HERE / "output" / f"{name}.mp4")
    tmp = HERE / ".work" / name
    tmp.mkdir(parents=True, exist_ok=True)
    from lab import pipeline as P

    if args.preview:
        from lab.preview import make_preview
        make_preview(text, args, Path(args.preview))
        return
    if args.export_beats:
        plan = P.build_plan(text, args.seed, args.style, args.max_scenes)
        out.parent.mkdir(parents=True, exist_ok=True)
        p = out.with_suffix(".beats.txt")
        p.write_text("\n".join(f"{i + 1:03d}  {s['text']}" for i, (_, _, s) in enumerate(P.body_sentences(plan))), encoding="utf-8")
        print(f"wrote {p}")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    total, plan = P.make(text, args, out, tmp)
    print(f"done: {out}  ({total:.1f}s)")


if __name__ == "__main__":
    main()
