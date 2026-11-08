import { motion } from "framer-motion";
import {
  Anchor,
  ChevronDown,
  FileCheck2,
  FilePlus2,
  FolderPlus,
  Link2,
  RefreshCw,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Stamp,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, type CaseView, type CustodyRow, type LabEvidence } from "../../api";
import { CopyButton, cx, EmptyState, ErrorState, ExhibitBadge, LoadingState } from "../../components/ui";
import { useLab } from "../../context";
import { displayValue, formatBytes, formatIST, shortHash } from "../../lib/format";
import { useAsync } from "../../lib/hooks";
import { verdictMeta, isVerdictLabel } from "../../lib/verdict";

const GENESIS = /^0+$/;

const EVENT_META: Record<string, { label: string; color: string; icon: typeof Link2 }> = {
  INTAKE: { label: "Intake", color: "#22d3ee", icon: FilePlus2 },
  ANALYSIS: { label: "Analysis", color: "#a78bfa", icon: ScanSearch },
  STATUS_CHANGE: { label: "Status", color: "#94a3b8", icon: FolderPlus },
  EXPORT: { label: "Report", color: "#34d399", icon: Stamp },
};

function eventMeta(e: string) {
  return EVENT_META[e] ?? { label: e.replace(/_/g, " ").toLowerCase(), color: "#94a3b8", icon: Link2 };
}

function s(v: unknown): string {
  return v === null || v === undefined ? "" : String(v);
}

/** One plain-language line for a custody row's payload. */
export function custodySummary(row: CustodyRow, exhibit?: LabEvidence): { text: ReactNode; alert?: boolean } {
  const p = row.payload ?? {};
  const action = s(p.action);
  if (row.event === "STATUS_CHANGE" && action === "case_opened") {
    return { text: <>Case opened: “{s(p.title)}”{p.fir ? <> · {s(p.fir)}</> : null}</> };
  }
  if (action === "INTEGRITY_FAILURE") {
    return {
      alert: true,
      text: (
        <>
          INTEGRITY FAILURE: stored file hash {shortHash(s(p.found))} ≠ intake {shortHash(s(p.expected))}
        </>
      ),
    };
  }
  if (row.event === "INTAKE") {
    return {
      text: (
        <>
          <span className="text-slate-200">{s(p.filename) || exhibit?.filename}</span> sealed as {s(p.exhibit) || exhibit?.exhibit} ·{" "}
          {s(p.format).toUpperCase()} · {typeof p.size === "number" ? formatBytes(p.size) : "?"} · {s(p.role)}
          {p.received_from ? <> · from {s(p.received_from)}</> : null}
        </>
      ),
    };
  }
  if (row.event === "ANALYSIS") {
    const v = s(p.verdict);
    const meta = isVerdictLabel(v) ? verdictMeta(v) : null;
    return {
      text: (
        <>
          {s(p.techniques)} techniques run · verdict{" "}
          <span className="font-semibold" style={{ color: meta?.hex }}>
            {meta?.label ?? (v || "none")}
          </span>
          {p.risk_index !== undefined && p.risk_index !== null ? <> · risk index {s(p.risk_index)}</> : null} · engine {s(p.engine)}
        </>
      ),
    };
  }
  if (row.event === "EXPORT" && action === "report_generated") {
    const ex = Array.isArray(p.exhibits) ? (p.exhibits as unknown[]).map(String).join(", ") : "";
    return { text: <>Court report {s(p.report_id)} generated{ex ? <> · exhibits {ex}</> : null}</> };
  }
  const parts = Object.entries(p)
    .slice(0, 4)
    .map(([k, v]) => `${k}: ${displayValue(v, 40)}`);
  return { text: <>{action ? `${action.replace(/_/g, " ")} · ` : ""}{parts.join(" · ")}</> };
}

function HashFlow({ prev, hash }: { prev: string; hash: string }) {
  return (
    <div className="flex items-center gap-2 font-mono text-2xs">
      <span className={cx("rounded px-1.5 py-0.5", GENESIS.test(prev) ? "bg-white/[0.04] text-slate-600" : "bg-white/[0.04] text-slate-400")} title={`prev_hash ${prev}`}>
        {GENESIS.test(prev) ? "genesis" : shortHash(prev, 8, 4)}
      </span>
      <span className="text-slate-600">→</span>
      <span className="rounded bg-accent/10 px-1.5 py-0.5 text-accent-soft" title={`row_hash ${hash}`}>
        {shortHash(hash, 8, 4)}
      </span>
    </div>
  );
}

