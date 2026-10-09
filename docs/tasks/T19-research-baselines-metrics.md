# T19 — Research R1: ICFD loader, D2 + D3 baselines, metrics module

## Goal
The measurement backbone of the paper: a correct recall@FPR + bootstrap metrics module, a loader
for ICFD-31k's official splits, the TF-IDF baseline (D2) on CPU, the fine-tuned transformer (D3)
on Kaggle, and a clean-test results table with CIs. Thresholds come from VALIDATION only.

## Owner
Kartikey (metrics, loader, D2, run_clean) + Shivendra (review, D3 run). Effort ≈ 1.5 days.

## Depends on
T05 frozen (D4 = `satyapan.asks.extractor.ask_score`, lexicon v1.0 tagged).

## Files to create or modify
- `research/metrics.py` — all functions (docstrings are the spec)
- `research/data/icfd.py` — `load_icfd`, `load_jsonl_conversations`
- `research/baselines/d2_tfidf.py` — `train_d2`, `score_d2`
- `research/baselines/d3_finetune.py` — Kaggle script (HF Trainer), writes score CSVs only
- `research/run_clean.py` (new) — fits thresholds on validation, writes results
- `results/thresholds.json` (new), `results/research_clean.csv` (new)

## Do not touch
`src/satyapan/asks/` (frozen), contracts, tests. Never commit ICFD text; `research/_data/` is git-ignored.

## Interfaces
See docstrings. Score CSV format everywhere: `conv_id,score` (no text).
`results/research_clean.csv`: `detector,split,metric,point,low,high,n_pos,n_neg` with metric in
{`recall@1%FPR`, `recall@5%FPR`, `AUROC`}.

## Plan (steps)
1. Metrics with the unit tests (pure numpy). Get these exactly right — the paper depends on them.
2. JSONL loader (tests) → then `load_icfd` after inspecting the real download (document fields).
3. Pre-registration: confirm lexicon v1.0 tag; write D3 CONFIG; `git tag prereg-v1` (leader).
4. D2 on CPU: train on train, score validation + test + cross-domain.
5. D3 on Kaggle 2×T4 (XLM-R-base; MuRIL-base; RoBERTa-base replication): download score CSVs only.
6. D4 scores = `ask_score(text)` for each conversation.
7. `run_clean.py`: thresholds at 1%/5% FPR from validation negatives → `results/thresholds.json`;
   clean-test table with 10,000-resample CIs.

## Acceptance criteria
`make task T=T19`: metric unit tests, loader, D2 toy test, and the committed clean table + thresholds.

## Test command
`make task T=T19`

## Definition of Done
Green + `make check`; class balance of ICFD test noted (if normals < 1,000 → recall@5%FPR primary).

## Common mistakes
- Choosing any threshold or hyper-parameter on test.
- Mixing chunks of one conversation across splits (use official conversation-level splits).
- Unpaired comparisons where the protocol says paired.
- Pasting ICFD conversations into a free model to "debug".

## Hints and links
- ICFD-31k: https://github.com/SPELLAILab/ICFD-31k (license: defensive research only)
- `docs/RESEARCH_PROTOCOL.md` §4, §7

## Agent plan (write yours here)
1. **Metrics module (`research/metrics.py`)**:
   - Implemented `threshold_at_fpr` with exact tie handling and validation-negative search.
   - Implemented `recall_at_threshold` and `fpr_at_threshold` with ValueError validation when positive or negative classes are missing.
   - Implemented `auroc` using vectorized Mann-Whitney U formulation with fractional tie ranks.
   - Implemented `bootstrap_ci`, `paired_bootstrap_diff`, and `paired_drop_diff` using deterministic `np.random.default_rng` resampling with replacement and percentile CIs.
2. **Data loaders (`research/data/icfd.py`)**:
   - Implemented `load_jsonl_conversations` parsing `conv_id`, `label`, `category`, and multi-turn speakers and texts.
   - Implemented `load_icfd` verifying official split sizes (21000/4500/4500/1000) and logging class balances.
3. **D2 baseline (`research/baselines/d2_tfidf.py`)**:
   - Implemented `train_d2` with `TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5))` + `LogisticRegression`.
   - Implemented `score_d2` returning class 1 predicted probabilities.
4. **D3 Kaggle script & clean evaluation pipeline**:
   - `research/baselines/d3_finetune.py` with CLI arguments and frozen pre-registration `CONFIG`.
   - `research/run_clean.py` fitting thresholds on validation negatives only and outputting CIs on clean test.
   - Generated `results/thresholds.json` and `results/research_clean.csv`.
5. **Verification**:
   - All 8 T19 acceptance tests passing 100%.
   - Full suite invariant tests (185 passed) green.
   - Code formatted and checked with `ruff` and `mypy` clean.
