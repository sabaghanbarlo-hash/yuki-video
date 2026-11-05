"""Yuki: a chibi narrator drawn entirely in code (Pillow), rigged for talking, blinking,
walking and arm gestures. Parts are drawn 3x supersampled, cached, then composited per frame.

This is the original Yuki rig (flat, no outlines, glossy eyes) with extra faces (sleepy, smug) and poses (crossed arms,
hand on head, pen, magnifier) for the collage look, plus `draw_figure`, a stateless renderer: the same inputs always give
the same picture, so frames can be rendered in any order on any worker.

Design space: figure canvas 480 x 700 units, feet at y=660, neck at (240, 330).
"""
import functools, math
from PIL import Image, ImageDraw, ImageFilter

SS = 3
FW, FH = 480, 700
HW, HH = 400, 380            # head canvas (units)
HEAD_POS = (40, 10)          # head canvas top-left on the figure canvas
NECK = (240, 330)            # rotation pivot for the head (figure coords)
SHOULDER = {"L": (172, 376), "R": (308, 376)}
UPPER, FORE = 54, 50

INK = (40, 32, 44)
HAIR = (70, 44, 42)
HAIR_HI = (92, 98, 124)
HAIR_BACK = (70, 44, 42)
HAIR_SIDE = (70, 44, 42)
SLEEVE = (100, 156, 106)
SKIN = (255, 225, 204)
SKIN_SH = (238, 196, 170)
BLUSH = (246, 150, 150)
GREEN, GREEN_D, GREEN_L = (112, 168, 116), (86, 140, 98), (138, 186, 132)
RED, RED_D, RED_L = (222, 64, 72), (170, 40, 52), (240, 110, 110)
SKIRT = (72, 66, 90)
LEG, LEG_HI = (36, 34, 46), (74, 72, 90)
CREAM = (244, 236, 218)
MOUTH_IN, TONGUE = (112, 34, 48), (238, 120, 132)
MOUTH_LN = (150, 60, 70)


from dataclasses import dataclass


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


def _P(S):
    return lambda *v: [int(round(x * S)) for x in v]


def _canvas(w, h):
    im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _bez(p0, p1, p2, p3, n=18):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _poly(d, pts, fill, outline=INK, width=4):
    outline = None if outline == INK else outline
    P = _P(SS)
    flat = [tuple(P(*p)) for p in pts]
    d.polygon(flat, fill=fill)
    if outline:
        d.line(flat + [flat[0]], fill=outline, width=width * SS, joint="curve")


def _ell(d, box, fill, outline=INK, width=4):
    outline = None if outline == INK else outline
    P = _P(SS)
    d.ellipse(P(*box), fill=fill, outline=outline, width=(width * SS if outline else 0))


def _round(d, box, r, fill, outline=INK, width=4):
    outline = None if outline == INK else outline
    P = _P(SS)
    d.rounded_rectangle(P(*box), radius=r * SS, fill=fill, outline=outline, width=(width * SS if outline else 0))


def _thick(d, a, b, w, fill):
    if fill == INK:      # outline underlays are skipped: the style has no black outlines
        return
    P = _P(SS)
    (x1, y1), (x2, y2) = P(*a), P(*b)
    r = w * SS / 2
    d.line([(x1, y1), (x2, y2)], fill=fill, width=int(w * SS))
    d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=fill)
    d.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=fill)


# ------------------------------------------------------------------ head

def _bell(d, bottom, fill, long=False):
    """Soft bell of hair: dome on top, sides that swell then tuck in, big round bottom corners (one smooth shape)."""
    P = _P(SS)
    inset = 8 if long else 22            # how far the bottom tucks in from the widest point
    top_y = 150
    L = []
    # left side, from the widest point down to the rounded corner, then along the bottom
    L += _bez((34, top_y), (30, top_y + 56), (30 + 0, bottom - 90), (34 + inset * .5, bottom - 52), 16)
    L += _bez((34 + inset * .5, bottom - 52), (36 + inset, bottom - 14), (60 + inset, bottom + 2), (104, bottom + 2), 14)
    R = [(400 - x, y) for x, y in L]
    pts = L + R[::-1]
    d.polygon([tuple(P(*p)) for p in pts], fill=fill)

EYE = (56, 36, 46)
LASH = (56, 36, 46)
CLIP, CLIP_C = (214, 72, 78), (252, 232, 208)


