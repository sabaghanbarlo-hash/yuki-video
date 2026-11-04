"""The picture for one beat of a collage video, drawn by the lab from the beat's own words.

For every beat it reads the keywords (things, places, verbs, feelings, numbers) and composes a cartoon scene:
    * the PLACE the words are about (bedroom for sleep, office for work, kitchen, gym, classroom, park, street, beach, space ...)
    * the THINGS they name (bed, phone, calendar, target, brain, planet ... ~90 drawings), shown big
    * simple cartoon PEOPLE doing what the line says (running, thinking, pointing, panicking, cheering, sitting ...), feeling what it feels
Nothing is picked at random without a reason, and a memory of the last scenes makes consecutive pictures differ: the same place, the
same main object or the same layout is not used twice in a row unless the words really are about it.
plan_picture() returns a plain dict (a "recipe"), so rendering later is stateless and works in parallel.
"""
import re
from . import knowledge as K
from . import props                       # noqa: F401  (registers the extra drawings)

R = lambda p: re.compile(p, re.I)

# ------------------------------------------------------------------ places
PLACE_WORDS = [   # (regex, toon env)   daily-life places first: they are what self-improvement scripts are about
    (R(r"\b(bed|bedroom|sleep\w*|asleep|insomnia|pillow|night|midnight|tired|exhaust\w+|nap\w*|dream\w*|wake|waking|awake|morning)\b"), "bedroom"),
    (R(r"\b(office|desk|laptop|email\w*|meeting\w*|boss|colleagues?|deadline\w*|work(ing)?|job|career|procrastinat\w+|coding|code|project\w*|client\w*|freelanc\w+|productiv\w+)\b"), "office"),
    (R(r"\b(kitchen|cook\w*|food|eat\w*|meal\w*|breakfast|lunch|dinner|recipe\w*|snack\w*|sugar|diet|hungry|coffee|fridge|fruit\w*|vegetable\w*)\b"), "kitchen"),
    (R(r"\b(gym|workout\w*|exercis\w+|muscle\w*|lift\w*|fitness|training|push.?ups?|run(ning)?|stronger|weights?)\b"), "gym"),
    (R(r"\b(school|class(room)?|study\w*|student\w*|exam\w*|homework|teacher\w*|lesson\w*|learn\w*|university|college|lecture|professor\w*|education|textbook\w*)\b"), "classroom"),
    (R(r"\b(park|outside|outdoors?|walk\w*|fresh air|bench|nature|friends?|picnic|sunshine|garden|stroll\w*|hik\w+)\b"), "park"),
    (R(r"\b(street|road|traffic|commut\w+|bus|train|crowd\w*|downtown|neighbou?rhood|shop\w*|store|market)\b"), "street"),
    (R(r"\b(home|house|room|living room|couch|sofa|alone|lonely|family|parents?|kids?|children)\b"), "room"),
    (R(r"\b(rooftop|skyline|city lights|high up|view)\b"), "rooftop"),
    (R(r"\b(lab|experiment\w*|scientists?|research\w*|test\w*|chemical\w*|microscop\w+|cells?|bacteria|dna|biology|chemistry|physics)\b"), "lab"),
    (R(r"\b(forest|woods|trees?|jungle|wild\w*|animals?|hunt\w*|ancestors?)\b"), "forest"),
    (R(r"\b(hills?|countryside|field\w*|farm\w*|village|path|journey|mountain\w*|valley)\b"), "hills"),
    (R(r"\b(beach|ocean|sea|waves?|shore|vacation|holiday|island)\b"), "beach"),
    (R(r"\b(desert|sand|dunes?|hot|heat|thirst\w*)\b"), "desert"),
    (R(r"\b(snow\w*|ice|frozen|winter|cold|arctic|freez\w+)\b"), "snow"),
    (R(r"\b(underwater|deep sea|dive\w*|reef|submarine)\b"), "underwater"),
    (R(r"\b(space|planets?|stars?|galax\w+|universe|cosmos|astronaut\w*|orbit|moon|solar system|rocket\w*)\b"), "space"),
    (R(r"\b(cave\w*|underground|tunnel|dark|lava|volcan\w+)\b"), "cave"),
    (R(r"\b(stage|audience|perform\w*|speech|presentation|public speaking|spotlight|applause|concert|show)\b"), "stage"),
]
PLACE_ENV_SPECIFIC = {"galaxy": "space", "solar_system": "space", "orbit": "space", "space": "space", "underwater": "underwater", "deep_sea": "underwater"}
FALLBACK_ENVS = ["street", "room", "park", "hills", "office", "rooftop", "forest", "kitchen", "classroom", "beach", "stage", "gym", "bedroom", "lab"]
TOPIC_ENV = {"space": "space", "earth": "hills", "ocean": "beach", "weather": "hills", "volcano": "cave", "ice": "snow", "desert": "desert", "nature": "forest",
             "body": "gym", "brain": "room", "micro": "lab", "physics": "lab", "tech": "office", "city": "street", "history": "street", "disaster": "street", "food": "kitchen"}

