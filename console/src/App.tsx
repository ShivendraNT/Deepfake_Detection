// Payment Verification Desk — top-level layout (T06).
// RoleSwitcher (top bar) + CaseList (left) + CaseView (right).
// CaseView order: TransactionCard FIRST, then BandBadge + ReasonCodes, then clearance steps,
// then EvidenceList. Makers never see scores (the server already strips them; do not
// render a score unless canSeeScores(role)).
// Spec: docs/tasks/T06-console-ui.md
import { useState } from "react";
import { DEMO_USERS } from "./api";
import type { DemoUser } from "./types";
import { CaseList } from "./components/CaseList";
import { CaseView } from "./components/CaseView";
import { OobInbox } from "./components/OobInbox";
import { RoleSwitcher } from "./components/RoleSwitcher";

export default function App() {
  const [user, setUser] = useState<DemoUser>(DEMO_USERS[0].user);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <div className="flex min-h-screen flex-col bg-slate-100 font-sans text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 shadow-xs dark:border-slate-800 dark:bg-slate-900">
        <div>
          <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Payment Verification Desk
          </h1>
          <p className="text-xs text-slate-500">
            Satyapan — evidence can only raise the band
          </p>
        </div>
        <RoleSwitcher user={user} onChange={setUser} />
      </header>

      <main className="grid flex-1 gap-4 p-4 md:grid-cols-[minmax(18rem,24rem)_minmax(0,1fr)]">
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-500">
            Cases
          </h2>
          <CaseList user={user} selectedId={selectedId} onSelect={setSelectedId} />
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-500">
            Case Details
          </h2>
          <OobInbox user={user} />
          <div className="mt-4">
            <CaseView user={user} caseId={selectedId} />
          </div>
        </section>
      </main>
    </div>
  );
}