def head_base(mouth, eyes, brow, gaze, look=YUKI, cover=None):
    """Smooth flat chibi head built like the Tiny Japanese characters: one soft bell of hair, wide round face,
    scalloped fringe, flat oval eyes with two light dots, round blush, tiny smile. No outlines.
    mouth 0..4, eyes 'open'|'blink'|'happy'|'wide', brow 'neutral'|'raised'|'worried'|'happy', gaze -1..1"""
    im, d = _canvas(HW, HH)
    P = _P(SS)
    HAIR, SKIN = look.hair, look.skin
    # hair: dome + straight sides with rounded bottom corners
    bottom = {"bob": 314, "long": 372, "boy": 250, "bun": 300}[look.style]
    _ell(d, (34, 22, 366, 300), HAIR)
    if look.style == "boy":
        _round(d, (40, 150, 360, 250), 40, HAIR)
    else:
        _bell(d, bottom, HAIR, long=(look.style == "long"))
    if look.style == "bun":
        _ell(d, (152, -6, 248, 54), HAIR, None)
    # face
    _ell(d, (82, 104, 318, 318), SKIN)
    # fringe: upper half of the dome + a row of soft scallops (boys: a flat swoosh)
    cx, cy, a, b = 200, 161, 166, 139
    top = [(cx + a * math.cos(math.radians(t)), cy + b * math.sin(math.radians(t))) for t in range(180, 361, 4)]
    d.polygon([tuple(P(*p)) for p in top], fill=HAIR)
    if look.style == "boy":
        d.polygon([tuple(P(*p)) for p in [(60, 150), (340, 150), (330, 176), (280, 192), (230, 172), (190, 186), (140, 176), (80, 190), (64, 176)]], fill=HAIR)
    else:
        for x in (96, 138, 180, 220, 262, 304):
            _ell(d, (x - 26, cy - 26, x + 26, cy + 26), HAIR, None)
        d.rectangle(P(62, 150, 338, 166), fill=HAIR)
    if sum(look.hair) < 260 and look.style != "boy":
        g = tuple(min(255, c + 30) for c in look.hair)
        d.arc(P(70, 40, 250, 150), 200, 262, fill=g, width=9 * SS)
        d.arc(P(86, 56, 236, 140), 205, 255, fill=g, width=5 * SS)
    if look.clip:
        _ell(d, (270, 44, 306, 80), look.clip, None)
        _ell(d, (281, 55, 295, 69), CLIP_C, None)

    # blush
    for bx in (123, 277):
        _ell(d, (bx - 25, 258, bx + 25, 285), look.blush, None)

    # eyes
    for cx_ in (143, 257):
        ex, ey = cx_ + gaze * 5, 226
        if eyes in ("open", "wide"):
            ry = 35 if eyes == "wide" else 32
            _ell(d, (ex - 24, ey - ry, ex + 24, ey + ry), EYE, None)
            _ell(d, (ex - 16 + gaze * 2, ey - ry + 6, ex + 2 + gaze * 2, ey - ry + 25), (255, 255, 255), None)
            _ell(d, (ex + 6, ey + 9, ex + 18, ey + 21), (255, 255, 255), None)
            if brow in ("angry", "sad"):
                s_ = 1 if cx_ < 200 else -1          # +1 for the left eye
                inner_low = brow == "angry"
                y_in, y_out = (ey - 6, ey - 38) if inner_low else (ey - 40, ey - 8)
                xi, xo = ex + 28 * s_, ex - 28 * s_
                pts = [(xo, 190), (xi, 190), (xi, y_in), (xo, y_out)]
                d.polygon([tuple(P(*p)) for p in pts], fill=SKIN)
                d.line([tuple(P(*p)) for p in ((xo, y_out), (xi, y_in))], fill=LASH, width=5 * SS)
        elif eyes in ("sleepy", "smug"):
            _ell(d, (ex - 24, ey - 32, ex + 24, ey + 32), EYE, None)
            _ell(d, (ex - 16 + gaze * 2, ey - 26, ex + 2 + gaze * 2, ey - 8), (255, 255, 255), None)
            _ell(d, (ex + 6, ey + 9, ex + 18, ey + 21), (255, 255, 255), None)
            lid = ey + 2 if eyes == "sleepy" else ey - 12            # how far the eyelid comes down
            droop = 5 if eyes == "sleepy" else -3                     # outer corner lower (sleepy) or higher (smug)
            s_ = 1 if cx_ < 200 else -1
            xo, xi = ex - 30 * s_, ex + 30 * s_
            d.polygon([tuple(P(*p)) for p in ((xo, 186), (xi, 186), (xi, lid), (xo, lid + droop))], fill=SKIN)
            d.line([tuple(P(*p)) for p in ((xo, lid + droop), (xi, lid))], fill=LASH, width=5 * SS)
            if eyes == "sleepy":                                       # tired bags under the eyes
                _ell(d, (ex - 22, ey + 30, ex + 22, ey + 44), SKIN_SH, None)
        elif eyes == "tears":                                                 # wet eyes + streaming tears
            _ell(d, (ex - 24, ey - 30, ex + 24, ey + 34), EYE, None)
            _ell(d, (ex - 17, ey - 24, ex + 3, ey - 4), (255, 255, 255), None)
            _ell(d, (ex - 4, ey + 6, ex + 18, ey + 24), (170, 220, 255), None)
            for k_ in (0, 1):
                tx = ex + (-1 if cx_ < 200 else 1) * (20 + k_ * 3)
                _ell(d, (tx - 7, ey + 26 + k_ * 20, tx + 7, ey + 52 + k_ * 20), (140, 206, 255), None)
            d.line([tuple(P(*q)) for q in ((ex - 28, ey - 40), (ex + 28, ey - 30))] if cx_ < 200 else [tuple(P(*q)) for q in ((ex - 28, ey - 30), (ex + 28, ey - 40))], fill=LASH, width=4 * SS)
        elif eyes == "sparkle":                                               # starstruck: big eyes full of stars
            _ell(d, (ex - 27, ey - 36, ex + 27, ey + 36), EYE, None)
            for (sx_, sy_, r_) in ((ex - 6, ey - 10, 15), (ex + 11, ey + 14, 8)):
                pts = []
                for i_ in range(8):
                    rr = r_ if i_ % 2 == 0 else r_ * 0.38
                    ang = math.radians(-90 + i_ * 45)
                    pts.append(P(sx_ + rr * math.cos(ang), sy_ + rr * math.sin(ang)))
                d.polygon([tuple(q) for q in pts], fill=(255, 255, 255))
        elif eyes == "heart":
            for hx_, hy_, r_ in ((ex, ey, 27),):
                _ell(d, (hx_ - r_, hy_ - r_ * 0.85, hx_, hy_ + r_ * 0.15), (240, 84, 120), None)
                _ell(d, (hx_, hy_ - r_ * 0.85, hx_ + r_, hy_ + r_ * 0.15), (240, 84, 120), None)
                d.polygon([tuple(P(*q)) for q in ((hx_ - r_ * 0.98, hy_ - r_ * 0.2), (hx_ + r_ * 0.98, hy_ - r_ * 0.2), (hx_, hy_ + r_ * 1.05))], fill=(240, 84, 120))
                _ell(d, (hx_ - r_ * 0.6, hy_ - r_ * 0.6, hx_ - r_ * 0.2, hy_ - r_ * 0.25), (255, 255, 255), None)
        elif eyes == "swirl":                                                 # dizzy spirals
            _ell(d, (ex - 26, ey - 30, ex + 26, ey + 30), (250, 250, 250), None)
            pts = [P(ex + (0.7 + t_ * 0.9) * math.cos(t_ * 6.8) * 2.0 * 1.0, ey + (0.7 + t_ * 0.9) * math.sin(t_ * 6.8) * 2.0) for t_ in [i / 60 for i in range(61)]]
            pts = [P(ex + (3 + t_ * 22) * math.cos(t_ * 17), ey + (3 + t_ * 22) * math.sin(t_ * 17)) for t_ in [i / 70 for i in range(71)]]
            d.line([tuple(q) for q in pts], fill=EYE, width=4 * SS)
        elif eyes == "dot":                                                   # deadpan: tiny dot eyes
            _ell(d, (ex - 8, ey - 8, ex + 8, ey + 8), EYE, None)
        elif eyes == "tiny":                                                  # shock: huge white eyes, tiny pupils
            _ell(d, (ex - 28, ey - 38, ex + 28, ey + 38), (252, 252, 252), None)
            _ell(d, (ex - 12 + gaze * 3, ey - 12, ex + 12 + gaze * 3, ey + 12), EYE, None)
        elif eyes == "lines":                                                 # > <  squeezed shut (laughing, pain)
            sg = 1 if cx_ < 200 else -1
            d.line([tuple(P(*q)) for q in ((ex - 22 * sg, ey - 18), (ex + 18 * sg, ey), (ex - 22 * sg, ey + 18))], fill=LASH, width=6 * SS)
        elif eyes == "wink":
            if cx_ < 200:
                d.arc(P(ex - 24, ey - 8, ex + 24, ey + 20), 205, 335, fill=LASH, width=6 * SS)
            else:
                _ell(d, (ex - 24, ey - 32, ex + 24, ey + 32), EYE, None)
                _ell(d, (ex - 16, ey - 26, ex + 2, ey - 7), (255, 255, 255), None)
                _ell(d, (ex + 6, ey + 9, ex + 18, ey + 21), (255, 255, 255), None)
        elif eyes == "dead":                                                  # creepy: no light in the eyes
            _ell(d, (ex - 24, ey - 32, ex + 24, ey + 32), (26, 26, 36), None)
        elif eyes == "shy":                                                   # looking away, a bit smaller
            _ell(d, (ex - 20 + 6, ey - 26, ex + 20 + 6, ey + 28), EYE, None)
            _ell(d, (ex - 12 + 6, ey - 20, ex + 2 + 6, ey - 4), (255, 255, 255), None)
            _ell(d, (ex + 8, ey + 6, ex + 18, ey + 16), (255, 255, 255), None)
            for k_ in range(3):
                x0 = (123 if cx_ < 200 else 277) - 18 + k_ * 14
                d.line([tuple(P(x0, 252)), tuple(P(x0 + 6, 266))], fill=(238, 120, 130), width=3 * SS)
        elif eyes == "blink":
            d.arc(P(ex - 24, ey - 12, ex + 24, ey + 12), 25, 155, fill=LASH, width=5 * SS)
        elif eyes == "happy":
            d.arc(P(ex - 24, ey - 8, ex + 24, ey + 20), 205, 335, fill=LASH, width=5 * SS)

    # mouth: tiny smile when closed; small soft shapes when talking
    mx, my = 200, 290
    MC = (96, 54, 62)
    if mouth == 0:
        if brow in ("worried", "sad", "angry"):
            d.arc(P(mx - 12, my - 2, mx + 12, my + 10), 200, 340, fill=MC, width=3 * SS)
        else:
            d.arc(P(mx - 15, my - 12, mx + 15, my + 4), 25, 155, fill=MC, width=3 * SS)
    elif mouth == 1:
        _ell(d, (mx - 7, my - 6, mx + 7, my + 8), MOUTH_IN, None)
    elif mouth == 2:
        _ell(d, (mx - 16, my - 8, mx + 16, my + 20), MOUTH_IN, None)
        _ell(d, (mx - 9, my + 8, mx + 9, my + 19), TONGUE, None)
    elif mouth == 3:
        _ell(d, (mx - 5, my - 5, mx + 5, my + 8), MOUTH_IN, None)
    elif mouth == 5:                                                   # smirk
        d.arc(P(mx - 6, my - 12, mx + 22, my + 4), 20, 150, fill=MC, width=3 * SS)
        d.line([tuple(P(*p)) for p in ((mx - 12, my - 2), (mx - 6, my - 1))], fill=MC, width=3 * SS)
    elif mouth == 7:                                                   # gasp: round open "o"
        _ell(d, (mx - 14, my - 12, mx + 14, my + 22), MOUTH_IN, None)
        _ell(d, (mx - 8, my + 6, mx + 8, my + 20), TONGUE, None)
    elif mouth == 8:                                                   # wobbly (nervous, confused, awkward)
        d.line([tuple(P(*q)) for q in ((mx - 18, my + 2), (mx - 9, my - 5), (mx, my + 3), (mx + 9, my - 5), (mx + 18, my + 2))], fill=MC, width=3 * SS)
    elif mouth == 9:                                                   # big laugh
        d.pieslice(P(mx - 26, my - 22, mx + 26, my + 24), 0, 180, fill=MOUTH_IN)
        d.pieslice(P(mx - 15, my - 2, mx + 15, my + 22), 0, 180, fill=TONGUE)
        d.rectangle(P(mx - 24, my - 4, mx + 24, my + 1), fill=(255, 255, 255))
    elif mouth == 10:                                                  # cat mouth  :3
        d.arc(P(mx - 20, my - 14, mx, my + 6), 10, 170, fill=MC, width=3 * SS)
        d.arc(P(mx, my - 14, mx + 20, my + 6), 10, 170, fill=MC, width=3 * SS)
    elif mouth == 11:                                                  # frown
        d.arc(P(mx - 16, my - 2, mx + 16, my + 20), 205, 335, fill=MC, width=4 * SS)
    elif mouth == 12:                                                  # tongue out
        d.arc(P(mx - 16, my - 12, mx + 16, my + 4), 25, 155, fill=MC, width=3 * SS)
        _round(d, (mx - 3, my - 2, mx + 14, my + 22), 8, TONGUE, None)
    elif mouth == 13:                                                  # grit teeth
        _round(d, (mx - 18, my - 8, mx + 18, my + 12), 5, (255, 255, 255), MC, 3 * SS)
        d.line([tuple(P(*q)) for q in ((mx - 18, my + 2), (mx + 18, my + 2))], fill=MC, width=2 * SS)
        for k_ in (-9, 0, 9):
            d.line([tuple(P(mx + k_, my - 8)), tuple(P(mx + k_, my + 12))], fill=MC, width=2 * SS)
    elif mouth == 14:                                                  # sobbing: wide wobbly open
        _ell(d, (mx - 16, my - 6, mx + 16, my + 20), MOUTH_IN, None)
        d.arc(P(mx - 12, my + 4, mx + 12, my + 22), 200, 340, fill=TONGUE, width=5 * SS)
    elif mouth == 15:                                                  # "ee": wide and thin, teeth showing
        _round(d, (mx - 20, my - 5, mx + 20, my + 8), 6, MOUTH_IN, None)
        d.rectangle(P(mx - 15, my - 4, mx + 15, my), fill=(255, 255, 255))
    elif mouth == 16:                                                  # "oo": small round pucker
        _ell(d, (mx - 8, my - 8, mx + 8, my + 10), MOUTH_IN, None)
    elif mouth == 6:                                                   # flat / unimpressed
        d.line([tuple(P(*p)) for p in ((mx - 12, my + 2), (mx + 12, my + 2))], fill=MC, width=3 * SS)
    else:  # 4: happy open smile
        d.pieslice(P(mx - 16, my - 11, mx + 16, my + 14), 0, 180, fill=MOUTH_IN)
        d.pieslice(P(mx - 9, my + 1, mx + 9, my + 13), 0, 180, fill=TONGUE)
    if cover:                                                          # hands pressed over the eyes (facepalm / sobbing)
        spots = ((143, 232), (257, 232)) if cover == "both" else ((236, 226),)
        for hx_, hy_ in spots:
            _ell(d, (hx_ - 50, hy_ - 44, hx_ + 50, hy_ + 52), tuple(max(0, c - 16) for c in look.skin), None)
            _ell(d, (hx_ - 44, hy_ - 40, hx_ + 44, hy_ + 44), look.skin, None)
            for fx in (-30, -10, 10, 30):
                d.line([tuple(P(hx_ + fx, hy_ - 36)), tuple(P(hx_ + fx, hy_ - 8))], fill=tuple(max(0, c - 22) for c in look.skin), width=3 * SS)
    return im



