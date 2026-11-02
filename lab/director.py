"""The director: reads the scenes of a script and decides, for every scene and every shot, what the video looks like.

Nothing here is a fixed template. For each scene it weighs what the words are about (space? the ocean? a person in a
situation? a number? a comparison?) and picks a visual style, a place, a time of day, a camera move, who is on screen,
what they do and what appears around them, so two different scripts (or two different scenes of one script) never end
up looking alike. The result is a plain dict structure (see `Plan` below) that the renderer draws and the web page can show.

    plan = direct(title, raw_scenes, seed)
    plan["scenes"][i] = dict(style, env, pal, tod, seed, mood, topic, transition, ambient, sentences=[...], shots=[...])
    shot = dict(sent=[first, last], template, cam=dict(...), actors=[...], sfx=[...])
Times (t0/t1) are added later by lab.pipeline once the narration has been recorded and measured.
"""
import hashlib, math, random, re
from . import knowledge as K
from .script import RawScene, WPS

STYLE_ALIASES = {"flat": "flat", "kurz": "flat", "kurzgesagt": "flat", "infographic": "flat", "explainer": "flat", "diagram": "flat",
                 "voxel": "voxel", "minecraft": "voxel", "blocky": "voxel", "blocks": "voxel", "3d": "voxel", "block": "voxel",
                 "toon": "toon", "characters": "toon", "character": "toon", "cartoon": "toon", "people": "toon", "simple": "toon",
                 "collage": "collage", "show": "collage", "host": "collage", "yuki": "collage", "pictures": "collage", "panels": "collage", "explainer_show": "collage"}
ENV_ALIASES = {   # words people write -> env ids per style
    "space": dict(flat="deep_space", voxel="space", toon="space"), "deep_space": dict(flat="deep_space", voxel="space", toon="space"),
    "galaxy": dict(flat="nebula", voxel="space", toon="space"), "nebula": dict(flat="nebula", voxel="space", toon="space"),
    "solar_system": dict(flat="solar", voxel="space", toon="space"), "solar": dict(flat="solar", voxel="space", toon="space"),
    "orbit": dict(flat="orbit", voxel="space", toon="space"), "moon": dict(flat="orbit", voxel="space", toon="space"),
    "ocean": dict(flat="ocean_surface", voxel="ocean", toon="beach"), "sea": dict(flat="ocean_surface", voxel="ocean", toon="beach"),
    "underwater": dict(flat="ocean_deep", voxel="underwater", toon="underwater"), "deep_sea": dict(flat="ocean_deep", voxel="underwater", toon="underwater"),
    "volcano": dict(flat="ember", voxel="volcano", toon="cave"), "lava": dict(flat="ember", voxel="volcano", toon="cave"),
    "ice": dict(flat="arctic", voxel="snow", toon="snow"), "arctic": dict(flat="arctic", voxel="snow", toon="snow"), "snow": dict(flat="arctic", voxel="snow", toon="snow"),
    "desert": dict(flat="dusk_desert", voxel="desert", toon="desert"), "storm": dict(flat="storm", voxel="plains", toon="hills"),
    "cell": dict(flat="micro", voxel="cave", toon="lab"), "micro": dict(flat="micro", voxel="cave", toon="lab"), "body": dict(flat="micro", voxel="cave", toon="lab"),
    "brain": dict(flat="neural", voxel="cave", toon="room"), "neural": dict(flat="neural", voxel="cave", toon="room"),
    "lab": dict(flat="lab", voxel="cave", toon="lab"), "laboratory": dict(flat="lab", voxel="cave", toon="lab"),
    "city": dict(flat="night_city", voxel="city", toon="street"), "street": dict(flat="night_city", voxel="city", toon="street"),
    "data": dict(flat="data", voxel="city", toon="room"), "tech": dict(flat="data", voxel="city", toon="room"),
    "tunnel": dict(flat="tunnel", voxel="cave", toon="stage"), "time": dict(flat="tunnel", voxel="plains", toon="stage"),
    "sky": dict(flat="day_sky", voxel="islands", toon="hills"), "forest": dict(flat="forest", voxel="plains", toon="forest"), "jungle": dict(flat="forest", voxel="plains", toon="forest"),
    "plains": dict(flat="day_sky", voxel="plains", toon="hills"), "hills": dict(flat="day_sky", voxel="plains", toon="hills"), "beach": dict(flat="ocean_surface", voxel="ocean", toon="beach"),
    "cave": dict(flat="strata", voxel="cave", toon="cave"), "room": dict(flat="lab", voxel="city", toon="room"), "stage": dict(flat="tunnel", voxel="islands", toon="stage"),
    "rooftop": dict(flat="night_city", voxel="city", toon="rooftop"), "islands": dict(flat="day_sky", voxel="islands", toon="hills"), "strata": dict(flat="strata", voxel="cave", toon="cave"),
}
CAMERAS_2D = ["push", "pull", "pan_l", "pan_r", "rise", "sink", "drift", "drift2"]
TRANSITIONS = ["fade", "wipe_l", "wipe_r", "slide", "iris", "zoom", "push", "flash"]

