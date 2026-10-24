# Test kit: every benchmark, how to reproduce it, and what it may claim

The finale asks for "the test workflow, open datasets, reproducibility instructions, results, and
the generation code of any synthetic data; completeness matters as much as accuracy". This page
is the index. Each row links to the script that produced a committed result file; every number
we may show is also in `results/EVIDENCE_LEDGER.md`.

## 1. One command per suite (any OS, CPU only)

```bash
uv sync --extra video --extra video-research      # or the pip fallback in README
python -m research.run_all --list                 # every stage and its exact command
python -m research.run_all text                   # scam-text benchmark       (~1.5 h, 4 cores)
python -m research.run_all video                  # video face check + baselines (~10 h, 4 cores)
python -m research.heldout.run_eval               # ask extractor, held-out set (seconds)
python -m research.alert_budget.run_alert_budget  # alert budget through the real policy path
python -m research.redteam.run_deterministic      # deterministic red team
python research/seal/run_codec_eval.py --workers 2   # Satyapan Seal through 14 codec chains
make check                                        # 560+ unit, contract and invariant tests
```

Data is downloaded from public mirrors by the scripts themselves and stored **outside** the repo
(`$SATYAPAN_TEXT_DATA`, `$SATYAPAN_VIDEO_DATA`, default `../satyapan-data/`); every file is
pinned by sha256 in `results/*_manifest.json`. Stages are deterministic (`SEED = 20261024`) and
resumable (`--from <stage>`).

## 2. Completeness: every detector Satya ships, and the test behind it

