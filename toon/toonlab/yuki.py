"""Yuki (and every other person) in the thick-ink cartoon look: big squircle head, bold outline, flat colours, glossy dot eyes,
big expressive mouth that follows the voice, stubby tube arms with mitten hands.

Figure space: origin = centre of the head. Head is 300 wide; neck at y=120; torso to y=300; legs to y=450.
Everything is stateless: the picture depends only on the arguments (so frames can be rendered in any order, in parallel).
"""
import math
from dataclasses import dataclass, field, replace
import skia
from .gfx import (C, INK, fill_paint, line_paint, poly_path, smooth_closed, smooth_open, outlined, outlined_oval, tube, shade, mix,
                  squircle_pts, ease_io, back_out, lerp)

OW = 4.6          # outline width (units)
MOUTH_IN = (96, 28, 44)
TONGUE = (240, 112, 128)


@dataclass(frozen=True)
class Look:
    name: str = "Yuki"
    hair: tuple = (54, 48, 74)
    hair_hi: tuple = (130, 138, 184)
    style: str = "bob"                 # bob | spiky | curly | long | short
    skin: tuple = (255, 226, 205)
    blush: tuple = (250, 140, 150)
    top: tuple = (112, 172, 116)       # hoodie
    scarf: tuple = (224, 62, 72)       # None = no scarf
    bottom: tuple = (74, 68, 96)       # skirt / trousers
    legs: tuple = (40, 36, 52)
    shoes: tuple = (44, 40, 56)
    skirt: bool = True
    glasses: bool = False
    hood: bool = True
    eye: tuple = (44, 30, 44)


YUKI = Look()
CAST = {
    "yuki": YUKI,
    "boy": Look("Boy", hair=(52, 40, 36), hair_hi=(110, 90, 80), style="spiky", top=(232, 150, 70), scarf=None, bottom=(84, 104, 150), legs=(84, 104, 150), skirt=False, hood=False),
    "girl": Look("Girl", hair=(170, 100, 60), hair_hi=(230, 170, 110), style="long", top=(184, 150, 230), scarf=None, bottom=(60, 60, 90), skirt=True, hood=False),
    "curly": Look("Curly", hair=(110, 70, 48), hair_hi=(170, 120, 90), style="curly", top=(236, 224, 120), scarf=None, bottom=(70, 76, 110), legs=(70, 76, 110), skirt=False, hood=False),
    "boss": Look("Boss", hair=(60, 60, 70), hair_hi=(130, 130, 150), style="short", skin=(244, 208, 180), top=(70, 90, 140), scarf=None, bottom=(54, 58, 84), legs=(54, 58, 84), skirt=False, glasses=True, hood=False),
    "teen": Look("Teen", hair=(30, 28, 40), hair_hi=(150, 90, 200), style="spiky", top=(60, 56, 74), scarf=None, bottom=(50, 50, 64), legs=(50, 50, 64), skirt=False, hood=False),
    "grandma": Look("Gran", hair=(220, 220, 230), hair_hi=(255, 255, 255), style="curly", skin=(248, 214, 190), top=(214, 130, 160), scarf=None, bottom=(110, 90, 130), skirt=True, glasses=True, hood=False),
}

# ------------------------------------------------------------------ faces
#  eye: open | wide | happy | closed | squint | sparkle | half | tear | small
#  brow: (lift, angle) per side, positive lift = up, positive angle = inner end DOWN (angry)
#  mouth (closed state): smile | smile_s | flat | frown | wavy | smirk | pout | o
FACES = {
    "neutral":   dict(eye="open", brow=(0, 0), mouth="smile_s", blush=0.25, wide=1.0),
    "smile":     dict(eye="open", brow=(2, 0), mouth="smile", blush=0.4, wide=1.0),
    "happy":     dict(eye="happy", brow=(4, 0), mouth="smile", blush=0.6, wide=1.1),
    "excited":   dict(eye="sparkle", brow=(10, -4), mouth="smile", blush=0.7, wide=1.25),
    "laughing":  dict(eye="happy", brow=(8, -3), mouth="smile", blush=0.7, wide=1.3, teeth=True),
    "starry":    dict(eye="sparkle", brow=(8, 0), mouth="smile", blush=0.8, wide=1.1),
    "proud":     dict(eye="happy", brow=(6, 3), mouth="smirk", blush=0.5, wide=1.0),
    "smug":      dict(eye="half", brow=(2, 7, 9, 0), mouth="smirk", blush=0.2, wide=1.0),
    "scheming":  dict(eye="half", brow=(0, 14), mouth="smirk", blush=0.1, wide=1.0),
    "deadpan":   dict(eye="half", brow=(-2, 0), mouth="flat", blush=0.0, wide=0.8),
    "bored":     dict(eye="half", brow=(-4, -3), mouth="flat", blush=0.0, wide=0.8),
    "sleepy":    dict(eye="closed", brow=(-3, -4), mouth="o", blush=0.3, wide=0.8),
    "curious":   dict(eye="open", brow=(12, -6, 0, 6), mouth="smile_s", blush=0.3, wide=0.95),
    "confused":  dict(eye="open", brow=(10, -8, -2, 8), mouth="wavy", blush=0.2, wide=0.9),
    "worried":   dict(eye="open", brow=(8, -14), mouth="wavy", blush=0.2, wide=0.9),
    "nervous":   dict(eye="small", brow=(8, -14), mouth="wavy", blush=0.3, wide=0.9, fx="sweat"),
    "embarrassed": dict(eye="small", brow=(6, -10), mouth="wavy", blush=1.0, wide=0.9, fx="sweat"),
    "sad":       dict(eye="open", brow=(6, -16), mouth="frown", blush=0.1, wide=0.85),
    "crying":    dict(eye="tear", brow=(8, -18), mouth="frown", blush=0.5, wide=1.0, fx="tears"),
    "shocked":   dict(eye="wide", brow=(18, 0), mouth="o", blush=0.0, wide=1.0, fx="gasp"),
    "gasp":      dict(eye="wide", brow=(18, 0), mouth="o", blush=0.0, wide=1.0),
    "terrified": dict(eye="wide", brow=(14, -10), mouth="wavy", blush=0.0, wide=1.0, fx="sweat"),
    "angry":     dict(eye="squint", brow=(-4, 20), mouth="frown", blush=0.1, wide=1.0, fx="anger"),
    "grumpy":    dict(eye="half", brow=(-3, 12), mouth="frown", blush=0.0, wide=0.9),
    "determined": dict(eye="open", brow=(-2, 12), mouth="smile_s", blush=0.2, wide=1.0),
    "lovestruck": dict(eye="sparkle", brow=(6, 0), mouth="smile", blush=1.0, wide=1.0, fx="hearts"),
    "pained":    dict(eye="closed", brow=(6, -14), mouth="wavy", blush=0.1, wide=0.9),
    "serene":    dict(eye="closed", brow=(3, 0), mouth="smile_s", blush=0.4, wide=0.9),
}
FACE_ALIASES = {"joy": "happy", "wonder": "starry", "awe": "starry", "worry": "worried", "fear": "terrified", "surprised": "shocked",
                "annoyed": "grumpy", "calm": "serene", "thinking": "curious", "love": "lovestruck", "tired": "sleepy", "funny": "laughing"}


def face_def(name):
    return FACES.get(FACE_ALIASES.get(name, name), FACES["neutral"])


# ------------------------------------------------------------------ arm poses  (upper-arm angle, forearm angle) per side; 0 = down, 90 = out sideways, 180 = up, negative = across the body
POSES = {
    "rest":    dict(L=(10, 6, "mitt"), R=(10, 6, "mitt")),
    "relax":   dict(L=(14, 10, "mitt"), R=(14, 10, "mitt")),
    "talk_a":  dict(L=(10, 6, "mitt"), R=(62, 150, "open")),
    "talk_b":  dict(L=(62, 150, "open"), R=(12, 8, "mitt")),
    "present": dict(L=(14, 8, "mitt"), R=(70, 100, "open")),
    "present2": dict(L=(70, 100, "open"), R=(70, 100, "open")),
    "point_r": dict(L=(10, 6, "mitt"), R=(98, 98, "point")),
    "point_l": dict(L=(98, 98, "point"), R=(10, 6, "mitt")),
    "shrug":   dict(L=(52, 148, "open"), R=(52, 148, "open")),
    "hips":    dict(L=(44, -42, "mitt"), R=(44, -42, "mitt")),
    "cross":   dict(L=(24, -88, "mitt"), R=(24, -88, "mitt")),
    "cheer":   dict(L=(96, 126, "open"), R=(96, 126, "open")),
    "wave":    dict(L=(10, 6, "mitt"), R=(92, 122, "open")),
    "idea":    dict(L=(10, 6, "mitt"), R=(140, 176, "point")),
    "think":   dict(L=(12, 8, "mitt"), R=(38, 138, "point")),
    "slump":   dict(L=(2, 0, "mitt"), R=(2, 0, "mitt")),
    "fist":    dict(L=(10, 6, "mitt"), R=(66, 140, "fist")),
    "thumbs":  dict(L=(10, 6, "mitt"), R=(70, 150, "thumb")),
    "stop":    dict(L=(10, 6, "mitt"), R=(84, 170, "open")),
    "hands_up": dict(L=(94, 128, "open"), R=(94, 128, "open")),
    "hug":     dict(L=(30, -110, "mitt"), R=(30, -110, "mitt")),
}
POSE_ALIASES = {"facepalm": "slump", "head": "think", "head_l": "think", "think_l": "think", "sob": "slump", "gasp_hands": "hands_up", "shy": "hug",
                "heart": "hug", "dance": "cheer", "clap": "present2", "talk": "talk_a", "pen": "think", "magnify": "point_r", "wave_both": "cheer", "bow": "slump", "shake": "stop"}


def pose_def(name):
    return POSES.get(POSE_ALIASES.get(name, name), POSES["rest"])


@dataclass
class State:
    face: str = "neutral"
    vis: int = 0                  # mouth shape from the voice: 0 closed 1 eh 2 ah 3 small 4 ee 5 oo
    amp: float = 0.0              # loudness 0..1
    blink: int = 0                # 0 open 1 half 2 closed
    gx: float = 0.0               # gaze -1..1
    gy: float = 0.0
    tilt: float = 0.0             # head tilt degrees
    pose: str = "rest"
    prev: str = "rest"
    blend: float = 1.0            # 0..1 progress from prev to pose
    t: float = 0.0
    sx: float = 1.0               # squash & stretch
    sy: float = 1.0
    flip: bool = False
    parts: str = "full"           # head | bust | torso | full
    walk: float = 0.0             # walking phase (0 = standing)
    wiggle: float = 1.0           # gesture energy
    beat: float = 0.0             # 0..1 emphasis pulse
    prof: float = 0.0             # -1..1 head turns a little (features slide)
    sleeve_up: bool = False


