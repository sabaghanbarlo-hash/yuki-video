"""Painted backdrops: flat colours, soft thin lines (thinner than the characters' ink so people pop), one function per place.
build(kind, w, h, seed) -> skia.Image.  Each place also tells where the floor is (fraction of the height)."""
import math, random, functools
import skia
from .gfx import C, fill_paint, line_paint, shade, mix, outlined, smooth_closed, poly_path, INK

SOFT = (70, 52, 84)          # soft line colour
LW = 3.0

PLAIN = {"cream": (252, 240, 222), "peach": (255, 216, 190), "mint": (200, 238, 218), "sky": (186, 220, 248), "lilac": (222, 208, 246),
         "yellow": (255, 236, 160), "rose": (252, 204, 214), "white": (252, 252, 254), "slate": (186, 196, 214), "sage": (206, 224, 190)}
MOOD_PLAIN = {"excited": "yellow", "happy": "peach", "wonder": "lilac", "curious": "sky", "shocked": "rose", "worried": "lilac", "sad": "slate", "angry": "rose", "neutral": "cream"}

FLOOR_Y = {"void": 0.74, "bedroom": 0.76, "office": 0.78, "classroom": 0.78, "kitchen": 0.76, "living": 0.78, "street": 0.80, "park": 0.80, "mind": 0.80, "space": 0.80, "plain": 0.80}


def _r(cv, x0, y0, x1, y1, col, rad=0, line=True, a=255):
    rr = skia.Rect.MakeLTRB(x0, y0, x1, y1)
    cv.drawRoundRect(rr, rad, rad, fill_paint(col, a))
    if line:
        cv.drawRoundRect(rr, rad, rad, line_paint(SOFT, LW, 150))


def _o(cv, x, y, rx, ry, col, line=True):
    rr = skia.Rect.MakeLTRB(x - rx, y - ry, x + rx, y + ry)
    cv.drawOval(rr, fill_paint(col))
    if line:
        cv.drawOval(rr, line_paint(SOFT, LW, 150))


def _poly(cv, pts, col, line=True):
    p = poly_path(pts)
    cv.drawPath(p, fill_paint(col))
    if line:
        cv.drawPath(p, line_paint(SOFT, LW, 150))


def _vgrad(cv, w, h, top, bot, y0=0, y1=None):
    y1 = y1 or h
    sh = skia.GradientShader.MakeLinear([(0, y0), (0, y1)], [C(top), C(bot)])
    p = skia.Paint(AntiAlias=True, Shader=sh)
    cv.drawRect(skia.Rect.MakeLTRB(0, y0, w, y1), p)


def _window(cv, x, y, w, h, night=False, curtain=None):
    sky_t, sky_b = ((30, 40, 90), (70, 80, 140)) if night else ((130, 200, 250), (210, 236, 252))
    _r(cv, x - 8, y - 8, x + w + 8, y + h + 8, (252, 250, 244), 6)
    sh = skia.GradientShader.MakeLinear([(0, y), (0, y + h)], [C(sky_t), C(sky_b)])
    cv.drawRect(skia.Rect.MakeLTRB(x, y, x + w, y + h), skia.Paint(AntiAlias=True, Shader=sh))
    if night:
        rnd = random.Random(int(x))
        for _ in range(9):
            cv.drawCircle(x + rnd.random() * w, y + rnd.random() * h * 0.7, 2.2, fill_paint((255, 250, 210)))
        cv.drawCircle(x + w * 0.74, y + h * 0.28, 22, fill_paint((255, 246, 200)))
    else:
        _o(cv, x + w * 0.3, y + h * 0.7, 46, 20, (255, 255, 255), False)
        _o(cv, x + w * 0.5, y + h * 0.62, 36, 18, (255, 255, 255), False)
    cv.drawLine(x + w / 2, y, x + w / 2, y + h, line_paint((252, 250, 244), 7))
    cv.drawLine(x, y + h / 2, x + w, y + h / 2, line_paint((252, 250, 244), 7))
    cv.drawRect(skia.Rect.MakeLTRB(x, y, x + w, y + h), line_paint(SOFT, LW, 150))
    if curtain:
        for sx in (0, 1):
            xx = x - 14 if sx == 0 else x + w - 26
            p = poly_path([(xx, y - 14), (xx + 40, y - 14), (xx + 52 - 12 * sx, y + h * 0.9), (xx - 12 * sx, y + h * 0.95)])
            cv.drawPath(p, fill_paint(curtain))
            cv.drawPath(p, line_paint(SOFT, LW, 150))


