# Evidence ledger

Every number that may appear in the Round 1 PDF must have a row here. If it is not here, or its
status is not **measured** or **external, cited**, it does not go on a slide. Last update: 08 Oct 2026.

**Status values.** *measured*: produced by the listed script on the listed data at the listed
commit; re-run the command to reproduce. *external, cited*: someone else's published number;
cite it as theirs. *illustrative*: a policy simulation, not a detection result; label it so.
*pending*: not measured yet; the slide must say "pending". *invalidated*: never show it.

**Data source codes.** S-HO = synthetic held-out text, written by an AI agent before it opened
the lexicon (`research/heldout/README.md`, commit 205f4e6). S-AB = synthetic payment cases built
deterministically from S-HO (`research/alert_budget/synth.py`). Nothing here uses real customer,
bank or personal data. Intervals are Wilson 95%. **Quote the `test` split** where both are given:
the context layer was designed while reading dev-split texts only (same author wrote both splits).

## 1. Ask extractor (frozen lexicon v1.0) on the held-out set

Script: `uv run python -m research.heldout.run_eval` → `results/asks_heldout_eval.json`, commit
`c6746a9` (first measured at `fda5496`, same numbers for the frozen variant). Status: **measured**.

| Claim | Value | n | 95% CI | Notes |
|---|---|---|---|---|
| Micro precision, frozen lexicon (test / all) | 0.47 / 0.39 | 73 / 135 flagged asks | [0.36, 0.58] / [0.31, 0.48] | replaces the circular P=1.000 |
| Micro recall, frozen lexicon (test / all) | 0.33 / 0.28 | 104 / 190 gold asks | [0.24, 0.42] / [0.22, 0.35] | replaces the circular R=1.000 |
| Attack texts with at least one ask detected (test / all) | 41.3% / 33.1% | 92 / 172 | [31.8, 51.5] / [26.5, 40.5] | most paraphrased asks are missed |
| Benign AP texts with a false ask (test / all) | 21.0% / 21.5% | 157 / 325 | [15.4, 28.1] / [17.4, 26.3] | footers, bank OTP SMS, IT notices |
| Benign false-ask rate **with context layer v1.2** (test / all) | 11.5% / 8.6% | 157 / 325 | [7.4, 17.4] / [6.0, 12.2] | recall unchanged (0.33 / 0.28) |
| Precision **with context layer v1.2** (test / all) | 0.60 / 0.60 | 57 / 88 flagged | [0.47, 0.71] / [0.50, 0.70] | |
| Recall per language, frozen (all): en / Hinglish / Devanagari | 0.28 / 0.36 / 0.15 | 95 / 55 / 40 gold asks | [0.20, 0.38] / [0.25, 0.50] / [0.07, 0.29] | Devanagari weakest |
| Benign false-ask rate per language, frozen (all): en / Hinglish / Devanagari | 21.2% / 29.1% / 11.8% | 236 / 55 / 34 | see json | |

Per ask type, frozen lexicon, all splits (precision over every text; recall over texts with that label):

| Ask | Precision | n flagged | Recall | n gold |
|---|---|---|---|---|
| A1 new / "safe" account | 0.46 [0.30, 0.64] | 28 | 0.43 [0.27, 0.61] | 30 |
| A2 OTP / PIN / password | 0.27 [0.16, 0.42] | 44 | 0.41 [0.26, 0.59] | 29 |
| A3 remote access / screen share | 0.67 [0.21, 0.94] | 3 | 0.09 [0.03, 0.28] | 22 |
| A4 secrecy / isolation | 0.25 [0.14, 0.41] | 36 | 0.29 [0.16, 0.47] | 31 |
| A5 bypass a control | 1.00 [0.44, 1.00] | 3 | 0.10 [0.04, 0.26] | 29 |
| A6 gift card / crypto / UPI collect | 0.73 [0.48, 0.89] | 15 | 0.48 [0.29, 0.67] | 23 |
| A7 payee / bank-detail change | 0.50 [0.19, 0.81] | 6 | 0.12 [0.04, 0.29] | 26 |

Caveats to print next to these: synthetic, single author (no inter-annotator agreement), clean
typed text (live ASR will be worse), no real brand names (brand-keyed lexicon entries look worse).

## 2. Alert budget through the real decision path

