"""Cartoon scenery for the 'simple characters' style: 13 layered parallax backdrops drawn in code, plus the animated
ambient particles that go with them.

build(env, pal_name, seed) -> (layers, ambient, pal, ground_y)
    layers    list[flat_env.Layer] on the oversized LW x LH canvas (use flat_env.view(layer, cam) exactly as for flat envs)
    ambient   dict understood by ambient_layer() (keys below)
    pal       palette dict (flat_env.PALETTES entry) actually used
    ground_y  screen y (720-space) where characters' feet should stand

ambient keys (all optional):
    dust=(color, n)      slow floating motes             fireflies=n   glowing wandering dots
    bubbles=n            rising bubbles                  snow=n        falling flakes
    rain=n               slanted rain streaks            twinkle=n     twinkling stars
    embers=n             rising sparks                   leaves=n      drifting leaves
    birds=n              small birds crossing the sky    beams=(color, alpha)  sweeping stage spotlights
    sparkle=(r,g,b,a)    glints                          sand=n        wind-blown specks
    clouds=n             a few slow cartoon clouds (drawn in front of the sky only if the env has no cloud layer)
"""
import math, random, functools
from PIL import Image
from .canvas import Cv, vgrad, shade, mix, hexc
from . import entities as E
from .flat_env import (Layer, PALETTES, LW, LH, MX, MY, SS, stars, hills, peaks, skyline_layer, rays, nebula, bokeh, _bg, _cv)

W, H = 1280, 720
GY = 700                                  # ground top in layer space  (screen y = GY - MY = 565)
FEET = GY - MY + 46                       # default foot line on screen


# ------------------------------------------------------------------ small props (layer coordinates, base = y of the ground line)
def ground(cv, y, col, line=None, deep=None):
    cv.rect(-10, y, LW + 10, LH + 10, col)
    cv.rect(-10, y, LW + 10, y + 9, line or shade(col, 0.18))
    cv.rect(-10, y + 70, LW + 10, LH + 10, deep or shade(col, -0.1))


def cloud_toon(cv, x, y, s, col=(255, 255, 255), alpha=255):
    r = s * 0.5
    for dx, dy, k in ((-0.55, 0.1, 0.62), (-0.15, -0.12, 0.85), (0.35, 0.0, 0.72), (0.7, 0.18, 0.5)):
        cv.circle(x + dx * r, y + dy * r, r * k * 0.7, col, alpha)
    cv.rect(x - r * 0.95, y + r * 0.02, x + r * 1.05, y + r * 0.42, col, r=r * 0.2, alpha=alpha)


def sun_toon(cv, x, y, r, col=(255, 224, 110)):
    cv.glow(x, y, r * 3.2, col, 0.55, 2.0)
    cv.circle(x, y, r * 1.18, shade(col, 0.2), alpha=110)
    cv.circle(x, y, r, col)


