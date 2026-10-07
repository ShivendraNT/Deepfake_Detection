// T06: band badge — colour AND the word, never colour alone (accessibility).
import type { Band } from "../types";

const STYLES: Record<Band, string> = {
  PASS: "border-green-300 bg-green-100 text-green-800",
  VERIFY: "border-amber-300 bg-amber-100 text-amber-900",
  HOLD: "border-red-300 bg-red-100 text-red-800",
};

const MARK: Record<Band, string> = { PASS: "✓", VERIFY: "!", HOLD: "✕" };

interface BandBadgeProps {
  band?: Band | null;
  className?: string;
}

export function BandBadge({ band, className = "" }: BandBadgeProps) {
  if (!band) {
    return (
      <span
        data-testid="band-badge"
        className={`inline-flex items-center gap-1 border border-slate-300 bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600 ${className}`}
      >
        NO DECISION
      </span>
    );
  }
  return (
    <span
      data-testid="band-badge"
      className={`inline-flex items-center gap-1 border px-2 py-0.5 text-xs font-semibold ${STYLES[band]} ${className}`}
    >
      <span aria-hidden="true">{MARK[band]}</span>
      {band}
    </span>
  );
}

export default BandBadge;
