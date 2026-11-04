# Limits of this analysis (read this before quoting anything)

Every finding this system produces is an **assessment**, not a conclusion: "consistent with" or
"inconsistent with" manipulation, with a confidence and a named method. The system does not decide
guilt, authenticity in law, or admissibility. A qualified examiner signs; a court decides.

Section numbers below refer to `results/EVIDENCE_LEDGER.md`, where each number has a status
(measured / external-cited / illustrative / pending).

## 1. What the accuracy numbers do and do not mean

- **Field numbers exist only for faces and voices** (§§11–12), on public data: FF++ c23 and DFDC
  for face swaps, In-the-Wild for cloned voices. There, for example, 74.7% of FF++ fakes and
  24.8% of DFDC fakes are flagged for a callback, **0 of 563 real test videos were called
  synthetic**, and In-the-Wild voice AUC is 0.921 (clean) / 0.909 (Opus 16 kbps).
- **The whole-image synthetic, tampering, provenance and red-team rows (§§15.2–15.7) are measured
  on procedurally generated media** in which the manipulated class is built from the artefacts the
  detectors target. They show sensitivity and ablation, not field accuracy. Do not quote them as
  "99% accurate on real photos".
- There is **no public, licensed, in-the-wild benchmark of Indian messaging-forwarded media** that
  we could measure on. Until a lab runs this on its own seized exhibits, the field false-positive
  rate is unknown.

## 2. Named failure cases

| Failure | What happens | Why | Where measured |
|---|---|---|---|
| **Heavy re-encoding** (WhatsApp/Instagram copy, Q <= 80 or 4:2:0) | The whole-image synthetic check is capped at "suspicious, verify". On recompressed synthetic test images top-tier recall goes 100% -> **0%**; screening recall at the lower threshold stays 100% | Quantisation and chroma subsampling remove exactly the spectral and sensor-noise evidence the check uses, and they create their own 2-px periodicity. It cannot separate synthesis from compression, so it refuses to claim synthesis | §15.2 |
| **Resampling** (downscale then upscale) | Resampled authentic photos used to score as synthetic (100% FPR). The residual lag-1 autocorrelation gate now blocks the "smoothing" branch; measured authentic resized score 0.23, manipulated 0.93 | A resize IS an interpolation; it produces the same smoothing signature as a diffusion decoder | §15.7 |
| **Unseen face-swap method** | FaceShifter flagged 31.7% vs 85.4% for the four methods the model was trained on | GenD learned specific generation artefacts; a new generator moves outside them | §11 |
| **Small faces** | At 360p, 82% of DFDC faces are under 64 px -> "couldn't check", never a guess | The face crop is too small for the 224 px CNN | §11 |
| **Real face + cloned voice ("cheapfake")** | The face check is blind by construction; lip-sync is weak (0.62–0.67 AUC) | The pixels are genuine; only the audio is fake | §11 |
| **Background noise on a cloned voice** | 10 dB SNR white noise drops fakes flagged from 63.9% to 1.9% (AUC 0.952 -> 0.843) | The vocoder artefacts drown in noise; a denoiser in front does not fix it | §12 |
| **Audio under 3 s of speech** | Abstains ("too short to judge") | Not enough signal for a 5 s window decision | §12 |
| **Copy-move over flat regions** | A clone of an untextured area (sky, white paper, plain wall) is not matched | The detector needs textured blocks to match; flat blocks are skipped on purpose to avoid false pairs | §15.3 |
| **Cross-faded audio splices** | A DAW splice with matched room tone and a crossfade at both ends can hide the transient and the noise-floor step | Both cues need a discontinuity; a good crossfade removes it | §15.3 |
| **Metadata is not evidence of origin** | EXIF/XMP can be edited, copied between files, or stripped. We report "consistent with camera capture", never "taken by this camera" | Only a cryptographic C2PA manifest (or external custody) binds content to a signer | §15.4 |
| **Unsigned C2PA / COSE chains** | We verify our own Ed25519 JUMBF manifests end-to-end (15/15 valid, 15/15 tampered caught). For third-party C2PA manifests produced by real cameras and Adobe, the X.509/COSE chain needs the official `c2pa-python` library, which could not be installed in this offline environment; we detect the JUMBF box and say "unparsed" instead of pretending to verify | See `BLOCKERS.md` | §15.4 |
| **Screen recordings / re-shot photos** | A photo of a screen (moiré) or a screenshot of a photo is treated as a new capture; provenance will say "editor/screenshot export" | The capture chain is broken by the second camera; ask for the original file | — |
| **Video containers we cannot decode** | With the slim container (no `opencv`), video temporal checks abstain with "decoder not installed" | Honest abstention, never a pass | §15.5 |
| **Deepfake video generated entirely by a diffusion video model** | Not covered by any public licensed test set we could reach; the frame-level whole-image check may fire but it is uncalibrated for this | No licensed benchmark | pending |

## 3. Limits of the integrity story

- SHA-256 + Ed25519 custody + RFC 6962 Merkle proofs prove **integrity since intake**, and that the
  set of sealed records was not rewritten. They say **nothing** about what happened before intake.
- The anchor is a local text file (`anchor.txt`). For court use it must be transcribed into a
  signed paper register or written to WORM storage; we print it, we cannot enforce that step.
- Sealed originals are `0o444` read-only and the app refuses to analyse them directly, but an
  operator with OS-level privileges can change permissions. `verify_all()` will then report a
  mismatch and a failed Merkle proof — detection, not prevention.
- The Ed25519 private keys live under the case directory (`keys/`) for demo use. A real lab must
  use an HSM/smartcard and per-examiner keys.

## 4. Limits of the reporting story

- The Section 63 certificate is a **DRAFT**. Part A is a declaration for the person in charge;
  Part B is for the technical examiner. Blanks and unticked boxes mean "not certified yet".
- Report reproducibility is guaranteed from **stored case data**: same `evidence.json`,
  `custody.jsonl`, `analysis.json` -> byte-identical PDF/HTML/MD/JSON. A fresh intake has fresh
  timestamps, so its report will differ (that is expected, not a bug).
- The PDF embeds heatmaps as JPEG (`/DCTDecode`) inside the PDF. Those renderings are derived
  artefacts; the sealed originals are the evidence.

## 5. Privacy and legal

- Demo data is procedural and fictional. Never run real seized media through a shared machine
  without the lab's chain-of-custody procedure.
- This tool does **not** report anything anywhere. There is no auto-submission to 1930/NCRP/CERT-In
  or a bank. A human files reports.
- Detection of "synthetic" does not establish that a person is lying, and detection of "authentic"
  does not establish that the content is true. A real recording can document a crime; a fabricated
  one can document nothing.