function Block({
  row,
  index,
  exhibit,
  broken,
}: {
  row: CustodyRow;
  index: number;
  exhibit?: LabEvidence;
  broken: boolean;
}) {
  const [open, setOpen] = useState(false);
  const meta = eventMeta(row.event);
  const Icon = meta.icon;
  const sum = custodySummary(row, exhibit);
  return (
    <motion.div
      initial={{ opacity: 0, x: -14 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: Math.min(index, 20) * 0.045, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className={cx(
        "panel-tight relative overflow-hidden",
        broken && "border-red-500/50 bg-red-500/[0.06]",
        sum.alert && "border-red-500/40",
      )}
    >
      <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: broken ? "#f87171" : meta.color }} />
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-4 px-4 py-3 text-left">
        <div className="flex w-14 shrink-0 flex-col items-center">
          <span className="font-mono text-lg font-semibold text-white">#{row.seq}</span>
          <span className="text-[9px] uppercase tracking-widest text-slate-600">block</span>
        </div>
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border"
          style={{ borderColor: `${meta.color}55`, background: `${meta.color}14`, color: meta.color }}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: meta.color }}>
              {meta.label}
            </span>
            {exhibit && <ExhibitBadge exhibit={exhibit.exhibit} role={exhibit.role} size="sm" />}
            <span className="font-mono text-2xs text-slate-500">{formatIST(row.at)} IST</span>
            <span className="text-2xs text-slate-500">by {row.actor}</span>
          </div>
          <div className={cx("mt-0.5 truncate text-sm", sum.alert ? "text-red-200" : "text-slate-400")}>{sum.text}</div>
        </div>
        <div className="hidden shrink-0 md:block">
          <HashFlow prev={row.prev_hash} hash={row.row_hash} />
        </div>
        <ChevronDown className={cx("h-4 w-4 shrink-0 text-slate-500 transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t hairline bg-ink-950/40 px-4 py-3">
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div className="space-y-1.5">
              <div className="eyebrow">Hash chain</div>
              <div className="flex items-center gap-2 font-mono text-2xs text-slate-400">
                <span className="w-16 shrink-0 text-slate-600">prev</span>
                <span className="truncate">{row.prev_hash}</span>
                <CopyButton text={row.prev_hash} />
              </div>
              <div className="flex items-center gap-2 font-mono text-2xs text-accent-soft">
                <span className="w-16 shrink-0 text-slate-600">row hash</span>
                <span className="truncate">{row.row_hash}</span>
                <CopyButton text={row.row_hash} />
              </div>
              {exhibit && (
                <Link to={`/evidence/${exhibit.id}`} className="link inline-block pt-1 text-xs">
                  Open exhibit {exhibit.exhibit}
                </Link>
              )}
            </div>
            <div>
              <div className="eyebrow mb-1.5">Payload (as hashed)</div>
              <pre className="max-h-48 overflow-auto rounded-lg bg-ink-950/80 p-2.5 font-mono text-2xs leading-relaxed text-slate-300">
                {JSON.stringify(row.payload, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}

function Connector({ linked, gap, index }: { linked: boolean; gap: number; index: number }) {
  return (
    <div className="relative flex h-9 items-center pl-[38px]">
      <motion.div
        className={cx("h-full w-0.5 origin-top", linked ? "bg-gradient-to-b from-accent/70 to-accent/30" : "border-l-2 border-dashed border-slate-600")}
        initial={{ scaleY: 0 }}
        animate={{ scaleY: 1 }}
        transition={{ delay: Math.min(index, 20) * 0.045 + 0.15, duration: 0.3 }}
      />
      <span className="ml-4 inline-flex items-center gap-1.5 text-2xs text-slate-500">
        <Link2 className={cx("h-3 w-3", linked ? "text-accent/80" : "text-slate-600")} />
        {linked
          ? "prev_hash = previous row_hash"
          : `${gap} row${gap === 1 ? "" : "s"} of other cases in between (verified in the global chain, not shown)`}
      </span>
    </div>
  );
}

export function CustodyTab({ view }: { view: CaseView }) {
  const { custodyNonce } = useLab();
  const custody = useAsync(() => api.custody(view.case.id), `${view.case.id}:${custodyNonce}:${view.evidence.length}`);
  const byId = useMemo(() => new Map(view.evidence.map((e) => [e.id, e])), [view.evidence]);
  if (custody.error && !custody.data) return <div className="panel"><ErrorState error={custody.error} onRetry={() => void custody.reload()} /></div>;
  if (!custody.data) return <LoadingState label="Verifying the custody chain…" />;
  const { rows, chain, head } = custody.data;
  const ordered = [...rows].sort((a, b) => a.seq - b.seq);
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-5">
        <motion.div
          initial={{ opacity: 0, scale: 0.99 }}
          animate={{ opacity: 1, scale: 1 }}
          className={cx(
            "panel flex flex-wrap items-center gap-5 overflow-hidden p-6",
            chain.ok ? "border-emerald-400/25" : "border-red-500/40",
          )}
        >
          <div
            className="pointer-events-none absolute -left-16 -top-16 h-48 w-48 rounded-full blur-3xl"
            style={{ background: chain.ok ? "rgba(52,211,153,0.18)" : "rgba(248,113,113,0.2)" }}
          />
          <div
            className={cx(
              "relative flex h-16 w-16 items-center justify-center rounded-2xl border",
              chain.ok ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-300" : "border-red-400/40 bg-red-500/10 text-red-300",
            )}
          >
            {chain.ok ? <ShieldCheck className="h-8 w-8" /> : <ShieldAlert className="h-8 w-8" />}
          </div>
          <div className="relative min-w-0 flex-1">
            <div className={cx("text-2xl font-semibold tracking-tight", chain.ok ? "text-emerald-200" : "text-red-200")}>
              {chain.ok ? "Chain INTACT ✓" : `Chain BROKEN at #${chain.broken_at_seq ?? "?"}`}
            </div>
            <div className="mt-1 text-sm text-slate-400">
              {chain.ok
                ? `${chain.rows_checked} rows re-hashed and verified end to end, from the genesis block to the head.`
                : `${chain.reason ?? "hash mismatch"}: every row after #${chain.broken_at_seq ?? "?"} can no longer be trusted.`}
            </div>
          </div>
          <div className="relative min-w-[260px] rounded-xl border border-white/[0.08] bg-ink-950/50 px-4 py-3">
            <div className="eyebrow flex items-center gap-1.5">
              <Anchor className="h-3 w-3" /> Head hash
            </div>
            <div className="mt-1 flex items-center gap-1">
              <span className="truncate font-mono text-xs text-accent-soft" title={head}>
                {shortHash(head, 16, 10)}
              </span>
              <CopyButton text={head} />
            </div>
          </div>
          <button type="button" className="btn-ghost btn-sm relative" onClick={() => void custody.reload()} title="Re-verify now">
            <RefreshCw className="h-3.5 w-3.5" /> Re-verify
          </button>
        </motion.div>

        {ordered.length === 0 ? (
          <div className="panel">
            <EmptyState title="No custody rows" body="Rows are written when the case is opened and on every intake, analysis and report." />
          </div>
        ) : (
          <div>
            {GENESIS.test(ordered[0]?.prev_hash ?? "") && (
              <div className="mb-1 flex items-center gap-3 pl-[22px]">
                <span className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-ink-900 font-mono text-2xs text-slate-500">
                  0
                </span>
                <span className="font-mono text-2xs text-slate-600">GENESIS · 0000…0000</span>
              </div>
            )}
            {ordered.map((r, i) => {
              const prev = ordered[i - 1];
              const linked = prev ? prev.row_hash === r.prev_hash : GENESIS.test(r.prev_hash);
              const gap = prev ? Math.max(0, r.seq - prev.seq - 1) : Math.max(0, r.seq - 1);
              const broken = !chain.ok && chain.broken_at_seq !== null && r.seq >= chain.broken_at_seq;
              return (
                <div key={r.seq}>
                  {(i > 0 || !GENESIS.test(r.prev_hash)) && <Connector linked={linked} gap={gap} index={i} />}
                  <Block row={r} index={i} exhibit={r.evidence_id ? byId.get(r.evidence_id) : undefined} broken={broken} />
                </div>
              );
            })}
            <div className="mt-1 flex h-9 items-center pl-[38px]">
              <div className="h-full w-0.5 bg-gradient-to-b from-accent/40 to-transparent" />
            </div>
            <div className="flex items-center gap-3 pl-[22px]">
              <span className="flex h-8 w-8 items-center justify-center rounded-full border border-accent/40 bg-accent/10 text-accent">
                <Anchor className="h-3.5 w-3.5" />
              </span>
              <span className="font-mono text-2xs text-slate-400">HEAD · {shortHash(head, 12, 8)}</span>
            </div>
          </div>
        )}
      </div>

      <div className="space-y-4">
        <div className="panel p-5">
          <h3 className="panel-title">
            <FileCheck2 className="h-4 w-4 text-accent" /> How the ledger works
          </h3>
          <ol className="mt-3 space-y-3 text-sm leading-relaxed text-slate-400">
            <li>
              <span className="text-slate-200">Every action is a row:</span> case opened, each intake (with the MD5 / SHA-1 / SHA-256 of
              the raw bytes), each analysis (with the SHA-256 of the full result) and each report.
            </li>
            <li>
              <span className="text-slate-200">Rows are chained:</span> row_hash = SHA-256(prev_hash + canonical row). Editing any past
              row changes its hash and breaks every row after it.
            </li>
            <li>
              <span className="text-slate-200">Re-verified on every view:</span> the whole chain is recomputed from the genesis block;
              the head hash is printed on the court report.
            </li>
          </ol>
        </div>
        <div className="panel p-5">
          <div className="eyebrow">This case</div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            {Object.entries(
              ordered.reduce<Record<string, number>>((acc, r) => ({ ...acc, [r.event]: (acc[r.event] ?? 0) + 1 }), {}),
            ).map(([k, n]) => {
              const m = eventMeta(k);
              return (
                <div key={k} className="rounded-lg border border-white/[0.06] bg-ink-900/50 px-3 py-2">
                  <div className="text-2xs uppercase tracking-wider" style={{ color: m.color }}>
                    {m.label}
                  </div>
                  <div className="font-mono text-xl font-semibold text-white">{n}</div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 text-2xs text-slate-500">
            {ordered.length} of {chain.rows_checked} rows in the workstation ledger belong to this case.
          </div>
        </div>
      </div>
    </div>
  );
}
