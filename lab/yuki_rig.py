"""Yuki: a chibi narrator drawn entirely in code (Pillow), rigged for talking, blinking, gesturing and reacting.

v2 (Nov 2026)
  * the head is built from cached layers (hair+face, blush, eyes, brows, mouth, effects) so every face has real eyebrows, glossy eyes that
    look where she looks, half-blinks, and the features slide a little when she "turns" her head
  * arms are tapered and jointed (shoulder -> elbow -> wrist), hands are real hands (mitten with thumb, open palm, pointing finger, fist, thumbs-up)
  * NO pose ever puts a hand on or near the face: the old facepalm / head / think / sob / gasp_hands names still work, they are aliases
    of poses that keep the hands at the chest (see ALIASES / resolve_pose)
  * life: breathing, weight shift, idle sway, saccades, irregular (sometimes double) blinks, beat gestures that follow the voice, overshoot
    when a pose changes, squash and stretch on hops, a lively scarf tail.  Everything is stateless: frames depend only on the arguments.

Design space: figure canvas 480 x 700 units, feet at y=660, neck at (240, 330).  Everything is drawn 3x supersampled at the final size.
"""
import functools, math
from dataclasses import dataclass
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import yuki_motion as M

SS = 3
FW, FH = 480, 700
HW, HH = 400, 380            # head canvas (units)
HEAD_POS = (40, 10)          # head canvas top-left on the figure canvas
NECK = (240, 330)            # rotation pivot for the head (figure coords)
SHOULDER = {"L": (164, 378), "R": (316, 378)}
UPPER, FORE = 58, 54
EYE_Y = 234                  # eye line (head units); the brows sit between the fringe (y 179) and the eyes (y 204)
BROW_Y = 194
MOUTH = (200, 292)

INK = (40, 32, 44)
HAIR = (70, 44, 42)
HAIR_HI = (92, 98, 124)
SKIN = (255, 225, 204)
SKIN_SH = (238, 196, 170)
BLUSH = (246, 150, 150)
GREEN, GREEN_D, GREEN_L = (112, 168, 116), (86, 140, 98), (138, 186, 132)
RED, RED_D, RED_L = (222, 64, 72), (170, 40, 52), (240, 110, 110)
SKIRT = (72, 66, 90)
CREAM = (244, 236, 218)
MOUTH_IN, TONGUE = (112, 34, 48), (238, 120, 132)
EYE = (56, 36, 46)
IRIS = (128, 84, 108)
LASH = (56, 36, 46)
BROW = (72, 50, 58)
WHITE = (255, 255, 255)
CLIP, CLIP_C = (214, 72, 78), (252, 232, 208)


@dataclass(frozen=True)
class Look:
    """Everything that makes one character different from another."""
    hair: tuple = (36, 34, 46)
    skin: tuple = (255, 224, 200)
    top: tuple = (108, 160, 108)
    top_d: tuple = (84, 134, 90)
    sleeve: tuple = (98, 150, 100)
    bottom: tuple = (52, 48, 64)
    legs: tuple = (36, 34, 46)
    shoes: tuple = (34, 32, 42)
    scarf: tuple = (222, 64, 72)        # None = no scarf
    clip: tuple = None                  # None = no hair clip
    skirt: bool = True
    style: str = "bob"                  # bob | long | boy | bun
    blush: tuple = (248, 172, 172)


YUKI = Look()


def shade(c, k):
    """k < 1 darker, k > 1 lighter."""
    if k <= 1:
        return tuple(int(v * k) for v in c)
    return tuple(min(255, int(v + (255 - v) * (k - 1))) for v in c)


