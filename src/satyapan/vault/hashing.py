"""Hashing helpers. PRE-IMPLEMENTED (T09 core)."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    """Lowercase hex SHA-256. Call this on the RAW bytes before any parsing."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _default(o: Any) -> Any:
    if isinstance(o, datetime | date):
        return o.isoformat()
    if isinstance(o, Enum):
        return o.value
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no spaces, UTF-8 kept. Same input -> same string."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default
    )


def chain_hash(prev_hash: str, row: dict[str, Any]) -> str:
    """row_hash = SHA-256(prev_hash ‖ canonical_json(row))."""
    return sha256_bytes((prev_hash + canonical_json(row)).encode("utf-8"))
