"""Turn the pasted script into scenes.

Format (everything except the words themselves is optional):

    # Title of the video
    ## A scene heading            <- starts a new scene (a line with only --- does the same)
    Paragraphs of narration. A blank line starts a new paragraph.
    [env: ocean | style: voxel | camera: orbit]     <- cues for the scene (one line, or at the start of a paragraph)
    Inline cues like [sfx: boom] or [pause: 1.2] sit exactly where they should happen.

If the script has no explicit scene dividers, it is split automatically at topic changes and at a natural scene length.
"""
import re
from dataclasses import dataclass, field

CUE = re.compile(r"\[\s*([a-zA-Z_ ]+?)\s*:\s*([^\]]*?)\s*\]")
ABBR = ("mr", "mrs", "ms", "dr", "prof", "st", "vs", "etc", "e.g", "i.e", "approx", "no", "fig", "jr", "sr", "inc", "ltd", "u.s", "u.k", "a.m", "p.m", "ca", "est")
WPS = 2.6          # narration speed in words per second (used for estimates and for splitting)

CUE_KEYS = {"env", "environment", "place", "style", "look", "camera", "cam", "char", "character", "actor", "seed", "transition",
            "mood", "template", "sfx", "pause", "music", "entity", "show", "label", "stat", "title", "caption", "host", "zoom", "palette", "time"}


@dataclass
class Sentence:
    text: str                       # as written (shown in captions)
    spoken: str                     # as read by the voice
    para_end: bool = False
    pause: float = None             # extra pause after this sentence (seconds)
    inline: list = field(default_factory=list)   # [(char_index, key, value)] inline cues


@dataclass
class RawScene:
    heading: str = ""
    sentences: list = field(default_factory=list)
    cues: dict = field(default_factory=dict)
    explicit: bool = False
    kind: str = "body"              # title | body | outro

    @property
    def text(self):
        return " ".join(s.text for s in self.sentences)

    @property
    def words(self):
        return len(self.text.split())


def split_sentences(text):
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    parts, buf = [], ""
    toks = re.findall(r"\S+\s*", text)
    for i, tok in enumerate(toks):
        buf += tok
        w = tok.strip()
        core = w.rstrip("\"')]”’")
        if not re.search(r"[.!?…]$", core):
            continue
        word = re.sub(r"[^a-z.]", "", core.lower()).rstrip(".")
        nxt = toks[i + 1].strip() if i + 1 < len(toks) else ""
        if core.endswith(".") and not core.endswith("..."):
            if word in ABBR or word.split(".")[-1] in ABBR:
                continue                                    # "Dr." "vs." "e.g." never end a sentence
            if re.fullmatch(r"[A-Z]\.", core) or re.fullmatch(r"(?:[A-Za-z]\.){2,}", core) and nxt[:1].islower():
                continue                                    # initials "J." and "U.S." before a lowercase word
        if nxt and nxt[0].islower() and not core.endswith(("!", "?")):
            continue                                        # "... and then." continues in lowercase: not a boundary
        parts.append(buf.strip()); buf = ""
    if buf.strip():
        parts.append(buf.strip())
    return parts