# ------------------------------------------------------------------ drawing context
class Cv:
    """A supersampled canvas that is drawn in *units*.  Layer images are placed in pixel space (units * s), and the canvas snaps to that grid,
    so layers drawn separately always line up exactly."""

    def __init__(self, x0, y0, x1, y1, s):
        self.s = s
        self.S = s * SS
        self.ix, self.iy = int(math.floor(x0 * s)), int(math.floor(y0 * s))
        self.w = max(1, int(math.ceil(x1 * s)) - self.ix)
        self.h = max(1, int(math.ceil(y1 * s)) - self.iy)
        self.im = Image.new("RGBA", (self.w * SS, self.h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def p(self, x, y):
        return ((x * self.s - self.ix) * SS, (y * self.s - self.iy) * SS)

    def box(self, b):
        return [*self.p(b[0], b[1]), *self.p(b[2], b[3])]

    def ell(self, b, fill):
        self.d.ellipse(self.box(b), fill=fill)

    def poly(self, pts, fill):
        self.d.polygon([self.p(*q) for q in pts], fill=fill)

    def line(self, pts, fill, w):
        P = [self.p(*q) for q in pts]
        wp = max(1.0, w * self.S)
        self.d.line(P, fill=fill, width=int(round(wp)), joint="curve")
        r = wp / 2
        for (x, y) in (P[0], P[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def arc(self, b, a0, a1, fill, w):
        self.d.arc(self.box(b), a0, a1, fill=fill, width=max(1, int(round(w * self.S))))

    def pie(self, b, a0, a1, fill):
        self.d.pieslice(self.box(b), a0, a1, fill=fill)

    def rrect(self, b, r, fill):
        self.d.rounded_rectangle(self.box(b), radius=r * self.S, fill=fill)

    def rect(self, b, fill):
        self.d.rectangle(self.box(b), fill=fill)

    def capsule(self, a, b, w, fill):
        self.line([a, b], fill, w)

    def out(self):
        return self.im.reduce(SS)

    def result(self):
        return (self.out(), self.ix, self.iy)


def _bez(p0, p1, p2, p3, n=18):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _qbez(p0, p1, p2, n=10):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]


# ================================================================== HEAD LAYERS
def _bell(cv, bottom, fill, long=False, x0=34, tuck=0):
    """The hair mass behind the head.  x0 = how far it reaches out at the sides; tuck = how far the bottom curls in under the jaw."""
    inset = 8 if long else 22
    top_y = 150
    L = []
    L += _bez((x0, top_y), (x0 - 4, top_y + 56), (x0 - 4, bottom - 90), (x0 + inset * .5, bottom - 52), 16)
    L += _bez((x0 + inset * .5, bottom - 52), (x0 + 2 + inset, bottom - 14), (x0 + 26 + inset + tuck, bottom + 2), (104 + tuck, bottom + 2), 14)
    R = [(400 - x, y) for x, y in L]
    cv.poly(L + R[::-1], fill)


def _side_locks(cv, fill):
    """Two locks that come down from the fringe along the face edge and curl in at the jaw: the hair frames the face instead of floating round it."""
    for sgn in (1, -1):
        def X(x):
            return x if sgn == 1 else 400 - x
        pts = _bez((X(84), 150), (X(70), 200), (X(76), 262), (X(104), 296), 14)
        pts += _bez((X(104), 296), (X(118), 300), (X(122), 284), (X(116), 262), 8)
        pts += _bez((X(116), 262), (X(110), 224), (X(110), 190), (X(126), 156), 10)
        cv.poly(pts, fill)


@functools.lru_cache(maxsize=8)
def _base_layer(look, s):
    """Hair + face + fringe, with a soft shadow under the fringe."""
    cv = Cv(0, 0, HW, HH, s)
    H_, SK = look.hair, look.skin
    bottom = {"bob": 306, "long": 372, "boy": 250, "bun": 300}[look.style]
    bob = look.style == "bob"
    cv.ell((50, 24, 350, 296) if bob else (34, 22, 366, 300), H_)
    if look.style == "boy":
        cv.rrect((40, 150, 360, 250), 40, H_)
    else:
        _bell(cv, bottom, H_, long=(look.style == "long"), x0=50 if bob else 34, tuck=10 if bob else 0)
    if look.style == "bun":
        cv.ell((152, -6, 248, 54), H_)
    cv.ell((82, 104, 318, 318), SK)
    # soft shadow the fringe throws on the forehead (clipped to the face)
    sh = Cv(0, 0, HW, HH, s)
    SROW = 153
    if look.style == "boy":
        sh.poly([(60, 150), (340, 150), (330, 181), (280, 197), (230, 177), (190, 191), (140, 181), (80, 195), (64, 181)], shade(SK, 0.9))
    else:
        for x in (96, 138, 180, 220, 262, 304):
            sh.ell((x - 26, SROW - 20, x + 26, SROW + 32), shade(SK, 0.9))
    fm = Cv(0, 0, HW, HH, s)
    fm.ell((82, 104, 318, 318), (255, 255, 255, 255))
    a = sh.im.getchannel("A")
    a = ImageChops.multiply(a, fm.im.getchannel("A"))
    sh.im.putalpha(a)
    cv.im.alpha_composite(sh.im)
    # fringe: dome + a row of soft scallops (boys: a flat swoosh)
    cx, cy, a_, b_ = 200, 161, (150 if bob else 166), 139
    cv.poly([(cx + a_ * math.cos(math.radians(t)), cy + b_ * math.sin(math.radians(t))) for t in range(180, 361, 4)], H_)
    if look.style == "boy":
        cv.poly([(60, 150), (340, 150), (330, 176), (280, 192), (230, 172), (190, 186), (140, 176), (80, 190), (64, 176)], H_)
    else:
        for x in (96, 138, 180, 220, 262, 304):
            cv.ell((x - 26, SROW - 26, x + 26, SROW + 26), H_)
        cv.rect((62, 142, 338, 160), H_)
    if bob:
        _side_locks(cv, H_)
    if sum(look.hair) < 260 and look.style != "boy":
        g = tuple(min(255, c + 30) for c in look.hair)
        cv.arc((92, 56, 252, 156), 205, 262, g, 8)
        cv.arc((106, 72, 238, 146), 208, 255, g, 4)
    if look.clip:
        cv.ell((270, 44, 306, 80), look.clip)
        cv.ell((281, 55, 295, 69), CLIP_C)
    return cv.result()


@functools.lru_cache(maxsize=16)
def _blush_layer(look, flush, s):
    cv = Cv(70, 250, 330, 300, s)
    col = shade(look.blush, 0.93) if flush else look.blush
    k = 1.25 if flush else 1.0
    for bx in (123, 277):
        cv.ell((bx - 25 * k, 261 - 2 * (k - 1) * 4, bx + 25 * k, 289 + 2 * (k - 1) * 4), col)
        if flush:
            for i in range(3):
                x0 = bx - 17 + i * 13
                cv.line([(x0, 266), (x0 + 8, 282)], (236, 108, 122), 3)
    return cv.result()


def _round_eye(cv, ex, ey, rx, ry, k, gx, gy, glossy=True):
    """The basic glossy chibi eye. k = how open (1 open ... 0.45 half-blink)."""
    rk = ry * k
    cx = ex + gx * 2.6
    cy = ey + gy * 2.0 + (ry - rk) * 0.55
    cv.ell((cx - rx, cy - rk, cx + rx, cy + rk), EYE)
    if not glossy or k < 0.6:
        return cx, cy
    # warm lower glow (a crescent) so the eye has depth
    cv.ell((cx - rx * 0.78 + gx * 1.0, cy - rk * 0.05, cx + rx * 0.78 + gx * 1.0, cy + rk * 0.94), IRIS)
    cv.ell((cx - rx * 0.86 + gx * 0.6, cy - rk * 0.98, cx + rx * 0.86 + gx * 0.6, cy + rk * 0.40), EYE)
    # highlights follow the gaze a bit more than the eye itself: that is what makes her look somewhere
    hx, hy = gx * 3.4, gy * 2.6
    cv.ell((cx - rx * 0.62 + hx, cy - rk * 0.72 + hy, cx + rx * 0.10 + hx, cy - rk * 0.12 + hy), WHITE)
    cv.ell((cx + rx * 0.22 + hx * 0.8, cy + rk * 0.28 + hy * 0.8, cx + rx * 0.62 + hx * 0.8, cy + rk * 0.62 + hy * 0.8), WHITE)
    return cx, cy


def _lash(cv, ex, ey, rx, ry, side, w=4):
    cv.line([(ex - side * (rx - 4), ey - ry * 0.62), (ex - side * (rx + 7), ey - ry * 0.62 - 7)], LASH, w)


def _closed_arc(cv, ex, ey, up=False, w=5):
    if up:
        cv.arc((ex - 24, ey - 8, ex + 24, ey + 20), 205, 335, LASH, w)
    else:
        cv.arc((ex - 24, ey - 12, ex + 24, ey + 12), 25, 155, LASH, w)


def _star(cv, cx, cy, r, fill):
    pts = []
    for i in range(8):
        rr = r if i % 2 == 0 else r * 0.38
        a = math.radians(-90 + i * 45)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    cv.poly(pts, fill)


@functools.lru_cache(maxsize=256)
def _eyes_layer(etype, k, gx, gy, look, s):
    """Both eyes. etype: see FACES; k: 1 open, 0.5 half blink, 0 closed; gx, gy: -1..1 where she looks."""
    cv = Cv(70, 168, 330, 316, s)
    SK = look.skin
    for cx_ in (143, 257):
        side = 1 if cx_ < 200 else -1               # +1 left eye (its inner corner is on the right)
        ex, ey = cx_, EYE_Y
        if etype in ("open", "wide", "dot", "dead", "tiny", "shy", "sleepy", "smug") and k == 0:
            _closed_arc(cv, ex, ey)
            continue
        if etype == "open":
            _round_eye(cv, ex, ey, 24, 30, k, gx, gy)
            if k > 0.6:
                _lash(cv, ex, ey, 24, 30, side)
        elif etype == "wide":
            _round_eye(cv, ex, ey, 26, 34, k, gx, gy)
            if k > 0.6:
                _lash(cv, ex, ey, 26, 34, side)
        elif etype in ("sleepy", "smug"):
            _round_eye(cv, ex, ey, 24, 32, 1.0, gx, gy)
            lid = ey + 2 if etype == "sleepy" else ey - 12
            droop = 5 if etype == "sleepy" else -3
            xo, xi = ex - 30 * side, ex + 30 * side
            cv.poly([(xo, 190), (xi, 190), (xi, lid), (xo, lid + droop)], SK)
            cv.line([(xo, lid + droop), (xi, lid)], LASH, 5)
            if etype == "sleepy":
                cv.ell((ex - 22, ey + 31, ex + 22, ey + 44), shade(SK, 0.93))
        elif etype == "tears":
            cx, cy = _round_eye(cv, ex, ey, 25, 32, 1.0, gx, gy)
            cv.ell((cx - 4, cy + 8, cx + 19, cy + 26), (176, 224, 255))      # watery shine
            for j in (0, 1):
                tx = ex + (-side) * (21 + j * 3)
                cv.ell((tx - 7, ey + 28 + j * 20, tx + 7, ey + 54 + j * 20), (140, 206, 255))
            cv.line([(ex - 28, ey - 39), (ex + 28, ey - 31)] if cx_ < 200 else [(ex - 28, ey - 31), (ex + 28, ey - 39)], LASH, 4)
        elif etype == "sparkle":
            cv.ell((ex - 28, ey - 36, ex + 28, ey + 36), EYE)
            cv.ell((ex - 22, ey + 2, ex + 22, ey + 33), IRIS)
            cv.ell((ex - 24, ey - 34, ex + 24, ey + 6), EYE)
            _star(cv, ex - 7, ey - 11, 15, WHITE)
            _star(cv, ex + 11, ey + 14, 8, WHITE)
        elif etype == "heart":
            r_ = 27
            for hx_, hy_ in ((ex, ey),):
                cv.ell((hx_ - r_, hy_ - r_ * 0.85, hx_, hy_ + r_ * 0.15), (240, 84, 120))
                cv.ell((hx_, hy_ - r_ * 0.85, hx_ + r_, hy_ + r_ * 0.15), (240, 84, 120))
                cv.poly([(hx_ - r_ * 0.98, hy_ - r_ * 0.2), (hx_ + r_ * 0.98, hy_ - r_ * 0.2), (hx_, hy_ + r_ * 1.05)], (240, 84, 120))
                cv.ell((hx_ - r_ * 0.6, hy_ - r_ * 0.6, hx_ - r_ * 0.2, hy_ - r_ * 0.25), WHITE)
        elif etype == "swirl":
            cv.ell((ex - 27, ey - 31, ex + 27, ey + 31), (250, 250, 250))
            pts = [(ex + (3 + t_ * 22) * math.cos(t_ * 17), ey + (3 + t_ * 22) * math.sin(t_ * 17)) for t_ in [i / 70 for i in range(71)]]
            cv.line(pts, EYE, 4)
        elif etype == "dot":
            cv.ell((ex - 8.5, ey - 8.5, ex + 8.5, ey + 8.5), EYE)
            cv.ell((ex - 4, ey - 5, ex - 0.5, ey - 1.5), WHITE)
        elif etype == "tiny":                                              # shock: big white eyes, tiny pupils
            cv.ell((ex - 29, ey - 38, ex + 29, ey + 38), (252, 252, 252))
            cv.ell((ex - 12 + gx * 4, ey - 12 + gy * 3, ex + 12 + gx * 4, ey + 12 + gy * 3), EYE)
            cv.ell((ex - 6 + gx * 4, ey - 8 + gy * 3, ex - 1 + gx * 4, ey - 3 + gy * 3), WHITE)
        elif etype == "lines":                                             # > <  squeezed shut
            sg = side
            cv.line([(ex - 22 * sg, ey - 18), (ex + 18 * sg, ey), (ex - 22 * sg, ey + 18)], LASH, 6)
        elif etype == "wink":
            if cx_ < 200:
                _closed_arc(cv, ex, ey, up=True, w=6)
            else:
                _round_eye(cv, ex, ey, 24, 32, k if k else 1.0, gx, gy)
                _lash(cv, ex, ey, 24, 32, side)
        elif etype == "dead":
            cv.ell((ex - 24, ey - 32, ex + 24, ey + 32), (26, 26, 36))
        elif etype == "shy":                                               # looking away, a bit smaller
            cv.ell((ex - 20 + 6, ey - 26, ex + 20 + 6, ey + 28), EYE)
            cv.ell((ex - 12 + 6, ey - 20, ex + 2 + 6, ey - 4), WHITE)
            cv.ell((ex + 8, ey + 6, ex + 18, ey + 16), WHITE)
        elif etype == "blink":
            _closed_arc(cv, ex, ey)
        elif etype == "happy":
            _closed_arc(cv, ex, ey, up=True)
    return cv.result()


# brow styles: (inner y, outer y, arch) for the viewer-left brow, same for the right brow, thickness.  Negative = up.
BROWS = {
    "neutral": ((0, 1, 3), (0, 1, 3), 5.5), "soft": ((-1, 0, 4), (-1, 0, 4), 5.5), "happy": ((-3, -1, 5), (-3, -1, 5), 5.5),
    "raised": ((-5, -4, 5), (-5, -4, 5), 5.5), "worried": ((-7, 3, 1), (-7, 3, 1), 5.5), "sad": ((-8, 4, 0), (-8, 4, 0), 5.5),
    "angry": ((5, -6, 0), (5, -6, 0), 6.5), "surprised": ((-8, -7, 6), (-8, -7, 6), 5.5), "confused": ((-8, -6, 6), (1, 2, 1), 5.5),
    "smug": ((-7, -5, 5), (3, 0, 1), 6), "flat": ((0, 0, 0), (0, 0, 0), 5.5), "scheme": ((5, -4, 2), (-7, -6, 5), 6),
    "gloom": ((-3, 4, 0), (-3, 4, 0), 5.5), "sleepy": ((3, 4, 2), (3, 4, 2), 5),
}


@functools.lru_cache(maxsize=64)
def _brow_layer(style, s):
    cv = Cv(70, 160, 330, 222, s)
    (l_, r_, th) = BROWS.get(style, BROWS["neutral"])
    for cx_, (iy, oy, arch) in ((143, l_), (257, r_)):
        side = 1 if cx_ < 200 else -1
        xi, xo = cx_ + side * 17, cx_ - side * 25
        yi, yo = BROW_Y + iy, BROW_Y + oy
        mid = ((xi + xo) / 2, (yi + yo) / 2 - arch * 1.8)
        cv.line(_qbez((xo, yo), mid, (xi, yi), 9), BROW, th)
    return cv.result()


@functools.lru_cache(maxsize=64)
def _mouth_layer(code, down, s):
    mx, my = MOUTH
    cv = Cv(mx - 50, my - 36, mx + 50, my + 44, s)
    MC = (150, 70, 80)
    if code == 0:
        if down:
            cv.arc((mx - 12, my - 1, mx + 12, my + 11), 200, 340, MC, 3.5)
        else:
            cv.arc((mx - 15, my - 12, mx + 15, my + 4), 25, 155, MC, 3.5)
    elif code == 1:                                                    # "eh": small soft oval
        cv.ell((mx - 8, my - 6, mx + 8, my + 9), MOUTH_IN)
        cv.ell((mx - 5, my + 2, mx + 5, my + 9), TONGUE)
    elif code == 2:                                                    # "ah": wide open
        cv.ell((mx - 15, my - 8, mx + 15, my + 20), MOUTH_IN)
        cv.ell((mx - 9, my + 7, mx + 9, my + 19), TONGUE)
        cv.rrect((mx - 10, my - 7, mx + 10, my - 2), 2, WHITE)
    elif code == 3:                                                    # small "mm/uh"
        cv.ell((mx - 5.5, my - 5, mx + 5.5, my + 8), MOUTH_IN)
    elif code == 4:                                                    # happy open smile
        cv.pie((mx - 17, my - 14, mx + 17, my + 16), 0, 180, MOUTH_IN)
        cv.rect((mx - 15.5, my + 1, mx + 15.5, my + 5.5), WHITE)
        cv.pie((mx - 9, my + 1, mx + 9, my + 14), 0, 180, TONGUE)
        cv.rect((mx - 17.5, my - 0.6, mx + 17.5, my + 1.4), MOUTH_IN)
    elif code == 5:                                                    # smirk
        cv.arc((mx - 6, my - 12, mx + 22, my + 4), 20, 150, MC, 3.5)
        cv.line([(mx - 12, my - 2), (mx - 6, my - 1)], MC, 3.5)
    elif code == 6:                                                    # flat / unimpressed
        cv.line([(mx - 11, my + 2), (mx + 11, my + 2)], MC, 3.5)
    elif code == 7:                                                    # gasp: round "o"
        cv.ell((mx - 13, my - 12, mx + 13, my + 22), MOUTH_IN)
        cv.ell((mx - 8, my + 6, mx + 8, my + 20), TONGUE)
    elif code == 8:                                                    # wobbly
        cv.line([(mx - 18, my + 2), (mx - 9, my - 5), (mx, my + 3), (mx + 9, my - 5), (mx + 18, my + 2)], MC, 3.5)
    elif code == 9:                                                    # big laugh
        cv.pie((mx - 27, my - 22, mx + 27, my + 26), 0, 180, MOUTH_IN)
        cv.pie((mx - 15, my - 2, mx + 15, my + 24), 0, 180, TONGUE)
        cv.rect((mx - 25, my - 3, mx + 25, my + 3), WHITE)
        cv.rect((mx - 27.5, my + 1, mx + 27.5, my + 3), MOUTH_IN)
    elif code == 10:                                                   # cat mouth  :3
        cv.arc((mx - 20, my - 14, mx, my + 6), 10, 170, MC, 3.5)
        cv.arc((mx, my - 14, mx + 20, my + 6), 10, 170, MC, 3.5)
    elif code == 11:                                                   # frown
        cv.arc((mx - 16, my - 2, mx + 16, my + 20), 205, 335, MC, 4)
    elif code == 12:                                                   # tongue out
        cv.arc((mx - 16, my - 12, mx + 16, my + 4), 25, 155, MC, 3.5)
        cv.rrect((mx - 3, my - 2, mx + 14, my + 22), 8, TONGUE)
        cv.line([(mx + 5.5, my + 1), (mx + 5.5, my + 12)], (214, 96, 110), 2)
    elif code == 13:                                                   # grit teeth
        cv.rrect((mx - 18, my - 8, mx + 18, my + 12), 5, WHITE)
        cv.rrect((mx - 18, my - 8, mx + 18, my + 12), 5, WHITE)
        cv.line([(mx - 18, my + 2), (mx + 18, my + 2)], MC, 2)
        for k_ in (-9, 0, 9):
            cv.line([(mx + k_, my - 8), (mx + k_, my + 12)], MC, 2)
    elif code == 14:                                                   # sobbing: wide wobbly
        cv.ell((mx - 16, my - 6, mx + 16, my + 20), MOUTH_IN)
        cv.arc((mx - 12, my + 4, mx + 12, my + 22), 200, 340, TONGUE, 5)
    elif code == 15:                                                   # "ee": wide and thin, teeth
        cv.rrect((mx - 20, my - 5, mx + 20, my + 8), 6, MOUTH_IN)
        cv.rect((mx - 15, my - 4, mx + 15, my), WHITE)
    elif code == 16:                                                   # "oo": small round pucker
        cv.ell((mx - 8, my - 8, mx + 8, my + 10), MOUTH_IN)
    return cv.result()


@functools.lru_cache(maxsize=32)
def _fx_layer(fx, s):
    cv = Cv(60, 90, 350, 330, s)
    if "sweat" in fx:
        cx, cy = 306, 200
        cv.poly([(cx, cy - 20), (cx - 9, cy - 2), (cx + 9, cy - 2)], (132, 198, 248))
        cv.ell((cx - 9, cy - 8, cx + 9, cy + 10), (132, 198, 248))
        cv.ell((cx - 5, cy - 4, cx - 1, cy + 2), (226, 244, 255))
    if "gloom" in fx:
        for i, x in enumerate((128, 156, 184)):
            cv.line([(x, 118), (x, 138 + (i % 2) * 14)], (122, 130, 205), 5)
    if "vein" in fx:
        cx, cy = 306, 138
        for (a, b) in (((-11, -4), (-3, -4)), ((-11, -4), (-11, -12)), ((11, -4), (3, -4)), ((11, -4), (11, -12)),
                       ((-11, 6), (-3, 6)), ((-11, 6), (-11, 14)), ((11, 6), (3, 6)), ((11, 6), (11, 14))):
            cv.line([(cx + a[0], cy + a[1]), (cx + b[0], cy + b[1])], (226, 56, 60), 3.4)
    if "lol" in fx:
        for ex_, sg in ((100, -1), (300, 1)):
            cv.ell((ex_ - 5, 236, ex_ + 5, 254), (140, 206, 255))
    return cv.result()


# ------------------------------------------------------------------ faces
# face -> (eyes, brow style, closed-mouth shape)
FACES = {
    "neutral": ("open", "neutral", 0), "smile": ("open", "soft", 0), "happy": ("happy", "happy", 0), "worried": ("wide", "worried", 0),
    "shocked": ("wide", "surprised", 2), "curious": ("wide", "confused", 3), "angry": ("open", "angry", 0), "sleepy": ("sleepy", "sleepy", 6),
    "smug": ("smug", "smug", 5), "serene": ("blink", "soft", 0), "sad": ("open", "sad", 0), "excited": ("wide", "raised", 0),
}
FACES.update({
    "laughing": ("lines", "happy", 9), "crying": ("tears", "sad", 14), "teary": ("tears", "sad", 11), "starry": ("sparkle", "happy", 4),
    "lovestruck": ("heart", "happy", 4), "dizzy": ("swirl", "confused", 8), "deadpan": ("dot", "flat", 6), "nervous": ("wide", "worried", 8),
    "gasp": ("tiny", "surprised", 7), "terrified": ("tiny", "worried", 13), "cheeky": ("wink", "happy", 12), "scheming": ("smug", "scheme", 10),
    "proud": ("happy", "happy", 10), "pained": ("lines", "sad", 13), "creepy": ("dead", "flat", 0), "determined": ("open", "angry", 5),
    "confused": ("open", "confused", 8), "awkward": ("dot", "worried", 8), "embarrassed": ("shy", "worried", 8), "inspired": ("sparkle", "raised", 4),
    "bored": ("dot", "flat", 6), "grumpy": ("open", "angry", 11), "dreamy": ("blink", "soft", 10), "yum": ("happy", "happy", 12),
})
FACE_FX = {   # little marks drawn on the head
    "worried": ("sweat",), "nervous": ("sweat",), "awkward": ("sweat",), "terrified": ("sweat", "gloom"), "creepy": ("gloom",), "embarrassed": ("flush",),
    "angry": ("vein",), "grumpy": ("vein",), "laughing": ("lol",), "lovestruck": ("flush",), "sad": ("gloom",),
}
FACE_GAZE_Y = {"sad": 0.6, "crying": 0.4, "teary": 0.5, "embarrassed": 0.5, "awkward": 0.3, "sleepy": 0.5, "worried": 0.25, "bored": 0.2, "creepy": 0.0,
               "dreamy": -0.3, "starry": -0.5, "inspired": -0.5, "curious": -0.25}
LOCK_MOUTH = {"laughing", "crying", "teary", "gasp", "terrified", "pained", "nervous", "awkward", "embarrassed", "cheeky", "yum"}   # keep their own mouth while talking
TALK_SHAPE = {0: None, 1: 3, 2: 1, 3: 2}
VISEME_MOUTH = {1: 1, 2: 2, 3: 3, 4: 15, 5: 16}   # eh, ah, small, ee, oo
NO_BLINK = {"lines", "happy", "blink", "wink", "tears", "sparkle", "heart", "swirl"}


def _head_image(face, mouth, blink, gx, gy, brow_lift, look, s):
    """Compose the head (HW x HH units) from the cached layers.  gx, gy in -1..1 (quantised by the caller)."""
    eyes, brow, closed = FACES.get(face, FACES["neutral"])
    fx = FACE_FX.get(face, ())
    W_, H_ = int(math.ceil(HW * s)), int(math.ceil(HH * s))
    im, bx, by = _base_layer(look, s)
    head = im.copy()
    # the face features slide with the gaze: the head seems to turn a little toward what she looks at
    tx, ty = int(round(gx * 3.6 * s)), int(round(gy * 1.8 * s))

    def put(layer, dx=0, dy=0):
        li, lx, ly = layer
        _clip_composite(head, li, lx + dx, ly + dy)

    put(_blush_layer(look, "flush" in fx, s), tx, ty)
    k = 1.0 if blink == 0 else (0.5 if blink == 1 else 0.0)
    if eyes in NO_BLINK:
        k = 1.0
    put(_eyes_layer(eyes, k, gx, gy, look, s), tx, ty)
    put(_brow_layer(brow, s), tx, ty + int(round(-brow_lift * 3.0 * s)))
    down = brow in ("worried", "sad", "angry", "gloom")
    put(_mouth_layer(mouth, down, s), tx, ty)
    fxk = tuple(f for f in fx if f != "flush")
    if fxk:
        put(_fx_layer(fxk, s), 0, 0)
    return head


# ================================================================== BODY
@functools.lru_cache(maxsize=8)
def _body_layer(phase_q, look, s):
    """Legs, skirt, hoodie, scarf wrap, drawstrings. phase_q: -6..6 walk step, or 0."""
    cv = Cv(0, 300, FW, FH, s)
    swing = phase_q / 6.0
    LEG = look.legs if look.skirt else look.bottom
    for side, hx in (("L", 214), ("R", 266)):
        sw = -swing if side == "L" else swing
        foot_x = hx + sw * 26
        lift = max(0.0, sw) * 20
        cv.line([(hx, 520), (foot_x, 626 - lift)], LEG, 38)
        fx_, fy_ = foot_x, 626 - lift
        cv.ell((fx_ - 30, fy_ - 6, fx_ + 30, fy_ + 30), look.shoes)
        cv.ell((fx_ - 20, fy_ - 2, fx_ + 4, fy_ + 8), tuple(min(255, c + 52) for c in look.shoes))
    cv.ell((170, 326, 310, 384), look.top_d)                                     # hood bunched behind the neck
    cv.rrect((152, 340, 328, 480), 46, look.top)                                 # torso
    cv.poly([(188, 424), (292, 424), (304, 462), (176, 462)], look.top_d)        # pocket
    for x0, x1 in ((222, 218), (258, 262)):                                      # drawstrings
        cv.line([(x0, 358), (x1, 428)], CREAM, 3)
        cv.ell((x1 - 5, 424, x1 + 5, 438), CREAM)
    if look.skirt:
        cv.poly([(160, 466), (320, 466), (350, 536), (130, 536)], look.bottom)
    else:
        cv.rrect((166, 466, 314, 548), 30, look.bottom)
    if look.scarf:
        cv.rrect((170, 322, 310, 362), 20, look.scarf)
        cv.rrect((176, 340, 304, 362), 12, shade(look.scarf, 0.88))               # underside of the wrap: depth
        cv.rrect((170, 322, 310, 350), 20, look.scarf)
    else:
        cv.rrect((186, 326, 294, 352), 14, look.top_d)
    return cv.result()


TAIL_ANCHOR = (260, 336)


@functools.lru_cache(maxsize=24)
def _scarf_layer(sway_q, look, s):
    sw = sway_q * 3
    cv = Cv(TAIL_ANCHOR[0] - 30, TAIL_ANCHOR[1] - 8, TAIL_ANCHOR[0] + 90, TAIL_ANCHOR[1] + 192, s)
    ox, oy = TAIL_ANCHOR[0] - 30, TAIL_ANCHOR[1] - 8
    top = (30 + ox, 8 + oy)
    tip = (top[0] + 28 + sw * 1.6, oy + 128)
    cv.line([(top[0] + 22, top[1] + 14), tip], look.scarf, 40)
    cv.line([(tip[0], oy + 118), (tip[0], oy + 132)], tuple(int(c * .8) for c in look.scarf), 40)
    cv.line([(top[0] + 22, top[1] + 14), (tip[0], oy + 118)], look.scarf, 40)
    cv.line([(top[0] + 22, top[1] + 16), (tip[0] - 2, oy + 112)], shade(look.scarf, 0.9), 8)   # fold line
    return cv.result()


# ================================================================== ARMS AND HANDS
def arm_points(side, a, b, sh=(0.0, 0.0)):
    """Shoulder, elbow, wrist and forearm direction (figure units) for upper-arm angle a and forearm angle b (degrees from straight down, outward +)."""
    sgn = -1 if side == "L" else 1
    sx, sy = SHOULDER[side]
    sx, sy = sx + sh[0], sy + sh[1]
    ar, br = math.radians(a), math.radians(b)
    ex, ey = sx + sgn * math.sin(ar) * UPPER, sy + math.cos(ar) * UPPER
    ux, uy = sgn * math.sin(br), math.cos(br)
    return (sx, sy), (ex, ey), (ex + ux * FORE, ey + uy * FORE), (ux, uy)


def hand_center(side, a, b):
    _, _, w, (ux, uy) = arm_points(side, a, b)
    return w[0] + ux * 12, w[1] + uy * 12


def _thumb_normal(ux, uy, side):
    n1, n2 = (-uy, ux), (uy, -ux)
    inward = 1 if side == "L" else -1
    sc = lambda n: n[0] * inward + (-n[1]) * 0.6
    return n1 if sc(n1) >= sc(n2) else n2


def _rot(v, deg):
    r = math.radians(deg)
    return (v[0] * math.cos(r) - v[1] * math.sin(r), v[0] * math.sin(r) + v[1] * math.cos(r))


def _draw_hand(cv, kind, w, u, side, skin):
    ux, uy = u
    sk2 = shade(skin, 0.9)
    nx, ny = _thumb_normal(ux, uy, side)
    add = lambda p, v, k=1.0: (p[0] + v[0] * k, p[1] + v[1] * k)
    c = add(w, u, 12)
    if kind == "open":
        pc = add(w, u, 9)
        for ang in (-27, -9, 9, 27):
            dv = _rot(u, ang)
            cv.capsule(add(pc, dv, 6), add(pc, dv, 20), 8, skin)
        t0 = add(pc, (nx, ny), 8)
        tv = _rot(u, 52 if (nx * _rot(u, 52)[0] + ny * _rot(u, 52)[1]) > 0 else -52)
        cv.capsule(t0, add(t0, tv, 11), 8.5, skin)
        cv.ell((pc[0] - 13.5, pc[1] - 13.5, pc[0] + 13.5, pc[1] + 13.5), skin)
    elif kind == "point":
        pc = add(w, u, 10)
        cv.ell((pc[0] - 12.5, pc[1] - 12.5, pc[0] + 12.5, pc[1] + 12.5), skin)
        cv.capsule(add(pc, u, 4), add(pc, u, 25), 8.5, skin)
        for off in (-4.5, 4.5):                                                  # folded fingers
            kp = add(add(pc, u, 8), (-ny, nx), off)
            cv.ell((kp[0] - 5.5, kp[1] - 5.5, kp[0] + 5.5, kp[1] + 5.5), sk2)
        cv.ell((pc[0] + nx * 9 - 5.5, pc[1] + ny * 9 - 5.5, pc[0] + nx * 9 + 5.5, pc[1] + ny * 9 + 5.5), skin)
    elif kind in ("fist", "thumb"):
        cv.ell((c[0] - 14.5, c[1] - 14, c[0] + 14.5, c[1] + 14), skin)
        for off in (-6, 0, 6):
            p0 = add(add(c, u, 2), (-ny, nx), off)
            cv.line([p0, add(p0, u, 9)], sk2, 2)
        if kind == "thumb":
            tp = (c[0] + nx * 5, c[1] + ny * 5)
            cv.capsule(tp, (tp[0] + nx * 3, tp[1] - 18), 9.5, skin)
        else:
            tp = add(c, (nx, ny), 8)
            cv.ell((tp[0] - 6.5, tp[1] - 6.5, tp[0] + 6.5, tp[1] + 6.5), skin)
    else:                                                                       # mitten with a thumb
        cv.ell((c[0] - 14.5, c[1] - 15, c[0] + 14.5, c[1] + 15), skin)
        tp = add(add(c, (nx, ny), 11), u, 2)
        cv.ell((tp[0] - 6.5, tp[1] - 6.5, tp[0] + 6.5, tp[1] + 6.5), skin)
        cv.line([add(c, u, 3), add(c, u, 12)], sk2, 1.6)


@functools.lru_cache(maxsize=3000)
def _arm_layer(side, a_q, b_q, hand, look, s):
    (sx, sy), (ex, ey), (wx, wy), (ux, uy) = arm_points(side, a_q, b_q)
    pts = [(sx, sy), (ex, ey), (wx, wy), (wx + ux * 40, wy + uy * 40)]
    m = 34
    cv = Cv(min(p[0] for p in pts) - m, min(p[1] for p in pts) - m, max(p[0] for p in pts) + m, max(p[1] for p in pts) + m, s)
    sl, edge = look.sleeve, shade(look.sleeve, 0.84)
    for grow, col in ((4.2, edge), (0.0, sl)):
        cv.capsule((sx, sy), (ex, ey), 34 + grow, col)
        cv.capsule((ex, ey), (wx, wy), 29 + grow, col)
        cv.ell((sx - 18 - grow / 2, sy - 18 - grow / 2, sx + 18 + grow / 2, sy + 18 + grow / 2), col)
        cv.ell((ex - 15 - grow / 2, ey - 15 - grow / 2, ex + 15 + grow / 2, ey + 15 + grow / 2), col)
    # ribbed cuff
    cv.capsule((wx - ux * 9, wy - uy * 9), (wx + ux * 1.5, wy + uy * 1.5), 27, look.top_d)
    _draw_hand(cv, hand, (wx, wy), (ux, uy), side, look.skin)
    return cv.result()


# ================================================================== POSES
# (alpha, beta) for the viewer-left arm and viewer-right arm: upper arm and forearm angle from straight down, outward positive
POSES = {
    "rest":      dict(L=(-4, -62), R=(-4, -62)),
    "relax":     dict(L=(8, 4), R=(8, 4)),
    "talk_a":    dict(L=(12, -14), R=(40, 100)),
    "talk_b":    dict(L=(40, 100), R=(12, -14)),
    "present":   dict(L=(52, 96), R=(52, 96)),
    "explain":   dict(L=(34, 100), R=(34, 100)),
    "point_r":   dict(L=(10, -30), R=(76, 104)),
    "point_l":   dict(L=(76, 104), R=(10, -30)),
    "point_up":  dict(L=(10, -30), R=(80, 148)),
    "shrug":     dict(L=(52, 125), R=(52, 125)),
    "shrug_big": dict(L=(62, 140), R=(62, 140)),
    "wave":      dict(L=(8, -20), R=(62, 168)),
    "cheer":     dict(L=(72, 172), R=(72, 172)),
    "hug":       dict(L=(-14, -88), R=(-14, -88)),
    "cross":     dict(L=(-14, -96), R=(-14, -100)),
    "welcome":   dict(L=(70, 108), R=(70, 108)),
    "idea":      dict(L=(-4, -62), R=(86, 142)),
    "pen":       dict(L=(10, -30), R=(66, 112)),
    "magnify":   dict(L=(10, -30), R=(62, 118)),
    "ponder":    dict(L=(-10, -80), R=(-10, 152)),
    "ponder_l":  dict(L=(-10, 152), R=(-10, -80)),
    "worry":     dict(L=(22, -102), R=(22, -102)),
    "slump":     dict(L=(4, -8), R=(4, -8)),
    "slump_sigh": dict(L=(2, -14), R=(2, -14)),
    "droop":     dict(L=(0, -44), R=(0, -44)),
    "clap":      dict(L=(-10, -110), R=(-10, -110)),
    "hands_up":  dict(L=(80, 156), R=(80, 156)),
    "surprise":  dict(L=(62, 150), R=(62, 150)),
    "shy":       dict(L=(-2, -66), R=(-2, -66)),
    "stop":      dict(L=(-6, -58), R=(74, 152)),
    "hips":      dict(L=(42, -26), R=(42, -26)),
    "heart":     dict(L=(-8, -132), R=(-8, -132)),
    "dance":     dict(L=(104, 150), R=(104, 150)),
    "shake":     dict(L=(4, -44), R=(4, -44)),
    "fist":      dict(L=(-6, -58), R=(34, -168)),
    "wave_both": dict(L=(66, 168), R=(66, 168)),
    "bow":       dict(L=(-4, -38), R=(-4, -38)),
    "lean_in":   dict(L=(8, -74), R=(8, -74)),
    "nod_yes":   dict(L=(8, -20), R=(30, 70)),
    "thumbs_up": dict(L=(8, -30), R=(40, 150)),
}
HANDS = {   # pose -> (left hand, right hand);  default mitten
    "talk_a": ("mitt", "open"), "talk_b": ("open", "mitt"), "present": ("open", "open"), "explain": ("open", "open"),
    "point_r": ("mitt", "point"), "point_l": ("point", "mitt"), "point_up": ("mitt", "point"), "shrug": ("open", "open"), "shrug_big": ("open", "open"),
    "wave": ("mitt", "open"), "cheer": ("fist", "fist"), "welcome": ("open", "open"), "idea": ("mitt", "point"), "pen": ("mitt", "mitt"),
    "magnify": ("mitt", "mitt"), "ponder": ("mitt", "open"), "ponder_l": ("open", "mitt"), "hands_up": ("open", "open"), "surprise": ("open", "open"),
    "stop": ("mitt", "open"), "fist": ("mitt", "fist"), "wave_both": ("open", "open"), "dance": ("open", "open"), "thumbs_up": ("mitt", "thumb"),
    "clap": ("open", "open"), "shake": ("fist", "fist"),
}
# per pose body language: sh = shoulders up (+) / down (-), lean = upper body sideways, dip = head down, tilt = head tilt (deg, + = toward viewer-right),
# gaze = (x, y) default look direction, beat = which arms emphasise with the voice, nod = head-nod strength
POSE_FX = {
    "rest": dict(), "relax": dict(), "talk_a": dict(beat="R"), "talk_b": dict(beat="L"), "present": dict(beat="LR"), "explain": dict(beat="LR", sh=1),
    "point_r": dict(beat="R"), "point_l": dict(beat="L"), "point_up": dict(beat="R", sh=1), "shrug": dict(sh=6, tilt=3), "shrug_big": dict(sh=9, tilt=4, dip=2),
    "wave": dict(beat="R", tilt=2), "cheer": dict(sh=3, beat="LR"), "hug": dict(sh=2, tilt=-2), "cross": dict(sh=1), "welcome": dict(sh=1),
    "idea": dict(beat="R", gaze=(0, -0.4)), "pen": dict(beat="R"), "magnify": dict(beat="R"),
    "ponder": dict(tilt=-6, gaze=(0.3, -0.8), beat="R"), "ponder_l": dict(tilt=6, gaze=(-0.3, -0.8), beat="L"),
    "worry": dict(sh=4, dip=3, tilt=-4, gaze=(0, 0.3)), "slump": dict(sh=-4, dip=7, gaze=(0, 0.5)), "slump_sigh": dict(sh=-6, dip=10, tilt=-4, gaze=(0, 0.6), sigh=1),
    "droop": dict(sh=-5, dip=9, tilt=-5, gaze=(0, 0.7)), "clap": dict(sh=1), "hands_up": dict(sh=5, dip=1), "surprise": dict(sh=5, gaze=(0, 0.0)),
    "shy": dict(sh=3, tilt=5, dip=3, gaze=(-0.4, 0.5)), "stop": dict(beat="R"), "hips": dict(sh=1), "heart": dict(sh=1, tilt=-3, dip=2),
    "dance": dict(sh=2), "shake": dict(sh=2), "fist": dict(beat="R", sh=1), "wave_both": dict(sh=2), "bow": dict(dip=14, sh=-2),
    "lean_in": dict(dip=6, lean=-2, tilt=3, sh=1, gaze=(0, 0.1)), "nod_yes": dict(nod=1.0), "thumbs_up": dict(beat="R", sh=1),
}
TALK_WIGGLE = {"talk_a", "talk_b", "present", "explain", "shrug", "shrug_big", "pen", "magnify", "hands_up", "stop", "welcome", "surprise", "point_up", "idea"}
FRONT = {"cheer", "wave", "wave_both", "dance"}      # hands rise beside the head: drawn over the hair edge (never over the face: the hands stay beyond x of the face)

# old pose names keep working: nothing that touches the face
ALIASES = {
    "think": "ponder", "think_l": "ponder_l", "head": "worry", "head_l": "worry", "facepalm": "slump_sigh", "sob": "droop", "gasp_hands": "surprise",
    "count": "point_up", "sigh": "slump_sigh", "chin": "ponder", "hand_on_head": "worry", "cover": "worry",
}
COVER = {}                         # (kept for old imports) no pose covers the face any more
PROPS = {"pen": ("R", "pen"), "magnify": ("R", "magnify")}


def resolve_pose(name):
    """Any pose name (including the old ones) -> a pose that exists. Unknown names give 'rest'."""
    if not name:
        return "rest"
    name = str(name).lower()
    name = ALIASES.get(name, name)
    return name if name in POSES else "rest"


def pose_hands(pose):
    return HANDS.get(resolve_pose(pose), ("mitt", "mitt"))


def pose_arms(pose, t, wiggle=1.0, beat=0.0):
    """-> ({'L': (a, b), 'R': (a, b)}, front) for a pose name at time t (talking gestures sway a little, `beat` 0..1 adds an emphasis lift)."""
    pose = resolve_pose(pose)
    P = POSES[pose]
    fx = POSE_FX.get(pose, {})
    out = {}
    for sd in ("L", "R"):
        a, b = P[sd]
        ph = 0.0 if sd == "L" else 1.9
        if pose == "wave" and sd == "R":
            b += 16 * math.sin(t * 7.5); a += 3 * math.sin(t * 7.5 + 1)
        elif pose == "clap":
            b += 17 * math.sin(t * 13); a += 5 * math.sin(t * 13)
        elif pose == "dance":
            a += 16 * math.sin(t * 6 + (0 if sd == "L" else math.pi)); b += 14 * math.sin(t * 6 + (0 if sd == "L" else math.pi))
        elif pose == "shake":
            a += 3 * math.sin(t * 34 + (0 if sd == "L" else 1.3)); b += 3 * math.sin(t * 29)
        elif pose == "wave_both":
            b += 16 * math.sin(t * 7.5 + (0 if sd == "L" else 1.6))
        elif pose in ("shy", "droop"):
            b += 6 * math.sin(t * 5.2 + (0 if sd == "L" else 0.9))
        elif pose == "cheer":
            a += 5 * math.sin(t * 8 + ph); b += 6 * math.sin(t * 8 + ph)
        if pose in TALK_WIGGLE:
            a += wiggle * 5 * (math.sin(t * 2.3 + ph) + 0.6 * math.sin(t * 4.1 + ph * 2))
            b += wiggle * 8 * (math.sin(t * 1.9 + ph + 0.8) + 0.5 * math.sin(t * 3.7 + ph))
        else:                                                                    # idle: arms are never frozen
            a += wiggle * 1.2 * math.sin(t * 1.3 + ph)
            b += wiggle * 1.6 * math.sin(t * 1.7 + ph + 1)
        if sd in fx.get("beat", "") and beat:                                    # emphasis: the arm lifts and the hand flicks out
            a += beat * 9 * wiggle
            b += beat * 13 * wiggle * (1 if b > 0 else -0.6)
        out[sd] = (a, b)
    return out, resolve_pose(pose) in FRONT


# ------------------------------------------------------------------ props
@functools.lru_cache(maxsize=16)
def _prop_layer(kind, s):
    if kind == "pen":
        cv = Cv(0, 0, 110, 110, s)
        cv.capsule((22, 88), (82, 24), 9, (40, 40, 52))
        cv.capsule((70, 38), (86, 20), 9, (232, 70, 76))
        cv.ell((14, 84, 28, 100), (60, 60, 80))
        return cv.result()
    cv = Cv(0, 0, 150, 150, s)
    cv.capsule((36, 118), (70, 84), 14, (120, 82, 60))
    cv.ell((56, 10, 146, 100), (104, 78, 70))
    cv.ell((60, 14, 142, 96), (150, 200, 235))
    cv.ell((64, 18, 138, 92), (214, 238, 252))
    cv.ell((74, 26, 100, 48), WHITE)
    return cv.result()


def _clip_composite(frame, layer, x, y):
    fw, fh = frame.size
    lw, lh = layer.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(fw, x + lw), min(fh, y + lh)
    if x1 <= x0 or y1 <= y0:
        return
    crop = layer.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    frame.alpha_composite(crop, (x0, y0))


def _lerp(a, b, k):
    return a + (b - a) * k


def _qa(v, step=3.0):
    return int(round(v / step)) * int(step)


# ================================================================== THE FIGURE
def draw_figure(frame, x, floor_y, s, pose="rest", prev_pose=None, blend=1.0, t=0.0, face="neutral", amp=0.0, vis=None, gaze=0, tilt=0.0,
                flip=False, hop=0.0, wiggle=1.0, shadow=False, look=YUKI, gaze_y=None, seed=0, energy=None):
    """Draw Yuki onto `frame` (RGBA) with her feet at (x, floor_y). Everything depends only on the arguments (frames can be rendered in any order).
    pose / prev_pose: names in POSES (old names work too); arms ease from prev_pose to pose as blend goes 0 -> 1, with a little overshoot;
    face: key of FACES; amp: 0..1 loudness of her voice right now (drives the mouth and the emphasis); vis: mouth shape 0..5 or None;
    gaze: -1..1 where she looks (+ = toward the viewer's right); gaze_y: -1 (up) .. 1 (down), default from the feeling and the pose;
    hop: 0..1 progress of a little jump (squash and stretch); seed: makes two shots move out of step; energy: gesture size (default from the face).
    -> (ox, oy): where the figure canvas starts on the frame."""
    s = round(float(s), 3)
    pose = resolve_pose(pose)
    prev_pose = resolve_pose(prev_pose) if prev_pose else None
    k = max(0.0, min(1.0, blend))
    kk = M.ease_out_back(k) if prev_pose and k < 1.0 else 1.0
    tt = t + 0.73 * seed
    en = (M.ENERGY.get(face, 0.9) if energy is None else energy) * max(0.0, wiggle)
    speak = M.clamp((amp - 0.05) / 0.2) if (vis is not None or amp > 0) else 0.0
    beat = M.beat(tt, seed) * en * (0.4 + 0.6 * speak)
    emph = M.clamp((amp - 0.5) / 0.4)
    breath = math.sin(tt * 2 * math.pi / 3.8)
    shift = math.sin(tt * 2 * math.pi / 6.1 + 0.7)

    # ---- arms (+ the body language of the pose, blended with the previous pose)
    arms_b, front_b = pose_arms(pose, tt, en, beat)
    fxb = POSE_FX.get(pose, {})
    hands_b = pose_hands(pose)
    if prev_pose and k < 1.0:
        arms_a, front_a = pose_arms(prev_pose, tt, en, beat)
        arms = {sd: (_lerp(arms_a[sd][0], arms_b[sd][0], kk), _lerp(arms_a[sd][1], arms_b[sd][1], kk)) for sd in arms_b}
        hands = pose_hands(prev_pose) if k < 0.5 else hands_b
        front = front_b if k > 0.5 else front_a
        fxa = POSE_FX.get(prev_pose, {})
        g = lambda key, d=0.0: _lerp(fxa.get(key, d), fxb.get(key, d), min(1.0, kk))
        gaze_pose = (_lerp(fxa.get("gaze", (0, 0))[0], fxb.get("gaze", (0, 0))[0], k), _lerp(fxa.get("gaze", (0, 0))[1], fxb.get("gaze", (0, 0))[1], k))
    else:
        arms, hands, front = arms_b, hands_b, front_b
        g = lambda key, d=0.0: fxb.get(key, d)
        gaze_pose = fxb.get("gaze", (0, 0))
    sh_up = g("sh") * (0.5 + 0.5 * min(1.3, en)) + (g("sigh") and 2.0 * math.sin(tt * 2 * math.pi / 3.8 - 0.5) or 0.0)
    lean = g("lean") + 1.6 * shift
    ux, uy = lean, -1.3 * breath - sh_up                      # the whole upper body (arms, head, scarf) moves relative to the hips
    settle = math.sin(math.pi * k) if (prev_pose and k < 1.0) else 0.0

    # ---- head
    eyes_t = FACES.get(face, FACES["neutral"])[0]
    bl = M.blink_phase(tt, seed)
    sac = M.saccade(tt, seed)
    gx = max(-1.0, min(1.0, float(gaze) * 0.85 + gaze_pose[0] + sac[0]))
    base_gy = FACE_GAZE_Y.get(face, 0.0) if gaze_y is None else gaze_y
    gy = max(-1.0, min(1.0, base_gy + gaze_pose[1] + sac[1]))
    gxq, gyq = round(gx * 2) / 2.0, round(gy * 2) / 2.0
    q = 0 if amp < 0.11 else 1 if amp < 0.34 else 2 if amp < 0.66 else 3
    closed = FACES.get(face, FACES["neutral"])[2]
    if vis is not None:
        q = 0 if (vis == 0 and amp < 0.11) else max(q, 1)
        mouth = closed if vis == 0 else VISEME_MOUTH[vis]
    else:
        mouth = closed if q == 0 else TALK_SHAPE[q]
        if q == 3 and face in ("happy", "smile", "excited"):
            mouth = 4
        if q and face == "smug":
            mouth = 1 if q < 3 else mouth
    if q and face in LOCK_MOUTH:
        mouth = closed
    head_tilt = tilt + g("tilt") * (0.6 + 0.4 * en) + 1.5 * math.sin(tt * 1.1) + 0.9 * math.sin(tt * 2.7 + 1) - 0.8 * shift - 2.0 * (gx * 0.4)
    nod = (0.9 + 1.5 * (0.5 + 0.5 * math.sin(tt * 5.3))) * (1 if q else 0) + 4.0 * beat * (0.5 + 0.5 * en) + g("dip") + 0.5 * sh_up \
        + g("nod") * 4.5 * max(0.0, math.sin(tt * 2 * math.pi * 1.4)) + 3.0 * settle
    head = _head_image(face, mouth, bl, gxq, gyq, emph * 0.6, look, s)

    # ---- squash and stretch on hops and settles
    hp = max(0.0, min(1.0, hop))
    hop_up = 14 * math.sin(hp * math.pi) if hp > 0 else 0.0
    sy_ = 1.0 + 0.05 * math.sin(hp * 2 * math.pi) * (1 if hp > 0 else 0) - 0.012 * settle
    sx_ = 1.0 / math.sqrt(sy_)

    bob = 2.6 * math.sin(tt * 1.7) + 1.0 * math.sin(tt * 3.1) + hop_up
    fig = Image.new("RGBA", (int(FW * s) + 2, int(FH * s) + 2), (0, 0, 0, 0))
    bi, bx, by = _body_layer(0, look, s)
    fig.alpha_composite(bi, (bx, by))
    if look.scarf:
        sway = max(-4, min(4, int(round(2.4 * math.sin(tt * 2.2) + 1.6 * math.sin(tt * 5.3 + 1.0) + 2.2 * (shift - math.sin(tt * 2 * math.pi / 6.1 + 0.7 - 0.5)) * 6 + 1.5 * hp * math.sin(hp * 6)))))
        si, sx0, sy0 = _scarf_layer(sway, look, s)
        _clip_composite(fig, si, sx0 + int(round(ux * 0.6 * s)), sy0 + int(round(uy * s)))
    arm_list = []
    for i, sd in enumerate(("L", "R")):
        a, b = arms[sd]
        li, lx, ly = _arm_layer(sd, _qa(a), _qa(b), hands[i], look, s)
        arm_list.append((sd, a, b, li, lx + int(round(ux * s)), ly + int(round(uy * s))))
    if not front:
        for sd, a, b, li, lx, ly in arm_list:
            _clip_composite(fig, li, lx, ly)
    pad = int(60 * s)
    hc = Image.new("RGBA", (head.width + 2 * pad, head.height + 2 * pad), (0, 0, 0, 0))
    hc.alpha_composite(head, (pad, pad))
    if abs(head_tilt) > 0.2:
        pivot = ((NECK[0] - HEAD_POS[0]) * s + pad, (NECK[1] - HEAD_POS[1]) * s + pad)
        hc = hc.rotate(-head_tilt, resample=Image.BICUBIC, center=pivot)
    _clip_composite(fig, hc, int(round((HEAD_POS[0] + ux) * s - pad)), int(round((HEAD_POS[1] + uy + nod) * s - pad)))
    if front:
        for sd, a, b, li, lx, ly in arm_list:
            _clip_composite(fig, li, lx, ly)
    pr = PROPS.get(pose)
    if pr and blend >= 0.6:
        sd = pr[0]
        i = 0 if sd == "L" else 1
        _, _, (wx, wy), (dx, dy) = arm_points(sd, arms[sd][0], arms[sd][1])
        hx, hy = wx + dx * 12 + ux, wy + dy * 12 + uy
        pi_, px0, py0 = _prop_layer(pr[1], s)
        off = (-20, -92) if pr[1] == "pen" else (-36, -94)
        _clip_composite(fig, pi_, px0 + int(round((hx + off[0]) * s)), py0 + int(round((hy + off[1]) * s)))
    if flip:
        fig = fig.transpose(Image.FLIP_LEFT_RIGHT)
    if abs(sy_ - 1.0) > 0.004:                                  # squash / stretch about the waist
        ax = fig.width / 2.0
        ay = 480 * s
        nw, nh = max(1, int(round(fig.width * sx_))), max(1, int(round(fig.height * sy_)))
        fig = fig.resize((nw, nh), Image.BILINEAR)
        ox = int(x - 240 * s - (ax * sx_ - ax))
        oy = int(floor_y - 660 * s - bob - (ay * sy_ - ay))
    else:
        ox = int(x - 240 * s)
        oy = int(floor_y - 660 * s - bob)
    if shadow:
        sh = Image.new("RGBA", (int(230 * s), int(40 * s)), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((0, 0, sh.width - 1, sh.height - 1), fill=(0, 0, 0, 55))
        sh = sh.filter(ImageFilter.GaussianBlur(4))
        _clip_composite(frame, sh, int(x - sh.width / 2), int(floor_y - sh.height / 2 - 2))
    _clip_composite(frame, fig, ox, oy)
    return (ox, oy)


# ------------------------------------------------------------------ legacy class (kept for old imports; draw_figure is the real renderer)
class Rig:
    """Animated state for one Yuki (old interface).  update() once per frame, then draw()."""

    def __init__(self, x, floor_y, scale=0.72, look=YUKI):
        self.look = look
        self.x, self.floor_y, self.scale = float(x), floor_y, scale
        self.target_x = float(x)
        self.vx = 0.0
        self.walk = 0.0
        self.t = 0.0
        self.pose, self.face, self.gaze, self.bounce, self.tilt, self.wiggle = "rest", "neutral", 0.0, 0.0, 0.0, 0.0
        self.speaking = 0.0

    def update(self, dt, pose="rest", tilt=0.0, wiggle=0.0, speaking=0.0, face="neutral", gaze=0.0, hop=0.0):
        self.t += dt
        self.pose, self.face, self.tilt, self.speaking, self.gaze = pose, face, tilt, speaking, gaze
        self.wiggle = max(0.4, wiggle)
        dx = self.target_x - self.x
        sp = max(-480.0, min(480.0, dx * 3.2))
        self.vx += (sp - self.vx) * (1 - math.exp(-dt * 8))
        self.x += self.vx * dt
        self.walk += abs(self.vx) * dt / 60.0
        self.bounce = max(self.bounce - dt * 3.2, 0.0)
        if hop > 0 and self.bounce <= 0:
            self.bounce = 1.0

    @property
    def moving(self):
        return abs(self.vx) > 25

    def draw(self, frame, mouth, blink=False):
        draw_figure(frame, self.x, self.floor_y, self.scale, pose=self.pose, t=self.t, face=self.face, amp=min(1.0, self.speaking * 0.6 + (0.3 if mouth else 0.0)),
                    gaze=int(round(self.gaze)), tilt=self.tilt, hop=(1.0 - self.bounce) if self.bounce > 0 else 0.0, wiggle=self.wiggle, shadow=True, look=self.look)
