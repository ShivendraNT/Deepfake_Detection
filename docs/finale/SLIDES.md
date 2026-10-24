# Finale slide copy (paste into the deck)

> Six slides, numbers only from `results/EVIDENCE_LEDGER.md`. The existing
> `Satyapan_Pitch_Deck.pptx` is the Round-1 deck; this is the finale story and the exact copy.
> Keep it to 3 minutes live: the demo is the product, the slides are the evidence.

---

## Slide 1 — The moment

**Title:** The money leaves before the detector finishes

- 2024, Arup: ~US$25.6M paid after a video call where the “CFO” was a deepfake.
- 2026: the best video detector scores **69.7% AUROC** on the newest generators; one detector
  scores **34.5%** on commercial generators — below chance on some.
- Detectors are losing the race. **So we stop racing them.**

**One line:** *Satya does not try to prove the voice is fake. It makes sure the payment is real.*

---

## Slide 2 — How it works

**Title:** The floor is trusted; evidence can only raise it

```
maker's payment + vendor master + config
                │
          POLICY FLOOR  ── PASS / VERIFY / HOLD
                │
   emails · invoices · asks · screen · voice · video · X1
                │  (each may raise, never lower)
          FINAL BAND  ── alert → verify the transaction → report
```

- Deepfake call, changed bank details, edited invoice, urgent secrecy, skipped approval — all are
  **raise-only signals**.
- The approver is asked through a channel the attacker does not control: their own phone.
- Every report is a draft. **A human presses Submit.**

---

## Slide 3 — Satya, live (the demo)

**Title:** One companion, the whole moment of decision

1. He starts **asleep**. Consent card → per-call yes. Never the microphone.
2. Meet call: local Whisper → asks + cues → **Pause before you pay**.
3. One tap: “Rajesh, did you ask for ₹48,50,000 to ••••4821?” → **I did not request this** →
   case stays **HOLD**.
4. Drop a vendor email + invoice: “the account differs from the vendor master” → call the vendor
   on the registered number.
5. Money already left: **five drafts in the golden hour**, UTR first, §63 hashes, all
   `MANUAL_ONLY`.

**Fallback:** replay is labelled **DEMO REPLAY — NOT LIVE CAPTURE**. We say it out loud.

---

## Slide 4 — Measured, with the failures

**Title:** What we measured (and where it fails)

Held-out, pre-registered test split (synthetic, no real data):

| Metric | Value | n |
|---|---|---|
| Product ask detection — precision | 61.2% [49.2–72.0] | 67 flagged |
| Product ask detection — recall | 39.4% [30.6–49.0] | 104 gold |
| Attack texts with ≥ 1 ask | 48.9% [39.0–59.0] | 92 |
| Benign AP texts with a false ask | 12.1% [7.9–18.1] | 157 |
| Routine payments at HOLD (false alarms) | **3.5% [1.7–7.0]** | 200 |
| Attacks at ≥ VERIFY | **78.6% [69.5–85.5]** | 98 |
| Payee-change / large new-payee / split attacks at ≥ VERIFY | **100%** | 17 / 37 / 6 |

**Say the failures out loud:** small new payees 52.9%; credential/remote asks with no payment
38.1% (test); Devanagari is the weakest language; a scanned PDF or unknown sender auth is GREY
(at least VERIFY), never PASS. The frozen research lexicon is weaker; the product phrasebook is
reported separately. Full protocol: `docs/JUDGE_KIT.md`.

---

## Slide 5 — What we engineered

**Title:** Not a wrapper

- **Policy engine**: floor from the payment + vendor master; a signal table that can only raise;
  LLM/style capped at VERIFY; detector crash → GREY; property-tested invariants.
- **Ask layer**: frozen lexicon + context filter + live phrasebook; English, Hinglish,
  Devanagari; every hit explained by the exact words.
- **X1 cross-channel**: a call ask + a new payee within 30 minutes → VERIFY; secrecy/bypass in the
  same window → HOLD. Only a companion sees both channels.
- **Channels**: email auth/look-alike/bank checks; invoice master diff + PDF metadata; on-device
  OCR; local Whisper; raise-only voice/video.
- **Response**: OOB from the directory, single-use 10-minute token; five golden-hour drafts;
  vault + §63 hashes; **no auto-report**.
- **Desktop**: four windows, consent-first state machine, one-card bubble, privacy tab.

Walkthrough: `docs/ENGINEERING_DEEP_DIVE.md`.

---

## Slide 6 — Delivery and the ask

**Title:** Built in the window, cut on purpose

**Built:** consent/modes, live call route A + replay, chips + alert, OOB phone page, file checks,
Screen Guard, Scribe/Report Copilot, Notebook, PWA OOB, automated dry runs 3/3, `make check` green
(818 passed).

**Cut, with reasons:** Gmail button (P2; no demo value), loopback as the *primary* route
(permission risk; kept as P1), “keep call audio” UI (vault exists; not in the 3-minute story),
fresh deck (story is here), Windows/Linux packaging (targets exist; untested on real hardware).

**The ask:** pilot with one SME finance team and their vendor master; we bring the install, the
consent receipts and the measured test kit. The floor is the product; the models are inputs.

**One line to close:** *When the voice is fake, the payment is still real. Verify that.*
