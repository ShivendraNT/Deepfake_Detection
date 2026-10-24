"""Lip-sync: does the mouth open and close with the speech energy?

Mouth openness comes from the landmarks (inner-lip gap / mouth width). The audio envelope is
the log RMS of the call audio around each frame time. On a real talking face the two are
correlated at a small lag (the call adds tens of ms of A/V offset). A real video with a cloned
voice dubbed over it, or a talking-head generator, breaks or shifts that link.

  av_corr  best Pearson correlation over lags in [-0.4, 0.4] s
  av_lag   the |lag| (s) at which it is best

Only computed when there is speech in at least 25% of the window; otherwise NaN (abstain).
"""

from __future__ import annotations

import numpy as np

MAX_LAG_S = 0.4
MIN_SPEECH_FRACTION = 0.25


def envelope_at(audio: np.ndarray, sr: int, times: np.ndarray, half_s: float = 0.04) -> np.ndarray:
    """log-RMS of the first-differenced audio in a +-half_s window around each time (s)."""
    x = np.diff(np.asarray(audio, dtype=np.float64), prepend=0.0)
    csum = np.concatenate([[0.0], np.cumsum(x * x)])
    half = max(1, int(half_s * sr))
    out = np.full(len(times), np.nan)
    for i, t in enumerate(times):
        c = int(round(t * sr))
        a, b = max(0, c - half), min(len(x), c + half)
        if b - a >= half:
            out[i] = 0.5 * np.log((csum[b] - csum[a]) / (b - a) + 1e-10)
    return out


def speech_mask(env: np.ndarray) -> np.ndarray:
    """Frames whose envelope is >= 6 dB above the window's noise floor (10th percentile)."""
    finite = env[np.isfinite(env)]
    if finite.size == 0:
        return np.zeros(len(env), dtype=bool)
    floor = np.percentile(finite, 10)
    return np.isfinite(env) & (env > floor + np.log(10 ** (6 / 20)))


def lipsync_features(
    t: np.ndarray, mouth: np.ndarray, audio: np.ndarray | None, sr: int, fs: float = 15.0
) -> dict[str, float]:
    out = {"av_corr": float("nan"), "av_lag": float("nan"), "speech_frac": float("nan")}
    if audio is None or len(audio) < sr or len(t) < 8:
        return out
    t = np.asarray(t, dtype=float)
    mouth = np.asarray(mouth, dtype=float)
    ok = np.isfinite(mouth)
    if ok.sum() < 8:
        return out
    grid = np.arange(t[ok][0], t[ok][-1] + 1e-9, 1.0 / fs)
    m = np.interp(grid, t[ok], mouth[ok])
    env = envelope_at(audio, sr, grid)
    speech = speech_mask(env)
    out["speech_frac"] = float(speech.mean())
    if speech.mean() < MIN_SPEECH_FRACTION or not np.isfinite(env).all():
        return out
    max_lag = int(round(MAX_LAG_S * fs))
    best, best_lag = -1.0, 0
    n = len(m)
    for lag in range(-max_lag, max_lag + 1):
        # lag > 0: the audio comes `lag` frames after the mouth movement.
        x, y = (m[: n - lag], env[lag:]) if lag >= 0 else (m[-lag:], env[: n + lag])
        if len(x) < 8 or x.std() < 1e-9 or y.std() < 1e-9:
            continue
        c = float(np.corrcoef(x, y)[0, 1])
        if c > best:
            best, best_lag = c, lag
    out["av_corr"] = best
    out["av_lag"] = abs(best_lag) / fs
    return out
