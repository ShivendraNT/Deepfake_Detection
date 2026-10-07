// T06: transaction card — shown FIRST, before any band or reason.
// Accounts are masked here (••••1234): the maker never sees a full number in the UI.
import type { PaymentAction } from "../types";

interface TransactionCardProps {
  txn: PaymentAction | null;
}

function mask(account: string | null): string {
  if (!account) return "—";
  return `••••${account.slice(-4)}`;
}

function money(inr: number): string {
  return `₹${inr.toLocaleString("en-IN")}`;
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="text-sm text-slate-900 dark:text-slate-100">{value}</dd>
    </div>
  );
}

export function TransactionCard({ txn }: TransactionCardProps) {
  if (!txn) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900">
        No transaction attached to this case.
      </div>
    );
  }

  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900 sm:grid-cols-3">
      <Field label="Amount" value={money(txn.amount_inr)} />
      <Field label="Rail" value={txn.rail} />
      <Field label="Beneficiary" value={txn.beneficiary_name} />
      <Field label="Account (masked)" value={mask(txn.account_number)} />
      <Field label="IFSC" value={txn.ifsc ?? "—"} />
      <Field label="UPI id" value={txn.upi_id ?? "—"} />
      <Field label="Beneficiary bank" value={txn.beneficiary_bank ?? "—"} />
      <Field label="Paid from (masked)" value={txn.debit_account_masked || "—"} />
      <Field label="Vendor id" value={txn.vendor_id ?? "—"} />
      <Field label="Bank-shown payee" value={txn.bank_shown_payee_name ?? "—"} />
      <Field label="UTR" value={txn.utr ?? "not sent yet"} />
      <Field label="Created" value={new Date(txn.created_at).toLocaleString("en-IN")} />
    </dl>
  );
}

export default TransactionCard;
