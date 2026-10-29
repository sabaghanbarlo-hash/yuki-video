"""'Simple characters' style: bean-bodied, round-headed cartoon people (big white eyes, dot pupils, flat colours) that walk,
talk, point, panic, float ... plus 13 cartoon environments. Everything is drawn in code; all designs are original.

    layers, ambient, pal, ground_y = build(env, pal_name, seed)       # backdrop (see toon_envs.py for the ambient keys)
    draw_character(cv, x, floor_y, scale, role, seed, action, t, facing=1, mouth=0.0, expression="neutral")
    draw_creature(cv, kind, x, y, scale, t, seed=0, facing=1)
    ambient_layer(ambient, t, seed) -> RGBA image of particles
"""
import math, random
from .canvas import Cv, shade, mix
from .toon_envs import build, ambient_layer, ENV_FN                     # noqa: F401  (re-exported)

ENV_IDS = ["street", "room", "hills", "beach", "space", "desert", "snow", "stage", "underwater", "rooftop", "cave", "lab", "forest"]
ROLES = ["astronaut", "scientist", "diver", "explorer", "geologist", "engineer", "citizen", "kid", "teacher", "robot"]
ACTIONS = ["idle", "walk", "run", "talk", "point", "jump", "panic", "shrug", "think", "fall", "float", "wave", "cheer", "look_up", "sit", "push"]
EXPRESSIONS = ["neutral", "happy", "worried", "shocked", "curious", "angry"]

SKIN = [(255, 214, 176), (240, 190, 150), (214, 155, 112), (171, 110, 74), (122, 76, 52), (255, 224, 196)]
HAIR = [(40, 30, 30), (92, 56, 34), (214, 160, 70), (176, 60, 40), (30, 30, 52), (120, 120, 132), (66, 44, 96)]
SHIRT = [(255, 120, 100), (90, 170, 255), (120, 210, 150), (255, 200, 80), (180, 130, 240), (255, 150, 200), (70, 200, 200)]
PANTS = [(52, 60, 100), (70, 70, 84), (96, 70, 56), (40, 80, 110)]
INK = (38, 34, 56)

HIP, SHO, NECK = -100.0, -172.0, -196.0            # design-space y (feet at 0, up is negative)
L_ARM1, L_ARM2, L_LEG1, L_LEG2 = 44.0, 42.0, 40.0, 40.0
DESIGN = 0.96                                       # scale 1.0 ~ 260 px


def _d(a):
    r = math.radians(a)
    return math.sin(r), math.cos(r)


def _rot(x, y, a):
    r = math.radians(a); c, s = math.cos(r), math.sin(r)
    return x * c - y * s, x * s + y * c


def _rect(cv, p0, p1, col, r=0, alpha=255):
    cv.rect(min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1]), col, r=r, alpha=alpha)