# ------------------------------------------------------------------ body
def body_base(phase_q, bow_q, look=YUKI):
    """Legs, skirt, hoodie, scarf wrap, drawstrings. phase_q: -6..6 walk step, or 0."""
    im, d = _canvas(FW, FH)
    swing = phase_q / 6.0
    LEG = look.legs if look.skirt else look.bottom
    for side, hx in (("L", 214), ("R", 266)):
        s = -swing if side == "L" else swing
        foot_x = hx + s * 26
        lift = max(0.0, s) * 20
        hip = (hx, 520)
        foot = (foot_x, 626 - lift)
        _thick(d, hip, foot, 38, LEG)
        # shoe
        _ell(d, (foot[0] - 30, foot[1] - 6, foot[0] + 30, foot[1] + 30), look.shoes, INK, 4)
        _ell(d, (foot[0] - 20, foot[1] - 2, foot[0] + 4, foot[1] + 8), tuple(min(255, c + 52) for c in look.shoes), None)
    # hood / collar bunched behind the neck
    _ell(d, (170, 326, 310, 384), look.top_d)
    # torso
    _round(d, (152, 340, 328, 480), 46, look.top, INK, 4)
    # pocket
    _poly(d, [(188, 424), (292, 424), (304, 462), (176, 462)], look.top_d, INK, 3)
    # drawstrings
    for x0, x1 in ((222, 218), (258, 262)):
        _thick(d, (x0, 358), (x1, 428), 3, CREAM)
        _ell(d, (x1 - 5, 424, x1 + 5, 438), CREAM, INK, 2)
    # skirt or trousers
    if look.skirt:
        _poly(d, [(160, 466), (320, 466), (350, 536), (130, 536)], look.bottom, INK, 4)
    else:
        _round(d, (166, 466, 314, 548), 30, look.bottom, INK, 4)
    # scarf wrap
    if look.scarf:
        _round(d, (170, 322, 310, 362), 20, look.scarf, INK, 4)
    else:
        _round(d, (186, 326, 294, 352), 14, look.top_d, INK, 4)
    return im


