# T07 — Extension capture core (tabCapture → offscreen → 16 kHz → ONNX every 5 s)

## Goal
On a Meet/Teams tab, after one click, capture ONLY the tab's audio, keep it audible, resample to
16 kHz mono, score each 5-second window with the Pascu ONNX model in the browser, classify with
`lib/voice_rules.js`, and emit window results to the side panel and the backend.

## Owner
Shivendra. Effort ≈ 1 day. Critical path.

## Depends on
Nothing (backend `/live/{id}/voice` is glue already; full live path is T11).

## Files to create or modify
- `extension/service_worker.js` — remove `STUB(T07)`; action click → side panel + stream id + offscreen
- `extension/offscreen.js` — remove `STUB(T07)`; capture, passthrough, resample, window, score
- `extension/lib/onnx_scorer.js` (new) — load `models/model.onnx` + `models/logreg.onnx` with onnxruntime-web
- `extension/vendor/` (new) — onnxruntime-web WASM build (copied, MIT license file included)
- `extension/manifest.json` — only if a permission is missing

## Do not touch
`extension/lib/voice_rules.js` (mirror of Python rules — change both + parity test only via
leader), `extension/lib/panel_state.js` and side panel files (T10), backend code.

## Interfaces
Messages (chrome.runtime):
```json
{"target": "offscreen", "type": "start-capture", "streamId": "...", "callId": "call_<ts>"}
{"type": "voice-window", "callId": "...", "windowIndex": 3, "label": "likely_synthetic",
 "consecutiveOverHi": 2}
```
Backend: `postVoiceWindows(callId, [VoiceWindowResult])` from `lib/api.js`
(`{"call_id","window_index","t_start_s","t_end_s","score","speech_seconds","model_version"}`).
Thresholds: read `config/voice_thresholds.json` values into the extension at build time
(tau_hi/tau_lo); show "uncalibrated" while `calibrated=false`.

## Plan (steps)
1. Download the Pascu repo models into `extension/models/` (git-ignored). Read their
   offscreen/worker code to copy the ONNX input format (do not copy code without checking license).
2. Service worker: `chrome.action.onClicked` → `chrome.sidePanel.open({tabId})` →
   `chrome.tabCapture.getMediaStreamId({targetTabId: tab.id})` → create offscreen doc
   (`reasons: ["USER_MEDIA"]`) → send start-capture.
3. Offscreen: `getUserMedia({audio: {mandatory: {chromeMediaSource: "tab", chromeMediaSourceId}}})`;
   `src.connect(ctx.destination)` FIRST (user must still hear the call).
4. Resample to 16000 Hz (AudioWorklet or ScriptProcessor + linear interpolation); buffer 5 s.
5. Score each window (ONNX); classify with `classifyWindows`; send `voice-window` + POST to backend.
6. MediaRecorder 10 s chunks → `postChunk` (wired fully in T11).
7. Manual test on a real Meet tab with a teammate: scores logged, audio audible. Measure ms/window.

## Acceptance criteria
- Static checks: `make task T=T07`.
- Manual (record in STATUS notes): scores logged every ~5 s on a Meet tab; user still hears audio;
  ms per window on the M4 measured.

## Test command
`make task T=T07` and `make ext-test`

## Definition of Done
Static tests green; manual acceptance noted with the measured latency; `make check` green.

## Common mistakes
- Calling tabCapture outside a user gesture (fails silently).
- Forgetting `connect(ctx.destination)` → the maker hears nothing (demo killer).
- Capturing the microphone (we only capture the tab = remote parties).
- Sending raw scores to the side panel UI for makers (send the label; scores go only to the backend).
- Committing `.onnx` files (no license).

## Hints and links
- Chrome tab capture how-to: https://developer.chrome.com/docs/extensions/how-to/web-platform/screen-capture
- Offscreen API: https://developer.chrome.com/docs/extensions/reference/api/offscreen
- Pascu et al. repo: https://github.com/OctavianPascu97/Audio-Deepfakes-Browser-Plugin
- onnxruntime-web: https://onnxruntime.ai/docs/tutorials/web/