def building(cv, x, base, w, h, col, rng, win=(255, 226, 130), lit=0.5, roof=None, cols=None):
    cv.rect(x, base - h, x + w, base + 40, col)
    cv.rect(x + w * 0.82, base - h, x + w, base + 40, shade(col, -0.12))          # shaded side
    cv.rect(x - 3, base - h - 6, x + w + 3, base - h + 6, roof or shade(col, -0.2))
    nx = max(1, int((w - 16) // 26))
    gap = (w - 16) / nx
    for wy in range(int(base - h + 22), int(base - 30), 34):
        for i in range(nx):
            wx = x + 8 + i * gap + gap * 0.18
            on = rng.random() < lit
            cv.rect(wx, wy, wx + gap * 0.62, wy + 20, win if on else shade(col, -0.28), r=2, alpha=255 if on else 200)
    if rng.random() < 0.4:
        cv.rect(x + w * 0.4, base - h - 24, x + w * 0.46, base - h - 4, shade(col, -0.25))
        cv.circle(x + w * 0.43, base - h - 26, 4, (255, 90, 90))


def house(cv, x, base, w, h, wall, roof, rng, door=(150, 100, 70), win=(255, 232, 150), snow=False):
    cv.rect(x, base - h, x + w, base, wall)
    rh = h * 0.55
    cv.poly([(x - w * 0.08, base - h + 2), (x + w * 0.5, base - h - rh), (x + w * 1.08, base - h + 2)], roof)
    cv.poly([(x + w * 0.5, base - h - rh), (x + w * 1.08, base - h + 2), (x + w * 0.72, base - h + 2)], shade(roof, -0.15))
    if snow:
        cv.poly([(x - w * 0.08, base - h + 2), (x + w * 0.5, base - h - rh), (x + w * 1.08, base - h + 2),
                 (x + w * 0.96, base - h + 10), (x + w * 0.8, base - h + 2), (x + w * 0.62, base - h + 12), (x + w * 0.4, base - h + 3),
                 (x + w * 0.2, base - h + 12), (x - w * 0.04, base - h + 8)], (245, 250, 255))
    cv.rect(x + w * 0.4, base - h * 0.55, x + w * 0.62, base, door, r=3)
    cv.rect(x + w * 0.12, base - h * 0.7, x + w * 0.32, base - h * 0.4, win, r=3)
    cv.rect(x + w * 0.7, base - h * 0.7, x + w * 0.88, base - h * 0.4, win, r=3)
    cv.glow(x + w * 0.22, base - h * 0.55, 40, win, 0.35)


def lamp(cv, x, base, h, col=(70, 76, 96), glow=(255, 226, 150)):
    cv.rect(x - 4, base - h, x + 4, base, col)
    cv.rect(x - 4, base - h, x + 30, base - h + 7, col, r=3)
    cv.glow(x + 24, base - h + 14, 70, glow, 0.5)
    cv.ellipse(x + 24, base - h + 11, 12, 6, glow)


def car(cv, x, base, s, col):
    w, h = 150 * s, 40 * s
    cv.rect(x, base - h - 8 * s, x + w, base - 8 * s, col, r=12 * s)
    cv.poly([(x + w * 0.22, base - h - 8 * s), (x + w * 0.34, base - h - 36 * s), (x + w * 0.7, base - h - 36 * s), (x + w * 0.82, base - h - 8 * s)], col)
    cv.poly([(x + w * 0.28, base - h - 11 * s), (x + w * 0.37, base - h - 31 * s), (x + w * 0.5, base - h - 31 * s), (x + w * 0.5, base - h - 11 * s)], (190, 230, 255))
    cv.poly([(x + w * 0.53, base - h - 11 * s), (x + w * 0.53, base - h - 31 * s), (x + w * 0.67, base - h - 31 * s), (x + w * 0.76, base - h - 11 * s)], (190, 230, 255))
    cv.rect(x, base - h * 0.5 - 8 * s, x + w, base - 8 * s, shade(col, -0.18), r=8 * s)
    for wx in (x + w * 0.24, x + w * 0.76):
        cv.circle(wx, base - 6 * s, 15 * s, (40, 44, 56)); cv.circle(wx, base - 6 * s, 7 * s, (170, 176, 190))
    cv.ellipse(x + w - 6 * s, base - h * 0.75, 6 * s, 5 * s, (255, 240, 170))


def tree_round(cv, x, base, h, trunk, leaf):
    cv.rect(x - h * 0.05, base - h * 0.5, x + h * 0.05, base, trunk)
    for dx, dy, k in ((-0.2, 0.55, 0.28), (0.2, 0.55, 0.28), (0.0, 0.8, 0.34), (-0.1, 0.4, 0.26), (0.12, 0.38, 0.24)):
        cv.circle(x + dx * h, base - dy * h, k * h, leaf)
    cv.circle(x - h * 0.08, base - h * 0.86, h * 0.14, shade(leaf, 0.2), alpha=170)


def pine(cv, x, base, h, col, snow=False):
    cv.rect(x - h * 0.04, base - h * 0.14, x + h * 0.04, base, (96, 66, 50))
    for i in range(4):
        w = h * (0.34 - i * 0.065)
        y1 = base - h * (0.1 + i * 0.22)
        cv.poly([(x - w, y1), (x, y1 - h * 0.34), (x + w, y1)], col)
        cv.poly([(x, y1 - h * 0.34), (x + w, y1), (x + w * 0.35, y1)], shade(col, -0.16))
        if snow:
            cv.poly([(x, y1 - h * 0.34), (x - w * 0.42, y1 - h * 0.17), (x - w * 0.18, y1 - h * 0.15), (x, y1 - h * 0.2), (x + w * 0.2, y1 - h * 0.15), (x + w * 0.42, y1 - h * 0.17)], (246, 250, 255))


def palm(cv, x, base, h, lean, trunk=(176, 128, 84), leaf=(60, 170, 100)):
    pts = [(x + lean * (i / 10) ** 2 * h, base - h * i / 10) for i in range(11)]
    cv.polyline(pts, h * 0.07, trunk)
    for i in range(1, 10, 2):
        a, b = pts[i]; cv.line((a - h * 0.035, b), (a + h * 0.035, b), 3, shade(trunk, -0.2))
    tx, ty = pts[-1]
    for ang in (-160, -125, -90, -55, -20, 15, 195):
        a = math.radians(ang)
        ex, ey = tx + math.cos(a) * h * 0.46, ty + math.sin(a) * h * 0.3 + h * 0.12
        mx, my = tx + math.cos(a) * h * 0.26, ty + math.sin(a) * h * 0.26 - h * 0.05
        nx, ny = -math.sin(a) * h * 0.06, math.cos(a) * h * 0.06
        cv.poly([(tx, ty), (mx + nx, my + ny), (ex, ey), (mx - nx, my - ny)], leaf)
    cv.circle(tx - 6, ty + 6, h * 0.035, (120, 84, 56)); cv.circle(tx + 8, ty + 8, h * 0.035, (120, 84, 56))


def cactus(cv, x, base, h, col=(86, 170, 110)):
    w = h * 0.16
    cv.rect(x - w, base - h, x + w, base, col, r=w)
    cv.rect(x - w, base - h, x - w * 0.25, base, shade(col, 0.1), r=w * 0.4, alpha=150)
    cv.polyline([(x - w * 0.6, base - h * 0.42), (x - w * 2.2, base - h * 0.42), (x - w * 2.2, base - h * 0.68)], w * 1.0, col)
    cv.polyline([(x + w * 0.6, base - h * 0.55), (x + w * 2.1, base - h * 0.55), (x + w * 2.1, base - h * 0.8)], w * 1.0, col)
    cv.circle(x, base - h, w * 0.1, (255, 130, 160)); cv.circle(x + w * 2.1, base - h * 0.8, w * 0.35, (255, 130, 160))


def mesa(cv, x, base, w, h, col):
    top = w * 0.62
    cv.poly([(x, base), (x + (w - top) / 2, base - h), (x + (w + top) / 2, base - h), (x + w, base)], col)
    cv.poly([(x + w * 0.55, base - h), (x + (w + top) / 2, base - h), (x + w, base), (x + w * 0.7, base)], shade(col, -0.18))
    for k in (0.3, 0.55, 0.78):
        cv.rect(x + w * 0.05 + (1 - k) * 0, base - h * k - 4, x + w * 0.95, base - h * k + 2, shade(col, 0.12), alpha=120)


def crystal(cv, x, base, h, col, up=True, glow=True):
    w = h * 0.26
    d = -1 if up else 1
    if glow:
        cv.glow(x, base + d * h * 0.45, h * 1.1, col, 0.38, 2.0)
    pts = [(x - w, base), (x - w * 0.7, base + d * h * 0.7), (x, base + d * h), (x + w * 0.7, base + d * h * 0.72), (x + w, base)]
    cv.poly(pts, col)
    cv.poly([(x, base + d * h), (x + w * 0.7, base + d * h * 0.72), (x + w, base), (x + w * 0.15, base)], shade(col, -0.2))
    cv.poly([(x - w * 0.45, base + d * h * 0.2), (x - w * 0.55, base + d * h * 0.62), (x - w * 0.2, base + d * h * 0.78), (x - w * 0.12, base + d * h * 0.24)], shade(col, 0.4), alpha=170)


def stalactite(cv, x, top, h, w, col):
    cv.poly([(x - w, top - 20), (x + w, top - 20), (x + w * 0.25, top + h * 0.6), (x, top + h), (x - w * 0.2, top + h * 0.55)], col)
    cv.poly([(x, top - 20), (x + w, top - 20), (x + w * 0.25, top + h * 0.6), (x, top + h)], shade(col, -0.14))


def coral(cv, x, base, h, col, rng):
    def branch(px, py, ang, ln, wd, depth):
        ex, ey = px + math.sin(ang) * ln, py - math.cos(ang) * ln
        cv.line((px, py), (ex, ey), wd, col)
        if depth > 0:
            branch(ex, ey, ang - rng.uniform(0.3, 0.7), ln * 0.72, wd * 0.8, depth - 1)
            branch(ex, ey, ang + rng.uniform(0.3, 0.7), ln * 0.72, wd * 0.8, depth - 1)
        else:
            cv.circle(ex, ey, wd * 0.9, shade(col, 0.25))
    branch(x, base, 0, h * 0.42, h * 0.1, 2)


def fan_coral(cv, x, base, h, col):
    for i in range(7):
        a = -0.9 + i * 0.3
        cv.poly([(x, base), (x + math.sin(a - 0.2) * h, base - math.cos(a - 0.2) * h), (x + math.sin(a + 0.2) * h, base - math.cos(a + 0.2) * h)], shade(col, 0.05 * (i % 2)))


def kelp(cv, x, base, h, col, rng):
    pts = [(x + math.sin(i * 0.7 + x) * 14, base - i * h / 14) for i in range(15)]
    cv.polyline(pts, 14, col)
    for i in range(2, 14, 3):
        px, py = pts[i]; cv.ellipse(px + (18 if i % 2 else -18), py, 18, 7, shade(col, 0.1))


def mushroom(cv, x, base, s, cap, stem=(250, 240, 220)):
    cv.rect(x - s * 0.13, base - s * 0.5, x + s * 0.13, base, stem, r=s * 0.08)
    cv.poly([(x - s * 0.5, base - s * 0.46), (x - s * 0.36, base - s * 0.8), (x, base - s * 0.98), (x + s * 0.36, base - s * 0.8), (x + s * 0.5, base - s * 0.46)], cap)
    cv.ellipse(x, base - s * 0.46, s * 0.5, s * 0.08, shade(cap, -0.2))
    for dx, dy, r in ((-0.2, 0.66, 0.07), (0.08, 0.82, 0.06), (0.25, 0.62, 0.065)):
        cv.circle(x + dx * s, base - dy * s, r * s, (255, 255, 255))


def flask(cv, x, base, s, liquid, kind=0):
    gl = (220, 240, 255)
    if kind == 0:
        cv.poly([(x - s * 0.08, base - s), (x + s * 0.08, base - s), (x + s * 0.08, base - s * 0.6), (x + s * 0.38, base), (x - s * 0.38, base), (x - s * 0.08, base - s * 0.6)], gl, alpha=120)
        cv.poly([(x - s * 0.2, base - s * 0.32), (x + s * 0.2, base - s * 0.32), (x + s * 0.38, base), (x - s * 0.38, base)], liquid)
    else:
        cv.rect(x - s * 0.22, base - s * 0.8, x + s * 0.22, base, gl, r=s * 0.1, alpha=120)
        cv.rect(x - s * 0.22, base - s * 0.45, x + s * 0.22, base, liquid, r=s * 0.1)
    cv.rect(x - s * 0.12, base - s - 6, x + s * 0.12, base - s + 2, (150, 110, 80))


def bookshelf(cv, x, y, w, h, wood, rng):
    cv.rect(x, y, x + w, y + h, wood, r=4)
    rows = 3
    rh = h / rows
    for r in range(rows):
        cv.rect(x + 6, y + r * rh + 6, x + w - 6, y + (r + 1) * rh - 3, shade(wood, -0.35))
        bx = x + 10
        while bx < x + w - 18:
            bw = rng.uniform(10, 20); bh = rng.uniform(rh * 0.5, rh - 14)
            cv.rect(bx, y + (r + 1) * rh - 3 - bh, bx + bw, y + (r + 1) * rh - 3, rng.choice([(232, 98, 98), (98, 160, 232), (240, 196, 80), (120, 200, 150), (180, 130, 230)]), r=2)
            bx += bw + 2


def plant_pot(cv, x, base, s):
    cv.poly([(x - s * 0.3, base - s * 0.4), (x + s * 0.3, base - s * 0.4), (x + s * 0.22, base), (x - s * 0.22, base)], (214, 120, 84))
    for a in (-0.7, -0.35, 0, 0.35, 0.7):
        cv.ellipse(x + math.sin(a) * s * 0.3, base - s * 0.4 - s * 0.35 * math.cos(a), s * 0.1, s * 0.3, (80, 180, 110))


# ------------------------------------------------------------------ environments: each returns (layers, ambient, ground_y)
def _env_street(pal, rng):
    far = _bg(pal, (130, 196, 250), (252, 232, 214)); sun_toon(far, LW * rng.uniform(0.2, 0.8), 250, 54)
    far.glow(LW / 2, LH * 0.7, 500, (255, 210, 170), 0.3)
    m0 = _cv(); skyline_layer(m0, rng, GY - 20, 160, 360, (176, 200, 228), windows=False, wmin=70, wmax=130)
    m1 = _cv(); x = -30
    cols = [(244, 170, 128), (130, 184, 232), (240, 214, 130), (160, 210, 170), (214, 150, 200), (232, 120, 120)]
    while x < LW:
        w = rng.uniform(110, 190); building(m1, x, GY - 8, w, rng.uniform(190, 330), rng.choice(cols), rng, lit=0.35); x += w + rng.uniform(4, 22)
    m2 = _cv()
    for i in range(4):
        lamp(m2, 160 + i * 440 + rng.uniform(-40, 40), GY + 6, 190)
    for i in range(5):
        tree_round(m2, rng.uniform(60, LW - 60), GY + 6, rng.uniform(110, 150), (126, 90, 64), (88, 176, 108))
    near = _cv()
    near.rect(-10, GY, LW + 10, LH + 10, (96, 102, 120))
    near.rect(-10, GY, LW + 10, GY + 64, (206, 204, 210)); near.rect(-10, GY + 60, LW + 10, GY + 70, (150, 150, 162))
    for k in range(-1, 24):
        near.rect(k * 80, GY + 20, k * 80 + 2, GY + 62, (186, 184, 192), alpha=140)
    for x in range(-40, LW, 150):
        near.rect(x, GY + 186, x + 80, GY + 196, (240, 232, 190))
    car(near, rng.uniform(100, 500), GY + 160, 1.15, rng.choice([(230, 92, 92), (92, 150, 230), (240, 190, 70)]))
    car(near, rng.uniform(900, 1500), GY + 160, 1.15, rng.choice([(110, 200, 150), (180, 120, 230), (250, 250, 250)]))
    return [Layer(far.hi(), 0.05, True), Layer(m0.hi(), 0.2), Layer(m1.hi(), 0.45), Layer(m2.hi(), 0.75), Layer(near.hi(), 1.0)], dict(clouds=3, birds=3, dust=((255, 255, 255), 8)), FEET - 6


def _env_room(pal, rng):
    wall = rng.choice([(255, 226, 200), (206, 232, 236), (234, 214, 244), (255, 238, 190)])
    far = _bg(pal, shade(wall, 0.12), shade(wall, -0.06))
    for x in range(0, LW, 90):
        far.rect(x, 0, x + 40, LH, shade(wall, -0.05), alpha=110)
    m1 = _cv()
    wx, wy, ww, wh = LW * rng.uniform(0.32, 0.55), 220, 360, 330
    m1.rect(wx - 14, wy - 14, wx + ww + 14, wy + wh + 14, (250, 246, 236), r=10)
    m1.rect(wx, wy, wx + ww, wy + wh, (140, 204, 250), r=4)
    m1.rect(wx, wy + wh * 0.5, wx + ww, wy + wh, (190, 230, 255), alpha=120)
    cloud_toon(m1, wx + ww * 0.3, wy + wh * 0.35, 120); cloud_toon(m1, wx + ww * 0.7, wy + wh * 0.22, 80)
    m1.rect(wx + ww / 2 - 4, wy, wx + ww / 2 + 4, wy + wh, (250, 246, 236)); m1.rect(wx, wy + wh / 2 - 4, wx + ww, wy + wh / 2 + 4, (250, 246, 236))
    for sd in (-1, 1):
        cx0 = wx - 20 if sd < 0 else wx + ww + 20
        m1.poly([(cx0, wy - 30), (cx0 + sd * 90, wy - 30), (cx0 + sd * 80, wy + wh + 40), (cx0, wy + wh + 40)], (232, 110, 120))
        for k in range(1, 4):
            m1.line((cx0 + sd * 22 * k, wy - 30), (cx0 + sd * 20 * k, wy + wh + 40), 4, (200, 80, 96), alpha=140)
    m1.rect(wx - 30, wy - 44, wx + ww + 30, wy - 28, (150, 100, 70), r=6)
    for i, (fx, fy) in enumerate(((120, 250), (LW - 240, 240), (LW - 400, 360))):
        c = rng.choice([(255, 190, 110), (120, 190, 240), (240, 130, 170)])
        m1.rect(fx, fy, fx + 120, fy + 90, (150, 100, 70), r=4); m1.rect(fx + 8, fy + 8, fx + 112, fy + 82, shade(c, 0.4))
        m1.poly([(fx + 8, fy + 82), (fx + 50, fy + 40), (fx + 76, fy + 66), (fx + 92, fy + 50), (fx + 112, fy + 82)], c)
        m1.circle(fx + 88, fy + 28, 10, (255, 236, 150))
    m2 = _cv()
    bookshelf(m2, 40, GY - 400, 230, 400, (176, 120, 80), rng)
    plant_pot(m2, LW - 90, GY + 6, 170); plant_pot(m2, 330, GY + 6, 110)
    sx = LW * rng.uniform(0.42, 0.7)
    m2.rect(sx, GY - 120, sx + 380, GY + 6, (110, 170, 214), r=22); m2.rect(sx - 20, GY - 96, sx + 30, GY + 6, (86, 146, 194), r=18); m2.rect(sx + 350, GY - 96, sx + 400, GY + 6, (86, 146, 194), r=18)
    m2.rect(sx + 30, GY - 160, sx + 350, GY - 100, (130, 188, 232), r=22)
    m2.rect(sx + 50, GY - 20, sx + 66, GY + 12, (100, 70, 50)); m2.rect(sx + 334, GY - 20, sx + 350, GY + 12, (100, 70, 50))
    near = _cv()
    ground(near, GY, (214, 158, 104), (232, 182, 128), (190, 134, 86))
    near.rect(-10, GY - 26, LW + 10, GY, (250, 246, 238))
    for x in range(-60, LW + 100, 150):
        near.rect(x, GY + 10, x + 3, LH + 10, (170, 120, 76), alpha=170)
    for y in (GY + 70, GY + 140, GY + 220):
        near.rect(-10, y, LW + 10, y + 3, (170, 120, 76), alpha=130)
    near.ellipse(LW * 0.3, GY + 150, 260, 40, (232, 120, 120), alpha=210); near.ellipse(LW * 0.3, GY + 150, 190, 26, (250, 186, 140), alpha=210)
    return [Layer(far.hi(), 0.04, True), Layer(m1.hi(), 0.25), Layer(m2.hi(), 0.6), Layer(near.hi(), 1.0)], dict(dust=((255, 244, 214), 16)), FEET + 8


def _env_hills(pal, rng):
    far = _bg(pal, (96, 176, 252), (226, 246, 255)); sun_toon(far, LW * rng.uniform(0.25, 0.75), 230, 58)
    m0 = _cv(); hills(m0, rng, GY - 230, 60, (150, 206, 230), 3, step=10)
    m1 = _cv()
    for i in range(4):
        cloud_toon(m1, rng.uniform(100, LW - 100), rng.uniform(130, 330), rng.uniform(170, 300))
    m2 = _cv(); hills(m2, rng, GY - 90, 55, (122, 206, 138), 3, step=10)
    for i in range(8):
        tree_round(m2, rng.uniform(40, LW - 40), GY - 50 + rng.uniform(-20, 30), rng.uniform(110, 170), (128, 92, 64), rng.choice([(70, 168, 98), (96, 190, 100), (58, 150, 110)]))
    near = _cv(); ground(near, GY, (100, 196, 108), (140, 224, 130), (80, 170, 94))
    for _ in range(46):
        fx, fy = rng.uniform(0, LW), rng.uniform(GY + 20, LH - 10)
        near.line((fx, fy), (fx, fy - 14), 3, (60, 150, 84))
        c = rng.choice([(255, 120, 150), (255, 230, 110), (255, 255, 255), (190, 150, 255)])
        near.circle(fx, fy - 18, 6, c); near.circle(fx, fy - 18, 2.5, (255, 210, 90))
    return [Layer(far.hi(), 0.04, True), Layer(m0.hi(), 0.2), Layer(m1.hi(), 0.3), Layer(m2.hi(), 0.6), Layer(near.hi(), 1.0)], dict(birds=3, leaves=6, dust=((255, 255, 200), 10)), FEET


def _env_beach(pal, rng):
    far = _bg(pal, (86, 190, 250), (255, 236, 200)); sun_toon(far, LW * rng.uniform(0.6, 0.85), 220, 60)
    m0 = _cv()
    hy = GY - 130
    m0.rect(-10, hy, LW + 10, LH + 10, (40, 170, 220)); m0.rect(-10, hy, LW + 10, hy + 30, (90, 210, 236))
    for k in range(18):
        wx_ = rng.uniform(0, LW); wy_ = hy + rng.uniform(14, 110)
        m0.line((wx_, wy_), (wx_ + rng.uniform(40, 90), wy_), 4, (190, 240, 255), alpha=140)
    bx = rng.uniform(200, 900)                                 # sailboat
    m0.poly([(bx - 40, hy + 4), (bx + 44, hy + 4), (bx + 26, hy + 20), (bx - 24, hy + 20)], (200, 90, 80))
    m0.poly([(bx, hy), (bx, hy - 84), (bx + 40, hy - 6)], (255, 255, 255)); m0.poly([(bx - 6, hy - 4), (bx - 6, hy - 62), (bx - 34, hy - 6)], (255, 214, 120))
    m1 = _cv()
    for i in range(3):
        cloud_toon(m1, rng.uniform(100, LW - 100), rng.uniform(120, 300), rng.uniform(150, 260))
    m2 = _cv()
    m2.poly([(-10, GY - 60), (LW + 10, GY - 78), (LW + 10, LH), (-10, LH)], (62, 190, 220), alpha=255)
    for k in range(3):
        pts = [(-10, GY - 56 + k * 6)]
        for x in range(0, LW + 40, 20):
            pts.append((x, GY - 62 + k * 6 + math.sin(x * 0.03 + k) * 6))
        pts += [(LW + 10, LH), (-10, LH)]
        m2.poly(pts, (86, 210, 232) if k == 0 else (255, 255, 255), alpha=200 if k else 255)
    for px, lean in ((120, 0.3), (LW - 160, -0.28)):
        palm(m2, px, GY + 20, rng.uniform(300, 360), lean)
    near = _cv(); ground(near, GY - 30, (246, 222, 156), (255, 240, 190), (232, 204, 136))
    for _ in range(26):
        sx_, sy_ = rng.uniform(0, LW), rng.uniform(GY + 10, LH - 10)
        near.circle(sx_, sy_, rng.uniform(2, 5), (214, 186, 120), alpha=200)
        if rng.random() < 0.2:
            near.ellipse(sx_, sy_, 10, 7, rng.choice([(255, 170, 150), (255, 220, 240), (250, 240, 230)]))
    near.poly([(LW * 0.78, GY + 130), (LW * 0.78 + 90, GY + 80), (LW * 0.78 + 180, GY + 130)], (240, 90, 90))
    near.poly([(LW * 0.78 + 90, GY + 80), (LW * 0.78 + 180, GY + 130), (LW * 0.78 + 130, GY + 130)], (255, 250, 250))
    near.rect(LW * 0.78 + 88, GY + 80, LW * 0.78 + 92, GY + 190, (120, 90, 70))
    return [Layer(far.hi(), 0.04, True), Layer(m0.hi(), 0.1), Layer(m1.hi(), 0.2), Layer(m2.hi(), 0.5), Layer(near.hi(), 1.0)], dict(birds=4, sparkle=(255, 255, 255, 50), sand=10), FEET + 4


def _env_space(pal, rng):
    far = _bg(pal, (6, 6, 28), (34, 18, 70)); stars(far, rng, 420); nebula(far, rng, [pal["a3"], pal["a2"]], 5, 0.9)
    m0 = _cv()
    ex, ey = LW * rng.uniform(0.55, 0.8), 260
    E.earth(m0, ex, ey, 360, 0, pal, 3)
    m1 = _cv(); hills(m1, rng, GY - 70, 28, (120, 118, 150), 3, jag=2, step=8)
    m2 = _cv(); hills(m2, rng, GY - 20, 20, (156, 154, 180), 3, jag=3, step=8)
    for _ in range(5):
        x = rng.uniform(0, LW); m2.poly(E.blob(x, GY - 8, rng.uniform(30, 70), 9, 0.3, rng.randrange(99), ry=rng.uniform(16, 34)), (136, 134, 160))
    near = _cv(); ground(near, GY, (176, 174, 200), (210, 208, 230), (142, 140, 170))
    for _ in range(9):
        cx_, cy_ = rng.uniform(0, LW), rng.uniform(GY + 30, LH - 20); r = rng.uniform(40, 110)
        near.ellipse(cx_, cy_, r, r * 0.26, (126, 124, 156)); near.ellipse(cx_, cy_ + 3, r * 0.88, r * 0.2, (152, 150, 182))
    for _ in range(18):
        near.circle(rng.uniform(0, LW), rng.uniform(GY + 20, LH), rng.uniform(3, 9), (150, 148, 176))
    # little flag
    fx = rng.uniform(900, 1500); near.rect(fx, GY - 110, fx + 5, GY + 10, (230, 230, 240)); near.poly([(fx + 5, GY - 110), (fx + 70, GY - 92), (fx + 5, GY - 74)], (240, 80, 90))
    return [Layer(far.hi(), 0.04, True), Layer(m0.hi(), 0.12), Layer(m1.hi(), 0.3), Layer(m2.hi(), 0.6), Layer(near.hi(), 1.0)], dict(twinkle=40, dust=((200, 200, 255), 8)), FEET


def _env_desert(pal, rng):
    far = _bg(pal, (255, 176, 120), (255, 232, 170)); sun_toon(far, LW * rng.uniform(0.25, 0.75), 330, 70, (255, 244, 190))
    m0 = _cv()
    for i in range(4):
        mesa(m0, rng.uniform(-100, LW), GY - 40, rng.uniform(260, 420), rng.uniform(150, 260), (214, 120, 92))
    m0.poly([(LW * 0.62, GY - 40), (LW * 0.62 + 130, GY - 220), (LW * 0.62 + 260, GY - 40)], (236, 196, 120))
    m0.poly([(LW * 0.62 + 130, GY - 220), (LW * 0.62 + 260, GY - 40), (LW * 0.62 + 170, GY - 40)], (206, 160, 92))
    m1 = _cv(); hills(m1, rng, GY - 60, 38, (240, 190, 124), 3, step=10)
    m2 = _cv(); hills(m2, rng, GY - 10, 26, (228, 170, 104), 2, step=10)
    for i in range(3):
        cactus(m2, rng.uniform(80, LW - 80), GY + 6, rng.uniform(150, 230))
    near = _cv(); ground(near, GY, (244, 204, 136), (255, 226, 164), (222, 176, 108))
    for _ in range(14):
        near.ellipse(rng.uniform(0, LW), rng.uniform(GY + 30, LH - 10), rng.uniform(30, 80), 5, (222, 176, 108), alpha=180)
    near.rect(LW * 0.1, GY + 40, LW * 0.1 + 6, GY + 100, (120, 90, 70)); near.circle(LW * 0.1 + 3, GY + 38, 8, (240, 240, 230))
    return [Layer(far.hi(), 0.04, True), Layer(m0.hi(), 0.15), Layer(m1.hi(), 0.35), Layer(m2.hi(), 0.65), Layer(near.hi(), 1.0)], dict(sand=22, dust=((255, 224, 160), 10), birds=1), FEET


def _env_snow(pal, rng):
    far = _bg(pal, (150, 200, 244), (238, 248, 255)); far.glow(LW * 0.3, 220, 300, (255, 255, 255), 0.5)
    m0 = _cv(); peaks(m0, rng, GY - 60, 260, 440, (170, 196, 232), snow=(255, 255, 255))
    m1 = _cv(); hills(m1, rng, GY - 90, 30, (222, 236, 250), 3, step=10)
    for i in range(9):
        pine(m1, rng.uniform(0, LW), GY - 70, rng.uniform(150, 250), (60, 130, 120), snow=True)
    m2 = _cv()
    for i in range(3):
        house(m2, 120 + i * 560 + rng.uniform(-60, 60), GY - 10, rng.uniform(120, 170), rng.uniform(80, 110), rng.choice([(236, 160, 120), (150, 190, 230), (230, 200, 130)]), (214, 90, 90), rng, snow=True)
    near = _cv(); ground(near, GY, (240, 248, 255), (255, 255, 255), (206, 224, 244))
    for _ in range(12):
        near.ellipse(rng.uniform(0, LW), rng.uniform(GY + 40, LH - 10), rng.uniform(40, 120), 8, (200, 220, 244), alpha=180)
    for i in range(2):
        px = rng.uniform(100, LW - 100)
        pine(near, px, GY + 40, rng.uniform(230, 300), (50, 118, 108), snow=True)
    # snowman
    sx = rng.uniform(900, 1500); near.circle(sx, GY + 100, 44, (255, 255, 255)); near.circle(sx, GY + 38, 32, (255, 255, 255)); near.circle(sx, GY - 12, 22, (255, 255, 255))
    near.circle(sx - 8, GY - 18, 3, (40, 40, 50)); near.circle(sx + 8, GY - 18, 3, (40, 40, 50)); near.poly([(sx, GY - 12), (sx + 24, GY - 8), (sx, GY - 6)], (255, 150, 60))
    return [Layer(far.hi(), 0.04, True), Layer(m0.hi(), 0.15), Layer(m1.hi(), 0.4), Layer(m2.hi(), 0.65), Layer(near.hi(), 1.0)], dict(snow=70, sparkle=(255, 255, 255, 60)), FEET


def _env_stage(pal, rng):
    far = _bg(pal, (46, 24, 90), (118, 44, 120)); stars(far, rng, 140, big=0.15)
    rays(far, rng, LW / 2, -40, (255, 236, 190), 5, 1300, 0.7, 24)
    m1 = _cv()
    m1.ellipse(LW / 2, GY - 120, 520, 230, (70, 40, 130), alpha=150)
    for k in range(12):
        m1.rect(k * 150, 0, k * 150 + 70, GY, (255, 255, 255), alpha=10)
    m2 = _cv()
    for sd in (-1, 1):
        x0 = 0 if sd < 0 else LW
        m2.poly([(x0, 0), (x0 + sd * 340, 0), (x0 + sd * 250, GY + 10), (x0, GY + 10)], (190, 36, 62))
        for k in range(1, 6):
            m2.line((x0 + sd * 52 * k, 0), (x0 + sd * 40 * k, GY + 10), 6, (146, 22, 48), alpha=190)
        m2.poly([(x0 + sd * 340, 0), (x0 + sd * 250, GY + 10), (x0 + sd * 230, GY + 10), (x0 + sd * 318, 0)], (226, 70, 96))
    m2.rect(-10, 0, LW + 10, 70, (170, 26, 52)); m2.rect(-10, 62, LW + 10, 80, (230, 190, 90))
    for k in range(0, LW, 120):
        m2.poly([(k, 80), (k + 60, 80), (k + 30, 108)], (230, 190, 90))
    near = _cv(); ground(near, GY, (170, 108, 74), (206, 142, 100), (130, 80, 56))
    for k in range(-1, 14):
        near.line((k * 150, GY + 10), (k * 150 - 120 + 240 * (k / 14), LH), 3, (120, 76, 52), alpha=150)
    near.ellipse(LW / 2, GY + 86, 420, 34, (255, 236, 190), alpha=70); near.ellipse(LW / 2, GY + 86, 300, 22, (255, 244, 210), alpha=70)
    near.rect(-10, GY + 190, LW + 10, GY + 215, (110, 66, 46))
    return [Layer(far.hi(), 0.03, True), Layer(m1.hi(), 0.2), Layer(m2.hi(), 0.8), Layer(near.hi(), 1.0)], dict(beams=((255, 236, 190), 26), dust=((255, 236, 190), 22), sparkle=(255, 230, 160, 70)), FEET + 6


def _env_underwater(pal, rng):
    far = _bg(pal, (40, 160, 214), (6, 44, 110)); rays(far, rng, rng.uniform(LW * 0.3, LW * 0.7), -60, (200, 250, 255), 9, 1500, 1.2, 24)
    m0 = _cv()
    for i in range(9):
        x = rng.uniform(0, LW); y = rng.uniform(200, GY - 100); s = rng.uniform(0.6, 1.1)
        d = rng.choice((-1, 1)); col = rng.choice([(255, 170, 90), (255, 220, 100), (140, 220, 255), (255, 140, 190)])
        m0.ellipse(x, y, 34 * s, 18 * s, col, alpha=200); m0.poly([(x - d * 30 * s, y), (x - d * 54 * s, y - 16 * s), (x - d * 54 * s, y + 16 * s)], col, alpha=200)
        m0.circle(x + d * 18 * s, y - 3 * s, 3.5 * s, (255, 255, 255), alpha=230)
    m1 = _cv(); hills(m1, rng, GY - 60, 30, (24, 100, 150), 3, step=10)
    for i in range(10):
        kelp(m1, rng.uniform(0, LW), GY - 40, rng.uniform(150, 320), (40, 150, 120), rng)
    m2 = _cv(); hills(m2, rng, GY - 4, 22, (222, 196, 142), 2, step=10)
    for i in range(5):
        coral(m2, rng.uniform(30, LW - 30), GY + 8, rng.uniform(130, 220), rng.choice([(255, 110, 140), (255, 170, 90), (190, 120, 240)]), rng)
    near = _cv(); ground(near, GY + 6, (236, 210, 156), (250, 228, 182), (208, 180, 126))
    for i in range(6):
        fan_coral(near, rng.uniform(0, LW), GY + 4, rng.uniform(70, 130), rng.choice([(255, 120, 150), (230, 110, 200)]))
    for _ in range(18):
        sx, sy = rng.uniform(0, LW), rng.uniform(GY + 30, LH - 10)
        near.ellipse(sx, sy, rng.uniform(6, 12), 5, rng.choice([(255, 220, 230), (255, 190, 150), (255, 255, 240)]))
    return [Layer(far.hi(), 0.05, True), Layer(m0.hi(), 0.25), Layer(m1.hi(), 0.5), Layer(m2.hi(), 0.8), Layer(near.hi(), 1.0)], dict(bubbles=26, dust=((190, 235, 255), 24)), FEET + 4


def _env_rooftop(pal, rng):
    far = _bg(pal, (86, 52, 140), (255, 160, 100)); sun_toon(far, LW * rng.uniform(0.3, 0.7), 470, 84, (255, 214, 120)); stars(far, rng, 70, ysplit=0.4)
    m0 = _cv(); skyline_layer(m0, rng, GY - 90, 150, 320, (122, 80, 150), windows=False, wmin=60, wmax=110)
    m1 = _cv(); skyline_layer(m1, rng, GY - 40, 140, 300, (84, 56, 118), windows=True, wmin=80, wmax=150)
    for i in range(2):
        tx = rng.uniform(100, LW - 150); m1.rect(tx, GY - 330, tx + 60, GY - 260, (100, 70, 90), r=4); m1.poly([(tx - 6, GY - 330), (tx + 30, GY - 366), (tx + 66, GY - 330)], (70, 46, 80)); m1.rect(tx + 8, GY - 260, tx + 14, GY - 150, (70, 46, 80)); m1.rect(tx + 46, GY - 260, tx + 52, GY - 150, (70, 46, 80))
    m2 = _cv()
    for i in range(3):
        bx = rng.uniform(40, LW - 200); m2.rect(bx, GY - 70, bx + 110, GY + 4, (130, 124, 146), r=5); m2.rect(bx + 14, GY - 56, bx + 96, GY - 44, (90, 86, 108)); m2.rect(bx + 14, GY - 34, bx + 96, GY - 22, (90, 86, 108))
    near = _cv(); ground(near, GY, (112, 108, 132), (156, 150, 176), (86, 82, 106))
    near.rect(-10, GY - 56, LW + 10, GY + 8, (150, 144, 170)); near.rect(-10, GY - 64, LW + 10, GY - 48, (186, 180, 204))
    for k in range(-1, 18):
        near.rect(k * 120, GY + 12, k * 120 + 3, LH, (84, 80, 104), alpha=150)
    near.rect(-10, GY + 160, LW + 10, GY + 166, (84, 80, 104), alpha=150)
    near.rect(LW * 0.8, GY - 200, LW * 0.8 + 90, GY - 56, (160, 90, 80), r=6); near.rect(LW * 0.8 + 10, GY - 190, LW * 0.8 + 80, GY - 170, (120, 66, 60))
    return [Layer(far.hi(), 0.04, True), Layer(m0.hi(), 0.15), Layer(m1.hi(), 0.35), Layer(m2.hi(), 0.7), Layer(near.hi(), 1.0)], dict(birds=3, dust=((255, 214, 170), 14), twinkle=14), FEET


def _env_cave(pal, rng):
    far = _bg(pal, (40, 24, 66), (88, 46, 104)); far.glow(LW * 0.5, LH * 0.6, 700, (170, 90, 190), 0.22)
    m0 = _cv(); hills(m0, rng, GY - 150, 70, (58, 36, 86), 3, jag=6, step=10)
    for i in range(14):
        stalactite(m0, rng.uniform(0, LW), 0, rng.uniform(120, 280), rng.uniform(24, 46), (70, 44, 100))
    m1 = _cv()
    for i in range(7):
        crystal(m1, rng.uniform(0, LW), GY - 20, rng.uniform(90, 220), rng.choice([(110, 230, 255), (255, 120, 220), (150, 130, 255)]))
    for i in range(10):
        stalactite(m1, rng.uniform(0, LW), 0, rng.uniform(70, 200), rng.uniform(20, 36), (92, 60, 118))
    m2 = _cv()
    hills(m2, rng, GY - 10, 30, (110, 76, 120), 3, jag=5, step=8)
    for i in range(4):
        x = rng.uniform(0, LW); h = rng.uniform(90, 190); m2.poly([(x - 40, GY + 10), (x - 10, GY - h), (x + 14, GY - h * 0.9), (x + 44, GY + 10)], (104, 70, 112))
    near = _cv(); ground(near, GY, (96, 70, 100), (132, 98, 136), (70, 48, 78))
    for _ in range(14):
        near.poly(E.blob(rng.uniform(0, LW), rng.uniform(GY + 40, LH - 10), rng.uniform(16, 44), 8, 0.35, rng.randrange(99), ry=rng.uniform(8, 20)), (74, 52, 84))
    for i in range(4):
        crystal(near, rng.uniform(0, LW), GY + rng.uniform(70, 160), rng.uniform(50, 110), rng.choice([(110, 230, 255), (255, 120, 220)]))
    return [Layer(far.hi(), 0.05, True), Layer(m0.hi(), 0.2), Layer(m1.hi(), 0.45), Layer(m2.hi(), 0.7), Layer(near.hi(), 1.0)], dict(fireflies=22, dust=((200, 160, 255), 18), sparkle=(190, 240, 255, 70)), FEET


def _env_lab(pal, rng):
    far = _bg(pal, (222, 240, 246), (186, 214, 228))
    for x in range(0, LW, 110):
        far.rect(x, 0, x + 2, LH, (255, 255, 255), alpha=130)
    for y in range(0, LH, 110):
        far.rect(0, y, LW, y + 2, (255, 255, 255), alpha=130)
    m1 = _cv()
    for i, (sx, sy, sw, sh) in enumerate(((140, 190, 300, 190), (LW - 520, 200, 380, 220))):
        m1.rect(sx - 8, sy - 8, sx + sw + 8, sy + sh + 8, (70, 84, 108), r=10); m1.rect(sx, sy, sx + sw, sy + sh, (16, 30, 52), r=6)
        pts = []
        for k in range(14):
            pts.append((sx + 14 + k * (sw - 28) / 13, sy + sh * 0.6 - math.sin(k * 0.9 + i * 2) * sh * 0.22 - k * 2))
        m1.polyline(pts, 4, (90, 240, 190)); m1.polyline([(x, y + 30) for x, y in pts], 3, (255, 170, 100), alpha=200)
        for k in range(5):
            m1.rect(sx + 14 + k * 26, sy + sh - 26, sx + 28 + k * 26, sy + sh - 12, (90, 200, 255), alpha=160)
    m1.rect(LW * 0.4, 150, LW * 0.4 + 230, 340, (250, 250, 255), r=8); m1.rect(LW * 0.4 + 14, 164, LW * 0.4 + 216, 326, (200, 226, 244))
    m1.circle(LW * 0.4 + 115, 245, 52, (255, 255, 255)); m1.line((LW * 0.4 + 115, 245), (LW * 0.4 + 115, 208), 5, (80, 90, 110)); m1.line((LW * 0.4 + 115, 245), (LW * 0.4 + 140, 256), 5, (80, 90, 110))
    m2 = _cv()
    m2.rect(-10, GY - 150, LW + 10, GY + 6, (232, 238, 246)); m2.rect(-10, GY - 160, LW + 10, GY - 140, (96, 110, 134))
    m2.rect(-10, GY - 140, LW + 10, GY - 120, (178, 190, 210), alpha=120)
    x = 60
    while x < LW - 80:
        kind = rng.randrange(3)
        col = rng.choice([(110, 230, 160), (255, 140, 190), (120, 190, 255), (255, 210, 90)])
        if kind == 0:
            flask(m2, x, GY - 160, 90, col, 0)
        elif kind == 1:
            flask(m2, x, GY - 160, 80, col, 1)
        else:
            m2.rect(x - 24, GY - 218, x + 24, GY - 160, (60, 70, 96), r=6); m2.circle(x, GY - 232, 20, (110, 124, 150)); m2.rect(x - 6, GY - 250, x + 6, GY - 232, (180, 190, 210))
        x += rng.uniform(150, 230)
    for k in range(-1, 14):
        m2.rect(k * 130 + 8, GY - 118, k * 130 + 120, GY - 6, (214, 222, 236), r=4); m2.rect(k * 130 + 54, GY - 88, k * 130 + 74, GY - 78, (110, 124, 150))
    near = _cv(); ground(near, GY, (200, 214, 232), (226, 236, 248), (176, 192, 214))
    for k in range(-1, 14):
        near.rect(k * 140, GY + 10, k * 140 + 3, LH, (150, 168, 196), alpha=190)
    for y in (GY + 80, GY + 170):
        near.rect(-10, y, LW + 10, y + 3, (150, 168, 196), alpha=190)
    return [Layer(far.hi(), 0.04, True), Layer(m1.hi(), 0.2), Layer(m2.hi(), 0.6), Layer(near.hi(), 1.0)], dict(sparkle=(160, 255, 220, 60), dust=((220, 245, 255), 10)), FEET + 6


def _env_forest(pal, rng):
    far = _bg(pal, (110, 190, 150), (40, 110, 90)); rays(far, rng, rng.uniform(LW * 0.3, LW * 0.7), -60, (255, 250, 190), 7, 1500, 0.9, 24)
    m0 = _cv(); hills(m0, rng, GY - 120, 40, (60, 140, 110), 3, step=10)
    for i in range(10):
        pine(m0, rng.uniform(0, LW), GY - 100, rng.uniform(200, 330), (48, 124, 98))
    m1 = _cv()
    for i in range(7):
        x = rng.uniform(0, LW); h = rng.uniform(360, 560); w = rng.uniform(36, 60)
        m1.rect(x, GY - h, x + w, GY + 10, (110, 76, 58)); m1.rect(x + w * 0.6, GY - h, x + w, GY + 10, (86, 58, 46))
        m1.ellipse(x + w / 2, GY - h, w * 3.1, w * 1.7, (60, 160, 100)); m1.ellipse(x + w / 2 - w, GY - h - w, w * 1.7, w * 1.1, (88, 190, 112))
    m2 = _cv(); hills(m2, rng, GY - 6, 24, (62, 150, 90), 3, step=10)
    for i in range(7):
        tree_round(m2, rng.uniform(0, LW), GY + 6, rng.uniform(130, 200), (118, 82, 60), (72, 170, 100))
    near = _cv(); ground(near, GY, (88, 176, 98), (124, 212, 118), (62, 140, 82))
    for i in range(7):
        mushroom(near, rng.uniform(0, LW), rng.uniform(GY + 40, LH - 10), rng.uniform(40, 80), rng.choice([(236, 84, 84), (255, 170, 80), (200, 120, 230)]))
    for _ in range(20):
        gx, gy = rng.uniform(0, LW), rng.uniform(GY + 20, LH - 6)
        for a in (-0.4, 0, 0.4):
            near.line((gx, gy), (gx + math.sin(a) * 24, gy - 30), 4, (60, 150, 80))
    return [Layer(far.hi(), 0.05, True), Layer(m0.hi(), 0.2), Layer(m1.hi(), 0.45), Layer(m2.hi(), 0.7), Layer(near.hi(), 1.0)], dict(fireflies=30, leaves=10, dust=((255, 250, 190), 12), beams=((255, 250, 190), 14)), FEET


ENV_FN = {"street": _env_street, "room": _env_room, "hills": _env_hills, "beach": _env_beach, "space": _env_space, "desert": _env_desert, "snow": _env_snow,
          "stage": _env_stage, "underwater": _env_underwater, "rooftop": _env_rooftop, "cave": _env_cave, "lab": _env_lab, "forest": _env_forest}
ENV_PAL = {"street": ["day", "dusk"], "room": ["day", "lab"], "hills": ["day", "forest"], "beach": ["day", "dusk"], "space": ["cosmos", "nebula", "neon"],
           "desert": ["dusk", "day"], "snow": ["ice", "day"], "stage": ["neon", "bio"], "underwater": ["ocean", "deep"], "rooftop": ["dusk", "neon"],
           "cave": ["bio", "nebula", "neon"], "lab": ["lab", "day"], "forest": ["forest", "day"]}


def build(env, pal_name, seed):
    if env not in ENV_FN:
        env = "hills"
    ok = ENV_PAL[env]
    name = pal_name if pal_name in ok else ok[int(seed) % len(ok)]
    pal = dict(PALETTES[name])
    rng = random.Random(int(seed) * 977 + sum(map(ord, env)))
    layers, ambient, gy = ENV_FN[env](pal, rng)
    return layers, ambient, pal, gy


# ------------------------------------------------------------------ ambient particles
@functools.lru_cache(maxsize=32)
def _particles(key, n, seed):
    rng = random.Random(hash((key, seed)) & 0xffffffff)
    return [(rng.random(), rng.random(), rng.uniform(0.5, 1.5), rng.uniform(0, 6.283), rng.random()) for _ in range(n)]


def ambient_layer(ambient, t, seed=0, size=(W, H)):
    """RGBA image (size) with the ambient particles of `ambient` at time t (seconds). Cheap (~5 ms)."""
    cv = Cv(W, H, 1)
    sd = int(seed) * 31
    a = ambient or {}
    if a.get("clouds"):
        for i, (px, py, sp, ph, r) in enumerate(_particles("clouds", int(a["clouds"]), sd)):
            x = ((px * (W + 600) + t * 10 * sp) % (W + 600)) - 300
            cloud_toon(cv, x, 70 + py * 150, 130 + r * 120, (255, 255, 255), alpha=150)
    if a.get("twinkle"):
        for px, py, sp, ph, r in _particles("twinkle", int(a["twinkle"]), sd):
            k = 0.5 + 0.5 * math.sin(t * 2.4 * sp + ph)
            cv.circle(px * W, py * H * 0.7, 1.4 + 2.2 * k * r, (255, 255, 235), alpha=int(80 + 175 * k))
    if a.get("dust"):
        col, n = a["dust"]
        for px, py, sp, ph, r in _particles("dust", int(n), sd):
            x = (px * W + math.sin(t * 0.4 * sp + ph) * 40 + t * 6 * sp) % W
            y = (py * H - t * 8 * sp) % H
            cv.circle(x, y, 1.6 + 2.2 * r, col, alpha=int(70 + 70 * math.sin(t * sp + ph) ** 2))
    if a.get("fireflies"):
        for px, py, sp, ph, r in _particles("ff", int(a["fireflies"]), sd):
            x = px * W + math.sin(t * 0.7 * sp + ph) * 60
            y = (0.3 + 0.6 * py) * H + math.cos(t * 0.5 * sp + ph * 2) * 40
            k = 0.5 + 0.5 * math.sin(t * 2.2 * sp + ph)
            cv.glow(x, y, 12 + 8 * k, (255, 245, 150), 0.9 * k)
            cv.circle(x, y, 2.2, (255, 255, 220), alpha=int(120 + 130 * k))
    if a.get("bubbles"):
        for px, py, sp, ph, r in _particles("bub", int(a["bubbles"]), sd):
            y = H + 20 - ((t * 36 * sp + py * (H + 60)) % (H + 60))
            x = px * W + math.sin(t * 1.3 * sp + ph) * 14
            rr = 3 + 9 * r
            cv.ring(x, y, rr, 1.6, (225, 250, 255), 170); cv.circle(x - rr * 0.35, y - rr * 0.35, rr * 0.22, (255, 255, 255), alpha=200)
    if a.get("snow"):
        for px, py, sp, ph, r in _particles("snow", int(a["snow"]), sd):
            y = ((py * (H + 30) + t * 46 * sp) % (H + 30)) - 15
            x = (px * W + math.sin(t * 0.8 * sp + ph) * 26 - t * 8) % W
            cv.circle(x, y, 1.8 + 3.2 * r, (255, 255, 255), alpha=220)
    if a.get("rain"):
        for px, py, sp, ph, r in _particles("rain", int(a["rain"]), sd):
            y = ((py * (H + 60) + t * 760 * sp) % (H + 60)) - 30
            x = (px * (W + 200) - t * 160 * sp) % (W + 200) - 60
            cv.line((x, y), (x - 9, y + 26), 2, (190, 215, 255), alpha=150, cap=False)
    if a.get("embers"):
        for px, py, sp, ph, r in _particles("emb", int(a["embers"]), sd):
            y = H - ((py * H + t * 60 * sp) % H)
            x = px * W + math.sin(t * 1.5 * sp + ph) * 26
            k = 1 - y / H
            cv.circle(x, y, 1.5 + 3 * r * k, (255, 170 + int(60 * r), 70), alpha=int(255 * min(1, 1.4 * k + 0.2)))
    if a.get("leaves"):
        for px, py, sp, ph, r in _particles("leaf", int(a["leaves"]), sd):
            y = ((py * (H + 40) + t * 28 * sp) % (H + 40)) - 20
            x = (px * W + math.sin(t * 0.9 * sp + ph) * 50 + t * 20) % W
            ang = t * 2 * sp + ph
            cv.poly([(x + math.cos(ang) * 8, y + math.sin(ang) * 4), (x, y - 3), (x - math.cos(ang) * 8, y - math.sin(ang) * 4), (x, y + 3)],
                    (120, 200, 90) if r > 0.4 else (240, 170, 70), alpha=210)
    if a.get("birds"):
        for px, py, sp, ph, r in _particles("bird", int(a["birds"]), sd):
            x = ((px * (W + 300) + t * 40 * sp) % (W + 300)) - 150
            y = 60 + py * 220 + math.sin(t * 0.7 + ph) * 14
            f = math.sin(t * 9 * sp + ph) * 7
            cv.polyline([(x - 14, y + f), (x, y), (x + 14, y + f)], 3, (60, 60, 80), alpha=200)
    if a.get("beams"):
        col, al = a["beams"]
        for i in range(3):
            x0 = W * (0.2 + 0.3 * i) + math.sin(t * 0.5 + i * 2) * 120
            sway = math.sin(t * 0.6 + i * 1.7) * 220
            cv.poly([(x0 - 10, -20), (x0 + 10, -20), (x0 + sway + 150, H), (x0 + sway - 150, H)], col, alpha=int(al))
    if a.get("sparkle"):
        r_, g_, b_, al = a["sparkle"]
        for px, py, sp, ph, r in _particles("spk", 18, sd):
            k = max(0.0, math.sin(t * 1.8 * sp + ph)) ** 6
            if k > 0.05:
                x, y = px * W, py * H; s = 4 + 10 * k
                cv.poly([(x, y - s), (x + s * 0.2, y - s * 0.2), (x + s, y), (x + s * 0.2, y + s * 0.2), (x, y + s), (x - s * 0.2, y + s * 0.2), (x - s, y), (x - s * 0.2, y - s * 0.2)],
                        (r_, g_, b_), alpha=int(min(255, al * 3 * k)))
    if a.get("sand"):
        for px, py, sp, ph, r in _particles("sand", int(a["sand"]), sd):
            x = (px * W + t * 120 * sp) % W
            y = H * (0.55 + 0.4 * py) + math.sin(t * 2 * sp + ph) * 6
            cv.line((x, y), (x + 14, y + 1), 2, (255, 236, 190), alpha=110, cap=False)
    img = cv.image()
    return img if tuple(size) == (W, H) else img.resize(size, Image.BILINEAR)
