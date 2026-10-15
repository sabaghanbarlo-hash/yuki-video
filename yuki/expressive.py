"""Expressive reading: turns a flat text-to-speech voice into a storyteller.

The voice model (Kokoro) reads each piece of text with the same neutral energy. This layer reads the script like a person
would, sentence by sentence:
  * ALL-CAPS rants      faster, higher, louder (the "WHAT SHOULD YOU DO?!" energy)
  * "!"                 brighter and a little louder
  * "?"                 lifted, with a beat of silence after it (setup lines like "And the worst part?" get a longer one)
  * "..."               slower, trailing off, longer pause
  * short punchlines    ("Yeah." "Nope." "Three out of five.") slower and deadpan, with a pause before them: comic timing
  * "quoted speech"     a little higher and quicker, like Yuki doing an impression of the person
  * the mood of the line (happy / sad / angry / shocked / excited ...) nudges all of the above
  * tiny random-looking but repeatable variations, so no two sentences sound copy-pasted
Pitch is moved by resampling, with the speed compensated, so a sentence keeps its length.
"""
import hashlib, re
import numpy as np

SR = 24000
ACRONYMS = {"NPC", "CEO", "TV", "AM", "PM", "UK", "USA", "US", "UN", "GPA", "PDF", "ID", "OK", "DIY", "FYI", "ASAP", "DM", "DMS", "AI", "PC", "USB", "WIFI", "FOMO", "NASA", "ER", "IQ", "BTW", "LOL", "OMG"}
QUOTE = re.compile(r'([“"])(.+?)([”"])')
SENT = re.compile(r"[^.!?…]+(?:\.{3}|[.!?…]+)[\"”')\]]*|[^.!?…]+$")
LAST_WORDS = [0]      # length of the previous sentence (carries over from one line to the next, for punchline timing)
MOOD = {  # rate x, semitones, dB
    "happy": (1.03, 0.6, 0.5), "excited": (1.07, 1.2, 1.5), "sad": (0.92, -1.0, -1.5), "angry": (1.05, 0.8, 2.0),
    "shocked": (1.02, 1.4, 1.0), "worried": (1.03, 0.4, 0.0), "curious": (0.99, 0.5, 0.0), "neutral": (1.0, 0.0, 0.0),
}


def _jit(text, k):
    h = hashlib.md5((text + str(k)).encode()).digest()
    return (h[k % 16] / 255.0 - 0.5) * 2          # -1 .. 1, repeatable


def _is_shout(words):
    letters = [w for w in words if re.search(r"[A-Za-z]", w)]
    core = lambda w: re.sub(r"[^A-Za-z]", "", w)
    caps = [w for w in letters if len(core(w)) >= 2 and w.upper() == w and core(w) not in ACRONYMS]
    if not caps:
        return False
    n_cap = len(caps) + sum(1 for w in letters if core(w) == "I")      # a capital "I" belongs to the rant
    return (n_cap >= 2 and n_cap >= 0.6 * len(letters)) or len(letters) <= 2


def _spoken_form(text, shout):
    """CAPS words are lower-cased for the voice model (it may spell them out); the loudness comes from the delivery instead."""
    if not shout:
        return text
    return re.sub(r"[A-Za-z']+", lambda m: m.group(0) if (m.group(0) in ACRONYMS or m.group(0) == "I" or m.group(0).startswith("I'")) else m.group(0).lower(), text)


def plan(text, mood="neutral", base_speed=1.0):
    """-> list of dicts: text, rate, st (semitones), db, pre, post.  One per sentence / quote."""
    segs, pos = [], 0
    chunks = []
    for m in QUOTE.finditer(text):                           # quoted speech may run over several sentences
        if m.start() > pos:
            chunks.append((text[pos:m.start()], False))
        chunks.append((m.group(2), True))
        pos = m.end()
    chunks.append((text[pos:], False))
    for chunk, quoted in chunks:
        for sent in [x.strip(" \"\u201c\u201d") for x in SENT.findall(chunk) if x.strip(" \"\u201c\u201d")]:
            if re.search(r"\w", sent):
                segs.append((sent, quoted))
    mrate, mst, mdb = MOOD.get(mood, MOOD["neutral"])
    out, prev_words = [], LAST_WORDS[0]
    for i, (t, quoted) in enumerate(segs):
        words = re.findall(r"[\w'’-]+", t)
        if not words:
            continue
        end = t.rstrip(" \"”')]")[-1:]
        ell = t.rstrip(" \"”')]").endswith(("...", "…"))
        shout = _is_shout(t.split())
        rate, st, db, pre, post = 1.0, 0.0, 0.0, 0.0, 0.30
        if end == "!":
            rate, st, db, post = 1.05, 1.0, 1.5, 0.28
        elif end == "?":
            rate, st, post = 0.98, 0.7, 0.42
            if len(words) <= 6 and not quoted:
                post = 0.62                                   # "And the worst part?"  ...(beat)
        elif ell:
            rate, st, post = 0.88, -0.5, 0.6
        if shout:
            rate *= 1.08; st += 2.2; db += 3.0; post = max(post, 0.34)
        if len(words) <= 3 and prev_words >= 8 and not shout and not quoted and end in ".!?":   # deadpan punchline
            rate *= 0.88; st -= 0.5; pre = 0.2; post = max(post, 0.46)
        if len(words) <= 2 and end == ".":
            post = max(post, 0.4)
        if quoted:
            rate *= 1.04; st += 1.6 if i % 2 == 0 else -1.2; db += 0.5
        rate *= mrate; st += mst; db += mdb
        st = max(-2.0, min(3.2, st))
        rate *= 1 + 0.025 * _jit(t, 1)
        st += 0.35 * _jit(t, 2)
        out.append(dict(text=_spoken_form(t, shout), rate=base_speed * rate, st=st, db=db, pre=pre, post=post))
        prev_words = len(words)
    LAST_WORDS[0] = prev_words
    if out:
        out[-1]["post"] = 0.0
    return out


def _shift(a, st):
    """Raise/lower pitch by `st` semitones and keep the length (done by the caller through speed). Plain resampling."""
    r = 2 ** (st / 12.0)
    if abs(r - 1) < 1e-3 or len(a) < 8:
        return a
    return np.interp(np.arange(0, len(a) - 1, r), np.arange(len(a)), a).astype(np.float32)


def speak(text, tts, mood="neutral", base_speed=1.0, pitch_bias=0.0, trim=None):
    """tts(text, speed) -> float32 mono at 24 kHz.  Returns the whole performance."""
    pieces = []
    for p in plan(text, mood, base_speed):
        r = 2 ** ((p["st"] + pitch_bias) / 12.0)
        a = tts(p["text"], float(np.clip(p["rate"] / r, 0.55, 1.6)))
        a = _shift(a, p["st"] + pitch_bias)
        if trim:
            a = trim(a)
        a = a * (10 ** (p["db"] / 20.0))
        if p["pre"]:
            pieces.append(np.zeros(int(p["pre"] * SR), np.float32))
        pieces.append(a.astype(np.float32))
        if p["post"]:
            pieces.append(np.zeros(int(p["post"] * SR), np.float32))
    if not pieces:
        return np.zeros(int(0.4 * SR), np.float32)
    x = np.concatenate(pieces)
    return np.tanh(x * 0.9) / 0.9 * 0.98 if np.abs(x).max() > 1.0 else x