def scarf_tail(sway_q, look=YUKI):
    """Scarf tail hanging from the right of the neck; sway_q in -4..4."""
    im, d = _canvas(120, 200)
    sw = sway_q * 3
    top = (30, 8)
    _thick(d, (top[0] + 22, top[1] + 14), (top[0] + 28 + sw * 1.6, 128), 40, look.scarf)
    _thick(d, (top[0] + 28 + sw * 1.6, 124), (top[0] + 28 + sw * 1.6, 132), 40, tuple(int(c * .78) for c in look.scarf))
    _thick(d, (top[0] + 22, top[1] + 14), (top[0] + 28 + sw * 1.6, 120), 40, look.scarf)
    return im


TAIL_ANCHOR = (260, 336)   # figure coords of tail top-left (+8px inset)


ARM_R = 150   # arm canvas is a square of 2*ARM_R units centred on the shoulder


def arm_img(side, a_q, b_q, look=YUKI):
    """Draw one arm on a small canvas centred on its shoulder.
    Angles in degrees (quantised) measured from straight-down, outward positive."""
    a, b = math.radians(a_q), math.radians(b_q)
    sgn = -1 if side == "L" else 1
    sx, sy = ARM_R, ARM_R
    ex, ey = sx + sgn * math.sin(a) * UPPER, sy + math.cos(a) * UPPER
    hx, hy = ex + sgn * math.sin(b) * FORE, ey + math.cos(b) * FORE
    im, d = _canvas(2 * ARM_R, 2 * ARM_R)
    _thick(d, (sx, sy), (ex, ey), 36, look.sleeve)
    _thick(d, (ex, ey), (hx, hy), 36, look.sleeve)
    # cuff + hand
    ux, uy = (hx - ex) / FORE, (hy - ey) / FORE
    cx, cy = hx - ux * 6, hy - uy * 6
    _thick(d, (cx, cy), (hx, hy), 32, look.top_d)
    px, py = hx + ux * 13, hy + uy * 13
    _ell(d, (px - 18, py - 18, px + 18, py + 18), look.skin, INK, 4)
    return im


