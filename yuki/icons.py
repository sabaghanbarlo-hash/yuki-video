"""Flat vector-style icons drawn in code (256x256 design space, 2x supersampled)."""
import functools, math, re
from PIL import Image, ImageDraw, ImageChops, ImageFilter
from .fonts import font

INK = (44, 40, 72)
WHITE = (255, 255, 255)
YEL, YEL_D = (255, 205, 70), (240, 160, 40)
RED, RED_D = (244, 90, 96), (200, 56, 70)
PINK = (255, 150, 180)
GREEN, GREEN_D = (92, 200, 128), (60, 156, 96)
BLUE, BLUE_D = (92, 156, 255), (60, 108, 214)
VIOLET = (150, 118, 255)
TEAL = (52, 196, 184)
ORANGE = (255, 150, 60)
GREY, GREY_L = (150, 156, 180), (214, 218, 232)
S = 2


class Dr:
    def __init__(self, im):
        self.im, self.d = im, ImageDraw.Draw(im)

    def p(self, *v):
        return [int(round(x * S)) for x in v]

    def ell(self, x0, y0, x1, y1, fill=None, ow=0, oc=INK):
        self.d.ellipse(self.p(x0, y0, x1, y1), fill=fill, outline=oc if ow else None, width=ow * S)

    def rr(self, x0, y0, x1, y1, r, fill=None, ow=0, oc=INK):
        self.d.rounded_rectangle(self.p(x0, y0, x1, y1), radius=r * S, fill=fill, outline=oc if ow else None, width=ow * S)

    def poly(self, pts, fill=None, ow=0, oc=INK):
        flat = [tuple(self.p(*q)) for q in pts]
        self.d.polygon(flat, fill=fill)
        if ow:
            self.d.line(flat + [flat[0]], fill=oc, width=ow * S, joint="curve")

    def line(self, pts, w=8, fill=INK, round_=True):
        flat = [tuple(self.p(*q)) for q in pts]
        self.d.line(flat, fill=fill, width=w * S, joint="curve")
        if round_:
            r = w * S / 2
            for x, y in (flat[0], flat[-1]):
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def arc(self, box, a0, a1, w=8, fill=INK):
        self.d.arc(self.p(*box), a0, a1, fill=fill, width=w * S)

    def text(self, xy, s, size, fill=INK, weight="bold"):
        self.d.text(self.p(*xy), s, font=font(size * S, weight), fill=fill, anchor="mm")


def _bulb(g, im):
    for a in range(-60, 61, 30):
        r = math.radians(a - 90)
        g.line([(128 + math.cos(r) * 92, 92 + math.sin(r) * 92), (128 + math.cos(r) * 114, 92 + math.sin(r) * 114)], 9, YEL_D)
    g.ell(62, 28, 194, 160, YEL, 7)
    g.poly([(98, 142), (158, 142), (150, 190), (106, 190)], YEL, 7)
    g.rr(100, 190, 156, 208, 7, GREY_L, 7)
    g.rr(108, 208, 148, 226, 8, GREY, 7)
    g.arc((84, 48, 140, 104), 200, 260, 8, WHITE)
    g.line([(112, 150), (122, 112), (134, 128), (144, 112), (152, 150)], 6, ORANGE)


def _brain(g, im):
    left = [(88, 70, 40), (58, 112, 38), (92, 150, 42), (62, 176, 28), (120, 104, 34)]
    right = [(168, 70, 40), (198, 112, 38), (164, 150, 42), (194, 176, 28), (136, 104, 34)]
    for cx, cy, r in left + right:
        g.ell(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4, INK)
    g.rr(112, 170, 144, 232, 12, INK)
    for cx, cy, r in left:
        g.ell(cx - r, cy - r, cx + r, cy + r, PINK)
    for cx, cy, r in right:
        g.ell(cx - r, cy - r, cx + r, cy + r, (255, 130, 168))
    g.rr(116, 172, 140, 228, 9, (255, 190, 206))
    g.line([(128, 66), (128, 176)], 6, INK)
    for box, a0, a1 in (((54, 72, 104, 118), 200, 320), ((66, 124, 112, 170), 20, 160), ((150, 72, 202, 118), 220, 340), ((144, 124, 190, 170), 20, 160)):
        g.arc(box, a0, a1, 6, INK)


def _clock(g, im):
    g.ell(24, 24, 232, 232, WHITE, 10)
    for i in range(12):
        a = math.radians(i * 30)
        r0, r1 = (88, 104) if i % 3 == 0 else (96, 104)
        g.line([(128 + math.sin(a) * r0, 128 - math.cos(a) * r0), (128 + math.sin(a) * r1, 128 - math.cos(a) * r1)], 6, INK)
    g.line([(128, 128), (128, 66)], 10, INK)
    g.line([(128, 128), (176, 150)], 10, RED_D)
    g.ell(116, 116, 140, 140, INK)


