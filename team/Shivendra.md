# Shivendra — lead · window manager · backend glue · integration

> Cards: **F01 → F02 → F03 → F04 (P1) → F05**. Plan and checkpoints: `docs/finale/PLAN.md`.
> You are the only one who edits contracts, policy, `tests/invariants/`, `tests/harness/`,
> `tests/conftest.py`, `desktop/shared/`, `desktop/preload/`, `desktop/package.json`.

**Your job in one line:** freeze the contracts in 2 hours so three people can work blind, build
the windows they render into, wire the backend, then integrate and run the demo.

**At every checkpoint (H2, H8, H16, H24, H32):** pull everyone's work, `make check`,
`cd desktop && npm run typecheck && npm run build`, run the scenario, say go / fix in one message.

---

## F01 — Contracts freeze + mock scenarios (P0 · H0 → H2)

**Goal.** Everyone can build against fixed types and a fake backend from hour 2.

**Read.** `docs/GRAND_FINALS_ARCHITECTURE.md` §4, §8, §9 · `desktop/shared/contracts.ts` ·
`src/satyapan/api/companion/models.py` · `desktop/renderer/src/companion/mockClient.ts`.

**Files.** `desktop/shared/contracts.ts` · `src/satyapan/api/companion/models.py` ·
`desktop/preload/index.ts` (signatures only, stubs OK) · `desktop/renderer/src/App.tsx` ·
`desktop/renderer/src/shared/api.ts` (new) · `desktop/renderer/src/shared/mockScenario.ts` (new) ·
`desktop/package.json` · `desktop/vite.web.config.ts` (new) · stub files listed in step 5.

**Steps.**
1. Paste the §9 TypeScript block into `contracts.ts`; extend `CompanionEventType` and make the
   new `CompanionPayload` fields optional. Add `Prefs`, `AppConfig.oob_url`, bridge methods.
   *Check:* `cd desktop && npm run typecheck`.
2. Mirror in Python: `AskChip`, `Coverage`, `SealStatus`, `OobTicket`, `ReportField`,
   `ReportSection`, `ReportPackV2`, new event types, optional payload fields. No score fields.
   *Check:* `make task T=T25` and `make schemas`.
3. `shared/api.ts`: `export const api = window.satyapan ?? createMockBridge()`. The mock bridge
   implements every bridge method in one browser tab (cards render into a `<div>` instead of a
   window). `VITE_SATYA_MOCK=1` forces the mock.
4. `shared/mockScenario.ts`: three timed scripts — `cfo_call`, `vendor_email`, `money_left` —
   as arrays of `{ at_ms, event }` using only contract types and fake data (`FAK…`, `9999…`,
   `*.example`). Include the exact demo lines from PLAN §7.
5. `App.tsx` routes `?view=` → `companion | bubble | workspace | capture | gallery | stage`.
   Create **stubs** so imports compile: `companion/MascotApp.tsx`, `companion/bubble/BubbleApp.tsx`,
   `companion/Gallery.tsx`, `workspace/Workspace.tsx` (keep — a test checks it),
   `capture/CaptureApp.tsx`. `stage` = mascot + bubble + notebook side by side in one tab, with
   Play buttons for the three scenarios. (Keep the words `Companion` and `Workspace` in App.tsx,
   and keep `companion/{mockClient,CaptureSource,ReportDraftClient,ConsentCard,Mascot}.ts(x)` as
   files — the T25 tests check them.)
6. `package.json`: add `"dev:web": "vite --config vite.web.config.ts"` (renderer only, mock on, **port 5174** — the console already uses 5173),
   deps `onnxruntime-web` (Kartikey) and `qrcode` (Saksham).
   *Check:* `npm run dev:web` → `http://localhost:5174/?view=stage` plays `cfo_call`.
7. Commit `F01: freeze finale contracts + mock bridge + stage view`. Post in the group: "CP0 —
   pull, run `npm run dev:web`, open `?view=stage`."

**Done when.** typecheck green · `make task T=T25` green · stage view plays all three scenarios ·
everyone confirmed they can run it.

---

## F02 — Window manager (P0 · H2 → H10)

**Goal.** Satya lives alone in a tiny click-through window; the bubble appears beside him;
Notebook and capture windows exist; tray, hotkeys and menus work.

**Read.** Architecture §4, §5 · `desktop/main/*.ts`.

