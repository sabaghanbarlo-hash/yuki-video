#!/usr/bin/env python3
"""Upload a rendered video to YouTube with the official YouTube Data API (resumable upload).

    python publish_youtube.py output/video.mp4 stories/script.txt

Env (repository secrets): YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Optional: PRIVACY (private|unlisted|public, default private), RESULT_JSON (where to write {"id","url"}).
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

mp4, script = sys.argv[1], sys.argv[2]
PRIVACY = os.environ.get("PRIVACY", "private")
need = [k for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN") if not os.environ.get(k)]
if need:
    sys.exit("Missing repository secret(s): " + ", ".join(need))


def post_form(url, data):
    r = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    try:
        return json.load(urllib.request.urlopen(r, timeout=60))
    except urllib.error.HTTPError as e:
        sys.exit(f"Google refused the login ({e.code}): {e.read().decode(errors='replace')[:300]}\n"
                 "If it says invalid_grant, the refresh token expired or was revoked: make a new one (see README).")


tok = post_form("https://oauth2.googleapis.com/token",
                {"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                 "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"})
AUTH = {"Authorization": "Bearer " + tok["access_token"]}

# ---------------------------------------------------------------- metadata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab.script import parse
from lab import knowledge as K
_text = open(script, encoding="utf-8").read()
title, _scenes = parse(_text)
first = _scenes[0].sentences[0].text if _scenes and _scenes[0].sentences else ""
topic = K.topic_of(_text) or "science"
title = (title or os.path.splitext(os.path.basename(script))[0].replace("-", " ").title())[:100]
side = os.path.splitext(script)[0] + ".desc"
if os.path.exists(side) and open(side, encoding="utf-8").read().strip():
    desc = open(side, encoding="utf-8").read().strip()
else:
    desc = ((first or "")[:220].rstrip() + "\n\n" if first else "") + \
        "Yuki Lab: animated science explainers, fascinating facts and what-if scenarios.\n\n#science #education #whatif"
TAGS = {"space": "space", "earth": "earth science", "ocean": "ocean", "weather": "weather", "volcano": "volcano", "ice": "ice", "desert": "desert", "nature": "nature",
        "body": "human body", "brain": "brain", "micro": "biology", "physics": "physics", "tech": "technology", "city": "cities", "history": "history", "disaster": "disasters"}
_cred = os.path.splitext(mp4)[0] + ".credits.txt"
if _cred and os.path.exists(_cred):
    desc = desc + "\n\n" + open(_cred, encoding="utf-8").read().strip()
meta = {"snippet": {"title": title, "description": desc[:4900], "categoryId": "27",
                    "tags": ["science", "explained", "what if", "facts", "animation", TAGS.get(topic, "science"), "Yuki Lab"]},
        "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False}}
size = os.path.getsize(mp4)
print(f"Title: {title}\nPrivacy: {PRIVACY}\nFile: {mp4} ({size / 1e6:.1f} MB)", flush=True)

# ---------------------------------------------------------------- resumable upload
r = urllib.request.Request(
    "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
    data=json.dumps(meta).encode(), method="POST",
    headers={**AUTH, "Content-Type": "application/json; charset=UTF-8",
             "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
try:
    loc = urllib.request.urlopen(r, timeout=60).headers["Location"]
except urllib.error.HTTPError as e:
    sys.exit(f"YouTube refused to start the upload ({e.code}): {e.read().decode(errors='replace')[:400]}")
print("Upload session opened. Sending video...", flush=True)

vid, body = None, {}
for attempt in range(4):
    try:
        put = urllib.request.Request(loc, method="PUT", data=open(mp4, "rb"),
                                     headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
        body = json.load(urllib.request.urlopen(put, timeout=3600))
        vid = body.get("id")
        break
    except urllib.error.HTTPError as e:
        print("YouTube said:", e.code, e.read().decode(errors="replace")[:300], flush=True)
        if e.code < 500:
            break
    except Exception as e:
        print("upload attempt failed:", e, flush=True)
    time.sleep(10 * (attempt + 1))
if not vid:
    sys.exit("The upload did not go through. The video is still in this run's artifacts.")

# ---------------------------------------------------------------- confirm
# The upload answer itself says what YouTube stored. (The upload-only permission cannot look videos up
# afterwards, so a lookup is only a bonus and its errors are ignored.)
st = body.get("status", {})
state = st.get("uploadStatus") or "uploaded"
priv = st.get("privacyStatus") or PRIVACY
if state in ("failed", "rejected", "deleted"):
    sys.exit(f"YouTube rejected the video (state: {state}, reason: {st.get('rejectionReason') or st.get('failureReason')}).")
class _Items(list):
    pass
items = [{"status": {"uploadStatus": state, "privacyStatus": priv}}]
url = f"https://youtu.be/{vid}"
print("PUBLISHED:", url, f"({state}, {items[0]['status'].get('privacyStatus')})")

# ---------------------------------------------------------------- thumbnail (best effort)
thumb = os.environ.get("THUMBNAIL") or (sys.argv[3] if len(sys.argv) > 3 else None)
thumb_state = "none"
if thumb and os.path.exists(thumb):
    ctype = "image/png" if thumb.lower().endswith(".png") else "image/jpeg"
    for attempt in range(3):
        try:
            tr = urllib.request.Request(
                f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media",
                data=open(thumb, "rb").read(), method="POST", headers={**AUTH, "Content-Type": ctype})
            urllib.request.urlopen(tr, timeout=120).read()
            thumb_state = "set"; print("Thumbnail set.", flush=True); break
        except urllib.error.HTTPError as e:
            thumb_state = f"failed {e.code}"
            print("Thumbnail not set:", e.code, e.read().decode(errors="replace")[:300], flush=True)
            if e.code < 500: break
        except Exception as e:
            thumb_state = f"failed {e}"; print("Thumbnail error:", e, flush=True)
        time.sleep(5)
out = os.environ.get("RESULT_JSON")
if out:
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump({"id": vid, "url": url, "title": title, "privacy": items[0]["status"].get("privacyStatus", PRIVACY), "thumbnail": thumb_state}, open(out, "w"))