# ------------------------------------------------------------------ head
HEAD_RX, HEAD_RY = 150, 134


def head_path():
    return smooth_closed(squircle_pts(0, 0, HEAD_RX, HEAD_RY, n=2.65, steps=28), 1.0)


def _hair_back(cv, lk, st):
    c, hi = lk.hair, lk.hair_hi
    s = lk.style
    if s == "bob":
        pts = [(-164, -10), (-160, -104), (-102, -162), (0, -178), (102, -162), (160, -104), (164, -10), (166, 70), (146, 116), (100, 124), (0, 112), (-100, 124), (-146, 116), (-166, 70)]
        outlined(cv, smooth_closed(pts, 0.9), c, OW)
    elif s == "long":
        pts = [(-174, -10), (-166, -104), (-104, -166), (0, -186), (104, -166), (166, -104), (174, -10), (186, 120), (176, 250), (130, 262), (0, 240), (-130, 262), (-176, 250), (-186, 120)]
        outlined(cv, smooth_closed(pts, 0.9), c, OW)
    elif s == "curly":
        for i in range(-4, 5):
            a = math.pi * (0.5 + i * 0.19)
            outlined_circle(cv, math.cos(a + math.pi) * 150 * 1.0 * (1 if True else 1), -math.sin(a) * 128 - 10, 52, c)
        for sx in (-1, 1):
            outlined_circle(cv, sx * 150, 20, 46, c)
            outlined_circle(cv, sx * 150, 70, 38, c)
    elif s == "short":
        pts = [(-158, -10), (-156, -100), (-100, -156), (0, -170), (100, -156), (156, -100), (158, -10), (152, 40), (-152, 40)]
        outlined(cv, smooth_closed(pts, 0.9), c, OW)
    # spiky: no back hair


def outlined_circle(cv, x, y, r, col):
    outlined_oval(cv, x, y, r, r, col, OW)


def _fringe(cv, lk, st):
    c, hi = lk.hair, lk.hair_hi
    s = lk.style
    if s == "bob":
        top = [(-152, -20), (-150, -98), (-100, -148), (0, -166), (100, -148), (150, -98), (152, -20)]
        side_r = [(158, 40), (148, 80), (134, 80), (132, 20)]
        fringe = [(112, -14), (98, -50), (72, -28), (56, -64), (22, -34), (-6, -66), (-38, -34), (-70, -62), (-92, -30), (-118, -50), (-114, -14)]
        side_l = [(-132, 20), (-134, 80), (-148, 80), (-158, 40)]
        pts = top + side_r + fringe + side_l
        p = smooth_closed(pts, 0.55)
        outlined(cv, p, c, OW)
        cv.save()
        cv.clipPath(p, skia.ClipOp.kIntersect, True)
        cv.drawPath(smooth_open([(-110, -120), (-50, -148), (20, -150), (70, -138)], 0.9), line_paint(hi, 16, 200))
        cv.restore()
        cv.drawPath(p, line_paint(INK, OW))
    elif s == "long":
        top = [(-154, -20), (-150, -100), (-100, -150), (0, -170), (100, -150), (150, -100), (154, -20)]
        pts = top + [(150, 60), (132, 70), (118, -6), (60, -40), (-20, -52), (-120, -10), (-132, 70), (-150, 60)]
        p = smooth_closed(pts, 0.55)
        outlined(cv, p, c, OW)
        cv.save()
        cv.clipPath(p, skia.ClipOp.kIntersect, True)
        cv.drawPath(smooth_open([(-110, -122), (-40, -150), (40, -146)], 0.9), line_paint(hi, 15, 200))
        cv.restore()
        cv.drawPath(p, line_paint(INK, OW))
    elif s == "spiky":
        pts = [(-152, -20), (-158, -90), (-130, -150), (-112, -204), (-70, -158), (-40, -222), (-4, -166), (38, -230), (60, -164), (104, -214), (116, -148), (160, -184), (150, -92), (154, -20),
               (130, -30), (112, -78), (60, -62), (18, -92), (-30, -60), (-70, -88), (-118, -64), (-132, -30)]
        p = poly_path(pts)
        outlined(cv, p, c, OW)
        cv.save()
        cv.clipPath(p, skia.ClipOp.kIntersect, True)
        cv.drawPath(smooth_open([(-110, -140), (-40, -176), (30, -180)], 0.9), line_paint(hi, 13, 200))
        cv.restore()
    elif s == "curly":
        for i in range(-3, 4):
            outlined_circle(cv, i * 40, -112 + abs(i) * 8 - (14 if i % 2 == 0 else 0), 46, c)
        outlined_circle(cv, -128, -52, 36, c)
        outlined_circle(cv, 128, -52, 36, c)
    elif s == "short":
        pts = [(-152, -20), (-150, -100), (-100, -150), (0, -166), (100, -150), (150, -100), (152, -20), (126, -50), (60, -86), (-20, -62), (-80, -66), (-128, -40)]
        p = smooth_closed(pts, 0.5)
        outlined(cv, p, c, OW)
        cv.save()
        cv.clipPath(p, skia.ClipOp.kIntersect, True)
        cv.drawPath(smooth_open([(-110, -122), (-40, -150), (40, -146)], 0.9), line_paint(hi, 14, 200))
        cv.restore()
        cv.drawPath(p, line_paint(INK, OW))


def _eyes(cv, lk, st, fd, gx, gy):
    kind = fd["eye"]
    if st.blink == 2 and kind not in ("happy", "closed"):
        kind = "closed"
    elif st.blink == 1 and kind in ("open", "wide", "sparkle", "tear", "small"):
        kind = "half"
    ey = 14
    for sx in (-1, 1):
        ex = sx * 64 + gx * 7
        y = ey + gy * 5
        if kind in ("open", "tear", "sparkle", "wide", "small"):
            rx, ry = {"open": (19, 28), "tear": (20, 29), "sparkle": (22, 31), "wide": (23, 34), "small": (14, 18)}[kind]
            cv.drawOval(skia.Rect.MakeLTRB(ex - rx, y - ry, ex + rx, y + ry), fill_paint(lk.eye))
            cv.drawOval(skia.Rect.MakeLTRB(ex - rx, y - ry, ex + rx, y + ry), line_paint(INK, 3))
            # glossy highlights
            hx, hy = ex + rx * 0.28 + gx * 2, y - ry * 0.34
            cv.drawCircle(hx, hy, rx * 0.40, fill_paint((255, 255, 255)))
            cv.drawCircle(ex - rx * 0.32, y + ry * 0.38, rx * 0.2, fill_paint((255, 255, 255), 230))
            if kind == "sparkle":
                cv.drawCircle(ex + rx * 0.05, y + ry * 0.05, rx * 0.16, fill_paint((255, 255, 255), 230))
            if kind == "tear":
                cv.drawOval(skia.Rect.MakeLTRB(ex - rx, y + ry - 6, ex + rx, y + ry + 12), fill_paint((150, 205, 250), 230))
        elif kind == "half":
            rx, ry = 19, 28
            cv.save()
            cv.clipRect(skia.Rect.MakeLTRB(ex - 30, y - 3 + 0, ex + 30, y + 40))
            cv.drawOval(skia.Rect.MakeLTRB(ex - rx, y - ry, ex + rx, y + ry), fill_paint(lk.eye))
            cv.drawCircle(ex + 4, y + 8, 4.5, fill_paint((255, 255, 255)))
            cv.restore()
            cv.drawPath(smooth_open([(ex - 22, y - 3), (ex, y - 5), (ex + 22, y - 3)], 0.5), line_paint(INK, 6))
        elif kind == "squint":
            cv.drawPath(smooth_open([(ex - sx * 20, y - 14 * 0 - 4), (ex, y + 6), (ex + sx * 20, y + 14)], 0.5), line_paint(INK, 7))
            cv.drawOval(skia.Rect.MakeLTRB(ex - 12, y - 2, ex + 12, y + 16), fill_paint(lk.eye))
        elif kind == "happy":
            cv.drawPath(smooth_open([(ex - 20, y + 10), (ex, y - 10), (ex + 20, y + 10)], 0.9), line_paint(INK, 7))
        else:  # closed (content / sleepy): a downward arc
            cv.drawPath(smooth_open([(ex - 20, y - 2), (ex, y + 10), (ex + 20, y - 2)], 0.9), line_paint(INK, 6.5))
        if lk.glasses:
            r = 36
            cv.drawCircle(ex, y, r, fill_paint((255, 255, 255), 40))
            cv.drawCircle(ex, y, r, line_paint(INK, 4.5))
    if lk.glasses:
        cv.drawLine(-26 + gx * 7, 10, 26 + gx * 7, 10, line_paint(INK, 4.5))


def _brows(cv, lk, st, fd, gx):
    b = fd["brow"]
    if len(b) == 2:
        b = (b[0], b[1], b[0], b[1])
    lift_l, ang_l, lift_r, ang_r = b
    lift_l += st.beat * 4
    lift_r += st.beat * 4
    for sx, lift, ang in ((-1, lift_l, ang_l), (1, lift_r, ang_r)):
        cx, cy = sx * 64 + gx * 6, -26 - lift
        a = math.radians(ang)
        dx = 22
        # inner end is toward the face centre
        inner = (cx - sx * dx * math.cos(a), cy + dx * math.sin(a))
        outer = (cx + sx * dx * math.cos(a), cy - dx * math.sin(a))
        mid = ((inner[0] + outer[0]) / 2, (inner[1] + outer[1]) / 2 - 5)
        cv.drawPath(smooth_open([inner, mid, outer], 0.8), line_paint(lk.hair if lk.style != "long" else INK, 8.5))
        cv.drawPath(smooth_open([inner, mid, outer], 0.8), line_paint(INK, 7))


