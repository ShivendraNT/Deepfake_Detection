# Finale plan — 48 hours at IIT Delhi

> What we build, who builds it, in what order, and how we demo it.
> Architecture: [`docs/GRAND_FINALS_ARCHITECTURE.md`](../GRAND_FINALS_ARCHITECTURE.md).
> Mascot/copy: [`MASCOT_SPEC.md`](MASCOT_SPEC.md). Your cards: `team/<YourName>.md`.

---

## 1. How we win (scoring map)

Judges score **what we built in the 48 hours**. Every row below must be visible in the demo or
on a slide, and must be backed by commits made during the event.

| Criterion | Pts | What the judges must see | Owner |
|---|---|---|---|
| Problem fit & user understanding | 20 | Priya the AP clerk; the Arup-style deepfake-CFO call; vendor bank-detail change; golden hour | Saarika (story), all |
| Technical architecture & detection logic | 20 | 4-window app + local engine diagram; payment floor + raise-only policy; asks + voice + Seal + email/invoice checks + **X1 cross-channel**; measured latency | Shivendra |
| Solution value & differentiation | 15 | Satya is *there at the moment of decision*; verify the **transaction** not the voice; 1-minute golden-hour pack with §63 hashes | all |
| Feasibility & finale execution | 15 | it runs live, offline, on a laptop; `make check` green; commit history of the 48 h | Shivendra |
| Safety, privacy & responsible AI | 15 | consent card; per-call yes; no mic; local only; abstain on bad audio; no auto-report; Privacy tab | Saksham (Privacy tab), Saarika (copy) |
| Adoption, integration & scale | 10 | install path, bank NCRP filing, I4C portal mapping, Windows, citizen mode | Kartikey (slide) |
| Communication | 5 | 3-minute story, a mascot people smile at, honest limits | Saarika |

**The one sentence every judge should remember:**
*"Satya doesn't try to prove the voice is fake — it makes sure the payment is real."*

---

## 2. Scope — what is P0 and what is not

**P0 = the demo path. If it is not P0, it does not start before checkpoint CP3.**

| P | Feature |
|---|---|
| **P0** | mascot-only window, radial menu, drag, three modes · consent card · call via Chrome extension route (A) + replay (C) · live chips + alert card · OOB from the alert, approver on a phone · drag-drop a file → result card · Scribe animation + Report Copilot (5 sections) · Notebook: Now, Cases, Timeline, Evidence, Reports, Privacy |
| **P1** | system-audio loopback route (B) · X1 cross-channel signal · Hinglish/हिन्दी copy toggle · Settings tab · "Keep as evidence" for call audio |
| **P2** | Gmail "Ask Satya" button · screenshot OCR drop · Windows build |
| **P3** | extension fills the open NCRP page (never submits) — only if someone can see the real form |

Route B (loopback) is P1 because it depends on a macOS permission quirk (see Risk R1). The spike
happens in the first 3 hours so we know early.

---

## 3. Task board

`H` = hours from the start of the finale. "Mock first" means you can start before the dependency
is done by using the mock client.

| ID | Task | Owner | P | Start → due | Needs |
|---|---|---|---|---|---|
| F01 | Contracts freeze + mock scenarios + `dev:mock` | Shivendra | P0 | H0 → **H2** | — |
| F02 | Window manager: 4 windows, click-through, drag/snap, bubble placement, tray, hotkeys, context menu, prefs | Shivendra | P0 | H2 → H10 | F01 |
| F03 | Backend glue: `calls/start|stop`, `files`, `oob`, event fan-in | Shivendra | P0 | H6 → H16 | F01 |
| F04 | X1 cross-channel signal (contract + policy table + tests) | Shivendra | P1 | H16 → H22 | F03 |
| F05 | Integration, demo fixtures, dry runs, backup recording | Shivendra + all | P0 | H20 → H46 | all |
| F06 | Mascot component (10 poses) + `?view=gallery` | Saarika | P0 | H2 → H14 | F01 |
| F07 | Mascot app: radial menu, drag hooks, `useSatya` brain | Saarika | P0 | H8 → H18 | F06, F02 (mock first) |
| F08 | Bubble cards (10 kinds) + `copy.ts` EN/Hinglish/हिन्दी | Saarika | P0 | H10 → H24 | F01 |
| F09 | Pitch deck + speaker notes + Q&A crib | Saarika (+ Shivendra) | P0 | H30 → H44 | demo works |
| F10 | Capture window: loopback spike, VAD call hint, chunks → `/live`, level meter | Kartikey | P0 spike, P1 route | H0 → H18 | F01 |
| F11 | Report pack v2: `/companion/report-pack`, 5 sections, field maps | Kartikey | P0 | H4 → H22 | F01 |
| F12 | Demo media: consented clone clips, replay WAVs, demo vendor email + invoice | Kartikey | P0 | H12 → H26 | consent forms |
| F13 | Gmail "Ask Satya" button (extension) | Kartikey | P2 | after CP3 | F03 |
| F14 | Notebook: shell + Now, Cases, Timeline, Evidence, Privacy, Settings | Saksham | P0 | H2 → H20 | F01 (mock first) |
| F15 | Reports tab: Scribe typing + Report Copilot + golden-hour timer | Saksham | P0 | H12 → H30 | F11 (mock first) |
| F16 | OOB phone page polish + QR code + LAN URL | Saksham | P0 | H10 → H20 | F03 (mock first) |

