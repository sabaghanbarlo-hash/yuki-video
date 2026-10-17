"""Per-episode YouTube thumbnail, built from the script's own content.

  * background  : the scene "world" that best matches the script (college -> campus, sleep -> night room, ...)
  * big words   : the punchiest 2-3 words of the title, one of them highlighted
  * face + pose : Yuki reacts the way the title feels (shocked, worried, happy, curious ...)
  * stickers    : icons for the topics the script talks about most (brain, clock, phone, heart ...)

    python make_thumbnail.py stories/my-script.txt --out output/my-script.jpg
"""
import hashlib, math, random, re
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import icons, world
from .character import Rig
from .fonts import font
from .script import NEG, POS, THEME_WORDS, parse_script

W, H = 1280, 720
NAVY = (28, 26, 54)
YELLOW = (255, 214, 64)
RED = (222, 64, 72)
WHITE = (255, 255, 255)

EXTRA_THEME_WORDS = {
    "classroom": "class classes classroom teacher teachers school homework lecture lectures professor professors lesson students student",
    "exam_hall": "exam exams test tests grade grades gpa finals deadline deadlines assignment assignments",
    "campus": "college university campus dorm dorms freshman roommate roommates semester degree graduate",
    "library": "library study studying books research thesis",
    "phone": "phone scroll scrolling social media instagram tiktok notifications screen app apps",
}
ALL_THEME_WORDS = {k: set(v.split()) for k, v in {**THEME_WORDS, **EXTRA_THEME_WORDS}.items()}
STOP = set("""a an the of to in on for at by is it i was were be been am are and or but my me you your we our they their
with that this as from so if not no do does did have has had will would can could should just very really than then
there here what when where why how who which about into out up down over under again more most some any all one""".split())
NEGATORS = {"not", "never", "no", "stop", "why", "how", "nobody", "nothing", "worst", "dont", "don't", "cant", "can't", "wont"}
EMO = {"emotion", "emotional", "emotionally", "brain", "mind", "love", "hate", "fear", "anxiety", "anxious", "lonely", "alone",
       "tired", "burnout", "stress", "stressed", "broke", "free", "secret", "truth", "lie", "lies", "regret", "panic", "trap"}


def _tokens(t):
    return re.findall(r"[a-z][a-z'’-]*", t.lower())


def _read(script):
    """-> (title, full_text)"""
    try:
        title, beats = parse_script(script)
        text = " ".join(b.text for b in beats)
    except Exception:
        raw = Path(script).read_text(encoding="utf-8", errors="replace")
        title, text = None, raw
    if not title:
        title = Path(script).stem.replace("-", " ").replace("_", " ").title()
    return title.strip(), text


# --------------------------------------------------------------------------- decisions
def pick_world(title, text):
    tt, body = _tokens(title), _tokens(text)
    first = body[:120]
    best, score = None, 0.0
    for th, words in ALL_THEME_WORDS.items():
        s = 4.0 * sum(w in words for w in tt) + 2.0 * sum(w in words for w in first) + sum(w in words for w in body)
        if s > score:
            best, score = th, s
    if best:
        return best
    h = int(hashlib.md5(title.encode()).hexdigest(), 16)
    return ["sunrise", "mind", "night_city", "room_day", "city_day", "nature"][h % 6]


def pick_face(title, text):
    tt = set(_tokens(title))
    body = set(_tokens(text[:1500]))
    if "?" in title or (_tokens(title) or [""])[0] in ("why", "how", "what", "when", "who", "is", "are", "do", "does"):
        return "curious", "think"
    if tt & NEG or tt & NEGATORS:
        return "shocked", "shrug"
    if tt & POS:
        return "happy", "cheer"
    if body & NEG and not body & POS:
        return "worried", "shrug"
    if body & POS:
        return "excited", "present"
    return "shocked", "point_l"