def _small(im, scale):
    w, h = im.size
    return im.resize((max(1, int(w * scale / SS)), max(1, int(h * scale / SS))), Image.LANCZOS)


# Cache only the small, already-scaled pieces (the 3x supersampled originals are large).
@functools.lru_cache(maxsize=96)
def body_small(phase_q, s, look=YUKI):
    return _small(body_base(phase_q, 0, look), s)


@functools.lru_cache(maxsize=48)
def scarf_small(sway_q, s, look=YUKI):
    return _small(scarf_tail(sway_q, look), s)


@functools.lru_cache(maxsize=2500)
def arm_small(side, a_q, b_q, s, look=YUKI):
    return _small(arm_img(side, a_q, b_q, look), s)


@functools.lru_cache(maxsize=900)
def head_small(mouth, eyes, brow, gaze, s, look=YUKI, cover=None):
    return _small(head_base(mouth, eyes, brow, gaze, look, cover), s)


# ------------------------------------------------------------------ poses
# (alpha, beta) for the viewer-left arm and viewer-right arm
POSES = {
    "rest":     dict(L=(-6, -58), R=(-6, -58)),
    "relax":    dict(L=(10, 6), R=(10, 6)),
    "talk_a":   dict(L=(14, -20), R=(46, 78)),
    "talk_b":   dict(L=(46, 78), R=(14, -20)),
    "present":  dict(L=(56, 78), R=(56, 78)),
    "point_r":  dict(L=(10, -30), R=(78, 104)),
    "point_l":  dict(L=(78, 104), R=(10, -30)),
    "shrug":    dict(L=(50, 122), R=(50, 122)),
    "think":    dict(L=(-6, -58), R=(-12, -152), front=True),
    "wave":     dict(L=(8, -20), R=(62, 168)),
    "cheer":    dict(L=(142, 166), R=(142, 166)),
    "hug":      dict(L=(-14, -88), R=(-14, -88)),
    # --- collage poses
    "cross":    dict(L=(4, -96), R=(4, -96), front=True),                 # arms crossed (smug / unimpressed)
    "head":     dict(L=(-6, -58), R=(130, 176), front=True),              # hand on the side of the head (worried, confused)
    "head_l":   dict(L=(130, 176), R=(-6, -58), front=True),
    "idea":     dict(L=(-6, -58), R=(140, 178), front=True),              # finger up
    "pen":      dict(L=(10, -30), R=(66, 112)),                           # pointing with a pen
    "magnify":  dict(L=(10, -30), R=(62, 118)),                           # holding a magnifying glass
    "think_l":  dict(L=(-12, -152), R=(-6, -58), front=True),
    "slump":    dict(L=(4, -8), R=(4, -8)),                               # tired, arms hanging
}
POSES.update({
    "facepalm":   dict(L=(-6, -58), R=(-8, -104), front=True),                 # (the hand over the face is drawn on the head)
    "sob":        dict(L=(-8, -100), R=(-8, -100), front=True),
    "clap":       dict(L=(-10, -110), R=(-10, -110), front=True),
    "hands_up":   dict(L=(96, 142), R=(96, 142)),                              # "don't shoot" / surprised
    "shy":        dict(L=(-4, -32), R=(-4, -32), front=True),                  # hands together, fidgeting
    "stop":       dict(L=(-6, -58), R=(74, 152)),
    "hips":       dict(L=(42, -26), R=(42, -26)),
    "heart":      dict(L=(-8, -132), R=(-8, -132), front=True),                # hands on the chest
    "dance":      dict(L=(120, 150), R=(120, 150)),
    "shake":      dict(L=(4, -44), R=(4, -44), front=True),                    # trembling, arms tight
    "gasp_hands": dict(L=(66, 168), R=(66, 168), front=True),                  # both hands up beside the face
    "fist":       dict(L=(-6, -58), R=(34, -168), front=True),
    "wave_both":  dict(L=(62, 168), R=(62, 168)),
    "bow":        dict(L=(-4, -38), R=(-4, -38), front=True),
})
PROPS = {"pen": ("R", "pen"), "magnify": ("R", "magnify")}
COVER = {"facepalm": "one", "sob": "both"}