def _mouth(cv, lk, st, fd):
    cx, cy = 0, 82
    w = fd.get("wide", 1.0)
    vis = st.vis if st.amp > 0.04 or st.vis else 0
    amp = max(0.0, min(1.0, st.amp))
    open_ = vis > 0 and amp > 0.05
    if not open_:
        m = fd["mouth"]
        lw = 5.2
        if m == "smile_s":
            cv.drawPath(smooth_open([(-20 * w, cy - 4), (0, cy + 6), (20 * w, cy - 4)], 0.9), line_paint(INK, lw))
        elif m == "smile":
            p = smooth_closed([(-34 * w, cy - 6), (0, cy + 14), (34 * w, cy - 6), (0, cy - 2)], 0.8)
            cv.drawPath(p, fill_paint(MOUTH_IN))
            cv.drawPath(p, line_paint(INK, lw))
            if fd.get("teeth"):
                pass
        elif m == "flat":
            cv.drawLine(-15 * w, cy + 2, 15 * w, cy + 2, line_paint(INK, lw))
        elif m == "frown":
            cv.drawPath(smooth_open([(-24, cy + 10), (0, cy - 4), (24, cy + 10)], 0.9), line_paint(INK, lw))
        elif m == "wavy":
            cv.drawPath(smooth_open([(-26, cy + 2), (-13, cy - 5), (0, cy + 5), (13, cy - 5), (26, cy + 2)], 0.8), line_paint(INK, lw))
        elif m == "smirk":
            cv.drawPath(smooth_open([(-18, cy + 4), (6, cy + 6), (28, cy - 8)], 0.8), line_paint(INK, lw))
        elif m == "pout":
            outlined_oval(cv, 0, cy + 2, 11, 8, MOUTH_IN, 4)
        elif m == "o":
            outlined_oval(cv, 0, cy + 4, 13, 16, MOUTH_IN, 4.2)
        return
    # talking mouth: width/height per viseme, scaled by loudness, bent by the feeling
    shapes = {1: (52, 34), 2: (68, 54), 3: (38, 26), 4: (76, 26), 5: (34, 38)}
    mw, mh = shapes.get(vis, (46, 30))
    mw *= w * (0.82 + 0.28 * amp)
    mh *= 0.45 + 0.75 * amp
    mood = fd["mouth"]
    droop = 5 if mood in ("frown", "wavy") else (-2 if mood in ("smile", "smirk") else 0)
    p = skia.Path()
    p.moveTo(-mw / 2, cy - mh * 0.25)
    p.quadTo(0, cy - mh * 0.55 + droop * 0.4, mw / 2, cy - mh * 0.25)
    p.cubicTo(mw * 0.5, cy + mh * 0.95, -mw * 0.5, cy + mh * 0.95, -mw / 2, cy - mh * 0.25)
    p.close()
    cv.drawPath(p, fill_paint(MOUTH_IN))
    cv.save()
    cv.clipPath(p, skia.ClipOp.kIntersect, True)
    cv.drawOval(skia.Rect.MakeLTRB(-mw * 0.34, cy + mh * 0.18, mw * 0.34, cy + mh * 1.25), fill_paint(TONGUE))
    if vis == 4 or fd.get("teeth"):
        cv.drawRect(skia.Rect.MakeLTRB(-mw / 2, cy - mh * 0.6, mw / 2, cy - mh * 0.02), fill_paint((255, 255, 255)))
    cv.restore()
    cv.drawPath(p, line_paint(INK, 5))


def _fx(cv, lk, st, fd):
    fx = fd.get("fx")
    if fx == "sweat":
        d = skia.Path()
        x, y = 132, -40 + (st.t * 12 % 20)
        d.moveTo(x, y - 24)
        d.cubicTo(x + 16, y - 2, x + 16, y + 16, x, y + 16)
        d.cubicTo(x - 16, y + 16, x - 16, y - 2, x, y - 24)
        outlined(cv, d, (170, 220, 255), 3.6)
    elif fx == "tears":
        for sx in (-1, 1):
            x = sx * 82
            cv.drawPath(smooth_open([(x, 50), (x + sx * 8, 80), (x + sx * 4, 118)], 0.8), line_paint((140, 200, 250), 12, 230))
    elif fx == "anger":
        x, y = 112, -112
        for dx, dy, ang in ((0, 0, 0), (0, 0, 90)):
            a = math.radians(ang)
            p = smooth_open([(x - 16 * math.cos(a) - 2, y - 16 * math.sin(a)), (x, y), (x + 16 * math.cos(a) + 2, y + 16 * math.sin(a))], 0.6)
        for ang in (45, 135, 225, 315):
            a = math.radians(ang)
            pa = skia.Path()
            pa.moveTo(x + 4 * math.cos(a), y + 4 * math.sin(a))
            pa.quadTo(x + 12 * math.cos(a + 0.7), y + 12 * math.sin(a + 0.7), x + 22 * math.cos(a), y + 22 * math.sin(a))
            cv.drawPath(pa, line_paint((220, 50, 56), 7))
    elif fx == "hearts":
        for i, (hx, hy) in enumerate(((-128, -150), (140, -120), (112, -180))):
            hy -= (st.t * 14 + i * 9) % 24
            _heart(cv, hx, hy, 18 - i * 2)
    elif fx == "gasp":
        for ang in (-60, -30, 0, 30, 60):
            a = math.radians(ang - 90)
            cv.drawLine(math.cos(a) * 176, math.sin(a) * 160 - 8, math.cos(a) * 204, math.sin(a) * 186 - 8, line_paint(INK, 5))


def _heart(cv, x, y, r, col=(240, 80, 110)):
    p = skia.Path()
    p.moveTo(x, y + r)
    p.cubicTo(x - r * 1.6, y - r * 0.2, x - r * 0.7, y - r * 1.3, x, y - r * 0.4)
    p.cubicTo(x + r * 0.7, y - r * 1.3, x + r * 1.6, y - r * 0.2, x, y + r)
    p.close()
    outlined(cv, p, col, 3.5)


def draw_head(cv, lk, st):
    fd = face_def(st.face)
    gx, gy = st.gx + st.prof * 0.8, st.gy
    cv.save()
    cv.translate(0, 120)                  # pivot at the neck
    cv.rotate(st.tilt)
    cv.translate(0, -120)
    _hair_back(cv, lk, st)
    hp = head_path()
    cv.save()
    cv.translate(st.prof * 8, 0)
    outlined(cv, hp, lk.skin, OW + 0.6)
    # ears (small bumps) only when hair doesn't hide them
    # blush
    b = fd.get("blush", 0.3)
    if b > 0.02:
        for sx in (-1, 1):
            cv.drawOval(skia.Rect.MakeLTRB(sx * 98 - 26, 44 - 14, sx * 98 + 26, 44 + 14), fill_paint(lk.blush, int(190 * min(1, b))))
    cv.save()
    cv.translate(st.prof * 14, 0)
    _eyes(cv, lk, st, fd, gx, gy)
    _mouth(cv, lk, st, fd)
    cv.restore()
    cv.restore()
    _fringe(cv, lk, st)
    cv.save()
    cv.translate(st.prof * 14, 0)
    _brows(cv, lk, st, fd, gx)
    cv.restore()
    _fx(cv, lk, st, fd)
    cv.restore()


# ------------------------------------------------------------------ body
TORSO_TOP, TORSO_BOT = 112, 300
SHOULDER = {-1: (-86, 150), 1: (86, 150)}
UPPER, FORE, ARM_W = 78, 72, 44


def _dir(side, deg):
    a = math.radians(deg)
    return (side * math.sin(a), math.cos(a))


def arm_pts(side, a1, a2):
    sx, sy = SHOULDER[side]
    d1, d2 = _dir(side, a1), _dir(side, a2)
    el = (sx + d1[0] * UPPER, sy + d1[1] * UPPER)
    wr = (el[0] + d2[0] * FORE, el[1] + d2[1] * FORE)
    return (sx, sy), el, wr, d2


def _hand(cv, lk, kind, wr, d, side):
    x, y = wr
    r = 27
    cv.save()
    cv.translate(x + d[0] * 6, y + d[1] * 6)
    ang = math.degrees(math.atan2(d[0], -d[1]))        # rotate so "up" of the hand follows the forearm
    cv.rotate(ang)
    sk = lk.skin
    if kind == "point":
        tube(cv, [(0, 0), (0, -44)], 15, sk, 3.8)
        outlined_oval(cv, 0, 0, r, r * 0.95, sk, 4)
        outlined_oval(cv, -side * 22, 6, 11, 14, sk, 3.8)
    elif kind == "open":
        for i, dx in enumerate((-17, -6, 6, 17)):
            tube(cv, [(dx, -8), (dx + (i - 1.5) * 2, -34 + abs(i - 1.5) * 4)], 11, sk, 3.4)
        outlined_oval(cv, 0, 4, r + 2, r, sk, 4)
        outlined_oval(cv, -side * 25, 10, 12, 15, sk, 3.8)
    elif kind == "fist":
        outlined_oval(cv, 0, 0, r + 1, r, sk, 4)
        for dx in (-9, 0, 9):
            cv.drawLine(dx, -r + 6, dx, -r + 18, line_paint(INK, 3))
    elif kind == "thumb":
        outlined_oval(cv, 0, 0, r, r * 0.95, sk, 4)
        tube(cv, [(side * 4, -8), (side * 4, -40)], 15, sk, 3.8)
    else:
        outlined_oval(cv, 0, 0, r, r * 0.95, sk, 4)
        outlined_oval(cv, -side * 22, 6, 10.5, 14, sk, 3.8)
    cv.restore()


def _arm(cv, lk, st, side, wiggle):
    cur, prv = pose_def(st.pose), pose_def(st.prev)
    key = "L" if side == -1 else "R"
    a1c, a2c, hk = cur[key]
    a1p, a2p, _ = prv[key]
    k = back_out(st.blend, 1.3) if st.blend < 1 else 1.0
    a1, a2 = lerp(a1p, a1c, k), lerp(a2p, a2c, k)
    w = math.sin(st.t * 7.5 + (2 if side < 0 else 0)) * 5 * wiggle
    idle = math.sin(st.t * 1.7 + side) * 2.5
    a2 += w + idle + st.beat * 12 * (1 if a2c > 60 else 0)
    a1 += idle * 0.5
    sh, el, wr, d2 = arm_pts(side, a1, a2)
    tube(cv, [sh, el, wr], ARM_W, lk.top if lk.hood or True else lk.top, 4.4)
    # cuff
    _hand(cv, lk, hk, wr, d2, side)