def _ease(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def _bean(cx, cy, hw, hh, n=26, p=0.55, taper=0.0):
    pts = []
    for i in range(n):
        a = math.tau * i / n
        c, s = math.cos(a), math.sin(a)
        x = hw * math.copysign(abs(c) ** p, c)
        y = hh * math.copysign(abs(s) ** p, s)
        x *= 1 + taper * (y / hh)
        pts.append((cx + x, cy + y))
    return pts


# ------------------------------------------------------------------ pose library
def _walk(t, amp, bend, freq, arm_amp, elbow, lean, bob):
    ph = math.tau * freq * t
    s, c = math.sin(ph), math.cos(ph)
    s2, c2 = -s, -c
    legs = [(amp * s, 6 + bend * max(0, c)), (amp * s2, 6 + bend * max(0, c2))]
    arms = [(-arm_amp * s, elbow + 14 * max(0, -c)), (arm_amp * s, elbow + 14 * max(0, c))]
    return dict(legs=legs, arms=arms, lean=lean, lift=bob * abs(c), ground=True, tilt=2 * s)


def pose(action, t, role="citizen"):
    """-> dict(arms=[(upper, bend) near, far], legs=[(upper, bend) near, far], lean, rot, lift, sx, sy, shake, tilt, look=(x,y), ground, extra)"""
    P = dict(arms=[(5, 8), (5, 8)], legs=[(2, 3), (-2, 3)], lean=0.0, rot=0.0, lift=0.0, sx=1.0, sy=1.0, shake=0.0, tilt=0.0, look=(0, 0), ground=True, extra=None, expr=None)
    if action == "walk":
        P.update(_walk(t, 28, 38, 1.1, 30, 16, 3, 3))
    elif action == "run":
        P.update(_walk(t, 52, 85, 2.1, 62, 80, 14, 13))
        P["look"] = (1, 0)
    elif action == "push":
        P.update(_walk(t, 18, 30, 0.8, 0, 0, 24, 1)); P["arms"] = [(88, 3), (84, 4)]
    elif action == "talk":
        a = math.sin(math.tau * 0.9 * t); b = math.sin(math.tau * 1.4 * t + 1.0); c = math.sin(math.tau * 0.6 * t + 2.0)
        P["arms"] = [(30 + 16 * a, 62 + 22 * b), (10 + 10 * max(0, c), 20 + 40 * max(0, c))]
        P["tilt"] = 3 * a; P["lift"] = 1.5 * abs(b)
    elif action == "point":
        P["arms"] = [(84 + 2 * math.sin(t * 3), 3), (4, 10)]; P["lean"] = 3; P["look"] = (1, 0)
    elif action == "jump":
        T = 1.15; u = (t % T) / T
        if u < 0.16:
            k = _ease(u / 0.16); P.update(sy=1 - 0.17 * k, sx=1 + 0.12 * k, arms=[(-20 * k, 20), (-20 * k, 20)], legs=[(26 * k, 40 * k), (-10 * k, 30 * k)], lean=8 * k)
        elif u < 0.88:
            k = (u - 0.16) / 0.72; h = math.sin(math.pi * k)
            P.update(lift=130 * h, sy=1 + 0.08 * (1 - abs(2 * k - 1)), sx=1 - 0.05, arms=[(150 + 10 * h, 8), (150 - 6 * h, 8)], legs=[(14, 38), (-14, 50)], ground=False)
            P["expr"] = "happy"
        else:
            k = _ease((u - 0.88) / 0.12); P.update(sy=1 - 0.14 * (1 - abs(1 - 2 * k)), sx=1 + 0.1 * (1 - abs(1 - 2 * k)), arms=[(40 * (1 - k), 20), (40 * (1 - k), 20)], legs=[(12, 30), (-8, 24)])
    elif action == "panic":
        sh = math.sin(t * 38)
        P.update(arms=[(138 + 14 * sh, 40 + 20 * math.sin(t * 22)), (140 - 14 * sh, 40 + 20 * math.sin(t * 19))], shake=3.2 * sh,
                 legs=[(16 * math.sin(t * 14), 40 * max(0, math.sin(t * 14))), (-16 * math.sin(t * 14), 40 * max(0, -math.sin(t * 14)))], lift=3 * abs(math.sin(t * 14)), tilt=6 * sh)
        P["expr"] = "shocked"
    elif action == "shrug":
        k = 0.5 + 0.5 * math.sin(math.tau * 0.8 * t)
        P.update(arms=[(34, 72 + 10 * k), (34, 72 + 10 * k)], tilt=8 * math.sin(math.tau * 0.8 * t), lift=3 * k)
    elif action == "think":
        P.update(arms=[(62, 148), (14, 98)], tilt=7 + 2 * math.sin(t * 1.5), look=(0.8, -0.8), lean=-2)
        P["expr"] = "curious"
    elif action == "fall":
        f = math.sin(t * 11)
        P.update(arms=[(120 + 40 * f, 30), (120 - 40 * f, 30)], legs=[(30 * f, 50), (-30 * f, 50)], rot=18 * math.sin(t * 4), lift=34, ground=False, tilt=10 * f)
        P["expr"] = "shocked"
    elif action == "float":
        P.update(arms=[(48 + 14 * math.sin(t * 1.1), 24), (58 - 14 * math.sin(t * 1.1 + 1), 22)], legs=[(-26 + 8 * math.sin(t * 0.9), 16), (-14 + 8 * math.sin(t * 0.9 + 2), 22)],
                 rot=24 * math.sin(t * 0.55) + 8, lift=38 + 8 * math.sin(t * 1.3), ground=False, tilt=3 * math.sin(t))
    elif action == "wave":
        P.update(arms=[(138, 26 + 24 * math.sin(math.tau * 2.2 * t)), (4, 8)], tilt=-3)
        P["expr"] = "happy"
    elif action == "cheer":
        k = abs(math.sin(math.tau * 1.4 * t))
        P.update(arms=[(136 - 8 * k, 34), (136 - 8 * (1 - k), 34)], legs=[(8, 8), (-8, 8)], lift=12 * k, sy=1 + 0.03 * k)
        P["expr"] = "happy"
    elif action == "look_up":
        P.update(tilt=-9, look=(0.2, -1), arms=[(10, 14), (8, 10)], lean=-4)
    elif action == "sit":
        P.update(legs=[(86, 86), (80, 82)], arms=[(24, 56), (20, 50)], lean=-3, tilt=2 * math.sin(t * 1.2))
    else:                                                  # idle
        br = math.sin(math.tau * t / 3.2)
        P.update(sy=1 + 0.012 * br, arms=[(5 + 2 * br, 8), (5 - 2 * br, 8)], tilt=1.5 * math.sin(t * 0.8))
    return P


# ------------------------------------------------------------------ look
def _look(role, seed):
    r = random.Random(seed * 7919 + 13)
    L = dict(skin=r.choice(SKIN), hair=r.choice(HAIR), shirt=r.choice(SHIRT), pants=r.choice(PANTS), shoe=(60, 56, 84), glove=None,
             hairstyle=r.choice(["short", "short", "long", "bob", "bun", "spiky", "afro", "bald"]), head=1.0, body=1.0, width=1.0)
    if role == "astronaut":
        L.update(shirt=(240, 244, 250), pants=(236, 240, 248), shoe=(190, 196, 212), glove=(250, 250, 252), hairstyle="short")
    elif role == "scientist":
        L.update(pants=(60, 70, 98), shoe=(70, 66, 90))
    elif role == "diver":
        L.update(shirt=(34, 74, 150), pants=(34, 74, 150), shoe=(255, 204, 60), glove=(40, 44, 70))
    elif role == "explorer":
        L.update(shirt=(206, 176, 112), pants=(110, 126, 80), shoe=(110, 76, 56))
    elif role == "geologist":
        L.update(shirt=(86, 108, 140), pants=(120, 96, 70), shoe=(90, 70, 56))
    elif role == "engineer":
        L.update(shirt=(80, 98, 138), pants=(60, 66, 84), shoe=(70, 60, 56), glove=(230, 190, 60))
    elif role == "kid":
        L.update(head=1.12, body=0.74, hairstyle=r.choice(["short", "bun", "spiky", "bob"]))
    elif role == "teacher":
        L.update(shirt=(124, 66, 80), pants=(60, 56, 76))
    elif role == "robot":
        L.update(skin=(176, 190, 208), shirt=(150, 164, 186), pants=(120, 134, 158), shoe=(90, 100, 124), glove=(210, 220, 232), hairstyle="bald")
    return L


# ------------------------------------------------------------------ the character
def draw_character(cv, x, floor_y, scale, role, seed, action, t, facing=1, mouth=0.0, expression="neutral"):
    role = role if role in ROLES else "citizen"
    L = _look(role, seed)
    P = pose(action if action in ACTIONS else "idle", t, role)
    if expression == "neutral" and P["expr"]:
        expression = P["expr"]
    S = scale * DESIGN
    bs = L["body"]
    fc = 1 if facing >= 0 else -1
    # ---- limb solving (design space)
    legs = []
    for a, b in P["legs"]:
        hip = (0.0, HIP)
        kx, ky = _d(a); knee = (hip[0] + kx * L_LEG1, hip[1] + ky * L_LEG1)
        ax, ay = _d(a - b); ank = (knee[0] + ax * L_LEG2, knee[1] + ay * L_LEG2)
        legs.append((hip, knee, ank))
    if P["ground"]:
        shift = -9 - max(l[2][1] for l in legs)
    else:
        shift = -9 - (HIP + L_LEG1 + L_LEG2)
    lean, rot_all = P["lean"], P["rot"]
    sx_, sy_ = P["sx"], P["sy"]
    sh_dx = P["shake"]
    lift = P["lift"]

    def T(px, py, upper=True):
        """design-space point -> screen"""
        if upper:
            if bs != 1.0:
                px, py = px * bs, HIP + (py - HIP) * bs
            ox, oy = _rot(px, py - HIP, lean); px, py = ox, oy + HIP
        py += shift
        if rot_all:
            ox, oy = _rot(px, py + 120, rot_all); px, py = ox, oy - 120
        px *= sx_; py *= sy_
        px += sh_dx; py -= lift
        return (x + fc * S * px, floor_y + S * py)

    def Tl(px, py):                                  # lower body: no lean, but body scale
        if bs != 1.0:
            px, py = px * bs, HIP + (py - HIP) * bs
        return T(px, py, upper=False)

    sc = S * (sx_ + sy_) / 2
    wlim = 26 * sc * bs
    skin, shirt, pants, shoe = L["skin"], L["shirt"], L["pants"], L["shoe"]
    hand_col = L["glove"] or skin
    robot = role == "robot"
    # ---- shadow
    hgt = max(0.0, lift) / 140.0
    cv.ellipse(x + fc * S * sh_dx, floor_y + 4 * S, 62 * S * (1 - 0.35 * min(1, hgt)), 11 * S * (1 - 0.3 * min(1, hgt)), (0, 0, 0), alpha=int(62 - 30 * min(1, hgt)))

    # ---- arms (solved in design space, rotated with torso)
    def arm_pts(a, b, side):
        shp = (17.0 * side, SHO)
        ex, ey = _d(a); el = (shp[0] + ex * L_ARM1, shp[1] + ey * L_ARM1)
        hx, hy = _d(a + b); hd = (el[0] + hx * L_ARM2, el[1] + hy * L_ARM2)
        return shp, el, hd

    arms = [arm_pts(*P["arms"][0], 1), arm_pts(*P["arms"][1], -1)]
    sleeve = {"scientist": (250, 252, 255), "teacher": (124, 66, 80)}.get(role, shirt)
    if role == "scientist":
        sleeve = (250, 252, 255)
    limb_w = (13 if robot else 18) * S * bs

    def draw_arm(idx, dark):
        shp, el, hd = arms[idx]
        c1 = shade(sleeve, -0.16) if dark else sleeve
        c2 = (shade(hand_col, -0.14) if dark else hand_col)
        if role in ("explorer", "citizen", "engineer", "kid", "geologist", "teacher", "diver", "astronaut", "scientist") and not robot:
            pass
        p0, p1, p2 = T(*shp), T(*el), T(*hd)
        if not robot:
            # sleeve to the elbow (or whole arm for suits), skin forearm
            full = role in ("astronaut", "diver", "scientist", "teacher", "explorer", "geologist", "engineer")
            cv.line(p0, p1, limb_w, c1)
            fa = c1 if full else (shade(skin, -0.12) if dark else skin)
            cv.line(p1, p2, limb_w * 0.92, fa)
            cv.circle(p2[0], p2[1], 9.2 * sc * bs, c2)
        else:
            cv.line(p0, p1, limb_w * 0.8, shade((132, 146, 168), -0.16 if dark else 0))
            cv.line(p1, p2, limb_w * 0.8, shade((132, 146, 168), -0.16 if dark else 0))
            cv.circle(p1[0], p1[1], 7.5 * sc * bs, (96, 108, 130)); cv.circle(p2[0], p2[1], 9 * sc * bs, c2)
        if idx == 0 and not dark:
            _held(cv, role, p1, p2, S * bs, fc, P)
        if idx == 1 and dark and role == "geologist":
            _hammer(cv, p1, p2, S * bs)

    # far arm + far leg first
    draw_arm(1, True)
    for i in (1, 0):
        hip, knee, ank = legs[i]
        dark = i == 1
        lc = shade(pants, -0.16) if dark else pants
        if robot:
            lc = shade((120, 134, 158), -0.14 if dark else 0)
        a0, a1, a2 = Tl(*hip), Tl(*knee), Tl(*ank)
        w = wlim * (0.78 if robot else 1.0)
        cv.line(a0, a1, w, lc); cv.line(a1, a2, w * 0.92, lc)
        if role == "diver":
            cv.line(a1, a2, w * 0.92, (34, 74, 150))
        if robot:
            cv.circle(a1[0], a1[1], 7 * sc, (96, 108, 130))
        sc_ = shade(shoe, -0.18) if dark else shoe
        ln = 17 + (14 if role == "diver" else 0)
        sx0, sy0 = Tl(ank[0] + 3, ank[1] + 5)
        sx1, sy1 = Tl(ank[0] + ln, ank[1] + 6)
        cv.line((sx0, sy0), (sx1, sy1), 17 * S, sc_)
        if i == 1:
            pass
    # gear behind the body
    _back_gear(cv, role, T, S, L, P)
    # ---- torso
    pts_p = [T(px, py) for px, py in _bean(0, HIP - 4, 36, 24, 22, 0.6)]
    cv.poly(pts_p, shade(pants, 0.0) if not robot else (120, 134, 158))
    tors = [T(px, py) for px, py in _bean(0, -150, 38, 44, 28, 0.55, taper=-0.06)]
    cv.poly(tors, shirt)
    cv.poly([T(px, py) for px, py in [(20, -190), (38, -160), (38, -128), (24, -108), (14, -108), (22, -150)]], shade(shirt, -0.14))   # shaded side
    _torso_detail(cv, role, T, S, L, P)
    # ---- head
    hc_local = (0.0, -226.0)
    tilt = P["tilt"] * (1 if True else 0)

    def Hh(u, v):
        ox, oy = _rot(u, v, tilt)
        return T(0 + ox, -226 + oy)

    hr = 46.0 * L["head"]
    c = T(0, -226)
    hrad = hr * S * bs ** 0.4 * (sx_ + sy_) / 2
    _hair_back(cv, L, Hh, hrad, hr, S, role, tilt)
    if robot:
        _robot_head(cv, Hh, S, expression, mouth, t, seed)
    else:
        cv.circle(Hh(0, 0)[0], Hh(0, 0)[1], hrad, skin)
        # ear
        e = Hh(-4, 6); cv.circle(e[0], e[1], 9 * S * L["head"], shade(skin, -0.1))
        _face(cv, Hh, S * L["head"], L, expression, mouth, t, seed, P)
        _hair_front(cv, L, Hh, S * L["head"], role, tilt)
    _headgear(cv, role, Hh, S * L["head"], L, tilt, seed, P)
    if action == "panic":
        k = (t * 1.6) % 1.0
        d = Hh(46 * 0.9, -20 + 60 * k); r_ = 5.5 * S
        cv.circle(d[0], d[1] + 3 * S, r_, (130, 200, 255), alpha=int(255 * (1 - k * 0.7)))
        cv.poly([(d[0], d[1] - 13 * S), (d[0] - r_ * 0.85, d[1] + 1 * S), (d[0] + r_ * 0.85, d[1] + 1 * S)], (130, 200, 255), alpha=int(255 * (1 - k * 0.7)))
    # near arm + near-side shading on top
    draw_arm(0, False)


# ------------------------------------------------------------------ details
def _face(cv, Hh, S, L, expr, mouth, t, seed, P):
    u0 = 11.0
    ex = {"shocked": 1.2, "worried": 1.0, "curious": 1.05}.get(expr, 1.0)
    rx, ry = 13.5 * S * ex, 15.5 * S * ex
    blink = ((t + (seed % 7) * 0.37) % 3.7) < 0.13 and expr != "shocked"
    lx, ly = P["look"]
    pr = (6.2 if expr != "shocked" else 4.4) * S
    for k, du in enumerate((-15, 16)):
        cx_, cy_ = Hh(u0 + du, -4)
        if blink or expr == "happy" and False:
            cv.line((cx_ - rx * 0.8, cy_), (cx_ + rx * 0.8, cy_), 3.2 * S, INK)
            continue
        cv.ellipse(cx_, cy_, rx, ry, (255, 255, 255))
        cv.ellipse(cx_, cy_, rx, ry, (0, 0, 0), alpha=0)
        px_ = cx_ + (3.2 + lx * 5) * S * (1 if True else 0)
        py_ = cy_ + ly * 5.5 * S + (1.5 * S if expr in ("worried",) else 0)
        cv.circle(px_, py_, pr, INK)
        cv.circle(px_ + pr * 0.32, py_ - pr * 0.34, pr * 0.3, (255, 255, 255))
        if expr == "happy":                                               # eyes squeezed by cheeks
            cv.ellipse(cx_, cy_ + ry * 0.95, rx * 1.15, ry * 0.42, L["skin"])
        # brows
        by = cy_ - ry - 6 * S
        if expr == "worried":
            a = -16 if k == 0 else 16
            _brow(cv, cx_, by, rx, a, S)
        elif expr == "angry":
            a = 18 if k == 0 else -18
            _brow(cv, cx_, by + 5 * S, rx, a, S)
            cv.poly([(cx_ - rx - 2, cy_ - ry - 2), (cx_ + rx + 2, cy_ - ry - 2), (cx_ + rx + 2, cy_ - ry * 0.35 + (6 if k == 0 else -6) * S), (cx_ - rx - 2, cy_ - ry * 0.35 - (6 if k == 0 else -6) * S)], L["skin"], alpha=0)
        elif expr == "curious":
            _brow(cv, cx_, by - (9 * S if k == 1 else 0), rx, -6 if k == 1 else 0, S)
        elif expr == "shocked":
            _brow(cv, cx_, by - 6 * S, rx, 0, S)
        elif expr == "happy":
            _brow(cv, cx_, by - 2 * S, rx * 0.9, -4 if k == 0 else 4, S)
    # cheeks
    if expr == "happy":
        for du in (-24, 30):
            c_ = Hh(u0 + du, 14); cv.ellipse(c_[0], c_[1], 7 * S, 4.5 * S, (255, 140, 140), alpha=120)
    # mouth
    mx, my = Hh(u0 + 2, 23)
    m = max(0.0, min(1.0, mouth))
    if expr == "shocked":
        m = max(m, 0.55)
    if m > 0.08 or expr in ("shocked",):
        w_ = (9 + 6 * m) * S; h_ = (3.5 + 15 * m) * S
        if expr == "shocked":
            w_ = (8 + 3 * m) * S
        cv.ellipse(mx, my + h_ * 0.4, w_, h_, (86, 30, 48))
        if h_ > 8 * S and expr != "shocked":
            cv.ellipse(mx, my + h_ * 0.95, w_ * 0.66, h_ * 0.42, (240, 110, 120))
        if expr == "happy" or (expr == "neutral" and m > 0.3):
            cv.rect(mx - w_ * 0.8, my - 1 * S, mx + w_ * 0.8, my + 3.6 * S, (255, 255, 255), r=2 * S)
    else:
        if expr == "happy":
            pts = [Hh(u0 + 2 + 14 * math.cos(math.radians(a)), 20 + 11 * math.sin(math.radians(a))) for a in range(0, 181, 15)]
            cv.poly(pts, (86, 30, 48))
        elif expr == "worried":
            pts = [Hh(u0 + 2 + du, 28 - 3 * math.sin(du * 0.55) - 1) for du in range(-10, 11, 3)]
            cv.polyline(pts, 3 * S, INK)
        elif expr == "angry":
            cv.line(Hh(u0 - 8, 26), Hh(u0 + 12, 24), 3.4 * S, INK)
        elif expr == "curious":
            cv.line(Hh(u0 - 4, 26), Hh(u0 + 10, 23), 3.2 * S, INK)
        else:
            pts = [Hh(u0 + 2 + du, 24 + 3.5 * math.cos(du * 0.18)) for du in range(-9, 10, 3)]
            cv.polyline(pts, 3 * S, INK)


def _brow(cv, cx, y, rx, ang, S):
    a = math.radians(ang)
    dx, dy = math.cos(a) * rx * 0.9, math.sin(a) * rx * 0.9
    cv.line((cx - dx, y - dy), (cx + dx, y + dy), 3.6 * S, INK)


def _hair_back(cv, L, Hh, hrad, hr, S, role, tilt):
    if role in ("astronaut", "robot"):
        return
    st, col = L["hairstyle"], L["hair"]
    Sh = S * L["head"]
    c = Hh(0, 0)
    if st == "afro":
        cv.circle(c[0], c[1] - 2 * Sh, hrad * 1.28, col)
    elif st == "long":
        cv.poly([Hh(-40, -10), Hh(-52, 60), Hh(-30, 88), Hh(8, 82), Hh(14, 20)], shade(col, -0.1))
    elif st == "bob":
        cv.circle(c[0] - 4 * Sh, c[1] + 6 * Sh, hrad * 1.1, shade(col, -0.1))
    elif st == "bun":
        b = Hh(-14, -58); cv.circle(b[0], b[1], 17 * Sh, col)


def _hair_front(cv, L, Hh, Sh, role, tilt):
    if role in ("astronaut", "robot") or L["hairstyle"] == "bald":
        return
    st, col = L["hairstyle"], L["hair"]
    r = 47.5 * (L["head"])
    arc = [Hh(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))) for a in range(165, 376, 14)]
    if st == "afro":
        fr = [Hh(44, -2), Hh(30, -24), Hh(10, -30), Hh(-10, -22), Hh(-32, -8), Hh(-46, 8)]
    elif st == "bald":
        return
    else:
        fr = [Hh(44, -12), Hh(32, -34), Hh(14, -40), Hh(-4, -34), Hh(-22, -20), Hh(-38, 0), Hh(-46, 12)]
    cv.poly(arc + fr, col)
    if st == "spiky":
        for i, a in enumerate((205, 235, 265, 295, 325)):
            p0 = Hh(r * 0.95 * math.cos(math.radians(a - 12)), r * 0.95 * math.sin(math.radians(a - 12)))
            p1 = Hh(r * 1.38 * math.cos(math.radians(a)), r * 1.38 * math.sin(math.radians(a)))
            p2 = Hh(r * 0.95 * math.cos(math.radians(a + 12)), r * 0.95 * math.sin(math.radians(a + 12)))
            cv.poly([p0, p1, p2], col)



