# Validation: measured accuracy, error rates and failure cases

Courts weigh scientific evidence by its known error rate. Every statistical technique in the
lab was chosen and calibrated on validation data with a rule written down before testing, and
then measured once on held-out data. The numbers below are reproducible with the commands
given; raw outputs are in `results/`.

## Summary

| Technique | Test data (held out) | Result | Reproduce |
|---|---|---|---|
| AI-generated image classifier (Community Forensics ViT) | Defactify test shard: 400 MS COCO photos vs 400 images from SD 2.1, SDXL, SD 3, DALL·E 3, Midjourney v6 | AUC **0.876** (0.890 after normalising size/format); at the strict threshold **52 %** of AI images flagged with **2.5 %** of real photos flagged; lenient: 65 % / 6.8 % | `python -m research.forensics.aigen_select` → `results/aigen_selection.json` |
| Face-swap detector, video (GenD + temporal fusion) | FaceForensics++ c23 test; DFDC (never seen) | AUC **0.946** (FF++), 0.778 (DFDC); **0 of 563** real videos called synthetic | `docs/VIDEO_DEEPFAKE.md`, `results/video_benchmark.md` |
| Face-swap detector, photo crops | FF++ / DFDC face crops | AUC 0.923 / 0.747; 0.4 % / 0.0 % of real crops over the strict threshold | `results/image_face_benchmark.md` |
| Synthetic voice (XLS-R, gustking) | In-the-Wild (real-world deepfakes, speakers never seen) | AUC **0.921** clean, 0.909 through Opus; 0.6 % of genuine voices flagged | `docs/VOICE_DEEPFAKE.md` |
| Classical tampering detectors (ELA, noise, copy-move, JPEG grid) | 300 genuine COCO photos + 450 synthetic forgeries made from them | genuine photos flagged at the moderate level: **2.7 %**; copy-move detected **41 %**; splice flagged by any detector **6 %**; crop-and-recompress **3 %** | `python -m research.forensics.classical_calib` → `results/forensics_classical.json` |
| Speaker comparison (WeSpeaker ResNet34, our NumPy Kaldi front end) | LJSpeech (1 speaker, 15 pairs) and LibriTTS-R (8 speakers, 8 same + 28 different pairs) | same-speaker cosine 0.62–0.89; different speakers ≤ 0.45 (95th pct 0.36); link threshold 0.55; the Piper clone of the LJSpeech voice scores **0.90** against the real speaker, ≤ 0.19 against others — a clone resembles its victim, so a voice link plus synthesis evidence reads as "cloned from" | small sanity check, reproduced by `tests/forensics/test_signal_techniques.py::test_fbank_*` and this table |
| Watermark decoder | bit-exact against `invisible-watermark` | identical bits; chance probability of a false match ≤ 10⁻⁹ for SDXL (48 bits) | `tests/forensics/test_signal_techniques.py` |
| ENF and splice cues | synthetic hum traces (continuous vs spliced), digital-silence and noise-floor joins | continuous traces show no jump; spliced traces flagged within 3 s of the join | `tests/forensics/test_signal_techniques.py` |

## Selection protocols (pre-registered)

**AI-generated image classifier.** Five permissively licensed candidates were compared on a
Defactify validation shard (150 real + 150 AI images) under two conditions, *native* and
*normalised* (centre square crop, 512 px, JPEG q90 — because the dataset's real and AI images
differ in size and aspect, a model could learn those instead). Rule: highest normalised AUC
wins; thresholds = 95th / 99th percentile of real-image scores, the larger of the two
conditions. Result: Community Forensics 0.952, SwinV2 (haywoodsloan) 0.949 but 3× slower,
Organika SDXL detector 0.899, SigLIP (Ateeqq) 0.886; one candidate could not be mapped to a
binary label. The winner was then scored once on a different shard (table above).

**Classical tampering detectors.** Before calibration they flagged 15 of 40 genuine photos.
Each detector now outputs one statistic; thresholds are the 98th / 99.5th / 99.9th percentile
on 300 genuine COCO photos (weak / moderate / strong), measured on a separate 300.

**Voice.** The XLS-R model was selected in the earlier pre-registered comparison of five
candidates on In-the-Wild (`docs/VOICE_DEEPFAKE.md`).

## Failure cases we found (and what we did)

1. **Open-source neural TTS evades the shipped voice detector.** A probe on 47 genuine clips
   (LJSpeech, LibriTTS-R) vs 42 clips from 8 Piper voices (English and Hindi), all through
   WhatsApp-like Opus, gave AUC 0.652 for the shipped model and 0 % detection at 1 % false
   alarms; the other candidates did no better (best: AST-ASVspoof5, AUC 0.841, 40 %)
   (`results/voice_tts_probe.json`). We therefore trained a second head on the same XLS-R
   features (`research/forensics/opentts_head.py`): training voices and test voices are
   disjoint, test speakers are unseen, Hindi real speech (FLEURS) is in both. Results and the
   ship/no-ship decision: `results/voice_opentts_head.json` and the section below.
2. **Modern online face-swap services are only partly caught.** On the consented UniData
   sample deepfakes (AI faces overlaid by aisaver.io-style services) the face timeline scores
   0.68–0.95 against 0.09–0.63 for real phone videos: fakes rank above reals, but most stay
   below the strict 1 % threshold, so the verdict is *suspicious*, not *synthetic*. GenD was
   trained on FaceForensics++ face swaps; the cross-exhibit links (same face as a profile
   photo, same scene as a seized clip) carry these cases.
3. **Splices in small, re-compressed photos are rarely caught by classical methods** at a
   false-alarm rate a court can accept (6 %). The aligned comparison against a recovered
   source (when one exists) shows the edited regions directly; a learned localiser (e.g.
   TruFor) is on the roadmap.
4. **Whisper hallucinates on silence and music** (e.g. 223 words for a 10-s near-silent
   clip). Segments with high compression ratio, punctuation-only text, repetition loops or
   impossible word rates are now dropped, and VAD runs on loudness-normalised audio.
5. **Generator signatures are fragile.** C2PA manifests and the SD watermark disappear when
   an image is screenshotted, resized or re-encoded (see exhibit `IMG-20261021-WA0012.jpg`);
   only the pixel-level classifier remains. Absence of a signature is never evidence of
   authenticity.

## Open-TTS voice head

See `results/voice_opentts_head.json` (written by `research/forensics/opentts_head.py`).
