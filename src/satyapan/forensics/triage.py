"""Batch triage for an evidence dump: rank files by forensic risk and cluster near-duplicates.

Typical use is *before* formal intake: a cyber cell receives 200 files and needs to know which
handful deserve an examiner's day. This module never seals anything and never writes findings;
`make triage F=FOLDER` prints a ranked table (and optionally a CSV).

Duplicate clustering uses **dHash** (difference hash) because byte hashes change on every re-encode.
Two images are in the same group when their pHash is within Hamming distance 40 and their 32x32
normalized correlation is at least 0.995; the exact
SHA-256 of every file is always printed so exact identity is still provable.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from satyapan.forensics.deepfake import score_whole_image
from satyapan.forensics.locker import sha256_file
from satyapan.forensics.provenance import analyze_provenance
from satyapan.forensics.tamper import analyze_image_tampering

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
DEFAULT_DUPLICATE_HAMMING = 40
DEFAULT_DUPLICATE_NCC = 0.995
RISK_VERIFY = 0.42
RISK_HIGH = 0.62


@dataclass
class TriageItem:
    path: str
    sha256: str
    source_type: str
    risk: float
    finding: str
    duplicate_group: int | None = None
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _to_gray(rgb: np.ndarray) -> np.ndarray:
    return 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]


def dhash(rgb: np.ndarray, hash_size: int = 8) -> int:
    """64-bit difference hash: sign of the horizontal gradient on a 9x8 grayscale thumbnail."""
    from PIL import Image

    small = Image.fromarray(rgb).convert("L").resize((hash_size + 1, hash_size))
    a = np.asarray(small, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).astype(np.uint64).ravel()
    out = 0
    for bit in bits:
        out = (out << 1) | int(bit)
    return int(out)


def ahash(rgb: np.ndarray, hash_size: int = 8) -> int:
    """64-bit average hash: pixel above the mean on an 8x8 grayscale thumbnail."""
    from PIL import Image

    small = Image.fromarray(rgb).convert("L").resize((hash_size, hash_size))
    a = np.asarray(small, dtype=np.float32)
    bits = (a > a.mean()).astype(np.uint64).ravel()
    out = 0
    for bit in bits:
        out = (out << 1) | int(bit)
    return int(out)


def _dct_matrix(n: int) -> np.ndarray:
    c = np.zeros((n, n), dtype=np.float32)
    for k in range(n):
        alpha = np.sqrt(1.0 / n) if k == 0 else np.sqrt(2.0 / n)
        for x in range(n):
            c[k, x] = alpha * np.cos(np.pi * (2 * x + 1) * k / (2.0 * n))
    return c


def phash(rgb: np.ndarray, hash_size: int = 16, sample: int = 32) -> int:
    """Perceptual DCT hash (255 bits at the default 16x16): robust to re-encoding, and more
    discriminative than a 9x8 spatial dHash on images that share a lighting gradient."""
    from PIL import Image

    g = np.asarray(
        Image.fromarray(rgb).convert("L").resize((sample, sample), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    c = _dct_matrix(sample)
    low = (c @ g @ c.T)[:hash_size, :hash_size].ravel()[1:]
    bits = (low > float(np.median(low))).astype(np.uint64)
    out = 0
    for bit in bits:
        out = (out << 1) | int(bit)
    return int(out)


def similarity_thumb(rgb: np.ndarray, size: int = 32) -> np.ndarray:
    """Zero-mean, unit-norm 32x32 grayscale thumbnail: dot product = normalized correlation."""
    from PIL import Image

    g = np.asarray(
        Image.fromarray(rgb).convert("L").resize((size, size), Image.Resampling.BILINEAR),
        dtype=np.float32,
    ).ravel()
    g = g - g.mean()
    return g / max(1e-6, float(np.linalg.norm(g)))


def hamming(a: int, b: int) -> int:
    """Number of differing bits between two 64-bit hashes."""
    return int((a ^ b).bit_count())


def find_duplicate_groups(
    hashes: list[int],
    thumbs: list[np.ndarray] | None = None,
    threshold: int = DEFAULT_DUPLICATE_HAMMING,
    ncc_threshold: float = DEFAULT_DUPLICATE_NCC,
) -> list[int]:
    """Union-find over perceptual hashes; returns a group id per item (1-based, first-seen).

    Two items are linked when their pHash distance is <= `threshold` and, when thumbnails are
    supplied, their normalized correlation is >= `ncc_threshold`. The correlation confirmation
    keeps a coarse hash from merging two different photos that share a lighting gradient.
    """
    n = len(hashes)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)

    for i in range(n):
        for j in range(i + 1, n):
            if hamming(hashes[i], hashes[j]) > threshold:
                continue
            if thumbs is not None and float(np.dot(thumbs[i], thumbs[j])) < ncc_threshold:
                continue
            union(i, j)

    groups: dict[int, int] = {}
    out: list[int] = []
    for i in range(n):
        root = find(i)
        if root not in groups:
            groups[root] = len(groups) + 1
        out.append(groups[root])
    return out


def _finding_for(risk: float) -> str:
    if risk >= RISK_HIGH:
        return "consistent_with_manipulation"
    if risk >= RISK_VERIFY:
        return "anomalies_detected_verify"
    return "consistent_with_authentic"


def triage_image(path: Path) -> tuple[float, list[str], dict[str, Any], int, np.ndarray]:
    """(risk, reasons, metrics, phash, correlation_thumbnail) for one image file."""
    from satyapan.imagecheck.face import decode_image

    raw = path.read_bytes()
    rgb = decode_image(raw)
    whole = score_whole_image(rgb, raw_bytes=raw)
    tamper = analyze_image_tampering(path)
    provenance = analyze_provenance(path)

    risk = max(
        float(whole["probability"]),
        float(tamper.tamper_probability),
        float(provenance.anomaly_score),
    )
    reasons: list[str] = []
    if float(tamper.tamper_probability) >= RISK_VERIFY:
        reasons.extend(tamper.why[:2])
    if float(whole["probability"]) >= RISK_VERIFY:
        reasons.append(
            f"whole-image synthetic likelihood {whole['probability']:.2f} "
            f"({whole['label']}, compression context "
            f"{whole['compression_context']['chroma_subsampling']}/Q"
            f"{whole['compression_context']['quality']})"
        )
    if float(provenance.anomaly_score) >= RISK_VERIFY:
        reasons.extend(provenance.why[:2])
    if not reasons:
        reasons.append("no manipulation indicators above threshold")

    metrics = {
        "whole_image": float(whole["probability"]),
        "tampering": float(tamper.tamper_probability),
        "provenance": float(provenance.anomaly_score),
        "source_attribution": provenance.source_attribution,
        "c2pa": provenance.c2pa.get("status"),
        "format": provenance.metadata.get("format"),
        "bytes": len(raw),
    }
    return risk, reasons, metrics, phash(rgb), similarity_thumb(rgb)


def triage_paths(
    paths: list[str | Path],
    *,
    duplicate_hamming: int = DEFAULT_DUPLICATE_HAMMING,
) -> dict[str, Any]:
    """Screen every path, rank by risk, and cluster near-duplicate images."""
    t0 = time.perf_counter()
    items: list[TriageItem] = []
    hashes: list[int] = []
    thumbs: list[np.ndarray] = []
    hash_slots: list[int] = []

    for raw_path in sorted(Path(p) for p in paths):
        if not raw_path.is_file():
            continue
        suffix = raw_path.suffix.lower()
        source_type = "image" if suffix in IMAGE_SUFFIXES else "other"
        if source_type != "image":
            items.append(
                TriageItem(
                    path=str(raw_path),
                    sha256=sha256_file(raw_path),
                    source_type=source_type,
                    risk=0.0,
                    finding="not_screened",
                    reasons=[
                        "batch triage currently screens images; use the case pipeline "
                        "for video/audio/document"
                    ],
                )
            )
            continue
        started = time.perf_counter()
        try:
            risk, reasons, metrics, ph, thumb = triage_image(raw_path)
        except Exception as exc:  # noqa: BLE001 - an unreadable file must not stop the dump
            items.append(
                TriageItem(
                    path=str(raw_path),
                    sha256=sha256_file(raw_path),
                    source_type=source_type,
                    risk=0.0,
                    finding="unreadable",
                    reasons=[f"could not analyse: {exc}"],
                )
            )
            continue
        hash_slots.append(len(items))
        hashes.append(ph)
        thumbs.append(thumb)
        metrics["phash"] = f"{ph:064x}"
        items.append(
            TriageItem(
                path=str(raw_path),
                sha256=sha256_file(raw_path),
                source_type=source_type,
                risk=round(risk, 4),
                finding=_finding_for(risk),
                reasons=reasons,
                metrics=metrics,
                seconds=round(time.perf_counter() - started, 3),
            )
        )

    groups = find_duplicate_groups(hashes, thumbs, threshold=duplicate_hamming)
    for slot, group in zip(hash_slots, groups, strict=True):
        items[slot].duplicate_group = group

    duplicates = {
        g: [items[s].path for s, gg in zip(hash_slots, groups, strict=True) if gg == g]
        for g in sorted(set(groups))
        if sum(1 for gg in groups if gg == g) > 1
    }

    ranked = sorted(items, key=lambda it: it.risk, reverse=True)
    elapsed = time.perf_counter() - t0
    return {
        "files_screened": len(items),
        "images_screened": len(hashes),
        "seconds": round(elapsed, 3),
        "files_per_second": round(len(items) / elapsed, 2) if elapsed > 0 else None,
        "high_risk": sum(1 for it in items if it.risk >= RISK_HIGH),
        "verify": sum(1 for it in items if RISK_VERIFY <= it.risk < RISK_HIGH),
        "duplicate_groups": {str(k): v for k, v in duplicates.items()},
        "items": [it.to_dict() for it in ranked],
    }
