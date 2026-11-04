"""More things that can be drawn: everyday objects for self-improvement / psychology / science scripts (bed, book, dumbbell, coffee,
calendar, target, ladder, lock, mail, trophy, flag, sprout, speech bubble, checklist, alarm clock, laptop, scroll-phone, key, pill, apple).
Same contract as entities.py: fn(cv, cx, cy, s, t, pal, seed), flat shapes, no outlines, a little motion from t."""
import math
from . import entities as E

TAU = math.tau


def _sh(c, k):
    return tuple(max(0, min(255, int(v + (255 - v) * k) if k > 0 else int(v * (1 + k)))) for v in c)


def bed(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.rect(cx - 150 * sc, cy - 30 * sc, cx - 130 * sc, cy + 100 * sc, (150, 104, 76), r=8 * sc)             # headboard
    cv.rect(cx - 150 * sc, cy + 30 * sc, cx + 150 * sc, cy + 70 * sc, (176, 124, 90), r=10 * sc)             # frame
    cv.rect(cx + 130 * sc, cy + 30 * sc, cx + 150 * sc, cy + 100 * sc, (150, 104, 76), r=8 * sc)
    cv.rect(cx - 134 * sc, cy - 6 * sc, cx + 136 * sc, cy + 40 * sc, (236, 240, 252), r=14 * sc)             # mattress
    cv.rect(cx - 40 * sc, cy - 6 * sc, cx + 136 * sc, cy + 40 * sc, (120, 150, 230), r=14 * sc)              # blanket
    cv.rect(cx - 124 * sc, cy - 36 * sc, cx - 50 * sc, cy + 2 * sc, (255, 255, 255), r=16 * sc)              # pillow
    for i in range(3):
        u = (t * 0.5 + i * 0.33) % 1.0
        cv.circle(cx - 90 * sc + u * 70 * sc, cy - 70 * sc - u * 90 * sc, (8 + 6 * u) * sc, (160, 170, 230), alpha=int(220 * (1 - u)))


def book(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    flap = math.sin(t * 1.4) * 4 * sc
    cv.poly([(cx - 150 * sc, cy - 70 * sc), (cx, cy - 56 * sc + flap), (cx, cy + 90 * sc), (cx - 150 * sc, cy + 76 * sc)], (96, 130, 226))
    cv.poly([(cx + 150 * sc, cy - 70 * sc), (cx, cy - 56 * sc + flap), (cx, cy + 90 * sc), (cx + 150 * sc, cy + 76 * sc)], (122, 156, 244))
    cv.poly([(cx - 138 * sc, cy - 56 * sc), (cx - 6 * sc, cy - 44 * sc + flap), (cx - 6 * sc, cy + 74 * sc), (cx - 138 * sc, cy + 62 * sc)], (250, 248, 238))
    cv.poly([(cx + 138 * sc, cy - 56 * sc), (cx + 6 * sc, cy - 44 * sc + flap), (cx + 6 * sc, cy + 74 * sc), (cx + 138 * sc, cy + 62 * sc)], (255, 252, 244))
    for i in range(5):
        y = cy - 24 * sc + i * 18 * sc
        cv.line((cx - 118 * sc, y), (cx - 28 * sc, y + 8 * sc), 5 * sc, (190, 196, 214))
        cv.line((cx + 28 * sc, y + 8 * sc), (cx + 118 * sc, y), 5 * sc, (190, 196, 214))


def dumbbell(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cy += math.sin(t * 3) * 6 * sc
    cv.rect(cx - 110 * sc, cy - 12 * sc, cx + 110 * sc, cy + 12 * sc, (170, 176, 196), r=8 * sc)
    for sd in (-1, 1):
        cv.rect(cx + sd * 118 * sc - 22 * sc, cy - 70 * sc, cx + sd * 118 * sc + 22 * sc, cy + 70 * sc, (70, 80, 120), r=12 * sc)
        cv.rect(cx + sd * 84 * sc - 18 * sc, cy - 52 * sc, cx + sd * 84 * sc + 18 * sc, cy + 52 * sc, (96, 108, 156), r=10 * sc)


def coffee(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.ellipse(cx, cy + 96 * sc, 130 * sc, 20 * sc, (210, 216, 232))
    cv.poly([(cx - 86 * sc, cy - 40 * sc), (cx + 86 * sc, cy - 40 * sc), (cx + 66 * sc, cy + 90 * sc), (cx - 66 * sc, cy + 90 * sc)], (250, 246, 238))
    cv.ring(cx + 96 * sc, cy + 10 * sc, 34 * sc, 14 * sc, (250, 246, 238))
    cv.ellipse(cx, cy - 40 * sc, 86 * sc, 14 * sc, (120, 80, 56))
    for i in range(3):
        u = (t * 0.45 + i / 3) % 1.0
        x = cx - 34 * sc + i * 34 * sc + math.sin(u * 7 + i) * 10 * sc
        cv.circle(x, cy - 60 * sc - u * 110 * sc, (10 + 8 * u) * sc, (236, 240, 252), alpha=int(200 * (1 - u)))


def calendar(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.rect(cx - 120 * sc, cy - 100 * sc, cx + 120 * sc, cy + 110 * sc, (250, 248, 242), r=18 * sc)
    cv.rect(cx - 120 * sc, cy - 100 * sc, cx + 120 * sc, cy - 50 * sc, (232, 80, 96), r=18 * sc)
    cv.rect(cx - 120 * sc, cy - 70 * sc, cx + 120 * sc, cy - 50 * sc, (232, 80, 96))
    for sd in (-1, 1):
        cv.rect(cx + sd * 60 * sc - 6 * sc, cy - 116 * sc, cx + sd * 60 * sc + 6 * sc, cy - 76 * sc, (90, 96, 130), r=6 * sc)
    k = int(t * 2.2) % 28
    for r_ in range(4):
        for c_ in range(5):
            i = r_ * 5 + c_
            x, y = cx - 84 * sc + c_ * 42 * sc, cy - 22 * sc + r_ * 34 * sc
            if i < k // 1 and i % 7 != 3:
                cv.circle(x, y, 11 * sc, (96, 200, 140))
            else:
                cv.circle(x, y, 7 * sc, (214, 220, 234))


def target(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    for r_, c in ((130, (236, 84, 96)), (100, (250, 248, 242)), (70, (236, 84, 96)), (40, (250, 248, 242)), (16, (236, 84, 96))):
        cv.circle(cx, cy, r_ * sc, c)
    u = min(1.0, (t * 0.9) % 2.2)
    ax, ay = cx + 6 * sc + (1 - u) * 160 * sc, cy - 4 * sc - (1 - u) * 160 * sc
    cv.line((ax, ay), (ax + 120 * sc, ay - 120 * sc), 8 * sc, (150, 104, 76))
    cv.poly([(ax + 120 * sc, ay - 120 * sc), (ax + 150 * sc, ay - 128 * sc), (ax + 128 * sc, ay - 150 * sc)], (90, 150, 236))


def ladder(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    for sd in (-1, 1):
        cv.line((cx + sd * 56 * sc - sd * 14 * sc, cy + 130 * sc), (cx + sd * 40 * sc, cy - 140 * sc), 16 * sc, (196, 140, 96))
    for i in range(6):
        y = cy + 100 * sc - i * 46 * sc
        w = 54 * sc - i * 3 * sc
        cv.line((cx - w, y), (cx + w, y), 12 * sc, (230, 176, 120))
    k = int(t * 1.2) % 7
    cv.circle(cx, cy + 100 * sc - min(5, k) * 46 * sc - 28 * sc, 14 * sc, (110, 150, 240))


def lock(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    open_ = 0.5 + 0.5 * math.sin(t * 1.3)
    cv.ring(cx, cy - 56 * sc - open_ * 22 * sc, 56 * sc, 18 * sc, (170, 176, 196))
    cv.rect(cx - 96 * sc, cy - 40 * sc, cx + 96 * sc, cy + 110 * sc, (255, 200, 80), r=20 * sc)
    cv.circle(cx, cy + 20 * sc, 22 * sc, (130, 96, 40))
    cv.rect(cx - 7 * sc, cy + 24 * sc, cx + 7 * sc, cy + 70 * sc, (130, 96, 40), r=5 * sc)


def mail(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cy += math.sin(t * 2) * 5 * sc
    cv.rect(cx - 130 * sc, cy - 80 * sc, cx + 130 * sc, cy + 80 * sc, (250, 248, 242), r=14 * sc)
    cv.poly([(cx - 130 * sc, cy - 70 * sc), (cx, cy + 20 * sc), (cx + 130 * sc, cy - 70 * sc), (cx + 130 * sc, cy - 80 * sc), (cx - 130 * sc, cy - 80 * sc)], (190, 204, 236))
    cv.polyline([(cx - 126 * sc, cy - 72 * sc), (cx, cy + 22 * sc), (cx + 126 * sc, cy - 72 * sc)], 8 * sc, (150, 170, 220), cap=False)
    cv.circle(cx + 110 * sc, cy - 80 * sc, (22 + 3 * math.sin(t * 5)) * sc, (236, 80, 90))


def trophy(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy - 20 * sc, 190 * sc, (255, 220, 100), 0.35, 2.0)
    for sd in (-1, 1):
        cv.ring(cx + sd * 98 * sc, cy - 40 * sc, 36 * sc, 12 * sc, (255, 200, 60))
    cv.poly([(cx - 90 * sc, cy - 110 * sc), (cx + 90 * sc, cy - 110 * sc), (cx + 64 * sc, cy + 20 * sc), (cx, cy + 50 * sc), (cx - 64 * sc, cy + 20 * sc)], (255, 206, 70))
    cv.rect(cx - 14 * sc, cy + 40 * sc, cx + 14 * sc, cy + 90 * sc, (235, 170, 40))
    cv.rect(cx - 70 * sc, cy + 88 * sc, cx + 70 * sc, cy + 122 * sc, (150, 104, 76), r=8 * sc)
    cv.circle(cx - 40 * sc, cy - 70 * sc, 14 * sc, (255, 245, 190), alpha=200)


def flag(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.line((cx - 60 * sc, cy + 130 * sc), (cx - 60 * sc, cy - 140 * sc), 12 * sc, (170, 176, 196))
    pts = []
    for i in range(0, 11):
        u = i / 10
        pts.append((cx - 54 * sc + u * 170 * sc, cy - 130 * sc + math.sin(t * 4 - u * 5) * 9 * sc * u))
    low = [(x, y + 100 * sc) for x, y in pts][::-1]
    cv.poly(pts + [(x, y - 0) for x, y in low], (236, 84, 96))
    cv.circle(cx - 60 * sc, cy - 144 * sc, 12 * sc, (255, 206, 70))
    cv.ellipse(cx - 60 * sc, cy + 134 * sc, 70 * sc, 14 * sc, (120, 170, 110))


def sprout(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    g = min(1.0, 0.35 + (t * 0.25) % 0.65)
    cv.ellipse(cx, cy + 110 * sc, 140 * sc, 30 * sc, (150, 104, 76))
    cv.rect(cx - 8 * sc, cy + 110 * sc - 200 * sc * g, cx + 8 * sc, cy + 110 * sc, (88, 176, 104), r=6 * sc)
    for sd in (-1, 1):
        lx, ly = cx + sd * 56 * sc * g, cy + 110 * sc - 170 * sc * g
        cv.ellipse(lx, ly, 62 * sc * g, 30 * sc * g, (120, 210, 120))
    cv.circle(cx, cy + 110 * sc - 206 * sc * g, 8 * sc, (150, 230, 140))


def speech(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.rect(cx - 130 * sc, cy - 90 * sc, cx + 130 * sc, cy + 60 * sc, (250, 248, 242), r=40 * sc)
    cv.poly([(cx - 60 * sc, cy + 50 * sc), (cx - 90 * sc, cy + 112 * sc), (cx - 10 * sc, cy + 56 * sc)], (250, 248, 242))
    for i in range(3):
        cv.circle(cx - 56 * sc + i * 56 * sc, cy - 16 * sc - abs(math.sin(t * 3 - i * 0.7)) * 14 * sc, 14 * sc, (110, 130, 200))


def checklist(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.rect(cx - 100 * sc, cy - 130 * sc, cx + 100 * sc, cy + 130 * sc, (250, 248, 242), r=14 * sc)
    cv.rect(cx - 44 * sc, cy - 144 * sc, cx + 44 * sc, cy - 112 * sc, (120, 130, 170), r=8 * sc)
    k = int(t * 1.4) % 5
    for i in range(4):
        y = cy - 70 * sc + i * 56 * sc
        cv.rect(cx - 78 * sc, y - 16 * sc, cx - 46 * sc, y + 16 * sc, (222, 228, 242), r=6 * sc)
        if i < k:
            cv.polyline([(cx - 74 * sc, y), (cx - 62 * sc, y + 12 * sc), (cx - 44 * sc, y - 14 * sc)], 7 * sc, (80, 190, 120))
        cv.line((cx - 28 * sc, y), (cx + 76 * sc, y), 8 * sc, (190, 198, 218))


def alarm(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    sh = math.sin(t * 38) * 3 * sc if int(t * 2) % 2 == 0 else 0
    cx += sh
    for sd in (-1, 1):
        cv.circle(cx + sd * 82 * sc, cy - 112 * sc, 36 * sc, (236, 84, 96))
        cv.line((cx + sd * 100 * sc, cy + 118 * sc), (cx + sd * 120 * sc, cy + 140 * sc), 10 * sc, (120, 126, 150))
    cv.circle(cx, cy, 116 * sc, (236, 84, 96)); cv.circle(cx, cy, 94 * sc, (250, 248, 242))
    for i in range(12):
        a = TAU * i / 12 - math.pi / 2
        cv.circle(cx + math.cos(a) * 78 * sc, cy + math.sin(a) * 78 * sc, 4 * sc, (110, 116, 150))
    cv.line((cx, cy), (cx + 30 * sc, cy - 34 * sc), 9 * sc, (60, 66, 100))
    cv.line((cx, cy), (cx - 6 * sc, cy - 66 * sc), 6 * sc, (60, 66, 100))
    cv.circle(cx, cy, 8 * sc, (60, 66, 100))
    if int(t * 2) % 2 == 0:
        for sd in (-1, 1):
            cv.polyline([(cx + sd * 134 * sc, cy - 40 * sc), (cx + sd * 152 * sc, cy - 20 * sc), (cx + sd * 134 * sc, cy)], 6 * sc, (255, 190, 70), cap=False)


def laptop(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy - 20 * sc, 190 * sc, (120, 180, 255), 0.22, 2.0)
    cv.rect(cx - 120 * sc, cy - 100 * sc, cx + 120 * sc, cy + 50 * sc, (70, 80, 120), r=12 * sc)
    cv.rect(cx - 108 * sc, cy - 88 * sc, cx + 108 * sc, cy + 38 * sc, (226, 236, 252), r=6 * sc)
    for i in range(4):
        w = (70 + (i * 53 + int(seed) * 17) % 80) * sc
        cv.rect(cx - 92 * sc, cy - 70 * sc + i * 26 * sc, cx - 92 * sc + w, cy - 58 * sc + i * 26 * sc, [(110, 150, 240), (240, 130, 160), (110, 200, 160), (250, 200, 90)][i], r=5 * sc)
    cv.poly([(cx - 150 * sc, cy + 60 * sc), (cx + 150 * sc, cy + 60 * sc), (cx + 126 * sc, cy + 84 * sc), (cx - 126 * sc, cy + 84 * sc)], (150, 160, 190))


def key(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.glow(cx, cy, 180 * sc, (255, 220, 100), 0.25, 2.0)
    cv.ring(cx - 70 * sc, cy, 56 * sc, 22 * sc, (255, 200, 70))
    cv.rect(cx - 16 * sc, cy - 10 * sc, cx + 140 * sc, cy + 10 * sc, (255, 200, 70), r=6 * sc)
    for dx in (60, 100, 130):
        cv.rect(cx + dx * sc - 8 * sc, cy, cx + dx * sc + 8 * sc, cy + 40 * sc, (255, 200, 70), r=4 * sc)


def pill(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.rect(cx - 110 * sc, cy - 46 * sc, cx + 110 * sc, cy + 46 * sc, (250, 248, 242), r=46 * sc)
    cv.rect(cx - 110 * sc, cy - 46 * sc, cx, cy + 46 * sc, (236, 84, 96), r=46 * sc)
    cv.rect(cx - 60 * sc, cy - 46 * sc, cx, cy + 46 * sc, (236, 84, 96))
    cv.circle(cx - 60 * sc, cy - 20 * sc, 10 * sc, (255, 255, 255), alpha=170)


def apple(cv, cx, cy, s, t, pal, seed=0):
    sc = s / 300
    cv.circle(cx - 38 * sc, cy + 14 * sc, 82 * sc, (236, 84, 96)); cv.circle(cx + 38 * sc, cy + 14 * sc, 82 * sc, (236, 84, 96))
    cv.rect(cx - 8 * sc, cy - 90 * sc, cx + 8 * sc, cy - 48 * sc, (120, 84, 56), r=5 * sc)
    cv.ellipse(cx + 44 * sc, cy - 74 * sc, 40 * sc, 18 * sc, (110, 200, 110))
    cv.circle(cx - 56 * sc, cy - 10 * sc, 18 * sc, (255, 190, 196), alpha=190)


def scroll_phone(cv, cx, cy, s, t, pal, seed=0):
    """A phone being scrolled: cards stream up the screen."""
    sc = s / 300
    cv.glow(cx, cy, 180 * sc, (120, 180, 255), 0.25, 2.0)
    cv.rect(cx - 66 * sc, cy - 130 * sc, cx + 66 * sc, cy + 130 * sc, (40, 46, 80), r=24 * sc)
    cv.rect(cx - 56 * sc, cy - 116 * sc, cx + 56 * sc, cy + 116 * sc, (230, 238, 252), r=14 * sc)
    off = (t * 70) % 76
    for i in range(-1, 4):
        y = cy - 100 * sc + i * 76 * sc - off * sc
        if y < cy - 112 * sc or y > cy + 70 * sc:
            continue
        cv.rect(cx - 46 * sc, y, cx + 46 * sc, y + 62 * sc, [(255, 176, 196), (170, 200, 255), (190, 236, 200), (255, 226, 160)][i % 4], r=10 * sc)
        cv.circle(cx - 30 * sc, y + 16 * sc, 8 * sc, (255, 255, 255), alpha=200)


E.ENTITY_FN.update(dict(bed=bed, book=book, dumbbell=dumbbell, coffee=coffee, calendar=calendar, target=target, ladder=ladder, lock=lock, mail=mail,
                        trophy=trophy, flag=flag, sprout=sprout, speech=speech, checklist=checklist, alarm=alarm, laptop=laptop, key=key, pill=pill,
                        apple=apple, scroll_phone=scroll_phone))
E.ENTITY_EXTENT.update(dict(bed=1.1, book=1.1, laptop=1.0))
