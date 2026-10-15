"""Script clean-up: turns a script pasted from anywhere (chat apps, docs, AI chats) into what Yuki should actually say.

Never spoken (turned into on-screen scene titles or simply dropped):
  * chat-app stamps      [10/15/2026 4:20 PM] Name:   /  12/10/2026, 4:20 PM - Name:   /  Name, [10/15/2026 4:20 PM]
  * a title line         TITLE: My Video        ->  the video title
  * section markers      [HOOK - 0:00]  [CHAPTER 1: THE FIRST DAY - 0:50]  CHAPTER 2: Making friends  Part 3  1. The ending
  * stage directions     [music]  [pause]  (laughs)  [B-ROLL: classroom]
  * timestamps alone on a line, ----- rules, markdown symbols (** # _), emojis
Chapter names become the small on-screen chip and start a new scene (so the background can change).
Cues such as [theme: classroom] [sfx: door_slam] [face: angry] [pose: cheer] [emote: !] [nosfx] [cast: ...] are kept.
"""
import re

CUE_KEYS = r"(?:theme|sfx|face|pose|emote|nosfx|cast|none|show|text|icon|list|steps|compare|loop|stat|quote|image|pic)"
STAMPS = [
    re.compile(r"^\s*\[\s*\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}[,\s]+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?\s*\]\s*[^:\n\[\]]{1,60}?:\s*"),
    re.compile(r"^\s*\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4},?\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?\s*[-\u2013\u2014]\s*[^:\n]{1,60}?:\s*"),
    re.compile(r"^\s*\[\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?\s*\]\s*[^:\n\[\]]{1,40}?:\s*"),
]
STAMP_OWN_LINE = re.compile(r"^\s*[^\n:\[\]]{1,40},\s*\[\s*\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}[^\]]*\]\s*$")
TITLE_RE = re.compile(r"^\s*(?:video\s+)?title\s*[:\-\u2013\u2014]\s*(.+?)\s*$", re.I)
CHAPTER_RE = re.compile(r"^(?:chapter|part|scene|section|act|segment|story|lesson|step|point|tip|rule|habit|reason|day|episode)\s*(?:#|no\.?|number)?\s*(?:\d{1,3}|[ivx]{1,5}|one|two|three|four|five|six|seven|eight|nine|ten)\b\s*[:.\-\u2013\u2014)]*\s*(.*)$", re.I)
BARE_MARK_RE = re.compile(r"^(?:hook|intro|introduction|opening|outro|ending|end|conclusion|closing|call to action|cta|recap|summary|prologue|epilogue|the end)\s*(?:[:.\-\u2013\u2014].*)?$", re.I)
NOTE_RE = re.compile(r"^(?:music|sfx|sound|pause|beat|b-?roll|transition|cut|cut to|fade|visual|visuals|on[- ]screen|screen|voice ?over|v\.?o\.?|narrator|note|notes|laughs?|laughter|sighs?|smiles?|\.\.\.)\b", re.I)
TIME_TAIL = re.compile(r"\s*[\u2014\u2013\-|@(]*\s*\(?\b\d{1,2}:\d{2}(?::\d{2})?\)?\s*$")
NUMBERED = re.compile(r"^\s*\d{1,2}[.)]\s+(.{2,70})$")
EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2B50\u2B06\u2B07\u2934\u2935\u3030\u303D\u3297\u3299\uFE0F\u200D]")


def _title_case(s):
    s = re.sub("[\"\u201c\u201d]", "", s).strip(" \t:-\u2013\u2014.")
    if not s:
        return ""
    small = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "at", "by", "vs", "is", "it"}
    words = s.lower().split()
    out = [w if (i and w in small) else re.sub(r"[a-z]", lambda m: m.group(0).upper(), w, count=1) for i, w in enumerate(words)]
    return " ".join(out)


def _label(text):
    """'CHAPTER 1: THE FIRST DAY - 0:50' -> 'The First Day';  'HOOK - 0:00' -> ''"""
    t = TIME_TAIL.sub("", text).strip()
    t = re.sub(r"^[\[(\s]+|[\])\s]+$", "", t)
    m = CHAPTER_RE.match(t)
    if m:
        t = m.group(1)
    elif BARE_MARK_RE.match(t):
        t = ""
    t = t.strip().strip("\"'\u201c\u201d")
    return _title_case(t)[:60] if t and len(t.split()) <= 12 else ""


