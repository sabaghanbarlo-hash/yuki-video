"""Cartoon icons for (almost) any noun or verb: ~1,370 flat pictures (Twemoji graphics, CC-BY 4.0, https://github.com/jdecked/twemoji)
with their keywords (Emojibase, MIT). find(text) reads a beat and returns the icons for the things it names, in the order they are
said, so each one can pop up at the moment the narrator says it."""
import functools, json, math, re
from pathlib import Path
from PIL import Image

DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"
ATTRIBUTION = "Icons: Twemoji by Twitter, Inc. and other contributors, licensed CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/)"
STOP = set("""a an the and or of to in on at for with by from as is are was were be been being it its this that these those you your i me my we our they their he she his her him them us not no yes so but if then than too very really just also even still only own same such like get gets got make makes made go goes went going say says said know knows known think thinks thought want wants need needs feel feels felt see sees seen look looks come comes came take takes took give gives gave let lets put puts keep keeps kept try tries tried use uses used find finds found tell tells told ask asks thing things way ways lot lots kind much many more most some any every each all both few little something anything everything nothing someone anyone everyone one two three here there where when what which who whom whose why how because while after before again always never often sometimes already yet ever about into over under out up down off back well now today day days time times people actually basically literally simply can could would should will shall may might must do does did done have has had having another reason nobody feels
""".split())
# abstract words people write -> the icon label words that picture them best
SYN = {
    "stress": "exploding head", "stressed": "exploding head", "anxiety": "anxious face with sweat", "anxious": "anxious face with sweat", "worry": "worried face", "worries": "worried face",
    "worried": "worried face", "fear": "fearful face", "scared": "fearful face", "afraid": "fearful face", "panic": "face screaming in fear", "angry": "enraged face", "anger": "enraged face",
    "sad": "crying face", "cry": "loudly crying face", "tired": "yawning face", "exhausted": "weary face", "sleepy": "sleeping face", "sleep": "sleeping face", "insomnia": "sleeping face",
    "happy": "smiling face with smiling eyes", "joy": "grinning face with smiling eyes", "laugh": "face with tears of joy", "funny": "face with tears of joy", "love": "red heart", "heart": "red heart",
    "confused": "face with spiral eyes", "overwhelmed": "face with spiral eyes", "bored": "neutral face", "lonely": "disappointed face", "alone": "disappointed face", "embarrassed": "flushed face",
    "awkward": "grimacing face", "surprised": "astonished face", "shock": "astonished face", "think": "thinking face", "thinking": "thinking face", "overthinking": "thought balloon", "thoughts": "thought balloon",
    "thought": "thought balloon", "mind": "brain", "brain": "brain", "memory": "brain", "memories": "brain", "idea": "light bulb", "ideas": "light bulb", "creative": "light bulb", "insight": "light bulb",
    "goal": "bullseye", "goals": "bullseye", "focus": "bullseye", "target": "bullseye", "aim": "bullseye", "purpose": "bullseye", "plan": "clipboard", "planning": "clipboard", "schedule": "calendar",
    "routine": "calendar", "habit": "calendar", "habits": "calendar", "consistency": "calendar", "daily": "calendar", "week": "calendar", "month": "calendar", "year": "calendar", "years": "calendar",
    "progress": "chart increasing", "growth": "seedling", "grow": "seedling", "improve": "chart increasing", "improvement": "chart increasing", "success": "trophy", "win": "trophy", "winner": "trophy",
    "achievement": "trophy", "fail": "cross mark", "failure": "cross mark", "mistake": "cross mark", "wrong": "cross mark", "correct": "check mark button", "right": "check mark button", "done": "check mark button",
    "finish": "chequered flag", "start": "chequered flag", "begin": "chequered flag", "money": "money bag", "rich": "money bag", "wealth": "money bag", "cash": "dollar banknote", "price": "label", "cost": "label",
    "pay": "credit card", "save": "piggy bank", "savings": "piggy bank", "invest": "chart increasing", "time": "alarm clock", "deadline": "alarm clock", "late": "alarm clock", "hurry": "alarm clock",
    "wait": "hourglass not done", "waiting": "hourglass not done", "procrastinate": "hourglass not done", "procrastination": "hourglass not done", "delay": "hourglass not done", "work": "briefcase",
    "job": "briefcase", "career": "briefcase", "boss": "briefcase", "office": "office building", "meeting": "handshake", "email": "envelope", "emails": "envelope", "message": "speech balloon",
    "messages": "speech balloon", "talk": "speech balloon", "conversation": "speech balloon", "speak": "speaking head", "say": "speech balloon", "words": "speech balloon", "chat": "speech balloon",
    "phone": "mobile phone", "scroll": "mobile phone", "scrolling": "mobile phone", "social": "mobile phone", "notifications": "bell", "notification": "bell", "screen": "desktop computer",
    "computer": "laptop", "laptop": "laptop", "internet": "globe with meridians", "online": "globe with meridians", "world": "globe showing europe-africa", "book": "open book", "books": "books",
    "read": "open book", "reading": "open book", "study": "books", "learn": "graduation cap", "learning": "graduation cap", "school": "school", "student": "graduation cap", "exam": "memo", "test": "memo",
    "write": "pen", "writing": "pen", "note": "memo", "notes": "memo", "journal": "notebook", "diary": "notebook", "list": "clipboard", "task": "clipboard", "tasks": "clipboard",
    "exercise": "person lifting weights", "workout": "person lifting weights", "gym": "person lifting weights", "run": "person running", "running": "person running", "walk": "person walking",
    "sport": "soccer ball", "health": "red heart", "healthy": "green apple", "diet": "green apple", "eat": "fork and knife with plate", "eating": "fork and knife with plate", "food": "fork and knife with plate",
    "meal": "fork and knife with plate", "breakfast": "fork and knife with plate", "sugar": "doughnut", "coffee": "hot beverage", "caffeine": "hot beverage", "tea": "teacup without handle", "water": "droplet",
    "drink": "cup with straw", "alcohol": "wine glass", "medicine": "pill", "doctor": "stethoscope", "sick": "face with thermometer", "pain": "adhesive bandage", "bed": "bed", "bedroom": "bed",
    "night": "crescent moon", "midnight": "crescent moon", "dark": "new moon", "morning": "sunrise", "sun": "sun", "light": "light bulb", "wake": "alarm clock", "alarm": "alarm clock",
    "home": "house", "house": "house", "family": "family", "friend": "people hugging", "friends": "people hugging", "relationship": "revolving hearts", "couple": "couple with heart", "baby": "baby",
    "kid": "child", "kids": "child", "child": "child", "children": "child", 
    "car": "automobile", "drive": "automobile", "travel": "airplane", "trip": "luggage", "vacation": "desert island", "beach": "beach with umbrella", "mountain": "mountain", "climb": "person climbing",
    "game": "video game", "games": "video game", "music": "musical note", "song": "musical note", "movie": "clapper board", "video": "video camera", "tv": "television", "photo": "camera",
    "problem": "warning", "danger": "warning", "risk": "warning", "warning": "warning", "stop": "stop sign", "secret": "shushing face", "silence": "shushing face", "quiet": "shushing face",
    "power": "high voltage", "energy": "high voltage", "battery": "battery", "fire": "fire", "motivation": "fire", "passion": "fire", "burnout": "battery", "tired out": "low battery",
    "gift": "wrapped gift", "party": "party popper", "celebrate": "party popper", "luck": "four leaf clover", "chance": "game die", "random": "game die", "choice": "balance scale",
    "decision": "balance scale", "fair": "balance scale", "law": "balance scale", "rules": "scroll", "history": "scroll", "ancient": "classical building", "science": "microscope", "research": "microscope",
    "experiment": "alembic", "scientist": "microscope", "chemistry": "test tube", "space": "milky way", "planet": "ringed planet", "star": "star", "stars": "glowing star", "rocket": "rocket",
    "robot": "robot", "ai": "robot", "technology": "gear", "machine": "gear", "system": "gear", "engine": "gear", "tool": "hammer and wrench", "fix": "wrench", "build": "brick",
    "bug": "bug", "virus": "microbe", "bacteria": "microbe", "germ": "microbe", "dna": "dna", "cell": "microbe", "body": "person standing", "eyes": "eyes", "eye": "eye", "see": "eyes", "watch": "eyes",
    "ear": "ear", "hear": "ear", "listen": "ear", "nose": "nose", "mouth": "mouth", "hand": "raised hand", "hands": "raised hands", "strong": "flexed biceps", "strength": "flexed biceps", "weak": "face with thermometer",
    "up": "up arrow", "down": "down arrow", "increase": "chart increasing", "decrease": "chart decreasing", "drop": "chart decreasing", "fall": "chart decreasing", "rise": "chart increasing",
    "cycle": "counterclockwise arrows button", "repeat": "repeat button", "loop": "repeat button", "again": "repeat button", "reset": "counterclockwise arrows button", "change": "counterclockwise arrows button",
    "question": "red question mark", "answer": "check mark button", "why": "red question mark", "mystery": "magnifying glass tilted left", "search": "magnifying glass tilted left", "find": "magnifying glass tilted left",
    "notice": "magnifying glass tilted left", "key": "key", "lock": "locked", "secure": "locked", "privacy": "locked", "free": "unlocked", "trap": "mouse trap", "stuck": "locked", "dream": "crescent moon",
    "nightmare": "ghost", "scary": "ghost", "monster": "alien monster", "magic": "crystal ball", "future": "crystal ball", "wish": "shooting star", "hope": "shooting star",
    "death": "skull", "dead": "skull", "kill": "skull", "poison": "skull and crossbones", "weather": "sun behind cloud", "rain": "cloud with rain", "storm": "cloud with lightning and rain", "snow": "snowflake",
    "cold": "cold face", "hot": "hot face", "tree": "deciduous tree", "forest": "evergreen tree", "nature": "deciduous tree", "flower": "cherry blossom", "plant": "seedling", "animal": "paw prints",
    "dog": "dog face", "cat": "cat face", "bird": "bird", "fish": "fish", "ocean": "water wave", "sea": "water wave", "city": "cityscape", "street": "cityscape",
}
NO_ICON = set("people person man men woman women guy someone everyone crowd society humans human team boy girl lady call calls called part head hard work works working found keep makes make feel feels".split())      # people are drawn as cartoon characters, not icons
_STEM = [("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")]


