import { motion } from "framer-motion";
import {
  AlertTriangle,
  Check,
  Copy,
  FileAudio2,
  FileImage,
  FileQuestion,
  FileText,
  FileVideo2,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import type { EvidenceRole, MediaKind } from "../api";
import { useCopy } from "../lib/hooks";
import { hypothesisMeta, strengthWord, type ToneMeta } from "../lib/verdict";
import satyaThink from "../assets/satya_think.webp";
import satyaWave from "../assets/satya_wave.webp";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

// ------------------------------------------------------------------ badges

export function ToneBadge({
  meta,
  size = "md",
  pulse = false,
  className,
}: {
  meta: ToneMeta;
  size?: "sm" | "md" | "lg";
  pulse?: boolean;
  className?: string;
}) {
  const pad = size === "sm" ? "px-1.5 py-0.5 text-2xs" : size === "lg" ? "px-3 py-1.5 text-sm" : "px-2 py-1 text-xs";
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border font-semibold uppercase tracking-wider",
        pad,
        meta.text,
        meta.bg,
        meta.border,
        className,
      )}
    >
      <span className="relative inline-flex h-1.5 w-1.5">
        {pulse && (
          <span className="absolute inset-0 animate-ping rounded-full opacity-75" style={{ background: meta.hex }} />
        )}
        <span className="relative h-1.5 w-1.5 rounded-full" style={{ background: meta.hex }} />
      </span>
      {meta.label}
    </span>
  );
}

export function ExhibitBadge({
  exhibit,
  role,
  size = "md",
  className,
}: {
  exhibit: string;
  role?: EvidenceRole;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const ref = role ? role === "reference" : exhibit.startsWith("R");
  const sz =
    size === "sm"
      ? "h-5 min-w-[1.75rem] px-1 text-2xs"
      : size === "lg"
        ? "h-9 min-w-[2.75rem] px-2 text-base"
        : "h-6 min-w-[2.1rem] px-1.5 text-xs";
  return (
    <span
      title={ref ? "Reference sample (known origin)" : "Questioned item (under examination)"}
      className={cx(
        "inline-flex items-center justify-center rounded-md border font-mono font-bold tracking-tight",
        sz,
        ref
          ? "border-violet-400/40 bg-violet-500/15 text-violet-200"
          : "border-cyan-400/40 bg-cyan-500/15 text-cyan-100",
        className,
      )}
    >
      {exhibit}
    </span>
  );
}

export function RoleChip({ role }: { role: EvidenceRole }) {
  return role === "reference" ? (
    <span className="chip border-violet-400/30 bg-violet-500/10 text-violet-200">Reference</span>
  ) : (
    <span className="chip border-cyan-400/30 bg-cyan-500/10 text-cyan-100">Questioned</span>
  );
}

export function MediaIcon({ kind, className = "h-4 w-4" }: { kind: MediaKind | string; className?: string }) {
  switch (kind) {
    case "image":
      return <FileImage className={className} aria-label="image" />;
    case "audio":
      return <FileAudio2 className={className} aria-label="audio" />;
    case "video":
      return <FileVideo2 className={className} aria-label="video" />;
    case "document":
      return <FileText className={className} aria-label="document" />;
    default:
      return <FileQuestion className={className} aria-label="file" />;
  }
}

// ------------------------------------------------------------------ meters

/** 4-segment ENFSI strength meter coloured by hypothesis. */
export function StrengthMeter({
  strength,
  hypothesis,
  showWord = false,
  className,
}: {
  strength: number;
  hypothesis: string;
  showWord?: boolean;
  className?: string;
}) {
  const h = hypothesisMeta(hypothesis);
  const s = Math.max(0, Math.min(4, Math.round(strength)));
  return (
    <span className={cx("inline-flex items-center gap-2", className)} title={`${h.label}: ${strengthWord(s)}`}>
      <span className="inline-flex gap-[3px]">
        {[1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="h-2.5 w-[7px] rounded-[2px]"
            style={{
              background: i <= s ? h.hex : "rgba(148,163,184,0.16)",
              boxShadow: i <= s ? `0 0 8px -1px ${h.hex}` : undefined,
            }}
          />
        ))}
      </span>
      {showWord && <span className={cx("text-2xs font-medium", s > 0 ? h.text : "text-slate-500")}>{strengthWord(s)}</span>}
    </span>
  );
}

export function ProgressBar({
  value,
  className,
  tone = "#22d3ee",
  indeterminate = false,
}: {
  value: number;
  className?: string;
  tone?: string;
  indeterminate?: boolean;
}) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className={cx("relative h-1.5 overflow-hidden rounded-full bg-white/[0.07]", indeterminate && "indeterminate", className)}>
      {!indeterminate && (
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ background: `linear-gradient(90deg, ${tone}66, ${tone})`, boxShadow: `0 0 12px ${tone}` }}
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={{ type: "spring", stiffness: 80, damping: 20 }}
        />
      )}
    </div>
  );
}

