"""Python ONNX voice detector, same model as the extension. TASK T17.

Model files (model.onnx + logreg.onnx from the Pascu et al. browser-plugin repo) are NOT
committed: the repo has no license file (docs/DATA_POLICY.md). Put them in
extension/models/ locally. Install: `uv sync --extra audio`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class WindowScorer(Protocol):
    model_version: str

    def score_windows(self, windows: list[Any]) -> list[float]:
        """One score in [0, 1] per 5 s window; higher = more likely synthetic."""
        ...


class OnnxVoiceDetector:
    def __init__(self, model_path: Path, logreg_path: Path, model_version: str) -> None:
        raise NotImplementedError("T17: see docs/tasks/T17-voice-uploads.md")

    def score_windows(self, windows: list[Any]) -> list[float]:
        raise NotImplementedError("T17: see docs/tasks/T17-voice-uploads.md")
