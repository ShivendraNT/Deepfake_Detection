# T06 — Console UI shell (Vite + React + Tailwind)

## Goal
The Payment Verification Desk screens: case list, case view (transaction card FIRST, then band
badge + reason codes, clearance steps, evidence list) and a role switcher (maker / checker / CFO /
security) — all against the existing API.

## Owner
Saksham. Effort ≈ 1 day.

## Depends on
T01 (done). API already serves `/cases`, `/cases/{id}`, `/vendors`, `/employees`.

## Files to create or modify
- `console/src/App.tsx` — replace the stub (remove the `STUB(T06)` line)
- `console/src/components/CaseList.tsx` (new)
- `console/src/components/CaseView.tsx` (new)
- `console/src/components/BandBadge.tsx` (new)
- `console/src/components/TransactionCard.tsx` (new)
- `console/src/components/ReasonCodes.tsx` (new)
- `console/src/components/EvidenceList.tsx` (new)
- `console/src/components/RoleSwitcher.tsx` (new)
- `console/src/__tests__/App.test.tsx` — may add more tests (keep the existing one)

## Do not touch
`console/src/types.ts`, `console/src/api.ts` (leader-owned mirrors of the contracts), anything in
`src/`, `extension/`.

## Interfaces
- Use `api.listCases(user)`, `api.getCase(user, id)` from `console/src/api.ts`; types from `types.ts`.
- Test ids required by the acceptance test: each row `data-testid="case-row"`, each badge
  `data-testid="band-badge"`.
- Band colours: PASS green, VERIFY amber, HOLD red — ALWAYS with the text label too (accessibility).
- `canSeeScores(role)` = role is checker or security. Makers never see a score column.
- Show `decision.clearance.callback_number` with the label "Call back on (from vendor master)".

## Plan (steps)
1. `cd console && npm install && npm run dev` (backend: `make run`). Open http://localhost:5173.
2. RoleSwitcher using `DEMO_USERS`; keep the selected user in React state.
3. CaseList: fetch summaries, render rows with BandBadge, title, amount (₹, Indian grouping via
   `toLocaleString("en-IN")`), status.
4. CaseView: TransactionCard → BandBadge + ReasonCodes → clearance steps → EvidenceList (filename,
   channel, first 12 chars of sha256).
5. Run `npm test` (vitest) — make the 12-row test pass.
6. Remove the `STUB(T06)` marker; run `make task T=T06`.

## Acceptance criteria
- All 12 fixtures render (vitest), each with a band badge.
- Components listed above exist; maker view has no score rendering.

## Test command
`make console-test` and `make task T=T06`

## Definition of Done
Both green, `make check` green, a screenshot in the PR, STATUS.md updated.

## Common mistakes
- Calling `http://127.0.0.1:8000` directly (CORS / port issues) — use `/api` (Vite proxy).
- Showing raw account numbers — they are already masked in titles; mask in the card with `••••1234`.
- Colour-only badges.
- Editing `types.ts` to make TypeScript happy — ask the leader instead.

## Hints and links
- Vite: https://vitejs.dev/guide/ · Tailwind v4 + Vite: https://tailwindcss.com/docs/installation/using-vite
- Testing Library: https://testing-library.com/docs/react-testing-library/intro/

## Agent plan (write yours here)
