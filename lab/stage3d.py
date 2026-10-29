"""Draws one frame of a blocky-3D scene from the director's plan: camera moves, people, animals, props and events."""
import math
import numpy as np
from PIL import Image
from . import voxel as V
from . import overlays as O
from .canvas import ease_out, ease_in_out

W, H = 1280, 720
ACC = O.ACCENTS


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def find_focus(world):
    """A flat, open spot where the action happens (near the middle, away from water)."""
    env = world.env
    if env == "space":
        return np.array([32.0, 10.0, 32.0])
    if env == "islands":
        return np.array([32.0, float(world.column_top(32, 32)), 32.0])
    if env == "cave":
        best, bs = (32, 32), 1e9
        for x in range(14, 50, 2):
            for z in range(14, 50, 2):
                hs = world.hm[x - 2:x + 3, z - 2:z + 3]
                sc = hs.max() - hs.min() + 0.02 * (abs(x - 32) + abs(z - 32))
                if sc < bs:
                    bs, best = sc, (x, z)
        return np.array([best[0] + 0.5, float(world.column_top(*best)), best[1] + 0.5])
    anchor = {"volcano": (32, 12), "ocean": (32, 32)}.get(env, (32, 32))
    best, bs = None, 1e9
    for x in range(10, 54, 2):
        for z in range(10, 54, 2):
            hs = world.hm[x - 2:x + 3, z - 2:z + 3]
            g = world.grid[x, int(hs.max()) - 1, z]
            if g in (V.WATER, V.LEAF, V.LAVA, V.CACTUS) and env != "ocean":
                continue
            if env == "volcano" and math.hypot(x - 32, z - 32) < 11:
                continue
            sc = (hs.max() - hs.min()) * 2.0 + 0.05 * math.hypot(x - anchor[0], z - anchor[1] - (14 if env == "volcano" else 0))
            if env == "ocean":
                sc += 0 if g != V.WATER else 4
            if sc < bs:
                bs, best = sc, (x, z)
    best = best or (32, 32)
    return np.array([best[0] + 0.5, float(world.column_top(*best)), best[1] + 0.5])


