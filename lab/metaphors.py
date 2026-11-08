"""Visual metaphors: drawings for ABSTRACT ideas (overthinking, replaying the past, the unknown future, being stuck, letting go, a choice ...).

Self-improvement and psychology scripts talk about things you cannot photograph.  Instead of a random living room, the lab now draws the
idea itself: a tangled scribble for overthinking, a thought cloud with a looping arrow for rumination, a clock running backwards for the
past, a crystal ball for the future, a maze for being stuck, balloons for letting go ...

Same contract as entities.py: fn(cv, cx, cy, s, t, pal, seed), flat shapes, no outlines, a little motion from t.  They are registered in
entities.ENTITY_FN, so they can be shown by name like every other drawing.
"""
import math
from . import entities as E

TAU = math.tau

INDIGO = (86, 84, 172)
INDIGO_D = (58, 56, 128)
LAV = (214, 210, 250)
LAV_L = (240, 238, 255)
CORAL = (240, 98, 108)
GOLD = (255, 200, 80)
TEAL = (84, 196, 190)
MINT = (150, 226, 182)
SKY = (120, 180, 255)
CREAM = (252, 248, 240)
WOOD = (150, 108, 78)
INK = (52, 48, 90)


def _wob(t, k, a=1.0):
    return math.sin(t * k) * a


# ------------------------------------------------------------------ overthinking / chaos
def tangle(cv, cx, cy, s, t, pal, seed=0):
    """A scribble ball that keeps winding itself up: overthinking, confusion, chaos, a complicated mess."""
    sc = s / 300
    cv.glow(cx, cy, 190 * sc, (170, 160, 255), 0.28, 2.0)
    cols = [INDIGO, CORAL, INDIGO_D, (130, 120, 220), INDIGO, TEAL]
    for i in range(6):
        pts = []
        n = 90
        ph = t * (0.55 if i % 2 else -0.45) + i * 1.1 + seed * 0.3
        ka, kb = 3 + (i % 3), 2 + (i % 2)
        for k in range(n + 1):
            u = k / n * TAU
            r = (70 + 46 * math.sin(u * kb + ph)) * (0.86 + 0.14 * math.sin(i + u))
            a = u * ka * 0.5 + ph * 0.4
            pts.append((cx + math.cos(u + ph * 0.3) * r * (1.0 + 0.18 * math.sin(a)) * 1.12, cy + math.sin(u * 1.0 + ph * 0.3) * r * 0.9 * (1.0 + 0.16 * math.cos(a))))
        cv.polyline(pts, (7 if i % 3 == 0 else 5) * sc, cols[i], alpha=235 if i < 4 else 170, cap=False)
    for i in range(4):                                   # little sparks of stress
        a = t * 1.7 + i * TAU / 4
        r = 150 * sc + _wob(t, 5 + i, 8 * sc)
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.8
        cv.line((x - 9 * sc, y), (x + 9 * sc, y), 4 * sc, GOLD); cv.line((x, y - 9 * sc), (x, y + 9 * sc), 4 * sc, GOLD)


def _cloud(cv, cx, cy, sc, fill, shade, wob=0.0):
    blobs = [(-92, 20, 62), (-38, -34, 74), (34, -44, 78), (92, -2, 66), (60, 38, 62), (-30, 46, 60)]
    for dx, dy, r in blobs:
        cv.circle(cx + dx * sc, cy + dy * sc + 7 * sc, r * sc, shade)
    for dx, dy, r in blobs:
        cv.circle(cx + dx * sc, cy + dy * sc, r * sc, fill)
    cv.circle(cx - 118 * sc, cy + 118 * sc + wob, 15 * sc, fill); cv.circle(cx - 92 * sc, cy + 92 * sc + wob, 24 * sc, fill)


