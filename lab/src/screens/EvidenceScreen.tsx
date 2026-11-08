import { motion } from "framer-motion";
import { AlertTriangle, ChevronRight, Download, History, Loader2, Microscope, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, urls, type EvidenceAnalysis, type EvidenceView } from "../api";
import { LiveAnalysis, StageChecklist } from "../components/LiveScan";
import { Lightbox, type LightboxItem } from "../components/Modal";
import { cx, EmptyState, ErrorState, ExhibitBadge, LoadingState, MediaIcon, RoleChip, SectionTitle, ToneBadge } from "../components/ui";
import { useLab, useToast } from "../context";
import { formatBytes, formatDurationMs, formatIST } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { linksFor } from "../lib/links";
import { mediaFacts } from "../lib/media";
import { useEvidenceStream } from "../lib/sse";
import { buildStageRows, expectedTechniques, isDone, type StageRow } from "../lib/stages";
import { evidenceMeta, isPending } from "../lib/verdict";
import { DataTable } from "./evidence/DataViews";
import { ImageViewer } from "./evidence/ImageViewer";
import { AudioViewer, VideoViewer } from "./evidence/MediaViewers";
import { IntegrityPanel, ProvenancePanel, RelatedPanel, VerdictPanel } from "./evidence/Panels";
import { TechniqueAccordion } from "./evidence/Techniques";

/** Checklist rows rebuilt from the stored results (always available, even after a restart). */
function rowsFromAnalysis(a: EvidenceAnalysis): StageRow[] {
  return a.techniques.map((t) => ({
    stage: t.id,
    label: t.name,
    status: t.status,
    message: t.summary,
    isTechnique: true,
    category: t.category,
    startedAt: null,
    endedAt: null,
    durationMs: t.duration_ms,
    sub: null,
  }));
}

function ExaminationLog({ view, techIndex }: { view: EvidenceView; techIndex: ReturnType<typeof useLab>["techIndex"] }) {
  const [open, setOpen] = useState(false);
  const a = view.analysis;
  if (!a) return null;
  const fromEvents = view.events.length > 0 && isDone(view.events);
  const rows = fromEvents ? buildStageRows(view.events, techIndex) : rowsFromAnalysis(a);
  const total = a.techniques.reduce((s, t) => s + t.duration_ms, 0);
  return (
    <div className="panel">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3 px-5 py-3.5 text-left">
        <History className="h-4 w-4 text-accent" />
        <span className="panel-title">Examination log</span>
        <span className="text-xs text-slate-500">
          {rows.length} steps · {formatDurationMs(total)} · started {formatIST(a.started_at)} IST
        </span>
        <ChevronRight className={cx("ml-auto h-4 w-4 text-slate-500 transition", open && "rotate-90")} />
      </button>
      {open && (
        <div className="border-t hairline px-3 py-3">
          <StageChecklist rows={rows} compact />
          {!fromEvents && <div className="px-2 pt-2 text-2xs text-slate-600">Rebuilt from the stored results (live event stream not retained).</div>}
        </div>
      )}
    </div>
  );
}

