"""T18 acceptance: EER, speaker-disjoint split, thresholds; then the committed results."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from research.audio.channel_eval import Item, eer, fit_thresholds, speaker_disjoint_split
from research.audio.run_audio_eval import (
    ManifestError,
    calibration_hash,
    validate_manifest,
)
from tests.helpers import ROOT, require_artifact

pytestmark = pytest.mark.task("T18")


def test_eer_separable_and_overlap() -> None:
    e, _ = eer([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
    assert e == pytest.approx(0.0, abs=1e-9)
    e2, _ = eer([0, 0, 0, 0, 1, 1, 1, 1], [0.1, 0.2, 0.3, 0.6, 0.4, 0.7, 0.8, 0.9])
    assert e2 == pytest.approx(0.25, abs=0.01)


def test_speaker_disjoint_split() -> None:
    items = [Item(Path(f"{s}_{i}.wav"), f"spk{s}", i % 2) for s in range(10) for i in range(4)]
    cal, test = speaker_disjoint_split(items, seed=1)
    assert {i.speaker for i in cal}.isdisjoint({i.speaker for i in test})
    assert len(cal) + len(test) == len(items)
    assert speaker_disjoint_split(items, seed=1) == (cal, test)


def test_fit_thresholds_on_uniform() -> None:
    scores = [i / 1000 for i in range(1000)]
    hi, lo = fit_thresholds(scores)
    assert hi == pytest.approx(0.99, abs=0.005) and lo == pytest.approx(0.95, abs=0.005)
    assert lo <= hi


def test_results_committed_and_thresholds_calibrated() -> None:
    # Provenance first (results/INVALIDATED.md): no manifest of real audio -> no result.
    mp = require_artifact("results/audio_eval_manifest.json", "T18")
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    validate_manifest(manifest)  # dataset, model_version, sha256 per file, disjoint speakers
    files = manifest["files"]
    test_files = [f for f in files if f["split"] == "test"]
    assert {int(f["label"]) for f in test_files} == {0, 1}, "test split needs bonafide + spoof"
    assert len({f["speaker"] for f in test_files}) >= 10

    p = require_artifact("results/audio_eval.csv", "T18")
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    assert {r["channel"] for r in rows} >= {"clean", "opus16k", "amrnb", "g711u"}
    assert all({"eer", "eer_low", "eer_high", "n_speakers", "n_items"} <= set(r) for r in rows)
    for r in rows:  # the CSV may only describe files that are in the manifest
        assert int(r["n_items"]) <= len(test_files)
        assert int(r["n_speakers"]) <= len({f["speaker"] for f in test_files})

    th = json.loads((ROOT / "config" / "voice_thresholds.json").read_text(encoding="utf-8"))
    assert th["calibrated"] is True
    assert th["calibration_set_sha256"] == calibration_hash(files)
    assert th["model_version"] == manifest["model_version"]


def _manifest(**over: object) -> dict[str, object]:
    files = [
        {
            "path": f"a{i}.wav",
            "sha256": f"{i:064x}",
            "speaker": f"s{i % 4}",
            "label": i % 2,
            "split": "cal" if i % 4 < 2 else "test",
            "source": "public",
        }
        for i in range(8)
    ]
    m: dict[str, object] = {"dataset": "x", "model_version": "m", "files": files}
    m["calibration_set_sha256"] = calibration_hash(files)
    m.update(over)
    return m


def test_manifest_guard_accepts_a_valid_manifest() -> None:
    validate_manifest(_manifest())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.update(dataset=""),
        lambda m: m.update(calibration_set_sha256="0" * 64),
        lambda m: m["files"][0].update(sha256="not-a-hash"),
        lambda m: m["files"][1].update(sha256=m["files"][0]["sha256"]),
        lambda m: m["files"][2].update(speaker="s0"),  # speaker leakage cal -> test
    ],
)
def test_manifest_guard_rejects_bad_manifests(mutate) -> None:  # type: ignore[no-untyped-def]
    m = _manifest()
    mutate(m)
    with pytest.raises(ManifestError):
        validate_manifest(m)


def test_runner_refuses_missing_audio(tmp_path: Path) -> None:
    from research.audio.run_audio_eval import main

    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(_manifest()), encoding="utf-8")
    with pytest.raises(ManifestError, match="missing audio file"):
        main(["--manifest", str(mp), "--data-root", str(tmp_path)])
