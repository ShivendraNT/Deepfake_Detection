"""Per-frame extraction over a dataset (the expensive pass). Writes one .npz (+ one .jpg
mosaic of face crops) per video under $SATYAPAN_VIDEO_DATA/frames/<condition>/.

    python -m research.video.extract --sets ffpp dfdc --condition orig --workers 4

Conditions (docs/VIDEO_DEEPFAKE.md §6, the call channel):
  orig     the file as distributed (FF++ c23 = H.264 at CRF 23; DFDC = phone/camera H.264)
  call720  VP8 (WebRTC's default) at 1.2 Mbit/s, <= 1280x720, then JPEG q85 per frame (the
           screen-capture hop from Satya's capture window to the local engine)
  call360  VP8 at 0.4 Mbit/s, <= 640x360 (a congested call), then JPEG q85
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import traceback
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from research.video.data import DATA, Item, dfdc_items, ffpp_items

MAX_SECONDS = 9.2  # two 6 s windows (0-6, 3-9): enough for the 2-in-a-row rule
CONDITIONS = {
    "orig": None,
    "call720": {"w": 1280, "h": 720, "kbps": 1200},
    "call360": {"w": 640, "h": 360, "kbps": 400},
}
MOSAIC_COLS = 4


def out_paths(item: Item, condition: str) -> tuple[Path, Path]:
    base = DATA / "frames" / condition / item.key.replace("/", "__")
    return base.with_suffix(".npz"), base.with_suffix(".jpg")


def transcode(src: Path, cond: dict[str, int], dst: Path) -> None:
    vf = (
        f"scale='min({cond['w']},iw)':'min({cond['h']},ih)':force_original_aspect_ratio="
        "decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2"
    )
    k = cond["kbps"]
    # -threads 1: parallel workers already use every core; threaded libvpx thrashes (7x slower).
    cmd = [
        "ffmpeg", "-v", "error", "-y", "-threads", "1", "-t", str(MAX_SECONDS + 0.5),
        "-i", str(src), "-vf", vf,
        "-c:v", "libvpx", "-threads", "1", "-b:v", f"{k}k", "-minrate", f"{k}k",
        "-maxrate", f"{k}k", "-bufsize", f"{k // 2}k", "-deadline", "realtime",
        "-cpu-used", "8", "-lag-in-frames", "0", "-error-resilient", "1",
        "-c:a", "libopus", "-b:a", "32k", "-ar", "48000", "-ac", "1", str(dst),
    ]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)


def read_audio(path: Path, sr: int = 16000) -> np.ndarray | None:
    cmd = ["ffmpeg", "-v", "error", "-t", str(MAX_SECONDS), "-i", str(path), "-vn", "-ac", "1",
           "-ar", str(sr), "-f", "f32le", "-"]  # fmt: skip
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or len(proc.stdout) < sr * 4:
        return None
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def decode(path: Path, jpeg_q: int | None):
    import cv2

    from satyapan.video.features import ANALYSIS_FPS

    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    stride = max(1, int(round(fps / ANALYSIS_FPS)))
    i = 0
    try:
        while True:
            t = i / fps
            if t > MAX_SECONDS:
                break
            if i % stride == 0:
                ok, bgr = cap.read()
                if not ok:
                    break
                if jpeg_q is not None:
                    ok2, enc = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_q])
                    bgr = cv2.imdecode(enc, cv2.IMREAD_COLOR)
                yield t, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            elif not cap.grab():
                break
            i += 1
    finally:
        cap.release()


def extract_one(args: tuple[Item, str]) -> tuple[str, str]:
    item, condition = args
    import cv2

    from satyapan.video.features import CROP_EVERY_S
    from satyapan.video.landmarks import FaceTracker
    from satyapan.video.observe import observe
    from satyapan.video.regions import PATCHES

    npz_path, jpg_path = out_paths(item, condition)
    if npz_path.exists():
        return item.key, "skip"
    src = DATA / item.path
    cond = CONDITIONS[condition]
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        video = src
        if cond is not None:
            video = Path(tmp) / "call.webm"
            transcode(src, cond, video)
        audio = read_audio(video)
        records = []
        next_crop = 0.0
        with FaceTracker() as tracker:
            for t, rgb in decode(video, 85 if cond is not None else None):
                obs = tracker.track(rgb, t)
                want = obs is not None and t >= next_crop
                rec = observe(
                    rgb, t, obs.pts if obs else None, obs.jaw_open if obs else 0.0, want_crop=want
                )
                if want:
                    next_crop = t + CROP_EVERY_S
                records.append(rec)
    if not records:
        return item.key, "no_frames"
    nan3 = (np.nan,) * 3
    crops = [(r.t, r.crop) for r in records if r.crop is not None]
    arrays = {
        "t": np.array([r.t for r in records], np.float32),
        "found": np.array([r.found for r in records], bool),
        "face_w": np.array([r.face_w for r in records], np.float32),
        "luma": np.array([r.luma for r in records], np.float32),
        "patches": np.array(
            [[r.patches.get(p, nan3) if r.found else nan3 for p in PATCHES] for r in records],
            np.float32,
        ),
        "spec": np.array([r.spec for r in records], np.float32),
        "iris_r": np.array([r.iris_r for r in records], np.float32),
        "mouth": np.array([r.mouth for r in records], np.float32),
        "jaw_open": np.array([r.jaw_open for r in records], np.float32),
        "crop_t": np.array([c[0] for c in crops], np.float32),
        "audio": audio if audio is not None else np.zeros(0, np.float32),
    }
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    if crops:
        rows = (len(crops) + MOSAIC_COLS - 1) // MOSAIC_COLS
        size = crops[0][1].shape[0]
        mosaic = np.zeros((rows * size, MOSAIC_COLS * size, 3), np.uint8)
        for k, (_, c) in enumerate(crops):
            r, col = divmod(k, MOSAIC_COLS)
            mosaic[r * size : (r + 1) * size, col * size : (col + 1) * size] = c
        cv2.imwrite(
            str(jpg_path), cv2.cvtColor(mosaic, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 98]
        )
    np.savez_compressed(npz_path, **arrays)
    return item.key, f"ok {len(records)} frames {len(crops)} crops {time.time() - t0:.1f}s"


def select(sets: list[str], splits: list[str] | None) -> list[Item]:
    items: list[Item] = []
    if "ffpp" in sets:
        items += ffpp_items()
    if "dfdc" in sets:
        items += dfdc_items()
    if splits:
        items = [i for i in items if i.split in splits]
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", nargs="+", default=["ffpp"])
    ap.add_argument("--splits", nargs="*")
    ap.add_argument("--condition", default="orig", choices=sorted(CONDITIONS))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--reverse", action="store_true", help="work from the end (a 2nd runner)")
    ap.add_argument(
        "--val-reals-only",
        action="store_true",
        help="from the val split keep only real videos (threshold checks)",
    )
    args = ap.parse_args()
    items = select(args.sets, args.splits)
    if args.val_reals_only:
        items = [i for i in items if not (i.split == "val" and i.label == 1)]
    if args.reverse:
        items = items[::-1]
    if args.limit:
        items = items[: args.limit]
    log = DATA / "logs" / f"extract_{args.condition}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    jobs = [(it, args.condition) for it in items]
    print(f"{len(jobs)} videos, condition={args.condition}", flush=True)
    done = 0
    with Pool(args.workers, maxtasksperchild=50) as pool, log.open("a") as fh:
        for key, status in pool.imap_unordered(_safe, jobs):
            done += 1
            fh.write(json.dumps({"key": key, "status": status}) + "\n")
            fh.flush()
            if done % 50 == 0 or not status.startswith(("ok", "skip")):
                print(f"{done}/{len(jobs)} {key} {status}", flush=True)


def _safe(job: tuple[Item, str]) -> tuple[str, str]:
    try:
        return extract_one(job)
    except Exception:  # noqa: BLE001 - one broken file must not stop the run; it is logged
        return job[0].key, "error " + traceback.format_exc(limit=2).replace("\n", " | ")


if __name__ == "__main__":
    sys.exit(main())
