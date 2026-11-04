"""Measured evaluation of IDEAS #1 (batch triage) and #2 (near-duplicate clustering).

Seeded set (`SEED = 20261108`, labeled synthetic): 20 authentic camera-like scenes, 20 manipulated
scenes (copy-move + GAN grid + SD metadata), and 20 re-encoded copies of the 20 authentic scenes
(JPEG Q55..Q85, 4:2:0, metadata stripped). Ground truth: each copy is a near-duplicate of exactly
one authentic scene; the manipulated scenes are distinct.

Reports:
1. Duplicate clustering precision/recall over the 20 ground-truth pairs.
2. Risk ranking AUC on the 40 distinct-content images (authentic=0 / manipulated=1).
3. Triage throughput (files/second).
"""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from typing import Any

import numpy as np  # provenance: seeded-resampling-ok
from PIL import Image, PngImagePlugin

from satyapan.forensics.triage import triage_paths

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "results" / "forensics_ideas_triage.json"
SEED = 20261108


def _authentic(rng: np.random.Generator, seed: int, size: int = 192) -> np.ndarray:
    """Camera-like scene with seed-specific structure, so distinct photos are truly distinct."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    # Continuous (non-cyclic) parameters: every scene index is structurally unique, so the
    # "distinct" ground-truth label is actually true.
    freq = 1.1 + 0.11 * seed
    cx, cy = 0.12 + 0.031 * seed, 0.18 + 0.027 * seed
    blob = 90.0 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / 0.02))
    lum = 45.0 + 110.0 * (0.5 * xx + 0.5 * yy) + 18.0 * np.sin(2.0 * np.pi * freq * xx) + blob
    tex = rng.normal(0.0, 3.5, (size, size)).astype(np.float32)
    shot = rng.normal(0.0, 1.0, (size, size)).astype(np.float32) * (0.3 * np.sqrt(lum))
    rgb = np.stack([lum + tex + shot, lum + tex + 0.9 * shot, lum * 0.95 + tex + shot], axis=-1)
    return np.clip(rgb, 10, 245).astype(np.uint8)


def _manipulated(rng: np.random.Generator, seed: int, size: int = 192) -> np.ndarray:
    """A *structurally unique* generated scene, so "distinct" ground truth is true.

    Every generated image gets its own low-frequency layout (unique blob positions and base
    frequency) plus the generator grid, instead of one shared template.
    """
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    freq = 0.9 + 0.09 * seed
    cx, cy = 0.15 + 0.029 * seed, 0.2 + 0.024 * seed
    base = 110.0 + 70.0 * np.cos(2.0 * np.pi * freq * xx) * np.sin(2.0 * np.pi * freq * yy)
    base += 85.0 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / 0.025))
    grid = ((-1.0) ** (np.arange(size)[:, None] + np.arange(size)[None, :])).astype(np.float32)
    rgb = np.stack([base + 3.6 * grid, base - 3.0 * grid, base + 3.2 * grid], axis=-1)
    out = np.clip(rgb, 0, 255).astype(np.uint8)
    rng2 = np.random.default_rng(seed + 1000)
    obj = rng2.integers(25, 230, (40, 40, 3), dtype=np.uint8)
    y1 = int(rng2.integers(10, size // 2 - 50))
    y2 = int(rng2.integers(size // 2, size - 50))
    out[y1 : y1 + 40, y1 : y1 + 40] = obj
    out[y2 : y2 + 40, y2 : y2 + 40] = obj
    return out


def _roc_auc(y: list[int], s: list[float]) -> float:
    pos = [v for t, v in zip(y, s, strict=True) if t == 1]
    neg = [v for t, v in zip(y, s, strict=True) if t == 0]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for n in neg:
            wins += 1.0 if p > n else (0.5 if p == n else 0.0)
    return round(wins / (len(pos) * len(neg)), 4)


def run() -> dict[str, Any]:
    rng = np.random.default_rng(SEED)  # provenance: seeded-resampling-ok
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        source_names: list[str] = []
        manip_names: list[str] = []
        copy_to_source: dict[str, str] = {}

        for i in range(20):
            rgb = _authentic(rng, i)
            p = tdir / f"auth_{i:02d}.png"
            Image.fromarray(rgb).save(p, format="PNG")
            source_names.append(p.name)

        for i in range(20):
            rgb = _manipulated(rng, i)
            p = tdir / f"manip_{i:02d}.png"
            pi = PngImagePlugin.PngInfo()
            pi.add_text("parameters", "Stable Diffusion XL, Steps: 30, CFG scale: 7.0")
            Image.fromarray(rgb).save(p, format="PNG", pnginfo=pi)
            manip_names.append(p.name)

        for i in range(20):
            # Re-encode the saved source file: exactly the WhatsApp forwarding use case.
            src = tdir / source_names[i]
            with Image.open(src) as im:
                arr = np.asarray(im.convert("RGB"))
            q = int(rng.integers(55, 86))
            buf = io.BytesIO()
            Image.fromarray(arr).save(buf, format="JPEG", quality=q, subsampling=2)
            p = tdir / f"copy_{i:02d}.jpg"
            p.write_bytes(buf.getvalue())
            copy_to_source[p.name] = source_names[i]

        files = sorted(tdir.iterdir())
        report = triage_paths(files)
        by_name = {Path(it["path"]).name: it for it in report["items"]}

    # 1. Duplicate clustering: one predicted group per ground-truth pair.
    tp = 0
    for copy_name, src_name in copy_to_source.items():
        if by_name[copy_name]["duplicate_group"] == by_name[src_name]["duplicate_group"]:
            tp += 1
    # A false positive is any pair (outside the 20 true pairs) that shares a group.
    groups: dict[int, list[str]] = {}
    for name, it in by_name.items():
        g = it["duplicate_group"]
        if g:
            groups.setdefault(g, []).append(name)
    true_pairs = {frozenset((c, s)) for c, s in copy_to_source.items()}
    extra_pairs = 0
    for members in groups.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if frozenset((members[i], members[j])) not in true_pairs:
                    extra_pairs += 1
    pred_pairs = sum(len(m) * (len(m) - 1) // 2 for m in groups.values())
    precision = round(tp / pred_pairs, 4) if pred_pairs else 0.0
    recall = round(tp / len(true_pairs), 4)

    # 2. Risk ranking on distinct content (authentic originals vs manipulated).
    y = [0] * len(source_names) + [1] * len(manip_names)
    scores = [by_name[n]["risk"] for n in source_names] + [by_name[n]["risk"] for n in manip_names]
    auc = _roc_auc(y, scores)

    summary = {
        "idea": "batch triage + near-duplicate clustering",
        "seed": SEED,
        "files_screened": report["files_screened"],
        "seconds": report["seconds"],
        "files_per_second": report["files_per_second"],
        "duplicates": {
            "ground_truth_pairs": len(true_pairs),
            "true_positives": tp,
            "predicted_pairs": pred_pairs,
            "extra_pairs": extra_pairs,
            "precision": precision,
            "recall": recall,
        },
        "risk_ranking_auc": auc,
        "high_risk": report["high_risk"],
        "verify": report["verify"],
        "duplicate_groups": len(report["duplicate_groups"]),
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
