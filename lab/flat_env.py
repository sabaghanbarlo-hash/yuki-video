"""Flat 'explainer' backdrops: layered parallax scenery drawn once per scene, then panned/zoomed by the camera."""
import math, random
from PIL import Image
from .canvas import Cv, vgrad, shade, mix, hexc, radial_grad
from . import entities as E

W, H = 1280, 720
MX, MY = 240, 135                       # extra margin around the screen so the camera can move
LW, LH = W + 2 * MX, H + 2 * MY
SS = 2

PALETTES = {
    "cosmos": dict(top=(12, 10, 44), bot=(54, 22, 104), a1=(255, 196, 72), a2=(84, 214, 255), a3=(255, 104, 168), ink=(255, 255, 255)),
    "nebula": dict(top=(26, 8, 58), bot=(130, 40, 130), a1=(255, 150, 220), a2=(140, 120, 255), a3=(90, 230, 255), ink=(255, 255, 255)),
    "neon": dict(top=(8, 10, 34), bot=(38, 12, 80), a1=(0, 240, 200), a2=(255, 60, 170), a3=(255, 220, 60), ink=(255, 255, 255)),
    "ocean": dict(top=(10, 84, 150), bot=(2, 24, 66), a1=(90, 226, 236), a2=(120, 170, 255), a3=(255, 210, 120), ink=(255, 255, 255)),
    "deep": dict(top=(4, 22, 54), bot=(0, 4, 18), a1=(70, 210, 230), a2=(120, 140, 255), a3=(255, 120, 200), ink=(255, 255, 255)),
    "ember": dict(top=(30, 6, 22), bot=(190, 58, 26), a1=(255, 170, 60), a2=(255, 100, 60), a3=(255, 230, 140), ink=(255, 255, 255)),
    "ice": dict(top=(110, 190, 236), bot=(228, 246, 255), a1=(255, 255, 255), a2=(90, 200, 255), a3=(150, 255, 200), ink=(24, 44, 90)),
    "dusk": dict(top=(58, 30, 112), bot=(255, 150, 84), a1=(255, 226, 124), a2=(255, 120, 120), a3=(160, 120, 255), ink=(255, 255, 255)),
    "bio": dict(top=(58, 14, 76), bot=(200, 68, 124), a1=(255, 170, 200), a2=(190, 140, 255), a3=(120, 230, 200), ink=(255, 255, 255)),
    "day": dict(top=(86, 168, 250), bot=(216, 242, 255), a1=(255, 220, 90), a2=(255, 255, 255), a3=(120, 220, 160), ink=(20, 40, 90)),
    "forest": dict(top=(26, 90, 84), bot=(8, 40, 46), a1=(176, 244, 150), a2=(255, 232, 140), a3=(120, 220, 200), ink=(255, 255, 255)),
    "lab": dict(top=(30, 48, 98), bot=(12, 22, 52), a1=(110, 200, 255), a2=(255, 170, 100), a3=(140, 255, 200), ink=(255, 255, 255)),
    "storm": dict(top=(24, 30, 58), bot=(78, 86, 120), a1=(255, 240, 150), a2=(150, 190, 255), a3=(255, 255, 255), ink=(255, 255, 255)),
}
ENV_PALETTES = {"deep_space": ["cosmos", "neon", "nebula"], "nebula": ["nebula"], "solar": ["cosmos", "dusk"], "orbit": ["cosmos"], "ocean_deep": ["ocean", "deep"],
                "ocean_surface": ["ocean", "day"], "strata": ["dusk", "ember"], "ember": ["ember"], "arctic": ["ice"], "dusk_desert": ["dusk"], "storm": ["storm"],
                "micro": ["bio"], "neural": ["neon", "bio"], "lab": ["lab"], "night_city": ["neon", "cosmos"], "data": ["neon"], "tunnel": ["neon", "cosmos", "nebula"],
                "day_sky": ["day"], "forest": ["forest"]}


class Layer:
    def __init__(self, img, par, opaque=False):
        self.img, self.par, self.opaque = img, par, opaque


