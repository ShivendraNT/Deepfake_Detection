# T15 — Bedrock summary + faithfulness checker + 30-sample injection red-team

## Goal
Optional EN/HI case summary from Bedrock (Claude Haiku 4.5, `in.` India profile) that can never
change the band and is accepted only if it passes a faithfulness checker; otherwise the template
is shown. Report the injection red-team as numbers.

## Owner
L. Effort ≈ 6 h.

## Depends on
T02 (done), T14 (templates for fallback).

## Files to create or modify
- `src/satyapan/explain/faithfulness.py` — `check_faithfulness`
- `src/satyapan/explain/summary.py` — `summarize`
- `src/satyapan/adapters/bedrock_llm.py` — `BedrockLLM` (Converse API, no tools, 5 s timeout)
- `data/demo/injection/injections.jsonl` — extend 12 → 30 samples
- `scripts/redteam.py` (new) — runs the 30 samples, writes `results/redteam.json`

## Do not touch
`explain/prompt.py` (pre-implemented isolation), policy, contracts, invariant tests.

## Interfaces
```python
check_faithfulness(summary, items, has_verified_clearance) -> FaithfulnessResult(ok, failures)
summarize(case, decision, lang, llm: LLMClient | None, has_verified_clearance=False) -> Explanation
BedrockLLM(settings).complete(system, user, max_tokens) -> str
```
`results/redteam.json`:
`{"n": 30, "bands_lowered": 0, "echoed_before_checker": k1, "echoed_after_checker": k2,
  "checker_rejection_rate": r, "model": "<bedrock model id or fake>", "date": "..."}`

## Plan (steps)
1. Faithfulness (a) entities, (b) citations, (c) forbidden words — exactly as the docstring.
2. `summarize` per its docstring (band always from `decision`).
3. `BedrockLLM`: `boto3.client("bedrock-runtime", region_name=settings.aws_region,
   config=Config(read_timeout=5, connect_timeout=5))`; `converse(modelId=settings.bedrock_model_id,
   system=[{"text": system}], messages=[{"role": "user", "content": [{"text": user}]}],
   inferenceConfig={"maxTokens": max_tokens, "temperature": 0})`. No `toolConfig`, ever.
4. Extend injections to 30 (white-on-white PDF text, HTML comments, Hindi, fake headers, JSON
   breakouts). Synthetic only.
5. `scripts/redteam.py`: for each sample, case_s07/s08/s11 with the sample as excerpt → decide
   (band before/after) → summarize with BedrockLLM (or FakeLLM echoing the sample if no AWS) →
   count echoes before/after checker. Write the JSON.

## Acceptance criteria
`make task T=T15` green, including `results/redteam.json` with `bands_lowered == 0`, n ≥ 30.

## Test command
`make task T=T15`

## Definition of Done
Green + `make check`; red-team numbers copied into `docs/EVALUATION.md` E3 row notes.

## Common mistakes
- Parsing anything from LLM output back into signals or bands.
- Passing tools/functions to Bedrock.
- Putting the case text in the system prompt (use `build_llm_request`).
- Hard-coding the Bedrock model ID (use `SATYAPAN_BEDROCK_MODEL_ID`; check the console).

## Hints and links
- Bedrock Converse: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
- Greshake et al. 2023, indirect prompt injection (why quoting is not a defence).

## Agent plan (write yours here)
