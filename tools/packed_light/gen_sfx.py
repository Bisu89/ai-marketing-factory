"""Synthesize the Packed Light test-cut SFX and pad music (numpy + stdlib only) into remotion/public/pk-ep01/."""
import os, wave
from pathlib import Path
import numpy as np

OUT = str(Path(__file__).resolve().parents[2] / "remotion" / "public" / "pk-ep01")
SR = 44100
rng = np.random.default_rng(7)


def t_(d):
    return np.arange(int(SR * d)) / SR


def noise(d):
    return rng.standard_normal(int(SR * d))


def band(x, lo, hi):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1e-6)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, n)


def env(n, a=0.005, d=0.1, curve=3.0):
    e = np.ones(n)
    na = max(1, int(SR * a))
    e[:na] = np.linspace(0, 1, na)
    nd = int(SR * d)
    if nd > 0:
        k = np.arange(n - na)
        e[na:] = np.exp(-curve * k / max(1, nd))
    return e


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1
    return x / m * peak


def save(name, x, peak=0.9):
    x = norm(x, peak)
    path = os.path.join(OUT, "sfx" if not name.startswith("music") else "", name + ".wav")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    print(name, round(len(x) / SR, 2), "s")


def place(base, clip, at):
    i = int(SR * at)
    n = min(len(clip), len(base) - i)
    if n > 0:
        base[i : i + n] += clip[:n]


def burst(d, lo, hi, a=0.003, dec=0.05, curve=4):
    n = int(SR * d)
    return band(noise(d), lo, hi) * env(n, a, dec, curve)


def loopable(x, xf=1.5):
    k = int(SR * xf)
    y = x.copy()
    ramp = np.linspace(0, 1, k)
    y[:k] = x[:k] * ramp + x[-k:] * (1 - ramp)
    return y[:-k]


# ---- forest ambience (loop) ----
d = 14
tt = t_(d)
wind = band(noise(d), 0, 450) * (0.55 + 0.35 * np.sin(2 * np.pi * 0.13 * tt) + 0.15 * np.sin(2 * np.pi * 0.31 * tt + 1))
rustle = band(noise(d), 2500, 6500) * (0.05 + 0.04 * np.sin(2 * np.pi * 0.4 * tt + 2)) ** 1
amb = wind * 1.0 + rustle * 2.2
save("amb_forest", loopable(amb), 0.7)

# ---- birds ----
def chirp(f0, f1, d, amp=1.0):
    tt = t_(d)
    f = np.linspace(f0, f1, len(tt))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env(len(tt), 0.01, d * 0.6, 3) * amp

b1 = np.zeros(int(SR * 1.2))
for i, (a, b) in enumerate([(3200, 4600), (3400, 4900), (3600, 5100)]):
    place(b1, chirp(a, b, 0.11), 0.05 + i * 0.2)
save("bird1", b1, 0.35)
b2 = np.zeros(int(SR * 1.4))
for i, (a, b) in enumerate([(4800, 3600), (4400, 3300), (4000, 2900), (3800, 4600)]):
    place(b2, chirp(a, b, 0.14), 0.05 + i * 0.22)
save("bird2", b2, 0.3)

# ---- gravel steps ----
g = np.zeros(int(SR * 1.2))
for i in range(3):
    place(g, burst(0.09, 900, 6000, 0.002, 0.04, 4), 0.1 + i * 0.4 + rng.uniform(-0.03, 0.03))
save("steps_gravel", g, 0.6)

# ---- leaf steps (6 steps) ----
l = np.zeros(int(SR * 3.2))
for i in range(6):
    place(l, burst(0.14, 300, 3500, 0.004, 0.07, 3.5) * rng.uniform(0.7, 1.0), 0.1 + i * 0.5 + rng.uniform(-0.04, 0.04))
save("steps_leaves", l, 0.6)

# ---- rope / tarp ----
r = np.zeros(int(SR * 1.2))
for i in range(3):
    place(r, band(noise(0.18), 700, 3000) * env(int(SR * 0.18), 0.04, 0.1, 2) * 0.8, 0.05 + i * 0.3)
save("rope", r, 0.5)
tf = np.zeros(int(SR * 1.6))
for i, a in enumerate([1.0, 0.6, 0.35]):
    place(tf, band(noise(0.35), 80, 900) * env(int(SR * 0.35), 0.01, 0.2, 3) * a, 0.05 + i * 0.4)
save("tarp_flap", tf, 0.55)