def _plant(cv, x, y, s=1.0):
    _poly(cv, [(x - 24 * s, y - 40 * s), (x + 24 * s, y - 40 * s), (x + 17 * s, y), (x - 17 * s, y)], (214, 120, 92))
    for a, l in ((-40, 80), (-15, 100), (10, 96), (38, 76), (0, 60)):
        ang = math.radians(a - 90)
        ex, ey = x + math.cos(ang) * l * s, y - 40 * s + math.sin(ang) * l * s
        p = skia.Path()
        p.moveTo(x, y - 40 * s)
        p.quadTo((x + ex) / 2 + 14 * s, (y - 40 * s + ey) / 2, ex, ey)
        p.quadTo((x + ex) / 2 - 14 * s, (y - 40 * s + ey) / 2, x, y - 40 * s)
        cv.drawPath(p, fill_paint((96, 176, 108)))
        cv.drawPath(p, line_paint(SOFT, LW, 150))


def _room(cv, w, h, wall, floor, fy, night=False, trim=None):
    cv.drawRect(skia.Rect.MakeLTRB(0, 0, w, h), fill_paint(wall))
    _r(cv, -10, fy - 14, w + 10, fy + 2, trim or shade(wall, -0.08), 0, True)
    cv.drawRect(skia.Rect.MakeLTRB(0, fy, w, h), fill_paint(floor))
    for i in range(1, 9):
        y = fy + (h - fy) * (i / 8) ** 1.6
        cv.drawLine(0, y, w, y, line_paint(shade(floor, -0.1), 2, 130))
    if night:
        cv.drawRect(skia.Rect.MakeLTRB(0, 0, w, h), fill_paint((20, 24, 70), 120))


def _bedroom(cv, w, h, night):
    fy = h * FLOOR_Y["bedroom"]
    _room(cv, w, h, (246, 214, 206) if not night else (120, 110, 150), (214, 176, 140) if not night else (120, 96, 100), fy, night)
    _window(cv, w * 0.12, h * 0.14, w * 0.2, h * 0.34, night, (206, 150, 190))
    _r(cv, w * 0.56, h * 0.18, w * 0.7, h * 0.4, (255, 244, 226), 8)               # poster
    _o(cv, w * 0.63, h * 0.29, 34, 34, (240, 160, 180))
    bx = w * 0.66
    _r(cv, bx, fy - 120, w + 40, fy + 30, (154, 108, 84), 10)                      # bed frame
    _r(cv, bx + 10, fy - 150, bx + 70, fy - 70, (160, 120, 96), 10)
    _r(cv, bx + 10, fy - 96, w + 30, fy - 10, (186, 168, 240), 16)                 # blanket
    _r(cv, bx + 24, fy - 130, bx + 130, fy - 84, (255, 252, 246), 20)              # pillow
    _r(cv, w * 0.38, fy - 70, w * 0.48, fy + 10, (180, 136, 100), 4)               # night stand
    _o(cv, w * 0.43, fy - 100, 22, 22, (255, 226, 150) if not night else (255, 236, 160))
    _o(cv, w * 0.30, fy + 70, 150, 34, (156, 214, 200), True)                      # rug


