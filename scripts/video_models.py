"""Fetch and verify the video-check model files (any OS: Windows, macOS, Linux).

    uv run python scripts/video_models.py            # download what has a URL, verify all
    uv run python scripts/video_models.py --verify   # only verify what is on disk

Files and their sha256 are listed in config/video_models.json. The blend CNN is not hosted in
this repo (licence: trained on FaceForensics++); the leader shares it, or it is rebuilt with
`python -m research.video.train_sbi`. Set SATYAPAN_BLEND_MODEL_URL to download it from a team
release. GenD (the face CNN the benchmark selected, MIT) is 1.2 GB and is built locally with
`python -m research.video.export_gend` (or downloaded from SATYAPAN_GEND_MODEL_URL); until it
exists Satya uses the blend CNN with its own fallback config. A file with the wrong hash is
deleted and reported, never used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "video_models.json"


def model_dir() -> Path:
    env = os.environ.get("SATYAPAN_VIDEO_MODELS")
    return Path(env) if env else ROOT / "models" / "video"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as fh:  # noqa: S310
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
    tmp.replace(dest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="do not download, only check")
    args = ap.parse_args()
    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    for meta in files.values():
        if meta.get("url_env") and os.environ.get(meta["url_env"]):
            meta["url"] = os.environ[meta["url_env"]]
    ok = True
    for name, meta in files.items():
        dest = model_dir() / name
        if not dest.exists() and meta.get("url") and not args.verify:
            print(f"downloading {name} ...")
            download(meta["url"], dest)
        if not dest.exists():
            how = meta.get("build") or "set its URL in config/video_models.json"
            if meta.get("optional"):
                print(f"OPTIONAL {name} not present ({meta['optional']}): {how}")
                continue
            ok = False
            print(f"MISSING  {name}: {how}")
            continue
        want = meta.get("sha256", "")
        got = sha256(dest)
        if want and got != want:
            dest.unlink()
            ok = False
            print(f"BAD HASH {name}: expected {want[:12]}..., got {got[:12]}... (deleted)")
            continue
        print(f"ok       {name}  sha256 {got[:12]}...  ({meta.get('license', '')[:60]})")
    print("video check ready" if ok else "video check NOT ready (Satya still runs; face check off)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
