# Saarika — Satya himself: mascot, menu, bubble cards, copy, deck

> Cards: **F06 → F07 → F08 → F09**. Your bible: `docs/finale/MASCOT_SPEC.md`.
> Plan and checkpoints: `docs/finale/PLAN.md`.
> You edit only: `desktop/renderer/src/companion/**`, `desktop/renderer/src/shared/tokens.ts`,
> `desktop/renderer/src/shared/copy.ts`, `desktop/renderer/src/assets/**`, `docs/pitch/finale/**`.

**Your job in one line:** make the judges smile at Satya in the first 10 seconds, and make every
word he says short, kind and clear.

**How you run things (no backend needed):**
`cd desktop && npm run dev:web` → open `http://localhost:5174/?view=gallery` (poses) or
`?view=stage` (mascot + bubble + notebook with Play buttons). Electron only at checkpoints:
`npm run dev`.

**Model use.** Plan + final review of each card: your strongest model (Claude Opus).
Steps: your fast model. One step per message. Paste the numbers from `MASCOT_SPEC.md` into the
prompt — never ask for "make it cute".

---

## F06 — The mascot component (P0 · H2 → H14)

**Goal.** One `<Mascot pose audioLevel look size reducedMotion />` that draws Satya exactly as
specified and animates all 10 poses.

**Read.** `MASCOT_SPEC.md` §2–§5 · `desktop/shared/contracts.ts` (type `Pose`) ·
the old `companion/Mascot.tsx` (only to see how Framer Motion is used; replace it).

**Files.** `shared/tokens.ts` (new) · `companion/Mascot.tsx` (rewrite) · `companion/poses.ts`
(new) · `companion/accessories.tsx` (new) · `companion/useBlink.ts` (new) ·
`companion/Gallery.tsx` (new) · `assets/fonts/*` (copy from `docs/pitch/round1/src/fonts/`).

**Steps.**
1. `tokens.ts`: copy §2 exactly. *Check:* `npm run typecheck`.
2. Static Satya (`idle` only): the 13 layers from §3 with the exact paths and colours, as
   `<motion.g id=…>`. Sticker outline + static drop-shadow. *Check:* `?view=gallery`, screenshot on
   white and on black.
3. `poses.ts`: a `Record<Pose, PoseSpec>` with eyes, ear angles, body scale, mouth, accessory,
   aura, loop — copy the §4 table into data. `Mascot` reads it and animates between poses with
   `motion.soft`. *Check:* gallery buttons switch poses smoothly.
4. Eye and mouth variants (§3): swap `d`/shape **only on pose change**.
5. Loops: breathe, blink (`useBlink.ts`, random 2.5–6 s, 20 % double), random ear twitch.
6. Look-at from the `look` prop (`{dx, dy, near}`), clamped as in §5.
7. Accessories (§4): `zzz`, `rings` (from `audioLevel`), `shield`, `glasses`, `quill`, `sparkles`,
   paws for `catch`/`wave`/`off`.
8. `Gallery.tsx`: all poses in a grid; controls for size S/M/L, audio level slider,
   reduced-motion toggle, light/dark background.
9. Run the §9 QA checklist; save screenshots in `docs/finale/screens/mascot/`.

**Done when.** All 10 poses match the spec · QA checklist ticked · idle CPU < 3 % in Electron.

**Prompt.**
```
You are helping Saarika with task F06 in this repo.
Read ONLY: AGENTS.md, team/Saarika.md (F06), docs/finale/MASCOT_SPEC.md, desktop/shared/contracts.ts,
desktop/renderer/src/companion/Mascot.tsx.
You may edit ONLY the files listed under F06. Use React + framer-motion + SVG. Animate only
transform/opacity. Use the exact paths, colours and numbers from MASCOT_SPEC.md — do not invent.
Do step <N> only. Then run: cd desktop && npm run typecheck. Tell me what to look at in
http://localhost:5174/?view=gallery.
```

---

## F07 — The mascot window: menu, drag, brain (P0 · H8 → H18)

**Goal.** The mascot window feels alive: hover, click → menu, drag, drop a file, and Satya's mood
follows what is happening.

**Read.** Architecture §4.1, §5, §6 · `MASCOT_SPEC.md` §5 (menu, drag) ·
`companion/useCompanion.ts` (old brain — reuse its logic) · `shared/api.ts`.

**Files.** `companion/MascotApp.tsx` · `companion/RadialMenu.tsx` · `companion/useDrag.ts` ·
`companion/useHitArea.ts` · `companion/satyaMachine.ts` (new, pure) · `companion/useSatya.ts` ·
`desktop/tests/satyaMachine.test.ts` (new).

**Steps.**
1. `satyaMachine.ts`: a **pure reducer** `(state, action) → state`.
   State: `{ userMode, pose, card, caseId, callId, chips, lastBand, dismissed }`.
   Actions: `EVENT(CompanionEvent)`, `SET_MODE`, `CALL_HINT`, `FILE_HOVER`, `FILE_DROP`,
   `CARD_ACTION`, `TIMER`. Follow the state diagram in Architecture §5.
   Write 10 vitest cases first (e.g. `alert.raised` → pose `alert` + `alert` card;
   `oob.result not_requested` → `alert` + HOLD; Sleeping ignores `CALL_HINT`).
   *Check:* `npx vitest run satyaMachine`.
