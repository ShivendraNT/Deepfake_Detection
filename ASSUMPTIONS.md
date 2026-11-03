# ASSUMPTIONS.md — Engineering Assumptions & Design Decisions

Per Hard Rule 7, engineering assumptions are recorded here rather than blocking execution.

1. **Coexistence with Existing Satyapan Invariants (`make check`)**:
   - All existing Satyapan modules (`contracts/`, `policy/`, `vault/`, `video/`, `voice/`, `imagecheck/`, `textrisk/`, `api/`, etc.) and all 884 existing tests + 7 safety invariant suites remain untouched and 100% green.
   - New forensic laboratory capabilities are organised cleanly under `src/satyapan/forensics/` and exposed via `src/satyapan/api/routes_forensics.py` (`/forensics` and `/api/forensics/*`), while reusing `src/satyapan/video/`, `src/satyapan/voice/`, `src/satyapan/imagecheck/`, `src/satyapan/document/`, and attributed modules from `~/Desktop/igdtu/pramaan/`.
   - Every new Python module under `src/satyapan/` is registered in `docs/ARCHITECTURE.md`'s module map to satisfy `tests/harness/test_docs_consistency.py::test_every_python_module_is_in_the_module_map`.
   - No module under `src/satyapan/` (outside `adapters/`) imports `socket` or any network library listed in `tests/invariants/test_network_boundary.py`; host identification in `forensics/locker.py` uses `platform.node()` instead of `socket.gethostname()`.

2. **Media Files in Repository (`test_no_media_files_in_repo`)**:
   - `tests/contracts/test_fixtures.py::test_no_media_files_in_repo` prohibits `.wav`, `.mp3`, `.ogg`, `.opus`, `.m4a`, `.mp4`, `.webm`, `.flac` inside `data/`, `extension/`, `research/`, `docs/`, `results/`, `console/src/`, `console/public/`.
   - Therefore, our committed open/synthetic forensic demo kit lives in `demo_kit/` at the repository root (which contains small deterministic images, PDFs, audio, video, and a manifest, well under a few megabytes total) and can also be regenerated deterministically offline via `scripts/make_forensic_demo_kit.py`.

3. **RNG Provenance Rule (`test_results_provenance.py`)**:
   - Any script in `research/` or `scripts/` that writes to `results/` and uses `random` or `numpy.random` must include `# provenance: seeded-resampling-ok` on the import line and exclusively instantiate `random.Random(SEED)` or `np.random.default_rng(SEED)`.

4. **Non-Absolutist Forensic Reporting (Hard Rule 6)**:
   - No forensic module or report ever outputs `"FAKE"`, `"GUILTY"`, or `"100% CERTAIN"`.
   - All findings use standardized forensic terminology:
     - `"consistent_with_manipulation"` ("Findings are consistent with digital manipulation or synthetic generation")
     - `"anomalies_detected_verify"` ("Forensic anomalies detected; manual expert examination recommended")
     - `"consistent_with_authentic"` ("No strong manipulation indicators detected; consistent with authentic capture within stated detector limits")
     - `"inconclusive_abstain"` ("Insufficient signal or unsupported condition; detector abstained")
   - Every finding carries a calibrated confidence score in `[0.0, 1.0]`, supporting evidence metrics, visual artifacts (heatmaps/spectrograms), and explicit methodological limitations.

5. **Offline PDF Generation**:
   - Because `reportlab` is not installed in the base offline `.venv`, `src/satyapan/forensics/report.py` implements a self-contained PDF 1.4 generator using Pillow + standard library `zlib` that embeds formatted text pages AND high-resolution forensic heatmap/spectrogram images into a single valid multi-page PDF, with optional `reportlab` acceleration if installed.