SKY_THINGS = {"sun", "moon", "planet", "ringed", "star", "galaxy", "blackhole", "comet", "asteroid", "rocket", "satellite", "ufo", "plane", "cloud", "bolt", "earth", "explosion"}
GROUND_THINGS = {"volcano", "mountain", "tree", "house", "car", "skyline", "pyramid", "dino", "crowd", "robot", "person"}
NOISY = {"clock", "eye", "gear", "coin", "scale", "water_drop", "person", "crowd", "cloud", "monitor", "phone", "battery", "bulb", "magnet", "sound", "thermo", "fire", "skull", "wave", "rain", "bolt", "explosion"}
ACTION_BY_MOOD = {"danger": ["panic", "run", "fall", "look_up"], "wonder": ["look_up", "cheer", "point", "float"], "funny": ["shrug", "jump", "cheer", "talk"],
                  "calm": ["idle", "sit", "think", "walk"], "shock": ["panic", "jump", "look_up", "fall"], "curious": ["think", "look_up", "point", "walk"],
                  "neutral": ["talk", "point", "walk", "think", "idle"]}
EXPR_BY_MOOD = {"danger": "worried", "wonder": "happy", "funny": "happy", "calm": "neutral", "shock": "shocked", "curious": "curious", "neutral": "neutral"}
ENT_LIFT = {"whale": 0.58, "shark": 0.55, "fish": 0.5, "jellyfish": 0.45}


def _seed_of(*parts):
    h = hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:8], 16)


def resolve_style(v):
    return STYLE_ALIASES.get((v or "").strip().lower())


def resolve_env(name, style):
    """Accept 'ocean', 'deep sea', 'night city' ... for any style -> a real env id of that style (or None)."""
    n = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    if n in K.ALL_ENVS.get(style, []):
        return n
    if n in ENV_ALIASES:
        return ENV_ALIASES[n][style]
    for k, v in ENV_ALIASES.items():
        if k in n or n in k:
            return v[style]
    return None


def _style_of_env(name):
    n = (name or "").strip().lower().replace(" ", "_")
    out = [s for s in ("flat", "voxel", "toon") if n in K.ALL_ENVS[s]]
    return out


# ------------------------------------------------------------------ analysing a piece of narration
def entities_in(text, limit=3):
    cands = []
    for idx, (name, rx, label) in enumerate(K.ENTITIES):
        m = rx.search(text)
        if m:
            cands.append((name, m.start(), idx))
    if len(cands) > 1:
        strong = [c for c in cands if c[0] not in NOISY]
        if strong:
            cands = strong + [c for c in cands if c[0] in NOISY and c[0] in ("explosion", "bolt", "fire", "wave") and len(strong) < 2]
    names = {}
    for n, p, i in cands:
        names.setdefault(n, (p, i))
    best = sorted(names.items(), key=lambda kv: kv[1][1])[:limit]       # most specific first
    best = sorted(best, key=lambda kv: kv[1][0])                        # then in reading order
    return [(n, K.ENTITY_LABEL.get(n, n.title()), p / max(1, len(text))) for n, (p, i) in best]


def features(text):
    nums = K.numbers(text)
    return dict(
        text=text, words=len(text.split()),
        ents=entities_in(text),
        nums=nums,
        mood=K.mood_of(text),
        hypo=bool(K.HYPO.search(text)), compare=bool(K.COMPARE.search(text)), scale=bool(K.SCALE.search(text)),
        process=len(K.PROCESS.findall(text)) >= 2, listy=bool(K.LISTY.search(text)) or text.count(",") >= 3,
        timey=bool(K.TIMEY.search(text)), hook=bool(K.HOOK.search(text.strip())),
        people=len(K.PEOPLE.findall(text)), blocky=bool(K.BLOCKY.search(text)),
    )


