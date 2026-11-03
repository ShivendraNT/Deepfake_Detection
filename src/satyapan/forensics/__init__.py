"""Forensic multimedia authentication, deepfake detection, tampering & provenance framework."""

from __future__ import annotations

from satyapan.forensics.deepfake import (
    DeepfakeAnalysisResult,
    analyze_audio_deepfake,
    analyze_image_deepfake,
    analyze_video_deepfake,
    extract_whole_image_features,
    score_whole_image,
)
from satyapan.forensics.locker import (
    GENESIS_LINK,
    CustodyEntry,
    ForensicEvidenceItem,
    ForensicLocker,
    VerifyReport,
)

__all__ = [
    "GENESIS_LINK",
    "CustodyEntry",
    "DeepfakeAnalysisResult",
    "ForensicEvidenceItem",
    "ForensicLocker",
    "VerifyReport",
    "analyze_audio_deepfake",
    "analyze_image_deepfake",
    "analyze_video_deepfake",
    "extract_whole_image_features",
    "score_whole_image",
]
