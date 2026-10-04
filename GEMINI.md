# Gemini CLI context

@./AGENTS.md

## Gemini CLI notes
- Follow AGENTS.md exactly; it is the single source of truth for this repo.
- Custom commands for this repo live in `.gemini/commands/` — use `/task T07`, `/check`, `/review`.
- Gemini CLI asks before running shell commands. Approve `make task ...` and `make check`;
  never approve `git push`, `rm -rf`, `curl` to unknown hosts, or package installs you did not plan.
- Free-tier prompts may be used for training: never paste real media, voices, bank details or `.env`.