def _clauses(text, n=4):
    parts = [p.strip(" ,.;:") for p in re.split(r",|;|\band\b|\bthen\b|\bnext\b|\bfinally\b|\bfirst\b|\bsecond\b|\bthird\b", text) if len(p.strip()) > 8]
    out = []
    for p in parts:
        w = p.split()
        out.append(" ".join(w[:5]) + ("…" if len(w) > 5 else ""))
    return out[:n]


# ------------------------------------------------------------------ choosing style / place for a scene
def choose_style(rng, text, topic, cues, prev_styles, f):
    forced = resolve_style(cues.get("style") or cues.get("look"))
    if forced:
        return forced
    envcue = cues.get("env") or cues.get("environment") or cues.get("place")
    if envcue:
        s = _style_of_env(envcue)
        if len(s) == 1:
            return s[0]
    w = [x ** 0.7 for x in K.TOPIC_STYLE.get(topic or "generic", K.TOPIC_STYLE["generic"])]
    if f["blocky"]:
        w[1] *= 3.0
    if f["people"] >= 3 or f["hypo"]:
        w[2] *= 1.5
    if f["nums"] or f["compare"]:
        w[0] *= 1.25
    for i, s in enumerate(("flat", "voxel", "toon")):
        if prev_styles and prev_styles[-1] == s:
            w[i] *= 0.3
        if len(prev_styles) > 1 and prev_styles[-2] == s:
            w[i] *= 0.7
        if s not in prev_styles and len(prev_styles) >= 1:
            w[i] *= 2.2                                              # make sure every look gets used
        w[i] *= 0.85 + 0.3 * rng.random()
    return ("flat", "voxel", "toon")[max(range(3), key=lambda i: w[i])]


def choose_env(rng, topic, style, cues, prev_env, place=None):
    envcue = cues.get("env") or cues.get("environment") or cues.get("place")
    if envcue:
        e = resolve_env(envcue, style)
        if e:
            return e
    if place:                                   # the place the words are actually about wins over a random pick
        e = resolve_env(place, style)
        if e:
            return e
    opts = list(K.ENVS.get(topic or "generic", K.ENVS["generic"]).get(style) or K.ENVS["generic"][style])
    extra = [e for e in K.ALL_ENVS[style] if e not in opts]
    pool = opts + (extra if len(opts) < 2 else [])
    fresh = [e for e in pool if e != prev_env.get(style)]
    return rng.choice(fresh or pool)


def choose_pal(rng, topic, cues, env=None):
    p = cues.get("palette")
    from .flat_env import PALETTES
    if p and p in PALETTES:
        return p
    opts = K.PALETTES.get(topic or "generic", K.PALETTES["generic"])
    return rng.choice(opts)


def choose_tod(rng, env, topic, mood, cues):
    t = (cues.get("time") or "").lower()
    from .voxel import SKY
    if t in ("day", "dusk", "night", "storm"):
        return t
    if mood == "danger" and env in ("plains", "ocean", "city", "snow"):
        return "storm" if rng.random() > 0.35 else "dusk"
    return {"plains": rng.choice(["day", "day", "dusk", "night"]), "desert": rng.choice(["day", "dusk", "day"]), "snow": rng.choice(["cold", "cold", "dusk"]),
            "ocean": rng.choice(["day", "dusk", "day"]), "underwater": "deep", "volcano": "ember", "city": rng.choice(["dusk", "night", "day"]),
            "cave": "cave", "space": "space", "islands": rng.choice(["day", "dusk", "day"])}.get(env, "day")


# ------------------------------------------------------------------ shots
def split_shots(sentences, rng):
    """Group sentences into shots of ~1-2 sentences (a new picture roughly every 5-9 seconds)."""
    shots, cur, words = [], [], 0
    for i, s in enumerate(sentences):
        n = len(s["text"].split())
        if cur and (words + n > 30 or (words >= 14 and rng.random() > 0.35) or len(cur) >= 3):
            shots.append(cur); cur, words = [], 0
        cur.append(i); words += n
    if cur:
        if shots and words < 7:
            shots[-1] += cur
        else:
            shots.append(cur)
    return shots


