"""Small, stateless motion helpers for Yuki. Everything depends only on (t, seed), so frames can be rendered in any order.

    blink_phase(t, seed)        0 = eyes open, 1 = half closed, 2 = closed   (single and now and then double blinks, never on a fixed beat)
    beat(t, seed)               0..1 pulse: a small emphasis "beat gesture" every ~1.1-1.9 s at pseudo-random moments
    saccade(t, seed)            tiny eye movements so the gaze is never frozen
    ease_out_back / smooth      easing with a little overshoot, so poses settle instead of stopping dead
    ENERGY                      how big the gestures are for a feeling (excited big, sad / sleepy small)
"""
import math


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out_back(x, c=1.25):
    """0 -> 1 with a small overshoot (about 7 % for c = 1.25)."""
    x = clamp(x)
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def hash01(k, salt=0):
    """Repeatable pseudo-random number in 0..1 from an integer."""
    n = (int(k) * 374761393 + int(salt) * 668265263 + 1442695040888963407) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    n ^= n >> 16
    return (n & 0xFFFFFF) / float(0x1000000)


def blink_phase(t, seed=0):
    """0 open, 1 half closed, 2 closed.  A blink every ~2.4-4.4 s at irregular moments, about one in five is a double blink."""
    per = 3.4
    k = int(math.floor((t + seed * 0.37) / per))
    for kk in (k - 1, k):                               # a blink may spill over into the next period (double blinks)
        start = kk * per - seed * 0.37 + 0.35 + hash01(kk, seed) * 2.3
        for i, off in enumerate((0.0, 0.26) if hash01(kk, seed + 7) > 0.8 else (0.0,)):
            u = t - (start + off)
            if 0.0 <= u < 0.17:
                return 1 if (u < 0.045 or u >= 0.115) else 2
    return 0


def beat(t, seed=0, period=1.5):
    """A short emphasis pulse (0..1): quick attack, soft release.  One per period at a pseudo-random moment."""
    k = int(math.floor(t / period))
    out = 0.0
    for kk in (k - 1, k):
        start = kk * period + hash01(kk, seed + 3) * period * 0.55
        u = t - start
        if 0.0 <= u < 0.62:
            a = smooth(u / 0.09) * math.exp(-max(0.0, u - 0.09) * 5.2)
            out = max(out, a)
    return out


def saccade(t, seed=0):
    """-> (dx, dy) in -1..1: the eyes rest, then flick to a nearby spot, a few times a second."""
    per = 0.9
    k = int(math.floor(t / per))
    x = (hash01(k, seed + 11) - 0.5) * 2.0
    y = (hash01(k, seed + 12) - 0.5) * 2.0
    if hash01(k, seed + 13) < 0.45:           # often she just keeps looking where she was looking
        x = y = 0.0
    return x * 0.5, y * 0.4


ENERGY = {
    "excited": 1.3, "laughing": 1.35, "starry": 1.2, "gasp": 1.25, "shocked": 1.2, "inspired": 1.2, "angry": 1.15, "proud": 1.1, "terrified": 1.2,
    "happy": 1.05, "cheeky": 1.05, "yum": 1.0, "determined": 1.1, "scheming": 0.9, "smile": 0.95, "neutral": 0.9, "curious": 0.95, "confused": 0.85,
    "dizzy": 0.9, "nervous": 0.9, "worried": 0.75, "awkward": 0.7, "embarrassed": 0.7, "dreamy": 0.6, "lovestruck": 0.8, "smug": 0.7, "grumpy": 0.8,
    "pained": 0.7, "sad": 0.45, "crying": 0.55, "teary": 0.5, "serene": 0.5, "deadpan": 0.45, "bored": 0.4, "sleepy": 0.35, "creepy": 0.4,
}
