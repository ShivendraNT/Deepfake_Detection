"""Video analysis for Satya: a live stream of screen frames, or a video file.

    analyzer = VideoAnalyzer.load()          # raises VideoUnavailable if deps/models missing
    stream = analyzer.new_stream()
    for window in stream.add_frames([(t, rgb), ...]):   # rgb: HxWx3 uint8
        ...                                              # one WindowResult per finished window

Frames are measured as they arrive and then dropped; only small per-frame numbers and a few
224 px face crops of the current window are kept, and those are dropped when the window is
scored. Nothing is written to disk.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from satyapan.video.cnn import BlendScorer, CnnSpec
from satyapan.video.features import (
    CROP_EVERY_S,
    CUES,
    HOP_S,
    WINDOW_S,
    Coverage,
    coverage,
    window_features,
)
from satyapan.video.fusion import DEFAULT_PATH as FUSION_PATH
from satyapan.video.fusion import FusionModel
from satyapan.video.landmarks import FaceTracker, VideoUnavailable, model_dir
from satyapan.video.observe import FrameRecord, observe
from satyapan.video.rules import DEFAULT_PATH as THRESHOLDS_PATH
from satyapan.video.rules import VideoThresholds, VideoVerdict, classify_windows, load_thresholds

FALLBACK_FUSION = FUSION_PATH.with_name("video_fusion__blend.json")
FALLBACK_THRESHOLDS = THRESHOLDS_PATH.with_name("video_thresholds__blend.json")


@dataclass
class WindowResult:
    index: int
    t_start: float
    t_end: float
    coverage: Coverage
    features: dict[str, float]
    score: float | None  # None = abstained (no usable face)
    cues: list[str] = field(default_factory=list)  # cues that pushed towards "fake"


class VideoAnalyzer:
    def __init__(
        self,
        fusion: FusionModel,
        thresholds: VideoThresholds,
        scorer: BlendScorer | None,
        tracker_factory: Callable[[], Any] = FaceTracker,
        crop_every_s: float = CROP_EVERY_S,
    ) -> None:
        self.fusion = fusion
        self.thresholds = thresholds
        self.scorer = scorer
        self.tracker_factory = tracker_factory
        self.crop_every_s = crop_every_s
        self._lock = threading.Lock()  # ONNX sessions are shared by all streams

    @classmethod
    def load(
        cls, fusion_path: Path | None = None, thresholds_path: Path | None = None
    ) -> VideoAnalyzer:
        """The shipped config; if its crop CNN is not on this laptop (e.g. the 1.2 GB GenD file
        was never built), the SBI fallback config (config/*__blend.json) with its own fusion and
        thresholds. Never a CNN with thresholds fitted for another one."""
        pairs = (
            [(fusion_path, thresholds_path or THRESHOLDS_PATH)]
            if fusion_path
            else [(FUSION_PATH, THRESHOLDS_PATH), (FALLBACK_FUSION, FALLBACK_THRESHOLDS)]
        )
        problems: list[str] = []
        for fp, tp in pairs:
            try:
                fusion, thr = FusionModel.load(fp), load_thresholds(tp)
            except FileNotFoundError as exc:
                problems.append(f"video config missing: {exc.filename}")
                continue
            spec = CnnSpec.from_config(fusion.cnn)
            if not (model_dir() / spec.file).exists():
                problems.append(f"{spec.file} missing in {model_dir()}")
                continue
            FaceTracker().close()  # fail early if mediapipe or the face model is missing
            return cls(fusion, thr, BlendScorer(model_dir() / spec.file), FaceTracker,
                       spec.crop_every_s)  # fmt: skip
        raise VideoUnavailable("; ".join(problems) + " (run `make video-models`)")

    def new_stream(self) -> VideoStream:
        return VideoStream(self)

    def score_window(
        self,
        index: int,
        records: Sequence[FrameRecord],
        audio: np.ndarray | None = None,
        sr: int = 16000,
        audio_t0: float = 0.0,
        cache: dict[float, float] | None = None,
    ) -> WindowResult:
        """cache: crop logits by frame time, shared by overlapping windows of one stream, so
        every crop is scored once."""
        cov = coverage(records)
        cache = {} if cache is None else cache
        with_crop = [r for r in records if r.found and r.crop is not None]
        todo = [r for r in with_crop if r.t not in cache]
        if self.scorer is not None and todo:
            with self._lock:
                fresh = self.scorer.logits(np.array([r.crop for r in todo]))
            cache.update({r.t: float(x) for r, x in zip(todo, fresh, strict=True)})
        logits = [cache[r.t] for r in with_crop if r.t in cache]
        feats = window_features(records, audio, sr, audio_t0, logits)
        t0 = records[0].t if records else 0.0
        t1 = records[-1].t if records else 0.0
        if not cov.usable:
            return WindowResult(index, t0, t1, cov, feats, None)
        x = np.array([[feats.get(f, float("nan")) for f in self.fusion.features]])
        score = float(self.fusion.score(x)[0])
        parts = self.fusion.contributions(x)
        cues = [
            cue
            for cue, names in CUES.items()
            if sum(parts.get(n, 0.0) for n in names) >= self.thresholds.cue_flag_logit
        ]
        return WindowResult(index, t0, t1, cov, feats, score, cues)

    def verdict(self, results: Sequence[WindowResult]) -> VideoVerdict:
        return classify_windows(
            [r.score for r in results], self.thresholds, [r.coverage.problem() for r in results]
        )

    def analyze_frames(
        self,
        frames: Iterable[tuple[float, np.ndarray]],
        audio: np.ndarray | None = None,
        sr: int = 16000,
    ) -> list[WindowResult]:
        stream = self.new_stream()
        try:
            if audio is not None:
                stream.add_audio(audio, 0.0, sr)
            out = stream.add_frames(frames)
            out += stream.flush()
            return out
        finally:
            stream.close()


class VideoStream:
    """One call (or one file): landmarks are tracked across frames, windows overlap."""

    def __init__(self, analyzer: VideoAnalyzer) -> None:
        self.analyzer = analyzer
        self._tracker: Any = analyzer.tracker_factory()
        self._records: list[FrameRecord] = []
        self._next_crop = 0.0
        self._next_window = 0.0  # start time of the next window to emit
        self._index = 0
        self._audio: np.ndarray | None = None
        self._audio_t0 = 0.0
        self._sr = 16000
        self._last_t = -1.0
        self._logits: dict[float, float] = {}  # crop logits of frames still in a window

    def add_audio(self, pcm: np.ndarray, t0: float, sr: int = 16000) -> None:
        """Call audio (mono float32) starting at t0 on the frame clock (for lip-sync)."""
        pcm = np.asarray(pcm, np.float32)
        if self._audio is None:
            self._audio, self._audio_t0, self._sr = pcm, t0, sr
            return
        end_t = self._audio_t0 + len(self._audio) / self._sr
        gap = int(round((t0 - end_t) * self._sr))
        if gap > 0:
            pcm = np.concatenate([np.zeros(gap, np.float32), pcm])
        elif gap < 0:
            pcm = pcm[-gap:]
        self._audio = np.concatenate([self._audio, pcm])
        keep = int((WINDOW_S + HOP_S + 2) * self._sr)  # bounded memory
        if len(self._audio) > keep:
            drop = len(self._audio) - keep
            self._audio = self._audio[drop:]
            self._audio_t0 += drop / self._sr

    def add_frames(self, frames: Iterable[tuple[float, np.ndarray]]) -> list[WindowResult]:
        if self._tracker is None:
            raise RuntimeError("stream is closed")
        out: list[WindowResult] = []
        for t, rgb in frames:
            if t <= self._last_t:
                continue  # duplicate or out-of-order frame: never stitched back in
            self._last_t = t
            if not self._records:
                self._next_window = max(self._next_window, t)
            obs = self._tracker.track(rgb, t)
            # Crops are only for the CNN; without it (tests, partial installs) skip the work.
            want = obs is not None and t >= self._next_crop and self.analyzer.scorer is not None
            rec = observe(
                rgb, t, obs.pts if obs else None, obs.jaw_open if obs else 0.0, want_crop=want
            )
            if want:
                self._next_crop = t + self.analyzer.crop_every_s
            self._records.append(rec)
            while t >= self._next_window + WINDOW_S:
                out.append(self._emit(self._next_window, self._next_window + WINDOW_S))
        return out

    def _emit(self, start: float, end: float) -> WindowResult:
        win = [r for r in self._records if start <= r.t < end]
        result = self.analyzer.score_window(
            self._index, win, self._audio, self._sr, self._audio_t0, self._logits
        )
        self._index += 1
        self._next_window = start + HOP_S
        # Forget what no future window needs (frames, crops, their logits).
        self._records = [r for r in self._records if r.t >= self._next_window]
        self._logits = {t: v for t, v in self._logits.items() if t >= self._next_window}
        return result

    def flush(self) -> list[WindowResult]:
        """At the end of a file: score a last partial window if it is long enough."""
        if not self._records or self._index > 0:
            return []
        return [self._emit(self._records[0].t, self._records[-1].t + 1e-6)]

    def close(self) -> None:
        if self._tracker is not None:
            self._tracker.close()
            self._tracker = None
        self._records = []
