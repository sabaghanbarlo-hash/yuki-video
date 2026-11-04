"""Draws one frame of a 'flat explainer' or 'simple characters' scene from the director's plan (see director.py)."""
import math, random, re
from PIL import Image
from .canvas import Cv, ease_out, ease_in_out, ease_back, shade, mix
from . import flat_env as F
from . import toon as T
from . import entities as E
from . import overlays as O

W, H = 1280, 720
MX, MY = F.MX, F.MY
ACC = O.ACCENTS


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


# ------------------------------------------------------------------ camera
def cam_state(spec, u, seed=0, t=0.0):
    """-> (cx, cy, zoom) for progress u (0..1) through the shot."""
    k, amp = spec.get("k", "drift"), spec.get("amp", 1.0)
    fl = -1 if spec.get("flip") else 1
    e = ease_in_out(clamp(u))
    if k == "push":
        return (fl * 20 * amp * e, 0, 1.0 + 0.16 * amp * e)
    if k == "pull":
        return (0, 0, 1.0 + 0.16 * amp * (1 - e))
    if k == "pan_l":
        return (-110 * amp * (e - 0.5), 0, 1.06)
    if k == "pan_r":
        return (110 * amp * (e - 0.5), 0, 1.06)
    if k == "rise":
        return (0, -60 * amp * (e - 0.5), 1.07)
    if k == "sink":
        return (0, 60 * amp * (e - 0.5), 1.07)
    if k == "shake":
        r = random.Random(int(t * 24) + seed)
        s = 9 * amp * (1 - 0.5 * e)
        return (r.uniform(-s, s), r.uniform(-s, s), 1.06)
    if k == "drift2":
        return (fl * 50 * math.sin(u * 3.0 + seed), 22 * math.cos(u * 2.0 + seed), 1.05 + 0.03 * math.sin(u * 2))
    return (fl * 40 * (e - 0.5) * amp, 14 * math.sin(u * 3 + seed), 1.04 + 0.06 * e)


def to_screen(px, py, cam):
    cx, cy, z = cam
    return W / 2 + (px - W / 2 - cx) * z, H / 2 + (py - H / 2 - cy) * z


# ------------------------------------------------------------------ number counting
_NUM = re.compile(r"\d[\d,]*\.?\d*")


def count_text(display, p):
    m = _NUM.search(display)
    if not m:
        return display
    raw = m.group(0)
    try:
        val = float(raw.replace(",", ""))
    except ValueError:
        return display
    dec = len(raw.split(".")[1]) if "." in raw else 0
    cur = val * ease_out(clamp(p))
    s = f"{cur:,.{dec}f}" if "," in raw else f"{cur:.{dec}f}"
    return display[:m.start()] + s + display[m.end():]


