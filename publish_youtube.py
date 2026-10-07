#!/usr/bin/env python3
"""Upload a rendered video to the Call of Yuki YouTube channel through Composio.

    python publish_youtube.py output/video.mp4 stories/script.txt

Env: COMPOSIO_API_KEY (required), PRIVACY (private|unlisted|public, default private),
     YT_ACCOUNT_ID (optional: Composio connected-account id; default = the 'call_of_yuki' channel),
     RESULT_JSON (optional: where to write {"id","url"}).

Composio's ready-made upload tools have had a bug that makes YouTube silently delete the video, so the main path
here talks to YouTube's resumable-upload API through Composio's authenticated proxy and sends the raw bytes
itself; the finished upload is then checked on YouTube. The ready-made tool is only a fallback.
"""
import hashlib, json, os, re, sys, time, urllib.error, urllib.request

mp4, script = sys.argv[1], sys.argv[2]
KEY = os.environ["COMPOSIO_API_KEY"]
PRIVACY = os.environ.get("PRIVACY", "private")
BASE = "https://backend.composio.dev"
CHANNEL_HINTS = ("call_of_yuki", "youtube_stramp-melam", "UCLzLuGd9DI8xAVyMF12ijLw", "yuukichandes")


def req(method, path, body=None, timeout=300):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={"x-api-key": KEY, "Content-Type": "application/json"})
    try:
        return 200, json.load(urllib.request.urlopen(r, timeout=timeout))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:800]
    except Exception as e:  # network
        return 0, str(e)


def find(o, pred):
    """First value anywhere in a nested structure for which pred(key, value) is true."""
    if isinstance(o, dict):
        for k, v in o.items():
            if pred(str(k), v):
                return v
            f = find(v, pred)
            if f:
                return f
    elif isinstance(o, list):
        for v in o:
            f = find(v, pred)
            if f:
                return f
    return None


# ---------------------------------------------------------------- which YouTube channel
code, r = req("GET", "/api/v3/connected_accounts?toolkit_slugs=youtube&statuses=ACTIVE&limit=50")
items = (r.get("items") if isinstance(r, dict) else None) or []
print(f"Found {len(items)} active YouTube connection(s).", flush=True)
want = os.environ.get("YT_ACCOUNT_ID", "").strip()
pick = None
for it in items:
    blob = json.dumps(it)
    if (want and (it.get("id") == want or want in blob)) or (not want and any(h in blob for h in CHANNEL_HINTS)):
        pick = it
        break
if not pick and len(items) == 1:
    pick = items[0]
if not pick:
    names = [f'{i.get("id")} {i.get("alias") or ""}' for i in items]
    sys.exit("Could not tell which connection is the Call of Yuki channel. Connections: " + "; ".join(names) +
             "\nSet the repository secret YT_ACCOUNT_ID to the right id.")
ACC, USER = pick.get("id"), pick.get("user_id")
print("Using connection:", ACC, pick.get("alias") or "", flush=True)

# ---------------------------------------------------------------- metadata
title, first = None, None
for line in open(script, encoding="utf-8"):
    line = line.strip()
    if line.startswith("# ") and not title:
        title = line[2:].strip()
    elif first is None and line and not line.startswith("#"):
        first = re.sub(r"^(\[[^\]]*\]\s*)+", "", line)
title = (title or os.path.splitext(os.path.basename(script))[0].replace("-", " ").title())[:100]
side = os.path.splitext(script)[0] + ".desc"
if os.path.exists(side) and open(side, encoding="utf-8").read().strip():
    desc = open(side, encoding="utf-8").read().strip()
else:
    desc = ((first or "")[:220].rstrip() + "…\n\n" if first else "") + \
        "Call of Yuki explores the hidden patterns of the mind through simple stories and psychology.\n\n" \
        "#selfimprovement #psychology #mindset"
