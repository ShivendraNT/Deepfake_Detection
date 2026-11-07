# Deployment roadmap for law-enforcement agencies

Satyapan Forensic Lab is built to run where evidence already lives: on an examiner's
workstation inside a cyber cell or a State / Central Forensic Science Laboratory, with no
dependency on cloud services. This roadmap takes it from the hackathon prototype to a tool an
FSL can use in casework and defend in court.

## 1. Who uses it, for what

| User | Typical question | Satyapan feature |
|---|---|---|
| Investigating officer, cyber police station | "Is this video of the 'officer' / this voice note of the 'son' real? What do I put in the case diary today?" | Drop files → verdict in minutes; triage list; links between exhibits; draft report for the FSL forwarding letter |
| District / state cyber cell analyst | "Which of the 2,000 media files on this seized phone matter?" | Batch examination (`make examine`), verdict + risk sorting, near-duplicate grouping, platform and generator attribution |
| FSL scientific officer (examiner of electronic evidence) | "Can I give an opinion on authenticity that survives cross-examination?" | Write-once evidence, custody chain, method references, known error rates, ENFSI-worded conclusions, BSA s.63 Part B draft |
| Prosecutor / court | "What exactly was found, and how reliable is it?" | Plain-language report with figures, what was not checked, limitations |
| I4C / NCRP analysts | "Is this synthetic-media modus operandi spreading?" | Exportable JSON per case: generator, platform, fraud-language and voice-clone patterns |

## 2. Deployment models

| Model | Hardware (per seat) | Notes |
|---|---|---|
| **Air-gapped FSL workstation** (recommended) | 8–16 CPU cores, 32 GB RAM, 1 TB SSD; GPU optional | Models installed once from a verified offline bundle (hashes pinned in `config/`); evidence and reports never leave the machine |
| Cyber-cell server (LAN) | 16–32 cores, 64 GB RAM, RAID storage, optional NVIDIA GPU | Dashboard served on the cell's LAN; role-based login added (examiner / IO / supervisor); nightly encrypted backup of `lab_data/` |
| State FSL cluster | Kubernetes or VM pool + object store with WORM retention | Analysis workers scale horizontally (the engine is stateless per exhibit); custody chain head anchored daily to WORM storage (`satyapan.vault.anchor`) |
| Field triage laptop | 8 cores, 16 GB RAM (measured: all models fit) | Same software; first look at a seized phone's media at the spot, hashes recorded before transport |

Measured on a 4-core CPU without GPU: an image takes 1–8 s, a 20-s voice note 10–25 s
(transcription included), a 10-s video 15–40 s. A GPU makes the face, voice and transcription
models 5–20× faster.

## 3. Phased plan

| Phase | Duration | Scope | Exit criteria |
|---|---|---|---|
| 0. Hackathon prototype (now) | done | 22 techniques, dashboard, reports, custody, dataset | Working demo on a realistic case; measured error rates published |
| 1. Pilot in one cyber cell + one FSL | 3 months | Install on 2–3 workstations; examiners run it in parallel with their current workflow on closed cases; collect disagreements | ≥ 300 exhibits examined; false-alarm rate on genuine casework ≤ 2 %; examiner feedback incorporated |
| 2. Validation for court use | 3–4 months | Re-fit thresholds on Indian casework media (WhatsApp/Telegram re-encodes, Indian languages, local phone models); blind proficiency tests; write the lab's validation file per ISO/IEC 17025 7.2; peer review of methods | Validation report signed by the lab; error rates per technique on Indian data; SOP approved |
| 3. Accreditation & notification | 6 months (parallel) | NABL ISO/IEC 17025 scope extension for "multimedia authentication"; supporting the lab's notification as an *Examiner of Electronic Evidence* under IT Act s.79A (MeitY) | Accredited scope; s.79A notification dossier |
| 4. State-wide roll-out | 6–12 months | Server deployments in state cyber HQ; integration with CCTNS / ICJS case numbers; training of 1 trainer per district | All districts can request examinations through the cell; turnaround SLA met |
| 5. Continuous improvement | ongoing | Quarterly model refresh against new generators (each through the pre-registered selection protocol); new technique modules: a learned splice/inpainting localiser (e.g. TruFor, CVPR 2023 — research-licensed, to be integrated after a code review in the lab), PRNU camera matching, AI-video (Sora/Veo-class) detection, document forgery | Benchmarks re-run and published each release |

## 4. Integration points

* **Case identity** — FIR number, police station and sections are case fields today; a CCTNS
  connector would pre-fill them and attach the report PDF to the case record.
* **NCRP / 1930 / I4C** — Satyapan never submits anything itself (no submit endpoint exists,
  enforced by `tests/invariants/test_no_auto_reporting.py`); it exports a structured JSON
  that I4C analysts can ingest for modus-operandi tracking.
* **Forensic suites** — exhibits can arrive as files exported from mobile-extraction tools;
  the JSON export and PDF go back into the lab's existing case-management system.
* **Content Credentials** — as Indian platforms and newsrooms adopt C2PA, the trust list of
  signers is configured per lab, turning "trust not established" into verified provenance.

## 5. Governance, privacy and safety

* **DPDP Act 2023**: evidence processed for investigation under legal authority; no copies
  outside the lab; retention per court orders; reports contain hashes, not raw personal data.
* **Human in the loop**: verdicts are opinions supporting an examiner; the examiner signs.
  The rule table is fixed and documented; no model can override it.
* **Known limits stated in every report**: new generators, heavy compression, noisy audio.
  A "no indications" result is never presented as proof of authenticity.
* **Supply chain**: every model file is pinned by SHA-256; model updates go through the
  selection protocol and change control; the offline bundle is signed.
* **Bias checks**: false-alarm rates reported separately for Hindi and English speech and
  across skin tones / camera types as Indian validation data grows.

## 6. Indicative cost (per FSL, first year)

| Item | Estimate |
|---|---|
| 5 examiner workstations (CPU, 32 GB) | ₹ 7.5 lakh |
| Optional GPU server for batch work | ₹ 8–12 lakh |
| Pilot support, validation study, training (2 engineers × 6 months) | ₹ 18 lakh |
| Accreditation scope extension and proficiency tests | ₹ 3–5 lakh |
| **Software licence** | none — the code is ours; third-party models are MIT / Apache-2.0 / CC BY, except the face-model training data terms noted in THIRD_PARTY.md |

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| New generator evades the detectors | Several independent techniques per verdict (metadata, provenance, signal, model); quarterly re-selection; "no indications" never means authentic |
| Over-reliance on a verdict | ENFSI wording, explicit "not checked" list, figures for the examiner to verify, mandatory human signature |
| Courts question an AI method | Published methods with references, known error rates, deterministic rule table, reproducible runs (same input → same result), full custody chain |
| Adversarial use of the tool to tune fakes | Deployed only inside LEA networks; no public endpoint |