def _office(cv, w, h, night):
    fy = h * FLOOR_Y["office"]
    _room(cv, w, h, (214, 232, 236) if not night else (96, 112, 150), (172, 164, 160), fy, night)
    _window(cv, w * 0.62, h * 0.12, w * 0.3, h * 0.36, night)
    _o(cv, w * 0.18, h * 0.2, 46, 46, (255, 255, 255))                             # wall clock
    cv.drawLine(w * 0.18, h * 0.2, w * 0.18, h * 0.2 - 30, line_paint(INK, 4))
    cv.drawLine(w * 0.18, h * 0.2, w * 0.18 + 22, h * 0.2 + 8, line_paint(INK, 4))
    dx = w * 0.12
    _r(cv, dx, fy - 80, dx + w * 0.48, fy - 56, (176, 124, 90), 6)                 # desk
    _r(cv, dx + 20, fy - 56, dx + 44, fy + 30, (150, 104, 76))
    _r(cv, dx + w * 0.48 - 44, fy - 56, dx + w * 0.48 - 20, fy + 30, (150, 104, 76))
    _r(cv, dx + 120, fy - 190, dx + 290, fy - 84, (66, 74, 96), 8)                  # monitor
    _r(cv, dx + 130, fy - 180, dx + 280, fy - 94, (140, 204, 240), 4)
    _r(cv, dx + 190, fy - 84, dx + 220, fy - 80, (66, 74, 96))
    _r(cv, dx + 330, fy - 104, dx + 372, fy - 80, (255, 255, 255), 8)              # mug
    _plant(cv, w * 0.9, fy + 10, 0.9)
    _r(cv, w * 0.5, fy - 80, w * 0.58, fy - 10, (136, 150, 190), 10)               # bin


def _classroom(cv, w, h, night):
    fy = h * FLOOR_Y["classroom"]
    _room(cv, w, h, (250, 234, 192), (206, 174, 132), fy, night)
    _r(cv, w * 0.2, h * 0.1, w * 0.78, h * 0.5, (54, 100, 88), 8)                  # blackboard
    _r(cv, w * 0.2, h * 0.5, w * 0.78, h * 0.52, (176, 124, 90), 2)
    cv.drawPath(skia.Path().moveTo(w * 0.3, h * 0.2).quadTo(w * 0.36, h * 0.12, w * 0.42, h * 0.22), line_paint((250, 250, 250), 5, 220))
    cv.drawLine(w * 0.5, h * 0.3, w * 0.64, h * 0.3, line_paint((250, 250, 250), 5, 200))
    cv.drawLine(w * 0.5, h * 0.38, w * 0.6, h * 0.38, line_paint((250, 250, 250), 5, 200))
    _window(cv, w * 0.04, h * 0.14, w * 0.11, h * 0.3, night)
    for i, x in enumerate((w * 0.12, w * 0.58, w * 0.86)):
        _r(cv, x, fy - 12, x + 160, fy + 6, (182, 128, 92), 6)
        cv.drawLine(x + 20, fy + 6, x + 14, fy + 90, line_paint((120, 120, 140), 6))
        cv.drawLine(x + 140, fy + 6, x + 146, fy + 90, line_paint((120, 120, 140), 6))


def _kitchen(cv, w, h, night):
    fy = h * FLOOR_Y["kitchen"]
    _room(cv, w, h, (255, 238, 204), (226, 206, 186), fy, night)
    for x in (w * 0.05, w * 0.2, w * 0.35):
        _r(cv, x, h * 0.1, x + w * 0.13, h * 0.34, (150, 200, 190), 6)             # wall cabinets
        _o(cv, x + w * 0.065, h * 0.22, 5, 5, (240, 240, 240), False)
    _r(cv, 0, fy - 100, w * 0.55, fy + 40, (150, 200, 190), 6)                      # counter
    _r(cv, 0, fy - 110, w * 0.55, fy - 92, (246, 246, 248), 4)
    _window(cv, w * 0.6, h * 0.14, w * 0.14, h * 0.3, night)
    _r(cv, w * 0.8, h * 0.1, w * 0.97, fy + 20, (232, 236, 246), 10)                # fridge
    cv.drawLine(w * 0.8, h * 0.42, w * 0.97, h * 0.42, line_paint(SOFT, LW, 150))
    _r(cv, w * 0.82, h * 0.16, w * 0.835, h * 0.34, (190, 196, 210), 3)
    _o(cv, w * 0.3, fy - 128, 28, 20, (240, 170, 80))
    _r(cv, w * 0.12, fy - 150, w * 0.14, fy - 112, (255, 255, 255), 3)