def _cv(opaque=False, pal=None):
    return Cv(LW, LH, SS)


def _bg(pal, top=None, bot=None):
    g = vgrad(LW * SS, LH * SS, top or pal["top"], bot or pal["bot"]).convert("RGBA")
    cv = Cv(LW, LH, SS, bg=g)
    return cv


def stars(cv, rng, n, ysplit=1.0, colors=((255, 255, 255), (255, 240, 200), (200, 220, 255)), big=0.04):
    for _ in range(n):
        x, y = rng.uniform(0, LW), rng.uniform(0, LH * ysplit)
        r = rng.uniform(0.8, 2.2) if rng.random() > big else rng.uniform(2.6, 4.2)
        c = rng.choice(colors)
        cv.circle(x, y, r, c, alpha=int(rng.uniform(120, 255)))
        if r > 2.5:
            cv.glow(x, y, r * 4, c, 0.35)


def nebula(cv, rng, colors, n=9, scale=1.0):
    for _ in range(n):
        x, y = rng.uniform(0, LW), rng.uniform(0, LH)
        r = rng.uniform(180, 420) * scale
        cv.glow(x, y, r, rng.choice(colors), rng.uniform(0.18, 0.4), 2.0)


def hills(cv, rng, base, amp, color, n=3, y_bottom=None, jag=0.0, step=14):
    ph = [rng.uniform(0, 6.28) for _ in range(n)]
    fr = [rng.uniform(0.004, 0.012) * (i + 1) for i in range(n)]
    am = [amp / (i + 1) for i in range(n)]
    pts = [(-10, y_bottom or LH + 10)]
    x = -10
    while x <= LW + 10:
        y = base + sum(am[i] * math.sin(x * fr[i] + ph[i]) for i in range(n)) + (rng.uniform(-jag, jag) if jag else 0)
        pts.append((x, y)); x += step
    pts.append((LW + 10, y_bottom or LH + 10))
    cv.poly(pts, color)


def peaks(cv, rng, base, hmin, hmax, color, snow=None, wmin=140, wmax=300):
    x = -80
    while x < LW + 80:
        w = rng.uniform(wmin, wmax); h = rng.uniform(hmin, hmax)
        cv.poly([(x, LH + 10), (x + w * 0.5, base - h), (x + w, LH + 10)], color)
        cv.poly([(x + w * 0.5, base - h), (x + w, LH + 10), (x + w * 0.62, LH + 10)], shade(color, -0.22))
        if snow:
            cv.poly([(x + w * 0.5, base - h), (x + w * 0.5 - w * 0.12, base - h + h * 0.22), (x + w * 0.5 - w * 0.03, base - h + h * 0.17), (x + w * 0.5 + w * 0.05, base - h + h * 0.24),
                     (x + w * 0.5 + w * 0.12, base - h + h * 0.2)], snow)
        x += w * rng.uniform(0.45, 0.8)


def skyline_layer(cv, rng, base, hmin, hmax, color, windows=True, wmin=40, wmax=90, alpha=255):
    x = -20
    while x < LW + 20:
        w = rng.uniform(wmin, wmax); h = rng.uniform(hmin, hmax)
        cv.rect(x, base - h, x + w, LH + 10, color)
        if rng.random() < 0.3:
            cv.rect(x + w * 0.45, base - h - rng.uniform(14, 40), x + w * 0.55, base - h, color)
        if windows:
            for wy in range(int(base - h + 12), int(LH), 20):
                for wx in range(int(x + 8), int(x + w - 10), 16):
                    if rng.random() < 0.35:
                        cv.rect(wx, wy, wx + 7, wy + 10, (255, 226, 130), alpha=int(rng.uniform(140, 255)))
        x += w + rng.uniform(0, 8)


