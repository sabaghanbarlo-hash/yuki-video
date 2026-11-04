"""The scene builder for Collage pictures: a picture is drawn from the KEYWORDS of the sentence it illustrates.

    plan_pictures(plan)    -> fills shot["pics"] = [spec, ...] (one per picture of the shot). A spec is plain data
                              (setting, props, people, camera), so every render process draws exactly the same picture.

How a picture is chosen
  * what the sentence is about -> things (props.py: bed, coffee, chart ... and entities.py: brain, planet, phone ...)
  * where it happens            -> one of the cartoon settings (room, street, forest, lab, beach, space ...)
  * who is in it                -> a simple cartoon person doing what the verbs say (sleeping, running, thinking, pointing ...)
  * how it feels                -> the person's face and the camera move
  * never the same twice        -> the whole video is planned together: a setting, a main thing or a layout that was just used
                                   is avoided, and people change their looks.
"""
import random, re
from . import knowledge as K, props as PR

R = lambda p: re.compile(p, re.I)

# things that are too generic to be the subject of a picture on their own
GENERIC = {"person", "crowd", "eye", "gear", "scale", "water_drop", "clock", "bolt", "battery", "skull", "star"}
SKY = {"sun", "moon", "planet", "ringed", "star", "galaxy", "blackhole", "comet", "asteroid", "rocket", "satellite", "ufo", "plane", "cloud", "earth", "explosion", "stormcloud"}

PEOPLE = R(r"\b(you|your|we|us|i|me|my|he|she|they|him|her|them|people|person|man|woman|boy|girl|kids?|child\w*|friends?|students?|workers?|boss|someone|everyone|humans?|"
           r"mother|father|parents?|teacher|doctor|patient|driver|pilot|athlete|team|crowd|family|neighbou?rs?|strangers?|customers?|audience)\b")
ROLE_WORDS = [(R(r"\b(kids?|child\w*|boy|girl|toddler\w*|baby|babies)\b"), "kid"), (R(r"\b(teacher|school|class\w*|student\w*|lesson\w*)\b"), "teacher"),
              (R(r"\b(scientists?|research\w*|experiment\w*|doctors?|patients?|brain|body|study|studies|lab)\b"), "scientist"),
              (R(r"\b(robots?|ai|machines?|automat\w+)\b"), "robot"), (R(r"\b(astronaut\w*|space|orbit|moon|planet\w*)\b"), "astronaut"),
              (R(r"\b(div(er|ing)|ocean|sea|underwater|coral)\b"), "diver"), (R(r"\b(engineer\w*|build\w*|code|coding|software|tech\w*|computer\w*)\b"), "engineer"),
              (R(r"\b(explor\w+|hik\w+|mountain\w*|desert|jungle|forest|travel\w*)\b"), "explorer")]

