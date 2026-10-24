"""Video deepfake check (finale). docs/VIDEO_DEEPFAKE.md.

Four independent cues on the other person's face, fused by a small calibrated model:

  blend   a CNN trained only on real faces with self-blended pseudo-fakes (SBI), which looks
          for the blending boundary / sharpness mismatch that face swaps leave at the face edge
  pulse   remote photoplethysmography: does the skin show one coherent heartbeat?
  light   lighting / colour / specular-highlight consistency between face regions
  lipsync does the mouth move with the voice (only when call audio is present)

The result is EVIDENCE that can only raise the band (ML source, media group); it never lowers
anything, and makers never see the raw score. Everything runs on the laptop; frames stay in
RAM and are dropped after the window is scored.

Runtime deps (`uv sync --extra video`): numpy, onnxruntime, mediapipe (which brings OpenCV).
Model files live in models/video/ (git-ignored): `make video-models`.
"""