def bokeh(cv, rng, colors, n=40, rmin=14, rmax=90):
    for _ in range(n):
        x, y, r = rng.uniform(0, LW), rng.uniform(0, LH), rng.uniform(rmin, rmax)
        c = rng.choice(colors)
        cv.circle(x, y, r, c, alpha=int(rng.uniform(25, 80)))
        cv.ring(x, y, r, 2, shade(c, 0.4), int(rng.uniform(40, 110)))


def rays(cv, rng, x0, y0, color, n=7, length=1200, spread=0.9, alpha=26):
    for i in range(n):
        a = math.pi / 2 + (i / (n - 1) - 0.5) * spread + rng.uniform(-0.05, 0.05)
        w = rng.uniform(0.04, 0.1)
        cv.poly([(x0, y0), (x0 + math.cos(a - w) * length, y0 + math.sin(a - w) * length), (x0 + math.cos(a + w) * length, y0 + math.sin(a + w) * length)], color, alpha=alpha)


# ------------------------------------------------------------------ the environments
def env_deep_space(pal, rng):
    far = _bg(pal); nebula(far, rng, [pal["a3"], pal["a2"], pal["bot"]], 7, 1.0); stars(far, rng, 380)
    mid = _cv(); stars(mid, rng, 40, big=0.2)
    for _ in range(rng.randint(2, 4)):
        s = rng.uniform(70, 160)
        E.planet(mid, rng.uniform(LW * 0.1, LW * 0.9), rng.uniform(LH * 0.15, LH * 0.85), s, 0, pal, rng.randrange(99))
    near = _cv()
    for _ in range(3):
        near.circle(rng.uniform(0, LW), rng.uniform(0, LH), rng.uniform(2, 5), (255, 255, 255), alpha=90)
    return [Layer(far.hi(), 0.1, True), Layer(mid.hi(), 0.45), Layer(near.hi(), 1.0)], dict(twinkle=60, shooting=True, dust=(pal["a2"], 14))


def env_nebula(pal, rng):
    far = _bg(pal); nebula(far, rng, [pal["a1"], pal["a2"], pal["a3"], pal["bot"]], 14, 1.2); stars(far, rng, 300)
    mid = _cv(); nebula(mid, rng, [pal["a1"], pal["a3"]], 5, 0.8); stars(mid, rng, 50, big=0.3)
    near = _cv(); nebula(near, rng, [pal["a2"]], 3, 0.7)
    return [Layer(far.hi(), 0.1, True), Layer(mid.hi(), 0.4), Layer(near.hi(), 0.9)], dict(twinkle=70, dust=(pal["a1"], 18))


def env_solar(pal, rng):
    far = _bg(pal, (6, 4, 26), (40, 14, 54)); stars(far, rng, 320)
    mid = _cv()
    side = rng.choice((-1, 1))
    cx = LW * (0.02 if side < 0 else 0.98)
    mid.glow(cx, LH * 0.5, 900, (255, 130, 40), 0.55, 2.4); mid.glow(cx, LH * 0.5, 520, (255, 190, 80), 0.6, 2.0)
    mid.circle(cx, LH * 0.5, 330, (255, 190, 64)); mid.circle(cx - side * -20, LH * 0.5 - 10, 300, (255, 214, 100))
    near = _cv()
    for _ in range(26):
        near.circle(rng.uniform(0, LW), rng.uniform(LH * 0.2, LH * 0.8), rng.uniform(2, 7), (200, 170, 140), alpha=rng.randint(80, 200))
    return [Layer(far.hi(), 0.08, True), Layer(mid.hi(), 0.3), Layer(near.hi(), 1.0)], dict(twinkle=40, dust=((255, 190, 90), 22))


