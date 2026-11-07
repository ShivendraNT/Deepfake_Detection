"""ffprobe wrapper (container and stream metadata for audio and video)."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def ffprobe(data: bytes | None = None, path: Path | None = None) -> dict[str, Any]:
    """Container + streams as ffprobe JSON. ValueError when ffprobe cannot read the file.
    MP4/MOV may keep their index at the end, so the bytes go through a temporary file."""
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams"]
    try:
        if path is not None:
            proc = subprocess.run([*cmd, str(path)], capture_output=True, timeout=60)
        else:
            with tempfile.NamedTemporaryFile(suffix=".bin") as tmp:
                tmp.write(data or b"")
                tmp.flush()
                proc = subprocess.run([*cmd, tmp.name], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"ffprobe could not run: {exc}") from exc
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "ignore").strip()
        raise ValueError(f"ffprobe failed: {err[:300]}")
    try:
        return json.loads(proc.stdout or b"{}")  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise ValueError("ffprobe output unreadable") from exc


def streams(info: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [s for s in info.get("streams", []) if s.get("codec_type") == kind]


def fraction(v: str | None) -> float | None:
    if not v or v in ("0/0", "N/A"):
        return None
    try:
        if "/" in v:
            a, b = v.split("/", 1)
            return float(a) / float(b) if float(b) else None
        return float(v)
    except ValueError:
        return None


def all_tags(info: dict[str, Any]) -> dict[str, str]:
    """Format tags plus per-stream tags (prefixed with the stream type)."""
    out = {str(k): str(v) for k, v in (info.get("format", {}).get("tags") or {}).items()}
    for s in info.get("streams", []):
        for k, v in (s.get("tags") or {}).items():
            out.setdefault(f"{s.get('codec_type', 'stream')}:{k}", str(v))
    return out
