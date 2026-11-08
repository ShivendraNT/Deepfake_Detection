import { AnimatePresence, motion } from "framer-motion";
import { Ban, Check, Circle, Loader2, PlugZap, Radar, X } from "lucide-react";
import { useMemo, type ReactElement } from "react";
import type { LabEvidence, ProgressEvent } from "../api";
import { formatDurationMs } from "../lib/format";
import { thumbUrl } from "../lib/media";
import { buildStageRows, overallProgress, type RowStatus, type StageRow, type TechIndex } from "../lib/stages";
import { categoryMeta } from "../lib/verdict";
import { cx, ExhibitBadge, MediaIcon, ProgressBar, SafeImg } from "./ui";

/** Animated scan over a thumbnail while an exhibit is being analysed. */
export function ScanOverlay({ intensity = 1 }: { intensity?: number }) {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" style={{ opacity: intensity }}>
      <div className="absolute inset-0 bg-ink-950/35" />
      <div className="scan-grid" />
      <div className="scan-line" />
      <div className="absolute inset-0 shadow-[inset_0_0_40px_rgba(34,211,238,0.25)]" />
      {/* corner brackets */}
      {(["left-2 top-2 border-l-2 border-t-2", "right-2 top-2 border-r-2 border-t-2", "left-2 bottom-2 border-b-2 border-l-2", "right-2 bottom-2 border-b-2 border-r-2"] as const).map(
        (c) => (
          <span key={c} className={cx("absolute h-4 w-4 border-accent/80", c)} />
        ),
      )}
    </div>
  );
}

const ROW_ICON: Record<RowStatus, { node: ReactElement; ring: string }> = {
  pending: { node: <Circle className="h-3 w-3 text-slate-600" />, ring: "border-white/10 bg-transparent" },
  running: { node: <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />, ring: "border-accent/50 bg-accent/10" },
  ok: { node: <Check className="h-3.5 w-3.5 text-emerald-300" strokeWidth={3} />, ring: "border-emerald-400/40 bg-emerald-500/15" },
  skipped: { node: <Ban className="h-3 w-3 text-slate-400" />, ring: "border-slate-500/40 bg-slate-500/10" },
  unavailable: { node: <PlugZap className="h-3 w-3 text-amber-300" />, ring: "border-amber-400/40 bg-amber-500/10" },
  error: { node: <X className="h-3.5 w-3.5 text-red-300" strokeWidth={3} />, ring: "border-red-400/40 bg-red-500/10" },
};

const STATUS_WORD: Record<RowStatus, string> = {
  pending: "waiting",
  running: "running",
  ok: "done",
  skipped: "not applicable",
  unavailable: "model unavailable",
  error: "error",
};

function Row({ row, compact }: { row: StageRow; compact?: boolean }) {
  const icon = ROW_ICON[row.status];
  const running = row.status === "running";
  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: row.status === "pending" ? 0.5 : 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ type: "spring", stiffness: 380, damping: 32 }}
      className={cx(
        "relative flex items-start gap-3 rounded-lg px-2.5",
        compact ? "py-1.5" : "py-2",
        running && "bg-accent/[0.07] shadow-[inset_0_0_0_1px_rgba(34,211,238,0.25)]",
      )}
    >
      {running && <span className="shimmer pointer-events-none absolute inset-0 rounded-lg" />}
      <span className={cx("relative mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border", icon.ring)}>
        {icon.node}
      </span>
      <div className="relative min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className={cx("truncate text-sm", running ? "font-semibold text-white" : "text-slate-200")}>{row.label}</span>
          {!compact && row.category && (
            <span className="hidden shrink-0 text-2xs uppercase tracking-wider text-slate-600 sm:inline">
              {categoryMeta(row.category).label}
            </span>
          )}
        </div>
        {row.message && row.status !== "pending" && (
          <div
            className={cx(
              "truncate text-xs",
              row.status === "error" ? "text-red-300/90" : row.status === "unavailable" ? "text-amber-200/80" : "text-slate-500",
            )}
            title={row.message}
          >
            {row.message}
          </div>
        )}
        {running && row.sub !== null && <ProgressBar value={row.sub} className="mt-1.5 h-1" />}
      </div>
      <div className="relative shrink-0 pt-0.5 text-right">
        <div className="font-mono text-2xs text-slate-500">
          {row.durationMs !== null ? formatDurationMs(row.durationMs) : running ? "…" : ""}
        </div>
        {!compact && row.status !== "ok" && row.status !== "pending" && row.status !== "running" && (
          <div className="text-2xs text-slate-600">{STATUS_WORD[row.status]}</div>
        )}
      </div>
    </motion.li>
  );
}

