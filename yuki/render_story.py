"""Story-mode rendering: a stage with a small cast, speech bubbles, emotes, sound effects and a quiet music bed."""
import math, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .audio import SR, silence, synth, synth_character, write_wav, mouth_track
from .character import Rig, YUKI, _clip_composite
from .fonts import font
from .visuals import ACCENTS, wrap
from . import world, sfx as SFX
from .render import (W, H, FPS, PAUSE, TITLE_SECS, chip_img, caption_img, draw_element, write_srt)

FLOOR_STAGE, FLOOR_CENTER, FLOOR_TITLE = 566, 604, 652
STAGE_SCALE = 0.62
SCALE = 0.74
NARR_SCALE, NARR_X, NARR_FLOOR = 0.46, 118, 676
SLOTS = {1: [800], 2: [640, 940], 3: [520, 790, 1060]}


# ------------------------------------------------------------------ small drawings
_bubble_cache, _emote_cache = {}, {}


def bubble_img(text, name, color, tail_x_frac=0.5):
    key = (text, name, color, round(tail_x_frac, 2))
    if key in _bubble_cache:
        return _bubble_cache[key]
    f, fn = font(26, "semibold"), font(19, "bold")
    d0 = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    lines = wrap(text, f, 470)
    tw = max(int(d0.textlength(l, font=f)) for l in lines)
    w = max(tw + 44, int(d0.textlength(name, font=fn)) + 40)
    lh = 35
    h = lh * len(lines) + 56
    im = Image.new("RGBA", (w + 8, h + 34), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((4, 8, w + 2, h + 6), 26, fill=(0, 0, 0, 70))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, w + 1, h), 26, fill=(255, 255, 255, 250))
    tx = int(18 + (w - 36) * tail_x_frac)
    d.polygon([(tx - 14, h - 2), (tx + 14, h - 2), (tx, h + 26)], fill=(255, 255, 255, 250))
    d.text((22, 12), name.upper(), font=fn, fill=color + (255,))
    for i, l in enumerate(lines):
        d.text((22, 36 + i * lh), l, font=f, fill=(40, 34, 60, 255))
    _bubble_cache[key] = (im, tx + 2)
    return _bubble_cache[key]


def emote_img(kind, size=104):
    if kind in _emote_cache:
        return _emote_cache[kind]
    S = 3
    im = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size * S // 2
    u = size * S / 100
    if kind in ("!", "?"):
        col = (255, 96, 70) if kind == "!" else (96, 150, 255)
        f = font(int(100 * u), "bold")
        d.text((c, c), kind, font=f, fill=col + (255,), anchor="mm", stroke_width=int(7 * u), stroke_fill=(255, 255, 255, 255))
    elif kind == "heart":
        col = (255, 96, 140, 255)
        for cx in (35, 65):
            d.ellipse([(cx - 22) * u, 22 * u, (cx + 22) * u, 66 * u], fill=col)
        d.polygon([(15 * u, 54 * u), (85 * u, 54 * u), (50 * u, 92 * u)], fill=col)
    elif kind == "anger":
        col = (232, 56, 60, 255)
        for a_ in (30, 70):
            d.line([(a_ * u, 10 * u), (a_ * u, 90 * u)], fill=col, width=int(12 * u))
            d.line([(10 * u, a_ * u), (90 * u, a_ * u)], fill=col, width=int(12 * u))
    elif kind == "sweat":
        col = (96, 180, 255, 255)
        d.polygon([(50 * u, 6 * u), (78 * u, 56 * u), (22 * u, 56 * u)], fill=col)
        d.ellipse([22 * u, 36 * u, 78 * u, 92 * u], fill=col)
        d.ellipse([34 * u, 56 * u, 46 * u, 70 * u], fill=(255, 255, 255, 200))
    elif kind == "zzz":
        f = font(int(70 * u), "bold")
        d.text((c, c), "Zz", font=f, fill=(120, 130, 255, 255), anchor="mm", stroke_width=int(5 * u), stroke_fill=(255, 255, 255, 255))
    elif kind == "star":
        col = (255, 208, 64, 255)
        pts = []
        for k in range(8):
            r = 46 if k % 2 == 0 else 14
            a = math.pi / 4 * k - math.pi / 2
            pts.append((50 * u + r * u * math.cos(a), 50 * u + r * u * math.sin(a)))
        d.polygon(pts, fill=col)
    else:  # dots
        for cx in (22, 50, 78):
            d.ellipse([(cx - 8) * u, 42 * u, (cx + 8) * u, 58 * u], fill=(120, 124, 150, 255))
    _emote_cache[kind] = im.resize((size, size), Image.LANCZOS)
    return _emote_cache[kind]