def _stem(w):
    for suf, rep in _STEM:
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)] + rep
    return w


@functools.lru_cache(maxsize=1)
def _index():
    f = DIR / "index.json"
    if not f.exists():
        return {}, {}, {}
    idx = json.load(open(f, encoding="utf-8"))
    by_label = {v[0].lower(): k for k, v in idx.items()}
    inv = {}
    for hx, (label, tags, grp) in idx.items():
        for w in re.findall(r"[a-z]+", label.lower()):
            inv.setdefault(_stem(w), {})[hx] = max(inv.get(_stem(w), {}).get(hx, 0), 3.0)
        for tg in tags:
            for w in re.findall(r"[a-z]+", tg.lower()):
                inv.setdefault(_stem(w), {})[hx] = max(inv.get(_stem(w), {}).get(hx, 0), 2.0)
    return idx, by_label, inv


GROUP_BONUS = {"objects": 0.6, "food-drink": 0.5, "travel-places": 0.5, "animals-nature": 0.5, "activities": 0.4, "symbols": 0.0, "people-body": 0.1, "smileys-emotion": 0.2}


def lookup(word):
    """One word -> (hexcode, score) or None."""
    idx, by_label, inv = _index()
    if not idx:
        return None
    w = word.lower()
    if w in NO_ICON:
        return None
    if w in SYN and SYN[w].lower() in by_label:
        return by_label[SYN[w].lower()], 10.0
    st = _stem(w)
    if st in SYN and SYN[st].lower() in by_label:
        return by_label[SYN[st].lower()], 9.0
    hits = inv.get(st) or inv.get(w)
    if not hits or len(hits) > 14 and max(hits.values()) < 3:
        return None
    hits = {k: v for k, v in hits.items() if "silhouette" not in idx[k][0]}
    if not hits:
        return None
    best = max(hits.items(), key=lambda kv: (kv[1] + GROUP_BONUS.get(idx[kv[0]][2], 0), -len(idx[kv[0]][0])))
    if best[1] < 2.0 or (len(hits) > 25 and best[1] < 3):
        return None
    return best[0], best[1]


