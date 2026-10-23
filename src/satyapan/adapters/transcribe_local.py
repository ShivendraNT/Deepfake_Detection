"""Local, offline speech-to-text for live calls and voice notes (T11/T17, finale).

Picks the best engine that is installed on this laptop:

1. ``mlx-whisper`` on Apple Silicon (fastest on M-series; ``uv sync --extra asr-mac``)
2. ``faster-whisper`` on any OS, CPU int8 (``uv sync --extra asr``)

Audio never leaves the machine. Model weights are downloaded once by ``make asr`` (that is the
only network use, and it happens before the demo, never in a unit test).

Live chunks arrive as 16 kHz mono 16-bit WAV from the capture window, so WAV is decoded in
process with no ffmpeg round-trip. Other formats (voice notes) go through ffmpeg.
"""

from __future__ import annotations

import io
import os
import platform
import re
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from satyapan.adapters.base import TranscriptResult

SAMPLE_RATE = 16_000

# A short glossary nudges Whisper towards payment vocabulary (Indian accounts payable).
# It is a decoding hint only: it never touches the policy or any band.
DOMAIN_PROMPT = (
    "Accounts payable call. Payment, NEFT, RTGS, IMPS, UPI, IFSC, account number, beneficiary, "
    "vendor, invoice, lakh, crore, OTP, PIN, AnyDesk, TeamViewer, escrow, approval, CFO, "
    "confidential, transfer."
)

# Whisper invents these on silence or music. Drop a segment that is only one of them.
_HALLUCINATIONS = re.compile(
    r"^\s*(thanks? (you )?for watching|thank you\.?|subtitles? by.*|please subscribe.*|"
    r"you\.?|bye\.?|\.+|music|\[.*\]|\(.*\)|♪+|transcribed by.*|amara\.org.*)\s*$",
    re.IGNORECASE,
)

FASTER_WHISPER_DEFAULT = "small"
MLX_DEFAULT = "mlx-community/whisper-large-v3-turbo"


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() in {"arm64", "aarch64"}


def decode_wav(data: bytes) -> np.ndarray:
    """16-bit PCM WAV -> float32 mono at 16 kHz. Raise ValueError if it is not plain PCM WAV."""
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"not a PCM WAV file: {exc}") from exc
    if width != 2:
        raise ValueError(f"unsupported WAV sample width: {width}")
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != SAMPLE_RATE and samples.size:
        duration = samples.size / rate
        target = max(1, int(round(duration * SAMPLE_RATE)))
        samples = np.interp(
            np.linspace(0.0, samples.size - 1, target), np.arange(samples.size), samples
        ).astype(np.float32)
    return samples


def decode_any(data: bytes, mime: str) -> np.ndarray:
    """WAV in process; anything else through ffmpeg (raises ValueError if ffmpeg fails)."""
    if data[:4] == b"RIFF" or mime.split(";")[0].strip() in {"audio/wav", "audio/x-wav"}:
        try:
            return decode_wav(data)
        except ValueError:
            pass  # e.g. float WAV: let ffmpeg handle it
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0"]
    cmd += ["-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"]
    try:
        proc = subprocess.run(cmd, input=data, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"ffmpeg could not run: {exc}") from exc
    if proc.returncode != 0 or not proc.stdout:
        raise ValueError(f"ffmpeg could not decode {mime} audio")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0


def clean_text(text: str) -> str:
    """Collapse whitespace and drop known Whisper hallucinations."""
    text = " ".join(text.split())
    return "" if _HALLUCINATIONS.match(text) else text


@dataclass
class EngineStatus:
    engine: str  # "mlx-whisper" | "faster-whisper" | "none"
    model: str
    ready: bool = False
    loading: bool = False
    error: str | None = None
    warmup_ms: float | None = None
    last_latency_ms: float | None = None
    language: str = "auto"

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "model": self.model,
            "ready": self.ready,
            "loading": self.loading,
            "error": self.error,
            "warmup_ms": self.warmup_ms,
            "last_latency_ms": self.last_latency_ms,
            "language": self.language,
        }


def detect_engine(preference: str = "auto") -> str:
    """Which engine is importable here. Does not load any model."""
    import importlib.util

    has_mlx = is_apple_silicon() and importlib.util.find_spec("mlx_whisper") is not None
    has_fw = importlib.util.find_spec("faster_whisper") is not None
    if preference == "mlx" and has_mlx:
        return "mlx-whisper"
    if preference == "faster" and has_fw:
        return "faster-whisper"
    if preference in {"auto", "mlx", "faster"}:
        if has_mlx:
            return "mlx-whisper"
        if has_fw:
            return "faster-whisper"
    return "none"


