"""Forensic Evidence Locker: case folders, read-only originals, working copies, Ed25519-signed
hash-chained custody log, and RFC 6962 Merkle tree inclusion proofs.

Adapted with attribution from sibling project Pramaan (`pramaan/locker/`: intake.py, signing.py,
custody.py, merkle.py, anchor.py, __init__.py) and extended with read-only original sealing
(`0o444`) and mandatory working-copy isolation (`checkout_working_copy`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import platform
import shutil
import stat
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

log = logging.getLogger(__name__)

GENESIS_LINK = "0" * 64
LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"
MERKLE_SCHEME = (
    "RFC 6962 Merkle tree, SHA-256 (leaf = H(0x00 || 'EVxxxx:<sha256>'), node = H(0x01 || L || R))"
)
TAMPER_SIM_FILE = "tamper_sim.json"
TAMPER_XOR = 0x01


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return ensure_utc(v)
    return ensure_utc(datetime.fromisoformat(str(v)))


@dataclass
class ForensicEvidenceItem:
    """One sealed piece of multimedia evidence inside a forensic case."""

    evidence_id: str  # "EV0001"
    case_id: str
    original_name: str  # file name as received
    stored_path: str  # path of the read-only sealed original inside originals/
    working_path: str  # path of the working copy inside working/ (empty until checked out)
    sha256: str  # 64 hex chars, hash of the raw bytes at intake
    size_bytes: int
    media_type: str  # e.g. "image/jpeg", "video/mp4", "audio/wav"
    source_type: str  # "image" | "video" | "audio" | "document"
    device: str  # source device identifier
    collector: str  # examiner / collector id
    collected_at_utc: datetime
    device_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["collected_at_utc"] = ensure_utc(self.collected_at_utc).isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ForensicEvidenceItem:
        copy = dict(d)
        copy["collected_at_utc"] = _parse_dt(copy["collected_at_utc"])
        copy.setdefault("working_path", "")
        copy.setdefault("media_type", "application/octet-stream")
        copy.setdefault("case_id", "")
        return cls(**copy)


@dataclass
class CustodyEntry:
    """One line of the hash-chained, Ed25519-signed custody log (custody.jsonl)."""

    seq: int
    evidence_id: str
    action: str  # "intake" | "working_copy" | "analyze" | "verify" | "report"
    actor: str
    time_utc: datetime
    file_sha256: str
    prev_link: str
    link: str
    signature: str
    signer: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["time_utc"] = ensure_utc(self.time_utc).isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CustodyEntry:
        copy = dict(d)
        copy["time_utc"] = _parse_dt(copy["time_utc"])
        copy.setdefault("notes", "")
        return cls(**copy)


@dataclass
class VerifyReport:
    """Verification result for all sealed originals, custody links, signatures, and anchors."""

    ok: bool
    file_mismatches: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    writable_originals: list[str] = field(default_factory=list)
    chain_breaks: list[int] = field(default_factory=list)
    bad_signatures: list[int] = field(default_factory=list)
    anchor_ok: bool | None = None
    merkle_ok: bool | None = None


# ---------------------------------------------------------------------------
# Hashing & Intake Helpers
# ---------------------------------------------------------------------------


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """Return the SHA-256 of a file as 64 lowercase hex chars, read in chunks."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 of raw bytes as 64 lowercase hex chars."""
    return hashlib.sha256(data).hexdigest()


def next_evidence_id(existing_ids: Iterable[str]) -> str:
    """Given ['EV0001', 'EV0002'] return 'EV0003'. Given [] return 'EV0001'."""
    max_num = 0
    for eid in existing_ids:
        if eid.startswith("EV"):
            try:
                num = int(eid[2:])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue
    return f"EV{max_num + 1:04d}"


