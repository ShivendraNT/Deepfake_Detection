# Investigation dataset — "Operation Pratibimb"

`data/forensics/demo/` holds a realistic multimedia case with ground truth for every file
(`manifest.json`). It is the demonstration case of the dashboard ("Load demo case") and the
input of `make lab-benchmark`. Rebuild it with `make demo-dataset`
(`scripts/build_demo_dataset.py`, fixed seeds; the AI portrait with
`scripts/make_ai_portrait.py`).

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

Every person is fictional; no real person's voice or likeness is cloned. The agency on the
notice is fictional and the document is marked as a demo exhibit.

## Exhibits and ground truth

| File | Role | Ground truth | How it was made | Expected evidence |
|---|---|---|---|---|
| `VID-20261021-WA0003.mp4` | questioned | synthetic | Real phone video with an AI-generated face overlaid by an online face-swap service (UniData sample, unmodified) | face-model elevation; same face as the profile photo; same scene as the seized clip |
| `laptop_seized_clip_0193.mp4` | reference | authentic | The genuine iPhone recording the deepfake was made from (UniData sample) | device tags (iPhone 13), continuous ENF, no face indications |
| `profile_photo_source.jpg` | reference | authentic | The face image used for the swap (UniData sample) | same-face link to the deepfake |
| `PTT-20261021-WA0007.opus` | questioned | synthetic | Piper TTS voice trained on the same speaker as the known sample (a voice clone), WhatsApp-style Opus | same speaker as R-sample; synthetic voice; secrecy/money asks in transcript; digital-silence joins |
| `daughter_known_voice_sample.m4a` | reference | authentic | LJSpeech public-domain recordings, one continuous take with room noise | control sample for speaker comparison |
| `PTT-20261021-WA0009.opus` | questioned | synthetic | Piper Hindi TTS voice (hi_IN rohan): "digital arrest", "safe account", OTP | synthetic-voice evidence; Hindi transcript + English translation; fraud lexicon hits |
| `call_recording_20261021_1412.wav` | questioned | manipulated | Genuine speech from two sessions with different mains-hum frequency (50.02 / 49.965 Hz) and background noise, joined at 19.4 s | ENF discontinuity + noise-floor step at the join |
| `notice_template_from_laptop.jpg` | reference | authentic | Fictional notice template, saved once at q92 | source of the forgery |
| `IMG-20261021-WA0011.jpg` | questioned | manipulated | Template with addressee and amount pasted from a separately compressed render (splice) and the stamp cloned (copy-move); resized to 1600 px, q82 | copy-move, ELA anomaly, aligned difference with the template boxing the edited fields |
| `officer_id_photo_original.png` | questioned | synthetic | SD-Turbo portrait with Stability's reference watermark and a signed C2PA manifest declaring `trainedAlgorithmicMedia` (throw-away demo CA) | C2PA AI declaration, SD watermark, AI-image classifier |
| `IMG-20261021-WA0012.jpg` | questioned | synthetic | The same portrait cropped, resized to 400 px and re-compressed (watermark and credentials lost) | AI-image classifier only; near-duplicate of the original |

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

`make lab-benchmark` loads the case through the normal intake and grades each verdict;
results in `results/forensics_demo_benchmark.md`. Large-sample error rates for each technique
are in [VALIDATION.md](VALIDATION.md); this small case demonstrates the workflow and the
cross-exhibit reasoning, not the statistics.
