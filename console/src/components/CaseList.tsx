// T06: left pane — the case queue for the signed-in demo user.
import { useEffect, useState } from "react";
import { api } from "../api";
import type { CaseSummary, DemoUser } from "../types";
import { BandBadge } from "./BandBadge";

interface CaseListProps {
  user: DemoUser;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function money(inr: number | null): string {
  return inr === null ? "—" : `₹${inr.toLocaleString("en-IN")}`;
}

export function CaseList({ user, selectedId, onSelect }: CaseListProps) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .listCases(user)
      .then((rows) => {
        if (alive) setCases(rows);
      })
      .catch((e: unknown) => {
        if (alive) setError(String(e));
      });
    return () => {
      alive = false;
    };
  }, [user]);

  if (error) return <p className="p-4 text-sm text-red-700">Could not load cases: {error}</p>;
  if (cases.length === 0)
    return <p className="p-4 text-sm text-slate-500">No cases for this user.</p>;

  return (
    <ul className="divide-y divide-slate-200 overflow-auto rounded-lg border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-700 dark:bg-slate-900">
      {cases.map((c) => (
        <li key={c.id}>
          <button
            type="button"
            data-testid="case-row"
            onClick={() => onSelect(c.id)}
            aria-current={selectedId === c.id ? "true" : undefined}
            className={`flex w-full flex-col gap-1 px-3 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800 ${
              selectedId === c.id ? "bg-sky-50 dark:bg-slate-800" : ""
            }`}
          >
            <span className="flex items-center justify-between gap-2">
              <BandBadge band={c.band} />
              <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                {money(c.amount_inr)}
              </span>
            </span>
            <span className="text-sm text-slate-800 dark:text-slate-200">{c.title}</span>
            <span className="flex items-center justify-between gap-2 text-xs text-slate-500">
              <span>{c.id}</span>
              <span>{c.status}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default CaseList;
