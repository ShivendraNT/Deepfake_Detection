# Evidence ledger

Every number that may appear in the Round 1 PDF must have a row here. If it is not here, or its
status is not **measured** or **external, cited**, it does not go on a slide. Last update: 24 Oct 2026 (finale: text §10, face check §11, voice §12, mixed kit §13, product config + judge kit §14).

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
| Automated tests | 511 passed, 138 skipped (unfinished tasks) | `make check` | `7f28b4e` | superseded |
| Automated tests (incl. Seal tests) | **561 passed**, 138 skipped (unfinished tasks) | `make check` | `2afaf2a` | measured |
| Automated tests (24 Oct finale) | **818 passed, 20 skipped** (unfinished T18–T23 + video fusion) | `make check` | current | measured |
| Desktop tests (24 Oct finale) | **84 passed** | `cd desktop && npx vitest run` | current | measured |
| Safety invariants property-tested (monotone, raise-only, LLM cap, floor isolation, OOB/grey, single weak signal) | 7 invariant files, hypothesis 200 examples each | `tests/invariants/` | `7f28b4e` | measured |

## 5. Illustrative (label as simulation, not detection)

| Claim | Value | Why it is not a detection result | Status |
|---|---|---|---|
| "Detectors changed the outcome in 8/12 scenarios" | 8/12 | signals in the 12 fixtures are hand-authored; it shows the policy table, not detection | illustrative (policy simulation) |
| "0/30 prompt injections lowered a band" | 0/30 | true by construction (excerpts never become signals); `results/redteam.json` not produced | illustrative; do not present as a result |

## 6. Pending (no number exists; slide must say "pending")

| Claim | Owner task | What is needed |
|---|---|---|
| Voice detector through AMR-NB / G.711 (clean and Opus 16 kbps are measured on public data: §12) | T18 | sox AMR-NB encoder; the GSM condition is measured on val only |
| Meet-captured bonafide false-positive rate at tau; per-speaker FPR (bias) | T18 | consented team windows |
| Consented clone catch rate through a real Meet call | T18 / T22 | x/N with Wilson CI |
| Spoken ask → side-panel chip latency; ms per window in Chrome | T11 / T07 step 8 | `results/t11_latency.csv` has a header only |
| LLM echo/obey rate before vs after the faithfulness checker | T15 | run `scripts/redteam.py` with Ollama |
| Paraphrase robustness ("money figure") | T19-T21 | not run; pre-registered plan only |
| Email / invoice checker detection rates | T03, T04, T08 | checkers are built; no labelled open e-mail/invoice set measured yet (scam-text model on e-mail is measured: §10) |
| Fully AI-generated portraits (GAN / diffusion, no swap) through the photo check | finale | a licensed generated-face test set |
| Cost per case (≈ ₹1), per live minute (≈ ₹2) | design §7 | estimate only; recompute from current ap-south-1 prices |

## 7. Invalidated (never show)

| Claim | Where it was | Why | See |
|---|---|---|---|
| Voice EER clean 4% / Opus 0% / AMR 4% / G.711 2% (n=100) | `results/audio_eval.csv` @ f83e3b7 | scores drawn with `random.gauss`, no audio | `results/INVALIDATED.md` |
| tau_hi 0.5926 / tau_lo 0.4899 "calibrated on Meet windows" | `config/voice_thresholds.json` @ f83e3b7 | fitted on random numbers | `results/INVALIDATED.md` |
| Ask extractor precision = recall = 1.000 (n=104) | T05 test / STATUS | circular: same people wrote lexicon and sentences | superseded by section 1 |

## 8. External, cited (their numbers, not ours)

Checked on 08 Oct 2026 against the source (links in the PDF appendix X6).

