#!/usr/bin/env python3
"""Find the free Kokoro voice that sounds closest to YOUR voice sample and save it to voice/match.json.

    python tools/match_kokoro.py voice/ref.m4a

Every English female Kokoro voice reads the same paragraph; each reading is compared with your recording
(average pitch, pitch range and tone colour) and the closest wins. Runs on GitHub (workflow 'Match my voice').
"""
import json, sys, tempfile, wave
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_features as vf

TEXT = ("Have you ever noticed how some days start slowly, and then suddenly everything changes? "
        "I remember sitting at my desk, staring at the screen, thinking that I would never finish. "
        "But then something small happened, and it made me laugh. After that, the whole day felt lighter, "
        "and honestly, I think that is when I understood what really matters.")
VOICES = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova",
          "af_river", "af_sarah", "af_sky", "bf_alice", "bf_emma", "bf_isabella", "bf_lily"]


def say(pipes, voice):
    from kokoro import KPipeline
    lang = "b" if voice.startswith("bf") else "a"
    if lang not in pipes:
        pipes[lang] = KPipeline(lang_code=lang)
    parts = []
    for _gs, _ps, audio in pipes[lang](TEXT, voice=voice, speed=1.0):
        a = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
        parts.append(a.astype(np.float32).reshape(-1))
    x = np.concatenate(parts)
    path = tempfile.mktemp(suffix=".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return vf.features(vf.load(path))


def main():
    ref = vf.features(vf.load(sys.argv[1]))
    print(f"Your voice: pitch {ref['f0_med']:.0f} Hz (range {ref['f0_lo']:.0f}-{ref['f0_hi']:.0f} Hz)")
    pipes, rows = {}, []
    for v in VOICES:
        try:
            f = say(pipes, v)
        except Exception as e:
            print(f"  {v}: failed ({e})")
            continue
        if not f:
            print(f"  {v}: could not measure")
            continue
        d = vf.distance(ref, f)
        rows.append((d, v, f))
        print(f"  {v:14s} pitch {f['f0_med']:5.0f} Hz  distance {d:.3f}")
    if not rows:
        sys.exit("No Kokoro voice could be rendered.")
    rows.sort(key=lambda r: r[0])
    d, best, bf = rows[0]
    dest = Path(__file__).resolve().parent.parent / "voice" / "match.json"
    old = json.loads(dest.read_text()) if dest.exists() else {}
    old.update(kokoro_voice=best, speed=0.97, your_pitch_hz=round(ref["f0_med"]), voice_pitch_hz=round(bf["f0_med"]),
               distance=round(d, 3),
               runner_ups=[dict(voice=v, distance=round(x, 3), pitch_hz=round(f["f0_med"])) for x, v, f in rows[1:5]])
    dest.write_text(json.dumps(old, indent=2))
    print("\nBEST MATCH:", json.dumps(old, indent=2))


if __name__ == "__main__":
    main()
