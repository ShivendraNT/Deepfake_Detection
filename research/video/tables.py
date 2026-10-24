"""Window table: one row per (video, window) with coverage, all cue features and the CNN
crop logits. Built from the per-frame extraction (cheap; no video decoding).

    python -m research.video.tables --condition orig

Writes $SATYAPAN_VIDEO_DATA/tables/<condition>.csv. The CNN is run once per crop mosaic and
cached in $SATYAPAN_VIDEO_DATA/logits/<condition>/.
"""

from __future__ import annotations

import argparse
import csv
import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from research.video.data import DATA, Item, dfdc_items, ffpp_items
from research.video.extract import out_paths
from research.video.records import load_crops, load_records

TABLES = DATA / "tables"
LOGITS = DATA / "logits"
META = ("key", "condition", "split", "source", "method", "label", "identity", "w_index",
        "t_start", "seconds", "face_fraction", "face_px", "luma", "usable", "problem")  # fmt: skip


BLEND = "blend"  # our SBI CNN; any other name is an hf_baselines model (cached logits)


def table_path(condition: str, cnn: str = BLEND) -> Path:
    return TABLES / (f"{condition}.csv" if cnn == BLEND else f"{condition}__{cnn}.csv")


def external_logits(item: Item, condition: str, cnn: str, crop_t: np.ndarray):
    """(crop times, logits) of an hf_baselines model: K evenly spaced crops, as scored."""
    from research.video.hf_baselines import cache_path, pick

    f = cache_path(cnn, condition, item)
    if not f.exists():
        return crop_t[:0], None
    return crop_t[pick(len(crop_t))], np.load(f)


def crop_logits(item: Item, condition: str, n: int) -> np.ndarray | None:
    """CNN logits for the n crops of one video (cached). None if no model yet."""
    from satyapan.video.cnn import BlendScorer
    from satyapan.video.landmarks import VideoUnavailable

    cache = LOGITS / condition / (item.key.replace("/", "__") + ".npy")
    if cache.exists():
        return np.load(cache)
    if n == 0:
        return np.zeros(0, np.float32)
    global _SCORER
    try:
        if _SCORER is None:
            _SCORER = BlendScorer(threads=1)
    except VideoUnavailable:
        return None
    _, jpg = out_paths(item, condition)
    logits = _SCORER.logits(load_crops(jpg, n))
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, logits)
    return logits


_SCORER = None


def rows_for(job: tuple[Item, str, str]) -> list[dict[str, object]]:
    from satyapan.video.features import coverage, window_features, windows

    item, condition, cnn = job
    npz, _ = out_paths(item, condition)
    if not npz.exists():
        return []
    recs, crop_t, audio = load_records(npz)
    if cnn == BLEND:
        logits = crop_logits(item, condition, len(crop_t))
    else:
        crop_t, logits = external_logits(item, condition, cnn, crop_t)
    rows = []
    for w, (s, e) in enumerate(windows(recs[0].t, recs[-1].t + 1e-6)):
        win = [r for r in recs if s <= r.t < e]
        cov = coverage(win)
        sel = (crop_t >= s) & (crop_t < e)
        lw = [] if logits is None else [float(x) for x in logits[sel]]
        feats = window_features(win, audio, 16000, 0.0, lw)
        row: dict[str, object] = {
            "key": item.key, "condition": condition, "split": item.split,
            "source": item.source, "method": item.method, "label": item.label,
            "identity": item.identity, "w_index": w, "t_start": s,
            "seconds": round(cov.seconds, 3), "face_fraction": round(cov.face_fraction, 3),
            "face_px": round(cov.face_px, 1), "luma": round(cov.luma, 1),
            "usable": int(cov.usable), "problem": cov.problem() or "",
        }  # fmt: skip
        row.update({k: (v if math.isfinite(v) else "") for k, v in feats.items()})
        rows.append(row)
    return rows


def items_for(condition: str) -> list[Item]:
    items = [i for i in ffpp_items() if i.split != "sbi_train"] + dfdc_items()
    return [i for i in items if out_paths(i, condition)[0].exists()]


def build(condition: str, workers: int, cnn: str = BLEND) -> Path:
    items = items_for(condition)
    with Pool(workers) as pool:
        chunks = pool.map(rows_for, [(i, condition, cnn) for i in items], chunksize=8)
    rows = [r for c in chunks for r in c]
    TABLES.mkdir(parents=True, exist_ok=True)
    out = table_path(condition, cnn)
    from satyapan.video.features import FEATURES

    cols = list(META) + list(FEATURES) + ["speech_frac"]
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    print(f"{out}: {len(rows)} windows from {len(items)} videos")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", default="orig")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cnn", default=BLEND, help="blend, or an hf_baselines model name")
    args = ap.parse_args()
    build(args.condition, args.workers, args.cnn)


if __name__ == "__main__":
    main()
