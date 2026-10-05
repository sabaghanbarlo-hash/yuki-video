"""Explainer visuals: pre-rendered elements that pop in on cue next to Yuki.

Each builder returns a Visual: a list of Elements (RGBA image + position + entrance time).
Times are relative to the start of the scene; the director fills in `t_in` for reveal items.
"""
import math, os
from dataclasses import dataclass, field
from PIL import Image, ImageDraw, ImageFilter
from .fonts import font
from .icons import icon, WHITE

PANEL = (480, 50, 1244, 566)          # x0, y0, x1, y1 where visuals live
PW, PH = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
NAVY = (44, 40, 84)
MUTED = (112, 110, 150)
RED, GREEN = (244, 90, 96), (92, 200, 128)
ACCENTS = [(255, 107, 107), (46, 196, 182), (255, 184, 64), (140, 110, 255), (80, 150, 255), (92, 200, 120), (255, 130, 190)]


@dataclass
class Element:
    img: Image.Image
    x: int
    y: int
    t_in: float = 0.0
    anim: str = "pop"          # pop | rise | fade | wipe | none
    dur: float = 0.38


@dataclass
class Visual:
    kind: str
    elements: list = field(default_factory=list)
    n_items: int = 0            # how many sequential reveals (director assigns times)
    item_idx: list = field(default_factory=list)   # indexes into elements that are reveal items
    pose: str = "point"         # gesture while presenting
    layout: str = "split"       # split | center
    meta: dict = field(default_factory=dict)


# ------------------------------------------------------------------ helpers
def wrap(text, fnt, max_w):
    dr = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if cur and dr.textlength(t, font=fnt) > max_w:
            lines.append(cur); cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines or [""]


def fit_text(text, max_w, max_h, start=64, min_size=22, weight="bold", spacing=1.18):
    """Largest font size where wrapped text fits in the box. Returns (font, lines, line_h)."""
    size = start
    while size >= min_size:
        f = font(size, weight)
        lines = wrap(text, f, max_w)
        lh = int(size * spacing)
        if lh * len(lines) <= max_h:
            return f, lines, lh
        size -= 2
    f = font(min_size, weight)
    return f, wrap(text, f, max_w), int(min_size * spacing)


def shadow_pad(img, blur=14, dy=8, alpha=64, pad=None):
    pad = pad or blur * 2
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    sh.paste((30, 24, 70, alpha), (pad, pad + dy), img.getchannel("A"))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(sh)
    out.alpha_composite(img, (pad, pad))
    return out, pad