**Folder ownership = no merge conflicts.** You only edit files in your folders.

| Person | Owns (write) |
|---|---|
| Shivendra | `desktop/main/**` (except `capture.ts`), `desktop/preload/**`, `desktop/shared/**`, `desktop/renderer/src/App.tsx`, `desktop/renderer/src/shared/api.ts`, `src/satyapan/api/companion/**`, `src/satyapan/contracts/**`, `src/satyapan/policy/**`, `tests/**` (except own task tests below) |
| Saarika | `desktop/renderer/src/companion/**`, `desktop/renderer/src/shared/{tokens,copy}.ts`, `desktop/renderer/src/assets/**`, `docs/pitch/finale/**` |
| Kartikey | `desktop/renderer/src/capture/**`, `desktop/main/capture.ts`, `src/satyapan/report/**`, `data/demo/finale/**`, `extension/**` (F13 only), `tests/finale/test_report_pack_v2.py` |
| Saksham | `desktop/renderer/src/workspace/**`, `console/src/components/OobInbox.tsx`, `console/public/**` (OOB page only), `desktop/tests/workspace*.test.ts` |

Need a change in someone else's folder? Message them. Need a contract change? Shivendra only.

---

## 4. Timeline and checkpoints

Everyone stops at each checkpoint for **15 minutes**: Shivendra pulls everything together, runs it,
and says go / fix.

| When | Checkpoint | Must be true |
|---|---|---|
| **H2** | **CP0 — contracts frozen** | `desktop/shared/contracts.ts` + Python models merged; `npm run dev:mock` opens all views; everyone has run it |
| **H8** | **CP1 — skeleton** | Satya in his own tiny click-through window, draggable; Notebook opens with tabs; loopback spike result known (go/no-go for route B); `/companion/report-pack` returns a stub |
| **H16** | **CP2 — mock demo** | the full "deepfake CFO" mock scenario plays in the UI: consent → call ask → live chips → alert → OOB wait → not requested → Scribe → Report Copilot |
| **H24** | **CP3 — real engine** | same story with the real backend and **replay audio**: chips from Whisper + asks, policy band, OOB from a phone, report pack from real case data |
| **H32** | **CP4 — live** | route A (Chrome extension on Meet) works on the stage laptop; route B if the spike said go |
| **H36** | **FEATURE FREEZE** | after this only bug fixes, copy fixes, deck |
| H36–H44 | dry runs | **6 full dry runs**, timed, each logged in `docs/finale/DRY_RUNS.md` (what broke) |
| H40 | backup | screen recording of a perfect run, saved on 2 laptops + a pen drive |
| H44–H48 | buffer | rest, final `make check`, charge everything |

**Sleep.** Two people sleep at a time, 3–4 h, never the two who own a failing checkpoint.
Suggested: Saarika + Kartikey H18–H22, Shivendra + Saksham H26–H30.

---

## 5. How each person works with an AI agent (weak-model playbook)

Weak models fail when the task is big and vague. They do fine when the task is small, the
interface is fixed, and there is a check to run. So:

1. **New chat per card.** Paste the card's "Prompt" block. Nothing else.
2. **One step per message.** "Do step 3 only. Then run the check and show me the output."
3. **The agent may read only:** `AGENTS.md`, your `team/<Name>.md`, the docs your card lists, and
   the files in your card's "Files" list. Never "explore the repo".