# ------------------------------------------------------------------ what the people do
ACTION_WORDS = [   # (regex, toon action)
    (R(r"\b(sleep\w*|asleep|tired|exhaust\w+|collapse\w*|lie|lying|rest\w*|nap\w*|bed|slump\w*)\b"), "sit"),
    (R(r"\b(scroll\w*|stare\w*|staring|binge\w*|watch\w*|sit\w*|sat|read\w*|study\w*|work(ing)?|type|typing|wait\w*)\b"), "sit"),
    (R(r"\b(run\w*|rush\w*|hurr\w+|race\w*|chase\w*|flee\w*|escape\w*|sprint\w*|late)\b"), "run"),
    (R(r"\b(walk\w*|go(ing)?|travel\w*|journey|head(ed)? to|stroll\w*|march\w*|move on|step)\b"), "walk"),
    (R(r"\b(jump\w*|leap\w*|bounce\w*|hop\w*|excit\w+|thrill\w*|energ\w+)\b"), "jump"),
    (R(r"\b(think\w*|wonder\w*|decid\w+|choose|choice\w*|imagine|consider\w*|ponder\w*|question\w*|doubt\w*|overthink\w*|confus\w+|why|how come)\b"), "think"),
    (R(r"\b(point\w*|show\w*|this is|that is|here is|look at|notice|see this|example|for instance|means)\b"), "point"),
    (R(r"\b(say|says|said|talk\w*|tell\w*|speak\w*|ask\w*|explain\w*|argu\w+|conversation\w*|chat\w*|shout\w*)\b"), "talk"),
    (R(r"\b(celebrat\w+|win\w*|won|succe\w+|achiev\w+|proud|victory|finally|best|great|yes)\b"), "cheer"),
    (R(r"\b(panic\w*|scar\w+|afraid|fear\w*|anxi\w+|stress\w*|overwhelm\w*|terrif\w+|nervous|danger\w*|worry\w*|worried|dread\w*)\b"), "panic"),
    (R(r"\b(maybe|perhaps|might|not sure|who knows|whatever|doesn.t matter|shrug\w*|idk|depends)\b"), "shrug"),
    (R(r"\b(look up|stars?|sky|above|future|dream\w*|hope\w*|wish\w*|imagine|goal\w*|vision)\b"), "look_up"),
    (R(r"\b(push\w*|pull\w*|struggl\w+|fight\w*|resist\w*|force\w*|carry|carrying|heavy|burden\w*|hard|difficult|grind\w*)\b"), "push"),
    (R(r"\b(fall\w*|fell|fail\w*|drop\w*|crash\w*|lose|lost|collapse\w*|slip\w*|mistake\w*)\b"), "fall"),
    (R(r"\b(wave|hello|hi|hey|welcome|goodbye|bye)\b"), "wave"),
    (R(r"\b(float\w*|drift\w*|calm|relax\w*|peace\w*|breathe|breathing|meditat\w+|free)\b"), "float"),
]
FACE_TO_EXPR = {
    "happy": "happy", "smile": "happy", "excited": "happy", "laughing": "happy", "starry": "happy", "lovestruck": "happy", "proud": "happy", "inspired": "happy",
    "cheeky": "happy", "dreamy": "happy", "yum": "happy", "serene": "happy",
    "worried": "worried", "nervous": "worried", "terrified": "worried", "sad": "worried", "crying": "worried", "teary": "worried", "pained": "worried",
    "awkward": "worried", "embarrassed": "worried", "sleepy": "neutral", "bored": "neutral", "deadpan": "neutral",
    "shocked": "shocked", "gasp": "shocked", "angry": "angry", "grumpy": "angry", "determined": "angry",
    "curious": "curious", "confused": "curious", "dizzy": "curious", "scheming": "curious", "smug": "neutral", "creepy": "worried",
}
ACTION_BY_EXPR = {"happy": ["cheer", "jump", "talk", "wave"], "worried": ["panic", "think", "shrug"], "shocked": ["panic", "fall", "look_up"], "angry": ["push", "point", "talk"],
                  "curious": ["think", "look_up", "point"], "neutral": ["talk", "idle", "shrug", "point"]}

