# PROGRESS.md — Autonomous Engineering Log

## Step 0 — Understand & Plan (Completed)
- **What we did**:
  - Switched to branch `igdtuw`.
  - Read `PS.md`, `README.md`, `docs/ARCHITECTURE.md`, `AGENTS.md`, `docs/JUDGES.md`, `docs/BENCHMARKS.md`, `docs/VIDEO_DEEPFAKE.md`, `docs/VOICE_DEEPFAKE.md`, `THIRD_PARTY.md`, and `results/EVIDENCE_LEDGER.md`.
  - Inspected sibling project `~/Desktop/igdtu` (`Pramaan`) including `pramaan/locker/` (`intake.py`, `signing.py`, `custody.py`, `merkle.py`, `anchor.py`), `pramaan/report/section63.py`, `pramaan/report/build.py`, `pramaan/ai/image_model.py`, `pramaan/parsers/image_meta.py`, and `pramaan/api.py`.
  - Verified baseline `make check`: **884 passed, 16 skipped, ALL GREEN**.
  - Wrote `GAP_PLAN.md` mapping all 5 PS deliverables and Milestones M1–M8 to existing files, gaps, and measurable targets.
  - Created `ASSUMPTIONS.md` and `BLOCKERS.md`.
- **What is measured**:
  - Baseline test suite: 884 passed, 16 skipped (`make check` green).
- **What is next**:
  - **M1**: Design note `docs/design/M1.md` → Implement `src/satyapan/forensics/locker.py` (case folders, read-only originals `0o444`, SHA-256 at intake, Ed25519-signed hash-chained custody log & RFC 6962 Merkle tree adapted from Pramaan, working-copy checkout) → Unit tests `tests/forensics/test_m1_locker.py` → Benchmark/verification script → Ledger rows → `make check` green → Commit.

## M1 — Evidence Intake & Integrity (Completed)
- **What we did**:
  - Wrote `docs/design/M1.md`.
  - Implemented `src/satyapan/forensics/locker.py` (`ForensicLocker`, `ForensicEvidenceItem`, `CustodyEntry`, `VerifyReport`) adapting Pramaan's Ed25519 signing, hash-chained JSONL custody log, RFC 6962 Merkle tree + O(log N) inclusion proofs, and reversible tamper simulator, plus read-only original sealing (`0o444`) and mandatory working-copy isolation (`checkout_working_copy` + `assert_is_working_copy`).
  - Recorded attribution in `THIRD_PARTY.md` and updated `docs/ARCHITECTURE.md` module map.
  - Added unit tests in `tests/forensics/test_m1_locker.py` and benchmark script `research/forensics/eval_m1_locker.py`.
- **What is measured**:
  - 50/50 read-only originals enforced, 50/50 working copies verified, 50/50 direct original access attempts blocked, 50/50 RFC 6962 Merkle inclusion proofs verified, 50/50 tamper attacks caught (file bit-flip, permission drop, custody log edit, Ed25519 signature corruption), 3.29 ms/item intake latency (`results/forensics_m1_locker.json`, `results/EVIDENCE_LEDGER.md` §15.1).
- **What is next**:
  - **M2**: Design note `docs/design/M2.md` → Implement `src/satyapan/forensics/deepfake.py` (reusing GenD face-swap & XLS-R voice-clone checks, adding whole-image AI-generated diffusion/GAN detection, frame-level + aggregate video scoring, validation calibration, held-out test AUC + FPR + compression robustness) → Tests → Ledger rows → `make check` green → Commit.
