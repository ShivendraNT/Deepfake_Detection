# Voice model files (not committed)

`model.onnx` + `logreg_prob.onnx`, the two-file format every Satya scorer reads (this extension,
the desktop capture window, `satyapan.voice.detector`). They are built, never downloaded from an
unlicensed source:

```bash
make voice        # = uv sync --extra audio --extra voice-build && python -m research.voice.export --install
```

The export builds whichever model the voice benchmark selected (`results/voice_selection.json`,
rule fixed in advance: `docs/VOICE_DEEPFAKE.md`) from its pinned Hugging Face revision. It
checks the ONNX graphs against PyTorch and puts both files here. The head weights are in
`config/voice_head.json`.

- `*.onnx` is git-ignored (`model.onnx` is 0.4–1.3 GB).
- The Pascu et al. plug-in files this format comes from have no licence file. We do not use or
  redistribute them.
