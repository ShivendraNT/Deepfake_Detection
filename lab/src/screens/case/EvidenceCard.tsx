import { motion } from "framer-motion";
import { AlertTriangle, Clock3 } from "lucide-react";
import { Link } from "react-router-dom";
import type { LabEvidence } from "../../api";
import { ScanOverlay } from "../../components/LiveScan";
import { MiniGauge } from "../../components/RiskGauge";
import { cx, ExhibitBadge, MediaIcon, ProgressBar, SafeImg, ToneBadge } from "../../components/ui";
import { useLab } from "../../context";
import { formatBytes, formatIST, shortHash } from "../../lib/format";
import { thumbUrl } from "../../lib/media";
import { useEvidenceStream } from "../../lib/sse";
import { activeStage, isDone, overallProgress } from "../../lib/stages";
import { evidenceMeta, isPending } from "../../lib/verdict";

export function EvidenceCard({
  ev,
  live,
  index,
  onDone,
}: {
  ev: LabEvidence;
  /** Subscribe to the SSE stream (the grid limits how many cards stream at once). */
  live: boolean;
  index: number;
  onDone: () => void;
}) {
  const { techIndex } = useLab();
  const pending = isPending(ev.status);
  const stream = useEvidenceStream(ev.id, pending && live, () => onDone());
  // A finished stream while the record is still pending means a re-analysis whose events the
  // server cannot replay (its stream stops at the first "done"): show an indeterminate bar.
  const streamUseful = stream.events.length > 0 && !(isDone(stream.events) && pending);
  const progress = streamUseful ? overallProgress(stream.events) : 0;
  const stage = streamUseful ? activeStage(stream.events, techIndex) : null;
  const meta = evidenceMeta(ev);
  const src = thumbUrl(ev);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index, 12) * 0.035, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      <Link
        to={`/evidence/${ev.id}`}
        className={cx(
          "panel group block overflow-hidden transition duration-200 hover:-translate-y-0.5",
          pending ? "border-accent/25 hover:shadow-glow" : "hover:border-white/15",
        )}
        style={!pending && ev.status === "done" ? { boxShadow: `inset 0 2px 0 0 ${meta.hex}` } : undefined}
      >
        <div className="relative aspect-[16/10] overflow-hidden rounded-t-2xl bg-ink-900">
          <SafeImg
            src={src}
            alt={ev.filename}
            className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
            fallback={
              <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-slate-600">
                <MediaIcon kind={ev.kind} className="h-10 w-10" />
                <span className="text-2xs uppercase tracking-wider">{pending ? "rendering preview…" : `${ev.kind} exhibit`}</span>
              </div>
            }
          />
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-ink-950/90 via-ink-950/10 to-ink-950/30" />
          {pending && <ScanOverlay />}
          <div className="absolute left-2.5 top-2.5 flex items-center gap-1.5">
            <ExhibitBadge exhibit={ev.exhibit} role={ev.role} />
          </div>
          <div className="absolute right-2.5 top-2.5 flex items-center gap-1 rounded-md border border-white/10 bg-ink-950/60 px-1.5 py-1 text-2xs uppercase tracking-wider text-slate-300 backdrop-blur">
            <MediaIcon kind={ev.kind} className="h-3.5 w-3.5" />
            {ev.kind}
          </div>
          <div className="absolute inset-x-2.5 bottom-2.5 flex items-end justify-between gap-2">
            <ToneBadge meta={meta} pulse={pending} />
            {ev.status === "done" && <MiniGauge value={ev.risk_index} color={meta.hex} />}
          </div>
        </div>
        <div className="space-y-2.5 p-3.5">
          <div>
            <div className="truncate text-sm font-semibold text-slate-100" title={ev.filename}>
              {ev.filename}
            </div>
            <div className="mt-0.5 flex items-center gap-1.5 truncate text-2xs text-slate-500">
              <span>{formatBytes(ev.size_bytes)}</span>
              <span>·</span>
              <span className="truncate">{ev.mime}</span>
              <span>·</span>
              <Clock3 className="h-3 w-3 shrink-0" />
              <span className="truncate">{formatIST(ev.received_at)}</span>
            </div>
          </div>
          {pending ? (
            <div className="space-y-1.5">
              <ProgressBar value={progress} indeterminate={!streamUseful} />
              <div className="flex items-center justify-between gap-2 text-2xs">
                <span className="truncate text-accent-soft">
                  {ev.status === "queued" && !streamUseful ? "Queued for a worker" : (stage?.label ?? "Analysing…")}
                </span>
                {streamUseful && <span className="font-mono text-slate-400">{Math.round(progress * 100)}%</span>}
              </div>
              {stage?.message && stage.message !== stage.label && (
                <div className="truncate text-2xs text-slate-500" title={stage.message}>
                  {stage.message}
                </div>
              )}
            </div>
          ) : ev.status === "error" ? (
            <div className="flex items-start gap-1.5 text-xs text-red-300/90">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span className="line-clamp-2">{ev.headline || "Analysis failed"}</span>
            </div>
          ) : (
            <div className="line-clamp-2 min-h-[2.5rem] text-xs leading-relaxed text-slate-400">{ev.headline || "—"}</div>
          )}
          <div className="flex items-center justify-between border-t hairline pt-2">
            <span className="font-mono text-2xs text-slate-500" title={`SHA-256 ${ev.sha256}`}>
              SHA-256 {shortHash(ev.sha256, 10, 6)}
            </span>
            {ev.received_from && (
              <span className="max-w-[45%] truncate text-2xs text-slate-600" title={`Received from ${ev.received_from}`}>
                {ev.received_from}
              </span>
            )}
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
