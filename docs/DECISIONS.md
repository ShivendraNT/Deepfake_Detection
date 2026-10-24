# Decision log (ADRs)

Each entry: decision, why, and which critique flaw (`critique.md` #N) it answers. Add new ADRs at
the bottom; never rewrite old ones (supersede them instead).

### ADR-001 One user, one surface
**Decision:** primary user = SME accounts-payable maker + checker. Surface = web console + Chrome
extension side panel for Meet/Teams **in the browser**. Citizen page is a thin stretch (T24).
**Why:** corporate controls (vendor master, maker-checker, on-file numbers) exist only here;
browser tabs are capturable (`chrome.tabCapture`), phone calls are not. **Flaws:** #1, #5, #14.

### ADR-002 The payment sets the floor; detectors decide WHO verifies
**Decision:** a deterministic floor from transaction vs vendor master; signals only raise. A
detector hit moves VERIFY → HOLD (checker verifies, record frozen, security notified).
**Why:** a perfect deepfake or injection cannot lower the bar; in Arup the deceived employee was
the verifier. The floor is product policy, not a research finding (H2 of v2 dropped).
**Flaws:** #2, #26.

### ADR-003 Monotone escalation lattice instead of learned fusion / LLR
**Decision:** per-signal target bands + "≥ 2 independent strong groups → HOLD".
**Why:** no joint multimodal labelled data exists; at real base rates the floor dominates anyway.
**Flaw:** #7.

### ADR-004 LLM and style signals: raise-only, capped at VERIFY, never "strong"
**Decision:** any signal with `source == llm` or `group == style` is capped at VERIFY and does
NOT count toward the strong-group rule. The LLM never sets the band and gets no tools.
**Why / deviation:** the v3 pseudo-code excluded only `group == style` from the strong-group count,
so two LLM-sourced "strong" signals could have reached HOLD — violating the invariant "no
LLM-only path reaches HOLD". We exclude LLM-sourced signals too (`policy/targets.py`), and the
contract forbids LLM sources on deterministic codes. **Flaw:** #8.

### ADR-005 No Black band, no auto-reporting, UTR-first pack
**Decision:** CONFIRMED_FRAUD is a status set only by checker/security. Reports are drafts
(`submission = "MANUAL_ONLY"`), led by UTR, amount, time, accounts. No 1930/NCRP integration is
claimed. No peer hash sharing. **Flaws:** #9, #10.

### ADR-006 Money is whole rupees (`int`)
**Decision:** `amount_inr: int`. **Why:** beginners + JSON + TypeScript; paise do not matter for
policy thresholds. Bank/UTR facts in reports are copied from the bank, not computed.

### ADR-007 OOB-Confirm instead of an external Signed Payment Request
**Decision:** external SPR → future-work slide. Internal OOB-Confirm to the claimed requester's
directory identity; token single-use, 10 min, bound to SHA-256(case ‖ amount ‖ beneficiary ‖
nonce); responder must be logged in as the requester. Rekognition Liveness removed.
**Flaws:** #11, #12.

### ADR-008 Research = "Ask, Not Style" on public data
**Decision:** one claim tested on ICFD-31k + external Hinglish sets with pre-registered splits,
thresholds on validation, paired bootstrap CIs. FinFake-IN dropped as a benchmark (kept only as
the "illustrative, n=12" fixtures). **Flaws:** #3, #6, #23, #27.

### ADR-009 Voice detector = Pascu et al. XLS-R-L7 ONNX, license risk acknowledged
**Decision:** use on-device in the extension + same model in Python for uploads; files not
committed (no license); email authors Day 1. Backup: server-side scoring with a permissively
licensed SSL detector (verify license), privacy line changes to "scored on the local backend".
**Flaws:** #21, #25 (no visual detector).

### ADR-010 Contracts first; the signal table is data
**Decision:** all shared models in `src/satyapan/contracts/` (Pydantic v2, `extra="forbid"`),
JSON Schemas exported to `schemas/`, signal semantics in `SIGNAL_TABLE` and enforced by the
`Signal` validator; build signals only with `Signal.make`. Enum values are stable strings.
**Why:** three beginners on free agents work in parallel; divergence is the main failure mode.

### ADR-011 Four AWS services, each with a local fallback
**Decision:** S3 Object Lock, Bedrock (Haiku 4.5 via `in.` profile), Transcribe (hi-IN/en-IN),
SES — ap-south-1 only, 5 s timeouts, AWS mode off by default. Not Textract (no Hindi),
not Rekognition, not Connect. **Flaws:** #19, #22.

### ADR-012 Lean agent harness
**Decision:** one canonical `AGENTS.md`; thin pointers for Claude/Gemini/Copilot. Core opencode
agents: `implementer` + `reviewer`; `planner`, `tester`, `researcher-eval`, `docs-pitch` are
optional helpers. Review by acceptance test; leader reviews only policy, vault, extension capture.
**Flaw:** #24.

### ADR-013 Vault claims limited to integrity since capture
**Decision:** SHA-256 at intake, hash-chained custody, head anchored to S3 Object Lock; BSA Sec 63
"helper" template only (signed by the company's custodian, reviewed by counsel). TSA is future
work. **Flaw:** #15.

### ADR-014 Role-based output coarsening
**Decision:** makers see band + reason codes; checker/security see scores; citizen page sees band +
action. **Flaw:** #13.

### ADR-015 Grey is a flag, not a band
**Decision:** grey reasons (parse failure, detector error, < 3 s speech, unsupported language,
conflicting data, no trusted auth header) force ≥ VERIFY + checker queue. Abstention rate is
reported. OOD detection dropped. **Flaw:** #20.

### ADR-016 Credential/OTP ask → HOLD (resolves an inconsistency in v3)
**Decision:** follow the v3 signal table (A2/A3 → HOLD), not the R2 prose ("credential ask →
VERIFY"). **Why:** an OTP/password request in a payment context is never routine; the signal
table is the more specific and later statement.

### ADR-017 Pre-implement the deterministic core
**Decision:** T01, T02, vault hashing + custody chain, voice window rules (Python + JS mirror),
the LLM prompt builder, and the evidence pipeline are implemented and tested before the team
starts. **Why:** everything depends on them; mid-level agents should never improvise safety code.

### ADR-018 Bank-claim rule uses display name + domain, not subject
**Decision:** `claims_to_be_bank(display_name, domain)` with whole-token matching.
**Why:** vendors routinely write "updated bank details" in subjects; that is A7 (ask extractor), not
a bank impersonation.

### ADR-019 No trusted Authentication-Results → GREY
**Decision:** if our own MTA's header is missing, the email gets `PARSE_FAILURE` grey (≥ VERIFY).
**Why:** we cannot evaluate sender auth; failing open would let header stripping lower scrutiny.

### ADR-020 Local LLM (Ollama) instead of Bedrock — supersedes the Bedrock part of ADR-011
**Decision:** the optional case summary (T15) runs on a local model through Ollama
(`llama3.1:8b` by default, `SATYAPAN_LLM_MODEL`), via `adapters/ollama_llm.py`. Bedrock is dropped.
**Why:** no paid services for the hackathon; also no prompt or evidence excerpt leaves the laptop.
The safety design is unchanged: no tools, constant system prompt, band never from the LLM, and the
faithfulness checker gates every summary (templates are the fallback). Cost: slower (~10-25 s per
summary on the M4), so it stays out of the live-call loop as before.

### ADR-021 Context layer before asks + no HOLD from one uncorroborated ask (policy 1.1.0)
**Context (judge panel, R1 report §2 and §4.1):** on the real engine, a standard "This e-mail is
confidential" footer turned a routine known-vendor payment (floor PASS) into **HOLD**, and so did a
forwarded bank SMS ("482913 is your OTP … do not share"). We measured it: on 400 synthetic
routine payments with realistic AP messages, policy 1.0.0 escalated 39.5% and held 31.8%
(`results/alert_budget.md`). The frozen lexicon also fires on 21.5% of benign AP texts
(`results/asks_heldout_eval.json`). The brief says: avoid automatic blocking based on a single
weak signal.
**Decision:** (1) A leader-owned pre-filter `src/satyapan/context/boilerplate.py` removes, and
labels in `DetectorOutput.artifacts["context"]`, e-mail disclaimers, quoted bank/system
notifications and protective warnings ("never share your OTP", "share mat karna", "साझा न करें")
before the frozen ask extractor runs (pipeline text/email/PDF paths and the live path). It never
removes a sentence that asks for something to be sent to the requester, contains money-movement
content, or has an un-negated action verb. The lexicon (T05, v1.0) is untouched. (2) In
`escalate()`, an ask signal that is not corroborated is capped at VERIFY. Corroboration = a
second distinct ask type, or a raising signal from another group that is not LLM/style, or a
risky floor action (N1, N2, C1, K2, T1, D1). `PolicyConfig.ask_corroboration=False` restores
1.0.0 (used only to reproduce before/after numbers).
**Why it is safe:** raise-only and monotone still hold (corroboration can only be gained by
adding signals; property test `tests/invariants/test_single_weak_signal.py`); LLM/style signals
never corroborate; the floor is unchanged, so payee changes and new payees above the de-minimis
still need verification whatever the text says. **Cost, stated honestly:** a single real
credential/remote-access ask during a routine K1 payment or a live call now gets VERIFY (maker
callback + side-panel warning) instead of HOLD; attack HOLD rate changes are reported in
`results/alert_budget.md`. The pre-filter is a new evasion surface (an ask phrased like a
disclaimer); `results/redteam_deterministic.json` measures it. The 1.0.0 T02 unit test that
used "one credential keyword on a K1 payment" to reach HOLD now reaches HOLD with a corroborated
ask; its assertions (checker queue, checker-only clearance) are unchanged.

### ADR-022 30-day cumulative de-minimis for new beneficiaries (judge finding b5)
**Decision:** the floor's N1/N2 test uses today's amount plus what the same new payee (account +
IFSC, or UPI ID) already received in the last `de_minimis_window_days` (30) days, from
`MasterData.new_payee_payments` (`contracts.OutgoingPayment`: the payer's own bank statement /
ERP payment register, trusted). `compute_floor`'s signature is unchanged (the data comes in
through `master`). **Why:** 10 × ₹24,999 to a new payee was 10 × PASS. **Assumption:** the
register feed exists (ERP/bank-statement export); without it the rule degrades to the old
per-payment test. **Not done here:** vendor onboarding (first phone/bank record of a new vendor)
is still the trust root and is assumed to be verified out of band (GSTIN lookup, penny drop,
callback number from GST/MCA records), see THREAT_MODEL.


### ADR-023 Satyapan Seal: authenticate the real executive (Voice Seal + Intent Seal)
**Decision:** add component C14 (`src/satyapan/seal/`, docs/SEAL.md). An enrolled executive's
client hides a keyed ±2 dB, 12-band level pattern in outgoing speech; keys come from a
passkey-committed TESLA hash chain, bound to the meeting id and 5 s epoch, disclosed only after
each epoch. The same passkey signs SHA-256 of the exact payment intent (Intent Seal). Three
provenance codes join the signal table: `VOICE_SEALED` (NONE, info only), `VOICE_UNSEALED_CLAIMED_EXEC`
(weak, VERIFY), `SEAL_PRESENCE_CONFLICT` (strong, HOLD if money else VERIFY); all deterministic.
The receiver protocol acquires the offset once (Bonferroni) and then scores at a fixed offset;
later looks use alpha spending. Never re-maximise the lag per epoch (the lab's v1 did and got 1
false seal in 560 sessions).
**Why:** detectors decay as generators improve (DF26); a seal's false-alarm rate is fixed by
statistics (H0 z ~ N(0,1), measured mean +0.04 / std 1.03 over 3,920 attack epochs) and its
security by cryptography, for every voice and language. It turns "detect the fake" into "prove the
real" without biometrics. **Limits (stated, not hidden):** a compromised exec laptop, browser
malware against the WebAuthn prompt (no transaction display), offline uploads cannot prove
timing, and Google Meet's own processing is untested until the two-laptop test.
**Safety:** a seal never lowers a band or clears a HOLD; "not sealed" is never shown as "fake".

**Interaction with ADR-021 (merge, 08 Oct):** `VOICE_UNSEALED_CLAIMED_EXEC` is a deterministic signal from a non-ask group, so under policy 1.1 it corroborates a single ask. "Skip the approval" (A5) + a claimed CFO whose voice is not sealed therefore reaches HOLD (checker verifies), while unsealed alone stays at VERIFY. Property test: `tests/seal/test_seal_policy.py::test_unsealed_raises_to_at_most_verify`.

### ADR-024 Live calls: local speech, a live-only phrasebook, cues that never score (finale)
**Decision:** live calls are transcribed on the laptop (`adapters/transcribe_local.py`:
mlx-whisper on Apple Silicon, faster-whisper int8 elsewhere; `make asr`), one utterance at a time
(the capture window cuts at pauses, ~0.5 s, instead of fixed 10 s chunks). Spoken asks go through
the frozen lexicon v1.0 **plus** `asks/phrasebook.py` (`live-1.1.0`): spoken variants the written
lexicon misses ("don't involve Rajesh", "read me the code", "I'll sign later", Hinglish; v1.1 adds
"add a new payee", "the account mentioned in my message", "give me access to your desktop",
"screen sharing on karo" — added only after inspecting miss cases on the **dev** split, then
re-scored once on test; both numbers are in `results/asks_heldout_eval.json`). The
phrasebook is product-only: research scripts keep calling `extract_asks` and never see it, so the
frozen research lexicon and its numbers are unchanged. The ADR-021 context filter runs first.
Context **cues** (RUSH, AUTHORITY, UNREACHABLE, AMOUNT) are highlighted for the user but are never a
`Signal` and never change a band. A missing speech engine is a visible status ("my ears aren't
installed"), never an empty transcript; a lost engine mid-call fails closed (Satya sleeps).
**Privacy:** captions travel only on the per-call `/live/{id}/events` stream to the desktop main
process and live in memory for that call; the companion bus (which has replayable history) never
carries transcript text, only ask quotes the user needs to see why Satya paused.
**Why:** judges must see a real call flagged live; a deaf demo that silently "listens" is worse
than no demo. Local ASR keeps call audio on the laptop.

### ADR-025 Video deepfake check: real-faces-only blend CNN + physiological cues, raise-only (finale)
**Decision:** during a call the user said yes to (and only with the `video` consent scope), the
capture window keeps the screen video track and posts ~15 downscaled JPEG frames/s to the local
engine; `src/satyapan/video/` tracks the largest face (MediaPipe Face Landmarker, 478 points) and
scores 6 s windows (3 s hop) from four cues: a blend-artifact CNN (EfficientNet-B0) trained only on
**real** faces with self-blended pseudo-fakes (SBI, Shiohara & Yamasaki 2022), rPPG pulse
coherence (POS), region lighting/colour/specular consistency and lip-sync. A logistic fusion is
fitted with identity-grouped 5-fold CV on FF++ train; thresholds come from FF++ val reals only
(1% / 5% window FPR). Two consecutive windows over tau_hi -> `VIDEO_LIKELY_SYNTHETIC` (media
group, ML, PLUS_ONE: one band above the floor, never HOLD on its own); `VIDEO_NO_SIGNS` and
`VIDEO_INCONCLUSIVE` are informational (NONE). No usable face (camera off, face < 64 px, too dark)
is an abstention, never a grey flag. Makers see labels, never scores.
**Privacy:** frames live in RAM for one window and are dropped; nothing is written to disk;
127.0.0.1 only. Video files handed to Satya go through the vault like any evidence.
**Why:** the brief asks for deepfake detection, and a live video CFO is the T-1 threat. Training on
real faces only means no deepfake method is "seen", which is the honest way to claim
generalisation; the transaction floor and OOB-Confirm still carry the decision when the face
check is wrong (docs/VIDEO_DEEPFAKE.md has the measured numbers and what we do not claim).


### ADR-026 GenD (CLIP ViT-L/14, MIT) replaces our SBI CNN as the face CNN; SBI is the fallback (finale)
**Decision:** the crop CNN of ADR-025 is now GenD (Yermakov et al., WACV 2026,
`yermandy/GenD_CLIP_L_14`, MIT), exported to one fp32 ONNX file (`research/video/export_gend.py`,
matches PyTorch to < 1e-5). It scores one face crop every 2.25 s, each crop once; its fusion is
the identity on the mean crop logit and its thresholds are the same 1 % / 5 % window FPR on FF++
val reals, max over the three channel conditions (`config/video_fusion.json`,
`config/video_thresholds.json`). Our SBI CNN keeps its own config (`config/video_*__blend.json`)
and is used automatically when the GenD file is not on the laptop; a CNN never runs with
another CNN's thresholds.
**How it was chosen:** five Hugging Face detectors and our CNN were scored on the same stored
crops under one protocol; the selection rule (eligible = redistributable licence + documented
training split disjoint from our val/test + exact ONNX export; replace only if the call360 val
AUC gain exceeds one bootstrap SE) was committed before any of them was scored
(`docs/VIDEO_DEEPFAKE.md` §5b). Result on val only: +0.183 AUC (SE 0.023) → GenD
(`results/video_selection.json`, recorded before any GenD test metric existed).
**Why not int8:** dynamic int8 quantisation changed GenD's logits (r = 0.92 vs fp32), so it would
not be the model we benchmarked. **Cost:** 1.2 GB on disk; about one ViT-L forward pass per 2 s
of call on a laptop CPU. **Not changed:** raise-only, PLUS_ONE cap, labels not scores for makers,
consent and RAM-only frames (ADR-025).