# ---- water slosh + metal clink ----
s = np.zeros(int(SR * 1.4))
for i in range(3):
    n = int(SR * 0.4)
    wave_env = np.sin(np.linspace(0, np.pi, n)) ** 2
    place(s, band(noise(0.4), 200, 1400) * wave_env * (1 - i * 0.25), 0.05 + i * 0.35)
save("slosh", s, 0.55)

def ring(freqs, d, dec):
    tt = t_(d)
    x = sum(np.sin(2 * np.pi * f * tt) * a for f, a in freqs)
    return x * env(len(tt), 0.001, dec, 4)

save("clink", ring([(2400, 1), (3700, 0.6), (5300, 0.3)], 0.5, 0.18), 0.5)

# ---- tin slide + tap ----
ts = band(noise(0.7), 1500, 6000) * np.sin(np.linspace(0, np.pi, int(SR * 0.7))) ** 1.5 * 0.5
tap = ring([(1800, 1), (2900, 0.4)], 0.2, 0.06)
tt_ = np.zeros(int(SR * 1.2))
place(tt_, ts, 0.05)
place(tt_, tap, 0.82)
save("tin_slide", tt_, 0.5)

# ---- twig snap, branch clatter ----
sn = np.zeros(int(SR * 0.6))
place(sn, burst(0.03, 1500, 9000, 0.0005, 0.012, 3), 0.02)
place(sn, ring([(1400, 1), (2100, 0.4)], 0.15, 0.03), 0.02)
place(sn, burst(0.1, 500, 4000, 0.002, 0.04, 4) * 0.3, 0.06)
save("twig_snap", sn, 0.7)
bc = np.zeros(int(SR * 1.0))
for i in range(6):
    f = rng.uniform(300, 650)
    at = 0.02 + i * 0.1 + rng.uniform(-0.01, 0.02)
    place(bc, ring([(f, 1), (f * 2.3, 0.3)], 0.15, 0.05) * rng.uniform(0.5, 1), at)
    place(bc, burst(0.05, 600, 4000, 0.001, 0.02, 3) * 0.3, at)
save("branch_clatter", bc, 0.6)

# ---- match strike + flare ----
m = np.zeros(int(SR * 1.6))
scr = band(noise(0.3), 1800, 8000) * np.linspace(0.2, 1, int(SR * 0.3)) ** 2
place(m, scr * 0.6, 0.0)
flare = band(noise(0.7), 700, 7000) * env(int(SR * 0.7), 0.01, 0.35, 3)
place(m, flare, 0.3)
place(m, band(noise(0.5), 100, 600) * env(int(SR * 0.5), 0.02, 0.25, 3) * 0.4, 0.3)
save("match_strike", m, 0.6)

# ---- smoke hiss ----
hs = band(noise(3.0), 3000, 10000) * np.sin(np.linspace(0, np.pi, int(SR * 3.0))) ** 1.2
save("smoke_hiss", hs, 0.3)

# ---- wood snap (splintering) ----
w = np.zeros(int(SR * 0.9))
place(w, burst(0.02, 1200, 9000, 0.0003, 0.01, 3), 0.01)
place(w, ring([(130, 1), (260, 0.4)], 0.3, 0.1) * 0.7, 0.012)
for k, at in enumerate([0.06, 0.1, 0.15, 0.21]):
    place(w, burst(0.04, 1500, 8000, 0.0005, 0.015, 3) * (0.5 - 0.1 * k), at)
place(w, burst(0.4, 400, 3000, 0.01, 0.18, 3) * 0.12, 0.12)
save("wood_snap", w, 0.75)

# ---- warm pad music (60 s) ----
D = 62
mt = t_(D)
chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]
seg = 8.0
pad = np.zeros(len(mt))
for i in range(int(np.ceil(D / seg))):
    t0 = i * seg
    ch = chords[i % 4]
    idx = (mt >= t0 - 1.5) & (mt < t0 + seg + 1.5)
    local = mt[idx] - t0
    a = np.clip((local + 1.5) / 2.0, 0, 1) * np.clip((seg + 1.5 - local) / 2.0, 0, 1)
    voice = np.zeros(local.shape)
    for f in ch:
        voice += np.sin(2 * np.pi * f * mt[idx] + 0.3 * np.sin(2 * np.pi * 0.2 * mt[idx])) * 0.5
        voice += np.sin(2 * np.pi * f * 2.003 * mt[idx]) * 0.12
    pad[idx] += voice * a
pad *= np.clip(mt / 3, 0, 1) * np.clip((D - mt) / 4, 0, 1)
save("music", pad, 0.5)