class Stage3D:
    def __init__(self, scene):
        self.sc = scene
        self.seed = scene["seed"]
        self.world = V.build_world(scene["env"], self.seed, scene.get("tod"))
        self.focus = find_focus(self.world)
        self.fog_boost = 1.0

    # ---- camera
    def camera(self, spec, u, t_abs, actors_pos):
        w = self.world
        f = self.focus
        k = spec["k"]
        r, h, a0, da, fov = spec["r"], spec["h"], spec["a0"], spec["da"], spec["fov"]
        e = ease_in_out(clamp(u))
        tgt = f + np.array([0, 1.3, 0])
        if w.env == "space":
            r *= 1.2; h += 2
        small = w.env in ("cave", "underwater")
        if small:
            r *= 0.8
        a = a0 + da * u
        if k == "orbit":
            pos = f + np.array([math.cos(a) * r, h, math.sin(a) * r])
        elif k == "orbit_low":
            pos = f + np.array([math.cos(a) * r * 0.7, 1.4 + h * 0.15, math.sin(a) * r * 0.7])
            tgt = f + np.array([0, 2.2, 0])
        elif k == "dolly":
            d = np.array([math.cos(a0), 0, math.sin(a0)])
            pos = f + d * (r * 1.6 * (1 - e) + r * 0.55 * e) + np.array([0, h * 0.7, 0])
        elif k == "crane":
            pos = f + np.array([math.cos(a0) * r, 1.5 + (h + 7) * e, math.sin(a0) * r])
            tgt = f + np.array([0, 1.0 + 1.5 * e, 0])
        elif k == "fly":
            d = np.array([math.cos(a0), 0, math.sin(a0)])
            side = np.array([-d[2], 0, d[0]])
            pos = f + side * (-20 + 40 * e) * (1 if da > 0 else -1) - d * r * 0.9 + np.array([0, h + 4, 0])
            tgt = f + np.array([0, 2, 0]) + side * (-6 + 12 * e) * (1 if da > 0 else -1)
        elif k == "top":
            pos = f + np.array([math.cos(a) * r * 0.75, h + 7, math.sin(a) * r * 0.75])
            tgt = f + np.array([0, 0, 0])
        elif k == "pan_look":
            pos = f + np.array([math.cos(a0) * r, h * 0.6 + 1.5, math.sin(a0) * r])
            side = np.array([-math.sin(a0), 0, math.cos(a0)])
            tgt = f + side * (-7 + 14 * e) * (1 if da > 0 else -1) + np.array([0, 2, 0])
        else:   # chase: stay behind the first walking person
            base = actors_pos[0] if actors_pos else f
            pos = base + np.array([math.cos(a0) * r * 0.55, h * 0.45 + 1.2, math.sin(a0) * r * 0.55])
            tgt = base + np.array([0, 1.4, 0])
        # stay above the ground
        if w.env not in ("cave", "space", "underwater"):
            gx = w.ground_y(pos[0], pos[2])
            pos[1] = max(pos[1], gx + 1.6)
        elif w.env == "cave":
            pos[1] = max(pos[1], f[1] + 1.4)
        elif w.env == "underwater":
            pos[1] = max(pos[1], w.ground_y(pos[0], pos[2]) + 1.4)
        if w.env != "space":                                   # never put the camera inside a block
            for _ in range(14):
                if w.get(int(pos[0]), int(pos[1]), int(pos[2])) not in (V.AIR, V.WATER):
                    pos[1] += 1.0
                else:
                    break
        sh = spec.get("shake", 0.0)
        if sh:
            rr = np.random.default_rng(int(t_abs * 24))
            pos = pos + rr.normal(0, 0.12 * sh, 3)
        return V.Cam(pos, tgt, fov)

    # ---- positions around the focus
    def slot_pos(self, slot, n=1, radius=2.4, ang0=0.3):
        if n <= 1 and slot == 0:
            return self.focus.copy()
        a = ang0 + slot * (math.tau / max(2, n + 1))
        p = self.focus + np.array([math.cos(a) * radius, 0, math.sin(a) * radius])
        p[1] = self.world.ground_y(p[0], p[2])
        return p

    # ---- the frame
    def frame(self, shot, t, dur, mouth=0.0, amp=0.0, t_abs=0.0):
        u = clamp(t / max(0.1, dur))
        w = self.world
        models, over, pos_list = [], [], []
        flash = 0.0
        shake_extra = 0.0
        shot_seed = shot["sent"][0] * 13 if shot.get("sent") else 0
        acts = shot["actors"]
        out_p = clamp((t - (dur - 0.2)) / 0.2)
        n_h = sum(1 for a in acts if a["k"] == "human")
        for a in acts:
            k = a["k"]
            lt = t - clamp(a.get("f_in", 0.0), 0, 0.85) * max(0.2, dur - 0.5)
            if lt < 0:
                continue
            pop = ease_out(clamp(lt / 0.4)) * (1 - out_p * 0.8)
            if k == "human":
                p0 = self.slot_pos(a["slot"], a["n"], 2.0 + 0.4 * a["slot"], 0.4 + a["slot"])
                yaw = math.pi * 0.85 + a["slot"] * 0.5 + math.sin(t_abs * 0.4) * 0.15
                act = a["action"]
                if a.get("walk") or act in ("walk", "run"):
                    act = "run" if act == "run" else "walk"
                    ang = a["seed"] * 0.5
                    d = np.array([math.cos(ang), 0, math.sin(ang)])
                    p0 = p0 + d * (-5 + 10 * u)
                    p0[1] = w.ground_y(p0[0], p0[2])
                    yaw = math.atan2(d[0], d[2])
                p1 = p0.copy()
                if act in ("float",):
                    p1[1] += 1.2
                if act == "fall":
                    p1[1] += 6 * (1 - ease_out(clamp(lt / 1.2)))
                if w.env == "ocean" and w.get(int(p1[0]), int(p1[1]) - 1, int(p1[2])) == V.WATER:
                    p1[1] = max(p1[1], w.water_y or p1[1])
                m = 0.5 + 0.5 * math.sin(t_abs * 11 + a["seed"])
                blink = (t_abs + a["seed"] * 0.7) % 3.3 < 0.12
                fs = V.human(a["role"], a["seed"], act, t_abs + a["seed"], mouth=(mouth if act in ("talk", "point", "shrug", "idle") else 0.2 * m), expression=a.get("expr", "neutral"), blink=blink)
                models.append(V.place(fs, p1, yaw, scale=pop))
                pos_list.append(p1)
            elif k == "critter":
                p0 = self.slot_pos(a["slot"], 4, 3.6, 2.0 + a["seed"])
                kind = a["kind"]
                if kind == "bird":
                    p0 = p0 + np.array([math.sin(t_abs * 0.8) * 3, 5 + math.sin(t_abs * 1.7), math.cos(t_abs * 0.8) * 3])
                elif kind == "fish":
                    p0 = p0 + np.array([math.sin(t_abs * 0.6 + a["seed"]) * 4, 2.5 + math.sin(t_abs), math.cos(t_abs * 0.6 + a["seed"]) * 4])
                else:
                    p0 = p0 + np.array([math.sin(t_abs * 0.5 + a["seed"]) * 1.2, 0, math.cos(t_abs * 0.5 + a["seed"]) * 1.2])
                    p0[1] = w.ground_y(p0[0], p0[2])
                yaw = t_abs * 0.5 + a["seed"]
                models.append(V.place(V.critter(kind, a["seed"], t_abs), p0, yaw, scale=pop * 1.1))
            elif k == "prop":
                try:
                    pm = V.prop(V.ENTITY_TO_PROP.get(a["name"], "crate"), a["seed"])
                except Exception:
                    pm = V.prop("crate", 0)
                if not isinstance(pm, V.FaceSet) or len(pm) == 0:
                    continue
                if a.get("sky") and w.env in ("underwater", "cave"):
                    if a.get("label") and lt > 0.3:
                        over.append((O.label_img(a["label"]), 36, 100 + 70 * a["slot"], clamp((lt - 0.3) / 0.3)))
                    continue
                ang = 0.9 + a["slot"] * 2.1 + a["seed"] * 0.3
                big = a["name"] in ("whale", "shark", "dino", "ufo", "plane", "pyramid", "ringed", "planet", "earth", "sun", "moon", "galaxy", "blackhole")
                if a.get("sky"):
                    rad = 9 + 2 * a["slot"]
                    p = self.focus + np.array([math.cos(ang) * rad, 7 + 2.5 * a["slot"] + math.sin(t_abs * 0.8 + a["seed"]) * 0.6, math.sin(ang) * rad])
                    sc = (1.0 if big else 0.9) * pop
                    if w.env == "space":
                        p[1] = self.focus[1] + 8 + 3 * a["slot"]
                else:
                    rad = 5 + 2 * a["slot"]
                    p = self.focus + np.array([math.cos(ang) * rad, 0, math.sin(ang) * rad])
                    p[1] = w.ground_y(p[0], p[2]) + (2.0 if a["name"] in ("whale", "shark", "fish", "jellyfish") else 0.0)
                    if a["name"] in ("whale", "shark", "fish", "jellyfish") and w.env == "plains":
                        p[1] += 4
                    sc = (1.1 if big else 1.0) * pop
                    if a["name"] in ("whale", "shark"):
                        p[0] += math.sin(t_abs * 0.35) * 6; p[2] += math.cos(t_abs * 0.35) * 6
                yaw = t_abs * 0.5 if a.get("sky") else ang + 1.6
                if a["name"] in ("rocket",):
                    p = self.focus + np.array([5, 1.0 + 3 * ease_out(clamp(lt / 3.0)) ** 2 * 6, 3])
                    yaw = 0
                models.append(V.place(pm, p, yaw, scale=sc, pitch=0.0))
                if a["name"] == "rocket":
                    models.append(V.smoke_models(p - np.array([0, 5, 0]), t_abs, 10, 3, (255, 160, 60), 6))
                if a.get("label") and lt > 0.3:
                    over.append((O.label_img(a["label"]), 36, 100 + 70 * a["slot"], clamp((lt - 0.3) / 0.3)))
            elif k == "label":
                over.append((O.label_img(a["text"]), 36, 100, clamp(lt / 0.4) * (1 - out_p)))
            elif k == "stat_small":
                from .stage2d import count_text
                im = O.chip_img(count_text(a["display"], clamp(lt / 1.0)), ACC[1], 34)
                over.append((im, W / 2 - im.width / 2, 40 + (1 - ease_out(clamp(lt / 0.5))) * 20, clamp(lt / 0.3) * (1 - out_p)))
        # events
        for ev in shot.get("events", []):
            te = ev["f"] * dur
            lt = t - te
            nm = ev["name"]
            if nm == "meteor":
                tgt = self.focus + np.array([7, 0, 5])
                tgt[1] = w.ground_y(tgt[0], tgt[2])
                fall = 1.7
                if -0.2 < lt < fall:
                    k = clamp(lt / fall)
                    p = tgt + np.array([-34, 38, -26]) * (1 - k)
                    models.append(V.place(V.prop("asteroid", 4), p, lt * 3, scale=1.4))
                    for j in range(7):
                        kk = clamp(k - j * 0.025)
                        models.append(V.place(V.prop("fire", j), tgt + np.array([-34, 38, -26]) * (1 - kk), 0, scale=0.6 * (1 - j * 0.1)))
                elif lt >= fall:
                    ex = V.explosion_models(tgt + np.array([0, 1.5, 0]), t, 3, 9.0, te + fall)
                    if ex is not None:
                        models.append(ex)
                    if lt - fall < 0.5:
                        shake_extra = 1.0 - (lt - fall) / 0.5
                        flash = max(flash, 0.6 * (1 - (lt - fall) / 0.25)) if lt - fall < 0.25 else flash
                    models.append(V.smoke_models(tgt, t_abs, 14, 2, (60, 56, 62), 12))
            elif nm == "eruption" and hasattr(w, "volcano_top"):
                cx, top, cz = w.volcano_top
                models.append(V.smoke_models(np.array([cx, top - 2, cz]), t_abs, 30, 5, (66, 60, 68), 30))
                models.append(V.smoke_models(np.array([cx, top - 3, cz]), t_abs * 1.7, 26, 8, (255, 120, 30), 14))
            elif nm == "lightning" and 0 <= lt < 0.7:
                flash = max(flash, 0.7 if int(lt * 12) % 2 == 0 else 0.2)
                p = self.focus + np.array([9, 0, -6])
                models.append(V.place(V.prop("bolt", 1), p + np.array([0, 14, 0]), 0.6, scale=2.4))
        spec = dict(shot["cam"])
        spec["shake"] = max(spec.get("shake", 0.0), shake_extra * 3.0)
        cam = self.camera(spec, u, t_abs, pos_list)
        img = V.render(w, cam, t_abs, models, (W, H), seed=self.seed)
        frame = img.convert("RGBA")
        if flash > 0.01:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * min(1, flash)))))
        if not getattr(self, "no_labels", False):
            for im, x, y, a in over:
                O.paste(frame, im, x, y, a)
        return frame
