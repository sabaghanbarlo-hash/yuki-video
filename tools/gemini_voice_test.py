"""Run by .github/workflows/gemini-voice-test.yml: lists the TTS models the key can see, then speaks two emotional lines in each voice."""
import os, re, sys, wave
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import gemini_tts as G

if not os.environ.get("GEMINI_API_KEY"):
    sys.exit("GEMINI_API_KEY is not set (Settings -> Secrets and variables -> Actions).")
print("TTS models visible to this key:", G.models())
LINES = [("worried", "Have you ever replayed a conversation in your head, wondering if you said something wrong?"),
         ("relieved", "Remember, you don't have to solve every thought that crosses your mind.")]
out = Path("output/voice-test"); out.mkdir(parents=True, exist_ok=True)
ok = 0
for v in [x.strip() for x in os.environ.get("VOICES", "Leda").split(",") if x.strip()]:
    for i, (tag, text) in enumerate(LINES):
        role, emo, st = G.feeling(text, first=(i == 0), last=(i == len(LINES) - 1))
        a = G.synth(text, v, dict(role=role, emotion=emo, strength=st))
        if a is None:
            print(f"  {v}/{tag}: no audio ({G.STATE['why'] or 'failed'})")
            continue
        with wave.open(str(out / f"{v}-{tag}.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(G.SR); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
        ok += 1
        print(f"  {v}/{tag}: {len(a) / G.SR:.1f}s  ({emo or role})")
print(f"{ok} clip(s) written")
sys.exit(0 if ok else 1)
