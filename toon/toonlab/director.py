"""The brain: reads the script, understands each line (feeling, places, things, numbers, people) and plans the shots.

parse(text)            -> title, sentences   (cues like [face: shocked] [pose: shrug] [set: office] [with: boss] [text: Real Talk] [shot: closeup] [sfx: gasp] [pause: 1])
make_shots(plan, seed) -> list of shots with t0/t1 after the voice timing is known
"""
import re, random
from . import icons, sets
from .expressive import sentence_mood
from . import sfx as SFX

SENT = re.compile(r"[^.!?…]+(?:\.{3}|[.!?…]+)[\"”')\]]*|[^.!?…]+$")
CUE = re.compile(r"\[([a-z_ ]+):\s*([^\]]*)\]", re.I)
NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(%|percent|per cent|times|x|million|billion|thousand|hours?|minutes?|seconds?|days?|weeks?|months?|years?)?", re.I)
QUOTE = re.compile(r"[“\"]([^”\"]{2,40})[”\"]")

TREND = re.compile(r"\\b(rise|rises|rising|grow|grows|growing|increase\\w*|climb\\w*|drop\\w*|fall|falls|falling|declin\\w*|decreas\\w*|shrink\\w*|more and more|less and less)\\b", re.I)
PEOPLE = {  # words that bring another character on screen
    "boss": "boss", "manager": "boss", "teacher": "boss", "professor": "boss", "doctor": "boss", "coworker": "boss", "colleague": "boss",
    "friend": "boy", "friends": "boy", "he": None, "brother": "boy", "dad": "boss", "father": "boss", "guy": "boy",
    "mom": "grandma", "mother": "grandma", "grandma": "grandma", "grandmother": "grandma", "grandparents": "grandma",
    "sister": "girl", "girl": "girl", "girlfriend": "girl", "she": None, "classmate": "curly", "stranger": "curly", "strangers": "curly",
    "teenager": "teen", "teen": "teen", "kid": "curly", "kids": "curly", "child": "curly",
}

FACE_BY_MOOD = {"neutral": ["neutral", "smile"], "happy": ["happy", "smile"], "excited": ["excited", "laughing"], "wonder": ["starry", "excited"], "curious": ["curious", "smile"],
                "shocked": ["shocked"], "worried": ["worried", "nervous"], "sad": ["sad"], "angry": ["angry", "grumpy"]}
FACE_WORDS = [
    (r"\b(awkward|embarrass\w+|cringe|blush\w*)\b", "embarrassed"), (r"\b(tired|sleepy|exhaust\w+|yawn\w*|drowsy|sleep)\b", "sleepy"),
    (r"\b(plan|plot|scheme|secret|sneaky|trick)\b", "scheming"), (r"\b(proud|nailed|crushed it|success\w*|winner)\b", "proud"),
    (r"\b(lol|haha|hilarious|funny|laugh\w*)\b", "laughing"), (r"\b(love|adore|crush|romantic)\b", "lovestruck"),
    (r"\b(bored|boring|nothing happens|meh)\b", "bored"), (r"\b(cry|crying|tears|heartbroken)\b", "crying"),
    (r"\b(confus\w+|no idea|makes no sense|weird)\b", "confused"), (r"\b(scary|terrified|horror|nightmare|panic\w*)\b", "terrified"),
    (r"\b(seriously|really\?|sure\.|obviously|of course)\b", "deadpan"), (r"\b(smart|genius|clever|trick)\b", "smug"),
    (r"\b(calm|peace\w*|relax\w*|breathe|breathing)\b", "serene"), (r"\b(angry|furious|hate|annoy\w+|rage)\b", "angry"),
]
POSE_BY_MOOD = {"neutral": ["talk_a", "present", "talk_b", "relax", "point_r"], "happy": ["present", "talk_a", "thumbs", "wave"], "excited": ["cheer", "talk_a", "present2", "fist"],
                "wonder": ["present2", "hands_up", "idea"], "curious": ["think", "point_r", "talk_b", "shrug"], "shocked": ["hands_up", "stop", "shrug"], "worried": ["shrug", "hands_up", "hug"],
                "sad": ["slump", "relax", "hug"], "angry": ["hips", "fist", "cross"]}
