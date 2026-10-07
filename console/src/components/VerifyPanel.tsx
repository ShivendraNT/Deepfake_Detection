// T13: verification actions — log a callback on the TRUSTED number, then Clear / Status /
// security-ack per role. The trusted number always comes from the vendor master or the
// employee directory (decision.clearance.callback_number); NEVER from the message, document
// or call, even if the caller claims to be the bank.
import { useState } from "react";
import { api } from "../api";
import type { Band, Case, CaseStatus, DemoUser, Role } from "../types";

interface VerifyPanelProps {
  user: DemoUser;
  caseItem: Case;
  onChanged: (updated: Case) => void;
}

const OUTCOMES = ["CONFIRMED", "DENIED", "NO_ANSWER"] as const;
type Outcome = (typeof OUTCOMES)[number];

// Mirrors satyapan.policy.permissions.can_clear (the server is still the authority).
function canClear(role: Role, band: Band): boolean {
  if (role === "checker") return true;
  if (role === "maker") return band === "PASS" || band === "VERIFY";
  if (role === "security") return band === "PASS";
  return false;
}

export function VerifyPanel({ user, caseItem, onChanged }: VerifyPanelProps) {
  const clearance = caseItem.decision?.clearance;
  const [numberDialed, setNumberDialed] = useState(clearance?.callback_number ?? "");
  const [outcome, setOutcome] = useState<Outcome>("CONFIRMED");
  const [payee, setPayee] = useState(caseItem.txn?.bank_shown_payee_name ?? "");
  const [confirmedBy, setConfirmedBy] = useState("");
  const [notes, setNotes] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const role = user.role;
  if (role === "requester" || role === "system") return null;

  const band = caseItem.decision?.band;
  const clearable = band !== undefined && canClear(role, band);
  const canAck = role === "security";
  const canSetFraud = role === "checker" || role === "security";
  const canReopen = role === "checker" || role === "security";
  const finalFraud = caseItem.status === "CONFIRMED_FRAUD";

  async function run(label: string, action: () => Promise<Case>) {
    setBusy(true);
    try {
      const updated = await action();
      setMsg(`${label} — OK`);
      onChanged(updated);
    } catch (e: unknown) {
      setMsg(`${label} failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function logCallback(e: React.FormEvent) {
    e.preventDefault();
    await run("Callback", () =>
      api.addCallback(user, caseItem.id, {
        number_dialed: numberDialed,
        outcome,
        confirmed_by_name: confirmedBy || null,
        bank_shown_payee_name: payee || null,
        notes,
      }),
    );
  }

  const last = caseItem.callbacks[caseItem.callbacks.length - 1] as
    | { outcome?: string; performed_as?: string }
    | undefined;

  return (
    <section
      aria-labelledby="verify-actions-heading"
      data-testid="verify-panel"
      className="space-y-4 rounded-lg border border-slate-200 bg-slate-50/70 p-5 dark:border-slate-800 dark:bg-slate-800/60"
    >
      <div className="flex items-center justify-between">
        <h3
          id="verify-actions-heading"
          className="text-xs font-bold uppercase tracking-wider text-slate-500"
        >
          Verification actions
        </h3>
        <span className="text-xs text-slate-500">
          {caseItem.callbacks.length} callback(s)
          {last?.outcome ? ` · last: ${last.outcome} by ${last.performed_as ?? "?"}` : ""}
        </span>
      </div>

      {/* Trusted number: the only number anyone may call back on */}
      <div className="rounded border border-blue-200 bg-blue-50 p-3 dark:border-blue-800/60 dark:bg-blue-950/40">
        <span className="block text-xs font-semibold text-blue-900 dark:text-blue-200">
          Trusted callback number (from {clearance?.callback_number_source ?? "vendor master"})
        </span>
        <span className="font-mono text-sm font-bold text-blue-700 dark:text-blue-300">
          {clearance?.callback_number ?? "No trusted number on file — get one from KYC records"}
        </span>
        <span className="mt-1 block text-[11px] text-blue-700 dark:text-blue-300">
          Never use a number from the message, document or call — even if the caller says they are
          the bank.
        </span>
      </div>

      {/* Callback form */}
      <form onSubmit={logCallback} className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs text-slate-600 dark:text-slate-300">
          Number dialed
          <input
            value={numberDialed}
            onChange={(e) => setNumberDialed(e.target.value)}
            placeholder="+91-00000-10001"
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 font-mono text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
        <label className="block text-xs text-slate-600 dark:text-slate-300">
          Outcome
          <select
            value={outcome}
            onChange={(e) => setOutcome(e.target.value as Outcome)}
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {OUTCOMES.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-xs text-slate-600 dark:text-slate-300">
          Name the bank shows for the payee
          <input
            value={payee}
            onChange={(e) => setPayee(e.target.value)}
            placeholder="Narmada Demo Logistics LLP"
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
        <label className="block text-xs text-slate-600 dark:text-slate-300">
          Who confirmed (name)
          <input
            value={confirmedBy}
            onChange={(e) => setConfirmedBy(e.target.value)}
            placeholder="Accounts head"
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
        <label className="block text-xs text-slate-600 sm:col-span-2 dark:text-slate-300">
          Notes
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
        <button
          type="submit"
          disabled={busy || !numberDialed}
          className="justify-self-start rounded bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          Log callback
        </button>
      </form>

      {/* Status buttons per role */}
      <div className="flex flex-wrap gap-2">
        {clearable && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void run("Clear", () => api.clearCase(user, caseItem.id))}
            className="rounded border border-green-300 bg-green-100 px-3 py-1.5 text-sm font-semibold text-green-800 disabled:opacity-50"
          >
            Clear case
          </button>
        )}
        {canAck && !caseItem.security_acknowledged_by && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void run("Security ack", () => api.securityAck(user, caseItem.id))}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
          >
            Acknowledge (security)
          </button>
        )}
        {canSetFraud && (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void run("Suspected fraud", () =>
                api.setCaseStatus(user, caseItem.id, "SUSPECTED_FRAUD" as CaseStatus),
              )
            }
            className="rounded border border-amber-300 bg-amber-100 px-3 py-1.5 text-sm font-semibold text-amber-800 disabled:opacity-50"
          >
            Mark suspected fraud
          </button>
        )}
        {canSetFraud && (
          <button
            type="button"
            disabled={busy || finalFraud}
            onClick={() =>
              void run("Confirmed fraud", () =>
                api.setCaseStatus(user, caseItem.id, "CONFIRMED_FRAUD" as CaseStatus),
              )
            }
            className="rounded border border-red-300 bg-red-100 px-3 py-1.5 text-sm font-semibold text-red-800 disabled:opacity-50"
          >
            Confirm fraud (final)
          </button>
        )}
        {canReopen && (
          <button
            type="button"
            disabled={busy || finalFraud}
            onClick={() =>
              void run("Reopen", () => api.setCaseStatus(user, caseItem.id, "OPEN" as CaseStatus))
            }
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
          >
            Reopen
          </button>
        )}
      </div>

      {msg && (
        <p
          data-testid="verify-feedback"
          className={`text-sm ${msg.endsWith("— OK") ? "text-green-700" : "text-red-700"}`}
        >
          {msg}
        </p>
      )}
    </section>
  );
}

export default VerifyPanel;