# ------------------------------------------------------------------ the stage
class Stage2D:
    def __init__(self, scene):
        self.sc = scene
        self.style = scene["style"]
        self.seed = scene["seed"]
        if self.style == "toon":
            self.layers, self.ambient, self.pal, self.gy = T.build(scene["env"], scene["pal"], self.seed)
        else:
            env = scene["env"] if scene["env"] in F.ENVS else "deep_space"
            pal_name = scene["pal"] if scene["pal"] in F.PALETTES else F.ENV_PALETTES.get(env, ["cosmos"])[0]
            self.layers, self.ambient, self.pal = F.build(env, pal_name, self.seed)
            self.gy = 565
        self.static_bg = None
        self._ambient_cache = {}

    # ---- backdrop
    def backdrop(self, cam):
        im = None
        for L in self.layers:
            v = F.view(L, cam)
            if im is None:
                im = v.convert("RGBA")
            else:
                im.alpha_composite(v.convert("RGBA") if v.mode != "RGBA" else v)
        return im

    def ambient_img(self, t):
        a = self.ambient or {}
        return T.ambient_layer({k: v for k, v in a.items() if k != "shooting"}, t, self.seed)

    # ---- one frame
    def frame(self, shot, t_rel, dur, mouth=0.0, amp=0.0, t_abs=0.0):
        u = clamp(t_rel / max(0.1, dur))
        cam = cam_state(shot["cam"], u, self.seed + shot["sent"][0] if shot.get("sent") else self.seed, t_abs)
        bg = self.backdrop((cam[0], cam[1], cam[2]))
        frame = bg
        amb = self.ambient_img(t_abs)
        frame.alpha_composite(amb)
        if (self.ambient or {}).get("shooting"):
            self._shooting(frame, t_abs)
        fg = Cv(W, H, 2)
        over = []                                  # (image, x, y, alpha)
        self._actors(shot, t_rel, dur, cam, fg, over, mouth, amp, t_abs)
        frame.alpha_composite(fg.image())
        for im, x, y, a in over:
            O.paste(frame, im, x, y, a)
        # a quick flash at the start of shots with a punchy mood
        for a in shot["actors"]:
            if a["k"] == "fx" and a.get("name") == "flash" and t_rel < 0.35:
                fl = Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - t_rel / 0.35))))
                frame.alpha_composite(fl)
        return frame

    def _shooting(self, frame, t):
        cv = Cv(W, H, 1)
        for i in range(2):
            ph = (t * 0.22 + i * 0.5 + self.seed * 0.13) % 1.0
            if ph < 0.12:
                k = ph / 0.12
                x0 = W * (0.15 + 0.6 * ((self.seed * 7 + i * 3) % 10) / 10)
                y0 = H * (0.08 + 0.2 * i)
                x, y = x0 + k * 340, y0 + k * 160
                for j in range(14):
                    kk = max(0, k - j * 0.012)
                    cv.circle(x0 + kk * 340, y0 + kk * 160, 3.2 - j * 0.2, (255, 255, 255), alpha=int(230 - j * 16))
        frame.alpha_composite(cv.image())

    # ---- actors
    def _actors(self, shot, t, dur, cam, fg, over, mouth, amp, t_abs):
        pal = self.pal
        cz = cam[2]
        # leaving: everything shrinks away in the last 0.2 s of the shot
        out_p = clamp((t - (dur - 0.22)) / 0.22)
        for a in shot["actors"]:
            k = a["k"]
            tin = clamp(a.get("f_in", 0.0), 0, 0.85) * max(0.2, dur - 0.5)
            lt = t - tin
            if lt < 0 and k not in ("fx",):
                continue
            p = clamp(lt / 0.55)
            pop = ease_back(p) if p < 1 else 1.0
            pop *= (1 - ease_in_out(out_p) * 0.9)
            if k == "entity":
                self._entity(a, lt, p, pop, cam, fg, over, t_abs)
            elif k == "char":
                self._char(a, lt, shot, dur, pop, cam, fg, mouth, t_abs)
            elif k == "creature":
                self._creature(a, lt, dur, pop, cam, fg, t_abs)
            elif k == "icon":
                self._icon(a, lt, p, pop, cam, over, t_abs, out_p)
            elif k == "spark":
                x, y = to_screen(a["x"] * W + math.sin(t_abs * 0.7 + a["seed"]) * 18, a["y"] * H + math.cos(t_abs * 0.5 + a["seed"]) * 14, cam)
                s = a["size"] * pop * cz * (0.7 + 0.3 * math.sin(t_abs * 3 + a["seed"]))
                col = pal["a1"] if a["seed"] % 2 else pal["a2"]
                fg.glow(x, y, s * 2.4, col, 0.5)
                fg.poly([(x, y - s), (x + s * 0.28, y - s * 0.28), (x + s, y), (x + s * 0.28, y + s * 0.28), (x, y + s), (x - s * 0.28, y + s * 0.28), (x - s, y), (x - s * 0.28, y - s * 0.28)], (255, 255, 255), alpha=220)
            elif k == "orbiter":
                ang = a["phase"] + t_abs * a["speed"]
                cx0, cy0 = a["around"]
                x, y = to_screen(cx0 * W + math.cos(ang) * a["radius"] * W * 0.8, cy0 * H + math.sin(ang) * a["radius"] * H * 0.5, cam)
                s = a["size"] * pop * cz
                E.planet(fg, x, y, s * 2, t_abs, pal, a["seed"])
            elif k == "ringpulse":
                x, y = to_screen(W / 2, H / 2, cam)
                for i in range(3):
                    ph = ((t_abs * 0.35) + i / 3) % 1.0
                    fg.ring(x, y, 60 + ph * 520, 4, pal["a2"], int(150 * (1 - ph)))
            elif k == "vs":
                x, y = to_screen(a["x"] * W, a["y"] * H, cam)
                im = O.outlined(a["text"], 96, ACC[0], (24, 22, 50))
                s = max(0.01, pop)
                im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
                over.append((im, x - im.width / 2, y - im.height / 2, 1.0))
            elif k == "arrow":
                self._arrow(a, lt, cam, fg)
            elif k == "stat":
                self._stat(a, lt, p, pop, cam, over)
            elif k == "stat_small":
                im = O.chip_img(count_text(a["display"], clamp(lt / 1.0)), ACC[1], 34)
                x, y = a["x"] * W, a["y"] * H
                over.append((im, x - im.width / 2, y - im.height / 2 + (1 - ease_out(p)) * 24, min(1.0, p * 1.6) * (1 - out_p)))
            elif k == "card":
                self._card(a, lt, p, out_p, over)
            elif k == "timeline":
                self._timeline(a, lt, dur, cam, fg, over, out_p)
            elif k == "qmark":
                x, y = to_screen(a["x"] * W, a["y"] * H + math.sin(t_abs * 2) * 10, cam)
                im = O.outlined("?", int(a["size"] * pop * cz) + 4, ACC[0], (24, 22, 50), weight="bold")
                fg.glow(x, y, 240 * pop, pal["a1"], 0.35)
                over.append((im, x - im.width / 2, y - im.height / 2, 1.0))

    # ---- icons: a cartoon picture of a thing the narrator names, popping up as it is said
    def _icon(self, a, lt, p, pop, cam, over, t_abs, out_p):
        from .icons import sticker
        sz = int(a["size"] * pop * cam[2])
        if sz < 8:
            return
        sz = max(16, int(round(sz / 8.0)) * 8)
        x, y = to_screen(a["x"] * W + math.cos(t_abs * 0.9 + a["seed"]) * 5, a["y"] * H + math.sin(t_abs * 1.4 + a["seed"]) * 9, cam)
        im = sticker(a["hex"], sz, a.get("rot", 0))
        over.append((im, x - im.width / 2, y - im.height / 2, min(1.0, p * 2.0) * (1 - out_p)))

    # ---- entities
    def _entity(self, a, lt, p, pop, cam, fg, over, t_abs):
        x0, y0 = a["x"] * W, a["y"] * H
        size = a["size"]
        entry = a.get("entry", "pop")
        s = pop
        ox = oy = 0
        if entry == "rise":
            oy = (1 - ease_out(p)) * 120
        elif entry == "slide_l":
            ox = -(1 - ease_out(p)) * 420; s = 0.6 + 0.4 * ease_out(p)
        elif entry == "slide_r":
            ox = (1 - ease_out(p)) * 420; s = 0.6 + 0.4 * ease_out(p)
        elif entry == "drop":
            q = clamp(lt / 0.8)
            oy = -(1 - (q * q)) * 500 if q < 1 else 0
            if q >= 1:
                oy = -abs(math.sin((lt - 0.8) * 7)) * 30 * math.exp(-(lt - 0.8) * 4)
            s = 1.0 if lt > 0 else 0
        elif entry == "grow":
            s = ease_out(p) * (0.5 + 0.5 * ease_out(p))
        m = a.get("motion", "float")
        if m == "float":
            oy += math.sin(t_abs * 1.3 + a["seed"]) * size * 0.025
            ox += math.cos(t_abs * 0.9 + a["seed"]) * size * 0.012
        elif m == "pulse":
            s *= 1 + 0.035 * math.sin(t_abs * 2.2)
        elif m == "spin_slow":
            ox += math.sin(t_abs * 0.5 + a["seed"]) * size * 0.04
        sx, sy = to_screen(x0 + ox, y0 + oy, cam)
        sz = size * s * cam[2]
        if sz < 4:
            return
        pal = self.pal
        if a.get("holo") and self.style == "toon":
            fg.circle(sx, sy, sz * 0.62, (255, 255, 255), alpha=70)
            fg.ring(sx, sy, sz * 0.62, 5, (255, 255, 255), 200)
            sz *= 0.7
        else:
            fg.glow(sx, sy, sz * 0.9, pal["a1"], 0.22 * min(1, p))
        E.draw_entity(fg, a["name"], sx, sy, sz, t_abs, pal, a["seed"])
        lab = a.get("label")
        if lab and lt > 0.2 and self.sc["kind"] == "body" and not getattr(self, "no_labels", False):
            im = O.label_img(lab)
            al = clamp((lt - 0.2) / 0.3)
            ly = sy + sz * 0.58 * E.ENTITY_EXTENT.get(a["name"], 1.0) * 0.8 + 6
            if ly + im.height > H - 190:                      # keep clear of the captions
                ly = max(8, sy - sz * 0.62 - im.height)
            over.append((im, sx - im.width / 2, ly, al))

    # ---- people & animals (toon)
    def _char(self, a, lt, shot, dur, pop, cam, fg, mouth, t_abs):
        x = a["x"]
        if a.get("to") is not None:
            x = a["x"] + (a["to"] - a["x"]) * clamp(lt / max(1.0, dur - 0.5))
        sx, sy = to_screen(x * W, self.gy + 44 + (a["seed"] % 3) * 7 * (a["scale"] < 0.8), cam)
        sc = a["scale"] * pop * cam[2]
        if sc < 0.02:
            return
        act = a["action"]
        mo = mouth if act in ("talk", "point", "shrug") else (0.25 if act in ("cheer", "panic", "jump") else 0.0)
        T.draw_character(fg, sx, sy, sc, a["role"], a["seed"], act, t_abs + a["seed"] * 0.37, a.get("facing", 1), mo, a.get("expr", "neutral"))

    def _creature(self, a, lt, dur, pop, cam, fg, t_abs):
        x = a["x"]
        if a.get("to") is not None:
            x = a["x"] + (a["to"] - a["x"]) * clamp(lt / max(1.0, dur - 0.5))
        kind = a["kind"]
        y = self.gy + 40
        if kind in ("bird", "fish_toon"):
            y = self.gy - 230 if kind == "bird" else self.gy - 80
        sx, sy = to_screen(x * W, y, cam)
        T.draw_creature(fg, kind, sx, sy, a["scale"] * pop * cam[2], t_abs, a["seed"], a.get("facing", 1))

    # ---- diagram pieces
    def _arrow(self, a, lt, cam, fg):
        p = ease_out(clamp(lt / 0.5))
        (x0, y0), (x1, y1) = a["a"], a["b"]
        sx0, sy0 = to_screen(x0 * W, y0 * H, cam)
        sx1, sy1 = to_screen(x1 * W, y1 * H, cam)
        xe, ye = sx0 + (sx1 - sx0) * p, sy0 + (sy1 - sy0) * p
        col = self.pal["a1"]
        fg.line((sx0, sy0), (xe, ye), 9, col)
        if p > 0.85:
            ang = math.atan2(sy1 - sy0, sx1 - sx0)
            hl = 26
            fg.poly([(xe + math.cos(ang) * hl, ye + math.sin(ang) * hl),
                     (xe + math.cos(ang + 2.5) * hl, ye + math.sin(ang + 2.5) * hl),
                     (xe + math.cos(ang - 2.5) * hl, ye + math.sin(ang - 2.5) * hl)], col)

    def _stat(self, a, lt, p, pop, cam, over):
        txt = count_text(a["display"], clamp(lt / 1.2))
        im = O.stat_img(txt, a.get("sub", ""), ACC[0], 132)
        s = max(0.02, pop)
        im2 = im.resize((max(1, int(im.width * s * cam[2])), max(1, int(im.height * s * cam[2]))), Image.BILINEAR)
        x, y = to_screen(a["x"] * W, a["y"] * H, cam)
        over.append((im2, x - im2.width / 2, y - im2.height / 2, 1.0))

    def _card(self, a, lt, p, out_p, over):
        im = O.label_img(a["text"], (255, 255, 255), 40)
        c = ACC[a["color_i"] % len(ACC)]
        bar = Image.new("RGBA", (14, im.height - 20), c + (255,))
        card = Image.new("RGBA", (im.width + 24, im.height), (0, 0, 0, 0))
        card.alpha_composite(im, (24, 0)); card.alpha_composite(bar, (6, 10))
        x = a["x"] * W - card.width / 2 + (1 - ease_out(p)) * -240
        over.append((card, x, a["y"] * H - card.height / 2, clamp(p * 2) * (1 - out_p)))

    def _timeline(self, a, lt, dur, cam, fg, over, out_p):
        y = a["y"] * H
        p = ease_out(clamp(lt / 0.8))
        x0, x1 = 120, 120 + (W - 240) * p
        sx0, sy = to_screen(x0, y, cam)
        sx1, _ = to_screen(x1, y, cam)
        fg.line((sx0, sy), (sx1, sy), 10, (255, 255, 255), alpha=230)
        n = len(a["marks"])
        for i, mk in enumerate(a["marks"]):
            fx = 0.15 + 0.7 * (i + 0.5) / n
            appear = clamp((lt - (0.3 + mk["pos"] * dur * 0.8)) / 0.4)
            if appear <= 0:
                continue
            mx, my = to_screen(fx * W, y, cam)
            fg.circle(mx, my, 20 * ease_back(appear), self.pal["a1"])
            fg.circle(mx, my, 9 * ease_back(appear), (255, 255, 255))
            im = O.chip_img(mk["text"], ACC[i % len(ACC)], 34)
            over.append((im, mx - im.width / 2, my - 86 - (1 - ease_out(appear)) * 20, appear * (1 - out_p)))