| Satya component | Decides | Benchmark (open data) | Split / selection | Result file | Status |
|---|---|---|---|---|---|
| Video face check (shipped): GenD crop CNN + 2-window rule | `VIDEO_LIKELY_SYNTHETIC` (ML, capped) | FF++ c23 (official splits), FaceShifter (unseen method), DFDC (unseen dataset); orig + 2 simulated call channels | chosen on val by a rule fixed in advance (`results/video_selection.json`); τ on val reals; test once | `results/video_benchmark.md` | measured |
| Video face check (fallback): our SBI CNN + fusion | same | same | CNN on train reals only; fusion by identity-grouped 5-fold CV + 1-SE rule; τ on val reals; test once | `results/video_benchmark__blend.md` | measured |
| Off-the-shelf video detectors (Hugging Face): GenD, MS-EffGCViT, 2 popular ViT "deepfake" classifiers, CommunityForensics | baselines / candidates for the CNN slot | same videos and crops as above | rule fixed before scoring (`docs/VIDEO_DEEPFAKE.md` §5b) | `results/video_external.md` | measured |
| Photo face check (one GenD crop) | `IMAGE_FACE_*` (ML; SUSPICIOUS → VERIFY) | FF++ c23 test, DFDC: one crop = one photo | τ on single val real crops; test once | `results/image_face_benchmark.md` | measured |
| Lip-sync cue | part of the face check | DFDC reals with own / swapped / TTS / 1 s-delayed audio | zero parameters | `results/video_lipsync.json` | measured |
| Scam-text classifier | `TEXT_SCAM_LIKELY` (STYLE, capped at VERIFY) | 7 open sets: phishing e-mail, CLAIR fraud, UCI SMS, Indian SMS, 14-language Indian scam/ham, Hinglish scam calls, scam dialogues | template-dedup + group splits; C by GroupKFold CV; τ on val; test once; leave-one-dataset-out | `results/text_benchmark.md`, `results/text_neardup.md` | measured |
| Text evasion robustness | same | the fraud test texts after 5 code-generated attacks | frozen model and τ | `results/text_benchmark.md` §robustness | measured |
| Text transformer baseline (multilingual-e5-small + LR) | comparison only | same 7 sets | same protocol | `results/text_embed_baseline.md` | measured |
| Ask extractor (payment asks) | ask chips + `ASK_*` signals | S-HO held-out texts (written before the lexicon was opened) | dev/test split; frozen lexicon | `results/asks_heldout_eval.json` | measured |
| Policy engine (bands) | PASS / VERIFY / HOLD | S-AB synthetic payment cases through the real decision path | — | `results/alert_budget.json` | measured |
| Safety invariants (raise-only, LLM cap, floor isolation) | — | property tests, 200 examples each | — | `tests/invariants/` | measured |
| Satyapan Seal | caller authenticity | SYN-V synthetic voices through 14 codec chains + Chrome WebRTC | — | `results/seal_*.json` | measured (illustrative) |
| Voice-clone detector: XLS-R layers 1–7 + LR (ours) vs 4 Hugging Face models | `VOICE_*` | ASVspoof 2019 LA train → In-the-Wild (speaker-disjoint val/test) + ASVspoof 2019 eval (13 attacks); clean, Opus 16 kbps, GSM | gate + selection on val (rule fixed first, `docs/VOICE_DEEPFAKE.md` §4); τ on val bonafide; test once | `results/voice_benchmark.md` | running (24 Oct) |
| Whole product on any files (the judges' kit) | band per file | any folder of files; names starting `fake…`/`real…` are graded | nothing fitted | `satya scan KIT/` → `<out>.csv/.md` | runner |

## 3. Synthetic data: what we generated and the code that generates it

| Synthetic data | Used for | Generation code |
|---|---|---|
| Self-blended images (a real face blended onto itself) | **training** the blend CNN (never tested on) | `research/video/sbi.py`, `research/video/sbi_prep.py` |
| Simulated call channels (VP8 at 1.2 / 0.4 Mbit/s + JPEG q85) | robustness conditions `call720`, `call360` | `research/video/extract.py` (`CONDITIONS`, ffmpeg) |
| Audio-visual mismatches (swapped, Piper TTS, 1 s delay) | lip-sync test | `research/video/lipsync_eval.py` |
| Obfuscated scam texts (homoglyph, leet, zero-width, spacing, combined) | text robustness | `research/text/attacks.py` (seeded per text) |
| Held-out ask texts S-HO and payment cases S-AB | ask extractor, alert budget | `research/heldout/README.md`, `research/alert_budget/synth.py` |
| TTS voices SYN-V | Seal | `research/seal/gen_voices.py` |

Two text sets are synthetic **by their authors** (Hinglish scam calls, scam dialogues); they are
flagged in `research/text/data.py` and reported separately, never pooled into a headline.

## 4. Rules every benchmark follows

1. **Leakage-safe splits.** Video: identity-disjoint official FF++ splits; DFDC only as a test
   set. Text: near-duplicate templates collapsed, splits by template group, official test rows
   whose template occurs in train are dropped (and counted).
2. **Selection on train/val only.** Hyper-parameters by grouped cross-validation on train;
   thresholds (τ_hi = 1 % FPR, τ_lo = 5 %) on validation negatives; the test split is scored
   once, after everything is frozen. Choices made before seeing a test number are committed
   first (git history), e.g. the Hugging Face selection rule.
3. **Honest intervals.** AUC/AP: 95 % bootstrap over identity or template clusters (2,000
   resamples); rates: Wilson 95 %. Paired differences on the same items.
4. **Shortcut checks.** Video: face size and brightness alone as "detectors"; text: zero-shot
   lexicon and leave-one-dataset-out next to the in-domain numbers.
5. **Provenance.** No result file may be written by code that uses an unseeded RNG
   (`tests/harness/test_results_provenance.py`); no media or message text is committed
   (`tests/contracts/test_fixtures.py::test_no_media_files_in_repo`).

## 5. Headline numbers (held-out test sets, scored once; full rows in `results/EVIDENCE_LEDGER.md`)

| Channel | Test (never used to fit) | Catches | False alarms on genuine items | Named failure case |
|---|---|---|---|---|
| Scam text (messages, e-mails, transcripts, OCR) | 7 open sets; leave-one-dataset-out | AUC 0.989–1.000 in-domain; 96.2 % of fraud texts under a combined obfuscation attack | 0.0–2.6 % per set at τ_hi | a never-seen source drops to AUC 0.69 (phishing e-mail) |
| Face in a video | FF++ c23 test, DFDC (unseen) | 74.7 % / 24.8 % of fakes flagged for a call-back | 0 of 563 real videos called synthetic; 1.2 % flagged for a call-back | unseen method FaceShifter 32 %; small faces at 360p → "couldn't check" |
| Face in a photo | same, one crop each | AUC 0.923 / 0.747 | 0.4 % / 0.0 % of real crops over τ_hi | expression-only edits (NeuralTextures) |
| Voice clone | In-the-Wild test, ASVspoof 2019 eval | running | running | see `docs/VOICE_DEEPFAKE.md` §5 |
| Asks (OTP, new account, secrecy…) | S-HO held-out texts (test split) | recall 0.33 [0.24, 0.42], precision 0.60 | 11.5 % of benign texts get a false ask | paraphrased asks are mostly missed: the text model and the call-back step carry them |

Video numbers: `docs/VIDEO_DEEPFAKE.md` §6/§8. Text: `docs/TEXT_BENCHMARK.md`. Any kit of files:
`uv run python scripts/satya.py scan KIT/` prints the band, why, and what could not be checked
for every file, and grades files whose names start with `fake…`/`real…`.