# ------------------------------------------------------------------ timeline + audio
def _voice_for(b, cast, args, idx, tmp):
    if b.speaker and not args.audio_dir:
        return synth_character(b.text, cast[b.speaker], args, tmp, emotion=b.emotion)
    return synth(b.text, args, idx, tmp, emotion=(b.emotion if "face" in b.cues else None))


def build_timeline(beats, cast, args, tmp):
    tmp = Path(tmp)
    parts, tl, t0 = [], [], 0.0
    n_voiced = sum(1 for b in beats if not b.title)
    k = 0
    for b in beats:
        if b.title:
            a, speech, dur = silence(TITLE_SECS), 0.0, TITLE_SECS
        else:
            print(f"  voicing line {k + 1}/{n_voiced}" + (f" ({b.speaker})" if b.speaker else ""), flush=True)
            a = _voice_for(b, cast, args, k, tmp)
            k += 1
            speech = len(a) / SR
            gap = PAUSE if not b.speaker else 0.28
            tail = b.text.rstrip(" \"\u201d')")
            if tail.endswith(("...", "\u2026")):
                gap += 0.25                                  # trailing off: let it hang
            elif tail.endswith("?") and len(tail.split()) <= 6:
                gap += 0.2                                   # a setup line: leave room for the punchline
            a = np.concatenate([a, silence(gap)])
            dur = speech + gap
        parts.append(a)
        tl.append(dict(beat=b, start=t0, speech=speech, dur=dur))
        t0 += dur
    voice = np.concatenate(parts + [silence(0.9)])
    peak = np.abs(voice).max()
    if peak > 0:
        voice = voice / peak * 0.9
    return tl, voice, t0 + 0.9


def mix(tl, voice, total, music_on=True):
    n = len(voice)
    out = voice.copy()
    n_fx = 0
    ext = n
    for e in tl:
        b = e["beat"]
        for fr, name in b.sfx:
            x = SFX.get(name)
            if x is None:
                continue
            at = e["start"] + (0.06 if fr <= 0 else fr * max(e["speech"], 0.2))
            i = int(at * SR)
            gain = 0.34 if name in ("rain", "wind", "cricket") else 0.6
            ext = max(ext, i + len(x))
            if i + len(x) > len(out):
                out = np.concatenate([out, np.zeros(i + len(x) - len(out), np.float32)])
            out[i:i + len(x)] += x * gain
            n_fx += 1
    if music_on:
        m = SFX.music(len(out) / SR + 0.5, "story")
        m = np.pad(m, (0, max(0, len(out) - len(m))))
        env = np.convolve(np.abs(voice), np.ones(int(0.12 * SR)) / int(0.12 * SR), mode="same")
        env = np.concatenate([env, np.zeros(len(out) - len(env))])[: len(out)]
        duck = 1 - 0.75 * np.clip(env / 0.18, 0, 1)
        fade = np.minimum(1, np.minimum(np.arange(len(out)) / (SR * 2.0), (len(out) - np.arange(len(out))) / (SR * 2.5)))
        out += m[: len(out)] * duck * fade * 0.075
    peak = np.abs(out).max()
    if peak > 0.97:
        out = out / peak * 0.97
    print(f"  sound effects placed: {n_fx}", flush=True)
    return out, len(out) / SR


