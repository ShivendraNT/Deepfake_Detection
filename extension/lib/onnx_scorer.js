import * as ort from "../vendor/ort.wasm.min.mjs";

// Input format (from the Pascu plugin, see T07 spec step 1 notes): raw 16 kHz mono Float32
// samples, no normalisation, shape [1, n]. model.onnx output "output" is [1, T, 1024]; mean-pool
// over T, then logreg_prob.onnx (logreg.onnx without ZipMap, made by
// scripts/prepare_ext_models.py) gives "probabilities" [1, 2]; column 1 = P(synthetic).

let modelSession = null;
let logregSession = null;

// Returns true when both models are ready, false otherwise (caller applies D5).
export async function loadScorer() {
    ort.env.wasm.wasmPaths = chrome.runtime.getURL("vendor/");
    ort.env.wasm.numThreads = 1;

    try {
        const opts = { executionProviders: ["wasm"] };
        modelSession = await ort.InferenceSession.create(chrome.runtime.getURL("models/model.onnx"), opts);
        logregSession = await ort.InferenceSession.create(chrome.runtime.getURL("models/logreg_prob.onnx"), opts);
        console.log("ONNX models loaded successfully.");
        return true;
    } catch (e) {
        console.error("Failed to load ONNX models:", e);
        modelSession = null;
        logregSession = null;
        return false;
    }
}

export async function score(float32Frames) {
    if (!modelSession || !logregSession) {
        throw new Error("Models not loaded");
    }

    const tensorInput = new ort.Tensor("float32", float32Frames, [1, float32Frames.length]);
    const modelOut = await modelSession.run({ input: tensorInput }, ["output"]);

    const [, T, featSize] = modelOut.output.dims;
    const data = modelOut.output.data;
    const pooled = new Float32Array(featSize);
    for (let t = 0; t < T; t++) {
        for (let f = 0; f < featSize; f++) {
            pooled[f] += data[t * featSize + f];
        }
    }
    for (let f = 0; f < featSize; f++) {
        pooled[f] /= T;
    }

    const logregInput = new ort.Tensor("float32", pooled, [1, featSize]);
    const logregOut = await logregSession.run({ X: logregInput }, ["probabilities"]);
    return logregOut.probabilities.data[1];
}
