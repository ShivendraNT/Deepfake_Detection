"""Per-evidence analysis context: the raw bytes, cached decodes and the artifact writer.

Every analyzer reads the evidence through this object, so the file is decoded once and the
original bytes are never modified (the store keeps them read-only and re-hashes them before
each analysis).
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from satyapan.forensics.filetype import Sniffed
from satyapan.forensics.models import Artifact, MediaInfo

MAX_ANALYSIS_SIDE = 2400  # pixel-level analyzers work on at most this many pixels per side

ProgressFn = Callable[[str, str, float], None]


def _noop(stage: str, message: str, progress: float) -> None:
    return None


@dataclass
class AnalysisContext:
    evidence_id: str
    case_id: str
    data: bytes
    filename: str
    sniffed: Sniffed
    media: MediaInfo
    artifact_dir: Path
    models: Any = None  # satyapan.forensics.registry.ModelRegistry
    progress: ProgressFn = _noop
    role: str = "questioned"
    cache: dict[str, Any] = field(default_factory=dict)
    peers: list[dict[str, Any]] = field(default_factory=list)  # other evidence in the case

    # ---- images -------------------------------------------------------------------------
    def pil(self) -> Any:
        """The decoded image (orientation from EXIF applied), RGB. ValueError if unreadable."""
        if "pil" not in self.cache:
            from PIL import Image, ImageOps

            register_heif()

            try:
                img = Image.open(io.BytesIO(self.data))
                img.load()
            except Exception as exc:  # noqa: BLE001 - PIL raises many types
                raise ValueError(f"image does not decode: {exc}") from exc
            self.cache["pil_raw"] = img
            with contextlib.suppress(Exception):  # a broken orientation tag must not stop analysis
                img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB",):
                img = img.convert("RGBA").convert("RGB") if "A" in img.mode else img.convert("RGB")
            self.cache["pil"] = img
        return self.cache["pil"]

    def pil_raw(self) -> Any:
        self.pil()
        return self.cache["pil_raw"]

    def rgb(self, max_side: int = MAX_ANALYSIS_SIDE) -> np.ndarray:
        """RGB uint8, downscaled so the longer side is at most max_side (analysis copy)."""
        key = f"rgb_{max_side}"
        if key not in self.cache:
            img = self.pil()
            if max(img.size) > max_side:
                img = img.copy()
                img.thumbnail((max_side, max_side))
            self.cache[key] = np.asarray(img, dtype=np.uint8)
        return self.cache[key]  # type: ignore[no-any-return]

    def gray(self, max_side: int = MAX_ANALYSIS_SIDE) -> np.ndarray:
        key = f"gray_{max_side}"
        if key not in self.cache:
            rgb = self.rgb(max_side).astype(np.float32)
            self.cache[key] = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
        return self.cache[key]  # type: ignore[no-any-return]

    # ---- audio --------------------------------------------------------------------------
    def audio(self, sr: int = 16000) -> np.ndarray:
        """Mono float32 at `sr` (decoded by ffmpeg). ValueError if there is no audio."""
        key = f"audio_{sr}"
        if key not in self.cache:
            path = self.cache.get("path")
            self.cache[key] = decode_audio(self.data, sr, path=path)
        return self.cache[key]  # type: ignore[no-any-return]

    def audio_native(self) -> tuple[np.ndarray, int]:
        """Mono float32 at the file's own sample rate (for bandwidth / ENF / splice work)."""
        sr = int(self.media.sample_rate or 16000)
        sr = max(8000, min(sr, 96000))
        return self.audio(sr), sr

    # ---- artifacts ----------------------------------------------------------------------
    def save_png(self, name: str, image: Any, kind: str, title: str, caption: str = "") -> Artifact:
        from PIL import Image

        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(image, np.ndarray):
            arr = image
            if arr.dtype != np.uint8:
                arr = np.clip(arr, 0, 255).astype(np.uint8)
            image = Image.fromarray(arr)
        fname = name if name.endswith(".png") else f"{name}.png"
        image.save(self.artifact_dir / fname, format="PNG", optimize=True)
        return Artifact(name=fname, kind=kind, title=title, caption=caption)

    def save_jpeg(
        self, name: str, image: Any, kind: str, title: str, caption: str = ""
    ) -> Artifact:
        from PIL import Image

        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(image, np.ndarray):
            image = Image.fromarray(np.clip(image, 0, 255).astype(np.uint8))
        fname = name if name.endswith(".jpg") else f"{name}.jpg"
        image.convert("RGB").save(self.artifact_dir / fname, format="JPEG", quality=88)
        return Artifact(name=fname, kind=kind, title=title, caption=caption,
                        media_type="image/jpeg")  # fmt: skip

    def save_json(self, name: str, obj: Any) -> str:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        fname = name if name.endswith(".json") else f"{name}.json"
        (self.artifact_dir / fname).write_text(json.dumps(obj, default=str), encoding="utf-8")
        return fname