@dataclass
class LocalTranscriber:
    """Transcriber protocol implementation backed by a local Whisper engine.

    The model loads lazily (first call or ``warm_up``) and calls are serialised with a lock:
    one model, one call at a time, which is what a laptop can actually run in real time.
    """

    engine: str = field(default_factory=lambda: detect_engine(_env("SATYAPAN_ASR", "auto")))
    model: str = ""
    language: str | None = field(
        default_factory=lambda: (
            None if _env("SATYAPAN_ASR_LANG", "en") == "auto" else _env("SATYAPAN_ASR_LANG", "en")
        )
    )
    prompt: str = DOMAIN_PROMPT
    status: EngineStatus = field(init=False)
    _model: Any = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.model:
            if self.engine == "mlx-whisper":
                self.model = _env("SATYAPAN_ASR_MODEL", MLX_DEFAULT)
            else:
                self.model = _env("SATYAPAN_ASR_MODEL", FASTER_WHISPER_DEFAULT)
        self.status = EngineStatus(
            engine=self.engine, model=self.model, language=self.language or "auto"
        )
        if self.engine == "none":
            self.status.error = (
                "No speech engine installed. Run `make asr` (or `uv sync --extra asr`)."
            )

    # ------------------------------------------------------------------ loading
    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        if self.engine == "none":
            raise RuntimeError(self.status.error or "no speech engine")
        self.status.loading = True
        try:
            if self.engine == "faster-whisper":
                from faster_whisper import WhisperModel

                threads = max(1, min(8, (os.cpu_count() or 4) - 1))
                self._model = WhisperModel(
                    self.model, device="cpu", compute_type="int8", cpu_threads=threads
                )
            else:
                import mlx_whisper

                self._model = mlx_whisper
            self.status.error = None
            return self._model
        except Exception as exc:  # noqa: BLE001 - surfaced to /companion/health
            self.status.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.status.loading = False

    def warm_up(self) -> None:
        """Load the model and run one tiny decode so the first real sentence is fast."""
        t0 = time.perf_counter()
        with self._lock:
            self._load()
            self._run(np.zeros(SAMPLE_RATE, dtype=np.float32), self.language)
        self.status.ready = True
        self.status.warmup_ms = round((time.perf_counter() - t0) * 1000, 1)

    # ------------------------------------------------------------------ decoding
    def _run(self, samples: np.ndarray, language: str | None) -> tuple[str, str, float]:
        if self.engine == "faster-whisper":
            segments, info = self._model.transcribe(
                samples,
                language=language,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
                initial_prompt=self.prompt,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
            )
            parts: list[str] = []
            end = 0.0
            for seg in segments:
                if getattr(seg, "no_speech_prob", 0.0) > 0.75 and seg.avg_logprob < -0.8:
                    continue
                parts.append(seg.text)
                end = float(seg.end)
            return " ".join(parts), str(info.language or language or "unknown"), end
        out = self._model.transcribe(
            samples,
            path_or_hf_repo=self.model,
            language=language,
            initial_prompt=self.prompt,
            condition_on_previous_text=False,
            temperature=0.0,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
        )
        segs = out.get("segments") or []
        kept = [
            s
            for s in segs
            if not (s.get("no_speech_prob", 0.0) > 0.75 and s.get("avg_logprob", 0.0) < -0.8)
        ]
        text = " ".join(str(s.get("text", "")) for s in kept) if segs else str(out.get("text", ""))
        end = float(kept[-1]["end"]) if kept else 0.0
        return text, str(out.get("language") or language or "unknown"), end

    def transcribe_samples(
        self, samples: np.ndarray, language_hint: str | None = None
    ) -> TranscriptResult:
        duration = samples.size / SAMPLE_RATE
        # Near-silent chunks never reach Whisper (it would invent text).
        if samples.size < SAMPLE_RATE * 0.3 or rms(samples) < 0.004:
            return TranscriptResult(
                text="", language="unknown", duration_s=duration, engine=self.engine
            )
        language = language_hint or self.language
        t0 = time.perf_counter()
        with self._lock:
            self._load()
            text, lang, _end = self._run(samples.astype(np.float32, copy=False), language)
        self.status.ready = True
        self.status.last_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        return TranscriptResult(
            text=clean_text(text),
            language=lang,
            duration_s=duration,
            engine=f"{self.engine}:{self.model}",
        )

    def transcribe(
        self, audio: bytes, mime: str, language_hint: str | None = None
    ) -> TranscriptResult:
        return self.transcribe_samples(decode_any(audio, mime), language_hint)


@dataclass
class UnavailableTranscriber:
    """Used when no engine is installed: fails loudly instead of returning a fake empty text.

    The live route turns the error into a visible status event ("my ears are not installed"),
    so a demo can never silently run on a deaf Satya.
    """

    reason: str = "No speech engine installed. Run `make asr`."
    status: EngineStatus = field(
        default_factory=lambda: EngineStatus(engine="none", model="", error=None)
    )

    def __post_init__(self) -> None:
        self.status.error = self.reason

    def warm_up(self) -> None:
        raise RuntimeError(self.reason)

    def transcribe(
        self, audio: bytes, mime: str, language_hint: str | None = None
    ) -> TranscriptResult:
        raise RuntimeError(self.reason)


def build_transcriber() -> LocalTranscriber | UnavailableTranscriber:
    """The transcriber for this laptop: a local engine, or one that explains what is missing."""
    if _env("SATYAPAN_ASR", "auto") == "off":
        return UnavailableTranscriber("Speech engine is switched off (SATYAPAN_ASR=off).")
    engine = detect_engine(_env("SATYAPAN_ASR", "auto"))
    if engine == "none":
        return UnavailableTranscriber()
    return LocalTranscriber(engine=engine)