def punch(title):
    """-> (big_words, small_words, highlight_index). Big text is the punchiest 2-3 word window of the title."""
    words = re.findall(r"[A-Za-z0-9$%][A-Za-z0-9'’$%-]*", title)
    if not words:
        return ["NEW", "EPISODE"], [], 0
    if len(words) <= 3:
        sc = [_wscore(w) for w in words]
        return [w.upper() for w in words], [], int(np.argmax(sc))
    sc = [_wscore(w) for w in words]
    best, bi, bn = -1.0, 0, 3
    for n in (2, 3, 4):
        for i in range(0, len(words) - n + 1):
            s = sum(sc[i:i + n]) - 0.9 * (n - 2) - (0.8 if n == 4 else 0)
            if s > best:
                best, bi, bn = s, i, n
    if bi > 0 and words[bi - 1].lower().strip("'’") in NEGATORS and bn < 4:      # keep "NOT" with what it negates
        bi -= 1; bn += 1
    big = words[bi:bi + bn]
    after = words[bi + bn:]
    small = after if after else []
    hi = int(np.argmax([_wscore(w) for w in big]))
    return [w.upper() for w in big], [w.upper() for w in small][:5], hi


def _wscore(w):
    lw = w.lower().strip("'’")
    if re.fullmatch(r"[\d$%.,]+", lw):
        return 3.0
    s = 0.0
    if lw not in STOP:
        s += 1.0 + (0.5 if len(lw) >= 7 else 0.0)
    if lw in NEGATORS:
        s += 1.6
    if lw in NEG or lw in EMO or any(lw.startswith(e) for e in ("emotion", "anxi", "lonel")):
        s += 1.4
    return s


def pick_icons(title, text, n=2):
    tt, body = Counter(_tokens(title)), Counter(_tokens(text))
    scored = []
    for name, words in icons.ICON_KEYS.items():
        ws = set(words.split())
        s = sum(3 * c for t, c in tt.items() if t in ws or t.rstrip("s") in ws) + \
            sum(c for t, c in body.items() if t in ws or t.rstrip("s") in ws)
        if s > 0:
            scored.append((s, name))
    scored.sort(reverse=True)
    out = [n_ for _, n_ in scored[:n]]
    for fb in ("bulb", "star"):
        if len(out) < n and fb not in out:
            out.append(fb)
    return out


# --------------------------------------------------------------------------- drawing helpers
def _fit_lines(lines, box_w, box_h, start=190, lo=46, weight="bold", spacing=1.04):
    for size in range(start, lo - 1, -4):
        f = font(size, weight)
        widths = [f.getbbox(l)[2] - f.getbbox(l)[0] for l in lines]
        lh = int(size * spacing)
        if max(widths) <= box_w and lh * len(lines) <= box_h:
            return f, size, lh
    return font(lo, weight), lo, int(lo * spacing)


def _wrap_big(words, max_lines=3):
    """Split the big words over lines: one word per line when short, otherwise balanced."""
    if len(words) <= 1:
        return list(words)
    if len(words) == 2:
        return list(words)
    return list(words[:max_lines]) if len(words) <= max_lines else [" ".join(words[:2])] + list(words[2:])


def _sticker(name, size, angle):
    ic = icons.icon(name, size)
    pad = 20
    big = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(ic, (pad, pad))
    mask = big.split()[3].filter(ImageFilter.MaxFilter(11))
    outline = Image.new("RGBA", big.size, WHITE + (255,))
    outline.putalpha(mask)
    sh = Image.new("RGBA", big.size, (0, 0, 0, 0))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * 0.55)))
    out = Image.new("RGBA", big.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (5, 11))
    out.alpha_composite(outline)
    out.alpha_composite(big)
    return out.rotate(angle, resample=Image.BICUBIC, expand=True)


def _background(theme, seed):
    bg = world.theme_image(theme).convert("RGB")
    z = 1.14
    bg = bg.resize((int(W * z), int(H * z)), Image.LANCZOS)
    ox = int((bg.width - W) * 0.7)
    bg = bg.crop((ox, int((bg.height - H) * 0.35), ox + W, int((bg.height - H) * 0.35) + H))
    bg = ImageEnhance.Color(bg).enhance(1.3)
    bg = ImageEnhance.Contrast(bg).enhance(1.12)
    arr = np.asarray(bg).astype(np.float32)
    xs = np.linspace(0, 1, W)[None, :, None]
    dark = np.clip(1.0 - xs / 0.72, 0, 1) ** 1.2 * 0.78                    # text side is darker
    arr = arr * (1 - dark) + np.array(NAVY, np.float32)[None, None, :] * dark
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.sqrt(((xx - W / 2) / (W * 0.72)) ** 2 + ((yy - H / 2) / (H * 0.78)) ** 2)
    arr = arr * (1 - np.clip(v - 0.55, 0, 1)[..., None] * 0.55)           # vignette
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