def draw_body(cv, lk, st):
    sway = math.sin(st.t * 1.6) * 3
    breath = math.sin(st.t * 2.2) * 2.2
    walk = st.walk
    if st.parts == "full":
        # legs
        for sx in (-1, 1):
            ph = math.sin(walk * 2 * math.pi + (0 if sx < 0 else math.pi)) if walk else 0
            fx = sx * 44 + ph * 26
            lift = max(0, math.cos(walk * 2 * math.pi + (0 if sx < 0 else math.pi))) * 16 if walk else 0
            tube(cv, [(sx * 40, 318), (fx, 428 - lift)], 34, lk.legs, 4.4)
            outlined_oval(cv, fx + 8 * (1 if not st.flip else 1), 442 - lift, 38, 20, lk.shoes, 4.4)
    # hood behind the neck
    if lk.hood:
        hp = smooth_closed([(-112, 90), (-130, 150), (-96, 196), (0, 206), (96, 196), (130, 150), (112, 90)], 0.8)
        outlined(cv, hp, shade(lk.top, -0.22), OW)
    # torso (hoodie)
    tp = smooth_closed([(-92, TORSO_TOP + 6), (-100, 150), (-112, 250), (-104, TORSO_BOT), (0, TORSO_BOT + 8 + breath), (104, TORSO_BOT), (112, 250), (100, 150), (92, TORSO_TOP + 6), (0, TORSO_TOP - 4)], 0.7)
    outlined(cv, tp, lk.top, OW)
    cv.save()
    cv.clipPath(tp, skia.ClipOp.kIntersect, True)
    cv.drawRect(skia.Rect.MakeLTRB(-130, 262, 130, 330), fill_paint(shade(lk.top, -0.14)))
    cv.restore()
    cv.drawPath(tp, line_paint(INK, OW))
    if lk.hood:   # pocket + strings
        cv.drawPath(smooth_open([(-52, 238), (-44, 270), (44, 270), (52, 238)], 0.6), line_paint(INK, 3.6))
        for sx in (-1, 1):
            cv.drawLine(sx * 26, 140, sx * 30, 190, line_paint(INK, 3.2))
            cv.drawCircle(sx * 30, 194, 4.5, fill_paint((250, 245, 235)))
    if lk.skirt and st.parts == "full":
        sp = smooth_closed([(-100, 292), (-124, 350), (0, 362), (124, 350), (100, 292), (0, 286)], 0.7)
        outlined(cv, sp, lk.bottom, OW)
    elif st.parts == "full":
        pass


def draw_scarf(cv, lk, st):
    if not lk.scarf:
        return
    sc = lk.scarf
    sw = math.sin(st.t * 2.4) * 8 + st.walk * 0
    # tail first (behind the loop)
    tail = smooth_closed([(52, 142), (92, 158 + sw * 0.3), (110 + sw, 232), (104 + sw * 1.4, 300), (76 + sw * 1.4, 306), (78 + sw, 240), (54, 188)], 0.6)
    outlined(cv, tail, shade(sc, -0.08), OW)
    loop = smooth_closed([(-118, 112), (-100, 156), (-40, 176), (30, 176), (100, 156), (118, 112), (60, 128), (0, 134), (-60, 128)], 0.65)
    outlined(cv, loop, sc, OW)
    cv.drawPath(smooth_open([(-84, 146), (-30, 160), (30, 160), (86, 146)], 0.8), line_paint(shade(sc, -0.25), 4, 220))
    knot = smooth_closed([(36, 128), (74, 132), (84, 170), (46, 184), (28, 156)], 0.6)
    outlined(cv, knot, shade(sc, -0.06), OW)


def draw_character(cv, lk, x, y, scale, st):
    """x, y = screen position of the HEAD CENTRE. scale = screen px per unit."""
    cv.save()
    cv.translate(x, y)
    cv.scale(scale * st.sx * (-1 if st.flip else 1), scale * st.sy)
    bob = math.sin(st.t * 2.2) * 2.0
    cv.translate(0, bob)
    if st.parts in ("full", "torso", "bust"):
        draw_body(cv, lk, st)
        draw_scarf(cv, lk, st)
    draw_head(cv, lk, st)
    if st.parts in ("full", "torso", "bust"):
        wig = st.wiggle * (0.35 + st.amp * 1.1)
        for side in (-1, 1):
            _arm(cv, lk, st, side, wig)
    cv.restore()


# ====================================================================== v2 redesign
# Cleaner bob with swept fringe, big glossy eyes, sleeves with ribbed cuffs, and properly built hands.
_old_hair_back, _old_fringe, _old_eyes = _hair_back, _fringe, _eyes


def head_path():
    return smooth_closed(squircle_pts(0, 6, HEAD_RX - 2, HEAD_RY, n=2.35, steps=40), 1.0)


def _pt_path(start, segs, close=True):
    p = skia.Path()
    p.moveTo(*start)
    for s in segs:
        if len(s) == 6:
            p.cubicTo(*s)
        else:
            p.quadTo(*s)
    if close:
        p.close()
    return p


def _mirror(seg):
    return tuple(-v if i % 2 == 0 else v for i, v in enumerate(seg))


def _hair_back(cv, lk, st):
    if lk.style != "bob":
        return _old_hair_back(cv, lk, st)
    col = shade(lk.hair, -0.2)
    p = skia.Path()
    p.moveTo(-156, -26)
    p.cubicTo(-182, 30, -178, 92, -150, 120)
    p.quadTo(-100, 130, -60, 112)
    p.quadTo(0, 98, 60, 112)
    p.quadTo(100, 130, 150, 120)
    p.cubicTo(178, 92, 182, 30, 156, -26)
    p.close()
    outlined(cv, p, col, OW)


def _fringe(cv, lk, st):
    if lk.style != "bob":
        return _old_fringe(cv, lk, st)
    c, hi = lk.hair, lk.hair_hi
    p = skia.Path()
    p.moveTo(-154, -22)
    p.cubicTo(-176, -134, -84, -182, 0, -180)               # dome
    p.cubicTo(84, -182, 176, -134, 154, -22)
    p.cubicTo(164, 20, 162, 64, 146, 96)                       # right side lock down to its tip
    p.quadTo(132, 56, 126, 0)                                  # back up along the cheek
    p.quadTo(126, -30, 108, -46)                               # swept fringe, right -> left, leaf-shaped clumps
    p.quadTo(100, -70, 80, -80)
    p.quadTo(74, -50, 56, -42)
    p.quadTo(58, -72, 34, -86)
    p.quadTo(26, -52, 4, -44)
    p.quadTo(8, -74, -18, -88)
    p.quadTo(-32, -54, -54, -46)
    p.quadTo(-52, -72, -80, -84)
    p.quadTo(-96, -52, -116, -40)
    p.quadTo(-124, -20, -126, 0)
    p.quadTo(-132, 56, -146, 96)                               # left lock tip
    p.cubicTo(-162, 64, -164, 20, -154, -22)
    p.close()
    outlined(cv, p, c, OW)
    cv.save()
    cv.clipPath(p, skia.ClipOp.kIntersect, True)
    cv.drawPath(smooth_open([(-104, -128), (-50, -156), (30, -158), (88, -140)], 0.9), line_paint(hi, 13, 190))
    cv.drawCircle(104, -118, 5, fill_paint(hi, 170))
    for x0, y0, x1, y1 in ((-60, -150, -54, -104), (10, -160, 8, -112), (70, -150, 64, -106)):
        cv.drawPath(smooth_open([(x0, y0), ((x0 + x1) / 2 - 3, (y0 + y1) / 2), (x1, y1)], 0.8), line_paint(shade(c, -0.25), 3, 160))
    cv.restore()
    cv.drawPath(p, line_paint(INK, OW))
    # ahoge: one cute loose strand (a curved leaf shape)
    a = skia.Path()
    a.moveTo(-4, -174)
    a.quadTo(8, -214, 48, -214)
    a.quadTo(26, -198, 22, -172)
    a.close()
    outlined(cv, a, c, OW - 0.6)


def _eyes(cv, lk, st, fd, gx, gy):
    kind = fd["eye"]
    if kind not in ("open", "tear", "sparkle", "wide", "small") or (st.blink and st.blink > 0):
        return _old_eyes(cv, lk, st, fd, gx, gy)
    ey = 16
    for sx in (-1, 1):
        ex = sx * 62 + gx * 7
        y = ey + gy * 5
        rx, ry = {"open": (23, 31), "tear": (24, 32), "sparkle": (26, 34), "wide": (27, 37), "small": (17, 21)}[kind]
        eye = skia.Rect.MakeLTRB(ex - rx, y - ry, ex + rx, y + ry)
        cv.drawOval(eye, fill_paint((38, 26, 50)))
        cv.save()
        cv.clipPath(skia.Path.Oval(eye), skia.ClipOp.kIntersect, True)
        # iris glow in the lower half
        cv.drawOval(skia.Rect.MakeLTRB(ex - rx * 0.86 + gx * 2, y - ry * 0.05, ex + rx * 0.86 + gx * 2, y + ry * 1.25), fill_paint((120, 84, 150), 235))
        cv.drawOval(skia.Rect.MakeLTRB(ex - rx * 0.6 + gx * 2, y + ry * 0.25, ex + rx * 0.6 + gx * 2, y + ry * 1.2), fill_paint((176, 132, 196), 200))
        cv.restore()
        cv.drawCircle(ex + rx * 0.3 + gx * 2, y - ry * 0.33, rx * 0.4, fill_paint((255, 255, 255)))
        cv.drawCircle(ex - rx * 0.34, y + ry * 0.42, rx * 0.19, fill_paint((255, 255, 255), 235))
        if kind == "sparkle":
            cv.drawCircle(ex + rx * 0.0, y + ry * 0.05, rx * 0.14, fill_paint((255, 255, 255), 230))
        if kind == "tear":
            cv.drawOval(skia.Rect.MakeLTRB(ex - rx, y + ry - 6, ex + rx, y + ry + 12), fill_paint((150, 205, 250), 230))
        # thick upper lash with a little flick at the outer corner
        lash = smooth_open([(ex - rx - 1, y + 2), (ex - rx * 0.7, y - ry * 0.78), (ex, y - ry - 2), (ex + rx * 0.7, y - ry * 0.78), (ex + rx + 1, y + 2)], 0.9)
        cv.drawPath(lash, line_paint(INK, 7.5))
        fx = ex + sx * (rx + 1)
        cv.drawLine(fx, y + 1, fx + sx * 8, y - 8, line_paint(INK, 5.5))
        if lk.glasses:
            r = 38
            cv.drawCircle(ex, y, r, fill_paint((255, 255, 255), 40))
            cv.drawCircle(ex, y, r, line_paint(INK, 4.5))
    if lk.glasses:
        cv.drawLine(-24 + gx * 7, 12, 24 + gx * 7, 12, line_paint(INK, 4.5))


# ---------------------------------------------------------------- hands
def _union(cv, parts, col, ow=4.0, creases=()):
    """Draw capsules/ovals as ONE shape: ink silhouette first, then flat fill, so no outlines show inside the hand."""
    for stage in (0, 1):
        for part in parts:
            if part[0] == "cap":
                _, a, b, w = part
                cv.drawLine(a[0], a[1], b[0], b[1], line_paint(INK if stage == 0 else col, w + (ow * 2 if stage == 0 else 0)))
            else:
                _, cx, cy, rx, ry = part
                e = ow if stage == 0 else 0
                cv.drawOval(skia.Rect.MakeLTRB(cx - rx - e, cy - ry - e, cx + rx + e, cy + ry + e), fill_paint(INK if stage == 0 else col))
    for a, b in creases:
        cv.drawPath(smooth_open([a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), b], 0.8), line_paint(shade(col, -0.45), 2.8, 235))


