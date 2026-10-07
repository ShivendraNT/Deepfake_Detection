# Threat model

Scope: the Payment Verification Desk (console + API) and the Chrome extension, deployed for one
company's AP team. Assets: money in the company's bank account; the vendor master (trust anchors);
evidence integrity; employees' and counterparties' personal data.

## 1. Attackers

| ID | Attacker | Capabilities | Goal |
|---|---|---|---|
| A1 | Impersonator on a call | real-time voice clone / face swap in Meet or Teams; scripted pressure; knows org chart | get the maker to pay a new account (Arup-style) |
| A2 | BEC / vendor email compromise | sends from look-alike domain OR from the vendor's real (compromised) mailbox with valid DMARC; edits invoice PDFs | redirect a genuine invoice to a mule account |
| A3 | Prompt injector | puts instructions in email bodies, HTML comments, hidden PDF text, fake headers, Hindi text | make the LLM or tool say "safe", lower the band |
| A4 | Query-access attacker (oracle) | submits their own fakes/messages repeatedly | tune a fake until the tool says PASS |
| A5 | Insider (maker under pressure or malicious) | can enter transactions, upload evidence, try to clear cases | push a payment through |
| A6 | Compromised executive mailbox | can click links in the CFO's email | approve an OOB-Confirm without the CFO |

Out of scope: compromise of the backend host, of the bank, or of the browser itself; phone-call
(PSTN) fraud; nation-state attacks on AWS.

## 2. Threats → mitigations → tests

| Threat | Mitigation | Where enforced / tested |
|---|---|---|
| A1 perfect deepfake fools the detector | detector is not the gate: N2/C1 floor + OOB-Confirm to the requester's directory identity + callback on master number | `policy/floor.py`; `tests/tasks/test_t12_oob.py` |
| A1 manipulated maker does the callback on a number the caller supplied | callback number comes only from master/directory; voice flag moves verification to the checker (VERIFY→HOLD) | `policy/clearance.py`; `tests/invariants/test_floor_always_applies.py` |
| A1 caller pre-empts callback ("I'm boarding") | OOB-Confirm cannot be intercepted by the call; HOLD needs checker callback + security ack | `workflows/oob.py`, `workflows/status.py` |
| A2 compromised vendor mailbox passes DMARC | floor C1 fires on any bank change vs master regardless of email auth | demo Moment 2; `case_s07` fixture |
| A2 look-alike domain | Levenshtein ≤ 2 + Unicode confusables vs master/directory domains | `email/domains.py` (T04) |
| A2 edited invoice | IFSC/account/UPI diff vs master; `%%EOF` count + ModDate | `document/` (T08) |
| A3 injection lowers the band | band only from deterministic floor + raise-only signals; LLM capped at VERIFY; LLM output never parsed into signals | `tests/invariants/test_injection_cannot_lower.py`, `test_llm_cap.py`, `test_monotonicity.py` |
| A3 injection in the system prompt | constant system prompt; untrusted text only as JSON values ≤ 300 chars | `tests/invariants/test_prompt_isolation.py` |
| A3 LLM summary echoes "this is safe" | faithfulness checker (entities, citations, forbidden words) → template fallback | `explain/faithfulness.py` (T15) |
| A3 fake `Authentication-Results` header | only the topmost header from our own authserv-id is trusted | `email/parser.py` (T03); fixture `05_fake_auth_header.eml` |
| A3 hidden HTML/PDF text | HTML comments and `display:none` removed from body text; PDF text layer only | T03 / T08 tests |
| A4 oracle tuning | makers see band + reason codes only; scores for checker/security only; citizen page band + action only; rate limits; no public upload endpoint | `api/views.py`; `tests/invariants/test_oracle_coarsening.py` |
| A5 maker clears HOLD | role check: only checker clears HOLD | `policy/permissions.py`; `tests/invariants/test_permissions.py` |
| A5 maker sets CONFIRMED_FRAUD / system auto-reports | CONFIRMED_FRAUD only checker/security; no submit endpoints; MANUAL_ONLY packs | `tests/invariants/test_no_auto_reporting.py` |
| A5 urgent-payment pressure | override needs two distinct senior approvers + reason + 48 h review; never on suspected/confirmed fraud | `workflows/status.py` (T13) |
| A6 CFO mailbox compromised | email link alone is insufficient: responder must be logged in as the requester; N2 > ₹10 lakh needs callback AND OOB | `workflows/oob.py` (T12) |
| OOB token replay / forwarding | single-use nonce, 10-minute expiry, binding = SHA-256(case ‖ amount ‖ beneficiary ‖ nonce), raw token never stored | T12 tests |
| Evidence tampering after capture | SHA-256 at intake; hash-chained custody; head anchored to S3 Object Lock | `tests/invariants/test_custody_chain.py`; T09 |
| Detector outage hides risk | any detector error → GREY → ≥ VERIFY + checker queue | `pipeline.py` |
| Data leaves India | AWS mode uses ap-south-1 only; LLM runs locally (Ollama) | `settings.py`; DATA_POLICY |
| Team leaks data to free coding agents | AGENTS.md rule 10; fake fixtures; `.env` read denied in opencode config | `opencode.json` |

## 3. Residual risks (say them honestly)

- A perfect deepfake on a K1-floor payment (known vendor, same account, in-pattern amount) passes
  if the detector misses it — but the money then goes to the genuine vendor's registered account.
- A mule account opened in a look-alike *name* passes the bank-shown-name check; C1/N2 floors
  still force a callback.
- Ask-obfuscation (attack set P2 in the research) can evade the deterministic extractor; the
  research reports this residual exposure as a number.
- The voice detector's false-alarm rate on real Meet audio is only as good as the τ calibration
  set (team voices, n stated on the slide).
- Demo identity headers are not authentication. Production needs SSO.
