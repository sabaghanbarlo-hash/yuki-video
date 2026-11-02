"""Frame compositor: scene stage + transitions + captions + heading chips + title/outro cards -> RGB bytes."""
import math
import numpy as np
from PIL import Image, ImageDraw
from . import overlays as O
from .canvas import ease_out, ease_in_out, ease_back

W, H, FPS = 1280, 720, 24
TR = 0.6                         # transition length (s)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


# ------------------------------------------------------------------ transitions
def blend(a, b, p, kind):
    """a = outgoing frame, b = incoming frame (RGBA), p 0..1."""
    e = ease_in_out(clamp(p))
    if kind == "fade":
        return Image.blend(a, b, e)
    if kind in ("wipe_l", "wipe_r"):
        xs = np.arange(W)[None, :]
        edge = e * (W + 160) - 80
        m = (xs < edge) if kind == "wipe_l" else (xs > W - edge)
        soft = np.clip(((edge - xs) / 80.0) if kind == "wipe_l" else ((xs - (W - edge)) / 80.0), 0, 1)
        mask = Image.fromarray((np.repeat(soft, H, 0) * 255).astype(np.uint8), "L")
        return Image.composite(b, a, mask)
    if kind in ("slide", "push"):
        out = Image.new("RGBA", (W, H))
        if kind == "slide":
            dx = int(W * e)
            out.paste(a, (-dx, 0)); out.paste(b, (W - dx, 0))
        else:
            dy = int(H * e)
            out.paste(a, (0, -dy)); out.paste(b, (0, H - dy))
        return out
    if kind == "iris":
        r = e * math.hypot(W, H) / 2
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=255)
        return Image.composite(b, a, m)
    if kind == "zoom":
        s = 1 + 0.5 * e
        aw, ah = int(W * s), int(H * s)
        az = a.resize((aw, ah), Image.BILINEAR).crop(((aw - W) // 2, (ah - H) // 2, (aw - W) // 2 + W, (ah - H) // 2 + H))
        s2 = 1.35 - 0.35 * e
        bw, bh = int(W * s2), int(H * s2)
        bz = b.resize((bw, bh), Image.BILINEAR).crop(((bw - W) // 2, (bh - H) // 2, (bw - W) // 2 + W, (bh - H) // 2 + H))
        return Image.blend(az, bz, clamp((p - 0.25) / 0.5))
    if kind == "flash":
        base = Image.blend(a, b, 1.0 if p > 0.5 else 0.0)
        k = 1 - abs(p - 0.5) * 2
        return Image.blend(base, Image.new("RGBA", (W, H), (255, 255, 255, 255)), clamp(k * 0.9))
    return Image.blend(a, b, e)


class Compositor:
    def __init__(self, plan, mouth, amp):
        self.plan = plan
        self.scenes = plan["scenes"]
        self.mouth, self.amp = mouth, amp
        self.total = self.scenes[-1]["t1"]
        self._stages = {}
        self._order = []

    def stage(self, i):
        if i not in self._stages:
            sc = self.scenes[i]
            if sc["style"] == "collage":
                from .collage import CollageStage
                st = CollageStage(sc)
            elif sc["style"] == "voxel":
                from .stage3d import Stage3D
                st = Stage3D(sc)
            else:
                from .stage2d import Stage2D
                st = Stage2D(sc)
            self._stages[i] = st
            self._order.append(i)
            while len(self._order) > 3:
                self._stages.pop(self._order.pop(0), None)
        return self._stages[i]

    def scene_at(self, t):
        for i, sc in enumerate(self.scenes):
            if t < sc["t1"]:
                return i
        return len(self.scenes) - 1

    def scene_frame(self, i, t, hold_end=False):
        sc = self.scenes[i]
        shot = sc["shots"][-1]
        for sh in sc["shots"]:
            if t < sh["t1"]:
                shot = sh
                break
        fr = min(int(t * FPS), len(self.amp) - 1)
        mo = float(self.amp[fr]) if (not hold_end and fr >= 0) else 0.0
        dur = max(0.3, shot["t1"] - shot["t0"])
        t_rel = t - shot["t0"]
        if hold_end:
            t_rel = min(t_rel, dur - 0.25)
        im = self.stage(i).frame(shot, max(0.0, t_rel), dur, mo, mo, t)
        return im

    # ---- the full frame
    def frame(self, fr):
        t = fr / FPS
        i = self.scene_at(t)
        sc = self.scenes[i]
        im = self.scene_frame(i, t)
        lt = t - sc["t0"]
        tr = sc.get("tr_len", TR)
        if i > 0 and lt < tr:
            prev = self.scene_frame(i - 1, t, hold_end=True)
            im = blend(prev.convert("RGBA"), im.convert("RGBA"), lt / tr, sc["transition"])
        im = im.convert("RGBA")
        self._overlays(im, i, t)
        collage = sc["style"] == "collage"
        if not collage:
            im.alpha_composite(O.vignette(W, H, 0.5 if sc["style"] != "voxel" else 0.3))
        # fade from / to black (collage videos fade from / to the cream page)
        edge = (238, 233, 223, 255) if collage else (0, 0, 0, 255)
        if t < 0.5:
            im = Image.blend(Image.new("RGBA", (W, H), edge), im, ease_out(t / 0.5))
        elif t > self.total - 0.7:
            im = Image.blend(im, Image.new("RGBA", (W, H), edge), clamp((t - (self.total - 0.7)) / 0.7))
        return im

    def frame_bytes(self, fr):
        return self.frame(fr).convert("RGB").tobytes()

    def _overlays(self, im, i, t):
        sc = self.scenes[i]
        lt = t - sc["t0"]
        if sc["kind"] in ("title", "outro"):
            p = clamp(lt / 0.7)
            title = sc.get("card_title", "")
            card = O.title_card(title, "YUKI LAB" if sc["kind"] == "title" else "SUBSCRIBE FOR MORE")
            s = max(0.02, ease_back(p))
            c2 = card.resize((max(1, int(W * s)), max(1, int(H * s))), Image.BILINEAR)
            O.paste(im, c2, (W - c2.width) // 2, (H - c2.height) // 2, clamp(p * 2))
            return
        # section chip
        if sc["heading"] and lt < 2.8 and sc["style"] != "collage":
            a = clamp(lt / 0.3) * clamp((2.8 - lt) / 0.4)
            O.paste(im, O.chip_img(sc["heading"], O.ACCENTS[sc["idx"] % len(O.ACCENTS)], 26), 34, 28 + (1 - ease_out(clamp(lt / 0.3))) * -20, a)
        # no burned-in captions: the video is delivered without subtitles
