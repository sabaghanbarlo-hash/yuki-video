"""Small, dependency-light voice analysis (numpy only): pitch (f0) and a timbre fingerprint."""
import subprocess, tempfile, wave
import numpy as np

SR = 16000


def load(path):
    tmp = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-ar", str(SR), "-ac", "1", tmp], check=True)
    with wave.open(tmp) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return x


def f0_track(x, fmin=70, fmax=400, frame=0.04, hop=0.01):
    n, h = int(frame * SR), int(hop * SR)
    lo, hi = int(SR / fmax), int(SR / fmin)
    out = []
    gate = 0.15 * np.sqrt(np.mean(x ** 2)) + 1e-4
    for i in range(0, len(x) - n - hi, h):
        seg = x[i:i + n + hi]
        if np.sqrt(np.mean(seg[:n] ** 2)) < gate:
            continue
        a = seg[:n] - seg[:n].mean()
        best, bl = 0.0, 0
        d = np.array([np.dot(a, seg[l:l + n] - seg[l:l + n].mean()) / (np.linalg.norm(a) * np.linalg.norm(seg[l:l + n] - seg[l:l + n].mean()) + 1e-9) for l in range(lo, hi)])
        l = int(np.argmax(d))
        if d[l] > 0.62:
            out.append(SR / (lo + l))
    return np.array(out)


def mel_fingerprint(x, n_mels=26, n_fft=512, hop=160):
    win = np.hanning(n_fft)
    frames = [x[i:i + n_fft] * win for i in range(0, len(x) - n_fft, hop)]
    P = np.abs(np.fft.rfft(np.array(frames), axis=1)) ** 2
    e = P.sum(1)
    P = P[e > np.percentile(e, 40)]                        # voiced / loud frames only
    f = np.fft.rfftfreq(n_fft, 1 / SR)
    mel = lambda hz: 2595 * np.log10(1 + hz / 700)
    pts = np.linspace(mel(60), mel(7600), n_mels + 2)
    hz = 700 * (10 ** (pts / 2595) - 1)
    fb = np.zeros((n_mels, len(f)))
    for m in range(n_mels):
        a, b, c = hz[m], hz[m + 1], hz[m + 2]
        fb[m] = np.clip(np.minimum((f - a) / (b - a), (c - f) / (c - b)), 0, None)
    L = np.log(P @ fb.T + 1e-9).mean(0)
    return L - L.mean()                                      # ignore loudness


def features(x):
    f = f0_track(x)
    if len(f) < 20:
        return None
    return dict(f0_med=float(np.median(f)), f0_lo=float(np.percentile(f, 15)), f0_hi=float(np.percentile(f, 85)),
                mel=mel_fingerprint(x))


def distance(ref, cand):
    pitch = abs(np.log(cand["f0_med"] / ref["f0_med"]))        # in octaves-ish
    rng = abs(np.log((cand["f0_hi"] / cand["f0_lo"]) / (ref["f0_hi"] / ref["f0_lo"])))
    timbre = float(np.sqrt(np.mean((cand["mel"] - ref["mel"]) ** 2)))
    return 3.0 * pitch + 0.8 * rng + 0.5 * timbre
