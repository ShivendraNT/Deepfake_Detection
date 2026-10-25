# Satya (Satyapan, सत्यापन): check it before you pay

**A scam and deepfake check for one person, on their own laptop.** Forward Satya what a scammer
sent you (a message, a screenshot, a voice note, a photo or a video), or let it listen to a
call after you say yes. It answers **PASS**, **VERIFY** (call back on a number you already have)
or **HOLD** (stop: don't pay, don't share a code). It says why in plain English or Hindi and
gives the next step. If money already left, it drafts your 1930 call with the UTR first.
Nothing is uploaded and nothing is kept.

Amazon AI Cyber Security Hackathon · team of 4 · Delhi Technological University.

- **Judges: start at [`docs/JUDGES.md`](docs/JUDGES.md)** (one page per criterion: run it,
  measured accuracy with failure cases, safeguards, the live journey, robustness, responsible AI).
- Try it: `make sync && make video && make live`, then open http://127.0.0.1:8000/check (a phone
  on the same Wi-Fi: `http://<laptop-ip>:8000/check`). Any folder of files:
  `make scan F=folder/`.
- How we know it works: [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md), the reproducible test kit
  on open data, with every number in [`results/EVIDENCE_LEDGER.md`](results/EVIDENCE_LEDGER.md).
- Checking the code: [`docs/VERIFY.md`](docs/VERIFY.md) (commands, expected results, every
  skipped test and why). Everything we did not write: [`THIRD_PARTY.md`](THIRD_PARTY.md).

**How it decides.** The *ask* (OTP, "safe account", secrecy, remote access, a new payee) is the
part a scam cannot hide, so Satya checks it deterministically, in English, Hinglish and
Devanagari. A scam-text model, an on-device voice-clone model and a face-swap check add evidence
that can **only raise** the answer, never lower it. One policy engine sets the band, and no
AI model can clear it. Satya never blocks anything and never reports on its own: a human
decides.

**Also for businesses** (our Round 1 scope): the same engine compares a pending payment with the
company's vendor master, sends "did you ask for this?" to the real approver's phone
(OOB-Confirm), and drafts the UTR-first report pack. See `docs/finale/LIVE_DEMO.md`.

## 60-second quickstart (macOS, Apple Silicon)

```bash
# 1. tools (once)
brew install uv ffmpeg node
# 2. install and verify
make sync          # creates .venv with core + dev dependencies
make check         # lint + types + tests -> must end with "ALL GREEN"
# 3. run the API with 12 demo cases
make run           # open http://127.0.0.1:8000/docs  -> try GET /cases
```