POSE_WORDS = [(r"\b(idea|realize\w*|aha|solution|trick|fix|answer)\b", "idea"), (r"\b(who knows|maybe|no idea|shrug|whatever|perhaps)\b", "shrug"), (r"\b(stop|no more|don.t|never|enough)\b", "stop"),
              (r"\b(look|there|over there|that way|see that)\b", "point_r"), (r"\b(hello|hi |hey|welcome|goodbye|bye)\b", "wave"), (r"\b(win|won|yes|great|awesome|amazing|best)\b", "cheer"),
              (r"\b(think|wonder|question|why|hmm)\b", "think"), (r"\b(whatever|fine|sure|obviously)\b", "cross")]


icons.NO_ICON.update("lie lies lying lay laying ever just tell told scientists scientist call calls chat meeting".split())


def _clean(t):
    return re.sub(r"\s+", " ", re.sub(r"\*+|_{2,}|`", "", t)).strip()


def parse(text):
    title, sents, scene = None, [], 0
    para_buf, para_idx = [], 0
    blocks = re.split(r"\n\s*\n", text.strip())
    for blk in blocks:
        for line in blk.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("# ") and title is None:
                title = _clean(line[2:]); continue
            if line.startswith("## ") or re.fullmatch(r"-{3,}", line):
                scene += 1
                if re.fullmatch(r"-{3,}", line):
                    continue
                line = ""
            if not line:
                continue
            cues = {}
            for m in CUE.finditer(line):
                cues.setdefault(m.group(1).strip().lower(), []).append(m.group(2).strip())
            body = CUE.sub("", line)
            # a line that only holds cues applies to the next sentence
            for m in SENT.finditer(body):
                s = _clean(m.group(0))
                if len(re.findall(r"[A-Za-z0-9]", s)) < 2:
                    continue
                sents.append(dict(text=s, spoken=s, cues={}, scene=scene, para_end=False))
            if sents and cues:
                if not body.strip():
                    pending = cues
                    sents.append(dict(text="", spoken="", cues=pending, scene=scene, para_end=False, cue_only=True))
                else:
                    first = [x for x in sents if not x.get("seen")]
                    tgt = sents[-1]
                    for k, v in cues.items():
                        tgt["cues"].setdefault(k, []).extend(v)
        if sents:
            sents[-1]["para_end"] = True
    # merge cue-only lines into the following sentence
    out, carry = [], {}
    for s in sents:
        if s.get("cue_only"):
            for k, v in s["cues"].items():
                carry.setdefault(k, []).extend(v)
            continue
        for k, v in carry.items():
            s["cues"].setdefault(k, []).extend(v)
        carry = {}
        out.append(s)
    for i, s in enumerate(out):
        s["idx"] = i
    return title, out


