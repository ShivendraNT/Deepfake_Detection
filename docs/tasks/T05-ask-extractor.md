# T05 — Ask extractor v1.0 (A1-A7; English, Hinglish, Devanagari)

## Goal
Deterministic lexicon + regex extractor for the seven attacker-invariant asks. It is the product
module (C5) AND research detector D4, so once done it is FROZEN and tagged.

## Owner
B1. Effort ≈ 1 day (most time = writing good test sentences and patterns).

## Depends on
T01 (done).

## Files to create or modify
- `src/satyapan/asks/lexicon.py` — extend `LEXICON` (≥ 8 patterns per ask type across scripts)
- `src/satyapan/asks/extractor.py` — `normalise`, `extract_asks`, `ask_signals`, `ask_score`
- `tests/tasks/data/t05_ask_sentences.jsonl` — extend from 30 to ≥ 80 labelled sentences (allowed!)

## Do not touch
Contracts, policy, other tests. NEVER copy or look at ICFD **test** rows (research leakage).
You may read ICFD *train* rows; log which ones in `research/LEXICON_LOG.md` (new).

## Interfaces
```python
normalise(text: str) -> str
extract_asks(text: str) -> list[AskSpan]        # AskSpan(ask_type, start, end, text, lexicon_id, script)
ask_signals(spans: list[AskSpan], evidence_id: str) -> list[Signal]   # one per distinct ask type
ask_score(text: str) -> int                      # number of distinct ask types (research D4)
```
Example: `extract_asks("Arjun ko mat batana, OTP batao")` →
`[AskSpan(ask_type="A4", text="ko mat batana"...), AskSpan(ask_type="A2", text="OTP batao", ...)]`
(exact span text depends on your patterns; spans index into `normalise(text)`).
Sentence file format: `{"text": "...", "asks": ["A1","A4"], "lang": "en" | "hi-Latn" | "hi-Deva"}`.

## Plan (steps)
1. `normalise` (NFC, quotes, whitespace). 2. `extract_asks` over the seed lexicon; merge
overlapping same-type spans; set `script`. 3. `ask_signals` + `ask_score`.
4. Write 50+ more sentences: every ask type in `en` and `hi-Latn`, ≥ 10 `hi-Deva` total, plus
negatives (normal finance talk) and tricky cases ("PIN code", "never share your OTP").
5. Improve patterns until precision ≥ 0.90 and recall ≥ 0.85 (printed by the test).
6. Fix the known false positive "PIN code" (negative lookahead) and relabel that sentence.
7. Set `LEXICON_VERSION = "1.0.0"`; ask the leader to tag `lexicon-v1.0`.

## Acceptance criteria
- ≥ 80 sentences; precision ≥ 0.90; recall ≥ 0.85 (`test_precision_recall_on_team_sentences`).
- Every ask type has `en` and `hi-Latn` sentences; ≥ 10 Devanagari sentences.
- Spans index into the normalised text; output deterministic; one signal per distinct type.

## Test command
`make task T=T05` (prints precision/recall — copy them into STATUS.md notes)

## Definition of Done
Green + `make check`; LEXICON_VERSION 1.0.0; STATUS note with P/R and n; leader tags the commit.

## Common mistakes
- Patterns so broad they fire on normal talk ("account" alone, "pin" alone).
- Forgetting `re.IGNORECASE` or Devanagari (no `\b` word boundaries work reliably around
  Devanagari — use plain substrings or `(?<!\S)`/`(?!\S)`).
- Writing test sentences by copying the patterns (they then test nothing). Write natural speech.
- Changing the lexicon after the research freeze.

## Hints and links
- Python `re`: https://docs.python.org/3/library/re.html ; test patterns at https://regex101.com (Python flavour)
- Asks A1-A7 definitions: `docs/RESEARCH_PROTOCOL.md` §2

## Agent plan (write yours here)
