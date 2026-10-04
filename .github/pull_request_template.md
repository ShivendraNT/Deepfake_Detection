## Task
- Spec: `docs/tasks/TNN-....md`
- Closes task: TNN

## What changed (1-3 bullets)
-

## Tests run (paste the last lines)
```
$ make task T=TNN
...
$ make check
...
```

## Invariants checklist
- [ ] Only files listed in the spec were changed
- [ ] No band is set outside `src/satyapan/policy/`; nothing lowers a band
- [ ] No network imports outside `src/satyapan/adapters/`; tests use fakes
- [ ] No contracts / invariant tests / harness tests edited
- [ ] No secrets, real bank details, real media or dataset text added
- [ ] Makers still never see raw scores
- [ ] `docs/STATUS.md` updated

## Screenshots (UI tasks)

## Agent used
(opencode + model / Gemini CLI / Copilot / Claude Code)
