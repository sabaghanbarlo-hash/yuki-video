"""Frame renderer: shot list + voice mouth track -> pictures."""
import bisect, math, os, re, subprocess, sys
import numpy as np
import skia
from . import gfx, sets, yuki, icons
from .gfx import C, INK, fill_paint, line_paint, ease_out, ease_io, back_out, lerp, hash01, draw_text, text_width, wrap_text, sticker, load_image
from .yuki import State, CAST, YUKI, draw_character

GOLD = (255, 200, 48)
GOLD_IN = (92, 52, 26)


def blink_phase(t, seed=0):
    per = 3.4
    k = int(math.floor((t + seed * 0.37) / per))
    for kk in (k - 1, k):
        start = kk * per - seed * 0.37 + 0.35 + hash01(kk, seed) * 2.3
        for off in ((0.0, 0.26) if hash01(kk, seed + 7) > 0.8 else (0.0,)):
            u = t - (start + off)
            if 0.0 <= u < 0.17:
                return 1 if (u < 0.045 or u >= 0.115) else 2
    return 0


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


class Renderer:
    def __init__(self, shots, sents, vis, amp, fps, W, H, seed=0, captions=False):
        self.shots, self.sents, self.vis, self.amp = shots, sents, vis, amp
        self.fps, self.W, self.H, self.seed, self.captions = fps, W, H, seed, captions
        self.starts = [s["t0"] for s in shots]
        self.k = W / 1280.0 if W >= H else H / 1280.0 * 0.82
        self.vertical = H > W

    # ---------------------------------------------------------------- helpers
    def shot_at(self, t):
        i = bisect.bisect_right(self.starts, t) - 1
        return self.shots[max(0, min(i, len(self.shots) - 1))]

    def mouth(self, t):
        f = int(clamp(t * self.fps, 0, len(self.vis) - 1))
        return int(self.vis[f]), float(self.amp[f])

    def state(self, t, sh, lt, face, pose, prev_pose, speaking=True, side=1, gx=0.0, parts="full", flip=False, seedoff=0):
        vis, amp = self.mouth(t) if speaking else (0, 0.0)
        pop = 1 - ease_out(lt / 0.32)
        wob = math.sin(lt * 34)
        beat = max(0.0, amp - 0.55) * 1.6 if speaking else 0.0
        st = State(face=face, vis=vis, amp=amp, blink=blink_phase(t + seedoff, self.seed + seedoff), gx=gx + 0.12 * math.sin(t * 0.9 + seedoff) + 0.08 * math.sin(t * 3.1),
                   gy=0.15 * math.sin(t * 0.7 + 1), tilt=2.4 * math.sin(t * 1.1 + 1 + seedoff) + 3.0 * beat * (1 if side > 0 else -1), pose=pose, prev=prev_pose,
                   blend=clamp(lt / 0.34), t=t + seedoff * 3.7, sx=1 - 0.07 * pop * wob, sy=1 + 0.09 * pop * wob, flip=flip, parts=parts,
                   wiggle=1.0 if speaking else 0.25, beat=beat)
        return st

    # ---------------------------------------------------------------- props
    def draw_icon(self, cv, hexcode, cx, cy, size, rot, born, t, sfxev=None):
        a = back_out(clamp((t - born) / 0.32), 2.2)
        if t < born or a <= 0.01:
            return
        bob = math.sin(t * 2.1 + cx * 0.01) * 6 * self.k
        img = load_image(gfx.ASSETS / "icons" / f"{hexcode}.png")
        sticker(cv, img, cx, cy + bob, size * a, rot + 4 * math.sin(t * 1.6 + cx), ow=4.5 * self.k, border=8 * self.k)

    def draw_label(self, cv, txt, cx, cy, size, born, t, rot=0):
        a = back_out(clamp((t - born) / 0.3), 2.0)
        if t < born or a <= 0.01:
            return
        cv.save()
        cv.translate(cx, cy)
        cv.rotate(rot)
        cv.scale(a, a)
        draw_text(cv, txt, 0, 0, "hand", size, GOLD, ow=size * 0.16, ink=GOLD_IN)
        cv.restore()

    def icon_times(self, sh, ic):
        out = []
        dur = max(0.4, sh["t1"] - sh["t0"])
        for (h, lab, w, p) in ic:
            q = (p - sh["f0"]) / max(0.05, sh["f1"] - sh["f0"])
            sent = self.sents[sh["sent"]]
            born = sent["t0"] + p * (sent["t1"] - sent["t0"])
            born = max(sh["t0"] + 0.18, min(born, sh["t1"] - 0.5))
            out.append(born)
        return out

    # ---------------------------------------------------------------- frame
    def frame(self, i):
        W, H, k = self.W, self.H, self.k
        t = i / self.fps
        sh = self.shot_at(t)
        lt = max(0.0, t - sh["t0"])
        dur = max(0.2, sh["t1"] - sh["t0"])
        p = clamp(lt / dur)
        surf = skia.Surface(W, H)
        cv = surf.getCanvas()
        kind = sh["kind"]
        # ---- camera: slow push + a little punch-in at the cut + shake on big feelings
        z = 1.05 + {"closeup": 0.07, "medium": 0.05, "wide": 0.035, "prop": 0.02, "text": 0.02, "chart": 0.015}[kind] * ease_io(p) + 0.05 * (1 - ease_out(lt / 0.2))
        shx = shy = 0.0
        if sh["mood"] in ("shocked", "angry", "excited") and lt < 0.5 and self.sents[sh["sent"]]["text"].rstrip()[-1:] in "!?":
            a = (1 - lt / 0.5) * 7 * k
            shx, shy = a * math.sin(lt * 70), a * math.cos(lt * 53)
        cv.save()
        cv.translate(W / 2 + shx, H / 2 + shy)
        cv.scale(z, z)
        cv.translate(-W / 2, -H / 2)
        bg = sets.build(sh["bg"], W, H, sh["night"])
        cv.drawImage(bg, 0, 0)
        side = sh["side"]
        getattr(self, "_" + kind)(cv, sh, t, lt, p, side)
        cv.restore()
        if self.captions:
            self._caption(cv, sh, t)
        arr = surf.makeImageSnapshot().toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)
        return np.ascontiguousarray(arr).tobytes()

    def _caption(self, cv, sh, t):
        W, H, k = self.W, self.H, self.k
        lines = wrap_text(sh["text"], "bold", 44 * k, W * 0.82)[:2]
        y = H * 0.9 - (len(lines) - 1) * 52 * k
        for ln in lines:
            draw_text(cv, ln, W / 2, y, "bold", 44 * k, (255, 255, 255), ow=9 * k)
            y += 52 * k

    # ---------------------------------------------------------------- shot types
    def _stickers_side(self, cv, sh, t, cx, cy, size):
        ic = sh["icons"][:2]
        times = self.icon_times(sh, ic)
        for n, ((h, lab, w, p), born) in enumerate(zip(ic, times)):
            off = (-0.5 + n) * 0.0
            x = cx + (n * 0.55 - 0.15) * size * (1 if n else 0)
            y = cy + n * size * 0.75 - (0.2 * size if len(ic) > 1 else 0)
            self.draw_icon(cv, h, x, y, size * (1 - 0.25 * n), (-7 + 12 * n) * (1 if sh["side"] > 0 else -1), born, t)

    def _closeup(self, cv, sh, t, lt, p, side):
        W, H, k = self.W, self.H, self.k
        if self.vertical:
            hx, hy, s = W * 0.5, H * 0.62, 1.75 * k * 1.0
        else:
            hx, hy, s = W * (0.5 + side * (0.14 if sh['icons'] else 0.07)), H * 0.55, 2.0 * k
        st = self.state(t, sh, lt, sh["face"], sh["pose"], sh["prev_pose"], True, side, gx=-side * (0.5 if sh["icons"] else 0.0), parts="bust", flip=(side > 0))
        draw_character(cv, YUKI, hx, hy, s, st)
        if sh["icons"]:
            if self.vertical:
                self._stickers_side(cv, sh, t, W * 0.5, H * 0.2, 330 * k)
            else:
                self._stickers_side(cv, sh, t, W * (0.5 - side * 0.3), H * 0.45, 330 * k)

    def _medium(self, cv, sh, t, lt, p, side):
        W, H, k = self.W, self.H, self.k
        s = 1.28 * k
        hx = W * (0.5 + side * 0.2)
        hy = H * 0.345 if not self.vertical else H * 0.4
        if self.vertical:
            hx = W * 0.5
        st = self.state(t, sh, lt, sh["face"], sh["pose"], sh["prev_pose"], True, side, gx=-side * 0.3, parts="full", flip=(side > 0))
        for n, who in enumerate(sh["people"][:1]):
            ox = W * (0.5 - side * 0.24) if not self.vertical else W * 0.2
            ps = self.state(t, sh, lt, "deadpan" if who == "boss" else "smile", "relax" if who != "boss" else "hips", "rest", False, -side, gx=side * 0.6, parts="full", flip=(side < 0), seedoff=3)
            draw_character(cv, CAST[who], ox, hy + 18 * k, s * 0.9, ps)
        draw_character(cv, YUKI, hx, hy, s, st)
        if sh["icons"]:
            if self.vertical:
                self._stickers_side(cv, sh, t, W * 0.5, H * 0.15, 300 * k)
            elif not sh["people"]:
                self._stickers_side(cv, sh, t, W * (0.5 - side * 0.3), H * 0.4, 300 * k)
            else:
                self._stickers_side(cv, sh, t, W * 0.5, H * 0.16, 230 * k)

    def _wide(self, cv, sh, t, lt, p, side):
        W, H, k = self.W, self.H, self.k
        s = 0.82 * k
        fy = H * sets.floor_frac(sh["bg"]) + 40 * k
        hy = fy - 462 * s + 10
        hx = W * (0.5 + side * 0.18)
        if self.vertical:
            hx = W * 0.5
            s = 1.1 * k
            hy = fy - 462 * s
        st = self.state(t, sh, lt, sh["face"], sh["pose"], sh["prev_pose"], True, side, gx=-side * 0.4, parts="full", flip=(side > 0))
        xs = [W * (0.5 - side * 0.2), W * (0.5 - side * 0.02)]
        for n, who in enumerate(sh["people"][:2]):
            ps = self.state(t, sh, lt, ["deadpan", "worried", "smile", "curious"][(n + len(who)) % 4], ["relax", "hips", "cross", "shrug"][(n + len(who)) % 4], "rest", False, -side, gx=side * 0.6, parts="full", flip=(side < 0), seedoff=3 + n)
            draw_character(cv, CAST[who], xs[n], hy + (8 * n) * k, s * (0.95 - 0.05 * n), ps)
        draw_character(cv, YUKI, hx, hy, s, st)
        if sh["icons"]:
            self._stickers_side(cv, sh, t, W * 0.5, H * 0.13, 190 * k)

    def _corner_yuki(self, cv, sh, t, lt, side, scale=1.0):
        W, H, k = self.W, self.H, self.k
        hx = W * (0.5 + side * 0.355) if not self.vertical else W * (0.5 + side * 0.3)
        hy = H * 0.82
        st = self.state(t, sh, lt, sh["face"], sh["pose"], sh["prev_pose"], True, side, gx=-side * 0.5, parts="bust", flip=(side > 0))
        draw_character(cv, YUKI, hx, hy, 0.95 * k * scale, st)

    def _prop(self, cv, sh, t, lt, p, side):
        W, H, k = self.W, self.H, self.k
        ic = sh["icons"][:4]
        n = len(ic)
        times = self.icon_times(sh, ic)
        if n == 0:
            return
        if self.vertical:
            cells = {1: [(0.5, 0.35)], 2: [(0.5, 0.2), (0.5, 0.5)], 3: [(0.5, 0.15), (0.3, 0.42), (0.7, 0.42)], 4: [(0.3, 0.18), (0.7, 0.18), (0.3, 0.46), (0.7, 0.46)]}[n]
        else:
            cells = {1: [(0.5, 0.4)], 2: [(0.34, 0.38), (0.66, 0.38)], 3: [(0.22, 0.38), (0.5, 0.3), (0.78, 0.38)], 4: [(0.2, 0.38), (0.4, 0.3), (0.6, 0.38), (0.8, 0.3)]}[n]
        size = {1: 400, 2: 330, 3: 280, 4: 240}[n] * k
        for j, ((h, lab, w, pp), (fx, fy), born) in enumerate(zip(ic, cells, times)):
            born = min(born, sh["t0"] + 0.25 + 0.4 * j)
            self.draw_icon(cv, h, W * fx, H * fy, size, (-6 + 5 * j) * (1 if j % 2 else -1), born, t)
            self.draw_label(cv, w, W * fx, H * fy + size * 0.64, 54 * k, born + 0.12, t, rot=(-3 + 2 * j))
        self._corner_yuki(cv, sh, t, lt, side)

    def _text(self, cv, sh, t, lt, p, side):
        W, H, k = self.W, self.H, self.k
        a = back_out(clamp(lt / 0.34), 2.0)
        cv.save()
        cv.translate(W / 2, H * 0.34)
        cv.rotate(-3 + 1.5 * math.sin(t * 1.4))
        cv.scale(a, a)
        if sh["number"]:
            num, unit = sh["number"]
            big = num + ("%" if unit in ("%", "percent", "per cent") else "")
            draw_text(cv, big, 0, 70 * k, "bold", 250 * k, (255, 255, 255), ow=30 * k, ink=INK)
            draw_text(cv, big, 0, 70 * k, "bold", 250 * k, (236, 84, 96), ow=0)
            sub = unit if unit not in ("%", "percent", "per cent", "") else ""
            if sub:
                draw_text(cv, sub, 0, 160 * k, "hand", 80 * k, GOLD, ow=14 * k, ink=GOLD_IN)
        else:
            txt = sh["quote"]
            size = 128 * k
            lines = wrap_text(txt, "hand", size, W * 0.8)
            while len(lines) > 2 and size > 60 * k:
                size *= 0.85
                lines = wrap_text(txt, "hand", size, W * 0.8)
            y = -(len(lines) - 1) * size * 0.55 + size * 0.3
            for ln in lines:
                draw_text(cv, ln, 0, y, "hand", size, GOLD, ow=size * 0.16, ink=GOLD_IN)
                y += size * 1.1
        cv.restore()
        self._corner_yuki(cv, sh, t, lt, side)

    def _chart(self, cv, sh, t, lt, p, side):
        """Hand-drawn axes with a line that draws itself - the 'value vs money' style gag."""
        W, H, k = self.W, self.H, self.k
        ch = sh["chart"] or dict(x="time", y="level", down=False)
        x0, x1 = (W * 0.16, W * 0.72) if side > 0 else (W * 0.3, W * 0.86)
        y0, y1 = H * 0.76, H * 0.12
        if self.vertical:
            x0, x1, y0, y1 = W * 0.15, W * 0.88, H * 0.5, H * 0.1
        grid = (212, 218, 230)
        for j in range(1, 10):
            gx = x0 + (x1 - x0) * j / 10
            cv.drawLine(gx, y0, gx, y1, line_paint(grid, 2 * k))
            gy = y0 + (y1 - y0) * j / 10
            cv.drawLine(x0, gy, x1, gy, line_paint(grid, 2 * k))
        a = back_out(clamp(lt / 0.3), 1.6)
        cv.drawLine(x0, y0, x1 + 26 * k, y0, line_paint(INK, 6 * k))
        cv.drawLine(x0, y0, x0, y1 - 26 * k, line_paint(INK, 6 * k))
        draw_text(cv, ch["x"], (x0 + x1) / 2, y0 + 78 * k, "hand", 52 * k, GOLD, ow=9 * k, ink=GOLD_IN)
        cv.save(); cv.translate(x0 - 66 * k, (y0 + y1) / 2); cv.rotate(-90)
        draw_text(cv, ch["y"], 0, 0, "hand", 52 * k, GOLD, ow=9 * k, ink=GOLD_IN)
        cv.restore()
        g = ease_io(clamp((lt - 0.35) / max(0.8, (sh["t1"] - sh["t0"]) * 0.7)))
        pts = []
        for j in range(0, 41):
            u = j / 40
            if u > g:
                break
            v = (1 - u) if ch["down"] else u
            v = clamp(v + 0.06 * math.sin(u * 9) * (1 - 0.4 * u))
            pts.append((x0 + (x1 - x0) * u * 0.96, y0 - (y0 - y1) * (0.08 + 0.84 * v)))
        if len(pts) > 1:
            path = skia.Path(); path.moveTo(*pts[0])
            for q in pts[1:]:
                path.lineTo(*q)
            cv.drawPath(path, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=14 * k, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join, Color=skia.Color(236, 84, 96)))
            ex, ey = pts[-1]
            cv.drawCircle(ex, ey, 17 * k, fill_paint((236, 84, 96)))
        self._corner_yuki(cv, sh, t, lt, side)