def _calendar(g, im):
    g.rr(32, 46, 224, 226, 26, WHITE, 8)
    g.rr(32, 46, 224, 108, 26, RED, 8)
    g.d.rectangle(g.p(36, 84, 220, 108), fill=RED)
    for x in (80, 176):
        g.rr(x - 8, 28, x + 8, 66, 8, GREY_L, 6)
    for r in range(3):
        for c in range(4):
            x, y = 62 + c * 44, 128 + r * 32
            g.rr(x, y, x + 28, y + 20, 6, (230, 234, 248) if (r, c) != (1, 2) else YEL)


def _target(g, im):
    g.ell(24, 40, 216, 232, RED, 8)
    g.ell(62, 78, 178, 194, WHITE, 6)
    g.ell(98, 114, 142, 158, RED, 6)
    g.line([(130, 140), (214, 56)], 10, INK)
    g.poly([(214, 56), (190, 60), (210, 80)], YEL, 5)


def _moon(g, im):
    layer = Image.new("L", im.size, 0)
    ImageDraw.Draw(layer).ellipse(g.p(40, 32, 212, 204), fill=255)
    cut = Image.new("L", im.size, 0)
    ImageDraw.Draw(cut).ellipse(g.p(96, 8, 250, 162), fill=255)
    mask = ImageChops.subtract(layer, cut)
    im.paste(Image.new("RGBA", im.size, YEL + (255,)), (0, 0), mask)
    edge = mask.filter(ImageFilter.MaxFilter(9))
    ring = ImageChops.subtract(edge, mask)
    im.paste(Image.new("RGBA", im.size, INK + (255,)), (0, 0), ring)
    for x, y, r in ((196, 70, 9), (176, 196, 6), (222, 140, 5)):
        g.poly([(x, y - r * 1.6), (x + r * .5, y - r * .5), (x + r * 1.6, y), (x + r * .5, y + r * .5), (x, y + r * 1.6), (x - r * .5, y + r * .5), (x - r * 1.6, y), (x - r * .5, y - r * .5)], YEL, 3)


def _phone(g, im):
    g.rr(70, 14, 186, 242, 26, (60, 64, 96), 8)
    g.rr(82, 40, 174, 214, 10, (130, 204, 255), 0)
    g.rr(94, 56, 162, 84, 8, WHITE)
    g.rr(94, 94, 162, 122, 8, WHITE)
    g.rr(94, 132, 162, 160, 8, WHITE)
    for x, y in ((166, 54), (166, 92), (166, 130)):
        g.ell(x - 14, y - 14, x + 14, y + 14, RED, 5, WHITE)
    g.rr(112, 22, 144, 30, 4, (30, 32, 56))


def _book(g, im):
    g.poly([(24, 64), (124, 82), (124, 214), (24, 196)], WHITE, 8)
    g.poly([(232, 64), (132, 82), (132, 214), (232, 196)], (244, 246, 255), 8)
    g.poly([(14, 190), (124, 212), (132, 212), (242, 190), (242, 206), (132, 232), (124, 232), (14, 206)], BLUE, 8)
    for i in range(4):
        g.line([(44, 100 + i * 24), (104, 108 + i * 24)], 5, GREY_L)
        g.line([(152, 108 + i * 24), (212, 100 + i * 24)], 5, GREY_L)
    g.poly([(176, 70), (200, 66), (200, 108), (188, 98), (176, 108)], RED, 5)


def _heart(g, im):
    g.ell(28, 46, 134, 152, RED)
    g.ell(122, 46, 228, 152, RED)
    g.poly([(32, 118), (224, 118), (128, 226)], RED)
    g.line([(34, 112), (128, 222), (222, 112)], 8, INK, False)
    g.arc((28, 46, 134, 152), 150, 360, 8, INK)
    g.arc((122, 46, 228, 152), 180, 390, 8, INK)
    g.arc((52, 66, 92, 106), 190, 260, 8, WHITE)


def _battery(g, im, level=1):
    g.rr(16, 74, 214, 182, 20, WHITE, 8)
    g.rr(214, 106, 240, 150, 8, INK)
    col = GREEN if level >= 3 else (YEL_D if level == 2 else RED)
    for i in range(level):
        x = 32 + i * 44
        g.rr(x, 90, x + 36, 166, 8, col)


def _battery_low(g, im):
    _battery(g, im, 1)


def _battery_full(g, im):
    _battery(g, im, 4)


