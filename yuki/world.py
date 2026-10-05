"""Backgrounds ("worlds"). Each theme is drawn in code at 1280x720 with the floor line at y=GROUND."""
import functools, math, random
import numpy as np
from PIL import Image, ImageDraw

W, H = 1280, 720
GROUND = 588

THEMES = ["room_day", "room_night", "night_city", "sunrise", "mind", "city_day", "nature"]


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


_BUILD = {
    "room_day": lambda: room(False), "room_night": lambda: room(True), "night_city": night_city, "sunrise": sunrise,
    "mind": mind, "city_day": city_day, "nature": nature,
}


@functools.lru_cache(maxsize=16)
def theme_image(name):
    im = _BUILD.get(name, _BUILD["room_day"])()
    return im.convert("RGB")


@functools.lru_cache(maxsize=16)
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
