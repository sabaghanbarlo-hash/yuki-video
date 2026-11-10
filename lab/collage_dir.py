"""The director of the collage look ("explainer show").

A collage video is a cream page where a picture (or two) changes every 2-4 seconds while Yuki sits in a corner of the
screen and reacts: she points, thinks, shrugs, slumps when it is about sleep, folds her arms when the script says "actually",
puts a hand on her head when it is worrying, and small cards (?, !, zzz ...) pop up next to her.

This module turns the sentences of one scene into those beats (shots). Everything is chosen from the words:

    beats      a sentence is cut at commas / "and" / "but" ... into pieces of roughly 5-12 words (about 2-4 s of narration)
    what       a picture of the idea, a big phrase on screen (quoted or "called ..."), 2-3 icons for a list, a counting number,
               two pictures side by side for a comparison
    layout     big panel left/right, medium panel, centred panel, two panels, full-screen picture; Yuki takes the free corner
    Yuki       pose + face from the mood of the words; arms ease from the previous pose at every cut
    cues       [show: a tired man rubbing his eyes]  [show: file:tired-man.jpg]  [text: Fake scenarios]  [pose: cross]  [face: smug]
               [layout: split]  [treat: blob]  [media: drawn]  - inline cues apply to the beat they sit in
"""
import re

from . import knowledge as K

R = lambda p: re.compile(p, re.I)

# ------------------------------------------------------------------ what the words feel like
L_SLEEP = R(r"\b(sleep\w*|tired|exhaust\w*|insomnia|bed|awake|yawn\w*|drowsy|fatigue\w*|wake|woke|nap\w*)\b")
L_WORRY = R(r"\b(anxi\w+|worr\w+|stress\w*|fear\w*|afraid|scared|panic\w*|nervous|dread\w*|overthink\w*|can.t|cannot|unable|struggl\w+|trouble|problems?|pain\w*|hurt\w*|lonely|depress\w+|burn\w*out|overwhelm\w*|bad|worse|worst|dangerous|risk\w*)\b")
L_ANGRY = R(r"\b(angry|anger|furious|rage|hate\w*|annoy\w*|frustrat\w*|rude|stupid|toxic|lie[sd]?|lying|unfair|blame\w*|ridiculous)\b")
L_HAPPY = R(r"\b(happy|joy\w*|love[sd]?|great|good|win\w*|won|success\w*|better|best|enjoy\w*|fun|wonderful|celebrat\w*|proud|laugh\w*|smile\w*|relax\w*|calm|peace\w*|beautiful)\b")
L_SMUG = R(r"\b(actually|not quite|myth|fake|false|wrong|isn.t|aren.t|doesn.t|don.t|never|however|nope|supposedly|so.called|pretend\w*|lie)\b")
L_SHRUG = R(r"\b(maybe|might|perhaps|who knows|not sure|somehow|probably|sort of|kind of|whatever|depends|unclear|nobody knows|no one knows)\b")
L_LOOK = R(r"\b(look\w*|notice\w*|closer|research\w*|stud(y|ies|ied)|scientists?|evidence|data|found|discover\w*|experiment\w*|test\w*|observ\w*|examin\w*|analy\w+|psycholog\w+)\b")
L_IDEA = R(r"\b(idea|realiz\w+|solution|key|trick|secret|turns? out|insight|answer|tip|hack|reason|because)\b")
L_INTRO = R(r"^\s*(hey|hi|hello|welcome|today|in this (video|episode)|let.s|ever)\b")
L_SHOCK = R(r"\b(suddenly|shock\w*|wait|unexpected\w*|surpris\w+|insane|crazy|unbelievable|wow|whoa|boom|instantly)\b")
L_SAD = R(r"\b(sad\w*|cry|cries|cried|crying|tears?|grief|griev\w+|lost|loss|miss(ed|ing)?|alone|heartbreak\w*|heartbroken|goodbye|died|death|funeral|mourn\w*|hopeless|regret\w*|empty)\b")
L_LAUGH = R(r"\b(funny|hilarious|joke[sd]?|laugh\w*|lol|haha+|ridiculous|silly|comedy|prank\w*|lmao)\b")
L_LOVE = R(r"\b(love[sd]?|loving|adore\w*|romantic|crush\w*|cute|kiss\w*|beloved)\b")
L_AWE = R(r"\b(amazing|incredible|wonder\w*|magical|breathtaking|stunning|gorgeous|marvel\w*|mind.?blowing|spectacular|awesome|inspir\w+)\b")
L_DIZZY = R(r"\b(confus\w+|dizzy|spin\w*|complicated|paradox\w*|puzzl\w+|mess|chaos|chaotic|overwhelm\w*|makes no sense|baffl\w+|weird|strange)\b")
L_BORED = R(r"\b(boring|bored|dull|nothing happens|same thing|routine|monoton\w+|whatever|meh|average|ordinary|so what)\b")
L_CREEPY = R(r"\b(creepy|scary|terrifying|horror|haunt\w*|ghost\w*|dark|darkness|nightmare\w*|sinister|eerie|disturbing|watching you|spooky|monster\w*|shadow\w*)\b")
L_NERVOUS = R(r"\b(nervous|awkward|embarrass\w+|shy|blush\w*|oops|sorry|apolog\w+|uncomfortable|cringe|yikes|mistake)\b")
L_PAIN = R(r"\b(ouch|painful|hurts?|injur\w+|crash\w*|slip\w*|sting\w*|broken|bruise\w*)\b")
L_PROUD = R(r"\b(proud|achiev\w+|accomplish\w*|victory|champion|winner|nailed|mastered|finally did|success|conquer\w*|crushed it)\b")
L_PLAN = R(r"\b(scheme\w*|sneaky|secretly|mischie\w+|cunning|outsmart\w*|trap)\b")
L_YUM = R(r"\b(delicious|tasty|yummy|eat\w*|food|cake|pizza|chocolate|sweets?|snack\w*|hungry|coffee|dinner|lunch|breakfast)\b")
L_DETERMINED = R(r"\b(determin\w+|never give up|keep going|push\w* through|fight\w*|challenge\w*|discipline|commit\w*|focus\w*|grind\w*|work hard|effort|persist\w*)\b")
L_STOP = R(r"\b(stop|don.t do|never do|avoid|warning|careful|wait a second|hold on)\b")
L_PEOPLEISH = R(r"\b(he|she|man|woman|people|person|friend|guy|girl|boy|someone|you|we|they|boss|doctor|teacher|mother|father|kids?|child\w*)\b")

