import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Cpu, Link2, ShieldAlert, ShieldCheck, WifiOff, XCircle } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useLab } from "../context";
import { useAsync } from "../lib/hooks";
import { shortHash } from "../lib/format";
import { cx } from "./ui";

export function Logo({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="lg-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#a5f3fc" />
          <stop offset="1" stopColor="#0891b2" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="62" height="62" rx="15" fill="#07101f" stroke="rgba(34,211,238,0.35)" />
      <path
        d="M32 10 L50 16.5 V30.5 C50 42 42.5 49.5 32 53.5 C21.5 49.5 14 42 14 30.5 V16.5 Z"
        fill="rgba(34,211,238,0.08)"
        stroke="url(#lg-logo)"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <circle cx="31" cy="30" r="7.5" fill="none" stroke="url(#lg-logo)" strokeWidth="2.8" />
      <path d="M36.5 35.5 L42 41" stroke="url(#lg-logo)" strokeWidth="3.2" strokeLinecap="round" />
    </svg>
  );
}

function ModelsPill() {
  const { health, healthError } = useLab();
  const [open, setOpen] = useState(false);
  const models = health ? Object.entries(health.models) : [];
  const total = models.length;
  const up = models.filter(([, m]) => m.available).length;
  const tone = healthError ? "red" : !health ? "slate" : up === total ? "emerald" : "amber";
  const dot = { red: "bg-red-400", slate: "bg-slate-500", emerald: "bg-emerald-400", amber: "bg-amber-400" }[tone];
  return (
    <div className="relative" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300 transition hover:border-white/20"
      >
        <span className="relative flex h-2 w-2">
          {tone === "emerald" && <span className={cx("absolute inset-0 animate-ping rounded-full opacity-60", dot)} />}
          <span className={cx("relative h-2 w-2 rounded-full", dot)} />
        </span>
        <Cpu className="h-3.5 w-3.5 text-slate-400" />
        {healthError ? (
          <span>Workstation offline</span>
        ) : health ? (
          <span>
            Models <span className="font-mono font-semibold text-white">{up}</span>
            <span className="text-slate-500">/{total}</span>
          </span>
        ) : (
          <span>Connecting…</span>
        )}
        {health && <span className="hidden font-mono text-2xs text-slate-500 xl:inline">engine {health.engine}</span>}
      </button>
      <AnimatePresence>
        {open && health && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="panel absolute right-0 top-full z-50 mt-2 w-[380px] p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <div className="eyebrow">Analysis models on this workstation</div>
              <div className="font-mono text-2xs text-slate-500">{health.techniques} techniques</div>
            </div>
            <ul className="space-y-2">
              {models.map(([name, m]) => (
                <li key={name} className="flex items-start gap-2.5">
                  {m.available ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                  ) : (
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
                  )}
                  <div className="min-w-0">
                    <div className="text-xs text-slate-200">{m.purpose}</div>
                    <div className="truncate font-mono text-2xs text-slate-500">
                      {name}
                      {m.model ? ` · ${m.model}` : ""}
                      {!m.available && m.detail ? ` · ${m.detail}` : ""}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-3 border-t hairline pt-3 font-mono text-2xs text-slate-500">
              Evidence store: {health.lab_dir}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function CustodyPill({ caseId }: { caseId: string }) {
  const { custodyNonce } = useLab();
  const navigate = useNavigate();
  const custody = useAsync(() => api.custody(caseId), `${caseId}:${custodyNonce}`, { pollMs: 15000 });
  const c = custody.data?.chain;
  if (!c) {
    return (
      <span className="hidden items-center gap-2 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-500 lg:flex">
        <Link2 className="h-3.5 w-3.5" /> Custody chain…
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => navigate(`/cases/${caseId}/custody`)}
      title={`Head ${custody.data?.head ?? ""}`}
      className={cx(
        "hidden items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition lg:flex",
        c.ok
          ? "border-emerald-400/30 bg-emerald-500/[0.07] text-emerald-200 hover:bg-emerald-500/[0.12]"
          : "border-red-400/40 bg-red-500/10 text-red-200 hover:bg-red-500/20",
      )}
    >
      {c.ok ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
      {c.ok ? (
        <span>
          Custody chain intact · <span className="font-mono">{c.rows_checked}</span> rows
        </span>
      ) : (
        <span>Custody chain BROKEN at #{c.broken_at_seq}</span>
      )}
      <span className="hidden font-mono text-2xs opacity-60 2xl:inline">{shortHash(custody.data?.head, 6, 4)}</span>
    </button>
  );
}

export function TopBar() {
  const { activeCaseId } = useLab();
  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-ink-950/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1680px] items-center gap-4 px-5 lg:px-8">
        <Link to="/" className="group flex min-w-0 items-center gap-3">
          <Logo />
          <div className="min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="truncate text-[15px] font-semibold tracking-tight text-white">Satyapan Forensic Lab</span>
              <span className="font-deva text-sm font-medium text-accent-soft/90">सत्यापन</span>
            </div>
            <div className="hidden truncate text-2xs text-slate-500 md:block">
              Multimedia evidence authentication · Deepfake detection · Provenance
            </div>
          </div>
        </Link>
        <div className="ml-auto flex items-center gap-2.5">
          {activeCaseId && <CustodyPill caseId={activeCaseId} />}
          <ModelsPill />
          <span
            className="hidden items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/[0.06] px-3 py-1.5 text-xs text-cyan-100/90 md:flex"
            title="All analysis runs locally. Uploads are hashed, stored write-once and never sent anywhere."
          >
            <WifiOff className="h-3.5 w-3.5 text-accent" />
            <span className="font-medium">Air-gapped</span>
            <span className="hidden text-cyan-100/60 xl:inline">· no evidence leaves this workstation</span>
          </span>
        </div>
      </div>
    </header>
  );
}
