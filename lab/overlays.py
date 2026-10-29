"""Text-based overlays: captions (with the spoken word lit up), label chips, big numbers, comparison bars, title cards."""
import functools, math
from PIL import Image, ImageDraw, ImageFilter
from .fonts import font

W, H = 1280, 720
ACCENTS = [(255, 206, 74), (92, 214, 255), (255, 112, 160), (140, 240, 170), (190, 150, 255), (255, 150, 90)]
INK = (24, 22, 50)

_probe = ImageDraw.Draw(Image.new("RGB", (4, 4)))


def tw(text, f):
    return _probe.textlength(text, font=f)


def wrap(text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if cur and tw(t, f) > maxw:
            lines.append(cur); cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines or [""]


def chunk_words(words, max_chars=58, max_words=11):
    """Split a sentence (list of words) into caption chunks that fit two lines."""
    chunks, cur, n = [], [], 0
    for i, w in enumerate(words):
        if cur and (n + 1 + len(w) > max_chars or len(cur) >= max_words):
            chunks.append(cur); cur, n = [], 0
        cur.append((i, w)); n += len(w) + 1
        if w.endswith((",", ";", ":")) and n > 26:
            chunks.append(cur); cur, n = [], 0
    if cur:
        if chunks and len(cur) <= 2 and sum(len(w) for _, w in cur) < 12:
            chunks[-1] += cur
        else:
            chunks.append(cur)
    return chunks


@functools.lru_cache(maxsize=2048)
def caption_img(words, hi, width=1060, size=38):
    """words: tuple of strings in the chunk, hi: index of the word being spoken (-1 for none)."""
    f = font(size, "semibold")
    sp = tw(" ", f)
    # lay out into lines
    lines, cur, cw = [], [], 0
    for i, w in enumerate(words):
        ww = tw(w, f)
        if cur and cw + sp + ww > width - 70:
            lines.append(cur); cur, cw = [], 0
        cur.append((i, w, ww)); cw += (sp if len(cur) > 1 else 0) + ww
    if cur:
        lines.append(cur)
    lh = int(size * 1.32)
    h = lh * len(lines) + 30
    im = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    maxw = max(sum(w for _, _, w in ln) + sp * (len(ln) - 1) for ln in lines)
    bx0 = (width - maxw) / 2 - 28
    d.rounded_rectangle((bx0, 0, bx0 + maxw + 56, h - 1), 26, fill=(14, 14, 36, 188))
    for li, ln in enumerate(lines):
        total = sum(w for _, _, w in ln) + sp * (len(ln) - 1)
        x = (width - total) / 2
        y = 15 + li * lh
        for i, w, ww in ln:
            col = (255, 214, 84, 255) if i == hi else (255, 255, 255, 255)
            d.text((x, y), w, font=f, fill=col)
            x += ww + sp
    return im


@functools.lru_cache(maxsize=256)
def chip_img(text, color=(255, 206, 74), size=26, dark=True):
    f = font(size, "semibold")
    w = int(tw(text.upper(), f)) + 46
    h = int(size * 1.75)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=tuple(color) + (240,))
    d.text((23, h * 0.15), text.upper(), font=f, fill=INK + (255,) if dark else (255, 255, 255, 255))
    return im


@functools.lru_cache(maxsize=256)
def label_img(text, color=(255, 255, 255), size=34):
    """Floating label with soft shadow (used next to entities)."""
    f = font(size, "semibold")
    w = int(tw(text, f)) + 40
    h = int(size * 1.8)
    im = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((10, 12, w + 10, h + 12), h // 2, fill=(0, 0, 0, 120))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 10, w + 10, h + 10), h // 2, fill=(20, 22, 48, 235))
    d.text((30, 10 + h * 0.14), text, font=f, fill=tuple(color) + (255,))
    return im


def outlined(text, size, fill=(255, 255, 255), stroke=INK, sw=None, weight="bold", spacing=0):
    f = font(size, weight)
    sw = sw if sw is not None else max(2, size // 12)
    lines = text.split("\n")
    wd = int(max(tw(l, f) for l in lines)) + sw * 2 + 8
    lh = int(size * 1.18)
    im = Image.new("RGBA", (wd, lh * len(lines) + sw * 2 + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        x = (wd - tw(l, f)) / 2
        d.text((x, sw + 2 + i * lh), l, font=f, fill=tuple(fill) + (255,), stroke_width=sw, stroke_fill=tuple(stroke) + (255,))
    return im


@functools.lru_cache(maxsize=256)
def big_text(text, size=84, color=(255, 255, 255), maxw=1000):
    f = font(size, "bold")
    lines = wrap(text, f, maxw)
    return outlined("\n".join(lines), size, color)


def stat_img(display, sub="", color=(255, 206, 74), size=120):
    """A huge number with a small caption under it."""
    num = outlined(display, size, color, (20, 18, 44), sw=max(4, size // 10))
    if num.width > 1100:
        size = int(size * 1100 / num.width)
        num = outlined(display, size, color, (20, 18, 44), sw=max(4, size // 10))
    if not sub:
        return num
    s = chip_img(sub, (255, 255, 255), 26)
    im = Image.new("RGBA", (max(num.width, s.width), num.height + s.height + 6), (0, 0, 0, 0))
    im.alpha_composite(num, ((im.width - num.width) // 2, 0))
    im.alpha_composite(s, ((im.width - s.width) // 2, num.height + 6))
    return im


def bars_img(items, width=900, prog=1.0, unit=""):
    """items: [(label, value, color)] -> horizontal bars growing to `prog` (0..1)."""
    mx = max(v for _, v, _ in items) or 1
    rowh = 78
    im = Image.new("RGBA", (width, rowh * len(items) + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(30, "semibold")
    for i, (lab, v, col) in enumerate(items):
        y = 8 + i * rowh
        d.text((0, y + 4), lab, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=INK + (255,))
        x0 = 250
        full = (width - x0 - 20) * v / mx
        cur = max(14, full * min(1.0, prog))
        d.rounded_rectangle((x0, y, x0 + cur, y + 52), 26, fill=tuple(col) + (255,))
        d.rounded_rectangle((x0 + 6, y + 6, x0 + cur - 6, y + 22), 12, fill=(255, 255, 255, 70))
    return im


@functools.lru_cache(maxsize=64)
def title_card(title, sub="YUKI LAB", w=W, h=H):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    t = big_text(title, 92, (255, 255, 255), 1040)
    im.alpha_composite(t, ((w - t.width) // 2, int(h * 0.42 - t.height / 2)))
    if sub:
        c = chip_img(sub, ACCENTS[0], 28)
        im.alpha_composite(c, ((w - c.width) // 2, int(h * 0.42 - t.height / 2) - 70))
    return im


@functools.lru_cache(maxsize=8)
def vignette(w=W, h=H, strength=0.55):
    import numpy as np
    y, x = np.mgrid[0:h, 0:w]
    dx, dy = (x - w / 2) / (w / 2), (y - h / 2) / (h / 2)
    d = np.sqrt(dx * dx * 0.8 + dy * dy)
    a = np.clip((d - 0.62) / 0.9, 0, 1) ** 1.6 * 255 * strength
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def paste(frame, im, x, y, alpha=1.0):
    """alpha-composite im on frame (RGBA) at (x, y) with clipping and an optional fade."""
    x, y = int(round(x)), int(round(y))
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda v, k=max(0.0, alpha): int(v * k))
        im = im.copy(); im.putalpha(a)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(frame.width, x + im.width), min(frame.height, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    frame.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))
