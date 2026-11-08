# Satyapan Forensic Lab (सत्यापन — "verification")

**Multimedia evidence authentication, deepfake detection and provenance analysis for Indian
law-enforcement agencies and forensic science laboratories.**
SUTRAM 2026 (IGDTUW × ISEA, MeitY) · Theme: AI-Powered Digital Investigation and Cyber
Forensics Technologies for India · **Problem Statement 2: Multimedia Evidence
Authentication, Deepfake Detection and Provenance Analysis Framework.**

An investigating officer or FSL examiner drops in the images, videos, voice notes and call
recordings of a case. Satyapan hashes every file before reading it, stores it write-once,
runs **22 forensic techniques** offline on the workstation, compares every exhibit with the
rest of the case, and answers for each exhibit:
*is it synthetic (AI-generated / deepfake)? was it edited after capture? where did it come
from?* Every answer comes with the measurements behind it (heatmaps, spectrograms, timelines,
the exact metadata), the strength of support on the ENFSI verbal scale, what could **not**
be checked, and a court-ready PDF report with the chain of custody and a draft certificate
under **Section 63(4)(c) of the Bharatiya Sakshya Adhiniyam, 2023**.

> Nothing leaves the workstation: no cloud, no evidence upload, no model call over the
> internet. An air-gapped FSL machine is the intended deployment.

| PS2 deliverable | What Satyapan ships | Where |
|---|---|---|
| Deepfake & synthetic-media detection engine | GenD face-swap model (images + video timeline), AI-generated image classifier (Community Forensics, chosen by a pre-registered comparison), XLS-R synthetic-voice model, and **cross-exhibit face-swap attribution** (same footage + different person + face of a third exhibit). Our open-TTS voice head was trained but is not shipped: it missed its pre-registered bar by 0.7 points | `src/satyapan/forensics/{image,video,audio}/`, `inference.py` |
| Authentication & tampering detection framework | ELA, noise inconsistency, copy-move (SIFT+RANSAC), JPEG grid / double compression, EXIF-thumbnail check, ENF (50 Hz grid) analysis, splice & edit-point cues, frame duplication / timestamp gaps, C2PA validation | same |
| Provenance & source-attribution tool | EXIF/XMP/IPTC & container device tags, C2PA Content Credentials, Stable Diffusion invisible watermark, generator signatures (A1111, ComfyUI, IPTC DigitalSourceType), platform traces (WhatsApp, Telegram, Meta FBMD), codec/bandwidth history, **cross-exhibit graph** (same picture, shared content with an aligned difference map, same face, same speaker, same device, same generator) and inferences from it (the source footage and face source of a deepfake; copies of synthetic pictures) | `src/satyapan/forensics/links.py`, `inference.py` |
| Explainable AI forensic dashboard | React dashboard: live analysis stream, heatmap overlays, spectrogram + score timelines, provenance graph, custody ledger | `lab/` (built copy served at `/lab`) |
| Automated forensic reporting system | PDF: hash report, methodology & references, per-exhibit findings with figures, provenance, cross-exhibit links, custody chain, known error rates, BSA s.63 Part B draft, QR verification code | `src/satyapan/forensics/report/` |

The final-round requirements map to: **working prototype** (`make lab`), **source code**
(this repo), **documentation** ([`docs/forensics/`](docs/forensics/)), **investigation
dataset** ([`data/forensics/demo/`](data/forensics/demo/), ground truth in its
`manifest.json`, described in [DATASET.md](docs/forensics/DATASET.md)), **demonstration on
a realistic cybercrime scenario** ("Operation Pratibimb", a digital-arrest extortion;
[DEMO_SCRIPT.md](docs/forensics/DEMO_SCRIPT.md)) and a **deployment roadmap for LEAs**
([DEPLOYMENT_ROADMAP.md](docs/forensics/DEPLOYMENT_ROADMAP.md)).

## Results at a glance

