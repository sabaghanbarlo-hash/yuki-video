"""Sound effects, all synthesized with numpy (nothing to download, no licences) + keyword matching that decides
which effect fits a line of the story."""
import re
import numpy as np

SR = 24000
_rng = np.random.default_rng(7)


def _t(sec):
    return np.arange(int(sec * SR)) / SR


def _env(n, a=0.005, d=0.2, curve=3.0):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-3) * curve / 3)
    return e.astype(np.float32)


def _noise(sec):
    return _rng.normal(0, 1, int(sec * SR)).astype(np.float32)


def _band(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    y = np.fft.irfft(X, len(x)).astype(np.float32)
    return y / (np.abs(y).max() + 1e-6)


def _tone(freq, sec, shape="sine", vib=0.0, vib_hz=6.0):
    t = _t(sec)
    f = freq * (1 + vib * np.sin(2 * np.pi * vib_hz * t)) if np.isscalar(freq) else freq
    ph = 2 * np.pi * np.cumsum(f) / SR if not np.isscalar(f) else 2 * np.pi * f * t
    if shape == "sine":
        return np.sin(ph).astype(np.float32)
    if shape == "tri":
        return (2 / np.pi * np.arcsin(np.sin(ph))).astype(np.float32)
    if shape == "square":
        return (np.sign(np.sin(ph)) * 0.6).astype(np.float32)
    s = np.zeros_like(ph)
    for h in range(1, 12):
        s += np.sin(h * ph) / h
    return (s / 1.8).astype(np.float32)


def _place(parts, total):
    out = np.zeros(int(total * SR) + SR, np.float32)
    for at, x in parts:
        i = int(at * SR)
        out[i:i + len(x)] += x[: len(out) - i]
    return out


def _norm(x, peak=0.8):
    return x / (np.abs(x).max() + 1e-6) * peak


def _thump(f0=150, sec=0.18, noise=0.3):
    t = _t(sec)
    x = np.sin(2 * np.pi * (f0 * np.exp(-t * 8) + 50) * t) * _env(len(t), 0.002, sec * 0.5)
    x += noise * _band(_noise(sec), 100, 1500) * _env(len(t), 0.001, 0.05)
    return x.astype(np.float32)


# ---------------------------------------------------------------- the effects
def knock():
    return _norm(_place([(0.0, _thump(220)), (0.22, _thump(215)), (0.44, _thump(225)), ], 0.7))


def door_slam():
    return _norm(_place([(0, _thump(110, 0.5, 1.0) * 1.0), (0, _band(_noise(0.3), 200, 4000) * _env(int(.3 * SR), .001, .1))], 0.6))


def door_open():
    n = 0.9
    f = np.linspace(180, 330, int(n * SR)) * (1 + 0.04 * np.sin(2 * np.pi * 18 * _t(n)))
    return _norm(_tone(f, n, "saw") * np.sin(np.pi * _t(n) / n) ** 0.7 * 0.6 + 0.2 * _band(_noise(n), 800, 3000) * np.sin(np.pi * _t(n) / n))


def phone_ring():
    parts = []
    for k in range(2):
        for j in range(8):
            t0 = k * 1.0 + j * 0.06
            tone = (_tone(1400, 0.05, "sine") + _tone(1700, 0.05, "sine")) * 0.5
            parts.append((t0, tone))
    return _norm(_place(parts, 1.9) * 0.7)


def alarm():
    parts = [(i * 0.28, _tone(1050, 0.14, "square") * _env(int(.14 * SR), .003, .3)) for i in range(5)]
    return _norm(_place(parts, 1.5), 0.6)


def ding():
    x = _tone(1320, 0.6) * _env(int(.6 * SR), .002, .35) + 0.6 * _tone(1980, 0.6) * _env(int(.6 * SR), .002, .2)
    return _norm(_place([(0, _tone(988, 0.35) * _env(int(.35 * SR), .002, .2) * .7), (0.12, x)], 0.8))


def whoosh():
    n = 0.55
    base = _noise(n)
    out = np.zeros_like(base)
    for i, (lo, hi) in enumerate([(300, 900), (700, 2200), (1500, 5000), (900, 2600), (400, 1200)]):
        seg = slice(i * len(base) // 5, (i + 1) * len(base) // 5 + 1)
        out[seg] += _band(base, lo, hi)[seg]
    return _norm(out * np.sin(np.pi * _t(n) / n) ** 1.5, 0.7)


def pop():
    t = _t(0.12)
    return _norm(np.sin(2 * np.pi * np.cumsum(350 + 900 * np.exp(-t * 40)) / SR) * _env(len(t), .001, .05), 0.7)


def boing():
    n = 0.7; t = _t(n)
    f = 220 + 160 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 4)
    return _norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), .005, .45), 0.7)