def env_orbit(pal, rng):
    far = _bg(pal, (4, 6, 26), (20, 20, 70)); stars(far, rng, 360)
    mid = _cv()
    mid.glow(LW * rng.uniform(0.2, 0.8), LH * 0.25, 220, (255, 240, 200), 0.18)
    near = _cv()
    R = 1500
    cxp, cyp = LW / 2 + rng.uniform(-200, 200), LH + R - rng.uniform(210, 290)
    near.glow(cxp, cyp, R + 120, (90, 170, 255), 0.45, 5.0)
    near.circle(cxp, cyp, R, (40, 100, 190)); near.circle(cxp + 30, cyp + 20, R - 24, (52, 124, 214))
    for _ in range(14):
        a = rng.uniform(-2.1, -1.05); d = rng.uniform(0.4, 0.97) * R
        near.poly(E.blob(cxp + math.cos(a) * d, cyp + math.sin(a) * d, rng.uniform(40, 160), 10, 0.45, rng.randrange(999), ry=rng.uniform(14, 36)), (88, 176, 108), alpha=230)
    for _ in range(22):
        a = rng.uniform(-2.2, -0.95); d = rng.uniform(0.7, 0.99) * R
        near.ellipse(cxp + math.cos(a) * d, cyp + math.sin(a) * d, rng.uniform(40, 120), rng.uniform(6, 14), (255, 255, 255), alpha=170)
    near.ring(cxp, cyp, R + 4, 6, (150, 220, 255), 150)
    return [Layer(far.hi(), 0.06, True), Layer(mid.hi(), 0.3), Layer(near.hi(), 0.8)], dict(twinkle=50, shooting=True)


def env_ocean_deep(pal, rng):
    far = _bg(pal); rays(far, rng, rng.uniform(LW * 0.3, LW * 0.7), -60, (190, 245, 255), 8, 1500, 1.1, 22)
    mid = _cv()
    hills(mid, rng, LH * 0.84, 40, shade(pal["bot"], 0.1), 3)
    for _ in range(rng.randint(4, 7)):
        x = rng.uniform(0, LW); h = rng.uniform(90, 260)
        pts = [(x + math.sin(i * 0.5) * 16, LH - i * h / 12) for i in range(13)]
        mid.polyline(pts, 12, (36, 130, 120), alpha=210)
    near = _cv()
    hills(near, rng, LH * 0.92, 22, (6, 28, 52), 3, jag=3)
    for _ in range(4):
        x = rng.uniform(0, LW); near.poly(E.blob(x, LH * 0.93, rng.uniform(40, 90), 9, 0.35, rng.randrange(99), ry=rng.uniform(26, 52)), (10, 40, 64))
    return [Layer(far.hi(), 0.1, True), Layer(mid.hi(), 0.5), Layer(near.hi(), 1.0)], dict(bubbles=26, dust=((190, 235, 255), 24), light=True)


def env_ocean_surface(pal, rng):
    far = _bg(pal, (120, 200, 255), (210, 240, 255))
    far.glow(LW * rng.uniform(0.3, 0.7), LH * 0.25, 320, (255, 240, 180), 0.8, 2.0); far.circle(LW * 0.5, LH * 0.25, 60, (255, 244, 190))
    mid = _cv()
    for i in range(3):
        E.cloud(mid, rng.uniform(0, LW), rng.uniform(40, LH * 0.35), rng.uniform(200, 320), 0, pal, i)
    near = _cv()
    for k, (y, col) in enumerate([(LH * 0.55, (50, 150, 226)), (LH * 0.62, (36, 124, 208)), (LH * 0.72, (24, 92, 176)), (LH * 0.84, (14, 64, 140))]):
        pts = [(-10, LH + 10)]
        for x in range(-10, int(LW) + 20, 16):
            pts.append((x, y + math.sin(x * 0.02 + k * 2) * (10 + k * 4)))
        pts.append((LW + 10, LH + 10)); near.poly(pts, col)
    return [Layer(far.hi(), 0.05, True), Layer(mid.hi(), 0.25), Layer(near.hi(), 0.7)], dict(sparkle=(255, 255, 255, 30), drift_clouds=True)