def _character(frame, face, pose, cx=985, scale=1.12, floor=806):
    rig = Rig(cx, floor, scale)
    rig.target_x = rig.x
    for _ in range(90):
        rig.update(1 / 24, pose=pose, face=face, speaking=0.0, wiggle=0.0)
    rig.tilt = -3.0 if pose in ("shrug", "think") else 2.0
    rig.draw(frame, 2, False)


def make(script, out, mode="explainer", seed=None):
    title, text = _read(script)
    rng = random.Random(seed if seed is not None else int(hashlib.md5(title.encode()).hexdigest()[:8], 16))
    theme = pick_world(title, text)
    face, pose = pick_face(title, text)
    big, small, hi = punch(title)
    names = pick_icons(title, text, 2)

    frame = _background(theme, rng)
    glow = world.glow(W, H, 985, 360, 470, (255, 226, 160), 0.55)
    frame.alpha_composite(glow)
    _character(frame, face, pose)

    # stickers
    for (name, (x, y), size, ang) in zip(names, ((742, 70), (690, 470)), (170, 150), (-9, 8)):
        st = _sticker(name, size, ang)
        frame.alpha_composite(st, (x, y))

    # big words
    lines = _wrap_big(big)
    box_w, box_h = 690, 400 if small else 470
    f, size, lh = _fit_lines(lines, box_w, box_h)
    layer = Image.new("RGBA", (box_w + 120, lh * len(lines) + 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    hl_word = big[hi]
    y = 40
    for ln in lines:
        col = YELLOW if hl_word in ln.split() and len(lines) > 1 and ln == next((l for l in lines if hl_word in l.split()), None) else WHITE
        if len(lines) == 1:
            col = WHITE
        sw = max(6, size // 11)
        d.text((46, y + 8), ln, font=f, fill=(0, 0, 0, 120), stroke_width=sw, stroke_fill=(0, 0, 0, 120))
        d.text((40, y), ln, font=f, fill=col, stroke_width=sw, stroke_fill=NAVY)
        y += lh
    layer = layer.rotate(2.5, resample=Image.BICUBIC, expand=True)
    ty = int(70 + (box_h - lh * len(lines)) / 2) if small else int(110 + (box_h - lh * len(lines)) / 2)
    frame.alpha_composite(layer, (14, max(30, ty)))

    # small line (rest of the title) in a pill
    if small:
        sf = font(50, "bold")
        s_txt = " ".join(small)
        tw = sf.getbbox(s_txt)[2]
        if tw > 640:
            sf = font(int(50 * 640 / tw), "bold"); tw = sf.getbbox(s_txt)[2]
        px, py = 58, 598
        pill = Image.new("RGBA", (tw + 64, 84), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pill)
        pd.rounded_rectangle((0, 0, pill.width - 1, pill.height - 1), radius=26, fill=RED + (255,))
        pd.text((32, 12), s_txt, font=sf, fill=WHITE)
        frame.alpha_composite(pill.rotate(-1.5, resample=Image.BICUBIC, expand=True), (px, py))

    # channel tag
    tf = font(26, "bold")
    tag = Image.new("RGBA", (250, 48), (0, 0, 0, 0))
    td = ImageDraw.Draw(tag)
    td.rounded_rectangle((0, 0, 249, 47), radius=24, fill=(255, 255, 255, 235))
    td.text((22, 8), "CALL OF YUKI", font=tf, fill=NAVY)
    frame.alpha_composite(tag, (44, 34))

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rgb = frame.convert("RGB")
    for q in (93, 88, 82, 74):
        rgb.save(out, "JPEG", quality=q, optimize=True)
        if out.stat().st_size < 1_900_000:
            break
    info = dict(title=title, theme=theme, face=face, pose=pose, big=big, small=small, icons=names,
                size_kb=round(out.stat().st_size / 1024))
    return info
