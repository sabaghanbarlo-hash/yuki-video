"""Natural, emotional narration with Google's Gemini text-to-speech (free tier, needs GEMINI_API_KEY).

Why: the old Kokoro voice reads every sentence in the same even tone, so the feelings never arrive.  Gemini's speech model can be DIRECTED like an
actor ("say this in a soft, slightly anxious voice, like quietly admitting a worry"), so each sentence gets its own acting note built from what
the sentence is doing in the story (hook, problem, advice, conclusion ...) and the feeling it carries (worry, relief, pride ...), the same reading
that picks Yuki's face (lab/understand.py, negation aware: "you don't have to solve every thought" is relief, not worry).

    synth(text, voice, ctx)  -> float32 mono audio at 24 kHz, or None when Gemini cannot answer (no key, quota used up, network)
                                 voice.synth() then falls back to the Kokoro voice for that sentence, so a video never fails.

Free-tier quotas for speech are small.  The code waits when the service says "retry in N seconds", stops asking once the DAILY quota is gone
(the remaining sentences use the fallback voice) and the pipeline does not cache fallback audio, so re-running the video later upgrades them.

Environment: GEMINI_API_KEY (required) - YUKI_GEMINI_VOICE (default Leda) - YUKI_GEMINI_TTS_MODEL (default: the best TTS model the key can see)
"""
import base64, json, os, re, time, urllib.error, urllib.request
import numpy as np

SR = 24000
API = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_VOICE = "Leda"
# a few of Gemini's prebuilt voices (name: character), handy for the voice test page
VOICES = {"Leda": "youthful", "Aoede": "breezy", "Sulafat": "warm", "Zephyr": "bright", "Achernar": "soft", "Vindemiatrix": "gentle", "Callirrhoe": "easy-going",
          "Kore": "firm", "Puck": "upbeat", "Charon": "informative", "Fenrir": "excitable", "Orus": "firm"}
FALLBACK_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-flash-tts", "gemini-2.5-pro-preview-tts"]

STATE = dict(models=None, dead=False, why="", calls=0, fails=0, spent=set())

BASE = "like a real young woman chatting to a friend: natural and human, never like a presenter or an announcer, with varied pitch, a natural rhythm and small pauses"

EMO_DIR = {
    "worried": "in a soft, slightly tense and anxious voice, a little quicker, like quietly admitting a worry",
    "scared": "in a hushed, shaky, frightened voice, as if holding her breath",
    "sad": "in a low, slow, heavy and sorrowful voice with a trembling softness",
    "angry": "in a tight, firm, frustrated voice with sharp emphasis on the key words",
    "happy": "in a bright, smiling, cheerful voice",
    "proud": "in a warm, glowing, proud voice, slow and satisfied",
    "excited": "in a lively, thrilled, fast and energetic voice with big pitch swings",
    "curious": "in an intrigued, wide-eyed voice with rising intonation",
    "confused": "in a puzzled, hesitant voice with small upward inflections",
    "shocked": "in a stunned, breathless voice, as if just realising something surprising",
    "tired": "in a weary, sleepy, drawn-out voice with a soft sigh",
    "bored": "in a flat, deadpan, drawling voice",
    "embarrassed": "in a shy, flustered voice with nervous little hesitations",
    "calm": "in a gentle, soothing, unhurried voice, reassuring, with a soft exhale",
    "determined": "in a steady, resolute, confident voice with firm emphasis",
    "hopeful": "in a warm, hopeful, lifting voice, with a smile growing in the tone",
    "smug": "in a playful, teasing, knowing voice with a smirk",
}
ROLE_DIR = {
    "intro": "in a friendly, welcoming, upbeat voice, as if greeting a friend she is happy to see",
    "hook": "in a curious, intriguing voice that draws the listener in, rising on the question",
    "definition": "in a clear, confident, explaining voice, like a smart friend sharing an insight",
    "problem": "in a slightly serious, concerned voice, slowing down on the key point",
    "contrast": "with a knowing shift in tone, leaning on the word that turns the sentence",
    "advice": "in a kind, encouraging and sincere voice",
    "example": "in a lively storytelling voice",
    "conclusion": "in a warm, sincere, slower voice with a gentle smile, like a closing thought",
    "statement": "in a natural, conversational voice",
}
ROLE_SHORT = {"hook": "drawing the listener in", "definition": "as if explaining an insight", "problem": "making the key point land", "advice": "kindly and sincerely",
              "conclusion": "like a closing thought", "contrast": "with a turn in the tone", "intro": "welcoming", "example": "storytelling", "statement": ""}


