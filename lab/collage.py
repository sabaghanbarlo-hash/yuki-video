"""The collage stage: a cream page, one or two pictures that change every few seconds, Yuki reacting in a corner.

    CollageStage(scene).frame(shot, t_rel, dur, mouth, amp, t_abs) -> RGBA 1280x720   (same interface as Stage2D / Stage3D)

A shot (see collage_dir.py) says what is on the page: kind (media | text | icons | stat), layout, treatment, entrance, and how Yuki
looks. Pictures come from lab/media.py (shot['media'] = file paths, prefetched before rendering); a picture that could not be fetched
is drawn by the lab's own flat / toon engines instead, so a shot is never empty.
Rendering is stateless: a frame depends only on (shot, time), so any worker can render any frame.
"""
import functools, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops

from .canvas import Cv, ease_out, ease_in_out, ease_back, shade
from .fonts import font
from . import yuki_rig as Y
from . import overlays as O

W, H = 1280, 720
PAPER = (238, 233, 223)
INK = (58, 54, 50)
PANEL_COLOURS = [(188, 208, 62), (240, 160, 64), (96, 176, 204), (232, 112, 122), (156, 136, 214), (250, 206, 84)]
SHAPE_COLOURS = [(30, 98, 214), (216, 40, 56), (255, 200, 60), (40, 170, 160), (250, 130, 60), (120, 90, 200)]


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


