"""CLI for the audio channel evaluation. TASK T18 — docs/tasks/T18-audio-channel-eval.md.

REAL AUDIO ONLY. This script refuses to do anything unless it is given a data manifest that
lists every audio file it will use, with its sha256, and every hash matches the file on disk.
Nothing is written to results/ or config/ before that check passes.

    uv run python -m research.audio.run_audio_eval \
        --manifest results/audio_eval_manifest.json --data-root research/_data/audio

Manifest format (results/audio_eval_manifest.json; audio itself is git-ignored, never committed):
    {
      "dataset": "In-the-Wild subset + consented team Meet windows",
      "model_version": "pascu-xlsr-l7",
      "files": [
        {"path": "itw/0001.wav", "sha256": "<64 hex>", "speaker": "itw_017",
         "label": 0, "split": "cal", "source": "public"},
        ...
      ],
      "calibration_set_sha256": "<sha256 of the sorted sha256s of split=cal, label=0 files,
                                  joined with newlines>"
    }
label: 0 = bonafide, 1 = spoof. split: "cal" or "test" (speaker-disjoint).

History: an earlier version of this file generated scores with random.gauss and wrote them to
results/ as if measured. That output was withdrawn (results/INVALIDATED.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
REQUIRED_KEYS = ("dataset", "model_version", "files", "calibration_set_sha256")
FILE_KEYS = ("path", "sha256", "speaker", "label", "split", "source")


class ManifestError(ValueError):
    """The manifest is missing, malformed, or does not match the files on disk."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def calibration_hash(files: list[dict[str, Any]]) -> str:
    """sha256 over the sorted file hashes of the bonafide calibration files."""
    cal = sorted(f["sha256"] for f in files if f["split"] == "cal" and int(f["label"]) == 0)
    return hashlib.sha256("\n".join(cal).encode("utf-8")).hexdigest()


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Schema checks that do not need the audio (also used by the T18 acceptance test)."""
    missing = [k for k in REQUIRED_KEYS if not manifest.get(k)]
    if missing:
        raise ManifestError(f"manifest missing {missing}")
    files = manifest["files"]
    seen: set[str] = set()
    for f in files:
        if any(k not in f for k in FILE_KEYS):
            raise ManifestError(f"file entry lacks one of {FILE_KEYS}: {f}")
        digest = str(f["sha256"])
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ManifestError(f"bad sha256 for {f['path']}")
        if digest in seen:
            raise ManifestError(f"duplicate audio file {f['path']}")
        seen.add(digest)
        if int(f["label"]) not in (0, 1) or f["split"] not in ("cal", "test"):
            raise ManifestError(f"bad label/split for {f['path']}")
    cal_spk = {f["speaker"] for f in files if f["split"] == "cal"}
    test_spk = {f["speaker"] for f in files if f["split"] == "test"}
    if cal_spk & test_spk:
        raise ManifestError(f"speakers in both splits: {sorted(cal_spk & test_spk)[:5]}")
    if manifest["calibration_set_sha256"] != calibration_hash(files):
        raise ManifestError("calibration_set_sha256 does not match the calibration files")


def verify_on_disk(manifest: dict[str, Any], data_root: Path) -> None:
    """Every listed file must exist under data_root and hash to the listed sha256."""
    for f in manifest["files"]:
        p = data_root / f["path"]
        if not p.is_file():
            raise ManifestError(f"missing audio file {p}")
        if sha256_file(p) != f["sha256"]:
            raise ManifestError(f"sha256 mismatch for {p}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, default=ROOT / "research" / "_data" / "audio")
    args = ap.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    verify_on_disk(manifest, args.data_root)
    raise NotImplementedError(
        "T18: see docs/tasks/T18-audio-channel-eval.md - score the verified files with the "
        "T17 ONNX detector through reencode() per channel, then bootstrap_eer_by_speaker() and "
        "fit_thresholds() on split=cal bonafide only. Write results only from real scores."
    )


if __name__ == "__main__":
    main()
