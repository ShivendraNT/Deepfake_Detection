// T06: evidence list — fingerprint first (sha256), before anyone opens the file.
import type { Evidence } from "../types";

interface EvidenceListProps {
  evidence: Evidence[];
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-IN");
}

export function EvidenceList({ evidence }: EvidenceListProps) {
  if (evidence.length === 0) {
    return (
      <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900">
        No evidence captured yet.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-700 dark:bg-slate-900">
      {evidence.map((e) => (
        <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
          <div className="min-w-0">
            <p className="truncate text-sm text-slate-900 dark:text-slate-100">
              {e.filename ?? e.media_type}
            </p>
            <p className="text-xs text-slate-500">
              {e.channel} · {e.media_type} · {(e.size_bytes / 1024).toFixed(1)} KB ·{" "}
              {when(e.captured_at)}
            </p>
          </div>
          <code className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            sha256 {e.sha256.slice(0, 12)}…
          </code>
        </li>
      ))}
    </ul>
  );
}

export default EvidenceList;
