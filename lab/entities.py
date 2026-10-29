"""Flat 'explainer' illustrations drawn in code: planets, cells, volcanoes, rockets ... (original designs, no outlines,
two-tone shading, soft glows). Every function draws onto a Cv at (cx, cy) with nominal size `s`, animated by time `t`."""
import math, random
from PIL import Image, ImageDraw, ImageChops
from .canvas import Cv, shade, mix, hexc, sphere_sprite, paste_alpha, ease_out, ease_back

TAU = math.tau


def rot(pts, cx, cy, ang):
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


def blob(cx, cy, r, n=14, wob=0.12, seed=0, ang=0.0, ry=None):
    rng = random.Random(seed)
    ph = [rng.uniform(0, TAU) for _ in range(3)]
    pts = []
    for i in range(n):
        a = TAU * i / n
        k = 1 + wob * (math.sin(a * 2 + ph[0]) * 0.6 + math.sin(a * 3 + ph[1]) * 0.4 + math.sin(a * 5 + ph[2]) * 0.2)
        pts.append((cx + math.cos(a + ang) * r * k, cy + math.sin(a + ang) * (ry or r) * k))
    return pts


PLANET_COLORS = [(224, 120, 84), (96, 160, 232), (170, 118, 220), (232, 188, 96), (92, 196, 168), (222, 110, 150), (132, 150, 240), (200, 150, 110)]


def _sprite(cv, spr, cx, cy, s):
    """Paste a hi-res sphere sprite (diameter 2r logical) centred."""
    cv.blit_hi(spr, cx - spr.width / cv.ss / 2, cy - spr.height / cv.ss / 2)


# ------------------------------------------------------------------ space
def sun(cv, cx, cy, s, t, pal, seed=0):
    r = s * 0.34
    cv.glow(cx, cy, r * 3.2, (255, 170, 60), 0.55, 2.2)
    cv.glow(cx, cy, r * 1.9, (255, 220, 120), 0.8, 2.0)
    for i in range(12):
        a = TAU * i / 12 + t * 0.25
        L = r * (1.55 + 0.18 * math.sin(t * 2 + i))
        w = 0.12
        cv.poly([(cx + math.cos(a - w) * r * 1.1, cy + math.sin(a - w) * r * 1.1), (cx + math.cos(a) * L, cy + math.sin(a) * L),
                 (cx + math.cos(a + w) * r * 1.1, cy + math.sin(a + w) * r * 1.1)], (255, 196, 70), alpha=170)
    _sprite(cv, sphere_sprite(r, (255, 192, 54), light=(-0.3, -0.4), shadow_k=-0.25, hi_k=0.5), cx, cy, s)
    cv.glow(cx - r * 0.25, cy - r * 0.3, r * 0.6, (255, 250, 200), 0.6, 1.5)


def moon(cv, cx, cy, s, t, pal, seed=0):
    r = s * 0.34
    cv.glow(cx, cy, r * 2.0, (200, 215, 255), 0.22, 2.0)
    spr = sphere_sprite(r, (214, 218, 232), light=(-0.5, -0.4), shadow_k=-0.35)
    sub = Cv(2 * r, 2 * r, cv.ss)
    sub.im.alpha_composite(spr)
    rng = random.Random(seed + 3)
    for _ in range(7):
        a, d = rng.uniform(0, TAU), rng.uniform(0.1, 0.72)
        px, py = r + math.cos(a) * r * d, r + math.sin(a) * r * d
        cr = rng.uniform(0.07, 0.16) * r
        sub.circle(px, py, cr, (170, 176, 196), alpha=200)
        sub.circle(px - cr * 0.15, py - cr * 0.15, cr * 0.7, (192, 198, 216), alpha=200)
    m = Image.new("L", sub.im.size, 0); ImageDraw.Draw(m).ellipse((0, 0, m.width - 1, m.height - 1), fill=255)
    sub.im.putalpha(ImageChops.multiply(sub.im.getchannel("A"), m))
    _sprite(cv, sub.im, cx, cy, s)


def earth(cv, cx, cy, s, t, pal, seed=0):
    r = s * 0.36
    cv.glow(cx, cy, r * 1.7, (110, 190, 255), 0.45, 2.2)
    sub = Cv(2 * r, 2 * r, cv.ss)
    sub.im.alpha_composite(sphere_sprite(r, (58, 132, 214), light=(-0.5, -0.45), shadow_k=-0.5))
    rng = random.Random(seed + 11)
    off = (t * 0.05) % 1.0
    for k in range(2):
        for j in range(5):
            a = TAU * (j / 5 + off + k * 0.5) % TAU
            gx = r + math.cos(a) * r * rng.uniform(0.1, 0.55)
            gy = r + rng.uniform(-0.6, 0.6) * r
            sub.poly(blob(gx, gy, r * rng.uniform(0.18, 0.32), 10, 0.35, seed + j + k * 7), (92, 184, 110) if k == 0 else (74, 160, 96))
    for j in range(4):
        cxx = r + math.cos(TAU * (j / 4 + off * 1.4)) * r * 0.5
        sub.ellipse(cxx, r + rng.uniform(-0.55, 0.55) * r, r * 0.34, r * 0.07, (255, 255, 255), alpha=200)
    # shade again on top for the terminator
    sh = sphere_sprite(r, (0, 0, 0), light=(-0.5, -0.45), shadow_k=0, hi_k=0)
    sh_a = sh.getchannel("A").point(lambda v: int(v * 0.0))
    m = Image.new("L", sub.im.size, 0); ImageDraw.Draw(m).ellipse((0, 0, m.width - 1, m.height - 1), fill=255)
    off2 = (-0.5 * r * 0.5 * cv.ss, -0.45 * r * 0.5 * cv.ss)
    m2 = Image.new("L", sub.im.size, 0)
    ImageDraw.Draw(m2).ellipse((off2[0], off2[1], m.width - 1 + off2[0], m.height - 1 + off2[1]), fill=255)
    cres = ImageChops.subtract(m, m2)
    dark = Image.new("RGBA", sub.im.size, (10, 30, 90, 255)); dark.putalpha(ImageChops.multiply(cres, Image.new("L", sub.im.size, 120)))
    sub.im.alpha_composite(dark)
    sub.im.putalpha(ImageChops.multiply(sub.im.getchannel("A"), m))
    _sprite(cv, sub.im, cx, cy, s)


def planet(cv, cx, cy, s, t, pal, seed=0, ringed=False):
    rng = random.Random(seed * 7 + 5)
    base = PLANET_COLORS[seed % len(PLANET_COLORS)]
    r = s * (0.28 if ringed else 0.34)
    cv.glow(cx, cy, r * 1.8, base, 0.28, 2.2)
    tilt = rng.uniform(-0.35, 0.2) if ringed else 0
    if ringed:
        ring_c = shade(base, 0.35)
        pts_b = [(cx + math.cos(a) * r * 2.0, cy + math.sin(a) * r * 0.55) for a in [TAU * i / 40 for i in range(0, 21)]]
        _ring(cv, cx, cy, r, tilt, ring_c, back=True)
    bands = [(0.18 + 0.15 * i, 0.26 + 0.15 * i, shade(base, -0.12 if i % 2 else 0.1)) for i in range(5)] if rng.random() < 0.6 else None
    spr = sphere_sprite(r, base, light=(-0.5, -0.45), bands=bands, shadow_k=-0.45)
    if not bands:
        sub = Cv(2 * r, 2 * r, cv.ss)
        sub.im.alpha_composite(spr)
        for _ in range(6):
            a, d = rng.uniform(0, TAU), rng.uniform(0.0, 0.7)
            cr = rng.uniform(0.06, 0.14) * r
            sub.circle(r + math.cos(a) * r * d, r + math.sin(a) * r * d, cr, shade(base, -0.2), alpha=170)
        m = Image.new("L", sub.im.size, 0); ImageDraw.Draw(m).ellipse((0, 0, m.width - 1, m.height - 1), fill=255)
        sub.im.putalpha(ImageChops.multiply(sub.im.getchannel("A"), m))
        spr = sub.im
    _sprite(cv, spr, cx, cy, s)
    if ringed:
        _ring(cv, cx, cy, r, tilt, shade(base, 0.35), back=False)


def _ring(cv, cx, cy, r, tilt, col, back):
    for k, (rr, w, a) in enumerate([(1.55, 0.16, 235), (1.9, 0.1, 190)]):
        pts = []
        rng = range(0, 181) if not back else range(180, 361)
        for d in rng[::6]:
            ang = math.radians(d)
            pts.append((math.cos(ang) * r * rr, math.sin(ang) * r * rr * 0.28))
        outer = [(x, y) for x, y in pts]
        inner = [(x * (1 - w / rr), y * (1 - w / rr)) for x, y in reversed(pts)]
        poly = [(cx + x * math.cos(tilt) - y * math.sin(tilt), cy + x * math.sin(tilt) + y * math.cos(tilt)) for x, y in outer + inner]
        cv.poly(poly, shade(col, -0.1 * k), alpha=a)


