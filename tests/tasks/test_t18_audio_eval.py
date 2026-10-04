"""T18 acceptance: EER, speaker-disjoint split, thresholds; then the committed results."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from research.audio.channel_eval import Item, eer, fit_thresholds, speaker_disjoint_split
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
    p = require_artifact("results/audio_eval.csv", "T18")
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    assert {r["channel"] for r in rows} >= {"clean", "opus16k", "amrnb", "g711u"}
    assert all({"eer", "eer_low", "eer_high", "n_speakers", "n_items"} <= set(r) for r in rows)
    th = json.loads((ROOT / "config" / "voice_thresholds.json").read_text(encoding="utf-8"))
    assert th["calibrated"] is True and th["calibration_set_sha256"]
