"""Fonts: Poppins is bundled in assets/fonts (OFL licence), DejaVu is the fallback."""
import functools
from pathlib import Path
from PIL import ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FILES = {"regular": "Poppins-Regular.ttf", "medium": "Poppins-Medium.ttf", "semibold": "Poppins-Bold.ttf", "bold": "Poppins-Bold.ttf"}
FALLBACK = {"regular": "DejaVuSans.ttf", "medium": "DejaVuSans.ttf", "semibold": "DejaVuSans-Bold.ttf", "bold": "DejaVuSans-Bold.ttf"}


@functools.lru_cache(None)
def font(size, weight="bold"):
    p = FONT_DIR / FILES.get(weight, FILES["bold"])
    if p.exists():
        return ImageFont.truetype(str(p), int(size))
    for base in ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/", "/usr/share/fonts/truetype/google-fonts/"):
        f = Path(base) / FALLBACK.get(weight, "DejaVuSans-Bold.ttf")
        if f.exists():
            return ImageFont.truetype(str(f), int(size))
    return ImageFont.load_default()
