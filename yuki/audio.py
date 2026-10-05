"""Voice backends, wav helpers and the audio -> mouth-shape tracker."""
import asyncio, re, subprocess, time, wave, zlib
from pathlib import Path
import numpy as np

SR = 24000


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def read_wav(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def to_wav(src, dst):
    run(["ffmpeg", "-y", "-i", str(src), "-ar", str(SR), "-ac", "1", str(dst)])


def silence(sec):
    return np.zeros(int(sec * SR), np.float32)


def trim(a, keep=0.06, thr=0.012):
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    s = max(0, idx[0] - int(keep * SR))
    e = min(len(a), idx[-1] + int(keep * SR))
    return a[s:e]


# ---------------------------------------------------------------- voices
async def _edge(text, voice, rate, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def synth_edge(text, voice, rate, tmp):
    mp3, wav = Path(tmp) / "x.mp3", Path(tmp) / "x.wav"
    err = None
    for attempt in range(4):
        try:
            asyncio.run(_edge(text, voice, rate, mp3))
            if mp3.exists() and mp3.stat().st_size > 500:
                break
        except Exception as e:  # network hiccup: retry
            err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"edge-tts failed after retries: {err}")
    to_wav(mp3, wav)
    return trim(read_wav(wav))


_FORMANTS = {"a": (730, 1090), "e": (530, 1840), "i": (270, 2290), "o": (570, 840), "u": (300, 870)}


def synth_babble(text):
    """Placeholder 'mumble' voice: syllable-timed vowel sounds. NOT speech; used to test lip-sync offline."""
    rng = np.random.default_rng(zlib.crc32(text.encode()))
    out = [silence(0.05)]
    for tok in re.findall(r"[A-Za-z']+|[.,!?;:]", text):
        if tok in ".!?":
            out.append(silence(0.34)); continue
        if tok in ",;:":
            out.append(silence(0.2)); continue
        vowels = re.findall(r"[aeiou]", tok.lower()) or ["a"]
        for i in range(max(1, len(re.findall(r"[aeiouy]+", tok.lower())))):
            f1, f2 = _FORMANTS[vowels[min(i, len(vowels) - 1)]]
            dur = float(rng.uniform(0.11, 0.2))
            n = int(dur * SR)
            t = np.arange(n) / SR
            f0 = 175 + 28 * np.sin(2 * np.pi * 1.7 * t + rng.uniform(0, 6)) + rng.uniform(-12, 12)
            phase = 2 * np.pi * np.cumsum(f0) / SR
            sig = np.zeros(n, np.float32)
            for h in range(1, 28):
                fr = h * 175
                amp = np.exp(-((fr - f1) / 170) ** 2) + 0.7 * np.exp(-((fr - f2) / 260) ** 2) + 0.06
                sig += (amp / h ** 0.35 * np.sin(h * phase)).astype(np.float32)
            env = np.sin(np.pi * t / dur) ** 0.8
            sig = sig * env.astype(np.float32)
            sig += rng.normal(0, 0.01, n).astype(np.float32) * env.astype(np.float32)
            out.append(sig / (np.abs(sig).max() + 1e-6) * 0.5)
        out.append(silence(0.05))
    return np.concatenate(out)


def silent_words(text):
    return silence(max(1.4, len(text.split()) / 2.6))


def synth(text, args, idx, tmp):
    """Return mono float32 audio at SR for one beat."""
    if args.audio_dir:
        for ext in ("wav", "mp3", "m4a", "ogg", "flac"):
            f = Path(args.audio_dir) / f"{idx + 1:03d}.{ext}"
            f2 = Path(args.audio_dir) / f"{idx + 1:02d}.{ext}"
            for cand in (f, f2):
                if cand.exists():
                    to_wav(cand, Path(tmp) / "x.wav")
                    return trim(read_wav(Path(tmp) / "x.wav"))
        raise SystemExit(f"Missing recording for beat {idx + 1} in {args.audio_dir} (expected {idx + 1:03d}.wav/.mp3)")
    if args.tts == "edge":
        return synth_edge(text, args.voice, args.rate, tmp)
    if args.tts == "babble":
        return synth_babble(text)
    return silent_words(text)


# ---------------------------------------------------------------- lip sync
def mouth_track(audio, n_frames, fps):
    """Per-frame mouth level 0..3 from loudness (0 closed, 1 small, 2 medium, 3 wide)."""
    hop = SR / fps
    rms = np.zeros(n_frames, np.float32)
    for f in range(n_frames):
        seg = audio[int(f * hop): int((f + 1) * hop * 1.4)]
        rms[f] = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0
    active = rms[rms > 0.006]
    ref = np.percentile(active, 90) if len(active) else 1.0
    lv = np.clip(rms / max(ref, 1e-4), 0, 1.3)
    sm = lv.copy()
    sm[1:-1] = 0.5 * lv[1:-1] + 0.25 * (lv[:-2] + lv[2:])
    lvl = np.where(sm < 0.11, 0, np.where(sm < 0.34, 1, np.where(sm < 0.66, 2, 3))).astype(np.int8)
    # remove one-frame flicker
    for i in range(1, n_frames - 1):
        if lvl[i - 1] == lvl[i + 1] != lvl[i]:
            lvl[i] = lvl[i - 1]
    return lvl, np.clip(sm, 0, 1)
