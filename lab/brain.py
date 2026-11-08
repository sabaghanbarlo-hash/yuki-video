"""Optional LLM "art director": a language model reads the WHOLE script once and decides, for every beat, what the sentence is doing, how
Yuki should feel and move, and which drawings would explain it.  This is what makes the picture choice truly context-aware (an LLM can tell
that "you don't have to solve every thought" is relief, and that a thought bubble looping round explains rumination).

It is optional and free: set ONE of these (repository secrets in the workflow; locally as environment variables) and it switches on:
    GROQ_API_KEY      Groq's free tier (default model llama-3.3-70b-versatile; override with YUKI_BRAIN_MODEL)
    GEMINI_API_KEY    Google AI Studio free tier (default gemini-2.5-flash; override with YUKI_BRAIN_MODEL)
    YUKI_LLM_URL + YUKI_LLM_KEY (+ YUKI_LLM_MODEL)   any OpenAI-compatible endpoint (OpenRouter, Together, ...)
Without a key, or if the service is unreachable or answers nonsense, nothing changes: lab/understand.py's rules decide (they already cover
roles, feelings with negation, and ~30 abstract concepts).  Everything the model returns is checked against what the lab can actually draw
(faces, poses, drawings, places), so a bad answer can never break a video.  Only the script text is sent; answers are cached in .work/brain/.
"""
import hashlib, json, os, re, time, urllib.error, urllib.request
from pathlib import Path

from . import metaphors, props, understand as U  # noqa: F401  (metaphors/props register the drawings the model may choose)

CACHE = Path(".work/brain")
ACTIONS = {"sit", "run", "walk", "jump", "think", "point", "talk", "cheer", "panic", "shrug", "look_up", "push", "fall", "wave", "float", "idle"}
PLACES = {"bedroom", "office", "kitchen", "gym", "classroom", "park", "street", "room", "rooftop", "lab", "forest", "hills", "beach", "desert", "snow", "underwater", "space", "cave", "stage"}
GLOSS = dict(
    tangle="tangled scribble (overthinking, chaos, confusion, complexity)", thought_loop="thought cloud with a looping arrow (rumination, replaying, repeating a worry or habit)",
    rewind_clock="clock running backwards (the past, memories, regret)", crystal_ball="crystal ball (the future, prediction, what-if)", maze="maze (stuck, lost, hard problem)",
    qmarks="floating question marks (doubt, unknown, uncertainty, a question)", signpost="two-way signpost (a choice or decision)", balloons="balloons drifting away (letting go, relief, acceptance)",
    bars_up="growing bar chart (progress, improvement, results)", bars_down="shrinking bar chart (decline, loss, falling behind)", scale="balance scale (weighing, fairness, trade-off)",
    brain="brain (the mind, psychology)", bulb="light bulb (an idea, insight, answer)", battery="battery (energy, burnout)", hourglass="hourglass (time passing, waiting, procrastination)",
    scroll_phone="scrolling phone (social media, distraction)", target="target (goal, focus)", trophy="trophy (success)", calendar="calendar (habit, routine, days)",
    speech="speech bubble (a conversation, something said)", eye="eye (being watched, judged)", heart="heart (love, health, care)", coin="coin (money)", bed="bed (sleep)",
    book="book (learning, studying, evidence)", laptop="laptop (work)", gear="gear (a mechanism, control)", lock="padlock (control, secrets, being closed)", ladder="ladder (climbing, steps)",
    sprout="sprout (growth, a beginning)", clock="clock (time)", checklist="checklist (tasks, a plan)", flag="flag (a milestone or goal reached)", crowd="crowd (other people, society)",
)


def _beats(raw_scenes):
    from .collage_dir import split_beats
    out = []
    for sc in raw_scenes:
        for s in sc.sentences:
            text = s.text.strip()
            for (c0, c1) in split_beats(text):
                b = text[c0:c1].strip()
                if b:
                    out.append(b)
    return out


