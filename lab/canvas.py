"""Small drawing toolkit on top of Pillow: supersampled canvas, gradients, glows, colour helpers."""
import functools, math
import numpy as np
from PIL import Image, ImageDraw, ImageChops, ImageFilter


# ------------------------------------------------------------------ colours
def hexc(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def shade(c, k):
    """k > 0 lightens toward white, k < 0 darkens toward black (and a touch toward blue, so shadows stay colourful)."""
    if k >= 0:
        return mix(c, (255, 255, 255), k)
    return mix(c, (int(c[0] * 0.25), int(c[1] * 0.25), int(c[2] * 0.45 + 12)), -k)


def hue_shift(c, deg):
    import colorsys
    r, g, b = [x / 255 for x in c[:3]]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb((h + deg / 360) % 1, l, s)
    return (int(r * 255), int(g * 255), int(b * 255))


def lum(c):
    return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255


def ease_out(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def ease_in_out(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def ease_back(p):
    p = max(0.0, min(1.0, p))
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def ease_elastic(p):
    p = max(0.0, min(1.0, p))
    if p in (0, 1):
        return p
    return 2 ** (-9 * p) * math.sin((p * 10 - 0.75) * (2 * math.pi) / 3) + 1


# ------------------------------------------------------------------ cached gradient / glow sprites
@functools.lru_cache(maxsize=64)
def _vgrad_arr(h, top, bot):
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    a = np.array(top, np.float32)[None, :]
    b = np.array(bot, np.float32)[None, :]
    return (a + (b - a) * t).astype(np.uint8)


def vgrad(w, h, top, bot):
    col = _vgrad_arr(int(h), tuple(top[:3]), tuple(bot[:3]))
    arr = np.repeat(col[:, None, :], int(w), axis=1)
    return Image.fromarray(arr, "RGB")


def hgrad(w, h, left, right):
    return vgrad(h, w, left, right).transpose(Image.TRANSPOSE)


@functools.lru_cache(maxsize=256)
def radial_sprite(r, color, strength=1.0, power=2.0):
    """Soft round glow, side 2r, RGBA with alpha fading to the edge."""
    r = max(2, int(r))
    y, x = np.mgrid[-r:r, -r:r].astype(np.float32)
    d = np.sqrt(x * x + y * y) / r
    a = np.clip(1 - d, 0, 1) ** power * strength
    arr = np.zeros((2 * r, 2 * r, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color[:3]
    arr[..., 3] = np.clip(a * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


@functools.lru_cache(maxsize=64)
def radial_grad(w, h, inner, outer, cx=0.5, cy=0.5, rad=0.75):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((x / w - cx) * (w / max(w, h))) ** 2 + ((y / h - cy) * (h / max(w, h))) ** 2) / rad
    d = np.clip(d, 0, 1)[..., None]
    a = np.array(inner[:3], np.float32)[None, None, :]
    b = np.array(outer[:3], np.float32)[None, None, :]
    return Image.fromarray((a + (b - a) * d).astype(np.uint8), "RGB")


@functools.lru_cache(maxsize=128)
def circle_mask(size_w, size_h):
    m = Image.new("L", (size_w * 2, size_h * 2), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size_w * 2 - 1, size_h * 2 - 1), fill=255)
    return m.resize((size_w, size_h), Image.LANCZOS)


def paste_alpha(dst, src, x, y, alpha=1.0):
    """alpha_composite src onto dst (RGBA) at (x, y), clipped, with an extra global alpha."""
    x, y = int(round(x)), int(round(y))
    if alpha < 0.999:
        a = src.getchannel("A").point(lambda v, k=alpha: int(v * k))
        src = src.copy(); src.putalpha(a)
    dw, dh = dst.size
    sw, sh = src.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dw, x + sw), min(dh, y + sh)
    if x1 <= x0 or y1 <= y0:
        return
    dst.alpha_composite(src.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


# ------------------------------------------------------------------ the canvas
class Cv:
    """A supersampled RGBA drawing surface. All coordinates are logical (1280 x 720 space); `ss` is the supersample
    factor. `image()` returns the downsampled result."""

    def __init__(self, w, h, ss=2, bg=(0, 0, 0, 0)):
        self.w, self.h, self.ss = int(w), int(h), ss
        if isinstance(bg, Image.Image):
            self.im = bg.convert("RGBA")
        else:
            self.im = Image.new("RGBA", (int(w * ss), int(h * ss)), bg if len(bg) == 4 else tuple(bg) + (255,))
        self.d = ImageDraw.Draw(self.im)

    # --- helpers
    def _pts(self, pts):
        s = self.ss
        return [(x * s, y * s) for x, y in pts]

    def _layer(self, bbox, alpha, fn):
        """draw fn(draw, ox, oy) onto a small layer and composite with `alpha` (0-255 fill alpha handled by caller)."""
        s = self.ss
        x0, y0, x1, y1 = [int(v * s) for v in bbox]
        x0, y0 = max(0, x0 - 2), max(0, y0 - 2)
        x1, y1 = min(self.im.width, x1 + 2), min(self.im.height, y1 + 2)
        if x1 <= x0 or y1 <= y0:
            return
        lay = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        fn(ImageDraw.Draw(lay), x0, y0)
        self.im.alpha_composite(lay, (x0, y0))

    # --- primitives
    def poly(self, pts, fill, alpha=255):
        if len(pts) < 3:
            return
        fill = tuple(fill[:3])
        if alpha >= 255:
            self.d.polygon(self._pts(pts), fill=fill + (255,))
        else:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            s = self.ss
            self._layer((min(xs), min(ys), max(xs), max(ys)), alpha,
                        lambda d, ox, oy: d.polygon([(x * s - ox, y * s - oy) for x, y in pts], fill=fill + (int(alpha),)))

    def ellipse(self, cx, cy, rx, ry, fill, alpha=255):
        s = self.ss
        box = (cx - rx, cy - ry, cx + rx, cy + ry)
        if alpha >= 255:
            self.d.ellipse([box[0] * s, box[1] * s, box[2] * s, box[3] * s], fill=tuple(fill[:3]) + (255,))
        else:
            self._layer(box, alpha, lambda d, ox, oy: d.ellipse([box[0] * s - ox, box[1] * s - oy, box[2] * s - ox, box[3] * s - oy],
                                                                  fill=tuple(fill[:3]) + (int(alpha),)))

    def circle(self, cx, cy, r, fill, alpha=255):
        self.ellipse(cx, cy, r, r, fill, alpha)

    def ring(self, cx, cy, r, width, fill, alpha=255):
        s = self.ss
        box = (cx - r - width, cy - r - width, cx + r + width, cy + r + width)

        def fn(d, ox, oy):
            d.ellipse([(cx - r) * s - ox, (cy - r) * s - oy, (cx + r) * s - ox, (cy + r) * s - oy],
                      outline=tuple(fill[:3]) + (int(alpha),), width=max(1, int(width * s)))
        self._layer(box, alpha, fn)

    def rect(self, x0, y0, x1, y1, fill, r=0, alpha=255):
        s = self.ss
        fillc = tuple(fill[:3]) + (int(alpha),)
        if alpha >= 255:
            if r > 0:
                self.d.rounded_rectangle([x0 * s, y0 * s, x1 * s, y1 * s], radius=r * s, fill=fillc)
            else:
                self.d.rectangle([x0 * s, y0 * s, x1 * s, y1 * s], fill=fillc)
        else:
            def fn(d, ox, oy):
                box = [x0 * s - ox, y0 * s - oy, x1 * s - ox, y1 * s - oy]
                if r > 0:
                    d.rounded_rectangle(box, radius=r * s, fill=fillc)
                else:
                    d.rectangle(box, fill=fillc)
            self._layer((x0, y0, x1, y1), alpha, fn)

    def line(self, p0, p1, width, fill, alpha=255, cap=True):
        """Thick line as a capsule."""
        x0, y0 = p0; x1, y1 = p1
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        if L < 1e-6:
            if cap:
                self.circle(x0, y0, width / 2, fill, alpha)
            return
        nx, ny = -dy / L * width / 2, dx / L * width / 2
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], fill, alpha)
        if cap:
            self.circle(x0, y0, width / 2, fill, alpha)
            self.circle(x1, y1, width / 2, fill, alpha)

    def polyline(self, pts, width, fill, alpha=255, cap=True):
        for a, b in zip(pts[:-1], pts[1:]):
            self.line(a, b, width, fill, alpha, cap)

    def arc_poly(self, cx, cy, r0, r1, a0, a1, fill, alpha=255, n=28):
        """Filled annular sector (angles in degrees, 0 = right, clockwise on screen)."""
        outer = [(cx + r1 * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r1 * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        inner = [(cx + r0 * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r0 * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n, -1, -1)]
        self.poly(outer + inner, fill, alpha)

    def glow(self, cx, cy, r, color, strength=1.0, power=2.0):
        s = self.ss
        sp = radial_sprite(int(r * s), tuple(color[:3]), round(strength, 2), power)
        paste_alpha(self.im, sp, cx * s - sp.width / 2, cy * s - sp.height / 2)

    def blit(self, img, x, y, alpha=1.0, scale=1.0):
        """Paste an RGBA image given at *logical* resolution (img.size == logical size) at logical (x, y)."""
        s = self.ss
        if abs(scale - 1.0) > 1e-3:
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
        paste_alpha(self.im, img, x * s, y * s, alpha)

    def blit_hi(self, img, x, y, alpha=1.0):
        """Paste an RGBA image that is already supersampled (img.size == logical*ss)."""
        paste_alpha(self.im, img, x * self.ss, y * self.ss, alpha)

    def masked_layer(self, bbox, draw_fn, mask_fn):
        """draw_fn(Cv) paints onto a temp canvas the size of bbox; mask_fn(Cv-sized L image maker)."""
        x0, y0, x1, y1 = bbox
        lay = Cv(x1 - x0, y1 - y0, self.ss)
        draw_fn(lay)
        mask = Image.new("L", lay.im.size, 0)
        mask_fn(ImageDraw.Draw(mask), self.ss)
        a = ImageChops.multiply(lay.im.getchannel("A"), mask)
        lay.im.putalpha(a)
        paste_alpha(self.im, lay.im, x0 * self.ss, y0 * self.ss)

    def image(self):
        if self.ss == 1:
            return self.im
        return self.im.resize((self.w, self.h), Image.BOX if self.ss == 2 else Image.LANCZOS)

    def hi(self):
        return self.im


def sphere_sprite(r, base, light=(-0.45, -0.5), ss=2, bands=None, rim=None, shadow_k=-0.45, hi_k=0.28):
    """Flat-shaded sphere as an RGBA sprite (side 2r): base disc, crescent shadow, small highlight, optional bands."""
    S = int(2 * r * ss)
    cv = Cv(2 * r, 2 * r, ss)
    cv.ellipse(r, r, r, r, base)
    # optional bands (clipped to the disc)
    if bands:
        for (y0, y1, col) in bands:
            cv.rect(0, 2 * r * y0, 2 * r, 2 * r * y1, col)
    # shadow crescent = disc minus offset disc
    m_disc = Image.new("L", (S, S), 0); ImageDraw.Draw(m_disc).ellipse((0, 0, S - 1, S - 1), fill=255)
    off = (light[0] * r * 0.5 * ss, light[1] * r * 0.5 * ss)
    m_off = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m_off).ellipse((off[0], off[1], S - 1 + off[0], S - 1 + off[1]), fill=255)
    crescent = ImageChops.subtract(m_disc, m_off)
    shadow = Image.new("RGBA", (S, S), shade(base, shadow_k) + (255,))
    shadow.putalpha(ImageChops.multiply(crescent, Image.new("L", (S, S), 150)))
    cv.im.alpha_composite(shadow)
    # highlight
    hx, hy = r + light[0] * r * 0.52, r + light[1] * r * 0.52
    cv.ellipse(hx, hy, r * 0.17, r * 0.12, shade(base, hi_k), alpha=140)
    # clip everything to the disc
    cv.im.putalpha(ImageChops.multiply(cv.im.getchannel("A"), m_disc))
    if rim:
        cv.ring(r, r, r - 1, 2, rim, 90)
    return cv.im  # supersampled sprite
