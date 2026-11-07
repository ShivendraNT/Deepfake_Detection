# Methodology

How Satyapan Forensic Lab examines multimedia evidence, from intake to report. Every
technique below is in `src/satyapan/forensics/` and listed with its method and reference by
`GET /lab/api/techniques`; the report's methodology section is generated from the same text.

## 1. Evidence handling (forensic integrity)

Follows the ISO/IEC 27037 principles of auditability, repeatability, reproducibility and
justifiability.

| Step | What happens | Code |
|---|---|---|
| Hash first | MD5, SHA-1 and SHA-256 of the raw upload, computed before any parser touches it. MD5/SHA-1 are recorded because seizure memos and FSL worksheets in India still quote them; SHA-256 is the identity used everywhere else. | `filetype.hashes`, `service.add_evidence` |
| True format | Format from magic bytes, not the extension; a mismatch (e.g. a video renamed `.jpg`) becomes a finding. | `filetype.sniff` |
| Write-once store | Original saved under `evidence/<case>/<sha256>`, permissions read-only, never modified; duplicates in a case are detected by hash. | `store.write_once` |
| Re-verification | Before every analysis the stored copy is re-hashed; a mismatch aborts the analysis and appends an `INTEGRITY_FAILURE` row to the custody chain. | `service.analyze_now` |
| Custody chain | Every action (case opened, intake, analysis with the SHA-256 of its result, report with the SHA-256 of the PDF) is a row in an append-only SQLite log where each row hash covers the previous row hash. Any edit, deletion or re-ordering breaks verification. | `satyapan.vault.custody` |
| Exhibit marks | Questioned items `Q1, Q2, …`, known/reference samples `R1, R2, …`, as in FSL practice. | `service._next_exhibit` |
| Offline | All models run locally (ONNX Runtime / CPU); no network calls exist outside `satyapan/adapters/` (enforced by `tests/invariants/test_network_boundary.py`). | — |

## 2. Techniques

Strengths are on the ENFSI verbal scale: weak, moderate, strong, very strong support for a
hypothesis — *synthetic* (AI-generated / deepfake), *manipulated* (edited after capture) or
*authentic* (unaltered capture). Context findings (a GPS fix, a platform trace, fraud
language in a transcript) carry no weight in the verdict.

### Images

| Technique | Method | Can support |
|---|---|---|
| File structure & compression | JPEG segments (APPn, COM, DQT, DHT, SOF, trailing bytes after EOI) and PNG chunks are parsed byte by byte; JPEG quality estimated by matching the quantisation tables to IJG tables 1–100. | manipulated (data appended after the image) |
| Metadata | EXIF (incl. GPS), XMP (incl. edit history) and IPTC are extracted and cross-checked: capture vs modify time, EXIF vs actual pixel size (crop/resize), editing software. | manipulated (weak–moderate), context |
| Generator & platform signatures | Prompt/seed blocks of Stable Diffusion front-ends (A1111, ComfyUI, InvokeAI, NovelAI), IPTC `DigitalSourceType = trainedAlgorithmicMedia`, AI-system fields, Meta's `FBMD` marker, messaging-app and camera naming. | synthetic (strong–very strong), context |
| EXIF thumbnail | The preview cameras embed is compared with the main image (correlation, mean difference, aspect ratio after removing letterbox bars). Editors that keep the old EXIF block leave the original picture behind. | manipulated (moderate–strong) |
| Content Credentials (C2PA) | Manifest read and validated with the C2PA SDK: signer, claim generator, actions, digital source type, hard-binding hash. | synthetic (very strong, signed AI declaration), manipulated (strong, hash mismatch), authentic (signed capture) |
| Stable Diffusion watermark | NumPy re-implementation of the `invisible-watermark` dwtDct decoder (bit-exact against the library); bits compared with the SDXL, SD 1.x and SD 2.x messages; binomial chance probability reported. | synthetic (very strong) |
| Error Level Analysis | Re-compression at q90; error normalised by local texture; robust z-scores; connected anomalous regions. | manipulated |
| Noise inconsistency | Per-block noise σ from the finest Haar diagonal band (MAD estimator); robust outlier regions. | manipulated |
| Copy-move | SIFT self-matching, generalised 2-NN ratio test, RANSAC similarity transforms; a compact dominant group of matching keypoints = a cloned region. | manipulated |
| JPEG grid / double compression | Blockiness at the 8 grid offsets: shifted or secondary grids reveal crop-and-re-save; a grid in a lossless file reveals earlier JPEG compression. | manipulated, context |
| AI-generated image classifier | Community Forensics ViT (trained on 2.7 M images from 4,803 generators) on the whole image + a native-resolution centre crop. | synthetic (moderate–strong) |
| Faces | Up to four faces (YuNet + MediaPipe), 224-px crops scored by GenD (CLIP ViT-L/14); occlusion maps show which face regions drove a high score. | synthetic (moderate–strong) |
| Spectral residual | Fourier spectrum of the noise residual; periodic peaks off the JPEG lattice. | visual aid only |

### Audio (also the audio track of videos)