# what a person is doing, from the verbs
ACTION_RULES = [
    (R(r"\b(sleep\w*|asleep|nap\w*|tired|exhaust\w*|yawn\w*|bored|boring|lazy|rest\w*|lying)\b"), "sit"),
    (R(r"\b(run\w*|rush\w*|hurry\w*|sprint\w*|chase\w*|escape\w*|flee\w*)\b"), "run"),
    (R(r"\b(walk\w*|go(es|ing)?|went|travel\w*|move\w*|commut\w+|head(ing)? (to|out)|arriv\w+)\b"), "walk"),
    (R(r"\b(scare\w*|afraid|panic\w*|danger\w*|terrif\w+|nightmare\w*|scream\w*|fear\w*|anxi\w+|stress\w*|worr\w+|overwhelm\w*)\b"), "panic"),
    (R(r"\b(think\w*|wonder\w*|why|how|what|imagin\w+|idea|remember\w*|decide\w*|consider\w*|question\w*|mind|dream\w*|guess\w*|confus\w+)\b"), "think"),
    (R(r"\b(look\w*|see|seen|watch\w*|notice\w*|stare\w*|search\w*|spot\w*|discover\w*|sky|above|up)\b"), "look_up"),
    (R(r"\b(win|won|winning|success\w*|happy|joy\w*|celebrat\w*|love\w*|great|amazing|best|proud|fun|enjoy\w*|cheer\w*|reward\w*|achiev\w+)\b"), "cheer"),
    (R(r"\b(jump\w*|leap\w*|bounce\w*|rise|rose|boost\w*|launch\w*|excit\w+|energy|energi\w+|wake\w*|woke)\b"), "jump"),
    (R(r"\b(fall\w*|fell|drop\w*|trip\w*|slip\w*|crash\w*|collapse\w*|lose|lost|fail\w*)\b"), "fall"),
    (R(r"\b(float\w*|drift\w*|weightless|space|zero gravity)\b"), "float"),
    (R(r"\b(hello|hi|hey|welcome|greet\w*|goodbye|bye|meet\w*)\b"), "wave"),
    (R(r"\b(maybe|perhaps|might|unclear|unknown|not sure|depends|who knows|whatever|ignor\w+|don.t (know|care)|nobody)\b"), "shrug"),
    (R(r"\b(this|that|here|there|point\w*|show\w*|example\w*|called|named|known as|means?|is a|are)\b"), "point"),
    (R(r"\b(push\w*|pull\w*|carry\w*|lift\w*|work\w*|build\w*|make\w*|made|fix\w*|force\w*)\b"), "push"),
    (R(r"\b(talk\w*|say\w*|said|tell\w*|told|speak\w*|ask\w*|answer\w*|explain\w*|argue\w*|chat\w*|call\w*|message\w*)\b"), "talk"),
]
EXPR = {"danger": "worried", "wonder": "happy", "funny": "happy", "calm": "neutral", "shock": "shocked", "curious": "curious", "neutral": "neutral"}
EXPR_WORDS = [(R(r"\b(angry|furious|hate\w*|annoy\w*|rage)\b"), "angry"), (R(r"\b(scared|afraid|worr\w+|anxi\w+|stress\w*|nervous|terrif\w+|panic\w*|danger\w*)\b"), "worried"),
              (R(r"\b(wow|suddenly|shock\w*|unbelievable|surpris\w+|impossible|incredible)\b"), "shocked"), (R(r"\b(why|how|what|wonder\w*|curious|mystery|strange|weird)\b"), "curious"),
              (R(r"\b(happy|love\w*|great|amazing|win|won|joy\w*|fun|celebrat\w*|good|better|best|enjoy\w*)\b"), "happy")]

# where it takes place (toon settings): keywords -> setting. First strong match wins; otherwise the topic's settings.
SETTING_RULES = [
    ("room", R(r"\b(bed\w*|sleep\w*|pillow\w*|home|house|apartment|kitchen|living room|couch|sofa|tv|screen|phone|laptop|desk|tired|morning|night|insomnia|netflix|binge|scroll\w*|alone)\b")),
    ("street", R(r"\b(street|road|traffic|commut\w+|city|town|downtown|cars?|bus|train|shop\w*|store|market|crowd\w*|people)\b")),
    ("rooftop", R(r"\b(roof\w*|skyline|skyscraper\w*|tower|night city|view)\b")),
    ("lab", R(r"\b(lab\w*|experiment\w*|scientist\w*|research\w*|brain|body|cells?|chemical\w*|test\w*|data|study|studies|science|medicine|doctor\w*|hospital)\b")),
    ("stage", R(r"\b(stage|perform\w*|audience|present\w*|speech|talk show|show|concert|music|theater|theatre|applause|fame|famous)\b")),
    ("forest", R(r"\b(forest|tree\w*|jungle|woods|nature|plant\w*|garden|camp\w*|hik\w+|animals?)\b")),
    ("hills", R(r"\b(hill\w*|field\w*|farm\w*|countryside|outdoors?|mountain\w*|valley|walk in the park|park)\b")),
    ("beach", R(r"\b(beach\w*|sea|ocean|waves?|island|vacation|holiday|summer|sun\w*|swim\w*|relax\w*)\b")),
    ("underwater", R(r"\b(underwater|deep sea|coral|reef|dive\w*|fish|whale\w*|shark\w*|submarine)\b")),
    ("space", R(r"\b(space|planet\w*|galax\w+|star\w*|moon|orbit|astronaut\w*|universe|cosmic|rocket\w*|mars|solar)\b")),
    ("desert", R(r"\b(desert|sand|dunes?|dry|drought|heat wave|camel)\b")),
    ("snow", R(r"\b(snow\w*|ice|cold|winter|frozen|freez\w+|arctic|blizzard)\b")),
    ("cave", R(r"\b(cave\w*|underground|mine\w*|dark|darkness|volcano|lava|deep down|buried)\b")),
]
ALL_SETTINGS = ["room", "street", "hills", "beach", "space", "desert", "snow", "stage", "underwater", "rooftop", "cave", "lab", "forest"]
EVERYDAY = ["room", "street", "hills", "forest", "rooftop", "lab", "stage", "beach"]       # for sentences that are about no place in particular