| Check | Result | Source |
|---|---|---|
| Demo case "Operation Pratibimb" (11 exhibits, ground truth) | **9 / 11 correct, 0 false alarms** on the 4 genuine exhibits; the 2 misses are open-source TTS voice notes (documented blind spot) | `results/forensics_demo_benchmark.md` |
| Image pipeline end to end, 40 held-out genuine photos | **0 false alarms** (39 no indications, 1 suspicious) | `results/forensics_e2e_images.md` |
| Face-swap video detector (FF++ c23 test) | AUC 0.946, 0 of 563 real videos called synthetic | `docs/VIDEO_DEEPFAKE.md` |
| AI-image classifier (Defactify test) | AUC 0.88; 52 % caught at 2.5 % false alarms | `results/aigen_selection.json` |
| Synthetic voice (In-the-Wild, unseen speakers) | AUC 0.92; 0.6 % genuine voices flagged | `docs/VOICE_DEEPFAKE.md` |
| Call-recording splice (demo) | ENF break found at 16.5 s, −57 mHz (truth: 16.54 s, −55 mHz) | `make lab-benchmark` |

---

## Run it

Needs Python 3.11+, [`uv`](https://docs.astral.sh/uv/), `ffmpeg`, and on Linux
`libegl1 libgles2` (MediaPipe). Node is only needed to rebuild the dashboard.

```bash
make lab-setup        # Python deps + the face, voice, speech and forensic models (once, ~4 GB)
make demo-dataset     # build the investigation dataset locally (once; real-person media are never committed)
make lab              # http://127.0.0.1:8000/lab  (API docs at /docs)
```

In the dashboard press **Load demo case** to open the scripted case, or create a case and
drop files. From a terminal:

```bash
make examine F=path/to/seized_folder REPORT=1   # batch triage + PDF report
make lab-benchmark                               # score the lab on the investigation dataset
make check                                       # lint + types + every test
```

A workstation without a model still runs: the affected technique reports *unavailable*, the
verdict lists it under "could not be checked", and nothing is guessed.

## How a verdict is reached

1. **Intake** — MD5, SHA-1 and SHA-256 of the raw bytes first; format from magic bytes (a
   renamed file is reported); original stored read-only under its SHA-256; custody row.
2. **Integrity** — the stored copy is re-hashed before every analysis; a mismatch stops
   the analysis and is written to the custody chain.
3. **Techniques** — every applicable technique runs; each returns findings with a
   hypothesis (synthetic / manipulated / authentic / context) and a strength.
4. **Verdict** — a fixed, documented rule table (not a model) combines them into
   SYNTHETIC, MANIPULATED, SUSPICIOUS, NO INDICATIONS or INCONCLUSIVE, worded on the ENFSI
   scale ("strong support for the proposition that…"). Strength words follow measured error
   rates: one classifier score is at most *moderate* support, so a firm verdict needs a strong
   finding or two independent ones. "No indications" never claims authenticity, and every
   technique that could not run is listed.
5. **Case comparison** — each exhibit is compared with the rest of the case; two
   deterministic inferences (face replaced in reused footage, copy of a synthetic picture)
   can re-decide a verdict, logged in the custody chain with the verdict before and after.
6. **Report** — the PDF and its SHA-256 go into the custody chain.

Details: [METHODOLOGY.md](docs/forensics/METHODOLOGY.md). Measured accuracy and failure
cases: [VALIDATION.md](docs/forensics/VALIDATION.md).

## Repository map

```
src/satyapan/forensics/   the lab: intake, techniques, engine, verdict, links, report, API service
src/satyapan/api/routes_lab.py   REST + SSE API (/lab/api/...) and the dashboard (/lab)
lab/                      dashboard source (React + TypeScript); built into src/satyapan/forensics/ui
data/forensics/demo/      investigation dataset: generated exhibits + manifest.json (ground truth); the rest is built by make demo-dataset
research/forensics/       model selection & calibration scripts (results/ holds their outputs)
scripts/                  dataset builder, model installer, benchmark
tests/forensics/          forensic test suite (formats, signals, verdict rules, API, hostile files)
docs/forensics/           methodology, validation, dataset, demo script, deployment roadmap
```

The repository grew out of **Satya**, our earlier consumer deepfake / scam companion
(desktop app, phone page, live-call alerts). Its detectors (GenD face model, XLS-R voice
model, Whisper, the Hindi/Hinglish fraud lexicon) are reused by the lab; its documentation
is in [`docs/legacy/SATYA_CONSUMER_README.md`](docs/legacy/SATYA_CONSUMER_README.md).

Third-party models, data and licences: [`THIRD_PARTY.md`](THIRD_PARTY.md). Team Satyapan.
