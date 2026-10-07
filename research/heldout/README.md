# Held-out ask set (lexicon-blind)

Two files used to measure the frozen ask extractor (T05, lexicon v1.0) and the alert budget.

| File | Rows | What |
|---|---|---|
| `asks_heldout.jsonl` | 172 | Attacker asks, A1-A7, gold labels in `asks` (multi-label) |
| `benign_ap.jsonl` | 325 | Benign accounts-payable / business texts, `asks: []` |

Both are **synthetic**. All names, phone numbers (`+91-00000-…`), accounts (`9999…`),
IFSCs (`FAK…`), UPI IDs (`@fakeupi`), domains (`*.example`) and banks ("Fictional Bank A") are
invented. No real people, companies, banks or products are named.

## Disclosure (who wrote this and what they had seen)

- Written on 2026-10-07 by an **AI coding agent (Claude, Anthropic)** working for the team lead.
- It was written **before** the author opened `src/satyapan/asks/` (lexicon and extractor) or
  `tests/tasks/data/t05_ask_sentences.jsonl`. The git history shows this file committed before
  any later commit that touches those paths.
- **Contamination risk, stated plainly:** the author had read the Round 1 judge-panel report. It
  quotes about 7 probe sentences and names 4 benign texts the lexicon flags (OTP SMS with
  "do not share", a confidentiality footer, a Diwali gift-card notice, a "new account manager"
  intro). So the benign set deliberately contains these categories. That can make the benign
  false-ask rate look *worse* than a random sample of AP mail. The ask set was not tuned to evade
  the lexicon, but the author knew it is a surface keyword lexicon.
- One author. No second annotator, so no inter-annotator agreement. Labels follow the
  definitions below; a human should spot-check before the numbers are quoted as final.

## Label definitions (gold `asks`)

An ask is a request **to the reader** to do something. Warnings, negations ("never share your
OTP") and reports about an ask ("someone asked us to pay a new account, I forwarded it to
security") are **not** asks.

| Code | Ask |
|---|---|
| A1 | Pay / transfer to a new, "safe", escrow, holding or otherwise different account or beneficiary |
| A2 | Share an OTP, PIN, password, CVV, token code or similar credential with the requester |
| A3 | Install remote-access software, share the screen, or hand over device control to the requester |
| A4 | Secrecy or isolation: keep it from colleagues, do not call back, delete the chat, cover story |
| A5 | Bypass a control: skip approval / checker / PO / callback, split to avoid limits |
| A6 | Pay with gift cards / vouchers, crypto, or accept a UPI collect request / scan a QR "to receive" |
| A7 | Change payee or bank details of an existing payee (new account, new IFSC, new UPI ID) |

`benign_ap.jsonl` rows have `asks: []`. Six rows are marked `"borderline": true`: legitimate
messages that contain a real but benign request close to an ask definition (e.g. HR asking staff
not to discuss salary revisions, a vendor saying its old contact has left). They stay in the set
(they are realistic AP traffic) and the eval reports the false-ask rate with and without them.

## Pre-registered split (fixed before any measurement)

`split = "dev" if int(sha256(id), 16) % 2 == 0 else "test"`.

- **dev** may be looked at while designing the leader-owned context layer
  (`src/satyapan/context/`). Its "after" numbers are optimistic.
- **test** must not be inspected row-by-row while tuning. Its "after" numbers are the honest
  estimate. Report both; quote test.

## Known limitations (say these next to any number)

- Text is clean typed text. Live call transcripts (Whisper) will have ASR errors, so live recall
  will be lower.
- Real product names of remote-access apps and gift-card brands were avoided on purpose (data
  policy). A lexicon keyed on brand names will look worse here than on real scam text.
- The mix of ask types and languages is chosen for coverage, not to match real attack frequency.
  Per-ask n is 22-31, so the 95% CIs are wide (about ±15-20 points).
- English 83, Hinglish (Roman) 51, Hindi (Devanagari) 38 asks. No other Indian languages.
