# T12 — OOB-Confirm ("Did you ask for this payment?")

## Goal
One tap sends a confirmation request to the CLAIMED requester's directory identity (in-app inbox,
and SES email in AWS mode). The token is single-use, expires in 10 minutes, and is bound to the
case, amount and beneficiary. Only the logged-in requester can answer. DENIED → HOLD +
SUSPECTED_FRAUD (the policy engine already does this when `case.oob.result == DENIED`).

## Owner
B3. Effort ≈ 5 h. Backend part needs only T02; console page needs T06.

## Depends on
T02 (done), T06 (for the CFO console page).

## Files to create or modify
- `src/satyapan/workflows/oob.py` — hashes, message, `OOBService.create/respond`
- `src/satyapan/adapters/ses_mailer.py` — `SesMailer` (boto3 sesv2 `send_email`, 5 s timeout)
- `console/src/components/OobInbox.tsx` (new) — CFO screen: list messages, Yes/No buttons

## Do not touch
Contracts (OOBRequest is fixed), policy, API route glue unless broken, tests.

## Interfaces
```python
beneficiary_hash(account_number, ifsc, upi_id) -> str
binding_hash(case_id, amount_inr, beneficiary_hash_hex, nonce) -> str
oob_message(case, requester, maker_name) -> str
OOBService(mailer, ttl_minutes=10)
  .create(case, requester, maker_name, now) -> (OOBRequest, raw_token)
  .respond(token, approve, session_employee_id, now) -> OOBRequest
Errors: UnknownTokenError, TokenReplayError, TokenExpiredError, WrongResponderError (all OOBError)
```
Message example: `Did you just ask Priya to pay ₹48,50,000 to A/c ••••4821 (FAKM0000482)?`
Email body must contain the console link `/oob/<token>`.

## Plan (steps)
1. Hash helpers (`hashlib.sha256(f"...".encode()).hexdigest()`).
2. `oob_message` with Indian digit grouping (write a tiny helper or reuse T16's `format_inr` if done).
3. `create`: `secrets.token_urlsafe(32)` for nonce and token; store `OOBRequest` in a dict keyed by
   `token_sha256`; send mail (catch mailer exceptions → `channels=["in_app"]`).
4. `respond`: the 4 error checks in the docstring order; then update result, `spent=True`.
5. `SesMailer` (AWS mode only; sandbox → verified team addresses).
6. Console `OobInbox` for role requester: `api.oobInbox`, extract token from body, Yes/No →
   `api.respondOob`.

## Acceptance criteria
- Binding + token hash correct; raw token never in the stored object; 10-min expiry.
- Deny → HOLD + SUSPECTED_FRAUD; replay, expiry, wrong user, unknown token rejected.
- API flow: maker creates → CFO inbox → CFO denies → case HOLD / SUSPECTED_FRAUD.

## Test command
`make task T=T12`

## Definition of Done
Green + `make check`; demo rehearsal on two browser profiles noted in STATUS.

## Common mistakes
- Storing or logging the raw token.
- Letting anyone holding the link respond (must be logged in as the requester — compromised mailbox).
- Using `random` instead of `secrets`.
- Treating APPROVED as clearing a HOLD (it does not; only the checker clears HOLD).

## Hints and links
- Python `secrets`: https://docs.python.org/3/library/secrets.html
- SES v2 send_email: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sesv2/client/send_email.html

## Agent plan (write yours here)
