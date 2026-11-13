"""Voice backends, wav helpers and the audio -> mouth-shape tracker."""
import asyncio, hashlib, re, subprocess, time, wave, zlib
from pathlib import Path
import numpy as np
from . import voice_polish as VP

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
    """Cut silence at both ends. Word endings (s, t, f, soft vowels) are quiet, so the cut level is low and a generous
    tail is kept and faded out: the last word is never chopped."""
    keep = max(keep, 0.12)
    thr = min(thr, 0.004)
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    s = max(0, idx[0] - int(keep * SR))
    e = min(len(a), idx[-1] + int(keep * SR))
    out = a[s:e].copy()
    n = min(len(out) // 2, int(0.02 * SR))
    if n > 1:
        out[-n:] *= np.linspace(1, 0, n, dtype=np.float32)
    return out


# ---------------------------------------------------------------- voices
async def _edge(text, voice, rate, out, pitch="+0Hz"):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))


def synth_edge(text, voice, rate, tmp, pitch="+0Hz"):
    mp3, wav = Path(tmp) / "x.mp3", Path(tmp) / "x.wav"
    err = None
    for attempt in range(4):
        try:
            asyncio.run(_edge(text, voice, rate, mp3, pitch))
            if mp3.exists() and mp3.stat().st_size > 500:
                break
        except Exception as e:  # network hiccup: retry
            err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"edge-tts failed after retries: {err}")
    to_wav(mp3, wav)
    return trim(read_wav(wav))



# ---------------------------------------------------------------- Kokoro (Apache-2.0, free, runs on CPU, no online service)
_KP = {}
KOKORO_F = ["af_bella", "af_nicole", "af_sarah", "af_sky", "bf_emma", "af_nova", "af_heart", "bf_isabella"]
KOKORO_M = ["am_adam", "am_michael", "am_eric", "bm_george", "am_liam", "bm_lewis", "am_puck", "bm_daniel"]


def _kokoro(lang):
    if lang not in _KP:
        from kokoro import KPipeline
        print("  loading the voice model (first time takes a minute)...", flush=True)
        _KP[lang] = KPipeline(lang_code=lang)
    return _KP[lang]


def _kokoro_raw(text, voice, speed):
    pipe = _kokoro("b" if voice[:2] in ("bf", "bm") else "a")
    chunks = []
    for _gs, _ps, audio in pipe(text, voice=voice, speed=float(speed)):
        a = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
        chunks.append(a.astype(np.float32).reshape(-1))
        chunks.append(silence(0.08))
    if not chunks:
        return silence(0.3)
    return trim(np.concatenate(chunks[:-1]))


def synth_kokoro(text, voice, speed, tmp, emotion=None, expressive=True, pitch_bias=0.0, energy=1.0):
    """Speak `text` with a Kokoro voice (af_/am_ = American, bf_/bm_ = British). Returns mono float32 at 24 kHz.
    expressive=True reads it like a storyteller (see expressive.py) instead of one flat sentence-reader tone."""
    if not expressive:
        return _kokoro_raw(text, voice, speed)
    from . import expressive as E
    return E.speak(text, lambda t, sp: _kokoro_raw(t, voice, sp), mood=emotion or "neutral", base_speed=float(speed),
                   pitch_bias=pitch_bias, trim=lambda x: trim(x, keep=0.05), energy=energy)


# ---------------------------------------------------------------- cloned voice (Chatterbox, MIT licence, free, runs on CPU)
_CB = {}


def _chatterbox():
    if "m" not in _CB:
        import torch
        _orig = torch.load
        torch.load = lambda *a, **k: _orig(*a, **{**k, "map_location": torch.device("cpu")})  # CPU-only runners
        from chatterbox.tts import ChatterboxTTS
        print("  loading the voice model (first time takes a few minutes)...", flush=True)
        _CB["m"] = ChatterboxTTS.from_pretrained(device="cpu")
    return _CB["m"]