UNITS = [
    (r"°\s*C\b", " degrees Celsius"), (r"°\s*F\b", " degrees Fahrenheit"), (r"°", " degrees"),
    (r"\bkm/h\b", " kilometers per hour"), (r"\bmph\b", " miles per hour"), (r"\bm/s\b", " meters per second"),
    (r"(?<=\d)\s*km\b", " kilometers"), (r"(?<=\d)\s*cm\b", " centimeters"), (r"(?<=\d)\s*mm\b", " millimeters"),
    (r"(?<=\d)\s*kg\b", " kilograms"), (r"(?<=\d)\s*g\b", " grams"), (r"(?<=\d)\s*mi\b", " miles"),
    (r"(?<=\d)\s*ft\b", " feet"), (r"(?<=\d)\s*lbs?\b", " pounds"), (r"(?<=\d)\s*m\b(?!\w)", " meters"),
    (r"(?<=\d)\s*%", " percent"), (r"\bvs\.?\b", "versus"), (r"\be\.g\.", "for example"), (r"\bi\.e\.", "that is"),
    (r"&", " and "), (r"≈|~(?=\d)", " about "), (r"\bAI\b", "A I"), (r"\bUFOs?\b", "U F O"),
    (r"\bDNA\b", "D N A"), (r"\bRNA\b", "R N A"), (r"\bNASA\b", "NASA"), (r"\bCO2\b", "C O two"), (r"\bH2O\b", "H two O"),
    (r"\bCPU\b", "C P U"), (r"\bGPS\b", "G P S"), (r"\bMRI\b", "M R I"),
]
UNITS = [(re.compile(p), r) for p, r in UNITS]