2. `useSatya.ts`: wires the reducer to `api` (events, card actions, call hints, audio level) and
   performs side effects (`showCard`, `startCall`, `submitFile`, `requestOob`, `setUserMode`).
3. `useHitArea.ts`: `setClickThrough(false)` on pointer-enter of Satya/petals, `true` on leave.
4. `useDrag.ts`: pointer-down → after 4 px movement send `dragBy` per animation frame; tilt from
   velocity; click if < 4 px and < 250 ms; double-click → Notebook.
5. `RadialMenu.tsx`: 5 petals (lucide icons: Eye, Moon, FileSearch, BookOpen, Power) per §5.
   Arc inward near edges (main tells you the side via the mascot's screen position, or use
   `window.screenX`).
6. File drop: `dragenter` → `FILE_HOVER` (pose `catch`); `drop` → read the `File` into an
   `ArrayBuffer` → `FILE_DROP` → `file_ask` card → on "Check it" → `submitFile`.
7. *Check:* `?view=stage` plays all three scenarios with correct poses and cards; then in Electron
   (`npm run dev`) click-through and drag work.

**Prompt.**
```
You are helping Saarika with task F07 in this repo.
Read ONLY: AGENTS.md, team/Saarika.md (F07), docs/GRAND_FINALS_ARCHITECTURE.md §4.1, §5, §6,
docs/finale/MASCOT_SPEC.md §5, desktop/shared/contracts.ts, desktop/renderer/src/shared/api.ts,
desktop/renderer/src/companion/useCompanion.ts.
You may edit ONLY the files listed under F07. The reducer must be pure (no api calls inside).
Do step <N> only. Then run: cd desktop && npm run typecheck && npx vitest run. Show the output.
```

---

## F08 — Bubble cards + copy (P0 · H10 → H24)

**Goal.** Every card kind looks calm and clean, fits 340 px, and speaks EN / Hinglish / हिन्दी.

**Read.** `MASCOT_SPEC.md` §7, §8 · contracts `BubbleCard`, `CardAction`, `AskChip` ·
old `companion/{AlertCard,ConsentCard,ScribeCard,Toast}.tsx` (reuse what's good).

**Files.** `shared/copy.ts` (new) · `companion/bubble/BubbleApp.tsx` ·
`companion/bubble/CardShell.tsx` · `companion/bubble/cards/<Kind>Card.tsx` (one per kind:
Consent, CallAsk, FileAsk, Live, Result, Alert, OobWait, OobResult, Scribe, Toast) ·
`companion/chime.ts`. Keep `companion/ConsentCard.tsx` as a file (a test checks it exists) — it can
re-export the new card.

**Steps.**
1. `copy.ts`: every key from §8, `t(key, lang, vars)`; missing key → the EN text, never the key.
2. `CardShell.tsx`: card frame, tail (left/right), header dot, close ×, buttons (max 3), enter/exit
   motion; reports its height with `ResizeObserver` → `api.resizeBubble(h)`.
3. One card per step, simplest first: Toast → Consent → CallAsk → FileAsk → Result → Live →
   Alert → OobWait → OobResult → Scribe. Each button calls `api.cardAction(card.id, action.id)`.
4. `Alert`: chips row, the `alert.body` text, "Copy a safe reply" copies `safe_reply`.
5. Language: read `prefs.lang`; add a tiny EN/HI toggle in `?view=stage` to test all three.
6. QA: every card in 3 languages, light + dark, at 340 px → screenshots in
   `docs/finale/screens/bubble/`.

**Prompt.**
```
You are helping Saarika with task F08 in this repo.
Read ONLY: AGENTS.md, team/Saarika.md (F08), docs/finale/MASCOT_SPEC.md §7-§8,
desktop/shared/contracts.ts, desktop/renderer/src/shared/{api,tokens}.ts.
You may edit ONLY the files listed under F08. Follow the anti-slop rules in MASCOT_SPEC §7.
Do step <N> only (one card at a time). Then run: cd desktop && npm run typecheck.
Tell me the URL to check it: http://localhost:5174/?view=bubble&card=<kind>.
```

---

## F09 — Deck + story (P0 · H30 → H44, with Shivendra)

**Files.** `docs/pitch/finale/**` (reuse the round-1 HTML deck build in `docs/pitch/round1/`).

**Slides (max 9 + appendix).**
1. Hook — the Arup call; "Satya doesn't prove the voice is fake, it makes sure the payment is real."
2. Priya and the three attacks (call, vendor email, money already gone).
3. **Live demo** (title slide only).
4. Architecture — the diagram from Architecture §3.
5. Detection logic — floor + raise-only + signals (asks, voice, Seal, email/invoice, X1) + OOB.
6. Safety & privacy — consent per call, no mic, local, abstain, no auto-report, Privacy tab.
7. Golden hour — 1930 / bank / NCRP / CERT-In / §63 hashes, with the cited facts.
8. Evidence — only rows from `results/EVIDENCE_LEDGER.md` (n + CI) + "built in 48 h" (commits).
9. Adoption & scale — SME install, banks on NCRP, I4C mapping, Windows, citizen mode.
Appendix — AI/asset/dataset disclosure (required by the rules), consent forms, limits.

**Rules.** No number without a ledger row. No claim we can't show. Max 25 words per slide body.
Practise the 3-minute script (PLAN §7) until it's 2:50.
