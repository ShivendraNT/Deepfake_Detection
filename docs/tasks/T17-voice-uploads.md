# T17 — Voice uploads path (Python ONNX + Transcribe batch with Whisper fallback)

## Goal
An uploaded WhatsApp voice note / call recording becomes: a voice signal (same model and same
window rule as the extension), a transcript (Transcribe hi-IN/en-IN in AWS mode, else local
Whisper), and ask signals from the transcript.

## Owner
Kartikey. Effort ≈ 6 h.

## Depends on
T07 (model files + input format), T01 (done). T05 for asks (tests use the seed lexicon).

## Files to create or modify
- `src/satyapan/voice/audio_io.py` — `decode_to_16k_mono`, `split_windows`, `estimate_speech_seconds`
- `src/satyapan/voice/detector.py` — `OnnxVoiceDetector`
- `src/satyapan/voice/upload.py` — `analyze_voice_upload`
- `src/satyapan/adapters/transcribe_aws.py` — `AwsTranscriber`

## Do not touch
`voice/rules.py` (shared rule), contracts, tests, extension.

## Interfaces
Docstrings in the four files are the spec. Install: `uv sync --extra audio` (numpy + onnxruntime);
`brew install ffmpeg` on macOS.

## Plan (steps)
1. `decode_to_16k_mono` via `subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
   "-i", "pipe:0", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"], input=data,
   capture_output=True, timeout=60)`; non-zero return → `ValueError`; `np.frombuffer(..., "float32")`.
2. `split_windows`, `estimate_speech_seconds` (energy VAD as described).
3. `analyze_voice_upload` per docstring (tests use a fake scorer + fake transcriber).
4. `OnnxVoiceDetector`: `onnxruntime.InferenceSession` for both models; same preprocessing as the
   extension (ask the leader / T07 notes); outputs probability of "fake".
5. `AwsTranscriber` (AWS mode): upload to the evidence bucket, `start_transcription_job` with
   `IdentifyLanguage=True, LanguageOptions=["hi-IN", "en-IN"]`, poll with a deadline.
6. Measure Transcribe vs Whisper on 20 demo clips → `results/asr_compare.csv` (E8).

## Acceptance criteria
`make task T=T17`: decode + windows + VAD; synthetic + OTP ask → both signals; scorer crash →
DETECTOR_ERROR grey; < 3 s → SPEECH_TOO_SHORT; garbage bytes → ValueError.

## Test command
`make task T=T17`

## Definition of Done
Green + `make check`; one real (consented, local-only) voice note scored end-to-end via the console.

## Common mistakes
- Committing audio (forbidden; tests generate tones).
- Different window rule from the extension (always call `classify_windows`).
- Letting an exception escape (must become a grey reason).

## Hints and links
- onnxruntime Python: https://onnxruntime.ai/docs/get-started/with-python.html
- Transcribe language identification: https://docs.aws.amazon.com/transcribe/latest/dg/lang-id.html

## Agent plan (write yours here)
