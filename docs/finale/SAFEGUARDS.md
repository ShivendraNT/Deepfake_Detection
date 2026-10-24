# Safeguards — running, not described

> For the judge question: *“The alert is nice, but what stops this from becoming a surveillance
> tool or an auto-filing robot?”* Every row below names the code path, the test that proves it,
> and what you can see on stage.

---

## 1. Consent, per call, never the microphone

| Safeguard | How it is enforced | Proof |
|---|---|---|
| Satya starts **asleep** | `UserMode` defaults to `SLEEPING`; `AppState` starts in `SLEEP`; the mascot shows Zz | `scripts/dry_run.py` step 1 asserts `default_mode == "SLEEP"`; `tests/finale/test_live_finale.py` |
| Nothing is captured before a visible **consent card** | `POST /companion/session/start` requires `consent=True`; the desktop only starts watchers after the user accepts | `tests/finale/test_companion_finale.py::test_calls_start_is_rejected_without_a_consented_session`; `desktop/tests/*` |
| **Per-call yes** | the `call_ask` bubble card; “Not this one” ignores hints for 30 min; `startCall` only after the click | `desktop/renderer/src/companion/useSatya.ts`, `desktop/main/index.ts` |
| **Never the microphone** | capture is system/output audio (loopback or Chrome tab capture); there is no mic path in `capture.ts` | `desktop/main/capture.ts`, `src/satyapan/api/routes_live.py`; code review |
| **Hide / Off / Quit stop the session first** | `hideCompanion()`/`quit()` call `setUserMode('SLEEPING')` and `stopSession()` before hiding/exiting | `desktop/main/index.ts`; T25 tests |
| Any capture error → **Sleeping** | a `capture` status with `error` sets the mode to SLEEPING and shows a notice | `desktop/renderer/src/companion/satyaMachine.ts`; `tests/finale/test_live_finale.py` |
| **Emergency stop** | `Ctrl/⌘+Shift+.` stops listening and reading from any state | `desktop/main/index.ts::emergencyStop` |

**What a judge can see live:** start the app → Satya is asleep; click Watch → the consent card
appears; accept → he wakes. Press `Ctrl/⌘+Shift+.` during a call → he sleeps immediately.

---

## 2. Local processing and data minimisation

| Safeguard | How it is enforced | Proof |
|---|---|---|
| Everything runs on the laptop | FastAPI binds `127.0.0.1`; the desktop talks only to it; speech, OCR, face check and policy are local | `desktop/renderer/src/shared/api.ts`, `desktop/main/backend.ts`, `src/satyapan/settings.py` |
| No call audio leaves the laptop | local Whisper; audio chunks go to the local API only; no upload adapter in the live path | `src/satyapan/adapters/transcribe_local.py`, `src/satyapan/live/` |
| Captions are memory-only | the live bus keeps captions for the call; the companion bus never carries transcript text | `tests/finale/test_companion_finale.py::test_live_chips_accumulate...` asserts the transcript is not in the event JSON |
| Screen text is transient | `lastScreenText` is dropped when the finding closes, on sleep/off, or after a successful check | `desktop/main/index.ts` (the “Check it properly” fix) |
| No raw scores to makers | `CompanionPayload` has no score field; `Signal.score` is only for checker/security roles | `tests/finale/test_companion_finale.py::_assert_no_scores`; `tests/invariants/` |
| Delete session data | `privacy.delete_session` command; the Privacy tab has a two-step confirm | `desktop/renderer/src/workspace/tabs/PrivacyTab.tsx`; `api/companion/service.py::command` |
| Content protection | the mascot/bubble/Notebook are hidden from screen sharing by default | `desktop/main/index.ts::applyContentProtection`; tray toggle for the demo |

**What a judge can see live:** Notebook → Privacy: the “On this laptop” panel, the scopes that are
on, the consent receipt, and the Delete button. The Timeline shows every action with `text_stored=
false` on screen findings.

---

## 3. Raise-only, fail-closed, explainable

| Safeguard | How it is enforced | Proof |
|---|---|---|
| The floor uses **trusted data only** | `compute_floor(case, master, cfg)` takes no evidence content | `tests/invariants/` (floor isolation) |
| Evidence can only **raise** | `SIGNAL_TABLE` targets are raise-only; `apply_decision` never lowers | `tests/invariants/` (monotone, raise-only) |
| LLM/style signals cap at **VERIFY** | signal-table source rules + the policy cap | `tests/invariants/` (LLM cap) |
| A single weak signal cannot jump a band | policy table + corroboration rule | `tests/invariants/` (single weak signal) |
| Detector crash/parse failure → **GREY** | `pipeline._run` converts any exception to `GREY`; GREY forces ≥ VERIFY | `src/satyapan/pipeline.py`; `tests/tasks/test_t02*`, `tests/invariants/` |
| Band is set only by `satyapan.policy` | no other module calls `decide` or writes `Decision.band`; the desktop only relays | `tests/invariants/`; `desktop/main/index.ts` |
| Makers see **reasons**, not scores | companion payload + Notebook copy | `tests/finale/test_companion_finale.py::_assert_no_scores` |

