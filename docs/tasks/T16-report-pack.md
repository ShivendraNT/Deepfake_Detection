# T16 — Report pack (attempted + money-sent), UTR-first

## Goal
Human-triggered drafts that help freeze money in the golden hour: a 1930 call script with the UTR
on line 1, a bank fraud-desk email, an NCRP complaint draft (copyable fields), a Chakshu note, an
evidence index (JSON + printable HTML) and a BSA Sec 63 helper template. Never auto-submitted.

## Owner
B2. Effort ≈ 5 h.

## Depends on
T09 (evidence index uses vault data — fixtures already have hashes), T13 (statuses). The builder
can be written now against fixture `case_s12` (CONFIRMED_FRAUD with UTR).

## Files to create or modify
- `src/satyapan/report/pack.py` — `format_inr`, `build_report_pack`, `render_html`
- `src/satyapan/report/templates.py` (new, optional) — text templates as constants

## Do not touch
Contracts (`ReportPack` is fixed), API route, tests. Never add network/subprocess imports here.

## Interfaces
```python
format_inr(4850000) == "₹48,50,000"
build_report_pack(case, master, custody_rows, variant: "ATTEMPTED" | "MONEY_SENT", generated_by, now) -> ReportPack
render_html(pack) -> str        # html.escape every value; 1930 script first
```
1930 script line 1 example:
`UTR FAKEUTR620001: I want to report a financial cyber fraud. Amount ₹6,20,000 sent on 04 Oct 2026 16:42 from Fictional Bank (a/c ••••1234) by NEFT to beneficiary a/c 99996666006200, IFSC FAKE0000620, bank Fictional Bank E.`

## Plan (steps)
1. `format_inr` (Indian grouping: last 3 digits, then groups of 2).
2. Unlock rules → `ReportNotUnlockedError`.
3. `TransactionFacts` from `case.txn`.
4. 1930 script (MONEY_SENT), bank email, NCRP fields in the order in the docstring, Chakshu note.
5. Evidence index from `case.evidence`; `custody_head` from rows.
6. Sec 63 helper text: "To be signed by the person in charge of the device/system ... (we do not
   sign; counsel to review)".
7. `render_html` with `html.escape`; API check with the checker role.

## Acceptance criteria
`make task T=T16`: Indian formatting; UTR on line 1; subject starts "URGENT: fraud"; NCRP order;
evidence index hashes; MANUAL_ONLY; ATTEMPTED needs suspected/confirmed; MONEY_SENT needs confirmed
+ UTR; HTML escapes attacker text; maker gets 403.

## Test command
`make task T=T16`

## Definition of Done
Green + `make check`; NCRP field order verified against the live portal before the demo (note in STATUS).

## Common mistakes
- Leading with media hashes instead of transaction facts (banks freeze money on UTR + accounts).
- Any "submit" button or HTTP call to cybercrime.gov.in / 1930 (forbidden; invariant test).
- Forgetting to escape HTML.

## Hints and links
- NCRP: https://cybercrime.gov.in/ · 1930 helpline · Chakshu: https://sancharsaathi.gov.in/sfc/

## Agent plan (write yours here)
