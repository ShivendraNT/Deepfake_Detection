"""Pure signal-processing functions for audio forensics (NumPy / SciPy only, unit-tested)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------------------------
# Spectrogram and bandwidth
# ---------------------------------------------------------------------------------------------


def frames(x: np.ndarray, size: int, hop: int) -> np.ndarray:
    if len(x) < size:
        x = np.pad(x, (0, size - len(x)))
    n = 1 + (len(x) - size) // hop
    idx = np.arange(size)[None, :] + hop * np.arange(n)[:, None]
    return x[idx]


def stft_power(
    x: np.ndarray, sr: int, n_fft: int, max_frames: int = 3000
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Power spectrogram [freq, time], frequencies (Hz) and frame centre times (s)."""
    hop = max(n_fft // 4, int(np.ceil(max(1, len(x) - n_fft) / max_frames)))
    f = frames(x.astype(np.float32), n_fft, hop) * np.hanning(n_fft).astype(np.float32)
    p = (np.abs(np.fft.rfft(f, axis=1)) ** 2).T.astype(np.float32)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    times = (np.arange(p.shape[1]) * hop + n_fft / 2) / sr
    return p, freqs, times


@dataclass
class Bandwidth:
    cutoff_hz: float
    nyquist_hz: float
    sharp: bool
    drop_db: float
    ltas_db: list[float] = field(default_factory=list)
    ltas_hz: list[float] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.cutoff_hz / self.nyquist_hz if self.nyquist_hz else 1.0


def effective_bandwidth(x: np.ndarray, sr: int) -> Bandwidth:
    """Highest frequency that still carries signal in the long-term average spectrum of the
    active frames, and whether the spectrum ends in a brick wall (codec / resampler)."""
    n_fft = 4096 if sr >= 32000 else 2048 if sr >= 16000 else 1024
    p, freqs, _ = stft_power(x, sr, n_fft, max_frames=1500)
    e = 10 * np.log10(p.sum(axis=0) + 1e-20)
    active = e > (e.max() - 45)
    if active.sum() < 3:
        active = np.ones_like(e, dtype=bool)
    ltas = 10 * np.log10(p[:, active].mean(axis=1) + 1e-20)
    k = 5
    sm = np.convolve(ltas, np.ones(k) / k, mode="same")
    band = (freqs >= 200) & (freqs <= min(3000, sr / 2 - 1))
    ref = float(np.percentile(sm[band], 90)) if band.any() else float(sm.max())
    floor = ref - 75.0
    nyq = sr / 2.0
    above = sm > floor
    cut_bin = len(freqs) - 1
    run = 6
    for i in range(len(freqs) - run, 0, -1):
        if above[i : i + run].all():
            cut_bin = i + run - 1
            break
    cutoff = float(freqs[cut_bin])
    hz_per_bin = freqs[1] - freqs[0]
    w = max(3, int(400 / hz_per_bin))
    below = sm[cut_bin + 2 : cut_bin + 2 + w]
    before = sm[max(0, cut_bin - w) : cut_bin]
    drop = float(before.mean() - below.mean()) if len(below) and len(before) else 0.0
    sharp = cutoff < 0.96 * nyq and drop > 25.0
    step = max(1, len(freqs) // 256)
    return Bandwidth(cutoff, nyq, sharp, drop,
                     [round(float(v), 1) for v in sm[::step]],
                     [round(float(v), 1) for v in freqs[::step]])  # fmt: skip


def explain_cutoff(cutoff_hz: float, sr: int) -> str:
    c = cutoff_hz
    if c < 4300:
        return "narrowband telephony (8 kHz sampling: GSM / AMR-NB / landline)"
    if c < 8300:
        return "wideband speech (16 kHz sampling: VoIP, WhatsApp/Opus voice, many TTS engines)"
    if c < 11300:
        return "22.05 kHz audio (common neural-TTS and low-rate MP3 output)"
    if c < 12300:
        return "24 kHz audio (common neural-TTS output) or Opus super-wideband"
    if c < 16800:
        return "lossy compression low-pass (MP3/AAC around 128 kbps cut near 16 kHz)"
    if c < 19800:
        return "lossy compression low-pass (high-bitrate MP3/AAC)"
    return "full-band audio"


# ---------------------------------------------------------------------------------------------
# Electrical Network Frequency (India: 50 Hz)
# ---------------------------------------------------------------------------------------------


@dataclass
class EnfResult:
    present: bool
    harmonic: int
    snr_db: float
    times: list[float]
    freqs: list[float]  # ENF estimate per frame (Hz, at the fundamental)
    snrs: list[float]
    jumps: list[dict[str, float]]


def enf_trace(x16k: np.ndarray, nominal: float = 50.0, win_s: float = 4.0,
              hop_s: float = 1.0) -> EnfResult:  # fmt: skip
    """Track the mains hum (and its harmonics) with zero-padded STFT peak picking and
    quadratic interpolation; flag abrupt jumps in the trace (possible edit points)."""
    from scipy.signal import butter, resample_poly, sosfiltfilt

    fs = 1000
    x = resample_poly(x16k.astype(np.float64), 1, 16)
    best: EnfResult | None = None
    for h in (1, 2, 3):
        lo, hi = h * (nominal - 2.0), h * (nominal + 2.0)
        if hi >= fs / 2:
            continue
        sos = butter(4, [lo, hi], btype="bandpass", fs=fs, output="sos")
        y = sosfiltfilt(sos, x)
        size, hop = int(win_s * fs), int(hop_s * fs)
        if len(y) < size + hop:
            break
        fr = frames(y, size, hop) * np.hanning(size)
        nfft = 1 << 15
        spec = np.abs(np.fft.rfft(fr, n=nfft, axis=1)) ** 2
        freqs = np.fft.rfftfreq(nfft, 1 / fs)
        sb = (freqs >= h * (nominal - 0.5)) & (freqs <= h * (nominal + 0.5))
        wide = (freqs >= lo) & (freqs <= hi)
        idx_sb = np.where(sb)[0]
        est, snrs = [], []
        for row in spec:
            k = idx_sb[np.argmax(row[idx_sb])]
            a, b, c = np.log(row[k - 1] + 1e-30), np.log(row[k] + 1e-30), np.log(row[k + 1] + 1e-30)
            den = a - 2 * b + c
            off = 0.5 * (a - c) / den if den != 0 else 0.0
            f = (k + float(np.clip(off, -0.5, 0.5))) * (freqs[1] - freqs[0])
            near = np.abs(freqs - f) < 0.6 * h
            noise = np.median(row[wide & ~near]) + 1e-30
            snrs.append(10 * np.log10(row[k] / noise))
            est.append(f / h)
        times = list(np.arange(len(est)) * hop_s + win_s / 2)
        med_snr = float(np.median(snrs)) if snrs else 0.0
        res = EnfResult(False, h, med_snr, times, est, [float(s) for s in snrs], [])
        if best is None or res.snr_db > best.snr_db:
            best = res
    if best is None:
        return EnfResult(False, 1, 0.0, [], [], [], [])
    f = np.array(best.freqs)
    d = np.abs(np.diff(f)) if len(f) > 1 else np.zeros(0)
    smooth = float(np.median(d)) if len(d) else 1.0
    best.present = best.snr_db > 10.0 and smooth < 0.01 and len(f) >= 4
    if best.present and len(d):
        mad = float(np.median(np.abs(d - np.median(d)))) * 1.4826 + 1e-4
        thr = max(0.012, 8 * mad)
        for i in np.where(d > thr)[0]:
            left = f[max(0, i - 2) : i + 1]
            right = f[i + 1 : i + 4]
            if len(right) and abs(float(np.median(right)) - float(np.median(left))) > thr * 0.8:
                best.jumps.append({"t": float(best.times[i] + best.times[i + 1]) / 2.0,
                                   "delta_hz": float(f[i + 1] - f[i])})  # fmt: skip
    return best


# ---------------------------------------------------------------------------------------------
# Splice / edit cues
# ---------------------------------------------------------------------------------------------


@dataclass
class SpliceCue:
    t: float
    kind: str  # digital_silence | noise_floor_jump | discontinuity
    detail: str
    weight: float


def digital_silence(x: np.ndarray, sr: int, min_ms: float = 12.0) -> list[SpliceCue]:
    """Runs of exact digital zero inside a recording that otherwise has background noise."""
    zero = np.abs(x) < 1e-7
    if zero.mean() > 0.5:
        return []
    cues: list[SpliceCue] = []
    edges = np.diff(np.concatenate([[0], zero.astype(np.int8), [0]]))
    starts, ends = np.where(edges == 1)[0], np.where(edges == -1)[0]
    n = len(x)
    for s, e in zip(starts, ends, strict=True):
        dur = (e - s) / sr * 1000
        if dur >= min_ms and s > sr * 0.05 and e < n - sr * 0.05:
            cues.append(SpliceCue(s / sr, "digital_silence",
                                  f"{dur:.0f} ms of exact digital silence mid-recording", 2.0))  # fmt: skip
    return cues[:20]


def noise_floor_jumps(
    x: np.ndarray, sr: int, win_s: float = 2.0, hop_s: float = 0.5
) -> tuple[list[SpliceCue], list[float], list[float]]:
    """Background level per window = 10th percentile of its 20 ms frame energies (the pauses,
    or the whole window when there is no speech). Two neighbouring windows whose levels differ
    by more than 6 dB, with steady levels on each side, suggest audio recorded under different
    conditions was joined there."""
    fl = int(0.02 * sr)
    hop = fl // 2
    if len(x) < sr * 3:
        return [], [], []
    fr = frames(x, fl, hop)
    e = 10 * np.log10((fr.astype(np.float64) ** 2).mean(axis=1) + 1e-12)
    t = (np.arange(len(e)) * hop + fl / 2) / sr
    w = max(4, int(win_s / (hop / sr)))
    step = max(1, int(hop_s / (hop / sr)))
    levels, lt = [], []
    for i in range(0, len(e) - w + 1, step):
        levels.append(float(np.percentile(e[i : i + w], 10)))
        lt.append(float(t[i + w // 2]))
    cues: list[SpliceCue] = []
    lv = np.array(levels)
    k = max(1, int(round(win_s / hop_s)))  # windows that do not overlap
    if len(lv) > 2 * k + 1:
        d = np.full(len(lv), 0.0)
        for i in range(k, len(lv) - k):
            d[i] = float(np.median(lv[i : i + k]) - np.median(lv[max(0, i - k) : i]))
        cand = [i for i in range(k, len(lv) - k) if abs(d[i]) > 6.0
                and abs(d[i]) >= np.abs(d[max(0, i - k) : i + k + 1]).max() - 1e-9]  # fmt: skip
        for i in cand:
            left = lv[max(0, i - 2 * k) : max(1, i - k // 2)]
            right = lv[min(len(lv) - 1, i + k // 2) : i + 2 * k]
            if len(left) and len(right) and np.std(left) < 3.0 and np.std(right) < 3.0:
                ts = (lt[i - 1] + lt[i]) / 2 if i > 0 else lt[i]
                cues.append(SpliceCue(ts - win_s / 2 + hop_s / 2, "noise_floor_jump",
                                      f"background level changes by {d[i]:+.1f} dB",
                                      1.5 if abs(d[i]) > 10 else 1.0))  # fmt: skip
    return cues, lt, [round(v, 2) for v in levels]


def discontinuities(x: np.ndarray, sr: int, max_cues: int = 10) -> list[SpliceCue]:
    """Isolated sample-to-sample jumps far above the local norm (hard cuts without fades)."""
    if len(x) < sr:
        return []
    d = np.abs(np.diff(x.astype(np.float64)))
    blk = int(0.05 * sr)
    nb = len(d) // blk
    if nb < 4:
        return []
    db = d[: nb * blk].reshape(nb, blk)
    local = np.median(db, axis=1) + 1e-6
    peak = db.max(axis=1)
    ratio = peak / local
    cand = np.where(ratio > 60)[0]
    cues = []
    for b in cand[:max_cues]:
        i = b * blk + int(np.argmax(db[b]))
        lvl = float(np.abs(x[max(0, i - blk) : i + blk]).mean()) + 1e-9
        if d[i] > 0.25 and d[i] / lvl > 8:
            cues.append(SpliceCue(i / sr, "discontinuity",
                                  f"waveform jumps by {d[i]:.2f} between two samples", 0.7))  # fmt: skip
    return cues


def merge_cues(cues: list[SpliceCue], within_s: float = 0.4) -> list[dict[str, Any]]:
    cues = sorted(cues, key=lambda c: c.t)
    out: list[dict[str, Any]] = []
    for c in cues:
        if out and c.t - out[-1]["t"] <= within_s:
            g = out[-1]
            g["kinds"].append(c.kind)
            g["details"].append(c.detail)
            g["weight"] += c.weight
        else:
            out.append({"t": round(c.t, 2), "kinds": [c.kind], "details": [c.detail],
                        "weight": c.weight})  # fmt: skip
    return out


def normalise_loudness(x: np.ndarray, target_peak: float = 0.5) -> np.ndarray:
    """Scale so the 99.9th-percentile absolute sample is target_peak (VAD is gain-sensitive;
    the deepfake models normalise internally, so scoring is unaffected)."""
    if len(x) == 0:
        return x
    p = float(np.percentile(np.abs(x), 99.9))
    if p < 1e-5:
        return x
    return (x * (target_peak / p)).astype(np.float32)


def speech_segments(x16k: np.ndarray) -> list[tuple[float, float]]:
    """Speech (start_s, end_s) from Silero VAD (shipped with faster-whisper) on loudness-
    normalised audio; an adaptive energy detector when it is not installed."""
    y = normalise_loudness(x16k)
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        ts = get_speech_timestamps(y, VadOptions(threshold=0.5, min_silence_duration_ms=300,
                                                 speech_pad_ms=100))  # fmt: skip
        return [(t["start"] / 16000, t["end"] / 16000) for t in ts]
    except Exception:  # noqa: BLE001 - no faster-whisper: energy fallback
        fl = 480
        n = len(y) // fl
        if n == 0:
            return []
        rms = np.sqrt((y[: n * fl].reshape(n, fl) ** 2).mean(axis=1))
        thr = max(0.02, float(np.percentile(rms, 20)) * 4)
        on = rms > thr
        out, start = [], None
        for i, v in enumerate(on):
            if v and start is None:
                start = i
            if not v and start is not None:
                out.append((start * 0.03, i * 0.03))
                start = None
        if start is not None:
            out.append((start * 0.03, n * 0.03))
        return out


def speech_seconds(x16k: np.ndarray) -> float:
    return float(sum(e - s for s, e in speech_segments(x16k)))
