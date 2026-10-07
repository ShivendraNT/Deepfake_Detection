"""Anchor the custody chain head outside our own DB. TASK T09.

Every 15 minutes and on every status change, write the head as a NEW object to an S3 bucket
with Object Lock (GOVERNANCE, 1-day retention in the hackathon; COMPLIANCE in production).
Local fallback: write anchors/<seq>-<head>.json under the vault dir and show the head in the UI.
See docs/tasks/T09-evidence-vault.md.
"""

from __future__ import annotations

from datetime import datetime

from satyapan.contracts.common import utcnow
from satyapan.contracts.custody import AnchorRecord
from satyapan.vault.custody import CustodyLog
from satyapan.vault.hashing import canonical_json
from satyapan.vault.storage import BlobStore


def anchor_head(log: CustodyLog, store: BlobStore, now: datetime | None = None) -> AnchorRecord:
    """Write {"head_hash", "seq", "at"} as JSON to key f"anchors/{seq:08d}-{head}.json".

    Return an AnchorRecord. object_lock_mode is "GOVERNANCE" when the store is S3, else None.
    Never overwrite an existing anchor key.
    """
    head = log.head()
    seq = log.last_seq()
    at = now or utcnow()
    # seq + head are both in the key, so every new chain state gets its own object.
    key = f"anchors/{seq:08d}-{head}.json"
    body = canonical_json({"head_hash": head, "seq": seq, "at": at}).encode("utf-8")
    # S3Storage exposes put_locked (Object Lock GOVERNANCE); LocalStorage has no lock to take.
    locked = getattr(store, "put_locked", None)
    uri = locked(key, body) if callable(locked) else store.put(key, body, "application/json")
    return AnchorRecord(
        head_hash=head,
        seq=seq,
        at=at,
        uri=uri,
        object_lock_mode=_lock_mode(store),
    )


def _lock_mode(store: BlobStore) -> str | None:
    """Object Lock mode only makes sense on S3; local anchors get None."""
    from satyapan.adapters.s3_store import S3Storage  # local import: boto3 is an optional extra

    return "GOVERNANCE" if isinstance(store, S3Storage) else None