def _cap_from(x, y, ang_deg, length, w):
    a = math.radians(ang_deg)
    return ("cap", (x, y), (x + math.sin(a) * length, y - math.cos(a) * length), w)


def _hand(cv, lk, kind, wr, d, side):
    x, y = wr
    cv.save()
    cv.translate(x + d[0] * 24, y + d[1] * 24)
    cv.rotate(math.degrees(math.atan2(d[0], -d[1])))
    sk = lk.skin
    t = -side                                   # thumb side (toward the body)
    if kind == "open":
        fingers = [(-17, -12, -20 * 1, 33, 13), (-6, -17, -6, 40, 13.5), (6, -17, 6, 38, 13.5), (17, -12, 20, 31, 12.5)]
        parts = [("oval", 0, 0, 29, 27)]
        for fx, fy, ang, ln, w in fingers:
            parts.append(_cap_from(fx, fy, ang, ln, w))
        parts.append(_cap_from(t * 22, 6, t * 52, 28, 15))
        _union(cv, parts, sk, 4.0, creases=[((-11.5, -26), (-11, -18)), ((0, -30), (0, -20)), ((11.5, -26), (11, -18))])
    elif kind == "point":
        parts = [("oval", 0, 2, 28, 26)]
        for fx in (4, 14, 23):
            parts.append(("oval", fx, -18, 9.5, 9.5))
        parts.append(_cap_from(-9, -14, 0, 38, 13.5))              # index finger up
        parts.append(_cap_from(t * 21, 6, t * 40, 22, 14))
        _union(cv, parts, sk, 4.0, creases=[((9, -18), (9, -8)), ((19, -17), (19, -7))])
    elif kind == "fist":
        parts = [("oval", 0, 0, 29, 27)]
        for fx in (-18, -6, 6, 18):
            parts.append(("oval", fx, -19, 10.5, 10.5))
        parts.append(("cap", (t * 17, 8), (t * 3, -3), 13))
        _union(cv, parts, sk, 4.0, creases=[((-12, -22), (-12, -8)), ((0, -24), (0, -9)), ((12, -22), (12, -8))])
    elif kind == "thumb":
        parts = [("oval", 0, 2, 28, 26)]
        for fx in (-18, -6, 6, 18):
            parts.append(("oval", fx, -12, 10, 10))
        parts.append(_cap_from(t * 17, -6, t * 14, 32, 17))
        _union(cv, parts, sk, 4.0, creases=[((-12, -14), (-12, -2)), ((0, -16), (0, -3)), ((12, -14), (12, -2))])
    else:   # mitt: relaxed hand, fingers loosely curled, thumb resting beside
        parts = [("oval", 0, 0, 28, 26)]
        for fx, fy in ((-17, -17), (-6, -21), (6, -21), (17, -17)):
            parts.append(("oval", fx, fy, 9.5, 11))
        parts.append(_cap_from(t * 21, 4, t * 22, 24, 14))
        _union(cv, parts, sk, 4.0, creases=[((-11.5, -24), (-11.5, -12)), ((0, -28), (0, -14)), ((11.5, -24), (11.5, -12))])
    cv.restore()


def _arm(cv, lk, st, side, wiggle):
    cur, prv = pose_def(st.pose), pose_def(st.prev)
    key = "L" if side == -1 else "R"
    a1c, a2c, hk = cur[key]
    a1p, a2p, _ = prv[key]
    k = back_out(st.blend, 1.3) if st.blend < 1 else 1.0
    a1, a2 = lerp(a1p, a1c, k), lerp(a2p, a2c, k)
    w = math.sin(st.t * 7.5 + (2 if side < 0 else 0)) * 5 * wiggle
    idle = math.sin(st.t * 1.7 + side) * 2.5
    a2 += w + idle + st.beat * 12 * (1 if a2c > 60 else 0)
    a1 += idle * 0.5
    sh, el, wr, d2 = arm_pts(side, a1, a2)
    col = lk.top
    tube(cv, [sh, el], 50, col, 4.4)                  # upper arm (puffy hoodie sleeve)
    tube(cv, [el, wr], 42, col, 4.4)                  # forearm, a little slimmer
    cuff0 = (wr[0] - d2[0] * 14, wr[1] - d2[1] * 14)
    tube(cv, [cuff0, (wr[0] + d2[0] * 2, wr[1] + d2[1] * 2)], 45, shade(col, -0.16), 4.2)   # ribbed cuff
    _hand(cv, lk, hk, wr, d2, side)


# ====================================================================== v3: softer, more anime
OW = 3.4
LINE = (52, 36, 66)          # plum line-art instead of near-black: softer, prettier


def _grad(x0, y0, x1, y1, c0, c1, a=255):
    p = skia.Paint(AntiAlias=True)
    p.setShader(skia.GradientShader.MakeLinear([(x0, y0), (x1, y1)], [C(c0, a), C(c1, a)]))
    return p


def head_path():
    pts = [(0, -134), (92, -112), (142, -40), (146, 30), (126, 86), (78, 122), (30, 138), (0, 140),
           (-30, 138), (-78, 122), (-126, 86), (-146, 30), (-142, -40), (-92, -112)]
    return smooth_closed(pts, 1.0)


def _hair_fill(cv, lk, path):
    top = shade(lk.hair, -0.12)
    bot = mix(lk.hair, lk.hair_hi, 0.38)
    cv.drawPath(path, _grad(0, -180, 0, 100, top, bot))


def _hair_back(cv, lk, st):
    if lk.style != "bob":
        return _old_hair_back(cv, lk, st)
    p = skia.Path()
    p.moveTo(-156, -26)
    p.cubicTo(-176, 30, -174, 96, -152, 126)
    p.quadTo(-110, 140, -66, 116)
    p.quadTo(0, 100, 66, 116)
    p.quadTo(110, 140, 156, 128)
    p.cubicTo(174, 96, 176, 30, 156, -26)
    p.close()
    cv.drawPath(p, _grad(0, -20, 0, 130, shade(lk.hair, -0.25), shade(lk.hair, -0.02)))
    cv.drawPath(p, line_paint(LINE, OW))


def _fringe_path():
    p = skia.Path()
    p.moveTo(-154, -22)
    p.cubicTo(-178, -136, -84, -186, 0, -184)
    p.cubicTo(84, -186, 178, -136, 154, -22)
    p.cubicTo(166, 24, 164, 70, 150, 108)                      # right side lock, long and tapered
    p.quadTo(134, 60, 128, 0)
    p.quadTo(128, -32, 112, -50)
    p.quadTo(104, -78, 84, -88)                                # swept bangs
    p.quadTo(78, -54, 58, -46)
    p.quadTo(60, -80, 34, -94)
    p.quadTo(26, -56, 2, -46)
    p.quadTo(6, -80, -22, -96)
    p.quadTo(-36, -58, -62, -50)
    p.quadTo(-58, -78, -90, -90)
    p.quadTo(-104, -56, -122, -42)
    p.quadTo(-128, -20, -130, 0)
    p.quadTo(-136, 60, -150, 108)
    p.cubicTo(-166, 70, -168, 24, -154, -22)
    p.close()
    return p


def _fringe(cv, lk, st):
    if lk.style != "bob":
        return _old_fringe(cv, lk, st)
    c, hi = lk.hair, lk.hair_hi
    p = _fringe_path()
    _hair_fill(cv, lk, p)
    cv.save()
    cv.clipPath(p, skia.ClipOp.kIntersect, True)
    # glossy "angel ring" highlight + soft secondary shine
    ring = smooth_open([(-100, -122), (-56, -150), (14, -156), (74, -142)], 0.9)
    cv.drawPath(ring, line_paint((226, 232, 255), 9, 150))
    cv.drawPath(smooth_open([(94, -132), (116, -108)], 0.5), line_paint((226, 232, 255), 6, 110))
    # darker strand lines flowing from the crown
    for x0, y0, x1, y1 in ((-70, -170, -86, -96), (-20, -178, -28, -104), (30, -178, 38, -106), (80, -166, 100, -100)):
        cv.drawPath(smooth_open([(x0, y0), ((x0 + x1) / 2 + 6, (y0 + y1) / 2), (x1, y1)], 0.8), line_paint(shade(c, -0.35), 2.6, 60))
    cv.restore()
    cv.drawPath(p, line_paint(LINE, OW))
    a = skia.Path()
    a.moveTo(-4, -178)
    a.quadTo(10, -218, 52, -214)
    a.quadTo(28, -200, 22, -176)
    a.close()
    cv.drawPath(a, fill_paint(shade(c, -0.05)))
    cv.drawPath(a, line_paint(LINE, OW))


def _brows(cv, lk, st, fd, gx):
    b = fd["brow"]
    if len(b) == 2:
        b = (b[0], b[1], b[0], b[1])
    lift_l, ang_l, lift_r, ang_r = b
    lift_l += st.beat * 4
    lift_r += st.beat * 4
    for sx, lift, ang in ((-1, lift_l, ang_l), (1, lift_r, ang_r)):
        cx, cy = sx * 62 + gx * 6, -22 - lift
        a = math.radians(ang)
        dx = 19
        inner = (cx - sx * dx * math.cos(a), cy + dx * math.sin(a))
        outer = (cx + sx * dx * math.cos(a), cy - dx * math.sin(a))
        mid = ((inner[0] + outer[0]) / 2, (inner[1] + outer[1]) / 2 - 4)
        cv.drawPath(smooth_open([inner, mid, outer], 0.8), line_paint(shade(lk.hair, -0.1), 5.2))