def direction(text, role="statement", emotion=None, strength=0.0):
    """The acting note for one sentence."""
    t = text.strip()
    if emotion in EMO_DIR and strength >= 0.8:
        d = EMO_DIR[emotion]
        extra = ROLE_SHORT.get(role, "")
        if extra:
            d += ", " + extra
    else:
        d = ROLE_DIR.get(role, ROLE_DIR["statement"])
    if t.endswith("?") and role != "hook":
        d += ", with a questioning lift at the end"
    elif t.endswith("!"):
        d += ", with real energy on the exclamation"
    elif t.endswith("..."):
        d += ", trailing off thoughtfully"
    return d


def feeling(text, first=False, last=False):
    """-> (role, emotion, strength) using the same reading as Yuki's face (and the optional LLM art director)."""
    try:
        from . import understand as U
        role = U.role_of(text, first, last)
        emo, strength, _neg = U.feeling_of(text)
        br = (U.STATE.get("brain") or {}).get(U.norm(text)) or {}
        if br.get("role") in U.ROLES:
            role = br["role"]
        if br.get("emotion") in U.EMOTIONS:
            emo, strength = br["emotion"], max(strength, 1.2)
        return role, emo, strength
    except Exception:
        return "statement", None, 0.0


# ------------------------------------------------------------------ network
def _key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def _call(method, path, body=None, timeout=90):
    req = urllib.request.Request(f"{API}/{path}", data=None if body is None else json.dumps(body).encode(), method=method,
                                 headers={"x-goog-api-key": _key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _rank(name):
    """Best first: newest version, full-size flash before lite, flash before pro, stable before preview."""
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    ver = float(m.group(1)) if m else 0.0
    return (("lite" in name), ("pro" in name), -ver, ("preview" in name), name)


def models():
    """TTS-capable models this key can use, in the order they are tried (each model has its own free daily quota, so spare ones are used when one runs out).
    YUKI_GEMINI_TTS_MODEL pins one model as the first choice."""
    if STATE["models"] is not None:
        return STATE["models"]
    found = []
    try:
        d = _call("GET", "models?pageSize=200", timeout=30)
        found = [m["name"].split("/")[-1] for m in d.get("models", []) if "tts" in m.get("name", "") and "generateContent" in m.get("supportedGenerationMethods", ["generateContent"])]
        found.sort(key=_rank)
    except Exception as e:
        print(f"  [gemini] could not list models ({type(e).__name__}); trying the usual names", flush=True)
    if not found:
        found = list(FALLBACK_MODELS)
    forced = os.environ.get("YUKI_GEMINI_TTS_MODEL")
    out = ([forced] if forced else []) + [m for m in found if m != forced]
    STATE["models"] = out
    return out


def _retry_delay(err_body):
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', err_body) or re.search(r"retry in (\d+(?:\.\d+)?)s", err_body, re.I)
    return float(m.group(1)) if m else None


def _pcm(resp):
    for c in resp.get("candidates", []):
        for p in (c.get("content") or {}).get("parts", []):
            inl = p.get("inlineData") or p.get("inline_data")
            if inl and inl.get("data"):
                rate = SR
                m = re.search(r"rate=(\d+)", inl.get("mimeType") or inl.get("mime_type") or "")
                if m:
                    rate = int(m.group(1))
                a = np.frombuffer(base64.b64decode(inl["data"]), dtype="<i2").astype(np.float32) / 32768
                if rate != SR and len(a):
                    a = np.interp(np.arange(0, len(a), rate / SR), np.arange(len(a)), a).astype(np.float32)
                return a
    return None


FLOW = ("Perform the whole TRANSCRIPT below out loud as ONE continuous piece of speech, the way a real person tells something to a friend: "
        "the sentences lead into each other and each one picks up the energy and the thought of the one before, the pitch rises and falls with the meaning, "
        "the voice lands on the important words and goes lighter on the rest, and between sentences there is only a natural breath, never an announcer's stop. "
        "The notes are only for how to perform it: never read them aloud.")


def take_prompt(texts, ctxs):
    """Director's notes for SEVERAL sentences spoken in one go (a flowing take)."""
    lines = []
    for i, (t, c) in enumerate(zip(texts, ctxs), 1):
        c = c or {}
        lines.append(f"{i}. {direction(t, c.get('role', 'statement'), c.get('emotion'), c.get('strength', 0.0))}")
    return (f"{FLOW}\n\n### DIRECTOR'S NOTES\nOverall: {BASE}.\nHow each sentence feels, in order (blend them smoothly, do not switch abruptly):\n"
            + "\n".join(lines) + "\n\n### TRANSCRIPT\n" + " ".join(texts))


def synth_take(texts, voice=None, ctxs=None, max_wait=75):
    """One recording of several consecutive sentences, so the voice carries the thought across them. -> float32 array or None."""
    ctxs = ctxs or [None] * len(texts)
    return synth(" ".join(texts), voice, None, max_wait, prompt=take_prompt(texts, ctxs))


def synth(text, voice=None, ctx=None, max_wait=75, prompt=None):
    """-> float32 array at 24 kHz, or None (caller uses the fallback voice)."""
    if STATE["dead"] or not _key():
        return None
    ctx = ctx or {}
    voice = voice or os.environ.get("YUKI_GEMINI_VOICE") or DEFAULT_VOICE
    if prompt is None:
        d = direction(text, ctx.get("role", "statement"), ctx.get("emotion"), ctx.get("strength", 0.0))
        prompt = ("Perform the TRANSCRIPT below out loud. The notes are only for how to perform it: never read them aloud.\n\n"
                  f"### DIRECTOR'S NOTES\nStyle: {d}.\nDelivery: {BASE}.\n\n### TRANSCRIPT\n{text}")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    STATE["calls"] += 1
    for model in models():
        if model in STATE["spent"]:
            continue
        for attempt in range(4):
            try:
                a = _pcm(_call("POST", f"models/{model}:generateContent", body))
                if a is not None and len(a) > SR * 0.2:
                    return a
                time.sleep(1.5)                                      # the speech model sometimes answers with text only: ask again
                continue
            except urllib.error.HTTPError as e:
                err = e.read().decode("utf-8", "replace")[:900]
                if e.code == 429:
                    if re.search(r"per ?day|daily|PerDay", err, re.I) and not re.search(r"PerMinute", err, re.I):
                        STATE["spent"].add(model)                    # every speech model has its own daily quota: try the next model
                        print(f"  [gemini] daily free quota of {model} is used up", flush=True)
                        if all(m in STATE["spent"] for m in models()):
                            STATE.update(dead=True, why="daily quota used up (all speech models)")
                            print("  [gemini] every speech model's daily free quota is used up", flush=True)
                            return None
                        break
                    wait = (_retry_delay(err) or 20) + 1.5
                    if wait > max_wait:
                        break
                    time.sleep(wait)
                    continue
                if e.code in (400, 403, 404):
                    if e.code == 403 or "API key" in err or "API_KEY" in err:
                        STATE.update(dead=True, why="key rejected")
                        print(f"  [gemini] the API key was refused ({e.code}); using the fallback voice. {err[:160]}", flush=True)
                        return None
                    print(f"  [gemini] model {model} unavailable ({e.code}); trying the next one", flush=True)
                    break
                time.sleep(2 + attempt * 3)
            except Exception as e:
                time.sleep(2 + attempt * 3)
    STATE["fails"] += 1
    if STATE["fails"] >= 3:
        STATE.update(dead=True, why="repeated failures")
        print("  [gemini] it keeps failing; the remaining sentences use the fallback voice", flush=True)
    return None
