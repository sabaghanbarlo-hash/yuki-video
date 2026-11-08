"""script text -> plan -> narration -> timeline -> sound -> frames -> MP4 (+ subtitles).

    build_plan(text, args)           parse + direct, adds the title / outro cards
    voice(plan, args, tmp)           records every sentence (Kokoro / Edge / cloned voice / your own recording)
    timeline(plan, durations)        puts every scene, shot and sentence on the clock
    mix(plan, sentence_audio)        narration + sound effects + ambience + music (ducked under the voice)
    render_video(...)                parallel frame rendering with ffmpeg
"""
import hashlib, json, math, os, random, re, subprocess, sys, time
from pathlib import Path
import numpy as np

from . import knowledge as K
from . import voice as A
from . import sfx as S
from .script import parse, WPS
from .director import direct, entities_in, make_cam_2d, summary

SR = A.SR
FPS = 24
TITLE_SECS, OUTRO_SECS, LEAD, HOLD = 3.6, 3.2, 0.45, 0.4


# ------------------------------------------------------------------ plan
def _card_scene(kind, idx, title, topic, seed):
    rng = random.Random(seed + idx)
    ents = entities_in(title) if kind == "title" else []
    env = rng.choice(K.ENVS.get(topic or "generic", K.ENVS["generic"])["flat"])
    pal = rng.choice(K.PALETTES.get(topic or "generic", K.PALETTES["generic"]))
    actors = []
    if ents:
        actors.append(dict(k="entity", name=ents[0][0], x=0.5, y=0.72 if kind == "title" else 0.5, size=260, f_in=0.2, motion="float", entry="pop", seed=3))
    else:
        for i in range(6):
            actors.append(dict(k="spark", x=rng.uniform(0.1, 0.9), y=rng.uniform(0.1, 0.9), size=rng.uniform(14, 36), f_in=rng.uniform(0, 0.6), seed=rng.randrange(99)))
    shot = dict(sent=None, text=title, template=kind, cam=dict(k="push", amp=1.0, flip=False), actors=actors, feat={})
    return dict(idx=idx, heading="", kind=kind, style="flat", env=env, pal=pal, tod=None, seed=rng.randrange(1, 999), topic=topic, mood="wonder", cues={},
                sentences=[], shots=[shot], transition="fade", sfx=[], text=title, card_title=title)


def build_plan(text, seed=0, force_style=None, max_scenes=None):
    title, raw = parse(text)
    if max_scenes:
        raw = raw[:max_scenes]
    if not raw:
        raise SystemExit("The script has no text to narrate.")
    if force_style == "collage" or any("collage" in str(r.cues.get("style", "")).lower() for r in raw):
        from . import understand
        understand.begin(title, raw, force_style)                  # the optional LLM art director reads the whole script (no key = rules only)
    plan = direct(title, raw, seed, force_style)
    sc = plan["scenes"]
    topic = sc[0]["topic"]
    if not all(x["style"] == "collage" for x in sc):             # collage videos start straight on the hook and end on the last beat
        if title:
            sc.insert(0, _card_scene("title", 0, title, topic, plan.get("seed", 0) + 11))
        sc.append(_card_scene("outro", 0, "Thanks for watching", sc[-1]["topic"], 77))
    for i, s in enumerate(sc):
        s["idx"] = i
    plan["has_title"] = bool(title)
    return plan


def body_sentences(plan):
    """[(scene, sentence_index_in_scene, sentence)] in narration order."""
    return [(sc, i, s) for sc in plan["scenes"] if sc["kind"] == "body" for i, s in enumerate(sc["sentences"])]


# ------------------------------------------------------------------ narration
def voice(plan, args, tmp):
    """-> list of float32 arrays (one per sentence, in narration order)."""
    sents = body_sentences(plan)
    tmp = Path(tmp); (tmp / "voice").mkdir(parents=True, exist_ok=True)
    if getattr(args, "audio", None):
        return align_upload(args.audio, [s["spoken"] for _, _, s in sents], tmp)
    out = []
    for n, (sc, i, s) in enumerate(sents):
        key = hashlib.md5(f"v3|{args.tts}|{getattr(args, 'voice', '')}|{getattr(args, 'energy', 1)}|{getattr(args, 'speed', 1)}|{s['mood']}|{s['spoken']}".encode()).hexdigest()[:16]
        f = tmp / "voice" / f"{key}.npy"
        if f.exists() and not getattr(args, "audio_dir", None):
            out.append(np.load(f)); continue
        print(f"  voicing {n + 1}/{len(sents)}", flush=True)
        ctx = None
        if args.tts == "gemini":                                          # the acting note: what the sentence does + the feeling it carries
            from . import gemini_tts as G
            role, emo, strength = G.feeling(s["spoken"], first=(n == 0), last=(n == len(sents) - 1))
            ctx = dict(role=role, emotion=emo, strength=strength)
        a = A.synth(s["spoken"], args, n, tmp, emotion=s["mood"], ctx=ctx)
        a = np.asarray(a, np.float32)
        if not (args.tts == "gemini" and A.FALLBACK.get("used")):          # fallback audio is never cached: a later run tries Gemini again
            np.save(f, a)
        out.append(a)
    return out