def make_cam_2d(rng, idx, mood, template):
    kind = rng.choice(CAMERAS_2D)
    if mood in ("danger", "shock") and rng.random() > 0.5:
        kind = "shake"
    if template in ("hero", "stat", "question") and rng.random() > 0.4:
        kind = rng.choice(["push", "drift", "drift2"])
    if template in ("pair", "process", "timeline") and kind in ("push", "pull") and rng.random() > 0.5:
        kind = "drift"
    return dict(k=kind, amp=rng.uniform(0.6, 1.1), flip=rng.random() > 0.5)


def build_scene(idx, raw: RawScene, prev, rng, force_style=None):
    cues = dict(raw.cues)
    text = raw.text
    f_all = features(text)
    topic = (cues.get("topic") or K.topic_of(text) or (prev["topic"] if prev else "generic"))
    if force_style:
        cues.setdefault("style", force_style)
    style = choose_style(rng, text, topic, cues, prev["_styles"] if prev else [], f_all)
    envmem = prev["_env"] if prev else {}
    place, pscore = K.place_of(text)
    if pscore < 2:                                                  # no place named here: stay where the previous scene was
        place = prev.get("_place") if prev and (topic == prev["topic"] or topic in (None, "generic")) else None
    if style == "collage":
        env, pal = "paper", "day"
    else:
        env = choose_env(rng, topic, style, cues, envmem, place)
        pal = choose_pal(rng, K.PLACE_TOPIC.get(place, topic) if place else topic, cues, env)
    mood = cues.get("mood") if cues.get("mood") in K.MOODS or cues.get("mood") == "neutral" else f_all["mood"]
    tod = choose_tod(rng, env, topic, mood, cues) if style == "voxel" else None
    seed = int(cues["seed"]) if cues.get("seed", "").isdigit() else rng.randrange(1, 9999)
    sents = []
    for s in raw.sentences:
        sents.append(dict(text=s.text, spoken=s.spoken, mood=K.MOOD_VOICE.get(K.mood_of(s.text), "neutral"), pause=s.pause, inline=list(s.inline), para_end=s.para_end))
    scene = dict(idx=idx, heading=raw.heading, kind="body", style=style, env=env, pal=pal, tod=tod, seed=seed, topic=topic, mood=mood, cues=cues,
                 sentences=sents, text=text)
    scene["_styles"] = (prev["_styles"] if prev else []) + [style]
    scene["_place"] = place
    scene["_env"] = dict(envmem); scene["_env"][style] = env
    # transition into this scene
    tr = cues.get("transition")
    if not tr:
        tr = {"shock": "flash", "danger": rng.choice(["flash", "zoom", "slide"]), "wonder": rng.choice(["zoom", "fade", "iris"]), "calm": "fade"}.get(mood) or rng.choice(TRANSITIONS)
        if prev and prev.get("transition") == tr:
            tr = rng.choice([t for t in TRANSITIONS if t != tr])
    scene["transition"] = tr
    # shots
    if style == "collage":
        from . import collage_dir
        scene["shots"] = collage_dir.plan_shots(scene, rng, prev, first_overall=(idx == 0))
        scene["transition"] = "fade" if idx else "fade"
        scene["tr_len"] = 0.22
        scene["sfx"] = sound_cues(sents, rng, scene)
        return scene
    groups = split_shots(sents, rng)
    shots = []
    used_templates = []
    for gi, grp in enumerate(groups):
        txt = " ".join(sents[i]["text"] for i in grp)
        f = features(txt)
        if cues.get("show") and gi == 0 and not f["ents"]:
            f["ents"] = [(cues["show"].strip().lower().replace(" ", "_"), cues["show"].title(), 0.1)]
        if cues.get("entity") and gi == 0:
            f["ents"] = [(cues["entity"].strip().lower().replace(" ", "_"), cues["entity"].title(), 0.1)]
        shot = dict(sent=[grp[0], grp[-1]], text=txt, feat=dict(mood=f["mood"], ents=[e[0] for e in f["ents"]]))
        builder = {"flat": flat_shot, "toon": toon_shot, "voxel": voxel_shot}[style]
        builder(shot, f, scene, rng, gi, used_templates)
        used_templates.append(shot["template"])
        shots.append(shot)
    scene["shots"] = shots
    # sound effects from the words
    scene["sfx"] = sound_cues(sents, rng, scene)
    return scene