SKIP_ENT_WORDS = R(r"^(you|your|i|we|they|it|this|that|there|here|then|so|and|but|or|if|when|what|how|why|who|which|the|a|an)$")


# ------------------------------------------------------------------ reading the sentence
def things_in(text):
    """-> list of (name, label, position) in reading order; everyday props first, then the general entities."""
    found = []
    for nm, rx, lab in PR.PROPS:
        m = rx.search(text)
        if m:
            found.append((nm, lab, m.start(), 2))
    for nm, rx, lab in K.ENTITIES:
        m = rx.search(text)
        if m and nm not in GENERIC:
            found.append((nm, lab, m.start(), 1))
    # explicit, concrete mentions beat soft ones; keep the order of the sentence among equals
    seen, out = set(), []
    for nm, lab, pos, w in sorted(found, key=lambda x: (-x[3], x[2])):
        if nm not in seen:
            seen.add(nm); out.append((nm, lab, pos))
    return out


def person_action(text, mood, rng):
    for rx, act in ACTION_RULES:
        if rx.search(text):
            return act
    return rng.choice({"danger": ["panic", "run"], "wonder": ["look_up", "cheer"], "funny": ["shrug", "jump"], "shock": ["panic", "jump"]}.get(mood, ["talk", "idle", "point", "walk"]))


def person_expr(text, mood):
    for rx, e in EXPR_WORDS:
        if rx.search(text):
            return e
    return EXPR.get(mood, "neutral")


def person_role(text, topic):
    for rx, r in ROLE_WORDS:
        if rx.search(text):
            return r
    return K.ROLES.get(topic or "generic", "citizen")


def setting_for(text, topic, use, rng):
    cands = []
    for env, rx in SETTING_RULES:
        n = len(rx.findall(text))
        if n:
            cands.append((n, env))
    cands.sort(reverse=True)
    place, ps = K.place_of(text)
    if place and ps >= 2:
        from . import director as D
        e = D.resolve_env(place, "toon")
        if e:
            cands.insert(0, (9, e))
    order = [e for _, e in cands]
    if not order:                                                               # about no particular place: rotate the everyday ones
        order = list(EVERYDAY)
    # the least recently used of the fitting settings wins (the first one when none was used)
    best = min(order[:3], key=lambda e: (use["env"].get(e, 0), order.index(e)))
    if use["last_env"] == best and len(order) > 1:
        alt = [e for e in order if e != best]
        best = alt[0] if alt else best
    return best