def _provider():
    if os.environ.get("YUKI_LLM_URL") and os.environ.get("YUKI_LLM_KEY"):
        return dict(kind="openai", name="custom", url=os.environ["YUKI_LLM_URL"], key=os.environ["YUKI_LLM_KEY"], models=[os.environ.get("YUKI_LLM_MODEL") or os.environ.get("YUKI_BRAIN_MODEL") or "default"])
    if os.environ.get("GROQ_API_KEY"):
        m = os.environ.get("YUKI_BRAIN_MODEL")
        return dict(kind="openai", name="groq", url="https://api.groq.com/openai/v1/chat/completions", key=os.environ["GROQ_API_KEY"],
                    models=[m] if m else ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "llama-3.1-70b-versatile"])
    if os.environ.get("GEMINI_API_KEY"):
        m = os.environ.get("YUKI_BRAIN_MODEL")
        return dict(kind="gemini", name="gemini", url="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", key=os.environ["GEMINI_API_KEY"],
                    models=[m] if m else ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"])
    return None


def _system_prompt():
    from . import entities as E
    things = sorted(set(E.ENTITY_FN) & set(GLOSS)) + sorted(n for n in E.ENTITY_FN if n not in GLOSS)
    gl = "\n".join(f"  {n}: {GLOSS.get(n, '')}".rstrip(": ") for n in things)
    return f"""You are the art director of a cartoon explainer channel. A cartoon girl, Yuki, narrates; beside her a picture appears for every short phrase of the script.
Your job, for each numbered phrase: understand what it MEANS in context, then choose how Yuki reacts and what drawing would EXPLAIN the idea to a viewer (not merely decorate it).
Think about negation ("you don't have to worry" is relief), irony, abstract ideas (use a visual metaphor) and the story so far.

Answer with JSON only: {{"beats":[{{"i":<number>,"role":..,"emotion":..,"face":..,"pose":..,"metaphors":[..],"icon_words":[..],"place":..,"action":..}}]}} with ONE entry per phrase, same numbers.
Allowed values (anything else is ignored):
 role: {", ".join(U.ROLES)}
 emotion (the feeling the phrase carries): {", ".join(U.EMOTIONS)}
 face: {", ".join(sorted(U.FACES))}
 pose: {", ".join(sorted(U.POSES))}   (poses never touch the face; pick one that fits the meaning and varies from the previous phrase)
 metaphors: 0-2 drawings, ONLY if they truly illustrate the idea, otherwise [].  Choices:
{gl}
 icon_words: up to 3 simple concrete English nouns for objects the phrase names or clearly implies, e.g. "phone", "bed", "calendar"; [] if none.
 place: optional, one of {", ".join(sorted(PLACES))} - only if the phrase clearly happens somewhere, else null.
 action: optional, what a cartoon person in the picture does: one of {", ".join(sorted(ACTIONS))}, else null.
Be specific and varied: do not give every phrase the same face, pose or drawing."""


def _post(url, headers, body, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "yuki-lab/1.0", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _ask(prov, system, user):
    """-> parsed JSON dict or None.  Tries the provider's models in order."""
    last = None
    for model in prov["models"]:
        for attempt in range(2):
            try:
                if prov["kind"] == "openai":
                    body = dict(model=model, temperature=0.3, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], response_format={"type": "json_object"})
                    data = _post(prov["url"], {"Authorization": "Bearer " + prov["key"]}, body)
                    txt = data["choices"][0]["message"]["content"]
                else:
                    body = dict(systemInstruction={"parts": [{"text": system}]}, contents=[{"role": "user", "parts": [{"text": user}]}],
                                generationConfig=dict(temperature=0.3, responseMimeType="application/json"))
                    data = _post(prov["url"].format(model=model), {"x-goog-api-key": prov["key"]}, body)
                    txt = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
                txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
                return json.loads(txt)
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code in (400, 404):                    # unknown model / bad request: try the next model
                    break
                if e.code in (429, 500, 502, 503):
                    time.sleep(3 + 4 * attempt)
                    continue
                return None                                  # 401/403: the key is wrong, do not hammer
            except Exception as e:                           # timeouts, bad JSON ...
                last = type(e).__name__
                time.sleep(1.5)
    print(f"  [brain] no answer from {prov['name']} ({last})", flush=True)
    return None


def _clean(e):
    """One model answer -> only values the lab understands."""
    from . import entities as E
    out = {}
    role = str(e.get("role") or "").lower()
    if role in U.ROLES:
        out["role"] = role
    emo = str(e.get("emotion") or "").lower()
    if emo in U.EMOTIONS:
        out["emotion"] = emo
    face = str(e.get("face") or "").lower()
    if face in U.FACES:
        out["face"] = face
    pose = str(e.get("pose") or "").lower().replace(" ", "_")
    pose = {"think": "ponder", "facepalm": "slump_sigh", "head": "worry"}.get(pose, pose)
    if pose in U.POSES:
        out["pose"] = pose
    mt = [m for m in (e.get("metaphors") or []) if isinstance(m, str) and m in E.ENTITY_FN][:2]
    if mt:
        out["metaphors"] = mt
    iw = [re.sub(r"[^a-z ]", "", w.lower()).strip() for w in (e.get("icon_words") or []) if isinstance(w, str)]
    iw = [w for w in iw if w and len(w) < 24][:3]
    if iw:
        out["icon_words"] = iw
    if str(e.get("place") or "").lower() in PLACES:
        out["place"] = str(e["place"]).lower()
    if str(e.get("action") or "").lower() in ACTIONS:
        out["action"] = str(e["action"]).lower()
    return out


def prime(title, raw_scenes, chunk=26):
    """-> {normalised beat text: hints}  ({} when no key / no answer)."""
    prov = _provider()
    if not prov:
        return {}
    beats = _beats(raw_scenes)
    if not beats:
        return {}
    system = _system_prompt()
    key = hashlib.sha1((prov["name"] + "|" + (prov["models"][0] or "") + "|" + system + "|" + "\n".join(beats)).encode()).hexdigest()[:16]
    cache = CACHE / f"{key}.json"
    try:
        if cache.exists():
            data = json.loads(cache.read_text())
            print(f"  [brain] {len(data)} beats from cache", flush=True)
            return data
    except Exception:
        pass
    out = {}
    for c0 in range(0, len(beats), chunk):
        part = beats[c0:c0 + chunk]
        ctx = beats[max(0, c0 - 3):c0]
        user = f"Video title: {title or '(untitled)'}\n"
        if ctx:
            user += "Earlier phrases (context only, do not answer):\n" + "\n".join("  - " + b for b in ctx) + "\n"
        user += "Phrases to direct:\n" + "\n".join(f"{i}. {b}" for i, b in enumerate(part)) + f"\n(total phrases in the video: {len(beats)}; the last one wraps up the video)"
        ans = _ask(prov, system, user)
        if not ans:
            continue
        items = ans.get("beats") if isinstance(ans, dict) else ans
        for e in items or []:
            try:
                i = int(e.get("i"))
            except Exception:
                continue
            if 0 <= i < len(part):
                h = _clean(e)
                if h:
                    out[U.norm(part[i])] = h
    if out:
        print(f"  [brain] {prov['name']}: directed {len(out)}/{len(beats)} beats", flush=True)
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(out))
        except Exception:
            pass
    return out