export function StageChecklist({
  rows,
  compact = false,
  className,
}: {
  rows: StageRow[];
  compact?: boolean;
  className?: string;
}) {
  return (
    <ul className={cx("space-y-0.5", className)}>
      <AnimatePresence initial={false}>
        {rows.map((r) => (
          <Row key={r.stage} row={r} compact={compact} />
        ))}
      </AnimatePresence>
    </ul>
  );
}

/** The full-size live analysis view: scanning media on the left, streaming checklist on the right. */
export function LiveAnalysis({
  ev,
  events,
  techIndex,
  expected,
  connection,
}: {
  ev: LabEvidence;
  events: ProgressEvent[];
  techIndex: TechIndex;
  expected: string[];
  connection: string;
}) {
  const rows = useMemo(() => buildStageRows(events, techIndex, expected), [events, techIndex, expected]);
  const progress = overallProgress(events);
  const doneTech = rows.filter((r) => r.isTechnique && r.status !== "pending" && r.status !== "running").length;
  const totalTech = rows.filter((r) => r.isTechnique).length;
  const running = rows.find((r) => r.status === "running");
  return (
    <div className="panel overflow-hidden">
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(380px,460px)]">
        <div className="relative border-b hairline p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inset-0 animate-ping rounded-full bg-accent opacity-70" />
                <span className="relative h-2.5 w-2.5 rounded-full bg-accent" />
              </span>
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">Live examination</span>
            </div>
            <span className="font-mono text-2xs text-slate-500">
              {connection === "open" || connection === "connecting" ? "streaming events" : connection === "polling" ? "polling" : connection}
            </span>
          </div>
          <div className="relative mx-auto mt-4 flex aspect-[16/10] max-h-[420px] w-full items-center justify-center overflow-hidden rounded-xl border border-white/[0.08] bg-ink-900">
            <SafeImg
              src={thumbUrl(ev)}
              alt={ev.filename}
              className="h-full w-full object-contain"
              fallback={
                <div className="flex flex-col items-center gap-2 text-slate-500">
                  <MediaIcon kind={ev.kind} className="h-12 w-12" />
                  <span className="text-xs">{ev.kind} exhibit</span>
                </div>
              }
            />
            <ScanOverlay />
            <div className="absolute left-3 top-3 flex items-center gap-2">
              <ExhibitBadge exhibit={ev.exhibit} role={ev.role} />
            </div>
            <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between gap-3">
              <div className="min-w-0 rounded-lg bg-ink-950/70 px-3 py-2 backdrop-blur">
                <div className="flex items-center gap-2 text-2xs uppercase tracking-wider text-accent-soft">
                  <Radar className="h-3.5 w-3.5" /> {running ? "Now running" : progress >= 1 ? "Complete" : "Preparing"}
                </div>
                <div className="truncate text-sm font-medium text-white">{running?.label ?? (progress >= 1 ? "Verdict ready" : "Waiting for a worker")}</div>
              </div>
              <div className="rounded-lg bg-ink-950/70 px-3 py-2 text-right backdrop-blur">
                <div className="font-mono text-2xl font-semibold text-white tabular">{Math.round(progress * 100)}%</div>
                <div className="font-mono text-2xs text-slate-400">
                  {doneTech}/{totalTech || "?"} techniques
                </div>
              </div>
            </div>
          </div>
          <ProgressBar value={progress} className="mt-4 h-2" />
        </div>
        <div className="max-h-[560px] overflow-y-auto p-3">
          <StageChecklist rows={rows} />
        </div>
      </div>
    </div>
  );
}
