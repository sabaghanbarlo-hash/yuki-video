"""Fonts: Poppins (bundled in assets/fonts, downloaded if missing), DejaVu as fallback."""
import functools, urllib.request
from pathlib import Path
from PIL import ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-{}.ttf"
WEIGHTS = {"regular": "Regular", "medium": "Medium", "semibold": "SemiBold", "bold": "Bold"}
FALLBACK = {"regular": "DejaVuSans.ttf", "medium": "DejaVuSans.ttf", "semibold": "DejaVuSans-Bold.ttf", "bold": "DejaVuSans-Bold.ttf"}


def _fetch(weight):
    p = FONT_DIR / f"Poppins-{WEIGHTS[weight]}.ttf"
    if p.exists() and p.stat().st_size > 10000:
        return p
    try:
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(BASE.format(WEIGHTS[weight]), p)
        if p.stat().st_size > 10000:
            return p
    except Exception:
        pass
    return None


@functools.lru_cache(None)
def font(size, weight="bold"):
    p = _fetch(weight)
    if p:
        return ImageFont.truetype(str(p), int(size))
    for base in ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/"):
        f = Path(base) / FALLBACK[weight]
        if f.exists():
            return ImageFont.truetype(str(f), int(size))
    return ImageFont.load_default()