def _living(cv, w, h, night):
    fy = h * FLOOR_Y["living"]
    _room(cv, w, h, (226, 214, 246) if not night else (110, 100, 160), (196, 156, 124), fy, night)
    _window(cv, w * 0.7, h * 0.12, w * 0.22, h * 0.34, night, (240, 170, 150))
    for i, (x, y, ww, hh, col) in enumerate(((w * 0.1, h * 0.14, 110, 80, (255, 226, 150)), (w * 0.22, h * 0.2, 80, 100, (160, 214, 200)), (w * 0.34, h * 0.12, 90, 70, (246, 170, 184)))):
        _r(cv, x, y, x + ww, y + hh, (255, 252, 246), 4)
        _r(cv, x + 10, y + 10, x + ww - 10, y + hh - 10, col, 2)
    _r(cv, w * 0.06, fy - 120, w * 0.5, fy + 10, (120, 170, 220), 30)               # sofa
    _r(cv, w * 0.04, fy - 80, w * 0.1, fy + 10, (106, 156, 208), 20)
    _r(cv, w * 0.46, fy - 80, w * 0.52, fy + 10, (106, 156, 208), 20)
    _r(cv, w * 0.12, fy - 100, w * 0.2, fy - 50, (250, 214, 120), 12)
    _r(cv, w * 0.6, fy - 90, w * 0.9, fy - 4, (60, 66, 96), 8)                      # tv unit
    _r(cv, w * 0.62, fy - 180, w * 0.88, fy - 84, (30, 34, 54), 8)
    _r(cv, w * 0.63, fy - 172, w * 0.87, fy - 92, (96, 150, 210), 4)
    _plant(cv, w * 0.94, fy + 4, 0.9)


def _street(cv, w, h, night):
    fy = h * FLOOR_Y["street"]
    _vgrad(cv, w, h, (130, 196, 246) if not night else (24, 28, 70), (220, 240, 252) if not night else (78, 80, 140), 0, fy)
    rnd = random.Random(11)
    x = -20
    while x < w:
        bw, bh = rnd.randint(110, 190), rnd.randint(190, 360)
        col = rnd.choice([(250, 200, 160), (200, 214, 246), (246, 190, 200), (212, 236, 200), (250, 230, 160)])
        if night:
            col = shade(col, -0.5)
        _r(cv, x, fy - bh, x + bw, fy - 20, col, 4)
        for wy in range(int(fy - bh + 24), int(fy - 60), 46):
            for wx in range(int(x + 16), int(x + bw - 30), 40):
                lit = rnd.random() > 0.5
                _r(cv, wx, wy, wx + 22, wy + 26, (255, 232, 140) if (night and lit) else ((190, 226, 250) if not night else (60, 66, 100)), 2, False)
        x += bw + rnd.randint(-10, 14)
    cv.drawRect(skia.Rect.MakeLTRB(0, fy - 22, w, h), fill_paint((124, 128, 148) if not night else (60, 62, 88)))
    cv.drawRect(skia.Rect.MakeLTRB(0, fy - 22, w, fy + 18), fill_paint((206, 204, 214) if not night else (100, 100, 130)))
    for i in range(0, int(w), 140):
        _r(cv, i + 20, fy + (h - fy) * 0.5, i + 100, fy + (h - fy) * 0.5 + 10, (250, 244, 210), 3, False)
    for lx in (w * 0.18, w * 0.78):
        cv.drawLine(lx, fy - 6, lx, fy - 260, line_paint((70, 74, 96), 9))
        _o(cv, lx + 18, fy - 262, 20, 14, (255, 236, 160) if night else (240, 240, 250))