QSTOP = set("""a an the and or of to in on at for with by from as is are was were be been being it its this that these those you your i me my we our
they their he she his her him them us not no yes so but if then than too very really just also even still only own same such like get gets got make
makes made go goes went going say says said know knows known think thinks thought want wants need needs feel feels felt see sees seen look looks come
comes came take takes took give gives gave let lets put puts keep keeps kept try tries tried use uses used find finds found tell tells told ask asks
thing things way ways lot lots kind much many more most some any every each all both few little something anything everything nothing someone anyone
everyone one two three here there where when what which who whom whose why how because while after before again always never often sometimes
already yet ever about into over under out up down off back well now today day days time times people actually basically literally simply
can could would should will shall may might must do does did done have has had having""".split())

NUMBERWORDS = set("one two three four five six seven eight nine ten hundred thousand million billion".split())

FACE_DEFAULTS = [("smile", "talk_a"), ("neutral", "point"), ("smile", "talk_b"), ("neutral", "present"), ("smile", "pen"), ("neutral", "talk_a")]
GENERIC_ICONS = {"body": "heart", "brain": "brain", "micro": "cell", "physics": "atom", "tech": "monitor", "city": "crowd", "history": "clock",
                 "food": "water_drop", "space": "planet", "nature": "tree", "generic": "bulb", "disaster": "skull", "earth": "earth", "ocean": "wave",
                 "weather": "cloud", "volcano": "volcano", "ice": "snowflake", "desert": "sun"}
