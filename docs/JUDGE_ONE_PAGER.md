# Satyapan / Satya — judge one-pager

**When the voice is fake, the payment is still real. Verify that.**

Satya is a desktop companion for an Indian SME finance team. It listens to a call only after a
per-call yes, reads an email/invoice only when handed over, and compares every request with the
**payment and the vendor master**. Detectors can only **raise** a band. The approver is asked on
their own phone. Reports are drafts; a human submits.

---

## Three commands

```bash
make judge      # measured scoreboard + check any email/PDF/text, or a labelled kit
make dry-run    # consent -> live call -> alert -> OOB "not me" -> report pack -> stop
make oob-check  # the real phone page over HTTP (start make live first)
```

Every command is local, offline, and uses fake data (`*.example`, `FAK…`, `9999…`).

---

## The five judging questions, and where the answer is

| Question | Show this | Where |
|---|---|---|
| **1. Does it run end to end?** | live demo: consent → call → chips → alert → OOB → report; or `make dry-run` 3/3 | `docs/finale/LIVE_DEMO.md`, `docs/finale/DRY_RUNS.md` |
| **2. What is measured?** | held-out ask detection, real alert budget, labelled fixtures, named failures | `docs/JUDGE_KIT.md`, `results/EVIDENCE_LEDGER.md` |
| **3. What did you engineer?** | floor + raise-only policy, signal table, X1, asks/context/phrasebook, email/invoice/screen, OOB, vault, report pack | `docs/ENGINEERING_DEEP_DIVE.md` |
| **4. What happens after the alert?** | OOB on the approver’s phone; “I did not request this” → DENIED / HOLD; five `MANUAL_ONLY` drafts | `docs/finale/SAFEGUARDS.md`, `make dry-run`, `make oob-check` |
| **5. Did you deliver the plan?** | F01–F16 and P0/P1/P2 with cuts and reasons | `docs/finale/DELIVERED.md`, `docs/STATUS.md` |

---

## Headline numbers (test split, synthetic, no real data)

| Metric | Value |
|---|---|
| Ask detection — precision / recall (shipped product) | 61.2% [49.2–72.0] / 39.4% [30.6–49.0] |
| Attack texts with ≥ 1 ask | 48.9% [39.0–59.0] (45/92) |
| Benign AP texts with a false ask | 12.1% [7.9–18.1] (19/157) |
| **Routine payments at HOLD (false alarms)** | **3.5% [1.7–7.0] (7/200)** |
| **Attacks at ≥ VERIFY** | **78.6% [69.5–85.5] (77/98)** |
| Payee-change / large new-payee / split attacks at ≥ VERIFY | **100%** (17/17, 37/37, 6/6) |
| E-mail / invoice labelled fixtures | 10/10, 6/6 exact |
| Demo scenarios (illustrative) | 12/12 bands, 8/12 changed by detectors |
| Automated tests | **818 passed, 20 skipped**; desktop **84/84**; extension **11/11** |

**Failures we name:** small new payees reach ≥ VERIFY 52.9%; credential/remote asks with no
payment 38.1% (test) / 58% (all); Devanagari recall is the weakest language; a scanned PDF or an
unknown sender-auth header is GREY (≥ VERIFY), never PASS. The frozen research lexicon is weaker
than the product phrasebook; both rows are reported.

---

## What is real, what is cut

**Real:** system-audio capture (no mic), local Whisper, asks/cues, policy band, X1, OOB phone,
Screen Guard OCR, email/invoice checks, vault + §63 hashes, five golden-hour drafts,
`MANUAL_ONLY`. **Cut:** Gmail button (P2), loopback as primary route (kept as P1; replay
fallback), “keep call audio” button (vault exists; not in the 3-minute story), fresh deck file
(copy is in `docs/finale/SLIDES.md`), Windows/Linux packaging (targets exist; untested on real
hardware; the demo laptop is macOS).

**Never claimed:** field accuracy, a prevented-loss figure, media-origin authenticity, or that a
PASS means “safe”.

---

## One line to close

*Satya does not try to prove the voice is fake. It makes sure the payment is real.*