def env_strata(pal, rng):
    far = _bg(pal, (130, 200, 255), (200, 236, 255))
    mid = _cv()
    layers = [(0.42, (96, 170, 100)), (0.47, (150, 104, 78)), (0.58, (124, 84, 70)), (0.7, (214, 120, 70)), (0.84, (232, 84, 56)), (0.95, (255, 170, 70))]
    for k, (y, col) in enumerate(layers):
        pts = [(-10, LH + 10)]
        for x in range(-10, int(LW) + 20, 20):
            pts.append((x, LH * y + math.sin(x * 0.011 + k * 1.7) * 14 + math.sin(x * 0.03 + k) * 5))
        pts.append((LW + 10, LH + 10)); mid.poly(pts, col)
    rng2 = random.Random(rng.randrange(999))
    for _ in range(60):
        y = rng2.uniform(LH * 0.5, LH * 0.98); x = rng2.uniform(0, LW)
        mid.ellipse(x, y, rng2.uniform(6, 22), rng2.uniform(4, 10), (255, 255, 255), alpha=rng2.randint(18, 50))
    near = _cv(); rays(near, rng, LW * 0.5, LH * 0.45, (255, 200, 120), 0, 0, 0, 0)
    return [Layer(far.hi(), 0.05, True), Layer(mid.hi(), 0.5), Layer(near.hi(), 1.0)], dict(dust=((255, 190, 120), 14), heat=True)


def env_ember(pal, rng):
    far = _bg(pal); far.glow(LW * 0.5, LH * 0.95, 900, (255, 120, 50), 0.6, 2.0); stars(far, rng, 80, 0.5)
    mid = _cv(); peaks(mid, rng, LH * 0.78, 120, 300, (58, 18, 40), wmin=200, wmax=420)
    near = _cv(); peaks(near, rng, LH * 0.9, 60, 160, (28, 8, 22), wmin=160, wmax=340)
    near.rect(0, LH * 0.93, LW, LH, (255, 110, 40)); near.rect(0, LH * 0.96, LW, LH, (255, 200, 80))
    near.glow(LW / 2, LH * 0.94, 700, (255, 140, 40), 0.6, 2.0)
    return [Layer(far.hi(), 0.06, True), Layer(mid.hi(), 0.4), Layer(near.hi(), 0.9)], dict(embers=60, ash=30)


def env_arctic(pal, rng):
    far = _bg(pal, (14, 30, 80), (80, 140, 210))
    for k in range(3):
        col = [(120, 255, 190), (130, 200, 255), (200, 140, 255)][k]
        pts = []
        for i in range(0, 41):
            x = i * LW / 40
            pts.append((x, LH * (0.2 + 0.08 * k) + math.sin(i * 0.4 + k) * 40))
        far.poly(pts + [(LW, LH * 0.62), (0, LH * 0.62)], col, alpha=40)
    stars(far, rng, 220, 0.6)
    mid = _cv(); peaks(mid, rng, LH * 0.72, 120, 280, (190, 220, 244), snow=(255, 255, 255), wmin=220, wmax=420)
    near = _cv(); hills(near, rng, LH * 0.86, 30, (240, 248, 255), 3); hills(near, rng, LH * 0.93, 14, (214, 234, 250), 3)
    return [Layer(far.hi(), 0.06, True), Layer(mid.hi(), 0.4), Layer(near.hi(), 0.9)], dict(snow=90, twinkle=40)


def env_dusk_desert(pal, rng):
    far = _bg(pal); far.glow(LW * rng.uniform(0.35, 0.65), LH * 0.66, 700, (255, 210, 120), 0.8, 2.0)
    far.circle(LW * 0.5, LH * 0.62, 110, (255, 238, 170)); far.circle(LW * 0.5, LH * 0.62, 90, (255, 248, 210)); stars(far, rng, 80, 0.4)
    mid = _cv(); hills(mid, rng, LH * 0.7, 30, (214, 110, 110), 3)
    mid2 = _cv(); hills(mid2, rng, LH * 0.78, 40, (186, 86, 100), 3)
    near = _cv(); hills(near, rng, LH * 0.88, 36, (120, 56, 90), 3)
    for _ in range(3):
        x = rng.uniform(0, LW); h = rng.uniform(80, 150)
        near.rect(x, LH * 0.9 - h, x + 18, LH * 0.9, (60, 26, 60), r=8)
        near.rect(x - 26, LH * 0.9 - h * 0.6, x - 12, LH * 0.9 - h * 0.35, (60, 26, 60), r=7); near.rect(x - 26, LH * 0.9 - h * 0.4, x, LH * 0.9 - h * 0.32, (60, 26, 60), r=6)
        near.rect(x + 30, LH * 0.9 - h * 0.75, x + 44, LH * 0.9 - h * 0.45, (60, 26, 60), r=7); near.rect(x + 18, LH * 0.9 - h * 0.5, x + 44, LH * 0.9 - h * 0.42, (60, 26, 60), r=6)
    return [Layer(far.hi(), 0.05, True), Layer(mid.hi(), 0.3), Layer(mid2.hi(), 0.55), Layer(near.hi(), 0.95)], dict(dust=((255, 220, 160), 20), heat=True)


