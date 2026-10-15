"""Story mode: script parsing and the story 'director'.

Story script format
-------------------
    # The Day Everything Went Wrong
    [cast: Mia = girl | Tom = boy | Mr. Park = man]       (optional: pick looks; names are auto-assigned otherwise)

    ## Monday morning                                        (section chip + a new scene)
    Plain paragraphs are narration: Yuki tells the story.
    Mia: I can't believe I overslept!                       (a character speaks, in a speech bubble)
    Tom (shocked): You did WHAT?                            (optional mood in brackets)

Cues go at the START of a line and apply to that line:
    [theme: night_city]      change the scene background   (room_day room_night night_city sunrise mind city_day nature)
    [sfx: door_slam]         play a sound effect at the start of the line
    [sfx: laugh @ 0.6]       ... or part-way through it (0 = start, 1 = end);  several:  [sfx: knock | gasp @ 0.7]
    [face: angry]  [pose: cheer]  [emote: !]   mood / pose / the little symbol above the head (! ? heart anger sweat zzz star dots)
    [nosfx]                  no automatic effects for this line

Sound effects are also added automatically from the words ("knocked", "laughed", "thunder", ...).
Effects: knock door_slam door_open phone_ring alarm ding whoosh pop boing sad tada crash thunder rain footsteps
         heartbeat record_scratch cash camera applause laugh gasp cricket bell sparkle error slap wind horn explosion sigh love
"""
import re
from dataclasses import dataclass, field
from . import cast as C
from . import audio as A
from . import sfx as SFX
from . import visuals as V
from .script import split_sentences, group_sentences, pick_theme, THEME_WORDS
from .world import THEMES
from .clean import preprocess, clean_spoken

DIALOGUE = re.compile(r"^(?P<name>[A-Z][\w.'’-]*(?:\s+[A-Z][\w.'’-]*){0,2})\s*(?:\((?P<emo>[A-Za-z ]+)\))?\s*:\s*(?P<text>\S.*)$")
LEAD = re.compile(r"^\s*((?:\[[^\]]*\]\s*)+)(.*)$")
CUE = re.compile(r"\[\s*([a-z_]+)\s*(?::\s*(.*?))?\s*\]", re.I | re.S)
NOT_NAMES = {"Note", "Tip", "Title", "Scene", "Chapter", "Part", "Step", "Fact", "Narrator", "Yuki"}
EMOTIONS = {"happy": "happy", "excited": "excited", "sad": "sad", "angry": "angry", "mad": "angry", "furious": "angry",
            "shocked": "shocked", "surprised": "shocked", "scared": "worried", "worried": "worried", "nervous": "worried",
            "curious": "curious", "confused": "curious", "neutral": "neutral", "calm": "neutral", "laughing": "happy",
            "crying": "sad", "embarrassed": "worried", "proud": "happy", "tired": "sad"}
STORY_THEME_WORDS = {
    "city_day": "office meeting interview boss job hired fired desk coworker colleagues manager company client",
    "night_city": "street alley downtown taxi bus subway streetlight",
    "room_night": "midnight bedtime night asleep insomnia 3am",
    "sunrise": "morning breakfast sunrise woke dawn",
    "nature": "park garden forest hike mountain beach lake camping picnic river",
    "mind": "dream imagine thought thinking remembered memory idea realized",
    "room_day": "home kitchen dinner mom dad living room couch school class lunch",
}
SCENE_BREAK = re.compile(r"^(?:the next (?:day|morning|week)|later|that (?:night|evening|morning)|meanwhile|years later|"
                         r"a (?:week|month|year|few days) later|weeks later|months later|at (?:the|his|her) (?:office|school|house)|"
                         r"two days later|three days later|one day|the following)", re.I)