## Agent plan (write yours here)

**APPROVED by Authority (Claude Opus, 06 Oct 2026). Worker: Gemini Pro. Work in `~/Desktop/sat-t07`.**

### Decisions locked before coding (do not re-decide while implementing)
- **D1. Two audio graphs, not one.** Passthrough runs on a native-rate `AudioContext` (the user
  hears full-quality audio). Analysis runs on a second `new AudioContext({ sampleRate: 16000 })`
  fed from the same `MediaStream`; Chrome resamples it natively. Do NOT play audio through the
  16 kHz context (it would sound like a telephone line in the demo).
- **D2. Mono** = an AudioWorklet node with `channelCount: 1, channelCountMode: "explicit"`
  (the browser downmixes). The worklet only posts Float32 frames; all logic lives in pure modules.
- **D3. No raw score leaves the offscreen document except to the backend.** The runtime message
  is exactly the spec interface `{type:"voice-window", callId, windowIndex, label,
  consecutiveOverHi, calibrated}`, with no `score`/`maxScore` field (the stub comment that says "send
  score" is overruled by the spec + AGENTS.md rule 9). Scores go only in `postVoiceWindows`.
- **D4. SW → side panel uses the LiveEvent shape** of `replay/sample_events.jsonl`
  (`{type:"voice", call_id, window_index, label, consecutive_over_hi}`), so T10 needs one reducer for
  both the local relay and backend SSE. The reducer is idempotent per window, so duplicates are harmless.
- **D5. Never invent a score.** If the ONNX models are missing or fail to load, send
  `{type:"status", message:"Voice check unavailable (model not loaded)"}` and post nothing.
  Capture, passthrough and chunk upload keep running.
- **D6. Backend is optional.** Every `fetch` (startCall / postVoiceWindows / postChunk) is wrapped
  in try/catch and never stops capture (routes return 501 until T11).
- **D7. Thresholds** come from `config/voice_thresholds.json` through a tiny generator
  `scripts/sync_ext_thresholds.mjs` → `extension/lib/thresholds.js` (committed, generated header).
  `calibrated:false` travels in every voice-window message so the panel can show "uncalibrated".
- **D8. Licensing/size.** `*.onnx` stays git-ignored (already in .gitignore). onnxruntime-web is
  vendored into `extension/vendor/` with its MIT `LICENSE`, `.mjs` and `.wasm` files only.
- **Approved extra files** (outside the spec list, all inside `extension/` or `scripts/`):
  `extension/lib/audio_window.js`, `extension/lib/pcm_worklet.js`, `extension/lib/thresholds.js`,
  `extension/tests/audio_window.test.mjs`, `scripts/sync_ext_thresholds.mjs`.

- **D9 (review amendment, 06 Oct).** Vendor onnxruntime-web **1.20.1** (`ort.wasm.min.mjs`,
  `ort-wasm-simd-threaded.{mjs,wasm}`), the version Pascu ships; 1.14 cannot load `logreg.onnx`
  (ONNX IR 10). onnxruntime-web cannot read the ZipMap output `output_probability`, so
  `scripts/prepare_ext_models.py` (approved extra file) derives `extension/models/logreg_prob.onnx`
  (git-ignored) exposing the `probabilities` tensor [N,2].

### Steps
- [x] **1. Models + input format (human + agent).** Shivendra downloads `model.onnx` and `logreg.onnx`
  into `extension/models/` by hand (licence: no redistribution). Agent reads the Pascu plugin's
  scoring code to record in this spec: input tensor name/shape/dtype, normalisation, which output
  is P(synthetic). Confirm `git status` does not show the .onnx files. *Check:* notes written here.
  **Notes (from Pascu `popup.js` + `onnxWorker.js`, checked against the .onnx graphs):**
  `model.onnx` (IR 6, opset 11): input `input` float32 `[1, n]` = raw 16 kHz mono samples, **no
  normalisation**; output `output` float32 `[1, T, 1024]` (T≈249 for 5 s); ignore 2nd output.
  Mean-pool over T → `[1, 1024]`. `logreg.onnx` (IR 10, ai.onnx.ml LinearClassifier, LOGISTIC):
  input `X` `[N, 1024]`; `output_label` int64 (1 = deepfake), `output_probability` = ZipMap
  (unreadable in ort-web; Pascu only reads the label). We use `logreg_prob.onnx` → `probabilities`
  `[N, 2]`, **column 1 = P(synthetic)**. Verified: JS (ort-web 1.20.1) == Python onnxruntime.
- [x] **2. Pure windowing module + node tests.** `lib/audio_window.js`: `createWindower({sampleRate:16000,
  windowSeconds:5})` that takes Float32 frames and returns full 5 s windows (hop 5 s), with
  `t_start_s/t_end_s`. Also `speechSeconds(window)`: energy VAD on 30 ms frames (RMS threshold).
  Tests in `tests/audio_window.test.mjs` (synthetic sine/silence arrays, no audio files).
  *Check:* `make ext-test` green.
- [x] **3. Service worker.** Remove `STUB(T07)`. In `action.onClicked`, call `chrome.sidePanel.open({tabId})`
  and `chrome.tabCapture.getMediaStreamId({targetTabId})` **before any other await** (user-gesture
  rule). Ensure a single offscreen doc (`chrome.runtime.getContexts` check, then
  `chrome.offscreen.createDocument({reasons:["USER_MEDIA"]})`). `callId = "call_" + Date.now()`,
  saved in `chrome.storage.session` `{callId, tabId}`. Send start-capture. Relay offscreen →
  panel using the D4 shape. Handle `stop-capture` and `tabs.onRemoved` (stop + close the offscreen doc).
  Clicking again on a tab that's already captured = stop (toggle). *Check:* T07 test 1 green.
- [x] **4. Offscreen capture + passthrough.** Remove `STUB(T07)`. `getUserMedia({audio:{mandatory:
  {chromeMediaSource:'tab', chromeMediaSourceId}}, video:false})`. **First line after it:**
  `passCtx.createMediaStreamSource(media).connect(passCtx.destination)`. Then the 16 kHz analysis
  graph (D1/D2) → worklet → windower. Tab audio only, never the mic. *Check:* T07 test 2 green.
- [x] **5. ONNX scorer.** Vendor onnxruntime-web (D8; ask before any `npm install`). `lib/onnx_scorer.js`:
  `loadScorer()` (wasm, `ort.env.wasm.wasmPaths` set to `chrome.runtime.getURL("vendor/")`,
  single-thread) → `score(Float32Array) -> number in [0,1]`, following the step 1 notes. Load
  failure → D5. Log `ms/window` with `performance.now()`.
- [x] **6. Classify + emit.** For each window: score → push into `scores[]`, add to `speechTotal` →
  `classifyWindows(scores, {tauHi, tauLo}, speechTotal)` → send the voice-window message (D3) →
  `postVoiceWindows(callId, [VoiceWindowResult])` with `model_version` from thresholds (D6).
  Call `startCall(callId)` once at the start.
- [x] **7. 10 s chunks for T11.** Run MediaRecorder in **stop/restart cycles of 10 s**, NOT
  `start(10000)` timeslices: timeslice blobs after the first have no WebM header and can't be
  decoded by Whisper. `postChunk(callId, i, blob)` (D6).
- [ ] **8. Verify + manual acceptance.** `make task T=T07`, `make ext-test`, `make check` all green.
  Then load unpacked in Chrome → Meet call with a teammate: (a) remote voice still audible,
  (b) a voice-window every ~5 s in the offscreen console, (c) no score in the side panel's
  messages, (d) ms/window on the M4. Write (a)–(d) into the STATUS.md notes; set T07 `done`.

### Manual-test traps to watch
Calling tabCapture after an `await` (fails silently) · forgetting passthrough (call goes silent) ·
two offscreen docs (`createDocument` throws) · tab-capture of a tab that's already captured
(throws "Cannot capture a tab with an active stream", so use stop/toggle) · `.onnx` in git.