def _file_md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def synth_clone(text, ref, tmp, exaggeration=0.5, cfg=0.5):
    """Speak `text` in the voice of the recording `ref`. Sentence by sentence; finished sentences are cached on disk
    so a re-run (or a crashed run) does not start from zero."""
    if not ref or not Path(ref).exists():
        raise SystemExit("Cloned voice needs a sample of your voice: put it at voice/ref.wav (10-30 s, clean, one speaker) "
                         "or pass --ref path/to/sample.wav")
    cache = Path(tmp) / "clone_cache"
    cache.mkdir(parents=True, exist_ok=True)
    rid = _file_md5(ref)[:10]
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]
    pieces = []
    for sent in sents:
        key = hashlib.md5(f"v2|{rid}|{exaggeration}|{cfg}|{sent}".encode()).hexdigest()[:16]
        f = cache / f"{key}.wav"
        if not f.exists():
            import torchaudio
            m = _chatterbox()
            wav = m.generate(sent, audio_prompt_path=str(ref), exaggeration=exaggeration, cfg_weight=cfg)
            raw = cache / f"{key}_raw.wav"
            torchaudio.save(str(raw), wav.detach().cpu().reshape(1, -1), m.sr)
            to_wav(raw, f)
            raw.unlink(missing_ok=True)
        pieces.append(trim(read_wav(f), keep=0.04))
        pieces.append(silence(0.16))
    return np.concatenate(pieces[:-1]) if pieces else silence(0.5)


# ---------------------------------------------------------------- Voice Studio (OmniVoice engine, free, runs on CPU)
_VS = {}
VS_MODEL = "k2-fsa/OmniVoice"


def _voicestudio(ref):
    if "m" not in _VS:
        import torch
        from omnivoice import OmniVoice
        print("  loading the Voice Studio model (first time downloads it)...", flush=True)
        _VS["m"] = OmniVoice.from_pretrained(VS_MODEL, device_map="cpu", dtype=torch.float32)
    if ref and _VS.get("ref") != str(ref):
        txt = Path(str(ref) + ".txt")
        if not txt.exists():
            txt = Path(ref).with_suffix(".txt")
        rt = txt.read_text().strip() if txt.exists() else None
        if rt is None:
            _VS["m"].load_asr_model("openai/whisper-small")      # no transcript next to the sample: read it ourselves
        wav = Path("/tmp") / f"vs_ref_{_file_md5(ref)[:8]}.wav"
        if not wav.exists():
            to_wav(ref, wav)
        _VS["prompt"] = _VS["m"].create_voice_clone_prompt(ref_audio=str(wav), ref_text=rt)
        _VS["ref"] = str(ref)
    return _VS["m"]


PACE = 0.98              # barely above the model's own pace: no 'sped up' sound
SYL_SEC = 0.160          # natural, lively speech: about 6.5 syllables a second
MAX_SLOW = 1.30          # a take that runs more than 30% longer than natural speech is re-recorded


def _syllables(t):
    n = 0
    for w in re.findall(r"[A-Za-z']+", t):
        g = len(re.findall(r"[aeiouy]+", w.lower()))
        if w.lower().endswith("e") and g > 1 and not w.lower().endswith(("le", "ee")):
            g -= 1
        n += max(1, g)
    return max(1, n)


def _phrases(sent):
    """Split a sentence at commas, colons, dashes ... into short phrases (a model drifts into stretched words on long runs)."""
    parts = [p.strip() for p in re.split(r"(?<=[,;:])\s+|\s+[-\u2013\u2014]+\s+", sent) if p.strip()]
    long_ = []
    for p in parts:                                              # a long run without a comma: break it before a conjunction
        w = p.split()
        cut = next((i for i in range(4, len(w) - 3) if w[i].lower() in ("to", "and", "but", "because", "so", "when", "while", "that", "which", "or")), None) if len(w) > 11 else None
        long_ += [" ".join(w[:cut]), " ".join(w[cut:])] if cut else [p]
    parts, out = long_, []
    for p in parts:                                              # never leave a one- or two-word crumb on its own
        if out and len(p.split()) < 3:
            out[-1] += " " + p
        else:
            out.append(p)
    if len(out) > 1 and len(out[0].split()) < 3:
        out[1] = out[0] + " " + out[1]
        out = out[1:]
    return out or [sent]


