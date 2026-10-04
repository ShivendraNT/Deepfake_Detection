# Research protocol — "Ask, Not Style"

Working title: *Ask, Not Style: Paraphrase-Robust Fraud-Conversation Detection for Indian English
and Hinglish.* One claim. Public data the team did not author. Pre-registered.

## 1. Research question

Under an adaptive attacker who uses an LLM to rewrite a fraud conversation's **style** while
keeping its **request**, how much do Indian-English/Hinglish fraud-conversation detectors lose at a
fixed false-alarm rate? Do detectors restricted to attacker-invariant "asks" keep their recall?

Motivation: ICFD-31k baselines hint at shortcut learning (RoBERTa 99.6 F1 vs zero-shot Gemma-2
35.8; human κ = 0.534). "Talking Like a Phisher" (arXiv 2507.16291) showed GPT-4o rewrites cut
Korean vishing-classifier accuracy by up to 30.96%. Nobody has tested Hinglish, or the ask/style split.

## 2. Definitions (frozen before any test data is seen)

**Invariant asks** (the scam cannot work without them): A1 transfer to a new/"safe" account;
A2 share OTP/PIN/password/CVV; A3 install remote-access/screen-share app; A4 secrecy/isolation;
A5 bypass a process; A6 gift card/crypto/UPI collect; A7 change of payee/bank details.

**Style cues:** urgency, threat, authority claims, emotional pressure (removable without abandoning
the scam).

## 3. Hypotheses

- **H1:** under style-stripping paraphrase P1, the fine-tuned full-text classifier D3 loses
  ≥ 10 points of recall at 1% FPR. Rejected if the 95% CI of the drop includes values < 10.
- **H2:** ask-based detectors (D4, D6) lose significantly less recall than D3 under P1 (paired
  bootstrap on the difference of drops; rejected if the CI includes 0).
- **H3:** paraphrase-augmented training (D3+aug, generator A) recovers recall on generator-A
  paraphrases but significantly less on generator-B paraphrases.
- **H4 (cost, reported either way):** ask-based detection fires later in streaming; median
  time-to-first-alert vs D3 at matched chunk-level FPR.

## 4. Data, licenses and splits

| Set | Use | Size | License / notes |
|---|---|---|---|
| ICFD-31k train | train D2, D3, D5; build lexicon | 21,000 | **defensive research only; no scam-script generation; no commercial deployment without permission.** Official conversation-level split; streaming chunks inherit it |
| ICFD-31k validation | ALL thresholds, lexicon freeze, calibration | 4,500 | never use test for any choice |
| ICFD-31k test | clean evaluation + paraphrase source | 4,500 | check class balance on download; if normals < 1,000 make recall@5%FPR primary |
| ICFD-31k cross-domain | unseen fraud types | 1,000 | generalisation |
| HF `Indian_Cyber_Scam_PhoneCall_Hinglish_Dataset` | external test only | ~10k | Apache-2.0; if scam-only, report recall at the ICFD-val threshold; never mix sources in one AUROC |
| HF `scam_ham_india_14_languages` (Hinglish + English) | external transfer check | ~2k | MIT; SMS modality |
| P0 / P1 / P2 attack sets | robustness | §5 | generated from **test** only; **never released as text** |

Download manually into `research/_data/` (git-ignored). Never commit dataset text, never paste it
into a free model. The product never ships an ICFD-trained model.

**Pre-registration (do this before touching test):**
1. Freeze `src/satyapan/asks/lexicon.py` → `LEXICON_VERSION = "1.0.0"`; built from ICFD *train*
   + general knowledge only; record which train rows were looked at in `research/LEXICON_LOG.md`.
2. Freeze D3 config (`research/baselines/d3_finetune.py:CONFIG`) and all thresholds
   (`results/thresholds.json`, fitted on validation).
3. `git tag prereg-v1` and push; also a timestamped OSF/GitHub record.

## 5. Attack sets (T20)

| Set | What | Generators | n |
|---|---|---|---|
| P0 | meaning-preserving paraphrase of **normal** conversations (control: LLM-written-ness ≠ fraud) | A, B | 1,000 per generator |
| P1 | style-stripping paraphrase of **fraud** conversations; calm, polite; ask kept | A = Qwen2.5-7B-Instruct, B = Llama-3.1-8B-Instruct or Gemma-2-9B-it (vLLM, Kaggle 2×T4); optional C = Gemini Flash on 500 | 1,000 per generator |
| P2 | ask-obfuscation (indirect phrasing of the ask) — attacks OUR method | A | 500 |

**Meaning-preservation filter** (report discard rate): LaBSE cosine ≥ 0.80; judge LLM from a third
family confirms "same request present; still a fraud attempt" (never sees our lexicon); two team
members label 200 random pairs (ask preserved? fluent? still a scam?) → Cohen's κ; if
human-confirmed preservation < 85%, tighten the prompt and regenerate.