def _mini_speech(cv, x, y, sc, fill, dots, t, flip=False):
    w, h = 50 * sc, 34 * sc
    cv.rect(x - w, y - h, x + w, y + h, fill, r=17 * sc)
    d = -1 if flip else 1
    cv.poly([(x - 22 * sc * d, y + h - 3 * sc), (x - 40 * sc * d, y + h + 20 * sc), (x - 4 * sc * d, y + h - 3 * sc)], fill)
    for i in range(3):
        cv.circle(x - 22 * sc + i * 22 * sc, y - 2 * sc - abs(math.sin(t * 4 - i * 0.7)) * 5 * sc, 5.5 * sc, dots)


def thought_loop(cv, cx, cy, s, t, pal, seed=0):
    """A thought cloud in which the same little conversation goes round and round: replaying, rumination, a habit loop, 'again and again'."""
    sc = s / 300
    cv.glow(cx, cy, 200 * sc, (190, 180, 255), 0.25, 2.0)
    _cloud(cv, cx, cy - 10 * sc, sc, LAV_L, LAV, wob=_wob(t, 2.0, 3 * sc))
    R = 74 * sc
    sp = (t * 70) % 360
    cv.arc_poly(cx, cy - 12 * sc, R - 5 * sc, R + 5 * sc, sp, sp + 250, INDIGO, alpha=230, n=36)           # the looping arrow
    a_end = math.radians(sp + 250)
    ex, ey = cx + R * math.cos(a_end), cy - 12 * sc + R * math.sin(a_end)
    tx, ty = -math.sin(a_end), math.cos(a_end)
    nx, ny = math.cos(a_end), math.sin(a_end)
    cv.poly([(ex + tx * 24 * sc, ey + ty * 24 * sc), (ex + nx * 15 * sc, ey + ny * 15 * sc), (ex - nx * 15 * sc, ey - ny * 15 * sc)], INDIGO)
    for i in range(2):                                    # the same two sentences, chasing each other
        a = math.radians(t * 70 * 0.9 + i * 180 + 40)
        _mini_speech(cv, cx + math.cos(a) * 74 * sc * 0.62, cy - 12 * sc + math.sin(a) * 74 * sc * 0.5, sc * 0.62, [CORAL, TEAL][i], CREAM, t, flip=bool(i))


# ------------------------------------------------------------------ past / future
def rewind_clock(cv, cx, cy, s, t, pal, seed=0):
    """A clock running backwards with a rewind arrow: the past, memories, regret, 'what I said yesterday'."""
    sc = s / 300
    cv.glow(cx, cy, 200 * sc, (255, 190, 140), 0.26, 2.0)
    cv.circle(cx, cy, 118 * sc, INDIGO_D); cv.circle(cx, cy, 106 * sc, CREAM)
    for i in range(12):
        a = TAU * i / 12 - math.pi / 2
        cv.line((cx + math.cos(a) * 88 * sc, cy + math.sin(a) * 88 * sc), (cx + math.cos(a) * 100 * sc, cy + math.sin(a) * 100 * sc), (7 if i % 3 == 0 else 4) * sc, INDIGO_D, cap=False)
    for k in range(5, 0, -1):                              # fading trail of earlier hand positions
        am = -(t - k * 0.07) * 4.6 - math.pi / 2
        cv.line((cx, cy), (cx + math.cos(am) * 80 * sc, cy + math.sin(am) * 80 * sc), 6 * sc, CORAL, alpha=int(46 / k * 3.2))
    ah = -t * 0.38 - math.pi / 2; am = -t * 4.6 - math.pi / 2
    cv.line((cx, cy), (cx + math.cos(ah) * 52 * sc, cy + math.sin(ah) * 52 * sc), 10 * sc, INDIGO_D)
    cv.line((cx, cy), (cx + math.cos(am) * 80 * sc, cy + math.sin(am) * 80 * sc), 7 * sc, CORAL)
    cv.circle(cx, cy, 9 * sc, INDIGO_D)
    # rewind arrow, counter-clockwise around the clock
    a0, a1 = 150, 330
    cv.arc_poly(cx, cy, 134 * sc, 146 * sc, a0, a1, GOLD, n=40)
    ex, ey = cx + 140 * sc * math.cos(math.radians(a0)), cy + 140 * sc * math.sin(math.radians(a0))
    ang = math.radians(a0 - 90)
    cv.poly([(ex + math.cos(ang) * 30 * sc, ey + math.sin(ang) * 30 * sc), (ex + math.cos(math.radians(a0)) * 22 * sc, ey + math.sin(math.radians(a0)) * 22 * sc),
             (ex - math.cos(math.radians(a0)) * 22 * sc, ey - math.sin(math.radians(a0)) * 22 * sc)], GOLD)


