# Contributing

## Branches
- One branch per task: `tNN-short-name` (e.g. `t05-ask-extractor`). Never commit to `main` directly.
- Keep branches short-lived (< 1 day). Rebase on `main` before opening the PR: `git pull --rebase origin main`.

## The loop
Follow `docs/harness/WORKFLOW.md`: spec → plan → red test → small steps → `make task T=TNN` →
`make check` → update `docs/STATUS.md` → commit → PR.

## Commits
`TNN: <imperative summary>` — e.g. `T08: extract IFSC/account/UPI from invoice text`.

## Pull requests
- Use the PR template (`.github/pull_request_template.md`).
- **Merge rule:** `make task T=TNN` and `make check` green → merge. Review is by acceptance test.
- The leader reads diffs line-by-line only for `src/satyapan/policy/`, `src/satyapan/vault/` and
  extension capture code (`extension/offscreen.js`, `extension/service_worker.js`).
- Ask the `reviewer` agent (`@reviewer` in opencode, or `/review`) before requesting a human.

## Never
- Edit `src/satyapan/contracts/`, `src/satyapan/policy/`, `tests/invariants/`, `tests/harness/`,
  `tests/conftest.py` without the leader.
- Delete, skip or loosen tests. Commit media, real data, `.env`, `.onnx` files, dataset text.
- `git push --force` on `main`.

## Without uv (pip fallback)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest hypothesis httpx ruff mypy numpy
make check RUN=
```
