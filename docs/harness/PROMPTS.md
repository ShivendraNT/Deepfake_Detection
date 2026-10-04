# Prompt cookbook (copy, paste, replace TNN)

All prompts assume the tool has loaded `AGENTS.md` (opencode, Copilot and Codex do this
automatically; Claude Code via `CLAUDE.md`; Gemini CLI via `GEMINI.md`).

---

## 1. Start a task

### opencode (agent: `implementer`, or just run `/task T05`)
```
Task T05. Read AGENTS.md, docs/tasks/T05-ask-extractor.md and tests/tasks/test_t05_ask_extractor.py.
Read ONLY the files listed in the spec. Do not explore the rest of the repo.
1) Write a plan of at most 8 small steps into the "Agent plan" section of the spec.
2) Run `make task T=T05` and show me the first failure.
3) Implement step 1 only, then run `make task T=T05` again. Stop and show me the result.
Never edit tests, contracts, policy or invariants.
```

### Gemini CLI (`/task T05` or)
```
@AGENTS.md @docs/tasks/T05-ask-extractor.md @tests/tasks/test_t05_ask_extractor.py
You are implementing task T05. Follow the spec exactly. Work in small steps:
plan (<= 8 steps) -> run `make task T=T05` -> implement ONE step -> re-run. After each step,
stop and report which tests pass. Do not edit any file not listed in the spec.
```

### GitHub Copilot (Chat / agent mode in VS Code)
```
#file:AGENTS.md #file:docs/tasks/T05-ask-extractor.md #file:tests/tasks/test_t05_ask_extractor.py
Implement task T05 exactly as the spec says. Only edit the files in "Files to create or modify".
Keep every function signature and docstring. After editing, tell me to run `make task T=T05`.
```

### Claude Code (leader)
```
/task-start T07
```
(or: "Implement T07 following docs/tasks/T07-extension-capture.md; plan first, then step by step.")

---

## 2. Debug a failing test

```
`make task T=T08` fails. Here is the FIRST failure only:
<paste ~30 lines of the failure>
1) Explain in 2 sentences why it fails, quoting the spec line it violates.
2) Propose the smallest fix in the source file (NOT in the test).
3) Apply it and re-run `make task T=T08`.
If you have tried 3 fixes for this same error, stop and write a BLOCKED note (AGENTS.md §7).
```

## 3. Write extra tests (agent: `tester`)

```
For task T13, add 3 more edge-case tests to tests/tasks/test_t13_callbacks.py at the END of the
file, marked with the existing `pytestmark`. Cover: <case 1>, <case 2>, <case 3>.
Rules: no network, no real data, use fixtures `master` and `repo` from tests/conftest.py,
do not modify existing tests. Run `make task T=T13`.
```

## 4. Review a diff (agent: `reviewer`, or `/review`)

```
Review my changes for task T12 (`git diff main...HEAD`). Check, and answer each with PASS/FAIL + line refs:
1. Only files listed in docs/tasks/T12-oob-confirm.md were changed.
2. Signatures and docstrings unchanged; contracts not edited.
3. No band is set outside src/satyapan/policy; no signal lowers a band.
4. No network imports outside src/satyapan/adapters; tests use fakes.
5. No secrets, real bank details, real media or dataset text added.
6. Raw OOB tokens are never stored or logged.
7. `make task T=T12` and `make check` were run and are green (ask me for the output).
Finish with: APPROVE or REQUEST CHANGES and a short list of required fixes.
```

## 5. Hand-over when switching tools (rate limits)

```
I am continuing task T10 from another agent. Read AGENTS.md and docs/tasks/T10-extension-sidepanel.md,
especially the "Agent plan" section (steps done so far are ticked). Run `make task T=T10`, tell me
which step we are on, then continue with the NEXT step only.
```

## 6. Ask for an explanation (learning mode)

```
Explain src/satyapan/policy/engine.py to a first-year student: what decide() does, in 6 bullet
points, with one tiny example using fixture case_s07. Do not change any file.
```
