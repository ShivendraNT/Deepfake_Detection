# T09 — Evidence vault: storage adapter, intake, S3 Object Lock anchor

> Partially done: `vault/hashing.py` and `vault/custody.py` (hash chain + `verify_chain` +
> tamper test) are pre-implemented. You build storage, intake and anchoring.

## Goal
Every uploaded file is hashed BEFORE parsing, stored (local folder or S3 ap-south-1), logged in
the custody chain, and the chain head is anchored outside our DB (S3 Object Lock, or a local
anchors folder as fallback).

## Owner
B3. Effort ≈ 4 h (+1 h for real S3 if credits exist).

## Depends on
T01 (done).

## Files to create or modify
- `src/satyapan/vault/storage.py` — `LocalStorage.put/get`, `get_storage`
- `src/satyapan/vault/intake.py` — `intake`
- `src/satyapan/vault/anchor.py` — `anchor_head`
- `src/satyapan/adapters/s3_store.py` — `S3Storage` (boto3; only file allowed to import it)

## Do not touch
`vault/hashing.py`, `vault/custody.py` (leader), contracts, tests, API routes.

## Interfaces
```python
LocalStorage(root: Path).put(key, data, media_type) -> "file:///abs/path"; .get(uri) -> bytes
get_storage(settings) -> BlobStore            # S3 if aws_mode and s3_bucket, else Local; fallback on error
intake(data, *, case_id, channel, filename, media_type, submitted_by, store, log, now=None, excerpt=None) -> Evidence
anchor_head(log, store, now=None) -> AnchorRecord   # key anchors/{seq:08d}-{head}.json
S3Storage(settings).put / get / put_locked(key, data, retain_days=1)
```

## Plan (steps)
1. `LocalStorage.put`: reject keys with `..` parts or leading `/` (ValueError); write file; return
   `path.resolve().as_uri()`. `get`: parse `file://` URI (`urllib.parse.urlparse` is fine — it does
   no network) and read bytes.
2. `intake`: follow the 5 numbered steps in its docstring exactly (hash first!).
3. `anchor_head`: JSON `{"head_hash", "seq", "at"}` → store; `object_lock_mode="GOVERNANCE"`
   if the store is `S3Storage` else `None`.
4. `get_storage`: try S3 when enabled; `except Exception` → log warning → LocalStorage.
5. `S3Storage` (optional for tests): boto3 client with `Config(connect_timeout=5, read_timeout=5)`;
   `put_object(..., ServerSideEncryption="AES256")`; `put_locked` adds
   `ObjectLockMode="GOVERNANCE", ObjectLockRetainUntilDate=now+1 day`.
6. Manually (AWS mode): create bucket in ap-south-1 WITH Object Lock enabled at creation; IAM
   policy allows `s3:PutObject`, `s3:GetObject`, not `s3:DeleteObject*`. Budget alarm US$5.

## Acceptance criteria
- Local round trip; traversal keys rejected; intake hashes first and logs INTAKE with sha256;
  anchor JSON contains the current head; S3 failure falls back to LocalStorage.
- Tamper test (pre-done) still green: editing a row breaks `verify_chain()`.

## Test command
`make task T=T09`

## Definition of Done
Green + `make check`; if AWS used, note bucket name + Object Lock mode in STATUS notes.

## Common mistakes
- Parsing or decoding the file before hashing.
- Using COMPLIANCE mode in the hackathon (you cannot delete the bucket for the retention period).
- Overwriting an anchor key; storing full file contents in custody payloads.
- Importing boto3 anywhere except `adapters/s3_store.py` (invariant test fails).

## Hints and links
- S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- boto3 put_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_object.html

## Agent plan (write yours here)