# ------------------------------------------------------------------ render
def head_top(rig):
    return rig.floor_y - 628 * rig.scale


def render_story(beats, cast, args, out_path, tmp):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tl, voice, t_voice = build_timeline(beats, cast, args, tmp)
    audio, total = mix(tl, voice, t_voice, music_on=getattr(args, "music", True))
    write_srt(tl, out_path.with_suffix(".srt"))
    n_frames = int(math.ceil(total * FPS))
    full = Path(tmp) / "full.wav"
    write_wav(full, audio)
    lvl, amp = mouth_track(voice, n_frames, FPS)

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

    yuki = Rig(W / 2, FLOOR_CENTER, SCALE, YUKI)
    chars = {}
    colors = {n: ACCENTS[i % len(ACCENTS)] for i, n in enumerate(cast)}
    cur, prev_theme, theme_changed_at, dt = 0, tl[0]["beat"].theme, -99.0, 1.0 / FPS
    heading_chip, run, prev_lv, last_beat = {}, 0, 0, -1
    for fr in range(n_frames):
        t = fr / FPS
        while cur + 1 < len(tl) and t >= tl[cur + 1]["start"]:
            cur += 1
            if tl[cur]["beat"].theme != tl[cur - 1]["beat"].theme:
                prev_theme = tl[cur - 1]["beat"].theme
                theme_changed_at = t
        e = tl[cur]; b = e["beat"]; lt = t - e["start"]
        new_beat = cur != last_beat
        last_beat = cur
        bg = world.camera(b.theme, t)
        k = (t - theme_changed_at) / 0.5
        if 0 <= k < 1 and prev_theme != b.theme:
            bg = Image.blend(world.camera(prev_theme, t), bg, k * k * (3 - 2 * k))
        frame = bg.convert("RGBA")
        if b.heading and not b.title:
            if b.heading not in heading_chip:
                heading_chip[b.heading] = chip_img(b.heading, ACCENTS[len(heading_chip) % len(ACCENTS)])
            _clip_composite(frame, heading_chip[b.heading], 34, 26)
        if b.visual is not None:
            fo = max(0.0, (e["dur"] - lt) / 0.22) if lt > e["dur"] - 0.22 else 1.0
            for el in b.visual.elements:
                draw_element(frame, el, lt, fo)

        # ---- who stands where
        stage = [] if b.title else list(b.onstage)
        slots = SLOTS.get(len(stage), [])
        for name, sx in zip(stage, slots):
            if name not in chars:
                chars[name] = Rig(-170 if sx < W / 2 else W + 170, FLOOR_STAGE, STAGE_SCALE, cast[name]["look"])
            chars[name].target_x = sx
        for name in list(chars):
            if name not in stage:
                r = chars[name]
                r.target_x = -230 if r.x < W / 2 else W + 230
                if r.x < -200 or r.x > W + 200:
                    del chars[name]
        if new_beat:
            if b.title:
                yuki.scale, yuki.target_x = SCALE, 250
            elif stage:
                yuki.scale, yuki.target_x = NARR_SCALE, NARR_X
            else:
                yuki.scale, yuki.target_x = SCALE, W / 2
        yfloor = FLOOR_TITLE if b.title else (NARR_FLOOR if stage else FLOOR_CENTER)
        yuki.floor_y += (yfloor - yuki.floor_y) * (1 - math.exp(-dt * 5))

        # ---- mouth for whoever is talking
        speaking = lt < e["speech"]
        lv = int(lvl[fr]) if speaking else 0
        if lv != prev_lv:
            run += 1
            prev_lv = lv
        mouth = {0: 0, 1: 3, 2: (1 if run % 2 == 0 else 3), 3: (2 if run % 3 else 1)}[lv]
        if b.face == "happy" and lv >= 3:
            mouth = 4
        wig = (0.4 + 0.9 * float(amp[fr])) if speaking else 0.2
        spk_amp = float(amp[fr]) if speaking else 0.0
        hop = 1 if (new_beat or lt < dt * 1.5) and b.emotion in ("shocked", "excited") and lt < dt * 1.5 else 0

        # ---- update + draw (back to front by x)
        riglist = []
        narr = b.speaker is None
        yface = b.face if narr else "neutral"
        ypose = ("wave" if b.title else b.pose) if (speaking and narr) or b.title else "relax"
        yuki.update(dt, pose=ypose, tilt=(3.0 if cur % 2 == 0 else -3.0) * (1 if (speaking and narr) else 0.4),
                    wiggle=wig if narr else 0.2, speaking=spk_amp if narr else 0.0, face=yface,
                    gaze=1.0 if stage else 0.0, hop=hop if narr else 0)
        riglist.append((yuki.x - 1000, yuki, mouth if narr else 0, True))
        for name, r in chars.items():
            is_spk = name == b.speaker
            face = b.face if is_spk else ("shocked" if b.emote == "!" and name in stage else
                                          "curious" if b.emote == "?" and name in stage else "neutral")
            pose = b.pose if (is_spk and speaking) else "relax"
            r.update(dt, pose=pose, tilt=(3.0 if is_spk else -2.0), wiggle=wig if is_spk else 0.2,
                     speaking=spk_amp if is_spk else 0.0, face=face, gaze=0.0, hop=hop)
            riglist.append((r.x, r, mouth if is_spk else 0, False))
        for _, r, mth, _y in sorted(riglist, key=lambda z: z[0]):
            r.draw(frame, mth, fr in blink_frames)

        # ---- emote above the head of the speaker / narrator
        if b.emote and 0.18 <= lt < 1.9 and not b.title:
            tgt = chars.get(b.speaker) if b.speaker in chars else (yuki if not stage else (chars[stage[0]] if stage[0] in chars else yuki))
            p = min(1.0, (lt - 0.18) / 0.22)
            sc = 0.5 + 0.5 * (1 + 2.7 * (p - 1) ** 3 + 1.7 * (p - 1) ** 2)
            em = emote_img(b.emote)
            if sc != 1:
                em = em.resize((max(1, int(em.width * sc)), max(1, int(em.height * sc))), Image.BILINEAR)
            if lt > 1.6:
                a = em.getchannel("A").point(lambda v, kk=max(0, (1.9 - lt) / 0.3): int(v * kk)); em = em.copy(); em.putalpha(a)
            _clip_composite(frame, em, int(tgt.x + 62 * tgt.scale / 0.74), int(head_top(tgt) + 14 * tgt.scale / 0.74 + (1 - p) * 20))

        # ---- bubble (dialogue) or caption (narration)
        if not b.title and speaking and e.get("caps"):
            if b.speaker and b.speaker in chars:
                r = chars[b.speaker]
                bi, tx = bubble_img(b.text, b.speaker, colors[b.speaker])
                bx = int(max(14, min(W - bi.width - 14, r.x - tx)))
                by = int(max(8, head_top(r) - bi.height + 6))
                if lt < 0.14:
                    sc = 0.8 + 0.2 * lt / 0.14
                    bi = bi.resize((int(bi.width * sc), int(bi.height * sc)), Image.BILINEAR)
                _clip_composite(frame, bi, bx, by)
            else:
                cw = 1000 if not stage else 900
                for text, a, z in e["caps"]:
                    if a <= lt < z or (text == e["caps"][-1][0] and lt >= a):
                        ci = caption_img(text, cw)
                        _clip_composite(frame, ci, (W - cw) // 2, H - 22 - ci.height)
                        break
        ff.stdin.write(frame.convert("RGB").tobytes())
        if fr % (FPS * 20) == 0:
            print(f"  frame {fr}/{n_frames}", flush=True)
    ff.stdin.close(); ff.wait()
    wavf = Path(tmp) / "full.wav"
    subprocess.run(["ffmpeg", "-y", "-i", str(silent), "-i", str(wavf), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "160k", "-shortest", str(out_path)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return total
