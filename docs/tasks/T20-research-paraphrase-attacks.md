# T20 — Research R2: paraphrase attack sets P0/P1 (+P2) and meaning-preservation filters

## Goal
Generate style-stripping paraphrases of ICFD **test** frauds (P1), meaning-preserving paraphrases
of normals (P0) and ask-obfuscation (P2) with open models on Kaggle, filter them (LaBSE ≥ 0.80 +
third-family judge + 200-pair human audit with Cohen's κ), and report discard stats. Text stays private.

## Owner
L. Effort ≈ 1 day (mostly GPU time).

## Depends on
T19 (splits, loader). **Email the ICFD authors first** (defensive robustness evaluation).

## Files to create or modify
- `research/attacks/paraphrase.py` — `build_prompt`, `generate_with_vllm`
- `research/attacks/filters.py` — `cosine`, `filter_pair`, `cohen_kappa`, `discard_rate`
- `research/attacks/run_attacks.py` (new) — Kaggle driver; writes private outputs + stats
- `results/attack_filter_stats.json` (new) — `{"P1-A": {"n_generated", "discard_rate", "kappa", ...}}`

## Do not touch
`PROMPTS` wording after the first generation run (record changes in DECISIONS.md if needed),
the lexicon, contracts, tests.

## Interfaces
Docstrings. Outputs: `research/_data/attacks/{set}_{gen}.jsonl` (git-ignored) with
`conv_id, rewrite_sha256, cosine, judge_ok` — and the text itself only in the private file.

## Plan (steps)
1. Pure functions + tests (`build_prompt`, `cosine`, `filter_pair`, `cohen_kappa`, `discard_rate`).
2. Kaggle notebook: vLLM generator A (Qwen2.5-7B-Instruct) on 1,000 test frauds (P1) and 1,000
   normals (P0); then generator B; then P2 (500, A only).
3. LaBSE embeddings (sentence-transformers) → cosine; judge model from a third family.
4. Two teammates label 200 random pairs → κ; if preservation < 85% tighten the prompt, regenerate.
5. Write stats JSON; never commit text.

## Acceptance criteria
`make task T=T20`: function tests + committed `results/attack_filter_stats.json`.

## Test command
`make task T=T20`

## Definition of Done
Green + `make check`; authors' reply (or no-reply date) noted in STATUS.

## Common mistakes
- Paraphrasing train or validation for the attack sets (attack sets come from TEST only;
  D3+aug uses TRAIN paraphrases separately).
- Releasing or committing paraphrase text (license).
- Letting the judge see the lexicon.

## Hints and links
- vLLM on Kaggle T4: dtype half, tensor_parallel_size=2.
- LaBSE: `sentence-transformers/LaBSE`.

## Agent plan (write yours here)