def align_upload(path, spoken, tmp):
    """Cut one long narration recording into sentences: find the pauses, then pick the pauses that best match
    where each sentence should end given its length."""
    wav = Path(tmp) / "upload.wav"
    A.to_wav(path, wav)
    x = A.read_wav(wav)
    x = x / (np.abs(x).max() + 1e-6)
    hop = int(0.02 * SR)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1))
    thr = max(0.012, np.percentile(rms[rms > 0.004], 25) * 0.5) if (rms > 0.004).any() else 0.01
    quiet = rms < thr
    gaps = []                                   # (start_frame, end_frame) of pauses >= 0.16 s
    i = 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if (j - i) * 0.02 >= 0.16:
                gaps.append((i, j))
            i = j
        else:
            i += 1
    voiced = np.nonzero(~quiet)[0]
    if not len(voiced):
        raise SystemExit("The uploaded audio is silent.")
    v0, v1 = voiced[0], voiced[-1] + 1
    w = np.array([len(s) + 8 for s in spoken], float)
    cum = np.cumsum(w) / w.sum()
    inner = [g for g in gaps if g[0] > v0 and g[1] < v1]
    centers = np.array([(g[0] + g[1]) / 2 for g in inner]) if inner else np.array([])
    bounds, last = [], v0
    for k in range(len(spoken) - 1):
        target = v0 + cum[k] * (v1 - v0)
        ok = centers[centers > last + 5] if len(centers) else centers
        b = ok[np.argmin(np.abs(ok - target))] if len(ok) else target
        bounds.append(int(b)); last = b
    edges = [v0] + bounds + [v1]
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        seg = x[int(a * hop): int(b * hop)]
        out.append(A.trim(seg.astype(np.float32), keep=0.12))
    return out


# ------------------------------------------------------------------ timeline
def gap_after(s):
    g = s["pause"] if s.get("pause") is not None else (0.55 if s.get("para_end") else 0.3)
    if s["text"].rstrip().endswith("?"):
        g += 0.25
    return g


def timeline(plan, durations):
    """durations: seconds of narration per sentence (narration order). Fills t0/t1 everywhere; returns total seconds."""
    t = 0.0
    k = 0
    for sc in plan["scenes"]:
        sc["t0"] = t
        if sc["kind"] == "title":
            t += TITLE_SECS
        elif sc["kind"] == "outro":
            t += OUTRO_SECS
        else:
            t += LEAD
            for s in sc["sentences"]:
                s["t0"] = t
                s["t1"] = t + float(durations[k])
                t = s["t1"] + gap_after(s)
                k += 1
            t += HOLD - 0.25
        sc["t1"] = t
        for si, sh in enumerate(sc["shots"]):
            if sh["sent"] is None:
                sh["t0"], sh["t1"] = sc["t0"], sc["t1"]
                continue
            i0, i1 = sh["sent"]
            if sh.get("span"):                                   # collage beat: a slice of one sentence
                sn = sc["sentences"][i0]
                a = sh["span"][0]
                sh["t0"] = sc["t0"] if si == 0 else sn["t0"] + a * (sn["t1"] - sn["t0"]) - (0.12 if a == 0 else 0.0)
            else:
                sh["t0"] = sc["t0"] if si == 0 else sc["sentences"][i0]["t0"] - 0.12
        for si, sh in enumerate(sc["shots"]):
            if sh["sent"] is None:
                continue
            sh["t1"] = sc["shots"][si + 1]["t0"] if si + 1 < len(sc["shots"]) else sc["t1"]
    return t


def estimate_durations(plan):
    return [len(s["spoken"].split()) / WPS + 0.25 for _, _, s in body_sentences(plan)]


# ------------------------------------------------------------------ captions
def caption_plan(plan):
    from .overlays import chunk_words
    for sc in plan["scenes"]:
        for s in sc["sentences"]:
            words = s["text"].split()
            wt = np.array([len(w) + 2.0 for w in words]); wt = wt / wt.sum()
            edges = s["t0"] + np.concatenate([[0], np.cumsum(wt)]) * (s["t1"] - s["t0"])
            chunks = []
            for ch in chunk_words(words):
                idxs = [i for i, _ in ch]
                chunks.append(dict(words=[w for _, w in ch], t0=float(edges[idxs[0]]), t1=float(edges[idxs[-1] + 1]), wt=[float(edges[i]) for i in idxs]))
            s["caps"] = chunks


