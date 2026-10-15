"""Script parsing and the 'director': turns plain English into beats with visuals, themes, poses and moods.

Script format
-------------
    # Video title
    ## Section name            (shows a small chip while the section runs)
    Plain paragraphs. The director splits them into beats (1-2 sentences) and picks visuals itself.

Optional cues go at the START of a line; that line becomes one beat with those cues:
    [theme: night_city] [face: worried] [pose: shrug]
    [keyword: Never your discipline | It's your plan]
    [icon: sleep | Tired at 11 PM]
    [icons: phone=Scrolling | clock=No time | battery_low=Low energy]
    [list: The 2-minute rule :: Pick one tiny action | Do it for two minutes | Stop]
    [steps: Title :: Start tiny | Repeat daily | Add a minute]
    [loop: The reset loop :: Big plan | Burnout | Guilt | Restart]
    [compare: What you plan :: Gym 7 days | No sugar || What works :: Walk 5 min | Sleep earlier]
    [stat: 2 minutes | is all it takes]
    [quote: You fall to the level of your systems. | James Clear]
    [graph: Motivation :: 9,7,5,3,2 :: Mon,Tue,Wed,Thu,Fri]
    [image: pictures/photo.png | caption]
    [none]
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from . import visuals as V
from .icons import pick_icon, _ICONS
from .world import THEMES

SENT_RE = re.compile(r'(?<=[.!?])["”)]*\s+')
LEAD_RE = re.compile(r"^\s*((?:\[[^\]]*\]\s*)+)(.*)$")
CUE_RE = re.compile(r"\[\s*([a-z_]+)\s*(?::\s*(.*?))?\s*\]", re.I | re.S)


@dataclass
class Beat:
    text: str
    scene: int
    heading: str = None
    cues: dict = field(default_factory=dict)
    visual: object = None
    theme: str = "room_day"
    pose: str = "talk_a"
    face: str = "neutral"
    layout: str = "split"
    title: bool = False


# ------------------------------------------------------------------ parsing
def split_sentences(t):
    return [s.strip() for s in SENT_RE.split(t) if s.strip()]


def group_sentences(sents, lo=70, hi=230):
    beats, cur = [], ""
    for s in sents:
        if cur and (len(cur) >= lo or len(cur) + len(s) > hi):
            beats.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        if beats and len(cur) < 30:
            beats[-1] += " " + cur
        else:
            beats.append(cur)
    return beats


def parse_cues(s):
    cues = {}
    for m in CUE_RE.finditer(s):
        k, v = m.group(1).lower(), (m.group(2) or "").strip()
        if k in ("theme", "pose", "face"):
            cues[k] = v.lower()
        elif k == "none":
            cues["visual"] = ("none", "")
        else:
            cues["visual"] = (k, v)
    return cues


def parse_script(path):
    """Returns (title, beats)."""
    title, heading, beats, scene = None, None, [], 0
    from .clean import preprocess, clean_spoken
    text = preprocess(Path(path).read_text(encoding="utf-8"))
    for para in re.split(r"\n\s*\n", text):
        lines = [l.rstrip() for l in para.strip().splitlines() if l.strip()]
        body = []
        for l in lines:
            if re.match(r"^#{2,4}(\s|$)", l):
                heading = l.lstrip("#").strip() or None
            elif l.startswith("# "):
                title = l[2:].strip()
            else:
                body.append(l.strip())
        if not body:
            continue
        has_cues = any(LEAD_RE.match(l) for l in body)
        if has_cues:
            pending = {}
            for l in body:
                m = LEAD_RE.match(l)
                if m:
                    pending.update(parse_cues(m.group(1)))
                    rest = m.group(2).strip()
                else:
                    rest = l
                if rest:
                    beats.append(Beat(rest, scene, heading, pending))
                    pending = {}
        else:
            for b in group_sentences(split_sentences(clean_spoken(" ".join(body)))):
                beats.append(Beat(b, scene, heading, {}))
        scene += 1
    return title, beats


# ------------------------------------------------------------------ cue -> visual
def _split_title(arg):
    if "::" in arg:
        t, rest = arg.split("::", 1)
        return t.strip(), rest.strip()
    return None, arg.strip()


def _items(s):
    return [p.strip() for p in s.split("|") if p.strip()]


def _icon_name(name, label=""):
    name = name.strip().lower()
    if name in _ICONS:
        return name
    return pick_icon(name + " " + label) or "star"


def build_visual(kind, arg, base_dir):
    kind = kind.lower()
    if kind == "none":
        return None
    parts = [p.strip() for p in arg.split("|")] if arg else []
    if kind == "keyword" and parts:
        return V.v_keyword(parts[0], parts[1] if len(parts) > 1 else None)
    if kind == "icon" and parts:
        label = parts[1] if len(parts) > 1 else None
        return V.v_icon(_icon_name(parts[0], label or ""), label)
    if kind == "icons":
        items = []
        for p in parts[:4]:
            n, _, lab = p.partition("=")
            items.append((_icon_name(n, lab), lab.strip() or n.strip()))
        v = V.v_icons(items); v.meta["labels"] = [lab for _, lab in items]
        return v
    if kind in ("list", "bullets"):
        title, rest = _split_title(arg); items = _items(rest)
        v = V.v_bullets(items, title); v.meta["labels"] = items[:6]
        return v
    if kind == "steps":
        title, rest = _split_title(arg); items = _items(rest)
        v = V.v_steps(items, title); v.meta["labels"] = items[:5]
        return v
    if kind == "loop":
        title, rest = _split_title(arg); items = _items(rest)
        v = V.v_loop(items, title); v.meta["labels"] = items[:5]
        return v
    if kind == "compare":
        sides = arg.split("||")
        if len(sides) == 2:
            lt, li = _split_title(sides[0]); rt, ri = _split_title(sides[1])
            return V.v_compare(lt or "Before", _items(li), rt or "After", _items(ri))
    if kind == "stat" and parts:
        return V.v_stat(parts[0], parts[1] if len(parts) > 1 else None)
    if kind == "quote" and parts:
        return V.v_quote(parts[0], parts[1] if len(parts) > 1 else None)
    if kind == "graph":
        segs = [s.strip() for s in arg.split("::")]
        if len(segs) >= 2:
            vals = [float(x) for x in segs[1].split(",") if x.strip()]
            labs = [x.strip() for x in segs[2].split(",")] if len(segs) > 2 else None
            return V.v_graph(segs[0], vals, labs)
    if kind == "image" and parts:
        return V.v_image(str(Path(base_dir) / parts[0]), parts[1] if len(parts) > 1 else None)
    print(f"  ! could not read cue [{kind}: {arg}] - using automatic visual")
    return "auto"


# ------------------------------------------------------------------ automatic choices
NUM_RE = re.compile(r"\b((?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen|twenty|thirty|sixty|hundred)\s?(?:%|percent|minutes?|mins?|hours?|seconds?|days?|weeks?|months?|years?|times)\b|\d+%)", re.I)
QUOTE_RE = re.compile(r"[\"“]([^\"”]{18,120})[\"”]")
NEG = set("never fail failed failure stuck tired exhausted hard struggle struggling quit give guilt burnout burned overwhelmed anxious stress stressed lonely fall falls broken wrong worst hate can't cannot don't".split())
POS = set("love great win won happy finally proud better best amazing easy simple freedom enjoy joy hope good".split())

THEME_WORDS = {
    "room_night": "night sleep tired midnight bed insomnia late dark evening exhausted 3am",
    "night_city": "city streets alone lonely lights outside commute",
    "sunrise": "morning sunrise begin beginning start starting fresh new dawn tomorrow monday",
    "mind": "brain mind think thinking thought thoughts overthink focus idea psychology habit habits brain feelings emotion",
    "city_day": "work job office people busy boss money career colleagues friends",
    "nature": "nature grow growing growth seed tree walk calm breathe peace slow outside plant",
    "room_day": "home room desk plan routine today",
}


def _words(t):
    return re.findall(r"[a-z']+", t.lower())


def pick_theme(text):
    ws = _words(text)
    best, score = None, 0
    for th, words in THEME_WORDS.items():
        s = sum(1 for w in ws if w in set(words.split()))
        if s > score:
            best, score = th, s
    return best


def mood(text):
    ws = set(_words(text))
    if "?" in text:
        return "curious"
    if ws & NEG and not ws & POS:
        return "worried"
    if "!" in text or ws & POS:
        return "happy"
    return "neutral"


def _clean_phrase(s, max_words=9):
    s = re.sub(r"\s+", " ", s).strip()
    words = s.split()
    if len(words) > max_words:
        cut = re.split(r"[,;:—-]\s", s)
        s = cut[0] if 3 <= len(cut[0].split()) <= max_words else " ".join(words[:max_words]) + "…"
    return s


def _enumeration(sentence):
    """'A, B, and C' with short items -> [A, B, C]"""
    s = re.sub(r"^(?:[^:]+:\s*)", "", sentence.strip().rstrip(".!?"))
    parts = [p.strip() for p in re.split(r",\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+", s) if p.strip()]
    if 3 <= len(parts) <= 4 and all(1 <= len(p.split()) <= 4 for p in parts):
        return parts
    return None


def auto_visual(text, state):
    sents = split_sentences(text)
    last = state.get("last")
    # 1. quote
    m = QUOTE_RE.search(text)
    if m:
        return V.v_quote(m.group(1).strip()), "quote"
    # 2. stat
    m = NUM_RE.search(text)
    if m and last != "stat":
        s = next((s for s in sents if m.group(0) in s), sents[0])
        return V.v_stat(m.group(0).strip(), _clean_phrase(s, 9) if len(s) < 90 else None), "stat"
    # 3. enumeration
    for s in sents:
        items = _enumeration(s)
        if items:
            names = [pick_icon(i) for i in items]
            if all(names):
                v = V.v_icons([(n, i[:1].upper() + i[1:]) for n, i in zip(names, items)]); v.meta["labels"] = items
            else:
                v = V.v_bullets([i[:1].upper() + i[1:] for i in items]); v.meta["labels"] = items
            return v, "icons"
    # pacing: every 4th automatic beat has no card, so Yuki walks to the middle and talks to the camera
    if state.get("n", 0) % 4 == 3:
        return None, "none"
    # 4. icon or keyword card, alternating
    from .icons import ICON_KEYS
    name = pick_icon(text, avoid=(state.get("last_icon"),))
    cands = [s for s in sents if len(s.split()) <= 10]
    prefer_icon = last != "icon"
    if name and (prefer_icon or not cands):
        ws = text.replace("’", "'").split()
        low = [re.sub(r"[^a-z']", "", w.lower()) for w in ws]
        keys = set(ICON_KEYS[name].split())
        idx = next((i for i, w in enumerate(low) if w in keys or w.rstrip("s") in keys), None)
        label = None
        if idx is not None:
            label = re.sub(r"[^\w' -]", "", ws[idx]).strip()
            label = label[:1].upper() + label[1:]
        state["last_icon"] = name
        return V.v_icon(name, label), "icon"
    if cands:
        pick = min(cands, key=lambda s: abs(len(s.split()) - 6))
        return V.v_keyword(_clean_phrase(pick), None, color=state.get("n", 0)), "keyword"
    return None, "none"


# ------------------------------------------------------------------ planning
def plan(title, beats, base_dir):
    """Fill in visual / theme / pose / face / layout for every beat."""
    state = {"last": None, "n": 0, "since_visual": 0}
    out = []
    if title:
        t = Beat(title, -1, None, {}, V.v_title(title), "room_day", "wave", "happy", "split", title=True)
        out.append(t)
    theme_prev, theme_run = None, 0
    scene_theme = {}
    # scene themes
    for sc in sorted({b.scene for b in beats}):
        txt = " ".join(b.text for b in beats if b.scene == sc)
        th = pick_theme(txt)
        order = ["room_day", "sunrise", "mind", "nature", "city_day"]
        if th is None or (th == theme_prev and theme_run >= 3):
            cands = [x for x in order if x != theme_prev]
            th = cands[sc % len(cands)]
        theme_run = theme_run + 1 if th == theme_prev else 1
        theme_prev = th
        scene_theme[sc] = th
    cur_theme = None
    for i, b in enumerate(beats):
        new_scene = i == 0 or b.scene != beats[i - 1].scene
        if "theme" in b.cues and b.cues["theme"] in THEMES:
            cur_theme = b.cues["theme"]
        elif new_scene:
            cur_theme = scene_theme[b.scene]
        b.theme = cur_theme
        # visual
        vis, kind = None, "none"
        if "visual" in b.cues:
            res = build_visual(b.cues["visual"][0], b.cues["visual"][1], base_dir)
            if res == "auto":
                vis, kind = auto_visual(b.text, state)
            else:
                vis, kind = res, (b.cues["visual"][0] if res else "none")
        else:
            vis, kind = auto_visual(b.text, state)
        b.visual = vis
        b.layout = "split" if vis is not None else "center"
        state["last"] = kind
        state["n"] += 1
        state["since_visual"] = 0 if vis is not None else state["since_visual"] + 1
        # mood + pose
        b.face = b.cues.get("face") or mood(b.text)
        if "pose" in b.cues:
            b.pose = b.cues["pose"]
        elif vis is not None:
            b.pose = vis.pose if vis.pose in ("present",) else ("point_r" if vis.pose == "point" else vis.pose)
        elif b.face == "curious":
            b.pose = "think"
        elif b.face == "worried":
            b.pose = "shrug"
        elif "!" in b.text and i % 3 == 0:
            b.pose = "cheer"
        else:
            b.pose = "talk_a" if i % 2 == 0 else "talk_b"
        out.append(b)
    return out
