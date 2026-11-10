"""Post-processing for cloned-voice narration (Voice Studio / OmniVoice / Chatterbox).

Fixes three things:
  1. dead air      - long pauses inside a sentence are shortened to a natural beat
  2. breathing     - audible inhales (low-energy, noisy segments) are cut out
  3. flat emotion  - each mood gets its own speed, pause length, loudness and (optional) reference clip

Pure numpy, no extra dependencies. Audio is mono float32 at 24 kHz.
"""
import re
from pathlib import Path
import numpy as np

SR = 24000
HOP = int(0.010 * SR)          # 10 ms analysis frames

# mood -> speed multiplier, gap after sentence (s), loudness (dB), reference clip suffix
MOODS = {
    "neutral":  dict(speed=1.00, gap=0.16, db=0.0,  ref="neutral", pitch=0.0),
    "happy":    dict(speed=1.04, gap=0.13, db=0.5,  ref="happy",   pitch=0.9),
    "excited":  dict(speed=1.08, gap=0.09, db=1.5,  ref="excited", pitch=1.5),
    "wonder":   dict(speed=0.98, gap=0.20, db=0.3,  ref="calm",    pitch=0.5),
    "curious":  dict(speed=1.00, gap=0.18, db=0.0,  ref="calm",    pitch=0.6),
    "shocked":  dict(speed=1.05, gap=0.12, db=1.0,  ref="excited", pitch=1.3),
    "worried":  dict(speed=1.00, gap=0.18, db=-0.3, ref="serious", pitch=0.3),
    "sad":      dict(speed=0.95, gap=0.26, db=-1.5, ref="serious", pitch=-1.1),
    "angry":    dict(speed=1.05, gap=0.10, db=2.0,  ref="excited", pitch=-0.3),
    "calm":     dict(speed=0.97, gap=0.22, db=-0.6, ref="calm",    pitch=-0.5),
}


def mood_cfg(mood):
    return MOODS.get(mood or "neutral", MOODS["neutral"])


# ------------------------------------------------------------------ text
def clean_text(t):
    """Punctuation that makes TTS stall: ellipses, dashes, semicolons, brackets, line breaks."""
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"(\.\s*){2,}|…", ". ", t)              # "..." -> "."
    t = re.sub(r"\s*[—–]\s*|\s+-\s+", ", ", t)         # dashes -> comma
    t = re.sub(r"\s*[;:]\s*", ", ", t)
    t = re.sub(r"[()\[\]\"“”*_]", "", t)
    t = re.sub(r",\s*,+", ",", t)
    t = re.sub(r"\s+([,.!?])", r"\1", t)
    t = re.sub(r"([.!?])(?=[A-Za-z])", r"\1 ", t)
    return re.sub(r"\s+", " ", t).strip()


def split_sentences(text):
    """Sentence split that merges tiny fragments (<3 words) into the next sentence: fewer chunks, fewer seams."""
    raw = [x.strip() for x in re.split(r"(?<=[.!?])\s+", clean_text(text)) if x.strip()]
    out = []
    for s in raw:
        if out and len(out[-1].split()) < 3 and not out[-1].endswith(("?", "!")):
            out[-1] = out[-1] + " " + s
        else:
            out.append(s)
    return out


# ------------------------------------------------------------------ audio analysis
def _frames(a):
    n = len(a) // HOP
    if n == 0:
        return np.zeros(0), np.zeros(0)
    f = a[: n * HOP].reshape(n, HOP)
    rms = np.sqrt((f ** 2).mean(1))
    zcr = (np.abs(np.diff(np.sign(f), axis=1)) > 0).mean(1)
    return rms, zcr


def _level(rms):
    act = rms[rms > 0.006]
    return float(np.percentile(act, 90)) if len(act) else 1.0


def _runs(mask):
    """[(start, end)] of consecutive True values (end exclusive)."""
    out, s = [], None
    for i, v in enumerate(mask):
        if v and s is None:
            s = i
        elif not v and s is not None:
            out.append((s, i)); s = None
    if s is not None:
        out.append((s, len(mask)))
    return out