def sad():
    notes = [(311, .5), (293, .5), (277, .5), (246, 1.0)]
    parts, at = [], 0
    for i, (f, d) in enumerate(notes):
        vib = 0.03 if i < 3 else 0.06
        x = _tone(f, d, "saw", vib, 6 if i < 3 else 5) * _env(int(d * SR), .02, d * 0.9)
        x = _band(x, 100, 1800 if i < 3 else 900) * np.hanning(len(x)) ** 0.3
        parts.append((at, x)); at += d * 0.92
    return _norm(_place(parts, at + 0.2), 0.7)


def tada():
    parts = []
    for i, f in enumerate([523, 659, 784]):
        parts.append((i * 0.11, _tone(f, 0.5, "tri") * _env(int(.5 * SR), .005, .25)))
    parts.append((0.36, (_tone(1047, 1.0, "tri") + 0.5 * _tone(1319, 1.0, "tri") + 0.4 * _tone(784, 1.0, "tri")) * _env(int(SR), .005, .6)))
    return _norm(_place(parts, 1.5), 0.75)


def crash():
    n = 1.1
    x = _band(_noise(n), 300, 9000) * _env(int(n * SR), .001, .35)
    for f in (420, 633, 877, 1310):
        x += 0.15 * _tone(f, n) * _env(int(n * SR), .001, .3)
    return _norm(x + _thump(90, .3, 0) * 0.6 if False else x, 0.8)


def thunder():
    n = 2.4
    x = _band(_noise(n), 30, 220) * np.minimum(1, _t(n) / .08) * np.exp(-_t(n) * 1.1)
    x += 0.5 * _band(_noise(n), 60, 600) * np.exp(-_t(n) * 2.2)
    return _norm(x, 0.9)


def rain():
    n = 4.0
    x = _band(_noise(n), 2500, 9000) * 0.6 + _band(_noise(n), 500, 2500) * 0.25
    return _norm(x * np.minimum(1, np.minimum(_t(n) / .5, (n - _t(n)) / .5)), 0.35)


def footsteps():
    parts = [(i * 0.34, _thump(120 + (i % 2) * 20, .12, .5) * 0.8) for i in range(5)]
    return _norm(_place(parts, 1.9), 0.55)


def heartbeat():
    parts = []
    for i in range(4):
        parts += [(i * 0.8, _thump(70, .16, 0) * 1.0), (i * 0.8 + 0.2, _thump(60, .14, 0) * 0.7)]
    return _norm(_place(parts, 3.3), 0.8)


def record_scratch():
    n = 0.6; t = _t(n)
    f = 2000 * np.exp(-t * 4)
    x = _band(_noise(n), 400, 5000) * 0.6 + 0.4 * np.sin(2 * np.pi * np.cumsum(f) / SR)
    return _norm(x * np.minimum(1, (n - t) / .1) * _env(len(t), .002, 1), 0.7)


def cash():
    a = _tone(2093, 0.5) * _env(int(.5 * SR), .001, .3)
    b = _tone(3136, 0.9) * _env(int(.9 * SR), .001, .6)
    click = _band(_noise(0.05), 1500, 8000) * _env(int(.05 * SR), .001, .02)
    return _norm(_place([(0, click), (0.04, a * .7), (0.16, b)], 1.1), 0.7)


def camera():
    c = _band(_noise(0.04), 1000, 7000) * _env(int(.04 * SR), .0005, .015)
    return _norm(_place([(0, c), (0.07, c * 0.8)], 0.2), 0.7)


def applause():
    n = 2.6
    x = np.zeros(int(n * SR), np.float32)
    for _ in range(170):
        at = _rng.uniform(0, n - 0.05)
        c = _band(_noise(0.04), 800, 6000) * _env(int(.04 * SR), .0005, .012) * _rng.uniform(.3, 1)
        i = int(at * SR); x[i:i + len(c)] += c
    return _norm(x * np.minimum(1, np.minimum(_t(n) / .3, (n - _t(n)) / .6)), 0.6)


def laugh():
    parts, at = [], 0
    for i in range(5):
        d = 0.14
        f0 = 260 - i * 8
        t = _t(d)
        sig = sum(np.sin(2 * np.pi * f0 * h * t) * np.exp(-((f0 * h - 800) / 400) ** 2) for h in range(1, 14)).astype(np.float32)
        sig = sig * np.hanning(len(t)) + 0.15 * _band(_noise(d), 2000, 6000) * np.hanning(len(t))
        parts.append((at, sig * (1 - i * 0.1))); at += 0.19
    return _norm(_place(parts, at + 0.1), 0.6)


