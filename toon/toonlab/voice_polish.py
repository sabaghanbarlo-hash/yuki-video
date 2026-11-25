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
    "neutral":  dict(speed=1.00, gap=0.16, db=0.0,  ref="neutral"),
    "happy":    dict(speed=1.04, gap=0.13, db=0.5,  ref="happy"),
    "excited":  dict(speed=1.10, gap=0.09, db=1.5,  ref="excited"),
    "wonder":   dict(speed=0.98, gap=0.20, db=0.3,  ref="calm"),
    "curious":  dict(speed=1.00, gap=0.18, db=0.0,  ref="calm"),
    "shocked":  dict(speed=1.06, gap=0.12, db=1.0,  ref="excited"),
    "worried":  dict(speed=1.00, gap=0.18, db=-0.3, ref="serious"),
    "sad":      dict(speed=0.93, gap=0.26, db=-1.5, ref="serious"),
    "angry":    dict(speed=1.06, gap=0.10, db=2.0,  ref="excited"),
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


def polish(a, max_gap=0.14, min_gap=0.20):
    """Full clean-up of one synthesized sentence."""
    a = remove_breaths(a)
    a = tighten(a, max_gap=max_gap, min_gap=min_gap)
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


# ------------------------------------------------------------------ flowing narration: one take = a few sentences spoken together
def level(a, target=0.085):
    """Bring the speech of a take to a common loudness (active speech only), so neighbouring takes do not jump in volume."""
    rms, _ = _frames(a)
    act = rms[rms > 0.02 * (rms.max() if len(rms) else 1)]
    if len(act) == 0:
        return a
    cur = float(np.sqrt(np.mean(act ** 2)))
    g = float(np.clip(target / max(cur, 1e-4), 0.35, 3.0))
    y = a * g
    pk = float(np.abs(y).max())
    if pk > 0.95:
        y = np.tanh(y / pk * 1.1) / np.tanh(1.1) * 0.95
    return y.astype(np.float32)


def _units(text):
    """Rough 'time cost' of a sentence: syllables plus an allowance for the punctuation pauses."""
    t = re.sub(r"\[[^\]]*\]", "", text)
    syl = 0
    for w in re.findall(r"[A-Za-z']+", t):
        g = len(re.findall(r"[aeiouy]+", w.lower()))
        if w.lower().endswith("e") and g > 1 and not w.lower().endswith(("le", "ee")):
            g -= 1
        syl += max(1, g)
    syl += 0.7 * len(re.findall(r"[,;:]", t))
    syl += 1.4 if t.rstrip().endswith(("?", "!")) else 1.0 if t.rstrip().endswith(".") else 0.4
    return max(1.0, syl)


def cut_take(x, sentences):
    """Cut ONE recording of several sentences back into one array per sentence.
    Each cut is made at the quietest moment near where the sentence should end (by its length), so a natural pause or breath
    is where the cut falls and no word is ever split.  Returns len(sentences) float32 arrays (edges trimmed, short fade)."""
    n = len(sentences)
    if n <= 1:
        return [trim_edges(x, keep=0.05)] if n == 1 else []
    rms, _ = _frames(x)
    if len(rms) < 10:
        return [x] * n
    sm = np.convolve(rms, np.ones(3) / 3, mode="same")
    lv = _level(rms)
    voiced = np.where(sm > 0.05 * lv)[0]
    if len(voiced) == 0:
        return [x] * n
    v0, v1 = int(voiced[0]), int(voiced[-1]) + 1
    w = np.array([_units(t) for t in sentences], float)
    cum = np.cumsum(w) / w.sum()
    bounds, last = [], v0
    for k in range(n - 1):
        target = v0 + cum[k] * (v1 - v0)
        span = (v1 - v0) * (w[k] + w[k + 1]) / w.sum()
        half = int(max(45, 0.30 * span))                           # search +-30% of the two neighbouring sentences (at least 0.45 s)
        lo, hi = int(max(last + 30, target - half)), int(min(v1 - 30, target + half))
        if hi <= lo:
            b = int(target)
        else:
            seg = sm[lo:hi]
            dist = np.abs(np.arange(lo, hi) - target) / half
            score = seg / (lv + 1e-9) + 0.12 * dist                # quiet first, nearer the expected place second
            b = lo + int(np.argmin(score))
            # a pause is a run of quiet frames: cut in the middle of it
            q = np.where(sm[max(lo, b - 40):min(hi, b + 40)] < sm[b] * 1.35 + 0.01 * lv)[0]
            if len(q):
                b = max(lo, b - 40) + int((q[0] + q[-1]) // 2)
        bounds.append(b); last = b
    edges = [0] + bounds + [len(rms)]
    out = []
    for i in range(n):
        seg = x[edges[i] * HOP: edges[i + 1] * HOP]
        out.append(trim_edges(seg, keep=0.05) if len(seg) > HOP * 4 else seg)
    return out