ROLE_WORDS = [(R(r"\b(astronaut\w*|space|orbit|moon|planets?)\b"), "astronaut"), (R(r"\b(teach\w+|class(room)?|lesson\w*|school|professor\w*|lecture)\b"), "teacher"),
              (R(r"\b(kids?|child\w*|boy|girl|young|baby|toddler)\b"), "kid"), (R(r"\b(scientists?|research\w*|experiment\w*|lab)\b"), "scientist"),
              (R(r"\b(engineer\w*|code|coding|software|robots?|tech\w*|computer\w*|build\w*)\b"), "engineer"), (R(r"\b(dive\w*|ocean|underwater|sea|reef)\b"), "diver"),
              (R(r"\b(explor\w+|hik\w+|mountain\w*|jungle|desert|journey|adventur\w+|climb\w*)\b"), "explorer")]
PEOPLE_MANY = R(r"\b(people|everyone|crowd\w*|society|humans?|humanity|millions|billions|friends|family|others|colleagues|students|they|everybody|we all)\b")
PEOPLE_TWO = R(r"\b(friend|partner|couple|both|two|you and|he and|she and|someone and|talk to|argue|compare|versus|vs|than)\b")
SKY = {"sun", "moon", "planet", "ringed", "star", "galaxy", "blackhole", "comet", "asteroid", "rocket", "satellite", "ufo", "plane", "cloud", "bolt", "earth", "explosion"}
BIG_ONLY = {"skyline", "mountain", "volcano", "wave", "pyramid", "whale", "dino", "galaxy", "earth_layers"}


def _words(t):
    return len(t.split())


def _pick_unused(rng, options, recent, k=3):
    fresh = [o for o in options if o not in recent[-k:]]
    return rng.choice(fresh or options)


def new_memory():
    return dict(envs=[], ents=[], tpls=[], roles=[], acts=[], n=0)


def choose_env(txt, topic, rng, mem, f):
    place, ps = K.place_of(txt)
    if place and ps >= 2 and place in PLACE_ENV_SPECIFIC:
        return PLACE_ENV_SPECIFIC[place]
    hits = []
    for rx, env in PLACE_WORDS:
        n = len(rx.findall(txt))
        if n:
            hits.append((n, env))
    hits.sort(key=lambda h: -h[0])
    cands = [e for _, e in hits]
    fresh = [e for e in cands if e not in mem["envs"][-2:]]
    if fresh:
        return fresh[0]
    if cands:                                                        # the words really are about this place: stay, but the layout will differ
        return cands[0]
    t_env = TOPIC_ENV.get(topic)
    pool = ([t_env] if t_env else []) + FALLBACK_ENVS
    fresh = [e for e in pool if e not in mem["envs"][-4:]]
    return (fresh or pool)[0] if t_env and t_env in fresh else rng.choice(fresh or pool)


