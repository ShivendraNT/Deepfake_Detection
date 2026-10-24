"""Remote photoplethysmography (rPPG): the faint colour change of skin with each heartbeat.

Plane-Orthogonal-to-Skin (POS, Wang et al. 2017) per skin patch, then three window features:

  snr_db     how much of the pulse-band power sits at one heart rate (+ its harmonic)
  coherence  do forehead and both cheeks pulse together (FakeCatcher-style spatial check)
  hr_spread  do the patches agree on the heart rate (Hz)

Numpy only. Pulse band 0.7-3.5 Hz (42-210 bpm). Needs >= 8 Hz sampling and >= 4 s.
"""

from __future__ import annotations

import numpy as np

BAND = (0.7, 3.5)
POS_SECONDS = 1.6


def resample_uniform(t: np.ndarray, x: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Linear resampling of x(t) (rows = time) onto a uniform grid at fs; NaN rows dropped."""
    ok = np.all(np.isfinite(x.reshape(len(x), -1)), axis=1)
    t, x = t[ok], x[ok]
    if len(t) < 2:
        return np.empty(0), np.empty((0,) + x.shape[1:])
    grid = np.arange(t[0], t[-1] + 1e-9, 1.0 / fs)
    cols = x.reshape(len(x), -1)
    out = np.stack([np.interp(grid, t, cols[:, j]) for j in range(cols.shape[1])], axis=1)
    return grid, out.reshape((len(grid),) + x.shape[1:])


def pos(rgb: np.ndarray, fs: float) -> np.ndarray:
    """POS pulse signal from an (N, 3) RGB trace sampled at fs."""
    n = len(rgb)
    win = max(2, int(round(POS_SECONDS * fs)))
    h = np.zeros(n)
    if n < win:
        return h
    proj = np.array([[0.0, 1.0, -1.0], [-2.0, 1.0, 1.0]])
    for start in range(n - win + 1):
        c = rgb[start : start + win].T
        mean = c.mean(axis=1, keepdims=True)
        if np.any(mean <= 1e-6):
            continue
        s = proj @ (c / mean)
        std1 = s[1].std()
        alpha = s[0].std() / std1 if std1 > 1e-9 else 0.0
        p = s[0] + alpha * s[1]
        h[start : start + win] += p - p.mean()
    return h


def bandpass(x: np.ndarray, fs: float, band: tuple[float, float] = BAND) -> np.ndarray:
    """Zero-phase FFT band-pass (rectangular in frequency, after linear detrending)."""
    if len(x) < 4:
        return np.zeros_like(x)
    t = np.arange(len(x))
    x = x - np.polyval(np.polyfit(t, x, 1), t)
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / fs)
    spec[(f < band[0]) | (f > band[1])] = 0
    return np.fft.irfft(spec, n=len(x))


def spectrum(x: np.ndarray, fs: float, nfft: int = 2048) -> tuple[np.ndarray, np.ndarray]:
    w = np.hanning(len(x))
    p = np.abs(np.fft.rfft(x * w, n=max(nfft, len(x)))) ** 2
    f = np.fft.rfftfreq(max(nfft, len(x)), 1.0 / fs)
    return f, p


def snr_db(x: np.ndarray, fs: float) -> tuple[float, float]:
    """(SNR in dB, dominant frequency in Hz) of a pulse signal (de Haan & Jeanne 2013).

    The signal band around the peak scales with the window: a Hann window of T seconds
    spreads a pure tone over about +-1.2/T Hz, so a fixed +-0.1 Hz (meant for long windows)
    would call a perfect 6 s pulse "noisy"."""
    f, p = spectrum(x, fs)
    band = (f >= BAND[0]) & (f <= BAND[1])
    if not band.any() or p[band].sum() <= 0:
        return float("nan"), float("nan")
    f0 = float(f[band][np.argmax(p[band])])
    hw = max(0.1, 1.2 / (len(x) / fs))
    sig = band & ((np.abs(f - f0) <= hw) | (np.abs(f - 2 * f0) <= 2 * hw))
    noise = band & ~sig
    ps, pn = p[sig].sum(), p[noise].sum()
    if pn <= 0:
        return 30.0, f0
    return float(10 * np.log10(max(ps, 1e-12) / pn)), f0


def max_xcorr(a: np.ndarray, b: np.ndarray, max_lag: int) -> float:
    """Largest Pearson correlation of a and b over lags in [-max_lag, max_lag]."""
    best = -1.0
    n = len(a)
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            x, y = a[lag:], b[: n - lag]
        else:
            x, y = a[: n + lag], b[-lag:]
        if len(x) < 8 or x.std() < 1e-9 or y.std() < 1e-9:
            continue
        best = max(best, float(np.corrcoef(x, y)[0, 1]))
    return best


def pulse_features(
    t: np.ndarray, traces: dict[str, np.ndarray], fs: float = 15.0
) -> dict[str, float]:
    """Window features from per-patch RGB traces {patch: (N, 3)} sampled at times t."""
    nan = {"pulse_snr": float("nan"), "pulse_coherence": float("nan"),
           "pulse_hr_spread": float("nan")}  # fmt: skip
    names = [n for n in ("forehead", "cheek_l", "cheek_r") if n in traces]
    if len(names) < 2 or len(t) < 4:
        return nan
    stacked = np.stack([traces[n] for n in names], axis=1)  # (N, P, 3)
    grid, rs = resample_uniform(np.asarray(t, dtype=float), stacked, fs)
    if len(grid) < int(4 * fs):
        return nan
    pulses = [bandpass(pos(rs[:, i, :], fs), fs) for i in range(len(names))]
    snrs, f0s = zip(*(snr_db(p, fs) for p in pulses), strict=True)
    lag = int(round(0.2 * fs))
    pairs = [(i, j) for i in range(len(pulses)) for j in range(i + 1, len(pulses))]
    coh = [max_xcorr(pulses[i], pulses[j], lag) for i, j in pairs]
    ok_snr = [v for v in snrs if np.isfinite(v)]
    ok_f0 = [v for v in f0s if np.isfinite(v)]
    return {
        "pulse_snr": float(np.mean(ok_snr)) if ok_snr else float("nan"),
        "pulse_coherence": float(np.mean(coh)),
        "pulse_hr_spread": float(np.std(ok_f0)) if len(ok_f0) >= 2 else float("nan"),
    }