ACCENT_COLOURS = [(255, 206, 74), (92, 214, 255), (255, 112, 160), (140, 240, 170), (190, 150, 255), (255, 150, 90)]


# ------------------------------------------------------------------ cutting a sentence into beats
def _words(t):
    return len(t.split())


def split_beats(text, lo=4, hi=10):
    """-> [(start_char, end_char)] covering the sentence; each piece is about 4-10 words (2-4 seconds of narration)."""
    text = text.strip()
    if _words(text) <= hi:
        return [(0, len(text))]
    cuts = [m.end() for m in re.finditer(r"[,;:—–]\s+|\s(?=(?:and|but|because|so|which|while|when|then|or|yet|until|since|although|if)\s)", text)]
    cuts = sorted(set(c for c in cuts if 0 < c < len(text)))
    pieces, start = [], 0
    for c in cuts + [len(text)]:
        seg = text[start:c]
        nxt_len = len(text[c:].split())
        if _words(seg) >= lo and (nxt_len >= 3 or c == len(text)):
            pieces.append((start, c)); start = c
    if start < len(text):
        if pieces and _words(text[start:]) < 3:
            pieces[-1] = (pieces[-1][0], len(text))
        else:
            pieces.append((start, len(text)))
    out = []
    for a, b in pieces:                                   # cut pieces that are still long at the middle space
        seg = text[a:b]
        while _words(seg) > hi + 3:
            ws = [m.end() for m in re.finditer(r"\s", seg)]
            mid = min(ws, key=lambda x: abs(x - len(seg) / 2))
            out.append((a, a + mid)); a += mid; seg = text[a:b]
        out.append((a, b))
    return out or [(0, len(text))]


# ------------------------------------------------------------------ what to show
FILLER_WORDS = {"remember", "sometimes", "always", "never", "maybe", "really", "actually", "basically", "simply", "just", "keep", "making", "makes", "make", "take", "takes",
                "thing", "things", "something", "anything", "everything", "means", "mean", "means", "going", "doing", "being", "having", "getting", "trying", "need", "needs",
                "best", "better", "often", "every", "much", "many", "more", "most", "very", "even", "still", "also", "here", "there", "that", "this", "than", "then", "your", "yours"}


def caps(phrase):
    """Capitalise each word without the 'Don'T' bug of str.title()."""
    return " ".join(w[:1].upper() + w[1:] for w in phrase.split())


def key_phrase(txt, n=4):
    ws = re.findall(r"[A-Za-z][A-Za-z'\-]+", txt)
    keep, seen = [], set()
    for w in ws:
        lw = w.lower().strip("'-")
        if "'" in lw or lw in FILLER_WORDS or lw in QSTOP or lw in NUMBERWORDS or len(lw) < 4 or lw in seen:
            continue
        seen.add(lw); keep.append(lw)
    return " ".join(keep[:n])


def stat_caption(txt):
    """The few words that say what a number counts: 'about 70 percent of people with insomnia' -> 'people with insomnia'."""
    m = K.NUM.search(txt)
    after = re.sub(r"^\s*(of|in|on|for|per|a|an|the)\b\s*", "", txt[m.end():].strip(" ,.;:!?")) if m else ""
    ws = [w for w in after.split()][:4]
    if len(ws) < 1 and m:
        ws = key_phrase(txt[:m.start()], 3).split()
    return " ".join(ws)


def clean_prompt(txt):
    """The beat itself, tidied, as a picture prompt for the AI (it understands sentences better than keyword lists)."""
    t = re.sub(r"\[[^\]]*\]", " ", txt)
    t = re.sub(r"[\"“”]", "", t)
    t = re.sub(r"^\s*(and|but|so|then|because|which|while|when|or|yet|now|well|okay|ok)\b[,\s]*", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" ,.;:!?")
    return " ".join(t.split()[:24])


