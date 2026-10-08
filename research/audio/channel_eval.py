"""Audio channel evaluation + threshold fitting for the voice detector. TASK T18.

Channels (ffmpeg): clean; Opus 16 kbps; AMR-NB 12.2 kbps @ 8 kHz; G.711 mu-law @ 8 kHz.
Splits: speaker-disjoint 50/50 calibration / test. Metrics: EER, FPR/FNR at fixed tau,
bootstrap CIs resampled BY SPEAKER. tau_hi = 1% FPR, tau_lo = 5% FPR on Meet-captured
bonafide calibration windows. NEVER commit audio (team voices are personal data).
"""

from __future__ import annotations

import random  # provenance: seeded-resampling-ok (speaker split, bootstrap CI)
import subprocess
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

ChannelName = Literal["clean", "opus16k", "amrnb", "g711u"]

FFMPEG_ARGS: dict[ChannelName, list[str]] = {
    "clean": [],
    "opus16k": ["-c:a", "libopus", "-b:a", "16k"],
    "amrnb": ["-ar", "8000", "-ac", "1", "-c:a", "libopencore_amrnb", "-b:a", "12.2k"],
    "g711u": ["-ar", "8000", "-ac", "1", "-c:a", "pcm_mulaw"],
}


@dataclass(frozen=True)
class Item:
    path: Path
    speaker: str
    label: int  # 1 = spoof/fake, 0 = bonafide


def reencode(src: Path, channel: ChannelName, out_dir: Path) -> Path:
    """Round-trip through the codec and back to 16 kHz mono WAV (subprocess ffmpeg)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{src.stem}_{channel}.wav"

    if channel == "clean":
        cmd = ["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(out_path)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_path

    codec_args = FFMPEG_ARGS[channel]
    ext = ".opus" if channel == "opus16k" else ".wav"
    intermediate = out_dir / f"{src.stem}_{channel}_temp{ext}"

    try:
        encode_cmd = ["ffmpeg", "-y", "-i", str(src)] + codec_args + [str(intermediate)]
        subprocess.run(encode_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        decode_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(intermediate),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(out_path),
        ]
        subprocess.run(decode_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        if intermediate.exists():
            intermediate.unlink()

    return out_path


def speaker_disjoint_split(items: Sequence[Item], seed: int = 0) -> tuple[list[Item], list[Item]]:
    """Shuffle SPEAKERS (not items) with random.Random(seed); first half of speakers ->
    calibration, rest -> test. No speaker may appear in both."""
    speakers = sorted(list({item.speaker for item in items}))
    rng = random.Random(seed)
    rng.shuffle(speakers)
    n_cal = len(speakers) // 2
    cal_speakers = set(speakers[:n_cal])

    cal_items = [it for it in items if it.speaker in cal_speakers]
    test_items = [it for it in items if it.speaker not in cal_speakers]
    return cal_items, test_items


def eer(labels: Sequence[int], scores: Sequence[float]) -> tuple[float, float]:
    """Equal error rate and the threshold where FPR == FNR (linear interpolation on the ROC)."""
    if len(labels) != len(scores):
        raise ValueError("labels and scores must have same length")
    if not labels:
        return 0.0, 0.0

    n_bonafide = sum(1 for y in labels if y == 0)
    n_spoof = sum(1 for y in labels if y == 1)
    if n_bonafide == 0 or n_spoof == 0:
        return 0.0, 0.0

    sorted_pairs = sorted(zip(scores, labels, strict=True), key=lambda x: x[0])
    unique_scores = sorted(list(set(scores)))
    thresholds = [unique_scores[0] - 1e-6] + unique_scores + [unique_scores[-1] + 1e-6]

    points: list[tuple[float, float, float]] = []
    for t in thresholds:
        fp = sum(1 for s, y in sorted_pairs if s >= t and y == 0)
        fn = sum(1 for s, y in sorted_pairs if s < t and y == 1)
        fpr = fp / n_bonafide
        fnr = fn / n_spoof
        points.append((t, fpr, fnr))

    for i in range(len(points) - 1):
        t1, fpr1, fnr1 = points[i]
        t2, fpr2, fnr2 = points[i + 1]
        diff1 = fpr1 - fnr1
        diff2 = fpr2 - fnr2

        if diff1 == 0:
            return float(fpr1), float(t1)
        if diff2 == 0:
            return float(fpr2), float(t2)

        if diff1 > 0 and diff2 < 0:
            alpha = diff1 / (diff1 - diff2)
            eer_val = fpr1 + alpha * (fpr2 - fpr1)
            t_eer = t1 + alpha * (t2 - t1)
            return float(eer_val), float(t_eer)

    best_t, best_fpr, best_fnr = min(points, key=lambda p: abs(p[1] - p[2]))
    return float((best_fpr + best_fnr) / 2), float(best_t)


def fit_thresholds(bonafide_scores: Sequence[float]) -> tuple[float, float]:
    """(tau_hi, tau_lo) = scores at 1% and 5% FPR on bonafide CALIBRATION windows."""
    if not bonafide_scores:
        return 0.9, 0.6
    arr = np.asarray(bonafide_scores, dtype=float)
    hi = float(np.percentile(arr, 99))
    lo = float(np.percentile(arr, 95))
    return hi, lo


def bootstrap_eer_by_speaker(
    items: Sequence[Item], scores: Sequence[float], n_boot: int = 2000, seed: int = 0
) -> tuple[float, float, float]:
    """(point, low, high): resample SPEAKERS with replacement, keep all their items."""
    labels = [it.label for it in items]
    point, _ = eer(labels, scores)
    if not items or len(items) != len(scores):
        return point, point, point

    speaker_map: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for it, s in zip(items, scores, strict=True):
        speaker_map[it.speaker].append((it.label, s))

    speakers = sorted(list(speaker_map.keys()))
    if not speakers:
        return point, point, point

    rng = random.Random(seed)
    boot_eers: list[float] = []

    for _ in range(n_boot):
        sample_speakers = rng.choices(speakers, k=len(speakers))
        b_labels: list[int] = []
        b_scores: list[float] = []
        for spk in sample_speakers:
            for y, s in speaker_map[spk]:
                b_labels.append(y)
                b_scores.append(s)

        if any(y == 0 for y in b_labels) and any(y == 1 for y in b_labels):
            val, _ = eer(b_labels, b_scores)
            boot_eers.append(val)

    if not boot_eers:
        return point, point, point

    low = float(np.percentile(boot_eers, 2.5))
    high = float(np.percentile(boot_eers, 97.5))
    return point, low, high