class Rig:
    """Animated state for one Yuki. Call update() once per frame, then draw()."""

    def __init__(self, x, floor_y, scale=0.72, look=YUKI):
        self.look = look
        self.x, self.floor_y, self.scale = float(x), floor_y, scale
        self.target_x = float(x)
        self.vx = 0.0
        self.walk = 0.0
        self.arms = {"L": [-6.0, -58.0], "R": [-6.0, -58.0]}
        self.tilt = 0.0
        self.nod = 0.0
        self.t = 0.0
        self.front = False
        self.brow = "neutral"
        self.face = "neutral"
        self.gaze = 0.0
        self.bounce = 0.0

    def update(self, dt, pose="rest", tilt=0.0, wiggle=0.0, speaking=0.0, face="neutral", gaze=0.0, hop=0.0):
        self.t += dt
        k = 1 - math.exp(-dt * 5.5)
        P = POSES.get(pose, POSES["rest"])
        for s in ("L", "R"):
            ta, tb = P[s]
            if pose == "wave" and s == "R":
                tb += 14 * math.sin(self.t * 7.5)
            if pose in ("talk_a", "talk_b", "present", "shrug"):
                ph = 0.0 if s == "L" else 1.9
                ta += wiggle * 6 * (math.sin(self.t * 2.3 + ph) + 0.6 * math.sin(self.t * 4.1 + ph * 2))
                tb += wiggle * 9 * (math.sin(self.t * 1.9 + ph + 0.8) + 0.5 * math.sin(self.t * 3.7 + ph))
            self.arms[s][0] += (ta - self.arms[s][0]) * k
            self.arms[s][1] += (tb - self.arms[s][1]) * k
        self.front = bool(P.get("front", False))
        self.tilt += (tilt + 1.6 * math.sin(self.t * 1.1) + 1.0 * math.sin(self.t * 2.7 + 1) - self.tilt) * (1 - math.exp(-dt * 3.5))
        self.nod += ((2.2 * speaking * (0.5 + 0.5 * math.sin(self.t * 5.3)) + 1.2 * speaking) - self.nod) * (1 - math.exp(-dt * 8))
        self.brow = {"neutral": "neutral", "curious": "raised", "worried": "worried", "happy": "happy", "excited": "raised",
                     "angry": "angry", "sad": "sad", "shocked": "raised"}.get(face, "neutral")
        self.gaze += (gaze - self.gaze) * (1 - math.exp(-dt * 8))
        self.face = face
        # horizontal movement toward target with easing
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

    def draw(self, frame, mouth, blink):
        s = self.scale
        t = self.t
        moving = self.moving
        phase_q = int(round(math.sin(self.walk * 2 * math.pi) * 6)) if moving else 0
        bob = 2.6 * math.sin(t * 1.7) + 1.0 * math.sin(t * 3.1) + (7 * abs(math.sin(self.walk * 2 * math.pi)) if moving else 0)
        if self.bounce > 0:
            bob += 14 * math.sin(self.bounce * math.pi)
        eyes = "blink" if blink else {"happy": "happy", "excited": "wide", "curious": "wide", "shocked": "wide"}.get(self.face, "open")
        if blink and self.face == "happy":
            eyes = "happy"
        gq = int(round(max(-1, min(1, self.gaze))))
        fig = Image.new("RGBA", (int(FW * s) + 2, int(FH * s) + 2), (0, 0, 0, 0))

        L = self.look
        fig.alpha_composite(body_small(phase_q, s, L))
        sway = int(round(2.4 * math.sin(t * 2.2) + self.vx / 120.0))
        sway = max(-4, min(4, sway))
        if L.scarf:
            fig.alpha_composite(scarf_small(sway, s, L), (int((TAIL_ANCHOR[0] - 30) * s), int((TAIL_ANCHOR[1] - 8) * s)))
        q = lambda v: int(round(v / 3.0)) * 3
        arms = [(sd, q(self.arms[sd][0]), q(self.arms[sd][1])) for sd in ("L", "R")]

        def paste_arm(sd, a, b):
            sx, sy = SHOULDER[sd]
            fig.alpha_composite(arm_small(sd, a, b, s, L), (int((sx - ARM_R) * s), int((sy - ARM_R) * s)))

        if not self.front:
            for sd, a, b in arms:
                paste_arm(sd, a, b)
        # head: rotate around the neck
        hs = head_small(int(mouth), eyes, self.brow, gq, s, L)
        pad = int(60 * s)
        hc = Image.new("RGBA", (hs.width + 2 * pad, hs.height + 2 * pad), (0, 0, 0, 0))
        hc.alpha_composite(hs, (pad, pad))
        pivot = ((NECK[0] - HEAD_POS[0]) * s + pad, (NECK[1] - HEAD_POS[1]) * s + pad)
        hc = hc.rotate(-self.tilt, resample=Image.BICUBIC, center=pivot)
        fig.alpha_composite(hc, (int(HEAD_POS[0] * s - pad), int(HEAD_POS[1] * s - pad + self.nod * s)))
        if self.front:
            for sd, a, b in arms:
                paste_arm(sd, a, b)
        # place on frame: feet bottom at floor_y
        ox = int(self.x - 240 * s)
        oy = int(self.floor_y - 660 * s - bob)
        # soft shadow
        sh = Image.new("RGBA", (int(230 * s), int(40 * s)), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((0, 0, sh.width - 1, sh.height - 1), fill=(0, 0, 0, 70))
        sh = sh.filter(ImageFilter.GaussianBlur(4))
        _clip_composite(frame, sh, int(self.x - sh.width / 2), int(self.floor_y - sh.height / 2 - 2))
        _clip_composite(frame, fig, ox, oy)


def _clip_composite(frame, layer, x, y):
    fw, fh = frame.size
    lw, lh = layer.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(fw, x + lw), min(fh, y + lh)
    if x1 <= x0 or y1 <= y0:
        return
    crop = layer.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    frame.alpha_composite(crop, (x0, y0))


# ------------------------------------------------------------------ stateless renderer
FACES = {   # face -> (eyes, brow, closed-mouth shape, open-smile when talking loud)
    "neutral": ("open", "neutral", 0), "smile": ("open", "happy", 0), "happy": ("happy", "happy", 0), "worried": ("wide", "sad", 0),
    "shocked": ("wide", "neutral", 2), "curious": ("wide", "raised", 3), "angry": ("open", "angry", 0), "sleepy": ("sleepy", "neutral", 6),
    "smug": ("smug", "neutral", 5), "serene": ("blink", "neutral", 0), "sad": ("open", "sad", 0), "excited": ("wide", "raised", 0),
}
FACES.update({
    "laughing":    ("lines", "happy", 9),   "crying":      ("tears", "sad", 14),      "teary":      ("tears", "sad", 11),
    "starry":      ("sparkle", "happy", 4), "lovestruck":  ("heart", "happy", 4),     "dizzy":      ("swirl", "neutral", 8),
    "deadpan":     ("dot", "neutral", 6),   "nervous":     ("wide", "sad", 8),        "gasp":       ("tiny", "raised", 7),
    "terrified":   ("tiny", "sad", 13),     "cheeky":      ("wink", "happy", 12),     "scheming":   ("smug", "happy", 10),
    "proud":       ("happy", "happy", 10),  "pained":      ("lines", "sad", 13),      "creepy":     ("dead", "neutral", 0),
    "determined":  ("open", "angry", 5),    "confused":    ("open", "raised", 8),     "awkward":    ("dot", "sad", 8),
    "embarrassed": ("shy", "sad", 8),       "inspired":    ("sparkle", "raised", 4),  "bored":      ("dot", "neutral", 6),
    "grumpy":      ("open", "angry", 11),   "dreamy":      ("blink", "happy", 10),    "yum":        ("happy", "happy", 12),
})
LOCK_MOUTH = {"laughing", "crying", "teary", "gasp", "terrified", "pained", "nervous", "awkward", "embarrassed", "cheeky", "yum"}   # keep their own mouth while talking
TALK_SHAPE = {0: None, 1: 3, 2: 1, 3: 2}
VISEME_MOUTH = {1: 1, 2: 2, 3: 3, 4: 15, 5: 16}   # eh, ah, small, ee, oo


def _lerp(a, b, k):
    return a + (b - a) * k


def pose_arms(pose, t, wiggle=1.0):
    """-> ({'L': (a, b), 'R': (a, b)}, front) for a pose name at time t (talking gestures sway a little)."""
    P = POSES.get(pose, POSES["rest"])
    out = {}
    for sd in ("L", "R"):
        a, b = P[sd]
        if pose == "wave" and sd == "R":
            b += 14 * math.sin(t * 7.5)
        if pose == "clap":
            b += 17 * math.sin(t * 13) ; a += 5 * math.sin(t * 13)
        elif pose == "dance":
            a += 16 * math.sin(t * 6 + (0 if sd == "L" else math.pi)); b += 14 * math.sin(t * 6 + (0 if sd == "L" else math.pi))
        elif pose == "shake":
            a += 3 * math.sin(t * 34 + (0 if sd == "L" else 1.3)); b += 3 * math.sin(t * 29)
        elif pose == "wave_both":
            b += 14 * math.sin(t * 7.5 + (0 if sd == "L" else 1.6))
        elif pose in ("shy", "sob"):
            b += 6 * math.sin(t * 5.2 + (0 if sd == "L" else 0.9))
        if pose in ("talk_a", "talk_b", "present", "shrug", "pen", "magnify", "hands_up", "stop", "hips", "gasp_hands"):
            ph = 0.0 if sd == "L" else 1.9
            a += wiggle * 6 * (math.sin(t * 2.3 + ph) + 0.6 * math.sin(t * 4.1 + ph * 2))
            b += wiggle * 9 * (math.sin(t * 1.9 + ph + 0.8) + 0.5 * math.sin(t * 3.7 + ph))
        out[sd] = (a, b)
    return out, bool(P.get("front", False))


def _prop_sprite(kind, s):
    if kind == "pen":
        im, d = _canvas(110, 110)
        _thick(d, (22, 88), (82, 24), 9, (40, 40, 52))
        _thick(d, (70, 38), (86, 20), 9, (232, 70, 76))
        _ell(d, (14, 84, 28, 100), (60, 60, 80), None)
        return _small(im, s)
    im, d = _canvas(150, 150)                                           # magnifying glass
    _thick(d, (36, 118), (70, 84), 14, (120, 82, 60))
    _ell(d, (56, 10, 146, 100), (150, 200, 235), None)
    _ell(d, (64, 18, 138, 92), (214, 238, 252), None)
    _ell(d, (74, 26, 100, 48), (255, 255, 255), None)
    d.arc([v * SS for v in (60, 14, 142, 96)], 0, 360, fill=(104, 78, 70), width=9 * SS)
    return _small(im, s)


def draw_figure(frame, x, floor_y, s, pose="rest", prev_pose=None, blend=1.0, t=0.0, face="neutral", amp=0.0, vis=None, gaze=0, tilt=0.0,
                flip=False, hop=0.0, wiggle=1.0, shadow=False, look=YUKI):
    """Draw Yuki onto `frame` (RGBA) with her feet at (x, floor_y). Everything depends only on the arguments.
    pose / prev_pose: names in POSES (arms ease from prev_pose to pose as blend goes 0 -> 1); face: key of FACES;
    amp: 0..1 loudness of her voice right now (drives the mouth); hop: 0..1 progress of a little jump."""
    k = max(0.0, min(1.0, blend)); k = k * k * (3 - 2 * k)
    arms_b, front_b = pose_arms(pose, t, wiggle)
    if prev_pose and k < 1.0:
        arms_a, front_a = pose_arms(prev_pose, t, wiggle)
        arms = {sd: (_lerp(arms_a[sd][0], arms_b[sd][0], k), _lerp(arms_a[sd][1], arms_b[sd][1], k)) for sd in arms_b}
        front = front_b if k > 0.5 else front_a
    else:
        arms, front = arms_b, front_b
    eyes, brow, closed = FACES.get(face, FACES["neutral"])
    # blinking on a fixed schedule (slow when sleepy)
    per = 5.2 if face == "sleepy" else 3.3
    blink = ((t + 0.9) % per) < (0.22 if face == "sleepy" else 0.13)
    if blink and eyes in ("open", "wide", "sleepy", "smug", "dot", "dead"):
        eyes = "blink"
    q = 0 if amp < 0.11 else 1 if amp < 0.34 else 2 if amp < 0.66 else 3
    if vis is not None:
        q = 0 if (vis == 0 and amp < 0.11) else max(q, 1)
        mouth = closed if vis == 0 else VISEME_MOUTH[vis]
    else:
        mouth = closed if q == 0 else TALK_SHAPE[q]
        if q == 3 and face in ("happy", "smile", "excited"):
            mouth = 4
        if q and face == "smug" and q < 3:
            mouth = 1
    sway = max(-4, min(4, int(round(2.4 * math.sin(t * 2.2)))))
    bob = 2.6 * math.sin(t * 1.7) + 1.0 * math.sin(t * 3.1) + (14 * math.sin(max(0.0, min(1.0, hop)) * math.pi) if hop > 0 else 0)
    head_tilt = tilt + 1.6 * math.sin(t * 1.1) + 1.0 * math.sin(t * 2.7 + 1)
    nod = 1.2 * (1 if q else 0) + 2.2 * (0.5 + 0.5 * math.sin(t * 5.3)) * (1 if q else 0)
    gq = int(max(-1, min(1, gaze)))
    fig = Image.new("RGBA", (int(FW * s) + 2, int(FH * s) + 2), (0, 0, 0, 0))
    fig.alpha_composite(body_small(0, s, look))
    if look.scarf:
        fig.alpha_composite(scarf_small(sway, s, look), (int((TAIL_ANCHOR[0] - 30) * s), int((TAIL_ANCHOR[1] - 8) * s)))
    qa = lambda v: int(round(v / 3.0)) * 3
    arm_list = [(sd, qa(arms[sd][0]), qa(arms[sd][1])) for sd in ("L", "R")]

    def paste_arm(sd, a, b):
        sx, sy = SHOULDER[sd]
        fig.alpha_composite(arm_small(sd, a, b, s, look), (int((sx - ARM_R) * s), int((sy - ARM_R) * s)))

    def paste_prop(sd, a, b):
        pr = PROPS.get(pose)
        if not pr or pr[0] != sd or blend < 0.6:
            return
        sgn = -1 if sd == "L" else 1
        ar, br = math.radians(a), math.radians(b)
        sx, sy = SHOULDER[sd]
        ex, ey = sx + sgn * math.sin(ar) * UPPER, sy + math.cos(ar) * UPPER
        hx, hy = ex + sgn * math.sin(br) * FORE, ey + math.cos(br) * FORE
        sp = _prop_sprite(pr[1], s)
        if pr[1] == "pen":
            fig.alpha_composite(sp, (int((hx - 20) * s), int((hy - 92) * s)))
        else:
            fig.alpha_composite(sp, (int((hx - 36) * s), int((hy - 94) * s)))

    if not front:
        for sd, a, b in arm_list:
            paste_arm(sd, a, b)
    hs = head_small(int(mouth), eyes, brow, gq, s, look, COVER.get(pose) if (blend >= 0.5 or not prev_pose) else COVER.get(prev_pose))
    pad = int(60 * s)
    hc = Image.new("RGBA", (hs.width + 2 * pad, hs.height + 2 * pad), (0, 0, 0, 0))
    hc.alpha_composite(hs, (pad, pad))
    pivot = ((NECK[0] - HEAD_POS[0]) * s + pad, (NECK[1] - HEAD_POS[1]) * s + pad)
    hc = hc.rotate(-head_tilt, resample=Image.BICUBIC, center=pivot)
    fig.alpha_composite(hc, (int(HEAD_POS[0] * s - pad), int(HEAD_POS[1] * s - pad + nod * s)))
    if front:
        for sd, a, b in arm_list:
            paste_arm(sd, a, b)
    for sd, a, b in arm_list:
        paste_prop(sd, a, b)
    if flip:
        fig = fig.transpose(Image.FLIP_LEFT_RIGHT)
    ox = int(x - 240 * s)
    oy = int(floor_y - 660 * s - bob)
    if shadow:
        sh = Image.new("RGBA", (int(230 * s), int(40 * s)), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((0, 0, sh.width - 1, sh.height - 1), fill=(0, 0, 0, 55))
        sh = sh.filter(ImageFilter.GaussianBlur(4))
        _clip_composite(frame, sh, int(x - sh.width / 2), int(floor_y - sh.height / 2 - 2))
    _clip_composite(frame, fig, ox, oy)
    return (ox, oy)
