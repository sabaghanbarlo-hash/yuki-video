#!/usr/bin/env python3
"""Call of Yuki video generator.

Usage:
    python generate.py stories/my-script.txt [--tts edge|none] [--voice en-US-AriaNeural]
                       [--audio-dir audio/my-script] [--out output/my-script.mp4]

Script format (plain text):
    # Video title            (optional, shown on an intro card)
    ## Section name          (optional, shown as a chip until the next ##)
    Paragraphs separated by blank lines. One paragraph = one scene.

Voice options:
    --tts edge       free Microsoft Edge voices (placeholder voice, needs internet)
    --tts none       no network: silent timing based on word count (layout testing)
    --audio-dir DIR  use your own recordings: DIR/01.wav|mp3, DIR/02.wav|mp3 ... one per
                     paragraph (title card is not numbered). Overrides --tts. This is where
                     a cloned or recorded voice plugs in later.
"""
import argparse, asyncio, math, os, re, subprocess, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1280, 720, 24
HERE = Path(__file__).parent
PAUSE = 0.45          # seconds of silence after each paragraph
TITLE_SECS = 2.8
SR = 24000

PALETTES = [  # (top, bottom, accent)
    ((38, 44, 82), (120, 86, 120), (255, 196, 160)),
    ((24, 56, 70), (70, 120, 120), (190, 240, 210)),
    ((60, 40, 76), (170, 90, 110), (255, 205, 190)),
    ((30, 48, 88), (86, 112, 168), (200, 220, 255)),
    ((52, 44, 60), (140, 96, 90), (255, 214, 170)),
    ((28, 60, 56), (100, 130, 100), (225, 245, 190)),
]