def choose_action(txt, expr, rng, mem):
    cands = []
    for rx, act in ACTION_WORDS:
        if rx.search(txt):
            cands.append(act)
    fresh = [a for a in cands if a not in mem["acts"][-1:]]
    if fresh or cands:
        return (fresh or cands)[0]
    return rng.choice([a for a in ACTION_BY_EXPR.get(expr, ACTION_BY_EXPR["neutral"]) if a not in mem["acts"][-2:]] or ACTION_BY_EXPR["neutral"])


ENV_ROLES = {"bedroom": ["citizen", "kid"], "office": ["citizen", "engineer"], "kitchen": ["citizen", "kid"], "gym": ["citizen"], "park": ["citizen", "kid", "explorer"],
             "street": ["citizen", "kid"], "room": ["citizen", "kid"], "rooftop": ["citizen"], "classroom": ["teacher", "kid", "citizen"], "lab": ["scientist", "engineer"],
             "space": ["astronaut"], "underwater": ["diver"], "forest": ["explorer", "citizen"], "hills": ["explorer", "citizen", "kid"], "beach": ["citizen", "kid", "explorer"],
             "desert": ["explorer"], "snow": ["explorer"], "cave": ["explorer", "geologist"], "stage": ["citizen", "teacher"]}


def choose_role(txt, rng, mem, topic, env="street"):
    for rx, role in ROLE_WORDS:
        if rx.search(txt) and role in (ENV_ROLES.get(env) or [role]) + ["astronaut", "diver"]:
            return role
    pool = ENV_ROLES.get(env) or ["citizen", "kid"]
    return _pick_unused(rng, pool, mem["roles"], 1)