def _eyes(cv, lk, st, fd, gx, gy):
    kind = fd["eye"]
    if kind not in ("open", "tear", "sparkle", "wide", "small") or (st.blink and st.blink > 0):
        return _old_eyes(cv, lk, st, fd, gx, gy)
    ey = 14
    for sx in (-1, 1):
        ex = sx * 62 + gx * 7
        y = ey + gy * 5
        rx, ry = {"open": (29, 38), "tear": (30, 39), "sparkle": (31, 41), "wide": (32, 44), "small": (20, 25)}[kind]
        eye = skia.Path.Oval(skia.Rect.MakeLTRB(ex - rx, y - ry, ex + rx, y + ry))
        cv.save()
        cv.clipPath(eye, skia.ClipOp.kIntersect, True)
        cv.drawPaint(_grad(0, y - ry, 0, y + ry, (36, 24, 72), (120, 96, 214)))
        # lower glow of the iris
        cv.drawOval(skia.Rect.MakeLTRB(ex - rx * 0.78 + gx * 2, y + ry * 0.12, ex + rx * 0.78 + gx * 2, y + ry * 1.35), fill_paint((176, 214, 255), 150))
        cv.drawOval(skia.Rect.MakeLTRB(ex - rx * 0.32 + gx * 2, y - ry * 0.22, ex + rx * 0.32 + gx * 2, y + ry * 0.38), fill_paint((24, 16, 44), 215))   # pupil
        cv.restore()
        # big window highlight + small sparkle
        cv.drawOval(skia.Rect.MakeLTRB(ex - rx * 0.62 + gx * 2, y - ry * 0.7, ex - rx * 0.02 + gx * 2, y - ry * 0.1), fill_paint((255, 255, 255)))
        cv.drawCircle(ex + rx * 0.36 + gx * 2, y + ry * 0.46, rx * 0.15, fill_paint((255, 255, 255), 240))
        cv.drawCircle(ex + rx * 0.12 + gx * 2, y + ry * 0.62, rx * 0.075, fill_paint((255, 255, 255), 220))
        if kind == "sparkle":
            cv.drawCircle(ex - rx * 0.1, y - ry * 0.02, rx * 0.12, fill_paint((255, 255, 255), 230))
        if kind == "tear":
            cv.drawOval(skia.Rect.MakeLTRB(ex - rx, y + ry - 6, ex + rx, y + ry + 12), fill_paint((170, 220, 255), 225))
        # upper lid: thick lash line with a wing, and a faint double-lid crease
        lash = smooth_open([(ex - rx - 1, y + 6), (ex - rx * 0.72, y - ry * 0.8), (ex, y - ry - 3), (ex + rx * 0.72, y - ry * 0.8), (ex + rx + 1, y + 6)], 0.9)
        cv.drawPath(lash, line_paint(LINE, 8.5))
        wing = smooth_open([(ex + sx * (rx + 1), y + 2), (ex + sx * (rx + 9), y - 6), (ex + sx * (rx + 16), y - 12)], 0.7)
        cv.drawPath(wing, line_paint(LINE, 5.2))
        cv.drawPath(smooth_open([(ex - rx * 0.7, y - ry - 8), (ex, y - ry - 14), (ex + rx * 0.7, y - ry - 8)], 0.9), line_paint(LINE, 2.4, 120))
        cv.drawPath(smooth_open([(ex - rx * 0.6, y + ry + 2), (ex, y + ry + 6), (ex + rx * 0.6, y + ry + 2)], 0.9), line_paint(LINE, 2.2, 140))
        if lk.glasses:
            r = 42
            cv.drawCircle(ex, y, r, fill_paint((255, 255, 255), 40))
            cv.drawCircle(ex, y, r, line_paint(LINE, 4.5))
    if lk.glasses:
        cv.drawLine(-24 + gx * 7, 12, 24 + gx * 7, 12, line_paint(LINE, 4.5))


def draw_head(cv, lk, st):
    fd = face_def(st.face)
    gx, gy = st.gx + st.prof * 0.8, st.gy
    cv.save()
    cv.translate(0, 120)
    cv.rotate(st.tilt)
    cv.translate(0, -120)
    _hair_back(cv, lk, st)
    hp = head_path()
    cv.save()
    cv.translate(st.prof * 8, 0)
    cv.drawPath(hp, fill_paint(lk.skin))
    cv.save()
    cv.clipPath(hp, skia.ClipOp.kIntersect, True)
    if lk.style == "bob":      # cel shadow cast by the fringe + under the chin
        cv.save()
        cv.translate(0, 9)
        cv.drawPath(_fringe_path(), fill_paint(shade(lk.skin, -0.075), 255))
        cv.restore()
    cv.restore()
    cv.drawPath(hp, line_paint(LINE, OW + 0.4))
    b = fd.get("blush", 0.3)
    if b > 0.02:
        for sx in (-1, 1):
            cx, cy = sx * 92, 74
            cv.drawOval(skia.Rect.MakeLTRB(cx - 26, cy - 13, cx + 26, cy + 13), fill_paint(lk.blush, int(150 * min(1, b))))
            for k in (-1, 0, 1):
                cv.drawLine(cx + k * 9 - 3, cy - 6, cx + k * 9 + 3, cy + 6, line_paint(shade(lk.blush, -0.15), 2.6, int(170 * min(1, b))))
    cv.save()
    cv.translate(st.prof * 14, 10)               # features sit lower on the face (anime proportions)
    _eyes(cv, lk, st, fd, gx, gy)
    cv.drawLine(2, 62, 6, 66, line_paint(shade(lk.skin, -0.4), 3.0, 200))     # tiny nose tick
    cv.restore()
    cv.save()
    cv.translate(st.prof * 14, 6)
    _mouth(cv, lk, st, fd)
    cv.restore()
    cv.restore()
    _fringe(cv, lk, st)
    cv.save()
    cv.translate(st.prof * 14, 10)
    _brows(cv, lk, st, fd, gx)
    cv.restore()
    _fx(cv, lk, st, fd)
    cv.restore()


# ---------------------------------------------------------------- simple, cute hands (no fingers needed)
def _hand(cv, lk, kind, wr, d, side):
    x, y = wr
    cv.save()
    cv.translate(x + d[0] * 22, y + d[1] * 22)
    cv.rotate(math.degrees(math.atan2(d[0], -d[1])))
    sk = lk.skin
    t = -side
    parts = [("oval", 0, 0, 28, 26)]
    if kind == "point":
        parts.append(("cap", (-8, -12), (-8, -40), 14))                    # one little pointing finger
        parts.append(("oval", t * 21, 6, 11, 14))
    elif kind == "thumb":
        parts.append(("cap", (t * 15, -8), (t * 13, -34), 16))
    elif kind == "open":
        parts = [("oval", 0, 0, 30, 28), ("oval", t * 24, 8, 12, 15)]
    elif kind == "fist":
        parts = [("oval", 0, 0, 27, 25), ("oval", t * 17, 6, 11, 12)]
    else:
        parts.append(("oval", t * 21, 7, 11, 14))
    _union(cv, parts, sk, 3.4)
    cv.restore()


def _arm(cv, lk, st, side, wiggle):
    cur, prv = pose_def(st.pose), pose_def(st.prev)
    key = "L" if side == -1 else "R"
    a1c, a2c, hk = cur[key]
    a1p, a2p, _ = prv[key]
    k = back_out(st.blend, 1.3) if st.blend < 1 else 1.0
    a1, a2 = lerp(a1p, a1c, k), lerp(a2p, a2c, k)
    w = math.sin(st.t * 7.5 + (2 if side < 0 else 0)) * 5 * wiggle
    idle = math.sin(st.t * 1.7 + side) * 2.5
    a2 += w + idle + st.beat * 12 * (1 if a2c > 60 else 0)
    a1 += idle * 0.5
    sh, el, wr, d2 = arm_pts(side, a1, a2)
    col = lk.top
    tube(cv, [sh, el], 37, col, 3.6, ink=LINE)
    tube(cv, [el, wr], 33, col, 3.6, ink=LINE)
    cuff0 = (wr[0] - d2[0] * 10, wr[1] - d2[1] * 10)
    tube(cv, [cuff0, (wr[0] + d2[0] * 2, wr[1] + d2[1] * 2)], 36, shade(col, -0.16), 3.6, ink=LINE)
    _hand(cv, lk, hk, wr, d2, side)


# ====================================================================== v4: selectable eye + hair designs
DESIGN = {"eyes": "doodle", "hair": "shag"}


def set_design(eyes=None, hair=None):
    if eyes:
        DESIGN["eyes"] = eyes
    if hair:
        DESIGN["hair"] = hair


def _star(cv, x, y, r, a=255):
    p = skia.Path()
    p.moveTo(x, y - r)
    p.quadTo(x + r * 0.12, y - r * 0.12, x + r, y)
    p.quadTo(x + r * 0.12, y + r * 0.12, x, y + r)
    p.quadTo(x - r * 0.12, y + r * 0.12, x - r, y)
    p.quadTo(x - r * 0.12, y - r * 0.12, x, y - r)
    p.close()
    cv.drawPath(p, fill_paint((255, 255, 255), a))