Script: `uv run python -m research.alert_budget.run_alert_budget` → `results/alert_budget.json`,
`results/alert_budget.md`, commit `7f28b4e`. BEFORE was also measured on the unmodified policy
1.0.0 code (commit `fda5496`); the knob-off emulation reproduces it exactly. Data: S-AB, 400
routine known-vendor payments (each with 1-3 benign AP messages) and 184 attack cases (172
held-out asks + 12 de-minimis splits). Status: **measured**.

| Claim (test split; all splits in brackets) | Before (policy 1.0.0) | After (policy 1.1.0 + context v1.2) | n |
|---|---|---|---|
| Routine payments escalated to >= VERIFY | 36.5% [30.1, 43.4] (all 39.5%) | 21.5% [16.4, 27.7] (all 17.8%) | 200 (400) |
| Routine payments at HOLD (checker queue) | 27.5% [21.8, 34.1] (all 31.8%) | **3.0%** [1.4, 6.4] (all 2.3%) | 200 (400) |
| Attack cases at >= VERIFY | 71.4% [61.8, 79.4] (all 68.5%) | 76.5% [67.2, 83.8] (all 74.5%) | 98 (184) |
| Attack cases at HOLD | 25.5% [17.9, 34.9] (all 23.4%) | 12.2% [7.1, 20.2] (all 9.2%) | 98 (184) |
| Payee-change attacks at >= VERIFY (all) | 100% | 100% | 26 |
| New-payee (large) attacks at >= VERIFY (all) | 100% | 100% | 75 |
| De-minimis split payments at >= VERIFY (all) | 0% | **100%** | 12 |
| Credential / remote-access asks with no payment at >= VERIFY (all) | 29% | 27% | 48 |

How to read the attack HOLD drop (computed by the script): of 13 test-split attack cases that
lost HOLD, **9** had been held only because a standard confidentiality footer appended to the
attacker's mail fired a secrecy ask (the same false positive that hits routine payments; they
stay at VERIFY through the floor), and **4** are real single credential asks with no payment,
now VERIFY instead of HOLD. That second group is the real cost of ADR-021. One attack case
(`case_a_ask_055`, a remote-access ask the lexicon misses) went from VERIFY to PASS because its
only flag had come from the footer. Upper-bound caveat: every routine case carries a message and
the benign set is rich in footers/SMS. Sender-auth checks (T03/T04) are not built, so they add
nothing on either side.

## 3. Red-team (deterministic, no LLM)

Script: `uv run python -m research.redteam.run_deterministic` → `results/redteam_deterministic.json`,
commit `c6746a9`. Status: **measured** (the LLM echo/obey part is **pending**: no Ollama here).

| Claim | Before | After | n |
|---|---|---|---|
| Reassuring-but-faithful summaries that pass the faithfulness checker | 100% | 36.7% [21.9, 54.5] | 30 |
| Neutral faithful summaries wrongly rejected | 0% | 0% [0, 27.8] | 10 |
| Routine payments pushed to HOLD by one planted secrecy word | 100% | 20.5% [15.5, 26.6] (100% still >= VERIFY) | 200 |
| ... by one planted credential word | 100% | 10.5% [7.0, 15.5] | 200 |
| ... by a planted OTP-SMS-shaped or disclaimer-shaped line | 100% | 3.0% [1.4, 6.4] | 200 |
| ... by two planted keyword types (flooding still works) | 100% | **100%** | 200 |
| Asks hidden by wrapping them in boilerplate (round 3, final, worst wrapper) | n/a | 5.3% [1.5, 17.3] | 38 |
| Known gap: "Our bank will never ask for your OTP ... but <ask>" (round 2) | n/a | 34.2% [21.2, 50.1] | 38 |

Pre-filter history (same script): round 1 wrappers hid up to 15/38 asks with context v1.0
(commit `1cbf71b`), round 2 hid 15/38 with v1.1; round 3 was written before v1.2 was run and
is reported as final. Paraphrased reassurance still passes the deny-list (11/30): the real
defences are structural (LLM never sets the band, template fallback).

## 4. Engineering facts

| Claim | Value | Source | Commit | Status |
|---|---|---|---|---|
| Automated tests | 511 passed, 138 skipped (unfinished tasks) | `make check` | `7f28b4e` | measured |
| Safety invariants property-tested (monotone, raise-only, LLM cap, floor isolation, OOB/grey, single weak signal) | 7 invariant files, hypothesis 200 examples each | `tests/invariants/` | `7f28b4e` | measured |

