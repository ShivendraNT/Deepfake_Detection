# T21 — Research R3: evaluate D2/D3/D4/D6 on P0/P1/P2 and draw the money figure

## Goal
The paper's main result: recall@1%FPR (and 5%) with 95% CIs per detector × condition, the paired
drop-difference tests for H1/H2, residual exposure per attack set, and `figures/money.png`.

## Owner
L. Effort ≈ 0.5 day.

## Depends on
T19 (scores, thresholds, metrics), T20 (attack sets scored by D2/D3/D4).

## Files to create or modify
- `research/eval/d6.py` — `d6_alert`, `d6_score`, `fit_d6`, `residual_exposure`
- `research/eval/run_eval.py` — `run`
- `research/eval/plot_money.py` — `plot`
- `results/research_main.csv` (new), `figures/money.png` (new)

## Do not touch
Thresholds from T19 (validation-fitted, frozen), metrics module semantics, tests.

## Interfaces
Docstrings. `results/research_main.csv` columns: `detector,condition,metric,point,low,high,n_pos,n_neg`.

## Plan (steps)
1. `d6.py` + tests. 2. `fit_d6` on validation only → store (k, t) in `results/thresholds.json`.
3. `run_eval.py`: all detectors × {clean, P0, P1-A, P1-B, P2}; paired drop diffs (H1, H2).
4. `plot_money.py` (matplotlib, colour-blind-safe, CI whiskers, n in caption).
5. Residual exposure table per attack set.

## Acceptance criteria
`make task T=T21`: D6 functions + committed CSV and PNG.

## Test command
`make task T=T21`

## Definition of Done
Green + `make check`; numbers copied into `docs/EVALUATION.md`; nothing on a slide without CI and n.

## Common mistakes
- Re-fitting thresholds on attacked data. - Dropping the P2 panel because it looks bad (it is the
  honest residual risk). - Unpaired CIs for paired questions.

## Hints and links
- `docs/RESEARCH_PROTOCOL.md` §3, §7.

## Agent plan (write yours here)
