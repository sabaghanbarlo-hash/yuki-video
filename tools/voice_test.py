#!/usr/bin/env python3
"""Voice check: reads a few lines with the flat voice and with the storyteller delivery, writes both as mp3 and prints
how much the pitch / loudness / pacing move.   python tools/voice_test.py [out_dir]"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from lab import voice as A

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "results")
OUT.mkdir(parents=True, exist_ok=True)
match = json.loads((HERE / "voice" / "match.json").read_text()) if (HERE / "voice" / "match.json").exists() else {}
voice, speed = match.get("kokoro_voice", "af_jessica"), float(match.get("speed", 1.0))
LINES = [
    "You know how people say college is the best time of your life?",
    "Yeah.",
    "I would like to know who these people are, what college they attended, and whether they were being held at gunpoint when they said that.",
    "And the worst part?",
    "Nobody prepared me for any of this.",
    "Meanwhile, I wake up at 7:43 AM for an 8 AM class, stare at the ceiling for three minutes, and seriously consider changing my identity.",
    'The professor says, "Interesting. Three out of five."',
    "THREE? I LOST SLEEP FOR A THREE? I HAVE AGED SEVENTEEN YEARS FOR THIS?",
    "Congratulations. You are now a background character in your own social life.",
    "At that point, I don't even want a degree. I want compensation.",
]


def f0_track(x, sr=A.SR):
    hop, win = int(0.02 * sr), int(0.04 * sr)
    out = []
    for i in range(0, len(x) - win, hop):
        seg = x[i:i + win] - x[i:i + win].mean()
        if np.sqrt((seg ** 2).mean()) < 0.02:
            continue
        ac = np.correlate(seg, seg, "full")[win - 1:]
        lo, hi = int(sr / 400), int(sr / 75)
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.35 * ac[0]:
            out.append(sr / k)
    return np.array(out)


def stats(x):
    f = f0_track(x)
    st = 12 * np.log2(f / np.median(f)) if len(f) > 20 else np.array([0.0])
    fr = int(0.05 * A.SR)
    rms = np.array([np.sqrt((x[i:i + fr] ** 2).mean()) for i in range(0, len(x) - fr, fr)])
    rms = rms[rms > 0.01]
    return dict(seconds=round(len(x) / A.SR, 1), pitch_median_hz=int(np.median(f)) if len(f) else 0,
                pitch_spread_semitones=round(float(np.std(st)), 2), pitch_p5_p95_semitones=round(float(np.percentile(st, 95) - np.percentile(st, 5)), 2),
                loudness_spread_db=round(float(np.std(20 * np.log10(rms))), 2))


res = {}
for name, expr, en in (("flat", False, 1.0), ("lively", True, 1.2), ("wild", True, 1.7)):
    parts = []
    for ln in LINES:
        parts.append(A.synth_kokoro(ln, voice, speed, "/tmp", expressive=expr, energy=en))
        parts.append(A.silence(0.38))
    x = np.concatenate(parts)
    x = x / max(1e-6, np.abs(x).max()) * 0.9
    wav = OUT / f"voice-test-{name}.wav"
    A.write_wav(wav, x)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-b:a", "96k", str(OUT / f"voice-test-{name}.mp3")], check=True)
    wav.unlink()
    res[name] = stats(x)
    print(name, res[name], flush=True)
(OUT / "voice-test.json").write_text(json.dumps({"voice": voice, "speed": speed, **res}, indent=1))
