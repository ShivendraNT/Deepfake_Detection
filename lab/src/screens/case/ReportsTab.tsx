import { AnimatePresence, motion } from "framer-motion";
import { Braces, CheckSquare, ExternalLink, FileText, Loader2, ScrollText, Square, Stamp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError, urls, type CaseView, type ReportRecord } from "../../api";
import { CopyButton, cx, EmptyState, ExhibitBadge, ToneBadge } from "../../components/ui";
import { useToast } from "../../context";
import { formatBytes, formatIST, shortHash } from "../../lib/format";
import { evidenceMeta, isPending } from "../../lib/verdict";

function ReportCard({ r, active, onPreview }: { r: ReportRecord; active: boolean; onPreview: () => void }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cx("panel-tight p-4 transition", active && "border-accent/40 shadow-glow")}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-emerald-400/30 bg-emerald-500/10 text-emerald-300">
            <FileText className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="truncate font-mono text-sm font-semibold text-white">{r.id}</div>
            <div className="text-2xs text-slate-500">
              {formatIST(r.created_at)} IST · {formatBytes(r.size_bytes)}
            </div>
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          <button type="button" className={cx("btn-sm", active ? "btn-secondary" : "btn-ghost")} onClick={onPreview}>
            Preview
          </button>
          <a className="btn-secondary btn-sm" href={urls.reportPdf(r.id)} target="_blank" rel="noreferrer">
            Open PDF <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-[88px_1fr] gap-x-2 gap-y-1 text-xs">
        <span className="text-slate-500">Examiner</span>
        <span className="truncate text-slate-300">
          {r.examiner || "—"}
          {r.designation ? <span className="text-slate-500"> · {r.designation}</span> : null}
        </span>
        <span className="text-slate-500">Exhibits</span>
        <span className="flex flex-wrap gap-1">
          {r.exhibits.map((x) => (
            <ExhibitBadge key={x} exhibit={x} size="sm" />
          ))}
        </span>
        <span className="text-slate-500">PDF SHA-256</span>
        <span className="flex min-w-0 items-center gap-1">
          <span className="truncate font-mono text-2xs text-accent-soft" title={r.sha256}>
            {shortHash(r.sha256, 16, 10)}
          </span>
          <CopyButton text={r.sha256} />
        </span>
      </div>
    </motion.div>
  );
}

