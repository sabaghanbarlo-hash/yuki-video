"""Video format: where the frame size lives.

    long   1280 x 720   landscape 16:9 - a normal YouTube video
    short   720 x 1280  portrait 9:16  - a YouTube Short (Collage look, same engine, vertical layouts)

`set_format()` must be called once, before anything is planned or rendered (generate.py does it). The frame size is read
at call time by lab/compose.py, lab/collage.py and lab/overlays.py, and the render workers are forked afterwards, so they inherit it.
"""
SIZES = {"long": (1280, 720), "short": (720, 1280)}
_cur = "long"


def set_format(name):
    global _cur
    name = (name or "long").lower()
    if name not in SIZES:
        raise SystemExit(f"unknown format {name!r}: use long or short")
    _cur = name
    w, h = SIZES[name]
    from . import compose, collage, overlays
    compose.W, compose.H = w, h
    collage.W, collage.H = w, h
    overlays.W, overlays.H = w, h
    collage.paper.cache_clear()
    return w, h


def current():
    return _cur


def is_short():
    return _cur == "short"


def size():
    return SIZES[_cur]
