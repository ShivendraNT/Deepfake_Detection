"""Dataset manifests and downloads for the video benchmark.

Every evaluation set is a list of `Item`s: one video (or one frame sequence) with a label,
an identity (for identity-disjoint splitting and cluster bootstrap), a split and a source.
Selections that subsample are seeded, so a rerun picks exactly the same files.

Sources (all public research datasets; terms in docs/DATA_POLICY.md):
- FaceForensics++ c23 (Rossler et al. 2019), official identity-disjoint splits from
  github.com/ondyari/FaceForensics (dataset/splits/*.json). Files come from the public HF
  mirror `gonnerthetooner/FaceForensics` (a copy of Kaggle `xdxd003/ff-c23`); the original
  FF++ terms (non-commercial research) apply.
- DFDC (Dolhansky et al. 2020), train parts 0-2 from the HF mirror
  `gonnerthetooner/DFDC-extracted-full`; labels from each part's metadata.json. Paid, consenting
  actors. Never used for training or threshold fitting (cross-dataset test only).
"""

from __future__ import annotations

import hashlib
import json
import os
import random  # provenance: seeded-resampling-ok
import shutil
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Media never lives inside the repo tree, not even git-ignored (tests/contracts/test_fixtures.py,
# docs/DATA_POLICY.md): videos, frames and crops go next to the checkout by default.
DATA = Path(os.environ.get("SATYAPAN_VIDEO_DATA", str(ROOT.parent / "satyapan-data" / "video")))
SEED = 20261024

FFPP_REPO = "gonnerthetooner/FaceForensics"
FFPP_PREFIX = "faceforensics_c23/FaceForensics++_C23"
FFPP_SPLITS = "https://raw.githubusercontent.com/ondyari/FaceForensics/master/dataset/splits"
FFPP_METHODS = ("Deepfakes", "Face2Face", "FaceSwap", "NeuralTextures")
FFPP_UNSEEN = ("FaceShifter",)
# Fusion training uses a seeded subset of the official train pairs (CPU budget). The 120
# fusion pairs are held out of CNN training; 60 of them are extracted ("spare" = never read).
FFPP_FUSION_TRAIN_PAIRS = 120
FFPP_FUSION_USED_PAIRS = 60
FFPP_VAL_FAKE_PAIRS = 35  # all 140 val reals set thresholds; half the val fakes for a check

DFDC_REPO = "gonnerthetooner/DFDC-extracted-full"
DFDC_PARTS = tuple(f"dfdc_train_part_{i:02d}/dfdc_train_part_{i}" for i in range(3))


@dataclass(frozen=True)
class Item:
    key: str  # unique id, e.g. "ffpp/Deepfakes/000_003"
    path: str  # relative to DATA
    label: int  # 1 = fake, 0 = real
    identity: str  # cluster for splitting/bootstrap (FF++: the target video id)
    split: str  # "sbi_train" | "fusion_train" | "val" | "test" | "xtest"
    source: str  # dataset name
    method: str  # "real" or the manipulation method


def hf_url(repo: str, path: str) -> str:
    return f"https://huggingface.co/datasets/{repo}/resolve/main/" + urllib.parse.quote(path)


def fetch(url: str, dest: Path, retries: int = 4) -> Path:
    """Download with curl (honours the proxy and its CA bundle). Skips existing files."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(retries):
        proc = subprocess.run(
            ["curl", "-sSfL", "--max-time", "600", "-o", str(tmp), url],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            tmp.replace(dest)
            return dest
        if attempt == retries - 1:
            raise RuntimeError(f"download failed {url}: {proc.stderr.strip()}")
    return dest


def ffpp_splits() -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for split in ("train", "val", "test"):
        path = fetch(f"{FFPP_SPLITS}/{split}.json", DATA / "ffpp" / f"split_{split}.json")
        out[split] = [(a, b) for a, b in json.loads(path.read_text())]
    return out


def ffpp_items() -> list[Item]:
    """FF++ c23 items for every role in the protocol (docs/VIDEO_DEEPFAKE.md §5).

    sbi_train   reals of the other 240 train pairs = 480 videos (the CNN never sees a
                real deepfake, and never sees the fusion videos)
    fusion_train seeded 60 of 360 train pairs: 120 reals + their 4x120 fakes
    val         all 70 val pairs: 140 reals (thresholds) + 4x70 fakes of 35 pairs (check)
    test        all 70 test pairs: 140 reals + 4x140 fakes + 140 FaceShifter (unseen method)
    """
    splits = ffpp_splits()
    items: list[Item] = []

    def reals(pairs: list[tuple[str, str]], split: str) -> None:
        for a, b in pairs:
            for vid in (a, b):
                items.append(
                    Item(
                        f"ffpp/original/{vid}",
                        f"ffpp/original/{vid}.mp4",
                        0,
                        vid,
                        split,
                        "ffpp_c23",
                        "real",
                    )
                )

    def fakes(pairs: list[tuple[str, str]], split: str, methods: tuple[str, ...]) -> None:
        for method in methods:
            for a, b in pairs:
                for tgt, src in ((a, b), (b, a)):
                    name = f"{tgt}_{src}"
                    items.append(
                        Item(
                            f"ffpp/{method}/{name}",
                            f"ffpp/{method}/{name}.mp4",
                            1,
                            tgt,
                            split,
                            "ffpp_c23",
                            method,
                        )
                    )

    train = list(splits["train"])
    rng = random.Random(SEED)
    rng.shuffle(train)
    fusion = sorted(train[:FFPP_FUSION_TRAIN_PAIRS])
    reals(sorted(train[FFPP_FUSION_TRAIN_PAIRS:]), "sbi_train")
    rng_used = random.Random(SEED + 1)
    used = sorted(rng_used.sample(fusion, FFPP_FUSION_USED_PAIRS))
    spare = [p for p in fusion if p not in used]
    reals(used, "fusion_train")
    fakes(used, "fusion_train", FFPP_METHODS)
    reals(spare, "spare")
    fakes(spare, "spare", FFPP_METHODS)
    val = list(splits["val"])
    rng_val = random.Random(SEED + 2)
    val_fake = sorted(rng_val.sample(val, FFPP_VAL_FAKE_PAIRS))
    reals(val, "val")
    fakes(val_fake, "val", FFPP_METHODS)
    fakes([p for p in val if p not in val_fake], "spare", FFPP_METHODS)
    reals(splits["test"], "test")
    fakes(splits["test"], "test", FFPP_METHODS + FFPP_UNSEEN)
    return items


def ffpp_remote(item: Item) -> str:
    _, method, name = item.key.split("/")
    return hf_url(FFPP_REPO, f"{FFPP_PREFIX}/{method}/{name}.mp4")


def dfdc_items(n_fake: int = 250) -> list[Item]:
    """DFDC train parts 0-2: every real video plus a seeded sample of fakes.

    identity = the original (source) video, so a real and the fakes made from it share a
    cluster in the bootstrap. Never used for training or threshold fitting."""
    real: list[tuple[str, str]] = []
    fake: list[tuple[str, str, str]] = []
    for i, part in enumerate(DFDC_PARTS):
        meta_path = fetch(
            hf_url(DFDC_REPO, f"{part}/metadata.json"), DATA / "dfdc" / f"metadata_{i}.json"
        )
        meta = json.loads(meta_path.read_text())
        for name, v in sorted(meta.items()):
            if v["label"] == "REAL":
                real.append((part, name))
            else:
                fake.append((part, name, v.get("original") or name))
    rng = random.Random(SEED)
    fake = sorted(rng.sample(fake, min(n_fake, len(fake))))
    items = [Item(f"dfdc/{n}", f"dfdc/{n}", 0, n, "xtest", "dfdc", "real") for _, n in real]
    items += [Item(f"dfdc/{n}", f"dfdc/{n}", 1, o, "xtest", "dfdc", "dfdc") for _, n, o in fake]
    return items


def _dfdc_part(name: str) -> str:
    for i, part in enumerate(DFDC_PARTS):
        meta = json.loads((DATA / "dfdc" / f"metadata_{i}.json").read_text())
        if name in meta:
            return part
    raise KeyError(name)


def remote_url(item: Item) -> str:
    if item.source == "ffpp_c23":
        return ffpp_remote(item)
    if item.source == "dfdc":
        name = item.key.split("/", 1)[1]
        return hf_url(DFDC_REPO, f"{_dfdc_part(name)}/{name}")
    raise ValueError(f"no remote for {item.source}")


def download(items: list[Item], workers: int = 8) -> None:
    unique = {it.path: it for it in items}
    todo = [it for it in unique.values() if not (DATA / it.path).exists()]
    print(f"{len(unique)} files, {len(todo)} to download")

    def one(it: Item) -> None:
        fetch(remote_url(it), DATA / it.path)

    with ThreadPoolExecutor(workers) as pool:
        for i, _ in enumerate(pool.map(one, todo), 1):
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}", flush=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_manifest(items: list[Item], out: Path) -> None:
    """Commit-able manifest: every file with its sha256, label, identity and split."""
    rows = []
    for it in items:
        row = asdict(it)
        row["sha256"] = sha256_file(DATA / it.path)
        rows.append(row)
    out.write_text(json.dumps({"seed": SEED, "items": rows}, indent=1) + "\n")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("sets", nargs="+", choices=["ffpp", "dfdc"])
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if not shutil.which("curl"):
        raise SystemExit("curl is required")
    for name in args.sets:
        items = ffpp_items() if name == "ffpp" else dfdc_items()
        download(items, args.workers)


if __name__ == "__main__":
    main()
