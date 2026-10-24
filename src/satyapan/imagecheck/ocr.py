"""Text inside an image (a screenshot of a WhatsApp/SMS/e-mail scam, a photographed invoice).

RapidOCR (Apache-2.0, ONNX models bundled, CPU, any OS): `uv pip install rapidocr-onnxruntime`
(the `ocr` extra). Without it the image is still face-checked and the result says OCR is off.
The text then goes through the same ask extractor and scam-text model as any message.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np


class OcrUnavailable(RuntimeError):
    pass


_ENGINE: Any = None
_LOCK = threading.Lock()
# English recogniser (PaddleOCR en_PP-OCRv3 via RapidOCR's ONNX export, Apache-2.0): the
# bundled default model often drops the spaces between English words, which hides asks.
EN_REC = Path(__file__).resolve().parents[3] / "models" / "ocr" / "en_PP-OCRv3_rec_infer.onnx"


def _engine() -> Any:
    global _ENGINE
    with _LOCK:
        if _ENGINE is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except Exception as exc:  # noqa: BLE001 - not installed / broken install
                raise OcrUnavailable(
                    "text-in-image reading is off: `uv pip install rapidocr-onnxruntime`"
                ) from exc
            _ENGINE = RapidOCR(rec_model_path=str(EN_REC)) if EN_REC.exists() else RapidOCR()
        return _ENGINE


def read_text(rgb: np.ndarray) -> str:
    """Lines of text in reading order (top to bottom, left to right), joined by newlines."""
    result, _ = _engine()(rgb)
    if not result:
        return ""
    boxes = sorted(result, key=lambda r: (round(min(p[1] for p in r[0]) / 12), r[0][0][0]))
    return "\n".join(str(r[1]) for r in boxes if str(r[1]).strip())
