# T14 — Explanation templates (English + Hindi) for every reason code

## Goal
Authoritative, plain-language text for every `ReasonCode` in EN and HI (Devanagari), plus a
template explanation for a decision. This is what the maker reads; the LLM summary (T15) is
optional prose on top and falls back to this.

## Owner
Saksham. Effort ≈ 3 h.

## Depends on
T02 (done).

## Files to create or modify
- `src/satyapan/explain/templates.py` — fill `REASON_TEXT` for ALL codes; `reason_text`, `explain_template`

## Do not touch
`explain/prompt.py`, contracts, tests.

## Interfaces
```python
REASON_TEXT: dict[ReasonCode, dict[Lang, str]]
reason_text(code: ReasonCode, lang: Lang) -> str
explain_template(decision: Decision, lang: Lang) -> Explanation   # text starts "Band: VERIFY" / "स्तर: VERIFY"
SUGGESTED_LINES: dict[Lang, str]
```

## Plan (steps)
1. List codes: `python -c "from satyapan.contracts import ReasonCode; print(*ReasonCode, sep='\n')"`.
2. Write EN text for each (≤ 2 sentences: what happened + what to do). Use the two examples' tone.
3. Write HI text (Devanagari). Ask a Hindi-fluent teammate to proofread. Keep band names in English.
4. `reason_text`, `explain_template` (headline + one line per reason code, `\n`-joined).
5. `GET /cases/case_s07/explanation?lang=hi` works.

## Acceptance criteria
Every code has non-empty EN + Devanagari HI ≤ 300 chars; no "safe/legitimate/verified/genuine"
(or सुरक्षित/वैध/सत्यापित/असली/प्रामाणिक); headline format; API returns 200.

## Test command
`make task T=T14`

## Definition of Done
Green + `make check`; a Hindi speaker has proofread (note who in STATUS).

## Common mistakes
- Reassuring words ("the vendor is genuine") — templates must never reassure.
- Machine translation left unchecked. Keep Hindi simple, everyday words.
- Text that tells the maker to call a number from the message. Always "number on file".

## Hints and links
- Lewis et al. 2022: warnings alone barely help — give a concrete ACTION in every line.

## Agent plan (write yours here)
1. Enumerate every `ReasonCode` (33) and group them floor / email / doc / voice / ask / style /
   watchlist / decision-level using `contracts/signal_table.py` + ARCHITECTURE §6.1-6.2.
2. Draft EN text per code: one line of WHAT HAPPENED + one line of WHAT TO DO (concrete action),
   ≤ 300 chars, no reassuring words, callback wording always "number on file".
3. Draft HI text in simple everyday Devanagari, same two beats; band names (PASS/VERIFY/HOLD)
   and product terms (OOB-Confirm, PDF) stay in English; ask a Hindi speaker to proofread.
4. Fill `REASON_TEXT` for all 33 codes; verify with a script that keys == set(ReasonCode),
   lengths ≤ 300, Devanagari present, forbidden words absent.
5. Implement `reason_text` (direct dict lookup, `KeyError` if missing).
6. Implement `explain_template`: headline `Band: <band>` / `स्तर: <band>` + one line per
   `decision.reason_codes` in order, `\n`-joined, `source="template"`.
7. Run `pytest --task T14 -v` until green, then lint + typecheck + full test run.
8. Update `docs/STATUS.md` (status + Hindi proofreader note) after the leader's review.