export function ReportsTab({ view, onChanged }: { view: CaseView; onChanged: () => void }) {
  const { push } = useToast();
  const [examiner, setExaminer] = useState(view.case.examiner);
  const [designation, setDesignation] = useState("");
  const [notes, setNotes] = useState("");
  const [selected, setSelected] = useState<Set<string>>(() => new Set(view.evidence.map((e) => e.id)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(view.reports[0]?.id ?? null);
  const [extra, setExtra] = useState<ReportRecord[]>([]);

  // New exhibits are selected by default.
  const ids = view.evidence.map((e) => e.id).join(",");
  useEffect(() => {
    setSelected((cur) => {
      const next = new Set(cur);
      for (const e of view.evidence) if (!next.has(e.id) && !cur.size) next.add(e.id);
      return next.size ? next : new Set(view.evidence.map((e) => e.id));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids]);

  const reports = useMemo(() => {
    const seen = new Set(view.reports.map((r) => r.id));
    return [...extra.filter((r) => !seen.has(r.id)), ...view.reports];
  }, [view.reports, extra]);
  const pending = view.evidence.filter((e) => selected.has(e.id) && isPending(e.status)).length;
  const allOn = selected.size === view.evidence.length && view.evidence.length > 0;

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const ordered = view.evidence.filter((e) => selected.has(e.id)).map((e) => e.id);
      const rec = await api.makeReport(view.case.id, { evidence_ids: ordered, examiner, designation, notes });
      setExtra((x) => [rec, ...x]);
      setPreview(rec.id);
      push({ tone: "success", title: "Court report generated", body: `${rec.id} · SHA-256 ${shortHash(rec.sha256)} recorded in the custody log.` });
      onChanged();
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : String(e);
      setError(msg);
      push({ tone: "error", title: "Report failed", body: msg });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
      <div className="space-y-5">
        <div className="panel p-5">
          <h3 className="panel-title">
            <Stamp className="h-4 w-4 text-accent" /> Examination report
          </h3>
          <p className="mt-1.5 text-xs leading-relaxed text-slate-500">
            A signed-hash PDF with the methodology, each technique’s findings and limits, the evaluative statements and the full
            custody log. Generating it is itself recorded in the custody chain.
          </p>
          <div className="mt-4 space-y-3.5">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label" htmlFor="rep-examiner">
                  Examiner
                </label>
                <input id="rep-examiner" className="input" placeholder="Dr. A. Rao" value={examiner} onChange={(e) => setExaminer(e.target.value)} />
              </div>
              <div>
                <label className="label" htmlFor="rep-designation">
                  Designation
                </label>
                <input
                  id="rep-designation"
                  className="input"
                  placeholder="Scientific Officer (Cyber)"
                  value={designation}
                  onChange={(e) => setDesignation(e.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="label" htmlFor="rep-notes">
                Examiner’s notes
              </label>
              <textarea
                id="rep-notes"
                className="input min-h-[76px] resize-y"
                placeholder="Exhibits received in sealed condition; seals intact and matched with the forwarding letter."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="label mb-0">Exhibits in the report</span>
                <button
                  type="button"
                  className="text-2xs text-accent-soft hover:text-white"
                  onClick={() => setSelected(allOn ? new Set() : new Set(view.evidence.map((e) => e.id)))}
                >
                  {allOn ? "Select none" : "Select all"}
                </button>
              </div>
              <ul className="max-h-[280px] space-y-1 overflow-y-auto rounded-lg border border-white/[0.06] bg-ink-950/40 p-1.5">
                {view.evidence.length === 0 && <li className="p-3 text-xs text-slate-500">No exhibits in this case.</li>}
                {view.evidence.map((e) => {
                  const on = selected.has(e.id);
                  return (
                    <li key={e.id}>
                      <button
                        type="button"
                        onClick={() =>
                          setSelected((cur) => {
                            const n = new Set(cur);
                            if (n.has(e.id)) n.delete(e.id);
                            else n.add(e.id);
                            return n;
                          })
                        }
                        className={cx(
                          "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left transition",
                          on ? "bg-accent/[0.07]" : "hover:bg-white/[0.04]",
                        )}
                      >
                        {on ? <CheckSquare className="h-4 w-4 shrink-0 text-accent" /> : <Square className="h-4 w-4 shrink-0 text-slate-600" />}
                        <ExhibitBadge exhibit={e.exhibit} role={e.role} size="sm" />
                        <span className="min-w-0 flex-1 truncate text-xs text-slate-300">{e.filename}</span>
                        <ToneBadge meta={evidenceMeta(e)} size="sm" />
                      </button>
                    </li>
                  );
                })}
              </ul>
              {pending > 0 && (
                <div className="mt-1.5 text-2xs text-amber-300/90">
                  {pending} selected exhibit(s) are still being analysed; the report will show their current state.
                </div>
              )}
            </div>
            {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</div>}
            <button type="button" className="btn-primary w-full" disabled={busy || selected.size === 0} onClick={() => void generate()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScrollText className="h-4 w-4" />}
              {busy ? "Compiling report and sealing its hash…" : `Generate court report (${selected.size} exhibit${selected.size === 1 ? "" : "s"})`}
            </button>
          </div>
        </div>
        <div className="panel flex items-center justify-between gap-3 p-4">
          <div>
            <div className="text-sm font-medium text-slate-200">Machine-readable export</div>
            <div className="text-2xs text-slate-500">Case, exhibits, every analysis, links and the custody log as JSON.</div>
          </div>
          <a className="btn-secondary btn-sm" href={urls.exportJson(view.case.id)} download={`${view.case.id}_export.json`}>
            <Braces className="h-3.5 w-3.5" /> Export case JSON
          </a>
        </div>
      </div>

      <div className="space-y-5">
        {reports.length === 0 ? (
          <div className="panel">
            <EmptyState
              title="No reports yet"
              body="Generate the examination report when the analyses are complete. Each report gets its own SHA-256, printed with a verification QR code."
            />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 2xl:grid-cols-2">
              <AnimatePresence initial={false}>
                {reports.map((r) => (
                  <ReportCard key={r.id} r={r} active={preview === r.id} onPreview={() => setPreview(r.id)} />
                ))}
              </AnimatePresence>
            </div>
            {preview && (
              <div className="panel overflow-hidden">
                <div className="flex items-center justify-between border-b hairline px-4 py-2.5">
                  <div className="flex items-center gap-2 text-sm text-slate-300">
                    <FileText className="h-4 w-4 text-accent" /> Preview · <span className="font-mono text-xs">{preview}.pdf</span>
                  </div>
                  <a className="btn-ghost btn-sm" href={urls.reportPdf(preview)} target="_blank" rel="noreferrer">
                    Open in new tab <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                <iframe key={preview} title={`Report ${preview}`} src={`${urls.reportPdf(preview)}#view=FitH`} className="h-[78vh] w-full bg-white" />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
