"""Photos and screenshots handed to Satya: face check + text in the image (finale)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest
from PIL import Image

from satyapan.contracts.enums import Channel, ReasonCode
from satyapan.contracts.signal_table import SIGNAL_TABLE
from satyapan.imagecheck import ocr
from satyapan.imagecheck.face import (
    ImageFaceChecker,
    ImageFaceThresholds,
    ImageFaceVerdict,
    decode_image,
)

IMAGE_CODES = (
    ReasonCode.IMAGE_FACE_NO_SIGNS,
    ReasonCode.IMAGE_FACE_INCONCLUSIVE,
    ReasonCode.IMAGE_FACE_LIKELY_SYNTHETIC,
)


def _png(w: int = 320, h: int = 240) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 110, 100)).save(buf, "PNG")
    return buf.getvalue()


@dataclass
class _Obs:
    pts: np.ndarray
    jaw_open: float = 0.0


class _Tracker:
    def __init__(self, size: float | None) -> None:
        self.size = size

    def track(self, frame: np.ndarray, t: float) -> Any:
        if self.size is None:
            return None
        pts = np.array([[100, 50], [100 + self.size, 50 + self.size]], np.float32)
        return _Obs(pts)

    def close(self) -> None:
        pass


class _Scorer:
    def __init__(self, logit: float) -> None:
        self.logit = logit

    def logits(self, crops: np.ndarray) -> np.ndarray:
        return np.full(len(crops), self.logit, np.float32)


def _checker(logit: float, face: float | None = 120.0) -> ImageFaceChecker:
    thr = ImageFaceThresholds(tau_hi=4.0, tau_lo=3.0, model_file="m.onnx", calibrated=False)
    return ImageFaceChecker(_Scorer(logit), thr, lambda: _Tracker(face))


@pytest.fixture(autouse=True)
def _no_cv2_crop(monkeypatch) -> None:
    import satyapan.video.observe as obs

    monkeypatch.setattr(obs, "face_crop", lambda rgb, pts: np.zeros((224, 224, 3), np.uint8))


def test_image_codes_are_ml_media_and_only_likely_raises() -> None:
    for code in IMAGE_CODES:
        spec = SIGNAL_TABLE[code]
        assert spec.group.value == "media"
    assert SIGNAL_TABLE[ReasonCode.IMAGE_FACE_LIKELY_SYNTHETIC].target.value == "PLUS_ONE"
    assert SIGNAL_TABLE[ReasonCode.IMAGE_FACE_NO_SIGNS].target.value == "NONE"
    assert SIGNAL_TABLE[ReasonCode.IMAGE_FACE_INCONCLUSIVE].target.value == "NONE"


@pytest.mark.parametrize(
    ("logit", "face", "code", "problem"),
    [
        (5.0, 120.0, ReasonCode.IMAGE_FACE_LIKELY_SYNTHETIC, None),
        (3.5, 120.0, ReasonCode.IMAGE_FACE_INCONCLUSIVE, None),
        (-2.0, 120.0, ReasonCode.IMAGE_FACE_NO_SIGNS, None),
        (9.0, 30.0, ReasonCode.IMAGE_FACE_INCONCLUSIVE, "face_too_small"),
        (9.0, None, ReasonCode.IMAGE_FACE_INCONCLUSIVE, "no_face"),
    ],
)
def test_face_verdicts(logit: float, face: float | None, code: ReasonCode, problem) -> None:
    v = _checker(logit, face).check(np.zeros((240, 320, 3), np.uint8))
    assert (v.code, v.problem) == (code, problem)


def test_not_an_image_is_a_parse_failure_never_a_pass() -> None:
    with pytest.raises(ValueError):
        decode_image(b"%PDF-1.4 not an image")


def test_images_are_routed_to_the_image_channel() -> None:
    from satyapan.api.companion.service import _channel_for

    assert _channel_for("whatsapp.png", "image/png") == Channel.IMAGE
    assert _channel_for("ceo.JPG", "") == Channel.IMAGE
    assert _channel_for(None, "image/webp") == Channel.IMAGE


def _run_image(master, monkeypatch, checker, ocr_text: str | None):
    from satyapan.contracts.case import Case
    from satyapan.contracts.common import utcnow
    from satyapan.contracts.enums import CaseKind
    from satyapan.contracts.evidence import Evidence
    from satyapan.pipeline import PipelineContext, analyze_evidence
    from satyapan.settings import Settings
    from satyapan.voice.rules import VoiceThresholds

    if ocr_text is None:

        def unavailable(rgb: np.ndarray) -> str:
            raise ocr.OcrUnavailable("off")

        monkeypatch.setattr(ocr, "read_text", unavailable)
    else:
        monkeypatch.setattr(ocr, "read_text", lambda rgb: ocr_text)
    data = _png()
    ev = Evidence(id="ev_img", case_id="case_img", channel=Channel.IMAGE, filename="x.png",
                  media_type="image/png", sha256="0" * 64, size_bytes=len(data),
                  captured_at=utcnow(), submitted_by="emp_priya",
                  storage_uri="file://vault_data/x")  # fmt: skip
    case = Case(id="case_img", title="t", kind=CaseKind.DATA_REQUEST, created_at=utcnow(),
                created_by="emp_priya")  # fmt: skip
    ctx = PipelineContext(
        master=master,
        settings=Settings(),
        image=checker,
        thresholds=VoiceThresholds(0.9, 0.6, "t"),
        live_phrasebook=True,
    )
    return analyze_evidence(data, ev, case, ctx)


def test_a_screenshot_is_read_and_its_asks_found(master, monkeypatch) -> None:
    out = _run_image(master, monkeypatch, None, "Share the OTP you just received to unblock")
    codes = {s.code for s in out.signals}
    assert ReasonCode.ASK_CREDENTIAL in codes
    assert out.artifacts["face_label"] == "not_analysed"


def test_a_swapped_face_raises_and_missing_ocr_is_said(master, monkeypatch) -> None:
    out = _run_image(master, monkeypatch, _checker(6.0), None)
    assert {s.code for s in out.signals} == {ReasonCode.IMAGE_FACE_LIKELY_SYNTHETIC}
    assert "off" in out.artifacts["ocr"]
    assert all(s.score is None or isinstance(s.score, float) for s in out.signals)


def test_verdict_type_is_frozen() -> None:
    v = ImageFaceVerdict(ReasonCode.IMAGE_FACE_NO_SIGNS, -1.0, 100.0, None)
    with pytest.raises(AttributeError):
        v.logit = 1.0  # type: ignore[misc]