def _too_slow(a, text):
    return len(a) / SR > max(0.6, _syllables(text) * SYL_SEC * MAX_SLOW)


def _gentle(a, text, tmp):
    """Last resort after several takes: ease a still-dragging phrase by at most 10% (no audible speed-up)."""
    want = _syllables(text) * SYL_SEC * MAX_SLOW
    dur = len(a) / SR
    if dur <= want or dur < 0.6:
        return a
    rate = min(1.10, dur / want)
    src, dst = Path(tmp) / "pace_in.wav", Path(tmp) / "pace_out.wav"
    write_wav(src, a)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter:a", f"atempo={rate:.4f}", "-ar", str(SR), "-ac", "1", str(dst)], check=True)
    return read_wav(dst)


def synth_voicestudio(text, ref, tmp, speed=1.0, steps=16, emotion=None, instruct="female, young adult, warm, expressive"):
    """Voice Studio (OmniVoice) narration: breaths and dead air removed, delivery set per mood (see voice_polish.py).
    Every sentence is spoken phrase by phrase and each phrase is brought to an even, natural pace.  Finished phrases are cached on disk."""
    from . import expressive as E
    cache = Path(tmp) / "vs_cache"
    cache.mkdir(parents=True, exist_ok=True)
    ref0 = ref if ref and Path(ref).exists() else None
    pieces, prev_words = [], 0
    for k, sent in enumerate(VP.split_sentences(text)):
        sm = E.sentence_mood(sent, emotion or "neutral")          # every sentence has its own feeling
        cfg = VP.mood_cfg(sm)
        ref = VP.pick_ref(ref0, sm) if ref0 else None
        rid = _file_md5(ref)[:10] if ref else "design"
        words = len(sent.split())
        sp = float(speed) * max(1.0, cfg["speed"]) * PACE          # a sad line may rest in its pauses, but its words are never dragged
        if sent.endswith("!"):
            sp *= 1.03
        if words <= 3 and prev_words >= 8 and sent.endswith((".", "!")):     # short punchline after a long line: slightly slower, deadpan
            sp *= 0.95
        sp = round(sp * (1 + 0.025 * E._jit(sent, 1)), 3)
        pre, suf = E.vocal_tag(sent, sm, k)
        phr = _phrases(sent)
        for n, ph in enumerate(phr):
            spoken = (pre if n == 0 else "") + ph + (suf if n == len(phr) - 1 else "")
            key = hashlib.md5(f"v6|{rid}|{sp}|{steps}|{spoken}".encode()).hexdigest()[:16]
            f = cache / f"{key}.wav"
            if not f.exists():
                import torch, torchaudio
                m = _voicestudio(ref)
                kw = dict(text=spoken, language="en", num_step=steps, speed=sp)
                if ref:
                    kw["voice_clone_prompt"] = _VS["prompt"]
                else:
                    kw["instruct"] = instruct
                best = None
                for take in range(4):                                  # a take with a dragged word is simply recorded again, like an actor would
                    torch.manual_seed(1000 * take + int(key[:6], 16) % 997)
                    wav = m.generate(**kw)[0].detach().cpu().reshape(1, -1)
                    raw = cache / f"{key}_raw.wav"
                    torchaudio.save(str(raw), wav, m.sampling_rate)
                    to_wav(raw, cache / f"{key}_take.wav")
                    raw.unlink(missing_ok=True)
                    cand = VP.polish(read_wav(cache / f"{key}_take.wav"))
                    if best is None or len(cand) < len(best):
                        best = cand
                    if not _too_slow(cand, ph):
                        best = cand
                        break
                (cache / f"{key}_take.wav").unlink(missing_ok=True)
                write_wav(f, best)
            a = _gentle(read_wav(f), ph, tmp)
            a = VP.gain_db(a, cfg["db"] + (1.0 if sent.endswith("!") else 0.0))
            pieces.append(a)
            if n < len(phr) - 1:
                pieces.append(silence(0.09 if ph.endswith(",") else 0.14))      # a breath between phrases
        gap = cfg["gap"] + (0.12 if sent.endswith("?") else 0.0) + (0.22 if words <= 6 and sent.endswith("?") else 0.0)
        pieces.append(silence(gap * 0.9))
        prev_words = words
    return np.concatenate(pieces[:-1]) if pieces else silence(0.5)


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