def _star4(cv, x, y, r, fill, alpha=255):
    cv.poly([(x, y - r), (x + r * 0.28, y - r * 0.28), (x + r, y), (x + r * 0.28, y + r * 0.28), (x, y + r), (x - r * 0.28, y + r * 0.28), (x - r, y), (x - r * 0.28, y - r * 0.28)], fill, alpha)


def crystal_ball(cv, cx, cy, s, t, pal, seed=0):
    """A crystal ball with swirling stars: the future, predictions, 'what if', the unknown."""
    sc = s / 300
    cv.glow(cx, cy - 10 * sc, 210 * sc, (190, 150, 255), 0.3, 2.0)
    cv.poly([(cx - 96 * sc, cy + 132 * sc), (cx + 96 * sc, cy + 132 * sc), (cx + 62 * sc, cy + 78 * sc), (cx - 62 * sc, cy + 78 * sc)], WOOD)
    cv.rect(cx - 104 * sc, cy + 124 * sc, cx + 104 * sc, cy + 142 * sc, (120, 84, 60), r=8 * sc)
    cv.circle(cx, cy - 6 * sc, 114 * sc, (122, 104, 206))
    cv.circle(cx, cy - 6 * sc, 104 * sc, (166, 148, 240))
    cv.circle(cx - 14 * sc, cy - 22 * sc, 78 * sc, (190, 176, 252), alpha=190)
    for i in range(7):
        a = t * (0.9 + 0.12 * i) + i * 0.9
        r = (30 + 14 * (i % 3)) * sc
        x, y = cx + math.cos(a) * r, cy - 6 * sc + math.sin(a) * r * 0.8
        _star4(cv, x, y, (13 + 4 * (i % 2)) * sc * (0.7 + 0.3 * math.sin(t * 3 + i)), [GOLD, CREAM, MINT][i % 3])
    cv.arc_poly(cx - 6 * sc, cy - 8 * sc, 86 * sc, 94 * sc, 200, 262, (255, 255, 255), alpha=150, n=16)


# ------------------------------------------------------------------ stuck / unknown / choice
_MAZE = [  # wall segments on a 5x5 grid, (x0, y0, x1, y1) in grid units
    (0, 1, 3, 1), (1, 2, 1, 4), (1, 3, 2, 3), (2, 2, 4, 2), (3, 2, 3, 4), (4, 0, 4, 1), (2, 0, 2, 1), (3, 3, 5, 3), (0, 3, 1, 3), (2, 4, 3, 4),
]
_PATH = [(0.5, 0.5), (0.5, 1.5), (0.5, 2.5), (0.5, 3.5), (0.5, 4.5), (1.5, 4.5), (1.5, 3.5)]


