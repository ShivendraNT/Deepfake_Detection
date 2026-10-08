// T06: right pane — one case, ordered per the spec:
// TransactionCard FIRST, then BandBadge + ReasonCodes, then clearance steps, then EvidenceList.
// Makers never see scores: any score rendering is gated by canSeeScores(role).
import React, { useEffect, useState } from "react";
import { api } from "../api";
import type { Case, DemoUser, Role } from "../types";
import { BandBadge } from "./BandBadge";
import { EvidenceList } from "./EvidenceList";
import { ReasonCodes } from "./ReasonCodes";
import { TransactionCard } from "./TransactionCard";
import { VerifyPanel } from "./VerifyPanel";

interface CaseViewProps {
  user?: DemoUser;
  caseId?: string | null;
  caseItem?: Case | null;
  currentRole?: Role;
  loading?: boolean;
}

export function canSeeScores(role: Role): boolean {
  return role === "checker" || role === "security";
}

export function CaseView({
  user,
  caseId,
  caseItem: propCaseItem,
  currentRole: propRole,
  loading: propLoading,
}: CaseViewProps) {
  const [fetchedCase, setFetchedCase] = useState<Case | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshTick, setRefreshTick] = useState<number>(0);

  const activeRole: Role = propRole || user?.role || "maker";

  useEffect(() => {
    if (propCaseItem !== undefined || !user || !caseId) {
      setFetchedCase(null);
      return;
    }

    let active = true;
    setLoading(true);

    api
      .getCase(user, caseId)
      .then((data) => {
        if (!active) return;
        setFetchedCase(data && !Array.isArray(data) ? data : null);
      })
      .catch((err) => {
        console.error("Failed to load case detail:", err);
        if (active) setFetchedCase(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [user, caseId, propCaseItem, refreshTick]);

  const currentCase = propCaseItem !== undefined ? propCaseItem : fetchedCase;
  const isLoading = propLoading !== undefined ? propLoading : loading;

  if (isLoading) {
    return (
      <div className="animate-pulse rounded-lg border border-slate-200 bg-white p-12 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900">
        Loading case details…
      </div>
    );
  }

  if (!currentCase) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-12 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900">
        Select a case from the list on the left to inspect verification details.
      </div>
    );
  }

  const decision = currentCase.decision;
  const clearance = decision?.clearance;
  const showScores = canSeeScores(activeRole);

  return (
    <div className="max-w-4xl space-y-6 rounded-lg border border-slate-200 bg-white p-6 shadow-xs dark:border-slate-800 dark:bg-slate-900">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-slate-400">{currentCase.id}</span>
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              {currentCase.kind}
            </span>
            <span className="text-xs capitalize text-slate-400">
              Status: {currentCase.status.toLowerCase().replace(/_/g, " ")}
            </span>
          </div>
          <h2 className="mt-1 text-xl font-bold text-slate-900 dark:text-slate-100">
            {currentCase.title}
          </h2>
        </div>

        <div>
          <BandBadge band={decision?.band} />
        </div>
      </div>

      {/* 1. Transaction Card FIRST */}
      <section aria-labelledby="transaction-heading">
        <h3
          id="transaction-heading"
          className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400"
        >
          1. Transaction Summary
        </h3>
        <TransactionCard txn={currentCase.txn} />
      </section>

      {/* 2. Band Badge & Reason Codes */}
      <section
        aria-labelledby="risk-reasons-heading"
        className="space-y-3 rounded-lg border border-slate-200 bg-slate-50/70 p-5 dark:border-slate-700 dark:bg-slate-800/60"
      >
        <div className="flex items-center justify-between">
          <h3
            id="risk-reasons-heading"
            className="text-xs font-bold uppercase tracking-wider text-slate-400"
          >
            2. Risk Band &amp; Reason Codes
          </h3>
          <BandBadge band={decision?.band} />
        </div>
        <ReasonCodes
          reasonCodes={decision?.reason_codes || []}
          infoCodes={decision?.info_codes || []}
        />
      </section>

      {/* 3. Clearance Steps */}
      {clearance && (
        <section
          aria-labelledby="clearance-heading"
          className="space-y-3 rounded-lg border border-slate-200 bg-slate-50/70 p-5 dark:border-slate-700 dark:bg-slate-800/60"
        >
          <h3
            id="clearance-heading"
            className="text-xs font-bold uppercase tracking-wider text-slate-400"
          >
            3. Required Clearance Steps
          </h3>

          <div className="space-y-2 text-xs">
            {clearance.callback_number && (
              <div className="rounded border border-blue-200 bg-blue-50 p-3 dark:border-blue-800/60 dark:bg-blue-950/40">
                <span className="block font-semibold text-blue-900 dark:text-blue-200">
                  Call back on (from vendor master)
                </span>
                <span className="text-sm font-bold text-blue-700 dark:text-blue-300">
                  {clearance.callback_number}
                </span>
                {clearance.callback_number_source && (
                  <span className="mt-0.5 block text-[11px] text-blue-600 dark:text-blue-400">
                    Source: {clearance.callback_number_source}
                  </span>
                )}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 text-slate-600 dark:text-slate-300">
              <div>
                <span className="block font-semibold text-slate-500">Authorized roles:</span>
                <span className="font-mono">{clearance.who.join(", ") || "checker"}</span>
              </div>
              <div>
                <span className="block font-semibold text-slate-500">
                  Required verification methods:
                </span>
                <span>{clearance.methods.join(", ") || "out-of-band callback"}</span>
              </div>
            </div>

            {clearance.notes.length > 0 && (
              <ul className="list-disc pl-5 text-slate-600 dark:text-slate-300">
                {clearance.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}

      {/* 3b. Verification actions (T13): callback form + Clear / Status per role */}
      {user && (
        <VerifyPanel
          key={currentCase.id}
          user={user}
          caseItem={currentCase}
          onChanged={() => {
            if (propCaseItem === undefined) setRefreshTick((t) => t + 1);
          }}
        />
      )}

      {/* 4. Evidence List */}
      <section aria-labelledby="evidence-heading">
        <h3
          id="evidence-heading"
          className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400"
        >
          4. Fingerprinted Evidence ({currentCase.evidence?.length || 0})
        </h3>
        <EvidenceList evidence={currentCase.evidence || []} />
      </section>

      {/* 5. Detection Signals — scores only for checker/security */}
      {currentCase.signals && currentCase.signals.length > 0 && (
        <section
          aria-labelledby="signals-heading"
          className="space-y-3 rounded-lg border border-slate-200 bg-slate-50/70 p-5 dark:border-slate-700 dark:bg-slate-800/60"
        >
          <h3
            id="signals-heading"
            className="text-xs font-bold uppercase tracking-wider text-slate-400"
          >
            5. Detection Signals ({currentCase.signals.length})
          </h3>
          <div className="divide-y divide-slate-100 text-xs dark:divide-slate-800">
            {currentCase.signals.map((sig) => (
              <div key={sig.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                      {sig.code}
                    </span>
                    <span className="rounded bg-slate-100 px-1 text-[10px] font-semibold uppercase text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                      {sig.detector}
                    </span>
                    <span className="text-[10px] text-slate-400">{sig.strength}</span>
                  </div>
                  <span className="text-[11px] text-slate-500">Source: {sig.source}</span>
                </div>

                {showScores && sig.score != null && (
                  <div className="text-right">
                    <span className="block text-[10px] text-slate-400">Score</span>
                    <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                      {sig.score.toFixed(3)}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default CaseView;