def card(w, h, fill=(255, 255, 255, 244), radius=34, accent=None, border=None):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius, fill=fill, outline=border, width=4 if border else 0)
    if accent:
        d.rounded_rectangle((0, 0, w - 1, 14), radius // 2, fill=accent)
        d.rectangle((0, 8, w - 1, 14), fill=accent)
    return im


def put(el_list, img, x, y, **kw):
    """Add an element with a soft shadow; (x, y) is the top-left of the *card* (without shadow)."""
    sp, pad = shadow_pad(img)
    el = Element(sp, int(x - pad), int(y - pad), **kw)
    el_list.append(el)
    return el


def center_x(w):
    return PANEL[0] + (PW - w) // 2


def text_block(lines, fnt, lh, fill=NAVY, align="left", width=None, shadow=False):
    w = width or int(max(ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength(l, font=fnt) for l in lines)) + 8
    im = Image.new("RGBA", (w, lh * len(lines) + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        tw = d.textlength(l, font=fnt)
        x = {"left": 4, "center": (w - tw) / 2, "right": w - tw - 4}[align]
        if shadow:
            d.text((x + 2, i * lh + 4), l, font=fnt, fill=(0, 0, 0, 60))
        d.text((x, i * lh + 2), l, font=fnt, fill=fill)
    return im


def tint(c, k):
    return tuple(int(255 - (255 - v) * k) for v in c)


# ------------------------------------------------------------------ builders
def v_title(title, subtitle="CALL OF YUKI"):
    v = Visual("title", layout="split", pose="present")
    f, lines, lh = fit_text(title, PW - 120, 300, start=78, min_size=40)
    tb = text_block(lines, f, lh, NAVY, "left")
    h = tb.height + 150
    c = card(PW - 20, h, accent=ACCENTS[3])
    d = ImageDraw.Draw(c)
    d.text((54, 54), subtitle, font=font(30, "semibold"), fill=ACCENTS[0])
    c.alpha_composite(tb, (50, 100))
    put(v.elements, c, PANEL[0] + 10, PANEL[1] + (PH - h) // 2 - 10, t_in=0.15, anim="rise", dur=0.5)
    return v


def v_keyword(text, sub=None, color=0):
    """Big punchy phrase with a marker highlight."""
    v = Visual("keyword", layout="split", pose="point")
    f, lines, lh = fit_text(text, PW - 130, 280, start=84, min_size=40)
    dr = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    acc = ACCENTS[color % len(ACCENTS)]
    h = lh * len(lines) + (70 if sub else 20) + 80
    c = card(PW - 20, h, accent=acc)
    d = ImageDraw.Draw(c)
    y = 70
    for l in lines:
        tw = dr.textlength(l, font=f)
        d.rounded_rectangle((52, y + lh * 0.55, 52 + tw + 14, y + lh * 0.95), 12, fill=tint(acc, 0.35))
        d.text((58, y), l, font=f, fill=NAVY)
        y += lh
    if sub:
        sf, sl, slh = fit_text(sub, PW - 120, 90, start=32, min_size=20, weight="medium")
        for l in sl:
            d.text((58, y + 12), l, font=sf, fill=MUTED)
            y += slh
    put(v.elements, c, PANEL[0] + 10, PANEL[1] + (PH - h) // 2, t_in=0.1, anim="pop")
    return v


def v_icon(name, label=None, color=0):
    v = Visual("icon", layout="split", pose="present")
    size = 260
    ic = icon(name, size)
    acc = ACCENTS[color % len(ACCENTS)]
    h = size + 80 + (90 if label else 0)
    w = 520
    c = card(w, h, fill=(255, 255, 255, 244), accent=acc)
    c.alpha_composite(ic, ((w - size) // 2, 56))
    if label:
        f, lines, lh = fit_text(label, w - 70, 120, start=42, min_size=24)
        tb = text_block(lines, f, lh, NAVY, "center", width=w - 40)
        c.alpha_composite(tb, (20, 56 + size + 14))
    put(v.elements, c, center_x(w), PANEL[1] + (PH - h) // 2, t_in=0.1, anim="pop")
    return v


def v_icons(items):
    """Up to 4 icon tiles in a row, revealed one by one. items: [(icon_name, label)]"""
    items = items[:4]
    n = len(items)
    v = Visual("icons", layout="split", pose="point", n_items=n)
    gap = 26
    tw = min(250, (PW - gap * (n - 1)) // n)
    th = tw + 120
    x0 = PANEL[0] + (PW - (tw * n + gap * (n - 1))) // 2
    y0 = PANEL[1] + (PH - th) // 2
    for i, (nm, label) in enumerate(items):
        acc = ACCENTS[(i * 2 + 1) % len(ACCENTS)]
        c = card(tw, th, accent=acc)
        isz = int(tw * 0.62)
        c.alpha_composite(icon(nm, isz), ((tw - isz) // 2, 44))
        f, lines, lh = fit_text(label, tw - 28, 80, start=30, min_size=18)
        tb = text_block(lines, f, lh, NAVY, "center", width=tw - 8)
        c.alpha_composite(tb, (4, 44 + isz + 10))
        put(v.elements, c, x0 + i * (tw + gap), y0, t_in=99, anim="pop")
        v.item_idx.append(len(v.elements) - 1)
    return v


def v_bullets(items, title=None):
    items = items[:6]
    n = len(items)
    v = Visual("bullets", layout="split", pose="point", n_items=n)
    rows_h = min(86, (PH - 150) // max(n, 1))
    h = rows_h * n + (96 if title else 40) + 30
    w = PW - 20
    base = card(w, h, accent=ACCENTS[4])
    d = ImageDraw.Draw(base)
    y = 40
    if title:
        d.text((40, 38), title, font=font(34, "bold"), fill=NAVY)
        y = 100
    x0, y0 = PANEL[0] + 10, PANEL[1] + (PH - h) // 2
    put(v.elements, base, x0, y0, t_in=0.05, anim="pop")
    for i, it in enumerate(items):
        acc = ACCENTS[i % len(ACCENTS)]
        rw = w - 60
        f, lines, lh = fit_text(it, rw - 110, rows_h - 12, start=36, min_size=20, weight="semibold", spacing=1.1)
        row = Image.new("RGBA", (rw, rows_h), (0, 0, 0, 0))
        rd = ImageDraw.Draw(row)
        rd.rounded_rectangle((0, 4, rw - 1, rows_h - 4), 22, fill=tint(acc, 0.22))
        rd.ellipse((14, rows_h // 2 - 25, 64, rows_h // 2 + 25), fill=acc)
        rd.text((39, rows_h // 2 + 1), str(i + 1), font=font(28, "bold"), fill=WHITE, anchor="mm")
        ty = (rows_h - lh * len(lines)) // 2
        for k, l in enumerate(lines):
            rd.text((84, ty + k * lh + 2), l, font=f, fill=NAVY)
        v.elements.append(Element(row, x0 + 30, y0 + y + i * rows_h, t_in=99, anim="rise", dur=0.35))
        v.item_idx.append(len(v.elements) - 1)
    return v


def v_stat(number, label=None, color=1):
    v = Visual("stat", layout="split", pose="present")
    acc = ACCENTS[color % len(ACCENTS)]
    f, lines, lh = fit_text(number, PW - 140, 230, start=150, min_size=60)
    w = PW - 60
    lab_h = 0
    if label:
        lf, ll, llh = fit_text(label, w - 80, 120, start=40, min_size=22, weight="semibold")
        lab_h = llh * len(ll) + 20
    h = lh * len(lines) + lab_h + 100
    c = card(w, h, accent=acc)
    d = ImageDraw.Draw(c)
    y = 62
    for l in lines:
        tw = d.textlength(l, font=f)
        d.text(((w - tw) / 2, y), l, font=f, fill=acc)
        y += lh
    if label:
        for l in ll:
            tw = d.textlength(l, font=lf)
            d.text(((w - tw) / 2, y + 6), l, font=lf, fill=NAVY)
            y += llh
    put(v.elements, c, PANEL[0] + 30, PANEL[1] + (PH - h) // 2, t_in=0.1, anim="pop")
    return v


def v_quote(text, who=None):
    v = Visual("quote", layout="split", pose="present")
    w = PW - 20
    f, lines, lh = fit_text(text, w - 150, 300, start=50, min_size=26, weight="semibold")
    h = lh * len(lines) + 140 + (50 if who else 0)
    c = card(w, h, accent=ACCENTS[3])
    d = ImageDraw.Draw(c)
    d.text((38, 30), "“", font=font(150, "bold"), fill=tint(ACCENTS[3], 0.5))
    y = 82
    for l in lines:
        d.text((90, y), l, font=f, fill=NAVY)
        y += lh
    if who:
        d.text((90, y + 14), "— " + who, font=font(28, "medium"), fill=MUTED)
    put(v.elements, c, PANEL[0] + 10, PANEL[1] + (PH - h) // 2, t_in=0.1, anim="pop")
    return v


def v_compare(left_title, left_items, right_title, right_items):
    v = Visual("compare", layout="split", pose="present")
    n = min(max(len(left_items), len(right_items), 1), 4)
    gap = 24
    cw = (PW - gap) // 2
    rows_h = min(88, (PH - 220) // n)
    ch = 130 + rows_h * n
    y0 = PANEL[1] + (PH - ch) // 2
    sides = [(left_title, left_items, RED, "cross", tint(RED, 0.16)), (right_title, right_items, GREEN, "check", tint(GREEN, 0.16))]
    for si, (ttl, its, acc, ic, soft) in enumerate(sides):
        c = card(cw, ch, accent=acc)
        d = ImageDraw.Draw(c)
        f, ls, lh = fit_text(ttl, cw - 110, 70, start=36, min_size=20)
        d.text((86, 40), ls[0], font=f, fill=NAVY)
        c.alpha_composite(icon(ic, 54), (22, 36))
        put(v.elements, c, PANEL[0] + si * (cw + gap), y0, t_in=0.1 + si * 0.45, anim="pop")
        for i, it in enumerate(its[:n]):
            ff, lines, llh = fit_text(it, cw - 90, rows_h - 12, start=30, min_size=18, weight="semibold", spacing=1.1)
            row = Image.new("RGBA", (cw - 40, rows_h), (0, 0, 0, 0))
            rd = ImageDraw.Draw(row)
            rd.rounded_rectangle((0, 4, cw - 41, rows_h - 4), 20, fill=soft)
            ty = (rows_h - llh * len(lines)) // 2
            for k, l in enumerate(lines):
                rd.text((22, ty + k * llh + 2), l, font=ff, fill=NAVY)
            v.elements.append(Element(row, PANEL[0] + si * (cw + gap) + 20, y0 + 110 + i * rows_h, t_in=0.35 + si * 0.45 + i * 0.3, anim="rise"))
    return v


def _arrow(d, p0, p1, color, w=10, head=22):
    d.line([p0, p1], fill=color, width=w)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    pts = [p1, (p1[0] - head * math.cos(ang - 0.45), p1[1] - head * math.sin(ang - 0.45)),
           (p1[0] - head * math.cos(ang + 0.45), p1[1] - head * math.sin(ang + 0.45))]
    d.polygon(pts, fill=color)


def v_loop(nodes, title=None):
    nodes = nodes[:5]
    n = len(nodes)
    v = Visual("loop", layout="split", pose="point", n_items=n)
    size = min(PW, PH) - 30
    cx, cy = PANEL[0] + PW // 2, PANEL[1] + PH // 2
    R = size * 0.41
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(ring)
    c0 = size / 2
    pos = []
    for i in range(n):
        a = -math.pi / 2 + i * 2 * math.pi / n
        pos.append((c0 + R * math.cos(a), c0 + R * math.sin(a), a))
    for i in range(n):
        x0, y0, a0 = pos[i]
        x1, y1, a1 = pos[(i + 1) % n]
        s0, s1 = a0 + 0.42, (a1 if a1 > a0 else a1 + 2 * math.pi) - 0.42
        pts = [(c0 + R * math.cos(s0 + (s1 - s0) * k / 14), c0 + R * math.sin(s0 + (s1 - s0) * k / 14)) for k in range(15)]
        d.line(pts, fill=tint(ACCENTS[i % len(ACCENTS)], 0.7), width=12, joint="curve")
        _arrow(d, pts[-2], pts[-1], tint(ACCENTS[i % len(ACCENTS)], 0.7), 12, 30)
    if title:
        f, lines, lh = fit_text(title, size * 0.30, 120, start=30, min_size=18)
        tb = text_block(lines, f, lh, NAVY, "center", width=int(size * 0.32))
        cw_, ch_ = tb.width + 40, tb.height + 30
        cc = card(cw_, ch_, radius=ch_ // 2 if len(lines) == 1 else 40)
        cc.alpha_composite(tb, (20, 12))
        ring.alpha_composite(cc, (int(c0 - cw_ / 2), int(c0 - ch_ / 2)))
    put(v.elements, ring, cx - size // 2, cy - size // 2, t_in=0.05, anim="fade")
    for i, label in enumerate(nodes):
        x, y, _ = pos[i]
        f, lines, lh = fit_text(label, 190, 90, start=30, min_size=18)
        tw = max(ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength(l, font=f) for l in lines)
        w, h = int(tw) + 54, lh * len(lines) + 34
        c = card(w, h, fill=tint(ACCENTS[i % len(ACCENTS)], 0.9) + (255,), radius=h // 2, border=ACCENTS[i % len(ACCENTS)])
        tb = text_block(lines, f, lh, NAVY, "center", width=w - 8)
        c.alpha_composite(tb, (4, 8))
        put(v.elements, c, cx - size / 2 + x - w / 2, cy - size / 2 + y - h / 2, t_in=99, anim="pop")
        v.item_idx.append(len(v.elements) - 1)
    return v


def v_steps(items, title=None):
    """Ascending staircase: each step reveals in turn."""
    items = items[:5]
    n = len(items)
    v = Visual("steps", layout="split", pose="point", n_items=n)
    gap = 14
    sw = (PW - gap * (n - 1) - 20) // n
    base_y = PANEL[1] + PH - 20
    if title:
        f, ls, lh = fit_text(title, PW - 40, 70, start=38, min_size=22)
        tb = text_block(ls, f, lh, NAVY, "left")
        pill = card(tb.width + 56, tb.height + 22, radius=(tb.height + 22) // 2)
        pill.alpha_composite(tb, (28, 8))
        put(v.elements, pill, PANEL[0] + 10, PANEL[1] + 6, t_in=0.05, anim="pop")
    top_room = 90 if title else 20
    for i, it in enumerate(items):
        acc = ACCENTS[i % len(ACCENTS)]
        h = int(150 + (PH - top_room - 190) * (i / max(n - 1, 1)))
        c = card(sw, h, fill=tint(acc, 0.2) + (255,), radius=26, accent=acc)
        d = ImageDraw.Draw(c)
        d.ellipse((sw // 2 - 26, 34, sw // 2 + 26, 86), fill=acc)
        d.text((sw // 2, 61), str(i + 1), font=font(30, "bold"), fill=WHITE, anchor="mm")
        f, lines, lh = fit_text(it, sw - 24, h - 110, start=30, min_size=16, weight="semibold", spacing=1.1)
        tb = text_block(lines, f, lh, NAVY, "center", width=sw - 8)
        c.alpha_composite(tb, (4, 98))
        put(v.elements, c, PANEL[0] + 10 + i * (sw + gap), base_y - h, t_in=99, anim="rise")
        v.item_idx.append(len(v.elements) - 1)
    return v


def v_graph(title, values, labels=None, color=0, unit=""):
    """Animated line chart that draws itself left to right."""
    v = Visual("graph", layout="split", pose="point")
    w, h = PW - 20, PH - 60
    c = card(w, h, accent=ACCENTS[color % len(ACCENTS)])
    d = ImageDraw.Draw(c)
    d.text((40, 36), title, font=font(32, "bold"), fill=NAVY)
    gx0, gy0, gx1, gy1 = 90, 120, w - 50, h - 80
    for k in range(5):
        y = gy0 + (gy1 - gy0) * k / 4
        d.line((gx0, y, gx1, y), fill=(226, 228, 242), width=2)
    d.line((gx0, gy0, gx0, gy1), fill=MUTED, width=4)
    d.line((gx0, gy1, gx1, gy1), fill=MUTED, width=4)
    put(v.elements, c, PANEL[0] + 10, PANEL[1] + 30, t_in=0.05, anim="pop")
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = [(gx0 + 30 + (gx1 - gx0 - 60) * i / max(len(values) - 1, 1), gy1 - 30 - (gy1 - gy0 - 70) * (val - lo) / span)
           for i, val in enumerate(values)]
    line = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(line)
    acc = ACCENTS[color % len(ACCENTS)]
    ld.polygon(pts + [(pts[-1][0], gy1), (pts[0][0], gy1)], fill=tint(acc, 0.2) + (255,))
    ld.line(pts, fill=acc, width=10, joint="curve")
    for (x, y) in pts:
        ld.ellipse((x - 11, y - 11, x + 11, y + 11), fill=WHITE, outline=acc, width=6)
    if labels:
        for (x, y), lb in zip(pts, labels):
            tw = ld.textlength(lb, font=font(22, "medium"))
            ld.text((x - tw / 2, gy1 + 14), lb, font=font(22, "medium"), fill=MUTED)
    v.elements.append(Element(line, PANEL[0] + 10, PANEL[1] + 30, t_in=0.6, anim="wipe", dur=1.6))
    return v


def v_image(path, caption=None):
    """A picture in a tilted white frame (local file, or a placeholder if missing)."""
    v = Visual("image", layout="split", pose="present")
    box_w, box_h = PW - 80, PH - 120
    if path and os.path.exists(path):
        im = Image.open(path).convert("RGB")
        im.thumbnail((box_w, box_h), Image.LANCZOS)
    else:
        im = Image.new("RGB", (box_w, box_h), (214, 226, 252))
        ImageDraw.Draw(im).text((box_w // 2, box_h // 2), "image", font=font(40), fill=MUTED, anchor="mm")
    pad = 22
    fr = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2 + (70 if caption else 0)), (255, 255, 255, 255))
    fr.paste(im, (pad, pad))
    if caption:
        f, lines, lh = fit_text(caption, fr.width - 40, 60, start=30, min_size=18, weight="medium")
        ImageDraw.Draw(fr).text((fr.width // 2, im.height + pad + 40), lines[0], font=f, fill=NAVY, anchor="mm")
    rot = fr.rotate(-2.2, resample=Image.BICUBIC, expand=True)
    put(v.elements, rot, PANEL[0] + (PW - rot.width) // 2, PANEL[1] + (PH - rot.height) // 2, t_in=0.1, anim="pop")
    return v


def v_none():
    return Visual("none", layout="center", pose="rest")