def _headgear(cv, role, Hh, Sh, L, tilt, seed, P):
    c = Hh(0, 0)
    if role == "astronaut":
        r = 60 * Sh
        cv.circle(c[0], c[1] + 2 * Sh, r, (170, 215, 255), alpha=70)
        cv.ring(c[0], c[1] + 2 * Sh, r, 7 * Sh, (238, 242, 250))
        cv.polyline([Hh(-36, -36), Hh(-18, -48), Hh(6, -50)], 5 * Sh, (255, 255, 255), alpha=200)
        # neck ring
        a, b = Hh(-30, 56), Hh(36, 56); cv.line(a, b, 10 * Sh, (226, 232, 244))
    elif role == "scientist":
        for du in (-15, 16):
            e = Hh(11 + du, -4); cv.ring(e[0], e[1], 17 * Sh, 2.8 * Sh, INK)
        cv.line(Hh(11 - 15 + 17, -4), Hh(11 + 16 - 17, -4), 2.6 * Sh, INK)
        cv.line(Hh(11 - 15 - 17, -4), Hh(-30, -6), 2.6 * Sh, INK)
    elif role == "teacher":
        for du in (-15, 16):
            e = Hh(11 + du, -4); cv.rect(e[0] - 16 * Sh, e[1] - 12 * Sh, e[0] + 16 * Sh, e[1] + 12 * Sh, (0, 0, 0), r=6 * Sh, alpha=0)
            cv.ring(e[0], e[1], 16 * Sh, 3 * Sh, (150, 60, 70))
        cv.line(Hh(11 - 15 + 16, -4), Hh(11 + 16 - 16, -4), 2.6 * Sh, (150, 60, 70))
    elif role == "diver":
        for k, du in enumerate((-15, 16)):
            pass
        m0, m1 = Hh(-18, -22), Hh(46, 20)
        cv.rect(min(m0[0], m1[0]) - 4 * Sh, min(m0[1], m1[1]) - 6 * Sh, max(m0[0], m1[0]) + 4 * Sh, max(m0[1], m1[1]) + 6 * Sh, (120, 210, 255), r=12 * Sh, alpha=70)
        cv.line(Hh(-20, -2), Hh(-46, 2), 6 * Sh, (30, 40, 70))
        cv.ring((m0[0] + m1[0]) / 2, (m0[1] + m1[1]) / 2, 36 * Sh, 0.1, (0, 0, 0), alpha=0)
        for (a, b) in ((Hh(-18, -24), Hh(46, -24)), (Hh(-18, 22), Hh(46, 22))):
            cv.line(a, b, 5 * Sh, (30, 40, 70))
        cv.line(Hh(-18, -24), Hh(-18, 22), 5 * Sh, (30, 40, 70)); cv.line(Hh(46, -24), Hh(46, 22), 5 * Sh, (30, 40, 70))
    elif role == "explorer":
        cv.ellipse(*Hh(4, -20), 70 * Sh, 12 * Sh, (176, 132, 74))
        cv.poly([Hh(-40, -22), Hh(-34, -50), Hh(-4, -66), Hh(30, -50), Hh(44, -22)], (196, 150, 86))
        cv.line(Hh(-39, -26), Hh(43, -26), 8 * Sh, (120, 70, 50))
    elif role in ("geologist", "engineer"):
        col = (255, 208, 50) if role == "geologist" else (246, 246, 250)
        cv.poly([Hh(-46, -16), Hh(-42, -46), Hh(-14, -64), Hh(24, -62), Hh(46, -36), Hh(52, -16)], col)
        _rect(cv, Hh(-52, -22), Hh(62, -12), shade(col, -0.12), r=4 * Sh) if False else cv.line(Hh(-52, -16), Hh(62, -16), 11 * Sh, shade(col, -0.1))
        cv.line(Hh(0, -63), Hh(6, -24), 9 * Sh, shade(col, -0.12))
        if role == "engineer":
            for du in (-15, 16):
                e = Hh(11 + du, -34); cv.circle(e[0], e[1], 11 * Sh, (60, 70, 96)); cv.circle(e[0], e[1], 7.5 * Sh, (150, 220, 255))
            cv.line(Hh(-30, -34), Hh(48, -34), 4 * Sh, (60, 70, 96))
    elif role == "robot":
        a0 = Hh(0, -42); a1 = Hh(4, -66)
        cv.line(a0, a1, 4 * Sh, (110, 122, 146)); cv.circle(a1[0], a1[1], 6.5 * Sh, (255, 100, 110))


