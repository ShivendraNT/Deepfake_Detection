# Judge kit — how to score Satyapan in five minutes

> **One command:** `make judge` (or `uv run python scripts/judge_kit.py` on Windows, no `make`).
> **One live check:** `make judge ARGS="..."` is not wired; use
> `uv run python scripts/judge_kit.py --file path/to/email.eml` or `--text "..."`.
> Everything is local, offline, and uses fake data only (`*.example`, `FAK…`, `9999…`).

This kit exists so a judge can do three things without trusting a slide:

1. **Score the shipped detector stack** on a pre-registered held-out split, with n and Wilson
   95% intervals.
2. **Hand Satya a new input** (an email, an invoice PDF, a call/WhatsApp transcript, a screen
   snippet) and watch the real pipeline produce signals, the policy floor, the band and the
   next action.
3. **See the failure cases**, not just the wins.

---

## 1. Run it

```bash
# scoreboard: ask detection + alert budget + labelled fixtures + demo cases
make judge
# Windows / no make:
uv run python scripts/judge_kit.py

# a judge-supplied email, with a known vendor and its registered account
uv run python scripts/judge_kit.py --file my_scam.eml --vendor-id V001

# a new payee, large amount
uv run python scripts/judge_kit.py --file invoice.pdf --new-payee --amount 4800000

# a raw transcript or screen snippet
uv run python scripts/judge_kit.py --text "keep this between us, pay the new account"
uv run python scripts/judge_kit.py --screen --text "Account 9999000099917 ..."

# a normal invoice is not automatically fraud
uv run python scripts/judge_kit.py --file data/demo/invoices/inv_kaveri_ok.pdf --vendor-id V001

# a machine-readable scoreboard
uv run python scripts/judge_kit.py --json

# score a labelled kit supplied by the judges (one JSON object per line)
uv run python scripts/judge_kit.py --labels kit.jsonl
```

`kit.jsonl` format:

```json
{"id":"bec-1","path":"samples/bank-change.eml","vendor_id":"V002","amount":284000,"expected":"VERIFY"}
{"id":"cfo-call","text":"Keep this between us. Pay the new account.","new_payee":true,"amount":4850000,"expected":"HOLD"}
{"id":"routine","path":"samples/invoice.pdf","vendor_id":"V001","amount":210000,"expected":"PASS"}
```

`expected` is the **policy band** for that sample (PASS / VERIFY / HOLD), not a free-text
“scam/benign” label: a benign message can still be VERIFY because the payment itself is a new
payee. The mode prints the exact-match rate, the share of unsafe samples caught at ≥ VERIFY,
the false-alarm rate on safe samples, a confusion matrix and each failure with its policy reasons.
Rows can override any global payment flag (`vendor_id`, `new_payee`, `amount`, `account`, `ifsc`,
`beneficiary`).

The scoreboard takes **under a second** on a laptop. The live checks take a few milliseconds for
text/email, and roughly 50–300 ms for a PDF (text extraction).

`make dry-run` runs the whole story (consent → live call → alert → approver says “not me” →
report pack → stop) against the real app in-process; see `docs/finale/DRY_RUNS.md`.

---

## 2. What the scoreboard measures

### 2.1 Ask detection on a pre-registered held-out split

Data: `research/heldout/asks_heldout.jsonl` (172 attack texts, multi-label A1–A7) and
`research/heldout/benign_ap.jsonl` (325 everyday AP texts: footers, bank OTP SMS, IT notices,
Diwali vouchers, GST/TDS mail, WhatsApp chatter). The split is **pre-registered by
`sha256(id)` parity**: dev if the hash is even, test if odd. The context filter was designed on
dev only; quote the **test** split. The data is synthetic and AI/team-authored — it contains no
real customer, bank or personal data.

| Configuration | Precision | Recall | Attack with ≥ 1 ask | Benign false ask |
|---|---|---|---|---|
| Frozen research lexicon v1.0 | 46.6% [35.6–57.9] (34/73) | 32.7% [24.4–42.2] (34/104) | 41.3% (38/92) | 21.0% (33/157) |
| Context filter v1.2 (research) | 59.7% [46.7–71.4] (34/57) | 32.7% [24.4–42.2] (34/104) | 41.3% (38/92) | 11.5% (18/157) |
| **Product (shipped): context + phrasebook `live-1.1.0`** | **61.2% [49.2–72.0] (41/67)** | **39.4% [30.6–49.0] (41/104)** | **48.9% (45/92)** | **12.1% (19/157)** |