def _fade(x, n=int(0.006 * SR)):
    if len(x) > 2 * n:
        r = np.linspace(0, 1, n, dtype=np.float32)
        x = x.copy(); x[:n] *= r; x[-n:] *= r[::-1]
    return x


def remove_breaths(a, level=None):
    """Cut inhales: noisy (high zero-crossing), quiet (well under speech level), 0.12-0.9 s, next to silence or an edge."""
    rms, zcr = _frames(a)
    if len(rms) == 0:
        return a
    lv = level or _level(rms)
    quiet = rms < 0.10 * lv
    breathy = (rms >= 0.02 * lv) & (rms < 0.40 * lv) & (zcr > 0.14)
    cut = np.zeros(len(rms), bool)
    for s, e in _runs(breathy):
        dur = (e - s) * 0.010
        if not (0.25 <= dur <= 0.9):
            continue
        before = s == 0 or quiet[max(0, s - 4):s].any()
        # an inhale comes BEFORE speech; a soft noisy sound right after speech is the end of a word ("yes", "this"): keep it
        if before:
            cut[max(0, s - 1):min(len(rms), e + 1)] = True
    if not cut.any():
        return a
    keep = np.ones(len(a), bool)
    for s, e in _runs(cut):
        keep[s * HOP: e * HOP] = False
    return a[keep]


def tighten(a, max_gap=0.14, min_gap=0.20, level=None):
    """Shorten quiet runs longer than `min_gap` to `max_gap`. Removes dead air without touching speech."""
    rms, _ = _frames(a)
    if len(rms) == 0:
        return a
    lv = level or _level(rms)
    quiet = rms < 0.09 * lv
    pieces, pos = [], 0
    for s, e in _runs(quiet):
        dur = (e - s) * 0.010
        if dur < min_gap or s == 0 or e >= len(rms):
            continue
        keep_each = int(max_gap / 2 * SR)
        gs, ge = s * HOP, e * HOP
        pieces.append(a[pos: gs + keep_each])
        pieces.append(a[ge - keep_each: ge])
        pos = ge
    pieces.append(a[pos:])
    return np.concatenate(pieces) if len(pieces) > 1 else a


def trim_edges(a, keep=0.14):
    """Trim silence/breath at both ends, relative to this clip's own speech level (not a fixed threshold)."""
    rms, _ = _frames(a)
    if len(rms) == 0:
        return a
    lv = _level(rms)
    idx = np.where(rms > 0.04 * lv)[0]
    if len(idx) == 0:
        return a
    s = max(0, idx[0] * HOP - int(keep * SR))
    e = min(len(a), (idx[-1] + 1) * HOP + int(keep * SR))
    out = a[s:e].copy()
    n = min(len(out) // 2, int(0.02 * SR))
    if n > 1:
        out[-n:] *= np.linspace(1, 0, n, dtype=np.float32)
    return out


def polish(a, max_gap=0.14):
    """Full clean-up of one synthesized sentence."""
    a = remove_breaths(a)
    a = tighten(a, max_gap=max_gap)
    a = trim_edges(a)
    return _fade(a.astype(np.float32))


def gain_db(a, db):
    return (a * (10 ** (db / 20))).astype(np.float32) if db else a


# ------------------------------------------------------------------ reference clip per mood
def pick_ref(base_ref, mood):
    """voice/ref.m4a is the default. Optional extras: voice/ref_excited.m4a, ref_calm.m4a, ref_serious.m4a, ref_happy.m4a."""
    if not base_ref:
        return base_ref
    p = Path(base_ref)
    want = mood_cfg(mood)["ref"]
    if want == "neutral":
        return base_ref
    for ext in (p.suffix, ".m4a", ".wav", ".mp3"):
        c = p.with_name(f"{p.stem}_{want}{ext}")
        if c.exists():
            return str(c)
    return base_ref
