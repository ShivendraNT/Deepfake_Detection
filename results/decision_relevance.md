| Case | Scenario | Action | Rules-only | Full | Changed? | Region |
|---|---|---|---|---|---|---|
| case_s01 | Kaveri monthly invoice (routine) | K1 | PASS | PASS | no | baseline |
| case_s02 | Kaveri 'overdue' reminder from look-alike domain | K1 | PASS | VERIFY | yes | R2 |
| case_s03 | Small new payee + voice note flagged synthetic | N1 | PASS | VERIFY | yes | R2 |
| case_s04 | 'Send payroll file and share the OTP' request | D1 | PASS | HOLD | yes | R2 |
| case_s05 | Godavari invoice after 6 months dormant | K2 | VERIFY | VERIFY | no | floor only |
| case_s06 | 'CFO' on Meet: confidential escrow ₹48.5 lakh (Moment 1) | N2 | VERIFY | HOLD | yes | R1/R3 |
| case_s07 | Narmada bank change, every detector green (Moment 2) | C1 | VERIFY | VERIFY | no | floor catches it |
| case_s08 | Kaveri bank change from look-alike domain | C1 | VERIFY | HOLD | yes | R3 |
| case_s09 | Tapti asks to change phone number on file | T1 | HOLD | HOLD | no | floor only |
| case_s10 | Tapti UPI payment from a watch-listed sender | K1 | PASS | VERIFY | yes | R4 |
| case_s11 | Narmada invoice email containing a prompt injection | K1 | PASS | VERIFY | yes | R2 (LLM capped) |
| case_s12 | Golden hour: ₹6.2 lakh already sent to a mule account | C1 | VERIFY | HOLD | yes | golden hour |

Illustrative, n=12 team-authored scenarios. Detectors changed the outcome in 8/12.