What this means in plain words: on unseen paraphrases, the shipped product finds at least one
payment trick in about **one of every two** attack messages, with a false-ask rate of about
**one in eight** benign AP messages. It is not a victory lap; it is an honest, measured layer.
The **payment floor** is the primary control; the ask layer raises the band when it fires.

**Protocol note (important for a judge):** `live-1.1.0` adds patterns for paraphrases found in
**dev-split misses only** (“add a new payee”, “the account mentioned in my message”, “give me
access to your desktop”, “screen sharing on karo”). The test split was re-scored **once** after
the layer was frozen. Both product rows are reported so the change is auditable:

| Product phrasebook | Precision | Recall | Attack with ≥ 1 ask | Benign false ask |
|---|---|---|---|---|
| `live-1.0.0` (before the dev-only extension) | 61.5% (40/65) | 38.5% (40/104) | 46.7% (43/92) | 12.1% (19/157) |
| `live-1.1.0` (shipped) | 61.2% (41/67) | 39.4% (41/104) | 48.9% (45/92) | 12.1% (19/157) |

The **frozen lexicon** numbers are the research claim and did not change. The phrasebook is
product-only: research scripts call `extract_asks` and never see it.

### 2.2 End-to-end policy (alert budget)

Data: `research/alert_budget/synth.py` builds **400 routine** payments (known vendor, registered
account, in-pattern amount, with 1–3 benign messages) and **184 attack** cases (one per held-out
attacker ask, shaped by the ask into a payee change, a new payee, a small new payee or a
credential/remote-access request, plus 12 de-minimis split payments). Every case runs through
the **real** pipeline: `analyze_evidence` → `merge_output` → `recompute` → `satyapan.policy`.
No band is hand-set.

Product configuration, test split (quote this):

| Metric | Value |
|---|---|
| Routine payments at **HOLD** (false alarms sent to the checker) | **3.5% [1.7–7.0] (7/200)** |
| Routine payments escalated to ≥ VERIFY | 23.5% [18.2–29.8] (47/200) |
| Attack cases at ≥ VERIFY | **78.6% [69.5–85.5] (77/98)** |
| Attack cases at HOLD | 16.3% [10.3–24.9] (16/98) |
| Payee-change attacks at ≥ VERIFY | 100% (17/17) |
| Large new-payee attacks at ≥ VERIFY | 100% (37/37) |
| De-minimis split payments at ≥ VERIFY | 100% (6/6) |
| Small new-payee attacks at ≥ VERIFY | 52.9% (9/17) |
| No-payment credential/remote-access asks at ≥ VERIFY | 38.1% (8/21) |

The **research/frozen** configuration (no live phrasebook) gives test-split HOLD 3.0% (6/200)
and attack ≥ VERIFY 76.5% (75/98). The product adds one attack catch and one routine HOLD.

Why the HOLD rate is the headline: a routine payment is the common case; 3.5% of them reach a
human checker, and **about four in five attacks reach at least VERIFY**. The floor catches every
payee change and every large new payee in this synthetic set. Small new payees are deliberately
allowed to pass the floor when the amount is small (to avoid drowning the checker), so the
52.9% there is the measured cost of that policy choice, not a bug.

### 2.3 Communication checkers on labelled fixtures

These are **functional checks**, not a generalisation estimate. They prove the shipped rules do
what the labels say on the team-authored fixtures.

| Check | Result |
|---|---|
| E-mail signals (`data/demo/emails/`, 10 files) | **10/10 exact** signal + grey match |
| Invoice signals + extracted fields + PDF metadata (`data/demo/invoices/`, 6 files) | **6/6 exact** |

The e-mail set covers: a legitimate authenticated invoice, a bank-detail change that passes
DMARC (the floor catches it), a look-alike domain, a DMARC failure with a Reply-To mismatch, a
forged Authentication-Results header, a bank impersonation, a legitimate `.bank.in` sender, a
free-mail “CEO”, a prompt-injection email, and an email with no trusted auth header (GREY, never
PASS). The invoice set covers correct invoices, a changed bank account, an edited amount, an
edited bank account, and a UPI invoice.

### 2.4 Demo scenarios (illustrative)

| Metric | Value |
|---|---|
| Full-engine band matches the expected band (`data/demo/expected_decisions.json`) | **12/12** |
| Detectors change the rules-only outcome | **8/12** |

This is illustrative (n=12, team-authored). It shows *where* detectors matter, not real-world
accuracy.

