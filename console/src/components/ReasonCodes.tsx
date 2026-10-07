// T06: reason codes behind the band. Plain words, no scores (makers see this too).
interface ReasonCodesProps {
  reasonCodes: string[];
  infoCodes?: string[];
}

function plain(code: string): string {
  return code.replace(/_/g, " ").toLowerCase();
}

export function ReasonCodes({ reasonCodes, infoCodes = [] }: ReasonCodesProps) {
  if (reasonCodes.length === 0 && infoCodes.length === 0) {
    return <p className="text-sm text-slate-500">No reason codes on this decision.</p>;
  }

  return (
    <div className="space-y-2">
      {reasonCodes.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {reasonCodes.map((code) => (
            <li
              key={code}
              title={plain(code)}
              className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-900 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-200"
            >
              <span className="font-mono">{code}</span>
            </li>
          ))}
        </ul>
      )}

      {infoCodes.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {infoCodes.map((code) => (
            <li
              key={code}
              title={plain(code)}
              className="rounded border border-slate-300 bg-slate-100 px-2 py-1 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            >
              <span className="font-mono">{code}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="text-xs text-slate-500">
        Evidence can raise the band, never lower it. Clear only through the steps below.
      </p>
    </div>
  );
}

export default ReasonCodes;
