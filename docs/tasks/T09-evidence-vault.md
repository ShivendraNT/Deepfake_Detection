# T09 — Evidence vault: storage adapter, intake, S3 Object Lock anchor

> Partially done: `vault/hashing.py` and `vault/custody.py` (hash chain + `verify_chain` +
> tamper test) are pre-implemented. You build storage, intake and anchoring.

## Goal
Every uploaded file is hashed BEFORE parsing, stored (local folder or S3 ap-south-1), logged in
the custody chain, and the chain head is anchored outside our DB (S3 Object Lock, or a local
anchors folder as fallback).

## Owner
Saksham. Effort ≈ 4 h (+1 h for real S3 if credits exist).

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

1. `LocalStorage.put/get` in `vault/storage.py`: reject keys with a `..` part or a leading `/`
   (`ValueError`), mkdir parents, write bytes, return `path.resolve().as_uri()`; `get` parses the
   `file://` URI (`urllib.parse.urlparse` + `unquote`, `Path.from` → read) and rejects other
   schemes. Turns `test_local_storage_roundtrip` + the 3 traversal tests green.
2. `get_storage(settings)` in `vault/storage.py`: `LocalStorage(settings.vault_dir)` unless
   `settings.aws_mode and settings.s3_bucket`; construct `S3Storage(settings)` inside
   `try/except Exception` → `logging.warning` → fall back to LocalStorage. Turns the two
   `get_storage_*` tests green.
3. `intake(...)` in `vault/intake.py`: follow the 5 docstring steps in order — `sha256_bytes(data)`
   first, store at `{case_id}/{sha}`, id `ev_{sha[:16]}`, `log.append(... CustodyEvent.INTAKE ...)`,
   then build `Evidence(captured_at=now or utcnow(), excerpt=excerpt[:EXCERPT_MAX_CHARS])`.
   Turns `test_intake_hashes_stores_and_logs` green.
4. `anchor_head(log, store, now)` in `vault/anchor.py`: body `{"head_hash","seq","at"}` via
   `canonical_json`, key `anchors/{seq:08d}-{head}.json`, `object_lock_mode="GOVERNANCE"` only when
   `isinstance(store, S3Storage)` (lazy import), else `None`. Turns `test_anchor_writes_head` green.
5. `S3Storage` in `adapters/s3_store.py`: boto3 imported **inside** `__init__` (optional extra),
   `Config(connect_timeout=..., read_timeout=settings.aws_timeout_s)`, `put` with
   `ServerSideEncryption="AES256"`, `get` from `s3://bucket/key`, `put_locked` adds
   `ObjectLockMode="GOVERNANCE"` + `ObjectLockRetainUntilDate=now+1 day`. Not covered by unit tests;
   the boto3-import invariant test guards the file location.
6. Run the whole T09 suite, then `ruff check/format` + `mypy` + full `pytest` (the `make check`
   equivalent); fix with `ruff format .` if needed.
7. Update `docs/STATUS.md` (T09 → `done` + one-line note) and commit `T09: ...`.
