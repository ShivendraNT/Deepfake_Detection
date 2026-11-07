# Satyapan Forensic Lab (सत्यापन — "verification")

**Multimedia evidence authentication, deepfake detection and provenance analysis for Indian
law-enforcement agencies and forensic science laboratories.**
SUTRAM 2026 (IGDTUW × ISEA, MeitY) · Theme: AI-Powered Digital Investigation and Cyber
Forensics Technologies for India · **Problem Statement 2: Multimedia Evidence
Authentication, Deepfake Detection and Provenance Analysis Framework.**

An investigating officer or FSL examiner drops in the images, videos, voice notes and call
recordings of a case. Satyapan hashes every file before reading it, stores it write-once,
runs **22 forensic techniques** offline on the workstation, and answers for each exhibit:
*is it synthetic (AI-generated / deepfake)? was it edited after capture? where did it come
from?* Every answer comes with the measurements behind it (heatmaps, spectrograms, timelines,
the exact metadata), the strength of support on the ENFSI verbal scale, what could **not**
be checked, and a court-ready PDF report with the chain of custody and a draft certificate
under **Section 63(4)(c) of the Bharatiya Sakshya Adhiniyam, 2023**.

> Nothing leaves the workstation: no cloud, no evidence upload, no model call over the
> internet. An air-gapped FSL machine is the intended deployment.

| PS2 deliverable | What Satyapan ships | Where |
|---|---|---|
| Deepfake & synthetic-media detection engine | GenD face-swap model (images + video timeline), AI-generated image classifier (Community Forensics, chosen by a pre-registered comparison), XLS-R synthetic-voice model + our open-TTS head | `src/satyapan/forensics/{image,video,audio}/` |
| Authentication & tampering detection framework | ELA, noise inconsistency, copy-move (SIFT+RANSAC), JPEG grid / double compression, EXIF-thumbnail check, ENF (50 Hz grid) analysis, splice & edit-point cues, frame duplication / timestamp gaps, C2PA validation | same |
| Provenance & source-attribution tool | EXIF/XMP/IPTC & container device tags, C2PA Content Credentials, Stable Diffusion invisible watermark, generator signatures (A1111, ComfyUI, IPTC DigitalSourceType), platform traces (WhatsApp, Telegram, Meta FBMD), codec/bandwidth history, **cross-exhibit graph** (same picture, shared content with an aligned difference map, same face, same speaker, same device, same generator) | `src/satyapan/forensics/links.py` |
| Explainable AI forensic dashboard | React dashboard: live analysis stream, heatmap overlays, spectrogram + score timelines, provenance graph, custody ledger | `lab/` (built copy served at `/lab`) |
| Automated forensic reporting system | PDF: hash report, methodology & references, per-exhibit findings with figures, provenance, cross-exhibit links, custody chain, known error rates, BSA s.63 Part B draft, QR verification code | `src/satyapan/forensics/report/` |

The final-round requirements map to: **working prototype** (`make lab`), **source code**
(this repo), **documentation** ([`docs/forensics/`](docs/forensics/)), **investigation
dataset** ([`data/forensics/demo/`](data/forensics/demo/), ground truth in its
`manifest.json`, described in [DATASET.md](docs/forensics/DATASET.md)), **demonstration on
a realistic cybercrime scenario** ("Operation Pratibimb", a digital-arrest extortion;
[DEMO_SCRIPT.md](docs/forensics/DEMO_SCRIPT.md)) and a **deployment roadmap for LEAs**
([DEPLOYMENT_ROADMAP.md](docs/forensics/DEPLOYMENT_ROADMAP.md)).

---

## Run it

Needs Python 3.11+, [`uv`](https://docs.astral.sh/uv/), `ffmpeg`, and on Linux
`libegl1 libgles2` (MediaPipe). Node is only needed to rebuild the dashboard.

```bash
make lab-setup        # Python deps + the face, voice, speech and forensic models (once, ~4 GB)
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
   scale ("strong support for the proposition that…"). "No indications" never claims
   authenticity, and every technique that could not run is listed.
5. **Links & report** — features of each exhibit are compared with the rest of the case;
   the report and its SHA-256 go into the custody chain.

Details: [METHODOLOGY.md](docs/forensics/METHODOLOGY.md). Measured accuracy and failure
cases: [VALIDATION.md](docs/forensics/VALIDATION.md).

## Repository map

```
src/satyapan/forensics/   the lab: intake, techniques, engine, verdict, links, report, API service
src/satyapan/api/routes_lab.py   REST + SSE API (/lab/api/...) and the dashboard (/lab)
lab/                      dashboard source (React + TypeScript); built into src/satyapan/forensics/ui
data/forensics/demo/      investigation dataset + manifest.json (ground truth)
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
