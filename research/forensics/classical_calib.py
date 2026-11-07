"""Calibrate the classical tampering detectors on genuine photographs (pre-registered).

    uv run python -m research.forensics.classical_calib

Genuine images: MS COCO photographs from the Defactify validation shard (calibration) and
test shard (held-out check). Forgeries are made from them with fixed seeds:
  * copy-move: a 48-128 px patch copied elsewhere in the same image, saved at q 85-95;
  * splice: a 64-160 px patch from another photograph, pre-compressed at q 50-70, pasted,
    saved at q 85-95;
  * crop-recompress: compressed at q 60-80, cropped by 1-7 px, saved at q 90.
Rule: thresholds weak / moderate / strong = the 98th / 99.5th / 99.9th percentile of each
statistic on the calibration reals (strong = 1.05 x max when n < 1000). Detection rates are
reported on the held-out forgeries, never used to tune.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from research.forensics.aigen_select import TEST, VAL

ROOT = Path(__file__).resolve().parents[2]
OUT_CFG = ROOT / "config" / "forensic_thresholds.json"
OUT_RES = ROOT / "results" / "forensics_classical.json"
STATS = ("ela", "noise", "copymove", "grid_shift", "grid_second")


def reals(path: Path, n: int, seed: int) -> list[bytes]:
    import pyarrow.parquet as pq

    tab = pq.read_table(path, columns=["Image", "Label_B"])
    lb = np.array(tab.column("Label_B").to_pylist())
    idx = np.random.default_rng(seed).choice(np.where(lb == 0)[0], size=n, replace=False)
    col = tab.column("Image")
    return [col[int(i)].as_py()["bytes"] for i in sorted(idx)]


def jpeg(arr: np.ndarray, q: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=int(q))
    return buf.getvalue()


def dec(b: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(b)).convert("RGB")).copy()


def copy_move(b: bytes, rng: np.random.Generator) -> bytes:
    img = dec(b)
    h, w = img.shape[:2]
    s = int(rng.integers(48, min(129, h // 3, w // 3)))
    for _ in range(20):
        y0, x0 = rng.integers(0, h - s), rng.integers(0, w - s)
        y1, x1 = rng.integers(0, h - s), rng.integers(0, w - s)
        if abs(int(y0) - int(y1)) > s or abs(int(x0) - int(x1)) > s:
            break
    img[y1 : y1 + s, x1 : x1 + s] = img[y0 : y0 + s, x0 : x0 + s]
    return jpeg(img, int(rng.integers(85, 96)))


def splice(b: bytes, donor: bytes, rng: np.random.Generator) -> bytes:
    img = dec(b)
    don = dec(jpeg(dec(donor), int(rng.integers(50, 71))))
    h, w = img.shape[:2]
    s = int(rng.integers(64, min(161, h // 2, w // 2, don.shape[0] // 2, don.shape[1] // 2)))
    y0, x0 = rng.integers(0, don.shape[0] - s), rng.integers(0, don.shape[1] - s)
    y1, x1 = rng.integers(0, h - s), rng.integers(0, w - s)
    img[y1 : y1 + s, x1 : x1 + s] = don[y0 : y0 + s, x0 : x0 + s]
    return jpeg(img, int(rng.integers(85, 96)))


def crop_recompress(b: bytes, rng: np.random.Generator) -> bytes:
    img = dec(jpeg(dec(b), int(rng.integers(60, 81))))
    dy, dx = int(rng.integers(1, 8)), int(rng.integers(1, 8))
    return jpeg(img[dy:, dx:], 90)


def stats(b: bytes) -> dict[str, float]:
    from satyapan.forensics.image import pixel_techniques as P

    rgb = dec(b)
    gray = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    out: dict[str, float] = {}
    out["ela"] = float(P.ela_stats(rgb, gray)["score"])
    ns = P.noise_stats(gray)
    out["noise"] = float(ns["score"]) if ns else 0.0
    import cv2

    g8 = cv2.cvtColor(rgb if max(rgb.shape[:2]) <= P.CM_MAX_SIDE else cv2.resize(
        rgb, None, fx=P.CM_MAX_SIDE / max(rgb.shape[:2]), fy=P.CM_MAX_SIDE / max(rgb.shape[:2])),
        cv2.COLOR_RGB2GRAY)  # fmt: skip
    cl = P.copy_move_clusters(g8)
    H, W = g8.shape
    sizes = sorted((c["pairs"] for c in cl), reverse=True)
    best = 0.0
    for c in cl:
        dominant = len(sizes) < 2 or c["pairs"] >= 2 * sizes[1] or (c is cl[0] and c["pairs"] >= 40)
        if c["spread"] < 0.25 * max(H, W) and (dominant or c["pairs"] >= 30):
            best = max(best, float(c["pairs"]))
    out["copymove"] = best
    sh, se = P.grid_scores(P.blocking_profile(gray))
    out["grid_shift"], out["grid_second"] = sh, se
    return out


def run(images: list[bytes]) -> dict[str, np.ndarray]:
    rows = [stats(b) for b in images]
    return {k: np.array([r[k] for r in rows]) for k in STATS}


def main() -> None:
    rng = np.random.default_rng(20261107)
    cal = reals(VAL, 300, 1)
    test = reals(TEST, 300, 2)
    print(f"calibration reals {len(cal)}, test reals {len(test)}", flush=True)
    s_cal = run(cal)
    thr: dict[str, dict[str, float]] = {}
    for k in STATS:
        v = s_cal[k]
        strong = float(np.quantile(v, 0.999)) if len(v) >= 1000 else float(v.max()) * 1.05
        thr[k] = {"weak": float(np.quantile(v, 0.98)), "moderate": float(np.quantile(v, 0.995)),
                  "strong": max(strong, float(np.quantile(v, 0.995)) + 1e-6)}  # fmt: skip
        floor = {"ela": 4.0, "noise": 4.0, "copymove": 10.0, "grid_shift": 0.15,
                 "grid_second": 0.5}[k]  # fmt: skip
        for lv in thr[k]:
            thr[k][lv] = max(thr[k][lv], floor)
    print("thresholds", json.dumps(thr, indent=1), flush=True)
    forg = {
        "copy_move": [copy_move(b, rng) for b in test[:150]],
        "splice": [splice(b, test[(i + 7) % len(test)], rng) for i, b in enumerate(test[:150])],
        "crop_recompress": [crop_recompress(b, rng) for b in test[150:300]],
    }
    s_test = run(test)
    res = {"rule": __doc__.split("Rule:")[1].strip(), "n_calibration_reals": len(cal),
           "n_test_reals": len(test), "thresholds": thr, "test_fpr": {}, "test_tpr": {}}  # fmt: skip
    for k in STATS:
        res["test_fpr"][k] = {lv: float((s_test[k] >= thr[k][lv]).mean()) for lv in thr[k]}
    for name, imgs in forg.items():
        s = run(imgs)
        res["test_tpr"][name] = {k: {lv: float((s[k] >= thr[k][lv]).mean()) for lv in thr[k]}
                                 for k in STATS}  # fmt: skip
        anyd = np.zeros(len(imgs), bool)
        for k in STATS:
            anyd |= s[k] >= thr[k]["moderate"]
        res["test_tpr"][name]["any_moderate"] = float(anyd.mean())
        print(name, json.dumps(res["test_tpr"][name]), flush=True)
    anyf = np.zeros(len(test), bool)
    for k in STATS:
        anyf |= s_test[k] >= thr[k]["moderate"]
    res["test_fpr"]["any_moderate"] = float(anyf.mean())
    print("test FPR", json.dumps(res["test_fpr"]), flush=True)
    OUT_RES.write_text(json.dumps(res, indent=1))
    OUT_CFG.write_text(json.dumps({
        "_note": "Classical tampering detector operating points; research/forensics/classical_calib.py",
        "thresholds": thr,
        "fpr": {"weak": 0.02, "moderate": 0.005, "strong": 0.001},
        "calibration_set": "300 MS COCO photographs (Defactify validation shard)",
    }, indent=1))  # fmt: skip
    print("wrote", OUT_CFG, OUT_RES)


if __name__ == "__main__":
    main()