def star(cv, cx, cy, s, t, pal, seed=0):
    r = s * 0.4
    tw = 0.75 + 0.25 * math.sin(t * 3 + seed)
    cv.glow(cx, cy, r * 2.2, (255, 240, 190), 0.5 * tw, 2.0)
    pts = []
    for i in range(8):
        a = TAU * i / 8 - math.pi / 2
        rr = r * tw if i % 2 == 0 else r * 0.22
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    cv.poly(pts, (255, 244, 200))


def galaxy(cv, cx, cy, s, t, pal, seed=0):
    r = s * 0.5
    cv.glow(cx, cy, r * 1.2, (150, 110, 255), 0.4, 2.0)
    rng = random.Random(seed + 2)
    for arm in range(2):
        for i in range(70):
            u = i / 70
            a = arm * math.pi + u * 5.2 + t * 0.18
            rad = r * (0.08 + 0.92 * u)
            x = cx + math.cos(a) * rad + rng.uniform(-1, 1) * r * 0.05
            y = cy + math.sin(a) * rad * 0.42 + rng.uniform(-1, 1) * r * 0.025
            c = mix((255, 236, 200), (150, 160, 255), u)
            cv.circle(x, y, max(1.2, r * 0.035 * (1.1 - u * 0.5)), c, alpha=int(230 - 130 * u))
    cv.glow(cx, cy, r * 0.32, (255, 240, 210), 0.95, 1.6)


def blackhole(cv, cx, cy, s, t, pal, seed=0):
    r = s * 0.2
    cv.glow(cx, cy, r * 4.2, (255, 140, 60), 0.3, 2.2)
    for k, (rr, col, a) in enumerate([(3.0, (255, 110, 40), 120), (2.5, (255, 170, 70), 170), (2.0, (255, 226, 150), 220)]):
        cv.poly([(cx + math.cos(TAU * i / 60) * r * rr, cy + math.sin(TAU * i / 60) * r * rr * 0.26) for i in range(60)], col, alpha=a)
    cv.circle(cx, cy, r * 1.05, (255, 200, 120))
    cv.circle(cx, cy, r, (4, 2, 10))
    # lensed back of the disk wrapping over the top
    cv.arc_poly(cx, cy - r * 0.05, r * 1.02, r * 1.5, 195, 345, (255, 190, 100), alpha=150)
    cv.arc_poly(cx, cy - r * 0.05, r * 1.0, r * 1.18, 195, 345, (255, 240, 200), alpha=190)
    cv.circle(cx, cy, r * 0.98, (2, 1, 6))


def asteroid(cv, cx, cy, s, t, pal, seed=0):
    r = s * 0.32
    pts = blob(cx, cy, r, 13, 0.28, seed, ang=t * 0.6 * (1 if seed % 2 else -1))
    cv.glow(cx, cy, r * 1.5, (200, 160, 110), 0.12, 2.0)
    cv.poly(pts, (126, 110, 100))
    shadow = [(x + (cx - x) * 0.0, y) for x, y in pts]
    inner = [(cx + (x - cx) * 0.78 - r * 0.1, cy + (y - cy) * 0.78 - r * 0.12) for x, y in pts]
    cv.poly(inner, (156, 138, 124))
    rng = random.Random(seed)
    for _ in range(4):
        a, d = rng.uniform(0, TAU), rng.uniform(0, 0.55)
        cr = rng.uniform(0.1, 0.2) * r
        px, py = cx + math.cos(a + t * 0.6) * r * d, cy + math.sin(a + t * 0.6) * r * d
        cv.circle(px, py, cr, (100, 88, 82)); cv.circle(px - cr * 0.15, py - cr * 0.15, cr * 0.72, (126, 112, 104))


def comet(cv, cx, cy, s, t, pal, seed=0):
    r = s * 0.12
    ang = math.radians(-35)
    for i, (L, w, a) in enumerate([(2.6, 1.0, 40), (2.1, 0.7, 70), (1.6, 0.45, 110)]):
        d = (-math.cos(ang), -math.sin(ang))
        n = (-d[1], d[0])
        tip = (cx + d[0] * s * L, cy + d[1] * s * L)
        cv.poly([(cx + n[0] * r * w * 1.6, cy + n[1] * r * w * 1.6), tip, (cx - n[0] * r * w * 1.6, cy - n[1] * r * w * 1.6)], (150, 210, 255), alpha=a)
    cv.glow(cx, cy, r * 3.4, (190, 230, 255), 0.8, 2.0)
    cv.circle(cx, cy, r, (240, 250, 255))


def rocket(cv, cx, cy, s, t, pal, seed=0, angle=-0.6):
    sc = s / 200
    def T(pts): return rot([(cx + x * sc, cy + y * sc) for x, y in pts], cx, cy, angle)
    # flame
    fl = 1 + 0.18 * math.sin(t * 40) + 0.1 * math.sin(t * 27)
    cv.glow(*(rot([(cx, cy + 100 * sc)], cx, cy, angle)[0]), 70 * sc, (255, 160, 50), 0.6, 2.0)
    cv.poly(T([(-22, 70), (0, 70 + 120 * fl), (22, 70)]), (255, 150, 40))
    cv.poly(T([(-12, 70), (0, 70 + 78 * fl), (12, 70)]), (255, 232, 130))
    # fins
    cv.poly(T([(-34, 20), (-70, 80), (-34, 66)]), (212, 62, 74)); cv.poly(T([(34, 20), (70, 80), (34, 66)]), (212, 62, 74))
    # body
    body = [(-36, 70), (-38, -10), (-24, -70), (0, -112), (24, -70), (38, -10), (36, 70)]
    cv.poly(T(body), (238, 240, 250))
    cv.poly(T([(8, 70), (10, -10), (20, -66), (0, -112), (24, -70), (38, -10), (36, 70)]), (200, 206, 224))
    cv.poly(T([(-26, -52), (0, -112), (26, -52), (14, -60), (-14, -60)]), (222, 70, 80))
    cx2, cy2 = rot([(cx, cy - 14 * sc)], cx, cy, angle)[0]
    cv.circle(cx2, cy2, 17 * sc, (60, 80, 130)); cv.circle(cx2, cy2, 13 * sc, (120, 200, 255)); cv.circle(cx2 - 4 * sc, cy2 - 4 * sc, 4 * sc, (230, 250, 255))