def _robot_head(cv, Hh, S, expr, mouth, t, seed):
    c = Hh(0, 0)
    cv.poly([Hh(-44, -38), Hh(44, -38), Hh(48, -30), Hh(48, 36), Hh(40, 44), Hh(-40, 44), Hh(-48, 36), Hh(-48, -30)], (176, 190, 208))
    cv.poly([Hh(20, -38), Hh(44, -38), Hh(48, -30), Hh(48, 36), Hh(40, 44), Hh(24, 44)], (150, 164, 186))
    cv.rect(c[0] - 40 * S, c[1] - 30 * S, c[0] + 40 * S, c[1] + 30 * S, (0, 0, 0), alpha=0)
    cv.poly([Hh(-36, -26), Hh(36, -26), Hh(40, -20), Hh(40, 24), Hh(34, 30), Hh(-34, 30), Hh(-40, 24), Hh(-40, -20)], (22, 36, 60))
    blink = ((t + (seed % 5) * 0.4) % 3.5) < 0.12
    col = {"angry": (255, 90, 90), "worried": (255, 190, 90), "happy": (120, 255, 200), "shocked": (255, 255, 255)}.get(expr, (110, 230, 255))
    for du in (-16, 16):
        e = Hh(du + 3, -6)
        hh = 3 if blink else (15 if expr == "shocked" else 11)
        cv.rect(e[0] - 8 * S, e[1] - hh * S, e[0] + 8 * S, e[1] + hh * S, col, r=3 * S)
    m = Hh(3, 16)
    cv.rect(m[0] - 14 * S, m[1] - (2 + 7 * mouth) * S, m[0] + 14 * S, m[1] + (2 + 7 * mouth) * S, col, r=2 * S)
    for du in (-48, 48):
        e = Hh(du, 0); cv.rect(e[0] - 4 * S, e[1] - 12 * S, e[0] + 4 * S, e[1] + 12 * S, (130, 144, 166), r=2 * S)


