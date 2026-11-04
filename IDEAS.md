# IDEAS.md — ten directions, scored, and what we built

Scored **impact** (does it raise a forensic lab's outcome or a judge's score?) × **effort**
(can it be built, tested and measured in this repo without new licensed data?). Built items have
measured rows in `results/EVIDENCE_LEDGER.md` §16.

| # | Direction | Impact | Effort | Score | Status |
|---|---|---|---|---|---|
| 1 | **Batch triage of an evidence dump** — screen hundreds of files, rank by risk, cluster duplicates | High: labs receive folders, not single files | Low (reuses M2/M3/M4 + a perceptual hash) | **9** | **built** (§16.1) |
| 2 | **Near-duplicate / re-encode clustering across exhibits** — catch the same photo forwarded twice | High: reveals distribution chain and "original vs copy" | Low (dHash + Hamming) | **8.5** | **built** (§16.1) |
| 3 | **Examiner annotations with a signed audit trail** — notes per finding appended to the custody chain | High: a lab must record who concluded what | Low | **8** | **built** (§16.2) |
| 4 | Hindi / bilingual report and UI strings | High for Indian labs (Hindi is the working language in many cyber cells) | Medium (static translation, no LLM) | 7.5 | planned |
| 5 | Reliability diagram + ECE for every detector's confidence | High credibility: "is 0.9 actually 90%?" | Medium (needs labelled scores) | 7 | planned |
| 6 | Cross-file consistency inside one case (same scene, contradictory EXIF, timeline contradictions) | High: classic forensic cross-examination | Medium | 7 | partly (duplicates) |
| 7 | Original-vs-working visual diff heatmap in the dashboard | Medium: makes tampering obvious to a non-expert | Low | 6.5 | planned |
| 8 | Video keyframe ELA/noise maps (extend M3 image maps to frames) | Medium | Medium | 5.5 | planned |
| 9 | Timeline export (CSV/ICS) and a printable custody sheet | Low-medium: court paperwork | Low | 5 | planned |
| 10 | Perceptual-hash watchlist across cases (same file re-submitted) | Medium | Low-medium | 5 | planned |

Why this order: a lab's first hour is triage, and a judge's first question is "what happens when I
hand you 200 files?". Items 1–3 are cheap, testable and measurable today. Items 4–5 need translation
work and more labelled scores; 6–10 are refinements of surfaces we already have.

---

## Built: batch triage + duplicate clustering (`forensics/triage.py`, `scripts/forensics_scan.py`)

**Use.** `make triage F=path/to/folder` (or `uv run python scripts/forensics_scan.py FOLDER --csv
out.csv`). Every image gets: SHA-256, perceptual hashes, M2 whole-image + M3 tampering + M4
provenance verdicts, a **risk score**, the top reasons, and a `duplicate_group` id when its dHash is
within Hamming 8 of another file. Output is a ranked table (+ optional CSV), not an opaque score.

**Why a perceptual hash and not just SHA-256?** Bytes change on every re-encode; the picture does not.
dHash (64-bit, 9x8 gradient signs) survives JPEG quality changes; Hamming ≤ 8 groups a WhatsApp copy
with its source. SHA-256 is still printed so the examiner can prove exact-file identity.

**Measured (synthetic, `SEED=20261108`, `results/forensics_ideas_triage.json`).**
Near-duplicate clustering: **precision 100%, recall 100%** on 20 ground-truth copy pairs (20 predicted,
0 spurious) among 60 files. Risk ranking of distinct content: **ROC AUC 1.000** (20 authentic vs 20
manipulated). Throughput: **2.19 files/s** on one laptop CPU with all three image engines running.

That precision number came from two fixes. A coarse dHash alone merged different photos that share
a lighting gradient (precision 14–18% at 100% recall). pHash alone was also unstable on very smooth
scenes — its median threshold flips many bits on re-encoding (copy distances 26–56 while correlation
stayed 0.9997). The shipped rule is therefore **32x32 luminance normalized correlation ≥ 0.995**
(pHash is recorded for the examiner, not used to decide). Copies score 0.9997 correlation, distinct
content ≤ 0.982, and flat images are excluded so they cannot match everything.

**Honest limits.** A mirrored or heavily cropped copy can be missed (not claimed). Two near-identical
photographs of the same scene will group — correctly, but an examiner must still open them. It is a
triage aid, not an identification.

## Built: signed examiner annotations (`ForensicLocker.annotate`)

An examiner can attach a note to an exhibit; it is written as an `annotation` entry in the same
Ed25519-signed hash chain as intake/analytics, so the note's content and order are tamper-evident.
Notes are plain text and never change a detector's finding or the band — an examiner's conclusion is
a separate, attributable record. Test: editing the note afterwards breaks the chain and `verify_all()`
reports the sequence number (`tests/forensics/test_ideas_triage.py`).
