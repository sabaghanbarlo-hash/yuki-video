#!/usr/bin/env python3
"""Call of Yuki video generator: English script -> explainer video with an animated chibi narrator.

    python generate.py stories/my-script.txt                   # free Edge voice (needs internet)
    python generate.py stories/my-script.txt --tts clone       # your cloned voice (voice/ref.wav), free, slow on CPU
    python generate.py stories/my-script.txt --tts babble      # offline test voice (not speech) to check animation
    python generate.py stories/my-script.txt --export-beats    # list the numbered beats (for recording your own voice)
    python generate.py stories/my-script.txt --audio-dir mine  # use your recordings: mine/001.wav, 002.mp3 ...

See yuki/script.py for the script format and the optional [cues].
"""
import argparse, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from yuki.script import parse_script, plan          # noqa: E402
from yuki.render import render                       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--tts", default="edge", choices=["edge", "clone", "babble", "none"])
    ap.add_argument("--voice", default="en-US-AriaNeural")
    ap.add_argument("--rate", default="-4%")
    ap.add_argument("--ref", default=None, help="voice sample for --tts clone (default: voice/ref.wav or .mp3)")
    ap.add_argument("--exaggeration", type=float, default=0.5, help="clone: 0.3 calm ... 0.8 very expressive")
    ap.add_argument("--cfg", type=float, default=0.5, help="clone: lower = faster, more relaxed pacing")
    ap.add_argument("--audio-dir")
    ap.add_argument("--out")
    ap.add_argument("--max-beats", type=int)
    ap.add_argument("--export-beats", action="store_true")
    args = ap.parse_args()

    if args.tts == "clone" and not args.ref:
        for cand in ("voice/ref.wav", "voice/ref.mp3", "voice/ref.m4a", "voice/ref.ogg", "voice/ref.flac"):
            if (HERE / cand).exists():
                args.ref = str(HERE / cand)
                break

    name = Path(args.script).stem
    out = Path(args.out or HERE / "output" / f"{name}.mp4")
    tmp = HERE / ".work" / name
    tmp.mkdir(parents=True, exist_ok=True)

    title, beats = parse_script(args.script)
    if args.max_beats:
        beats = beats[: args.max_beats]
    beats = plan(title, beats, Path(args.script).parent.parent)
    spoken = [b for b in beats if not b.title]
    print(f"{len(spoken)} beats" + (f", title: {title}" if title else ""))

    if args.export_beats:
        out.parent.mkdir(parents=True, exist_ok=True)
        p = out.with_suffix(".beats.txt")
        p.write_text("\n".join(f"{i + 1:03d}  {b.text}" for i, b in enumerate(spoken)), encoding="utf-8")
        print(f"wrote {p}")
        return

    total = render(beats, args, out, tmp)
    print(f"done: {out}  ({total:.1f}s)  subtitles: {out.with_suffix('.srt')}")


if __name__ == "__main__":
    main()