def _torso_detail(cv, role, T, S, L, P):
    if role == "astronaut":
        cv.poly([T(-22, -176), T(22, -176), T(22, -140), T(-22, -140)], (60, 80, 120))
        for i, col in enumerate(((255, 110, 90), (120, 230, 150), (255, 220, 90))):
            q = T(-12 + i * 12, -164); cv.circle(q[0], q[1], 4.6 * S, col)
        cv.poly([T(-38, -112), T(38, -112), T(38, -122), T(-38, -122)], (230, 120, 70))
    elif role == "scientist":
        cv.poly([T(px, py) for px, py in _bean(0, -146, 40, 46, 28, 0.55)], (250, 252, 255))
        cv.poly([T(20, -190), T(38, -160), T(38, -122), T(24, -104), T(18, -104), T(24, -150)], (222, 230, 242))
        cv.line(T(0, -184), T(0, -112), 3 * S, (196, 206, 222))
        cv.poly([T(-14, -190), T(0, -168), T(-16, -164)], (240, 244, 252)); cv.poly([T(14, -190), T(0, -168), T(16, -164)], (230, 236, 248))
        _rect(cv, T(10, -150), T(24, -138), (120, 190, 255), r=2)
    elif role == "diver":
        cv.poly([T(-38, -170), T(38, -170), T(38, -158), T(-38, -158)], (255, 204, 60)); cv.poly([T(-38, -138), T(38, -138), T(38, -128), T(-38, -128)], (255, 204, 60))
    elif role == "explorer":
        cv.poly([T(-18, -190), T(22, -190), T(40, -150), T(22, -110), T(-22, -110), T(-40, -150)], shade(L["shirt"], -0.0), alpha=0)
        cv.line(T(-26, -190), T(24, -112), 7 * S, (120, 76, 56))
        _rect(cv, T(-26, -152), T(-8, -132), (176, 140, 84), r=3 * S)
    elif role == "geologist":
        cv.poly([T(-38, -188), T(-14, -188), T(-4, -112), T(-38, -112)], (255, 140, 40)); cv.poly([T(38, -188), T(14, -188), T(4, -112), T(38, -112)], (255, 140, 40))
        cv.line(T(-26, -150), T(-8, -150), 4 * S, (240, 240, 250)); cv.line(T(26, -150), T(8, -150), 4 * S, (240, 240, 250))
    elif role == "engineer":
        cv.poly([T(-38, -188), T(-12, -188), T(-4, -112), T(-38, -112)], (214, 238, 60)); cv.poly([T(38, -188), T(12, -188), T(4, -112), T(38, -112)], (214, 238, 60))
        cv.poly([T(-38, -150), T(-6, -150), T(-5, -140), T(-38, -140)], (230, 232, 240)); cv.poly([T(38, -150), T(6, -150), T(5, -140), T(38, -140)], (230, 232, 240))
    elif role == "teacher":
        cv.poly([T(-14, -190), T(0, -150), T(14, -190)], (250, 250, 252)); cv.poly([T(-3, -160), T(3, -160), T(5, -122), T(-5, -122)], (210, 80, 90))
    elif role == "robot":
        _rect(cv, T(-20, -176), T(20, -142), (60, 80, 120), r=4 * S)
        for i, col in enumerate(((255, 110, 110), (120, 255, 190), (110, 210, 255))):
            q = T(-10 + i * 10, -162); cv.circle(q[0], q[1], 3.8 * S, col)
        cv.line(T(-38, -122), T(38, -122), 4 * S, (96, 108, 130))
    elif role == "kid":
        cv.line(T(-34, -150), T(34, -150), 8 * S, shade(L["shirt"], 0.22), alpha=255)
    else:                                                  # citizen: little pocket / stripe
        cv.line(T(-34, -144), T(34, -144), 7 * S, shade(L["shirt"], 0.18))


