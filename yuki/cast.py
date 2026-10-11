"""The supporting cast for story mode: looks, genders and voices, picked from the character's name."""
import zlib
from .character import Look, YUKI

SKINS = [(255, 225, 204), (246, 208, 178), (222, 168, 128), (186, 130, 96)]

GIRLS = [
    Look(hair=(70, 44, 42), top=(240, 150, 170), top_d=(214, 120, 146), sleeve=(236, 142, 164), bottom=(120, 100, 150), scarf=None, clip=(250, 220, 120), style="long"),
    Look(hair=(236, 196, 104), top=(250, 214, 96), top_d=(222, 184, 70), sleeve=(244, 206, 88), bottom=(90, 120, 170), scarf=None, clip=(240, 110, 130), style="bob"),
    Look(hair=(40, 34, 44), top=(150, 130, 220), top_d=(120, 102, 190), sleeve=(142, 122, 212), bottom=(70, 70, 100), scarf=None, clip=None, style="bun"),
    Look(hair=(150, 70, 52), top=(96, 190, 190), top_d=(70, 160, 162), sleeve=(88, 182, 184), bottom=(60, 70, 96), scarf=None, clip=(255, 255, 255), style="long"),
]
BOYS = [
    Look(hair=(38, 32, 40), top=(96, 150, 230), top_d=(70, 122, 204), sleeve=(88, 142, 224), bottom=(54, 62, 96), legs=(54, 62, 96), shoes=(236, 236, 240), scarf=None, clip=None, skirt=False, style="boy"),
    Look(hair=(196, 100, 58), top=(240, 140, 80), top_d=(212, 112, 58), sleeve=(234, 132, 72), bottom=(86, 90, 110), shoes=(52, 48, 60), scarf=None, clip=None, skirt=False, style="boy"),
    Look(hair=(90, 62, 44), top=(120, 200, 150), top_d=(90, 170, 122), sleeve=(112, 192, 142), bottom=(110, 100, 90), shoes=(60, 52, 48), scarf=None, clip=None, skirt=False, style="boy"),
    Look(hair=(30, 28, 36), top=(190, 90, 100), top_d=(160, 66, 78), sleeve=(182, 82, 92), bottom=(48, 50, 66), shoes=(30, 30, 40), scarf=None, clip=None, skirt=False, style="boy"),
]
OLDER_F = Look(hair=(196, 196, 208), top=(180, 150, 210), top_d=(150, 120, 184), sleeve=(172, 142, 204), bottom=(100, 90, 120), scarf=None, clip=None, style="bun")
OLDER_M = Look(hair=(170, 170, 182), top=(120, 130, 150), top_d=(94, 104, 126), sleeve=(112, 122, 142), bottom=(70, 72, 84), shoes=(40, 38, 46), scarf=None, clip=None, skirt=False, style="boy")

FEMALE = set("""mia emma olivia sophia ava isabella lily anna sara sarah mom mother mum sister aunt grandma girl woman lady
queen princess teacher mrs ms miss kate katie lucy emily hannah nora zoe ella chloe amy lisa maria laura jessica
jennifer nina eva ivy ruby grace alice rose sofia leila yuki mina saba sana neda""".split())
MALE = set("""tom jack liam noah oliver ben max sam dad father brother uncle grandpa boy man guy king prince teacher mr sir
john james david mike michael chris alex daniel leo ryan luke adam ali omar kevin steve bob joe""".split())
OLD = set("grandma grandpa granny grandfather grandmother old elder".split())

VOICES = {
    "F": ["en-US-JennyNeural", "en-GB-SoniaNeural", "en-AU-NatashaNeural", "en-US-MichelleNeural"],
    "M": ["en-US-GuyNeural", "en-GB-RyanNeural", "en-US-DavisNeural", "en-US-TonyNeural"],
}
PITCH = {"F": ["+0Hz", "+6Hz", "-4Hz", "+10Hz"], "M": ["+0Hz", "-4Hz", "-8Hz", "+4Hz"]}


def _h(name):
    return zlib.crc32(name.lower().encode())


def gender(name, hint=None):
    if hint in ("F", "M"):
        return hint
    w = name.lower().replace(".", "").split()
    for t in w:
        if t in FEMALE:
            return "F"
        if t in MALE:
            return "M"
    return "F" if _h(name) % 2 == 0 else "M"


def make(name, hint=None, look_hint=None, avoid=()):
    """Return (Look, gender, voice, pitch) for a character name. Same name -> same character every time."""
    g = gender(name, hint)
    h = _h(name)
    w = set(name.lower().replace(".", "").split())
    if w & OLD:
        look = OLDER_F if g == "F" else OLDER_M
    else:
        pool = GIRLS if g == "F" else BOYS
        k0 = (h >> 3) % len(pool)
        look = pool[k0]
        for j in range(len(pool)):                      # never give two characters the same outfit
            look = pool[(k0 + j) % len(pool)]
            if look.top not in avoid:
                break
    skin = SKINS[(h >> 7) % len(SKINS)] if (h >> 7) % 5 else SKINS[0]
    from dataclasses import replace
    look = replace(look, skin=skin)
    if look_hint:
        look = replace(look, **look_hint)
    voice = VOICES[g][(h >> 11) % len(VOICES[g])]
    pitch = PITCH[g][(h >> 13) % len(PITCH[g])]
    return look, g, voice, pitch
