"""Pictures for the collage look.

Every beat of a collage video shows a picture. Where it comes from is decided per run (`--media`):

    auto    your own files in media/  ->  AI-drawn picture (Pollinations, free, no key)  ->  free-licence stock photo
            (Wikimedia Commons / Openverse)  ->  a picture drawn by the lab itself (never fails)
    ai      your files -> AI picture -> drawn
    stock   your files -> stock photo -> drawn
    local   only your files in media/ -> drawn
    drawn   always the lab's own drawings (works offline; this is what the preview uses)

Nothing is copied from films, TV or other people's videos. Stock photos are only taken when their licence is CC0, public domain,
CC BY or CC BY-SA, and the credit lines are written to <video>.credits.txt so they can go in the video description.

Your own pictures: put images in media/ (jpg/png/webp). A file is used when its name shares words with what the beat is about
(media/tired-man.jpg matches "a tired man rubbing his eyes"), or when a script cue names it: [show: file:tired-man.jpg].
"""
import hashlib, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image

UA = "YukiLab/1.0 (+https://github.com/sabaghanbarlo-hash/yuki-video; contact: github issues)"
AI_STYLE = ", flat vector editorial illustration, paper-cut collage, muted warm colours, simple shapes, soft grain, centered subject, no text, no letters, no watermark"
OK_LICENCES = ("cc0", "public domain", "pd", "cc by", "cc-by", "cc by-sa", "cc-by-sa")
BAD_WORDS = re.compile(r"\b(logo|flag|map of|diagram|screenshot|poster|coat of arms|signature|stamp)\b", re.I)
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
STOP = set("a an the and or of to in on at for with by from as is are was were be been it its this that these those you your i my we our they their he she his her".split())


def log(*a):
    print("  [media]", *a, flush=True)


# ------------------------------------------------------------------ http
def _get(url, timeout=40, tries=2, headers=None, backoff=4.0):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 429 or e.code >= 500:
                time.sleep(backoff * (i + 1))
                continue
            break
        except Exception as e:                                   # network down, blocked host, timeout ...
            last = type(e).__name__
            time.sleep(1.0)
    raise IOError(last or "failed")


def _as_image(data, min_w=320):
    im = Image.open(io.BytesIO(data))
    im.load()
    im = im.convert("RGB")
    if im.width < min_w:
        raise ValueError("too small")
    if max(im.size) > 1600:
        k = 1600 / max(im.size)
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    return im


# ------------------------------------------------------------------ the sources
def words_of(text):
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in STOP and len(w) > 2]


def local_match(query, folder, want=None):
    """A picture of yours in media/ whose file name shares words with the query (or is named exactly)."""
    folder = Path(folder)
    if not folder.is_dir():
        return None
    files = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in IMG_EXT]
    if want:
        for p in files:
            if p.name.lower() == want.lower():
                return p
    q = set(words_of(query))
    best, bs = None, 0
    for p in files:
        toks = set(words_of(re.sub(r"[-_.]+", " ", p.stem)))
        sc = len(q & toks)
        if sc > bs:
            best, bs = p, sc
    return best if bs >= 1 else None


def ai_image(prompt, w, h, seed):
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt + AI_STYLE) +
           f"?width={w}&height={h}&seed={seed}&nologo=true&model=flux&safe=true&private=true&nofeed=true")
    data, ctype = _get(url, timeout=70, tries=3, backoff=8.0)
    if "image" not in ctype and not data[:4] in (b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\x89PNG"):
        raise ValueError("not an image")
    return _as_image(data, 256), "AI-generated picture (Pollinations)"


def _licence_ok(s):
    s = (s or "").lower().replace("_", " ")
    if "nc" in s.split() or "-nc" in s or " nc" in s or "nd" in s.split():
        return False
    return any(s.startswith(x) or x in s for x in OK_LICENCES)


def wikimedia(query, seed):
    q = urllib.parse.quote(f"{query} filetype:bitmap")
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=12"
           f"&gsrsearch={q}&prop=imageinfo&iiprop=url|extmetadata|size|mime&iiurlwidth=1280")
    data, _ = _get(url, timeout=30, tries=2)
    pages = list((json.loads(data).get("query") or {}).get("pages", {}).values())
    pages.sort(key=lambda p: p.get("index", 99))
    cands = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        title = p.get("title", "")
        if ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 700 or not _licence_ok(lic) or BAD_WORDS.search(title):
            continue
        art = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip() or "unknown author"
        cands.append((ii.get("thumburl") or ii.get("url"), f"{title.replace('File:', '')} - {art} - {lic} - Wikimedia Commons"))
    if not cands:
        raise LookupError("no match")
    url_, credit = cands[seed % min(len(cands), 4)]
    data, _ = _get(url_, timeout=40, tries=2)
    return _as_image(data, 500), credit


