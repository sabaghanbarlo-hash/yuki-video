"""Timeline building and frame rendering."""
import math, re, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageChops

from .audio import SR, silence, synth, write_wav, mouth_track
from .character import Rig, _clip_composite
from .fonts import font
from .visuals import ACCENTS, card, wrap
from . import world

W, H, FPS = 1280, 720, 24
PAUSE = 0.38
TITLE_SECS = 3.0
SPLIT_X, CENTER_X = 250, 640
FLOOR_SPLIT, FLOOR_CENTER = 652, 604
SCALE = 0.74


# ------------------------------------------------------------------ helpers
def chunk_caption(text, max_chars=64):
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = []
    for s in sents:
        cur = ""
        for w in s.split():
            if cur and len(cur) + 1 + len(w) > max_chars:
                chunks.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            chunks.append(cur)
    merged = []
    for c in chunks:
        if merged and len(c) < 16 and len(merged[-1]) + len(c) < max_chars + 8:
            merged[-1] += " " + c
        else:
            merged.append(c)
    return merged or [text]


_cap_cache = {}


def caption_img(text, width):
    key = (text, width)
    if key in _cap_cache:
        return _cap_cache[key]
    f = font(36, "semibold")
    lines = wrap(text, f, width - 70)
    lh = 48
    h = lh * len(lines) + 34
    im = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, width - 1, h - 1), 30, fill=(24, 20, 52, 205))
    for i, l in enumerate(lines):
        tw = d.textlength(l, font=f)
        d.text(((width - tw) / 2, 17 + i * lh), l, font=f, fill=(255, 255, 255, 255))
    _cap_cache[key] = im
    return im


def chip_img(text, color):
    f = font(24, "semibold")
    d0 = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    w = int(d0.textlength(text.upper(), font=f)) + 44
    im = Image.new("RGBA", (w, 46), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 45), 23, fill=color + (235,))
    d.text((22, 9), text.upper(), font=f, fill=(34, 30, 64, 255))
    return im


def reveal_times(text, labels, speech):
    n = len(labels)
    low = text.lower()
    fr = []
    for lab in labels:
        pos = None
        for k in [x for x in re.findall(r"[a-z']+", lab.lower()) if len(x) > 2]:
            i = low.find(k)
            if i >= 0:
                pos = i / max(1, len(low)); break
        fr.append(pos)
    times, prev = [], 0.05
    for i, f in enumerate(fr):
        if f is None:
            f = (i + 0.6) / (n + 0.4)
        tt = max(0.3 + f * speech * 0.88, prev + 0.4)
        times.append(tt); prev = tt
    if times and times[-1] > max(speech, 0.3 + 0.4 * n):
        lim = max(speech * 0.95, 0.3 + 0.4 * (n - 1))
        times = [0.3 + (t - 0.3) * (lim - 0.3) / (times[-1] - 0.3) for t in times]
    return times


def ease_out_back(p):
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def draw_element(frame, el, lt, fade_out):
    p = (lt - el.t_in) / max(el.dur, 1e-3)
    if p <= 0:
        return
    p = min(p, 1.0)
    img, x, y = el.img, el.x, el.y
    alpha = fade_out
    if el.anim == "pop" and p < 1:
        sc = 0.62 + 0.38 * ease_out_back(p)
        nw, nh = max(1, int(img.width * sc)), max(1, int(img.height * sc))
        x += (img.width - nw) // 2; y += (img.height - nh) // 2
        img = img.resize((nw, nh), Image.BILINEAR)
        alpha *= min(1.0, p * 2.4)
    elif el.anim == "rise" and p < 1:
        e = 1 - (1 - p) ** 3
        y += int((1 - e) * 38)
        alpha *= min(1.0, p * 2.6)
    elif el.anim == "fade" and p < 1:
        alpha *= p
    elif el.anim == "wipe" and p < 1:
        e = 1 - (1 - p) ** 2
        cw = max(1, int(img.width * e))
        img = img.crop((0, 0, cw, img.height))
    if alpha < 0.999:
        a = img.getchannel("A").point(lambda v, k=alpha: int(v * k))
        img = img.copy(); img.putalpha(a)
    _clip_composite(frame, img, x, y)


# ------------------------------------------------------------------ timeline
def build_timeline(beats, args, tmp):
    tmp = Path(tmp)
    parts, tl, t0 = [], [], 0.0
    for i, b in enumerate(beats):
        if b.title:
            a = silence(TITLE_SECS)
            speech, dur = 0.0, TITLE_SECS
        else:
            idx = i - (1 if beats[0].title else 0)
            print(f"  voicing beat {idx + 1}/{len(beats) - (1 if beats[0].title else 0)}", flush=True)
            a = synth(b.text, args, idx, tmp)
            speech = len(a) / SR
            a = np.concatenate([a, silence(PAUSE)])
            dur = speech + PAUSE
        parts.append(a)
        tl.append(dict(beat=b, start=t0, speech=speech, dur=dur))
        t0 += dur
    audio = np.concatenate(parts)
    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio / peak * 0.9
    return tl, audio, t0


def finalize_visuals(tl):
    for e in tl:
        v = e["beat"].visual
        if v is None:
            continue
        labels = v.meta.get("labels")
        if v.item_idx:
            lab = labels if labels and len(labels) == len(v.item_idx) else [""] * len(v.item_idx)
            times = reveal_times(e["beat"].text, lab, e["speech"])
            for k, idx in enumerate(v.item_idx):
                v.elements[idx].t_in = times[k]