def _back_gear(cv, role, T, S, L, P):
    if role == "astronaut":
        cv.poly([T(-52, -182), T(-30, -186), T(-30, -118), T(-52, -118)], (196, 204, 220))
        _rect(cv, T(-56, -170), T(-44, -150), (230, 120, 70))
    elif role == "diver":
        _rect(cv, T(-64, -184), T(-30, -104), (230, 190, 60), r=12 * S); _rect(cv, T(-62, -176), T(-52, -112), (255, 230, 120), r=4 * S)
        cv.circle(*T(-48, -190), 7 * S, (120, 130, 150))
    elif role == "explorer":
        _rect(cv, T(-58, -182), T(-26, -114), (150, 100, 66), r=8 * S); _rect(cv, T(-58, -156), T(-26, -148), (110, 70, 48))
        cv.circle(*T(-60, -190), 9 * S, (214, 190, 140))


def _held(cv, role, p1, p2, S, fc, P):
    if role == "teacher":
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        n = math.hypot(dx, dy) or 1
        ang = math.atan2(dy, dx) - fc * 0.5
        e = (p2[0] + math.cos(ang) * 80 * S, p2[1] + math.sin(ang) * 80 * S)
        cv.line(p2, e, 4 * S, (170, 120, 70)); cv.circle(e[0], e[1], 4.5 * S, (255, 100, 100))