**Files.** `desktop/main/windows.ts`, `desktop/main/index.ts`, `desktop/main/ipc.ts`,
`desktop/main/tray.ts`, `desktop/main/prefs.ts` (new), `desktop/main/placement.ts` (new),
`desktop/preload/index.ts`, `desktop/renderer/index.html` (CSP), `desktop/tests/placement.test.ts` (new).

**Steps.**
1. `createMascotWindow`: 280×280, `transparent`, `frame: false`, `focusable: false`,
   `skipTaskbar`, `hasShadow: false`, `setAlwaysOnTop(true, 'floating')`,
   `setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })`,
   `setIgnoreMouseEvents(true, { forward: true })`. Restore position from `prefs.ts`
   (`userData/satya.json`), default bottom-right with 24 px margin. Keep the sandbox flags.
2. IPC `setClickThrough(b)` → `setIgnoreMouseEvents(b, { forward: true })`.
   `dragBy(dx, dy)` → `setPosition`. `dragEnd()` → snap to edge if within 24 px, clamp to the
   work area, save prefs, re-place the bubble.
3. Cursor feed: 30 Hz timer while the mascot is visible → `{dx, dy, near}` relative to Satya's
   centre (`screen.getCursorScreenPoint()`). Stop the timer when hidden/Off.
4. `placement.ts`: pure `placeBubble(mascot, workArea, bubble) → {x, y, tail}` (left if mascot is
   on the right half, else right; shift up/down to stay on screen). Unit-test 4 corners.
5. Bubble window (hidden at start): `showCard(card)` → place, send `(card, tail)`, then
   `showInactive()` for `live`/`toast`, `show()` otherwise. `hideCard` hides.
   `cardAction` → relay to the mascot window. `resizeBubble(h)` → setSize + re-place.
6. Notebook window (`?view=workspace`) open/focus; capture window (`?view=capture`, `show: false`,
   `backgroundThrottling: false`) created on first `startCall`/Watching. Import Kartikey's
   `registerCapture()` from `main/capture.ts`.
7. Tray (mode label + Watch/Sleep/Show-Hide/Notebook/Quit), hotkeys `⌘⇧S`, `⌘⇧.`, `⌘⇧N`,
   native context menu on right-click. `setUserMode`: WATCHING → session/start;
   SLEEPING → session/stop; OFF → session/stop + hide mascot + bubble. Quit/hide keep
   `before-quit` + `session/stop` (T25 tests).
8. `openExternal(url)` allow-list: `tel:1930`, `mailto:*`, `https://cybercrime.gov.in*`. CSP in
   `index.html`: `default-src 'self'; connect-src 'self' http://127.0.0.1:8000; img-src 'self' data:`.

*Check after each step:* `cd desktop && npm run typecheck && npx vitest run` ·
*after step 8:* `npm run build && npm run dev`, then the manual list below · `make task T=T25`.

**Manual check.** Click empty space next to Satya → the app behind gets the click · drag →
moves smoothly, snaps, remembers position after restart · bubble flips side at screen edges ·
Meet stays focused while a `live` card shows · `⌘⇧.` stops listening from any state.

---

## F03 — Backend glue (P0 · H6 → H16)

**Goal.** The desktop talks to the existing engine through a few thin endpoints, and the UI gets
one event stream.

**Read.** Architecture §6, §8 · `src/satyapan/api/companion/{router,service,bus}.py` ·
`src/satyapan/api/routes_live.py`, `routes_cases.py` (evidence upload), `routes_verify.py` (oob) ·
`src/satyapan/live/service.py`.

**Files.** `src/satyapan/api/companion/**` · `tests/finale/test_companion_finale.py` (new).

**Steps.**
1. `POST /companion/calls/start {source, consent_id}` → requires an active consented session →
   `state.live().start(call_id, maker)` → set source → emit `call.started` → `{call_id, case_id}`.
   `POST /companion/calls/stop` → stop + `call.stopped`. Tests: refused without consent.
2. Fan-in: subscribe to the live bus for the active call; map `ask` → `live.chips` (accumulate
   codes), `voice` → `seal`/`coverage`, `band` → `alert.raised` when ≥ VERIFY, with T14 template
   text and `next_actions` `verify`, `copy_reply`, `open_notebook`. **Relay the policy `Decision`;
   never compute a band.** Tests: no score/confidence fields; band equals the policy's.