4. **Contracts are frozen.** If the agent wants to change `contracts.ts`, say no and write
   `NEEDS-CONTRACT:` at the end of your card.
5. **Check after every step** (the card says which command). Red → fix → green → commit.
6. **3 failed attempts on the same error → stop.** Write `BLOCKED: <error, what you tried>` under
   the card and message Shivendra. Don't let the agent rewrite random files.
7. **UI tasks:** paste the exact table rows from `MASCOT_SPEC.md` into the prompt. Ask for those
   numbers, not "make it cute". Then compare a screenshot against the QA checklist.
8. **Strong model only for plan and review.** Use your strongest model (Claude Opus or equivalent)
   to (a) approve the plan of a card and (b) review the final diff. Use the free/fast model for
   the steps.

**Prompt template (every card has a filled-in version):**

```
You are helping <Name> with task <Fxx> in this repo.
Read ONLY: AGENTS.md, team/<Name>.md (section <Fxx>), <listed docs>, <listed files>.
You may edit ONLY: <files>. Do not touch contracts or anyone else's folder.
Do step <N> only. Then run: <check command>. Show me the output and a short diff summary.
If the check fails 3 times, stop and write what you tried.
```

---

## 6. Commits during the event

Shivendra decides the git workflow. Whatever it is, make the 48 hours **visible**:
- Small commits, one per step: `F06: blink + breathe loop`, `F11: NCRP field map`.
- Commit at every checkpoint even if partial.
- If the Round-1 code is brought into the hackathon repo, bring it as **one clearly labelled
  baseline commit** at the start ("Round-1 prototype baseline, built before the finale") and list
  it in the AI/asset disclosure. Judges respect honesty; they punish surprises.

---

## 7. The 3-minute demo