def sound_cues(sents, rng, scene):
    out, last = [], None
    for si, s in enumerate(sents):
        found = []
        for rx, name in K.SFX_RULES:
            m = rx.search(s["text"])
            if m:
                found.append((m.start() / max(1, len(s["text"])), name))
        found.sort()
        for frac, name in found[:2]:
            if name == last:
                continue
            out.append(dict(sent=si, frac=frac, name=name, gain=0.9))
            last = name
        for (pos, key, val) in s["inline"]:
            if key == "sfx":
                out.append(dict(sent=si, frac=pos / max(1, len(s["text"])), name=val.strip().lower().replace(" ", "_"), gain=1.0))
    return out


# ------------------------------------------------------------------ FLAT (Kurzgesagt-like diagrams)
def _px(ent):
    return {"galaxy": 420, "skyline": 520, "wave": 520, "mountain": 460, "volcano": 440, "whale": 400, "dino": 400, "earth_layers": 420}.get(ent, 330)


def _entry(rng, kind=None):
    return kind or rng.choice(["pop", "pop", "rise", "slide_l", "slide_r", "drop", "grow"])


def flat_shot(shot, f, scene, rng, gi, used):
    ents = f["ents"]
    nums = f["nums"]
    actors = []
    tpl = None
    big = [n for n in nums if n["kind"] in ("count", "percent", "temp", "year") and (n["big"] or n["kind"] != "count")]
    if f["hook"] and gi == 0 and f["words"] <= 22 and "question" not in used:
        tpl = "question"
    elif big and "stat" not in used[-2:]:
        tpl = "stat"
    elif f["timey"] and len(nums) >= 1 and "timeline" not in used[-2:]:
        tpl = "timeline"
    elif (f["compare"] or f["scale"]) and len(ents) >= 2:
        tpl = "pair"
    elif f["process"] and len(ents) >= 2:
        tpl = "process"
    elif f["listy"] and f["words"] >= 14 and "list" not in used[-2:]:
        tpl = "list"
    elif len(ents) >= 3 and "process" not in used[-1:]:
        tpl = "process"
    elif len(ents) >= 2:
        tpl = "pair"
    elif len(ents) == 1:
        tpl = "hero"
    else:
        tpl = "scenic"
    if used and tpl == used[-1] and tpl in ("hero", "scenic", "pair"):                      # no two identical looks in a row
        alt = {"hero": "orbit" if len(ents) else "scenic", "scenic": "question", "pair": "process" if len(ents) >= 2 else "hero"}[tpl]
        tpl = alt if (alt != "orbit" or ents) else tpl
    if tpl == "orbit":
        pass
    shot["template"] = tpl
    shot["cam"] = make_cam_2d(rng, gi, f["mood"], tpl)
    first = ents[0] if ents else None

    def ent(name, label, x, y, size, fin=0.0, motion="float", entry=None, lab=True, **kw):
        a = dict(k="entity", name=name, x=x, y=y, size=size, f_in=fin, motion=motion, entry=_entry(rng, entry), seed=rng.randrange(99), **kw)
        if lab:
            a["label"] = label
        actors.append(a)

    if tpl == "hero":
        n, lab, p = first
        ent(n, lab, 0.5, ENT_LIFT.get(n, 0.5), _px(n) * 1.15, 0.0, rng.choice(["float", "float", "spin_slow", "pulse"]), "pop")
        # a few small satellites related to the topic keep the frame alive
        for k in range(rng.choice([0, 2, 3])):
            actors.append(dict(k="spark", x=rng.uniform(0.12, 0.88), y=rng.uniform(0.15, 0.8), size=rng.uniform(10, 26), f_in=rng.uniform(0.0, 0.4), seed=rng.randrange(99)))
    elif tpl == "orbit":
        n, lab, p = first
        ent(n, lab, 0.5, 0.5, _px(n) * 0.9, 0.0, "float", "pop")
        for k in range(3):
            actors.append(dict(k="orbiter", around=(0.5, 0.5), radius=0.27 + 0.05 * k, size=26 + 10 * k, speed=0.6 - 0.15 * k, phase=rng.random() * 6.28, f_in=0.1 + 0.1 * k, seed=rng.randrange(99)))
    elif tpl == "pair":
        a, b = ents[0], ents[1]
        small, large = (200, 440) if f["scale"] else (330, 330)
        flip = rng.random() > 0.5
        ent(a[0], a[1], 0.27, 0.54, small if not flip else large, 0.0, "float", "slide_l")
        ent(b[0], b[1], 0.73, 0.54, large if not flip else small, max(0.25, b[2] * 0.8), "float", "slide_r")
        actors.append(dict(k="vs", text="VS" if (f["compare"] and not f["scale"]) else ("×" if f["scale"] else "&"), x=0.5, y=0.54, f_in=0.3))
    elif tpl == "process":
        items = ents[:4]
        n = len(items)
        for i, (nm, lab, p) in enumerate(items):
            x = (i + 0.5) / n
            ent(nm, lab, x, 0.5, 250 if n > 2 else 300, max(0.05, p * 0.85), "float", rng.choice(["pop", "rise"]))
            if i > 0:
                actors.append(dict(k="arrow", a=((i - 0.5) / n + 0.06, 0.5), b=(x - 0.06 - 0.0, 0.5), f_in=max(0.05, p * 0.85) + 0.02))
    elif tpl == "stat":
        nb = big[0]
        actors.append(dict(k="stat", display=nb["display"], sub=(first[1] if first else ""), x=0.5, y=0.46, f_in=max(0.05, nb["pos"] / max(1, len(f["text"])) * 0.8), kind=nb["kind"], value=nb["value"]))
        if first:
            ent(first[0], first[1], rng.choice([0.17, 0.83]), 0.62, 230, 0.0, "float", "pop", lab=False)
        if len(nums) > 1:
            actors.append(dict(k="stat_small", display=nums[1]["display"], x=0.5, y=0.78, f_in=0.55))
    elif tpl == "timeline":
        marks = []
        for nb in nums[:3]:
            marks.append(dict(text=nb["display"], pos=nb["pos"] / max(1, len(f["text"]))))
        actors.append(dict(k="timeline", marks=marks, y=0.64, f_in=0.0))
        if first:
            ent(first[0], first[1], 0.5, 0.32, 280, 0.05, "float", "pop")
    elif tpl == "list":
        items = _clauses(f["text"], 4)
        if len(items) < 2:
            items = [" ".join(f["text"].split()[:5]), " ".join(f["text"].split()[5:10])]
        for i, it in enumerate(items):
            actors.append(dict(k="card", text=it, x=0.5, y=0.3 + i * 0.14, w=0.62, color_i=i, f_in=0.08 + 0.78 * i / max(1, len(items))))
        if first:
            ent(first[0], first[1], 0.86, 0.5, 200, 0.0, "float", "pop", lab=False)
    elif tpl == "question":
        actors.append(dict(k="qmark", x=0.5, y=0.45, size=300, f_in=0.0))
        if first:
            ent(first[0], first[1], rng.choice([0.2, 0.8]), 0.55, 260, 0.2, "float", "pop", lab=False)
    else:   # scenic: no concrete thing to show -> the place itself + drifting shapes
        for k in range(rng.choice([4, 6, 8])):
            actors.append(dict(k="spark", x=rng.uniform(0.1, 0.9), y=rng.uniform(0.15, 0.85), size=rng.uniform(14, 40), f_in=rng.uniform(0, 0.6), seed=rng.randrange(99)))
        actors.append(dict(k="ringpulse", x=0.5, y=0.5, f_in=0.0))
    if f["mood"] in ("danger", "shock") and tpl in ("hero", "pair"):
        actors.append(dict(k="fx", name="flash", f_in=0.0))
    shot["actors"] = actors


