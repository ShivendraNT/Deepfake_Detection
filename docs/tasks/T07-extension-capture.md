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
