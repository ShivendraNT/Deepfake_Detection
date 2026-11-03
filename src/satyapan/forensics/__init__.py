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
from satyapan.forensics.pipeline import (
    analyze_case,
    analyze_evidence_item,
    infer_source_and_media_type,
    load_case_analysis,
    seed_demo_forensic_case,
)
from satyapan.forensics.provenance import (
    ProvenanceAnalysisResult,
    analyze_provenance,
    attribute_compression_source,
    embed_c2pa_jumbf_manifest,
    extract_and_verify_metadata,
    verify_c2pa_credentials,
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
    "ProvenanceAnalysisResult",
    "TamperAnalysisResult",
    "VerifyReport",
    "analyze_audio_deepfake",
    "analyze_audio_tampering",
    "analyze_case",
    "analyze_evidence_item",
    "analyze_image_deepfake",
    "analyze_image_tampering",
    "analyze_provenance",
    "analyze_video_deepfake",
    "analyze_video_tampering",
    "attribute_compression_source",
    "copy_move_analysis",
    "double_jpeg_analysis",
    "ela_analysis",
    "embed_c2pa_jumbf_manifest",
    "extract_and_verify_metadata",
    "extract_whole_image_features",
    "infer_source_and_media_type",
    "load_case_analysis",
    "noise_residual_analysis",
    "score_whole_image",
    "seed_demo_forensic_case",
    "verify_c2pa_credentials",
]