# ------------------------------------------------------------------ layouts
def layout(kind, things, person, rng, side):
    """-> actors (dicts for Stage2D). x/y are fractions of the 1280x720 frame; the picture is cropped around its middle, so
    everything stays between 0.28 and 0.72."""
    A = []
    big = things[0][0] if things else None

    def ent(nm, lab, x, y, size, fin=0.0, holo=False, entry="pop", motion="float"):
        if nm in SKY and y > 0.3 and not holo:
            y = min(y, 0.3)
        A.append(dict(k="entity", name=nm, x=x, y=y, size=size, f_in=fin, motion=motion, entry=entry, label=None, seed=rng.randrange(99), holo=holo))

    def char(role, x, act, scale, expr, facing, fin=0.0, to=None):
        A.append(dict(k="char", role=role, seed=rng.randrange(60), x=x, scale=scale, action=act, to=to, expr=expr, facing=facing, f_in=fin))

    px = 0.36 if side == "L" else 0.64
    ex = 0.66 if side == "L" else 0.34
    f = 1 if side == "L" else -1
    if kind == "hero_only":                                  # one big thing
        ent(big, things[0][1], 0.5, 0.45, 340, entry=rng.choice(["pop", "rise", "grow"]))
        for i, (nm, lab, _) in enumerate(things[1:3]):
            ent(nm, lab, 0.3 if i == 0 else 0.7, 0.2, 120, fin=0.25 + 0.15 * i, holo=True)
    elif kind == "person_thing":                             # a person next to the thing
        char(person["role"], px, person["act"], 0.95, person["expr"], f)
        ent(big, things[0][1], ex, 0.42, 250, fin=0.12, entry=rng.choice(["pop", "slide_r" if side == "L" else "slide_l", "drop"]))
        if len(things) > 1:
            ent(things[1][0], things[1][1], ex, 0.14, 120, fin=0.4, holo=True)
    elif kind == "thought":                                  # a big person thinking/reacting, the thing in a bubble
        char(person["role"], 0.42 if side == "L" else 0.58, person["act"], 1.5, person["expr"], f)
        ent(big, things[0][1], 0.64 if side == "L" else 0.36, 0.3, 230, fin=0.2, holo=True)
    elif kind == "row":                                      # several things side by side
        n = min(3, len(things))
        xs = {1: [0.5], 2: [0.37, 0.63], 3: [0.3, 0.5, 0.7]}[n]
        for i, x in enumerate(xs):
            ent(things[i][0], things[i][1], x, 0.45, 200 if n < 3 else 150, fin=0.12 * i, entry=rng.choice(["pop", "rise"]))
    elif kind == "walk":                                     # a person crossing the picture, the thing in the background
        d = 1 if side == "L" else -1
        if big:
            ent(big, things[0][1], 0.5, 0.36, 230, holo=big not in SKY, entry="grow")
        char(person["role"], 0.3 if d > 0 else 0.7, "walk" if person["act"] not in ("run", "panic") else person["act"], 0.9, person["expr"], d, to=0.7 if d > 0 else 0.3)
    elif kind == "duo":                                      # two people talking, the thing between/above them
        char(person["role"], 0.33, person["act"], 0.85, person["expr"], 1)
        char(person["role2"], 0.67, "talk" if person["act"] != "talk" else "think", 0.85, "curious", -1, fin=0.1)
        if big:
            ent(big, things[0][1], 0.5, 0.2, 150, fin=0.3, holo=True)
    elif kind == "crowd":
        n = rng.choice([3, 4, 5])
        for i in range(n):
            x = 0.3 + 0.4 * i / max(1, n - 1)
            char(rng.choice(["citizen", "kid", "teacher", "engineer", "scientist"]), x, rng.choice(["talk", "walk", "cheer", "shrug", "idle", "point"]), 0.62 + 0.12 * (i % 2),
                 person["expr"], 1 if x < 0.5 else -1, fin=0.05 * i)
        if big:
            ent(big, things[0][1], 0.5, 0.17, 130, fin=0.3, holo=True)
    elif kind == "person_big":                               # just a person, big, no props
        char(person["role"], 0.5, person["act"], 1.5, person["expr"], f)
    return A