def analyze(sents, seed=0):
    """Fill in feeling, face, pose, icons, numbers, people, place for every sentence."""
    rnd = random.Random(seed * 7919 + 13)
    scene_text = {}
    for s in sents:
        scene_text.setdefault(s["scene"], []).append(s["text"])
    prev_mood = "neutral"
    place_by_scene = {k: sets.pick_place(" ".join(v)) for k, v in scene_text.items()}
    last_place = None
    for i, s in enumerate(sents):
        t = s["text"]
        mood = sentence_mood(t, prev_mood if i else "neutral")
        if mood not in FACE_BY_MOOD:
            mood = "neutral"
        s["mood"] = mood
        face = None
        for rx, f in FACE_WORDS:
            if re.search(rx, t, re.I):
                face = f; break
        if "face" in s["cues"]:
            face = s["cues"]["face"][0].strip().lower()
        s["face"] = face or rnd.choice(FACE_BY_MOOD[mood])
        pose = None
        for rx, p in POSE_WORDS:
            if re.search(rx, t, re.I):
                pose = p; break
        if "pose" in s["cues"]:
            pose = s["cues"]["pose"][0].strip().lower()
        s["pose_hint"] = pose
        s["icons"] = icons.find(t, limit=4)
        if "show" in s["cues"]:
            s["icons"] = icons.find(" ".join(s["cues"]["show"]), limit=3) or s["icons"]
        s["quote"] = None
        qm = QUOTE.search(t)
        if "text" in s["cues"]:
            s["quote"] = s["cues"]["text"][0]
        elif qm:
            s["quote"] = qm.group(1)
        nm = NUM.search(t)
        s["number"] = None
        if nm and (nm.group(2) or len(nm.group(1)) <= 4) and not re.fullmatch(r"(19|20)\d\d", nm.group(1)):
            s["number"] = (nm.group(1), (nm.group(2) or "").lower())
        s["people"] = []
        for w in re.findall(r"[a-z]+", t.lower()):
            if PEOPLE.get(w) and PEOPLE[w] not in s["people"]:
                s["people"].append(PEOPLE[w])
        if "with" in s["cues"]:
            s["people"] = [x.strip() for x in s["cues"]["with"][0].split(",") if x.strip()]
        place = sets.pick_place(t) or place_by_scene.get(s["scene"])
        if "set" in s["cues"]:
            place = s["cues"]["set"][0].strip().lower()
        if place:
            last_place = place
        s["place"] = place or last_place
        s["night"] = bool(re.search(r"\b(night|midnight|3 ?am|2 ?am|dark|insomnia|asleep|sleep)\b", t, re.I))
        s["sfx"] = [(f, n) for f, n in SFX.find(t)] if "sfx" not in s["cues"] else [(0.0, s["cues"]["sfx"][0].strip().lower())]
        s["pause"] = float(s["cues"]["pause"][0]) if "pause" in s["cues"] else None
        s["shot_cue"] = s["cues"]["shot"][0].strip().lower() if "shot" in s["cues"] else None
        prev_mood = mood
    return sents


# ------------------------------------------------------------------ shots
def split_chunks(s, dur):
    """Cut one sentence into 1-3 chunks (at commas / conjunctions) so a new picture arrives every ~2.5-4 s."""
    words = s["text"].split()
    n = 1 if dur < 3.9 else (2 if dur < 7.4 else 3)
    if n == 1 or len(words) < 6:
        return [(0.0, 1.0, s["text"])]
    cuts = []
    for k in range(1, n):
        target = k / n
        best, bd = None, 9
        for j in range(2, len(words) - 2):
            w = words[j - 1]
            ok = w.endswith((",", ";", ":", "—")) or words[j].lower() in ("and", "but", "so", "because", "which", "while", "then", "or")
            d = abs(j / len(words) - target) - (0.12 if ok else 0)
            if d < bd and abs(j / len(words) - target) < 0.28:
                best, bd = j, d
        cuts.append(best if best is not None else int(len(words) * target))
    cuts = sorted(set(cuts))
    out, a = [], 0
    for c in cuts + [len(words)]:
        out.append((a / len(words), c / len(words), " ".join(words[a:c])))
        a = c
    return out