ANGRY = re.compile(r"\b(furious|angry|how dare|shut up|stupid|idiot|hate you|get out|are you kidding|unbelievable)\b", re.I)
SADW = re.compile(r"\b(sorry|crying|cried|miss you|lonely|alone|lost|gone|failed|sad|heartbroken|tired)\b", re.I)
SHOCK = re.compile(r"\b(what\?!|no way|oh my|can't believe|cannot believe|you did what|seriously\?|wait,? what)\b", re.I)
HAPPYW = re.compile(r"\b(yay|love|great|amazing|won|finally|thank you|best|awesome|haha|yes!)\b", re.I)
EMOTE_FOR = {"shocked": "!", "curious": "?", "angry": "anger", "sad": "sweat", "worried": "sweat", "excited": "star"}
EMOTE_SFX = {"gasp": "!", "love": "heart", "cricket": "dots", "sparkle": "star", "sigh": "sweat", "sad": "sweat", "record_scratch": "?"}


# ---------------------------------------------------------------- background that follows the story
# theme -> (strong words, weak words).  Strong words are places / unmistakable settings (worth 2), weak words hint (worth 1).
THEME_KEYS = {
    "exam_hall": ("exam exams quiz quizzes revision midterm midterms finals test paper essay question answer graded", "grade studied forgot memorize memorized"),
    "classroom": ("classroom lecture lectures professor professors syllabus teacher teachers attendance seat desk whiteboard chalkboard homework assignment assignments",
                  "class classes students student presentation powerpoint projector slide slides group groups research professor's"),
    "campus": ("campus college university orientation enrolled degree dorm freshman semester tuition", "walking building arrived arrive lost hallway"),
    "phone": ("group-chat chat chats messages message unread instagram tiktok notification notifications emojis texts phone scrolled scrolling spotify playlist youtube",
              "screen sends sent replies emoji online"),
    "library": ("library librarian bookshelf", "studying textbook textbooks highlighters"),
    "room_night": ("midnight 3am insomnia", "night asleep sleep-deprived tired dark"),
    "sunrise": ("sunrise dawn matcha", "morning breakfast woke"),
    "room_day": ("bedroom pajamas cereal couch kitchen living", "home bed ceiling shoes rest dinner mom dad lie"),
    "city_day": ("traffic commute office boss interview coworkers", "job work bus train"),
    "nature": ("park garden forest hike mountain beach lake camping picnic river", "trees flowers outside"),
    "night_city": ("downtown streetlight taxi subway alley", "street"),
    "mind": ("dream dreamed imagined imagine daydream", "brain thoughts memory"),
}
_TK = {th: ({w: 2 for w in a.split()}, {w: 1 for w in b.split()}) for th, (a, b) in THEME_KEYS.items()}
TIE_ORDER = ["exam_hall", "classroom", "phone", "library", "campus", "room_night", "sunrise", "room_day", "city_day", "nature", "night_city", "mind"]
LATE_NIGHT = re.compile(r"\b(?:12|1|2|3|4)(?::\d{2})?\s*(?:am|a\.m\.)\b", re.I)


def theme_scores(text):
    low = text.lower().replace("group chat", "group-chat")
    ws = re.findall(r"[a-z0-9][a-z0-9'\-]*", low)
    out = {}
    for th, (strong, weak) in _TK.items():
        sc = 0
        for w in set(ws):
            w2 = w[:-1] if w.endswith("s") and w[:-1] in strong else w
            sc += strong.get(w, strong.get(w2, 0)) or weak.get(w, 0)
        if sc:
            out[th] = sc
    if LATE_NIGHT.search(text):
        out["room_night"] = out.get("room_night", 0) + 2
    if re.search(r"\b(?:5|6)\s*(?:am|a\.m\.)\b", text, re.I):
        out["sunrise"] = out.get("sunrise", 0) + 1
    return out