def maze(cv, cx, cy, s, t, pal, seed=0):
    """A maze with a little dot that keeps running into dead ends: stuck, lost, uncertain, a hard problem."""
    sc = s / 300
    u = 46 * sc
    x0, y0 = cx - 2.5 * u, cy - 2.5 * u
    cv.rect(x0 - 14 * sc, y0 - 14 * sc, x0 + 5 * u + 14 * sc, y0 + 5 * u + 14 * sc, LAV_L, r=22 * sc)
    for (a, b, c, d) in _MAZE:
        cv.line((x0 + a * u, y0 + b * u), (x0 + c * u, y0 + d * u), 8 * sc, INDIGO)
    cv.polyline([(x0, y0), (x0 + 5 * u, y0), (x0 + 5 * u, y0 + 5 * u), (x0, y0 + 5 * u), (x0, y0)], 9 * sc, INDIGO_D)
    _star4(cv, x0 + 4.5 * u, y0 + 4.5 * u, 16 * sc * (1 + 0.15 * math.sin(t * 4)), GOLD)
    n = len(_PATH) - 1
    ph = (t * 0.5) % 2.0
    k = ph if ph < 1 else 2 - ph                            # walks to the dead end and back, again and again
    seg = min(n - 1, int(k * n)); f = k * n - seg
    p0, p1 = _PATH[seg], _PATH[seg + 1]
    px, py = p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f
    cv.circle(x0 + px * u, y0 + py * u + 3 * sc, 14 * sc, (0, 0, 0), alpha=40)
    cv.circle(x0 + px * u, y0 + py * u, 14 * sc, CORAL)
    cv.circle(x0 + px * u - 4 * sc, y0 + py * u - 4 * sc, 4 * sc, CREAM)


def _qmark(cv, x, y, r, fill, alpha=255):
    w = r * 0.34
    cv.arc_poly(x, y - r * 0.55, r * 0.62 - w / 2, r * 0.62 + w / 2, 180, 440, fill, alpha=alpha, n=24)
    cv.line((x + r * 0.62 * 0.5 * 0, y + r * 0.1), (x, y + r * 0.45), w, fill, alpha=alpha, cap=False)
    cv.circle(x, y + r * 0.92, w * 0.62, fill, alpha=alpha)


def qmarks(cv, cx, cy, s, t, pal, seed=0):
    """Question marks floating about: doubt, the unknown, 'what if', uncertainty."""
    sc = s / 300
    cv.glow(cx, cy, 180 * sc, (190, 180, 255), 0.2, 2.0)
    for i, (dx, dy, r, c) in enumerate([(-70, 20, 92, INDIGO), (56, -52, 70, CORAL), (82, 70, 52, TEAL), (-20, -92, 40, GOLD)]):
        _qmark(cv, cx + dx * sc + _wob(t, 1.6 + i * 0.3, 7 * sc), cy + dy * sc + _wob(t * 1.1 + i, 2.0, 9 * sc), r * sc, c)


def signpost(cv, cx, cy, s, t, pal, seed=0):
    """A signpost pointing two ways: a choice, a decision, direction, 'which way'."""
    sc = s / 300
    sway = _wob(t, 1.2, 1.6)
    cv.rect(cx - 10 * sc, cy - 120 * sc, cx + 10 * sc, cy + 140 * sc, WOOD, r=6 * sc)
    cv.ellipse(cx, cy + 142 * sc, 70 * sc, 14 * sc, (0, 0, 0), alpha=40)
    for (dy, d, c) in ((-96, 1, CORAL), (-26, -1, TEAL), (44, 1, GOLD)):
        y = cy + dy * sc
        x1 = cx + d * 118 * sc
        cv.poly([(cx - d * 18 * sc, y - 28 * sc), (x1 - d * 22 * sc, y - 28 * sc), (x1 + d * 12 * sc, y), (x1 - d * 22 * sc, y + 28 * sc), (cx - d * 18 * sc, y + 28 * sc)], c)
        cv.line((cx - d * 4 * sc, y), (x1 - d * 28 * sc, y), 5 * sc, CREAM, alpha=200)
    cv.circle(cx, cy - 124 * sc, 13 * sc, WOOD)


