# Saksham — the Notebook (Satya's info tab), Reports, and the approver's phone

> Cards: **F14 → F16 → F15**. Plan: `docs/finale/PLAN.md`. Styling: `docs/finale/MASCOT_SPEC.md`
> §2 (tokens) and §7 (anti-slop rules).
> You edit only: `desktop/renderer/src/workspace/**`, `console/src/components/OobInbox.tsx`,
> `console/public/**` (OOB page only), `desktop/tests/workspace*.test.ts`.
> Also: proofread the हिन्दी column in `MASCOT_SPEC.md` §8 for Saarika (you did T14).

**Your job in one line:** when a judge double-clicks Satya, they should see a calm, beautiful
notebook where *everything* Satya did is logged and explained — and the golden-hour pack writes
itself in front of them.

**How you run things (no backend needed):** `cd desktop && npm run dev:web` →
`http://localhost:5174/?view=workspace` (mock data). Electron only at checkpoints.

**Model use.** Plan + final review: your strongest model. Steps: fast model, one step per message.

---

## F14 — Notebook shell + tabs (P0 · H2 → H20)

**Goal.** A 1120×720 window with a left sidebar and seven tabs that read from the bridge (mock
first, real later — same code).

**Read.** Architecture §4.3, §10 · `MASCOT_SPEC.md` §2, §7 · contracts (`WorkspaceSnapshot`,
`CaseSummary`, `AuditRow`, `CompanionState`, `Prefs`) · old `workspace/Workspace.tsx`.

**Files.** `workspace/Workspace.tsx` (stays the root — a test checks it) ·
`workspace/Sidebar.tsx` · `workspace/tabs/{Now,Cases,Timeline,Evidence,Privacy,Settings}Tab.tsx` ·
`workspace/ui/{BandBadge,Hash,Empty,Section}.tsx` · `desktop/tests/workspace.test.ts`.

**Layout.**
```
┌─────────────┬──────────────────────────────────────────────────┐
│ (Satya 28px)│  Now                                   ● Watching │
│  Satya's    │ ┌────────────────────────────────────────────────┐│
│  Notebook   │ │ Live call · 02:14 · coverage: usable           ││
│             │ │ [New account] [Keep it secret] [Skip approval] ││
│ ◉ Now       │ │ Voice not verified by Seal                     ││
│ ○ Cases     │ └────────────────────────────────────────────────┘│
│ ○ Timeline  │  Last alert — Pause before you pay.  [Open case]  │
│ ○ Evidence  │                                                   │
│ ○ Reports   │                                                   │
│ ○ Privacy   │                                                   │
│ ○ Settings  │                                                   │
└─────────────┴──────────────────────────────────────────────────┘
```
Paper background (`ui.*.paper`), sidebar `ui.*.sidebar`, Inter 14 px base, headings 20/600,
hashes in JetBrains Mono. Bands: PASS green "Looks OK", VERIFY amber "Verify first", HOLD coral
"On hold" — words, never scores.

**Steps.**
1. Shell: sidebar + header (tiny `<Mascot size={28} pose=…/>` from Saarika's component, mode
   pill) + tab switch. *Check:* `?view=workspace`.
2. **Now**: mode, source, live call panel (chips, coverage, seal, elapsed), last alert with
   "Open case". Updates from `api.onEvent`.
3. **Cases**: list (`listCases`) + detail (`workspace(caseId)`): band badge, floor band, queue,
   reasons in plain words, masked payee, amount `₹48,50,000`, evidence list, drafts.
4. **Timeline**: `audit()` + live events, newest first, grouped by time ("2 min ago").
   Icons per action. This is the "Satya keeps track of everything" screen — make it beautiful.
5. **Evidence**: per file: name, channel, size, SHA-256 (short, copy full), custody rows
   (`custody(caseId)`), a "Re-check integrity" button (P1: calls the backend verify; P0: shows
   the stored hash chain).
6. **Privacy**: what's on right now (scopes), consent receipts with times, what was kept and why,
   "Delete session data" (calls a command — Shivendra wires it), a plain-words paragraph:
   *"Satya runs on this laptop. He never uses your microphone. Call audio stays in memory unless
   you tap 'Keep as evidence'."*
7. **Settings**: size S/M/L, sounds, language EN/Hinglish/हिन्दी, "Notice calls automatically",
   source (Chrome tab / System audio / Replay), hotkeys list, OOB QR code (F16).
8. Tests: 5 vitest cases (renders each tab with mock data; no raw-score text; account masked).

*Check:* `cd desktop && npm run typecheck && npx vitest run workspace`.