def _chart(g, im):
    g.line([(30, 30), (30, 220), (230, 220)], 9, INK)
    for i, (h, c) in enumerate(((50, BLUE), (96, TEAL), (150, GREEN))):
        x = 56 + i * 56
        g.rr(x, 214 - h, x + 40, 214, 6, c, 6)
    g.line([(52, 140), (110, 104), (150, 118), (210, 52)], 9, RED_D)
    g.poly([(224, 38), (196, 50), (218, 72)], RED_D)


def _coin(g, im):
    g.ell(28, 28, 228, 228, YEL, 9)
    g.ell(54, 54, 202, 202, YEL_D, 0)
    g.ell(54, 54, 202, 202, None, 5, (255, 226, 150))
    g.text((128, 132), "$", 118, WHITE)


def _fire(g, im):
    g.poly([(128, 16), (170, 78), (206, 120), (208, 170), (176, 220), (128, 238), (80, 220), (48, 170), (52, 120), (86, 90), (96, 120), (108, 60)], ORANGE, 8)
    g.poly([(128, 110), (156, 150), (166, 188), (146, 218), (110, 218), (90, 188), (100, 150)], YEL, 0)


def _check(g, im):
    g.ell(24, 24, 232, 232, GREEN, 9)
    g.line([(72, 132), (114, 172), (188, 86)], 24, WHITE)


def _cross(g, im):
    g.ell(24, 24, 232, 232, RED, 9)
    g.line([(86, 86), (170, 170)], 24, WHITE)
    g.line([(170, 86), (86, 170)], 24, WHITE)


def _loop(g, im):
    g.arc((36, 36, 220, 220), 200, 350, 22, TEAL)
    g.poly([(206, 112), (240, 128), (200, 160)], TEAL)
    g.arc((36, 36, 220, 220), 20, 170, 22, VIOLET)
    g.poly([(50, 144), (16, 128), (56, 96)], VIOLET)


def _mountain(g, im):
    g.poly([(10, 220), (96, 70), (150, 150), (190, 100), (246, 220)], (120, 140, 190), 8)
    g.poly([(96, 70), (72, 112), (92, 104), (104, 118), (122, 104)], WHITE, 0)
    g.line([(96, 70), (96, 24)], 7, INK)
    g.poly([(96, 24), (140, 38), (96, 54)], RED, 5)


def _hourglass(g, im):
    g.rr(48, 20, 208, 44, 10, BLUE_D, 7)
    g.rr(48, 212, 208, 236, 10, BLUE_D, 7)
    g.poly([(66, 44), (190, 44), (136, 128), (190, 212), (66, 212), (120, 128)], (226, 240, 255), 7)
    g.poly([(88, 52), (168, 52), (128, 110)], YEL, 0)
    g.poly([(88, 204), (168, 204), (128, 150)], YEL, 0)


def _star(g, im):
    pts = []
    for i in range(10):
        r = 108 if i % 2 == 0 else 46
        a = math.radians(-90 + i * 36)
        pts.append((128 + math.cos(a) * r, 136 + math.sin(a) * r))
    g.poly(pts, YEL, 8)
    g.arc((78, 88, 128, 138), 190, 260, 8, WHITE)


def _question(g, im):
    g.ell(24, 24, 232, 232, BLUE, 9)
    g.text((128, 134), "?", 150, WHITE)


def _bubble(g, im):
    g.poly([(70, 170), (60, 226), (122, 176)], WHITE, 8)
    g.rr(20, 34, 236, 186, 44, WHITE, 8)
    for x in (82, 128, 174):
        g.ell(x - 14, 96, x + 14, 124, VIOLET)


def _sprout(g, im):
    g.line([(128, 224), (128, 120)], 11, GREEN_D)
    g.poly([(128, 130), (70, 112), (40, 62), (104, 66), (128, 100)], GREEN, 7)
    g.poly([(128, 112), (186, 96), (216, 40), (150, 46), (128, 80)], (130, 220, 140), 7)
    g.poly([(40, 232), (70, 196), (186, 196), (216, 232)], (150, 104, 80), 7)


def _sleep(g, im):
    _moon(g, im)
    for (x, y, s) in ((176, 150, 56), (206, 98, 40)):
        g.text((x, y), "Z", s, VIOLET)


def _lightning(g, im):
    g.poly([(150, 12), (60, 140), (118, 140), (92, 244), (200, 100), (140, 100), (170, 12)], YEL, 8)


def _lock(g, im):
    g.arc((70, 28, 186, 150), 180, 360, 20, GREY)
    g.line([(80, 90), (80, 112)], 20, GREY, False)
    g.line([(176, 90), (176, 112)], 20, GREY, False)
    g.rr(44, 106, 212, 226, 24, YEL, 8)
    g.ell(114, 140, 142, 168, INK)
    g.rr(122, 160, 134, 196, 5, INK)


