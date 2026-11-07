"""Lazily loaded models shared by all analyses on this workstation.

Each model loads on first use and is cached; ONNX sessions are guarded by a lock because the
lab runs several evidence items in parallel. `status()` answers "what can this workstation
check?" without loading anything (used by /lab/api/health and the dashboard).
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from satyapan.forensics.base import Unavailable

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config"


def forensic_model_dir() -> Path:
    env = os.environ.get("SATYAPAN_FORENSIC_MODELS")
    return Path(env) if env else ROOT / "models" / "forensics"


def load_json(name: str) -> dict[str, Any]:
    path = CONFIG / name
    if not path.exists():
        raise Unavailable(f"config/{name} missing")
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


class ModelRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}
        self._errors: dict[str, str] = {}
        self.locks: dict[str, threading.Lock] = {}
        self._loaders: dict[str, Callable[[], Any]] = {
            "face_cnn": self._load_face_cnn,
            "video": self._load_video,
            "voice": self._load_voice,
            "aigen": self._load_aigen,
            "asr": self._load_asr,
            "speaker": self._load_speaker,
            "face_id": self._load_face_id,
        }

    def lock(self, name: str) -> threading.Lock:
        with self._lock:
            return self.locks.setdefault(name, threading.Lock())

    def get(self, name: str) -> Any:
        with self.lock(f"load:{name}"):
            if name in self._cache:
                return self._cache[name]
            if name in self._errors:
                raise Unavailable(self._errors[name])
            try:
                obj = self._loaders[name]()
            except Unavailable as exc:
                self._errors[name] = str(exc)
                raise
            except Exception as exc:  # noqa: BLE001 - missing system libs, bad model files
                self._errors[name] = f"{type(exc).__name__}: {exc}"
                raise Unavailable(self._errors[name]) from exc
            self._cache[name] = obj
            return obj

    def reset(self) -> None:
        with self._lock:
            self._cache.clear()
            self._errors.clear()

    # ------------------------------------------------------------------ status (no loading)
    def status(self) -> dict[str, dict[str, Any]]:
        from satyapan.video.landmarks import model_dir as video_dir
        from satyapan.voice.detector import voice_model_dir

        def has(path: Path) -> bool:
            return path.exists() and path.stat().st_size > 0

        out: dict[str, dict[str, Any]] = {}
        try:
            thr = load_json("image_face_thresholds.json")
            face_file = video_dir() / str(thr["model"])
            out["face_cnn"] = {"available": has(face_file) and has(video_dir() /
                               "face_landmarker.task"), "model": thr["model"],
                               "purpose": "face-swap / synthetic face detection (GenD)"}  # fmt: skip
        except Exception as exc:  # noqa: BLE001
            out["face_cnn"] = {"available": False, "detail": str(exc)}
        out["video"] = dict(out["face_cnn"], purpose="deepfake video timeline (GenD + fusion)")
        vdir = voice_model_dir()
        out["voice"] = {"available": has(vdir / "model.onnx") and has(vdir / "logreg_prob.onnx"),
                        "model": "XLS-R deepfake-audio (gustking) ONNX",
                        "purpose": "synthetic / cloned voice detection"}  # fmt: skip
        try:
            spec = load_json("aigen_model.json")
            out["aigen"] = {"available": has(forensic_model_dir() / spec["file"]),
                            "model": spec.get("name"), "purpose": "AI-generated image detection"}  # fmt: skip
        except Unavailable as exc:
            out["aigen"] = {"available": False, "detail": str(exc),
                            "purpose": "AI-generated image detection"}  # fmt: skip
        try:
            import faster_whisper  # noqa: F401

            asr = True
        except ImportError:
            try:
                import mlx_whisper  # noqa: F401

                asr = True
            except ImportError:
                asr = False
        out["asr"] = {"available": asr, "purpose": "speech transcription (Whisper, offline)"}
        sp = forensic_model_dir() / "speaker_resnet34.onnx"
        out["speaker"] = {"available": has(sp), "purpose": "speaker comparison"}
        fid = forensic_model_dir() / "face_recognition_sface_2021dec.onnx"
        out["face_id"] = {"available": has(fid), "purpose": "face identity comparison (SFace)"}
        try:
            import c2pa  # noqa: F401

            out["c2pa"] = {"available": True, "purpose": "Content Credentials validation"}
        except ImportError:
            out["c2pa"] = {"available": False, "purpose": "Content Credentials validation"}
        return out

    # ------------------------------------------------------------------ loaders
    def _load_face_cnn(self) -> Any:
        from satyapan.imagecheck.face import ImageFaceThresholds
        from satyapan.video.cnn import BlendScorer
        from satyapan.video.landmarks import FaceTracker, VideoUnavailable, model_dir

        try:
            thr = ImageFaceThresholds.load()
        except FileNotFoundError as exc:
            raise Unavailable("config/image_face_thresholds.json missing") from exc
        path = model_dir() / thr.model_file
        if not path.exists():
            raise Unavailable(f"{thr.model_file} not installed (run `make video`)")
        try:
            FaceTracker().close()
            scorer = BlendScorer(path, threads=max(2, (os.cpu_count() or 4) - 1))
        except VideoUnavailable as exc:
            raise Unavailable(str(exc)) from exc
        return {"scorer": scorer, "thresholds": thr, "tracker": FaceTracker}

    def _load_video(self) -> Any:
        from satyapan.video.analyzer import VideoAnalyzer
        from satyapan.video.landmarks import VideoUnavailable

        try:
            return VideoAnalyzer.load()
        except VideoUnavailable as exc:
            raise Unavailable(str(exc)) from exc

    def _load_voice(self) -> Any:
        from satyapan.voice.detector import load_default_detector
        from satyapan.voice.rules import load_thresholds

        thr = load_thresholds(CONFIG / "voice_thresholds.json")
        try:
            det = load_default_detector(thr.model_version)
        except FileNotFoundError as exc:
            raise Unavailable(f"{exc} (run `make voice`)") from exc
        return {"detector": det, "thresholds": thr}

    def _load_aigen(self) -> Any:
        from satyapan.forensics.image.aigen import AiImageModel

        spec = load_json("aigen_model.json")
        path = forensic_model_dir() / spec["file"]
        if not path.exists():
            raise Unavailable(f"{spec['file']} not installed (run `make forensics-models`)")
        return AiImageModel(path, spec)

    def _load_asr(self) -> Any:
        from satyapan.forensics.audio.transcribe import ForensicTranscriber

        return ForensicTranscriber.load()

    def _load_speaker(self) -> Any:
        from satyapan.forensics.audio.speaker import SpeakerEmbedder

        path = forensic_model_dir() / "speaker_resnet34.onnx"
        if not path.exists():
            raise Unavailable("speaker model not installed (run `make forensics-models`)")
        return SpeakerEmbedder(path)

    def _load_face_id(self) -> Any:
        import cv2

        path = forensic_model_dir() / "face_recognition_sface_2021dec.onnx"
        if not path.exists():
            raise Unavailable("SFace model not installed (run `make forensics-models`)")
        return cv2.FaceRecognizerSF.create(str(path), "")


_REGISTRY: ModelRegistry | None = None


def registry() -> ModelRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ModelRegistry()
    return _REGISTRY
