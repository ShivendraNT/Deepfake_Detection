"""TESLA-style key chain for the Voice Seal: delayed key disclosure, bound to one meeting.

Plain words
-----------
The executive's device picks a random secret seed and hashes it n times:

    K_{n-1} = H(seed),  K_{n-2} = H(K_{n-1}),  ...,  K_0 = H(K_1),  commitment C = H(K_0)

with H = SHA-256. So every key is the hash of the NEXT one: K_{e-1} = H(K_e). The device signs
only C (with its passkey, at session start). During the call it uses K_e to seal the speech of
epoch e (5 seconds), and reveals K_e only AFTER epoch e has ended.

Why this works:
* Anyone can check a revealed key: hashing K_e (e+1) times must give the signed commitment C,
  or, cheaper, hashing it once must give the previously revealed K_{e-1}.
* Nobody can compute K_{e+1} from K_e (that would mean inverting SHA-256). So while epoch e is
  being spoken, K_e is still secret to everyone except the executive's device: a receiver, a
  relay or a recording cannot forge the seal for the epoch that is happening now.
* The seal pattern of epoch e is derived from HMAC-SHA256(K_e, "seal|<binding>|<e>"), where
  `binding` is the canonical meeting id (or voice-note id). Audio sealed for meeting A is
  therefore pure noise to a verifier of meeting B (relay defeated), and epoch e's pattern is
  noise at epoch e+3 (replay defeated).

This file has no audio code; `voiceseal.py` turns `epoch_seed()` into a +/-1 pattern.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timedelta

# How long after an epoch ends the executive's client may still be uploading its key, before the
# registry treats the session as "no longer live" (used for presence checks only).
LIVE_GRACE_S = 15.0

_MEET_CODE = re.compile(r"^[a-z]{3}-[a-z]{4}-[a-z]{3}$")


def h(x: bytes) -> bytes:
    """The chain hash H = SHA-256."""
    return hashlib.sha256(x).digest()


def make_chain(seed: bytes, n_epochs: int) -> tuple[bytes, list[bytes]]:
    """Return (commitment, keys) with keys[e] = K_e for e in 0..n_epochs-1.

    keys[e-1] == H(keys[e]) and commitment == H(keys[0]). `seed` must be secret and random
    (32 bytes from os.urandom / crypto.getRandomValues) in real use; tests pass fixed seeds.
    """
    if n_epochs <= 0:
        raise ValueError("n_epochs must be positive")
    chain = [h(seed)]  # K_{n-1}
    for _ in range(n_epochs - 1):
        chain.append(h(chain[-1]))
    chain.reverse()  # chain[0] = K_0
    return h(chain[0]), chain


def key_matches_commitment(commitment: bytes, key: bytes, epoch: int) -> bool:
    """True iff H^(epoch+1)(key) == commitment. O(epoch) hashes (720 for a 1-hour call)."""
    if epoch < 0:
        return False
    x = key
    for _ in range(epoch + 1):
        x = h(x)
    return hmac.compare_digest(x, commitment)


def key_follows(prev_key: bytes, prev_epoch: int, key: bytes, epoch: int) -> bool:
    """True iff H^(epoch - prev_epoch)(key) == prev_key: the cheap incremental check."""
    if epoch <= prev_epoch:
        return False
    x = key
    for _ in range(epoch - prev_epoch):
        x = h(x)
    return hmac.compare_digest(x, prev_key)


def earlier_keys(key: bytes, epoch: int) -> dict[int, bytes]:
    """All keys K_0..K_epoch derivable from K_epoch (hash forward)."""
    out = {epoch: key}
    x = key
    for e in range(epoch - 1, -1, -1):
        x = h(x)
        out[e] = x
    return out


def epoch_end(t0: datetime, epoch_s: float, epoch: int) -> datetime:
    """Wall-clock time at which epoch `epoch` ends (its key may be disclosed from then on)."""
    return t0 + timedelta(seconds=epoch_s * (epoch + 1))


def epoch_has_ended(t0: datetime, epoch_s: float, epoch: int, now: datetime) -> bool:
    return now >= epoch_end(t0, epoch_s, epoch)


def epoch_seed(key: bytes, binding: str, epoch: int) -> bytes:
    """HMAC-SHA256(K_e, "seal|<binding>|<e>"): ties epoch e's pattern to this meeting/note."""
    return hmac.new(key, f"seal|{binding}|{epoch}".encode(), hashlib.sha256).digest()


def canonical_binding(meeting_or_note: str) -> str:
    """Canonical binding string, so the sender and every receiver derive the same pattern.

    "https://meet.google.com/abc-defg-hij?authuser=0" -> "meet:abc-defg-hij"
    "abc-defg-hij"                                    -> "meet:abc-defg-hij"
    "note:VN-2026-10-07-0042"                          -> "note:VN-2026-10-07-0042"
    "https://teams.example/l/meetup-join/xyz"          -> "url:teams.example/l/meetup-join/xyz"
    """
    s = meeting_or_note.strip()
    if not s:
        raise ValueError("empty meeting/note id")
    if s.startswith(("note:", "meet:", "url:")):
        prefix, _, rest = s.partition(":")
        if not rest:
            raise ValueError("empty meeting/note id")
        return f"{prefix}:{rest.lower() if prefix == 'meet' else rest}"
    low = s.lower()
    for scheme in ("https://", "http://"):
        if low.startswith(scheme):
            low = low[len(scheme) :]
    low = low.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if low.startswith("meet.google.com/"):
        low = low[len("meet.google.com/") :]
    if _MEET_CODE.match(low):
        return f"meet:{low}"
    return f"url:{low}"
