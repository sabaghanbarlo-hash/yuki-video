"""Yuki: a chibi narrator drawn entirely in code (Pillow), rigged for talking, blinking,
walking and arm gestures. Parts are drawn 3x supersampled, cached, then composited per frame.

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

INK = (24, 20, 30)
HAIR = (28, 28, 38)
HAIR_HI = (92, 98, 124)
SKIN = (255, 224, 198)
SKIN_SH = (238, 196, 170)
BLUSH = (246, 150, 150)
GREEN, GREEN_D, GREEN_L = (104, 158, 106), (76, 124, 86), (138, 186, 132)
RED, RED_D, RED_L = (208, 46, 54), (148, 28, 40), (236, 96, 96)
SKIRT = (40, 38, 48)
LEG, LEG_HI = (32, 30, 40), (70, 68, 84)
CREAM = (244, 236, 218)
MOUTH_IN, TONGUE = (112, 34, 48), (238, 120, 132)


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
    P = _P(SS)
    flat = [tuple(P(*p)) for p in pts]
    d.polygon(flat, fill=fill)
    if outline:
        d.line(flat + [flat[0]], fill=outline, width=width * SS, joint="curve")


def _ell(d, box, fill, outline=INK, width=4):
    P = _P(SS)
    d.ellipse(P(*box), fill=fill, outline=outline, width=(width * SS if outline else 0))


def _round(d, box, r, fill, outline=INK, width=4):
    P = _P(SS)
    d.rounded_rectangle(P(*box), radius=r * SS, fill=fill, outline=outline, width=(width * SS if outline else 0))


def _thick(d, a, b, w, fill):
    P = _P(SS)
    (x1, y1), (x2, y2) = P(*a), P(*b)
    r = w * SS / 2
    d.line([(x1, y1), (x2, y2)], fill=fill, width=int(w * SS))
    d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=fill)
    d.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=fill)


# ------------------------------------------------------------------ head
def head_base(mouth, eyes, brow, gaze):
    """mouth 0..4, eyes 'open'|'blink'|'happy'|'wide', brow 'neutral'|'raised'|'worried'|'happy', gaze -1..1"""
    im, d = _canvas(HW, HH)
    P = _P(SS)
    # back hair (bob)
    _ell(d, (46, 52, 354, 290), HAIR)
    _round(d, (46, 150, 354, 312), 70, HAIR)
    # face
    _ell(d, (56, 96, 344, 330), SKIN)
    # soft chin shade
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    sd.ellipse(P(70, 280, 330, 350), fill=SKIN_SH + (120,))
    mask = Image.new("L", im.size, 0); ImageDraw.Draw(mask).ellipse(P(58, 98, 342, 328), fill=255)
    sh.putalpha(Image.composite(sh.getchannel("A"), Image.new("L", im.size, 0), mask))
    im.alpha_composite(sh)
    d = ImageDraw.Draw(im)
    _ell(d, (56, 96, 344, 330), None, INK, 4)

    # blush
    for cx in (102, 298):
        _ell(d, (cx - 28, 278, cx + 28, 306), BLUSH + (210,), None)

    # eyes
    for k, cx in enumerate((138, 262)):
        ex, ey = cx + gaze * 6, 248
        if eyes in ("open", "wide"):
            ry = 43 if eyes == "wide" else 38
            _ell(d, (ex - 29, ey - ry, ex + 29, ey + ry), (36, 32, 46), None)
            lower = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(lower).ellipse(P(ex - 29, ey - ry, ex + 29, ey + ry), fill=(78, 74, 100, 255))
            m2 = Image.new("L", im.size, 0)
            ImageDraw.Draw(m2).ellipse(P(ex - 29, ey - ry, ex + 29, ey + ry), fill=255)
            ImageDraw.Draw(m2).rectangle(P(ex - 34, ey - ry - 2, ex + 34, ey + 6), fill=0)
            lower.putalpha(m2)
            im.alpha_composite(lower)
            d = ImageDraw.Draw(im)
            _ell(d, (ex - 14 + gaze * 2, ey - ry + 7, ex + 6 + gaze * 2, ey - ry + 27), (255, 255, 255), None)
            _ell(d, (ex + 8, ey + 10, ex + 19, ey + 21), (255, 255, 255), None)
            d.arc(P(ex - 31, ey - ry - 3, ex + 31, ey + ry), 192, 348, fill=INK, width=7 * SS)
            wing = -1 if k == 0 else 1
            d.line(P(ex + wing * 29, ey - ry + 10, ex + wing * 38, ey - ry + 2), fill=INK, width=5 * SS)
        elif eyes == "blink":
            d.arc(P(ex - 29, ey - 14, ex + 29, ey + 14), 20, 160, fill=INK, width=6 * SS)
        elif eyes == "happy":
            d.arc(P(ex - 29, ey - 12, ex + 29, ey + 22), 200, 340, fill=INK, width=6 * SS)

    # mouth
    mx, my = 200, 296
    if mouth == 0:
        d.arc(P(mx - 20, my - 12, mx + 20, my + 8), 20, 160, fill=INK, width=4 * SS)
    elif mouth == 1:
        _ell(d, (mx - 9, my - 8, mx + 9, my + 9), MOUTH_IN, INK, 3)
    elif mouth == 2:
        _ell(d, (mx - 17, my - 10, mx + 17, my + 20), MOUTH_IN, INK, 3)
        _ell(d, (mx - 10, my + 7, mx + 10, my + 19), TONGUE, None)
    elif mouth == 3:
        _ell(d, (mx - 7, my - 7, mx + 7, my + 10), MOUTH_IN, INK, 3)
    else:  # 4: happy open smile
        d.pieslice(P(mx - 20, my - 14, mx + 20, my + 16), 0, 180, fill=MOUTH_IN, outline=INK, width=3 * SS)
        d.pieslice(P(mx - 11, my + 1, mx + 11, my + 15), 0, 180, fill=TONGUE)

    # side locks
    for sgn, x0 in ((1, 56), (-1, 344)):
        pts = [(x0 - sgn * 4, 130), (x0 + sgn * 30, 116), (x0 + sgn * 50, 156), (x0 + sgn * 44, 238),
               (x0 + sgn * 34, 290), (x0 + sgn * 12, 316), (x0 - sgn * 6, 300)]
        _poly(d, pts, HAIR, INK, 4)
    # bangs (parted, soft scallops)
    top = _bez((54, 172), (44, 84), (140, 50), (200, 50), 14) + _bez((200, 50), (262, 50), (356, 84), (346, 172), 14)
    tips = [(346, 170), (306, 214), (258, 198), (216, 220), (176, 178), (136, 210), (96, 230), (56, 176)]
    low = []
    for (a, b) in zip(tips[:-1], tips[1:]):
        mid = ((a[0] + b[0]) / 2, min(a[1], b[1]) - 14)
        low += _bez(a, (a[0], mid[1]), (b[0], mid[1]), b, 8)[1:]
    _poly(d, top + low, HAIR, INK, 4)
    # highlight sweeps
    d.arc(P(96, 62, 262, 168), 205, 262, fill=HAIR_HI, width=9 * SS)
    d.arc(P(210, 64, 330, 142), 250, 296, fill=HAIR_HI, width=7 * SS)

    # brows
    by = {"neutral": 194, "raised": 182, "worried": 196, "happy": 188}[brow]
    for k, cx in enumerate((138, 262)):
        ex = cx + gaze * 6
        if brow == "worried":
            a, b = ((ex - 24, by + 8), (ex + 22, by - 8)) if k == 0 else ((ex - 22, by - 8), (ex + 24, by + 8))
        elif brow == "raised":
            a, b = (ex - 22, by + 3), (ex + 22, by - 3)
        else:
            a, b = (ex - 22, by + 2), (ex + 22, by + 2)
        mid = ((a[0] + b[0]) / 2, min(a[1], b[1]) - (5 if brow in ("raised", "happy") else 2))
        d.line([tuple(P(*p)) for p in _bez(a, (a[0] + 8, mid[1]), (b[0] - 8, mid[1]), b, 8)], fill=INK, width=5 * SS, joint="curve")
    return im


# ------------------------------------------------------------------ body
def body_base(phase_q, bow_q):
    """Legs, skirt, hoodie, scarf wrap, drawstrings. phase_q: -6..6 walk step, or 0."""
    im, d = _canvas(FW, FH)
    swing = phase_q / 6.0
    for side, hx in (("L", 214), ("R", 266)):
        s = -swing if side == "L" else swing
        foot_x = hx + s * 26
        lift = max(0.0, s) * 20
        hip = (hx, 520)
        foot = (foot_x, 626 - lift)
        _thick(d, hip, foot, 46, INK)
        _thick(d, hip, foot, 38, LEG)
        _thick(d, (hip[0] - 9, hip[1] + 8), (foot[0] - 9, foot[1] - 14), 5, LEG_HI)
        # shoe
        _ell(d, (foot[0] - 30, foot[1] - 6, foot[0] + 30, foot[1] + 30), (34, 32, 42), INK, 4)
        _ell(d, (foot[0] - 20, foot[1] - 2, foot[0] + 4, foot[1] + 8), (86, 84, 104), None)
    # hood bunched behind the neck
    _ell(d, (170, 326, 310, 384), GREEN_D)
    # torso
    _round(d, (152, 340, 328, 480), 46, GREEN, INK, 4)
    d.arc(_P(SS)(160, 360, 220, 470), 90, 160, fill=GREEN_L, width=5 * SS)
    # pocket
    _poly(d, [(188, 424), (292, 424), (304, 462), (176, 462)], GREEN_D, INK, 3)
    # drawstrings
    for x0, x1 in ((222, 218), (258, 262)):
        _thick(d, (x0, 358), (x1, 428), 5, INK)
        _thick(d, (x0, 358), (x1, 428), 3, CREAM)
        _ell(d, (x1 - 5, 424, x1 + 5, 438), CREAM, INK, 2)
    # skirt
    skirt = [(160, 466), (320, 466), (350, 536), (130, 536)]
    _poly(d, skirt, SKIRT, INK, 4)
    d.line(_P(SS)(150, 492, 330, 492), fill=(62, 60, 76), width=3 * SS)
    # scarf wrap
    _round(d, (170, 322, 310, 362), 20, RED, INK, 4)
    d.arc(_P(SS)(182, 326, 298, 352), 200, 340, fill=RED_L, width=4 * SS)
    return im


def scarf_tail(sway_q):
    """Scarf tail hanging from the right of the neck; sway_q in -4..4."""
    im, d = _canvas(120, 200)
    sw = sway_q * 3
    top = (30, 8)
    pts = [(top[0], top[1]), (top[0] + 44, top[1]), (top[0] + 54 + sw, 100), (top[0] + 50 + sw * 1.6, 170),
           (top[0] + 22 + sw * 1.6, 188), (top[0] + 6 + sw, 160), (top[0] + 2, 90)]
    _poly(d, pts, RED, INK, 4)
    d.line(_P(SS)(top[0] + 14, top[1] + 14, top[0] + 20 + sw, 150), fill=RED_L, width=4 * SS)
    d.line(_P(SS)(top[0] + 10 + sw, 176, top[0] + 46 + sw * 1.6, 168), fill=RED_D, width=4 * SS)
    return im


TAIL_ANCHOR = (260, 336)   # figure coords of tail top-left (+8px inset)


ARM_R = 150   # arm canvas is a square of 2*ARM_R units centred on the shoulder


def arm_img(side, a_q, b_q):
    """Draw one arm on a small canvas centred on its shoulder.
    Angles in degrees (quantised) measured from straight-down, outward positive."""
    a, b = math.radians(a_q), math.radians(b_q)
    sgn = -1 if side == "L" else 1
    sx, sy = ARM_R, ARM_R
    ex, ey = sx + sgn * math.sin(a) * UPPER, sy + math.cos(a) * UPPER
    hx, hy = ex + sgn * math.sin(b) * FORE, ey + math.cos(b) * FORE
    im, d = _canvas(2 * ARM_R, 2 * ARM_R)
    _thick(d, (sx, sy), (ex, ey), 44, INK)
    _thick(d, (ex, ey), (hx, hy), 44, INK)
    _thick(d, (sx, sy), (ex, ey), 36, GREEN)
    _thick(d, (ex, ey), (hx, hy), 36, GREEN)
    # cuff + hand
    ux, uy = (hx - ex) / FORE, (hy - ey) / FORE
    cx, cy = hx - ux * 6, hy - uy * 6
    _thick(d, (cx, cy), (hx, hy), 40, INK)
    _thick(d, (cx, cy), (hx, hy), 32, GREEN_D)
    px, py = hx + ux * 13, hy + uy * 13
    _ell(d, (px - 18, py - 18, px + 18, py + 18), SKIN, INK, 4)
    return im


def _small(im, scale):
    w, h = im.size
    return im.resize((max(1, int(w * scale / SS)), max(1, int(h * scale / SS))), Image.LANCZOS)


# Cache only the small, already-scaled pieces (the 3x supersampled originals are large).
@functools.lru_cache(maxsize=64)
def body_small(phase_q, s):
    return _small(body_base(phase_q, 0), s)


@functools.lru_cache(maxsize=32)
def scarf_small(sway_q, s):
    return _small(scarf_tail(sway_q), s)


@functools.lru_cache(maxsize=1500)
def arm_small(side, a_q, b_q, s):
    return _small(arm_img(side, a_q, b_q), s)


@functools.lru_cache(maxsize=400)
def head_small(mouth, eyes, brow, gaze, s):
    return _small(head_base(mouth, eyes, brow, gaze), s)


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
}


class Rig:
    """Animated state for one Yuki. Call update() once per frame, then draw()."""

    def __init__(self, x, floor_y, scale=0.72):
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
        k = 1 - math.exp(-dt * 9)
        P = POSES.get(pose, POSES["rest"])
        for s in ("L", "R"):
            ta, tb = P[s]
            if pose == "wave" and s == "R":
                tb += 16 * math.sin(self.t * 9)
            if pose in ("talk_a", "talk_b", "present", "shrug"):
                ta += wiggle * 10 * math.sin(self.t * 7 + (0 if s == "L" else 1.6))
                tb += wiggle * 14 * math.sin(self.t * 6 + (0.7 if s == "L" else 2.2))
            self.arms[s][0] += (ta - self.arms[s][0]) * k
            self.arms[s][1] += (tb - self.arms[s][1]) * k
        self.front = bool(P.get("front", False))
        self.tilt += (tilt + 1.2 * math.sin(self.t * 1.3) - self.tilt) * (1 - math.exp(-dt * 6))
        self.nod += ((3.5 * speaking * abs(math.sin(self.t * 8.5))) - self.nod) * (1 - math.exp(-dt * 14))
        self.brow = {"neutral": "neutral", "curious": "raised", "worried": "worried", "happy": "happy", "excited": "raised"}.get(face, "neutral")
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
        bob = 2.2 * math.sin(t * 2.0) + (7 * abs(math.sin(self.walk * 2 * math.pi)) if moving else 0)
        if self.bounce > 0:
            bob += 14 * math.sin(self.bounce * math.pi)
        eyes = "blink" if blink else {"happy": "happy", "excited": "wide", "curious": "wide"}.get(self.face, "open")
        if blink and self.face == "happy":
            eyes = "happy"
        gq = int(round(max(-1, min(1, self.gaze))))
        fig = Image.new("RGBA", (int(FW * s) + 2, int(FH * s) + 2), (0, 0, 0, 0))

        fig.alpha_composite(body_small(phase_q, s))
        sway = int(round(2.4 * math.sin(t * 2.2) + self.vx / 120.0))
        sway = max(-4, min(4, sway))
        fig.alpha_composite(scarf_small(sway, s), (int((TAIL_ANCHOR[0] - 30) * s), int((TAIL_ANCHOR[1] - 8) * s)))
        q = lambda v: int(round(v / 6.0)) * 6
        arms = [(sd, q(self.arms[sd][0]), q(self.arms[sd][1])) for sd in ("L", "R")]

        def paste_arm(sd, a, b):
            sx, sy = SHOULDER[sd]
            fig.alpha_composite(arm_small(sd, a, b, s), (int((sx - ARM_R) * s), int((sy - ARM_R) * s)))

        if not self.front:
            for sd, a, b in arms:
                paste_arm(sd, a, b)
        # head: rotate around the neck
        hs = head_small(int(mouth), eyes, self.brow, gq, s)
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