**What a judge can see live:** Notebook → Cases → *Expert view*: the floor band, each raising
signal, the policy version, and the plain-English reason. No number that looks like a
probability.

---

## 4. OOB-Confirm: a channel the attacker does not control

| Safeguard | How it is enforced | Proof |
|---|---|---|
| Approver contact comes only from the **directory/master** | `_resolve_approver(case)`; a phone number inside the message is never used | `tests/finale/test_companion_finale.py::test_oob_uses_the_directory_contact...`; T12 tests |
| Single-use token, **10-minute expiry** | `OOBService.create/respond`; `OOBTicket.expires_at` | `src/satyapan/workflows/oob.py`; `tests/tasks/test_t12_oob.py` |
| Silence is **never approval** | the pending state stays pending; only an explicit approve does | `OOBService`; phone page tests |
| “I did not request this” is stronger than reject | `reason="not_requested"` → DENIED → case stays HOLD | `api/routes_verify.py`; `tests/finale/test_live_finale.py` |
| The approver sees the **exact question** | `/oob/request?token=` renders the case title, maker and amount | `console/public/oob.html`; `tests/finale/test_live_finale.py::test_phone_page...` |
| No scores on the phone page | the response model has no score field | same test's `_assert_no_scores` |

**What a judge can see live:** click **Verify with Rajesh** → the phone page (QR or localhost
fallback) shows the exact question; tap **I did not request this** → Satya holds up the shield,
the case stays HOLD.

---

## 5. Human review and no auto-reporting

| Safeguard | How it is enforced | Proof |
|---|---|---|
| No auto-submit anywhere | `ReportPackV2.submission` is the literal `MANUAL_ONLY`; `auto_submit` is the literal `False` | `src/satyapan/api/companion/models.py`; `tests/finale/test_report_pack_v2.py` |
| 5 drafts, UTR first | `build_report_pack_v2`; the 1930 script starts with the UTR | `src/satyapan/report/`; `tests/finale/test_live_finale.py` |
| External links are allow-listed | `tel:1930`, `mailto:*`, `https://cybercrime.gov.in` only | `desktop/main/ipc.ts`; `desktop/tests/*` |
| A human must answer the checker queue | HOLD → `CHECKER_REVIEW`; the alert card asks for OOB | `src/satyapan/policy/engine.py`; alert tests |
| §63 is a **draft** Part A, not a certificate | the report template says `DRAFT_REQUIRES_COUNSEL_AND_SIGNATORY_REVIEW` | `src/satyapan/report/`; `tests/finale/test_report_pack_v2.py` |

**What a judge can see live:** Reports → type a fake UTR → **Write my report pack** → the five
drafts, the golden-hour timer, and the line *“Drafts only. Nothing has been sent.”*

---

## 6. Audit and withdrawal

- Every action is recorded in `CompanionService._record`: session start/stop, call start/stop,
  OOB create/result, evidence submit, report draft, screen finding. The Notebook → Timeline shows
  it newest-first.
- The evidence vault stores a SHA-256 per file and an append-only custody chain; the Evidence tab
  can re-check integrity.
- “Delete session data” clears the session buffers; the Privacy tab has a confirm step and does not
  claim deletion if the request was not accepted.
- The app starts asleep and returns to sleep on any capture error; nothing keeps recording in the
  background.

---

## 7. What is **not** protected (say this before a judge asks)

- A **compromised laptop** (root/admin malware) can read memory or the vault. The claim is
  “local and minimised”, not “secure against a compromised OS”.
- A **malicious browser extension** with tab-capture permissions is outside the Electron trust
  boundary.
- **Screen-sharing by the attacker** can see the user's screen; we hide Satya from capture by
  default, but we cannot control other apps.
- **Network metadata** (the OOB page on the LAN, or Meet itself) is visible to the network.
- The **video/voice checks are raise-only and can miss**; the floor and OOB are the controls that
  remain.
- We do **not** claim media-origin authenticity: the vault proves bytes have not changed since
  capture, not that a person spoke them.

---

## 8. The 60-second proof

```bash
# 1. the safety invariants (property-tested, 200 examples each)
uv run pytest tests/invariants -q

# 2. the full story: consent -> call -> alert -> OOB "not me" -> report pack -> stop
make dry-run

# 3. the real phone page over HTTP (start the engine first: make live)
make oob-check

# 4. the health posture the desktop shows on startup
curl -s http://127.0.0.1:8000/companion/health | python -m json.tool
# -> policy_authority: satyapan.policy, raw_scores_visible: false, manual_only: true,
#    default_mode: SLEEP
```

Last run: `docs/finale/DRY_RUNS.md` (3/3 automated runs, 94–132 ms each; the human stage run is
still to be filled in on the demo laptop). `make oob-check` passed over a real uvicorn server:
the page served at `/oob`, `/api/oob/inbox`, the exact question, and “I did not request this” →
DENIED / HOLD.