def _park(cv, w, h, night):
    fy = h * FLOOR_Y["park"]
    _vgrad(cv, w, h, (140, 206, 250) if not night else (28, 34, 84), (232, 246, 252) if not night else (90, 96, 150), 0, fy)
    cv.drawCircle(w * 0.82, h * 0.16, 46, fill_paint((255, 236, 150) if not night else (250, 246, 220)))
    for cx, cy, s in ((w * 0.2, h * 0.14, 1.0), (w * 0.5, h * 0.22, 0.8), (w * 0.66, h * 0.1, 0.7)):
        for dx, dy, r in ((-40, 6, 30), (0, -10, 42), (44, 6, 32)):
            cv.drawCircle(cx + dx * s, cy + dy * s, r * s, fill_paint((255, 255, 255, 230) if not night else (160, 170, 210)))
    for i, (x, hh, col) in enumerate(((w * 0.1, 140, (150, 210, 150)), (w * 0.5, 190, (130, 200, 150)), (w * 0.9, 150, (160, 214, 150)))):
        p = skia.Path()
        p.moveTo(x - 360, fy)
        p.quadTo(x, fy - hh * 2, x + 360, fy)
        cv.drawPath(p, fill_paint(shade(col, -0.35) if night else col))
    cv.drawRect(skia.Rect.MakeLTRB(0, fy - 10, w, h), fill_paint((134, 200, 120) if not night else (50, 90, 80)))
    p = skia.Path()
    p.moveTo(w * 0.3, h)
    p.quadTo(w * 0.5, fy + 10, w * 0.62, fy - 6)
    p.lineTo(w * 0.7, fy - 6)
    p.quadTo(w * 0.7, fy + 20, w * 0.9, h)
    p.close()
    cv.drawPath(p, fill_paint((240, 220, 180) if not night else (110, 100, 120)))
    for tx, th in ((w * 0.06, 300), (w * 0.93, 340), (w * 0.24, 220)):
        cv.drawRect(skia.Rect.MakeLTRB(tx - 12, fy - th * 0.5, tx + 12, fy + 10), fill_paint((156, 110, 80)))
        cv.drawCircle(tx, fy - th * 0.55, th * 0.3, fill_paint((84, 176, 108) if not night else (40, 96, 80)))
        cv.drawCircle(tx - th * 0.2, fy - th * 0.42, th * 0.2, fill_paint((98, 190, 118) if not night else (46, 108, 90)))
    _r(cv, w * 0.36, fy + 20, w * 0.52, fy + 34, (170, 118, 84), 4)


def _space(cv, w, h, night):
    _vgrad(cv, w, h, (22, 20, 58), (62, 44, 110))
    rnd = random.Random(5)
    for _ in range(70):
        cv.drawCircle(rnd.random() * w, rnd.random() * h, rnd.choice([1.5, 2, 2.5, 3.5]), fill_paint((255, 250, 220), rnd.randint(140, 255)))
    cv.drawCircle(w * 0.2, h * 0.26, 74, fill_paint((250, 164, 120)))
    cv.drawCircle(w * 0.18, h * 0.22, 74, fill_paint((250, 190, 150), 0))
    cv.drawOval(skia.Rect.MakeLTRB(w * 0.2 - 128, h * 0.26 - 22, w * 0.2 + 128, h * 0.26 + 22), line_paint((255, 226, 180), 8, 200))
    cv.drawCircle(w * 0.82, h * 0.62, 46, fill_paint((120, 190, 240)))
    cv.drawCircle(w * 0.78, h * 0.58, 14, fill_paint((150, 214, 250)))
    cv.drawRect(skia.Rect.MakeLTRB(0, h * 0.82, w, h), fill_paint((50, 38, 96)))