meta = {"snippet": {"title": title, "description": desc[:4900], "categoryId": "27",
                    "tags": ["self improvement", "psychology", "mindset", "habits", "Call of Yuki"]},
        "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False}}
size = os.path.getsize(mp4)
print(f"Title: {title}\nPrivacy: {PRIVACY}\nFile: {mp4} ({size / 1e6:.1f} MB)", flush=True)


# ---------------------------------------------------------------- upload through the authenticated proxy
def proxy(method, url, body=None, headers=None):
    payload = {"endpoint": url, "method": method, "connected_account_id": ACC}
    if body is not None:
        payload["body"] = body
    if headers:
        payload["parameters"] = [{"name": k, "value": v, "type": "header"} for k, v in headers.items()]
    return req("POST", "/api/v3/tools/execute/proxy", payload)


def check_on_youtube(vid, wait=240):
    """True once YouTube still lists the video and has not rejected/deleted it."""
    end = time.time() + wait
    last = None
    while time.time() < end:
        code, r = proxy("GET", f"https://www.googleapis.com/youtube/v3/videos?part=status,processingDetails&id={vid}")
        data = r.get("data") if isinstance(r, dict) else None
        its = (data or {}).get("items") if isinstance(data, dict) else None
        if code == 200 and its:
            st = its[0].get("status", {}).get("uploadStatus")
            last = st
            if st in ("failed", "rejected", "deleted"):
                return False, st
            if st in ("processed", "uploaded") and time.time() > end - wait + 60:
                return True, st
        time.sleep(15)
    return (last in ("processed", "uploaded")), last


def upload_resumable():
    code, r = proxy("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                    body=meta, headers={"X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size),
                                        "Content-Type": "application/json; charset=UTF-8"})
    loc = find(r, lambda k, v: k.lower() == "location" and isinstance(v, str) and v.startswith("https://"))
    if not loc:
        print(f"Proxy gave no upload address (HTTP {code}); response keys: {list(r) if isinstance(r, dict) else str(r)[:200]}")
        return None
    print("Upload session opened. Sending video bytes...", flush=True)
    for attempt in range(3):
        try:
            put = urllib.request.Request(loc, method="PUT", data=open(mp4, "rb"),
                                         headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
            resp = json.load(urllib.request.urlopen(put, timeout=3600))
            return resp.get("id")
        except urllib.error.HTTPError as e:
            print("YouTube said:", e.code, e.read().decode(errors="replace")[:300])
            if e.code < 500:
                return None
        except Exception as e:
            print("upload attempt failed:", e)
        time.sleep(10 * (attempt + 1))
    return None


def upload_tool_fallback():
    md5 = hashlib.md5(open(mp4, "rb").read()).hexdigest()
    name = os.path.basename(mp4)
    for ver in ("v3.1", "v3"):
        code, r = req("POST", f"/api/{ver}/files/upload/request",
                      {"toolkit_slug": "youtube", "tool_slug": "YOUTUBE_MULTIPART_UPLOAD_VIDEO", "filename": name,
                       "mimetype": "video/mp4", "md5": md5})
        if code == 200:
            break
    else:
        print("file staging failed:", code, r)
        return None
    url = r.get("new_presigned_url") or r.get("newPresignedUrl")
    if url:
        urllib.request.urlopen(urllib.request.Request(url, method="PUT", data=open(mp4, "rb"),
                                                      headers={"Content-Type": "video/mp4"}), timeout=3600)
    body = {"connected_account_id": ACC, "version": "latest",
            "arguments": {"title": title, "description": desc[:4900], "categoryId": "27", "privacyStatus": PRIVACY,
                          "tags": meta["snippet"]["tags"],
                          "videoFile": {"name": name, "mimetype": "video/mp4", "s3key": r.get("key")}}}
    if USER:
        body["user_id"] = USER
    code, res = req("POST", "/api/v3/tools/execute/YOUTUBE_MULTIPART_UPLOAD_VIDEO", body, timeout=900)
    if code != 200:
        print("upload tool failed:", code, res)
        return None
    return find(res, lambda k, v: k == "id" and isinstance(v, str) and len(v) == 11)


vid = upload_resumable()
if not vid:
    print("Falling back to the ready-made Composio upload tool...", flush=True)
    vid = upload_tool_fallback()
if not vid:
    sys.exit("The upload did not go through. The video is still in this run's artifacts (download it from the run page).")
print("YouTube video id:", vid, flush=True)
ok, state = check_on_youtube(vid)
if not ok:
    sys.exit(f"YouTube accepted the upload but the video is not usable (state: {state}). "
             "Download it from this run's artifacts and upload it by hand.")
url = f"https://youtu.be/{vid}"
print("PUBLISHED:", url, f"({state})")
out = os.environ.get("RESULT_JSON")
if out:
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump({"id": vid, "url": url, "title": title, "privacy": PRIVACY}, open(out, "w"))