def write_srt(tl, path):
    def ts(x):
        return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(x % 1 * 1000):03d}"
    n = 1
    with open(path, "w", encoding="utf-8") as f:
        for e in tl:
            if e["beat"].title:
                continue
            chunks = chunk_caption(e["beat"].text)
            wts = np.array([len(c) for c in chunks], float)
            bounds = np.concatenate([[0], np.cumsum(wts / wts.sum())]) * e["speech"]
            for k, c in enumerate(chunks):
                e.setdefault("caps", []).append((c, bounds[k], bounds[k + 1]))
                f.write(f"{n}\n{ts(e['start'] + bounds[k])} --> {ts(e['start'] + bounds[k + 1])}\n{c}\n\n")
                n += 1


# ------------------------------------------------------------------ main render
def render(beats, args, out_path, tmp):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tl, audio, total = build_timeline(beats, args, tmp)
    finalize_visuals(tl)
    write_srt(tl, out_path.with_suffix(".srt"))
    n_frames = int(math.ceil(total * FPS))
    full = Path(tmp) / "full.wav"
    write_wav(full, audio)
    lvl, amp = mouth_track(audio, n_frames, FPS)

    rng = np.random.default_rng(5)
    blink_frames, t = set(), 2.0
    while t < total:
        f0 = int(t * FPS)
        blink_frames.update({f0, f0 + 1, f0 + 2})
        t += rng.uniform(2.6, 5.2)

    silent = Path(tmp) / "video_silent.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(silent)],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    rig = Rig(CENTER_X, FLOOR_CENTER, SCALE)
    cur = 0
    prev_theme = tl[0]["beat"].theme
    theme_changed_at = -99.0
    dt = 1.0 / FPS
    heading_chip = {}
    run, prev_lv = 0, 0
    for fr in range(n_frames):
        t = fr / FPS
        while cur + 1 < len(tl) and t >= tl[cur + 1]["start"]:
            cur += 1
            if tl[cur]["beat"].theme != tl[cur - 1]["beat"].theme:
                prev_theme = tl[cur - 1]["beat"].theme
                theme_changed_at = t
        e = tl[cur]; b = e["beat"]; lt = t - e["start"]
        # ---- background (with crossfade on theme change)
        bg = world.camera(b.theme, t)
        k = (t - theme_changed_at) / 0.5
        if 0 <= k < 1 and prev_theme != b.theme:
            bg = Image.blend(world.camera(prev_theme, t), bg, k * k * (3 - 2 * k))
        frame = bg.convert("RGBA")
        # ---- section chip
        if b.heading and not b.title:
            if b.heading not in heading_chip:
                heading_chip[b.heading] = chip_img(b.heading, ACCENTS[len(heading_chip) % len(ACCENTS)])
            _clip_composite(frame, heading_chip[b.heading], 34, 26)
        # ---- visual
        if b.visual is not None:
            fade_out = 1.0
            if lt > e["dur"] - 0.22:
                fade_out = max(0.0, (e["dur"] - lt) / 0.22)
            for el in b.visual.elements:
                draw_element(frame, el, lt, fade_out)
        # ---- character
        speaking = lt < e["speech"]
        lv = int(lvl[fr]) if speaking else 0
        if lv != prev_lv:
            run += 1
            prev_lv = lv
        # vary the open shapes from syllable to syllable so the mouth doesn't loop mechanically
        mouth = {0: 0, 1: 3, 2: (1 if run % 2 == 0 else 3), 3: (2 if run % 3 else 1)}[lv]
        if b.face == "happy" and lv >= 3:
            mouth = 4
        pose = b.pose if (speaking or lt < e["speech"] + 0.25) else "relax"
        if b.title:
            pose = "wave"
        if b.layout == "split":
            rig.target_x = SPLIT_X
            tgt_floor = FLOOR_SPLIT
        else:
            rig.target_x = CENTER_X
            tgt_floor = FLOOR_CENTER
        rig.floor_y += (tgt_floor - rig.floor_y) * (1 - math.exp(-dt * 5))
        tilt = (3.0 if (cur % 2 == 0) else -3.0) * (1 if speaking else 0.4)
        if b.face == "curious":
            tilt = 5.0
        gaze = 1.0 if (b.layout == "split" and lt < e["dur"] * 0.7) else 0.0
        hop = 1 if (lt < dt * 1.5 and b.face in ("happy",) and b.pose in ("cheer", "wave")) else 0
        wig = (0.4 + 0.9 * float(amp[fr])) if speaking else 0.2
        rig.update(dt, pose=pose, tilt=tilt, wiggle=wig, speaking=float(amp[fr]) if speaking else 0.0,
                   face=b.face, gaze=gaze, hop=hop)
        rig.draw(frame, mouth, fr in blink_frames)
        # ---- captions
        if not b.title and speaking and e.get("caps"):
            cw = 760 if b.layout == "split" else 1000
            for text, a, z in e["caps"]:
                if a <= lt < z or (text == e["caps"][-1][0] and lt >= a):
                    ci = caption_img(text, cw)
                    if b.layout == "split":
                        _clip_composite(frame, ci, 484, H - 24 - ci.height - 6)
                    else:
                        _clip_composite(frame, ci, (W - cw) // 2, H - 22 - ci.height)
                    break
        ff.stdin.write(frame.convert("RGB").tobytes())
        if fr % (FPS * 20) == 0:
            print(f"  frame {fr}/{n_frames}", flush=True)
    ff.stdin.close(); ff.wait()
    subprocess.run(["ffmpeg", "-y", "-i", str(silent), "-i", str(full), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "160k", "-shortest", str(out_path)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return total
