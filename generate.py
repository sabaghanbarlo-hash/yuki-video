#!/usr/bin/env python3
"""Call of Yuki video generator: English script -> explainer video with an animated chibi narrator.

    python generate.py stories/my-script.txt                   # free Edge voice (needs internet)
    python generate.py stories/my-script.txt --tts clone       # your cloned voice (voice/ref.wav), free, slow on CPU
    python generate.py stories/my-script.txt --tts babble      # offline test voice (not speech) to check animation
    python generate.py stories/my-script.txt --export-beats    # list the numbered beats (for recording your own voice)
    python generate.py stories/my-script.txt --audio-dir mine  # use your recordings: mine/001.wav, 002.mp3 ...
    python generate.py stories/my-story.txt --mode story       # storytelling video: cast, speech bubbles, sound effects

See yuki/script.py (explainer) and yuki/story.py (story) for the script formats and the optional [cues].
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from yuki.script import parse_script, plan          # noqa: E402
from yuki.render import render                       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--tts", default="kokoro", choices=["kokoro", "edge", "clone", "babble", "none"])
    ap.add_argument("--mode", default="explainer", choices=["explainer", "story"])
    ap.add_argument("--voice", default=None, help="edge voice name (default: the voice matched to yours in voice/match.json)")
    ap.add_argument("--pitch", default=None, help='edge pitch shift, e.g. "-8Hz"')
    ap.add_argument("--rate", default=None)
    ap.add_argument("--flat-voice", action="store_true", help="read everything in one flat tone (no storyteller delivery)")
    ap.add_argument("--no-music", action="store_true", help="story mode: no background music")
    ap.add_argument("--ref", default=None, help="voice sample for --tts clone (default: voice/ref.wav or .mp3)")
    ap.add_argument("--exaggeration", type=float, default=0.5, help="clone: 0.3 calm ... 0.8 very expressive")
    ap.add_argument("--cfg", type=float, default=0.5, help="clone: lower = faster, more relaxed pacing")
    ap.add_argument("--audio-dir")
    ap.add_argument("--out")
    ap.add_argument("--max-beats", type=int)
    ap.add_argument("--export-beats", action="store_true")
    args = ap.parse_args()

    match = {}
    mp = HERE / "voice" / "match.json"
    if mp.exists():
        try:
            match = json.loads(mp.read_text())
        except Exception:
            match = {}
    if args.tts == "kokoro":
        args.voice = args.voice or match.get("kokoro_voice") or "af_bella"
        args.speed = float(match.get("speed", 1.0))
    else:
        args.voice = args.voice or match.get("voice") or "en-US-AriaNeural"
    args.pitch = args.pitch or match.get("pitch") or "+0Hz"
    args.rate = args.rate or match.get("rate") or "-4%"
    args.music = not args.no_music
    args.expressive = not args.flat_voice

    if args.tts == "clone" and not args.ref:
        for cand in ("voice/ref.wav", "voice/ref.mp3", "voice/ref.m4a", "voice/ref.ogg", "voice/ref.flac"):
            if (HERE / cand).exists():
                args.ref = str(HERE / cand)
                break

    name = Path(args.script).stem
    out = Path(args.out or HERE / "output" / f"{name}.mp4")
    tmp = HERE / ".work" / name
    tmp.mkdir(parents=True, exist_ok=True)

    if args.mode == "story":
        from yuki.story import parse_story, plan_story
        from yuki.render_story import render_story
        title, beats, decl = parse_story(args.script)
        if args.max_beats:
            beats = beats[: args.max_beats]
        beats, cast = plan_story(title, beats, decl)
        spoken = [b for b in beats if not b.title]
        print(f"story: {len(spoken)} lines, cast: {', '.join(cast) or 'narrator only'}" + (f", title: {title}" if title else ""))
    else:
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

    total = render_story(beats, cast, args, out, tmp) if args.mode == "story" else render(beats, args, out, tmp)
    print(f"done: {out}  ({total:.1f}s)  subtitles: {out.with_suffix('.srt')}")


if __name__ == "__main__":
    main()