# ------------------------------------------------------------------ release / growth
def balloons(cv, cx, cy, s, t, pal, seed=0):
    """Balloons drifting away: letting go, release, acceptance, relief."""
    sc = s / 300
    cols = [CORAL, GOLD, TEAL, (170, 140, 240)]
    for i, (dx, base, r) in enumerate([(-86, 10, 52), (-8, -30, 60), (78, 22, 50), (150, 70, 40)]):
        rise = (t * (22 + 6 * i)) % 340 if i == 3 else 0.0
        a = 1.0 if i != 3 else max(0.0, 1.0 - rise / 300)
        x = cx + dx * sc + _wob(t, 1.1 + i * 0.3, 8 * sc) + (rise * 0.1 * sc if i == 3 else 0)
        y = cy + base * sc - r * sc * 0.4 - rise * sc + _wob(t, 1.5 + i * 0.2, 6 * sc)
        if a <= 0.02:
            continue
        al = int(255 * a)
        cv.line((x, y + r * sc * 1.02), (cx + (dx * 0.25) * sc, cy + 150 * sc), 3 * sc, (120, 110, 150), alpha=int(160 * a), cap=False)
        cv.ellipse(x, y, r * sc * 0.9, r * sc, cols[i], alpha=al)
        cv.poly([(x - 6 * sc, y + r * sc * 0.98), (x + 6 * sc, y + r * sc * 0.98), (x, y + r * sc * 1.12)], cols[i], alpha=al)
        cv.ellipse(x - r * sc * 0.3, y - r * sc * 0.35, r * sc * 0.14, r * sc * 0.26, (255, 255, 255), alpha=int(150 * a))


def _bars(cv, cx, cy, s, t, up, c_main, c_arrow):
    sc = s / 300
    cv.rect(cx - 150 * sc, cy - 126 * sc, cx + 150 * sc, cy + 126 * sc, LAV_L, r=26 * sc)
    base = cy + 96 * sc
    cv.line((cx - 120 * sc, base), (cx + 124 * sc, base), 6 * sc, INDIGO_D)
    g = min(1.0, (t * 0.7) % 3.0 / 1.2)
    hs = [0.30, 0.50, 0.72, 1.0] if up else [1.0, 0.74, 0.5, 0.3]
    pts = []
    for i, h in enumerate(hs):
        hh = 150 * sc * h * min(1.0, max(0.0, g * 1.6 - i * 0.28))
        x = cx - 90 * sc + i * 62 * sc
        cv.rect(x - 22 * sc, base - hh, x + 22 * sc, base, c_main, r=8 * sc)
        pts.append((x, base - 150 * sc * h * min(1.0, max(0.0, g * 1.6 - i * 0.28)) - 22 * sc))
    if g > 0.9:
        cv.polyline(pts, 8 * sc, c_arrow)
        (x0_, y0_), (x1_, y1_) = pts[-2], pts[-1]
        a = math.atan2(y1_ - y0_, x1_ - x0_)
        cv.poly([(x1_ + math.cos(a) * 24 * sc, y1_ + math.sin(a) * 24 * sc), (x1_ + math.cos(a + 2.4) * 22 * sc, y1_ + math.sin(a + 2.4) * 22 * sc),
                 (x1_ + math.cos(a - 2.4) * 22 * sc, y1_ + math.sin(a - 2.4) * 22 * sc)], c_arrow)


def bars_up(cv, cx, cy, s, t, pal, seed=0):
    """Bars growing with an arrow: progress, improvement, growth, results."""
    _bars(cv, cx, cy, s, t, True, TEAL, GOLD)


def bars_down(cv, cx, cy, s, t, pal, seed=0):
    """Bars shrinking with an arrow: decline, loss, falling behind, drop."""
    _bars(cv, cx, cy, s, t, False, CORAL, INDIGO_D)


FUNCS = dict(tangle=tangle, thought_loop=thought_loop, rewind_clock=rewind_clock, crystal_ball=crystal_ball, maze=maze, qmarks=qmarks, signpost=signpost,
             balloons=balloons, bars_up=bars_up, bars_down=bars_down)
E.ENTITY_FN.update(FUNCS)
E.ENTITY_EXTENT.update(dict(thought_loop=1.15, rewind_clock=1.1, crystal_ball=1.1, maze=0.9, bars_up=0.9, bars_down=0.9, balloons=1.1, signpost=1.0))