def env_storm(pal, rng):
    far = _bg(pal)
    mid = _cv()
    for i in range(7):
        E.cloud(mid, rng.uniform(0, LW), rng.uniform(0, LH * 0.5), rng.uniform(420, 720), 0, pal, i, dark=True)
    near = _cv(); hills(near, rng, LH * 0.9, 20, (16, 20, 36), 3)
    return [Layer(far.hi(), 0.05, True), Layer(mid.hi(), 0.35), Layer(near.hi(), 0.9)], dict(rain=140, lightning=True, drift_clouds=True)


def env_micro(pal, rng):
    far = _bg(pal); bokeh(far, rng, [pal["a1"], pal["a2"], pal["a3"], pal["top"]], 24, 40, 150)
    mid = _cv(); bokeh(mid, rng, [pal["a1"], pal["a2"], pal["a3"]], 18, 20, 80)
    for _ in range(4):
        E.cell(mid, rng.uniform(0, LW), rng.uniform(0, LH), rng.uniform(100, 200), 0, pal, rng.randrange(99))
    near = _cv(); bokeh(near, rng, [(255, 255, 255), pal["a1"]], 14, 14, 50)
    return [Layer(far.hi(), 0.08, True), Layer(mid.hi(), 0.4), Layer(near.hi(), 0.95)], dict(dust=((255, 200, 230), 36), float=True)


def env_neural(pal, rng):
    far = _bg(pal); nebula(far, rng, [pal["a2"], pal["a1"]], 6, 0.9)
    mid = _cv()
    nodes = [(rng.uniform(0, LW), rng.uniform(0, LH)) for _ in range(46)]
    for i, (x, y) in enumerate(nodes):
        near = sorted(nodes, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)[1:4]
        for (x2, y2) in near:
            mid.line((x, y), (x2, y2), 2, pal["a1"], alpha=90, cap=False)
    for (x, y) in nodes:
        mid.glow(x, y, 26, pal["a1"], 0.7); mid.circle(x, y, rng.uniform(3, 7), (255, 255, 255), alpha=230)
    near_l = _cv(); bokeh(near_l, rng, [pal["a2"], pal["a1"]], 10, 20, 60)
    return [Layer(far.hi(), 0.08, True), Layer(mid.hi(), 0.5), Layer(near_l.hi(), 1.0)], dict(twinkle=30, dust=(pal["a1"], 20), nodes=nodes)


