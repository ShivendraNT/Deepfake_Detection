"""Shared paths and helpers for the Voice Seal research scripts.

Audio NEVER lives in the repo (tests/contracts/test_fixtures.py bans media files under
research/, results/, docs/ ...). Generated audio goes to $SATYAPAN_SEAL_DATA, default
~/.cache/satyapan/seal/. Only hashes of it (data manifest) are written to results/.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:  # allow `python research/seal/x.py` without install
    sys.path.insert(0, str(ROOT / "src"))
RESULTS = ROOT / "results"
DATA = Path(os.environ.get("SATYAPAN_SEAL_DATA", str(Path.home() / ".cache/satyapan/seal")))
VOICES_DIR = DATA / "voices"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return out.stdout.strip() + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def tool_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, cmd in (("ffmpeg", ["ffmpeg", "-version"]), ("sox", ["sox", "--version"])):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, check=False)
            out[name] = (r.stdout or r.stderr).splitlines()[0].strip()
        except OSError:
            out[name] = "missing"
    import numpy
    import scipy

    out["numpy"] = numpy.__version__
    out["scipy"] = scipy.__version__
    out["python"] = sys.version.split()[0]
    return out