def gasp():
    n = 0.45
    x = _band(_noise(n), 800, 4500) * (np.minimum(1, _t(n) / .3) ** 2) * np.minimum(1, (n - _t(n)) / .06)
    return _norm(x, 0.6)


def cricket():
    parts = []
    for k in range(3):
        for j in range(4):
            parts.append((k * 0.9 + j * 0.07, _tone(4300, .04) * np.hanning(int(.04 * SR))))
    return _norm(_place(parts, 2.6), 0.35)


def bell():
    x = sum(a * _tone(f, 1.6) for f, a in [(660, 1), (1320, .5), (1985, .3), (2640, .15)]) * _env(int(1.6 * SR), .001, 1.0)
    return _norm(x, 0.7)


def sparkle():
    parts = [(i * 0.07, _tone(f, 0.35) * _env(int(.35 * SR), .002, .2)) for i, f in enumerate([1568, 1760, 2093, 2349, 2637, 3136])]
    return _norm(_place(parts, 0.9), 0.55)


def error():
    return _norm(_tone(140, 0.45, "square") * _env(int(.45 * SR), .005, .6), 0.5)


def slap():
    return _norm(_place([(0, _band(_noise(0.15), 600, 5000) * _env(int(.15 * SR), .0005, .04)), (0, _thump(200, .1, 0) * .4)], 0.2), 0.8)


def wind():
    n = 3.0
    m = 0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * _t(n))
    return _norm(_band(_noise(n), 200, 1500) * m * np.minimum(1, np.minimum(_t(n) / .6, (n - _t(n)) / .8)), 0.35)


def horn():
    n = 0.7
    x = (_tone(392, n, "square") + _tone(494, n, "square")) * 0.5
    return _norm(x * np.minimum(1, np.minimum(_t(n) / .02, (n - _t(n)) / .1)), 0.5)


def explosion():
    n = 1.8
    x = _band(_noise(n), 40, 3000) * np.exp(-_t(n) * 2.2) + np.sin(2 * np.pi * np.cumsum(120 * np.exp(-_t(n) * 2) + 30) / SR) * np.exp(-_t(n) * 2.5)
    return _norm(x, 0.9)


def sigh():
    n = 0.9
    x = _band(_noise(n), 500, 3000 ) * np.hanning(int(n * SR)) ** 1.2
    return _norm(x, 0.35)


def love():
    parts = [(0, _tone(784, .5) * _env(int(.5 * SR), .005, .3)), (0.14, _tone(988, .5) * _env(int(.5 * SR), .005, .3)), (0.3, _tone(1319, .8) * _env(int(.8 * SR), .005, .5))]
    return _norm(_place(parts, 1.2), 0.5)


SFX = {k: v for k, v in dict(
    knock=knock, door_slam=door_slam, door_open=door_open, phone_ring=phone_ring, alarm=alarm, ding=ding, whoosh=whoosh,
    pop=pop, boing=boing, sad=sad, tada=tada, crash=crash, thunder=thunder, rain=rain, footsteps=footsteps,
    heartbeat=heartbeat, record_scratch=record_scratch, cash=cash, camera=camera, applause=applause, laugh=laugh,
    gasp=gasp, cricket=cricket, bell=bell, sparkle=sparkle, error=error, slap=slap, wind=wind, horn=horn,
    explosion=explosion, sigh=sigh, love=love).items()}
_cache = {}


def get(name):
    name = name.strip().lower().replace(" ", "_").replace("-", "_")
    alias = {"door": "door_open", "phone": "phone_ring", "ring": "phone_ring", "notification": "ding", "applaud": "applause",
             "wah": "sad", "fail": "sad", "trombone": "sad", "boom": "explosion", "fanfare": "tada", "win": "tada",
             "scratch": "record_scratch", "heart": "heartbeat", "money": "cash", "laughter": "laugh", "step": "footsteps",
             "steps": "footsteps", "scream": "gasp", "shock": "gasp", "cheer": "applause", "magic": "sparkle", "kiss": "love"}
    name = alias.get(name, name)
    if name not in SFX:
        return None
    if name not in _cache:
        x = SFX[name]().astype(np.float32)
        idx = np.where(np.abs(x) > 0.004)[0]
        _cache[name] = x[: idx[-1] + int(0.05 * SR)] if len(idx) else x
    return _cache[name]