def assign_themes(beats, min_dwell=4):
    """One background per beat, chosen from what the story is talking about. A running 'what are we talking about'
    score (recent lines count most) decides; the background only changes when the story clearly moves somewhere else,
    and not more often than every `min_dwell` beats, so it never flickers."""
    n = len(beats)
    if not n:
        return []
    total = {}
    for b in beats:
        for th, v in theme_scores(b.text).items():
            total[th] = total.get(th, 0) + v
    place = {k: v for k, v in total.items() if k in ("campus", "classroom", "library", "city_day", "nature", "room_day")}
    default = max(place, key=lambda k: (place[k], -TIE_ORDER.index(k))) if place else "room_day"
    ctx, seq, cur, since, quiet = {}, [], None, 99, 0
    for i, b in enumerate(beats):
        ctx = {k: v * 0.62 for k, v in ctx.items() if v * 0.62 > 0.05}
        for th, v in theme_scores(b.text).items():
            ctx[th] = ctx.get(th, 0) + v
        if i + 1 < n:                                           # peek at the next line so the change lands on time
            for th, v in theme_scores(beats[i + 1].text).items():
                ctx[th] = ctx.get(th, 0) + 0.5 * v
        if b.heading and (i == 0 or beats[i - 1].heading != b.heading):
            for th, v in theme_scores(b.heading).items():
                ctx[th] = ctx.get(th, 0) + v
        best = max(ctx, key=lambda k: (ctx[k], -TIE_ORDER.index(k))) if ctx else None
        if cur is None:
            cur = best if best and ctx[best] >= 1 else default
            since = 0
        elif best and best != cur and since >= min_dwell and ctx[best] >= 2 and ctx[best] >= ctx.get(cur, 0) + 1.2:
            cur, since = best, 0
        quiet = quiet + 1 if not ctx or max(ctx.values()) < 0.8 else 0
        if quiet >= 7 and cur != default and since >= min_dwell:
            cur, since, quiet = default, 0, 0                  # nothing says where we are any more: back to the main setting
        seq.append(cur)
        since += 1
    return seq


@dataclass
class SBeat:
    text: str
    scene: int = 0
    speaker: str = None            # None = Yuki narrating
    emotion: str = None
    heading: str = None
    cues: dict = field(default_factory=dict)
    theme: str = "room_day"
    sfx: list = field(default_factory=list)     # [(fraction, name)]
    onstage: list = field(default_factory=list)
    pose: str = "talk_a"
    face: str = "neutral"
    emote: str = None
    title: bool = False
    visual: object = None
    layout: str = "center"


def _cues(s):
    out = {"sfx": []}
    for m in CUE.finditer(s):
        k, v = m.group(1).lower(), (m.group(2) or "").strip()
        if k == "sfx":
            for part in v.split("|"):
                nm, _, at = part.partition("@")
                nm = nm.strip()
                if nm:
                    try:
                        fr = float(at.strip()) if at.strip() else 0.0
                    except ValueError:
                        fr = 0.0
                    out["sfx"].append((max(0.0, min(1.0, fr)), nm))
        elif k in ("theme", "pose", "face", "emote"):
            out[k] = v.lower() if k != "emote" else v
        elif k == "nosfx":
            out["nosfx"] = True
        elif k == "cast":
            out["cast"] = v
    return out


def guess_emotion(text):
    if ANGRY.search(text):
        return "angry"
    if SHOCK.search(text):
        return "shocked"
    if SADW.search(text):
        return "sad"
    if text.rstrip().endswith("?"):
        return "curious"
    if "!" in text or HAPPYW.search(text):
        return "happy"
    return "neutral"