_HEIF: list[bool] = []


def register_heif() -> bool:
    """HEIC/HEIF (the iPhone camera default) through pillow-heif when installed."""
    if not _HEIF:
        try:
            from pillow_heif import register_heif_opener

            register_heif_opener()
            _HEIF.append(True)
        except ImportError:
            _HEIF.append(False)
    return _HEIF[0]


def decode_audio(
    data: bytes, sr: int = 16000, stream: str = "a:0", path: Path | None = None
) -> np.ndarray:
    """ffmpeg -> mono float32 at sr. Works for audio files and the audio track of a video.
    Reads from the stored file when a path is given (MP4/MOV may keep their index at the end,
    which a pipe cannot seek to)."""
    if not data and path is None:
        raise ValueError("empty file")
    src = str(path) if path is not None else "pipe:0"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src, "-map", stream,
        "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "pipe:1",
    ]  # fmt: skip
    try:
        proc = subprocess.run(cmd, input=None if path is not None else data,
                              capture_output=True, timeout=300)  # fmt: skip
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"ffmpeg could not run: {exc}") from exc
    if proc.returncode != 0 or not proc.stdout:
        err = proc.stderr.decode("utf-8", "ignore").strip().splitlines()
        raise ValueError(f"no decodable audio stream ({err[-1] if err else 'empty'})")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def colormap(values: np.ndarray, cmap: str = "inferno") -> np.ndarray:
    """values in [0, 1] -> RGB uint8 using OpenCV's perceptual colormaps."""
    import cv2

    maps = {
        "inferno": cv2.COLORMAP_INFERNO,
        "magma": cv2.COLORMAP_MAGMA,
        "turbo": cv2.COLORMAP_TURBO,
        "viridis": cv2.COLORMAP_VIRIDIS,
        "jet": cv2.COLORMAP_JET,
        "hot": cv2.COLORMAP_HOT,
    }
    v = np.nan_to_num(np.clip(values, 0.0, 1.0)) * 255.0
    bgr = cv2.applyColorMap(v.astype(np.uint8), maps.get(cmap, cv2.COLORMAP_INFERNO))
    return bgr[..., ::-1].copy()


def overlay(
    rgb: np.ndarray, heat: np.ndarray, alpha: float = 0.55, cmap: str = "turbo"
) -> np.ndarray:
    """Blend a [0,1] heat map (any size) over an RGB image."""
    import cv2

    h, w = rgb.shape[:2]
    heat_r = cv2.resize(heat.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    col = colormap(heat_r, cmap).astype(np.float32)
    a = (alpha * np.clip(heat_r, 0, 1) ** 0.8)[..., None]
    out = rgb.astype(np.float32) * (1 - a) + col * a
    return np.clip(out, 0, 255).astype(np.uint8)


def robust_z(x: np.ndarray) -> np.ndarray:
    """(x - median) / (1.4826 * MAD); 0 where MAD is 0."""
    med = float(np.nanmedian(x))
    mad = float(np.nanmedian(np.abs(x - med))) * 1.4826
    if mad <= 1e-9:
        return np.zeros_like(x, dtype=np.float32)
    return ((x - med) / mad).astype(np.float32)


def block_reduce(x: np.ndarray, block: int, fn: str = "mean") -> np.ndarray:
    """Non-overlapping block statistic over a 2-D array (edges cropped)."""
    h, w = x.shape[:2]
    hb, wb = h // block, w // block
    if hb == 0 or wb == 0:
        return np.zeros((max(hb, 1), max(wb, 1)), dtype=np.float32)
    v = x[: hb * block, : wb * block].reshape(hb, block, wb, block)
    if fn == "median":
        return np.median(v, axis=(1, 3)).astype(np.float32)
    if fn == "max":
        return v.max(axis=(1, 3)).astype(np.float32)
    return v.mean(axis=(1, 3)).astype(np.float32)


def regions_from_mask(
    mask: np.ndarray, min_frac: float = 0.002, max_regions: int = 6
) -> list[tuple[float, float, float, float, float]]:
    """Connected components of a boolean block mask -> normalised boxes (x, y, w, h, area)."""
    import cv2

    m = mask.astype(np.uint8)
    if m.sum() == 0:
        return []
    n, _, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    H, W = m.shape
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        frac = area / float(H * W)
        if frac < min_frac:
            continue
        out.append((x / W, y / H, w / W, h / H, frac))
    out.sort(key=lambda r: -r[4])
    return out[:max_regions]