def make_shots(sents, seed=0, fmt="long"):
    rnd = random.Random(seed * 31 + 5)
    shots, side, last_kinds = [], 1, []
    pose_i = {}
    prev_place, set_since = None, 0
    cur_pose = "rest"
    for s in sents:
        dur = s["t1"] - s["t0"]
        chunks = split_chunks(s, dur)
        for ci, (f0, f1, ctext) in enumerate(chunks):
            t0 = s["t0"] + f0 * dur
            t1 = s["t0"] + f1 * dur
            if ci == 0:
                t0 -= 0.0
            # ---- icons that belong to this chunk
            n = max(1, len(s["text"]))
            ic = [(h, lab, w, p) for (h, lab, w, p) in s["icons"] if f0 - 0.001 <= p < f1 + 0.001] if len(chunks) > 1 else list(s["icons"])
            strong = [x for x in ic if x[2] in icons.SYN]
            has_quote, has_num = (s["quote"] is not None and ci == len(chunks) - 1 or (s["quote"] is not None and len(chunks) == 1)), (s["number"] is not None and f0 <= 0.7)
            # ---- choose the kind of shot
            kind = s["shot_cue"] if (s["shot_cue"] in ("closeup", "medium", "wide", "prop", "text") and ci == 0) else None
            chart = None
            if kind is None and ci == 0 and "chart" not in last_kinds[-4:] and (t1 - t0) > 1.8:
                cc = s["cues"].get("chart")
                trend = TREND.search(s["text"])
                if cc or trend:
                    if cc:
                        parts = [x.strip() for x in cc[0].split("|")]
                        chart = dict(x=parts[0] if parts and parts[0] else "time", y=parts[1] if len(parts) > 1 else "level", down=len(parts) > 2 and parts[2].lower().startswith("d"))
                    else:
                        lab = (s["icons"][0][2] if s["icons"] else "it")
                        chart = dict(x="time", y=lab, down=bool(re.search(r"drop|fall|declin|decreas|less|shrink|lower", trend.group(0), re.I)))
                    kind = "chart"
            if kind is None:
                if has_quote or (has_num and not last_kinds[-1:] == ["text"]):
                    kind = "text"
                elif len(ic) >= 2 and "prop" not in last_kinds[-2:] and (t1 - t0) > 1.6:
                    kind = "prop"
                elif s["mood"] in ("shocked", "sad", "angry", "excited", "worried") and "closeup" not in last_kinds[-1:]:
                    kind = "closeup"
                elif s["people"] and "wide" not in last_kinds[-2:]:
                    kind = "wide"
                else:
                    cycle = ["medium", "closeup", "medium", "wide", "closeup", "medium"]
                    kind = cycle[len(shots) % len(cycle)]
                    if kind == last_kinds[-1:] [0:1] and True and last_kinds:
                        kind = "closeup" if last_kinds[-1] != "closeup" else "medium"
                if len(last_kinds) >= 2 and last_kinds[-1] == last_kinds[-2] == kind:
                    kind = {"closeup": "medium", "medium": "closeup", "wide": "closeup", "prop": "medium", "text": "closeup", "chart": "medium"}[kind]
            if not shots:
                kind = kind if kind in ("text",) else ("medium" if s["place"] else "closeup")
            # ---- place / backdrop
            place = s["place"]
            if kind in ("closeup",):
                bg = "plain:" + sets.MOOD_PLAIN.get(s["mood"], "cream") if (place is None or rnd.random() < 0.55) else place
                if s["mood"] == "neutral" and rnd.random() < 0.3:
                    bg = "void"
                if rnd.random() < 0.38:
                    bg = "plain:white"
            elif kind == "chart":
                bg = "plain:white"
            elif kind in ("prop", "text"):
                bg = rnd.choice(["void", "plain:white", "plain:cream", "plain:sky", "plain:mint"]) if kind == "prop" else "plain:" + rnd.choice(["yellow", "peach", "lilac", "sky", "mint", "rose"])
            else:
                bg = place or rnd.choice(["living", "park", "street", "mind", "office"])
            night = bool(s["night"]) and bg in ("bedroom", "office", "living", "street", "park", "kitchen", "classroom")
            # ---- pose / face
            hint = s["pose_hint"]
            plist = POSE_BY_MOOD.get(s["mood"], POSE_BY_MOOD["neutral"])
            k = pose_i.get(s["mood"], rnd.randrange(len(plist)))
            pose_i[s["mood"]] = k + 1
            pose = hint if (hint and ci == 0) else plist[k % len(plist)]
            face = s["face"]
            if ci == len(chunks) - 1 and s["para_end"] and s["mood"] in ("neutral", "happy", "curious"):
                face = rnd.choice(["smile", "proud", "happy"]) if "face" not in s["cues"] else face
            side = -side if kind != "text" else side
            sh = dict(kind=kind, t0=t0, t1=t1, sent=s["idx"], chunk=ci, text=ctext, bg=bg, night=night, face=face, pose=pose, prev_pose=cur_pose, side=side,
                      icons=ic[:3] if kind != "prop" else (ic + [x for x in s["icons"] if x not in ic])[:4], people=s["people"][:2] if kind in ("wide", "medium") else [],
                      chart=chart, quote=s["quote"] if has_quote else None, number=s["number"] if (has_num and kind == "text") else None, mood=s["mood"], f0=f0, f1=f1)
            cur_pose = pose
            shots.append(sh)
            last_kinds.append(kind)
    # chain: each shot runs until the next one starts (no gaps)
    for i in range(len(shots) - 1):
        shots[i]["t1"] = shots[i + 1]["t0"]
    return shots