def collect_device_info(device: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a dict describing the collection host and source device."""
    info: dict[str, Any] = {
        "device": device,
        "collected_by_host": platform.node() or "forensic-workstation",
        "collector_os": platform.platform(),
    }
    if extra:
        info.update(extra)
    return info


def _set_readonly(path: Path) -> None:
    """Mark a sealed original file as read-only (0o444)."""
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def _set_writable(path: Path) -> None:
    """Mark a file as owner-writable (0o644)."""
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)


def is_readonly(path: str | Path) -> bool:
    """Return True if no write bits are set on `path`."""
    mode = Path(path).stat().st_mode
    return (mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)) == 0


# ---------------------------------------------------------------------------
# Ed25519 Digital Signatures (adapted from Pramaan pramaan/locker/signing.py)
# ---------------------------------------------------------------------------


def generate_keypair(name: str, key_dir: str | Path) -> tuple[Path, Path]:
    """Create <name>.key and <name>.pub if they do not exist yet. Return (priv_path, pub_path)."""
    kdir = Path(key_dir)
    kdir.mkdir(parents=True, exist_ok=True)
    priv_path = kdir / f"{name}.key"
    pub_path = kdir / f"{name}.pub"

    if not priv_path.exists() or not pub_path.exists():
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        priv_path.write_bytes(priv_pem)
        pub_path.write_bytes(pub_pem)

    return priv_path, pub_path


def load_private_key(path: str | Path) -> Ed25519PrivateKey:
    pem = Path(path).read_bytes()
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Expected Ed25519PrivateKey")
    return key


def load_public_key(path: str | Path) -> Ed25519PublicKey:
    pem = Path(path).read_bytes()
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Expected Ed25519PublicKey")
    return key


def sign_bytes(data: bytes, private_key: Ed25519PrivateKey) -> str:
    return private_key.sign(data).hex()


def verify_signature(data: bytes, signature_hex: str, public_key: Ed25519PublicKey) -> bool:
    try:
        sig = bytes.fromhex(signature_hex)
        public_key.verify(sig, data)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Signed Hash-Chained Custody Log (adapted from Pramaan pramaan/locker/custody.py)
# ---------------------------------------------------------------------------


def canonical_json(d: dict[str, Any]) -> str:
    serializable = {
        k: (ensure_utc(v).isoformat() if isinstance(v, datetime) else v) for k, v in d.items()
    }
    return json.dumps(serializable, sort_keys=True, separators=(",", ":"), default=str)


def compute_link(prev_link: str, body: dict[str, Any]) -> str:
    combined = prev_link + canonical_json(body)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def read_custody_log(log_path: str | Path) -> list[CustodyEntry]:
    p = Path(log_path)
    if not p.exists():
        return []
    out: list[CustodyEntry] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(CustodyEntry.from_dict(json.loads(line)))
    return out


def append_custody_entry(
    log_path: str | Path,
    *,
    evidence_id: str,
    action: str,
    actor: str,
    file_sha256: str,
    private_key: Ed25519PrivateKey,
    signer: str,
    notes: str = "",
    now: datetime | None = None,
) -> CustodyEntry:
    p = Path(log_path)
    existing = read_custody_log(p)
    seq = len(existing) + 1
    prev_link = existing[-1].link if existing else GENESIS_LINK
    time_utc = ensure_utc(now or utcnow())

    body = {
        "seq": seq,
        "evidence_id": evidence_id,
        "action": action,
        "actor": actor,
        "time_utc": time_utc,
        "file_sha256": file_sha256,
        "prev_link": prev_link,
        "signer": signer,
        "notes": notes,
    }
    link = compute_link(prev_link, body)
    signature = sign_bytes(link.encode("utf-8"), private_key)

    entry = CustodyEntry(
        seq=seq,
        evidence_id=evidence_id,
        action=action,
        actor=actor,
        time_utc=time_utc,
        file_sha256=file_sha256,
        prev_link=prev_link,
        link=link,
        signature=signature,
        signer=signer,
        notes=notes,
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
    return entry


def verify_custody_chain(
    entries: list[CustodyEntry], public_keys: dict[str, Ed25519PublicKey]
) -> tuple[list[int], list[int]]:
    chain_breaks: list[int] = []
    bad_signatures: list[int] = []

    for i, entry in enumerate(entries):
        expected_prev = entries[i - 1].link if i > 0 else GENESIS_LINK
        if entry.prev_link != expected_prev:
            chain_breaks.append(entry.seq)

        body = {
            "seq": entry.seq,
            "evidence_id": entry.evidence_id,
            "action": entry.action,
            "actor": entry.actor,
            "time_utc": entry.time_utc,
            "file_sha256": entry.file_sha256,
            "prev_link": entry.prev_link,
            "signer": entry.signer,
            "notes": entry.notes,
        }
        if compute_link(entry.prev_link, body) != entry.link and entry.seq not in chain_breaks:
            chain_breaks.append(entry.seq)

        pub = public_keys.get(entry.signer)
        if pub is None or not verify_signature(entry.link.encode("utf-8"), entry.signature, pub):
            bad_signatures.append(entry.seq)

    return chain_breaks, bad_signatures


# ---------------------------------------------------------------------------
# RFC 6962 Merkle Tree (adapted from Pramaan pramaan/locker/merkle.py)
# ---------------------------------------------------------------------------


def leaf_data(evidence_id: str, sha256_hex: str) -> str:
    return f"{evidence_id}:{sha256_hex.lower()}"


def leaf_hash(evidence_id: str, sha256_hex: str) -> str:
    return hashlib.sha256(
        LEAF_PREFIX + leaf_data(evidence_id, sha256_hex).encode("utf-8")
    ).hexdigest()


def node_hash(left_hex: str, right_hex: str) -> str:
    return hashlib.sha256(
        NODE_PREFIX + bytes.fromhex(left_hex) + bytes.fromhex(right_hex)
    ).hexdigest()


def _split_power_of_two(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def root_from_leaves(leaves: list[str]) -> str:
    n = len(leaves)
    if n == 0:
        return hashlib.sha256(b"").hexdigest()
    if n == 1:
        return leaves[0]
    k = _split_power_of_two(n)
    return node_hash(root_from_leaves(leaves[:k]), root_from_leaves(leaves[k:]))


def audit_path(leaves: list[str], index: int) -> list[dict[str, str]]:
    n = len(leaves)
    if not 0 <= index < n:
        raise IndexError(f"leaf index {index} out of range for {n} leaves")
    if n == 1:
        return []
    k = _split_power_of_two(n)
    if index < k:
        return [
            *audit_path(leaves[:k], index),
            {"side": "right", "hash": root_from_leaves(leaves[k:])},
        ]
    return [
        *audit_path(leaves[k:], index - k),
        {"side": "left", "hash": root_from_leaves(leaves[:k])},
    ]


def root_from_path(leaf_hex: str, path: Iterable[dict[str, str]]) -> str:
    h = leaf_hex
    for step in path:
        h = node_hash(step["hash"], h) if step["side"] == "left" else node_hash(h, step["hash"])
    return h


def records_to_leaves(records: Iterable[tuple[str, str]]) -> tuple[list[str], list[str]]:
    pairs = sorted(records, key=lambda r: r[0])
    return [eid for eid, _ in pairs], [leaf_hash(eid, sha) for eid, sha in pairs]


def root_for_records(records: Iterable[tuple[str, str]]) -> str:
    return root_from_leaves(records_to_leaves(records)[1])


def build_merkle_proof(records: Iterable[tuple[str, str]], evidence_id: str) -> dict[str, Any]:
    ids, leaves = records_to_leaves(records)
    if evidence_id not in ids:
        raise KeyError(evidence_id)
    index = ids.index(evidence_id)
    path = audit_path(leaves, index)
    steps: list[dict[str, Any]] = []
    h = leaves[index]
    for level, step in enumerate(path, 1):
        before = h
        h = node_hash(step["hash"], h) if step["side"] == "left" else node_hash(h, step["hash"])
        steps.append(
            {
                "level": level,
                "sibling_side": step["side"],
                "sibling_hash": step["hash"],
                "input_hash": before,
                "output_hash": h,
            }
        )
    n = len(leaves)
    return {
        "scheme": MERKLE_SCHEME,
        "leaf_index": index,
        "leaf_count": n,
        "max_path_length": 0 if n <= 1 else math.ceil(math.log2(n)),
        "leaf_hash": leaves[index],
        "path": path,
        "steps": steps,
        "computed_root": h,
    }


# ---------------------------------------------------------------------------
# Forensic Locker Class
# ---------------------------------------------------------------------------


class ForensicLocker:
    """Manages one forensic case directory (`case_dir`):
    - `originals/`: read-only sealed copies (`0o444`), never modified by analysis;
    - `working/`: working copies checked out after SHA-256 re-verification;
    - `artifacts/`: heatmaps, spectrograms, and per-item JSON findings;
    - `evidence.json`: list of `ForensicEvidenceItem` records;
    - `custody.jsonl`: Ed25519-signed hash-chained custody log;
    - `anchor.txt`: paper-register anchor with chain head + RFC 6962 Merkle root.
    """

    def __init__(
        self,
        case_dir: str | Path,
        collector: str = "examiner",
        key_dir: str | Path | None = None,
        case_meta: dict[str, Any] | None = None,
    ) -> None:
        self.case_dir = Path(case_dir)
        self.case_id = self.case_dir.name
        self.collector = collector
        self.key_dir = Path(key_dir) if key_dir else (self.case_dir / "keys")
        self.originals_dir = self.case_dir / "originals"
        self.working_dir = self.case_dir / "working"
        self.artifacts_dir = self.case_dir / "artifacts"
        self.evidence_file = self.case_dir / "evidence.json"
        self.custody_file = self.case_dir / "custody.jsonl"
        self.anchor_file = self.case_dir / "anchor.txt"
        self.meta_file = self.case_dir / "case_meta.json"

        for d in (self.originals_dir, self.working_dir, self.artifacts_dir, self.key_dir):
            d.mkdir(parents=True, exist_ok=True)

        if case_meta or not self.meta_file.exists():
            existing = self.case_meta()
            merged = {
                "case_id": self.case_id,
                "title": (case_meta or {}).get("title") or existing.get("title") or self.case_id,
                "agency": (case_meta or {}).get("agency")
                or existing.get("agency")
                or "Digital Forensics Laboratory",
                "examiner": (case_meta or {}).get("examiner")
                or existing.get("examiner")
                or self.collector,
                "created_at_utc": existing.get("created_at_utc") or utcnow().isoformat(),
                **(case_meta or {}),
            }
            self.meta_file.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    def case_meta(self) -> dict[str, Any]:
        if not self.meta_file.exists():
            return {"case_id": self.case_id, "examiner": self.collector}
        try:
            return dict(json.loads(self.meta_file.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            return {"case_id": self.case_id, "examiner": self.collector}

    def items(self) -> list[ForensicEvidenceItem]:
        if not self.evidence_file.exists():
            return []
        raw = json.loads(self.evidence_file.read_text(encoding="utf-8"))
        return [ForensicEvidenceItem.from_dict(d) for d in raw]

    def _save_items(self, items: list[ForensicEvidenceItem]) -> None:
        self.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_file.write_text(
            json.dumps([i.to_dict() for i in items], indent=2),
            encoding="utf-8",
        )

    def get_item(self, evidence_id: str) -> ForensicEvidenceItem:
        for item in self.items():
            if item.evidence_id == evidence_id:
                return item
        raise KeyError(f"Unknown evidence_id: {evidence_id}")

    def _private_key(self, signer: str | None = None) -> tuple[str, Ed25519PrivateKey]:
        who = signer or self.collector
        priv_path, _ = generate_keypair(who, self.key_dir)
        return who, load_private_key(priv_path)

    def log_action(
        self,
        evidence_id: str,
        action: str,
        file_sha256: str,
        *,
        actor: str | None = None,
        notes: str = "",
        now: datetime | None = None,
    ) -> CustodyEntry:
        who, priv = self._private_key(actor)
        return append_custody_entry(
            self.custody_file,
            evidence_id=evidence_id,
            action=action,
            actor=who,
            file_sha256=file_sha256,
            private_key=priv,
            signer=who,
            notes=notes,
            now=now,
        )

    def intake_bytes(
        self,
        data: bytes,
        original_name: str,
        *,
        source_type: str = "image",
        media_type: str = "application/octet-stream",
        device: str = "submitted-media",
        device_info: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ForensicEvidenceItem:
        """Seal raw bytes into `originals/<evidence_id>__<name>` with `0o444` read-only mode."""
        raw_sha256 = sha256_bytes(data)
        safe_name = Path(original_name).name or "evidence.bin"

        for existing in self.items():
            if (
                existing.sha256 == raw_sha256
                and existing.original_name == safe_name
                and existing.device == device
                and Path(existing.stored_path).exists()
            ):
                return existing

        all_items = self.items()
        evidence_id = next_evidence_id(i.evidence_id for i in all_items)
        dst = self.originals_dir / f"{evidence_id}__{safe_name}"
        if dst.exists():
            _set_writable(dst)
        dst.write_bytes(data)
        _set_readonly(dst)

        stored_sha256 = sha256_file(dst)
        if stored_sha256 != raw_sha256:
            raise RuntimeError(f"Intake hash mismatch for {evidence_id}")

        item = ForensicEvidenceItem(
            evidence_id=evidence_id,
            case_id=self.case_id,
            original_name=safe_name,
            stored_path=str(dst.resolve()),
            working_path="",
            sha256=stored_sha256,
            size_bytes=len(data),
            media_type=media_type,
            source_type=source_type,
            device=device,
            collector=self.collector,
            collected_at_utc=ensure_utc(now or utcnow()),
            device_info=collect_device_info(device, device_info),
        )
        all_items.append(item)
        self._save_items(all_items)

        self.log_action(
            evidence_id=evidence_id,
            action="intake",
            file_sha256=stored_sha256,
            notes=f"Sealed read-only original ({len(data)} bytes) at originals/{dst.name}",
            now=now,
        )
        self.write_anchor()
        return item

    def intake(
        self,
        src: str | Path,
        *,
        source_type: str = "image",
        media_type: str = "application/octet-stream",
        device: str = "submitted-media",
        device_info: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ForensicEvidenceItem:
        """Hash `src` BEFORE parsing, copy to `originals/` as read-only (`0o444`), log custody."""
        src_path = Path(src)
        src_sha256 = sha256_file(src_path)
        safe_name = src_path.name

        for existing in self.items():
            if (
                existing.sha256 == src_sha256
                and existing.original_name == safe_name
                and existing.device == device
                and Path(existing.stored_path).exists()
            ):
                return existing

        all_items = self.items()
        evidence_id = next_evidence_id(i.evidence_id for i in all_items)
        dst = self.originals_dir / f"{evidence_id}__{safe_name}"
        if dst.exists():
            _set_writable(dst)
        shutil.copy2(src_path, dst)
        _set_readonly(dst)

        stored_sha256 = sha256_file(dst)
        if stored_sha256 != src_sha256:
            raise RuntimeError(f"Intake copy hash mismatch for {evidence_id}")

        size_bytes = dst.stat().st_size
        item = ForensicEvidenceItem(
            evidence_id=evidence_id,
            case_id=self.case_id,
            original_name=safe_name,
            stored_path=str(dst.resolve()),
            working_path="",
            sha256=stored_sha256,
            size_bytes=size_bytes,
            media_type=media_type,
            source_type=source_type,
            device=device,
            collector=self.collector,
            collected_at_utc=ensure_utc(now or utcnow()),
            device_info=collect_device_info(device, device_info),
        )
        all_items.append(item)
        self._save_items(all_items)

        self.log_action(
            evidence_id=evidence_id,
            action="intake",
            file_sha256=stored_sha256,
            notes=f"Sealed read-only original ({size_bytes} bytes) from {safe_name}",
            now=now,
        )
        self.write_anchor()
        return item

    def checkout_working_copy(
        self,
        evidence_id: str,
        *,
        actor: str | None = None,
        purpose: str = "forensic_analysis",
    ) -> Path:
        """Verify the sealed original's SHA-256 and read-only status, copy it to `working/`,
        record a signed `working_copy` custody entry, and return the working copy `Path`.
        Every detector MUST operate on this working copy, never on `originals/`.
        """
        all_items = self.items()
        target: ForensicEvidenceItem | None = None
        for item in all_items:
            if item.evidence_id == evidence_id:
                target = item
                break
        if target is None:
            raise KeyError(f"Unknown evidence_id: {evidence_id}")

        orig_path = Path(target.stored_path)
        if not orig_path.exists():
            raise FileNotFoundError(f"Sealed original missing: {orig_path}")
        if not is_readonly(orig_path):
            raise PermissionError(f"Sealed original {orig_path} is not read-only (0o444)!")

        current_sha = sha256_file(orig_path)
        if current_sha != target.sha256:
            raise ValueError(
                f"Integrity failure on {evidence_id}: expected {target.sha256}, got {current_sha}"
            )

        work_dst = self.working_dir / f"{evidence_id}__{target.original_name}"
        if work_dst.exists():
            _set_writable(work_dst)
        shutil.copy2(orig_path, work_dst)
        _set_writable(work_dst)

        work_sha = sha256_file(work_dst)
        if work_sha != target.sha256:
            raise RuntimeError(f"Working copy hash mismatch for {evidence_id}")

        target.working_path = str(work_dst.resolve())
        self._save_items(all_items)

        self.log_action(
            evidence_id=evidence_id,
            action="working_copy",
            file_sha256=work_sha,
            actor=actor or self.collector,
            notes=f"Checked out verified working copy for {purpose}",
        )
        self.write_anchor()
        return work_dst

    def assert_is_working_copy(self, path: str | Path) -> Path:
        """Raise PermissionError if `path` is inside `originals/`. Used by detectors as a guard."""
        resolved = Path(path).resolve()
        if resolved.is_relative_to(self.originals_dir.resolve()):
            raise PermissionError(
                f"Forensic violation: detector attempted direct access to original {resolved}"
            )
        return resolved

    def annotate(
        self,
        evidence_id: str,
        note: str,
        *,
        actor: str | None = None,
        now: datetime | None = None,
    ) -> CustodyEntry:
        """Attach an examiner note to an exhibit as a signed `annotation` custody entry.

        The note is written into the same Ed25519 hash chain as intake and analysis, so its text
        and position are tamper-evident. It never changes a detector finding.
        """
        item = self.get_item(evidence_id)
        text = (note or "").strip()
        if not text:
            raise ValueError("annotation note must not be empty")
        entry = self.log_action(
            evidence_id=evidence_id,
            action="annotation",
            file_sha256=item.sha256,
            actor=actor or self.collector,
            notes=text[:2000],
            now=now,
        )
        self.write_anchor()
        return entry

    def custody_entries(self) -> list[CustodyEntry]:
        return read_custody_log(self.custody_file)

    def chain_head(self) -> str:
        entries = self.custody_entries()
        return entries[-1].link if entries else GENESIS_LINK

    def merkle_root(self) -> str:
        return root_for_records((i.evidence_id, i.sha256) for i in self.items())

    def write_anchor(self) -> Path:
        head = self.chain_head()
        root = self.merkle_root()
        now_str = utcnow().isoformat()
        content = f"{self.case_id}\n{head}\n{now_str}\n{root}\n"
        self.anchor_file.write_text(content, encoding="utf-8")
        return self.anchor_file

    def read_anchor_info(self) -> dict[str, str] | None:
        if not self.anchor_file.exists():
            return None
        lines = [ln.strip() for ln in self.anchor_file.read_text(encoding="utf-8").splitlines()]
        lines += ["", "", "", ""]
        return {
            "case_id": lines[0],
            "chain_head": lines[1],
            "anchored_at_utc": lines[2],
            "merkle_root": lines[3],
        }

    def verify_all(self) -> VerifyReport:
        file_mismatches: list[str] = []
        missing_files: list[str] = []
        writable_originals: list[str] = []

        for item in self.items():
            p = Path(item.stored_path)
            if not p.exists():
                missing_files.append(item.evidence_id)
            else:
                if not is_readonly(p):
                    writable_originals.append(item.evidence_id)
                if sha256_file(p) != item.sha256:
                    file_mismatches.append(item.evidence_id)

        entries = self.custody_entries()
        public_keys: dict[str, Ed25519PublicKey] = {}
        for entry in entries:
            if entry.signer not in public_keys:
                pub_path = self.key_dir / f"{entry.signer}.pub"
                if pub_path.exists():
                    public_keys[entry.signer] = load_public_key(pub_path)

        chain_breaks, bad_signatures = verify_custody_chain(entries, public_keys)

        anchor_info = self.read_anchor_info()
        anchor_ok: bool | None = None
        merkle_ok: bool | None = None
        if anchor_info is not None:
            if anchor_info.get("merkle_root"):
                merkle_ok = self.merkle_root() == anchor_info["merkle_root"]
            if chain_breaks or bad_signatures:
                anchor_ok = False
            else:
                anchor_ok = self.chain_head() == anchor_info["chain_head"]

        ok = (
            not file_mismatches
            and not missing_files
            and not writable_originals
            and not chain_breaks
            and not bad_signatures
            and anchor_ok is not False
            and merkle_ok is not False
        )
        return VerifyReport(
            ok=ok,
            file_mismatches=file_mismatches,
            missing_files=missing_files,
            writable_originals=writable_originals,
            chain_breaks=chain_breaks,
            bad_signatures=bad_signatures,
            anchor_ok=anchor_ok,
            merkle_ok=merkle_ok,
        )

    def audit_proof(self, evidence_id: str) -> dict[str, Any]:
        items = self.items()
        item = next((i for i in items if i.evidence_id == evidence_id), None)
        if item is None:
            raise KeyError(evidence_id)
        records = [(i.evidence_id, i.sha256) for i in items]
        proof = build_merkle_proof(records, evidence_id)

        stored = Path(item.stored_path)
        current_sha = sha256_file(stored) if stored.exists() else None
        anchor_info = self.read_anchor_info() or {}
        anchored_root = anchor_info.get("merkle_root") or None

        on_disk_root = None
        if current_sha is not None:
            on_disk_root = root_for_records(
                [(eid, current_sha if eid == evidence_id else sha) for eid, sha in records]
            )

        proof.update(
            {
                "evidence_id": evidence_id,
                "original_name": item.original_name,
                "recorded_sha256": item.sha256,
                "current_sha256": current_sha,
                "file_intact": current_sha == item.sha256,
                "readonly_intact": is_readonly(stored) if stored.exists() else False,
                "leaf_data": leaf_data(evidence_id, item.sha256),
                "anchored_root": anchored_root,
                "anchored_at_utc": anchor_info.get("anchored_at_utc") or None,
                "chain_head": anchor_info.get("chain_head") or None,
                "record_included": anchored_root is not None
                and proof["computed_root"] == anchored_root,
                "on_disk_root": on_disk_root,
                "on_disk_matches_anchor": anchored_root is not None
                and on_disk_root == anchored_root,
            }
        )
        proof["verified"] = bool(
            proof["record_included"] and proof["file_intact"] and proof["readonly_intact"]
        )
        return proof

    def integrity_info(self) -> dict[str, Any]:
        rep = self.verify_all()
        entries = self.custody_entries()
        signers: dict[str, dict[str, Any]] = {}
        for e in entries:
            if e.signer in signers:
                continue
            pub = self.key_dir / f"{e.signer}.pub"
            signers[e.signer] = {
                "signer": e.signer,
                "algorithm": "Ed25519",
                "public_key_sha256": (
                    hashlib.sha256(pub.read_bytes()).hexdigest() if pub.exists() else None
                ),
            }
        return {
            "ok": rep.ok,
            "status": "PASSED" if rep.ok else "FAILED",
            "file_mismatches": rep.file_mismatches,
            "missing_files": rep.missing_files,
            "writable_originals": rep.writable_originals,
            "chain_breaks": rep.chain_breaks,
            "bad_signatures": rep.bad_signatures,
            "anchor_ok": rep.anchor_ok,
            "merkle_ok": rep.merkle_ok,
            "chain_head": self.chain_head(),
            "custody_entries": len(entries),
            "merkle_root": self.merkle_root(),
            "evidence_count": len(self.items()),
            "records": [{"evidence_id": i.evidence_id, "sha256": i.sha256} for i in self.items()],
            "anchor": self.read_anchor_info(),
            "signers": list(signers.values()),
            "tamper_simulation": self.tamper_status(),
        }

    # ---- Demo Tamper Simulator (adapted from Pramaan) ----
    def _tamper_file(self) -> Path:
        return self.case_dir / TAMPER_SIM_FILE

    def tamper_status(self) -> dict[str, Any]:
        p = self._tamper_file()
        if not p.exists():
            return {}
        try:
            return dict(json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            return {}

    def _save_tamper_status(self, status: dict[str, Any]) -> None:
        p = self._tamper_file()
        if status:
            p.write_text(json.dumps(status, indent=2), encoding="utf-8")
        elif p.exists():
            p.unlink()

    def simulate_tamper(self, evidence_id: str) -> bool:
        """Flip 1 bit in the middle byte of `evidence_id`'s sealed copy in `originals/` for live
        tamper-detection demonstration, recording the offset so `restore_tamper` can undo it."""
        status = self.tamper_status()
        if evidence_id in status:
            return True
        try:
            item = self.get_item(evidence_id)
        except KeyError:
            return False
        path = Path(item.stored_path).resolve()
        if not path.is_relative_to(self.originals_dir.resolve()) or not path.exists():
            return False
        size = path.stat().st_size
        if size == 0:
            return False
        st = path.stat()
        offset = size // 2
        _set_writable(path)
        try:
            with path.open("r+b") as fh:
                fh.seek(offset)
                original = fh.read(1)[0]
                tampered = original ^ TAMPER_XOR
                fh.seek(offset)
                fh.write(bytes([tampered]))
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        finally:
            _set_readonly(path)
        status[evidence_id] = {
            "evidence_id": evidence_id,
            "original_name": item.original_name,
            "offset": offset,
            "original_byte": original,
            "tampered_byte": tampered,
            "at_utc": utcnow().isoformat(),
        }
        self._save_tamper_status(status)
        return True

    def restore_tamper(self, evidence_id: str) -> bool:
        """Undo `simulate_tamper` and verify that the sealed copy matches its original SHA-256."""
        status = self.tamper_status()
        rec = status.get(evidence_id)
        if rec is None:
            return False
        try:
            item = self.get_item(evidence_id)
        except KeyError:
            return False
        path = Path(item.stored_path).resolve()
        if not path.exists():
            return False
        st = path.stat()
        _set_writable(path)
        try:
            with path.open("r+b") as fh:
                fh.seek(int(rec["offset"]))
                fh.write(bytes([int(rec["original_byte"])]))
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        finally:
            _set_readonly(path)
        ok = sha256_file(path) == item.sha256
        if ok:
            status.pop(evidence_id, None)
            self._save_tamper_status(status)
        return ok
