/** Types for the parity `onnx_scorer.js` module (the implementation stays identical). */

export function loadScorer(): Promise<boolean>

export function score(float32Frames: Float32Array): Promise<number>