def synth_character(text, info, args, tmp, emotion=None):
    """A supporting character's line: own edge voice (clone/own recordings are for the narrator only)."""
    if args.tts == "kokoro":
        v = info.get("kvoice") or (KOKORO_F if info["gender"] == "F" else KOKORO_M)[0]
        if v == getattr(args, "voice", None):                      # never the same voice as the narrator
            pool = KOKORO_F if info["gender"] == "F" else KOKORO_M
            v = pool[(pool.index(v) + 1) % len(pool)] if v in pool else pool[0]
        return synth_kokoro(text, v, 1.0, tmp, emotion=emotion, expressive=getattr(args, "expressive", True), energy=getattr(args, "energy", 1.2))
    if args.tts == "gemini":                                         # supporting characters: their own Gemini voice (never the narrator's), Kokoro if Gemini is unavailable
        from . import gemini_tts as G
        pool = ["Aoede", "Zephyr", "Achernar"] if info["gender"] == "F" else ["Puck", "Charon", "Orus"]
        pool = [v for v in pool if v != getattr(args, "voice", None)]
        a = G.synth(text, pool[sum(map(ord, info.get("voice", "x"))) % len(pool)], dict(role="example", emotion=emotion, strength=1.0 if emotion else 0.0))
        if a is not None:
            return trim(np.asarray(a, np.float32) / max(1.0, float(np.abs(a).max()) / 0.9))
        v = info.get("kvoice") or (KOKORO_F if info["gender"] == "F" else KOKORO_M)[0]
        return synth_kokoro(text, v, 1.0, tmp, emotion=emotion, expressive=getattr(args, "expressive", True), energy=getattr(args, "energy", 1.2))
    if args.tts in ("edge", "clone"):
        return synth_edge(text, info["voice"], "+0%", tmp, info["pitch"])
    if args.tts == "babble":
        a = synth_babble(text)
        k = 1.18 if info["gender"] == "F" else 0.86
        return np.interp(np.arange(0, len(a), k), np.arange(len(a)), a).astype(np.float32)
    return silent_words(text)


def silent_words(text):
    return silence(max(1.4, len(text.split()) / 2.6))


FALLBACK = dict(used=False)       # set when the last gemini sentence had to use the fallback voice (the pipeline then does not cache it)


def _fallback_voice(text, args, tmp, emotion):
    """Kokoro (the voice matched to the user's sample), else Microsoft edge, when Gemini cannot answer."""
    import json as _json
    kv = "af_bella"
    try:
        kv = _json.loads((Path(__file__).resolve().parent.parent / "voice" / "match.json").read_text()).get("kokoro_voice") or kv
    except Exception:
        pass
    try:
        return synth_kokoro(text, kv, getattr(args, "speed", 1.0), tmp, emotion=emotion, expressive=getattr(args, "expressive", True), energy=getattr(args, "energy", 1.2))
    except Exception as e:
        print(f"  [voice] kokoro fallback failed ({type(e).__name__}); trying edge", flush=True)
        return synth_edge(text, "en-US-AriaNeural", "-4%", tmp)


def synth_gemini_only(text, args, ctx=None):
    """Gemini audio or None (no fallback): the pipeline decides what to do when some sentences cannot be voiced."""
    from . import gemini_tts as G
    a = G.synth(text, getattr(args, "voice", None), ctx)
    return None if a is None else trim(np.asarray(a, np.float32) / max(1.0, float(np.abs(a).max()) / 0.9))