# ------------------------------------------------------------------ TOON (simple characters)
def toon_shot(shot, f, scene, rng, gi, used):
    ents = f["ents"]
    role = K.ROLES.get(scene["topic"], "citizen")
    from .toon import ROLES as ALL_ROLES
    actors = []
    mood = f["mood"]
    acts = ACTION_BY_MOOD.get(mood, ACTION_BY_MOOD["neutral"])
    expr = EXPR_BY_MOOD.get(mood, "neutral")
    templates = ["solo", "duo", "walk", "crowd", "reaction", "pointing"]
    if f["people"] < 2:
        templates = ["solo", "walk", "pointing", "reaction"]
    if mood in ("danger", "shock"):
        templates = ["crowd", "reaction", "duo", "walk"]
    if f["hypo"] and gi == 0:
        templates = ["solo", "walk"]
    templates = [t for t in templates if t not in used[-2:]] or templates
    tpl = rng.choice(templates)
    shot["template"] = tpl
    shot["cam"] = make_cam_2d(rng, gi, mood, tpl)
    if tpl == "reaction":
        shot["cam"] = dict(k="push", amp=1.4, flip=rng.random() > 0.5)
    roles = [role] + [r for r in rng.sample(ALL_ROLES, 3) if r != role]
    seed0 = rng.randrange(40)
    sky = [e for e in ents if e[0] in SKY_THINGS]
    ground = [e for e in ents if e[0] not in SKY_THINGS]

    def char(r, x, act, scale, to=None, expr_=None, facing=1, fin=0.0, say=None):
        actors.append(dict(k="char", role=r, seed=seed0 + len(actors), x=x, scale=scale, action=act, to=to, expr=expr_ or expr, facing=facing, f_in=fin))

    if tpl == "solo":
        x = rng.choice([0.3, 0.38, 0.62, 0.7])
        char(role, x, rng.choice(acts), 1.0, expr_=expr, facing=1 if x < 0.5 else -1)
    elif tpl == "duo":
        char(roles[0], 0.3, rng.choice(acts), 0.95, facing=1)
        char(roles[1], 0.7, rng.choice(acts), 0.95, facing=-1, fin=0.1)
    elif tpl == "walk":
        d = 1 if rng.random() > 0.5 else -1
        char(role, 0.15 if d > 0 else 0.85, "walk" if mood != "danger" else "run", 0.95, to=0.85 if d > 0 else 0.15, facing=d)
        if rng.random() > 0.5:
            actors.append(dict(k="creature", kind=rng.choice(["cat", "dog", "bird", "blob_alien"]), x=0.1 if d > 0 else 0.9, to=0.7 if d > 0 else 0.3, scale=0.9, facing=d, seed=rng.randrange(9), f_in=0.1))
    elif tpl == "crowd":
        n = rng.choice([3, 4, 5])
        for i in range(n):
            x = 0.16 + 0.68 * (i + rng.uniform(-0.1, 0.1)) / max(1, n - 1)
            char(rng.choice(ALL_ROLES), x, rng.choice(acts[:3] if mood in ("danger", "shock") else acts), 0.62 + 0.14 * (i % 2), facing=1 if x < 0.5 else -1, fin=0.04 * i)
    elif tpl == "reaction":
        char(role, 0.5, rng.choice(acts), 1.55, expr_=expr)
    else:   # pointing at the thing being talked about
        x = rng.choice([0.25, 0.75])
        char(role, x, "point", 1.0, facing=1 if x < 0.5 else -1)
    # what the narration is about: shown big in the sky / on the ground, or as a hologram bubble
    for k, (nm, lab, p) in enumerate(ents[:2]):
        if tpl in ("reaction",) and k > 0:
            break
        if nm in SKY_THINGS:
            side = 0.72 if tpl in ("solo", "pointing") and actors and actors[0]["x"] < 0.5 else 0.28
            actors.append(dict(k="entity", name=nm, x=side if k == 0 else 1 - side, y=0.25 + 0.05 * k, size=220 if k == 0 else 150, f_in=max(0.0, p * 0.8), motion="float", entry="pop", label=lab, seed=rng.randrange(99)))
        else:
            side = 0.72 if tpl in ("solo", "pointing") and actors and actors[0]["x"] < 0.5 else 0.28
            actors.append(dict(k="entity", name=nm, x=side if k == 0 else 1 - side, y=0.3, size=210 if k == 0 else 140, f_in=max(0.0, p * 0.8), motion="float", entry="pop", label=lab, seed=rng.randrange(99), holo=True))
    if f["nums"] and f["nums"][0]["kind"] in ("count", "percent", "temp", "year"):
        nb = f["nums"][0]
        actors.append(dict(k="stat_small", display=nb["display"], x=0.5, y=0.14, f_in=max(0.05, nb["pos"] / max(1, len(f["text"])) * 0.8)))
    if mood in ("wonder", "funny") and rng.random() > 0.5:
        actors.append(dict(k="creature", kind=rng.choice(["blob_alien", "cat", "bird", "dino_toon", "dog"]), x=rng.choice([0.08, 0.92]), to=None, scale=0.8, facing=1, seed=rng.randrange(9), f_in=0.2))
    shot["actors"] = actors