def env_lab(pal, rng):
    far = _bg(pal); far.glow(LW * 0.5, -100, 900, pal["a1"], 0.35, 2.0)
    for x in range(0, int(LW), 60):
        far.line((x, 0), (x, LH), 1, (255, 255, 255), alpha=14, cap=False)
    for y in range(0, int(LH), 60):
        far.line((0, y), (LW, y), 1, (255, 255, 255), alpha=14, cap=False)
    mid = _cv()
    for _ in range(18):
        x, y, r = rng.uniform(0, LW), rng.uniform(0, LH), rng.uniform(20, 70)
        c = rng.choice([pal["a1"], pal["a2"], pal["a3"]])
        k = rng.randrange(4)
        if k == 0:
            mid.ring(x, y, r, 3, c, 70)
        elif k == 1:
            mid.poly([(x + math.cos(a) * r, y + math.sin(a) * r) for a in [math.tau * i / 6 for i in range(6)]], c, alpha=34)
        elif k == 2:
            mid.rect(x - r * 0.15, y - r * 0.5, x + r * 0.15, y + r * 0.5, c, r=4, alpha=60); mid.rect(x - r * 0.5, y - r * 0.15, x + r * 0.5, y + r * 0.15, c, r=4, alpha=60)
        else:
            mid.circle(x, y, r * 0.5, c, alpha=40)
    near = _cv(); bokeh(near, rng, [pal["a1"]], 8, 20, 60)
    return [Layer(far.hi(), 0.08, True), Layer(mid.hi(), 0.45), Layer(near.hi(), 1.0)], dict(dust=(pal["a1"], 22), float=True)


def env_night_city(pal, rng):
    far = _bg(pal, (10, 12, 40), (92, 40, 110)); stars(far, rng, 160, 0.6)
    far.glow(LW * rng.uniform(0.2, 0.8), LH * 0.2, 200, (255, 245, 210), 0.6); far.circle(far.w * 0.5, LH * 0.2, 0.01, (0, 0, 0), alpha=0)
    m1 = _cv(); skyline_layer(m1, rng, LH * 0.78, 100, 300, (30, 30, 76), wmin=50, wmax=110)
    m2 = _cv(); skyline_layer(m2, rng, LH * 0.88, 80, 260, (20, 20, 56), wmin=60, wmax=130)
    near = _cv(); skyline_layer(near, rng, LH * 0.97, 40, 160, (10, 10, 30), windows=True, wmin=80, wmax=170)
    return [Layer(far.hi(), 0.05, True), Layer(m1.hi(), 0.3), Layer(m2.hi(), 0.6), Layer(near.hi(), 1.0)], dict(twinkle=40, car_lights=True)


def env_data(pal, rng):
    far = _bg(pal, (4, 6, 20), (14, 10, 44))
    horizon = LH * 0.58
    for i in range(1, 22):
        y = horizon + (i / 21) ** 2 * (LH - horizon)
        far.line((0, y), (LW, y), 1, pal["a1"], alpha=int(30 + 60 * i / 21), cap=False)
    for i in range(-24, 25):
        far.line((LW / 2 + i * 14, horizon), (LW / 2 + i * 120, LH), 1, pal["a1"], alpha=60, cap=False)
    far.glow(LW / 2, horizon, 600, pal["a2"], 0.35, 2.0)
    mid = _cv()
    for _ in range(40):
        x = rng.uniform(0, LW); y = rng.uniform(0, LH * 0.7)
        mid.rect(x, y, x + rng.uniform(6, 26), y + 6, rng.choice([pal["a1"], pal["a2"], pal["a3"]]), r=3, alpha=rng.randint(60, 180))
    near = _cv(); bokeh(near, rng, [pal["a1"], pal["a2"]], 8, 10, 30)
    return [Layer(far.hi(), 0.08, True), Layer(mid.hi(), 0.5), Layer(near.hi(), 1.0)], dict(bits=70)


def env_tunnel(pal, rng):
    far = _bg(pal, (6, 4, 26), (30, 10, 64))
    cx, cy = LW / 2, LH / 2
    for i in range(18, 0, -1):
        r = i ** 1.6 * 38
        c = mix(pal["a2"], pal["a1"], i / 18)
        far.ring(cx, cy, r, 3 + i * 0.3, c, int(40 + 4 * (18 - i)))
    for i in range(22):
        a = math.tau * i / 22
        far.line((cx + math.cos(a) * 40, cy + math.sin(a) * 40), (cx + math.cos(a) * 1500, cy + math.sin(a) * 1500), 2, pal["a3"], alpha=26, cap=False)
    far.glow(cx, cy, 240, (255, 255, 255), 0.5, 2.0)
    mid = _cv(); bokeh(mid, rng, [pal["a1"], pal["a2"], pal["a3"]], 12, 10, 40)
    return [Layer(far.hi(), 0.1, True), Layer(mid.hi(), 0.7)], dict(streaks=60, dust=(pal["a1"], 12))


