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
