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
- How we know it works: [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md), the reproducible test kit
  on open data, with every number in [`results/EVIDENCE_LEDGER.md`](results/EVIDENCE_LEDGER.md).
- Checking the code: [`docs/VERIFY.md`](docs/VERIFY.md) (commands, expected results, every
  skipped test and why). Everything we did not write: [`THIRD_PARTY.md`](THIRD_PARTY.md).
- Rules for anyone (human or AI) changing this repo: [`AGENTS.md`](AGENTS.md). Read it first.

**How it decides.** The *ask* (OTP, "safe account", secrecy, remote access, a new payee) is the
part a scam cannot hide, so Satya checks it deterministically, in English, Hinglish and
Devanagari. A scam-text model, an on-device voice-clone model and a face-swap check add evidence
that can **only raise** the answer, never lower it. One policy engine sets the band, and no
AI model can clear it. Satya never blocks anything and never reports on its own: a human
decides.

**Also for businesses** (our Round 1 scope): the same engine compares a pending payment with the
company's vendor master, sends "did you ask for this?" to the real approver's phone
(OOB-Confirm), and drafts the UTR-first report pack. See `docs/finale/LIVE_DEMO.md`.

---

## 1. What you need (install once)

| Requirement | Why | Check |
|---|---|---|
| Python **3.11+** | the engine (`requires-python = ">=3.11"`) | `python3 --version` |
| [`uv`](https://docs.astral.sh/uv/) | installs/syncs the venv; every `make` target uses it | `uv --version` |
| **ffmpeg** | decodes audio/video for the live and media checks | `ffmpeg -version` |
| **Node.js LTS + npm** | the Electron desktop app, web console, extension tests | `node -v && npm -v` |
| **git** | clone | `git --version` |
| _(optional)_ Ollama + `llama3.1:8b` | local LLM summaries (T15) and the red-team | `ollama list` |
| _(optional)_ a `.env` | only for AWS/Ollama overrides; local fallbacks work without it | see §2 |

**macOS:** `brew install uv ffmpeg node`. **Debian/Ubuntu:** `sudo apt install ffmpeg libegl1
libgles2 tesseract-ocr` (EGL for the face check, tesseract for Screen Guard OCR).

**macOS permissions (needed for live calls, not for tests):** System Settings → Privacy &
Security → **Screen & System Audio Recording** → enable **Satya** (or **Electron** in dev).
Quit and relaunch after granting; the prompt only appears once. System-audio loopback needs
macOS 13+. Satya **never** captures the microphone.

### Platform notes

| Laptop | Notes |
|---|---|
| macOS Apple Silicon | everything native; speech uses mlx-whisper |
| macOS Intel | use Python 3.11/3.12; mediapipe/onnxruntime builds for Intel are pinned |
| Windows x64 | everything native; system-audio loopback is built into Windows |
| Windows on ARM | app is native arm64; run the Python engine as **x64 Python**: `uv python install cpython-3.12-windows-x86_64` then `uv venv --python cpython-3.12-windows-x86_64` (CTranslate2/OpenCV have no win_arm64 wheels) |
| Linux x64 / arm64 | `sudo apt install ffmpeg libegl1 libgles2 tesseract-ocr` |

**No `make` (Windows)?** Every target also exists as a script:
`uv run python scripts/satya.py <task>` (`sync`, `asr`, `video`, `check`, `run`, `live`, …).

---

## 2. Configure (optional, 20 seconds)

```bash
cp .env.example .env      # .env is git-ignored
```

Everything works with **AWS mode off** and local fallbacks. Never commit `.env`, never paste it
into an AI chat, never put real keys or real customer data in it. The knobs you may care about:

| Variable | Default | Meaning |
|---|---|---|
| `SATYAPAN_AWS_MODE` | `off` | `off` = fully local; AWS is only the deployment story |
| `SATYAPAN_PROFILE` | `business` | `personal` = the consumer journey (`make live-personal`) |
| `SATYAPAN_ASR_WARMUP` | unset | `1` loads the speech model at boot so the first call is fast |
| `SATYAPAN_LLM_MODEL` / `SATYAPAN_OLLAMA_URL` | `llama3.1:8b` / `http://127.0.0.1:11434` | optional local summaries |
| `SATYAPAN_VAULT_DIR` / `SATYAPAN_CUSTODY_DB` | `vault_data` | hash-chained local vault |
| `SATYAPAN_TRUSTED_AUTHSERV_ID` | demo domain | only trust mail from your own authserv |

---

## 3. Install and verify (5 minutes)

```bash
git clone <this-repo> && cd Deepfake_Detection
make sync        # creates .venv with core + dev dependencies
make check       # ruff + format + mypy + all Python tests -> ends with "make check: ALL GREEN"
```

Current baseline: **884 passed, 16 skipped** (T18 and T20–T23 are not implemented; they are
explicitly marked, never hidden). Desktop: `94` vitest tests green. `make check` must be green
before any commit.

**pip fallback (no uv):**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest hypothesis httpx ruff mypy numpy
make check RUN=
```

### The optional model installs (once per laptop, need internet the first time)

```bash
make asr          # speech engine + model (mlx-whisper on Apple Silicon, faster-whisper elsewhere)
make video        # face check for video deepfakes (GenD + models), verifies them
make voice        # voice-clone model (1.3 GB ONNX; needs torch once)
make demo-audio   # labelled synthetic replay call for demos
make doctor       # is speech ready and fast enough on THIS laptop?
```

Without these, Satya still runs and **abstains honestly** (`video_unavailable`,
`asr unavailable`) — an abstention never becomes a fake PASS.

---

## 4. Run the project

### 4a. Backend (the engine) — one terminal

```bash
make live        # DEMO: no --reload, speech warmed up, binds 0.0.0.0:8000
# or
make run         # DEV: --reload (restarts on save; never use mid-call)
# or
make live-personal   # consumer profile (alerts speak to a person on their own call)
```

Open **http://127.0.0.1:8000/docs** (API) or:

| URL | What |
|---|---|
| `/check` | single-page scam check (works from a phone on the same Wi-Fi) |
| `/pocket` | **Satya Pocket**: installable phone app (message, screenshot, voice note, PDF, video, alerts, report) |
| `/oob` | the approver's OOB-Confirm page |
| `/mobile` | read-only live mirror |
| `/health` | liveness probe (`{"status":"ok"}`) |

**Only one backend can run at a time.** `live`, `run` and `live-personal` all bind port 8000,
so a second one fails with `[Errno 48] address already in use`. That error means one is
*already working* — check it with `curl -s 127.0.0.1:8000/health`.

### 4b. Desktop app (Satya himself) — second terminal

```bash
cd desktop
npm install
npm run dev        # the real Electron app (mascot window + Notebook)
```

| Command | What it does |
|---|---|
| `npm run dev` | Electron app against `127.0.0.1:8000` |
| `npm run dev:web` | renderer only in a browser with the mock bridge, port **5174** (no backend needed) |
| `npm run typecheck` | strict TS for main + renderer |
| `npx vitest run` | 94 desktop tests |
| `npm run build && npm run preview` | production bundle, then run it |
| `npm run dist:mac` / `dist:win` / `dist:linux` | installers (dmg / NSIS / AppImage+deb) |

The desktop app talks **only** to `127.0.0.1:8000`; there is no cloud dependency.

### 4c. Extension and console (optional surfaces)

```bash
make ext-test       # Chrome MV3 extension: tab audio -> on-device voice score, side panel
make console-test   # React OOB console
```

### 4d. One-command rehearsal

```bash
make dry-run     # consent -> call -> alert -> OOB -> report, in-process, fake speech
make judge       # measured scoreboard + check any judge-supplied email/PDF/text
make oob-check   # the real approver page over HTTP (needs `make live` running)
```

---

## 5. What to do on stage (the live demo)

Satya starts **asleep**. Nothing is captured before a visible consent card is accepted.

1. Single-click Satya → **Wake up** → accept the consent card.
2. Single-click again → **Listen to a call** (headphones petal). *This* starts system-audio
   capture for that call — waking up alone never starts listening (per-call consent).
3. Play the video/call in QuickTime, Meet, Zoom, Teams… with the volume up.
4. Satya streams **5-second windows**: transcript → asks (secrecy, new account, OTP, bypass…)
   → the policy engine raises the band → a **HOLD** card appears while the call is still running.
5. Screen checks are a separate petal: **Scan my screen**. A detected meeting window prompts
   "want me to listen?"; if that meeting window closes, the loopback call stops.

Close any unrelated Meet/Teams tab before a scripted demo — a detected meeting going away
stops the loopback call by design.

### Replay the exact same path from a terminal (no clicking, nothing stored)

```bash
# audio only
PYTHONPATH=src uv run python scripts/replay_live_media.py audio path/to/call.wav

# video + its own audio
PYTHONPATH=src uv run python scripts/replay_live_media.py both path/to/video.mp4

# video frames + a separate call audio track
PYTHONPATH=src uv run python scripts/replay_live_media.py both path/to/video.mp4 \
  --audio-file path/to/call.wav
```

It uses the real FastAPI app, live service, voice/video models, speech engine and policy engine
in-process, prints `[audio 0-5s]`, `ask A4: confidential`, `BAND VERIFY`, `BAND HOLD`, and ends
with `Final policy band: HOLD`. `make testkit` builds local synthetic media in `.cache/testkit`
(git-ignored; the repo never contains audio/video).

---

## 6. Verify everything

```bash
make check               # lint + format + mypy + Python tests (before every commit)
make task T=T07          # ONLY one task's acceptance tests, strict
make fmt                 # auto-format + auto-fix lint
make ci                  # every surface: Python + judge kit + dry-run + desktop + console + extension
make testkit-check       # scan the local media test kit with every installed detector
make redteam             # 30-sample injection red-team on local Ollama (writes results/redteam.json)
make status              # task board from docs/STATUS.md
make scan F=folder/      # one verdict per file in any folder, offline, nothing kept
make demo-data           # regenerate data/demo fixtures and re-export the JSON schemas
```

`make ci` is the same matrix CI runs on Ubuntu, macOS x64/arm64 and Windows
(`.github/workflows/ci.yml`). `docs/CROSS_PLATFORM.md` lists the OS/arch matrix and the one
OS-specific piece (audio capture).

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `[Errno 48] address already in use` on `make live` | a backend is already listening. Use it (`curl 127.0.0.1:8000/health`), or `lsof -tiTCP:8000 -sTCP:LISTEN \| xargs kill` then start **one** |
| Satya says *"Start the local engine with make live"* | that card appears when the backend was unreachable. Confirm `/health`, dismiss the stale card, wake again |
| Woke Satya, but nothing is captured | waking ≠ listening. Click **Listen to a call**; audio is only analysed after a yes for that call |
| No system audio / silent windows | macOS **Screen & System Audio Recording** permission for Satya/Electron; relaunch the app. macOS 13+ required |
| Call stops by itself | a detected meeting window closed. Close unrelated Meet/Teams tabs before demoing |
| "It isn't watching my screen" | screen checks are the **Scan my screen** petal, not watch mode; Linux also needs `tesseract-ocr` |
| Video/video window `video_unavailable` | `make video`, then restart the engine |
| Speech slow or missing | `make asr && make doctor`; first model download needs internet once |
| First live call is slow | start with `make live` (sets `SATYAPAN_ASR_WARMUP=1`), not `make run` |
| `npm run dev:web` not reachable | the web mock is a separate command on port 5174; the Electron app does not open it |
| Windows: `make: command not found` | `uv run python scripts/satya.py <task>` (see §1) |

---

## 8. Safety rules the code enforces

These are invariants with tests, not slogans (`tests/invariants/`):

1. **Only `src/satyapan/policy/` sets the band.** Every other layer relays the `Decision`.
2. **Raise-only.** Signals can raise the band or do nothing; nothing lowers it. LLM/style
   signals are capped at VERIFY.
3. **The floor uses trusted data only** — maker-entered transaction + vendor master + config.
   Email/PDF/audio/LLM content never enters `compute_floor`.
4. **Signals are built with `Signal.make(...)`**; deterministic detectors use
   `SignalSource.DETERMINISTIC`.
5. **Callback/OOB contacts come only from the vendor master or employee directory**, never from
   a message, document or call.
6. **No auto-reporting.** No code submits to 1930, NCRP, CERT-In, a bank or the police. Reports
   are drafts (`submission = "MANUAL_ONLY"`); opening a `tel:`/`mailto:`/portal link is a user click.
7. **LLM safety.** No tools, never sets the band, untrusted text never enters the system prompt,
   output must pass the faithfulness checker.
8. **Network only in `src/satyapan/adapters/`.** Unit tests never touch the network.
9. **Makers never see raw scores**; only checker/security views do.
10. **Consent first.** Satya starts asleep; no capture before the consent card; call audio only
    after a yes for that call; **the microphone is never captured**; hide/off/quit stops first;
    any capture error → Sleeping.
11. **Data hygiene.** Never commit real voices, media, bank details, customer data, API keys or
    `.env`. Demo data is fake on purpose (IFSC `FAK…`, accounts `9999…`, domains `*.example`).
    Cloned voices only from a teammate who signed `docs/consent/`.

---

## 9. Repo map

| Path | What |
|---|---|
| `docs/JUDGES.md` | **judges start here**: one page per rubric criterion |
| `AGENTS.md` | rules for every AI agent and human (single source of truth) |
| `docs/tasks/` | T-task specs (`T01` … `T25`), mostly done |
| `docs/STATUS.md` | task board: owner, status, dependencies |
| `docs/ARCHITECTURE.md` | design: components, policy tables, API, AWS mapping, failure modes |
| `docs/THREAT_MODEL.md`, `docs/DATA_POLICY.md` | security + privacy/ethics |
| `docs/RESEARCH_PROTOCOL.md`, `docs/EVALUATION.md` | paper protocol + honest product numbers |
| `docs/VIDEO_DEEPFAKE.md`, `docs/VOICE_DEEPFAKE.md`, `docs/TEXT_BENCHMARK.md` | each detector: protocol, thresholds, results |
| `docs/BENCHMARKS.md` | the test kit: every benchmark, how to reproduce it, what it may claim |
| `docs/JUDGE_KIT.md`, `docs/JUDGE_ONE_PAGER.md`, `docs/ENGINEERING_DEEP_DIVE.md` | scoring, one-page answers, code walkthrough |
| `docs/finale/` | finale plan, mascot spec, live runbook (`LIVE_DEMO.md`), `DELIVERED.md`, `SAFEGUARDS.md`, `DRY_RUNS.md` |
| `docs/CROSS_PLATFORM.md` | OS/arch matrix, CI, the audio-capture difference |
| `docs/POCKET.md` | phone app: install, four tabs, two-minute demo, limits |
| `team/` | each person's finale cards |
| `desktop/` | Electron app: Satya the companion (`main/`, `preload/`, `renderer/src/{companion,workspace,capture,shared}`) |
| `src/satyapan/` | Python backend: `contracts/`, `policy/`, detectors (`asks/`, `email/`, `document/`, `voice/`, `video/`, `live/`, `imagecheck/`, `textrisk/`), `report/`, `api/` |
| `extension/` | Chrome MV3 extension (tab audio → on-device voice score, side panel) |
| `console/` | React web console (OOB approver page) |
| `research/` | research scripts (metrics, baselines, attacks, evaluation) |
| `scripts/` | `satya.py` task runner, replay harness, judge kit, test-kit and demo builders |
| `tests/` | contracts, safety invariants, harness, per-task acceptance tests, finale |
| `data/demo/` | synthetic, obviously fake fixtures (vendors, emails, invoices, 12 cases) |
| `schemas/` | JSON Schemas exported from the contracts |

---

## 10. Grand finale (IIT Delhi, 24–25 Oct 2026)

We are turning Satyapan into **Satya**, a small desktop companion that sits on the clerk's screen.
Read in this order:

1. `docs/GRAND_FINALS_ARCHITECTURE.md` — what we build and why (single source of truth).
2. `docs/finale/PLAN.md` — 48-hour plan, checkpoints, demo script, risks, Q&A.
3. `team/<YourName>.md` — your cards (F01–F16) with steps, checks and a ready prompt.
4. `docs/finale/MASCOT_SPEC.md` — Satya's drawing, poses, motion and copy.

Satya is a living desktop companion (procedural, spring-animated mascot, 12 poses, ~20
reactions) that starts asleep and only watches after consent. On a real call he:

1. notices the meeting window (Meet, Zoom, Teams, WhatsApp, Webex, Slack huddle…) and asks to listen;
2. hears **only what the laptop plays** (system audio, never the microphone), cuts it at pauses
   and transcribes it **on the laptop**, captions about a second behind speech;
3. highlights the *asks* (new account, secrecy, skip the approval, read me the OTP, remote access,
   gift cards, changed bank details; English + Hinglish) and context cues (rush, authority,
   "can't talk", amounts). The policy engine sets the band; evidence can only raise it;
4. one tap sends the exact question to the real approver's phone (OOB-Confirm over the LAN);
5. if money already left: the golden-hour report pack (1930 script, NCRP fields, bank recall
   letter) is drafted with the UTR. A human submits it; nothing is sent automatically.

Also: Screen Guard (on-device OCR of what is on screen, on request or every few seconds when
allowed), clipboard check, file/voice-note checks, an expert view of how the policy decided, and
"hide Satya from screen sharing".

The step-by-step live demo (two laptops, a phone hotspot, permissions, script, fallbacks):
**`docs/finale/LIVE_DEMO.md`**.

---

## 11. What is built

Everything on the Satya path runs and is tested (`make check`: 884 Python tests; desktop:
typecheck + 94 vitest tests). Status per task: `docs/STATUS.md`; plan vs built vs cut:
`docs/JUDGES.md` §5.

**Round 1:** contracts, fixtures, mock API, the policy engine + property tests, the vault hash
chain, the voice window rules (Python + JS), the LLM prompt isolation, the evidence pipeline, the
ask extractor, the email/invoice/voice-note checkers, OOB, the UTR-first report pack, and Seal.

**Finale:** the Satya desktop companion (four windows, consent/modes, bubble cards, Notebook),
the companion API + SSE, the live call path (system audio, local Whisper, labelled replay),
**X1 cross-channel**, Screen Guard/clipboard, file drop, the OOB phone page, report pack v2, the
raise-only video check (model-dependent; abstains if absent), the judge kit, the automated
dry-run harness and cross-platform CI. The exact status of every card and every deliberate cut is
in `docs/finale/DELIVERED.md`.

## License

MIT for this code (`LICENSE`). Third-party models and datasets keep their own terms — see
`docs/DATA_POLICY.md`.
