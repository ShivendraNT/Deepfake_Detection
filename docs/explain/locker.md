# `forensics/locker.py` — evidence intake, working copies, custody, Merkle proofs

**What it does.** One forensic case = one folder. `intake()` hashes the raw bytes with SHA-256
*before anything parses them*, copies the file to `originals/EV0001__name` and sets it read-only
(`0o444`). Every analysis then has to call `checkout_working_copy()`, which re-hashes the sealed
original, refuses if the hash or the read-only bit is wrong, copies it to `working/`, and appends a
signed custody entry. `verify_all()` re-checks everything. `audit_proof()` proves one record is in
the anchored Merkle root.

**Core idea.** Separate *what must never change* from *what we analyse*. The originals are sealed,
read-only, and never read by detectors (there is a guard that raises if you try). The custody log is
a hash chain: each entry stores `link = SHA-256(prev_link || canonical_json(body))` and an Ed25519
signature over that link, so editing any old row breaks every later row. The RFC 6962 Merkle tree
commits to the *set* of `(evidence_id, sha256)` records, so a single record can be proved against a
short root printed in a paper register with O(log N) hashes.

**Five questions a judge may ask**

1. *Why hash before parsing?* Because a malicious file could make a parser behave differently from
   the bytes you later testify about. Hash first, then everything downstream refers to that hash.
2. *What if someone edits the sealed file?* `verify_all()` reports a `file_mismatch`, the Merkle
   proof fails, and the dashboard banner turns red. It is *detection*, not prevention — an admin can
   change permissions, but cannot do it silently.
3. *Why Ed25519 and not just SHA-256?* A hash chain alone is self-attested: whoever rewrites the
   rows can rewrite the chain. Signatures bind each row to a key you can pin out-of-band.
4. *Why RFC 6962 (Certificate Transparency) shape?* Its leaf/node prefixes (`0x00`/`0x01`) prevent
   second-preimage tricks and its split rule avoids the duplicate-last-node ambiguity. It is a
   published, auditable construction, not something we invented.
5. *Is the anchor tamper-proof?* No. `anchor.txt` is local. For court use it must be transcribed
   into a signed register or written to WORM storage. We make that step easy and we say so.

**Weaknesses.** Demo keys live under the case folder (use an HSM in production). The chain proves
integrity *since intake*, never before. `0o444` is not an immutable filesystem.