def synth_gemini_take(texts, args, ctxs=None):
    """Gemini audio for several consecutive sentences spoken as one flowing take, or None (the pipeline decides what to do)."""
    from . import gemini_tts as G
    a = G.synth_take(texts, getattr(args, "voice", None), ctxs)
    return None if a is None else trim(np.asarray(a, np.float32) / max(1.0, float(np.abs(a).max()) / 0.9), keep=0.05)


TAKE_SLOW = 1.5          # a whole take may run this much longer than natural speech (it contains the pauses between sentences) before it is recorded again


def synth_voicestudio_take(texts, ref, tmp, speed=1.0, steps=16, emotion=None, instruct="female, young adult, warm, expressive", k0=0):
    """Voice Studio narration of SEVERAL consecutive sentences in ONE go.  The model hears the whole thought, so the intonation runs across the
    commas and from sentence to sentence like a person talking (before, every phrase was recorded alone and glued together, which sounds like a robot
    reading words).  Only real dead air is shortened; natural pauses stay.  Finished takes are cached on disk."""
    from . import expressive as E
    from collections import Counter
    cache = Path(tmp) / "vs_cache"
    cache.mkdir(parents=True, exist_ok=True)
    ref0 = ref if ref and Path(ref).exists() else None
    moods = [E.sentence_mood(t, emotion or "neutral") for t in texts]
    top = [m for m, _ in Counter(moods).most_common() if m != "neutral"]
    dom = top[0] if top else "neutral"
    cfg = VP.mood_cfg(dom)
    ref = VP.pick_ref(ref0, dom) if ref0 else None
    rid = _file_md5(ref)[:10] if ref else "design"
    spoken = []
    for j, t in enumerate(texts):
        pre, suf = E.vocal_tag(t, moods[j], k0 + j)
        spoken.append(pre + t + suf)
    text = " ".join(spoken)
    sp = round(float(speed) * max(1.0, cfg["speed"]) * PACE, 3)
    key = hashlib.md5(f"vf1|{rid}|{sp}|{steps}|{text}".encode()).hexdigest()[:16]
    f = cache / f"{key}.wav"
    if not f.exists():
        import torch, torchaudio
        m = _voicestudio(ref)
        kw = dict(text=text, language="en", num_step=steps, speed=sp)
        if ref:
            kw["voice_clone_prompt"] = _VS["prompt"]
        else:
            kw["instruct"] = instruct
        syl = sum(_syllables(t) for t in texts)
        limit = max(1.0, syl * SYL_SEC * TAKE_SLOW)
        best = None
        for take in range(4):                                    # a take with dragged words is simply recorded again, like an actor would
            torch.manual_seed(1000 * take + int(key[:6], 16) % 997)
            wav = m.generate(**kw)[0].detach().cpu().reshape(1, -1)
            raw = cache / f"{key}_raw.wav"
            torchaudio.save(str(raw), wav, m.sampling_rate)
            to_wav(raw, cache / f"{key}_take.wav")
            raw.unlink(missing_ok=True)
            cand = VP.polish(read_wav(cache / f"{key}_take.wav"), max_gap=0.42, min_gap=0.60)
            if best is None or len(cand) < len(best):
                best = cand
            if len(cand) / SR <= limit:
                best = cand
                break
        (cache / f"{key}_take.wav").unlink(missing_ok=True)
        write_wav(f, best)
    return VP.level(read_wav(f))


def synth_gemini(text, args, tmp, emotion=None, ctx=None):
    from . import gemini_tts as G
    a = G.synth(text, getattr(args, "voice", None), ctx)
    FALLBACK["used"] = a is None
    if a is None:
        return _fallback_voice(text, args, tmp, emotion)
    return trim(np.asarray(a, np.float32) / max(1.0, float(np.abs(a).max()) / 0.9))


