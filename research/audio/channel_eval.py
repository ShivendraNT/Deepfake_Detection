"""Audio channel evaluation + threshold fitting for the voice detector. TASK T18.

Channels (ffmpeg): clean; Opus 16 kbps; AMR-NB 12.2 kbps @ 8 kHz; G.711 mu-law @ 8 kHz.
Splits: speaker-disjoint 50/50 calibration / test. Metrics: EER, FPR/FNR at fixed tau,
bootstrap CIs resampled BY SPEAKER. tau_hi = 1% FPR, tau_lo = 5% FPR on Meet-captured
bonafide calibration windows. NEVER commit audio (team voices are personal data).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
    raise NotImplementedError("T18: see docs/tasks/T18-audio-channel-eval.md")


def speaker_disjoint_split(items: Sequence[Item], seed: int = 0) -> tuple[list[Item], list[Item]]:
    """Shuffle SPEAKERS (not items) with random.Random(seed); first half of speakers ->
    calibration, rest -> test. No speaker may appear in both."""
    raise NotImplementedError("T18: see docs/tasks/T18-audio-channel-eval.md")


def eer(labels: Sequence[int], scores: Sequence[float]) -> tuple[float, float]:
    """Equal error rate and the threshold where FPR == FNR (linear interpolation on the ROC)."""
    raise NotImplementedError("T18: see docs/tasks/T18-audio-channel-eval.md")


def fit_thresholds(bonafide_scores: Sequence[float]) -> tuple[float, float]:
    """(tau_hi, tau_lo) = scores at 1% and 5% FPR on bonafide CALIBRATION windows."""
    raise NotImplementedError("T18: see docs/tasks/T18-audio-channel-eval.md")


def bootstrap_eer_by_speaker(
    items: Sequence[Item], scores: Sequence[float], n_boot: int = 2000, seed: int = 0
) -> tuple[float, float, float]:
    """(point, low, high): resample SPEAKERS with replacement, keep all their items."""
    raise NotImplementedError("T18: see docs/tasks/T18-audio-channel-eval.md")