def write_srt(plan, path):
    def ts(x):
        return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(x % 1 * 1000):03d}"
    n = 1
    with open(path, "w", encoding="utf-8") as f:
        for sc in plan["scenes"]:
            for s in sc["sentences"]:
                for c in s.get("caps", []):
                    f.write(f"{n}\n{ts(c['t0'])} --> {ts(c['t1'])}\n{' '.join(c['words'])}\n\n")
                    n += 1


# ------------------------------------------------------------------ sound
def _put(out, x, at, gain=1.0):
    i = int(at * SR)
    if i >= len(out) or i < 0:
        return
    seg = x[: len(out) - i] * gain
    out[i:i + len(seg)] += seg


def mix(plan, sent_audio, total):
    n = int(total * SR) + SR
    voice_t = np.zeros(n, np.float32)
    k = 0
    for sc in plan["scenes"]:
        for s in sc["sentences"]:
            _put(voice_t, sent_audio[k], s["t0"]); k += 1
    peak = np.abs(voice_t).max()
    if peak > 0:
        voice_t = voice_t / peak * 0.86
    fx = np.zeros(n, np.float32)
    amb = np.zeros(n, np.float32)
    last_t = -9
    for si, sc in enumerate(plan["scenes"]):
        if sc["kind"] == "body":
            a = S.ambience(sc["env"], (sc["t1"] - sc["t0"]) + 1.6)
            _put(amb, a, max(0, sc["t0"] - 0.8), 0.5)
        if si > 0:
            nm = {"flash": "impact", "zoom": "whoosh_low", "iris": "pop", "fade": None}.get(sc["transition"], "whoosh")
            g = S.get(nm) if nm else None
            if g is not None:
                _put(fx, g, max(0, sc["t0"] - 0.15), 0.22)
        for ev in sc.get("sfx", []):
            s = sc["sentences"][ev["sent"]]
            at = s["t0"] + ev["frac"] * (s["t1"] - s["t0"])
            nm = ev["name"]
            g = S.get(nm)
            if g is None or at - last_t < 0.6:
                continue
            _put(fx, g, at, 0.30 * ev.get("gain", 1.0))
            last_t = at
        for sh in sc["shots"]:
            if sc["kind"] == "body" and sc["style"] == "collage" and sh.get("cut_sfx") and sh["t0"] > sc["t0"] + 0.2:
                g = S.get(sh["cut_sfx"])
                if g is not None:
                    _put(fx, g, max(0, sh["t0"] - 0.02), 0.14)
            tpl = sh.get("template")
            if sc["kind"] == "body" and tpl in ("stat", "timeline", "question", "pair", "process"):
                g = S.get("pop" if tpl != "stat" else "ding")
                if g is not None:
                    _put(fx, g, sh["t0"] + 0.12, 0.16)
            for ev in sh.get("events", []):
                nm = {"meteor": "impact", "rocket": "rocket", "eruption": "rumble", "lightning": "thunder"}.get(ev["name"])
                g = S.get(nm) if nm else None
                if g is not None:
                    off = 1.7 if ev["name"] == "meteor" else 0.0
                    _put(fx, g, sh["t0"] + ev["f"] * (sh["t1"] - sh["t0"]) + off, 0.4)
    # music bed ducked under the voice
    mus = S.music(total + 1, "calm")
    mus = np.resize(mus, n).astype(np.float32)
    mus = mus / (np.abs(mus).max() + 1e-6)
    env = np.abs(voice_t)
    w = int(0.3 * SR)
    env = np.convolve(env, np.ones(w, np.float32) / w, mode="same")
    env = np.clip(env / 0.08, 0, 1)
    duck = 1.0 - 0.7 * env
    fade = np.ones(n, np.float32)
    f_in, f_out = int(1.5 * SR), int(2.0 * SR)
    fade[:f_in] = np.linspace(0, 1, f_in); fade[int(total * SR) - f_out:int(total * SR)] = np.linspace(1, 0, f_out); fade[int(total * SR):] = 0
    out = voice_t + fx + amb * 0.55 + mus * 0.15 * duck * fade
    pk = np.abs(out).max()
    if pk > 0.95:
        out = np.tanh(out / pk * 1.1) / np.tanh(1.1) * 0.95
    return out[: int(total * SR)], voice_t[: int(total * SR)]


# ------------------------------------------------------------------ render
_G = {}


def _init_worker(plan, mouth, amp, size):
    from .compose import Compositor
    _G["comp"] = Compositor(plan, mouth, amp)


def _render_chunk(job):
    idx, f0, f1, path = job
    comp = _G["comp"]
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1280x720", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-g", "48", str(path)], stdin=subprocess.PIPE)
    for fr in range(f0, f1):
        ff.stdin.write(comp.frame_bytes(fr))
    ff.stdin.close(); ff.wait()
    return idx, f1 - f0