3. `POST /companion/files` (multipart `file`, `case_id?`): same path as `/cases/{id}/evidence`
   (vault intake → `analyze_evidence` → merge → `recompute`) → `EvidenceResult` +
   `analysis.completed`.
4. `POST /companion/oob {case_id}` → existing OOB create (approver from directory only) →
   `OobTicket` + `oob.sent`. Hook `/oob/respond` to emit `oob.result` + `case.updated`.
   Add an optional `reason: "not_requested"` to `/oob/respond` (Saksham's third button).
   Test: a phone number inside an email/transcript is never used as the channel.
5. `GET /companion/report-pack?case_id=` → `build_report_pack_v2(...)` from Kartikey (F11).
   Until it lands, return a stub built from `mockScenario` data.

*Check:* `uv run pytest tests/finale -q` · `make task T=T25` · `make check`.

---

## F04 — X1 cross-channel signal (P1 · H16 → H22)

**Goal.** One explainable signal that only a multi-channel companion can produce.

**Files.** `src/satyapan/contracts/signal_table.py` (+ enums), `src/satyapan/policy/` (target only
via the table), `src/satyapan/pipeline.py` (derive from case evidence timestamps),
`src/satyapan/explain/templates.py` (EN/HI text), `tests/invariants/` (property: X1 can only raise),
`tests/finale/test_x1.py`.

**Rule.** Within 30 min in one case: an A1 or A7 ask from a call/message **and** a new or changed
beneficiary → VERIFY; plus A4 or A5 → HOLD. Built with `Signal.make(...)`, deterministic source.
After the change: `make schemas`, update `console/src/types.ts` if needed, `make check`.

---

## F05 — Integration, demo, recording (P0 · H20 → H46)

1. Demo fixtures: a call case with Rajesh as approver; vendor email case (s07); money-left case
   (s12) with a fake UTR. All fake data.
2. CP3 (H24): full story on the real backend with replay audio. CP4 (H32): live on Meet.
3. H36 freeze. 6 timed dry runs on the **stage laptop**, logged in `docs/finale/DRY_RUNS.md`.
4. H40 backup recording (2 laptops + pen drive).
5. Every number on a slide → a row in `results/EVIDENCE_LEDGER.md`. No row, no number.

**Prompt for your agent (F02 example):**
```
You are helping Shivendra with task F02 in this repo.
Read ONLY: AGENTS.md, team/Shivendra.md (F02), docs/GRAND_FINALS_ARCHITECTURE.md §4-§5,
desktop/main/*.ts, desktop/preload/index.ts, desktop/shared/contracts.ts.
You may edit ONLY the files listed under F02. Keep sandbox/contextIsolation flags exactly.
Do step <N> only. Then run: cd desktop && npm run typecheck && npx vitest run. Show the output.
```

---

## Agent plan — F01 + F02 (24 Oct, opencode / DeepSeek V4.1 Flash)

1. F01.1 Add finale types, event fields and bridge methods to `desktop/shared/contracts.ts` (backwards compatible).
2. F01.2 Mirror types in `src/satyapan/api/companion/models.py`; run `make task T=T25` for zero regressions.
3. F01.3 `renderer/src/shared/api.ts` (real bridge or in-memory mock, `VITE_SATYA_MOCK=1` forces mock).
4. F01.4 `renderer/src/shared/mockScenario.ts` — `cfo_call`, `vendor_email`, `money_left` (fake data only).
5. F01.5 `App.tsx` router + stubs (`MascotApp`, `BubbleApp`, `Gallery`, `CaptureApp`, `Stage`) and `vite.web.config.ts` on :5174.
6. F02.1 `main/placement.ts` (pure `placeBubble`, `snapToEdges`) + `desktop/tests/placement.test.ts`; `main/prefs.ts`.
7. F02.2 `main/windows.ts` + `main/index.ts` — mascot / bubble / workspace / capture windows, click-through, drag, cursor feed.
8. F02.3 `main/ipc.ts` + `main/tray.ts` + `preload/index.ts` — bridge methods, allow-listed `openExternal`, mode tray + hotkeys; CSP.

Check after each step: `cd desktop && npm run typecheck && npx vitest run` · `make task T=T25` · at the end `make check`.