| Claim | Value | Source | Check result |
|---|---|---|---|
| In-the-wild drop of open-source detectors vs academic benchmarks | AUC down ~50% video, 48% audio, 45% image | Deepfake-Eval-2024, Chandra et al., arXiv 2503.02857 (abstract) | verified |
| Best detector on 2026 video generators; humans | 69.7% AUROC (GenD-PE, pooled, §6.1); humans 52.6% accuracy on DF26 fakes | DF26, Shykula, Yermakov et al., arXiv 2609.07369 | verified (video, not audio) |
| A detector on closed-source generators | 34.5% AUROC (DFD-FCG on Grok Imagine 1.0 / Kling 3.0 / Veo 3.1 / Wan 2.6; Table 3 only) | DF26, Table 3 | verified; say "one detector", "below 50% = worse than chance" |
| Base voice model (browser plug-in) | In-the-Wild EER 6.6%, OOD avg 8.4% (AASIST 11.3%) | Pascu et al., arXiv 2606.30780 | paper exists; these figures are NOT in the abstract, not re-checked: **do not use in the PDF** |
| In-band caller authentication | ~63 s average to authenticate; pairwise shared secrets | CallShield, arXiv 2601.09327 (abstract) | verified |
| Indian incident | Rs 10.70 crore, Starmangalsutra Pvt Ltd (Sky Gold & Diamonds subsidiary), impersonated director, purported deepfake + compromised company phone and laptop, July 2026 | Economic Times via AI Incident Database #1596 | verified; "profile cloning" NOT found, removed from the PDF |
| SEBI boss-scam caution | PR 40/2026, 17 Jul 2026 | sebi.gov.in PDF | verified |
| Arup | HK$200M (~US$25.6M), 15 transfers after a deepfaked video call | Fortune, 17 May 2024 | verified |
| India cyber-fraud loss 2024 | Rs 22,845.73 crore (Lok Sabha reply, 22 Jul 2025) | PTI via The Week | verified |
| AIForge-Doc, Lewis 2022, ADD-C | see earlier notes | — | not re-checked: not used in the PDF |

## 9. Satyapan Seal

Data source: **SYN-V** = 10 synthetic TTS voices (Kokoro-82M int8 ONNX stock voices, Apache-2.0;
6 English, 4 Hindi; 38-65 s each), generated by `research/seal/gen_voices.py` outside the repo;
sha256 of every file is in the result JSONs (`manifest`). No real person's voice. Every row is
**illustrative of the mechanism** (synthetic voices, n = 10), not a field result; print
"synthetic TTS voices, n = 10" next to it. Intervals are Wilson 95% (sessions) where a
proportion is quoted. Not covered by any row: Google Meet's server-side / ML noise
cancellation, real network jitter/loss, speaker-to-microphone path, other participants mixed in
(two-laptop test, `research/seal/README.md` §6, is **pending**).

Codec-chain rows: `python research/seal/run_codec_eval.py --workers 2` → `results/seal_codec_eval.csv`,
`results/seal_codec_epochs.csv`, `results/seal_summary.json`; code at `d6ae619` (manifest
`git_commit`), results committed in `bb92393`. 14 chains (ffmpeg libopus / pcm_mulaw /
libmp3lame, sox AMR-NB); attack cases per voice x chain: unsealed/clone, relay (other meeting),
replay (epoch + 3), wrong identity.

