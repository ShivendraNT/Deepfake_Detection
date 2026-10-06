import { classifyWindows } from "./lib/voice_rules.js";
import { createWindower, speechSeconds } from "./lib/audio_window.js";
import { THRESHOLDS } from "./lib/thresholds.js";
import { loadScorer, score } from "./lib/onnx_scorer.js";
import { startCall, postVoiceWindows, postChunk } from "./lib/api.js";

let mediaStream = null;
let passCtx = null;
let analysisCtx = null;
let mediaRecorder = null;
let activeCallId = null;
let windower = null;
let scores = [];
let speechTotal = 0;
let chunkIndex = 0;
let recorderInterval = null;
let modelLoaded = false;
let unavailableSent = false;
// Windows are scored one at a time, in order: concurrent session.run() calls fail in
// onnxruntime-web, and out-of-order scores would break the consecutive-window rule.
let windowQueue = Promise.resolve();

// Pre-load the ONNX scorer right away when offscreen loads
const scorerReady = loadScorer().then((ok) => {
    modelLoaded = ok;
});

// Not async: returning a Promise from onMessage would keep the sender's channel open.
chrome.runtime.onMessage.addListener((message) => {
    if (message.target !== "offscreen") return;

    if (message.type === "start-capture") {
        startCapture(message.streamId, message.callId);
    } else if (message.type === "stop-capture") {
        stopCapture();
    }
});

async function startCapture(streamId, callId) {
    if (activeCallId) stopCapture();
    activeCallId = callId;

    try {
        const media = await navigator.mediaDevices.getUserMedia({
            audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } },
            video: false
        });
        mediaStream = media;

        // D1. Two audio graphs. Passthrough first.
        passCtx = new AudioContext();
        const passSrc = passCtx.createMediaStreamSource(media);
        passSrc.connect(passCtx.destination); 

        // Analysis graph (16kHz)
        analysisCtx = new AudioContext({ sampleRate: 16000 });
        const analysisSrc = analysisCtx.createMediaStreamSource(media);
        
        await analysisCtx.audioWorklet.addModule('lib/pcm_worklet.js');
        const workletNode = new AudioWorkletNode(analysisCtx, 'pcm-worklet', {
            channelCount: 1,
            channelCountMode: "explicit"
        });

        windower = createWindower({ sampleRate: 16000, windowSeconds: 5 });
        scores = [];
        speechTotal = 0;
        chunkIndex = 0;
        unavailableSent = false;
        windowQueue = Promise.resolve();

        workletNode.port.onmessage = (event) => {
            const frames = event.data;
            const windows = windower.push(frames);
            for (const win of windows) {
                windowQueue = windowQueue.then(() => processWindow(win, callId));
            }
        };

        analysisSrc.connect(workletNode);
        workletNode.connect(analysisCtx.destination);

        startCall(callId).catch(console.error);

        // MediaRecorder stop/restart cycles of 10s
        startChunkRecording(media, callId);

    } catch (e) {
        console.error("Failed to start capture:", e);
    }
}

async function processWindow(win, callId) {
    await scorerReady;
    if (activeCallId !== callId) return; // capture stopped or restarted meanwhile
    if (!modelLoaded) {
        // D5: send {type:"status", message:"Voice check unavailable (model not loaded)"} once, post nothing
        if (unavailableSent) return;
        unavailableSent = true;
        chrome.runtime.sendMessage({
            type: "status",
            message: "Voice check unavailable (model not loaded)"
        }).catch(() => {});
        return;
    }

    const startMs = performance.now();
    let windowScore = 0;
    try {
        windowScore = await score(win.data);
    } catch (e) {
        console.error("Scoring failed:", e);
        return;
    }
    const elapsedMs = performance.now() - startMs;
    console.log(`ms/window = ${elapsedMs.toFixed(2)}ms, score = ${windowScore}`);

    const spSec = speechSeconds(win.data);
    speechTotal += spSec;
    
    scores.push(windowScore);

    const classification = classifyWindows(scores, THRESHOLDS, speechTotal);

    // Send voice-window to SW (D3 message shape)
    chrome.runtime.sendMessage({
        type: "voice-window",
        callId: callId,
        windowIndex: win.windowIndex,
        label: classification.label,
        consecutiveOverHi: classification.maxConsecutiveOverHi,
        calibrated: THRESHOLDS.calibrated
    }).catch(() => {});

    // POST to backend
    const voiceWindowResult = {
        call_id: callId,
        window_index: win.windowIndex,
        t_start_s: win.t_start_s,
        t_end_s: win.t_end_s,
        score: windowScore,
        speech_seconds: spSec,
        model_version: THRESHOLDS.modelVersion
    };
    
    postVoiceWindows(callId, [voiceWindowResult]).catch(e => {
        // D6: Backend is optional. Ignore failures.
    });
}

function startChunkRecording(media, callId) {
    // 10s cycles
    const recordCycle = () => {
        if (!mediaStream) return;
        
        mediaRecorder = new MediaRecorder(media, { mimeType: "audio/webm;codecs=opus" });
        mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) {
                postChunk(callId, chunkIndex, e.data).catch(() => {});
                chunkIndex++;
            }
        };
        mediaRecorder.onstop = () => {
            // Restart recording if we're still capturing
            if (activeCallId === callId && mediaStream) {
                recordCycle();
            }
        };
        mediaRecorder.start();
        
        recorderInterval = setTimeout(() => {
            if (mediaRecorder && mediaRecorder.state === "recording") {
                mediaRecorder.stop(); // This triggers onstop, which restarts it
            }
        }, 10000);
    };

    recordCycle();
}

function stopCapture() {
    if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop());
        mediaStream = null;
    }
    if (passCtx) { passCtx.close(); passCtx = null; }
    if (analysisCtx) { analysisCtx.close(); analysisCtx = null; }
    if (recorderInterval) { clearTimeout(recorderInterval); recorderInterval = null; }
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        mediaRecorder = null;
    }
    activeCallId = null;
}
