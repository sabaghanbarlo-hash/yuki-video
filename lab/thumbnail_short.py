"""Thumbnail for a Short: vertical 1080 x 1920, made from the script (no stock art, no paid APIs).

    make_short_thumbnail(text, out, seed)

What is on it depends on the script:
  * the hook, in huge ink letters (the title, or the opening sentence), with a highlighter bar in the topic's colour
  * Yuki, big, with the face / pose / reaction card that fit the opening feeling (shocked for a scary hook, curious for a question ...)
  * a topic icon sticker (brain, bed, phone, clock ... picked from the words) or, when the opening says a number ("70 percent"), a stat badge
  * the channel chip at the top
The layout keeps the important things in the middle: Shorts cover the bottom edge and the right edge with buttons, and the channel grid crops the sides.
"""
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

TW, TH = 1080, 1920
DANGLERS = {'the', 'a', 'an', 'of', 'to', 'and', 'or', 'but', 'your', 'you', 'our', 'their', 'his', 'her', 'its', 'in', 'on', 'at', 'for', 'with', 'is', 'are', 'that', 'this', 'by', 'as', 'only', 'just', 'even', 'not', 'be'}
QWORDS = {"why", "how", "what", "is", "are", "do", "does", "can", "should", "will", "who", "when", "which", "did", "would"}
# topic -> (page accent colour). Defaults to the Mind Lab violet.
TOPIC_COLOUR = {"brain": (156, 136, 214), "body": (232, 112, 122), "micro": (188, 208, 62), "space": (96, 176, 204), "physics": (96, 176, 204),
                "tech": (96, 176, 204), "ocean": (96, 176, 204), "ice": (96, 176, 204), "earth": (240, 160, 64), "desert": (240, 160, 64),
                "volcano": (232, 112, 122), "disaster": (232, 112, 122), "nature": (188, 208, 62), "weather": (96, 176, 204),
                "history": (250, 206, 84), "city": (250, 206, 84)}
DEFAULT_COLOUR = (156, 136, 214)
FACE_FOR_THUMB = {"neutral": "curious", "smile": "excited", "serene": "curious", "bored": "shocked", "deadpan": "shocked", "sleepy": "shocked", "dreamy": "curious"}
POSE_FOR_FACE = {"shocked": "gasp_hands", "gasp": "gasp_hands", "terrified": "gasp_hands", "worried": "head", "nervous": "head", "pained": "head", "sad": "sob", "crying": "sob",
                 "teary": "sob", "curious": "think", "confused": "think", "dizzy": "head", "excited": "cheer", "starry": "cheer", "laughing": "cheer", "happy": "cheer",
                 "proud": "fist", "determined": "fist", "inspired": "idea", "smug": "hips", "scheming": "hips", "cheeky": "hips", "angry": "cross", "grumpy": "cross",
                 "embarrassed": "shy", "awkward": "shy"}
ACCENT_FOR_FACE = {"curious": "q", "confused": "q", "shocked": "ex", "gasp": "ex", "terrified": "ex", "worried": "sweat", "nervous": "sweat", "pained": "sweat", "sleepy": "zzz"}