**Cast.** Shivendra = operator on Laptop A (Priya's Mac). Kartikey = "caller" on Laptop B,
plays the **consented** clone clips into Meet. A **judge** (or Saksham) holds the approver phone
as Rajesh. Saarika = narrator.

**Before going on stage:** Do Not Disturb on · Satya in Sleeping · backend `make run` healthy ·
macOS Screen & System Audio Recording permission already granted · phone on the same hotspot,
OOB page open · replay fixture ready · volume tested · Notebook closed.

| Time | Beat | What the judges see |
|---|---|---|
| 0:00–0:15 | Hook | "In 2024 a finance clerk at Arup paid about $25M after a video call where everyone else was a deepfake. Detectors are losing this race. So Satya doesn't try to prove the voice is fake — it makes sure the payment is real." |
| 0:15–0:30 | Meet Satya | Satya asleep in the corner (Zz). Click → menu blooms → Watch → consent card → Start. He wakes and waves. |
| 0:30–1:05 | The call | Meet call from "Rajesh (CFO)". Bubble: "Sounds like a call. Listen for payment tricks?" → Yes. Ears perk up, rings pulse with the voice. Clone: *"Priya, confidential acquisition. Transfer ₹48.5 lakh to this new escrow account today. Don't loop in Arjun."* Chips appear: **New account · Keep it secret · Skip approval**. |
| 1:05–1:35 | Pause + verify | Satya hops once, holds the shield: **"Pause before you pay."** → **Verify with Rajesh**. The judge's phone buzzes: "Did you ask Priya to pay ₹48,50,000 to ••••4821?" Judge taps **I did not request this**. Satya: "Rajesh says he didn't ask. I've put this payment on hold." |
| 1:35–2:00 | The email | Drag a vendor email + invoice onto Satya → "Should I read this?" → Check it → **"Verify first: the bank account differs from the vendor master. Call the vendor on their registered number."** (passes DMARC — the floor catches what detectors can't) |
| 2:00–2:35 | Golden hour | "What if the money already left?" → Satya puts on glasses and **writes**: 1930 script with the UTR on line 1, bank email, NCRP field helper, CERT-In email, §63 Part A with SHA-256 hashes. Timer: 58:41 left. "One tap to copy. A human submits." |
| 2:35–3:00 | Close | Notebook → Timeline + Privacy: every step logged, nothing recorded without a yes, all local. One slide: measured numbers (latency 3.12 s, alert budget HOLD 27.5% → 3.5% product / 3.0% frozen, 0/30 injections lowered a band). |

**Fallbacks (decide in 2 seconds, no panic):**
- Live capture fails → switch to **replay** (the label says DEMO REPLAY — say so).
- Phone can't reach the laptop → Saksham's laptop as the approver.
- Detector misses the clone → the chips + OOB still stop it: "this is exactly why the floor exists".
- Anything else → play the backup recording.

---

## 8. Risk register

| # | Risk | Likelihood | Mitigation | Owner |
|---|---|---|---|---|
| R1 | Loopback gives silence (macOS needs `NSAudioCaptureUsageDescription`; when launched from Terminal the *Terminal* app is the one asking) | high | spike in H0–H3; patch dev Electron's Info.plist; launch with `open -a` or a packaged build; else route A only | Kartikey |
| R2 | Venue Wi-Fi isolates devices (phone can't reach laptop) | high | phone hotspot for both; QR with the LAN URL in Settings | Saksham |
| R3 | Whisper model not cached → downloads on stage | med | pre-download models before leaving; test with Wi-Fi off | Shivendra |
| R4 | Bubble window steals focus during the call | med | passive cards use `showInactive()`; test with Meet focused | Shivendra |
| R5 | Weak model edits frozen files / other folders | med | folder ownership; review diffs at checkpoints; `make check` | all |
| R6 | Scope creep ("one more feature") | high | P0 list; nothing new after H36 | Shivendra |
| R7 | Clone clip sounds bad through Meet | med | test 5 clips through real Meet in H12–H20, keep the best 2 | Kartikey |
| R8 | macOS permission popup in the middle of the demo | med | grant all permissions on the stage laptop before; dry runs on that laptop | Shivendra |
| R9 | Hindi text overflow or wrong | low | Saksham proofreads; QA at 340 px | Saarika |
| R10 | Exhaustion → bugs at H40 | high | sleep shifts; freeze at H36 | all |

---

## 9. Judge Q&A crib (everyone learns these)

- **"Can you detect every deepfake?"** No, and nobody can. That's why Satya checks the
  *payment* and verifies through a channel the attacker doesn't control. The voice detector is one
  raise-only signal.
- **"Isn't listening to calls a privacy problem?"** Satya starts asleep, asks per call, never uses
  the mic, keeps audio in RAM, runs locally, and logs every action in the Privacy tab.
- **"Why not auto-file the complaint?"** There is no public 1930/NCRP API; the portal needs the
  victim's OTP; a human must stand behind a police complaint. Satya does 95 % of the work in a
  minute.
- **"Is the §63 certificate valid?"** It is a draft of Part A with real SHA-256 hashes from our
  vault. A human signs it; Part B needs an expert. The Supreme Court upheld the hash requirement in
  May 2026 (*Pune Bar Assn. v. Union of India*).
- **"What about Hindi / accents?"** Ask extraction works on EN, Hinglish and Devanagari. Accent is
  never a risk feature. Bad audio → we abstain.
- **"How does it scale?"** Signed installer for SMEs; banks can file on NCRP with their own
  credentials using our pack; same mascot in citizen mode; Windows supports loopback natively.
- **"What did you build in these 48 hours?"** Point at the commit log and the F-tasks.
- **"Your numbers?"** Only measured rows from `results/EVIDENCE_LEDGER.md`, with n and CI. Ask
  extractor recall on held-out data is modest (frozen 0.33; shipped product 0.39) — that's why it's not the only line of
  defence.

---

## 10. Before we leave for IIT Delhi (22–23 Oct)

- [ ] Everyone: pull the repo, `make sync`, `cd desktop && npm install`, `npm run dev` works.
- [ ] Everyone: read the architecture doc §0–§6 and your own `team/<Name>.md`.
- [ ] Shivendra: confirm with organisers what may be prepared before (designs? data?) and what
      counts as "built during the hackathon". Follow their answer.
- [ ] Kartikey: signed voice-consent forms (`docs/consent/`), clone clips generated on Colab from a
      **consenting** teammate only; keep originals off GitHub.
- [ ] Shivendra: Whisper + ONNX models cached; test the backend with Wi-Fi off.
- [ ] Saksham: phone ↔ laptop over a phone hotspot works for the OOB page.
- [ ] All: chargers, a USB-C hub, HDMI adapter, a pen drive with the backup recording, a phone
      hotspot plan with data.
