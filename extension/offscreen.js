// STUB(T07) — see docs/tasks/T07-extension-capture.md. Remove this marker line when done.
//
// Steps:
// 1. Listen for { target: "offscreen", type: "start-capture", streamId, callId }.
// 2. const media = await navigator.mediaDevices.getUserMedia({ audio: { mandatory: {
//        chromeMediaSource: "tab", chromeMediaSourceId: streamId } }, video: false });
// 3. const ctx = new AudioContext(); const src = ctx.createMediaStreamSource(media);
//    src.connect(ctx.destination);   // MUST: otherwise the user stops hearing the call
// 4. Resample to 16000 Hz mono (OfflineAudioContext or a simple linear resampler in an
//    AudioWorklet), collect 5-second windows (hop 5 s).
// 5. For each window: score with onnxruntime-web (models/model.onnx + models/logreg.onnx,
//    as in the Pascu et al. plugin); then classifyWindows() from ./lib/voice_rules.js over all
//    scores so far; send { type: "voice-window", callId, windowIndex, score, label } to the SW
//    and POST the VoiceWindowResult to /live/{callId}/voice (lib/api.js).
// 6. In parallel, MediaRecorder(media, { mimeType: "audio/webm;codecs=opus" }) with a 10 s
//    timeslice -> postChunk(callId, i, blob) (lib/api.js). Live transcription is T11.
// 7. Only the TAB audio (remote participants) is captured, never the microphone.

import { classifyWindows } from "./lib/voice_rules.js";

export { classifyWindows };
