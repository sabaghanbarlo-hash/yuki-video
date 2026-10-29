"""Blocky 3D worlds ("Minecraft-style") rendered by a small software engine: no game assets, no GPU, no downloads.

    world = build_world(env, seed, time_of_day)            # terrain, trees, buildings ... as a grid of blocks
    img   = render(world, cam, t, models=[...], size=(1280, 720))      # PIL RGB image

* Terrain is a numpy grid of block ids; only the exposed faces are kept (a few thousand quads).
* Everything that moves (people, animals, rockets, planets, meteors ...) is a Model: a set of coloured quads that is
  transformed every frame (see `human`, `critter`, `prop`).
* Rendering = perspective projection with numpy, back-face + frustum culling, painter's sort, Pillow polygons.
  Face shading, distance fog, glowing blocks, animated water/lava and "pixel" speckles up close give the blocky look.
"""
import functools, math
import numpy as np
from PIL import Image, ImageDraw

W, H = 1280, 720
NX, NY, NZ = 64, 44, 64

# ------------------------------------------------------------------ blocks
# id: (top colour, side colour, bottom colour, jitter, emissive, grass-band colour for the side faces)
B = {}
_names = {}


def _blk(name, top, side=None, bottom=None, jit=0.07, emis=0.0, band=None):
    i = len(B) + 1
    side = side or top
    B[i] = dict(top=np.array(top, float), side=np.array(side, float), bottom=np.array(bottom or side, float), jit=jit, emis=emis,
                band=None if band is None else np.array(band, float))
    _names[name] = i
    return i


AIR = 0
GRASS = _blk("grass", (104, 168, 66), (134, 98, 66), (120, 86, 58), 0.08, band=(104, 168, 66))
DIRT = _blk("dirt", (134, 98, 66), jit=0.07)
STONE = _blk("stone", (128, 128, 134), jit=0.08)
SAND = _blk("sand", (226, 208, 150), jit=0.05)
WATER = _blk("water", (52, 118, 214), jit=0.0)
SNOW = _blk("snow", (246, 250, 255), (236, 244, 252), jit=0.03)
ICE = _blk("ice", (170, 214, 246), jit=0.04)
LOG = _blk("log", (126, 96, 56), (104, 78, 46), jit=0.06)
LEAF = _blk("leaf", (62, 140, 54), jit=0.12)
SPRUCE = _blk("spruce", (38, 98, 70), jit=0.1)
LAVA = _blk("lava", (255, 122, 24), jit=0.14, emis=1.0)
SANDSTONE = _blk("sandstone", (214, 186, 126), (206, 176, 116), jit=0.05)
CACTUS = _blk("cactus", (66, 148, 72), (54, 128, 62), jit=0.06)
BASALT = _blk("basalt", (62, 58, 66), jit=0.1)
CRYSTAL = _blk("crystal", (120, 240, 255), jit=0.12, emis=0.85)
CONCRETE = _blk("concrete", (156, 160, 172), (146, 150, 164), jit=0.06)
WINDOW_ON = _blk("window_on", (255, 226, 132), jit=0.1, emis=0.9)
WINDOW_OFF = _blk("window_off", (60, 78, 112), jit=0.08)
ASPHALT = _blk("asphalt", (62, 64, 74), jit=0.04)
CORAL1 = _blk("coral1", (240, 98, 130), jit=0.1)
CORAL2 = _blk("coral2", (170, 110, 235), jit=0.1)
CORAL3 = _blk("coral3", (255, 170, 80), jit=0.1)
KELP = _blk("kelp", (40, 160, 96), jit=0.1)
CLOUD = _blk("cloud", (252, 252, 255), (238, 242, 252), jit=0.02)
GRAVEL = _blk("gravel", (140, 134, 128), jit=0.12)
BRICK = _blk("brick", (176, 84, 66), jit=0.08)
GOLD = _blk("gold", (255, 214, 70), jit=0.05, emis=0.3)
PLANKS = _blk("planks", (178, 138, 86), jit=0.06)
ASH = _blk("ash", (92, 86, 92), jit=0.1)
MOSS = _blk("moss", (60, 116, 70), jit=0.1)
GLASS = _blk("glass", (170, 220, 240), jit=0.03)
NAME = dict(_names)

# lookup tables for vectorised face building
_TOP = np.zeros((len(B) + 1, 3)); _SIDE = np.zeros_like(_TOP); _BOT = np.zeros_like(_TOP)
_JIT = np.zeros(len(B) + 1); _EMI = np.zeros(len(B) + 1); _BAND = np.zeros_like(_TOP); _HASBAND = np.zeros(len(B) + 1, bool)
for _i, _b in B.items():
    _TOP[_i], _SIDE[_i], _BOT[_i], _JIT[_i], _EMI[_i] = _b["top"], _b["side"], _b["bottom"], _b["jit"], _b["emis"]
    if _b["band"] is not None:
        _BAND[_i] = _b["band"]; _HASBAND[_i] = True
for _n in ("snow",):
    _BAND[SNOW] = _TOP[SNOW]


# ------------------------------------------------------------------ face sets
OFFS = np.array([
    [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
    [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],
    [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],
    [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
    [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
    [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],
], float)
NORM = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)], float)
DIRS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]


class FaceSet:
    """N quads: P (N,4,3) corners, Nn (N,3) normals, C (N,3) colours, E (N,) glow 0..1 (1 = unshaded), K (N,) kind (0 plain, 1 water, 2 lava, 3 decal)."""

    def __init__(self, P, Nn, C, E, K, S=None):
        self.P, self.Nn, self.C, self.E, self.K, self.S = P, Nn, C, E, K, S

    @staticmethod
    def empty():
        return FaceSet(np.zeros((0, 4, 3)), np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0), np.zeros(0, np.int8))

    def __len__(self):
        return len(self.P)

    @staticmethod
    def cat(sets):
        sets = [s for s in sets if s is not None and len(s)]
        if not sets:
            return FaceSet.empty()
        return FaceSet(np.concatenate([s.P for s in sets]), np.concatenate([s.Nn for s in sets]), np.concatenate([s.C for s in sets]),
                       np.concatenate([s.E for s in sets]), np.concatenate([s.K for s in sets]))

    def transformed(self, R=None, pos=(0, 0, 0), scale=1.0):
        P = self.P * scale
        Nn = self.Nn
        if R is not None:
            P = P @ R.T
            Nn = Nn @ R.T
        return FaceSet(P + np.asarray(pos, float), Nn, self.C, self.E, self.K)

    def tinted(self, col, k):
        return FaceSet(self.P, self.Nn, self.C * (1 - k) + np.asarray(col, float) * k, self.E, self.K)


def _hash3(i, j, k, d, seed=0):
    h = (i.astype(np.int64) * 73856093) ^ (j.astype(np.int64) * 19349663) ^ (k.astype(np.int64) * 83492791) ^ (np.int64(d + 1) * 2654435761) ^ np.int64(seed * 40503)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFF).astype(np.float64) / 65535.0


def faces_from_grid(grid, seed=0, origin=(0, 0, 0), transparent=(WATER,)):
    """Exposed faces of every block (water only shows its top and faces next to air)."""
    nx, ny, nz = grid.shape
    solid = grid != AIR
    wmask = np.zeros(grid.shape, bool)
    for tb in transparent:
        wmask |= grid == tb
    parts = []
    pad = np.zeros((nx + 2, ny + 2, nz + 2), np.uint8)
    pad[1:-1, 1:-1, 1:-1] = grid
    for d, (dx, dy, dz) in enumerate(DIRS):
        nb = pad[1 + dx:1 + dx + nx, 1 + dy:1 + dy + ny, 1 + dz:1 + dz + nz]
        nb_air = nb == AIR
        nb_water = np.zeros_like(nb_air)
        for tb in transparent:
            nb_water |= nb == tb
        vis = solid & (nb_air | (nb_water & ~wmask))
        if d == 3:
            vis &= (np.arange(ny)[None, :, None] > 0)             # nobody sees the underside of the world floor
        idx = np.argwhere(vis)
        if not len(idx):
            continue
        i, j, k = idx[:, 0], idx[:, 1], idx[:, 2]
        ids = grid[i, j, k]
        base = _TOP[ids] if d == 2 else (_BOT[ids] if d == 3 else _SIDE[ids])
        jit = (_hash3(i, j, k, d, seed) - 0.5) * 2 * _JIT[ids]
        col = np.clip(base * (1 + jit[:, None]), 0, 255)
        P = idx[:, None, :].astype(float) + OFFS[d][None] + np.asarray(origin, float)
        emis = _EMI[ids]
        kind = np.zeros(len(idx), np.int8)
        kind[np.isin(ids, [w for w in transparent])] = 1
        kind[ids == LAVA] = 2
        parts.append(FaceSet(P, np.tile(NORM[d], (len(idx), 1)), col, emis, kind))
        if d in (0, 1, 4, 5):                                       # grass / snow band on the upper part of side faces
            hb = _HASBAND[ids]
            if hb.any():
                sel = np.where(hb)[0]
                P2 = P[sel].copy()
                lo = P2[:, :, 1] < P2[:, :, 1].max(axis=1, keepdims=True) - 0.5
                P2[:, :, 1] = np.where(lo, P2[:, :, 1].max(axis=1, keepdims=True) - 0.28, P2[:, :, 1])
                P2 += NORM[d] * 0.003
                bc = np.clip(_BAND[ids[sel]] * (1 + jit[sel, None] * 0.8), 0, 255)
                parts.append(FaceSet(P2, np.tile(NORM[d], (len(sel), 1)), bc, np.zeros(len(sel)), np.zeros(len(sel), np.int8)))
    return FaceSet.cat(parts)


def faces_from_cells(cells, scale=1.0, jitter=0.05, seed=0):
    """cells: {(x,y,z): (r,g,b) | (r,g,b,glow)} -> FaceSet (a small voxel model, one quad per exposed face)."""
    keys = set(cells)
    P, Nn, C, E = [], [], [], []
    rng = np.random.default_rng(seed)
    for (x, y, z), c in cells.items():
        glow = c[3] if len(c) > 3 else 0.0
        for d, (dx, dy, dz) in enumerate(DIRS):
            if (x + dx, y + dy, z + dz) in keys:
                continue
            P.append(OFFS[d] + (x, y, z)); Nn.append(NORM[d])
            j = 1 + (rng.random() - 0.5) * 2 * jitter
            C.append(np.clip(np.array(c[:3], float) * j, 0, 255)); E.append(glow)
    if not P:
        return FaceSet.empty()
    P = np.array(P) * scale
    return FaceSet(P, np.array(Nn), np.array(C), np.array(E), np.zeros(len(P), np.int8))


def box_faces(center, size, colors, glow=0.0):
    """One axis-aligned box. colors: one colour or 6 (per face direction +x -x +y -y +z -z)."""
    c = np.asarray(center, float); s = np.asarray(size, float)
    cols = np.asarray(colors, float)
    if cols.ndim == 1:
        cols = np.tile(cols, (6, 1))
    P = (OFFS - 0.5) * s + c
    return FaceSet(P, NORM.copy(), cols.copy(), np.full(6, glow), np.zeros(6, np.int8))


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def limb(center, size, color, pivot, R, glow=0.0):
    """A box rotated about `pivot` by R (3x3)."""
    f = box_faces(center, size, color, glow)
    pv = np.asarray(pivot, float)
    return FaceSet((f.P - pv) @ R.T + pv, f.Nn @ R.T, f.C, f.E, f.K)