def synth(text, args, idx, tmp, emotion=None, ctx=None):
    """Return mono float32 audio at SR for one beat.  ctx (role/emotion/strength) tells the gemini voice how to act the sentence."""
    if args.audio_dir:
        for ext in ("wav", "mp3", "m4a", "ogg", "flac"):
            f = Path(args.audio_dir) / f"{idx + 1:03d}.{ext}"
            f2 = Path(args.audio_dir) / f"{idx + 1:02d}.{ext}"
            for cand in (f, f2):
                if cand.exists():
                    to_wav(cand, Path(tmp) / "x.wav")
                    return trim(read_wav(Path(tmp) / "x.wav"))
        raise SystemExit(f"Missing recording for beat {idx + 1} in {args.audio_dir} (expected {idx + 1:03d}.wav/.mp3)")
    if args.tts == "gemini":
        return synth_gemini(text, args, tmp, emotion=emotion, ctx=ctx)
    if args.tts == "kokoro":
        return synth_kokoro(text, args.voice, getattr(args, "speed", 1.0), tmp, emotion=emotion, expressive=getattr(args, "expressive", True), energy=getattr(args, "energy", 1.2))
    if args.tts == "edge":
        return synth_edge(text, args.voice, args.rate, tmp, getattr(args, "pitch", "+0Hz"))
    if args.tts == "clone":
        return synth_clone(text, getattr(args, "ref", None), tmp, getattr(args, "exaggeration", 0.5), getattr(args, "cfg", 0.5))
    if args.tts == "voicestudio":
        return synth_voicestudio(text, getattr(args, "ref", None), tmp, getattr(args, "speed", 1.0), getattr(args, "steps", 16), emotion=emotion)
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


def viseme_track(audio, n_frames, fps):
    """Per-frame mouth shape from the sound itself: 0 closed, 1 mid "eh", 2 wide "ah", 3 small, 4 "ee" (wide, thin), 5 "oo" (round).
    Uses loudness for open/closed and the spectrum (where the vowel energy sits) for the shape."""
    hop = SR / fps
    win = 1024
    rms = np.zeros(n_frames, np.float32)
    cls = np.zeros(n_frames, np.int8)
    freqs = np.fft.rfftfreq(win, 1.0 / SR)
    band = lambda lo, hi: (freqs >= lo) & (freqs < hi)
    b_lo, b_f1, b_f2, b_hi = band(150, 450), band(450, 1100), band(1400, 3200), band(4500, 9000)
    hann = np.hanning(win).astype(np.float32)
    for f in range(n_frames):
        c = int((f + 0.5) * hop)
        seg = audio[max(0, c - win // 2): c + win // 2]
        if len(seg) < win:
            seg = np.pad(seg, (0, win - len(seg)))
        rms[f] = np.sqrt(np.mean(seg ** 2))
        sp = np.abs(np.fft.rfft(seg * hann)) ** 2
        lo, f1, f2, hi = sp[b_lo].sum(), sp[b_f1].sum(), sp[b_f2].sum(), sp[b_hi].sum()
        tot = lo + f1 + f2 + 1e-9
        if hi > 1.2 * (lo + f1 + f2):
            cls[f] = 3
        elif f2 / tot > 0.38:
            cls[f] = 4
        elif lo / tot > 0.55 and f1 < 0.45 * lo:
            cls[f] = 5
        elif f1 / tot > 0.5:
            cls[f] = 2
        else:
            cls[f] = 1
    active = rms[rms > 0.006]
    ref = np.percentile(active, 90) if len(active) else 1.0
    lv = np.clip(rms / max(ref, 1e-4), 0, 1.3)
    sm = lv.copy()
    sm[1:-1] = 0.65 * lv[1:-1] + 0.175 * (lv[:-2] + lv[2:])
    vis = np.zeros(n_frames, np.int8)
    for f in range(n_frames):
        if sm[f] < 0.10:
            vis[f] = 0
        elif sm[f] < 0.24:
            vis[f] = 3 if cls[f] in (1, 2, 3) else cls[f]
        else:
            vis[f] = cls[f]
            if vis[f] == 1 and sm[f] > 0.7:
                vis[f] = 2
    out = vis.copy()
    for i in range(1, n_frames - 1):
        if vis[i - 1] == vis[i + 1] != vis[i]:
            out[i] = vis[i - 1]
    return out, np.clip(sm, 0, 1)