| Claim | Value | n | 95% CI | Data source | Script + command | Commit | Status |
|---|---|---|---|---|---|---|---|
| Attack sessions falsely sealed (clone, relay, replay, wrong identity; 14 codec chains) | **0 / 560** | 560 sessions | [0, 0.68%] | SYN-V | `run_codec_eval.py` (above) | `d6ae619` / `bb92393` | measured (illustrative) |
| Attack epochs (post-acquisition) z: mean / std / max; epochs with z >= 4 | +0.04 / 1.03 / 3.13; 0 | 3,920 epochs | n/a | SYN-V | same → `seal_summary.json → pooled` | same | measured (illustrative) |
| Genuine sessions verified (all 14 chains) | **139 / 140** (miss: Opus 24k + 15 dB white noise, one Hindi voice) | 140 sessions | [96.1%, 99.9%] | SYN-V | same | same | measured (illustrative) |
| Genuine sessions verified per chain: Opus 16k 16 kHz (WhatsApp-style note), AMR-NB 12.2k, G.711 mu-law, Opus 24k + 5% frame loss | 10/10 each | 10 per chain | [72.2%, 100%] each | SYN-V | same → `seal_codec_eval.csv` | same | measured (illustrative) |
| Median time to verdict (seconds of sealed speech; key-disclosure latency not included) | 5 s (clean, Opus 12-32k, AMR-NB 12.2, G.711, MP3, 5% loss); 10 s Opus 8k and 15 dB noise; 20 s AMR-NB 4.75 | 10 per chain | n/a | SYN-V | same | same | measured (illustrative) |
| Language: attack z mean / std, English vs Hindi voices | +0.06 / 1.03 (EN, 2,856 epochs) vs -0.02 / 1.03 (HI, 1,064 epochs); genuine z 5.46 vs 5.94 | 6 EN + 4 HI voices | n/a | SYN-V | same → `pooled.by_language` | same | measured (illustrative) |
| Detection compute | median 5.9 ms per session (38-65 s stream, 51 lags, Python) | 700 sessions | n/a | SYN-V | same → `compute` | same | measured |
| Chrome WebRTC client pipeline (getUserMedia with echo cancellation / noise suppression / AGC **on and off**, Opus, NetEQ, loopback): sealed runs | **4 / 4** sealed (EN 13/13 epochs, z 6.89 / 6.79; HI 9/9, z 5.27 / 5.48); verdict 5 s (EN), 10 s (HI) | 2 voices x APM on/off | [51%, 100%] | SYN-V (am_michael, hf_alpha) | `python research/seal/webrtc_probe.py --voices am_michael,hf_alpha --rnnoise sh.rnnn` → `results/seal_webrtc_probe.json` (Chromium 141.0.7390.37) | `31a952e` / `a7eebae` | measured (illustrative, n = 2 voices) |
| Same probe: controls (relay to another meeting, replay at epoch + 3, unsealed audio) falsely sealed | 0 / 10 | 10 recordings | [0, 27.8%] | SYN-V | same | same | measured (illustrative) |
| Same probe: RNNoise ML denoiser applied to the received audio | still sealed (13/13, 9/9 epochs) | 2 voices | n/a | SYN-V | same | same | measured (illustrative) |
| Same probe: constant 3% time-scale (sox tempo 0.97 / 1.03) | fixed-rate verifier: not sealed; with rate search: sealed but only 4-5 of 9-13 epochs | 2 voices | n/a | SYN-V | same | same | measured; known weakness |
| Audibility proxies, seal +/-2 dB: PESQ-WB mean / STOI mean (vs plain Opus 32k with no seal) | 4.61 / 0.988 (4.46 / 0.994) | 10 voices, first 30 s | min PESQ 4.60 (4.41) | SYN-V | `python research/seal/quality.py` → `results/seal_quality.json` | code `400343c` + `quality.py` (run on a dirty tree, script committed with the results in `622fe9d`) | measured (proxy only; human listening test pending) |
| Intent Seal tamper tests: amount change, beneficiary swap, replay, phishing origin, foreign key | all refused | unit tests | n/a | fictional case data, virtual authenticator | `uv run pytest tests/seal/test_seal_registry_intent.py tests/seal/test_seal_api.py` | `2afaf2a` | measured (tests pass) |
| Seal through a real Google Meet call (server-side processing, Meet noise cancellation on/off) | — | — | — | consented / synthetic | `scripts/seal_cli.py verify ...` (README §6) | — | **pending** (finale hour 0-4) |
| Human listening test (A/B 1.5 vs 2.0 dB, 3 listeners) | — | — | — | — | README §6 step 8 | — | **pending** |
| Intent Seal verification time 0.146 ms (innovation-lab probe) | not reproduced in the repo | — | — | — | — | — | not for the PDF |

## 10. Scam-text classifier (`TEXT_SCAM_LIKELY`, style evidence capped at VERIFY)

Script: `python -m research.run_all text` (= `research.text.data`, `research.text.bench`,
`research.text.neardup`) → `results/text_benchmark.{json,md}`, `results/text_neardup.{json,md}`,
`results/text_eval_manifest.json` (sha256 of every raw file and of the table; rebuild identical).
Data: 7 open sets (licences in `docs/TEXT_BENCHMARK.md` §2), template-deduplicated, splits by
template group or official split minus leaked templates. C by grouped 5-fold CV on train,
τ_hi = 1 % FPR on val legitimate texts, test scored once. Status: **measured**.