def plan_picture(txt, seed, mem, topic="generic", face="neutral", qi=0, kind="media"):
    """-> recipe dict for one picture. `mem` (from new_memory()) is updated so the next picture differs."""
    import random
    from .director import features, make_cam_2d
    rng = random.Random(seed * 31 + qi * 7 + mem["n"])
    f = features(txt)
    ents = [e for e in f["ents"]]
    mood = f["mood"]
    expr = FACE_TO_EXPR.get(face, "neutral")
    env = choose_env(txt, topic, rng, mem, f)
    action = choose_action(txt, expr, rng, mem)
    role = choose_role(txt, rng, mem, topic, env)

    # ---- which things to show: the beat's own keywords, a different one than last time when there is a choice
    named = [e for e in ents if e[0] not in ("person", "crowd")]
    fresh = [e for e in named if e[0] not in mem["ents"][-2:]]
    shown = (fresh or named)[:2]
    many = bool(PEOPLE_MANY.search(txt)) or any(e[0] == "crowd" for e in ents)
    two = bool(PEOPLE_TWO.search(txt)) and not many

    # ---- layout of the picture
    tpls = []
    if shown:
        tpls = ["showcase", "pointing", "solo", "duo"] if not many else ["crowd", "showcase", "pointing"]
        if f["hook"] or action == "think":
            tpls = ["reaction", "showcase", "solo"]
        if shown[0][0] in BIG_ONLY:
            tpls = ["showcase", "walk", "pointing"]
    else:
        tpls = ["solo", "walk", "reaction", "duo"] if not many else ["crowd", "solo", "walk"]
        if two:
            tpls = ["duo", "solo"]
    if action in ("run", "walk"):
        tpls = ["walk"] + tpls
    if action == "sit":
        tpls = ["solo", "reaction"] + tpls
    tpl = _pick_unused(rng, tpls, mem["tpls"], 2)

    seed0 = rng.randrange(60)
    actors = []

    def char(r, x, act, scale, to=None, expr_=None, facing=1, fin=0.0):
        actors.append(dict(k="char", role=r, seed=seed0 + len(actors) * 7, x=x, scale=scale, action=act, to=to, expr=expr_ or expr, facing=facing, f_in=fin))

    if tpl == "walk":
        d = 1 if rng.random() > 0.5 else -1
        char(role, 0.15 if d > 0 else 0.85, "run" if action == "run" or expr == "worried" else "walk", 1.3, to=0.85 if d > 0 else 0.15, facing=d)
    elif tpl == "duo":
        char(role, 0.3, action if action != "walk" else "talk", 1.3, facing=1)
        char(_pick_unused(rng, ["citizen", "kid", "teacher", "scientist", "engineer"], [role], 1), 0.7, rng.choice(["talk", "think", "shrug", "point"]), 1.3, facing=-1, fin=0.1)
    elif tpl == "crowd":
        n = rng.choice([3, 4, 5])
        acts = ACTION_BY_EXPR.get(expr, ACTION_BY_EXPR["neutral"])
        for i in range(n):
            x = 0.16 + 0.68 * (i + rng.uniform(-0.1, 0.1)) / max(1, n - 1)
            char(rng.choice(["citizen", "kid", "teacher", "scientist", "engineer", "explorer"]), x, action if i == 0 else rng.choice(acts), 0.9 + 0.2 * (i % 2), facing=1 if x < 0.5 else -1, fin=0.04 * i)
    elif tpl == "reaction":
        char(role, 0.5 if not shown else 0.3, action, 2.1 if not shown else 1.7, expr_=expr)
    elif tpl == "showcase":
        x = rng.choice([0.2, 0.8])
        char(role, x, action if action not in ("walk", "run") else "point", 1.2, facing=1 if x < 0.5 else -1)
    elif tpl == "pointing":
        x = rng.choice([0.25, 0.75])
        char(role, x, "point", 1.45, facing=1 if x < 0.5 else -1)
    else:   # solo
        x = rng.choice([0.3, 0.38, 0.62, 0.7])
        char(role, x, action, 1.5, facing=1 if x < 0.5 else -1)

    # ---- the things the words name
    cx0 = actors[0]["x"] if actors else 0.5
    for k, (nm, lab, p) in enumerate(shown):
        side = 0.72 if cx0 < 0.5 else 0.28
        if tpl == "showcase":
            side = 0.5 if k == 0 and len(shown) == 1 else (0.38 if k == 0 else 0.68)
            size, y = (400 if len(shown) == 1 else 290), 0.40
        else:
            size, y = (300 if k == 0 else 190), (0.27 + 0.06 * k if nm in SKY else 0.30 + 0.05 * k)
            if k:
                side = 1 - side
        if nm in BIG_ONLY:
            size = int(size * 0.9)
        actors.append(dict(k="entity", name=nm, x=side, y=y, size=size, f_in=max(0.0, p * 0.5), motion="float", entry=rng.choice(["pop", "rise", "grow"]), label=lab,
                           seed=rng.randrange(99), holo=nm not in SKY and tpl != "showcase"))
    if f["nums"] and f["nums"][0]["kind"] in ("count", "percent", "temp", "year"):
        nb = f["nums"][0]
        actors.append(dict(k="stat_small", display=nb["display"], x=0.5, y=0.13, f_in=0.1))
    if expr in ("happy",) and mood in ("wonder", "funny") and rng.random() > 0.55:
        actors.append(dict(k="creature", kind=rng.choice(["cat", "dog", "bird", "blob_alien"]), x=rng.choice([0.07, 0.93]), to=None, scale=0.8, facing=1, seed=rng.randrange(9), f_in=0.2))

    cam = make_cam_2d(rng, mem["n"], mood, "hero" if tpl in ("reaction", "showcase") else tpl)
    if tpl == "reaction":
        cam = dict(k="push", amp=1.2, flip=rng.random() > 0.5)
    mem["envs"].append(env); mem["tpls"].append(tpl); mem["acts"].append(action); mem["roles"].append(role)
    for e in shown:
        mem["ents"].append(e[0])
    mem["n"] += 1
    for key in ("envs", "ents", "tpls", "roles", "acts"):
        mem[key] = mem[key][-8:]
    pal = {"bedroom": "dusk", "space": "cosmos", "underwater": "ocean", "cave": "bio", "snow": "ice", "desert": "dusk", "stage": "neon", "lab": "lab", "forest": "forest"}.get(env, "day")
    return dict(env=env, pal=pal, tpl=tpl, actors=actors, cam=cam, mood=mood, topic=topic)