**Prompt.**
```
You are helping Saksham with task F14 in this repo.
Read ONLY: AGENTS.md, team/Saksham.md (F14), docs/GRAND_FINALS_ARCHITECTURE.md §4.3,
docs/finale/MASCOT_SPEC.md §2 and §7, desktop/shared/contracts.ts, desktop/renderer/src/shared/api.ts,
desktop/renderer/src/workspace/Workspace.tsx.
You may edit ONLY the files listed under F14. Use only data from the api bridge (mock works the
same). Never show scores. Do step <N> only. Then run: cd desktop && npm run typecheck. Tell me the
URL to check: http://localhost:5174/?view=workspace.
```

---

## F16 — The approver's phone (OOB) (P0 · H10 → H20)

**Goal.** The judge holding the phone understands the request in 3 seconds and taps one big button.

**Read.** `console/src/components/OobInbox.tsx` (your T12 code) · `console/src/api.ts` ·
`console/vite.config.ts` · Architecture §6.4.

**Files.** `console/src/components/OobInbox.tsx` · `console/public/**` (if you add a standalone
page) · `workspace/tabs/SettingsTab.tsx` (QR block).

**Steps.**
1. Mobile-first layout (375 px wide): "Did you ask **Priya** to pay **₹48,50,000** to
   **Fictional Escrow Ltd ••••4821** today?" + time asked + "Asked via Satya on Priya's laptop".
2. Three full-width buttons, 56 px tall: **Approve this exact payment** · **Reject** ·
   **I did not request this** (map: approve → `approve: true`; reject → `approve: false`;
   not requested → `approve: false, reason: "not_requested"` — Shivendra adds the optional
   `reason` in F03).
3. Result screen after tapping (big tick or cross, one line).
4. Phone access: run the console with `npm run dev -- --host` so the phone can open
   `http://<laptop-LAN-IP>:5173/…` (the `/api` proxy already forwards to the backend).
   Test over a **phone hotspot** (venue Wi-Fi may block device-to-device).
5. QR code in Settings (`qrcode` package) for `AppConfig.oob_url`.

*Check:* `make console-test` · the full loop on a real phone: Satya alert → Verify → phone →
tap → Satya reacts.

---

## F15 — Reports tab: Scribe + Report Copilot (P0 · H12 → H30)

**Goal.** The wow moment: the pack writes itself, then becomes a checklist the user can act on in
minutes.

**Read.** Architecture §6.5 · contracts `ReportPackV2`, `ReportSection`, `ReportField` ·
`companion/useTypewriter.ts` (reuse).

**Files.** `workspace/report/ReportsTab.tsx` · `workspace/report/ScribeDocument.tsx` ·
`workspace/report/CopilotChecklist.tsx` · `workspace/report/GoldenHourTimer.tsx` ·
`workspace/report/FieldRow.tsx`.

**Steps.**
1. `GoldenHourTimer`: counts down 60:00 from `money_left_at`; after zero shows "Still report — it
   still helps." No red flashing.
2. `ScribeDocument`: sections appear one by one. For each: title fades in, body types out at
   ~45 chars/s (reuse `useTypewriter`), then source chips fade in under each paragraph
   (`maker-entered`, `vault ev_…`, `vendor master`, `you confirmed`). A small Satya in `write`
   pose sits at the top while it types. Reduced motion → show instantly.
   Text comes **only** from `ReportPackV2` — the animation never invents words.
3. `CopilotChecklist`: 5 steps (1930, bank, NCRP, CERT-In, §63). Each step: destination,
   deadline hint, "Open" button (`openExternal(open_url)`), the fields as `FieldRow`s with copy
   buttons, sensitive values masked with a "Reveal" toggle, and a "Done" checkbox the user ticks.
   `applies = false` → step shown greyed with the reason.
4. Banner on top, always: **"Drafts only. Nothing has been sent. You review and submit."**
5. "Export PDF" (P1): `window.print()` with a print stylesheet.

*Check:* `npm run typecheck` · `?view=stage` → Play `money_left` → Satya writes, Notebook types,
checklist works with copy buttons.

**Prompt.**
```
You are helping Saksham with task F15 in this repo.
Read ONLY: AGENTS.md, team/Saksham.md (F15), docs/GRAND_FINALS_ARCHITECTURE.md §6.5,
desktop/shared/contracts.ts, desktop/renderer/src/shared/api.ts,
desktop/renderer/src/companion/useTypewriter.ts.
You may edit ONLY the files listed under F15. All text comes from ReportPackV2 — never generate
report text in the UI. Do step <N> only. Then run: cd desktop && npm run typecheck.
```