def parse_story(path):
    """Returns (title, beats, cast_decl) where cast_decl = {name: gender_hint}."""
    from pathlib import Path
    title, heading, beats, scene, decl = None, None, [], 0, {}
    since_break = 0
    text = preprocess(Path(path).read_text(encoding="utf-8"))
    for para in re.split(r"\n\s*\n", text):
        lines = [l.strip() for l in para.strip().splitlines() if l.strip()]
        new_heading = False
        body = []
        for l in lines:
            if re.match(r"^#{2,4}(\s|$)", l):
                heading = l.lstrip("#").strip() or None; new_heading = True
            elif l.startswith("# "):
                title = l[2:].strip()
            else:
                body.append(l)
        if not body:
            if new_heading:
                scene += 1; since_break = 0
            continue
        first_plain = re.sub(r"^(?:\[[^\]]*\]\s*)+", "", body[0])
        if new_heading or (since_break >= 7 and not DIALOGUE.match(first_plain)) or SCENE_BREAK.match(first_plain):
            if beats:
                scene += 1
            since_break = 0
        narr_buf = []

        def flush():
            for b in group_sentences(split_sentences(clean_spoken(" ".join(narr_buf))), lo=60, hi=190):
                beats.append(SBeat(b, scene, None, None, heading))
            narr_buf.clear()

        for l in body:
            m = LEAD.match(l)
            cues, rest = ({"sfx": []}, l)
            if m:
                cues, rest = _cues(m.group(1)), m.group(2).strip()
                if "cast" in cues:
                    for part in re.split(r"[|,;]", cues["cast"]):
                        n, _, g = part.partition("=")
                        g = g.strip().lower()
                        decl[n.strip()] = ("F" if re.match(r"(girl|woman|female|f$|lady|mom|mother|she)", g) else
                                           "M" if re.match(r"(boy|man|male|m$|guy|dad|father|he)", g) else None)
                    if not rest:
                        continue
            d = DIALOGUE.match(rest) if rest else None
            if d and d.group("name").split()[0] not in NOT_NAMES and not rest.startswith("http"):
                flush()
                emo = EMOTIONS.get((d.group("emo") or "").strip().lower())
                txt = clean_spoken(d.group("text")).strip('"“”')
                beats.append(SBeat(txt, scene, d.group("name").strip(), emo or guess_emotion(txt), heading, cues))
            elif rest:
                if m:                        # a cue line is its own narration beat
                    flush()
                    beats.append(SBeat(clean_spoken(rest), scene, None, None, heading, cues))
                else:
                    narr_buf.append(rest)
            elif m and cues:                 # a cue on its own line applies to the next beat
                flush()
                beats.append(SBeat("", scene, None, None, heading, cues))
        flush()
        since_break += 1
    beats = [b for b in beats if b.text or b.cues.get("sfx") or "theme" in b.cues]
    # empty "cue only" beats: merge their cues into the following beat
    merged, carry = [], None
    for b in beats:
        if not b.text:
            carry = b.cues if carry is None else {**carry, "sfx": carry["sfx"] + b.cues["sfx"]}
            continue
        if carry:
            b.cues = {**carry, **b.cues, "sfx": carry["sfx"] + b.cues["sfx"]}
            carry = None
        merged.append(b)
    return title, merged, decl


def _scene_theme(text, prev, run, idx):
    ws = set(re.findall(r"[a-z']+", text.lower()))
    best, score = None, 0
    for th, words in STORY_THEME_WORDS.items():
        s = len(ws & set(words.split()))
        if s > score:
            best, score = th, s
    best = best or pick_theme(text)
    if best == "mind":                      # abstract grid background is for explainers, not stories
        best = None
    order = ["room_day", "city_day", "nature", "sunrise", "night_city"]
    if best is None or (best == prev and run >= 3):
        cands = [x for x in order if x != prev]
        best = cands[idx % len(cands)]
    return best