---

## 3. Named failure cases

A judge should ask “where does it fail?” and get a specific answer.

**Ask layer (product, test split):**

- **47 of 92 attack texts produce no ask at all.** The clean misses are paraphrases outside the
  pattern vocabulary. Examples:
  - `ask-003` (gold A1): *“Can you move 9.5 lakh to the account I just texted you? …”*
  - `ask-014` (gold A1): *“Beneficiary add kar lo, naam Demo Consultancy hai, aur 5,40,000
    transfer kar do aaj shaam …”*
  - `ask-020` (gold A1, Devanagari): *“डील पूरी होने तक पैसा इस सुरक्षित खाते में रखना है, अभी
    ट्रांसफर करें।”*
- **19 of 157 benign AP texts produce a false ask.** Examples:
  - a Hindi dispatch footer (“we never ask for OTP…”) fires A7;
  - an air-conditioning service report footer fires A4;
  - a bank SMS about a declined ₹1 UPI collect fires A6.
- **Devanagari recall is the weakest language** (about 15% in the frozen lexicon; the product
  improves it slightly but it remains the main language gap).
- **Small new payees** (below the floor’s amount threshold) reach ≥ VERIFY only 52.9% of the
  time. That is the deliberate false-positive/coverage trade-off.
- **Credential/remote-access asks with no payment at all** reach ≥ VERIFY 38.1% (test) / 58%
  (all) — a single ask is capped at VERIFY by policy, so a miss there does not become HOLD.

**Parsing / channel limits:**

- A **scanned PDF with no text layer** cannot be parsed; the pipeline returns GREY → at least
  VERIFY, never PASS. It does not silently pass.
- An **email without a trusted `Authentication-Results` header** is GREY → at least VERIFY. We
  never treat “unknown auth” as “authenticated”.
- A **voice note without the local speech engine** is checked only if a transcript exists;
  otherwise the voice itself is “not analysed” and the floor still applies. The UI says so.
- The **video check** is a separate, raise-only signal; if the model files are absent it
  abstains (no signal), not “safe”. See `docs/VIDEO_DEEPFAKE.md`.

---

## 4. What this does **not** claim

- No field accuracy, no “fraud prevented” number, no real-world prevalence.
- No claim that a PASS means “safe”: PASS means the **payment** matches the vendor master and no
  raising signal fired; absence of evidence is not proof of innocence.
- The held-out set is **synthetic**. It was written to test the ask layer, not to estimate
  production traffic.
- The e-mail/invoice fixtures are functional checks (n=10 / n=6).
- The 12 demo scenarios are illustrative.
- The phrasebook is a **product** layer; the research claim is the frozen lexicon.
- A missing detector is an abstention or GREY, never PASS. The policy is raise-only.

---

## 5. How the scoreboard maps to the judging rubric

| Rubric row | What to show |
|---|---|
| **1. Working prototype** | `make judge` on the judge’s own email/PDF/text; `make dry-run` for the full consent → call → alert → OOB → report path |
| **2. Spot-check + measured accuracy** | The tables above with n and CIs; the named failure cases; the held-out test split; the frozen thresholds |
| **3. Own engineering** | `docs/ENGINEERING_DEEP_DIVE.md`: floor + raise-only policy, signal table, X1 cross-channel, deterministic detectors, local ASR, on-device OCR, vault, OOB, report pack |
| **4. Alert + response** | `make dry-run` and `docs/finale/SAFEGUARDS.md`: the alert’s policy band, the OOB question on the approver’s phone, “not me” → HOLD, report drafts with `MANUAL_ONLY` |
| **5. Delivery vs plan** | `docs/finale/DELIVERED.md`: every F-card and P0/P1/P2, with cuts and reasons |

---

## 6. Reproduce the numbers

```bash
# held-out ask detection (writes results/asks_heldout_eval.json)
uv run python -m research.heldout.run_eval

# alert budget (writes results/alert_budget.json + .md; a few minutes)
uv run python -m research.alert_budget.run_alert_budget

# decision relevance on the 12 demo cases
uv run python scripts/decision_relevance.py

# the scoreboard itself (writes results/judge_kit.json + .md)
make judge

# automated story rehearsal (writes results/dry_runs.json + docs/finale/DRY_RUNS.md)
make dry-run
```

Every result JSON records the git commit, the date, the data hashes and the command. The
`results/EVIDENCE_LEDGER.md` is the single allowed source for a number on a slide.
