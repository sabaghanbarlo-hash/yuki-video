#!/usr/bin/env python3
"""Parallel voice helper for the main Yuki system (generate.py itself is not changed).

    python generate_parallel.py scripts/x.txt --tts voicestudio --count         # prints "N sentences" and stops
    python generate_parallel.py scripts/x.txt --tts voicestudio --shard 2/20    # voices only the sentences n % 20 == 2, saves them, stops

Every other option is the same as in generate.py (--ref, --seed, --style, --format, --no-flow ...).  The voiced sentences are saved in
.work/<script name>/voice/ under exactly the names generate.py uses, so a normal generate.py run afterwards finds them all and only renders.
"""
import hashlib, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _pop(flag, has_value=True):
    if flag not in sys.argv:
        return None
    i = sys.argv.index(flag)
    if has_value:
        v = sys.argv[i + 1]
        del sys.argv[i:i + 2]
        return v
    del sys.argv[i]
    return True


SHARD = _pop("--shard")
COUNT = _pop("--count", has_value=False)
if not SHARD and not COUNT:
    sys.exit("use --count, or --shard i/N (a normal render is generate.py)")

from lab import pipeline as P


def _make(text, args, out_path, tmp):
    if getattr(args, "audio", None) or getattr(args, "flow", False):
        sys.exit("parallel voice works with one recording per sentence (--no-flow) and no --audio")
    plan = P.build_plan(text, seed=getattr(args, "seed", 0), force_style=getattr(args, "style", None), max_scenes=getattr(args, "max_scenes", None))
    sents = P.body_sentences(plan)
    print(f"{len(sents)} sentences", flush=True)
    if COUNT:
        return 0, plan
    i, n_sh = (int(x) for x in SHARD.split("/"))
    tmp = Path(tmp)
    (tmp / "voice").mkdir(parents=True, exist_ok=True)
    mine = [n for n in range(len(sents)) if n % n_sh == i]
    for k, n in enumerate(mine):
        s = sents[n][2]
        key = hashlib.md5(f"v4|{args.tts}|{getattr(args, 'voice', '')}|{getattr(args, 'energy', 1)}|{getattr(args, 'speed', 1)}|{s['mood']}|{s['spoken']}".encode()).hexdigest()[:16]
        f = tmp / "voice" / f"{key}.npy"
        if f.exists():
            continue
        print(f"  shard {i + 1}/{n_sh}: voicing {k + 1}/{len(mine)} (sentence {n + 1}/{len(sents)})", flush=True)
        a = np.asarray(P.A.synth(s["spoken"], args, n, tmp, emotion=s["mood"]), np.float32)
        np.save(f, a)
        P.mem_guard(f" after sentence {n + 1}/{len(sents)}")
    print(f"shard {i + 1}/{n_sh} voiced ({len(mine)} sentences)", flush=True)
    return 0, plan


P.make = _make
import generate
generate.main()
