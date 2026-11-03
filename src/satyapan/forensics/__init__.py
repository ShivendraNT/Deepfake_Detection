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
from satyapan.forensics.tamper import (
    TamperAnalysisResult,
    analyze_audio_tampering,
    analyze_image_tampering,
    analyze_video_tampering,
    copy_move_analysis,
    double_jpeg_analysis,
    ela_analysis,
    noise_residual_analysis,
)

__all__ = [
    "GENESIS_LINK",
    "CustodyEntry",
    "DeepfakeAnalysisResult",
    "ForensicEvidenceItem",
    "ForensicLocker",
    "TamperAnalysisResult",
    "VerifyReport",
    "analyze_audio_deepfake",
    "analyze_audio_tampering",
    "analyze_image_deepfake",
    "analyze_image_tampering",
    "analyze_video_deepfake",
    "analyze_video_tampering",
    "copy_move_analysis",
    "double_jpeg_analysis",
    "ela_analysis",
    "extract_whole_image_features",
    "noise_residual_analysis",
    "score_whole_image",
]