# ------------------------------------------------------------------ noise
def _noise2(n, rng, scale):
    g = rng.random((scale + 2, scale + 2))
    xs = np.linspace(0, scale, n, endpoint=False)
    i = xs.astype(int); f = xs - i
    f = f * f * (3 - 2 * f)
    a = g[np.ix_(i, i)]; b = g[np.ix_(i + 1, i)]; c = g[np.ix_(i, i + 1)]; d = g[np.ix_(i + 1, i + 1)]
    fx = f[:, None]; fy = f[None, :]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(n, rng, octaves=((3, 1.0), (6, 0.5), (12, 0.25))):
    out = np.zeros((n, n)); tot = 0
    for sc, amp in octaves:
        out += _noise2(n, rng, sc) * amp; tot += amp
    return out / tot


# ------------------------------------------------------------------ the world
SKY = {   # time of day -> sky top, sky horizon, fog, light tint, sun colour, stars
    "day": dict(top=(76, 150, 240), bot=(190, 224, 255), fog=(190, 224, 255), tint=(1.0, 1.0, 0.97), sun=(255, 244, 190), stars=0, amb=0.55),
    "dusk": dict(top=(60, 40, 120), bot=(255, 150, 90), fog=(240, 150, 110), tint=(1.05, 0.9, 0.82), sun=(255, 170, 90), stars=0.25, amb=0.45),
    "night": dict(top=(6, 8, 30), bot=(26, 32, 80), fog=(18, 22, 56), tint=(0.62, 0.7, 1.0), sun=(210, 224, 255), stars=1, amb=0.5),
    "storm": dict(top=(64, 72, 90), bot=(130, 140, 158), fog=(120, 130, 148), tint=(0.85, 0.9, 1.0), sun=(210, 216, 226), stars=0, amb=0.55),
    "ember": dict(top=(40, 14, 18), bot=(190, 70, 34), fog=(130, 48, 26), tint=(1.1, 0.85, 0.72), sun=(255, 140, 70), stars=0, amb=0.5),
    "cold": dict(top=(120, 176, 232), bot=(228, 242, 255), fog=(220, 236, 250), tint=(0.95, 1.0, 1.05), sun=(255, 252, 235), stars=0, amb=0.58),
    "deep": dict(top=(10, 60, 120), bot=(20, 120, 170), fog=(14, 80, 130), tint=(0.8, 0.95, 1.1), sun=(160, 230, 255), stars=0, amb=0.55),
    "cave": dict(top=(10, 10, 20), bot=(20, 18, 34), fog=(14, 12, 26), tint=(0.9, 0.9, 1.0), sun=(0, 0, 0), stars=0, amb=0.42),
    "space": dict(top=(2, 2, 12), bot=(14, 8, 40), fog=(8, 6, 24), tint=(1.0, 1.0, 1.05), sun=(255, 244, 210), stars=1, amb=0.5),
}


class World:
    def __init__(self, env, seed, tod):
        self.env, self.seed, self.tod = env, seed, tod
        self.sky = dict(SKY[tod])
        self.grid = np.zeros((NX, NY, NZ), np.uint8)
        self.rng = np.random.default_rng(seed * 7919 + 13)
        self.fog_near, self.fog_far = 40.0, 120.0
        self.enclosed = False
        self.sun_dir = np.array([0.5, 0.55, -0.7])
        self.faces = None
        self.deco = []                  # static decorations (FaceSet)
        self.clouds = []                # (FaceSet, speed)
        self.spawn = (NX / 2, 12, NZ / 2)
        self.particles = None           # ("snow"|"ash"|"bubbles"|"rain"|"embers", n)
        self.hm = np.zeros((NX, NZ), int)
        self.water_y = None

    # -------- editing helpers
    def set(self, x, y, z, b):
        if 0 <= x < NX and 0 <= y < NY and 0 <= z < NZ:
            self.grid[x, y, z] = b

    def get(self, x, y, z):
        if 0 <= x < NX and 0 <= y < NY and 0 <= z < NZ:
            return self.grid[x, y, z]
        return AIR

    def fill_ball(self, cx, cy, cz, r, b, only_air=False, rr=None, flat=1.0):
        ri = int(math.ceil(r)) + 1
        for x in range(int(cx) - ri, int(cx) + ri + 1):
            for y in range(int(cy) - ri, int(cy) + ri + 1):
                for z in range(int(cz) - ri, int(cz) + ri + 1):
                    if (x - cx) ** 2 + ((y - cy) / flat) ** 2 + (z - cz) ** 2 <= r * r:
                        if not only_air or self.get(x, y, z) == AIR:
                            self.set(x, y, z, b)

    def column_top(self, x, z):
        col = self.grid[int(x) % NX, :, int(z) % NZ]
        nz = np.nonzero((col != AIR))[0]
        return int(nz.max()) + 1 if len(nz) else 0

    def ground_y(self, x, z):
        """height of the floor at world (x, z) for standing things (water surface counts as ground)."""
        xi, zi = int(np.clip(x, 0, NX - 1)), int(np.clip(z, 0, NZ - 1))
        return float(self.column_top(xi, zi))

    def finish(self):
        self.faces = faces_from_grid(self.grid, self.seed)
        for i in range(len(self.hm.flat)):
            pass
        self.hm = np.array([[self.column_top(x, z) for z in range(NZ)] for x in range(NX)])
        # a handful of slowly drifting cloud slabs
        return self

    # -------- common ingredients
    def tree(self, x, z, kind="oak", h=None):
        y0 = self.column_top(x, z)
        r = self.rng
        if kind == "oak":
            h = h or int(r.integers(4, 6))
            for y in range(h):
                self.set(x, y0 + y, z, LOG)
            for dx in range(-2, 3):
                for dy in range(-1, 3):
                    for dz in range(-2, 3):
                        d = dx * dx + dz * dz + (dy * 1.4) ** 2
                        if d <= 5.6 and (dx or dz or dy > 1) and r.random() > 0.12:
                            if self.get(x + dx, y0 + h - 1 + dy, z + dz) == AIR:
                                self.set(x + dx, y0 + h - 1 + dy, z + dz, LEAF)
        elif kind == "spruce":
            h = h or int(r.integers(6, 9))
            for y in range(h):
                self.set(x, y0 + y, z, LOG)
            for layer in range(h - 1):
                rad = max(0, (h - 2 - layer) // 2)
                for dx in range(-rad, rad + 1):
                    for dz in range(-rad, rad + 1):
                        if abs(dx) + abs(dz) <= rad + 1 and (dx or dz or layer >= h - 3) and layer >= 2:
                            self.set(x + dx, y0 + layer, z + dz, SPRUCE)
            self.set(x, y0 + h, z, SPRUCE)
        elif kind == "palm":
            h = h or int(r.integers(5, 8))
            for y in range(h):
                self.set(x + (1 if y > h - 3 else 0), y0 + y, z, LOG)
            tx = x + 1
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)):
                self.set(tx + dx, y0 + h - (1 if abs(dx) + abs(dz) > 1 else 0), z + dz, LEAF)
            self.set(tx, y0 + h, z, LEAF)
        elif kind == "cactus":
            h = h or int(r.integers(2, 5))
            for y in range(h):
                self.set(x, y0 + y, z, CACTUS)
            if h > 2 and r.random() > 0.4:
                s = 1 if r.random() > 0.5 else -1
                self.set(x + s, y0 + 1, z, CACTUS); self.set(x + s, y0 + 2, z, CACTUS)

    def scatter(self, n, ok, fn, margin=3):
        placed = 0; tries = 0
        while placed < n and tries < n * 25:
            tries += 1
            x, z = int(self.rng.integers(margin, NX - margin)), int(self.rng.integers(margin, NZ - margin))
            if ok(x, z):
                fn(x, z); placed += 1

    def add_clouds(self, n=9, y=None, speed=1.4, white=True):
        r = self.rng
        for _ in range(n):
            cells = {}
            cx, cz = 0, 0
            for _b in range(int(r.integers(4, 9))):
                bx, bz = int(r.integers(-4, 5)), int(r.integers(-2, 3))
                for dx in range(int(r.integers(2, 4))):
                    for dz in range(int(r.integers(2, 4))):
                        cells[(bx + dx, 0, bz + dz)] = (252, 252, 255) if white else (150, 156, 170)
                if r.random() > 0.5:
                    cells[(bx + 1, 1, bz + 1)] = (246, 248, 255) if white else (140, 146, 160)
            fs = faces_from_cells(cells, scale=1.0, jitter=0.02)
            self.clouds.append((fs, (float(r.uniform(-30, NX + 30)), float(y if y is not None else r.uniform(30, 40)), float(r.uniform(-20, NZ + 20))), speed * float(r.uniform(0.6, 1.4))))


def _flat_ground(w, base, top, h, wl=None, sand_shore=True):
    for x in range(NX):
        for z in range(NZ):
            hh = int(h[x, z])
            w.grid[x, 0:max(1, hh - 3), z] = STONE
            w.grid[x, max(1, hh - 3):hh, z] = DIRT
            if wl is not None and hh <= wl + (1 if sand_shore else 0):
                w.grid[x, hh - 1, z] = SAND if sand_shore else DIRT
                w.grid[x, hh: wl + 1, z] = WATER
            else:
                w.grid[x, hh - 1, z] = top


def build_world(env, seed=1, tod=None):
    """env: plains desert snow ocean underwater volcano city cave space islands"""
    tod = tod or {"plains": "day", "desert": "day", "snow": "cold", "ocean": "day", "underwater": "deep", "volcano": "ember", "city": "dusk",
                  "cave": "cave", "space": "space", "islands": "day"}.get(env, "day")
    if tod not in SKY:
        tod = "day"
    w = World(env, int(seed), tod)
    fn = {"plains": _plains, "desert": _desert, "snow": _snow, "ocean": _ocean, "underwater": _underwater, "volcano": _volcano, "city": _city,
          "cave": _cave, "space": _space, "islands": _islands}.get(env, _plains)
    fn(w)
    return w.finish()


def _plains(w):
    r = w.rng
    h = (6 + 10 * fbm(NX, r)).astype(int)
    wl = 9
    _flat_ground(w, STONE, GRASS, h, wl)
    w.water_y = wl + 1
    w.scatter(34, lambda x, z: w.grid[x, h[x, z] - 1, z] == GRASS, lambda x, z: w.tree(x, z, "oak"))
    w.scatter(40, lambda x, z: w.grid[x, h[x, z] - 1, z] == GRASS and w.get(x, h[x, z], z) == AIR,
              lambda x, z: w.set(x, h[x, z], z, [CORAL1, GOLD, CORAL2][int(r.integers(0, 3))]) if r.random() > 0.0 else None)
    w.add_clouds(10)
    w.fog_near, w.fog_far = 46, 130