def to_spoken(text):
    t = re.sub(r"[*_`#]+", "", text)
    t = re.sub(r"\$\s?(\d[\d,\.]*)\s*(trillion|billion|million|thousand|k|m|bn)?",
               lambda m: f"{m.group(1)} {({'k': 'thousand', 'm': 'million', 'bn': 'billion'}.get((m.group(2) or '').lower(), (m.group(2) or '').lower()))} dollars".replace("  ", " "), t)
    for rx, rep in UNITS:
        t = rx.sub(rep, t)
    t = re.sub(r"(\d)x\b", r"\1 times", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_cues(blob):
    """'env: ocean | style: voxel' or '[env: ocean] [style: voxel]' -> dict."""
    out = {}
    for m in CUE.finditer(blob):
        inner = m.group(0)[1:-1]
        for part in inner.split("|"):
            if ":" in part:
                k, v = part.split(":", 1)
                k = k.strip().lower().replace(" ", "_")
                if k in CUE_KEYS:
                    out[k] = v.strip()
    return out


def _para_to_sentences(para, scene_cues):
    """Strip cues from a paragraph, returning sentences with inline cues anchored to character positions."""
    inline_raw = []                    # (position in cleaned text, key, value)
    clean, pos = "", 0
    for m in CUE.finditer(para):
        clean += para[pos:m.start()]
        for part in m.group(0)[1:-1].split("|"):
            if ":" in part:
                k, v = part.split(":", 1)
                k = k.strip().lower().replace(" ", "_")
                if k in CUE_KEYS:
                    inline_raw.append((len(clean), k, v.strip()))
        pos = m.end()
    clean += para[pos:]
    sents = split_sentences(clean)
    out, cursor = [], 0
    # map inline cues to the sentence they fall in
    spans = []
    i = 0
    for s in sents:
        j = clean.find(s[: max(5, min(len(s), 12))], i)
        j = i if j < 0 else j
        spans.append((j, j + len(s)))
        i = j + len(s)
    for si, s in enumerate(sents):
        a, b = spans[si]
        sent = Sentence(text=s, spoken=to_spoken(s), para_end=(si == len(sents) - 1))
        for (p, k, v) in inline_raw:
            lo = a if si > 0 else 0
            hi = b if si < len(sents) - 1 else len(clean) + 1
            if lo <= p < hi or (si == len(sents) - 1 and p >= b):
                if k == "pause":
                    try:
                        sent.pause = float(re.sub(r"[^0-9.]", "", v) or 1.0)
                    except ValueError:
                        sent.pause = 1.0
                else:
                    sent.inline.append((max(0, p - a), k, v))
        out.append(sent)
    return out


def parse(text):
    """-> (title, [RawScene])"""
    text = text.replace("﻿", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    title = ""
    scenes, cur = [], RawScene()
    para_lines = []
    explicit_any = any(re.match(r"^\s*(##\s+|---+\s*$|===+\s*$)", ln) for ln in lines)

    def flush_para():
        nonlocal para_lines
        if para_lines:
            para = " ".join(x.strip() for x in para_lines if x.strip())
            if para:
                cur.sentences += _para_to_sentences(para, cur.cues)
        para_lines = []

    def new_scene(heading="", explicit=True):
        nonlocal cur
        flush_para()
        if cur.sentences or cur.cues or cur.heading:
            scenes.append(cur)
        cur = RawScene(heading=heading, explicit=explicit)

    for ln in lines:
        s = ln.strip()
        if not s:
            flush_para()
            continue
        m = re.match(r"^#\s+(.*)$", s)
        if m and not title and not scenes and not cur.sentences:
            title = m.group(1).strip()
            continue
        m = re.match(r"^##+\s+(.*)$", s)
        if m:
            new_scene(m.group(1).strip())
            continue
        if re.match(r"^(---+|===+)$", s):
            new_scene("")
            continue
        if CUE.fullmatch(s) or re.fullmatch(r"(?:\[[^\]]*\]\s*)+", s):          # a line of only cues
            flush_para()
            cur.cues.update(parse_cues(s))
            continue
        para_lines.append(ln)
    new_scene("")
    scenes = [sc for sc in scenes if sc.sentences]
    if not explicit_any:
        scenes = auto_split(scenes)
    scenes = split_on_place(scenes)
    return title, scenes


def auto_split(scenes):
    """No dividers in the script: cut at topic changes and at a natural scene length (~10-18 s of narration)."""
    from . import knowledge as K
    sents = []
    for sc in scenes:
        sents += sc.sentences
    out, cur, words, last_topic = [], [], 0, None
    TARGET, MAXW, MINW = 38, 62, 16
    for i, s in enumerate(sents):
        n = len(s.text.split())
        topic = K.topic_of(s.text)
        shift = bool(last_topic and topic and topic != last_topic and words >= MINW)
        if cur and ((words + n > MAXW) or (shift and words >= MINW + 6) or (words >= TARGET and (cur[-1].para_end or words >= TARGET + 10))):
            out.append(cur); cur, words = [], 0
        cur.append(s); words += n
        if topic:
            last_topic = topic
    if cur:
        if out and sum(len(x.text.split()) for x in cur) < 10:
            out[-1] += cur
        else:
            out.append(cur)
    res = []
    for c in out:
        sc = RawScene(sentences=c)
        res.append(sc)
    # carry the first scene's cues if the script had a single cue block
    if scenes and scenes[0].cues and res:
        res[0].cues = dict(scenes[0].cues)
    return res


def estimate_seconds(sentences):
    n = sum(len(s.text.split()) for s in sentences)
    return n / WPS + 0.25 * len(sentences)


def split_on_place(scenes):
    """A scene whose narration moves to a different place ('in the desert' ... 'under the sea') is cut there, so each
    scene is drawn where it happens. Scenes with an explicit [env: ...] cue are left alone."""
    from dataclasses import replace
    from . import knowledge as K
    out = []
    for sc in scenes:
        if sc.cues.get("env") or sc.cues.get("environment") or sc.cues.get("place"):
            out.append(sc); continue
        groups, cur, words, last = [], [], 0, None
        for s in sc.sentences:
            alias, score = K.place_of(s.text)
            alias = alias if score >= 3 else None
            if cur and alias and last and alias != last and words >= 14:
                groups.append(cur); cur, words = [], 0
            cur.append(s); words += len(s.text.split())
            if alias:
                last = alias
        if cur:
            groups.append(cur)
        if len(groups) > 1 and sum(len(x.text.split()) for x in groups[-1]) < 8:
            groups[-2] += groups.pop()
        for gi, g in enumerate(groups):
            keep = sc.cues if gi == 0 else {k: v for k, v in sc.cues.items() if k in ("style", "look", "palette", "mood")}
            out.append(replace(sc, sentences=g, heading=sc.heading if gi == 0 else "", cues=dict(keep)))
    return out
