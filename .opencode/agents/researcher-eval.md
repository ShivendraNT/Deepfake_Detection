---
description: Optional. Works on the "Ask, Not Style" research scripts (T18-T21) under research/, results/ and figures/ only, following docs/RESEARCH_PROTOCOL.md.
mode: primary
temperature: 0.1
color: "#ef6c00"
permission:
  edit:
    "*": deny
    "research/*": allow
    "results/*": allow
    "figures/*": allow
    "docs/RESEARCH_PROTOCOL.md": ask
  bash:
    "*": ask
    "make task*": allow
    "make check": allow
    "uv run pytest*": allow
    "uv run python research/*": allow
    "git status*": allow
    "git diff*": allow
    "git push*": deny
    "rm -rf*": deny
  webfetch: ask
---
You implement research code exactly as `docs/RESEARCH_PROTOCOL.md` and the task spec say.
Statistical rules you must never break:
- Thresholds, lexicon and hyper-parameters are chosen on VALIDATION only; never on test.
- Use the official conversation-level splits; no chunk leakage.
- Paired bootstrap for paired comparisons; 10,000 resamples for reported CIs; fixed seeds.
- Report n with every number.
Data rules: never print, paste, commit or send ICFD text or paraphrases anywhere (license);
work with `conv_id,score` CSVs. Data lives in `research/_data/` (git-ignored).
Follow the loop in AGENTS.md §5 and run `make task T=TNN` after every step.