# ---------------------------------------------------------------- which effect fits which words
RULES = [
    (r"\bknock(?:ed|ing)?\b", "knock"),
    (r"\bslam(?:med)?\b", "door_slam"),
    (r"\b(?:door (?:opened|creaked|swung)|opened the door|creak)", "door_open"),
    (r"\b(?:phone (?:rang|buzzed)|ringing|rang|calling me|called me|buzzed)\b", "phone_ring"),
    (r"\balarm\b", "alarm"),
    (r"\b(?:notification|new message|text message|texted|pinged|ping|an email)\b", "ding"),
    (r"\b(?:thunder|lightning)\b", "thunder"),
    (r"\b(?:explod\w+|explosion|bang|boom)\b", "explosion"),
    (r"\b(?:crash(?:ed)?|shatter\w*|smash\w*|broke|dropped|tripped|fell (?:down|over|off))\b", "crash"),
    (r"\b(?:gasp(?:ed)?|shocked|stunned|jaw dropped|couldn.t believe|speechless|froze)\b", "gasp"),
    (r"\b(?:laugh(?:ed|ing|ter)?|giggl\w+|hilarious|cracked up|burst out)\b", "laugh"),
    (r"\b(?:awkward|silence|silent|nobody said|no one said|crickets)\b", "cricket"),
    (r"\b(?:wait,? what|hold on|record scratch|stopped (?:dead|mid)|wait a (?:minute|second))\b", "record_scratch"),
    (r"\b(?:heart (?:was )?(?:pounding|racing|raced|beating)|nervous|terrified|scared|afraid)\b", "heartbeat"),
    (r"\b(?:footsteps|tiptoed|walked (?:in|out|away|up|down|over))\b", "footsteps"),
    (r"\b(?:cash|money|dollars?|paid|salary|rich|expensive|bought|\$\d+)\b", "cash"),
    (r"\b(?:photo|picture|selfie|camera|snapped)\b", "camera"),
    (r"\b(?:clapped|applause|cheered|crowd|standing ovation)\b", "applause"),
    (r"\b(?:won|winner|champion|victory|promoted|got the job|passed|finally did it|success\w*|achiev\w+)\b", "tada"),
    (r"\b(?:cried|crying|failed|failure|lost everything|disappointed|heartbroken|rejected|fired)\b", "sad"),
    (r"\b(?:sigh(?:ed)?)\b", "sigh"),
    (r"\b(?:magic\w*|sparkl\w+|miracle|dream(?:ed|s)?|wish(?:ed)?)\b", "sparkle"),
    (r"\b(?:love[ds]?|kiss(?:ed)?|crush|romantic|hug(?:ged)?)\b", "love"),
    (r"\b(?:slapped|slap)\b", "slap"),
    (r"\b(?:honk\w*|traffic|drove|car horn)\b", "horn"),
    (r"\b(?:rain(?:ed|ing|y)?|storm\w*|pouring)\b", "rain"),
    (r"\b(?:wind|windy|freezing|blizzard)\b", "wind"),
    (r"\b(?:bell)\b", "bell"),
    (r"\b(?:suddenly|rushed|sprinted|zoomed|dashed|flew|ran (?:to|out|away|home|off|into))\b", "whoosh"),
    (r"\b(?:jumped|bounced|sprang|hopped)\b", "boing"),
    (r"\b(?:popped up|appeared|out of nowhere)\b", "pop"),
]
RULES = [(re.compile(p, re.I), n) for p, n in RULES]


def find(text):
    """[(fraction_of_line, sfx_name)] in reading order; best first match per effect."""
    hits = []
    for rx, name in RULES:
        m = rx.search(text)
        if m:
            hits.append((m.start() / max(1, len(text)), name))
    hits.sort()
    return hits


# ---------------------------------------------------------------- music bed (soft, synthesized)
def music(seconds, style="story"):
    """Gentle looping bed: soft pad + light plucks. Very quiet; meant to sit under the voice."""
    bpm = 92 if style == "story" else 70
    beat = 60 / bpm
    prog = [(261.6, 329.6, 392.0), (220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7)]
    bar = beat * 4
    n = int(seconds * SR) + SR
    out = np.zeros(n, np.float32)
    i = 0
    while i * bar < seconds + bar:
        ch = prog[i % 4]
        at = i * bar
        for f in ch:
            seg = _tone(f / 2, bar + 0.4, "tri") * np.minimum(1, _t(bar + 0.4) / .3) * np.minimum(1, (bar + .4 - _t(bar + .4)) / .4) * 0.25
            _mix(out, seg, at)
        pat = [0, 1, 2, 1, 2, 1, 0, 2] if style == "story" else [0, 2, 1, 2]
        step = bar / len(pat)
        for k, p in enumerate(pat):
            note = _tone(ch[p] * 2, 0.5, "sine") * _env(int(.5 * SR), .003, .22) * 0.35
            _mix(out, note, at + k * step)
        i += 1
    return out[: int(seconds * SR)]


def _mix(out, seg, at):
    i = int(at * SR)
    if i >= len(out):
        return
    out[i:i + len(seg)] += seg[: len(out) - i]