def render_video(plan, mouth, amp, total, audio, out_path, tmp, workers=None, progress=True):
    import multiprocessing as mp
    tmp = Path(tmp); out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(math.ceil(total * FPS))
    chunk = FPS * 8
    jobs = []
    for i, f0 in enumerate(range(0, n_frames, chunk)):
        jobs.append((i, f0, min(n_frames, f0 + chunk), tmp / f"chunk_{i:04d}.mp4"))
    workers = workers or max(1, min(os.cpu_count() or 2, 4))
    t0 = time.time()
    done = 0
    ctx = mp.get_context("fork")
    if workers == 1:
        _init_worker(plan, mouth, amp, None)
        for j in jobs:
            _render_chunk(j); done += j[2] - j[1]
            print(f"  frames {done}/{n_frames}  ({time.time() - t0:.0f}s)", flush=True)
    else:
        _G["plan"] = plan
        with ctx.Pool(workers, initializer=_init_worker, initargs=(plan, mouth, amp, None)) as pool:
            for idx, n in pool.imap_unordered(_render_chunk, jobs):
                done += n
                print(f"  frames {done}/{n_frames}  ({time.time() - t0:.0f}s)", flush=True)
    lst = tmp / "chunks.txt"
    lst.write_text("".join(f"file '{j[3].name}'\n" for j in jobs))
    silent = tmp / "silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)], check=True)
    wavp = tmp / "mix.wav"
    A.write_wav(wavp, audio)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(wavp), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", str(out_path)], check=True)
    for j in jobs:
        j[3].unlink(missing_ok=True)


def mouth_levels(voice_track, n_frames):
    lvl, amp = A.mouth_track(voice_track, n_frames, FPS)
    return lvl, amp


def prepare_media(plan, args, tmp, out_path):
    """Collage videos: fetch (or find) the picture of every beat; write <video>.credits.txt for stock photos."""
    if not any(sc["style"] == "collage" for sc in plan["scenes"]):
        return
    from . import media as M
    root = Path(__file__).resolve().parent.parent
    M.prefetch(plan, getattr(args, "media", "auto") or "auto", cache_dir=root / ".work" / "media", local_dir=root / "media")
    if plan.get("credits"):
        Path(out_path).with_suffix(".credits.txt").write_text("Pictures used in this video:\n" + "\n".join("- " + c for c in plan["credits"]) + "\n", encoding="utf-8")


def make(text, args, out_path, tmp):
    """Everything: returns (total_seconds, plan)."""
    tmp = Path(tmp); tmp.mkdir(parents=True, exist_ok=True)
    plan = build_plan(text, seed=getattr(args, "seed", 0), force_style=getattr(args, "style", None), max_scenes=getattr(args, "max_scenes", None))
    print(f"plan: {sum(1 for s in plan['scenes'] if s['kind'] == 'body')} scenes - " + ", ".join(f"{x['style']}/{x['env']}" for x in plan["scenes"] if x["kind"] == "body"), flush=True)
    if getattr(args, "export_beats", False):
        return 0, plan
    prepare_media(plan, args, tmp, out_path)
    sent_audio = voice(plan, args, tmp)
    durs = [len(a) / SR for a in sent_audio]
    total = timeline(plan, durs)
    caption_plan(plan)
    audio, voice_t = mix(plan, sent_audio, total)
    n_frames = int(math.ceil(total * FPS))
    lvl, amp = mouth_levels(voice_t, n_frames)
    lvl, _ = A.viseme_track(voice_t, n_frames, FPS)
    json.dump(_plan_json(plan), open(Path(out_path).with_suffix(".plan.json"), "w"), indent=1)
    render_video(plan, lvl, amp, total, audio, out_path, tmp, workers=getattr(args, "workers", None))
    return total, plan


def _plan_json(plan):
    out = dict(title=plan["title"], scenes=[])
    for sc in plan["scenes"]:
        out["scenes"].append(dict(idx=sc["idx"], kind=sc["kind"], heading=sc["heading"], style=sc["style"], env=sc["env"], mood=sc["mood"], topic=sc["topic"],
                                  transition=sc["transition"], t0=round(sc["t0"], 2), t1=round(sc["t1"], 2), text=sc.get("text", "")[:400],
                                  shots=[dict(template=s["template"], t0=round(s["t0"], 2), t1=round(s["t1"], 2), things=[a.get("name") or a.get("k") for a in s["actors"] if a["k"] in ("entity", "prop", "char", "human", "creature", "critter")],
                                            **({k: s.get(k) for k in ("kind", "layout", "treat", "pose", "face", "queries", "title", "text")} if sc["style"] == "collage" else {})) for s in sc["shots"]]))
    return out
