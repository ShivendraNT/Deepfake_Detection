"""Anchor the custody chain head outside our own DB. TASK T09.

Every 15 minutes and on every status change, write the head as a NEW object to an S3 bucket
with Object Lock (GOVERNANCE, 1-day retention in the hackathon; COMPLIANCE in production).
Local fallback: write anchors/<seq>-<head>.json under the vault dir and show the head in the UI.
See docs/tasks/T09-evidence-vault.md.
"""

from __future__ import annotations

from datetime import datetime

from satyapan.contracts.custody import AnchorRecord
from satyapan.vault.custody import CustodyLog
from satyapan.vault.storage import BlobStore


def anchor_head(log: CustodyLog, store: BlobStore, now: datetime | None = None) -> AnchorRecord:
    """Write {"head_hash", "seq", "at"} as JSON to key f"anchors/{seq:08d}-{head}.json".

    Return an AnchorRecord. object_lock_mode is "GOVERNANCE" when the store is S3, else None.
    Never overwrite an existing anchor key.
    """
    raise NotImplementedError("T09: see docs/tasks/T09-evidence-vault.md")