def env_day_sky(pal, rng):
    far = _bg(pal); far.glow(LW * rng.uniform(0.2, 0.8), LH * 0.18, 380, (255, 244, 180), 0.8, 2.0)
    mid = _cv()
    for i in range(5):
        E.cloud(mid, rng.uniform(0, LW), rng.uniform(40, LH * 0.5), rng.uniform(180, 360), 0, pal, i)
    m2 = _cv(); hills(m2, rng, LH * 0.82, 40, (118, 200, 150), 3)
    near = _cv(); hills(near, rng, LH * 0.92, 24, (74, 164, 112), 3)
    return [Layer(far.hi(), 0.04, True), Layer(mid.hi(), 0.25), Layer(m2.hi(), 0.55), Layer(near.hi(), 0.95)], dict(drift_clouds=True, float=True)


def env_forest(pal, rng):
    far = _bg(pal, (60, 150, 130), (16, 70, 66)); rays(far, rng, rng.uniform(LW * 0.3, LW * 0.7), -60, (255, 250, 190), 7, 1500, 0.9, 20)
    mids = []
    for k, (par, col, hmin, hmax, base) in enumerate([(0.3, (34, 112, 96), 220, 380, 0.88), (0.6, (22, 84, 78), 260, 460, 0.95)]):
        c = _cv()
        x = -40
        while x < LW + 40:
            h = rng.uniform(hmin, hmax); w = rng.uniform(90, 170)
            c.rect(x + w * 0.46, LH * base - h * 0.5, x + w * 0.54, LH * base, shade(col, -0.3))
            for j in range(4):
                yy = LH * base - h * 0.35 - j * h * 0.18
                ww = w * (0.55 - j * 0.1)
                c.poly([(x + w / 2 - ww, yy + h * 0.16), (x + w / 2, yy - h * 0.14), (x + w / 2 + ww, yy + h * 0.16)], col)
            x += w * rng.uniform(0.55, 0.9)
        mids.append(Layer(c.hi(), par))
    near = _cv(); hills(near, rng, LH * 0.97, 14, (8, 40, 44), 3)
    return [Layer(far.hi(), 0.05, True)] + mids + [Layer(near.hi(), 1.0)], dict(fireflies=40, float=True)


ENVS = {"deep_space": env_deep_space, "nebula": env_nebula, "solar": env_solar, "orbit": env_orbit, "ocean_deep": env_ocean_deep, "ocean_surface": env_ocean_surface,
        "strata": env_strata, "ember": env_ember, "arctic": env_arctic, "dusk_desert": env_dusk_desert, "storm": env_storm, "micro": env_micro, "neural": env_neural,
        "lab": env_lab, "night_city": env_night_city, "data": env_data, "tunnel": env_tunnel, "day_sky": env_day_sky, "forest": env_forest}


def build(env, pal_name, seed):
    pal = PALETTES[pal_name]
    rng = random.Random(seed * 131 + 7)
    layers, ambient = ENVS[env](pal, rng)
    return layers, ambient, pal


def view(layer, cam, out_w=W, out_h=H):
    """Camera-transformed view of a layer: cam = (x, y, zoom). Returns an image of size out_w x out_h."""
    cx, cy, z = cam
    p = layer.par
    zp = 1 + (z - 1) * p
    half_w, half_h = W / 2 / zp, H / 2 / zp
    ox = LW / 2 + cx * p; oy = LH / 2 + cy * p
    ox = max(half_w, min(LW - half_w, ox)); oy = max(half_h, min(LH - half_h, oy))
    box = ((ox - half_w) * SS, (oy - half_h) * SS, (ox + half_w) * SS, (oy + half_h) * SS)
    return layer.img.resize((out_w, out_h), Image.BILINEAR, box=box, reducing_gap=None)
