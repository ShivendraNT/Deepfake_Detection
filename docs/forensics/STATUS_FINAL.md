# Final status — SUTRAM 2026, Problem Statement 2

Branch `claude/peaceful-babbage-cv9arb`, 8 November 2026. Every number below is reproducible
with the command printed next to it; the raw benchmark rows are in
`results/forensics_demo_benchmark.{md,json}`.

## What was done

- **Face-swap inference is calibrated to SFace's published operating point.** Two videos with
  the same footage are called a face replacement only when the **median** SFace cosine over
  index-matched key frames is below **0.363** (OpenCV's same-identity point), or when one
  video's face matches a third exhibit far better than the other's does. A face source is
  accepted only if a `SAME_FACE` link exists, its median cosine to the altered face is
  ≥ 0.45, its median cosine to the other video is < 0.363, and it beats the two videos' own
  median by ≥ 0.25. The finding text names all three cosines and the 0.363 reference point.
  This replaces the old max-pair rule, which treated a single lucky frame pair as identity.
- **The case-level pass is safe under concurrency.** `apply_case_inferences` now checks an
  exhibit's status and writes its new analysis under one store lock, so a re-queued exhibit is
  never put back to DONE with a stale verdict; the queue set is also locked. Tests cover two
  workers finishing together, idempotent re-runs, custody rows and a re-queued exhibit.
- **Inference input is defensive.** Missing feature maps, malformed embeddings, missing paths
  and an unwritable artifact directory are a missing comparison, not a crash; `matched_frames`
  scales its search window when the two videos have very different frame counts.
- **Dashboard.** The generic evidence view already rendered any finding code; a small
  `case.compare` view now summarises weighted findings, context notes and codes. The built
  copy under `src/satyapan/forensics/ui` was rebuilt and committed.
- **Report and docs.** The demo PDF was regenerated and checked; METHODOLOGY and VALIDATION
  now describe the median rule and the measured demo cosines.

## Measured results

| Check | Command | Result |
|---|---|---|
| Investigation dataset | `make lab-benchmark` | 11 exhibits, **9 correct, 0 false alarms**, 2 missed, 0 flagged-but-not-conclusive; 50 s |
| Face-swap demo (Q5) | inside the benchmark | median SFace **0.36** (< 0.363), source **0.80**, source-vs-original **0.19**, frame difference **4.4×** on the face → *strong* FACE_REPLACED |
| Copy of a synthetic picture (Q2) | inside the benchmark | classifier strict hit + `COPY_OF_SYNTHETIC` (Q7) → SYNTHETIC |
| Full checks | `make check` | **963 passed, 17 skipped** (the documented T18/T20–T23 task tests); ruff, format and mypy green |
| Dashboard | `cd lab && npm run build && npx vitest run` | build clean; **53 tests passed** |
| Report | `generate_report` on the demo case | 46 pages, “Page x of 46” footers; Part B hashes and designation filled; no `no_signs`; device line **“Android 13 phone”** |

The two misses are the open-source TTS voice notes (Q3 and Q4), the documented blind spot in
VALIDATION §“Open-TTS voice head”. The seizing of the original clip and the profile photo is
what turns Q5 from a weak face-model cue into *strong* support; without those exhibits the
same file would stay inconclusive.

## Known limits

1. **Open-source neural TTS is missed.** Piper voice notes score below the strict threshold;
   the open-TTS head reached 49.3 % detection against its pre-registered ≥ 50 % ship rule, so
   it contributes nothing. The report says *no indications*, never *authentic*.
2. **Modern online face swaps are often below the face model's strict threshold.** They are
   caught when the case also holds the original footage (or a face source) and the comparison
   can name both; on its own, a modern swap gets a weak or moderate indication only.
3. **Cross-exhibit findings need both exhibits in the same case.** Nothing is compared across
   unrelated cases, and an original that was not seized cannot be recovered by comparison.
4. **Copy-move remains indicative.** A newly re-rendered document with repeated text can
   produce a compact one-line cluster; the committed demo template does not, but an examiner
   should read the overlay. This is why copy-move is capped at moderate unless a structural
   finding corroborates it.
5. **Models and demo media are not in git.** Rebuild them with `make lab-setup`,
   `make forensics-models`, `make voice` and `make demo-dataset`. The gustking XLS-R model is
   1.2 GB and is exported locally from its pinned Hugging Face revision.