def _desert(w):
    r = w.rng
    n = fbm(NX, r, ((2, 1.0), (5, 0.5), (11, 0.15)))
    xs = np.arange(NX)
    dunes = 0.5 + 0.5 * np.sin(xs[:, None] * 0.18 + n * 6 + xs[None, :] * 0.05)
    h = (5 + 5 * n + 4 * dunes).astype(int)
    for x in range(NX):
        for z in range(NZ):
            hh = int(h[x, z])
            w.grid[x, 0:max(1, hh - 3), z] = SANDSTONE
            w.grid[x, max(1, hh - 3):hh, z] = SAND
    w.scatter(16, lambda x, z: True, lambda x, z: w.tree(x, z, "cactus"))
    # a stepped pyramid
    px, pz = int(r.integers(36, 50)), int(r.integers(14, 28))
    for lvl in range(9):
        for x in range(px - 9 + lvl, px + 10 - lvl):
            for z in range(pz - 9 + lvl, pz + 10 - lvl):
                y = w.column_top(px, pz) if lvl == 0 else None
    base = int(h[px, pz]) - 1
    for lvl in range(10):
        for x in range(px - 10 + lvl, px + 11 - lvl):
            for z in range(pz - 10 + lvl, pz + 11 - lvl):
                for y in range(base, base + lvl + 1):
                    if y == base + lvl or lvl == 0:
                        w.set(x, y, z, SANDSTONE if lvl < 9 else GOLD)
                    elif w.get(x, y, z) == AIR:
                        w.set(x, y, z, SANDSTONE)
    w.add_clouds(4, speed=0.8)
    w.fog_near, w.fog_far = 50, 140
    w.particles = ("sand", 40)


def _snow(w):
    r = w.rng
    h = (6 + 13 * fbm(NX, r, ((3, 1.0), (7, 0.55), (13, 0.2)))).astype(int)
    for x in range(NX):
        for z in range(NZ):
            hh = int(h[x, z])
            w.grid[x, 0:max(1, hh - 2), z] = STONE
            w.grid[x, max(1, hh - 2):hh, z] = SNOW if hh > 8 else ICE
            if hh <= 8:
                w.grid[x, hh - 1, z] = ICE
            else:
                w.grid[x, hh - 1, z] = SNOW
    w.scatter(40, lambda x, z: h[x, z] > 9, lambda x, z: w.tree(x, z, "spruce"))
    w.add_clouds(7, speed=0.9)
    w.fog_near, w.fog_far = 36, 110
    w.particles = ("snow", 150)


def _ocean(w):
    r = w.rng
    n = fbm(NX, r, ((2, 1.0), (4, 0.5)))
    h = (3 + 11 * np.clip(n - 0.38, 0, 1) * 2.2 + 0.0).astype(int)
    h = np.maximum(h, 3)
    wl = 8
    _flat_ground(w, STONE, SAND, h, wl, sand_shore=True)
    for x in range(NX):
        for z in range(NZ):
            if h[x, z] > wl + 2 and w.grid[x, h[x, z] - 1, z] == SAND:
                w.grid[x, h[x, z] - 1, z] = GRASS
    w.water_y = wl + 1
    w.scatter(6, lambda x, z: w.grid[x, h[x, z] - 1, z] in (GRASS, SAND) and h[x, z] > wl + 1, lambda x, z: w.tree(x, z, "palm"))
    w.add_clouds(8)
    w.fog_near, w.fog_far = 50, 150


def _underwater(w):
    r = w.rng
    h = (3 + 5 * fbm(NX, r, ((3, 1.0), (7, 0.6)))).astype(int)
    for x in range(NX):
        for z in range(NZ):
            hh = int(h[x, z])
            w.grid[x, 0:max(1, hh - 2), z] = STONE
            w.grid[x, max(1, hh - 2):hh, z] = SAND if r.random() > 0.25 else GRAVEL
    for _ in range(30):                                      # coral heads
        cx, cz = int(r.integers(3, NX - 3)), int(r.integers(3, NZ - 3))
        col = [CORAL1, CORAL2, CORAL3][int(r.integers(0, 3))]
        top = w.column_top(cx, cz)
        for _b in range(int(r.integers(5, 14))):
            x, z = cx + int(r.integers(-2, 3)), cz + int(r.integers(-2, 3))
            for y in range(int(r.integers(1, 5))):
                w.set(x, w.column_top(x, z) + 0, z, col)
    for _ in range(45):                                      # kelp
        x, z = int(r.integers(2, NX - 2)), int(r.integers(2, NZ - 2))
        y0 = w.column_top(x, z)
        for y in range(int(r.integers(4, 11))):
            w.set(x, y0 + y, z, KELP)
    for _ in range(8):                                       # rocks
        x, z = int(r.integers(4, NX - 4)), int(r.integers(4, NZ - 4))
        w.fill_ball(x, w.column_top(x, z), z, float(r.uniform(2, 4)), STONE, flat=0.7)
    w.fog_near, w.fog_far = 6, 46
    w.particles = ("bubbles", 70)
    w.enclosed = True


def _volcano(w):
    r = w.rng
    n = fbm(NX, r, ((3, 1.0), (8, 0.4)))
    cx, cz = NX / 2 + float(r.uniform(-4, 4)), NZ / 2 + float(r.uniform(-4, 4))
    xs, zs = np.meshgrid(np.arange(NX), np.arange(NZ), indexing="ij")
    d = np.hypot(xs - cx, zs - cz)
    cone = 30 * np.exp(-(d / 15.0) ** 2) + 12 * np.exp(-(d / 26.0) ** 2)
    h = (4 + 5 * n + cone).astype(int)
    h = np.clip(h, 3, NY - 6)
    wl = 7
    for x in range(NX):
        for z in range(NZ):
            hh = int(h[x, z])
            w.grid[x, 0:max(1, hh - 2), z] = BASALT
            w.grid[x, max(1, hh - 2):hh, z] = ASH if r.random() > 0.3 else BASALT
            if hh <= wl:
                w.grid[x, hh: wl + 1, z] = WATER
    top = int(h.max())
    for x in range(NX):                                      # crater and lava
        for z in range(NZ):
            if d[x, z] < 4.2 and h[x, z] >= top - 3:
                w.grid[x, top - 3: NY, z] = AIR
                w.grid[x, top - 4, z] = LAVA
                w.grid[x, 0:top - 4, z] = np.where(w.grid[x, 0:top - 4, z] == AIR, BASALT, w.grid[x, 0:top - 4, z])
    for _ in range(5):                                       # lava rivers running downhill
        a = float(r.uniform(0, math.tau)); rr = 4.0
        for _s in range(60):
            x, z = int(cx + math.cos(a) * rr), int(cz + math.sin(a) * rr)
            if not (1 <= x < NX - 1 and 1 <= z < NZ - 1):
                break
            hh = w.column_top(x, z)
            if hh <= wl + 1:
                break
            w.set(x, hh - 1, z, LAVA)
            if r.random() > 0.5:
                w.set(x + 1, w.column_top(x + 1, z) - 1, z, LAVA)
            rr += 0.6; a += float(r.uniform(-0.18, 0.18))
    w.volcano_top = (cx, top, cz)
    w.scatter(14, lambda x, z: h[x, z] <= wl + 3 and h[x, z] > wl, lambda x, z: w.tree(x, z, "palm"))
    w.add_clouds(9, y=36, speed=1.0, white=False)
    w.fog_near, w.fog_far = 34, 105
    w.particles = ("embers", 90)