| Claim | Value | n | 95% CI | Notes |
|---|---|---|---|---|
| Test AUC, in-domain (union model), per dataset | 0.989–1.000 | 112–2,576 test texts per set | template-cluster bootstrap, see md | two sets are near-copies of train (neardup audit); quote LODO for generalisation |
| AUC on novel test texts only (no train text with cos ≥ 0.8) | 0.987–1.000 (5 sets with n ≥ 163) | 163–2,159 | see `text_neardup.md` | unchanged vs all test texts |
| Leave-one-dataset-out test AUC (never-seen source) | 0.693 (phishing e-mail) to 0.995 (Hinglish calls) | per set | e.g. UCI SMS 0.856 [0.815, 0.893], Indian SMS 0.850 [0.815, 0.881] | the honest generalisation number |
| Fraud texts caught at τ_hi, clean / combined obfuscation attack, with de-obfuscation | 97.0 % / 96.2 % | 2,213 attacked fraud test texts | [96.2, 97.6] / [95.4, 97.0] | attacks are code-generated (`research/text/attacks.py`) |
| Same, model without the de-obfuscation layer | 96.6 % / 40.1 % | 2,213 | [95.8, 97.3] / [38.1, 42.2] | the layer is what keeps recall under attack |
| False alarms at τ_hi per dataset (legitimate test texts) | 0.0–2.6 % | 17–1,624 legit per set | e.g. phishing e-mail 2.6 % [2.0, 3.5] | τ fitted on pooled val |
| Whole consumer path (Scam Check page: quick check + impossible-claim rules), scam texts flagged VERIFY or HOLD | 96.6 % | 2,213 | [95.8, 97.3] | `results/consumer_text_eval.md`; in-domain test sets, so quote LODO for unseen sources |
| Same path, genuine texts flagged / put on HOLD | 2.7 % / 0.9 % | 4,363 | [2.2, 3.2] / [0.7, 1.3] | worst set: phishing e-mail 5.4 % flagged |
| Genuine texts flagged by language (whole consumer path) | English 3.2 %, English/Hindi SMS 0.6 %, Hindi 0 %, Hinglish 6.2 %, other Indian languages 0.6 % | 3,375 / 711 / 35 / 64 / 178 | see md | Hinglish is the worst; scams flagged 96–100 % in every language |
| What the impossible-claim rules add over the policy path | +0.0 pts scams caught, +0.3 pts genuine flagged | 6,576 | — | their value is the plain-language reason, not recall |

## 11. Face check on video and photos (`VIDEO_*`, `IMAGE_FACE_*`, ML evidence, never HOLD alone)

Script: `python -m research.run_all video` → `results/video_benchmark.{json,md}` (shipped GenD
check), `results/video_benchmark__blend.{json,md}` (our SBI fallback), `results/video_external.md`,
`results/image_face_benchmark.md`, `results/video_selection.json`, `results/video_eval_manifest.json`.
Data: FF++ c23 (official identity-disjoint splits), DFDC parts 0–2 (never used to fit anything).
τ_hi = 1 % / τ_lo = 5 % FPR on FF++ val reals, test scored once. Status: **measured**.

| Claim | Value | n | 95% CI | Notes |
|---|---|---|---|---|
| Selection: GenD − our SBI CNN, val AUC at call quality (360p) | +0.183 (SE 0.023) | FF++ val, call360 | [0.138, 0.227] | decided before any test number (`video_selection.json`) |
| Video AUC, FF++ test (5 methods) / DFDC (unseen) | 0.946 / 0.778 | 810 / 623 videos | [0.932, 0.960] / [0.734, 0.823] | `video_benchmark.md`, condition orig |
| Fakes flagged for a call-back (VERIFY or above), FF++ test / DFDC | 74.7 % / 24.8 % | 695 / 250 | [71.3, 77.8] / [19.9, 30.5] | LIKELY alone: 44.8 % / 7.2 % |
| Real videos called LIKELY_SYNTHETIC | 0 / 563 | 139 FF++ + 424 DFDC | [0, 0.7 %] | the strict alert never fired on a real test video |
| Real videos flagged for a call-back | 1.2 % (7 / 563) | 563 | — | 2.9 % FF++, 0.7 % DFDC |
| At 720p call quality: FF++ AUC / fakes flagged / reals flagged | 0.913 / 58.8 % / 2.2 % | 695 fake, 139 real | [0.895, 0.931] | VP8 1.2 Mbit/s + JPEG |
| At 360p call quality: FF++ AUC / fakes flagged / reals flagged | 0.877 / 50.6 % / 5.0 % | 695 fake, 139 real | [0.854, 0.900] | DFDC: 82 % of faces too small → "couldn't check" |
| Unseen method (FaceShifter) flagged | 31.7 % | 139 | — | vs 85.4 % for the 4 seen methods: name it as a failure case |
| Our SBI CNN (fallback), FF++ test / DFDC AUC | 0.786 / 0.633 | same videos | [0.760, 0.812] / [0.584, 0.682] | |
| Generic Hugging Face "deepfake" classifiers, FF++ test AUC | 0.52–0.65 | same crops | see `video_external.md` | popular ≠ tested |
| Photo check (one face crop), FF++ test / DFDC AUC | 0.923 / 0.747 | 3,360 / 2,688 crops | [0.909, 0.936] / [0.714, 0.779] | real crops over τ_hi: 0.4 % / 0.0 % |
| Photo check after a WhatsApp-style re-encode (JPEG q60), paired | AUC 0.913 → 0.872 (Δ −0.042 [−0.078, −0.008]); fakes flagged 49 % → 35 %; reals 0 % → 0 % | 100 real + 100 fake FF++ test frames | see md | `results/photo_whatsapp.md` |
| GenD latency | ≈ 1.3 s per crop, 2 CPU threads, other jobs running | benchmark logs | — | product: 1 crop per 2.25 s of call |

