# Module handbooks (read before defending the project)

One page per module: what it does, the core idea, the five hardest questions a judge could ask with
our answers, and its weaknesses. Read in this order.

| # | Handbook | Module |
|---|---|---|
| 1 | [locker.md](locker.md) | `src/satyapan/forensics/locker.py` — intake, working copies, custody, Merkle |
| 2 | [deepfake.md](deepfake.md) | `src/satyapan/forensics/deepfake.py` — synthetic media detection |
| 3 | [tampering.md](tampering.md) | `src/satyapan/forensics/tamper.py` — ELA, double-JPEG, copy-move, noise, video, audio |
| 4 | [provenance.md](provenance.md) | `src/satyapan/forensics/provenance.py` — metadata, C2PA, attribution |
| 5 | [dashboard.md](dashboard.md) | `src/satyapan/forensics/pipeline.py` + `src/satyapan/api/routes_forensics.py` |
| 6 | [report_section63.md](report_section63.md) | `src/satyapan/forensics/report.py` + `section63.py` |

Cross-reference: `docs/LIMITS.md` for failure cases, `docs/JUDGES.md` §PS for the deliverable map,
`results/EVIDENCE_LEDGER.md` §§15–16 for the numbers, `BLOCKERS.md` for what could not be executed
here (Docker daemon, third-party C2PA COSE chain).