def _mind(cv, w, h, night):
    _vgrad(cv, w, h, (96, 78, 190), (236, 150, 190))
    rnd = random.Random(8)
    for i in range(18):
        r = rnd.choice([10, 16, 26, 40, 60])
        cv.drawCircle(rnd.random() * w, rnd.random() * h * 0.9, r, fill_paint((255, 255, 255), rnd.randint(30, 80)))
    cv.drawRect(skia.Rect.MakeLTRB(0, h * 0.8, w, h), fill_paint((78, 60, 150, 140)))


def _void(cv, w, h, night):
    fy = h * FLOOR_Y["void"]
    cv.drawRect(skia.Rect.MakeLTRB(0, 0, w, h), fill_paint((252, 252, 255)))
    sh = skia.GradientShader.MakeLinear([(0, fy - 30), (0, h)], [C((252, 252, 255)), C((226, 230, 242))])
    cv.drawRect(skia.Rect.MakeLTRB(0, fy - 30, w, h), skia.Paint(AntiAlias=True, Shader=sh))
    vx = w / 2
    for i in range(-14, 15):                                                        # perspective tiles (studio floor)
        cv.drawLine(vx + i * 40, fy, vx + i * 190, h, line_paint((205, 210, 226), 2, 160))
    for k in range(1, 7):
        y = fy + (h - fy) * (k / 6) ** 1.7
        cv.drawLine(0, y, w, y, line_paint((205, 210, 226), 2, 160))


KINDS = {"bedroom": _bedroom, "office": _office, "classroom": _classroom, "kitchen": _kitchen, "living": _living, "street": _street, "park": _park, "space": _space, "mind": _mind, "void": _void}

KEYWORDS = {
    "bedroom": "bed sleep sleeping asleep insomnia pillow dream dreams alarm wake woke night midnight rest tired exhausted nap morning",
    "office": "work job boss office meeting deadline email career coworker colleague desk company salary project laptop productive productivity",
    "classroom": "school class classroom teacher student exam test learn learning study homework lesson university college grades",
    "kitchen": "kitchen cook cooking eat eating food breakfast dinner lunch coffee meal snack fridge diet sugar hungry",
    "living": "home family sofa couch tv television living room relax watch binge netflix evening apartment parents",
    "street": "street city town crowd traffic stranger strangers people walk walking public shop store mall bus train commute",
    "park": "park nature outside outdoors walk walking fresh air trees sun hike garden exercise run running jog",
    "space": "space universe planet planets star stars galaxy cosmos moon sun earth orbit astronaut telescope",
    "mind": "brain mind thought thoughts thinking overthinking anxiety stress memory memories emotion emotions feel feeling psychology subconscious habit habits belief fear",
}


def pick_place(text, default=None):
    import re
    words = re.findall(r"[a-z]+", text.lower())
    best, bs = None, 0
    for k, kws in KEYWORDS.items():
        ks = set(kws.split())
        sc = sum(1 for w in words if w in ks)
        if sc > bs:
            best, bs = k, sc
    return best if bs >= 1 else default


@functools.lru_cache(maxsize=48)
def build(kind, w, h, night=False):
    s = skia.Surface(w, h)
    cv = s.getCanvas()
    if kind.startswith("plain:"):
        col = PLAIN.get(kind.split(":", 1)[1], PLAIN["cream"])
        cv.drawRect(skia.Rect.MakeLTRB(0, 0, w, h), fill_paint(col))
        # soft radial "spotlight" so a plain colour is not dead flat
        sh = skia.GradientShader.MakeRadial((w / 2, h * 0.5), max(w, h) * 0.75, [C(shade(col, 0.45), 160), C(shade(col, -0.06), 0)])
        cv.drawRect(skia.Rect.MakeLTRB(0, 0, w, h), skia.Paint(AntiAlias=True, Shader=sh))
    else:
        KINDS.get(kind, _void)(cv, w, h, night)
    return s.makeImageSnapshot()


def floor_frac(kind):
    return FLOOR_Y.get(kind.split(":")[0], 0.8)