**Before generating P1/P2:** email the ICFD authors describing defensive robustness evaluation.
If refused, run attacks on the Apache/MIT Hinglish sets instead.

## 6. Detectors

| ID | Detector | Code |
|---|---|---|
| D1 | urgency/threat keyword rules | `research/baselines/` (optional) |
| D2 | TF-IDF char 2-5-gram + logistic regression | `research/baselines/d2_tfidf.py` |
| D3 | fine-tuned XLM-R-base / MuRIL-base; RoBERTa-base replication | `research/baselines/d3_finetune.py` (Kaggle) |
| D4 | deterministic ask extractor; score = # distinct ask types | `satyapan.asks.extractor.ask_score` |
| D5 | ask-span classifier (D3 arch on D4-hit turns ± 1) | optional |
| D6 | monotone OR of D4 and D3, thresholds jointly set on validation for 1% FPR | `research/eval/d6.py` |
| D7 | zero-shot open LLM judge (Qwen2.5-7B) | optional reference |
| D3+aug | D3 trained with generator-A P1-style paraphrases of **train** | for H3 |

## 7. Metrics and statistics

- **Primary:** recall at 1% FPR, threshold fixed on ICFD validation.
- 95% CIs: 10,000 conversation-level bootstrap resamples. Differences: *paired* bootstrap.
- **Secondary:** recall@5%FPR, AUROC, FPR shift on P0, streaming earliness (median seconds to first
  alert at matched chunk-level FPR), per-umbrella breakdown, cross-domain and external recall.
- **Ablations:** drop each ask type from D4; D5 vs D4; D6 threshold splits; generator A vs B;
  1 vs 2 paraphrase rounds.
- **Money figure** (`figures/money.png`): x = {clean, P1-A, P1-B, P2}; bars = D2, D3, D3+aug, D4,
  D6; y = recall@1%FPR with 95% CI whiskers; n in the caption. Second small panel: earliness.
- **Residual exposure** (links paper ↔ product): fraction of attacked frauds that still reach PASS
  = 1 − recall(D6) at the operating point, per attack set. Not a claim about the floor.

## 8. Threats to validity (put in the paper)

1. ICFD is synthetic (κ = 0.534) → external sets, cross-domain split, claims relative to clean.
2. Generator overlap with ICFD's generator → check the paper; use two other families; report P0.
3. Lexicon designed by the authors → frozen, train-only, pre-registered.
4. Text only, no ASR noise → optional appendix: TTS → Opus/AMR-NB → Whisper on 300 conversations.
5. License limits → no paraphrase text released; code, redacted prompts, hashes and metrics only.
6. No real base rates or victims → no claims about real-world fraud prevented.

## 9. Secondary engineering evaluation (product slide, not the paper claim) — T18

- Model: Pascu et al. XLS-R-L7 ONNX (reported ITW EER 6.6%, OOD avg 8.4% vs AASIST 11.3%).
- Data: In-the-Wild; HAV-DF audio; IndieFake if downloadable (*to verify*); ~200 bonafide 5 s
  windows of team voices captured **through real Meet tab capture** (consent forms first).
- Channels (ffmpeg): clean, Opus 16 kbps, AMR-NB 12.2 kbps @ 8 kHz, G.711 µ-law @ 8 kHz.
- Speaker-disjoint 50/50 calibration/test; EER; FPR/FNR at τ fixed on clean vs re-fit per channel;
  bootstrap CIs resampled by speaker.
- Decision: τ_hi = score at 1% FPR, τ_lo = 5% FPR on the Meet-captured bonafide calibration set →
  `config/voice_thresholds.json` with `calibration_set_sha256`.

## 10. Exact scripts (create/finish in tasks)

| Script | Task | Output |
|---|---|---|
| `research/metrics.py` | T19 | library |
| `research/data/icfd.py` | T19 | loaders |
| `research/baselines/d2_tfidf.py` | T19 | `results/scores/d2_{split}.csv` (conv_id, score) |
| `research/baselines/d3_finetune.py` | T19 (Kaggle) | `results/scores/d3_{split}.csv` |
| `research/attacks/paraphrase.py` | T20 (Kaggle) | private P0/P1/P2 under `research/_data/attacks/` |
| `research/attacks/filters.py` | T20 | `results/attack_filter_stats.json` |
| `research/eval/d6.py`, `research/eval/run_eval.py` | T21 | `results/research_main.csv` |
| `research/eval/plot_money.py` | T21 | `figures/money.png` |
| `research/audio/channel_eval.py` | T18 | `results/audio_eval.csv`, `config/voice_thresholds.json` |

## 11. Plan and venue

arXiv preprint ~3 weeks after the hackathon; then a 2027 workshop on security, trust or Indic NLP
(check current deadlines — none are assumed). No human-subjects study beyond two annotators.