def paper_bg(w, h, seed=7):
    """The cream page of the Collage videos at any size."""
    rng = np.random.default_rng(seed)
    base = np.zeros((h, w, 3), np.float32) + np.array((246, 226, 200), np.float32)
    lo = rng.normal(0, 1, (h // 24 + 2, w // 24 + 2)).astype(np.float32)
    lo = np.array(Image.fromarray(((lo - lo.min()) / (np.ptp(lo) + 1e-6) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255.0
    base += (lo[..., None] - 0.5) * 5.0
    base += rng.normal(0, 1.2, (h, w, 1)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    base -= (np.clip(d - 0.8, 0, 1) ** 2 * 7.0)[..., None]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def hook_text(title, first):
    t = re.sub(r"[#*_]+", "", title or "").strip() or (first or "")
    t = re.sub(r"\s+", " ", t).strip(" .")
    if len(t.split()) > 6:                                            # long opening: keep the first clause if it stands alone
        head = re.split(r"[,;:\u2014]| - ", t)[0].split()
        if len(head) >= 3:
            t = " ".join(head)
    words = t.split()[:7]
    while len(words) > 3 and words[-1].lower().strip(".,?!") in DANGLERS:
        words.pop()
    t = " ".join(words).rstrip(",;:-")
    if words and words[0].lower().strip("'") in QWORDS and not t.endswith("?"):
        t += "?"
    return t.upper()


def fit_lines(d, text, maxw, font, max_lines=4, start=214, minsize=92, maxh=700):
    size = start
    while True:
        f = font(size, "bold")
        lines, cur = [], ""
        for wd in text.split():
            t2 = (cur + " " + wd).strip()
            if d.textlength(t2, font=f) <= maxw or not cur:
                cur = t2
            else:
                lines.append(cur); cur = wd
        lines.append(cur)
        if (len(lines) <= max_lines and len(lines) * size * 1.12 <= maxh and max(d.textlength(l, font=f) for l in lines) <= maxw) or size <= minsize:
            return lines, size
        size -= 6


def find_stat(sentences, K, stat_caption):
    """The first number in the opening that is worth a badge: a percentage or a big count. -> (display, label) or None."""
    for s in sentences[:6]:
        for m in K.NUM.finditer(s):
            num, mult, unit = m.group(1), (m.group(2) or ""), (m.group(3) or "").lower()
            if unit in ("percent", "%"):
                return num.lstrip("$") + "%", stat_caption(s)
            if mult:
                return (num + " " + mult).strip(), stat_caption(s)
    return None


def rounded(w, h, r, fill):
    s = 3
    m = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=r * s, fill=255)
    m = m.resize((w, h), Image.LANCZOS)
    im = Image.new("RGBA", (w, h), tuple(fill[:3]) + (255,))
    im.putalpha(m.point(lambda v: int(v * (fill[3] / 255.0 if len(fill) > 3 else 1.0))))
    return im


def darker(c, k):
    return tuple(int(v * k) for v in c[:3])


def paste(dst, im, x, y, alpha=1.0):
    from . import overlays as O
    O.paste(dst, im, x, y, alpha)


def make_short_thumbnail(text, out, seed=0):
    from . import fmt as FM
    FM.set_format("short")
    from . import pipeline as P, knowledge as K, icons as IC
    from .fonts import font
    from .collage import INK, accent_img
    from .collage_dir import stat_caption
    from . import yuki_rig as Y
    from . import overlays as O

    plan = P.build_plan(text, seed, "collage", None)
    bodies = [s for s in plan["scenes"] if s["kind"] == "body"]
    sents = [s["text"] for sc in bodies for s in sc["sentences"]]
    first = sents[0] if sents else ""
    topic = K.topic_of(text)
    colour = TOPIC_COLOUR.get(topic, DEFAULT_COLOUR)
    dark = darker(colour, 0.55)
    shot = bodies[0]["shots"][0]

    im = paper_bg(TW, TH)
    d = ImageDraw.Draw(im)

    # ---- spotlight circle behind Yuki
    spot = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    ImageDraw.Draw(spot).ellipse((TW // 2 - 150, 1030, TW // 2 + 590, 1770), fill=colour + (120,))
    im.alpha_composite(spot.filter(ImageFilter.GaussianBlur(2)))

    # ---- the hook
    hook = hook_text(plan.get("title") or "", first)
    lines, size = fit_lines(d, hook, 940, font)
    f = font(size, "bold")
    lh = int(size * 1.12)
    block_h = lh * len(lines)
    y0 = int(150 + (730 - block_h) / 2)
    layer = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    ld, sd = ImageDraw.Draw(layer), ImageDraw.Draw(shadow)
    for i, l in enumerate(lines):
        w = ld.textlength(l, font=f)
        x = (TW - w) / 2
        yy = y0 + i * lh
        if i == len(lines) - 1:                                       # highlighter bar behind the last line
            bar = rounded(int(w + 70), int(size * 0.8), 26, colour + (240,))
            layer.alpha_composite(bar, (int(x - 35), int(yy + size * 0.24)))
        sd.text((x + 9, yy + 11), l, font=f, fill=dark + (150,), stroke_width=11, stroke_fill=dark + (150,))
        ld.text((x, yy), l, font=f, fill=INK + (255,), stroke_width=11, stroke_fill=(255, 252, 246, 255))
    im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(5)))
    im.alpha_composite(layer)
    text_bottom = y0 + block_h

    # ---- Yuki (opening feeling decides her face; thumbnails want a big reaction)
    face = FACE_FOR_THUMB.get(shot.get("face", "neutral"), shot.get("face", "neutral"))
    if hook.endswith("?") and face in ("excited", "happy"):
        face = "curious"
    pose = POSE_FOR_FACE.get(face, "present")
    S = 1.45
    fx, fy = 690, TH + 60
    yl = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    ox, oy = Y.draw_figure(yl, fx, fy, S, pose=pose, face=face, amp=0.0, t=1.3, flip=False)
    im.alpha_composite(yl)
    bb = yl.getchannel("A").getbbox() or (0, 0, 0, 0)
    head_x, head_y = ox + 240 * S, oy + 190 * S
    kind = ACCENT_FOR_FACE.get(face) or ((shot.get("accents") or ["ex"])[0])
    card = accent_img(kind, int(150 * S))
    card = card.rotate(-7, resample=Image.BICUBIC)
    cx, cy = int(head_x + 190 * S - card.width / 2), int(head_y - 215 * S - card.height / 2)
    cy = max(cy, text_bottom + 20)
    cx = min(cx, TW - card.width - 30)
    paste(im, card, cx, cy)

    # ---- stat badge or topic icon (bottom-left, clear of Yuki)
    stat = find_stat(sents, K, stat_caption)
    icon = None
    try:
        found = IC.find(" ".join([plan.get("title") or "", first, " ".join(sents[1:3])]), limit=3)
        icon = found[0][0] if found else None
    except Exception:
        icon = None
    if stat:
        num, label = stat
        nf = font(150 if len(num) <= 4 else 108, "bold")
        lab = (label or "").upper()[:24]
        lf = font(38, "bold")
        bw, bh = 400, 330
        badge = rounded(bw, bh, 40, colour + (255,))
        bd = ImageDraw.Draw(badge)
        bd.rounded_rectangle((5, 5, bw - 6, bh - 6), radius=36, outline=dark + (255,), width=6)
        nw = bd.textlength(num, font=nf)
        bd.text(((bw - nw) / 2, 36), num, font=nf, fill=(255, 255, 255, 255), stroke_width=6, stroke_fill=dark + (255,))
        if lab:
            lw = bd.textlength(lab, font=lf)
            if lw > bw - 40:
                lf = font(30, "bold"); lw = bd.textlength(lab, font=lf)
            bd.text(((bw - lw) / 2, 230), lab, font=lf, fill=INK + (255,))
        badge = badge.rotate(7, resample=Image.BICUBIC, expand=True)
        paste(im, badge, 50, 1235)
        if icon:
            paste(im, IC.sticker(icon, 190, -10), 30, 1160)
    elif icon:
        paste(im, IC.sticker(icon, 380, -8), 40, 1250)

    # ---- channel chip
    chip = O.chip_img("YUKI'S MIND LAB", colour, 36)
    paste(im, chip, (TW - chip.width) // 2, 62)

    im.convert("RGB").save(out, quality=92, subsampling=0)
    return dict(out=out, hook=hook, lines=lines, size=size, face=face, pose=pose, topic=topic, stat=stat, icon=icon, text_bottom=text_bottom, yuki_bbox=bb, card=(cx, cy, card.width, card.height))