def quoted_or_called(txt):
    m = re.search(r"[\"“]([^\"”]{3,34})[\"”]", txt) or re.search(r"\b(?:called|known as|named|termed|the term|dubbed)\s+[\"“]?([A-Za-z][\w' \-]{2,30}?)[\"”]?(?:[,.;!?]|$|\s(?:and|but|which|is|are))", txt)
    if m:
        t = m.group(1).strip(" ,.")
        return t[:1].upper() + t[1:]
    return None


def clause_items(txt, limit=3):
    parts = [p.strip(" .,;:!?") for p in re.split(r",|;|\band\b|\bor\b", txt) if len(p.split()) >= 1]
    items = []
    for p in parts:
        kp = key_phrase(p, 2)
        if kp:
            items.append(kp)
    return items[:limit]


def read_mood(txt, f, first_overall, rng, i):
    """-> (face, pose, accents). pose 'point' is resolved to point_r / point_l by the caller.
    About 30 feelings: each has a few (face, pose, accent) looks to choose from so repeats do not look the same."""
    t = txt.strip()
    C = lambda *opts: rng.choice(opts)
    if first_overall and L_INTRO.search(t):
        return "happy", "wave", ["spark"]
    if t.endswith("?") or f.get("hook"):
        return C(("curious", "think", ["q"]), ("confused", "head", ["q"]), ("curious", "think_l", ["q"]))
    if L_SLEEP.search(t):
        return C(("sleepy", "slump", ["zzz"]), ("bored", "slump", ["zzz"]))
    if L_CREEPY.search(t):
        return C(("creepy", "rest", ["gloom"]), ("terrified", "shake", ["sweat"]), ("nervous", "hands_up", ["sweat"]))
    if L_PAIN.search(t):
        return C(("pained", "shake", ["ex"]), ("crying", "sob", []), ("pained", "head", ["ex"]))
    if L_SAD.search(t):
        return C(("crying", "sob", ["gloom"]), ("teary", "heart", ["gloom"]), ("sad", "slump", ["gloom"]))
    if L_ANGRY.search(t):
        return C(("angry", "cross", ["anger"]), ("grumpy", "hips", ["anger"]), ("angry", "fist", ["anger"]))
    if L_NERVOUS.search(t):
        return C(("embarrassed", "shy", ["sweat"]), ("awkward", "shy", ["dots"]), ("nervous", "shake", ["sweat"]))
    if L_WORRY.search(t):
        return C(("worried", "head", ["sweat"]), ("nervous", "shake", ["sweat"]), ("worried", "facepalm", []))
    if L_DIZZY.search(t):
        return C(("dizzy", "head", ["q"]), ("confused", "shrug", ["q"]), ("dizzy", "hands_up", []))
    if L_LAUGH.search(t):
        return C(("laughing", "clap", ["ha"]), ("laughing", "hips", ["ha"]), ("cheeky", "talk_a", ["spark"]))
    if L_LOVE.search(t):
        return C(("lovestruck", "heart", ["heart"]), ("dreamy", "shy", ["heart"]), ("lovestruck", "gasp_hands", ["heart"]))
    if L_AWE.search(t):
        return C(("starry", "gasp_hands", ["star"]), ("inspired", "cheer", ["spark"]), ("starry", "clap", ["star"]))
    if L_SHOCK.search(t) or t.endswith("!"):
        return C(("gasp", "gasp_hands", ["ex"]), ("shocked", "shrug", ["ex"]), ("terrified", "hands_up", ["ex"]), ("gasp", "cheer", ["ex"]))
    if L_PROUD.search(t):
        return C(("proud", "hips", ["spark"]), ("proud", "fist", ["star"]), ("happy", "cheer", ["spark"]))
    if L_PLAN.search(t):
        return C(("scheming", "cross", []), ("scheming", "pen", []), ("cheeky", "idea", ["bulb"]))
    if L_STOP.search(t):
        return C(("determined", "stop", ["ex"]), ("worried", "stop", []))
    if L_YUM.search(t):
        return C(("yum", "talk_a", ["spark"]), ("happy", "heart", ["spark"]))
    if L_DETERMINED.search(t):
        return C(("determined", "fist", ["spark"]), ("determined", "hips", []))
    if L_BORED.search(t):
        return C(("bored", "relax", ["dots"]), ("deadpan", "shrug", ["dots"]), ("bored", "cross", []))
    if L_IDEA.search(t) and rng.random() < 0.7:
        return C(("excited", "idea", ["bulb"]), ("inspired", "idea", ["bulb"]))
    if L_SMUG.search(t):
        return C(("smug", "cross", []), ("scheming", "cross", []), ("deadpan", "shrug", []))
    if L_SHRUG.search(t):
        return C(("neutral", "shrug", []), ("awkward", "shrug", ["dots"]), ("confused", "shrug", ["q"]))
    if L_LOOK.search(t) and rng.random() < 0.8:
        return C(("smile", "magnify", []), ("smile", "pen", []), ("curious", "magnify", []))
    if L_HAPPY.search(t):
        return C(("happy", "cheer", ["spark"]), ("happy", "talk_a", []), ("proud", "talk_b", []), ("happy", "dance", ["note"]))
    face, pose = FACE_DEFAULTS[i % len(FACE_DEFAULTS)]
    return face, pose, []