def find(text, limit=4):
    """-> [(hexcode, label, word, position 0..1)] for the things the text names, in reading order; distinct icons only."""
    idx, _, _ = _index()
    if not idx:
        return []
    out, seen = [], set()
    n = max(1, len(text))
    for m in re.finditer(r"[A-Za-z']+", text):
        w = m.group(0).lower().replace("'", "")
        if w in STOP or len(w) < 3:
            continue
        r = lookup(w)
        if not r or r[0] in seen:
            continue
        seen.add(r[0])
        out.append((r[0], idx[r[0]][0], w, m.start() / n, r[1]))
    if len(out) > limit:                                    # keep the strongest matches, then back into reading order
        keep = sorted(out, key=lambda o: -o[4])[:limit]
        out = sorted(keep, key=lambda o: o[3])
    return [(h, lab, w, pos) for h, lab, w, pos, _ in out]


@functools.lru_cache(maxsize=512)
def image(hexcode, size=256):
    p = DIR / f"{hexcode}.png"
    im = Image.open(p).convert("RGBA")
    return im.resize((size, size), Image.LANCZOS)


@functools.lru_cache(maxsize=800)
def sticker(hexcode, size, rot=0):
    """The icon as a die-cut sticker: white edge, soft shadow, slight tilt."""
    from PIL import ImageFilter, ImageChops
    pad = max(6, size // 10)
    base = image(hexcode, 256).resize((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    canvas.alpha_composite(base, (pad, pad))
    alpha = canvas.getchannel("A")
    edge = alpha.filter(ImageFilter.MaxFilter(max(3, (size // 28) * 2 + 1)))
    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow = Image.new("RGBA", canvas.size, (90, 60, 30, 0))
    shadow.putalpha(edge.filter(ImageFilter.GaussianBlur(max(2, size // 22))).point(lambda v: int(v * 0.34)))
    out.alpha_composite(shadow, (max(1, size // 40), max(2, size // 22)))
    white = Image.new("RGBA", canvas.size, (255, 255, 255, 255)); white.putalpha(edge)
    out.alpha_composite(white)
    out.alpha_composite(canvas)
    return out.rotate(rot, resample=Image.BICUBIC, expand=False) if rot else out
