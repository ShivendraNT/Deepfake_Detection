# T11 — Live transcript path: 10 s chunks → Whisper → ask extractor → SSE

## Goal
During a call, 10-second tab-audio chunks reach the backend, are transcribed locally
(mlx-whisper turbo on the M4), scanned by the T05 ask extractor, combined with on-device voice
windows, re-decided by the policy engine, and pushed to the side panel as server-sent events —
with ask chips ≤ 13 s after the ask is spoken. No LLM in this loop.

## Owner
Shivendra. Effort ≈ 1 day. Critical path.

## Depends on
T05 (ask extractor), T07 (chunks + voice windows from the extension).

## Files to create or modify
- `src/satyapan/live/service.py` — `EventBus`, `LiveService.start/handle_chunk/handle_voice`
- `src/satyapan/adapters/transcribe_whisper.py` — `WhisperTranscriber`
- `src/satyapan/api/routes_live.py` — only if the glue needs a fix
- `extension/offscreen.js` — MediaRecorder chunk upload (shared with T07)

## Do not touch
Policy, contracts, ask lexicon (frozen after T05), tests.

## Interfaces
```python
LiveService(master, transcriber, thresholds)
  .start(call_id, maker_id) -> LiveSession          # case id f"case_live_{call_id}", kind LIVE_CALL
  .handle_chunk(call_id, chunk_index, audio, mime) -> list[LiveEvent]
  .handle_voice(call_id, windows: list[VoiceWindowResult]) -> list[LiveEvent]
EventBus.publish(call_id, event); EventBus.subscribe(call_id) -> asyncio.Queue
```
Routes (already wired): `POST /live/{id}/start`, `POST /live/{id}/chunk`, `POST /live/{id}/voice`,
`GET /live/{id}/events` (SSE). Tests inject `FakeTranscriber` via `AppState.transcriber_override`.

## Plan (steps)
1. `EventBus` (list of queues per call; `put_nowait`).
2. `start` → LIVE_CALL `Case` + session.
3. `handle_chunk`: transcriber → TranscriptEvent; `extract_asks` → AskEvent only for NEW ask
   types; `ask_signals(all spans seen so far)` replaces the earlier ask signals (asks only accumulate); `decide`; BandEvent on
   change with `SUGGESTED_LINES[Lang.EN]` (from T14 templates; fall back to a constant if T14 not done).
4. `handle_voice`: accumulate scores; `classify_windows` over all; replace the voice signal;
   VoiceEvent with `score=None`; BandEvent on change.
5. `WhisperTranscriber`: ffmpeg webm → 16 kHz wav (subprocess) → `mlx_whisper.transcribe(path,
   path_or_hf_repo=DEFAULT_MODEL)`; language auto. Import mlx lazily inside `__init__`.
6. Measure on 10 Hinglish clips: chunk → chip seconds. Record in `results/dry_runs.csv` notes.

## Acceptance criteria
- `make task T=T11`: transcript/ask/band events, no duplicate chips, voice rule, SSE bus, API route.
- Manual: a Hinglish test clip produces ask chips in ≤ 13 s on the M4.

## Test command
`make task T=T11`

## Definition of Done
Green tests + `make check` + measured latency in STATUS notes.

## Common mistakes
- Calling an LLM per chunk (latency + cost + injection surface). Never.
- Sending voice scores to the panel (makers see labels only).
- Losing earlier asks when a later chunk has none (keep all asks seen in the call).

## Hints and links
- mlx-whisper: https://github.com/ml-explore/mlx-examples/tree/main/whisper
- FastAPI streaming responses / SSE: https://fastapi.tiangolo.com/advanced/custom-response/

## Agent plan (write yours here)
