# T04 — Domain checks + email signals

## Goal
Deterministic sender checks: look-alike domains (edit distance ≤ 2 + Unicode confusables), banks
not on `.bank.in`, free-mail pretending to be corporate, Reply-To/Return-Path mismatch — and turn a
`ParsedEmail` into raise-only `Signal`s.

## Owner
B2. Effort ≈ 3 h. `domains.py` can start right away; `signals.py` needs T03.

## Depends on
T01 (done); T03 for `signals.py` and the fixture tests.

## Files to create or modify
- `src/satyapan/email/domains.py` — `levenshtein`, `normalise_domain`, `is_lookalike`,
  `claims_to_be_bank`, `is_bank_in`, `is_freemail`
- `src/satyapan/email/signals.py` — `email_signals`

## Do not touch
Contracts, policy, tests, fixtures, `email/parser.py` (T03's file — ask B2/T03 owner for fixes).

## Interfaces
```python
levenshtein(a: str, b: str) -> int
normalise_domain(domain: str) -> str
is_lookalike(domain: str, known_domains: set[str], max_distance: int = 2) -> str | None
claims_to_be_bank(display_name: str, domain: str) -> bool
is_bank_in(domain: str) -> bool
is_freemail(domain: str) -> bool
email_signals(parsed: ParsedEmail, master: MasterData, evidence_id: str) -> DetectorOutput
```
Signal example: `Signal.make(ReasonCode.EMAIL_LOOKALIKE_DOMAIN, source=SignalSource.DETERMINISTIC,
evidence_ids=[evidence_id], detector=DETECTOR_NAME, detail={"imitates": "kaveri-packaging.example"})`.
Rules: see the docstring of `email_signals` (it IS the spec). Expected signals per fixture:
`data/demo/emails/expected.json` → `"signals"` and `"grey"`.

## Plan (steps)
1. `levenshtein` (dynamic programming, two rows). 4 table tests.
2. `normalise_domain`: lower, strip trailing dot, `domain.encode().decode("idna")` only for labels
   starting with `xn--` (wrap in try/except → keep original).
3. `is_bank_in`, `is_freemail` (use `FREEMAIL_DOMAINS`).
4. `claims_to_be_bank`: tokens = `re.split(r"[^a-zऀ-ॿ]+", display_name.lower())` +
   domain labels split on `.` and `-`; True if any token in {"bank", "banking", "rbi", "nbfc", "बैंक"}
   or "reserve bank" in the display name.
5. `is_lookalike`: skip exact matches; return the first known domain with distance ≤ 2; also map
   confusables with `confusable_homoglyphs` (e.g. Cyrillic `а` → `a`) and compare again.
6. `email_signals`: apply the rules in the docstring in order; each code at most once.
7. Run the 10 fixture tests.

## Acceptance criteria
- 25 table-driven tests in `test_domain_table` pass.
- `email_signals` gives exactly the expected codes for all 10 fixtures; all sources deterministic.

## Test command
`make task T=T04`

## Definition of Done
Green task tests + `make check`; STATUS.md updated; commit `T04: ...`.

## Common mistakes
- Counting an exact match as a look-alike.
- Using the subject for the bank-claim rule (vendors write "updated bank details"; that is ask A7).
- Emitting `EMAIL_AUTH_PASS` when another email signal fired (it is only for "nothing wrong").
- Treating ESP bounce domains (`amazonses.com` …) as Reply-To/Return-Path mismatches.
- Typing `group=`/`target=` by hand instead of `Signal.make`.

## Hints and links
- confusable_homoglyphs: https://pypi.org/project/confusable-homoglyphs/
- RBI `.bank.in`: domain reserved for banks (registrar IDRBT).

## Agent plan (write yours here)