def classify(line):
    """-> ('skip',) | ('title', text) | ('scene', label) | ('text', line)"""
    raw = line.strip()
    if not raw:
        return ("skip",)
    s = re.sub(r"^[#>*\s]+", "", raw) if not raw.startswith("##") else raw
    s = s.replace("**", "").replace("__", "").strip()
    if re.fullmatch(r"[-=_*~\u2014\u2013 ]{3,}", s):
        return ("scene", "")
    if re.fullmatch(r"\[?\(?\d{1,2}:\d{2}(?::\d{2})?\)?\]?", s):
        return ("skip",)
    m = TITLE_RE.match(s)
    if m:
        return ("title", m.group(1).strip().strip("\"'\u201c\u201d"))
    wrapped = re.fullmatch(r"[\[(]\s*(.+?)\s*[\])]", s)
    if wrapped and not re.match(r"\[\s*" + CUE_KEYS + r"\b", s, re.I):
        inner = wrapped.group(1)
        if CHAPTER_RE.match(TIME_TAIL.sub("", inner).strip()) or BARE_MARK_RE.match(TIME_TAIL.sub("", inner).strip()) \
                or re.search(r"\d{1,2}:\d{2}", inner):
            return ("scene", _label(inner))
        if NOTE_RE.match(inner) or s.startswith("("):
            return ("skip",)
        return ("scene", _label(inner)) if inner.isupper() else ("skip",)
    m = CHAPTER_RE.match(s)
    if m and len(s) <= 90 and not re.search(r"[.!?]\s+\w", s):
        return ("scene", _label(s))
    if BARE_MARK_RE.match(s) and len(s) <= 40 and not s.endswith((".", "!", "?")) or re.fullmatch(r"(?:hook|intro|outro|ending)\s*[:\u2014\u2013-].*", s, re.I) and len(s) <= 60:
        return ("scene", _label(s))
    m = NUMBERED.match(s)
    if m and len(m.group(1).split()) <= 8 and not m.group(1).rstrip().endswith((".", "!", "?", ",")):
        return ("scene", _title_case(m.group(1)))
    return ("text", raw)


def clean_spoken(t):
    """Make one line fit for the voice: no brackets, emojis, markdown or odd symbols."""
    t = re.sub(r"\[[^\]]*\]|\([^)]*\b(?:laughs?|pause|beat|sighs?|music|sfx)\b[^)]*\)", " ", t, flags=re.I)
    t = EMOJI.sub("", t)
    t = t.replace("**", "").replace("__", "").replace("`", "")
    t = re.sub(r"(?<!\w)[*_]+|[*_]+(?!\w)", "", t)
    t = t.replace("\u2014", ", ").replace("\u2013", ", ").replace(" - ", ", ").replace("&", " and ")
    t = re.sub(r"\s*,\s*,+", ",", t)
    t = re.sub(r"\s+([,.!?;:])", r"\1", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def preprocess(text):
    """Raw pasted script -> tidy script text: '# Title', '## Scene label', and plain paragraphs."""
    text = text.replace("\r\n", "\n").replace("\ufeff", "")
    out, title = [], None
    for ln in text.split("\n"):
        if STAMP_OWN_LINE.match(ln):
            continue
        for rx in STAMPS:
            ln2 = rx.sub("", ln, count=1)
            if ln2 != ln:
                ln = ln2
                break
        if not ln.strip():
            out.append("")
            continue
        if ln.lstrip().startswith("## ") or ln.lstrip().startswith("# "):
            out.append(ln.strip()); continue
        kind = classify(ln)
        if kind[0] == "skip":
            continue
        if kind[0] == "title":
            if title is None:
                title = kind[1]
            continue
        if kind[0] == "scene":
            out.append("")
            out.append("## " + kind[1] if kind[1] else "##")
            out.append("")
            continue
        out.append(ln.strip())
    body = "\n".join(out)
    if title and not re.search(r"^# ", body, re.M):
        body = "# " + title + "\n\n" + body
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"


def title_of(text):
    t = preprocess(text)
    m = re.search(r"^# (.+)$", t, re.M)
    return m.group(1).strip() if m else None
