"""A judge-style test kit built from the open TEST sets, and the whole product's answers on it.

    python -m research.kit build [--out DIR]   # mixed kit, every file named by its truth
    python -m research.kit run   [--kit DIR]   # satya scan on it -> results/kit_scan.{csv,md}

The benchmarks score each model on its own. This is the other half of the test workflow: the
files a person would forward (messages, photos, videos, voice notes) go through the same quick
check as the Scam Check page, all detectors at once, and the band is graded against the file
name (`fake_…`/`scam_…` should be flagged, `real_…` should pass). Nothing here is fitted or
tuned; every item comes from a held-out test split (or DFDC, never used for fitting). The kit
stays OUTSIDE the repo (media); `kit_manifest.json` records each file's source and sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random  # provenance: seeded-resampling-ok
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "satyapan-data"
SEED = 20261024
N_TEXT, N_PHOTO, N_VOICE = 40, 20, 20  # per class


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def texts(out: Path, rng: random.Random) -> list[dict]:
    import pandas as pd

    from research.text.data import DATA as TEXT

    df = pd.read_parquet(TEXT / "table.parquet")
    test = df[df.split == "test"]
    rows = []
    for label, tag in ((1, "scam"), (0, "real")):
        pool = test[test.label == label]
        by_ds = {ds: g.index.tolist() for ds, g in pool.groupby("dataset")}
        for idx in by_ds.values():
            rng.shuffle(idx)
        picked: list[int] = []
        while len(picked) < N_TEXT and any(by_ds.values()):  # round-robin over the 7 sets
            for ds in sorted(by_ds):
                if by_ds[ds] and len(picked) < N_TEXT:
                    picked.append(by_ds[ds].pop())
        for i, ix in enumerate(picked):
            r = test.loc[ix]
            f = out / f"{tag}_text_{r.dataset}_{i:02d}.txt"
            f.write_text(str(r.text)[:5000], encoding="utf-8")  # the page takes 5,000 chars
            rows.append({"file": f.name, "source": f"text/{r.dataset}/test", "label": label})
    return rows


def photos(out: Path, rng: random.Random) -> list[dict]:
    from research.video.data import DATA as VIDEO
    from research.video.hf_baselines import items

    frames = VIDEO / "frames" / "orig"
    pool = [it for it in items() if it.split in ("test", "xtest")
            and (frames / (it.key.replace("/", "__") + ".jpg")).exists()]  # fmt: skip
    rows = []
    for label, tag in ((1, "fake"), (0, "real")):
        cand = sorted((it for it in pool if it.label == label), key=lambda it: it.key)
        for it in rng.sample(cand, min(N_PHOTO, len(cand))):
            src = frames / (it.key.replace("/", "__") + ".jpg")
            f = out / f"{tag}_photo_{it.key.replace('/', '_')}.jpg"
            shutil.copyfile(src, f)
            rows.append({"file": f.name, "source": f"video/{it.key} ({it.split}, frame)",
                         "label": label})  # fmt: skip
    return rows


def videos(out: Path, folder: Path) -> list[dict]:
    """Copy a folder of FF++/DFDC test videos, labelled by name (fake_/real_/ffpp_<method>_)."""
    rows = []
    for src in sorted(folder.glob("*.mp4")):
        n = src.stem
        label = 0 if n.startswith(("real_", "ffpp_real_")) else 1
        name = n.removeprefix("real_").removeprefix("fake_")
        f = out / f"{'real' if label == 0 else 'fake'}_video_{name}.mp4"
        shutil.copyfile(src, f)
        rows.append({"file": f.name, "source": f"video/{n}", "label": label})
    return rows


def voices(out: Path, rng: random.Random) -> list[dict]:
    import numpy as np
    import soundfile as sf

    from research.voice.data import load

    sp = load("test_itw")
    rows = []
    for label, tag in ((1, "fake"), (0, "real")):
        idx = sorted(np.flatnonzero(sp.labels == label).tolist())
        for i, ix in enumerate(rng.sample(idx, min(N_VOICE, len(idx)))):
            f = out / f"{tag}_voice_itw_{i:02d}.wav"
            sf.write(f, sp.audio[ix], 16000, subtype="PCM_16")
            rows.append({"file": f.name, "source": f"voice/in_the_wild/{sp.ids[ix]}",
                         "label": label})  # fmt: skip
    return rows


def build(out: Path, video_dir: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    rng = random.Random(SEED)
    rows = texts(out, rng) + photos(out, rng) + voices(out, rng)
    if video_dir.exists():
        rows += videos(out, video_dir)
    for r in rows:
        r["sha256"] = _sha(out / r["file"])
    (out / "kit_manifest.json").write_text(json.dumps({"seed": SEED, "files": rows}, indent=1))
    print(f"{len(rows)} files in {out}")


def run(kit: Path) -> None:
    from satyapan.check_cli import main as scan

    scan([str(kit), "--out", str(ROOT / "results" / "kit_scan")])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "run"])
    ap.add_argument("--out", "--kit", dest="kit", default=str(DATA / "kit"))
    ap.add_argument("--videos", default=str(DATA / "demo_kit" / "video"))
    a = ap.parse_args()
    if a.cmd == "build":
        build(Path(a.kit), Path(a.videos))
    else:
        run(Path(a.kit))


if __name__ == "__main__":
    main()