/** Segmented bar of verdict counts. */
export function DistributionBar({
  parts,
  className,
  height = "h-2",
}: {
  parts: { key: string; count: number; meta: ToneMeta }[];
  className?: string;
  height?: string;
}) {
  const total = parts.reduce((a, p) => a + p.count, 0);
  if (total === 0) {
    return <div className={cx("rounded-full bg-white/[0.05]", height, className)} />;
  }
  return (
    <div className={cx("flex gap-[2px] overflow-hidden rounded-full", height, className)}>
      {parts.map((p, i) => (
        <motion.div
          key={p.key}
          title={`${p.meta.label}: ${p.count}`}
          className="h-full first:rounded-l-full last:rounded-r-full"
          style={{ background: p.meta.hex, boxShadow: `0 0 10px -2px ${p.meta.hex}` }}
          initial={{ flexGrow: 0 }}
          animate={{ flexGrow: p.count }}
          transition={{ duration: 0.8, delay: 0.05 * i, ease: [0.22, 1, 0.36, 1] }}
        />
      ))}
    </div>
  );
}

export function DistributionLegend({ parts }: { parts: { key: string; count: number; meta: ToneMeta }[] }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1">
      {parts.map((p) => (
        <span key={p.key} className="inline-flex items-center gap-1.5 text-2xs text-slate-400">
          <span className="h-2 w-2 rounded-sm" style={{ background: p.meta.hex }} />
          {p.meta.label}
          <span className="font-mono text-slate-300">{p.count}</span>
        </span>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ buttons

export function CopyButton({ text, label, className }: { text: string; label?: string; className?: string }) {
  const [copied, copy] = useCopy();
  return (
    <button
      type="button"
      onClick={() => void copy(text)}
      className={cx(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-2xs font-medium transition",
        copied ? "text-emerald-300" : "text-slate-500 hover:bg-white/[0.06] hover:text-slate-200",
        className,
      )}
      title={copied ? "Copied" : `Copy ${label ?? ""}`.trim()}
      aria-label={`Copy ${label ?? "value"}`}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {label && <span>{copied ? "Copied" : label}</span>}
    </button>
  );
}

// ------------------------------------------------------------------ states

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <Loader2 className={cx("animate-spin text-accent", className)} />;
}

export function LoadingState({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div className={cx("flex flex-col items-center justify-center gap-3 py-16 text-center", className)}>
      <motion.img
        src={satyaThink}
        alt=""
        className="h-14 w-auto opacity-90"
        animate={{ y: [0, -4, 0] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Spinner />
        {label}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
  mascot = true,
  icon,
  className,
}: {
  title: string;
  body?: ReactNode;
  action?: ReactNode;
  mascot?: boolean;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("flex flex-col items-center justify-center gap-3 px-6 py-14 text-center", className)}>
      {icon ?? (mascot && <img src={satyaWave} alt="" className="h-16 w-auto opacity-90" />)}
      <div className="text-base font-semibold text-slate-200">{title}</div>
      {body && <div className="max-w-md text-sm text-slate-400">{body}</div>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: Error | string; onRetry?: () => void; className?: string }) {
  const msg = typeof error === "string" ? error : error.message;
  return (
    <div className={cx("flex flex-col items-center justify-center gap-3 px-6 py-12 text-center", className)}>
      <div className="flex h-11 w-11 items-center justify-center rounded-full border border-red-500/30 bg-red-500/10">
        <AlertTriangle className="h-5 w-5 text-red-300" />
      </div>
      <div className="text-sm font-semibold text-slate-200">Could not load this from the lab workstation</div>
      <div className="max-w-lg font-mono text-xs text-slate-500">{msg}</div>
      {onRetry && (
        <button type="button" className="btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" /> Retry
        </button>
      )}
    </div>
  );
}

/** <img> that degrades to a placeholder when the artifact is missing (404). */
export function SafeImg({
  src,
  alt,
  className,
  fallback,
  onLoad,
  draggable,
}: {
  src: string | null | undefined;
  alt: string;
  className?: string;
  fallback?: ReactNode;
  onLoad?: (e: React.SyntheticEvent<HTMLImageElement>) => void;
  draggable?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return <>{fallback ?? null}</>;
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      loading="lazy"
      decoding="async"
      draggable={draggable}
      onLoad={onLoad}
      onError={() => setFailed(true)}
    />
  );
}

export function SectionTitle({ icon, children, right }: { icon?: ReactNode; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h3 className="panel-title">
        {icon && <span className="text-accent">{icon}</span>}
        {children}
      </h3>
      {right}
    </div>
  );
}
