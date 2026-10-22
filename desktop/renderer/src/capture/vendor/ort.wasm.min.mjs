/**
 * Electron build shim for the extension's vendored ORT bundle.
 *
 * `lib/onnx_scorer.js` is copied byte-for-byte from the extension and imports
 * `../vendor/ort.wasm.min.mjs`. Desktop already depends on `onnxruntime-web`, so reuse its
 * wasm bundle instead of committing a second ~11 MB copy. The scorer logic is unchanged.
 */
export * from 'onnxruntime-web/wasm'
