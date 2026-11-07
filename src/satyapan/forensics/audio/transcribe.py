"""Offline transcription with timestamps (faster-whisper, or mlx-whisper on Apple Silicon).

Language is detected (Hindi, English, Hinglish and the other Whisper languages); the lab keeps
segment timestamps so a quoted sentence can be found in the recording.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from satyapan.forensics.base import Unavailable


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    language: str
    language_probability: float
    segments: list[Segment] = field(default_factory=list)
    engine: str = ""

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments).strip()


@dataclass
class ForensicTranscriber:
    engine: str
    model_name: str
    _model: Any = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def load(cls) -> ForensicTranscriber:
        from satyapan.adapters.transcribe_local import detect_engine

        engine = detect_engine(os.environ.get("SATYAPAN_ASR", "auto"))
        if engine == "none":
            raise Unavailable("no speech engine installed (run `make asr`)")
        cores = os.cpu_count() or 4
        default = "small" if cores >= 8 else "base"
        name = os.environ.get("SATYAPAN_LAB_ASR_MODEL", default)
        if engine == "mlx-whisper":
            name = os.environ.get("SATYAPAN_LAB_ASR_MODEL", "mlx-community/whisper-small-mlx")
        return cls(engine=engine, model_name=name)

    def _get(self) -> Any:
        if self._model is None:
            if self.engine == "faster-whisper":
                from faster_whisper import WhisperModel

                threads = max(1, min(8, (os.cpu_count() or 4) - 1))
                self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8",
                                           cpu_threads=threads)  # fmt: skip
            else:
                import mlx_whisper

                self._model = mlx_whisper
        return self._model

    def transcribe(self, x16k: np.ndarray) -> Transcript:
        with self._lock:
            model = self._get()
            if self.engine == "faster-whisper":
                segs, info = model.transcribe(
                    x16k.astype(np.float32), beam_size=1, temperature=0.0, vad_filter=True,
                    condition_on_previous_text=False,
                    vad_parameters={"min_silence_duration_ms": 400},
                )  # fmt: skip
                out = [Segment(float(s.start), float(s.end), s.text.strip()) for s in segs
                       if not (s.no_speech_prob > 0.7 and s.avg_logprob < -0.8)]  # fmt: skip
                return Transcript(str(info.language), float(info.language_probability), out,
                                  f"faster-whisper:{self.model_name}")  # fmt: skip
            res = model.transcribe(x16k.astype(np.float32), path_or_hf_repo=self.model_name,
                                   temperature=0.0, condition_on_previous_text=False)  # fmt: skip
            out = [Segment(float(s["start"]), float(s["end"]), str(s["text"]).strip())
                   for s in res.get("segments", [])]  # fmt: skip
            return Transcript(str(res.get("language", "unknown")), 1.0, out,
                              f"mlx-whisper:{self.model_name}")  # fmt: skip
