# Kartikey — Satya's ears + the golden-hour pack + demo media

> Cards: **F10 (spike first!) → F11 → F12 → F13 (P2)**. Plan: `docs/finale/PLAN.md`.
> You edit only: `desktop/renderer/src/capture/**`, `desktop/main/capture.ts`,
> `src/satyapan/report/**`, `data/demo/finale/**`, `tests/finale/test_report_pack_v2.py`,
> `extension/**` (F13 only).

**Your job in one line:** get call audio into the engine from any app, and turn a confirmed fraud
into five ready-to-send drafts.

**Model use.** Plan + final review: your strongest model. Steps: fast model, one step per message.
You already built `audio_io` (T17) and the report pack (T16) — most of this is porting and
mapping, not inventing.

---

## F10 — Capture window (spike P0 at H0–H3 · route P1 · → H18)

**Goal.** A hidden window that captures **system audio output** (never the mic), notices calls,
and streams 10 s chunks + voice windows to the existing `/live` endpoints — exactly like the
Chrome extension does today.

**Read.** Architecture §6.2 · `extension/offscreen.js` (your template) · `extension/lib/*.js` ·
Electron docs "desktopCapturer" (macOS audio section).

**Files.** `desktop/main/capture.ts` (new; exports `registerCapture()`) ·
`desktop/renderer/src/capture/CaptureApp.tsx` · `capture/pipeline.ts` · `capture/pcm-worklet.js`
(copy of `extension/lib/pcm_worklet.js`) · `capture/wav.ts` · `capture/vad.ts` · `capture/replay.ts` ·
copies of `audio_window.js`, `voice_rules.js`, `onnx_scorer.js`, `thresholds.js` under
`capture/lib/` (keep them identical — they are parity-tested).

**Step 0 — the spike (do this first, report GO / NO-GO by CP1).**
1. In `main/capture.ts`:
   `session.defaultSession.setDisplayMediaRequestHandler(async (_req, cb) => {`
   `const [s] = await desktopCapturer.getSources({ types: ['screen'] }); cb({ video: s, audio: 'loopback' }) })`.
2. In the capture renderer: `getDisplayMedia({ video: true, audio: true })`, stop the video
   tracks, connect audio to an `AnalyserNode`, log RMS every 500 ms. Play a YouTube video.
3. RMS stays 0? Fix in this order:
   a. `npx electron --version` must be ≥ 39 (CoreAudio Tap on macOS 14.2+). Ask Shivendra to bump it.
   b. Add `NSAudioCaptureUsageDescription` to the dev Electron app:
      `plutil -insert NSAudioCaptureUsageDescription -string "Satya listens to call audio only when you allow it." node_modules/electron/dist/Electron.app/Contents/Info.plist`
      (make it a `postinstall` script so it survives `npm install`).
   c. Launch so Electron is the "responsible" app, not Terminal: `npm run build`, then
      `open node_modules/electron/dist/Electron.app --args "$(pwd)"` (or a packaged build).
   d. System Settings → Privacy & Security → Screen & System Audio Recording → allow Electron.
4. Still silent after a–d → **NO-GO**: route B is dropped for the demo, we use the Chrome extension
   (route A) and replay. That's fine. Write the result under this card.

**Steps (if GO; replay works either way).**
1. `CaptureApp.tsx` listens for main's `start {source, call_id}` / `stop`. Status back to main:
   `capturing | error(reason)`. No samples for 3 s → `error('no audio')` (main sends Satya to
   Sleeping with a toast).
2. `pipeline.ts`: port `offscreen.js` — 16 kHz analysis context + worklet → windower → ONNX score
   → `classifyWindows` → `POST /live/{call_id}/voice`; chunk recorder → **10 s WAV**
   (`wav.ts`, PCM16 mono 16 kHz) → `POST /live/{call_id}/chunk` with `chunk_index`
   (one at a time, in order — copy the queue from `offscreen.js`).
3. Level meter: RMS → 0..1 at 20 Hz → main → mascot rings. **Never sent to the backend.**
4. `vad.ts` call hint: while Watching (not in a call), speech ≥ 3 s within 10 s (reuse
   `speechSeconds`) → `callHint` once; then cool down 30 s. Nothing is stored or transcribed.
5. `replay.ts`: plays a WAV from `data/demo/finale/` through the same graph; status label
   `DEMO REPLAY — NOT LIVE CAPTURE`.
6. Sequence numbers on every chunk; mark gaps, never stitch.

*Check:* `make ext-test` still green (libs unchanged) · `npm run typecheck` · manual: play a demo
clip in a Meet tab → chips appear in `/live/{call_id}/events` within ~13 s.

**Prompt.**
```
You are helping Kartikey with task F10 in this repo.
Read ONLY: AGENTS.md, team/Kartikey.md (F10), docs/GRAND_FINALS_ARCHITECTURE.md §6.2,
extension/offscreen.js, extension/lib/*.js, desktop/shared/contracts.ts.
You may edit ONLY the files listed under F10. Never capture the microphone. Never send raw audio
anywhere except POST /live/{call_id}/chunk on 127.0.0.1. Keep the copied lib files identical.
Do step <N> only. Then run: cd desktop && npm run typecheck. Show the output.
```

