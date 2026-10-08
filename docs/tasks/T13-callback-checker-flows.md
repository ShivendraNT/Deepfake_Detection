# T13 — Callback logging, checker HOLD flow, status changes, override, watchlist

## Goal
Make verification real: log callbacks ONLY to the trusted number, decide whether the clearance
requirement is met, let only the right role clear or change status, support the two-approver
urgent override, and keep a 30-day watchlist of flagged senders/calls.

## Owner
Saksham. Effort ≈ 6 h.

## Depends on
T02 (done), T06 (console buttons; backend can start now).

## Files to create or modify
- `src/satyapan/workflows/callbacks.py` — `record_callback`, `evaluate_clearance`
- `src/satyapan/workflows/status.py` — `clear_case`, `set_status`, `acknowledge_security`, `request_override`
- `src/satyapan/workflows/watchlist.py` — `Watchlist.add/add_from_case/signals_for`
- `console/src/components/VerifyPanel.tsx` (new) — callback form + Clear/Status buttons per role

## Do not touch
`policy/permissions.py` and `policy/clearance.py` (use them, don't change them), contracts, tests.

## Interfaces
Exact signatures and rules are in the docstrings of the three files (they are the spec). Key points:
- Trusted number = `resolve_callback_number(case, master, case.decision.action_type)`; compare
  digits only (`re.sub(r"\D", "", s)`); mismatch → `CallbackNumberError`.
- `evaluate_clearance(case, req, master) -> ClearanceStatus(satisfied, done, missing)`.
- `clear_case` uses `can_clear(role, case.decision.band)`; HOLD needs CHECKER_CALLBACK + SECURITY_ACK.
- `set_status` uses `can_set_status`; CONFIRMED_FRAUD is final.
- `request_override`: 2 distinct active senior approvers, reason ≥ 10 chars, `review_due_at = now + 48h`.
- Watchlist keys `"domain:<d>"` / `"call:<id>"`; expiry 30 days; `WATCHLIST_HIT` signal.

## Plan (steps)
1. `record_callback` + number check (2 tests).
2. Bank-name normaliser for BANK_NAME_MATCH (casefold, strip punctuation, `pvt`→`private`,
   `ltd`→`limited`, collapse spaces).
3. `evaluate_clearance` method by method; DENIED anywhere → not satisfied.
4. `clear_case`, `acknowledge_security`, `set_status` (+ watchlist add on fraud statuses).
5. `request_override`.
6. `Watchlist`.
7. Console `VerifyPanel` (shows the trusted number, "never use a number from the message").

## Acceptance criteria
`make task T=T13`: wrong number rejected; C1 needs callback + bank-name match; denied callback
never clears; maker can't clear HOLD; checker clears HOLD after callback + security ack and the
band stays HOLD; status permissions; override rules; watchlist expiry.

## Test command
`make task T=T13`

## Definition of Done
Green + `make check`; STATUS updated.

## Common mistakes
- Changing `case.decision.band` when clearing (clearing changes `status` only).
- Accepting the number typed by the maker as "trusted".
- Letting the system or maker set CONFIRMED_FRAUD.
- Approving an override with the same person twice.

## Hints and links
- Rules table: `docs/ARCHITECTURE.md` §6.4.

## Agent plan (write yours here)

1. [x] `record_callback`: `resolve_callback_number(case, master, case.decision.action_type)`,
   compare digits only (`re.sub(r"\D", "", s)`); no trusted number / mismatch →
   `CallbackNumberError`; build `CallbackRecord(id="cb_<hex>", number_source=...)`.
   → `test_callback_must_use_master_number`.
2. [x] Bank-name normaliser for `BANK_NAME_MATCH`: casefold → drop punctuation → `pvt`→`private`,
   `ltd`→`limited`, `llp`→`limited liability partnership` → collapse spaces.
3. [x] `evaluate_clearance`: mark each `req.methods` entry done (CONFIRMED callbacks, approved
   OOB, bank-name match, security ack, 2 approvers / 2 distinct CONFIRMED callbacks); any `DENIED`
   callback anywhere → `satisfied = False`; mode `all` / `any` / `none`. → 3 tests.
4. [x] `clear_case` (`can_clear` → PermissionError; requirements missing → ValueError; band
   untouched) and `acknowledge_security` (SECURITY only). → 2 tests.
5. [x] `Watchlist` (`add`, `add_from_case`, `signals_for`): expiry `now + days`, one deterministic
   `WATCHLIST_HIT` signal for any unexpired `domain:` / `call:` key.
6. [x] `set_status` (`can_set_status`, CONFIRMED_FRAUD final, fraud → `DEFAULT_WATCHLIST.add_from_case`)
   and `request_override` (2 distinct active senior approvers, reason ≥ 10 chars, +48 h review).
   → 3 tests.
7. [x] Console `console/src/components/VerifyPanel.tsx` (new): trusted number from
   `decision.clearance.callback_number` + "never use a number from the message", log-callback form,
   Clear / Status / security-ack buttons per role; wired into `CaseView` + `api.ts` helpers.
8. [ ] `pytest --task T13` (9/9 green ✓), `ruff` ✓, `mypy` ✓, `tsc --noEmit` ✓, `vitest` ✓,
   full suite = the same 17 pre-existing environment failures ✓, STATUS → `done` ✓, commit + push
   (waiting for the branch command).
