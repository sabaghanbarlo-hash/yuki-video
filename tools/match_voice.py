#!/usr/bin/env python3
"""Find the built-in (free) Edge voice that sounds closest to YOUR voice sample and save it to voice/match.json.

    python tools/match_voice.py voice/ref.m4a

Every English female neural voice reads the same paragraph; each reading is compared with your recording
(pitch, pitch range and tone colour). The best one is then nudged in pitch so its average pitch equals yours.
Needs internet (run it in GitHub Actions: workflow 'Match my voice').
"""
import asyncio, json, sys, tempfile
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_features as vf

TEXT = ("Have you ever noticed how some days start slowly, and then suddenly everything changes? "
        "I remember sitting at my desk, staring at the screen, thinking that I would never finish. "
        "But then something small happened, and it made me laugh. After that, the whole day felt lighter, "
        "and honestly, I think that is when I understood what really matters.")


async def synth(voice, out, pitch="+0Hz", rate="+0%"):
    import edge_tts
    await edge_tts.Communicate(TEXT, voice, rate=rate, pitch=pitch).save(str(out))


def analyse(voice, pitch="+0Hz", rate="+0%"):
    mp3 = Path(tempfile.mktemp(suffix=".mp3"))
    for _ in range(3):
        try:
            asyncio.run(synth(voice, mp3, pitch, rate))
            if mp3.exists() and mp3.stat().st_size > 2000:
                break
        except Exception as e:
            print("   retry", voice, e)
    else:
        return None
    return vf.features(vf.load(mp3))


def main():
    ref_path = sys.argv[1]
    ref = vf.features(vf.load(ref_path))
    print(f"Your voice: pitch {ref['f0_med']:.0f} Hz (range {ref['f0_lo']:.0f}-{ref['f0_hi']:.0f} Hz)")
    import edge_tts
    voices = asyncio.run(edge_tts.list_voices())
    cands = [v["ShortName"] for v in voices if v["Locale"].startswith("en-") and v["Gender"] == "Female"]
    print(f"Trying {len(cands)} voices...")
    rows = []
    for v in cands:
        f = analyse(v)
        if not f:
            print(f"  {v}: failed")
            continue
        d = vf.distance(ref, f)
        rows.append((d, v, f))
        print(f"  {v:34s} pitch {f['f0_med']:5.0f} Hz  distance {d:.3f}")
    rows.sort(key=lambda r: r[0])
    best_d, best, bf = rows[0]
    shift = int(round(max(-45, min(45, ref["f0_med"] - bf["f0_med"]))))
    pitch = f"{shift:+d}Hz"
    f2 = analyse(best, pitch=pitch)
    d2 = vf.distance(ref, f2) if f2 else best_d
    if f2 and d2 > best_d:                      # shifting made it worse: keep the plain voice
        pitch, f2, d2 = "+0Hz", bf, best_d
    out = dict(voice=best, pitch=pitch, rate="-4%", your_pitch_hz=round(ref["f0_med"]),
               voice_pitch_hz=round((f2 or bf)["f0_med"]), distance=round(d2, 3),
               runner_ups=[dict(voice=v, distance=round(d, 3), pitch_hz=round(f["f0_med"])) for d, v, f in rows[1:6]])
    dest = Path(__file__).resolve().parent.parent / "voice" / "match.json"
    dest.write_text(json.dumps(out, indent=2))
    print("\nBEST MATCH:", json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