| Technique | Method | Can support |
|---|---|---|
| Container & encoder | ffprobe: codec, rate, channels, bit rate, tags; encoder strings, voice-note formats, TTS tool names. | synthetic (moderate), context |
| Spectrogram & bandwidth | STFT spectrogram; long-term average spectrum of active frames; a brick-wall cut-off below Nyquist reveals an earlier sample rate (telephone, VoIP, TTS) or a lossy codec. | context (history) |
| ENF | The 50 Hz grid hum (and harmonics) is band-passed and tracked with zero-padded 4-s STFT frames and quadratic interpolation; a continuous trace supports an unedited recording, an abrupt jump marks a splice. | manipulated (strong), authentic (moderate) |
| Splice & edit points | Exact digital silence inside a noisy recording, steps in the background noise floor (10th-percentile energy per 2-s window), isolated waveform discontinuities, plus ENF jumps. | manipulated |
| Synthetic voice | XLS-R wav2vec2 model fine-tuned for deepfake speech (selected on In-the-Wild), 5-s windows with ≥ 1.5 s of speech (Silero VAD on loudness-normalised audio); plus the open-TTS head (see VALIDATION). | synthetic |
| Transcript & fraud language | Whisper `small` offline with language detection (Hindi, English, Hinglish…), English translation for non-English speech, hallucination filter; the text is matched against the deterministic fraud lexicon (OTP, "safe account", secrecy, remote access, digital arrest…). | context (modus operandi) |

### Video

| Technique | Method | Can support |
|---|---|---|
| Container, device & encoder | Brand, streams, frame rate, rotation, Apple/Android device tags and location, encoder (FFmpeg = not a camera original), synthetic-video tool names, audio/video track length mismatch. | manipulated (weak), synthetic (moderate), context |
| Frame integrity | All frames at 96×54: duplicated frames inside motion, colour-histogram cuts, presentation-timestamp gaps; regular duplicates are attributed to frame-rate conversion; contact sheet. | manipulated |
| Deepfake face timeline | Faces tracked at 15 fps; a GenD crop every 2.25 s; 6-s windows (3-s hop) fuse crop scores with blink, landmark-jitter, remote-PPG and lip-sync cues; two consecutive windows above the 1 % threshold = likely synthetic. | synthetic |

### Across exhibits

Perceptual hashes (pHash, dHash), SFace face embeddings, WeSpeaker speaker embeddings and
the device / generator strings of each exhibit are compared with every other exhibit in the
case. Two images that share content are aligned (SIFT + RANSAC homography) and their
difference map shows exactly what was changed — the derivation of a forgery from its source.

## 3. The verdict rule table

`satyapan/forensics/verdict.py`, applied in order:

1. **SYNTHETIC** — any finding gives *strong* or *very strong* support to "synthetic".
   Confidence is *very strong* if a finding is very strong or two techniques are strong.
2. **MANIPULATED** — any *strong* support for "manipulated", or two different techniques
   each give at least *moderate* support.
3. **SUSPICIOUS** — any *moderate* synthetic/manipulated finding, or three different
   techniques with *weak* support for manipulation.
4. **INCONCLUSIVE** — fewer than two authenticity techniques (synthetic or tampering
   category) could run on the file.
5. **NO INDICATIONS** — otherwise; worded "this does not prove the item is authentic", with
   positive indicators (signed capture, continuous ENF, consistent thumbnail) stated.

**Indicative techniques are capped.** ELA, noise inconsistency and the JPEG-grid analysis produce maps an examiner reads, not proof (SWGDE): their findings never exceed *moderate* support. A MANIPULATED verdict therefore needs a structural finding (a cloned region, a thumbnail that shows a different picture, a broken C2PA hash, a mains-frequency jump, appended data, missing frames) or two independent techniques agreeing. Before this cap, 2 of 40 genuine photographs were called manipulated on the strength of one noise map.

The rule is deterministic and unit-tested (`tests/forensics/test_verdict.py`); no model can
by itself produce MANIPULATED from a weak signal, and a missing model can only make a
verdict less certain, never more. The 0–100 "risk index" on the dashboard is derived from the
same rule for display only; the words are authoritative.

## 4. Operating points

Every statistical technique has two thresholds fitted on genuine data *before* testing:

| Technique | Lenient (moderate) | Strict (strong) | Fitted on |
|---|---|---|---|
| AI-image classifier | 5 % of real photos | 1 % | Defactify validation reals (MS COCO) |
| Face model (photos) | 5 % of real face crops | 1 % | FaceForensics++ c23 validation |
| Face model (video windows) | 5 % of real windows | 1 % | FaceForensics++ c23 validation, original quality |
| Synthetic voice (XLS-R) | 5 % of genuine 5-s clips | 1 % | In-the-Wild validation, clean/Opus/GSM |
| ELA, noise, copy-move, JPEG grid | 0.5 % of genuine photos (moderate), 2 % (weak) | 0.1 % | 300 MS COCO photos (`results/forensics_classical.json`) |

## 5. Reporting

`satyapan/forensics/report/builder.py` builds the PDF: cover with QR verification code (report
number, case, custody head, exhibit hashes), summary of conclusions, exhibits and hash
values, methodology and models present, one examination section per exhibit (verdict box,
media facts, findings table, figures, provenance and reconstructed history, technique log,
what could not be checked, known limits), relationships between exhibits, the custody chain
with its verification result, known error rates, a **draft certificate under Section
63(4)(c) of the Bharatiya Sakshya Adhiniyam, 2023 (Part B, expert)** pre-filled with the hash
values, and a glossary. The draft is for the examiner to verify and sign by hand — the
software never signs, submits or files anything.

## 6. Standards and references

ISO/IEC 27037:2012 (digital evidence handling); ISO/IEC 17025 (lab competence, for
accreditation); SWGDE Best Practices for Image Authentication and for Digital Audio
Authentication; ENFSI Guideline for Evaluative Reporting in Forensic Science (2015); C2PA
Technical Specification 2.1; IPTC Photo Metadata Standard; Bharatiya Sakshya Adhiniyam 2023
s.63; IT Act 2000 s.79A (Examiner of Electronic Evidence). Method references per technique
are in the report and in `GET /lab/api/techniques`.