---

## F11 — Report pack v2 (P0 · H4 → H22)

**Goal.** One pure function turns a case into the five Report Copilot sections the Notebook
animates and the user copies from.

**Read.** Architecture §6.5 · `src/satyapan/report/pack.py` (your T16 code) ·
`src/satyapan/contracts/report.py` · `ReportPackV2` in `src/satyapan/api/companion/models.py`
(Shivendra adds it in F01).

**Files.** `src/satyapan/report/pack_v2.py` (new) · `tests/finale/test_report_pack_v2.py` (new).

**Interface (frozen).**
```python
def build_report_pack_v2(
    case: Case, master: MasterData, custody_rows: list[CustodyRow],
    now: datetime, *, body_corporate: bool = True, generated_by: str = "satya",
) -> ReportPackV2: ...
```

**Sections, in this order (all `status = DRAFT_REQUIRES_HUMAN_REVIEW`).**

| id | body from | fields (in order) | open_url |
|---|---|---|---|
| `helpline_1930` | `call_script_1930` (UTR on line 1) | UTR, amount, date-time, your bank + masked a/c, beneficiary a/c, IFSC/UPI, beneficiary bank | `tel:1930` |
| `bank_fraud_desk` | `bank_email` | to, subject, UTR, amount, beneficiary, "please hold/recall" | `mailto:` with subject + body URL-encoded |
| `ncrp_portal` | short "how to file" steps | every `ncrp_draft` row in its order + evidence list (name + SHA-256) | `https://cybercrime.gov.in` |
| `cert_in` | template: incident type *"Identity theft, spoofing and phishing attacks"*, time noticed, systems affected, description, actions taken, contact | same as body, one field each | `mailto:incident@cert-in.org.in` · `applies = body_corporate` · `deadline_hint = "Within 6 hours of noticing (CERT-In Directions, 2022) — confirm with your IT/legal team"` |
| `bsa_s63_part_a` | existing `sec63_helper` | per evidence: description, SHA-256 (from custody/vault), algorithm `SHA256`; device particulars and lawful-control statements as **blanks for the custodian**; signatory blank | `null` |

**Rules.** Every field has `source` and `evidence_id` (or `system`). Account numbers →
`sensitive = true`. Copy the §63 Part A labels from the **official Schedule text of the BSA 2023**
(India Code) — do not make labels up. `submission = "MANUAL_ONLY"`, `auto_submit = False`.

**Steps.**
1. Write the tests first (≥ 10): 5 sections in order; UTR on line 1 of the 1930 body; each §63
   hash is 64 hex chars and equals the custody hash; mailto is URL-encoded; `cert_in.applies`
   follows the flag; no section has a submit URL other than the allowed ones; every field has a
   source; MANUAL_ONLY; only fake data.
2. Implement section by section until green.

*Check:* `uv run pytest tests/finale/test_report_pack_v2.py -q` · `make check`.

**Prompt.**
```
You are helping Kartikey with task F11 in this repo.
Read ONLY: AGENTS.md, team/Kartikey.md (F11), docs/GRAND_FINALS_ARCHITECTURE.md §6.5,
src/satyapan/report/pack.py, src/satyapan/contracts/report.py, src/satyapan/api/companion/models.py.
You may edit ONLY src/satyapan/report/pack_v2.py and tests/finale/test_report_pack_v2.py.
Pure function, no network, no new contract fields. Do step <N> only. Then run:
uv run pytest tests/finale/test_report_pack_v2.py -q. Show the output.
```

---

## F12 — Demo media (P0 · H12 → H26)

1. Signed consent form from the teammate whose voice is cloned (`docs/consent/`).
2. Script (fake names/amounts): *"Priya, it's Rajesh. Confidential acquisition — transfer ₹48.5
   lakh to the new escrow account I'm sending you, today. Don't loop in Arjun, I'll explain later."*
   Plus one Hinglish take.
3. Generate 3 takes on Colab (F5-TTS or XTTS-v2). Play each **through a real Meet call** into the
   stage laptop; keep the 2 that produce the chips reliably.
4. Replay WAVs (16 kHz mono) in `data/demo/finale/` — **git-ignored**; master copy on the pen drive.
5. Vendor email `.eml` (passes DMARC, changed bank details) + invoice PDF — reuse the `case_s07`
   fixtures if they fit.
6. Log every clip: source voice (consented), model, date — goes into the deck appendix.

---

## F13 — Gmail "Ask Satya" button (P2, only after CP3)

Content script on `mail.google.com` adds a small "Ask Satya" button on an open message. Click →
the extension sends the message text to `POST /companion/evidence` (consented session required) →
Satya shows the `result` card. Never reads mail on its own.