def _sun(g, im):
    for i in range(12):
        a = math.radians(i * 30)
        g.line([(128 + math.cos(a) * 82, 128 + math.sin(a) * 82), (128 + math.cos(a) * 114, 128 + math.sin(a) * 114)], 11, YEL_D)
    g.ell(56, 56, 200, 200, YEL, 8)
    g.arc((78, 78, 150, 150), 195, 255, 8, WHITE)


def _trophy(g, im):
    g.arc((20, 40, 90, 120), 100, 270, 12, YEL_D)
    g.arc((166, 40, 236, 120), 270, 80, 12, YEL_D)
    g.poly([(62, 28), (194, 28), (180, 120), (150, 150), (106, 150), (76, 120)], YEL, 8)
    g.rr(116, 150, 140, 190, 4, YEL_D, 6)
    g.rr(76, 190, 180, 224, 10, YEL_D, 7)
    g.poly([(128, 52), (136, 76), (160, 76), (140, 90), (148, 114), (128, 100), (108, 114), (116, 90), (96, 76), (120, 76)], WHITE, 0)


_ICONS = {
    "bulb": _bulb, "brain": _brain, "clock": _clock, "calendar": _calendar, "target": _target, "moon": _moon,
    "phone": _phone, "book": _book, "heart": _heart, "battery_low": _battery_low, "battery": _battery_full,
    "chart": _chart, "coin": _coin, "fire": _fire, "check": _check, "cross": _cross, "loop": _loop,
    "mountain": _mountain, "hourglass": _hourglass, "star": _star, "question": _question, "bubble": _bubble,
    "sprout": _sprout, "sleep": _sleep, "lightning": _lightning, "lock": _lock, "sun": _sun, "trophy": _trophy,
}

ICON_KEYS = {
    "bulb": "idea ideas insight realize realization clarity understand creative discover answer solution",
    "brain": "brain mind think thinking thought thoughts mental overthink overthinking focus memory psychology",
    "clock": "time minutes minute hour hours seconds deadline late schedule routine early",
    "calendar": "day days week weeks monday tuesday wednesday thursday friday saturday sunday month months year daily tomorrow today yesterday",
    "target": "goal goals target aim plan plans purpose direction priority priorities ambition",
    "sleep": "sleep tired rest exhausted bed insomnia dream asleep nap sleepy",
    "moon": "night midnight dark evening",
    "phone": "phone scroll scrolling social notifications instagram tiktok youtube screen app apps distraction distractions",
    "book": "book books read reading learn learning study lesson knowledge school",
    "heart": "love heart care kind kindness feel feelings emotion emotions compassion friend friends loved",
    "battery_low": "energy drained burnout burned fatigue depleted empty",
    "chart": "progress growth improve improvement results increase grow better compound level",
    "coin": "money pay paid cost expensive income rich budget price salary",
    "fire": "motivation motivated passion drive excited burning streak momentum",
    "check": "done finish finished complete completed success win habit habits consistent consistency achieve",
    "cross": "fail failure failed mistake mistakes wrong stop quit never problem broken",
    "loop": "cycle loop again repeat restart starting stuck pattern patterns over reset",
    "mountain": "climb mountain journey challenge hard difficult obstacle summit path struggle",
    "hourglass": "wait waiting patience slow delay procrastinate procrastination later",
    "star": "best special great amazing future shine perfect",
    "question": "why how what question questions wonder confused doubt ask",
    "bubble": "talk say said tell words voice conversation speak comment criticism opinion opinions",
    "sprout": "seed small tiny begin beginning plant slowly step steps baby little",
    "lightning": "fast quick instant power strong strength boost spark sudden",
    "lock": "trap trapped locked control limit limits boundaries safe",
    "sun": "happy joy bright hope sunrise positive morning",
    "trophy": "winner champion victory reward achievement trophy proud",
}


@functools.lru_cache(maxsize=128)
def icon(name, size=200):
    f = _ICONS.get(name, _star)
    N = 256 * S
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    f(Dr(im), im)
    return im.resize((size, size), Image.LANCZOS)


def pick_icon(text, avoid=()):
    """Choose the icon whose keywords best match the text; returns None if nothing matches."""
    toks = re.findall(r"[a-z][a-z'-]*", text.lower())
    best, score = None, 0
    for name, words in ICON_KEYS.items():
        ws = set(words.split())
        sc = sum(1 for t in toks if t in ws or t.rstrip("s") in ws)
        if name in avoid:
            sc -= 0.5
        if sc > score:
            best, score = name, sc
    return best