def plan_story(title, beats, decl):
    """Fill in themes, cast, sound effects, moods and poses. Returns (beats_with_title, cast) where cast = {name: info}."""
    names = []
    for b in beats:
        if b.speaker and b.speaker not in names:
            names.append(b.speaker)
    for n in decl:
        if n and n not in names:
            names.append(n)
    cast, used, used_v = {}, set(), set()
    for n in names:
        look, g, voice, pitch = C.make(n, decl.get(n), avoid=used)
        used.add(look.top)
        pool = A.KOKORO_F if g == "F" else A.KOKORO_M
        k0 = C._h(n) % len(pool)
        kv = next((pool[(k0 + j) % len(pool)] for j in range(len(pool)) if pool[(k0 + j) % len(pool)] not in used_v), pool[k0])
        used_v.add(kv)
        cast[n] = dict(look=look, gender=g, voice=voice, pitch=pitch, kvoice=kv)
    name_rx = {n: re.compile(r"(?<!\w)" + re.escape(n) + r"(?:'s|’s)?(?!\w)", re.I) for n in names}
    theme_seq = assign_themes(beats)
    out = []
    if title:
        out.append(SBeat(title, -1, None, "happy", None, {}, (theme_seq[0] if theme_seq else "room_day"), [], [], "wave", "happy", None, True, V.v_title(title), "split"))
    last_sfx_t = {}                 # sfx name -> beat index
    recent = []                     # recent names (most recent last)
    gap = 99
    cur_theme = None
    for i, b in enumerate(beats):
        new_scene = i == 0 or b.scene != beats[i - 1].scene
        if new_scene:
            recent = []
        if "theme" in b.cues and b.cues["theme"] in THEMES:
            cur_theme = b.cues["theme"]
        elif cur_theme is None or b.cues.get("_reset") or theme_seq[i] != theme_seq[i - 1 if i else 0]:
            cur_theme = theme_seq[i]
        b.theme = cur_theme
        # who is on stage
        mentioned = [n for n in names if name_rx[n].search(b.text)]
        for n in ([b.speaker] if b.speaker else []) + mentioned:
            if n in recent:
                recent.remove(n)
            recent.append(n)
        recent = recent[-4:]
        stage = []
        if b.speaker:
            stage.append(b.speaker)
        for n in reversed(recent):
            if n not in stage:
                stage.append(n)
        stage = stage[:3]
        # keep a stable left-to-right order: order of first appearance in the cast
        b.onstage = sorted(stage, key=lambda n: names.index(n))
        b.layout = "stage" if b.onstage else "center"
        # mood
        emo = b.emotion or b.cues.get("face") or guess_emotion(b.text)
        emo = EMOTIONS.get(emo, emo)
        b.emotion = emo
        b.face = emo if emo in ("happy", "sad", "angry", "shocked", "curious", "worried", "excited") else "neutral"
        # sound effects
        sfx_list = list(b.cues.get("sfx", []))
        if not b.cues.get("nosfx"):
            autos = [(fr, n) for fr, n in SFX.find(b.text) if SFX.get(n) is not None]
            kept = 0
            for fr, n in autos:
                if kept >= 2 or gap < 1 or any(n == x for _, x in sfx_list):
                    continue
                if i - last_sfx_t.get(n, -99) < 5:
                    continue
                sfx_list.append((fr, n)); last_sfx_t[n] = i; kept += 1
        for fr, n in sfx_list:
            last_sfx_t[n] = i
        gap = 0 if sfx_list else gap + 1
        b.sfx = sorted((fr, n) for fr, n in sfx_list if SFX.get(n) is not None)
        for fr, n in sfx_list:
            if SFX.get(n) is None:
                print(f"  ! unknown sound effect '{n}' (see list in the script help)")
        # emote symbol
        e = b.cues.get("emote")
        if not e:
            e = next((EMOTE_SFX[n] for _, n in b.sfx if n in EMOTE_SFX), None) or EMOTE_FOR.get(emo)
        b.emote = e if e in ("!", "?", "heart", "anger", "sweat", "zzz", "star", "dots") else None
        # pose
        if "pose" in b.cues:
            b.pose = b.cues["pose"]
        elif emo in ("excited", "happy") and "!" in b.text and i % 2 == 0:
            b.pose = "cheer"
        elif emo in ("sad", "worried"):
            b.pose = "shrug"
        elif emo == "curious":
            b.pose = "think" if not b.speaker else "talk_a"
        elif emo == "shocked":
            b.pose = "present"
        else:
            b.pose = "talk_a" if i % 2 == 0 else "talk_b"
        out.append(b)
    return out, cast