def pick_layout(things, has_people, mood, use, rng):
    opts = []
    if things:
        opts += [("hero_only", 3), ("row", 3 if len(things) >= 2 else 0), ("person_thing", 4 if has_people or True else 2), ("thought", 3), ("walk", 2)]
        if has_people:
            opts += [("duo", 2), ("crowd", 1)]
    else:
        opts += [("person_big", 3), ("walk", 3), ("duo", 2), ("crowd", 2)]
    opts = [(k, w) for k, w in opts if w > 0]
    # not the layout that was just used, and fewer of the ones already used a lot
    ws = []
    for k, w in opts:
        ws.append(max(0.15, w * (0.15 if use["last_layout"] == k else 1.0) / (1 + 0.5 * use["layout"].get(k, 0))))
    r = rng.random() * sum(ws)
    acc = 0.0
    for (k, _), w in zip(opts, ws):
        acc += w
        if r <= acc:
            return k
    return opts[0][0]


# ------------------------------------------------------------------ the whole video
def pic_spec(text, topic, mood, use, rng, seed):
    th = things_in(text)
    # do not put the same main thing in two neighbouring pictures
    if th and use["last_big"] == th[0][0] and len(th) > 1:
        th = th[1:] + th[:1]
    elif th and use["last_big"] == th[0][0] and rng.random() < 0.6:
        th = []
    has_people = bool(PEOPLE.search(text))
    side = rng.choice(["L", "R"])
    if use["last_side"] == side and rng.random() < 0.7:
        side = "R" if side == "L" else "L"
    kind = pick_layout(th, has_people, mood, use, rng)
    env = setting_for(text, topic, use, rng)
    role = person_role(text, topic)
    role2 = rng.choice([r for r in ("citizen", "kid", "teacher", "engineer", "scientist") if r != role])
    person = dict(role=role, role2=role2, act=person_action(text, mood, rng), expr=person_expr(text, mood))
    actors = layout(kind, th, person, rng, side)
    cam = rng.choice([dict(k="push", amp=1.0), dict(k="drift", amp=0.8), dict(k="pan_l", amp=0.8), dict(k="pan_r", amp=0.8), dict(k="rise", amp=0.7), dict(k="pull", amp=0.9)])
    cam["flip"] = rng.random() < 0.5
    pal = rng.choice(["day", "day", "day", "dusk"]) if env not in ("underwater", "space", "cave") else "night"
    use["env"][env] = use["env"].get(env, 0) + 1
    use["layout"][kind] = use["layout"].get(kind, 0) + 1
    use["last_env"], use["last_layout"], use["last_side"] = env, kind, side
    use["last_big"] = th[0][0] if th else None
    return dict(style="toon", env=env, pal=pal, cam=cam, actors=actors, seed=seed, topic=topic or "generic", mood=mood, layout=kind,
                keys=[t[0] for t in th[:3]])


def plan_pictures(plan, only_missing=True):
    """Give every collage picture that has no real image a drawn scene built from its sentence's keywords."""
    from . import director as D
    use = dict(env={}, layout={}, last_env=None, last_layout=None, last_side=None, last_big=None)
    n = 0
    for sc in plan["scenes"]:
        if sc.get("style") != "collage":
            continue
        for sh in sc["shots"]:
            qs = sh.get("queries") or []
            media = sh.get("media") or []
            sh["pics"] = []
            for qi in range(len(qs)):
                if only_missing and qi < len(media) and media[qi]:
                    sh["pics"].append(None)
                    continue
                if sh.get("kind") not in ("media", "text"):
                    sh["pics"].append(None)
                    continue
                txt = (sh.get("text") or "") if qi == 0 else qs[qi]
                txt = txt or qs[qi]
                rng = random.Random((sh.get("seed", 1) * 1009 + qi * 131 + n * 7) & 0xFFFFFF)
                f = D.features(txt)
                spec = pic_spec(txt, K.topic_of(txt) or sc.get("topic"), f["mood"], use, rng, (sh.get("seed", 1) + qi * 17 + n) % 100000)
                sh["pics"].append(spec)
                n += 1
    plan["pictures_drawn"] = n
    return plan
