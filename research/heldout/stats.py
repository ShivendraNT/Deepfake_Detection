"""Small, dependency-free helpers shared by the honest-evidence scripts.

No randomness here: Wilson intervals are closed-form, hashes and git metadata are read-only.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> dict[str, Any]:
    """Point estimate k/n with the Wilson score 95% interval. n=0 -> all None."""
    if n == 0:
        return {"k": 0, "n": 0, "value": None, "ci95": [None, None]}
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return {
        "k": k,
        "n": n,
        "value": round(p, 4),
        "ci95": [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)],
    }


def split_of(item_id: str) -> str:
    """Pre-registered split (research/heldout/README.md): sha256(id) parity."""
    return (
        "dev" if int(hashlib.sha256(item_id.encode("utf-8")).hexdigest(), 16) % 2 == 0 else "test"
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    """HEAD commit, with '+dirty' if the working tree has uncommitted changes."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
        dirty = subprocess.run(
            # code state only: regenerated files under results/ do not make the code dirty
            ["git", "status", "--porcelain", "--untracked-files=no", "--", ".", ":!results"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except OSError:
        return "unknown"
    return f"{head}+dirty" if dirty else head