## 12. Voice-clone check (`VOICE_*`, ML evidence; SUSPICIOUS → VERIFY, two windows over τ_hi → +1 band)

Script: `python -m research.run_all voice` (= `research.voice.data`, `research.voice.bench`,
`research.voice.export`) → `results/voice_benchmark.{json,md}`, `results/voice_selection.json`,
`results/voice_eval_manifest.json`. Protocol and amendments fixed before scoring:
`docs/VOICE_DEEPFAKE.md` §4. Status: **measured**.

| Claim | Value | n | 95% CI | Notes |
|---|---|---|---|---|
| Selection: gustking − ours, val AUC under Opus 16 kbps | +0.157 (SE 0.054) | 1,457 val clips | [0.026, 0.244] | decided before any test score; ours 0.791, gustking 0.949 |
| In-the-Wild test AUC, clean / Opus (real-world deepfakes, unseen speakers) | 0.921 / 0.909 | 669 bonafide + 331 spoof | [0.868, 0.957] / [0.857, 0.948] | seeded subset (amendment 2) |
| Same, clips with ≥ 3 s of speech (the product's range) | 0.952 / 0.947 | 160 + 155 | [0.910, 0.980] / [0.903, 0.978] | |
| Fakes flagged for a call-back (≥ τ_lo), ≥ 3 s speech, clean / Opus | 63.9 % / 66.5 % | 155 | [56.1, 71.0] / [58.7, 73.4] | |
| Genuine voices flagged (≥ τ_lo), ≥ 3 s speech | 0.6 % | 160 | [0.1, 3.5] | all clips: 1.6–1.8 % |
| Genuine voices over τ_hi (one window) | 0.0–0.1 % | 669 | [0.0, 0.8] | |
| ASVspoof 2019 eval AUC | 0.999 | 300 + 390 | [0.997, 1.000] | upper bound: the model card says "ASVspoof 2019" without a split |
| Evasion: white noise at 10 dB SNR on cloned voices (product scorer, frozen τ) | fakes flagged 63.9 % → 1.9 %; AUC 0.952 → 0.843 (paired −0.110 [−0.177, −0.059]) | 155 spoof + 160 bonafide, ≥ 3 s speech | see md | a measured weakness: `results/voice_evasion.md` |
| Denoiser (ffmpeg afftdn) in front of the voice check, VAL only | AUC −0.010 [−0.059, +0.038] on noisy clips, −0.023 [−0.035, −0.002] on clean | 197 spoof + 366 bonafide val clips | see md | rejected as a fix: `results/voice_denoise_probe.md` |
| Evasion: 10 % faster / 2 semitones up | AUC −0.004 / −0.007 (CIs include 0); fakes flagged 63.9 % / 76.8 % | same | see md | not effective evasions |
| Our re-trained recipe (not shipped), val AUC under Opus | 0.791 | 1,457 | [0.706, 0.904] | in-domain CV AUC 1.000: the out-of-domain gap |

## 13. The whole product on a mixed kit from the test sets (`satya scan`)

Script: `python -m research.run_all kit` (= `research.kit build` + `run`) →
`results/kit_scan.{csv,md}`, `results/kit_manifest.json` (source and sha256 of every file;
media outside the repo). Same answer as the consumer page (quick check + claim rules). Status:
**measured** (small n: quote as a spot check, not a benchmark).

| Claim | Value | n | Notes |
|---|---|---|---|
| Genuine files passed | 86 / 88 | 40 texts, 20 photos, 20 voices, 8 videos | two genuine voice notes got VERIFY (voice unusual; words read like a scam) |
| Fakes and scams flagged | 68 / 96 | 40 / 20 / 20 / 16 | texts 38, voices 15, videos 7, photos 8 |
| Time for 184 files, 4-core CPU | ≈ 7.5 min | — | first file includes model loading |
---

## 14. Finale: shipped product configuration + judge kit (24 Oct 2026)

The Round-1 rows above stay frozen. The finale ships a **product** configuration: the ADR-021
context filter plus the live phrasebook (`live-1.1.0`). It is measured on the SAME pre-registered
test split (`sha256(id)` parity). The phrasebook was extended once from **dev-split** misses only,
then the test split was re-scored once; both product rows are shown so the change is auditable.
The **research claim remains the frozen lexicon** (section 1). Data and commands are the same as
section 1/2 unless noted.

| Claim | Value | n | 95% CI | Data / command | Status |
|---|---|---|---|---|---|
| Product ask precision, test | 61.2% | 67 flagged asks | [49.2, 72.0] | `python -m research.heldout.run_eval` → `results/asks_heldout_eval.json` | measured |
| Product ask recall, test | 39.4% | 104 gold asks | [30.6, 49.0] | same | measured |
| Product attack texts with >= 1 ask, test | 48.9% | 92 | [39.0, 59.0] | same | measured |
| Product benign false-ask rate, test | 12.1% | 157 | [7.9, 18.1] | same | measured |
| Product `live-1.0.0` (before the dev-only extension), test | P 61.5% (40/65), R 38.5% (40/104), attack-any 46.7% (43/92), benign FA 12.1% (19/157) | as above | — | first score, kept for audit | measured, superseded |
| Product alert budget: routine payments at HOLD, test | **3.5%** | 200 | [1.7, 7.0] | `python -m research.alert_budget.run_alert_budget` → `results/alert_budget.json` | measured |
| Product alert budget: routine >= VERIFY, test | 23.5% | 200 | [18.2, 29.8] | same | measured |
| Product alert budget: attacks >= VERIFY, test | **78.6%** | 98 | [69.5, 85.5] | same | measured |
| Product alert budget: attacks at HOLD, test | 16.3% | 98 | [10.3, 24.9] | same | measured |
| Product attack catch by scenario, test (>= VERIFY): payee change / large new payee / split / small new payee / no-payment credential | 100% (17/17) / 100% (37/37) / 100% (6/6) / 52.9% (9/17) / 38.1% (8/21) | 98 | see json | same | measured; **named failures** are the last two |
| E-mail signal fixtures exact match | 10/10 | 10 | n/a | `python scripts/judge_kit.py` | measured (functional) |
| Invoice fields + metadata + signals exact match | 6/6 | 6 | n/a | same | measured (functional) |
| Demo scenarios: full band matches expected | 12/12 | 12 | n/a | `python scripts/decision_relevance.py`; `data/demo/expected_decisions.json` | illustrative |
| Detectors change the rules-only outcome | 8/12 | 12 | n/a | same | illustrative |
| Judge kit scoreboard runtime | 0.3 s | — | — | `python scripts/judge_kit.py` | measured |
| Automated end-to-end dry run | **3/3 PASS**, 94–132 ms per run | 3 runs | n/a | `python scripts/dry_run.py` → `results/dry_runs.json`, `docs/finale/DRY_RUNS.md` | measured (in-process; **not** stage latency) |
| Desktop tests | **84/84** | 84 | n/a | `cd desktop && npx vitest run` | measured |
| Desktop typecheck | green | — | — | `npm run typecheck` | measured |

**How to quote this honestly.** Say “on a pre-registered synthetic held-out split, the shipped
product finds at least one ask in 48.9% of attack texts with a 12.1% false-ask rate on benign AP
texts; through the real policy, 3.5% of routine payments reach HOLD and 78.6% of attacks reach at
least VERIFY.” Do **not** say “98% accurate” or quote the frozen-lexicon precision as the product
precision. The test split is synthetic and the failures are named in `docs/JUDGE_KIT.md`.
