"""Backgrounds ("worlds"). Each theme is drawn in code at 1280x720 with the floor line at y=GROUND."""
import functools, math, random
import numpy as np
from PIL import Image, ImageDraw

W, H = 1280, 720
GROUND = 588

THEMES = ["room_day", "room_night", "night_city", "sunrise", "mind", "city_day", "nature", "classroom", "exam_hall", "campus", "phone", "library"]


def vgrad(w, h, stops):
    """Vertical gradient from a list of (pos 0..1, (r,g,b))."""
    ys = np.linspace(0, 1, h)
    arr = np.zeros((h, 1, 3), np.float32)
    pos = [p for p, _ in stops]
    for c in range(3):
        arr[:, 0, c] = np.interp(ys, pos, [col[c] for _, col in stops])
    arr = np.repeat(arr, w, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


def glow(w, h, cx, cy, r, color, alpha=1.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** 2 * 255 * alpha
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = color
    out[..., 3] = a.astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def stars(d, rng, n, box, colors=((255, 255, 255), (255, 240, 200), (200, 220, 255))):
    x0, y0, x1, y1 = box
    for _ in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.choice([1, 1, 1.5, 2])
        c = rng.choice(colors) + (rng.randint(120, 255),)
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
        if r >= 2 and rng.random() < 0.3:
            d.line((x - 5, y, x + 5, y), fill=c, width=1)
            d.line((x, y - 5, x, y + 5), fill=c, width=1)


def cloud(d, x, y, s, color=(255, 255, 255, 235)):
    for dx, dy, r in ((0, 0, 30), (34, -12, 38), (74, -2, 32), (104, 8, 22), (-26, 10, 22)):
        d.ellipse((x + (dx - r) * s, y + (dy - r) * s, x + (dx + r) * s, y + (dy + r) * s), fill=color)
    d.rounded_rectangle((x - 40 * s, y + 4 * s, x + 118 * s, y + 38 * s), radius=int(18 * s), fill=color)


def hills(im, rng, base_y, color, amp, n, seed_off=0):
    d = ImageDraw.Draw(im)
    pts = [(-10, H + 10)]
    ph = rng.uniform(0, 6)
    for i in range(n + 1):
        x = -10 + (W + 20) * i / n
        pts.append((x, base_y - amp * (0.5 + 0.5 * math.sin(ph + i * 1.3 + seed_off)) - rng.uniform(0, amp * 0.25)))
    pts.append((W + 10, H + 10))
    d.polygon(pts, fill=color)


def skyline(im, rng, base, color, hmin, hmax, wmin, wmax, windows=None):
    d = ImageDraw.Draw(im)
    x = -20
    while x < W + 20:
        w = rng.randint(wmin, wmax)
        h = rng.randint(hmin, hmax)
        d.rectangle((x, base - h, x + w, base + 40), fill=color)
        if windows:
            for wy in range(base - h + 14, base - 8, 22):
                for wx in range(x + 8, x + w - 10, 18):
                    if rng.random() < 0.38:
                        d.rectangle((wx, wy, wx + 7, wy + 10), fill=windows)
        x += w + rng.randint(2, 10)


def tree(d, x, base, h, trunk=(120, 84, 66), leaf=(96, 170, 112), leaf2=(120, 196, 128)):
    d.rectangle((x - 7, base - h * 0.45, x + 7, base), fill=trunk)
    d.ellipse((x - h * 0.42, base - h * 1.0, x + h * 0.42, base - h * 0.3), fill=leaf)
    d.ellipse((x - h * 0.3, base - h * 1.0, x + h * 0.2, base - h * 0.55), fill=leaf2)


def floor_planks(im, y0, c1, c2, line):
    d = ImageDraw.Draw(im)
    g = vgrad(W, H - y0, [(0, c1), (1, c2)])
    im.alpha_composite(g, (0, y0))
    for y in range(y0 + 26, H, 34):
        d.line((0, y, W, y), fill=line, width=2)
    rng = random.Random(4)
    for y in range(y0, H, 34):
        off = rng.randint(0, 200)
        for x in range(-off, W, 240):
            d.line((x, y, x, y + 34), fill=line, width=2)


# -------------------------------------------------------------- themes
def room(night):
    rng = random.Random(11 if night else 5)
    if night:
        top = vgrad(W, GROUND, [(0, (58, 50, 98)), (1, (84, 66, 112))])
    else:
        top = vgrad(W, GROUND, [(0, (255, 240, 226)), (1, (250, 220, 204))])
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.alpha_composite(top, (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, GROUND - 22, W, GROUND), fill=(255, 255, 255, 60) if not night else (255, 255, 255, 22))
    # window
    wx0, wy0, wx1, wy1 = 70, 96, 330, 360
    frame_c = (255, 255, 255) if not night else (150, 140, 190)
    d.rounded_rectangle((wx0 - 14, wy0 - 14, wx1 + 14, wy1 + 14), 18, fill=frame_c)
    sky = vgrad(wx1 - wx0, wy1 - wy0, [(0, (120, 190, 245)), (1, (214, 236, 252))] if not night else [(0, (18, 20, 60)), (1, (70, 60, 120))])
    sd = ImageDraw.Draw(sky)
    if night:
        stars(sd, rng, 40, (0, 0, wx1 - wx0, wy1 - wy0))
        sd.ellipse((150, 40, 214, 104), fill=(255, 246, 214))
        sd.ellipse((168, 36, 232, 100), fill=(30, 26, 76))
    else:
        cloud(sd, 70, 100, 0.8)
        cloud(sd, 170, 200, 0.6)
        sd.ellipse((170, 30, 224, 84), fill=(255, 226, 120))
    im.alpha_composite(sky, (wx0, wy0))
    d = ImageDraw.Draw(im)
    d.line((wx0, (wy0 + wy1) // 2, wx1, (wy0 + wy1) // 2), fill=frame_c, width=8)
    d.line(((wx0 + wx1) // 2, wy0, (wx0 + wx1) // 2, wy1), fill=frame_c, width=8)
    # curtains
    cc = (242, 150, 160) if not night else (150, 90, 130)
    d.polygon([(wx0 - 30, wy0 - 24), (wx0 + 40, wy0 - 24), (wx0 + 24, wy1 + 30), (wx0 - 30, wy1 + 30)], fill=cc)
    d.polygon([(wx1 + 30, wy0 - 24), (wx1 - 40, wy0 - 24), (wx1 - 24, wy1 + 30), (wx1 + 30, wy1 + 30)], fill=cc)
    d.rounded_rectangle((wx0 - 44, wy0 - 34, wx1 + 44, wy0 - 18), 8, fill=(120, 90, 80))
    # shelf (right) with books + plant
    sx0, sy = 940, 250
    d.rounded_rectangle((sx0, sy, sx0 + 300, sy + 14), 6, fill=(150, 108, 84))
    bx = sx0 + 16
    for col in ((226, 110, 120), (120, 170, 220), (244, 200, 100), (140, 200, 150), (180, 140, 220), (240, 150, 100)):
        bw, bh = rng.randint(22, 34), rng.randint(60, 96)
        d.rounded_rectangle((bx, sy - bh, bx + bw, sy), 4, fill=col)
        bx += bw + 4
    d.ellipse((sx0 + 232, sy - 70, sx0 + 290, sy - 14), fill=(110, 186, 120))
    d.ellipse((sx0 + 222, sy - 50, sx0 + 268, sy - 4), fill=(96, 170, 108))
    d.rounded_rectangle((sx0 + 238, sy - 20, sx0 + 282, sy), 6, fill=(226, 140, 110))
    # picture frames
    for fx, fy, fw, fh, col in ((620, 110, 120, 90, (255, 214, 170)), (770, 140, 70, 70, (186, 214, 246))):
        d.rounded_rectangle((fx - 8, fy - 8, fx + fw + 8, fy + fh + 8), 8, fill=(150, 108, 84))
        d.rounded_rectangle((fx, fy, fx + fw, fy + fh), 4, fill=col)
        d.polygon([(fx + 10, fy + fh - 10), (fx + fw * 0.4, fy + fh * 0.4), (fx + fw * 0.6, fy + fh - 10)], fill=(255, 255, 255, 120))
    # floor
    if night:
        floor_planks(im, GROUND, (112, 80, 92), (84, 58, 78), (70, 46, 64))
    else:
        floor_planks(im, GROUND, (222, 178, 138), (200, 150, 112), (184, 138, 100))
    # rug
    rug = Image.new("RGBA", (W, H), (0, 0, 0, 0)); rd = ImageDraw.Draw(rug)
    rd.ellipse((90, GROUND - 6, 560, GROUND + 100), fill=(236, 120, 130, 210) if not night else (170, 96, 140, 230))
    rd.ellipse((130, GROUND + 4, 520, GROUND + 90), outline=(255, 235, 220, 200), width=4)
    im.alpha_composite(rug)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((1150, GROUND - 70, 1210, GROUND + 2), 10, fill=(214, 128, 100))
    for ang in range(-70, 71, 28):
        a = math.radians(ang)
        d.polygon([(1180, GROUND - 64), (1180 + math.sin(a) * 90 - 14, GROUND - 64 - math.cos(a) * 90), (1180 + math.sin(a) * 90 + 14, GROUND - 64 - math.cos(a) * 90 + 6)], fill=(104, 176, 116))
    if night:
        im.alpha_composite(glow(W, H, 1050, 420, 420, (255, 190, 120), 0.35))
        d = ImageDraw.Draw(im)
        d.rectangle((1080, 340, 1086, 566), fill=(90, 70, 70))
        d.polygon([(1048, 340), (1118, 340), (1100, 296), (1066, 296)], fill=(255, 214, 150))
    return im


def night_city():
    rng = random.Random(21)
    im = vgrad(W, H, [(0, (10, 14, 44)), (0.55, (44, 40, 98)), (0.82, (110, 76, 130)), (1, (60, 40, 90))])
    d = ImageDraw.Draw(im)
    stars(d, rng, 160, (0, 0, W, 360))
    im.alpha_composite(glow(W, H, 1000, 150, 300, (255, 240, 200), 0.35))
    d = ImageDraw.Draw(im)
    d.ellipse((940, 90, 1060, 210), fill=(255, 246, 216))
    for cx, cy, r in ((968, 128, 12), (1018, 170, 18), (996, 118, 7)):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(238, 228, 196))
    skyline(im, rng, GROUND - 20, (34, 30, 74), 110, 260, 60, 120, (255, 220, 140))
    skyline(im, rng, GROUND, (22, 20, 56), 70, 170, 70, 140, (255, 200, 120))
    g = vgrad(W, H - GROUND, [(0, (40, 34, 78)), (1, (26, 22, 56))])
    im.alpha_composite(g, (0, GROUND))
    d = ImageDraw.Draw(im)
    d.rectangle((0, GROUND, W, GROUND + 6), fill=(70, 60, 120))
    for x in range(0, W, 160):
        d.rounded_rectangle((x + 20, GROUND + 70, x + 100, GROUND + 78), 3, fill=(120, 110, 170))
    for x in (60, 1210):
        d.rectangle((x - 3, GROUND - 190, x + 3, GROUND), fill=(60, 56, 96))
        d.ellipse((x - 14, GROUND - 206, x + 14, GROUND - 178), fill=(255, 224, 150))
        im.alpha_composite(glow(W, H, x, GROUND - 192, 140, (255, 214, 130), 0.5))
        d = ImageDraw.Draw(im)
    return im


def sunrise():
    rng = random.Random(31)
    im = vgrad(W, H, [(0, (112, 104, 196)), (0.35, (236, 140, 168)), (0.62, (255, 190, 140)), (1, (255, 226, 170))])
    im.alpha_composite(glow(W, H, 880, 450, 520, (255, 236, 170), 0.9))
    d = ImageDraw.Draw(im)
    d.ellipse((810, 380, 950, 520), fill=(255, 244, 196))
    for x, y, s in ((200, 140, 1.0), (640, 90, 0.7), (1000, 200, 0.9)):
        cloud(d, x, y, s, (255, 226, 226, 200))
    for bx, by in ((420, 230), (460, 210), (500, 236)):
        d.arc((bx, by, bx + 30, by + 18), 200, 340, fill=(90, 70, 110), width=3)
        d.arc((bx + 24, by, bx + 54, by + 18), 200, 340, fill=(90, 70, 110), width=3)
    hills(im, rng, 520, (200, 120, 150), 70, 6, 0.4)
    hills(im, rng, 560, (130, 96, 150), 60, 7, 1.7)
    hills(im, rng, GROUND + 8, (92, 110, 130), 36, 8, 2.9)
    g = vgrad(W, H - GROUND, [(0, (118, 150, 120)), (1, (84, 120, 100))])
    im.alpha_composite(g, (0, GROUND))
    d = ImageDraw.Draw(im)
    for _ in range(40):
        x, y = rng.randint(0, W), rng.randint(GROUND + 10, H - 6)
        d.line((x, y, x + rng.randint(-3, 3), y - rng.randint(8, 18)), fill=(150, 190, 140), width=3)
    return im


def mind():
    rng = random.Random(41)
    im = vgrad(W, H, [(0, (40, 34, 108)), (0.6, (66, 90, 170)), (1, (60, 160, 190))])
    for _ in range(9):
        cx, cy, r = rng.randint(0, W), rng.randint(0, 520), rng.randint(120, 260)
        col = rng.choice([(180, 130, 255), (110, 200, 255), (255, 150, 200), (130, 240, 210)])
        im.alpha_composite(glow(W, H, cx, cy, r, col, 0.32))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 80):
        d.line((x, 0, x, GROUND), fill=(255, 255, 255, 16), width=1)
    for y in range(0, GROUND, 80):
        d.line((0, y, W, y), fill=(255, 255, 255, 16), width=1)
    for _ in range(26):
        x, y, s = rng.randint(20, W - 20), rng.randint(20, GROUND - 120), rng.randint(14, 46)
        kind = rng.choice(["ring", "dot", "tri", "plus"])
        col = (255, 255, 255, rng.randint(50, 120))
        if kind == "ring":
            d.ellipse((x - s, y - s, x + s, y + s), outline=col, width=3)
        elif kind == "dot":
            d.ellipse((x - s / 3, y - s / 3, x + s / 3, y + s / 3), fill=col)
        elif kind == "tri":
            d.polygon([(x, y - s), (x + s, y + s * 0.7), (x - s, y + s * 0.7)], outline=col, width=3)
        else:
            d.line((x - s / 2, y, x + s / 2, y), fill=col, width=4); d.line((x, y - s / 2, x, y + s / 2), fill=col, width=4)
    g = vgrad(W, H - GROUND, [(0, (120, 140, 214)), (1, (70, 80, 160))])
    im.alpha_composite(g, (0, GROUND))
    d = ImageDraw.Draw(im)
    d.rectangle((0, GROUND, W, GROUND + 4), fill=(200, 210, 255))
    for i in range(6):
        d.line((W // 2 + (i - 2.5) * 40, GROUND + 4, W // 2 + (i - 2.5) * 260, H), fill=(255, 255, 255, 40), width=2)
    return im


def city_day():
    rng = random.Random(51)
    im = vgrad(W, H, [(0, (126, 190, 246)), (1, (226, 242, 252))])
    d = ImageDraw.Draw(im)
    d.ellipse((1020, 70, 1110, 160), fill=(255, 232, 140))
    im.alpha_composite(glow(W, H, 1065, 115, 200, (255, 236, 160), 0.5))
    d = ImageDraw.Draw(im)
    for x, y, s in ((120, 120, 1.0), (520, 70, 0.8), (800, 180, 1.1)):
        cloud(d, x, y, s)
    skyline(im, rng, GROUND - 30, (170, 196, 232), 140, 300, 70, 130, (230, 244, 255))
    skyline(im, rng, GROUND, (130, 160, 214), 90, 220, 80, 150, (214, 232, 252))
    g = vgrad(W, H - GROUND, [(0, (118, 124, 142)), (1, (92, 98, 118))])
    im.alpha_composite(g, (0, GROUND))
    d = ImageDraw.Draw(im)
    d.rectangle((0, GROUND, W, GROUND + 12), fill=(196, 200, 212))
    for x in range(0, W, 150):
        d.rounded_rectangle((x + 20, GROUND + 82, x + 110, GROUND + 92), 4, fill=(250, 232, 130))
    return im


def nature():
    rng = random.Random(61)
    im = vgrad(W, H, [(0, (132, 202, 248)), (1, (230, 246, 252))])
    d = ImageDraw.Draw(im)
    d.ellipse((140, 70, 230, 160), fill=(255, 234, 140))
    im.alpha_composite(glow(W, H, 185, 115, 220, (255, 240, 170), 0.5))
    d = ImageDraw.Draw(im)
    for x, y, s in ((420, 120, 1.0), (860, 80, 0.9), (1100, 190, 0.7)):
        cloud(d, x, y, s)
    hills(im, rng, 470, (166, 214, 160), 80, 5, 0.7)
    hills(im, rng, 530, (120, 186, 132), 60, 6, 2.1)
    d = ImageDraw.Draw(im)
    for x in (80, 300, 560, 880, 1150):
        tree(d, x + rng.randint(-20, 20), GROUND - 10, rng.randint(150, 230))
    g = vgrad(W, H - GROUND, [(0, (110, 188, 112)), (1, (78, 150, 96))])
    im.alpha_composite(g, (0, GROUND))
    d = ImageDraw.Draw(im)
    for _ in range(46):
        x, y = rng.randint(0, W), rng.randint(GROUND + 12, H - 8)
        c = rng.choice([(255, 150, 170), (255, 226, 120), (255, 255, 255), (190, 160, 255)])
        d.line((x, y, x, y + 12), fill=(70, 130, 80), width=2)
        d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=c)
    return im


# -------------------------------------------------------------- school / story themes
def _desk(d, x, y, s=1.0, paper=False):
    """A student desk with a chair, seen from the front. (x, y) = bottom centre."""
    w, h = 150 * s, 62 * s
    d.rounded_rectangle((x - w * .36, y - h * 1.55, x + w * .36, y - h * .6), 10 * s, fill=(112, 150, 190))       # chair back
    d.rectangle((x - w * .30, y - h * .62, x + w * .30, y - h * .02), fill=(96, 132, 170))
    d.rounded_rectangle((x - w / 2, y - h * 1.08, x + w / 2, y - h * .86), 8 * s, fill=(226, 184, 132))           # table top
    d.rectangle((x - w * .44, y - h * .86, x - w * .40, y), fill=(150, 150, 164))
    d.rectangle((x + w * .40, y - h * .86, x + w * .44, y), fill=(150, 150, 164))
    if paper:
        d.polygon([(x - 26 * s, y - h * 1.07), (x + 28 * s, y - h * 1.07), (x + 36 * s, y - h * 1.2), (x - 18 * s, y - h * 1.2)], fill=(255, 255, 255))
        d.line((x - 12 * s, y - h * 1.14, x + 20 * s, y - h * 1.14), fill=(150, 160, 190), width=2)


def classroom(exam=False):
    rng = random.Random(71 if exam else 70)
    wall = [(0, (206, 214, 228)), (1, (190, 200, 218))] if exam else [(0, (255, 246, 218)), (1, (246, 230, 196))]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.alpha_composite(vgrad(W, GROUND, wall), (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, GROUND - 34, W, GROUND), fill=(255, 255, 255, 50))                      # skirting
    # window (right)
    wx0, wy0, wx1, wy1 = 1010, 96, 1230, 340
    d.rounded_rectangle((wx0 - 12, wy0 - 12, wx1 + 12, wy1 + 12), 14, fill=(255, 255, 255))
    sky = vgrad(wx1 - wx0, wy1 - wy0, [(0, (120, 190, 245) if not exam else (150, 170, 196)), (1, (214, 236, 252) if not exam else (200, 210, 224))])
    cloud(ImageDraw.Draw(sky), 60, 90, 0.7)
    im.alpha_composite(sky, (wx0, wy0)); d = ImageDraw.Draw(im)
    d.line((wx0, (wy0 + wy1) // 2, wx1, (wy0 + wy1) // 2), fill=(255, 255, 255), width=8)
    d.line(((wx0 + wx1) // 2, wy0, (wx0 + wx1) // 2, wy1), fill=(255, 255, 255), width=8)
    # chalkboard
    bx0, by0, bx1, by1 = 250, 84, 940, 346
    d.rounded_rectangle((bx0 - 16, by0 - 16, bx1 + 16, by1 + 16), 12, fill=(170, 124, 90))
    d.rounded_rectangle((bx0, by0, bx1, by1), 8, fill=(46, 94, 80) if not exam else (40, 70, 66))
    d.rounded_rectangle((bx0 + 30, by1 + 16, bx1 - 30, by1 + 26), 5, fill=(150, 108, 80))
    ch = (236, 240, 232, 210)
    for i, y in enumerate(range(by0 + 40, by0 + 150, 34)):                                    # scribbled lines of "writing"
        x = bx0 + 40
        while x < bx0 + rng.randint(300, 560):
            w = rng.randint(20, 70)
            d.line((x, y + rng.randint(-3, 3), x + w, y + rng.randint(-3, 3)), fill=ch, width=3)
            x += w + 16
    d.ellipse((bx1 - 220, by0 + 40, bx1 - 120, by0 + 140), outline=ch, width=4)
    d.line((bx1 - 110, by0 + 90, bx1 - 50, by0 + 60), fill=ch, width=4); d.polygon([(bx1 - 50, by0 + 60), (bx1 - 70, by0 + 58), (bx1 - 62, by0 + 76)], fill=ch)
    d.rectangle((bx0 + 60, by1 - 40, bx0 + 100, by1 - 28), fill=(255, 255, 255, 230))         # chalk dust piece
    # clock
    cx, cy = 150, 150
    d.ellipse((cx - 56, cy - 56, cx + 56, cy + 56), fill=(120, 96, 80)); d.ellipse((cx - 48, cy - 48, cx + 48, cy + 48), fill=(255, 255, 255))
    for k in range(12):
        a = math.radians(k * 30)
        d.line((cx + math.sin(a) * 38, cy - math.cos(a) * 38, cx + math.sin(a) * 44, cy - math.cos(a) * 44), fill=(70, 60, 70), width=3)
    h_ang, m_ang = (math.radians(240), math.radians(0)) if not exam else (math.radians(300), math.radians(60))
    d.line((cx, cy, cx + math.sin(h_ang) * 24, cy - math.cos(h_ang) * 24), fill=(60, 50, 60), width=5)
    d.line((cx, cy, cx + math.sin(m_ang) * 36, cy - math.cos(m_ang) * 36), fill=(60, 50, 60), width=3)
    # notice board
    d.rounded_rectangle((60, 260, 200, 380), 8, fill=(206, 160, 118))
    for (px, py, pw, ph, col) in ((74, 274, 50, 40, (255, 255, 255)), (132, 278, 56, 36, (255, 226, 150)), (80, 326, 46, 40, (190, 226, 255)), (138, 322, 50, 46, (255, 190, 200))):
        d.rectangle((px, py, px + pw, py + ph), fill=col); d.ellipse((px + pw / 2 - 3, py - 3, px + pw / 2 + 3, py + 3), fill=(220, 70, 70))
    # floor
    g = vgrad(W, H - GROUND, [(0, (206, 176, 140) if not exam else (170, 160, 150)), (1, (180, 148, 112) if not exam else (140, 130, 124))])
    im.alpha_composite(g, (0, GROUND)); d = ImageDraw.Draw(im)
    for y in range(GROUND + 26, H, 34):
        d.line((0, y, W, y), fill=(150, 118, 90, 120), width=2)
    # desks left and right (leave the middle for the characters)
    for x, y, s in ((95, GROUND + 56, 1.15), (255, GROUND + 28, 0.95), (1185, GROUND + 56, 1.15), (1025, GROUND + 28, 0.95)):
        _desk(d, x, y, s, paper=exam)
    if exam:
        im.alpha_composite(Image.new("RGBA", (W, H), (60, 80, 120, 34)))
    return im


def campus():
    rng = random.Random(81)
    im = vgrad(W, H, [(0, (118, 186, 246)), (1, (226, 242, 252))])
    d = ImageDraw.Draw(im)
    d.ellipse((1090, 60, 1170, 140), fill=(255, 232, 140)); im.alpha_composite(glow(W, H, 1130, 100, 200, (255, 236, 160), 0.45)); d = ImageDraw.Draw(im)
    for x, y, s in ((140, 110, 1.0), (520, 60, 0.7), (860, 140, 0.9)):
        cloud(d, x, y, s)
    brick, brick_d, trim = (188, 104, 88), (160, 82, 72), (250, 244, 232)
    # side wings
    for x0, x1 in ((20, 330), (950, 1260)):
        d.rectangle((x0, 330, x1, GROUND - 14), fill=brick); d.rectangle((x0 - 6, 322, x1 + 6, 336), fill=trim)
        for wx in range(x0 + 26, x1 - 40, 70):
            for wy in (356, 452):
                d.rounded_rectangle((wx, wy, wx + 38, wy + 62), 14, fill=(255, 238, 200)); d.line((wx + 19, wy, wx + 19, wy + 62), fill=brick_d, width=3)
    # main hall
    d.rectangle((330, 218, 950, GROUND - 14), fill=brick)
    d.polygon([(310, 222), (640, 118), (970, 222)], fill=trim)                                   # pediment
    d.polygon([(350, 216), (640, 130), (930, 216)], fill=(236, 226, 210))
    d.ellipse((602, 150, 678, 226), fill=(255, 255, 255), outline=(150, 120, 100), width=5)       # clock
    d.line((640, 188, 640, 160), fill=(70, 60, 70), width=4); d.line((640, 188, 662, 196), fill=(70, 60, 70), width=4)
    d.rectangle((318, 222, 962, 240), fill=trim)
    for wx in range(366, 930, 78):
        for wy in (262, 352):
            d.rounded_rectangle((wx, wy, wx + 42, wy + 70), 16, fill=(255, 238, 200)); d.line((wx + 21, wy, wx + 21, wy + 70), fill=brick_d, width=3)
    for cxp in (430, 535, 745, 850):                                                              # columns
        d.rectangle((cxp - 15, 246, cxp + 15, GROUND - 16), fill=trim); d.rectangle((cxp - 21, 242, cxp + 21, 258), fill=(236, 226, 210))
    d.rounded_rectangle((574, 380, 706, GROUND - 14), 30, fill=(110, 76, 66))                     # door
    d.line((640, 392, 640, GROUND - 14), fill=(86, 58, 52), width=3)
    for i in range(5):                                                                            # steps
        y = GROUND - 14 + i * 7
        d.rectangle((300 + i * 18, y, 980 - i * 18, y + 7), fill=(226 - i * 8, 220 - i * 8, 212 - i * 8))
    # lawn + path
    g = vgrad(W, H - GROUND, [(0, (116, 190, 114)), (1, (84, 156, 98))])
    im.alpha_composite(g, (0, GROUND + 20)); d = ImageDraw.Draw(im)
    d.rectangle((0, GROUND - 14, W, GROUND + 22), fill=(112, 186, 112))
    d.polygon([(560, GROUND + 20), (720, GROUND + 20), (900, H), (380, H)], fill=(236, 220, 188))
    for x in (60, 210, 1070, 1220):
        tree(d, x, GROUND + 14, 220 if x in (60, 1220) else 170)
    for x in (300, 980):
        d.rectangle((x - 3, GROUND - 120, x + 3, GROUND + 14), fill=(70, 70, 90)); d.ellipse((x - 14, GROUND - 138, x + 14, GROUND - 110), fill=(255, 232, 160))
    for _ in range(26):
        x, y = rng.randint(0, W), rng.randint(GROUND + 30, H - 6)
        if 380 < x < 900 and y > GROUND + 20 and abs(x - 640) < (y - GROUND) * 1.1:
            continue
        d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=rng.choice([(255, 150, 170), (255, 226, 120), (255, 255, 255)]))
    return im


def phone():
    """Group-chat world: floating chat bubbles on a night-blue gradient."""
    from .fonts import font
    rng = random.Random(91)
    im = vgrad(W, H, [(0, (26, 24, 70)), (0.6, (60, 52, 120)), (1, (96, 70, 150))])
    for _ in range(7):
        im.alpha_composite(glow(W, H, rng.randint(0, W), rng.randint(0, 520), rng.randint(160, 280), rng.choice([(120, 110, 255), (255, 130, 200), (90, 200, 255)]), 0.22))
    d = ImageDraw.Draw(im, "RGBA")
    cols = [(255, 255, 255, 46), (120, 200, 255, 120), (255, 160, 210, 120), (170, 150, 255, 120), (130, 240, 200, 110)]
    spots = [(70, 70), (360, 40), (700, 90), (1010, 52), (160, 250), (560, 210), (930, 230), (1130, 330), (60, 410), (330, 380), (800, 400), (1080, 470)]
    for i, (x, y) in enumerate(spots):
        w, h = rng.randint(150, 270), rng.randint(54, 84)
        left = i % 2 == 0
        c = cols[i % len(cols)]
        d.rounded_rectangle((x, y, x + w, y + h), h // 2 - 4, fill=c)
        tx = x + 22 if left else x + w - 22
        d.polygon([(tx, y + h - 6), (tx + (-14 if left else 14), y + h + 14), (tx + (30 if left else -30), y + h - 4)], fill=c)
        for k in range(3):
            d.ellipse((x + w / 2 - 28 + k * 28, y + h / 2 - 6, x + w / 2 - 16 + k * 28, y + h / 2 + 6), fill=(255, 255, 255, 190))
    for (x, y, n) in ((420, 130, "47"), (1180, 150, "9"), (140, 160, "3")):                       # unread badges
        d.ellipse((x - 26, y - 26, x + 26, y + 26), fill=(255, 70, 90, 235))
        f = font(26, "bold"); tw = d.textlength(n, font=f)
        d.text((x - tw / 2, y - 18), n, font=f, fill=(255, 255, 255))
    g = vgrad(W, H - GROUND, [(0, (120, 100, 190)), (1, (70, 60, 140))])
    im.alpha_composite(g, (0, GROUND)); d = ImageDraw.Draw(im)
    d.rectangle((0, GROUND, W, GROUND + 4), fill=(210, 200, 255))
    return im


def library():
    rng = random.Random(101)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.alpha_composite(vgrad(W, GROUND, [(0, (122, 86, 74)), (1, (96, 66, 62))]), (0, 0))
    d = ImageDraw.Draw(im)
    pal = [(226, 110, 120), (120, 170, 220), (244, 200, 100), (140, 200, 150), (180, 140, 220), (240, 150, 100), (90, 130, 170), (214, 214, 200)]
    for sx0, sx1 in ((20, 600), (680, 1260)):
        d.rectangle((sx0, 60, sx1, GROUND - 10), fill=(86, 58, 50))
        for sy in range(150, GROUND - 10, 128):
            x = sx0 + 10
            while x < sx1 - 30:
                bw, bh = rng.randint(18, 34), rng.randint(70, 112)
                d.rounded_rectangle((x, sy - bh, x + bw, sy), 3, fill=rng.choice(pal)); x += bw + rng.randint(1, 5)
            d.rectangle((sx0, sy, sx1, sy + 12), fill=(150, 108, 80))
    d.rectangle((600, 60, 680, GROUND - 10), fill=(70, 46, 42))
    im.alpha_composite(glow(W, H, 640, 150, 360, (255, 214, 150), 0.35)); d = ImageDraw.Draw(im)
    floor_planks(im, GROUND, (196, 150, 112), (168, 122, 92), (150, 108, 80))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((60, GROUND - 60, 360, GROUND - 38), 8, fill=(226, 184, 132)); d.rectangle((90, GROUND - 38, 100, GROUND + 30), fill=(150, 108, 80)); d.rectangle((320, GROUND - 38, 330, GROUND + 30), fill=(150, 108, 80))
    d.polygon([(150, GROUND - 62), (186, GROUND - 100), (214, GROUND - 100), (212, GROUND - 62)], fill=(255, 255, 255)); d.polygon([(214, GROUND - 100), (250, GROUND - 82), (252, GROUND - 62), (212, GROUND - 62)], fill=(240, 236, 226))
    return im


_BUILD = {
    "room_day": lambda: room(False), "room_night": lambda: room(True), "night_city": night_city, "sunrise": sunrise,
    "mind": mind, "city_day": city_day, "nature": nature,
    "classroom": lambda: classroom(False), "exam_hall": lambda: classroom(True), "campus": campus, "phone": phone, "library": library,
}


@functools.lru_cache(maxsize=24)
def theme_image(name):
    im = _BUILD.get(name, _BUILD["room_day"])()
    return im.convert("RGB")


@functools.lru_cache(maxsize=24)
def _big(name, zoom=1.07):
    im = theme_image(name)
    return im.resize((int(W * zoom), int(H * zoom)), Image.BICUBIC)


def camera(name, t, pan=14.0):
    """A slowly drifting crop of the themed background."""
    big = _big(name)
    mx, my = big.width - W, big.height - H
    ox = int(mx / 2 + math.sin(t * 0.18) * min(pan, mx / 2))
    oy = int(my / 2 + math.cos(t * 0.13) * min(pan * 0.6, my / 2))
    return big.crop((ox, oy, ox + W, oy + H))