def _eyes(cv, lk, st, fd, gx, gy):
    kind = fd["eye"]
    if kind not in ("open", "tear", "sparkle", "wide", "small") or (st.blink and st.blink > 0):
        return _old_eyes(cv, lk, st, fd, gx, gy)
    style = DESIGN["eyes"]
    sz = {"open": 1.0, "tear": 1.03, "sparkle": 1.06, "wide": 1.14, "small": 0.7}[kind]
    for sx in (-1, 1):
        ex, y = sx * 62 + gx * 7, 14 + gy * 5
        if style == "dot":
            rx, ry = 24 * sz, 31 * sz
            eye = skia.Rect.MakeLTRB(ex - rx, y - ry, ex + rx, y + ry)
            cv.drawOval(eye, fill_paint((46, 32, 54)))
            cv.drawCircle(ex + rx * 0.3 + gx * 2, y - ry * 0.3, rx * 0.4, fill_paint((255, 255, 255)))
            cv.drawCircle(ex - rx * 0.36, y + ry * 0.4, rx * 0.19, fill_paint((255, 255, 255), 235))
            lash = smooth_open([(ex - rx - 2, y - ry * 0.35), (ex - rx * 0.6, y - ry * 0.92), (ex, y - ry - 2), (ex + rx * 0.6, y - ry * 0.92), (ex + rx + 2, y - ry * 0.35)], 0.9)
            cv.drawPath(lash, line_paint(LINE, 6))
        elif style == "amber":
            rx, ry = 27 * sz, 34 * sz
            eye = skia.Path.Oval(skia.Rect.MakeLTRB(ex - rx, y - ry, ex + rx, y + ry))
            cv.save()
            cv.clipPath(eye, skia.ClipOp.kIntersect, True)
            cv.drawPaint(_grad(0, y - ry, 0, y + ry, (58, 30, 36), (226, 140, 92)))
            cv.drawOval(skia.Rect.MakeLTRB(ex - rx * 0.7, y + ry * 0.2, ex + rx * 0.7, y + ry * 1.3), fill_paint((255, 214, 150), 150))
            cv.restore()
            cv.drawOval(skia.Rect.MakeLTRB(ex - rx * 0.6 + gx * 2, y - ry * 0.72, ex - rx * 0.02 + gx * 2, y - ry * 0.14), fill_paint((255, 255, 255)))
            cv.drawCircle(ex + rx * 0.34, y + ry * 0.5, rx * 0.14, fill_paint((255, 255, 255), 235))
            lash = smooth_open([(ex - rx - 1, y - ry * 0.2), (ex - rx * 0.7, y - ry * 0.85), (ex, y - ry - 2), (ex + rx * 0.7, y - ry * 0.85), (ex + rx + 1, y - ry * 0.2)], 0.9)
            cv.drawPath(lash, line_paint(LINE, 6.5))
            cv.drawLine(ex + sx * (rx + 1), y - ry * 0.2, ex + sx * (rx + 8), y - ry * 0.45, line_paint(LINE, 4.6))
        else:  # "star": teal gem eyes with a sparkle star
            rx, ry = 28 * sz, 36 * sz
            eye = skia.Path.Oval(skia.Rect.MakeLTRB(ex - rx, y - ry, ex + rx, y + ry))
            cv.save()
            cv.clipPath(eye, skia.ClipOp.kIntersect, True)
            cv.drawPaint(_grad(0, y - ry, 0, y + ry, (22, 56, 92), (120, 224, 218)))
            cv.drawOval(skia.Rect.MakeLTRB(ex - rx * 0.76, y + ry * 0.05, ex + rx * 0.76, y + ry * 1.3), fill_paint((190, 250, 240), 130))
            cv.restore()
            _star(cv, ex + rx * 0.28 + gx * 2, y - ry * 0.34, rx * 0.46)
            cv.drawCircle(ex - rx * 0.34, y + ry * 0.42, rx * 0.15, fill_paint((255, 255, 255), 235))
            cv.drawCircle(ex + rx * 0.3, y + ry * 0.62, rx * 0.08, fill_paint((255, 255, 255), 220))
            lash = smooth_open([(ex - rx - 1, y), (ex - rx * 0.72, y - ry * 0.8), (ex, y - ry - 3), (ex + rx * 0.72, y - ry * 0.8), (ex + rx + 1, y)], 0.9)
            cv.drawPath(lash, line_paint(LINE, 7.5))
            cv.drawPath(smooth_open([(ex + sx * (rx + 1), y - 2), (ex + sx * (rx + 8), y - 9), (ex + sx * (rx + 14), y - 12)], 0.7), line_paint(LINE, 4.6))
        if lk.glasses:
            cv.drawCircle(ex, y, 42, fill_paint((255, 255, 255), 40))
            cv.drawCircle(ex, y, 42, line_paint(LINE, 4.5))
    if lk.glasses:
        cv.drawLine(-24 + gx * 7, 12, 24 + gx * 7, 12, line_paint(LINE, 4.5))


def _dome(p):
    p.moveTo(-154, -22)
    p.cubicTo(-178, -136, -84, -186, 0, -184)
    p.cubicTo(84, -186, 178, -136, 154, -22)


def _fringe_path():
    h = DESIGN["hair"]
    p = skia.Path()
    _dome(p)
    if h == "blunt":
        p.cubicTo(164, 24, 164, 66, 152, 96)                     # right side: stops at the jaw, rounded
        p.quadTo(146, 112, 130, 100)
        p.quadTo(126, 50, 126, -6)
        p.quadTo(126, -40, 100, -54)
        p.cubicTo(60, -34, -60, -34, -100, -54)                  # blunt, softly curved bangs
        p.quadTo(-126, -40, -126, -6)
        p.quadTo(-126, 50, -130, 100)
        p.quadTo(-146, 112, -152, 96)
        p.cubicTo(-164, 66, -164, 24, -154, -22)
    elif h == "sweep":
        p.cubicTo(164, 24, 160, 56, 148, 78)                     # right side: short, tucked
        p.quadTo(138, 84, 130, 70)
        p.quadTo(128, 20, 124, -10)
        p.quadTo(126, -44, 104, -66)                             # forehead opening on the right
        p.quadTo(70, -98, 34, -100)                              # the parting
        p.cubicTo(-10, -84, -70, -52, -112, -8)                  # one long swoop to the left temple
        p.quadTo(-128, 20, -134, 64)
        p.quadTo(-142, 104, -154, 116)                           # long left lock
        p.cubicTo(-166, 76, -168, 28, -154, -22)
    else:  # layered: small wispy bangs
        p.cubicTo(164, 24, 160, 60, 150, 84)
        p.quadTo(138, 70, 130, 50)
        p.quadTo(128, 10, 126, -10)
        p.quadTo(124, -34, 108, -48)
        tips = [(86, -42), (60, -36), (34, -46), (8, -34), (-18, -46), (-46, -36), (-74, -44), (-100, -34)]
        for i, (tx, ty) in enumerate(tips):
            p.quadTo(tx + 14, ty - 22, tx, ty - 2)
            p.quadTo(tx - 10, ty - 24, tx - 14, ty - 26) if i < len(tips) - 1 else None
        p.quadTo(-122, -20, -126, -6)
        p.quadTo(-128, 20, -130, 50)
        p.quadTo(-138, 70, -150, 84)
        p.cubicTo(-160, 60, -164, 24, -154, -22)
    p.close()
    return p


def _hair_back(cv, lk, st):
    if lk.style != "bob":
        return _old_hair_back(cv, lk, st)
    h = DESIGN["hair"]
    bot = {"blunt": 112, "sweep": 116, "layered": 96}[h]
    p = skia.Path()
    p.moveTo(-156, -26)
    p.cubicTo(-176, 30, -174, 80, -150, bot + 6)
    p.quadTo(-104, bot + 22, -62, bot - 2)
    p.quadTo(0, bot - 16, 62, bot - 2)
    p.quadTo(104, bot + 22, 150, bot + 6)
    p.cubicTo(174, 80, 176, 30, 156, -26)
    p.close()
    cv.drawPath(p, _grad(0, -20, 0, 130, shade(lk.hair, -0.22), shade(lk.hair, 0.02)))
    cv.drawPath(p, line_paint(LINE, OW))


def _fringe(cv, lk, st):
    if lk.style != "bob":
        return _old_fringe(cv, lk, st)
    h = DESIGN["hair"]
    c = lk.hair
    p = _fringe_path()
    _hair_fill(cv, lk, p)
    cv.save()
    cv.clipPath(p, skia.ClipOp.kIntersect, True)
    cv.drawPath(smooth_open([(-96, -124), (-52, -152), (12, -158), (70, -144)], 0.9), line_paint((226, 232, 255), 9, 140))
    if h == "blunt":
        for x in (-46, 0, 46):
            cv.drawPath(smooth_open([(x, -76), (x + 2, -52), (x, -38)], 0.8), line_paint(shade(c, -0.4), 3, 150))
    elif h == "sweep":
        for k in range(4):
            cv.drawPath(smooth_open([(40 - k * 4, -100 + k * 6), (-20 - k * 22, -80 + k * 16), (-90 - k * 8, -26 + k * 12)], 0.9), line_paint(shade(c, -0.4), 2.8, 110))
    cv.restore()
    cv.drawPath(p, line_paint(LINE, OW))
    if h == "layered":      # two thin face-framing strands on each side
        for sx in (-1, 1):
            for off, ln in ((0, 118), (16, 104)):
                s = skia.Path()
                x0 = sx * (122 + off * 0.5)
                s.moveTo(x0, -4)
                s.quadTo(x0 + sx * 12, 52, x0 + sx * 2, ln)
                s.quadTo(x0 - sx * 6, 52, x0 - sx * 12, -4)
                s.close()
                cv.drawPath(s, fill_paint(shade(c, -0.04)))
                cv.drawPath(s, line_paint(LINE, OW - 0.6))
    a = skia.Path()
    a.moveTo(-4, -180)
    a.quadTo(10, -218, 52, -214)
    a.quadTo(28, -202, 22, -178)
    a.close()
    cv.drawPath(a, fill_paint(shade(c, -0.05)))
    cv.drawPath(a, line_paint(LINE, OW))


# ====================================================================== v5: crayon-doodle look (from 2nd reference)
_v4_eyes, _v4_fringe_path, _v4_hair_back, _v4_fringe = _eyes, _fringe_path, _hair_back, _fringe
INKY = (24, 20, 28)


def _eyes(cv, lk, st, fd, gx, gy):
    if DESIGN["eyes"] != "doodle":
        return _v4_eyes(cv, lk, st, fd, gx, gy)
    kind = fd["eye"]
    if kind not in ("open", "tear", "sparkle", "wide", "small") or (st.blink and st.blink > 0):
        _old_eyes(cv, lk, st, fd, gx, gy)
        if kind in ("happy", "closed"):
            for sx in (-1, 1):       # little lash flicks on the outer corners of the closed arcs
                ex = sx * 62 + gx * 7
                for dy in (0,):
                    cv.drawPath(_line(ex + sx * 19, 24 + dy, ex + sx * 30, 17 + dy), line_paint(INKY, 4.2))
        return
    sz = {"open": 1.0, "tear": 1.0, "sparkle": 1.1, "wide": 1.25, "small": 0.7}[kind]
    for sx in (-1, 1):
        ex, y = sx * 56 + gx * 7, 20 + gy * 5
        rx, ry = 18 * sz, 25 * sz
        cv.drawOval(skia.Rect.MakeLTRB(ex - rx, y - ry, ex + rx, y + ry), fill_paint(INKY))
        cv.drawCircle(ex + rx * 0.28, y - ry * 0.34, rx * 0.4, fill_paint((255, 255, 255)))
        cv.drawCircle(ex - rx * 0.35, y + ry * 0.38, rx * 0.2, fill_paint((255, 255, 255), 230))
        lash = smooth_open([(ex - rx - 1, y - ry * 0.25), (ex - rx * 0.6, y - ry * 0.9), (ex, y - ry - 2), (ex + rx * 0.6, y - ry * 0.9), (ex + rx + 1, y - ry * 0.25)], 0.9)
        cv.drawPath(lash, line_paint(INKY, 5.5))
        for k, (dx, dy) in enumerate(((10, -5), (14, 2))):      # outer lash flicks
            cv.drawPath(_line(ex + sx * (rx - 1), y - ry * (0.4 - k * 0.25), ex + sx * (rx + dx), y - ry * (0.4 - k * 0.25) + dy - 6), line_paint(INKY, 4.2))
    if lk.glasses:
        for sx in (-1, 1):
            cv.drawCircle(sx * 58 + gx * 7, 18, 40, line_paint(LINE, 4.5))
        cv.drawLine(-18, 16, 18, 16, line_paint(LINE, 4.5))