export function EvidenceScreen() {
  const { evidenceId = "" } = useParams();
  const { setActiveCaseId, techniques, techIndex, bumpCustody } = useLab();
  const { push } = useToast();
  const view = useAsync(() => api.evidence(evidenceId), evidenceId);
  const ev = view.data?.evidence ?? null;
  const caseId = ev?.case_id ?? null;
  useEffect(() => {
    if (caseId) setActiveCaseId(caseId);
    return () => setActiveCaseId(null);
  }, [caseId, setActiveCaseId]);
  const caseView = useAsync(() => api.caseView(caseId ?? ""), caseId ?? "none", { enabled: !!caseId });

  const pending = isPending(ev?.status);
  const [polling, setPolling] = useState(false);
  const reload = view.reload;
  const onDone = useCallback(() => {
    void reload();
    bumpCustody();
  }, [reload, bumpCustody]);
  const stream = useEvidenceStream(evidenceId, pending && !polling, onDone);

  // The SSE stream replays from the start and stops at the first "done"; after a re-analysis it
  // can end while the item is still pending, so fall back to polling the evidence record.
  useEffect(() => {
    if (!pending) {
      setPolling(false);
      return;
    }
    if (stream.state === "error" || (stream.state === "done" && pending)) setPolling(true);
  }, [pending, stream.state]);
  useEffect(() => {
    if (!pending || !polling) return;
    const t = window.setInterval(() => void reload(), 1200);
    return () => window.clearInterval(t);
  }, [pending, polling, reload]);

  // When the analysis finishes, refresh custody + case data.
  const wasPending = useRef(false);
  useEffect(() => {
    if (wasPending.current && !pending && ev) {
      bumpCustody();
      void caseView.reload();
      push({
        tone: ev.status === "error" ? "error" : "success",
        title: ev.status === "error" ? `${ev.exhibit}: analysis failed` : `${ev.exhibit}: examination complete`,
        body: ev.headline ?? undefined,
      });
    }
    wasPending.current = pending;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);

  const [openTech, setOpenTech] = useState<Set<string>>(new Set());
  const [lightbox, setLightbox] = useState<LightboxItem[] | null>(null);
  const [busy, setBusy] = useState(false);

  // Open the techniques that produced evidential findings by default.
  const analysis = view.data?.analysis ?? null;
  const analysisKey = analysis ? `${analysis.evidence_id}:${analysis.finished_at ?? analysis.started_at}` : "";
  useEffect(() => {
    if (!analysis) return;
    setOpenTech(new Set(analysis.techniques.filter((t) => t.findings.some((f) => f.hypothesis !== "neutral" && f.strength > 0)).map((t) => t.id)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisKey]);

  const focusFinding = useCallback(
    (code: string) => {
      const t = analysis?.techniques.find((x) => x.findings.some((f) => f.code === code));
      if (!t) return;
      setOpenTech((s) => new Set([...s, t.id]));
      window.setTimeout(() => document.getElementById(`tech-${t.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    },
    [analysis],
  );

  const reanalyse = async () => {
    if (!ev) return;
    setBusy(true);
    try {
      await api.reanalyze(ev.id);
      push({ tone: "info", title: `${ev.exhibit} queued for re-analysis`, body: "The stored original is re-hashed before every run." });
      setPolling(false);
      await reload();
    } catch (e) {
      push({ tone: "error", title: "Could not queue re-analysis", body: e instanceof ApiError ? e.detail : String(e) });
    } finally {
      setBusy(false);
    }
  };

  const byId = useMemo(() => new Map((caseView.data?.evidence ?? []).map((e) => [e.id, e])), [caseView.data]);
  const related = useMemo(() => (ev ? linksFor(ev.id, [...(view.data?.links ?? []), ...(caseView.data?.links ?? [])]) : []), [ev, view.data, caseView.data]);
  const expected = useMemo(() => (ev ? expectedTechniques(techniques, ev.kind) : []), [techniques, ev]);

  if (view.error && !view.data) {
    return (
      <div className="panel">
        <ErrorState error={view.error} onRetry={() => void view.reload()} />
        <div className="pb-8 text-center">
          <Link to="/" className="link text-sm">
            Back to case files
          </Link>
        </div>
      </div>
    );
  }
  if (!view.data || !ev) return <LoadingState label="Loading exhibit…" />;

  const meta = evidenceMeta(ev);
  // A stream that already ended while the record is still pending replayed an older run.
  const streamStale = stream.state === "done" && pending;
  const liveEvents = polling || streamStale || !stream.events.length ? view.data.events : stream.events;
  const kind = analysis?.media.kind ?? ev.kind;
  const facts = mediaFacts(analysis);
  const c = caseView.data?.case;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-1.5 text-sm text-slate-500">
        <Link to="/" className="hover:text-white">
          Case files
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link to={`/cases/${ev.case_id}`} className="max-w-[420px] truncate hover:text-white">
          {c ? `${c.fir_number ? `${c.fir_number} · ` : ""}${c.title}` : "Case"}
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-slate-300">Exhibit {ev.exhibit}</span>
      </div>

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="panel overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(90deg, transparent, ${meta.hex}aa, transparent)` }} />
        <div className="flex flex-wrap items-center gap-5 p-5">
          <ExhibitBadge exhibit={ev.exhibit} role={ev.role} size="lg" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-xl font-semibold tracking-tight text-white" title={ev.filename}>
                {ev.filename}
              </h1>
              <RoleChip role={ev.role} />
              <ToneBadge meta={meta} pulse={pending} />
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
              <span className="inline-flex items-center gap-1.5 capitalize">
                <MediaIcon kind={kind} className="h-3.5 w-3.5 text-slate-500" /> {kind}
              </span>
              {facts.map((f) => (
                <span key={f} className="font-mono text-slate-400">
                  {f}
                </span>
              ))}
              <span className="font-mono">{formatBytes(ev.size_bytes)}</span>
              <span className="font-mono text-slate-500">{ev.mime}</span>
              {analysis?.media.extension_mismatch && (
                <span className="chip border-amber-400/30 bg-amber-500/10 text-amber-200" title="The file's bytes do not match its extension">
                  extension mismatch
                </span>
              )}
            </div>
            {ev.description && <p className="mt-1.5 max-w-3xl text-sm text-slate-400">{ev.description}</p>}
          </div>
          <div className="flex items-center gap-2">
            <a className="btn-secondary" href={urls.file(ev.id)} download={ev.filename}>
              <Download className="h-4 w-4" /> Download original
            </a>
            <button type="button" className="btn-secondary" disabled={pending || busy} onClick={() => void reanalyse()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />} Re-analyse
            </button>
          </div>
        </div>
        {ev.status === "error" && (
          <div className="flex items-start gap-2 border-t border-red-500/20 bg-red-500/[0.07] px-5 py-3 text-sm text-red-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{ev.headline || "The analysis failed."} Errors are never counted as “clean”; re-analyse or examine manually.</span>
          </div>
        )}
      </motion.div>

      {pending && (
        <LiveAnalysis
          ev={ev}
          events={liveEvents}
          techIndex={techIndex}
          expected={expected}
          connection={polling ? "polling" : stream.state}
        />
      )}
      {pending && analysis && (
        <div className="rounded-xl border border-amber-400/20 bg-amber-500/[0.05] px-4 py-2.5 text-xs text-amber-100/80">
          Showing the previous analysis below until the new run completes.
        </div>
      )}

      {analysis ? (
        <div className={cx("space-y-5", pending && "opacity-60")}>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
            <div className="min-w-0 space-y-5">
              <div className="panel p-5">
                <SectionTitle icon={<Microscope className="h-4 w-4" />} right={<span className="text-2xs text-slate-500">original, read-only copy</span>}>
                  {kind === "image" ? "Image examination" : kind === "audio" ? "Audio examination" : kind === "video" ? "Video examination" : "Exhibit"}
                </SectionTitle>
                {kind === "image" ? (
                  <ImageViewer ev={ev} analysis={analysis} />
                ) : kind === "audio" ? (
                  <AudioViewer ev={ev} analysis={analysis} />
                ) : kind === "video" ? (
                  <VideoViewer ev={ev} analysis={analysis} />
                ) : (
                  <EmptyState mascot={false} title="No viewer for this file type" body="Download the original to examine it." />
                )}
              </div>
              <RelatedPanel
                ev={ev}
                links={related}
                byId={byId}
                onArtifact={(src, title, caption) => setLightbox([{ src, title, caption }])}
              />
              <ExaminationLog view={view.data} techIndex={techIndex} />
            </div>
            <div className="min-w-0 space-y-5">
              <VerdictPanel analysis={analysis} onFinding={focusFinding} />
              <IntegrityPanel ev={ev} analysis={analysis} />
              <ProvenancePanel analysis={analysis} />
            </div>
          </div>
          <TechniqueAccordion analysis={analysis} evidenceId={ev.id} timeline={kind !== "image"} open={openTech} setOpen={setOpenTech} />
        </div>
      ) : !pending ? (
        <div className="panel">
          <EmptyState
            title="No stored analysis for this exhibit"
            body={ev.status === "error" ? "The last run failed. Re-analyse to try again." : "Queue an analysis to examine it."}
            action={
              <button type="button" className="btn-primary mt-2" onClick={() => void reanalyse()} disabled={busy}>
                <RotateCcw className="h-4 w-4" /> Analyse now
              </button>
            }
          />
          <div className="px-6 pb-6">
            <DataTable
              rows={[
                ["SHA-256", ev.sha256],
                ["SHA-1", ev.sha1],
                ["MD5", ev.md5],
              ]}
              mono
            />
          </div>
        </div>
      ) : null}
      <Lightbox items={lightbox ?? []} index={lightbox ? 0 : null} onIndex={() => undefined} onClose={() => setLightbox(null)} />
    </div>
  );
}