def openverse(query, seed):
    url = ("https://api.openverse.org/v1/images/?q=" + urllib.parse.quote(query) +
           "&license=cc0,pdm,by,by-sa&extension=jpg,png&page_size=12&mature=false")
    data, _ = _get(url, timeout=30, tries=2)
    res = [r for r in json.loads(data).get("results", []) if (r.get("width") or 0) >= 700 and not BAD_WORDS.search(r.get("title") or "")]
    if not res:
        raise LookupError("no match")
    r = res[seed % min(len(res), 4)]
    img, _ = _get(r.get("thumbnail") or r["url"], timeout=40, tries=2)
    credit = f"{(r.get('title') or 'picture').strip()} - {r.get('creator') or 'unknown author'} - {(r.get('license') or '').upper()} {r.get('license_version') or ''} - {r.get('source') or 'Openverse'}"
    return _as_image(img, 500), credit.strip()


# ------------------------------------------------------------------ one picture
def get_media(query, mode, w, h, seed, cache_dir, local_dir, want_file=None, stock_query=None):
    """-> dict(path, source, credit) or None (then the stage draws the picture itself)."""
    cache_dir = Path(cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    if mode == "drawn":
        return None
    p = local_match(f"{query} {stock_query or ''}", local_dir, want_file)
    if p is not None:
        return dict(path=str(p), source="yours", credit="")
    if want_file:
        log(f"file {want_file} not found in media/")
    if mode == "local":
        return None
    key = hashlib.md5(f"{mode}|{query}|{stock_query}|{w}x{h}|{seed}".encode()).hexdigest()[:16]
    cp = cache_dir / f"{key}.jpg"
    meta = cache_dir / f"{key}.json"
    if cp.exists() and meta.exists():
        return dict(path=str(cp), **json.loads(meta.read_text()))
    order = {"auto": ("ai", "wikimedia", "openverse"), "ai": ("ai",), "stock": ("wikimedia", "openverse")}.get(mode, ())
    for src in order:
        if src in _DEAD:
            continue
        try:
            if src == "ai":
                im, credit = ai_image(query, w, h, seed)
            elif src == "wikimedia":
                im, credit = wikimedia(stock_query or query, seed)
            else:
                im, credit = openverse(stock_query or query, seed)
            im.save(cp, quality=90)
            info = dict(source=src, credit="" if src == "ai" else credit)
            meta.write_text(json.dumps(info))
            return dict(path=str(cp), **info)
        except Exception as e:
            _FAILS[src] = _FAILS.get(src, 0) + 1
            log(f"{src} failed for '{query[:50]}': {type(e).__name__} {e}")
            if _FAILS[src] >= 4 and src not in _OK:                 # the source is unreachable: stop wasting time on it
                _DEAD.add(src)
                log(f"{src} looks unreachable here - skipping it from now on")
        else:
            pass
    return None


_FAILS, _DEAD, _OK = {}, set(), set()


def prefetch(plan, mode="auto", cache_dir=".work/media", local_dir="media", budget=900.0):
    """Fetch the picture of every collage shot before rendering. Fills shot['media'] = [paths] and writes plan['credits'].
    Takes at most `budget` seconds; shots left without a picture are drawn by the stage."""
    t0 = time.time()
    credits, n_total, n_got, n_ai, n_stock, n_own = [], 0, 0, 0, 0, 0
    last_ai = 0.0
    for sc in plan["scenes"]:
        if sc.get("style") != "collage":
            continue
        smode = (sc.get("cues", {}).get("media") or mode).lower()
        if smode not in ("auto", "ai", "stock", "local", "drawn"):
            smode = mode
        for sh in sc["shots"]:
            qs = sh.get("queries") or []
            sh["media"] = []
            if not qs or sh.get("kind") not in ("media", "text"):
                continue
            for qi, q in enumerate(qs):
                n_total += 1
                if time.time() - t0 > budget:
                    sh["media"].append(None); continue
                w, h = sh.get("media_size", (1024, 576))
                if smode in ("auto", "ai"):
                    gap = 4.0 - (time.time() - last_ai)               # be gentle with the free service
                    if gap > 0:
                        time.sleep(gap)
                got = get_media(q, smode, w, h, sh.get("seed", 1) + qi * 17, cache_dir, local_dir,
                                want_file=sh.get("file"), stock_query=(sh.get("stock_queries") or [None] * 9)[qi])
                if got and got["source"] == "ai":
                    last_ai = time.time()
                sh["media"].append(got["path"] if got else None)
                if got:
                    n_got += 1
                    n_ai += got["source"] == "ai"; n_own += got["source"] == "yours"
                    n_stock += got["source"] in ("wikimedia", "openverse")
                    if got.get("credit"):
                        credits.append(got["credit"])
    plan["credits"] = sorted(set(credits))
    plan["media_stats"] = dict(total=n_total, found=n_got, ai=n_ai, stock=n_stock, yours=n_own, drawn=n_total - n_got)
    log(f"{n_got}/{n_total} pictures found (AI {n_ai}, stock {n_stock}, yours {n_own}); the other {n_total - n_got} are drawn by the lab")
    return plan