def _fringe_path():
    if DESIGN["hair"] != "shag":
        return _v4_fringe_path()
    p = skia.Path()
    _dome(p)
    p.cubicTo(166, 20, 168, 70, 160, 108)             # right side, long
    p.lineTo(150, 100); p.lineTo(152, 128); p.lineTo(130, 106)   # ragged tips
    p.quadTo(112, 50, 104, -2)
    if BANG == "curtain":        # parted in the middle, two soft curtains sweeping outward
        p.cubicTo(100, -20, 84, -34, 62, -26)
        p.cubicTo(36, -18, 14, -40, 0, -64)
        p.cubicTo(-14, -40, -36, -18, -62, -26)
        p.cubicTo(-84, -34, -100, -20, -104, -2)
    else:                        # "short": straight, slightly uneven fringe with a few tips
        p.cubicTo(100, -26, 90, -34, 76, -30)
        p.lineTo(60, -22); p.lineTo(44, -34); p.lineTo(26, -20); p.lineTo(8, -34)
        p.lineTo(-10, -20); p.lineTo(-30, -34); p.lineTo(-48, -20); p.lineTo(-68, -32)
        p.cubicTo(-90, -32, -100, -22, -104, -2)
    p.quadTo(-112, 40, -122, 80)
    p.lineTo(-134, 112); p.lineTo(-146, 100); p.lineTo(-152, 126)
    p.lineTo(-162, 104)
    p.cubicTo(-170, 70, -168, 20, -154, -22)
    p.close()
    return p


def _hair_back(cv, lk, st):
    if DESIGN["hair"] != "shag" or lk.style != "bob":
        return _v4_hair_back(cv, lk, st)
    p = skia.Path()
    p.moveTo(-156, -26)
    p.cubicTo(-178, 40, -176, 90, -162, 124)
    p.lineTo(-148, 108); p.lineTo(-136, 134); p.lineTo(-112, 112)
    p.quadTo(0, 90, 112, 112)
    p.lineTo(136, 134); p.lineTo(148, 108); p.lineTo(162, 124)
    p.cubicTo(176, 90, 178, 40, 156, -26)
    p.close()
    cv.drawPath(p, fill_paint(lk.hair))
    cv.drawPath(p, line_paint(LINE, OW))


def _fringe(cv, lk, st):
    if DESIGN["hair"] != "shag" or lk.style != "bob":
        return _v4_fringe(cv, lk, st)
    p = _fringe_path()
    cv.drawPath(p, fill_paint(lk.hair))
    cv.save()
    cv.clipPath(p, skia.ClipOp.kIntersect, True)
    # crayon hatching
    for k in range(16):
        x = -140 + k * 18
        cv.drawPath(smooth_open([(x, -170), (x + 10, -120), (x + 22, -70)], 0.8), line_paint((70, 62, 84), 2.2, 70))
    cv.restore()
    cv.drawPath(p, line_paint(LINE, OW - 0.6))


# ====================================================================== v6: stick-figure doodle body (matches 2nd reference)
from dataclasses import replace as _replace
YUKI = _replace(YUKI, hair=(22, 18, 26), hair_hi=(70, 62, 84), skin=(255, 241, 228), top=(126, 150, 74), scarf=(226, 88, 52), bottom=(30, 26, 34), legs=(30, 26, 34), shoes=(30, 26, 34))
CAST["yuki"] = YUKI
SHOULDER = {-1: (-56, 140), 1: (56, 140)}
UPPER, FORE = 56, 52
_STK = (30, 26, 34)


def draw_body(cv, lk, st):
    walk = st.walk
    if lk is not YUKI and lk.style != "bob":
        pass
    breath = math.sin(st.t * 2.2) * 1.5
    if st.parts == "full":
        for sx in (-1, 1):
            ph = math.sin(walk * 2 * math.pi + (0 if sx < 0 else math.pi)) if walk else 0
            fx = sx * 26 + ph * 20
            lift = max(0, math.cos(walk * 2 * math.pi + (0 if sx < 0 else math.pi))) * 12 if walk else 0
            cv.drawPath(_line(sx * 22, 252, fx, 346 - lift), line_paint(_STK, 7))
            cv.drawPath(_line(fx, 346 - lift, fx + 16, 348 - lift), line_paint(_STK, 7))
    # vest
    vp = smooth_closed([(-48, 126), (-52, 170), (-56, 222), (0, 228 + breath), (56, 222), (52, 170), (48, 126), (0, 122)], 0.45)
    cv.drawPath(vp, fill_paint(lk.top))
    cv.save(); cv.clipPath(vp, skia.ClipOp.kIntersect, True)
    for k in range(7):
        cv.drawPath(_line(-50 + k * 16, 130, -54 + k * 16, 224), line_paint(shade(lk.top, -0.18), 2.4, 110))
    cv.restore()
    cv.drawPath(vp, line_paint(LINE, 4))
    # open vest: dark inner shirt + zip line
    cv.drawPath(smooth_closed([(-10, 134), (10, 134), (4, 160), (-4, 160)], 0.2), fill_paint((92, 88, 100)))
    cv.drawPath(_line(0, 160, 0, 224), line_paint(LINE, 3))
    if st.parts == "full":
        sp = smooth_closed([(-52, 218), (-66, 252), (0, 258), (66, 252), (52, 218), (0, 222)], 0.4)
        cv.drawPath(sp, fill_paint(lk.bottom)); cv.drawPath(sp, line_paint(LINE, 4))


def _line(x0, y0, x1, y1):
    p = skia.Path(); p.moveTo(x0, y0); p.lineTo(x1, y1); return p


def draw_scarf(cv, lk, st):
    if not lk.scarf:
        return
    sc = lk.scarf
    loop = smooth_closed([(-70, 114), (-62, 142), (-20, 152), (24, 152), (64, 142), (72, 114), (30, 128), (-30, 128)], 0.55)
    cv.drawPath(loop, fill_paint(sc))
    cv.save(); cv.clipPath(loop, skia.ClipOp.kIntersect, True)
    for k in range(9):
        cv.drawPath(_line(-64 + k * 16, 118, -60 + k * 16, 152), line_paint(shade(sc, -0.2), 2.4, 120))
    cv.restore()
    cv.drawPath(loop, line_paint(LINE, 4))


def _hand(cv, lk, kind, wr, d, side):
    x, y = wr
    cv.save()
    cv.translate(x, y)
    cv.rotate(math.degrees(math.atan2(d[0], -d[1])))
    if kind in ("open", "point"):
        n = 3 if kind == "open" else 1
        for i in range(n):
            a = (i - (n - 1) / 2) * 0.55
            cv.drawPath(_line(0, -4, math.sin(a) * 24, -math.cos(a) * 24 - 2), line_paint(_STK, 6))
        cv.drawCircle(0, 2, 11, fill_paint(_STK))
    elif kind == "thumb":
        cv.drawCircle(0, 2, 12, fill_paint(_STK))
        cv.drawPath(_line(side * 4, -4, side * 5, -24), line_paint(_STK, 8))
    else:
        cv.drawOval(skia.Rect.MakeLTRB(-11, -6, 11, 14), fill_paint(_STK))
    cv.restore()


def _arm(cv, lk, st, side, wiggle):
    cur, prv = pose_def(st.pose), pose_def(st.prev)
    key = "L" if side == -1 else "R"
    a1c, a2c, hk = cur[key]
    a1p, a2p, _ = prv[key]
    k = back_out(st.blend, 1.3) if st.blend < 1 else 1.0
    a1, a2 = lerp(a1p, a1c, k), lerp(a2p, a2c, k)
    w = math.sin(st.t * 7.5 + (2 if side < 0 else 0)) * 5 * wiggle
    idle = math.sin(st.t * 1.7 + side) * 2.5
    a2 += w + idle + st.beat * 12 * (1 if a2c > 60 else 0)
    a1 += idle * 0.5
    sh, el, wr, d2 = arm_pts(side, a1, a2)
    p = skia.Path(); p.moveTo(*sh); p.lineTo(*el); p.lineTo(*wr)
    cv.drawPath(p, line_paint(_STK, 7))
    _hand(cv, lk, hk, wr, d2, side)


# ====================================================================== v7: smaller face inside a bigger bob
_v3_draw_head = draw_head
FACE_K, HEAD_K = 0.8, 0.86
BANG = "short"


def draw_head(cv, lk, st):
    if lk.style != "bob" or DESIGN["hair"] != "shag":
        return _v3_draw_head(cv, lk, st)
    fd = face_def(st.face)
    gx, gy = st.gx + st.prof * 0.8, st.gy
    cv.save()
    cv.translate(0, 120); cv.rotate(st.tilt); cv.translate(0, -120)
    cv.translate(0, 12)
    cv.translate(0, 64); cv.scale(HEAD_K, HEAD_K); cv.translate(0, -64)
    _hair_back(cv, lk, st)
    cv.save()
    cv.translate(st.prof * 8, 52); cv.scale(FACE_K, FACE_K); cv.translate(0, -52)   # the face is smaller than the hair
    hp = head_path()
    cv.drawPath(hp, fill_paint(lk.skin))
    cv.drawPath(hp, line_paint(LINE, OW + 0.8))
    b = fd.get("blush", 0.3)
    if b > 0.02:
        for sx in (-1, 1):
            cx, cy = sx * 88, 70
            for k in (-1, 0, 1):
                cv.drawLine(cx + k * 12 - 4, cy - 7, cx + k * 12 + 4, cy + 7, line_paint((238, 120, 84), 4.4, int(210 * min(1, b))))
    cv.save(); cv.translate(st.prof * 14, 10)
    _eyes(cv, lk, st, fd, gx, gy)
    cv.restore()
    cv.save(); cv.translate(st.prof * 14, 8)
    _mouth(cv, lk, st, fd)
    cv.restore()
    cv.restore()
    _fringe(cv, lk, st)
    cv.save()
    cv.translate(st.prof * 14, 52); cv.scale(FACE_K, FACE_K); cv.translate(0, -52); cv.translate(0, 10)
    _brows(cv, lk, st, fd, gx)
    cv.restore()
    _fx(cv, lk, st, fd)
    cv.restore()


def draw_character(cv, lk, x, y, scale, st):
    cv.save()
    cv.translate(x, y)
    cv.scale(scale * st.sx * (-1 if st.flip else 1), scale * st.sy)
    cv.translate(0, math.sin(st.t * 2.2) * 2.0)
    full = st.parts in ("full", "torso", "bust")
    if full:
        draw_body(cv, lk, st)
    draw_head(cv, lk, st)
    if full:
        draw_scarf(cv, lk, st)       # scarf wraps in front of the chin so head and body join
        wig = st.wiggle * (0.35 + st.amp * 1.1)
        for side in (-1, 1):
            _arm(cv, lk, st, side, wig)
    cv.restore()
