# Data, ethics and AI-tool policy

Short version: **fake data in the repo, consented data only on the leader's machine, and nothing
real ever goes into a free AI model.**

## 1. Rules for everyone

1. **No real PII in the repo.** Demo data is synthetic and obviously fake: companies on `*.example`,
   banks "Fictional Bank A-E", IFSC `FAK…`, account numbers `9999…`, phones `+91-00000-…`,
   GSTINs with state code `00`, UTRs `FAKEUTR…`. `tests/contracts/test_fixtures.py` checks this.
2. **No media in the repo.** No `.wav/.mp3/.ogg/.mp4/.webm` (test enforced). Tests generate tones.
   Research video data lives **outside** the checkout (`$SATYAPAN_VIDEO_DATA`, default
   `../satyapan-data/video`); only manifests (path, sha256, label, split) are committed.
3. **Nothing real in prompts to free models.** OpenCode Zen free models (some may train on data,
   e.g. big-pickle), Gemini free tier and others may use prompts for training. Never paste: real
   or consented voices/videos, bank details, customer data, ICFD text or paraphrases, API keys.
4. **Secrets** live only in `.env` (git-ignored). `opencode.json` denies agents reading `.env`.

## 2. Team voice clones (demo + calibration)

- Every teammate whose voice is cloned or recorded signs `docs/consent/VOICE_CLONE_CONSENT_TEMPLATE.md`
  **before** any recording. Signed copies are kept offline by the leader (not in git).
- Clips live in a local folder outside the repo; deleted 30 days after the hackathon unless the
  person re-consents for the paper.
- Clones are generated on Colab (F5-TTS / XTTS-v2) from the consenting person's own recordings
  only. Never clone anyone else.

## 3. Datasets and model licenses

| Asset | License / terms | What we may do | What we may NOT do |
|---|---|---|---|
| ICFD-31k | defensive research only; no scam-script generation; no commercial deployment without written permission | train/evaluate research detectors; report metrics | release paraphrase text; ship an ICFD-trained model in the product; generate scripts without emailing the authors first |
| HF Indian_Cyber_Scam_PhoneCall_Hinglish_Dataset | Apache-2.0 | external test | mix into one AUROC with ICFD |
| HF scam_ham_india_14_languages | MIT | transfer check | — |
| Pascu et al. browser-plugin ONNX models | **no license file** | use locally, cite, email authors on Day 1 | commit or redistribute the `.onnx` files |
| In-the-Wild, HAV-DF, IndieFake | check each license before download | evaluation | redistribution of audio |
| FaceForensics++ c23 (Rossler et al. 2019; official splits from github.com/ondyari/FaceForensics) | FF++ terms: non-commercial research; files read from the public HF mirror `gonnerthetooner/FaceForensics` (copy of Kaggle `xdxd003/ff-c23`) | train the blend CNN on **real** videos only; fit the fusion on train; thresholds on val; evaluate on test | commit any frame/crop/video; redistribute the trained `blend_b0.onnx` outside the team; use it commercially without retraining on licensed data |
| DFDC train parts 0-2 (Dolhansky et al. 2020; paid, consenting actors) | DFDC terms: research; HF mirror `gonnerthetooner/DFDC-extracted-full` | cross-dataset **test only** (never trained or tuned on) | redistribute videos or audio |
| Piper TTS `en_US-ryan-medium` | public synthetic voice (MIT/CC per rhasspy/piper-voices) | the "real face + synthetic voice" lip-sync test | — |
| MediaPipe Face Landmarker (`face_landmarker.task`) | Apache-2.0 | face tracking in the product and the benchmark | — |
| SSL_Anti-spoofing (backup) | *verify license* | — | — |

## 4. DPDP Act 2023 data-flow table (lawful basis to confirm with counsel)

DPDP Rules notified Nov 2025; most fiduciary obligations phase in ~18 months later (≈ May 2027),
per secondary summaries — *verify on the PIB text*.

| Data | Processed where | Stored | Retention | Basis |
|---|---|---|---|---|
| Live Meet audio (remote party) | on-device (voice score); transcript: local whisper (demo) or Transcribe ap-south-1 (AWS mode) | **not stored** unless the user taps "save last 30 s as evidence" | saved clips 30 days; longer only if case is suspected/confirmed fraud | employer: s.7(i) employment / safeguarding from loss; counterparty: transient processing; retention relies on s.17(1)(c) offence-prevention exemption |
| Emails, invoices, voice notes | backend (Mac in demo; ap-south-1 in prod) | S3 ap-south-1, SSE | 90 days or life of case + export | same |
| LLM summaries | local Ollama model on the backend machine (nothing leaves it) | case DB | life of case | same |
| Employee directory, vendor master | backend | DB | while the contract lasts | contract / employment |

Everywhere: no consent banner is relied on for counterparties; the extension shows the *user* a
visible "Protection on" indicator; no data leaves Indian regions in AWS mode.

## 5. Reporting and sharing

- Reports are drafts; a human submits them. We never auto-report and never share victim media with
  third parties. No peer hash sharing.
- CONFIRMED_FRAUD can only be set by the checker or security lead.