# ------------------------------------------------------------------ the page
@functools.lru_cache(maxsize=1)
def paper():
    rng = np.random.default_rng(7)
    base = np.zeros((H, W, 3), np.float32) + np.array(PAPER, np.float32)
    lo = rng.normal(0, 1, (H // 24 + 2, W // 24 + 2)).astype(np.float32)
    lo = np.array(Image.fromarray(((lo - lo.min()) / (np.ptp(lo) + 1e-6) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255.0
    base += (lo[..., None] - 0.5) * 5.0
    grain = rng.normal(0, 1.2, (H, W, 1)).astype(np.float32)
    base += grain
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    base -= (np.clip(d - 0.75, 0, 1) ** 2 * 18.0)[..., None]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


# ------------------------------------------------------------------ geometry
def geometry(layout, side):
    """-> dict(panels=[(x, y, w, h)], yuki=(x, floor_y, scale)). side = where the panel sits ('l' / 'r'); Yuki takes the other corner."""
    r = side == "r"
    if layout == "full":
        return dict(panels=[(236 if r else 34, 38, 1010, 566)], yuki=(150 if r else 1130, H + 92, 0.72))
    if layout == "mid":
        return dict(panels=[(450 if r else 110, 66, 720, 452)], yuki=(222 if r else 1058, H + 56, 0.82))
    if layout == "center":
        return dict(panels=[(250, 44, 780, 440)], yuki=(124 if r else 1156, H + 84, 0.66))
    if layout == "split":
        xs = (300, 790) if r else (60, 550)
        return dict(panels=[(xs[0], 52, 430, 470), (xs[1], 52, 430, 470)], yuki=(150 if r else 1130, H + 84, 0.72))
    if layout == "fullbleed":
        return dict(panels=[(0, 0, W, H)], yuki=(160 if r else 1120, H + 100, 0.62))
    if layout == "title":
        return dict(panels=[(470 if r else 56, 196, 750, 470)], yuki=(200 if r else 1080, H + 30, 0.88), text=(470 if r else 56, 40, 750, 150))
    if layout == "icons":
        return dict(panels=[], yuki=(640, H + 40, 0.84))
    if layout == "stat":
        return dict(panels=[], yuki=(220 if r else 1060, H + 24, 0.86), text=(450 if r else 40, 170, 790, 380))
    return dict(panels=[(250, 44, 780, 440)], yuki=(112, H + 58, 0.52))


# ------------------------------------------------------------------ small drawing helpers
@functools.lru_cache(maxsize=256)
def round_mask(w, h, r):
    m = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 3 - 1, h * 3 - 1), radius=r * 3, fill=255)
    return m.resize((w, h), Image.LANCZOS)


@functools.lru_cache(maxsize=64)
def shadow_img(w, h, r=10, blur=14, alpha=70):
    pad = blur * 3
    im = Image.new("L", (w + pad * 2, h + pad * 2), 0)
    ImageDraw.Draw(im).rounded_rectangle((pad, pad, pad + w, pad + h), radius=r, fill=alpha)
    im = im.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", im.size, (40, 30, 20, 0)); out.putalpha(im)
    return out, pad


def paste(dst, im, x, y, alpha=1.0):
    O.paste(dst, im, x, y, alpha)


@functools.lru_cache(maxsize=96)
def blob_parts(w, h, seed):
    """(mask L, backdrop RGBA) for the paper-cut look: a wobbly cut-out edge and flat colour shapes sticking out behind it."""
    rng = random.Random(seed)
    pad = 60
    cw, ch = w + pad * 2, h + pad * 2
    n = rng.randint(7, 10)
    pts = []
    for i in range(n):                                       # walk round the rectangle, wobbling the corners and edges
        a = 2 * math.pi * i / n + rng.uniform(-0.12, 0.12)
        rx, ry = w / 2, h / 2
        k = 1 / max(abs(math.cos(a)) / rx, abs(math.sin(a)) / ry, 1e-6)
        k *= rng.uniform(0.90, 1.0)
        pts.append((cw / 2 + math.cos(a) * k, ch / 2 + math.sin(a) * k))
    S = 3
    mask = Image.new("L", (cw * S, ch * S), 0)
    ImageDraw.Draw(mask).polygon([(x * S, y * S) for x, y in pts], fill=255)
    outline = mask.filter(ImageFilter.MaxFilter(25))
    back = Image.new("RGBA", (cw * S, ch * S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(back)
    cols = rng.sample(SHAPE_COLOURS, 3)
    # big flat shapes behind: a slanted slab, a circle, a corner wedge
    sx = rng.choice([-1, 1])
    bd.polygon([((cw / 2 + sx * w * 0.10) * S, (ch / 2 - h * 0.46) * S), ((cw / 2 + sx * w * 0.62) * S, (ch / 2 - h * 0.50) * S),
                ((cw / 2 + sx * w * 0.56) * S, (ch / 2 + h * 0.10) * S), ((cw / 2 + sx * w * 0.14) * S, (ch / 2 + h * 0.02) * S)], fill=cols[0] + (255,))
    cx = cw / 2 - sx * w * 0.42
    bd.ellipse(((cx - h * 0.22) * S, (ch / 2 + h * 0.18) * S, (cx + h * 0.22) * S, (ch / 2 + h * 0.62) * S), fill=cols[1] + (255,))
    bd.polygon([((cw / 2 - sx * w * 0.5) * S, (ch / 2 - h * 0.5) * S), ((cw / 2 - sx * w * 0.16) * S, (ch / 2 - h * 0.5) * S), ((cw / 2 - sx * w * 0.5) * S, (ch / 2 - h * 0.12) * S)], fill=cols[2] + (255,))
    ol = Image.new("RGBA", back.size, (255, 255, 255, 0)); ol.putalpha(outline)
    back = Image.alpha_composite(back, ol)
    return mask.resize((cw, ch), Image.LANCZOS), back.resize((cw, ch), Image.LANCZOS), pad


# ------------------------------------------------------------------ reaction cards beside Yuki
@functools.lru_cache(maxsize=64)
def accent_img(kind, size):
    S = 3
    n = int(size * S)
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = n / 100.0

    def card(col, glyph, gcol, rot):
        c = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        cd = ImageDraw.Draw(c)
        cd.rounded_rectangle((22 * u, 8 * u, 78 * u, 92 * u), radius=5 * u, fill=col)
        f = font(int(62 * u), "bold")
        tw_ = cd.textlength(glyph, font=f)
        cd.text((50 * u - tw_ / 2, 50 * u - 36 * u), glyph, font=f, fill=gcol)
        return c.rotate(rot, resample=Image.BICUBIC, center=(n / 2, n / 2))

    if kind == "q":
        im = card((250, 208, 214, 255), "?", (74, 36, 58), 9)
    elif kind == "ex":
        im = card((178, 38, 42, 255), "!", (255, 235, 225), -10)
    elif kind == "zzz":
        for i, (sz, ox, oy, a) in enumerate(((34, 12, 62, 255), (46, 38, 36, 235), (62, 56, 6, 215))):
            f = font(int(sz * u), "bold")
            d.text((ox * u, oy * u), "Z", font=f, fill=(128, 142, 196, a))
    elif kind == "sweat":
        for (cx, cy, r) in ((44, 56, 17), (74, 30, 11)):
            d.polygon([(cx * u, (cy - r * 2.1) * u), ((cx - r * 0.95) * u, (cy - r * 0.2) * u), ((cx + r * 0.95) * u, (cy - r * 0.2) * u)], fill=(120, 190, 240, 255))
            d.ellipse(((cx - r) * u, (cy - r) * u, (cx + r) * u, (cy + r) * u), fill=(120, 190, 240, 255))
            d.ellipse(((cx - r * 0.5) * u, (cy - r * 0.55) * u, (cx - r * 0.1) * u, (cy - r * 0.1) * u), fill=(220, 242, 255, 255))
    elif kind == "anger":
        col = (214, 44, 48, 255)
        for (a, b) in (((18, 36), (44, 36)), ((18, 36), (18, 10)), ((82, 36), (56, 36)), ((82, 36), (82, 10)),
                       ((18, 64), (44, 64)), ((18, 64), (18, 90)), ((82, 64), (56, 64)), ((82, 64), (82, 90))):
            d.line([(a[0] * u, a[1] * u), (b[0] * u, b[1] * u)], fill=col, width=int(9 * u))
    elif kind == "spark":
        for (cx, cy, r) in ((40, 58, 26), (74, 28, 17), (20, 22, 11)):
            pts = [(cx, cy - r), (cx + r * .25, cy - r * .25), (cx + r, cy), (cx + r * .25, cy + r * .25), (cx, cy + r), (cx - r * .25, cy + r * .25), (cx - r, cy), (cx - r * .25, cy - r * .25)]
            d.polygon([(x * u, y * u) for x, y in pts], fill=(255, 205, 70, 255))
    elif kind == "bulb":
        d.ellipse((28 * u, 10 * u, 72 * u, 54 * u), fill=(255, 220, 90, 255))
        d.rounded_rectangle((38 * u, 50 * u, 62 * u, 74 * u), radius=4 * u, fill=(190, 190, 200, 255))
        d.rectangle((40 * u, 76 * u, 60 * u, 82 * u), fill=(140, 140, 156, 255))
        for ang in (-60, -30, 0, 30, 60):
            a = math.radians(ang - 90)
            d.line([(50 * u + math.cos(a) * 36 * u, 32 * u + math.sin(a) * 36 * u), (50 * u + math.cos(a) * 46 * u, 32 * u + math.sin(a) * 46 * u)], fill=(255, 200, 60, 255), width=int(4 * u))
    return im.resize((int(size), int(size)), Image.LANCZOS)


# ------------------------------------------------------------------ the stage
class CollageStage:
    def __init__(self, scene):
        self.sc = scene
        self.seed = scene["seed"]
        self._imgs = {}
        self._base = {}
        self._drawn = {}
        self._dframe = {}

    # ---- pictures
    def _source(self, shot, qi):
        """The picture for panel qi of a shot as an RGB image, or None (then it is drawn)."""
        paths = shot.get("media") or []
        p = paths[qi] if qi < len(paths) else None
        if not p:
            return None
        if p not in self._imgs:
            try:
                im = Image.open(p); im.load(); self._imgs[p] = im.convert("RGB")
            except Exception:
                self._imgs[p] = None
        return self._imgs[p]

    def _drawn_stage(self, shot, qi, pw, ph):
        key = (id(shot), qi)
        if key not in self._drawn:
            from . import director as D, knowledge as K
            from .stage2d import Stage2D
            rng = random.Random(shot["seed"] + qi * 13)
            txt = (shot["queries"][qi] if shot.get("queries") and qi < len(shot["queries"]) else "") + " " + shot["text"] if qi else shot["text"]
            f = D.features(shot["text"] if qi == 0 else (shot["queries"][qi] if qi < len(shot.get("queries", [])) else shot["text"]))
            topic = K.topic_of(txt) or self.sc.get("topic") or "generic"
            style = "toon" if (f["people"] >= 1 or topic in ("city", "history", "food", "body", "brain")) and rng.random() < 0.8 else "flat"
            place, ps = K.place_of(txt)
            env = D.choose_env(rng, topic, style, {}, {}, place if ps >= 2 else None)
            DARK = {"deep_space", "nebula", "solar", "night_city", "data", "ocean_deep", "storm", "ember", "tunnel", "space", "cave", "underwater", "stage", "neural", "micro"}
            if env in DARK:                                              # the page is cream: draw bright pictures
                env = rng.choice(["day_sky", "forest", "ocean_surface", "lab", "arctic", "dusk_desert", "strata"] if style == "flat" else ["street", "room", "hills", "beach", "lab", "forest", "stage"])
            pal = {"ocean": "ocean", "ice": "ice", "nature": "forest"}.get(topic) or rng.choice(["day", "day", "dusk"])
            sub = dict(idx=0, heading="", kind="body", style=style, env=env, pal=pal, tod=None, seed=shot["seed"] + qi, topic=topic, mood=f["mood"], cues={},
                       sentences=[dict(text=txt, spoken=txt, mood="neutral", pause=None, inline=[], para_end=True)], text=txt)
            sshot = dict(sent=[0, 0], text=txt, feat=dict(mood=f["mood"], ents=[e[0] for e in f["ents"]]))
            try:
                (D.toon_shot if style == "toon" else D.flat_shot)(sshot, f, sub, rng, 0, [])
            except Exception:
                sshot.update(template="hero", cam=dict(k="drift", amp=0.6, flip=False), actors=[])
            st2 = Stage2D(sub); st2.no_labels = True
            self._drawn[key] = (st2, sshot)
        return self._drawn[key]

    def _picture(self, shot, qi, pw, ph, t_rel, dur, t_abs):
        """RGB picture exactly pw x ph for panel qi at this moment (Ken Burns on stills; live drawing for drawn pictures)."""
        src = self._source(shot, qi)
        u = clamp(t_rel / max(0.5, dur))
        if src is not None:
            key = (id(src), pw, ph)
            if key not in self._base:
                ar = pw / ph
                sw, sh_ = src.size
                if sw / sh_ > ar:
                    nw = int(sh_ * ar); box = ((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh_)
                else:
                    nh = int(sw / ar); box = (0, (sh_ - nh) // 2, sw, (sh_ - nh) // 2 + nh)
                self._base[key] = src.crop(box).resize((int(pw * 1.16), int(ph * 1.16)), Image.LANCZOS)
            base = self._base[key]
            kb = shot["kb"]
            z = kb["z0"] + (kb["z1"] - kb["z0"]) * ease_in_out(u)
            bw, bh = base.size
            ww, wh = bw / (z * 1.16), bh / (z * 1.16)
            cx = bw / 2 + kb["dx"] * (bw - ww) * (u - 0.5)
            cy = bh / 2 + kb["dy"] * (bh - wh) * (u - 0.5)
            x0 = clamp(cx - ww / 2, 0, bw - ww); y0 = clamp(cy - wh / 2, 0, bh - wh)
            return base.crop((int(x0), int(y0), int(x0 + ww), int(y0 + wh))).resize((pw, ph), Image.BILINEAR)
        stage, sshot = self._drawn_stage(shot, qi, pw, ph)
        q = round(t_abs * 12) / 12.0                                   # drawn pictures move at 12 fps (half the work)
        fkey = (id(shot), qi, q)
        if fkey not in self._dframe:
            if len(self._dframe) > 6:
                self._dframe.clear()
            im = stage.frame(sshot, max(0.0, q - 0.0) % 40.0, 40.0, 0.0, 0.0, q).convert("RGB")
            ar = pw / ph
            if W / H > ar:
                nw = int(H * ar); im = im.crop(((W - nw) // 2, 0, (W - nw) // 2 + nw, H))
            else:
                nh = int(W / ar); im = im.crop((0, (H - nh) // 2, W, (H - nh) // 2 + nh))
            self._dframe[fkey] = im.resize((pw, ph), Image.BILINEAR)
        return self._dframe[fkey]

    # ---- entrance animation of the page content
    @staticmethod
    def _enter(kind, t, side):
        """-> (scale, dx, dy, alpha) for content that entered `t` seconds ago."""
        if kind == "pop":
            p = clamp(t / 0.30); return (0.86 + 0.14 * ease_back(p), 0, 0, clamp(t / 0.12))
        if kind == "slide":
            p = ease_out(clamp(t / 0.34)); return (1.0, (1 - p) * (260 if side == "r" else -260), 0, clamp(t / 0.14))
        if kind == "rise":
            p = ease_out(clamp(t / 0.34)); return (1.0, 0, (1 - p) * 90, clamp(t / 0.16))
        if kind == "fade":
            return (1.0, 0, 0, ease_in_out(clamp(t / 0.45)))
        return (1.0 + 0.03 * (1 - clamp(t / 0.16)), 0, 0, 1.0)

    # ---- one panel with its treatment
    def _panel(self, frame, shot, qi, rect, t_rel, dur, t_abs, ent):
        x, y, pw, ph = rect
        sc_, dx, dy, al = ent
        treat = shot["treat"] if shot["layout"] != "fullbleed" else "bleed"
        rng = random.Random(shot["seed"] + qi)
        if treat == "bleed":
            pic = self._picture(shot, qi, pw, ph, t_rel, dur, t_abs).convert("RGBA")
            paste(frame, pic, 0, 0, al)
            return
        inner_pad = 0
        colour = PANEL_COLOURS[(shot["colour"] + qi) % len(PANEL_COLOURS)]
        if treat == "color":
            inner_pad = 22
        ipw, iph = pw - inner_pad * 2, ph - inner_pad * 2
        pic = self._picture(shot, qi, ipw, iph, t_rel, dur, t_abs).convert("RGBA")
        layer = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        if treat == "frame":
            pic.putalpha(round_mask(ipw, iph, 6)); layer.alpha_composite(pic, (0, 0))
        elif treat == "color":
            bg = Image.new("RGBA", (pw, ph), colour + (255,)); bg.putalpha(round_mask(pw, ph, 14)); layer.alpha_composite(bg)
            pic.putalpha(round_mask(ipw, iph, 8)); layer.alpha_composite(pic, (inner_pad, inner_pad))
            d = ImageDraw.Draw(layer)
            d.rounded_rectangle((1, 1, pw - 2, ph - 2), radius=14, outline=shade(colour, 0.45) + (255,), width=3)
        elif treat == "sticker":
            ring = 10
            pic2 = pic.resize((ipw - ring * 2, iph - ring * 2), Image.BILINEAR)
            white = Image.new("RGBA", (pw, ph), (255, 252, 246, 255)); white.putalpha(round_mask(pw, ph, 14)); layer.alpha_composite(white)
            pic2.putalpha(round_mask(pic2.width, pic2.height, 8)); layer.alpha_composite(pic2, (ring + inner_pad, ring + inner_pad))
        elif treat == "blob":
            mask, back, pad = blob_parts(pw, ph, shot["seed"] + qi)
            big = Image.new("RGBA", (pw + pad * 2, ph + pad * 2), (0, 0, 0, 0))
            big.alpha_composite(back)
            full = pic.resize((pw, ph), Image.BILINEAR)
            cut = Image.new("RGBA", big.size, (0, 0, 0, 0)); cut.paste(full, (pad, pad))
            cut.putalpha(ImageChops.multiply(cut.getchannel("A"), mask))
            big.alpha_composite(cut)
            layer = big
        lw, lh = layer.size
        s = sc_ * (1.0 + 0.012 * math.sin(t_abs * 1.1 + qi))
        if abs(s - 1) > 1e-3:
            layer = layer.resize((max(1, int(lw * s)), max(1, int(lh * s))), Image.BILINEAR)
        ox = x + pw / 2 - layer.width / 2 + dx
        oy = y + ph / 2 - layer.height / 2 + dy
        if treat in ("frame", "color", "sticker"):
            sh, pad = shadow_img(pw, ph, 12, 14, 62)
            if abs(s - 1) > 1e-3:
                sh = sh.resize((int(sh.width * s), int(sh.height * s)), Image.BILINEAR); pad = int(pad * s)
            paste(frame, sh, ox - pad + 3, oy - pad + 9, al)
        rot = {"sticker": (-1.6, 1.4), "blob": (-1.0, 1.0)}.get(treat)
        if rot:
            layer = layer.rotate(rot[qi % 2], resample=Image.BICUBIC, expand=True)
            ox -= (layer.width - lw * s) / 2; oy -= (layer.height - lh * s) / 2
        paste(frame, layer, ox, oy, al)
        if treat == "blob" and shot.get("face") in ("worried", "curious", "shocked") and t_rel > 0.25:
            self._doodles(frame, ox, oy, pw, ph, shot, t_rel, t_abs)

    def _doodles(self, frame, ox, oy, pw, ph, shot, t_rel, t_abs):
        """Scribbled ? ! # @ marks floating by a confused head (paper-collage detail)."""
        rng = random.Random(shot["seed"])
        f = font(52, "bold")
        d_img = Image.new("RGBA", (260, 120), (0, 0, 0, 0))
        dd = ImageDraw.Draw(d_img)
        for i, g in enumerate(("?", "#", "@", "!")):
            col = (40, 40, 48, 255) if i % 2 == 0 else (30, 120, 160, 255)
            dd.text((12 + i * 56, 14 + 18 * math.sin(i * 2 + t_abs * 2)), g, font=f, fill=col)
        paste(frame, d_img, ox + pw * 0.36, oy - 26, clamp((t_rel - 0.25) / 0.2))

    # ---- text kinds
    def _title(self, frame, shot, geo, t_rel, ent):
        tx, ty, tw_, th = geo["text"]
        txt = shot["title"] or shot["text"]
        n = int(len(txt) * clamp(t_rel / 0.55) + 0.999)
        shown = txt[:max(1, n)]
        size = 88 if len(txt) <= 14 else 72 if len(txt) <= 22 else 58
        f = font(size, "medium")
        im = Image.new("RGBA", (tw_, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        w_ = d.textlength(shown, font=f)
        full_w = d.textlength(txt, font=f)
        d.text(((tw_ - full_w) / 2, (th - size) / 2 - 8), shown, font=f, fill=INK)
        paste(frame, im, tx, ty, ent[3])

    def _stat(self, frame, shot, geo, t_rel, ent):
        from .stage2d import count_text
        tx, ty, tw_, th = geo["text"]
        st = shot["stat"] or dict(display="", sub="")
        num = count_text(st["display"], clamp(t_rel / 1.1))
        size = 190 if len(num) <= 6 else 140 if len(num) <= 10 else 100
        f = font(size, "bold")
        im = Image.new("RGBA", (tw_, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        col = shade(PANEL_COLOURS[shot["colour"] % len(PANEL_COLOURS)], -0.38)
        w_ = d.textlength(num, font=f)
        d.text(((tw_ - w_) / 2, 40), num, font=f, fill=col)
        if st["sub"]:
            f2 = font(48, "medium")
            w2 = d.textlength(st["sub"], font=f2)
            d.text(((tw_ - w2) / 2, 40 + size * 1.35), st["sub"], font=f2, fill=INK)
        paste(frame, im, tx, ty + (1 - ease_out(clamp(t_rel / 0.4))) * 30, ent[3])

    def _icons(self, frame, shot, t_rel, dur, t_abs):
        from . import entities as E, flat_env as F
        items = shot["icons"][:3]
        n = len(items)
        xs = {1: [1020], 2: [230, 1050], 3: [190, 1090, 880]}[max(1, n)]
        ys = {1: 340, 2: 330, 3: 330}[max(1, n)]
        pal = F.PALETTES["day"]
        for i, it in enumerate(items):
            t0 = 0.15 + i * max(0.4, min(1.1, dur * 0.28))
            lt = t_rel - t0
            if lt <= 0:
                continue
            p = ease_back(clamp(lt / 0.4))
            cx, cy = xs[i], ys - (170 if (n == 3 and i == 2) else 0)
            cv = Cv(300, 300, 2)
            try:
                E.draw_entity(cv, it["entity"], 150, 130, 190 * max(0.05, p), t_abs, pal, shot["seed"] + i)
            except Exception:
                pass
            im = cv.image()
            f = font(40, "medium")
            lw = int(ImageDraw.Draw(Image.new("L", (4, 4))).textlength(it["label"], font=f)) + 20
            li = Image.new("RGBA", (lw, 60), (0, 0, 0, 0)); ImageDraw.Draw(li).text((10, 6), it["label"], font=f, fill=INK)
            paste(frame, im, cx - 150, cy - 150 + math.sin(t_abs * 1.6 + i) * 5, clamp(lt / 0.15))
            paste(frame, li, cx - lw / 2, cy + 82, clamp((lt - 0.1) / 0.2))

    # ---- Yuki
    def _yuki(self, frame, shot, geo, t_rel, mouth, t_abs):
        x, fy, s = geo["yuki"]
        if shot["layout"] in ("icons",):
            x = 640
        blend = clamp(t_rel / 0.30)
        prev = shot.get("prev") or {}
        pp = prev.get("pose")
        if prev.get("flip") != shot["flip"]:
            pp = None
        hop = clamp(t_rel / 0.45) if (shot.get("hop") and t_rel < 0.45) else 0.0
        s = round(s * 50) / 50.0
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ox, oy = Y.draw_figure(layer, x, fy, s, pose=shot["pose"], prev_pose=pp, blend=blend, t=t_abs, face=shot["face"], amp=mouth,
                               gaze=shot["gaze"], tilt=shot["tilt"], flip=shot["flip"], hop=hop)
        if shot["layout"] == "fullbleed":                            # a soft paper-white halo so she reads on a busy picture
            a = layer.getchannel("A").filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.GaussianBlur(5))
            halo = Image.new("RGBA", (W, H), (250, 246, 238, 0)); halo.putalpha(a.point(lambda v: min(255, int(v * 1.15))))
            frame.alpha_composite(halo)
        frame.alpha_composite(layer)
        # reaction cards
        head_x, head_y = ox + 240 * s, oy + 190 * s
        dirx = -1 if shot["flip"] else 1
        for i, acc in enumerate(shot.get("accents", [])[:2]):
            lt = t_rel - 0.18 - i * 0.14
            if lt <= 0:
                continue
            p = ease_back(clamp(lt / 0.32))
            size = int(max(24, 150 * s * p))
            im = accent_img(acc, max(24, int(round(size / 8.0)) * 8))
            wob = math.sin(t_abs * 4.0 + i) * 4
            im = im.rotate(wob, resample=Image.BICUBIC)
            ax = head_x + dirx * (180 + i * 70) * s - im.width / 2
            ay = head_y - (170 + (i % 2) * 20) * s - im.height / 2 + math.sin(t_abs * 2.0 + i) * 4
            paste(frame, im, ax, ay, clamp(lt / 0.12))

    # ---- one frame
    def frame(self, shot, t_rel, dur, mouth=0.0, amp=0.0, t_abs=0.0):
        frame = paper().copy()
        geo = geometry(shot["layout"], shot["side"])
        ent = self._enter(shot["enter"], t_rel, shot["side"])
        layout = shot["layout"]
        if layout in ("full", "mid", "center", "split", "fullbleed"):
            for qi, rect in enumerate(geo["panels"]):
                self._panel(frame, shot, qi, rect, t_rel, dur, t_abs, ent if qi == 0 else self._enter(shot["enter"], max(0.0, t_rel - 0.12), shot["side"]))
        elif layout == "title":
            self._title(frame, shot, geo, t_rel, ent)
            x, y, pw, ph = geo["panels"][0]
            pic = self._picture(shot, 0, pw, ph, t_rel, dur, t_abs).convert("RGBA")
            pic.putalpha(round_mask(pw, ph, 18))
            sc_, dx, dy, al = self._enter("rise" if shot["enter"] in ("cut", "slide") else shot["enter"], max(0.0, t_rel - 0.18), shot["side"])
            paste(frame, pic, x + dx, y + dy, al)
        elif layout == "stat":
            self._stat(frame, shot, geo, t_rel, ent)
        elif layout == "icons":
            self._icons(frame, shot, t_rel, dur, t_abs)
        self._yuki(frame, shot, geo, t_rel, float(mouth), t_abs)
        return frame
