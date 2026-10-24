"""Training data for the blend-artifact CNN: loose face crops + landmarks from REAL videos.

    python -m research.video.sbi_prep --workers 4

For each real video in the `sbi_train` role (480 FF++ train reals) and the `val` role
(140 FF++ val reals, for model selection), 16 (train) / 8 (val) frames spread evenly over
the whole video are landmarked; a loose square crop (2x the face box) is saved at 320 px with
the landmarks mapped into it. No fake video is ever read here.
"""

from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from research.video.data import DATA, Item, ffpp_items

LOOSE = 2.0
SIZE = 320
OUT = DATA / "sbi"


def loose_crop(frame: np.ndarray, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    import cv2

    from satyapan.video.regions import face_box

    x0, y0, x1, y1 = face_box(pts)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = max(x1 - x0, y1 - y0) * LOOSE
    s = SIZE / side
    m = np.array([[s, 0, -(cx - side / 2) * s], [0, s, -(cy - side / 2) * s]], np.float32)
    crop = cv2.warpAffine(
        frame,
        m,
        (SIZE, SIZE),
        flags=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    lm = pts @ m[:, :2].T + m[:, 2]
    return crop, lm.astype(np.float32)


def prep_one(job: tuple[Item, int]) -> tuple[str, int]:
    import cv2

    from satyapan.video.landmarks import FaceTracker

    item, n = job
    out = OUT / (item.key.replace("/", "__") + ".npz")
    if out.exists():
        return item.key, -1
    cap = cv2.VideoCapture(str(DATA / item.path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    want = set(np.linspace(0, max(total - 1, 0), n).astype(int).tolist())
    crops, lms = [], []
    with FaceTracker(still_images=True, max_faces=3) as tracker:
        i = 0
        while i <= max(want):
            if i in want:
                ok, bgr = cap.read()
                if not ok:
                    break
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                obs = tracker.track(rgb, 0.0)
                if obs is not None:
                    c, lm = loose_crop(rgb, obs.pts)
                    crops.append(
                        cv2.imencode(
                            ".jpg",
                            cv2.cvtColor(c, cv2.COLOR_RGB2BGR),
                            [cv2.IMWRITE_JPEG_QUALITY, 98],
                        )[1]
                    )
                    lms.append(lm)
            elif not cap.grab():
                break
            i += 1
    cap.release()
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = np.zeros(0, np.uint8)
    offsets = [0]
    for c in crops:
        blob = np.concatenate([blob, c.ravel()])
        offsets.append(len(blob))
    np.savez(
        out,
        jpg=blob,
        offsets=np.array(offsets),
        lms=np.array(lms, np.float32),
        identity=item.identity,
        split=item.split,
    )
    return item.key, len(crops)


def load_prepped(path: Path) -> tuple[list[np.ndarray], np.ndarray, str]:
    """(RGB crops, landmarks (n, 478, 2), split)."""
    import cv2

    z = np.load(path)
    crops = []
    for a, b in zip(z["offsets"][:-1], z["offsets"][1:], strict=True):
        bgr = cv2.imdecode(z["jpg"][a:b], cv2.IMREAD_COLOR)
        crops.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    return crops, z["lms"], str(z["split"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    items = [i for i in ffpp_items() if i.label == 0 and i.split in ("sbi_train", "val")]
    jobs = [(i, 16 if i.split == "sbi_train" else 8) for i in items]
    counts = {}
    with Pool(args.workers) as pool:
        for k, (key, n) in enumerate(pool.imap_unordered(prep_one, jobs), 1):
            counts[key] = n
            if k % 50 == 0:
                print(f"{k}/{len(jobs)}", flush=True)
    (OUT / "summary.json").write_text(json.dumps(counts, indent=1))
    print("frames:", sum(v for v in counts.values() if v > 0))


if __name__ == "__main__":
    main()
