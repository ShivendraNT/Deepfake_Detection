# Product-level evaluation (honest numbers)

Rule: **no number goes on a slide unless it comes from a file in `results/` and states n.**
Hackathon numbers are labelled "illustrative, n=X". The paper claim lives in
`docs/RESEARCH_PROTOCOL.md`; this file covers the product slide.

## 1. What we measure

| # | Measurement | Data | Metric | Produced by | File |
|---|---|---|---|---|---|
| E1 | Decision relevance (where detectors change the outcome) | 12 team-authored scenarios (`data/demo/cases/`) | rules-only band vs full band | `scripts/decision_relevance.py` (works now) | `results/decision_relevance.md` |
| E2 | Voice detector through real channels | In-the-Wild + HAV-DF audio (+ IndieFake if available) + ~200 Meet-captured bonafide windows | EER, FPR/FNR at τ, speaker-bootstrap CI | T18 | `results/audio_eval.csv` |
| E3 | Injection red-team | 30 samples × 3 cases (`data/demo/injection/injections.jsonl`) | bands lowered (0/90 runs; 0/30 samples — structural); summaries echoing the injection before/after checker; checker rejection rate | T15 | `results/redteam.json` |
| E4 | Ask extractor dev-set quality | ≥ 80 team-written sentences (not ICFD) | precision, recall | T05 test output | printed by `make task T=T05` |
| E5 | Paraphrase robustness (first research result) | ICFD test + P1-A | recall@1%FPR with CI for D2, D3, D4 | T19-T21 | `results/research_main.csv`, `figures/money.png` |
| E6 | Live latency | 10 Hinglish clips on the M4 | seconds from spoken ask to chip; voice alert delay | T11/T22 | `results/dry_runs.csv` |
| E7 | Demo reliability | 10 end-to-end dry runs | success count | T22 | `results/dry_runs.csv` |
| E8 | Transcribe vs Whisper on Hinglish | 20 demo clips | WER (manual reference) | T17 | `results/asr_compare.csv` |

## 2. E1 today (computed by the real engine)

Run `make demo-data`. Current output: detectors change the outcome in **8/12** scenarios
(R1-R4 regions); in the other 4 the floor alone decides (including Moment 2, where every detector
is green). Illustrative, n=12, team-authored — not evidence of real-world performance.

## 3. The "honest numbers" slide template

```
Voice detector (Pascu et al. XLS-R-L7, ONNX in the browser)
  Base model (paper): ITW EER 6.6%, OOD 8.4% vs AASIST 11.3%   [arXiv 2606.30780]
  Ours through Meet tab capture: EER __% [__, __]  (n=__ speakers, __ windows)
  Through AMR-NB 8 kHz:          EER __% [__, __]
  False alarms on team voices at τ_hi: __ / __ windows
Paraphrase robustness (ICFD-31k test, n=__ frauds / __ normals)
  D3 recall@1%FPR clean → P1: __ → __   D4: __ → __   D6: __ → __
Prompt injection (2026-10-25, ollama:llama3.1:8b): 0/90 bands lowered (structural; 30 samples × 3 cases)
  Successful calls 88/90 (2 timeouts); 41/88 echoed before the checker (46.6%); checker rejected
  32/41 echoes (78.0%); 9/88 final summaries still echoed (10.2%).
Decision relevance: detectors changed the outcome in 8/12 illustrative scenarios
```

Fill blanks only from `results/`. If a number is not ready, the slide says "pending", never a guess.

## 4. What we will NOT claim

- Any real-world fraud prevented or prevalence number.
- That the floor is a research finding (it is product policy).
- Media origin authenticity (vault proves integrity since capture only).
- Accuracy of the citizen page (rules only, no evaluation).
- That the text classifier is a general scam detector. It is style evidence capped at VERIFY;
  quote the leave-one-dataset-out AUC **0.69–0.99** (`docs/TEXT_BENCHMARK.md`), not the in-domain
  0.99+. The product ask layer is P 61.2 % / R 39.4 % with a 12.1 % benign false-ask rate on the
  held-out test split.
