"""Tiny drawing toolkit on top of skia-python: outlined flat-colour shapes, text with outline, easing helpers.
Everything is drawn in the thick-ink "cartoon" look: flat fills, one bold dark outline, no gradients on characters."""
import math
from pathlib import Path
import numpy as np
import skia

ASSETS = Path(__file__).resolve().parent.parent / "assets"
INK = (52, 36, 66)


def C(c, a=255):
    return skia.Color(int(c[0]), int(c[1]), int(c[2]), int(a))


def mix(a, b, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def shade(c, k):
    """k>0 lighter, k<0 darker (and a bit cooler so shadows stay colourful)."""
    if k >= 0:
        return mix(c, (255, 255, 255), k)
    return mix(c, (int(c[0] * 0.3), int(c[1] * 0.3), int(c[2] * 0.5 + 14)), -k)


def fill_paint(c, a=255):
    p = skia.Paint(AntiAlias=True, Color=C(c, a))
    p.setStyle(skia.Paint.kFill_Style)
    return p


def line_paint(c, w, a=255, cap=skia.Paint.kRound_Cap):
    p = skia.Paint(AntiAlias=True, Color=C(c, a))
    p.setStyle(skia.Paint.kStroke_Style)
    p.setStrokeWidth(w)
    p.setStrokeCap(cap)
    p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


def ease_out(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def ease_io(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def back_out(p, c=1.9):
    p = max(0.0, min(1.0, p))
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def lerp(a, b, k):
    return a + (b - a) * k


def hash01(k, salt=0):
    n = (int(k) * 374761393 + int(salt) * 668265263 + 1442695040888963407) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    n ^= n >> 16
    return (n & 0xFFFFFF) / float(0x1000000)


# ------------------------------------------------------------------ shapes
def poly_path(pts, closed=True):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if closed:
        p.close()
    return p


def squircle_pts(cx, cy, rx, ry, n=2.7, steps=96, bottom_flat=0.0):
    pts = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        c, s = math.cos(a), math.sin(a)
        x = rx * math.copysign(abs(c) ** (2 / n), c)
        y = ry * math.copysign(abs(s) ** (2 / n), s)
        if y > 0:
            y *= 1 - bottom_flat * 0.0
        pts.append((cx + x, cy + y))
    return pts


def smooth_closed(pts, tension=0.5):
    """Catmull-Rom style closed curve through points -> skia path of cubics."""
    n = len(pts)
    p = skia.Path()
    p.moveTo(*pts[0])
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3 * 2 * 0.5 * 1.0, p1[1] + (p2[1] - p0[1]) * tension / 3 * 2 * 0.5 * 1.0)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3 * 2 * 0.5 * 1.0, p2[1] - (p3[1] - p1[1]) * tension / 3 * 2 * 0.5 * 1.0)
        p.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    p.close()
    return p


def smooth_open(pts, tension=0.5):
    n = len(pts)
    p = skia.Path()
    p.moveTo(*pts[0])
    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        p.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    return p


def outlined(cv, path, color, ow=4.0, ink=INK, a=255):
    """Flat fill + bold ink outline (the outline is centred on the edge)."""
    cv.drawPath(path, fill_paint(color, a))
    if ow > 0:
        cv.drawPath(path, line_paint(ink, ow, a))


def outlined_oval(cv, cx, cy, rx, ry, color, ow=4.0, ink=INK):
    r = skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry)
    cv.drawOval(r, fill_paint(color))
    if ow > 0:
        cv.drawOval(r, line_paint(ink, ow))


def outlined_round_rect(cv, x0, y0, x1, y1, r, color, ow=4.0, ink=INK):
    rr = skia.Rect.MakeLTRB(x0, y0, x1, y1)
    cv.drawRoundRect(rr, r, r, fill_paint(color))
    if ow > 0:
        cv.drawRoundRect(rr, r, r, line_paint(ink, ow))


def tube(cv, pts, w, color, ow=4.0, ink=INK):
    """A thick rounded limb along a polyline: ink stroke underneath, colour stroke on top."""
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if ow > 0:
        cv.drawPath(p, line_paint(ink, w + ow * 2))
    cv.drawPath(p, line_paint(color, w))


# ------------------------------------------------------------------ text
_FONTS = {}


def font(name, size):
    key = (name, round(size, 1))
    if key not in _FONTS:
        f = {"hand": "GochiHand-Regular.ttf", "bold": "Fredoka.ttf"}[name]
        tf = skia.Typeface.MakeFromFile(str(ASSETS / "fonts" / f))
        fo = skia.Font(tf, size)
        fo.setEdging(skia.Font.Edging.kAntiAlias)
        fo.setSubpixel(True)
        _FONTS[key] = fo
    return _FONTS[key]


def text_width(txt, name, size):
    return font(name, size).measureText(txt)


def draw_text(cv, txt, x, y, name, size, color, ow=0.0, ink=INK, align="center"):
    """Text with an optional thick outline. (x, y) is the baseline anchor."""
    fo = font(name, size)
    w = fo.measureText(txt)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    blob = skia.TextBlob.MakeFromString(txt, fo)
    if ow > 0:
        cv.drawTextBlob(blob, x, y, line_paint(ink, ow))
    cv.drawTextBlob(blob, x, y, fill_paint(color))


def wrap_text(txt, name, size, max_w):
    words, lines, cur = txt.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_width(t, name, size) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------ images
_IMG = {}


def load_image(path):
    path = str(path)
    if path not in _IMG:
        _IMG[path] = skia.Image.open(path)
    return _IMG[path]


def sticker(cv, img, cx, cy, size, rot=0.0, ow=5.0, border=7.0, paper=(255, 255, 255)):
    """An icon with a white sticker border and a dark outline, like a die-cut sticker."""
    w, h = img.width(), img.height()
    s = size / max(w, h)
    cv.save()
    cv.translate(cx, cy)
    cv.rotate(rot)
    cv.scale(s, s)
    # silhouette -> dilated copies for the white border and ink outline
    sil = skia.Paint(AntiAlias=True)
    for rad, col in ((border + ow) / s, INK), (border / s, paper):
        sil.setColorFilter(skia.ColorFilters.Blend(C(col), skia.BlendMode.kSrcIn))
        sil.setImageFilter(skia.ImageFilters.Dilate(rad, rad))
        cv.drawImage(img, -w / 2, -h / 2, skia.SamplingOptions(skia.FilterMode.kLinear), sil)
    cv.drawImage(img, -w / 2, -h / 2, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(AntiAlias=True))
    cv.restore()


def surface(w, h):
    return skia.Surface(w, h)


def to_rgb(surf):
    img = surf.makeImageSnapshot()
    arr = img.toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)
    return np.ascontiguousarray(arr[:, :, :3])