**pip fallback (no uv):**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest hypothesis httpx ruff mypy numpy
make check RUN=
```

## Any laptop: Windows, macOS, Linux on x64 or arm64

No `make` (Windows)? Every Makefile task also runs as `uv run python scripts/satya.py <task>`
(`sync`, `asr`, `video`, `check`, `run`, `live`, `desktop`). Installers for the Electron app:
`cd desktop && npm run dist:mac` (dmg, arm64 + x64), `dist:win` (NSIS, x64 + arm64),
`dist:linux` (AppImage + deb, x64 + arm64).

| Laptop | Notes |
|---|---|
| macOS Apple Silicon | everything native; speech uses mlx-whisper |
| macOS Intel | use Python 3.11/3.12; the last mediapipe/onnxruntime builds for Intel Macs are pinned |
| Windows x64 | everything native; system-audio loopback is built into Windows |
| Windows on ARM | the app is native arm64; run the Python engine as **x64 Python** (Windows 11 emulates it transparently): `uv python install cpython-3.12-windows-x86_64` then `uv venv --python cpython-3.12-windows-x86_64` (Whisper's CTranslate2 and OpenCV have no win_arm64 wheels) |
| Linux x64 / arm64 | `sudo apt install ffmpeg libegl1 libgles2 tesseract-ocr` (face check needs EGL; Screen Guard OCR needs tesseract) |

**Video deepfake check** (face blending CNN, pulse, lighting, lip-sync; only after a yes for a
call): `make video` (or `scripts/satya.py video`). Design, protocol and measured numbers:
`docs/VIDEO_DEEPFAKE.md`. **Voice-clone check** (voice notes, call audio): `make voice` builds the
model the benchmark selected (licensed, pinned, 1.3 GB ONNX, torch needed once);
`docs/VOICE_DEEPFAKE.md`. **Scam-text check** (e-mails, messages, call transcripts): ships in
`config/text_model.*`, no extra install; benchmark in `docs/TEXT_BENCHMARK.md`.

**Benchmarks / test kit:** `docs/BENCHMARKS.md` (every detector → its open-data test, splits,
CV, frozen thresholds, synthetic-data generators); `python -m research.run_all --list`.

## Repo map

| Path | What |
|---|---|
| `docs/JUDGES.md` | **judges start here**: one page per rubric criterion |
| `AGENTS.md` | **rules for every AI agent and human** (single source of truth) |
| `docs/tasks/` | T-task specs (`T01` … `T25`), mostly done |
| `docs/STATUS.md` | task board: owner, status, dependencies |
| `docs/ARCHITECTURE.md` | design: components, policy tables, API, AWS mapping, failure modes |
| `docs/THREAT_MODEL.md`, `docs/DATA_POLICY.md` | security + privacy/ethics |
| `docs/RESEARCH_PROTOCOL.md`, `docs/EVALUATION.md` | paper protocol + honest product numbers |
| `docs/VIDEO_DEEPFAKE.md` | video deepfake check: idea-by-idea verdict, protocol, benchmark |
| `docs/TEXT_BENCHMARK.md` | scam-text classifier: open datasets, protocol, results |
| `docs/BENCHMARKS.md` | the test kit: every benchmark, how to reproduce it, what it may claim |
| `docs/finale/` | finale plan, mascot spec, **live demo runbook** (`LIVE_DEMO.md`) |
| `docs/DEMO_SCRIPT.md` | the Round-1 demo (superseded by `docs/finale/PLAN.md` §7) |
| `team/` | each person's finale cards |
| `desktop/` | Electron app: Satya the companion |
| `src/satyapan/` | Python backend (contracts, policy engine, detectors, API) |
| `extension/` | Chrome MV3 extension (tab audio → on-device voice score, side panel) |
| `console/` | React web console |
| `research/` | research scripts (metrics, baselines, attacks, evaluation) |
| `tests/` | contracts, safety invariants, harness checks, per-task acceptance tests |
| `data/demo/` | synthetic, obviously fake fixtures (vendors, emails, invoices, 12 cases) |
| `schemas/` | JSON Schemas exported from the contracts |

## Grand finale (IIT Delhi, 24–25 Oct 2026)

We are turning Satyapan into **Satya**, a small desktop companion that sits on the clerk's screen.
Read in this order:

1. `docs/GRAND_FINALS_ARCHITECTURE.md` — what we build and why (single source of truth).
2. `docs/finale/PLAN.md` — 48-hour plan, checkpoints, demo script, risks, Q&A.
3. `team/<YourName>.md` — your cards (F01–F16) with steps, checks and a ready prompt.
4. `docs/finale/MASCOT_SPEC.md` — Satya's drawing, poses, motion and copy.

Desktop quickstart: `cd desktop && npm install && npm run dev:web` (browser + mock, port 5174)
or `npm run dev` (Electron). Backend: `make run`.

### Satya, live (finale build)

Satya is a living desktop companion (procedural, spring-animated mascot with 12 poses and ~20
reactions) that starts **asleep** and only watches after a consent card. On a real call he:

1. notices the meeting window (Meet, Zoom, Teams, WhatsApp, Webex, Slack huddle…) and asks to listen;
2. hears **only what the laptop plays** (system audio, never the microphone), cuts it at pauses and
   transcribes it **on the laptop** (Whisper via `make asr`), captions about a second behind speech;
3. highlights the *asks* (new account, secrecy, skip the approval, read me the OTP, remote access,
   gift cards, changed bank details; English + Hinglish) and context cues (rush, authority,
   "can't talk", amounts). The policy engine sets the band; evidence can only raise it;
4. one tap sends the exact question to the real approver's phone (OOB-Confirm over the LAN);
5. if money already left: the golden-hour report pack (1930 script, NCRP fields, bank recall
   letter) is drafted with the UTR. A human submits it; nothing is sent automatically.

Also: Screen Guard (on-device OCR of what is on screen, on request or every few seconds when
allowed), clipboard check, file/voice-note checks, an expert view of how the policy decided, and
"hide Satya from screen sharing".

```bash
make asr && make demo-audio && make doctor   # once per laptop (speech engine + replay audio)
make live                                     # engine for the demo (no reload, warmed up)
cd desktop && npm run build && npm run preview
```

The step-by-step live demo (two laptops, a phone hotspot, permissions, script, fallbacks):
**`docs/finale/LIVE_DEMO.md`**.

## What is built

Everything on the Satya path runs and is tested (`make check`: 860+ Python tests; desktop: typecheck +
vitest). Status per task: `docs/STATUS.md`; plan vs built vs cut: `docs/JUDGES.md` §5.

## License

MIT for this code (`LICENSE`). Third-party models and datasets keep their own terms — see
`docs/DATA_POLICY.md`.
