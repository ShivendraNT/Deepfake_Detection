# Investigation dataset — "Operation Pratibimb"

`data/forensics/demo/` holds a realistic multimedia case with ground truth for every file
(`manifest.json`, with SHA-256 of every exhibit). It is the demonstration case of the
dashboard ("Load demo case") and the input of `make lab-benchmark`.

**What is in git and what is built.** The generated images (notice template, forged notice,
the AI "officer" portrait with its Content Credentials, its WhatsApp copy) and the manifest are
committed. Media of real people — the UniData participants' videos and photo, LJSpeech
recordings and the LJSpeech-trained TTS voice — are **never committed** (AGENTS.md data
hygiene); `make demo-dataset` downloads and builds them locally (`scripts/build_demo_dataset.py`,
fixed seeds; network needed once) and `make demo-dataset-check` verifies every file against the
manifest hashes. The committed, signed portrait is kept byte for byte; `--resign` regenerates it
with `scripts/make_ai_portrait.py` (separate environment, SD-Turbo).

## The scenario

**FIR No. 0457/2026, Cyber Crime Police Station (demo), South-West District, New Delhi.**
Sections: BNS 2023 §§ 308(2) extortion, 318(4) cheating, 319(2) cheating by personation,
336(3) forgery, 61(2) conspiracy; IT Act 2000 §§ 66C identity theft, 66D cheating by
personation using a computer resource.

On 21-10-2026 a 68-year-old retired professor (fictional) is told over a WhatsApp video call
by a man posing as an "enquiry officer" that a drugs parcel was seized in his name and that he
is under "digital arrest". He receives a notice on a fictional agency's letterhead, an
"officer ID" photo, a voice note in which his daughter pleads for money, and a Hindi voice
note from the "CBI". He transfers ₹4,50,000. Police seize the suspect's laptop, which holds the
clip and photo the deepfake was built from and the notice template. Months later the defence
offers a "call recording" as proof that the complainant agreed to "invest".

The scenario, its people and the agency on the notice are fictional, and the notice is marked
as a demo exhibit. Real people appear only through public research datasets: the UniData
participants consented to their deepfake dataset (the face swap is UniData's own sample, used
unmodified) and LJSpeech is a public-domain reading corpus; the "daughter" voice note is the
public Piper voice trained on LJSpeech. Teams that prefer their own voices can substitute a
consenting teammate's recordings (`docs/consent/`), kept off git like these.

## Exhibits and ground truth

| File | Role | Ground truth | How it was made | What the lab finds (measured, `make lab-benchmark`) |
|---|---|---|---|---|
| `VID-20261021-WA0003.mp4` | questioned | synthetic | Real phone video with the face swapped by an online face-swap service (UniData sample, unmodified; FFmpeg-encoded) | File alone: only a *weak* face-model elevation (the GenD model misses this swap). Case: same footage as R2 (pHash 0–2 bits on every key frame), a different person (SFace 0.22–0.33), the face of R4 (SFace 0.80–0.83), frame difference concentrated on the face → **SYNTHETIC, strong support, face source attributed** |
| `laptop_seized_clip_0193.mp4` | reference | authentic | The original Android 13 phone recording the deepfake was made from (UniData sample) | Device tag (Android 13, created 2024-09-17), continuous ENF → no indications; noted as the source footage |
| `profile_photo_source.jpg` | reference | authentic | The face image used for the swap (UniData sample) | No indications; noted as the face source |
| `PTT-20261021-WA0007.opus` | questioned | synthetic | Piper TTS voice `en_US-ljspeech-high`, trained on the same speaker as the known sample (a voice clone), WhatsApp-style Opus | Same speaker as R1 (cosine ≈ 0.9). **Missed** as synthetic: the XLS-R detector does not respond to this VITS voice (0 % at 1 % FPR on Piper voices, VALIDATION.md) |
| `daughter_known_voice_sample.m4a` | reference | authentic | LJSpeech public-domain recordings, one continuous take with room noise | No indications; control sample for the speaker comparison |
| `PTT-20261021-WA0009.opus` | questioned | synthetic | Piper Hindi TTS voice `hi_IN-rohan-medium`: "digital arrest", "safe account", OTP | Hindi transcript + English translation with fraud-lexicon hits; 3 of 4 windows above the lenient voice threshold (*weak*). **Missed** as synthetic |
| `call_recording_20261021_1412.wav` | questioned | manipulated | Genuine speech from two sessions with different mains hum (50.020 / 49.965 Hz) and background, joined at 16.54 s | **MANIPULATED, strong support**: one ENF break at 16.5 s, −57 mHz (truth −55 mHz) |
| `notice_template_from_laptop.jpg` | reference | authentic | Fictional notice template, saved once at q92 | No indications (one *weak* grid cue) |
| `IMG-20261021-WA0011.jpg` | questioned | manipulated | Template with addressee and amount pasted from a separately compressed render (splice) and the stamp cloned (copy-move); resized to 1600 px, q82 | **MANIPULATED, very strong support**: cloned stamp (54 keypoints), ELA regions; aligned difference with R3 boxes the edited fields |
| `officer_id_photo_original.png` | questioned | synthetic | SD-Turbo portrait, signed C2PA manifest declaring `trainedAlgorithmicMedia` (throw-away demo CA, not on a trust list). Stability's invisible watermark was applied but cannot be read back from this flat-background image, by the reference decoder or ours | **SYNTHETIC, moderately strong support**: untrusted C2PA AI declaration (*moderate*) + AI-image classifier above its strict threshold (*moderate*) |
| `IMG-20261021-WA0012.jpg` | questioned | synthetic | The same portrait cropped, resized to 400 px and re-compressed (metadata and credentials lost) | Classifier (*moderate*) + copy of Q7 (*moderate*) → **SYNTHETIC, moderately strong support** |

## Licences

* UniData deepfake-videos-dataset sample — CC BY-NC-ND 4.0, consented participants; files
  are copied **unmodified** (their hashes match the source) for non-commercial research use,
  with attribution. Source: `huggingface.co/datasets/UniDataPro/deepfake-videos-dataset`.
* LJSpeech 1.1 — public domain.
* Piper TTS (MIT) and its voices (per-voice licences in `rhasspy/piper-voices`).
* SD-Turbo (Stability AI Community Licence; non-commercial research use).
* Everything else (notice, forgery, call recording mix, Opus encodes) — generated for this
  dataset by Team Satyapan, released with the code.

## Benchmark

`make lab-benchmark` loads the case through the normal intake and grades each verdict
(`results/forensics_demo_benchmark.md`): **9 of 11 correct, 0 false alarms on the 4 genuine
exhibits, 2 missed** (the two TTS voice notes). Two of the nine (the face-swap video and the
WhatsApp copy) are only reached through cross-exhibit comparison; on its own file the video
gets a weak indication only. Large-sample error rates for each technique are in
[VALIDATION.md](VALIDATION.md); this small case demonstrates the workflow and the cross-exhibit
reasoning, not the statistics.