def _city(w):
    r = w.rng
    h = np.full((NX, NZ), 5)
    for x in range(NX):
        for z in range(NZ):
            w.grid[x, 0:4, z] = STONE
            w.grid[x, 4, z] = ASPHALT
    pitch = 11
    for bx in range(2, NX - 10, pitch):
        for bz in range(2, NZ - 10, pitch):
            kind = r.random()
            wd, dp = int(r.integers(5, 8)), int(r.integers(5, 8))
            ox, oz = bx + 2, bz + 2
            for x in range(bx, bx + 9):
                for z in range(bz, bz + 9):
                    w.grid[x, 4, z] = CONCRETE if (x in (bx, bx + 8) or z in (bz, bz + 8)) else (GRASS if kind > 0.84 else CONCRETE)
            if kind > 0.84:
                for _t in range(2):
                    w.tree(bx + int(r.integers(2, 7)), bz + int(r.integers(2, 7)), "oak")
                continue
            tall = int(r.choice([8, 10, 14, 18, 22, 28, 34], p=[0.2, 0.2, 0.18, 0.16, 0.12, 0.09, 0.05]))
            body = [CONCRETE, BRICK, GLASS, CONCRETE][int(r.integers(0, 4))]
            for x in range(ox, ox + wd):
                for z in range(oz, oz + dp):
                    for y in range(5, 5 + tall):
                        edge = x in (ox, ox + wd - 1) or z in (oz, oz + dp - 1)
                        if (x + z) % 2 == 0 and y % 2 == 1 and edge and y > 6:
                            w.grid[x, y, z] = WINDOW_ON if r.random() > 0.55 else WINDOW_OFF
                        else:
                            w.grid[x, y, z] = body
            if tall >= 18:                                   # antenna
                for y in range(5 + tall, 5 + tall + 4):
                    w.set(ox + wd // 2, y, oz + dp // 2, CONCRETE)
                w.set(ox + wd // 2, 5 + tall + 4, oz + dp // 2, LAVA)
    w.add_clouds(6, y=40, speed=1.2)
    w.fog_near, w.fog_far = 50, 140


def _cave(w):
    r = w.rng
    w.grid[:, :, :] = STONE
    n3 = fbm(NX, r, ((2, 1.0), (4, 0.5)))
    floor = (8 + 5 * n3).astype(int)
    ceil = (28 + 8 * fbm(NX, r, ((2, 1.0), (5, 0.4)))).astype(int)
    for x in range(NX):
        for z in range(NZ):
            edge = min(x, z, NX - 1 - x, NZ - 1 - z)
            if edge < 4:
                continue
            f, c = int(floor[x, z]), int(ceil[x, z])
            w.grid[x, f:c, z] = AIR
    # stalactites + crystal clusters + pools
    for _ in range(70):
        x, z = int(r.integers(5, NX - 5)), int(r.integers(5, NZ - 5))
        c = int(ceil[x, z])
        for y in range(c - int(r.integers(1, 6)), c):
            if w.get(x, y, z) == AIR:
                w.set(x, y, z, STONE)
    for _ in range(14):
        x, z = int(r.integers(6, NX - 6)), int(r.integers(6, NZ - 6))
        f = int(floor[x, z])
        for _b in range(int(r.integers(4, 10))):
            xx, zz = x + int(r.integers(-1, 2)), z + int(r.integers(-1, 2))
            for y in range(f, f + int(r.integers(2, 7))):
                if w.get(xx, y, zz) == AIR:
                    w.set(xx, y, zz, CRYSTAL if r.random() > 0.15 else CORAL2)
    for _ in range(3):
        x, z = int(r.integers(10, NX - 10)), int(r.integers(10, NZ - 10))
        mat = WATER if r.random() > 0.4 else LAVA
        rad = int(r.integers(3, 6))
        for dx in range(-rad, rad + 1):
            for dz in range(-rad, rad + 1):
                if dx * dx + dz * dz <= rad * rad:
                    f = int(floor[x + dx, z + dz])
                    w.set(x + dx, f - 1, z + dz, mat)
                    for yy in range(f, f + 4):
                        if w.get(x + dx, yy, z + dz) not in (AIR,):
                            w.set(x + dx, yy, z + dz, AIR)
    w.spawn = (NX / 2, 14, NZ / 2)
    w.fog_near, w.fog_far = 10, 52
    w.enclosed = True
    w.particles = ("dust", 40)
    w.floor = floor


def _space(w):
    r = w.rng
    for i in range(9):                                       # floating rocks
        cx, cz = int(r.integers(8, NX - 8)), int(r.integers(8, NZ - 8))
        cy = int(r.integers(8, NY - 10))
        rad = float(r.uniform(2.2, 6))
        w.fill_ball(cx, cy, cz, rad, STONE if r.random() > 0.3 else BASALT, flat=0.65)
        for _k in range(int(rad * 3)):
            w.set(cx + int(r.integers(-int(rad), int(rad) + 1)), cy + int(rad * 0.6), cz + int(r.integers(-int(rad), int(rad) + 1)), SAND if r.random() > 0.5 else GRAVEL)
    # central platform
    for x in range(20, 44):
        for z in range(20, 44):
            d = math.hypot(x - 32, z - 32)
            if d < 11:
                top = 10
                w.grid[x, top - 3: top, z] = STONE
                w.grid[x, top - 1, z] = ASH if d > 4 else CONCRETE
                for y in range(top - 3 - int((11 - d) * 0.5), top - 3):
                    w.set(x, y, z, STONE)
    w.fog_near, w.fog_far = 100, 300


def _islands(w):
    r = w.rng
    centers = [(32, 22, 32, 11)]
    for _ in range(7):
        centers.append((int(r.integers(8, NX - 8)), int(r.integers(10, 30)), int(r.integers(8, NZ - 8)), float(r.uniform(4, 8))))
    for cx, cy, cz, rad in centers:
        ri = int(rad) + 2
        for x in range(int(cx) - ri, int(cx) + ri + 1):
            for z in range(int(cz) - ri, int(cz) + ri + 1):
                d = math.hypot(x - cx, z - cz)
                if d <= rad:
                    depth = int((rad - d) * 0.9) + 1
                    w.set(x, cy, z, GRASS)
                    for k in range(1, 3):
                        w.set(x, cy - k, z, DIRT)
                    for k in range(3, 3 + depth):
                        w.set(x, cy - k, z, STONE)
    for cx, cy, cz, rad in centers:
        for _ in range(int(rad // 2) + 1):
            x, z = int(cx + r.integers(-int(rad) + 2, int(rad) - 1)), int(cz + r.integers(-int(rad) + 2, int(rad) - 1))
            if w.get(x, cy, z) == GRASS and w.get(x, cy + 1, z) == AIR:
                w.tree(x, z, "oak")
    w.add_clouds(16, y=8, speed=1.0)
    w.fog_near, w.fog_far = 60, 170
    w.sea_clouds = True


# ------------------------------------------------------------------ models: people, animals, props
def _col(c, k=1.0):
    return np.clip(np.array(c, float) * k, 0, 255)


ROLE_LOOK = {   # skin-agnostic: shirt, pants, hair, hat
    "astronaut": dict(shirt=(238, 240, 246), pants=(226, 228, 236), hair=None, hat="helmet"),
    "scientist": dict(shirt=(246, 246, 250), pants=(60, 70, 104), hair=(60, 40, 30), hat=None),
    "diver": dict(shirt=(38, 96, 168), pants=(30, 70, 130), hair=None, hat="mask"),
    "explorer": dict(shirt=(190, 160, 96), pants=(110, 92, 60), hair=(92, 60, 36), hat="cap"),
    "geologist": dict(shirt=(214, 126, 60), pants=(84, 84, 96), hair=(60, 44, 36), hat="hardhat"),
    "engineer": dict(shirt=(250, 196, 50), pants=(60, 70, 100), hair=(40, 36, 36), hat="hardhat"),
    "citizen": dict(shirt=(224, 92, 110), pants=(60, 66, 110), hair=(50, 36, 30), hat=None),
    "kid": dict(shirt=(80, 190, 130), pants=(70, 86, 160), hair=(210, 150, 60), hat=None),
    "teacher": dict(shirt=(140, 70, 150), pants=(70, 70, 80), hair=(120, 120, 130), hat=None),
    "robot": dict(shirt=(150, 160, 178), pants=(110, 118, 136), hair=None, hat="antenna"),
}
SKINS = [(255, 214, 176), (240, 190, 150), (214, 155, 112), (171, 110, 74), (122, 76, 52)]


def _pose(action, t):
    """-> dict(ll, rl, la, ra: x-swing angles; laz, raz: sideways arm angles; bob, lean, head, spin)"""
    p = dict(ll=0, rl=0, la=0, ra=0, laz=0.0, raz=0.0, bob=0.0, lean=0.0, head=0.0, hx=0.0, dy=0.0, sit=False)
    s = math.sin
    if action in ("walk", "run"):
        f = 7.5 if action == "run" else 5.0
        a = 0.75 if action == "run" else 0.5
        ph = t * f
        p.update(ll=s(ph) * a, rl=-s(ph) * a, la=-s(ph) * a * 0.9, ra=s(ph) * a * 0.9, bob=abs(s(ph)) * 0.07, lean=0.18 if action == "run" else 0.03)
    elif action == "talk":
        p.update(ra=-0.4 + s(t * 3) * 0.3, la=-0.2 + s(t * 2.3) * 0.15, raz=0.15, head=s(t * 1.7) * 0.15, bob=s(t * 3) * 0.01)
    elif action == "point":
        p.update(ra=-1.45, raz=-0.12, la=0.15, head=0.1, lean=0.04)
    elif action == "jump":
        k = abs(s(t * 4))
        p.update(ll=-0.4, rl=0.4, la=-2.6 * k, ra=-2.6 * k, bob=k * 0.9)
    elif action == "panic":
        p.update(la=-2.6 + s(t * 14) * 0.5, ra=-2.6 - s(t * 14) * 0.5, laz=0.3, raz=-0.3, ll=s(t * 12) * 0.5, rl=-s(t * 12) * 0.5, head=s(t * 9) * 0.25, bob=abs(s(t * 12)) * 0.05)
    elif action == "shrug":
        p.update(laz=0.6, raz=-0.6, la=-0.4, ra=-0.4, head=0.12 * s(t * 1.5))
    elif action == "think":
        p.update(ra=-2.2, la=0.1, head=0.18, raz=0.35)
    elif action == "fall":
        p.update(la=-2.8 + s(t * 10) * 0.3, ra=-2.8 - s(t * 10) * 0.3, ll=0.5 * s(t * 9), rl=-0.5 * s(t * 9), lean=0.4)
    elif action == "float":
        p.update(la=-0.3 + s(t * 1.6) * 0.3, ra=-0.5 - s(t * 1.6) * 0.3, ll=0.2 * s(t * 1.3), rl=-0.25 * s(t * 1.3), lean=0.3, dy=0.25 * s(t * 1.2))
    elif action == "wave":
        p.update(ra=-2.8, raz=-0.35 + s(t * 8) * 0.4)
    elif action == "cheer":
        p.update(la=-2.9, ra=-2.9, laz=0.35, raz=-0.35, bob=abs(s(t * 5)) * 0.35, ll=-0.2, rl=0.2)
    elif action == "look_up":
        p.update(head=0.0, hx=-0.5, la=0.1, ra=0.1)
    elif action == "sit":
        p.update(ll=-1.5, rl=-1.5, la=-0.8, ra=-0.8, sit=True)
    elif action == "push":
        p.update(la=-1.4, ra=-1.4, lean=0.35, ll=s(t * 4) * 0.35, rl=-s(t * 4) * 0.35)
    else:   # idle
        p.update(la=0.04 * s(t * 1.5), ra=-0.04 * s(t * 1.5), bob=0.01 * s(t * 1.6), head=0.04 * s(t * 0.9))
    return p


def human(role, seed, action, t, mouth=0.0, expression="neutral", blink=False):
    """Blocky person facing +z, feet at y = 0 (units = blocks, ~1.8 tall). Returns FaceSet in local coordinates."""
    look = ROLE_LOOK.get(role, ROLE_LOOK["citizen"])
    skin = SKINS[seed % len(SKINS)]
    shirt, pants, hair = look["shirt"], look["pants"], look["hair"]
    hat = look["hat"]
    if role == "robot":
        skin = (170, 182, 200)
    p = _pose(action, t)
    parts = []
    hipy = 0.72 - (0.25 if p["sit"] else 0.0) + p["bob"] + p["dy"]
    lean = rot_x(p["lean"])
    pivot_hip = np.array([0, hipy, 0.0])
    # legs
    for side, ang in ((-1, p["ll"]), (1, p["rl"])):
        R = rot_x(ang)
        leg = limb((side * 0.13, hipy - 0.36, 0), (0.24, 0.72, 0.26), _col(pants, 0.92 if side < 0 else 1.0), (side * 0.13, hipy, 0), R)
        parts.append(leg)
    torso_c = (0, hipy + 0.34, 0)
    torso = box_faces(torso_c, (0.52, 0.68, 0.28), _col(shirt))
    parts.append(torso)
    # arms
    sh = hipy + 0.62
    for side, ang, az in ((-1, p["la"], p["laz"]), (1, p["ra"], p["raz"])):
        R = rot_z(az * (1 if side > 0 else -1) * -1) @ rot_x(ang)
        arm = limb((side * 0.36, sh - 0.28, 0), (0.18, 0.62, 0.2), _col(shirt, 0.94), (side * 0.36, sh, 0), R)
        hand = limb((side * 0.36, sh - 0.62, 0), (0.17, 0.12, 0.19), _col(skin), (side * 0.36, sh, 0), R)
        parts.append(arm); parts.append(hand)
    # head
    hc = np.array([0, hipy + 0.98, 0])
    Rh = rot_y(p["head"]) @ rot_x(p["hx"])
    head = box_faces((0, 0, 0), (0.46, 0.46, 0.46), _col(skin))
    hp = [FaceSet(head.P @ Rh.T + hc, head.Nn @ Rh.T, head.C, head.E, head.K)]
    # face decals on +z
    eyecol = (30, 30, 44)
    ey = 0.04
    for sx in (-1, 1):
        if blink or expression == "happy":
            parts_e = box_faces((sx * 0.1, ey, 0.235), (0.1, 0.025, 0.01), eyecol)
        else:
            parts_e = box_faces((sx * 0.1, ey, 0.235), (0.085, 0.1 if expression != "shocked" else 0.14, 0.01), eyecol)
        hp.append(FaceSet(parts_e.P @ Rh.T + hc, parts_e.Nn @ Rh.T, parts_e.C, parts_e.E, parts_e.K))
        if expression in ("worried", "angry"):
            bro = box_faces((sx * 0.1, ey + 0.11, 0.235), (0.11, 0.03, 0.01), (60, 40, 40))
            Rb = rot_z(sx * (0.3 if expression == "worried" else -0.3))
            hp.append(FaceSet((bro.P - (sx * 0.1, ey + 0.11, 0.235)) @ Rb.T + (sx * 0.1, ey + 0.11, 0.235), bro.Nn @ Rb.T, bro.C, bro.E, bro.K).transformed(Rh, hc))
    mh = 0.02 + 0.1 * float(np.clip(mouth, 0, 1))
    mcol = (110, 40, 50) if mouth > 0.1 else (150, 70, 70)
    m = box_faces((0, -0.12, 0.235), (0.14 + 0.04 * mouth, mh, 0.01), mcol)
    hp.append(FaceSet(m.P @ Rh.T + hc, m.Nn @ Rh.T, m.C, m.E, m.K))
    if hair is not None:
        top = box_faces((0, 0.24, -0.0), (0.5, 0.1, 0.5), _col(hair)); back = box_faces((0, 0.06, -0.2), (0.5, 0.36, 0.1), _col(hair, 0.9))
        for f in (top, back):
            hp.append(FaceSet(f.P @ Rh.T + hc, f.Nn @ Rh.T, f.C, f.E, f.K))
    if hat == "helmet":
        f = box_faces((0, 0.02, 0), (0.62, 0.62, 0.62), (236, 240, 250))
        g = box_faces((0, 0.02, 0.2), (0.5, 0.42, 0.26), (60, 90, 150))
        hp += [FaceSet(x.P @ Rh.T + hc, x.Nn @ Rh.T, x.C, x.E, x.K) for x in (f, g)]
        hp[0] = FaceSet(hp[0].P, hp[0].Nn, hp[0].C * 0.0 + (236, 240, 250), hp[0].E, hp[0].K)
    elif hat == "hardhat":
        f = box_faces((0, 0.27, 0), (0.54, 0.14, 0.54), (255, 206, 40)); g = box_faces((0, 0.2, 0.3), (0.54, 0.04, 0.16), (255, 206, 40))
        hp += [FaceSet(x.P @ Rh.T + hc, x.Nn @ Rh.T, x.C, x.E, x.K) for x in (f, g)]
    elif hat == "cap":
        f = box_faces((0, 0.26, 0), (0.52, 0.1, 0.52), (110, 74, 40)); g = box_faces((0, 0.22, 0.3), (0.5, 0.03, 0.2), (110, 74, 40))
        hp += [FaceSet(x.P @ Rh.T + hc, x.Nn @ Rh.T, x.C, x.E, x.K) for x in (f, g)]
    elif hat == "mask":
        f = box_faces((0, 0.05, 0.25), (0.4, 0.2, 0.06), (150, 220, 250)); g = box_faces((0, 0.26, 0), (0.5, 0.08, 0.5), (30, 40, 60))
        hp += [FaceSet(x.P @ Rh.T + hc, x.Nn @ Rh.T, x.C, x.E, x.K) for x in (f, g)]
    elif hat == "antenna":
        f = box_faces((0, 0.34, 0), (0.05, 0.2, 0.05), (210, 210, 220)); g = box_faces((0, 0.46, 0), (0.1, 0.1, 0.1), (255, 90, 90), glow=0.8)
        hp += [FaceSet(x.P @ Rh.T + hc, x.Nn @ Rh.T, x.C, x.E, x.K) for x in (f, g)]
    parts += hp
    if role == "astronaut":
        parts.append(box_faces((0, hipy + 0.42, -0.2), (0.4, 0.5, 0.14), (200, 204, 216)))
    if role == "diver":
        parts.append(box_faces((0, hipy + 0.42, -0.2), (0.34, 0.5, 0.16), (240, 190, 40)))
    if role == "scientist":
        parts.append(box_faces((0, hipy + 0.0, 0), (0.54, 0.22, 0.3), (246, 246, 250)))
    fs = FaceSet.cat(parts)
    if p["lean"]:
        fs = FaceSet((fs.P - pivot_hip) @ lean.T + pivot_hip, fs.Nn @ lean.T, fs.C, fs.E, fs.K)
    return fs


def critter(kind, seed, t):
    """Original blocky animals/aliens. Facing +z, feet at y = 0."""
    r = np.random.default_rng(seed + 17)
    pal = [(238, 160, 190), (230, 190, 130), (150, 200, 240), (180, 150, 230), (140, 214, 150), (250, 224, 120)]
    c = pal[seed % len(pal)]
    parts = []
    s = math.sin
    if kind in ("cat", "dog", "critter", "dino_toon"):
        ph = t * 6
        for sx, sz, d in ((-0.16, -0.28, 0), (0.16, -0.28, 1), (-0.16, 0.28, 1), (0.16, 0.28, 0)):
            ang = s(ph + d * math.pi) * 0.5
            parts.append(limb((sx, 0.2, sz), (0.16, 0.4, 0.16), _col(c, 0.85), (sx, 0.4, sz), rot_x(ang)))
        parts.append(box_faces((0, 0.5, 0), (0.46, 0.34, 0.8), _col(c)))
        parts.append(box_faces((0, 0.66, 0.5), (0.34, 0.32, 0.34), _col(c, 1.05)))
        parts.append(box_faces((0, 0.6, 0.7), (0.2, 0.14, 0.1), _col(c, 0.8)))
        for sx in (-1, 1):
            parts.append(box_faces((sx * 0.09, 0.72, 0.67), (0.07, 0.07, 0.02), (20, 20, 30)))
            parts.append(box_faces((sx * 0.14, 0.86, 0.46), (0.08, 0.12, 0.08), _col(c, 0.8)))
        parts.append(limb((0, 0.62, -0.5), (0.08, 0.08, 0.34), _col(c, 0.8), (0, 0.62, -0.42), rot_y(s(t * 5) * 0.5) @ rot_x(0.5)))
    elif kind == "bird":
        fl = s(t * 12) * 0.7
        parts.append(box_faces((0, 0, 0), (0.3, 0.26, 0.5), _col(c)))
        parts.append(box_faces((0, 0.08, 0.3), (0.2, 0.2, 0.2), _col(c, 1.1)))
        parts.append(box_faces((0, 0.06, 0.45), (0.08, 0.06, 0.14), (255, 190, 70)))
        for sx in (-1, 1):
            parts.append(limb((sx * 0.4, 0.02, 0), (0.6, 0.04, 0.3), _col(c, 0.85), (sx * 0.14, 0.02, 0), rot_z(sx * fl)))
    elif kind == "fish_toon" or kind == "fish":
        wag = s(t * 8) * 0.4
        parts.append(box_faces((0, 0, 0), (0.22, 0.3, 0.7), _col(c)))
        parts.append(box_faces((0, 0.0, 0.0), (0.24, 0.16, 0.5), _col(c, 1.2)))
        parts.append(limb((0, 0, -0.5), (0.04, 0.34, 0.26), _col(c, 0.8), (0, 0, -0.35), rot_y(wag)))
        parts.append(box_faces((0, 0.2, 0.0), (0.04, 0.16, 0.3), _col(c, 0.8)))
        for sx in (-1, 1):
            parts.append(box_faces((sx * 0.12, 0.04, 0.24), (0.02, 0.07, 0.07), (20, 20, 30)))
    else:   # blob_alien / slime-like
        sq = 1 + 0.08 * s(t * 4)
        col = (120, 220, 150) if seed % 2 == 0 else (190, 140, 255)
        parts.append(box_faces((0, 0.32 * sq, 0), (0.6, 0.64 * sq, 0.6), col, glow=0.12))
        for sx in (-1, 1):
            parts.append(box_faces((sx * 0.14, 0.4 * sq, 0.31), (0.12, 0.16, 0.02), (255, 255, 255)))
            parts.append(box_faces((sx * 0.14, 0.4 * sq, 0.32), (0.06, 0.1, 0.02), (20, 20, 40)))
        parts.append(box_faces((0, 0.22 * sq, 0.31), (0.2, 0.06, 0.02), (60, 30, 70)))
        parts.append(box_faces((0, 0.75 * sq, 0), (0.05, 0.2, 0.05), col)); parts.append(box_faces((0, 0.9 * sq, 0), (0.12, 0.12, 0.12), (255, 220, 100), glow=0.9))
    return FaceSet.cat(parts)


def _sphere_cells(r, colfn, hollow=False):
    cells = {}
    ri = int(math.ceil(r))
    for x in range(-ri, ri + 1):
        for y in range(-ri, ri + 1):
            for z in range(-ri, ri + 1):
                d = math.sqrt(x * x + y * y + z * z)
                if d <= r + 0.2:
                    cells[(x, y, z)] = colfn(x, y, z, d)
    return cells


@functools.lru_cache(maxsize=64)
def prop(name, seed=0):
    """Voxel models for things an explainer talks about. Origin near the centre (or the base for buildings); 1 cell = 1 block."""
    r = np.random.default_rng(seed * 31 + 3)
    cells = {}
    if name == "sun":
        cells = _sphere_cells(5, lambda x, y, z, d: (255, 226 - int(d * 8), 70, 1.0))
    elif name == "moon":
        cells = _sphere_cells(4, lambda x, y, z, d: tuple(int(v) for v in np.array((214, 216, 224)) * (0.82 if (x * 7 + y * 3 + z * 5) % 11 == 0 else 1.0)) + (0.2,))
    elif name in ("earth", "earth_layers"):
        def ec(x, y, z, d):
            land = (math.sin(x * 0.9 + y * 0.4) + math.cos(z * 0.8 - y * 0.7) + math.sin((x + z) * 0.5)) > 0.9
            if abs(y) > 5:
                return (240, 246, 255)
            return (70, 170, 90) if land else (50, 110, 220)
        cells = _sphere_cells(6, ec)
        if name == "earth_layers":
            cells = {k: v for k, v in cells.items() if not (k[0] > 0 and k[2] > 0 and k[1] > -1)}
            core = _sphere_cells(2, lambda x, y, z, d: (255, 140, 40, 0.8))
            cells.update(core)
    elif name in ("planet", "ringed"):
        pal = [((224, 120, 84), (180, 90, 60)), ((96, 160, 232), (70, 120, 190)), ((170, 118, 220), (130, 80, 180)), ((232, 188, 96), (200, 150, 70))][seed % 4]
        cells = _sphere_cells(5, lambda x, y, z, d: pal[0] if (y + 20) % 4 < 2 else pal[1])
        if name == "ringed":
            for a in np.linspace(0, math.tau, 80, endpoint=False):
                for rr in (8, 9, 10):
                    cells[(int(round(math.cos(a) * rr)), 0, int(round(math.sin(a) * rr)))] = (230, 210, 160)
    elif name == "star":
        cells = _sphere_cells(2, lambda x, y, z, d: (255, 244, 180, 1.0))
    elif name in ("asteroid", "comet"):
        cells = _sphere_cells(2.6, lambda x, y, z, d: tuple(int(v) for v in np.array((118, 106, 98)) * (0.7 + 0.5 * ((x * 5 + y * 3 + z * 7) % 5) / 5)))
        cells = {k: v for k, v in cells.items() if r.random() > 0.12}
        cells[(0, 0, 0)] = (100, 90, 84)
    elif name == "rocket":
        for y in range(-6, 7):
            rad = 1 if y > -5 else 1
            for x in range(-1, 2):
                for z in range(-1, 2):
                    if abs(x) + abs(z) <= 1 + (1 if y < 2 else 0) and not (y > 4 and abs(x) + abs(z) > 0):
                        cells[(x, y, z)] = (240, 242, 248) if y < 4 else (232, 70, 70)
        for y in range(-6, -2):
            for sx in (-2, 2):
                cells[(sx, y, 0)] = (232, 70, 70); cells[(0, y, sx)] = (232, 70, 70)
        cells[(0, 2, 1)] = (110, 190, 240); cells[(0, 2, -1)] = (110, 190, 240); cells[(1, 2, 0)] = (110, 190, 240); cells[(-1, 2, 0)] = (110, 190, 240)
        cells[(0, 7, 0)] = (232, 70, 70)
    elif name == "satellite":
        for x in range(-1, 2):
            for y in range(-1, 2):
                for z in range(-1, 2):
                    cells[(x, y, z)] = (210, 214, 226)
        for sx in (-1, 1):
            for k in range(2, 6):
                for z in range(-1, 2):
                    cells[(sx * k, 0, z)] = (60, 100, 190, 0.15)
        cells[(0, 2, 0)] = (240, 240, 245)
    elif name == "ufo":
        for x in range(-6, 7):
            for z in range(-6, 7):
                d = math.hypot(x, z)
                if d <= 6:
                    cells[(x, 0, z)] = (170, 180, 200) if d > 4 else (150, 160, 180)
                if d <= 3.2:
                    cells[(x, 1, z)] = (120, 220, 255, 0.3) if d > 1.5 else (150, 240, 255, 0.5)
                if 3.5 < d <= 5.2 and (int(math.atan2(z, x) * 2.5) % 2 == 0):
                    cells[(x, -1, z)] = (255, 220, 90, 1.0)
    elif name == "whale":
        for x in range(-3, 4):
            for y in range(-2, 3):
                for z in range(-8, 9):
                    prof = 3.0 * math.sqrt(max(0, 1 - (z / 8.5) ** 2)) + 0.3
                    if abs(x) <= prof and abs(y) <= prof * 0.8 + 0.2:
                        cells[(x, y, z)] = (70, 100, 150) if y > -1 else (214, 226, 240)
        for x in range(-3, 4):
            cells[(x, 1, -9)] = (60, 90, 140); cells[(x, 2, -10)] = (60, 90, 140)
        cells[(3, 1, 5)] = (20, 20, 30)
    elif name == "shark":
        for x in range(-2, 3):
            for y in range(-1, 2):
                for z in range(-7, 7):
                    prof = 2.0 * math.sqrt(max(0, 1 - (z / 7.0) ** 2)) + 0.2
                    if abs(x) <= prof and abs(y) <= prof * 0.8:
                        cells[(x, y, z)] = (130, 142, 160) if y > -1 else (230, 236, 244)
        cells[(0, 2, -1)] = (110, 122, 140); cells[(0, 3, -1)] = (110, 122, 140); cells[(0, 2, -2)] = (110, 122, 140); cells[(0, 3, -3)] = (110, 122, 140)
        for y in (-2, -1, 0, 1, 2):
            cells[(0, y, -8)] = (110, 122, 140)
    elif name in ("fish",):
        return critter("fish", seed, 0)
    elif name == "jellyfish":
        for x in range(-3, 4):
            for z in range(-3, 4):
                d = math.hypot(x, z)
                if d <= 3:
                    cells[(x, 2, z)] = (240, 150, 220, 0.4)
                    if d <= 2:
                        cells[(x, 3, z)] = (250, 170, 240, 0.5)
        for x in (-2, 0, 2):
            for y in range(-3, 2):
                cells[(x, y, 0)] = (230, 140, 210, 0.3)
    elif name == "dino":
        for x in (-1, 0, 1):
            for y in range(0, 4):
                for z in range(-3, 4):
                    cells[(x, y + 2, z)] = (110, 190, 120)
        for z in range(-8, -3):
            cells[(0, 3 + (z + 8) // 3, z)] = (100, 180, 110)
        for z in range(3, 6):
            for y in range(4, 8):
                cells[(0, y, z)] = (116, 196, 126)
        for x in (-1, 1):
            for y in range(0, 2):
                cells[(x, y, -1)] = (90, 160, 100); cells[(x, y, 2)] = (90, 160, 100)
        cells[(1, 7, 6)] = (20, 20, 30)
    elif name == "pyramid":
        for lvl in range(7):
            for x in range(-7 + lvl, 8 - lvl):
                for z in range(-7 + lvl, 8 - lvl):
                    cells[(x, lvl, z)] = (222, 190, 120) if lvl < 6 else (255, 214, 70, 0.4)
    elif name in ("skyline", "house"):
        for k, (ox, h) in enumerate(((-4, 5), (0, 8), (4, 6))):
            for x in range(ox - 1, ox + 2):
                for z in range(-1, 2):
                    for y in range(h):
                        edge = x in (ox - 1, ox + 1) or z in (-1, 1)
                        cells[(x, y, z)] = (255, 226, 132, 0.8) if (edge and y % 2 == 1 and (x + z) % 2 == 0) else (150, 156, 176)
    elif name == "car":
        for x in range(-1, 2):
            for z in range(-3, 4):
                cells[(x, 1, z)] = (230, 70, 70)
        for x in range(-1, 2):
            for z in range(-1, 2):
                cells[(x, 2, z)] = (140, 200, 240)
        for sx in (-2, 2):
            for sz in (-2, 2):
                cells[(sx, 0, sz)] = (30, 30, 36)
    elif name == "plane":
        for z in range(-5, 6):
            cells[(0, 0, z)] = (240, 242, 248); cells[(0, 1, z)] = (240, 242, 248) if z < 3 else (200, 60, 60)
        for x in range(-5, 6):
            for z in range(-1, 2):
                cells[(x, 0, z)] = (210, 214, 224)
        for x in range(-2, 3):
            cells[(x, 0, -5)] = (210, 214, 224)
        cells[(0, 2, -5)] = (200, 60, 60); cells[(0, 3, -5)] = (200, 60, 60)
    elif name == "robot":
        return human("robot", seed, "idle", 0)
    elif name in ("tnt", "explosion"):
        for x in range(-1, 2):
            for y in range(-1, 2):
                for z in range(-1, 2):
                    cells[(x, y, z)] = (220, 60, 60) if (y + 1) % 2 == 0 else (240, 230, 220)
    elif name == "coin":
        for x in range(-3, 4):
            for y in range(-3, 4):
                if x * x + y * y <= 10:
                    cells[(x, y, 0)] = (255, 214, 70, 0.4); cells[(x, y, 1)] = (240, 190, 40)
    elif name in ("tree",):
        for y in range(0, 4):
            cells[(0, y, 0)] = (104, 78, 46)
        for x in range(-2, 3):
            for y in range(4, 8):
                for z in range(-2, 3):
                    if x * x + (y - 5.5) ** 2 + z * z <= 5.5:
                        cells[(x, y, z)] = (62, 140, 54)
    elif name in ("cloud",):
        for _b in range(5):
            bx, bz = int(r.integers(-3, 4)), int(r.integers(-1, 2))
            for dx in range(3):
                for dz in range(3):
                    cells[(bx + dx, 0, bz + dz)] = (252, 252, 255)
            cells[(bx + 1, 1, bz + 1)] = (246, 248, 255)
    elif name in ("fire",):
        for y in range(0, 4):
            for x in range(-1, 2):
                for z in range(-1, 2):
                    if abs(x) + abs(z) + y <= 3 and r.random() > 0.2:
                        cells[(x, y, z)] = (255, 120 + 30 * y, 30 + 20 * y, 1.0)
    elif name in ("brain", "heart", "cell", "virus", "dna", "atom", "bulb", "clock", "gear", "crowd", "person", "magnet", "battery", "monitor", "phone",
                  "eye", "sound", "skull", "bolt", "rain", "wave", "snowflake", "thermo", "hourglass", "water_drop", "scale", "volcano", "mountain"):
        cells = _generic_icon(name)
    if not cells:
        cells = _generic_icon("crate")
    return faces_from_cells(cells, jitter=0.06, seed=seed)


def _generic_icon(name):
    """A recognisable-enough little voxel sculpture for science concepts (cheap, original)."""
    c = {}
    if name == "brain":
        for x in range(-3, 4):
            for y in range(-2, 3):
                for z in range(-3, 4):
                    if x * x * 0.9 + y * y * 1.6 + z * z * 0.8 <= 8.5:
                        c[(x, y, z)] = (250, 170, 190) if (x + y * 2 + z) % 3 else (232, 140, 166)
    elif name == "heart":
        for x in range(-4, 5):
            for y in range(-4, 5):
                if (x * x + y * y - 9) ** 3 - x * x * y * y * y <= 0 and y > -4:
                    c[(x, -y + 1, 0)] = (230, 50, 70); c[(x, -y + 1, 1)] = (210, 40, 60)
    elif name in ("cell", "virus"):
        for x in range(-4, 5):
            for y in range(-4, 5):
                for z in range(-4, 5):
                    d = math.sqrt(x * x + y * y + z * z)
                    if 3.0 <= d <= 4.3:
                        c[(x, y, z)] = (250, 150, 190, 0.1) if name == "cell" else (150, 220, 120)
        if name == "cell":
            for x in range(-1, 2):
                for y in range(-1, 2):
                    for z in range(-1, 2):
                        c[(x, y, z)] = (140, 90, 220)
        else:
            for a in range(0, 360, 45):
                for b in (-60, 0, 60):
                    x, y, z = [int(round(5.3 * v)) for v in (math.cos(math.radians(a)) * math.cos(math.radians(b)), math.sin(math.radians(b)), math.sin(math.radians(a)) * math.cos(math.radians(b)))]
                    c[(x, y, z)] = (255, 90, 110)
    elif name == "dna":
        for i in range(24):
            a = i * 0.5
            y = i - 12
            for s, col in ((0, (90, 160, 255)), (math.pi, (255, 120, 170))):
                c[(int(round(math.cos(a + s) * 2.4)), y, int(round(math.sin(a + s) * 2.4)))] = col
            if i % 3 == 0:
                for k in range(-2, 3):
                    c[(int(round(math.cos(a) * k)), y, int(round(math.sin(a) * k)))] = (240, 230, 130, 0.3)
    elif name == "atom":
        c[(0, 0, 0)] = (255, 120, 90, 0.8); c[(1, 0, 0)] = (90, 150, 255, 0.5); c[(0, 1, 0)] = (255, 120, 90, 0.8)
        for k in range(3):
            for a in np.linspace(0, math.tau, 28, endpoint=False):
                x, y = math.cos(a) * 5.5, math.sin(a) * 5.5
                p = [(x, y, 0), (x, 0, y), (0, x, y)][k]
                c[tuple(int(round(v)) for v in p)] = (120, 220, 255, 0.5)
    elif name == "bulb":
        for x in range(-3, 4):
            for y in range(0, 7):
                for z in range(-3, 4):
                    if x * x + (y - 4) ** 2 + z * z <= 8.5:
                        c[(x, y + 2, z)] = (255, 238, 140, 1.0)
        for y in range(0, 2):
            for x in range(-1, 2):
                for z in range(-1, 2):
                    c[(x, y, z)] = (150, 150, 160)
    elif name == "clock":
        for x in range(-4, 5):
            for y in range(-4, 5):
                d = math.hypot(x, y)
                if d <= 4.5:
                    c[(x, y, 0)] = (245, 245, 250) if d < 3.8 else (80, 90, 120)
                    c[(x, y, 1)] = (245, 245, 250) if d < 3.8 else (80, 90, 120)
        for k in range(0, 4):
            c[(0, k, 1)] = (30, 30, 50); c[(k, 0, 2)] = (30, 30, 50)
    elif name == "gear":
        for a in np.linspace(0, math.tau, 120, endpoint=False):
            for rr in (2.8, 3.6, 4.4 + (0.9 if int(a * 8 / math.tau) % 2 == 0 else 0)):
                c[(int(round(math.cos(a) * rr)), int(round(math.sin(a) * rr)), 0)] = (170, 180, 196)
                c[(int(round(math.cos(a) * rr)), int(round(math.sin(a) * rr)), 1)] = (150, 160, 176)
    elif name in ("crowd", "person"):
        for k, ox in enumerate((-3, 0, 3) if name == "crowd" else (0,)):
            col = [(240, 100, 110), (100, 170, 255), (255, 210, 90)][k % 3]
            for y in range(0, 3):
                c[(ox, y, 0)] = col
            c[(ox, 3, 0)] = (255, 214, 176)
            c[(ox - 1, 2, 0)] = col; c[(ox + 1, 2, 0)] = col
    elif name == "bolt":
        pts = [(0, 8), (1, 6), (0, 5), (2, 3), (1, 2), (3, 0), (2, -2)]
        for (x, y) in pts:
            c[(x, y, 0)] = (255, 240, 120, 1.0); c[(x + 1, y, 0)] = (255, 250, 190, 1.0)
    elif name == "rain":
        for _ in range(24):
            x, y, z = int(np.random.default_rng(_).integers(-5, 6)), int(np.random.default_rng(_ + 50).integers(-5, 6)), int(np.random.default_rng(_ + 90).integers(-5, 6))
            c[(x, y, z)] = (150, 190, 255, 0.4); c[(x, y - 1, z)] = (150, 190, 255, 0.4)
    elif name == "wave":
        for x in range(-8, 9):
            h = int(3 + 2 * math.sin(x * 0.5))
            for y in range(0, h):
                for z in range(-1, 2):
                    c[(x, y, z)] = (80, 150, 240) if y < h - 1 else (230, 245, 255)
    elif name == "snowflake":
        for a in range(6):
            for k in range(0, 6):
                x, y = int(round(math.cos(a * math.pi / 3) * k)), int(round(math.sin(a * math.pi / 3) * k))
                c[(x, y, 0)] = (210, 240, 255, 0.4)
    elif name == "thermo":
        for y in range(-2, 8):
            c[(0, y, 0)] = (230, 60, 60, 0.4) if y < 4 else (230, 240, 250)
            c[(1, y, 0)] = (200, 210, 225); c[(-1, y, 0)] = (200, 210, 225)
        for x in range(-2, 3):
            for y in range(-4, -1):
                c[(x, y, 0)] = (230, 60, 60, 0.4)
    elif name == "hourglass":
        for y in range(-5, 6):
            w_ = abs(y) // 2 + 0 if abs(y) > 1 else 0
            for x in range(-w_, w_ + 1):
                c[(x, y, 0)] = (236, 200, 120) if y < 0 else (220, 190, 110)
    elif name == "water_drop":
        for y in range(-3, 5):
            rr = 3 if y < 1 else max(0, 4 - y)
            for x in range(-rr, rr + 1):
                for z in range(-rr, rr + 1):
                    if x * x + z * z <= rr * rr:
                        c[(x, y, z)] = (100, 190, 255, 0.2)
    elif name == "scale":
        for x in range(-6, 7):
            c[(x, 5, 0)] = (200, 160, 80)
        for y in range(0, 5):
            c[(0, y, 0)] = (200, 160, 80)
        for sx in (-6, 6):
            for x in range(-1, 2):
                c[(sx + x, 2, 0)] = (230, 210, 140)
    elif name in ("volcano", "mountain"):
        for lvl in range(9):
            for x in range(-9 + lvl, 10 - lvl):
                for z in range(-9 + lvl, 10 - lvl):
                    c[(x, lvl, z)] = (90, 84, 92) if name == "volcano" else ((240, 246, 255) if lvl > 6 else (120, 124, 130))
        if name == "volcano":
            c[(0, 8, 0)] = (255, 120, 30, 1.0)
    elif name == "monitor":
        for x in range(-4, 5):
            for y in range(-3, 4):
                c[(x, y, 0)] = (40, 50, 74); c[(x, y, 1)] = (90, 210, 255, 0.5) if abs(x) < 4 and abs(y) < 3 else (40, 50, 74)
        c[(0, -4, 0)] = (60, 66, 90); c[(-1, -5, 0)] = (60, 66, 90); c[(0, -5, 0)] = (60, 66, 90); c[(1, -5, 0)] = (60, 66, 90)
    elif name == "phone":
        for x in range(-2, 3):
            for y in range(-4, 5):
                c[(x, y, 0)] = (40, 44, 60); c[(x, y, 1)] = (110, 200, 255, 0.5) if abs(x) < 2 and abs(y) < 4 else (40, 44, 60)
    elif name == "eye":
        for x in range(-5, 6):
            for y in range(-2, 3):
                if abs(y) <= 2 - abs(x) // 3:
                    c[(x, y, 0)] = (248, 248, 252)
        for x in range(-1, 2):
            for y in range(-1, 2):
                c[(x, y, 1)] = (60, 130, 220); c[(0, 0, 1)] = (20, 20, 30)
    elif name == "sound":
        for k in range(1, 4):
            for a in np.linspace(-0.9, 0.9, 12):
                c[(int(round(math.cos(a) * k * 2.0)), int(round(math.sin(a) * k * 2.0)), 0)] = (150, 210, 255, 0.4)
        for y in range(-1, 2):
            c[(-2, y, 0)] = (200, 200, 210)
    elif name == "skull":
        for x in range(-3, 4):
            for y in range(-2, 4):
                if x * x + (y - 1) ** 2 <= 10:
                    c[(x, y, 0)] = (240, 238, 230)
        for sx in (-1, 1):
            c[(sx, 1, 1)] = (20, 20, 30)
    elif name == "magnet":
        for a in np.linspace(math.pi, 2 * math.pi, 24):
            for rr in (3, 4):
                c[(int(round(math.cos(a) * rr)), int(round(-math.sin(a) * rr)) + 3, 0)] = (220, 60, 60) if a < 1.5 * math.pi else (70, 120, 230)
    elif name == "battery":
        for x in range(-2, 3):
            for y in range(-4, 5):
                for z in range(-1, 2):
                    c[(x, y, z)] = (60, 200, 110) if y > -2 else (60, 70, 90)
        c[(0, 5, 0)] = (200, 200, 210); c[(1, 5, 0)] = (200, 200, 210)
    else:   # crate
        for x in range(-2, 3):
            for y in range(-2, 3):
                for z in range(-2, 3):
                    edge = sum(abs(v) == 2 for v in (x, y, z)) >= 2
                    c[(x, y, z)] = (130, 90, 56) if edge else (178, 138, 86)
    return c


ENTITY_TO_PROP = {
    "blackhole": "planet", "galaxy": "star", "ringed": "ringed", "rocket": "rocket", "satellite": "satellite", "ufo": "ufo", "volcano": "volcano",
    "mountain": "mountain", "tree": "tree", "cloud": "cloud", "bolt": "bolt", "rain": "rain", "wave": "wave", "whale": "whale", "shark": "shark", "fish": "fish",
    "jellyfish": "jellyfish", "cell": "cell", "virus": "virus", "dna": "dna", "atom": "atom", "brain": "brain", "heart": "heart", "bulb": "bulb", "clock": "clock",
    "hourglass": "hourglass", "thermo": "thermo", "snowflake": "snowflake", "fire": "fire", "skyline": "skyline", "house": "house", "car": "car", "plane": "plane",
    "monitor": "monitor", "phone": "phone", "robot": "robot", "coin": "coin", "magnet": "magnet", "battery": "battery", "eye": "eye", "sound": "sound",
    "skull": "skull", "crowd": "crowd", "person": "person", "explosion": "tnt", "gear": "gear", "water_drop": "water_drop", "dino": "dino", "pyramid": "pyramid",
    "scale": "scale", "earth_layers": "earth_layers", "sun": "sun", "moon": "moon", "earth": "earth", "planet": "planet", "asteroid": "asteroid", "comet": "comet",
    "star": "star",
}


# ------------------------------------------------------------------ camera + renderer
class Cam:
    def __init__(self, pos, target, fov=62.0, roll=0.0):
        self.pos = np.asarray(pos, float); self.target = np.asarray(target, float); self.fov = fov; self.roll = roll

    def basis(self):
        f = self.target - self.pos
        f = f / (np.linalg.norm(f) + 1e-9)
        up = np.array([0, 1.0, 0])
        r = np.cross(f, up)
        if np.linalg.norm(r) < 1e-6:
            r = np.array([1.0, 0, 0])
        r /= np.linalg.norm(r)
        u = np.cross(r, f)
        if self.roll:
            c, s = math.cos(self.roll), math.sin(self.roll)
            r, u = r * c + u * s, u * c - r * s
        return r, u, f


_SKY_CACHE = {}


def _sky_image(sky, size, horizon):
    key = (tuple(sky["top"]), tuple(sky["bot"]), size, int(horizon // 4))
    if key not in _SKY_CACHE:
        w, h = size
        y = np.arange(h)[:, None, None].astype(float)
        k = np.clip(1 - (y - 0) / max(1.0, horizon + 60), 0, 1) ** 0.8
        k = np.where(y > horizon + 60, 0, k)
        top, bot = np.array(sky["top"], float), np.array(sky["bot"], float)
        arr = (bot * (1 - k) + top * k) * np.ones((1, w, 1))
        if len(_SKY_CACHE) > 24:
            _SKY_CACHE.clear()
        _SKY_CACHE[key] = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    return _SKY_CACHE[key].copy()


def _stars(d, rng_seed, amount, t, size, cam):
    rng = np.random.default_rng(rng_seed)
    n = int(260 * amount)
    az = rng.uniform(0, math.tau, n); el = rng.uniform(-0.1, 1.2, n); br = rng.uniform(0.3, 1, n); ph = rng.uniform(0, 6.28, n)
    r, u, f = cam.basis()
    fl = (size[1] / 2) / math.tan(math.radians(cam.fov) / 2)
    dirs = np.stack([np.cos(el) * np.cos(az), np.sin(el), np.cos(el) * np.sin(az)], 1)
    xc = dirs @ r; yc = dirs @ u; zc = dirs @ f
    ok = zc > 0.05
    sx = size[0] / 2 + xc[ok] / zc[ok] * fl; sy = size[1] / 2 - yc[ok] / zc[ok] * fl
    for x, y, b, p in zip(sx, sy, br[ok], ph[ok]):
        if 0 <= x < size[0] and 0 <= y < size[1]:
            v = int(255 * b * (0.7 + 0.3 * math.sin(t * 2.2 + p)))
            s = 1 + (b > 0.8)
            d.rectangle((x, y, x + s, y + s), fill=(v, v, min(255, v + 18)))


def render(world, cam, t, models=(), size=(W, H), seed=0, extra_particles=None, tod_tint=None):
    """models: list of FaceSet already placed in world coordinates. Returns a PIL RGB image."""
    w_, h_ = size
    sky = world.sky
    r, u, f = cam.basis()
    fl = (h_ / 2) / math.tan(math.radians(cam.fov) / 2)
    # horizon row on screen
    hz = h_ / 2 + (f[1] / max(1e-3, math.sqrt(max(1e-6, 1 - f[1] ** 2)))) * fl * 0.98
    img = _sky_image(sky, size, float(np.clip(hz, -h_, 2 * h_)))
    d = ImageDraw.Draw(img)
    if sky.get("stars", 0) > 0.01:
        _stars(d, 5, sky["stars"], t, size, cam)
    # sun / moon billboard
    sd = world.sun_dir / np.linalg.norm(world.sun_dir)
    if world.tod != "cave" and world.env not in ("underwater",):
        xc, yc, zc = float(sd @ r), float(sd @ u), float(sd @ f)
        if zc > 0.05:
            sx, sy = w_ / 2 + xc / zc * fl, h_ / 2 - yc / zc * fl
            rad = 36 if world.tod != "night" else 26
            col = sky["sun"]
            for k in (3.2, 2.2, 1.5):
                a = tuple(int(c * 0.18 + b * 0.82) for c, b in zip(col, sky["bot"]))
                d.rectangle((sx - rad * k * 0.7, sy - rad * k * 0.7, sx + rad * k * 0.7, sy + rad * k * 0.7), fill=a if k > 2.5 else tuple(int(c * (0.3 + 0.2 * (3.3 - k)) + b * (0.7 - 0.2 * (3.3 - k))) for c, b in zip(col, sky["bot"])))
            d.rectangle((sx - rad * 0.8, sy - rad * 0.8, sx + rad * 0.8, sy + rad * 0.8), fill=tuple(col))
    # collect faces
    cloud_sets = []
    for fs, (cx, cy, cz), spd in world.clouds:
        cloud_sets.append(fs.transformed(None, ((cx + t * spd) % (NX + 80) - 40, cy, cz)))
    allf = FaceSet.cat([world.faces] + cloud_sets + list(models))
    if len(allf) == 0:
        return img
    P = allf.P
    cp = cam.pos
    v = P - cp
    xc = v @ r; yc = v @ u; zc = v @ f
    cen = P.mean(axis=1)
    cv_ = cen - cp
    cz_ = cv_ @ f
    dist = np.sqrt((cv_ ** 2).sum(1))
    front = (allf.Nn * cv_).sum(1) < 0
    ok = front & (zc.min(axis=1) > 0.15) & (dist < world.fog_far * 1.05 + 4)
    sx = w_ / 2 + xc / np.maximum(zc, 0.15) * fl
    sy = h_ / 2 - yc / np.maximum(zc, 0.15) * fl
    ok &= ~((sx.max(1) < -20) | (sx.min(1) > w_ + 20) | (sy.max(1) < -20) | (sy.min(1) > h_ + 20))
    idx = np.nonzero(ok)[0]
    if not len(idx):
        return img
    order = idx[np.argsort(-dist[idx])]
    # shading
    L = sd
    nd = np.clip(allf.Nn[order] @ L, 0, 1)
    amb = sky["amb"]
    light = amb + (1.08 - amb) * nd
    if world.enclosed or world.tod == "cave":
        light = 0.62 + 0.45 * nd
    tint = np.array(sky["tint"]) if tod_tint is None else np.asarray(tod_tint)
    col = allf.C[order].copy()
    kind = allf.K[order]
    glow = allf.E[order]
    # animated water / lava
    if (kind == 1).any():
        wob = 0.93 + 0.07 * np.sin(cen[order, 0] * 0.9 + cen[order, 2] * 0.7 + t * 2.2)
        col = np.where((kind == 1)[:, None], col * wob[:, None] + np.array([8, 12, 18]) * (wob[:, None] - 0.93) * 14, col)
    if (kind == 2).any():
        fl_ = 0.88 + 0.16 * np.sin(cen[order, 0] * 1.3 + cen[order, 2] * 1.1 + t * 3.1) + 0.06 * np.sin(t * 7 + cen[order, 0] * 3)
        col = np.where((kind == 2)[:, None], col * fl_[:, None], col)
    lit = col * (light[:, None] * tint[None, :])
    gl = np.clip(glow, 0, 1)[:, None]
    col = lit * (1 - gl) + col * gl * 1.0
    # fog
    dd = dist[order]
    fk = np.clip((dd - world.fog_near) / max(1.0, world.fog_far - world.fog_near), 0, 1) ** 1.2
    fogc = np.array(sky["fog"], float)
    col = col * (1 - fk[:, None]) + fogc * fk[:, None]
    col = np.clip(col, 0, 255).astype(np.uint8)
    edge = (col * 0.86).astype(np.uint8)
    pts = np.stack([sx[order], sy[order]], axis=2).reshape(len(order), 8)
    size_px = np.maximum(sx[order].max(1) - sx[order].min(1), sy[order].max(1) - sy[order].min(1))
    pl = pts.tolist(); cl = col.tolist(); el = edge.tolist(); szl = size_px.tolist()
    # speckles ("pixel texture") for faces that are big on screen
    big = np.nonzero((size_px > 34) & (kind != 3) & (glow < 0.99))[0]
    bigset = set(big.tolist())
    for i in range(len(pl)):
        c = tuple(cl[i])
        if szl[i] > 7:
            d.polygon(pl[i], fill=c, outline=tuple(el[i]))
        else:
            d.polygon(pl[i], fill=c, outline=c)
        if i in bigset:
            _speckle(d, pts[i], order[i], cl[i], fk[i], seed)
    # particles in front (snow, ash, bubbles, embers...)
    pt = extra_particles or world.particles
    if pt:
        _particles(d, pt, t, size, world.seed + seed, sky)
    return img


def _speckle(d, pts, face_id, base, fog, seed):
    rng = np.random.default_rng(int(face_id) * 7 + 3)
    p = np.asarray(pts).reshape(4, 2)
    a, b, c_, d_ = p
    n = 4
    for _ in range(n):
        u_, v_ = rng.random() * 0.8 + 0.05, rng.random() * 0.8 + 0.05
        q = a + (b - a) * u_ + (d_ - a) * v_
        sz = 0.17
        e1 = (b - a) * sz; e2 = (d_ - a) * sz
        k = 1 + (rng.random() - 0.5) * 0.22
        col = tuple(int(np.clip(x * k, 0, 255)) for x in base)
        d.polygon([tuple(q), tuple(q + e1), tuple(q + e1 + e2), tuple(q + e2)], fill=col)


def _particles(d, spec, t, size, seed, sky):
    kind, n = spec
    rng = np.random.default_rng(seed * 13 + 1)
    w_, h_ = size
    for i in range(int(n)):
        px, py, sp, ph = rng.random(), rng.random(), rng.uniform(0.6, 1.4), rng.uniform(0, 6.28)
        if kind == "snow":
            x = (px * w_ + math.sin(t * 0.8 * sp + ph) * 30 - t * 14) % w_
            y = (py * h_ + t * 70 * sp) % h_
            s = 2 + int(px * 3)
            d.rectangle((x, y, x + s, y + s), fill=(255, 255, 255))
        elif kind == "ash":
            x = (px * w_ + t * 10) % w_; y = (py * h_ + t * 40 * sp) % h_
            d.rectangle((x, y, x + 3, y + 3), fill=(150, 140, 140))
        elif kind == "embers":
            x = (px * w_ + math.sin(t * sp + ph) * 30) % w_; y = h_ - ((py * h_ + t * 70 * sp) % h_)
            s = 2 + int(px * 3)
            d.rectangle((x, y, x + s, y + s), fill=(255, 150 + int(90 * px), 50))
        elif kind == "bubbles":
            x = px * w_ + math.sin(t * 1.5 * sp + ph) * 16; y = h_ + 10 - ((py * (h_ + 20) + t * 60 * sp) % (h_ + 20))
            s = 4 + int(px * 9)
            d.rectangle((x, y, x + s, y + s), outline=(220, 246, 255), width=2)
        elif kind == "sand":
            x = (px * w_ + t * 170 * sp) % w_; y = h_ * (0.5 + 0.5 * py) + math.sin(t * 2 * sp + ph) * 6
            d.rectangle((x, y, x + 8, y + 1), fill=(240, 220, 170))
        elif kind == "dust":
            x = (px * w_ + math.sin(t * 0.4 * sp + ph) * 30) % w_; y = (py * h_ - t * 14 * sp) % h_
            d.rectangle((x, y, x + 2, y + 2), fill=(200, 210, 240))
        elif kind == "rain":
            x = (px * (w_ + 200) - t * 220 * sp) % (w_ + 200) - 60; y = (py * h_ * 1.1 + t * 900 * sp) % (h_ + 60) - 30
            d.line((x, y, x - 10, y + 30), fill=(190, 215, 255), width=2)


# ------------------------------------------------------------------ placing things
def place(fs, pos, yaw=0.0, scale=1.0, pitch=0.0, roll=0.0):
    R = rot_y(yaw)
    if pitch:
        R = R @ rot_x(pitch)
    if roll:
        R = R @ rot_z(roll)
    return fs.transformed(R, pos, scale)


def explosion_models(center, t, seed=0, radius=8.0, tstart=0.0):
    """A burst of glowing cubes that expands and fades (returns FaceSet or None before it starts)."""
    k = t - tstart
    if k < 0 or k > 2.2:
        return None
    rng = np.random.default_rng(seed + 5)
    n = 70
    dirs = rng.normal(size=(n, 3)); dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    speed = rng.uniform(0.35, 1.0, n)
    parts = []
    for i in range(n):
        p = np.asarray(center) + dirs[i] * radius * speed[i] * (1 - math.exp(-k * 3.0)) * 1.2
        p[1] -= 0.8 * k * k * speed[i]
        s = max(0.05, (0.9 + rng.random() * 0.9) * (1 - k / 2.2))
        col = (255, int(90 + 140 * (1 - k / 2.2) * rng.random()), 40) if k < 1.3 else (90, 84, 90)
        parts.append(box_faces(p, (s, s, s), col, glow=1.0 if k < 1.3 else 0.0))
    return FaceSet.cat(parts)


def smoke_models(base, t, n=22, seed=0, color=(70, 66, 74), rise=26.0):
    rng = np.random.default_rng(seed + 9)
    parts = []
    for i in range(n):
        ph = (t * 0.5 + rng.random()) % 1.0
        p = np.asarray(base) + np.array([math.sin(ph * 5 + i) * (1 + ph * 3), ph * rise, math.cos(ph * 4 + i * 2) * (1 + ph * 3)])
        s = 1.2 + ph * 3.2
        g = 1 - ph * 0.5
        parts.append(box_faces(p, (s, s, s), tuple(int(c * g) for c in color)))
    return FaceSet.cat(parts)