def _pick(rng, items, weights, avoid=None):
    ws = [w * (0.25 if it == avoid else 1.0) for it, w in zip(items, weights)]
    r, acc = rng.random() * sum(ws), 0.0
    for it, w in zip(items, ws):
        acc += w
        if r <= acc:
            return it
    return items[-1]


# ------------------------------------------------------------------ the scene
def plan_shots(scene, rng, prev_scene, first_overall=False):
    from .director import features
    sents = scene["sentences"]
    cues = scene["cues"]
    topic = scene.get("topic") or "generic"
    st = dict(prev_scene["_cc"]) if prev_scene and prev_scene.get("_cc") else dict(side="r", layout=None, treat=None, enter=None, kind=None, query="", queries=None, stock=None, seed=1, n=0, pose="rest", face="neutral", flip=False)
    shots = []
    for si, s in enumerate(sents):
        text = s["text"].strip()
        beats = split_beats(text)
        for bi, (c0, c1) in enumerate(beats):
            txt = text[c0:c1].strip()
            f = features(txt)
            inline = {}
            for (pos, key, val) in s.get("inline", []):
                if c0 <= pos < c1 or (bi == len(beats) - 1 and pos >= c1):
                    inline[key] = val
            first = first_overall and si == 0 and bi == 0
            scene_cues = cues if (si == 0 and bi == 0) else {}
            get = lambda k: inline.get(k) or scene_cues.get(k)

            # ---- what the beat is
            nums = f["nums"]
            term = get("text") or quoted_or_called(txt)
            items = clause_items(txt) if (f["listy"] and len(clause_items(txt)) >= 2) else []
            kind = "media"
            if get("text") or term:
                kind = "text"
            elif nums and rng.random() < 0.85 and not first:
                kind = "stat"
            elif len(items) >= 2 and rng.random() < 0.55 and st["kind"] != "icons":
                kind = "icons"
            elif _words(txt) >= 7 and not f["hook"] and rng.random() < 0.04 and st["kind"] == "media" and key_phrase(txt, 2):
                kind, term = "text", caps(key_phrase(txt, 2))
            if st["kind"] in ("text", "stat") and kind in ("text", "stat") and rng.random() < 0.7:
                kind = "media"                                         # never two text-ish beats in a row

            # ---- the picture(s)
            ents = [e for e in f["ents"] if e[0] not in ("person", "crowd")]
            phrase = key_phrase(txt, 4)
            q = get("show") or ""
            want_file = None
            if q.lower().startswith("file:"):
                want_file, q = q[5:].strip(), ""
            if not q:
                if ents:
                    q = (ents[0][1].lower() + (" " + phrase if phrase and ents[0][1].lower() not in phrase else ""))[:70].strip()
                else:
                    q = phrase
            reuse = False                                              # every beat gets its own picture (never "stay on the last one")
            if not q:
                q = topic if topic != "generic" else "idea"
            ai_text = get("show") or clean_prompt(txt)
            queries, stock_queries = [ai_text if not reuse else ai_text], [" ".join(q.split()[:3])]
            split = False
            part_txt = [txt]
            lay_cue = (get("layout") or "").lower()
            if (K.COMPARE.search(txt) and kind == "media") or lay_cue == "split":
                m = re.split(r"\b(?:than|versus|vs\.?|compared (?:to|with)|while|but)\b", txt, maxsplit=1)
                if len(m) == 2 and key_phrase(m[0], 3) and key_phrase(m[1], 3):
                    queries = [clean_prompt(m[0]), clean_prompt(m[1])]
                    stock_queries = [key_phrase(m[0], 3), key_phrase(m[1], 3)]
                    part_txt = [m[0], m[1]]
                    split = True

            # ---- layout / treatment
            avoid_lay = st["layout"]
            if kind in ("text", "icons", "stat"):
                layout = {"text": "title", "icons": "icons", "stat": "stat"}[kind]
            elif split:
                layout = "split"
            elif lay_cue in ("full", "mid", "center", "fullbleed", "split"):
                layout = lay_cue
            elif reuse and st["layout"] in ("full", "mid", "center", "fullbleed"):
                layout = st["layout"]
            else:
                layout = _pick(rng, ["full", "mid", "center", "fullbleed"], [4.6, 2.0, 0.5, 0.3], avoid_lay)   # the lab's own animation is the star: big panels
            side = (get("side") or "").lower()[:1]
            if side not in ("l", "r"):
                side = ("l" if st["side"] == "r" else "r") if rng.random() < 0.78 else st["side"]
            if reuse:
                side = st["side"]
            peopleish = len(L_PEOPLEISH.findall(txt)) >= 1 and not ents
            treat = (get("treat") or "").lower()
            if treat not in ("frame", "color", "blob", "sticker"):
                treat = _pick(rng, ["frame", "color", "blob", "sticker"], [0.45, 0.22, 0.45 if peopleish else 0.2, 0.18 if peopleish else 0.06], st["treat"])
            if reuse:
                treat = st["treat"] or treat
            enter = _pick(rng, ["pop", "slide", "rise", "fade", "cut"], [0.34, 0.22, 0.14, 0.10, 0.20], st["enter"])
            if layout == "fullbleed":
                enter = rng.choice(["fade", "cut"])
            if reuse:
                enter = "cut"

            # ---- Yuki
            try:                                                       # what the sentence DOES + feels like (negation aware), see understand.py
                from . import understand as U
                umem = st.setdefault("_u", U.new_memory())
                last = bool(scene.get("idx", 0) == U.STATE["n_scenes"] - 1 and si == len(sents) - 1 and bi == len(beats) - 1) if U.STATE["n_scenes"] else False
                hint = U.hint(txt, umem, rng, first=first, last=last)
                U.remember(umem, hint)
                face, pose, acc = hint["face"], hint["pose"], hint["acc"]
            except Exception as e:                                     # never fail a video because of the smart layer
                print(f"  [understand] fallback ({type(e).__name__}: {e})", flush=True)
                hint = None
                face, pose, acc = read_mood(txt, f, first, rng, st["n"])
            if get("face") or get("expr"):
                face = (get("face") or get("expr")).lower()
            if get("pose"):
                pose = get("pose").lower()
            if pose == "point":
                pose = "point_r"
            if pose == "talk_b" and st["pose"] == "talk_b":
                pose = "talk_a"
            if pose == st["pose"] and pose in ("cross", "head", "slump", "think", "shy", "sob", "hips", "heart", "shake") and rng.random() < 0.5:
                pose = "talk_a" if rng.random() < 0.5 else "present"      # do not freeze in one pose for a whole paragraph
            yuki_side = "l" if side == "r" else "r"
            if layout in ("title", "icons", "stat"):
                yuki_side = "l" if (side == "r") else "r"
            flip = yuki_side == "r"
            gaze = 1 if (side == "r") else -1
            tilt = {"curious": 5, "worried": -4, "smug": 4, "sleepy": -5, "confused": 7, "dizzy": -7, "crying": -4, "starry": 3, "scheming": 5, "dreamy": -5, "embarrassed": -6, "awkward": 4}.get(face, 2.5 if bi % 2 else -2.5) * (-1 if flip else 1)
            hop = face in ("shocked", "excited", "gasp", "starry", "laughing", "inspired", "proud") or first or (bool(acc) and "spark" in acc)
            kb = dict(z0=1.0, z1=1.0 + rng.uniform(0.05, 0.10), dx=rng.uniform(-0.5, 0.5), dy=rng.uniform(-0.4, 0.4))
            if rng.random() < 0.4:
                kb["z0"], kb["z1"] = kb["z1"], kb["z0"]
            size = {"full": (1024, 576), "mid": (896, 576), "center": (896, 512), "split": (640, 704), "fullbleed": (1024, 576), "title": (768, 512)}.get(layout, (896, 576))
            if reuse and st.get("queries"):
                queries, stock_queries, shot_seed = st["queries"], st["stock"], st["seed"]
                split = len(queries) > 1 and layout == "split"
            else:
                shot_seed = rng.randrange(1, 99999)
            shot = dict(
                sent=[si, si], span=[c0 / max(1, len(text)) if bi else 0.0, c1 / max(1, len(text)) if bi < len(beats) - 1 else 1.0],
                text=txt, template="collage", cam=dict(k="none", amp=0, flip=False), actors=[], feat=dict(mood=f["mood"], ents=[e[0] for e in ents]),
                kind=kind, layout=layout, side=side, treat=treat, enter=enter, queries=queries if kind in ("media", "text") else [], stock_queries=stock_queries,
                file=want_file, reuse=reuse, media_size=size, seed=shot_seed, kb=kb,
                pose=pose, face=face, yuki_side=yuki_side, flip=flip, gaze=gaze, tilt=tilt, hop=bool(hop), accents=acc,
                title=(term or "")[:40], icons=[], stat=None, colour=rng.randrange(len(ACCENT_COLOURS)),
                cut_sfx=("pop" if enter in ("pop", "rise", "cut") else "whoosh" if enter == "slide" else None),
            )
            if kind == "icons":
                from .director import entities_in
                topic_icon = GENERIC_ICONS.get(topic, "bulb")
                for it in items:
                    e = entities_in(it, 1)
                    shot["icons"].append(dict(label=it, entity=e[0][0] if e else topic_icon))
            if kind == "stat" and nums:
                shot["stat"] = dict(display=nums[0]["display"], sub=stat_caption(txt))
            if kind in ("media", "text"):                              # the lab's own picture, drawn from this beat's keywords
                from . import illustrate as IL
                mem = st.setdefault("_mem", IL.new_memory())
                shot["draw"] = [IL.plan_picture(pt, shot_seed, mem, topic, face, qi, kind, hint=hint if qi == 0 else None) for qi, pt in enumerate(part_txt)]
                shot["why"] = dict(role=hint["role"], emotion=hint["emotion"], concepts=hint["concepts"], source=hint["source"]) if hint else None
            shots.append(shot)
            if kind in ("media", "text"):
                st.update(queries=queries, stock=stock_queries, seed=shot_seed)
            st.update(side=side, layout=layout, treat=treat, enter=enter, kind=kind, query=q if kind in ("media", "text") else st["query"], n=st["n"] + 1,
                      pose=pose, face=face, flip=flip)
    # every shot knows how Yuki looked just before it (her arms ease from there)
    prev = prev_scene["shots"][-1] if prev_scene and prev_scene.get("shots") else None
    for sh in shots:
        sh["prev"] = dict(pose=prev["pose"], face=prev["face"], flip=prev["flip"]) if prev else dict(pose="rest", face="neutral", flip=sh["flip"])
        prev = sh
    scene["_cc"] = st
    return shots
