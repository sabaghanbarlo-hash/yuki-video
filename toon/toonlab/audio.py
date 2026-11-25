"""Narration (the Yuki voice engine), timeline, sound effects and music bed."""
import hashlib, os, re, subprocess, tempfile, wave
from pathlib import Path
import numpy as np
from . import voice as V
from . import sfx as S

SR = V.SR
LEAD, TAIL = 0.45, 1.2


def synth_all(sents, args, tmp):
    tmp = Path(tmp)
    (tmp / "voice").mkdir(parents=True, exist_ok=True)
    out = []
    shard = getattr(args, "shard", None)          # (i, N): this machine only voices sentences n % N == i
    for n, s in enumerate(sents):
        if shard and n % shard[1] != shard[0]:
            out.append(None); continue
        key = hashlib.md5(f"t1|{args.tts}|{getattr(args, 'voice', '')}|{getattr(args, 'energy', 1)}|{getattr(args, 'speed', 1)}|{s['mood']}|{s['spoken']}".encode()).hexdigest()[:16]
        f = tmp / "voice" / f"{key}.npy"
        if f.exists():
            out.append(np.load(f)); continue
        print(f"  voicing {n + 1}/{len(sents)}: {s['spoken'][:60]}", flush=True)
        a = np.asarray(V.synth(s["spoken"], args, n, tmp, emotion=s["mood"]), np.float32)
        np.save(f, a)
        out.append(a)
    return out


def gap_after(s):
    g = s["pause"] if s.get("pause") is not None else (0.55 if s.get("para_end") else 0.2)
    if s["text"].rstrip().endswith("?"):
        g += 0.12
    return g


def timeline(sents, audio):
    t = LEAD
    for s, a in zip(sents, audio):
        s["t0"] = t
        s["t1"] = t + len(a) / SR
        t = s["t1"] + gap_after(s)
    sents[-1]["t1"] += 0.25
    return t - gap_after(sents[-1]) + TAIL


def _put(out, x, at, gain=1.0):
    i = int(at * SR)
    if i >= len(out) or i < 0:
        return
    seg = x[: len(out) - i] * gain
    out[i:i + len(seg)] += seg


def clean_voice(x):
    try:
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, "v.wav"), os.path.join(d, "c.wav")
            with wave.open(src, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", "highpass=f=85,agate=threshold=0.035:ratio=9000:range=0.22:attack=6:release=120,lowpass=f=11000", dst], check=True)
            with wave.open(dst, "rb") as w:
                y = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
        return y[: len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y)))
    except Exception as e:
        print("  [mix] voice clean-up skipped", type(e).__name__)
        return x


def mix(sents, audio, shots, total, music=True):
    n = int(total * SR) + SR
    voice = np.zeros(n, np.float32)
    for s, a in zip(sents, audio):
        _put(voice, a, s["t0"])
    pk = np.abs(voice).max()
    if pk > 0:
        voice = voice / pk * 0.86
    voice = clean_voice(voice)
    fx = np.zeros(n, np.float32)
    last = -9
    for s in sents:                                   # words -> effects, at the moment they are said
        for frac, name in s["sfx"]:
            g = S.get(name)
            at = s["t0"] + frac * (s["t1"] - s["t0"])
            if g is not None and at - last > 0.9:
                _put(fx, g, at, 0.42); last = at
    for i, sh in enumerate(shots):                    # cuts and pop-ups
        if i and sh["t0"] > 0.3:
            g = S.get("whoosh" if sh["kind"] in ("wide",) else "pop")
            if sh["kind"] == "closeup" and i % 2:
                g = None
            if g is not None:
                _put(fx, g, max(0, sh["t0"] - 0.03), 0.16)
        for ev in sh.get("events", []):
            g = S.get(ev["sfx"])
            if g is not None:
                _put(fx, g, ev["t"], 0.2)
    out = voice + fx
    if music:
        mus = S.music_lofi(total + 1, "calm")
        mus = np.resize(mus, n).astype(np.float32)
        mus = mus / (np.abs(mus).max() + 1e-6)
        env = np.abs(voice)
        w = int(0.3 * SR)
        env = np.convolve(env, np.ones(w, np.float32) / w, mode="same")
        env = np.clip(env / 0.08, 0, 1)
        w2 = int(0.7 * SR)
        env = np.convolve(env, np.ones(w2, np.float32) / w2, mode="same")
        duck = 1.0 - 0.62 * np.clip(env * 1.6, 0, 1)
        fade = np.ones(n, np.float32)
        fi, fo = int(1.2 * SR), int(1.8 * SR)
        fade[:fi] = np.linspace(0, 1, fi); fade[int(total * SR) - fo:int(total * SR)] = np.linspace(1, 0, fo); fade[int(total * SR):] = 0
        out = out + mus * 0.16 * duck * fade
    pk = np.abs(out).max()
    if pk > 0.95:
        out = np.tanh(out / pk * 1.1) / np.tanh(1.1) * 0.95
    return out[: int(total * SR)], voice[: int(total * SR)]


def write_wav(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
