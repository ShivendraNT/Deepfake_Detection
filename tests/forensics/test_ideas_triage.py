"""Tests for IDEAS #1 (batch triage, ranking, duplicate clustering) and #3 (signed annotations)."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, PngImagePlugin

from satyapan.forensics.locker import ForensicLocker
from satyapan.forensics.triage import (
    dhash,
    find_duplicate_groups,
    hamming,
    phash,
    similarity_thumb,
    triage_paths,
)


def _scene(seed: int, size: int = 192) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    # Each scene gets its own structure (frequency + bright object position), as real photos do.
    freq = 1.1 + 0.11 * seed
    cx, cy = 0.12 + 0.031 * seed, 0.18 + 0.027 * seed
    blob = 90.0 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / 0.02))
    lum = 45.0 + 110.0 * (0.5 * xx + 0.5 * yy) + 18.0 * np.sin(2.0 * np.pi * freq * xx) + blob
    tex = rng.normal(0.0, 3.5, (size, size)).astype(np.float32)
    shot = rng.normal(0.0, 1.0, (size, size)).astype(np.float32) * (0.3 * np.sqrt(lum))
    rgb = np.stack([lum + tex + shot, lum + tex + 0.9 * shot, lum * 0.95 + tex + shot], axis=-1)
    return np.clip(rgb, 10, 245).astype(np.uint8)


def _manipulated(seed: int, size: int = 192) -> np.ndarray:
    rgb = _scene(seed, size).astype(np.float32)
    grid = ((-1.0) ** (np.arange(size)[:, None] + np.arange(size)[None, :])).astype(np.float32)
    rgb[:, :, 0] += 4.0 * grid
    rgb[:, :, 1] -= 3.2 * grid
    obj = np.random.default_rng(seed + 1).integers(25, 230, (40, 40, 3), dtype=np.uint8)
    out = np.clip(rgb, 0, 255).astype(np.uint8)
    out[20:60, 20:60] = obj
    out[110:150, 110:150] = obj
    return out


def _jpeg_bytes(rgb: np.ndarray, quality: int = 70) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality, subsampling=2)
    return buf.getvalue()


def test_dhash_survives_reencode_and_hamming_is_a_distance() -> None:
    rgb = _scene(3)
    h1 = dhash(rgb)
    h2 = dhash(np.asarray(Image.open(io.BytesIO(_jpeg_bytes(rgb))).convert("RGB")))
    assert hamming(h1, h1) == 0
    assert hamming(h1, h2) <= 8


def test_find_duplicate_groups_pairs_only_the_copies() -> None:
    a, b = _scene(1), _scene(2)
    a_copy = np.asarray(Image.open(io.BytesIO(_jpeg_bytes(a, 60))).convert("RGB"))
    b_copy = np.asarray(Image.open(io.BytesIO(_jpeg_bytes(b, 80))).convert("RGB"))
    rgb = [a, b, a_copy, b_copy]
    groups = find_duplicate_groups([phash(x) for x in rgb], [similarity_thumb(x) for x in rgb])
    assert groups[0] == groups[2]
    assert groups[1] == groups[3]
    assert groups[0] != groups[1]


def test_triage_ranks_manipulated_above_authentic_and_clusters(tmp_path: Path) -> None:
    paths: list[Path] = []
    for i in range(2):
        auth = _scene(10 + i)
        p_auth = tmp_path / f"auth_{i}.png"
        Image.fromarray(auth).save(p_auth, format="PNG")
        paths.append(p_auth)
        p_copy = tmp_path / f"copy_{i}.jpg"
        p_copy.write_bytes(_jpeg_bytes(auth, 70))
        paths.append(p_copy)
    for i in range(2):
        manip = _manipulated(20 + i)
        p = tmp_path / f"manip_{i}.png"
        pi = PngImagePlugin.PngInfo()
        pi.add_text("parameters", "Stable Diffusion XL, Steps: 30")
        Image.fromarray(manip).save(p, format="PNG", pnginfo=pi)
        paths.append(p)

    rep = triage_paths(paths)
    assert rep["files_screened"] == 6
    assert rep["images_screened"] == 6

    by_name = {Path(it["path"]).name: it for it in rep["items"]}
    for i in range(2):
        assert (
            by_name[f"copy_{i}.jpg"]["duplicate_group"]
            == by_name[f"auth_{i}.png"]["duplicate_group"]
        )
        assert (
            by_name[f"auth_{i}.png"]["duplicate_group"]
            != by_name[f"auth_{1 - i}.png"]["duplicate_group"]
        )
        assert by_name[f"manip_{i}.png"]["risk"] > by_name[f"auth_{i}.png"]["risk"]

    # ranked output is sorted by risk
    risks = [it["risk"] for it in rep["items"]]
    assert risks == sorted(risks, reverse=True)
    assert rep["files_per_second"] is not None


def test_triage_reports_unreadable_files_instead_of_crashing(tmp_path: Path) -> None:
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"not an image at all")
    rep = triage_paths([bad])
    assert rep["files_screened"] == 1
    assert rep["items"][0]["finding"] == "unreadable"


def test_annotations_are_signed_and_tamper_evident(tmp_path: Path) -> None:
    locker = ForensicLocker(tmp_path / "case_annot", collector="examiner_meera")
    item = locker.intake_bytes(b"annotated-evidence-bytes", "clip.png", source_type="image")

    entry = locker.annotate(item.evidence_id, "Face outline suspect; requested original file.")
    assert entry.action == "annotation"
    assert "origin" in entry.notes
    entries = locker.custody_entries()
    assert [e.action for e in entries] == ["intake", "annotation"]
    assert locker.verify_all().ok is True

    # Empty notes are refused; editing the note breaks the chain.
    try:
        locker.annotate(item.evidence_id, "   ")
        raise AssertionError("empty annotation should raise")
    except ValueError:
        pass

    lines = locker.custody_file.read_text(encoding="utf-8").splitlines()
    import json as _json

    row = _json.loads(lines[-1])
    row["notes"] = "edited after signing"
    lines[-1] = _json.dumps(row, sort_keys=True)
    locker.custody_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rep = locker.verify_all()
    assert rep.ok is False
    assert 2 in rep.chain_breaks