def satellite(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 220
    ang = 0.35 + 0.05 * math.sin(t)
    def T(pts): return rot([(cx + x * sc, cy + y * sc) for x, y in pts], cx, cy, ang)
    for sd in (-1, 1):
        cv.poly(T([(sd * 34, -22), (sd * 120, -22), (sd * 120, 22), (sd * 34, 22)]), (50, 90, 190))
        for k in range(1, 4):
            cv.poly(T([(sd * (34 + k * 28.6), -22), (sd * (34 + k * 28.6 + 2), -22), (sd * (34 + k * 28.6 + 2), 22), (sd * (34 + k * 28.6), 22)]), (120, 170, 255))
    cv.poly(T([(-34, -32), (34, -32), (34, 32), (-34, 32)]), (224, 226, 236))
    cv.poly(T([(-34, 14), (34, 14), (34, 32), (-34, 32)]), (186, 190, 208))
    cv.poly(T([(-10, -32), (10, -32), (10, -52), (-10, -52)]), (150, 156, 176))
    x, y = rot([(cx, cy - 58 * sc)], cx, cy, ang)[0]
    cv.circle(x, y, 14 * sc, (255, 200, 80)); cv.circle(x, y, 6 * sc, (255, 240, 180))


def ufo(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 200
    bob = math.sin(t * 2) * 6 * sc
    cy += bob
    cv.poly([(cx - 30 * sc, cy + 20 * sc), (cx + 30 * sc, cy + 20 * sc), (cx + 90 * sc, cy + 170 * sc), (cx - 90 * sc, cy + 170 * sc)], (160, 255, 200), alpha=60)
    cv.ellipse(cx, cy - 18 * sc, 40 * sc, 34 * sc, (140, 220, 255), alpha=235)
    cv.ellipse(cx - 12 * sc, cy - 28 * sc, 12 * sc, 8 * sc, (230, 250, 255), alpha=200)
    cv.ellipse(cx, cy + 6 * sc, 100 * sc, 26 * sc, (168, 176, 200))
    cv.ellipse(cx, cy + 14 * sc, 100 * sc, 18 * sc, (118, 126, 156))
    for i in range(5):
        a = (i - 2) * 0.42
        on = (math.sin(t * 6 + i * 1.3) > -0.2)
        cv.circle(cx + math.sin(a) * 74 * sc, cy + 10 * sc + math.cos(a) * 6 * sc, 6 * sc, (255, 240, 120) if on else (200, 180, 90))


# ------------------------------------------------------------------ earth & weather
def volcano(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    base = cy + 120 * sc
    cv.glow(cx, cy - 90 * sc, 150 * sc, (255, 110, 40), 0.45, 2.0)
    cv.poly([(cx - 190 * sc, base), (cx - 36 * sc, cy - 100 * sc), (cx + 36 * sc, cy - 100 * sc), (cx + 190 * sc, base)], (112, 78, 84))
    cv.poly([(cx + 20 * sc, cy - 100 * sc), (cx + 36 * sc, cy - 100 * sc), (cx + 190 * sc, base), (cx + 70 * sc, base)], (86, 58, 68))
    cv.poly([(cx - 36 * sc, cy - 100 * sc), (cx + 36 * sc, cy - 100 * sc), (cx + 26 * sc, cy - 112 * sc), (cx - 26 * sc, cy - 112 * sc)], (255, 120, 40))
    for k, off in enumerate((-10, 8)):
        w = 8 * sc
        pts = [(cx + off * sc, cy - 108 * sc)]
        for j in range(1, 7):
            pts.append((cx + off * sc + math.sin(j + k * 2) * 12 * sc * j / 3, cy - 108 * sc + j * 36 * sc))
        cv.polyline(pts, w, (255, 140, 40)); cv.polyline(pts, w * 0.5, (255, 220, 110))
    rng = random.Random(seed)
    for i in range(10):
        u = (t * 0.6 + i / 10) % 1.0
        ang = -math.pi / 2 + rng.uniform(-0.8, 0.8)
        d = u * 200 * sc
        x = cx + math.cos(ang) * d * 0.6
        y = cy - 112 * sc + math.sin(ang) * d - (-u * u * 100 * sc)
        cv.circle(x, y, 5 * sc * (1 - u * 0.5), (255, 190 - int(70 * u), 70), alpha=int(255 * (1 - u)))
    for i in range(5):
        u = (t * 0.25 + i / 5) % 1.0
        cv.circle(cx + math.sin(i * 2 + t) * 20 * sc * u, cy - 120 * sc - u * 230 * sc, (26 + 60 * u) * sc, (92, 80, 94), alpha=int(190 * (1 - u)))


def mountain(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    base = cy + 110 * sc
    for dx, h, w, col in ((-90, 150, 130, (104, 120, 160)), (60, 210, 170, (124, 140, 184))):
        top = (cx + dx * sc, base - h * sc * 1.2)
        L, Rr = (cx + (dx - w) * sc, base), (cx + (dx + w) * sc, base)
        cv.poly([L, top, Rr], col)
        cv.poly([top, Rr, (cx + (dx + w * 0.2) * sc, base)], shade(col, -0.25))
        cv.poly([top, (top[0] - w * 0.26 * sc, top[1] + h * 0.34 * sc), (top[0] - w * 0.08 * sc, top[1] + h * 0.26 * sc), (top[0] + w * 0.08 * sc, top[1] + h * 0.36 * sc),
                 (top[0] + w * 0.27 * sc, top[1] + h * 0.34 * sc)], (240, 246, 255))


def tree(cv, cx, cy, s, t, pal, seed=0, pine=None):
    sc = s / 300
    pine = (seed % 3 == 0) if pine is None else pine
    sway = math.sin(t * 1.4 + seed) * 4 * sc
    base = cy + 110 * sc
    cv.poly([(cx - 12 * sc, base), (cx + 12 * sc, base), (cx + 8 * sc, base - 90 * sc), (cx - 8 * sc, base - 90 * sc)], (126, 88, 70))
    if pine:
        for k in range(4):
            y = base - (60 + k * 52) * sc
            w = (96 - k * 20) * sc
            cv.poly([(cx - w + sway * k * 0.3, y + 48 * sc), (cx + sway * (k + 1) * 0.4, y - 56 * sc), (cx + w + sway * k * 0.3, y + 48 * sc)], (52, 140, 96) if k % 2 else (66, 164, 108))
    else:
        for (dx, dy, r, col) in ((-48, -140, 62, (70, 164, 100)), (48, -140, 62, (70, 164, 100)), (0, -184, 76, (86, 186, 110)), (0, -120, 74, (60, 150, 92))):
            cv.circle(cx + dx * sc + sway, base + dy * sc, r * sc, col)
        cv.circle(cx - 20 * sc + sway, base - 196 * sc, 22 * sc, (120, 214, 134), alpha=190)


def cloud(cv, cx, cy, s, t, pal, seed=0, dark=False):
    sc = s / 300
    col = (96, 104, 134) if dark else (250, 252, 255)
    sh = shade(col, -0.18)
    drift = math.sin(t * 0.6 + seed) * 6 * sc
    cx += drift
    for dx, dy, r in ((-78, 14, 46), (-30, -16, 62), (30, -2, 56), (78, 18, 42)):
        cv.circle(cx + dx * sc, cy + dy * sc + 12 * sc, r * sc, sh)
    cv.rect(cx - 118 * sc, cy + 22 * sc, cx + 118 * sc, cy + 62 * sc, sh, r=20 * sc)
    for dx, dy, r in ((-78, 14, 46), (-30, -16, 62), (30, -2, 56), (78, 18, 42)):
        cv.circle(cx + dx * sc, cy + dy * sc, r * sc, col)
    cv.rect(cx - 118 * sc, cy + 14 * sc, cx + 118 * sc, cy + 54 * sc, col, r=20 * sc)


def bolt(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    flick = 0.55 + 0.45 * (math.sin(t * 22) > -0.3)
    cv.glow(cx, cy, 190 * sc, (255, 240, 120), 0.5 * flick, 2.0)
    pts = [(cx + 20 * sc, cy - 150 * sc), (cx - 70 * sc, cy + 14 * sc), (cx - 8 * sc, cy + 14 * sc), (cx - 40 * sc, cy + 150 * sc), (cx + 78 * sc, cy - 40 * sc), (cx + 12 * sc, cy - 40 * sc)]
    cv.poly(pts, (255, 214, 60))
    cv.poly([(cx + 18 * sc, cy - 120 * sc), (cx - 40 * sc, cy + 6 * sc), (cx + 4 * sc, cy + 6 * sc), (cx - 20 * sc, cy + 100 * sc), (cx + 50 * sc, cy - 50 * sc), (cx + 6 * sc, cy - 50 * sc)], (255, 244, 170))


def rain(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cloud(cv, cx, cy - 70 * sc, s, t, pal, seed, dark=True)
    rng = random.Random(seed)
    for i in range(16):
        u = (t * 1.3 + rng.random()) % 1.0
        x = cx - 110 * sc + (i / 15) * 220 * sc
        y = cy - 10 * sc + u * 170 * sc
        cv.line((x, y), (x - 8 * sc, y + 22 * sc), 5 * sc, (120, 196, 255), alpha=int(255 * min(1, (1 - u) * 3)))


def wave(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    for k, (amp, col) in enumerate([(26, (60, 150, 230)), (20, (44, 118, 208)), (14, (30, 90, 180))]):
        pts = [(cx - 170 * sc, cy + 110 * sc)]
        for i in range(0, 41):
            x = cx - 170 * sc + i * 340 * sc / 40
            y = cy - 20 * sc + k * 34 * sc + math.sin(i * 0.5 + t * (1.6 + k * 0.3) + k) * amp * sc
            pts.append((x, y))
        pts.append((cx + 170 * sc, cy + 110 * sc))
        cv.poly(pts, col)
        crest = pts[1:-1]
        cv.polyline(crest, 4 * sc, shade(col, 0.4), alpha=170)


def whale(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    sw = math.sin(t * 1.8) * 10 * sc
    body = [(cx - 150 * sc, cy + 10 * sc), (cx - 110 * sc, cy - 50 * sc), (cx - 20 * sc, cy - 70 * sc), (cx + 80 * sc, cy - 40 * sc), (cx + 130 * sc, cy - 6 * sc),
            (cx + 130 * sc, cy + 24 * sc), (cx + 60 * sc, cy + 56 * sc), (cx - 30 * sc, cy + 66 * sc), (cx - 110 * sc, cy + 50 * sc)]
    tail = [(cx + 120 * sc, cy + 8 * sc), (cx + 190 * sc, cy - 40 * sc + sw), (cx + 210 * sc, cy - 20 * sc + sw), (cx + 168 * sc, cy + 14 * sc + sw * 0.6), (cx + 214 * sc, cy + 50 * sc + sw),
            (cx + 190 * sc, cy + 66 * sc + sw), (cx + 120 * sc, cy + 28 * sc)]
    cv.poly(tail, (52, 88, 150)); cv.poly(body, (62, 104, 172))
    cv.poly([(cx - 130 * sc, cy + 36 * sc), (cx - 20 * sc, cy + 30 * sc), (cx + 60 * sc, cy + 50 * sc), (cx - 30 * sc, cy + 64 * sc), (cx - 108 * sc, cy + 50 * sc)], (190, 214, 240))
    cv.poly([(cx - 10 * sc, cy + 26 * sc), (cx + 40 * sc, cy + 76 * sc + sw * 0.5), (cx + 10 * sc, cy + 30 * sc)], (52, 88, 150))
    cv.circle(cx - 100 * sc, cy + 6 * sc, 7 * sc, (20, 30, 60)); cv.circle(cx - 102 * sc, cy + 3 * sc, 2.4 * sc, (255, 255, 255))


def shark(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    sw = math.sin(t * 3) * 8 * sc
    cv.poly([(cx + 100 * sc, cy), (cx + 170 * sc, cy - 50 * sc + sw), (cx + 150 * sc, cy + sw * 0.4), (cx + 170 * sc, cy + 50 * sc + sw), (cx + 100 * sc, cy + 14 * sc)], (96, 112, 138))
    cv.poly([(cx - 150 * sc, cy + 10 * sc), (cx - 60 * sc, cy - 36 * sc), (cx + 50 * sc, cy - 34 * sc), (cx + 112 * sc, cy - 4 * sc), (cx + 112 * sc, cy + 10 * sc), (cx + 40 * sc, cy + 40 * sc), (cx - 70 * sc, cy + 36 * sc)], (112, 130, 158))
    cv.poly([(cx - 70 * sc, cy + 20 * sc), (cx + 40 * sc, cy + 18 * sc), (cx + 100 * sc, cy + 12 * sc), (cx + 38 * sc, cy + 40 * sc), (cx - 68 * sc, cy + 36 * sc)], (226, 234, 246))
    cv.poly([(cx - 20 * sc, cy - 34 * sc), (cx + 14 * sc, cy - 96 * sc), (cx + 36 * sc, cy - 34 * sc)], (96, 112, 138))
    cv.circle(cx - 100 * sc, cy, 6 * sc, (15, 20, 40))
    for i in range(4):
        cv.line((cx - 60 * sc + i * 9 * sc, cy + 6 * sc), (cx - 56 * sc + i * 9 * sc, cy + 22 * sc), 3 * sc, (20, 30, 60))


def fish(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    col = [(255, 168, 70), (92, 200, 220), (240, 110, 130), (130, 220, 150)][seed % 4]
    sw = math.sin(t * 5 + seed) * 10 * sc
    cv.poly([(cx + 70 * sc, cy), (cx + 138 * sc, cy - 46 * sc + sw), (cx + 138 * sc, cy + 46 * sc + sw)], shade(col, -0.15))
    cv.poly(blob(cx, cy, 90 * sc, 16, 0.02, 1, ry=58 * sc), col)
    cv.poly([(cx - 20 * sc, cy - 54 * sc), (cx + 30 * sc, cy - 80 * sc), (cx + 50 * sc, cy - 40 * sc)], shade(col, -0.2))
    cv.ellipse(cx - 4 * sc, cy + 24 * sc, 70 * sc, 24 * sc, shade(col, 0.4), alpha=170)
    for i in range(3):
        cv.line((cx + (10 + i * 18) * sc, cy - 40 * sc), (cx + (4 + i * 18) * sc, cy + 36 * sc), 7 * sc, shade(col, -0.2), alpha=160)
    cv.circle(cx - 52 * sc, cy - 10 * sc, 12 * sc, (255, 255, 255)); cv.circle(cx - 55 * sc, cy - 10 * sc, 6 * sc, (30, 30, 60))


def jellyfish(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    pulse = 1 + 0.06 * math.sin(t * 3)
    cy += math.sin(t * 1.5) * 8 * sc
    cv.glow(cx, cy, 160 * sc, (240, 130, 220), 0.35, 2.0)
    for i in range(6):
        x0 = cx - 70 * sc + i * 28 * sc
        pts = [(x0 + math.sin(t * 3 + i + j * 0.9) * 8 * sc, cy + 10 * sc + j * 24 * sc) for j in range(9)]
        cv.polyline(pts, 6 * sc, (240, 150, 230), alpha=190)
    pts = [(cx + math.cos(math.pi + math.pi * i / 20) * 100 * sc * pulse, cy + math.sin(math.pi + math.pi * i / 20) * 88 * sc / pulse) for i in range(21)]
    cv.poly(pts + [(cx + 100 * sc * pulse, cy + 6 * sc), (cx - 100 * sc * pulse, cy + 6 * sc)], (232, 120, 214))
    cv.poly([(cx + math.cos(math.pi + math.pi * i / 20) * 70 * sc, cy - 8 * sc + math.sin(math.pi + math.pi * i / 20) * 56 * sc) for i in range(21)], (250, 170, 236), alpha=200)


# ------------------------------------------------------------------ life & matter
def cell(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    wob = 0.04 + 0.01 * math.sin(t * 2)
    pts = blob(cx, cy, 120 * sc, 22, wob, seed + int(t * 1.5) * 0, ang=t * 0.2)
    cv.glow(cx, cy, 190 * sc, (255, 120, 190), 0.3, 2.0)
    cv.poly(pts, (240, 118, 170))
    cv.poly(blob(cx, cy, 108 * sc, 22, wob, seed, ang=t * 0.2), (255, 170, 200))
    cv.poly(blob(cx + 14 * sc, cy - 6 * sc, 46 * sc, 14, 0.06, seed + 1), (120, 70, 190))
    cv.circle(cx + 20 * sc, cy - 4 * sc, 15 * sc, (176, 120, 240))
    rng = random.Random(seed)
    for i in range(5):
        a = rng.uniform(0, TAU) + t * 0.2 * (1 if i % 2 else -1)
        d = rng.uniform(55, 95) * sc
        cv.ellipse(cx + math.cos(a) * d, cy + math.sin(a) * d, 16 * sc, 9 * sc, (255, 220, 120) if i % 2 else (120, 220, 190))


def virus(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    r = 78 * sc
    cv.glow(cx, cy, 190 * sc, (150, 255, 120), 0.3, 2.0)
    for i in range(14):
        a = TAU * i / 14 + t * 0.4
        x1, y1 = cx + math.cos(a) * r, cy + math.sin(a) * r
        x2, y2 = cx + math.cos(a) * (r + 46 * sc), cy + math.sin(a) * (r + 46 * sc)
        cv.line((x1, y1), (x2, y2), 8 * sc, (120, 200, 90)); cv.circle(x2, y2, 11 * sc, (210, 90, 120))
    cv.circle(cx, cy, r, (116, 190, 100)); cv.circle(cx - 8 * sc, cy - 10 * sc, r * 0.8, (150, 220, 120))
    for i in range(5):
        a = i * 1.7 + t * 0.3
        cv.circle(cx + math.cos(a) * r * 0.45, cy + math.sin(a) * r * 0.4, 8 * sc, (96, 168, 84))


def dna(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    n = 26
    top = cy - 150 * sc
    step = 300 * sc / n
    cols = [(255, 110, 150), (110, 220, 255)]
    pts_a, pts_b = [], []
    for i in range(n + 1):
        ph = i * 0.5 + t * 2.0
        y = top + i * step
        pts_a.append((cx + math.sin(ph) * 62 * sc, y, math.cos(ph)))
        pts_b.append((cx - math.sin(ph) * 62 * sc, y, -math.cos(ph)))
    for i in range(0, n + 1, 2):
        cv.line((pts_a[i][0], pts_a[i][1]), (pts_b[i][0], pts_b[i][1]), 6 * sc, (200, 210, 240), alpha=170)
    for strand, col in ((pts_a, cols[0]), (pts_b, cols[1])):
        for (x, y, z) in sorted(strand, key=lambda p: p[2]):
            cv.circle(x, y, (10 + 4 * z) * sc, shade(col, -0.18 * (1 - z)))


def atom(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 160 * sc, (120, 200, 255), 0.35, 2.0)
    for k in range(3):
        ang = k * math.pi / 3 + 0.3
        pts = [(math.cos(a) * 130 * sc, math.sin(a) * 46 * sc) for a in [TAU * i / 60 for i in range(61)]]
        pts = [(cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang)) for x, y in pts]
        cv.polyline(pts, 4 * sc, (150, 200, 255), alpha=180, cap=False)
        a = t * (2.2 + k * 0.5) + k * 2
        ex, ey = math.cos(a) * 130 * sc, math.sin(a) * 46 * sc
        cv.circle(cx + ex * math.cos(ang) - ey * math.sin(ang), cy + ex * math.sin(ang) + ey * math.cos(ang), 11 * sc, (255, 220, 110))
    for i, (dx, dy, col) in enumerate([(-10, -8, (255, 110, 120)), (10, -6, (110, 170, 255)), (0, 10, (255, 110, 120)), (-6, 0, (110, 170, 255))]):
        cv.circle(cx + dx * sc, cy + dy * sc, 18 * sc, col)
        cv.circle(cx + (dx - 5) * sc, cy + (dy - 5) * sc, 6 * sc, shade(col, 0.5), alpha=200)


def brain(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 190 * sc, (255, 140, 200), 0.3, 2.0)
    cv.poly(blob(cx - 4 * sc, cy, 128 * sc, 26, 0.09, seed + 4, ry=96 * sc), (246, 140, 176))
    cv.poly(blob(cx - 10 * sc, cy - 6 * sc, 110 * sc, 26, 0.08, seed + 4, ry=80 * sc), (255, 176, 200))
    cv.poly([(cx + 40 * sc, cy + 70 * sc), (cx + 70 * sc, cy + 130 * sc), (cx + 52 * sc, cy + 134 * sc), (cx + 28 * sc, cy + 78 * sc)], (226, 118, 156))
    rng = random.Random(seed)
    for k in range(7):
        pts = []
        x0, y0 = cx + rng.uniform(-80, 80) * sc, cy + rng.uniform(-50, 50) * sc
        for j in range(6):
            pts.append((x0 + j * 12 * sc * (1 if k % 2 else -1), y0 + math.sin(j * 1.3 + k) * 16 * sc))
        cv.polyline(pts, 5 * sc, (226, 118, 156), alpha=220)
    for i in range(7):
        u = (t * 0.9 + i * 0.37) % 1.0
        a = rng.uniform(0, TAU)
        d = rng.uniform(0.2, 0.9) * 100 * sc
        cv.glow(cx + math.cos(a) * d, cy + math.sin(a) * d * 0.7, 26 * sc, (255, 240, 130), 0.9 * math.sin(u * math.pi), 1.8)


def heart(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300 * (1 + 0.07 * max(0, math.sin(t * 7)) ** 2)
    cv.glow(cx, cy, 190 * sc, (255, 70, 100), 0.4, 2.0)
    def H(k, dy=0):
        pts = []
        for i in range(60):
            a = TAU * i / 60
            x = 16 * math.sin(a) ** 3
            y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
            pts.append((cx + x * 7.4 * sc * k, cy + (y * 7.4 * k + dy) * sc))
        return pts
    cv.poly(H(1.0), (222, 52, 84))
    cv.poly(H(0.86, -4), (244, 92, 116))
    cv.ellipse(cx - 62 * sc, cy - 56 * sc, 20 * sc, 10 * sc, (255, 190, 200), alpha=190)


def bulb(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    glow = 0.8 + 0.2 * math.sin(t * 5)
    cv.glow(cx, cy - 20 * sc, 200 * sc, (255, 230, 100), 0.6 * glow, 2.0)
    for i in range(10):
        a = TAU * i / 10
        cv.line((cx + math.cos(a) * 130 * sc, cy - 20 * sc + math.sin(a) * 130 * sc), (cx + math.cos(a) * 168 * sc, cy - 20 * sc + math.sin(a) * 168 * sc), 8 * sc, (255, 220, 90), alpha=int(220 * glow))
    cv.circle(cx, cy - 24 * sc, 92 * sc, (255, 226, 110))
    cv.poly([(cx - 36 * sc, cy + 50 * sc), (cx + 36 * sc, cy + 50 * sc), (cx + 30 * sc, cy + 84 * sc), (cx - 30 * sc, cy + 84 * sc)], (255, 226, 110))
    cv.circle(cx - 28 * sc, cy - 56 * sc, 24 * sc, (255, 248, 200), alpha=190)
    cv.rect(cx - 34 * sc, cy + 82 * sc, cx + 34 * sc, cy + 96 * sc, (170, 176, 196), r=6 * sc)
    cv.rect(cx - 28 * sc, cy + 98 * sc, cx + 28 * sc, cy + 112 * sc, (140, 146, 170), r=6 * sc)
    cv.polyline([(cx - 18 * sc, cy + 52 * sc), (cx - 10 * sc, cy + 10 * sc), (cx, cy + 30 * sc), (cx + 10 * sc, cy + 10 * sc), (cx + 18 * sc, cy + 52 * sc)], 5 * sc, (255, 150, 60), cap=False)


def clock(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 190 * sc, (150, 210, 255), 0.3, 2.0)
    cv.circle(cx, cy, 124 * sc, (70, 90, 160)); cv.circle(cx, cy, 112 * sc, (244, 246, 255))
    for i in range(12):
        a = TAU * i / 12 - math.pi / 2
        cv.line((cx + math.cos(a) * 94 * sc, cy + math.sin(a) * 94 * sc), (cx + math.cos(a) * 106 * sc, cy + math.sin(a) * 106 * sc), (7 if i % 3 == 0 else 4) * sc, (70, 90, 160), cap=False)
    ah = t * 0.6 - math.pi / 2; am = t * 7.2 - math.pi / 2
    cv.line((cx, cy), (cx + math.cos(ah) * 56 * sc, cy + math.sin(ah) * 56 * sc), 10 * sc, (50, 60, 120))
    cv.line((cx, cy), (cx + math.cos(am) * 84 * sc, cy + math.sin(am) * 84 * sc), 7 * sc, (230, 80, 100))
    cv.circle(cx, cy, 9 * sc, (50, 60, 120))


def hourglass(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    u = (t * 0.25) % 1.0
    cv.rect(cx - 86 * sc, cy - 130 * sc, cx + 86 * sc, cy - 114 * sc, (150, 110, 80), r=8 * sc)
    cv.rect(cx - 86 * sc, cy + 114 * sc, cx + 86 * sc, cy + 130 * sc, (150, 110, 80), r=8 * sc)
    cv.poly([(cx - 70 * sc, cy - 112 * sc), (cx + 70 * sc, cy - 112 * sc), (cx + 6 * sc, cy), (cx + 70 * sc, cy + 112 * sc), (cx - 70 * sc, cy + 112 * sc), (cx - 6 * sc, cy)], (200, 230, 255), alpha=120)
    top = 70 * (1 - u)
    cv.poly([(cx - 60 * sc * (top / 70 + 0.15), cy - 100 * sc + (70 - top) * sc), (cx + 60 * sc * (top / 70 + 0.15), cy - 100 * sc + (70 - top) * sc), (cx + 4 * sc, cy - 6 * sc), (cx - 4 * sc, cy - 6 * sc)], (255, 200, 90))
    bot = 70 * u
    cv.poly([(cx - 58 * sc, cy + 106 * sc), (cx + 58 * sc, cy + 106 * sc), (cx, cy + (106 - bot) * sc)], (255, 200, 90))
    cv.line((cx, cy - 6 * sc), (cx, cy + (106 - bot) * sc), 3 * sc, (255, 200, 90))


def thermo(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    lvl = 0.45 + 0.4 * (0.5 + 0.5 * math.sin(t * 0.8))
    cv.glow(cx, cy + 80 * sc, 150 * sc, (255, 90, 70), 0.3 * lvl, 2.0)
    cv.rect(cx - 28 * sc, cy - 140 * sc, cx + 28 * sc, cy + 80 * sc, (236, 240, 252), r=28 * sc)
    cv.circle(cx, cy + 100 * sc, 54 * sc, (236, 240, 252))
    cv.circle(cx, cy + 100 * sc, 40 * sc, (230, 64, 80))
    top = cy + 80 * sc - lvl * 200 * sc
    cv.rect(cx - 12 * sc, top, cx + 12 * sc, cy + 100 * sc, (230, 64, 80), r=10 * sc)
    for i in range(6):
        cv.line((cx + 34 * sc, cy - 110 * sc + i * 34 * sc), (cx + (56 if i % 2 == 0 else 46) * sc, cy - 110 * sc + i * 34 * sc), 4 * sc, (236, 240, 252), cap=False)


def snowflake(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 170 * sc, (190, 235, 255), 0.35, 2.0)
    for i in range(6):
        a = TAU * i / 6 + t * 0.2
        x1, y1 = cx + math.cos(a) * 130 * sc, cy + math.sin(a) * 130 * sc
        cv.line((cx, cy), (x1, y1), 12 * sc, (200, 240, 255))
        for k in (0.45, 0.72):
            bx, by = cx + math.cos(a) * 130 * sc * k, cy + math.sin(a) * 130 * sc * k
            for sd in (-1, 1):
                cv.line((bx, by), (bx + math.cos(a + sd * 0.8) * 40 * sc, by + math.sin(a + sd * 0.8) * 40 * sc), 8 * sc, (220, 246, 255))
    cv.circle(cx, cy, 20 * sc, (240, 252, 255))


def fire(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 220 * sc, (255, 120, 40), 0.5, 2.0)
    def flame(k, col, dx=0, hh=1.0):
        fl = 1 + 0.08 * math.sin(t * 13 + dx) + 0.05 * math.sin(t * 21)
        pts = [(cx + dx * sc, cy + 130 * sc)]
        for i in range(0, 13):
            u = i / 12
            w = math.sin(u * math.pi) ** 0.8 * 110 * k * (1 - 0.1 * u)
            pts.append((cx + (dx - w + math.sin(t * 6 + u * 4) * 6) * sc, cy + (130 - u * 250 * hh * fl) * sc))
        tip = (cx + (dx + math.sin(t * 5) * 8) * sc, cy + (130 - 270 * hh * fl) * sc)
        for i in range(12, -1, -1):
            u = i / 12
            w = math.sin(u * math.pi) ** 0.8 * 110 * k * (1 - 0.1 * u)
            pts.append((cx + (dx + w + math.sin(t * 6 + u * 4 + 2) * 6) * sc, cy + (130 - u * 250 * hh * fl) * sc))
        cv.poly(pts, col)
    flame(1.0, (240, 70, 40)); flame(0.78, (255, 150, 40), 6, 0.86); flame(0.5, (255, 230, 110), 4, 0.6)


def skyline(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    rng = random.Random(seed + 9)
    x = cx - 170 * sc
    base = cy + 120 * sc
    cols = [(70, 82, 140), (84, 96, 156), (60, 70, 124)]
    while x < cx + 160 * sc:
        w = rng.uniform(34, 62) * sc
        h = rng.uniform(70, 250) * sc
        col = cols[rng.randrange(3)]
        cv.rect(x, base - h, x + w, base, col)
        cv.rect(x + w * 0.55, base - h, x + w, base, shade(col, -0.2))
        for wy in range(int(base - h + 10 * sc), int(base - 14 * sc), int(18 * sc)):
            for wx in (x + w * 0.2, x + w * 0.6):
                if rng.random() < 0.55:
                    cv.rect(wx, wy, wx + 7 * sc, wy + 9 * sc, (255, 220, 120))
        x += w + rng.uniform(2, 10) * sc


def house(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.rect(cx - 110 * sc, cy - 10 * sc, cx + 110 * sc, cy + 110 * sc, (236, 220, 196))
    cv.rect(cx + 40 * sc, cy - 10 * sc, cx + 110 * sc, cy + 110 * sc, (214, 196, 172))
    cv.poly([(cx - 134 * sc, cy - 6 * sc), (cx, cy - 110 * sc), (cx + 134 * sc, cy - 6 * sc)], (206, 84, 84))
    cv.poly([(cx, cy - 110 * sc), (cx + 134 * sc, cy - 6 * sc), (cx + 40 * sc, cy - 6 * sc)], (170, 62, 72))
    cv.rect(cx - 30 * sc, cy + 30 * sc, cx + 10 * sc, cy + 110 * sc, (134, 96, 80), r=4 * sc)
    cv.rect(cx - 90 * sc, cy + 20 * sc, cx - 50 * sc, cy + 60 * sc, (150, 210, 250)); cv.rect(cx + 50 * sc, cy + 20 * sc, cx + 90 * sc, cy + 60 * sc, (255, 224, 140))


def car(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    col = [(232, 84, 96), (84, 160, 232), (250, 190, 70)][seed % 3]
    bob = math.sin(t * 14) * 1.5 * sc
    cy += bob
    cv.poly([(cx - 150 * sc, cy + 40 * sc), (cx - 140 * sc, cy - 10 * sc), (cx - 60 * sc, cy - 20 * sc), (cx - 20 * sc, cy - 78 * sc), (cx + 70 * sc, cy - 78 * sc), (cx + 110 * sc, cy - 20 * sc),
             (cx + 150 * sc, cy - 6 * sc), (cx + 152 * sc, cy + 40 * sc)], col)
    cv.poly([(cx - 8 * sc, cy - 64 * sc), (cx + 64 * sc, cy - 64 * sc), (cx + 92 * sc, cy - 22 * sc), (cx - 36 * sc, cy - 22 * sc)], (190, 230, 255))
    cv.rect(cx - 150 * sc, cy + 22 * sc, cx + 152 * sc, cy + 42 * sc, shade(col, -0.25))
    for wx in (-85, 85):
        cv.circle(cx + wx * sc, cy + 42 * sc, 36 * sc, (36, 40, 60)); cv.circle(cx + wx * sc, cy + 42 * sc, 20 * sc, (170, 176, 196))
        a = t * 14
        cv.line((cx + wx * sc, cy + 42 * sc), (cx + wx * sc + math.cos(a) * 18 * sc, cy + 42 * sc + math.sin(a) * 18 * sc), 5 * sc, (110, 116, 140))
    cv.circle(cx + 144 * sc, cy + 6 * sc, 8 * sc, (255, 240, 160))


def plane(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cy += math.sin(t * 1.3) * 5 * sc
    cv.poly([(cx - 150 * sc, cy - 10 * sc), (cx + 120 * sc, cy - 28 * sc), (cx + 170 * sc, cy), (cx + 120 * sc, cy + 26 * sc), (cx - 150 * sc, cy + 14 * sc)], (240, 244, 252))
    cv.poly([(cx - 150 * sc, cy - 6 * sc), (cx - 180 * sc, cy - 60 * sc), (cx - 140 * sc, cy - 60 * sc), (cx - 90 * sc, cy - 6 * sc)], (230, 80, 96))
    cv.poly([(cx - 20 * sc, cy + 6 * sc), (cx + 40 * sc, cy + 6 * sc), (cx - 40 * sc, cy + 110 * sc), (cx - 80 * sc, cy + 110 * sc)], (196, 204, 224))
    cv.poly([(cx - 20 * sc, cy - 10 * sc), (cx + 40 * sc, cy - 14 * sc), (cx - 30 * sc, cy - 90 * sc), (cx - 70 * sc, cy - 90 * sc)], (214, 220, 236))
    for i in range(8):
        cv.rect(cx + (-110 + i * 20) * sc, cy - 8 * sc, cx + (-98 + i * 20) * sc, cy + 2 * sc, (110, 170, 230), r=3 * sc)
    cv.poly([(cx + 120 * sc, cy - 26 * sc), (cx + 170 * sc, cy), (cx + 120 * sc, cy + 6 * sc)], (110, 170, 230))


def monitor(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 200 * sc, (90, 240, 220), 0.25, 2.0)
    cv.rect(cx - 140 * sc, cy - 100 * sc, cx + 140 * sc, cy + 70 * sc, (50, 56, 90), r=14 * sc)
    cv.rect(cx - 126 * sc, cy - 86 * sc, cx + 126 * sc, cy + 56 * sc, (14, 22, 42), r=8 * sc)
    rng = random.Random(seed)
    for i in range(6):
        w = rng.uniform(60, 190) * sc
        shown = min(1.0, max(0.0, (t * 1.2 - i * 0.25)))
        cv.rect(cx - 110 * sc + (i % 2) * 20 * sc, cy - 70 * sc + i * 20 * sc, cx - 110 * sc + (i % 2) * 20 * sc + w * shown, cy - 62 * sc + i * 20 * sc,
                [(90, 240, 200), (255, 120, 170), (255, 220, 110)][i % 3], r=4 * sc)
    cv.rect(cx - 12 * sc, cy + 70 * sc, cx + 12 * sc, cy + 104 * sc, (70, 76, 112))
    cv.rect(cx - 70 * sc, cy + 100 * sc, cx + 70 * sc, cy + 116 * sc, (70, 76, 112), r=8 * sc)


def phone(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 180 * sc, (120, 180, 255), 0.25, 2.0)
    cv.rect(cx - 66 * sc, cy - 130 * sc, cx + 66 * sc, cy + 130 * sc, (40, 46, 80), r=24 * sc)
    cv.rect(cx - 56 * sc, cy - 116 * sc, cx + 56 * sc, cy + 116 * sc, (230, 238, 252), r=14 * sc)
    for i in range(4):
        u = min(1.0, max(0.0, t * 1.5 - i * 0.4))
        side = i % 2
        w = 70 * sc
        x0 = cx - 46 * sc if side == 0 else cx + 46 * sc - w
        cv.rect(x0, cy - 100 * sc + i * 48 * sc, x0 + w * u, cy - 70 * sc + i * 48 * sc, (110, 170, 255) if side == 0 else (255, 160, 190), r=12 * sc)


def robot(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cy += math.sin(t * 2) * 5 * sc
    cv.glow(cx, cy, 180 * sc, (100, 220, 255), 0.25, 2.0)
    cv.line((cx, cy - 120 * sc), (cx, cy - 90 * sc), 6 * sc, (150, 156, 190)); cv.circle(cx, cy - 126 * sc, 10 * sc, (255, 100, 120))
    cv.rect(cx - 82 * sc, cy - 92 * sc, cx + 82 * sc, cy + 30 * sc, (188, 196, 222), r=28 * sc)
    cv.rect(cx - 66 * sc, cy - 74 * sc, cx + 66 * sc, cy + 12 * sc, (30, 40, 80), r=18 * sc)
    blink = 0.2 if (math.sin(t * 1.1) > 0.97) else 1.0
    for ex in (-28, 28):
        cv.ellipse(cx + ex * sc, cy - 30 * sc, 14 * sc, 16 * sc * blink, (110, 240, 230))
    cv.rect(cx - 56 * sc, cy + 36 * sc, cx + 56 * sc, cy + 124 * sc, (170, 178, 208), r=18 * sc)
    cv.circle(cx, cy + 80 * sc, 14 * sc, (255, 190, 80))
    for sd in (-1, 1):
        cv.line((cx + sd * 64 * sc, cy + 50 * sc), (cx + sd * 100 * sc, cy + 96 * sc + math.sin(t * 3 + sd) * 8 * sc), 14 * sc, (150, 156, 190))


def coin(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    w = abs(math.cos(t * 2.4)) * 0.92 + 0.08
    cv.glow(cx, cy, 180 * sc, (255, 210, 80), 0.4, 2.0)
    cv.ellipse(cx + 8 * sc * w, cy, 112 * sc * w, 112 * sc, (206, 150, 40))
    cv.ellipse(cx, cy, 112 * sc * w, 112 * sc, (255, 206, 64))
    cv.ellipse(cx, cy, 88 * sc * w, 88 * sc, (255, 226, 120))
    if w > 0.35:
        cv.rect(cx - 8 * sc * w, cy - 56 * sc, cx + 8 * sc * w, cy + 56 * sc, (214, 156, 40), r=4 * sc)
        cv.ellipse(cx, cy - 22 * sc, 34 * sc * w, 24 * sc, (214, 156, 40)); cv.ellipse(cx, cy + 22 * sc, 34 * sc * w, 24 * sc, (214, 156, 40))
        cv.ellipse(cx, cy - 22 * sc, 20 * sc * w, 12 * sc, (255, 226, 120)); cv.ellipse(cx, cy + 22 * sc, 20 * sc * w, 12 * sc, (255, 226, 120))


def magnet(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 190 * sc, (255, 120, 140), 0.25, 2.0)
    cv.arc_poly(cx, cy + 30 * sc, 56 * sc, 118 * sc, 180, 360, (210, 214, 232))
    cv.arc_poly(cx, cy + 30 * sc, 56 * sc, 118 * sc, 180, 270, (232, 70, 86))
    cv.arc_poly(cx, cy + 30 * sc, 56 * sc, 118 * sc, 270, 360, (80, 130, 230))
    cv.rect(cx - 118 * sc, cy + 30 * sc, cx - 56 * sc, cy + 110 * sc, (232, 70, 86)); cv.rect(cx + 56 * sc, cy + 30 * sc, cx + 118 * sc, cy + 110 * sc, (80, 130, 230))
    cv.rect(cx - 118 * sc, cy + 92 * sc, cx - 56 * sc, cy + 110 * sc, (240, 244, 252)); cv.rect(cx + 56 * sc, cy + 92 * sc, cx + 118 * sc, cy + 110 * sc, (240, 244, 252))
    for k in range(3):
        u = (t * 0.5 + k * 0.33) % 1.0
        r = (40 + 50 * k) * sc
        cv.polyline([(cx + math.cos(math.radians(a)) * r, cy + 100 * sc - math.sin(math.radians(a)) * (r * 1.4)) for a in range(0, 181, 12)], 3 * sc, (200, 220, 255), alpha=int(150 * (1 - 0.3 * k)), cap=False)


def battery(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    lv = 0.35 + 0.65 * ((t * 0.4) % 1.0)
    cv.glow(cx, cy, 180 * sc, (120, 255, 160), 0.25, 2.0)
    cv.rect(cx - 124 * sc, cy - 62 * sc, cx + 124 * sc, cy + 62 * sc, (210, 216, 236), r=20 * sc)
    cv.rect(cx + 124 * sc, cy - 26 * sc, cx + 146 * sc, cy + 26 * sc, (210, 216, 236), r=8 * sc)
    cv.rect(cx - 112 * sc, cy - 50 * sc, cx + 112 * sc, cy + 50 * sc, (36, 44, 76), r=12 * sc)
    n = 5
    for i in range(n):
        if (i + 1) / n <= lv + 0.01:
            cv.rect(cx - 104 * sc + i * 42 * sc, cy - 40 * sc, cx - 70 * sc + i * 42 * sc, cy + 40 * sc, (110, 240, 150) if lv > 0.35 else (255, 110, 100), r=8 * sc)
    cv.poly([(cx + 8 * sc, cy - 44 * sc), (cx - 18 * sc, cy + 6 * sc), (cx - 2 * sc, cy + 6 * sc), (cx - 10 * sc, cy + 44 * sc), (cx + 20 * sc, cy - 8 * sc), (cx + 4 * sc, cy - 8 * sc)], (255, 240, 130), alpha=235)


def eye(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    blink = max(0.08, 1 - max(0.0, math.sin(t * 1.7) - 0.93) * 14)
    cv.glow(cx, cy, 180 * sc, (140, 220, 255), 0.25, 2.0)
    top = [(cx + (u - 0.5) * 300 * sc, cy - math.sin(u * math.pi) * 96 * sc * blink) for u in [i / 20 for i in range(21)]]
    bot = [(cx + (u - 0.5) * 300 * sc, cy + math.sin(u * math.pi) * 96 * sc * blink) for u in [i / 20 for i in range(20, -1, -1)]]
    cv.poly(top + bot, (246, 248, 255))
    dx = math.sin(t * 0.9) * 22 * sc
    cv.circle(cx + dx, cy, 56 * sc * min(1, blink + 0.2), (80, 170, 220)); cv.circle(cx + dx, cy, 30 * sc * min(1, blink + 0.2), (24, 34, 70))
    cv.circle(cx + dx - 14 * sc, cy - 16 * sc, 11 * sc, (255, 255, 255))


def sound(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.poly([(cx - 130 * sc, cy - 28 * sc), (cx - 90 * sc, cy - 28 * sc), (cx - 40 * sc, cy - 80 * sc), (cx - 40 * sc, cy + 80 * sc), (cx - 90 * sc, cy + 28 * sc), (cx - 130 * sc, cy + 28 * sc)], (210, 216, 240))
    for k in range(4):
        u = (t * 0.8 + k * 0.25) % 1.0
        r = (60 + u * 130) * sc
        cv.arc_poly(cx - 30 * sc, cy, r, r + 12 * sc, -42, 42, (130, 210, 255), alpha=int(230 * (1 - u)))


def skull(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 190 * sc, (255, 80, 90), 0.25, 2.0)
    cv.circle(cx, cy - 18 * sc, 100 * sc, (240, 238, 232))
    cv.rect(cx - 56 * sc, cy + 40 * sc, cx + 56 * sc, cy + 110 * sc, (240, 238, 232), r=18 * sc)
    cv.ellipse(cx - 40 * sc, cy - 10 * sc, 26 * sc, 30 * sc, (34, 28, 46)); cv.ellipse(cx + 40 * sc, cy - 10 * sc, 26 * sc, 30 * sc, (34, 28, 46))
    cv.poly([(cx, cy + 14 * sc), (cx - 14 * sc, cy + 40 * sc), (cx + 14 * sc, cy + 40 * sc)], (34, 28, 46))
    for i in range(4):
        cv.rect(cx - 44 * sc + i * 24 * sc, cy + 66 * sc, cx - 36 * sc + i * 24 * sc, cy + 108 * sc, (190, 186, 188))


def person_icon(cv, cx, cy, s, col, t=0, bob=0):
    sc = s / 300
    cv.circle(cx, cy - 78 * sc + bob, 34 * sc, col)
    cv.rect(cx - 44 * sc, cy - 36 * sc + bob, cx + 44 * sc, cy + 76 * sc + bob, col, r=30 * sc)


def person(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 160 * sc, (140, 200, 255), 0.2, 2.0)
    person_icon(cv, cx, cy + 10 * sc, s, (110, 170, 250), t, math.sin(t * 2) * 3 * sc)


def crowd(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    rng = random.Random(seed)
    cols = [(110, 170, 250), (250, 150, 120), (140, 220, 170), (240, 200, 110), (190, 150, 240)]
    rows = [(-60, 0.6, 7), (0, 0.8, 6), (60, 1.0, 5)]
    for (dy, k, n) in rows:
        for i in range(n):
            x = cx + (i - (n - 1) / 2) * 62 * sc * 1.5 / (1.0 if n < 7 else 1.1)
            person_icon(cv, x, cy + dy * sc + 30 * sc, s * 0.34 * k, cols[(i + n) % 5], t, math.sin(t * 3 + i * 1.7) * 3 * sc * k)


def explosion(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    u = (t * 0.9) % 1.0
    k = 0.35 + 0.65 * ease_out(u)
    a = 1 - u ** 3
    cv.glow(cx, cy, 300 * sc * k, (255, 150, 50), 0.6 * a, 2.0)
    cv.ring(cx, cy, 190 * sc * k, 10 * sc * (1 - u * 0.7), (255, 220, 160), int(190 * a))
    rng = random.Random(seed)
    def burst(R, col, n=14, inner=0.62):
        pts = []
        for i in range(n * 2):
            ang = TAU * i / (n * 2) + 0.2
            rr = R * (1 if i % 2 == 0 else inner) * (1 + rng.uniform(-0.12, 0.12))
            pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
        cv.poly(pts, col)
    burst(150 * sc * k, (240, 70, 40)); burst(118 * sc * k, (255, 150, 50)); burst(80 * sc * k, (255, 230, 120)); cv.circle(cx, cy, 34 * sc * k, (255, 255, 235))


def gear(cv, cx, cy, s, t, pal, seed=0, n=10):
    sc = s / 300
    a0 = t * 0.9 * (1 if seed % 2 == 0 else -1)
    r = 104 * sc
    pts = []
    for i in range(n):
        for (da, rr) in ((-0.30, r), (-0.17, r * 1.26), (0.17, r * 1.26), (0.30, r)):
            a = a0 + TAU * (i + 0.5 + da) / n
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    cv.poly(pts, (158, 168, 204))
    cv.circle(cx, cy, r * 0.95, (184, 194, 226))
    cv.circle(cx, cy, r * 0.42, (60, 70, 110)); cv.circle(cx, cy, r * 0.3, (30, 36, 70))


def water_drop(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cy += math.sin(t * 2) * 5 * sc
    cv.glow(cx, cy, 170 * sc, (100, 190, 255), 0.3, 2.0)
    pts = [(cx, cy - 130 * sc)]
    for i in range(0, 41):
        a = math.pi * (i / 40) * 2 - math.pi / 2 + 0.0
    pts = []
    for i in range(61):
        ang = -math.pi / 2 + TAU * i / 60
        r = 92 * sc
        pts.append((cx + math.cos(ang) * r, cy + 40 * sc + math.sin(ang) * r))
    cv.poly([(cx, cy - 138 * sc), (cx + 84 * sc, cy + 20 * sc), (cx + 92 * sc, cy + 50 * sc)] + pts[15:46] + [(cx - 92 * sc, cy + 50 * sc), (cx - 84 * sc, cy + 20 * sc)], (70, 170, 245))
    cv.ellipse(cx - 34 * sc, cy + 30 * sc, 14 * sc, 30 * sc, (190, 232, 255), alpha=200)


def dino(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    col = (96, 170, 120)
    dark = shade(col, -0.3)
    sw = math.sin(t * 2.2) * 6 * sc
    for lx in (-62, 52):
        st = math.sin(t * 3 + lx) * 8 * sc
        cv.line((cx + lx * sc, cy + 20 * sc), (cx + lx * sc + st, cy + 112 * sc), 28 * sc, dark)
    cv.poly(blob(cx, cy, 108 * sc, 18, 0.03, 4, ry=66 * sc), col)
    cv.polyline([(cx + 80 * sc, cy - 6 * sc), (cx + 130 * sc, cy - 56 * sc), (cx + 150 * sc, cy - 130 * sc + sw), (cx + 188 * sc, cy - 150 * sc + sw)], 34 * sc, col)
    cv.circle(cx + 194 * sc, cy - 150 * sc + sw, 24 * sc, col); cv.circle(cx + 200 * sc, cy - 156 * sc + sw, 5 * sc, (20, 30, 40))
    cv.polyline([(cx - 90 * sc, cy + 6 * sc), (cx - 150 * sc, cy + 20 * sc + sw), (cx - 210 * sc, cy + 6 * sc + sw * 1.5)], 30 * sc, col)
    cv.ellipse(cx, cy + 28 * sc, 84 * sc, 30 * sc, shade(col, 0.3), alpha=170)
    for i in range(4):
        cv.circle(cx - 50 * sc + i * 30 * sc, cy - 56 * sc, 9 * sc, dark)


def pyramid(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    base = cy + 100 * sc
    cv.poly([(cx - 150 * sc, base), (cx, cy - 110 * sc), (cx + 40 * sc, base)], (232, 190, 110))
    cv.poly([(cx, cy - 110 * sc), (cx + 150 * sc, base), (cx + 40 * sc, base)], (190, 146, 80))
    for i in range(1, 5):
        y = base - i * 42 * sc
        cv.line((cx - (150 - i * 33) * sc, y), (cx + (140 - i * 33) * sc, y), 3 * sc, (170, 130, 76), cap=False)


def scale_balance(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    tilt = math.sin(t * 1.2) * 0.12
    cv.rect(cx - 8 * sc, cy - 90 * sc, cx + 8 * sc, cy + 110 * sc, (170, 176, 204), r=4 * sc)
    cv.rect(cx - 60 * sc, cy + 104 * sc, cx + 60 * sc, cy + 122 * sc, (140, 146, 180), r=8 * sc)
    L, Rr = (cx - math.cos(tilt) * 130 * sc, cy - 80 * sc - math.sin(tilt) * 130 * sc), (cx + math.cos(tilt) * 130 * sc, cy - 80 * sc + math.sin(tilt) * 130 * sc)
    cv.line(L, Rr, 10 * sc, (200, 206, 230))
    for (px, py), col in ((L, (110, 170, 250)), (Rr, (250, 170, 110))):
        cv.line((px, py), (px - 34 * sc, py + 80 * sc), 3 * sc, (170, 176, 204)); cv.line((px, py), (px + 34 * sc, py + 80 * sc), 3 * sc, (170, 176, 204))
        cv.poly([(px - 52 * sc, py + 80 * sc), (px + 52 * sc, py + 80 * sc), (px + 38 * sc, py + 98 * sc), (px - 38 * sc, py + 98 * sc)], col)
    cv.circle(cx, cy - 80 * sc, 14 * sc, (255, 210, 90))


def earth_layers(cv, cx, cy, s, t, pal, seed=0):
    r = s * 0.42
    cv.glow(cx, cy, r * 1.5, (255, 150, 70), 0.3, 2.2)
    layers = [(1.0, (74, 150, 104)), (0.95, (140, 96, 76)), (0.84, (232, 108, 54)), (0.56, (255, 172, 62)), (0.27, (255, 238, 160))]
    for k, col in layers:
        cv.circle(cx, cy, r * k, col)
    pulse = 0.5 + 0.5 * math.sin(t * 2.0)
    for k, col in layers[2:]:
        cv.ring(cx, cy, r * k, 3, shade(col, 0.35), int(120 + 80 * pulse))
    cv.glow(cx, cy, r * 0.34, (255, 252, 210), 0.5 + 0.4 * pulse, 1.6)
    # a cut-away corner showing the inside against the dark
    cv.poly([(cx, cy), (cx + r * 1.1 * math.cos(math.radians(-70)), cy + r * 1.1 * math.sin(math.radians(-70))),
             (cx + r * 1.1 * math.cos(math.radians(-20)), cy + r * 1.1 * math.sin(math.radians(-20)))], (18, 16, 40), alpha=0)
    cv.ring(cx, cy, r * 1.0, 2, (255, 255, 255), 50)


ENTITY_FN = {
    "sun": sun, "moon": moon, "earth": earth, "planet": planet, "ringed": lambda *a, **k: planet(*a, ringed=True, **k), "star": star, "galaxy": galaxy,
    "blackhole": blackhole, "asteroid": asteroid, "comet": comet, "rocket": rocket, "satellite": satellite, "ufo": ufo, "volcano": volcano,
    "mountain": mountain, "tree": tree, "cloud": cloud, "bolt": bolt, "rain": rain, "wave": wave, "whale": whale, "shark": shark, "fish": fish,
    "jellyfish": jellyfish, "cell": cell, "virus": virus, "dna": dna, "atom": atom, "brain": brain, "heart": heart, "bulb": bulb, "clock": clock,
    "hourglass": hourglass, "thermo": thermo, "snowflake": snowflake, "fire": fire, "skyline": skyline, "house": house, "car": car, "plane": plane,
    "monitor": monitor, "phone": phone, "robot": robot, "coin": coin, "magnet": magnet, "battery": battery, "eye": eye, "sound": sound,
    "skull": skull, "crowd": crowd, "person": person, "explosion": explosion, "gear": gear, "water_drop": water_drop, "dino": dino,
    "pyramid": pyramid, "scale": scale_balance, "earth_layers": earth_layers,
}
# how big (as a fraction of the nominal size) the drawing really is, for layout
ENTITY_EXTENT = {"whale": 1.4, "shark": 1.2, "fish": 0.9, "plane": 1.2, "car": 1.0, "skyline": 1.1, "wave": 1.2, "crowd": 1.1, "dino": 1.4, "mountain": 1.1, "volcano": 1.2,
                 "rocket": 1.0, "galaxy": 1.0, "comet": 1.3}


def draw_entity(cv, name, cx, cy, size, t, pal, seed=0):
    fn = ENTITY_FN.get(name)
    if fn is None:
        return False
    fn(cv, cx, cy, size, t, pal, seed)
    return True