## 5. Illustrative (label as simulation, not detection)

| Claim | Value | Why it is not a detection result | Status |
|---|---|---|---|
| "Detectors changed the outcome in 8/12 scenarios" | 8/12 | signals in the 12 fixtures are hand-authored; it shows the policy table, not detection | illustrative (policy simulation) |
| "0/30 prompt injections lowered a band" | 0/30 | true by construction (excerpts never become signals); `results/redteam.json` not produced | illustrative; do not present as a result |

## 6. Pending (no number exists; slide must say "pending")

| Claim | Owner task | What is needed |
|---|---|---|
| Voice detector EER through clean / Opus / AMR-NB / G.711, with speaker-bootstrap CI | T18 (+T17 model) | real audio + `results/audio_eval_manifest.json` (sha256 per file) |
| Meet-captured bonafide false-positive rate at tau; per-speaker FPR (bias) | T18 | consented team windows |
| Consented clone catch rate through a real Meet call | T18 / T22 | x/N with Wilson CI |
| Spoken ask → side-panel chip latency; ms per window in Chrome | T11 / T07 step 8 | `results/t11_latency.csv` has a header only |
| LLM echo/obey rate before vs after the faithfulness checker | T15 | run `scripts/redteam.py` with Ollama |
| Paraphrase robustness ("money figure") | T19-T21 | not run; pre-registered plan only |
| Email / invoice checker detection rates | T03, T04, T08 | not built |
| Cost per case (≈ ₹1), per live minute (≈ ₹2) | design §7 | estimate only; recompute from current ap-south-1 prices |

## 7. Invalidated (never show)

| Claim | Where it was | Why | See |
|---|---|---|---|
| Voice EER clean 4% / Opus 0% / AMR 4% / G.711 2% (n=100) | `results/audio_eval.csv` @ f83e3b7 | scores drawn with `random.gauss`, no audio | `results/INVALIDATED.md` |
| tau_hi 0.5926 / tau_lo 0.4899 "calibrated on Meet windows" | `config/voice_thresholds.json` @ f83e3b7 | fitted on random numbers | `results/INVALIDATED.md` |
| Ask extractor precision = recall = 1.000 (n=104) | T05 test / STATUS | circular: same people wrote lexicon and sentences | superseded by section 1 |

## 8. External, cited (their numbers, not ours)

| Claim | Value | Source | Check before submission |
|---|---|---|---|
| In-the-wild drop of open-source detectors vs academic benchmarks | AUC down ~50% video, 48% audio, 45% image | Deepfake-Eval-2024, Chandra et al., arXiv 2503.02857 | verify the arXiv ID and figures |
| Best detector on 2026 generators | 69.7% AUROC; 34.5% AUROC on commercial generators (below 50% = worse than chance); humans 52.6% | DF26, Shykula, Yermakov et al., arXiv 2609.07369 | ID verified by judge panel |
| Base voice model (browser plug-in) | In-the-Wild EER 6.6%, OOD avg 8.4% (AASIST 11.3%) | Pascu, Oneata, Cucu, Müller, arXiv 2606.30780 | ID verified by judge panel; model has no licence file, state permission status |
| AI-edited invoice amounts vs forensic detectors | TruFor AUC 0.751, GPT-4o 0.509 | AIForge-Doc, Wu et al., arXiv 2602.20569 | verify the arXiv ID and figures |
| Content warnings and human deepfake spotting | 10.7% without warning → 21.6% with warning | Lewis, Vu, Duch, Chowdhury (2022), Royal Society report | verify citation |
| Codec penalty on audio deepfake detection | ≈ +5.3 EER points | ADD-C | verify citation |

## 9. Satyapan Seal

*Placeholder, to be filled by the engineer working on the Seal. Their results go to
`results/seal_*.json`. Use the same columns: claim, value, n, 95% CI, data source (synthetic /
public / consented), script + command, commit, status. Until a row exists here, every Seal
number is **pending**.*

| Claim | Value | n | 95% CI | Data source | Script + command | Commit | Status |
|---|---|---|---|---|---|---|---|
| | | | | | | | pending |