def font(size, bold=True):
    custom = HERE / "assets" / "font.ttf"
    if custom.exists():
        return ImageFont.truetype(str(custom), size)
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for base in ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/"):
        if (Path(base) / name).exists():
            return ImageFont.truetype(base + name, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------- script
def parse_script(path):
    title, heading, scenes = None, None, []
    for block in re.split(r"\n\s*\n", Path(path).read_text(encoding="utf-8").strip()):
        lines = [l.rstrip() for l in block.strip().splitlines()]
        body = []
        for l in lines:
            if l.startswith("## "):
                heading = l[3:].strip()
            elif l.startswith("# "):
                title = l[2:].strip()
            elif l.strip():
                body.append(l.strip())
        if body:
            scenes.append({"text": " ".join(body), "heading": heading})
    return title, scenes


def chunk_text(text, max_chars=70):
    sents = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    for s in sents:
        words, cur = s.split(), ""
        for w in words:
            if cur and len(cur) + 1 + len(w) > max_chars:
                chunks.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            chunks.append(cur)
    # merge tiny tails
    merged = []
    for c in chunks:
        if merged and len(c) < 18 and len(merged[-1]) + len(c) < max_chars + 10:
            merged[-1] += " " + c
        else:
            merged.append(c)
    return merged


# ---------------------------------------------------------------- audio
def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def to_wav(src, dst):
    run(["ffmpeg", "-y", "-i", str(src), "-ar", str(SR), "-ac", "1", str(dst)])


def wav_len(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def silence_wav(p, secs):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.zeros(int(secs * SR), dtype=np.int16).tobytes())


async def _edge(text, voice, rate, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def make_scene_audio(i, scene, args, tmp):
    wav = tmp / f"scene{i:03d}.wav"
    if args.audio_dir:
        for ext in ("wav", "mp3", "m4a", "ogg", "flac"):
            f = Path(args.audio_dir) / f"{i + 1:02d}.{ext}"
            if f.exists():
                to_wav(f, wav); return wav
        sys.exit(f"Missing recording for paragraph {i + 1} in {args.audio_dir}")
    if args.tts == "edge":
        mp3 = tmp / f"scene{i:03d}.mp3"
        asyncio.run(_edge(scene["text"], args.voice, args.rate, mp3))
        to_wav(mp3, wav); return wav
    words = len(scene["text"].split())
    silence_wav(wav, max(1.5, words / 2.5))
    return wav


def concat_wavs(parts, out):
    data = []
    for p in parts:
        with wave.open(str(p)) as w:
            data.append(np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.concatenate(data).tobytes())


def envelope(wav_path, n_frames):
    with wave.open(str(wav_path)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    hop = SR / FPS
    env = np.zeros(n_frames, np.float32)
    for f in range(n_frames):
        seg = a[int(f * hop): int((f + 1) * hop * 1.5)]
        env[f] = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0
    ref = np.percentile(env[env > 0], 90) if (env > 0).any() else 1
    env = np.clip(env / ref, 0, 1)
    out, v = np.zeros_like(env), 0.0
    for i, e in enumerate(env):          # fast attack, slower release
        v = v + (e - v) * (0.65 if e > v else 0.28)
        out[i] = v
    return out


# ---------------------------------------------------------------- drawing
def gradient(top, bot):
    t = np.linspace(0, 1, H)[:, None, None]
    arr = np.array(top)[None, None, :] * (1 - t) + np.array(bot)[None, None, :] * t
    return Image.fromarray(np.repeat(arr, W, axis=1).astype(np.uint8), "RGB").convert("RGBA")


def soft_dot(r, color, alpha):
    d = Image.new("RGBA", (r * 4, r * 4), (0, 0, 0, 0))
    ImageDraw.Draw(d).ellipse((r, r, r * 3, r * 3), fill=color + (alpha,))
    return d.filter(ImageFilter.GaussianBlur(r * 0.55))


def make_background(idx):
    top, bot, acc = PALETTES[idx % len(PALETTES)]
    bg = gradient(top, bot)
    rng = np.random.default_rng(idx + 7)
    for _ in range(9):  # big bokeh
        r = int(rng.integers(50, 120))
        dot = soft_dot(r, acc, int(rng.integers(18, 40)))
        bg.alpha_composite(dot, (int(rng.integers(-60, W - 100)), int(rng.integers(-60, H - 140))))
    floor = Image.new("RGBA", (W, 90), (0, 0, 0, 0))
    ImageDraw.Draw(floor).rectangle((0, 20, W, 90), fill=(0, 0, 0, 55))
    bg.alpha_composite(floor.filter(ImageFilter.GaussianBlur(10)), (0, H - 90))
    return bg, acc


def wrap_px(text, fnt, max_w):
    lines, cur = [], ""
    dr = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    for w in text.split():
        t = (cur + " " + w).strip()
        if cur and dr.textlength(t, font=fnt) > max_w:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    return lines


def caption_card(text, acc):
    fnt = font(44)
    lines = wrap_px(text, fnt, 560)
    lh = 60
    h = lh * len(lines) + 56
    card = Image.new("RGBA", (640, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, 639, h - 1), 28, fill=(14, 14, 28, 150))
    d.rounded_rectangle((0, 0, 8, h - 1), 4, fill=acc + (255,))
    for i, l in enumerate(lines):
        d.text((40, 28 + i * lh + 2), l, font=fnt, fill=(0, 0, 0, 140))
        d.text((38, 28 + i * lh), l, font=fnt, fill=(255, 255, 255, 255))
    return card


def chip(text, acc):
    fnt = font(26)
    dr = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    w = int(dr.textlength(text.upper(), font=fnt)) + 48
    c = Image.new("RGBA", (w, 52), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((0, 0, w - 1, 51), 26, fill=acc + (230,))
    d.text((24, 10), text.upper(), font=fnt, fill=(24, 22, 40, 255))
    return c


def title_card(text, acc):
    fnt = font(62)
    lines = wrap_px(text, fnt, 620)
    lh = 80
    h = lh * len(lines) + 40
    c = Image.new("RGBA", (660, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((0, 12, 8, h - 12), 4, fill=acc + (255,))
    for i, l in enumerate(lines):
        d.text((43, 23 + i * lh), l, font=fnt, fill=(0, 0, 0, 150))
        d.text((40, 20 + i * lh), l, font=fnt, fill=(255, 255, 255, 255))
    return c


class Narrator:
    def __init__(self, path, height=590):
        im = Image.open(path).convert("RGBA")
        self.im = im.resize((int(im.width * height / im.height), height), Image.LANCZOS)
        self.shadow = soft_dot(70, (0, 0, 0), 90).resize((300, 80))

    def frame(self, t, amp):
        w, h = self.im.size
        sx = 1 - 0.035 * amp
        sy = 1 + 0.075 * amp
        s = self.im.resize((int(w * sx), int(h * sy)), Image.BICUBIC)
        s = s.rotate(1.4 * math.sin(t * 1.9), resample=Image.BICUBIC,
                     center=(s.width // 2, s.height), expand=False)
        bob = 5 * math.sin(t * 2.4) + amp * 14
        return s, bob


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--tts", default="edge", choices=["edge", "none"])
    ap.add_argument("--voice", default="en-US-AriaNeural")
    ap.add_argument("--rate", default="-4%")
    ap.add_argument("--audio-dir")
    ap.add_argument("--out")
    ap.add_argument("--sprite", default=str(HERE / "assets" / "narrator.png"))
    ap.add_argument("--max-scenes", type=int)
    args = ap.parse_args()

    name = Path(args.script).stem
    out = Path(args.out or HERE / "output" / f"{name}.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = HERE / ".work" / name
    tmp.mkdir(parents=True, exist_ok=True)

    title, scenes = parse_script(args.script)
    if args.max_scenes:
        scenes = scenes[: args.max_scenes]
    print(f"{len(scenes)} scenes" + (f", title: {title}" if title else ""))

    # audio per scene
    parts, timeline, t0 = [], [], 0.0
    if title:
        sp = tmp / "title.wav"; silence_wav(sp, TITLE_SECS)
        parts.append(sp); timeline.append({"kind": "title", "start": 0.0, "dur": TITLE_SECS})
        t0 = TITLE_SECS
    for i, sc in enumerate(scenes):
        print(f"  voicing scene {i + 1}/{len(scenes)}", flush=True)
        wav = make_scene_audio(i, sc, args, tmp)
        d = wav_len(wav)
        pause = tmp / f"pause{i:03d}.wav"; silence_wav(pause, PAUSE)
        parts += [wav, pause]
        timeline.append({"kind": "scene", "i": i, "start": t0, "dur": d + PAUSE, "speech": d})
        t0 += d + PAUSE
    full = tmp / "full.wav"
    concat_wavs(parts, full)
    total = t0
    n_frames = int(total * FPS)
    env = envelope(full, n_frames)

    # per-scene assets
    for tl in timeline:
        if tl["kind"] == "title":
            bg, acc = make_background(0)
            tl.update(bg=bg, acc=acc, card=title_card(title, acc))
            continue
        sc = scenes[tl["i"]]
        bg, acc = make_background(tl["i"] + 1)
        chunks = chunk_text(sc["text"])
        weights = np.array([len(c) for c in chunks], float)
        bounds = np.concatenate([[0], np.cumsum(weights / weights.sum())]) * tl["speech"]
        tl.update(bg=bg, acc=acc, bounds=bounds,
                  cards=[caption_card(c, acc) for c in chunks],
                  chip=chip(sc["heading"], acc) if sc["heading"] else None)

    # SRT
    srt = out.with_suffix(".srt")
    def ts(x):
        return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(x % 1 * 1000):03d}"
    with open(srt, "w", encoding="utf-8") as f:
        n = 1
        for tl in timeline:
            if tl["kind"] != "scene": continue
            for k, c in enumerate(chunk_text(scenes[tl["i"]]["text"])):
                f.write(f"{n}\n{ts(tl['start'] + tl['bounds'][k])} --> {ts(tl['start'] + tl['bounds'][k + 1])}\n{c}\n\n")
                n += 1

    nar = Narrator(args.sprite)
    rng = np.random.default_rng(3)
    parts_xy = rng.uniform(0, 1, (16, 3))
    dots = [soft_dot(int(6 + p[2] * 8), (255, 255, 255), 90) for p in parts_xy]

    silent = tmp / "video_silent.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(silent)],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    cur = 0
    base_x, foot_y = 300, H - 22
    for fr in range(n_frames):
        t = fr / FPS
        while cur + 1 < len(timeline) and t >= timeline[cur + 1]["start"]:
            cur += 1
        tl = timeline[cur]
        lt = t - tl["start"]
        frame = tl["bg"].copy()
        # drifting sparkles
        for p, dot in zip(parts_xy, dots):
            x = (p[0] * W + t * (6 + 10 * p[2])) % (W + 80) - 40
            y = (p[1] * H - t * (8 + 14 * p[2])) % (H + 80) - 40
            frame.alpha_composite(dot, (int(x), int(y)))
        amp = float(env[fr]) if tl["kind"] == "scene" else 0.0
        spr, bob = nar.frame(t, amp)
        sh = nar.shadow
        frame.alpha_composite(sh, (base_x - sh.width // 2, foot_y - sh.height // 2 - 6))
        px = base_x - spr.width // 2
        py = int(foot_y - spr.height - bob)
        if tl["kind"] == "title":
            frame.alpha_composite(tl["card"], (590, (H - tl["card"].height) // 2 - 10))
            a = min(1, lt / 0.4)
        else:
            a = 1
        frame.alpha_composite(spr, (max(px, -spr.width), py))
        if tl["kind"] == "scene":
            k = int(np.searchsorted(tl["bounds"], lt, side="right") - 1)
            k = min(max(k, 0), len(tl["cards"]) - 1)
            card = tl["cards"][k]
            fade = min(1, (lt - tl["bounds"][k]) / 0.18 + 0.15) if lt <= tl["speech"] else 1
            if fade < 1:
                card = card.copy(); card.putalpha(card.getchannel("A").point(lambda v: int(v * fade)))
            if lt <= tl["speech"] + 0.15:
                frame.alpha_composite(card, (590, (H - card.height) // 2 - 10))
            if tl["chip"] is not None:
                frame.alpha_composite(tl["chip"], (590, 48))
        if tl["kind"] == "title" and a < 1:
            frame = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), frame, a)
        ff.stdin.write(frame.convert("RGB").tobytes())
        if fr % (FPS * 30) == 0:
            print(f"  frame {fr}/{n_frames}", flush=True)
    ff.stdin.close(); ff.wait()

    run(["ffmpeg", "-y", "-i", str(silent), "-i", str(full), "-c:v", "copy", "-c:a", "aac",
         "-b:a", "160k", "-shortest", str(out)])
    print(f"done: {out}  ({total:.1f}s)  subtitles: {srt}")


if __name__ == "__main__":
    main()