def _hammer(cv, p1, p2, S):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    e = (p2[0] + ux * 38 * S, p2[1] + uy * 38 * S)
    cv.line(p2, e, 5 * S, (140, 96, 64))
    nx, ny = -uy, ux
    cv.poly([(e[0] + nx * 14 * S, e[1] + ny * 14 * S), (e[0] - nx * 14 * S, e[1] - ny * 14 * S), (e[0] - nx * 14 * S + ux * 14 * S, e[1] - ny * 14 * S + uy * 14 * S),
             (e[0] + nx * 14 * S + ux * 14 * S, e[1] + ny * 14 * S + uy * 14 * S)], (150, 156, 172))


# ------------------------------------------------------------------ creatures
CREATURES = ["blob_alien", "cat", "dog", "bird", "fish_toon", "dino_toon"]


def draw_creature(cv, kind, x, y, scale, t, seed=0, facing=1):
    """Small original cartoon animals/aliens. (x, y) = feet for walkers, centre for flyers/swimmers. scale 1.0 ~ 110 px."""
    fc = 1 if facing >= 0 else -1
    S = scale
    r = random.Random(seed * 31 + 5)
    X = lambda u: x + fc * S * u
    Y = lambda v: y + S * v
    pal = [(255, 170, 90), (150, 200, 255), (200, 170, 255), (255, 150, 180), (140, 220, 160), (250, 220, 110)]
    col = pal[seed % len(pal)]
    blink = (t + seed * 0.3) % 3.4 < 0.12

    def eye(u, v, rr=9):
        cv.circle(X(u), Y(v), rr * S, (255, 255, 255))
        if not blink:
            cv.circle(X(u + 2.5), Y(v + 0.5), rr * 0.5 * S, INK); cv.circle(X(u + 4), Y(v - 1.5), rr * 0.17 * S, (255, 255, 255))
        else:
            cv.line((X(u - rr * 0.7), Y(v)), (X(u + rr * 0.7), Y(v)), 2.4 * S, INK)

    if kind == "blob_alien":
        col = (120, 220, 150) if seed % 2 == 0 else (190, 140, 255)
        w = math.sin(t * 3)
        pts = [(X(math.cos(a) * (46 + 4 * math.sin(a * 3 + t * 4)) * (1 + 0.05 * w)), Y(-46 + math.sin(a) * (46 + 4 * math.sin(a * 3 + t * 4)) * (1 - 0.05 * w) * (1 if math.sin(a) < 0 else 0.5)))
               for a in [math.tau * i / 28 for i in range(28)]]
        for s_ in (-1, 1):
            a0 = (X(s_ * 20), Y(-86)); a1 = (X(s_ * 34 + 6 * w), Y(-122 + 4 * math.sin(t * 5 + s_)))
            cv.line(a0, a1, 3 * S, shade(col, -0.2)); cv.circle(a1[0], a1[1], 6 * S, (255, 220, 100))
        cv.poly(pts, col)
        cv.ellipse(X(-8), Y(-26), 22 * S, 8 * S, shade(col, 0.2), alpha=130)
        eye(-14, -56, 11); eye(14, -58, 9.5); eye(0, -76, 6.5)
        cv.poly([(X(-9), Y(-34)), (X(11), Y(-34)), (X(1), Y(-26 + 3 * math.sin(t * 5)))], (70, 36, 80))
    elif kind in ("cat", "dog"):
        ph = t * 5
        body = (230, 150, 90) if kind == "cat" else (214, 170, 120)
        body = pal[seed % len(pal)] if kind == "cat" and seed else body
        for i, (u, d) in enumerate(((-22, 0), (-8, 1), (24, 1), (36, 0))):
            sw = math.sin(ph + d * math.pi) * 8
            cv.line((X(u), Y(-30)), (X(u + sw), Y(-2)), 10 * S, shade(body, -0.12 if d else -0.04))
        tail = math.sin(t * (4 if kind == "dog" else 2)) * 14
        cv.polyline([(X(-44), Y(-52)), (X(-62), Y(-62 + tail * 0.3)), (X(-66 + tail * 0.4), Y(-92))], 9 * S, body)
        cv.ellipse(X(-2), Y(-50), 50 * S, 28 * S, body)
        cv.ellipse(X(6), Y(-38), 34 * S, 14 * S, shade(body, 0.28), alpha=160)
        hx, hy = X(46), Y(-72 + math.sin(ph * 2) * 1.5)
        if kind == "cat":
            cv.poly([(X(32), Y(-84)), (X(36), Y(-112)), (X(50), Y(-90))], body); cv.poly([(X(52), Y(-90)), (X(62), Y(-112)), (X(66), Y(-82))], body)
            cv.poly([(X(37), Y(-90)), (X(38), Y(-104)), (X(46), Y(-92))], (255, 170, 180))
        else:
            cv.ellipse(X(36), Y(-66), 9 * S, 18 * S, shade(body, -0.35))
            cv.ellipse(X(70), Y(-62), 16 * S, 11 * S, shade(body, 0.25))
        cv.circle(hx, hy, 26 * S, body)
        eye(40, -76, 7.5); eye(56, -76, 7.5)
        cv.circle(X(66), Y(-70), 4.5 * S, INK)
        if kind == "dog":
            cv.ellipse(X(66), Y(-54), 5 * S, 7 * S + 2 * math.sin(ph * 2) * S, (240, 110, 130))
    elif kind == "bird":
        f = math.sin(t * 10)
        by = y + math.sin(t * 2) * 5 * S
        cv.poly([(x - fc * 38 * S, by + 6 * S), (x - fc * 66 * S, by - 10 * S), (x - fc * 54 * S, by + 8 * S)], shade(col, -0.2))
        cv.ellipse(x, by, 38 * S, 30 * S, col); cv.ellipse(x + fc * 6 * S, by + 12 * S, 24 * S, 14 * S, shade(col, 0.3), alpha=160)
        cv.poly([(x + fc * 6 * S, by - 4 * S), (x - fc * 26 * S, by - 30 * S * f - 2 * S), (x - fc * 38 * S, by + 4 * S)], shade(col, -0.18))
        cv.circle(x + fc * 22 * S, by - 8 * S, 7.5 * S, (255, 255, 255)); cv.circle(x + fc * 24 * S, by - 8 * S, 3.6 * S, INK)
        cv.poly([(x + fc * 33 * S, by - 4 * S), (x + fc * 52 * S, by + 2 * S), (x + fc * 33 * S, by + 8 * S)], (255, 190, 70))
    elif kind == "fish_toon":
        w = math.sin(t * 6)
        by = y + math.sin(t * 1.6) * 4 * S
        cv.poly([(x - fc * 34 * S, by), (x - fc * (62 + 4 * w) * S, by - 24 * S + 6 * w * S), (x - fc * (62 + 4 * w) * S, by + 24 * S + 6 * w * S)], shade(col, -0.2))
        cv.ellipse(x, by, 44 * S, 29 * S, col)
        cv.ellipse(x + fc * 4 * S, by + 11 * S, 30 * S, 13 * S, shade(col, 0.3), alpha=170)
        cv.poly([(x - fc * 6 * S, by - 24 * S), (x + fc * 10 * S, by - 42 * S), (x + fc * 20 * S, by - 22 * S)], shade(col, -0.15))
        cv.circle(x + fc * 24 * S, by - 5 * S, 8.5 * S, (255, 255, 255)); cv.circle(x + fc * 26 * S, by - 5 * S, 4.2 * S, INK)
        for i in range(3):
            cv.line((x - fc * 10 * S + i * fc * 10 * S, by - 18 * S), (x - fc * 10 * S + i * fc * 10 * S, by + 16 * S), 3 * S, shade(col, -0.2), alpha=120)
    elif kind == "dino_toon":
        col = (110, 200, 130) if seed % 2 == 0 else (150, 190, 240)
        ph = t * 4
        for i, (u, d) in enumerate(((-12, 0), (16, 1))):
            sw = math.sin(ph + d * math.pi) * 9
            cv.line((X(u), Y(-40)), (X(u + sw), Y(-3)), 15 * S, shade(col, -0.18 if d else -0.05)); cv.ellipse(X(u + sw + 8), Y(-3), 15 * S, 7 * S, shade(col, -0.2))
        tw = math.sin(t * 2.5) * 10
        cv.poly([(X(-28), Y(-82)), (X(-92 + tw), Y(-50 + tw * 0.5)), (X(-28), Y(-34))], col)
        for i in range(5):
            u = -20 + i * -12; cv.poly([(X(u + 4 + 20 - i * 0), Y(-96 + i * 6)), (X(-12 + (-i * 12)), Y(-116 + i * 8)), (X(-14 + (-i * 12) - 12), Y(-90 + i * 8))], (255, 170, 90))
        cv.ellipse(X(0), Y(-70), 44 * S / S, 38 * S / S, col) if False else cv.ellipse(X(0), Y(-68), 44 * S, 38 * S, col)
        cv.ellipse(X(6), Y(-54), 28 * S, 16 * S, shade(col, 0.3), alpha=170)
        for i in range(4):
            u = -18 + i * -12
        cv.polyline([(X(26), Y(-96)), (X(38), Y(-110))], 0.1, col, alpha=0)
        cv.ellipse(X(40), Y(-102 + math.sin(ph * 2) * 1.5), 30 * S, 24 * S, col)
        cv.rect(X(44) if fc > 0 else X(70), Y(-92), X(70) if fc > 0 else X(44), Y(-84), (255, 255, 255), r=2 * S, alpha=0)
        eye(40, -110, 8)
        cv.poly([(X(56), Y(-96)), (X(68), Y(-92)), (X(56), Y(-88))], (255, 255, 255))
        cv.line((X(50), Y(-88)), (X(66), Y(-90)), 2.5 * S, (80, 40, 60))
        for s_ in (-1, 1):
            pass
        cv.line((X(24), Y(-62)), (X(36), Y(-52 + math.sin(ph * 2) * 3)), 6 * S, shade(col, -0.05))