# ------------------------------------------------------------------ VOXEL (blocky 3D worlds)
VOX_CAMS = ["orbit", "orbit_low", "dolly", "crane", "fly", "top", "pan_look", "chase"]


def voxel_shot(shot, f, scene, rng, gi, used):
    ents = f["ents"]
    mood = f["mood"]
    role = K.ROLES.get(scene["topic"], "citizen")
    from .toon import ROLES as ALL_ROLES
    cams = [c for c in VOX_CAMS if c not in used[-2:]]
    cam = rng.choice(cams or VOX_CAMS)
    if mood in ("danger", "shock") and rng.random() > 0.5:
        cam = "orbit_low"
    shot["template"] = cam
    shot["cam"] = dict(k=cam, r=rng.uniform(6.5, 11), h=rng.uniform(2.5, 6), a0=rng.uniform(0, 6.28), da=rng.uniform(0.5, 1.2) * (1 if rng.random() > 0.5 else -1), fov=rng.choice([56, 62, 70]), shake=1.0 if mood in ("danger", "shock") else 0.0)
    actors = []
    txt = f["text"].lower()
    n_people = 1 if f["people"] < 3 else rng.choice([1, 2, 3])
    for i in range(n_people):
        actors.append(dict(k="human", role=role if i == 0 else rng.choice(ALL_ROLES), seed=rng.randrange(40), slot=i, n=n_people, action=rng.choice(ACTION_BY_MOOD.get(mood, ACTION_BY_MOOD["neutral"])),
                           expr=EXPR_BY_MOOD.get(mood, "neutral"), walk=rng.random() > 0.6, f_in=0.0))
    if rng.random() > 0.5 or mood in ("wonder", "funny"):
        actors.append(dict(k="critter", kind=rng.choice(["cat", "dog", "blob_alien", "bird", "fish"]), seed=rng.randrange(9), slot=n_people + 1, f_in=0.1))
    events = []
    for k, (nm, lab, p) in enumerate(ents[:3]):
        if nm in ("volcano", "mountain", "skyline", "pyramid", "tree", "house") and scene["env"] in ("volcano", "city", "desert", "plains", "snow", "islands"):
            actors.append(dict(k="label", text=lab, f_in=max(0.0, p * 0.8)))
            continue
        actors.append(dict(k="prop", name=nm, label=lab, slot=k, f_in=max(0.0, p * 0.8), sky=nm in SKY_THINGS, seed=rng.randrange(9), size=1.0))
    if re.search(r"\b(explo\w+|impact|crash\w*|collid\w*|meteor\w*|asteroid\w*|comet|hit|hits|struck|smash\w*)\b", txt):
        events.append(dict(name="meteor", f=0.3 + rng.random() * 0.25))
    elif re.search(r"\b(rocket|launch\w*|lift.?off|blast off)\b", txt):
        events.append(dict(name="rocket", f=0.15))
    elif re.search(r"\b(erupt\w*|volcan\w+|lava)\b", txt) and scene["env"] == "volcano":
        events.append(dict(name="eruption", f=0.2))
    elif re.search(r"\b(lightning|thunder|storm)\b", txt):
        events.append(dict(name="lightning", f=0.3))
    if f["nums"]:
        nb = f["nums"][0]
        actors.append(dict(k="stat_small", display=nb["display"], x=0.5, y=0.14, f_in=max(0.05, nb["pos"] / max(1, len(f["text"])) * 0.8)))
    shot["events"] = events
    shot["actors"] = actors


# ------------------------------------------------------------------ the whole plan
def direct(title, raw_scenes, seed=0, force_style=None):
    base = _seed_of(title, " ".join(s.text for s in raw_scenes)[:400], seed)
    rng = random.Random(base)
    scenes, prev = [], None
    for i, raw in enumerate(raw_scenes):
        srng = random.Random(base * 31 + i * 7919)
        sc = build_scene(i, raw, prev, srng, force_style)
        scenes.append(sc)
        prev = sc
    plan = dict(title=title or "", seed=seed, scenes=scenes)
    # title + outro cards (no narration)
    first_topic = scenes[0]["topic"] if scenes else "generic"
    return plan


def summary(plan):
    """Human-readable breakdown for the web page / logs."""
    out = []
    for sc in plan["scenes"]:
        out.append(dict(i=sc["idx"], heading=sc["heading"] or " ".join(sc["text"].split()[:7]) + "…", style=K.STYLE_NAMES[sc["style"]], env=sc["env"], mood=sc["mood"],
                        topic=sc["topic"], shots=[s["template"] for s in sc["shots"]], words=len(sc["text"].split()), transition=sc["transition"]))
    return out
