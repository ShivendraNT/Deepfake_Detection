"""Evidence intake: hash BEFORE parsing, store, log custody. TASK T09.

See docs/tasks/T09-evidence-vault.md.
"""

from __future__ import annotations

from datetime import datetime

from satyapan.contracts.enums import Channel
from satyapan.contracts.evidence import Evidence
from satyapan.vault.custody import CustodyLog
from satyapan.vault.storage import BlobStore


def intake(
    data: bytes,
    *,
    case_id: str,
    channel: Channel,
    filename: str | None,
    media_type: str,
    submitted_by: str,
    store: BlobStore,
    log: CustodyLog,
    now: datetime | None = None,
    excerpt: str | None = None,
) -> Evidence:
    """1. sha = sha256_bytes(data)  (FIRST, before anything reads the content)
    2. key = f"{case_id}/{sha}"; uri = store.put(key, data, media_type)
    3. evidence id = "ev_" + sha[:16]
    4. log.append(case_id=..., event=CustodyEvent.INTAKE, actor=submitted_by,
                  evidence_id=..., payload={"sha256": sha, "size": len(data), "uri": uri,
                  "channel": channel.value, "filename": filename})
    5. return Evidence(...) with excerpt truncated to EXCERPT_MAX_CHARS.
    """
    raise NotImplementedError("T09: see docs/tasks/T09-evidence-vault.md")
