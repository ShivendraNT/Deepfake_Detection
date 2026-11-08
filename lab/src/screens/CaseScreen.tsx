import { motion } from "framer-motion";
import {
  ArrowLeft,
  Building2,
  CalendarClock,
  FileStack,
  FlaskConical,
  Gavel,
  Link2,
  MapPin,
  Network,
  ScrollText,
  ShieldCheck,
  UserRound,
  UserSquare2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type CaseView } from "../api";
import { cx, DistributionBar, DistributionLegend, ErrorState, LoadingState } from "../components/ui";
import { useLab } from "../context";
import { formatIST } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { groupLinks } from "../lib/links";
import { isFlagged, isPending, verdictDistribution } from "../lib/verdict";
import { CustodyTab } from "./case/CustodyTab";
import { ExhibitsTab } from "./case/ExhibitsTab";
import { GraphTab } from "./case/GraphTab";
import { ReportsTab } from "./case/ReportsTab";

const TABS = [
  { id: "exhibits", label: "Exhibits", icon: FileStack },
  { id: "graph", label: "Provenance graph", icon: Network },
  { id: "custody", label: "Chain of custody", icon: Link2 },
  { id: "reports", label: "Reports", icon: ScrollText },
] as const;
type TabId = (typeof TABS)[number]["id"];

function Fact({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 text-2xs uppercase tracking-wider text-slate-500">
        {icon}
        {label}
      </div>
      <div className="mt-0.5 truncate text-sm text-slate-200" title={typeof children === "string" ? children : undefined}>
        {children || <span className="text-slate-600">—</span>}
      </div>
    </div>
  );
}

function CaseHeader({ view, compact }: { view: CaseView; compact: boolean }) {
  const c = view.case;
  const parts = verdictDistribution(view.evidence);
  const flagged = view.evidence.filter((e) => isFlagged(e.verdict)).length;
  const pending = view.evidence.filter((e) => isPending(e.status)).length;
  const links = groupLinks(view.links).length;
  if (compact) {
    return (
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="panel overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent" />
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              {c.fir_number && (
                <span className="chip border-accent/30 bg-accent/10 font-mono text-xs normal-case tracking-normal text-accent-soft">
                  {c.fir_number}
                </span>
              )}
              <h1 className="truncate text-lg font-semibold tracking-tight text-white">{c.title}</h1>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
              {c.police_station && (
                <span className="inline-flex items-center gap-1.5">
                  <Building2 className="h-3.5 w-3.5 text-slate-500" />
                  {[c.police_station, c.district, c.state].filter(Boolean).join(", ")}
                </span>
              )}
              {c.offence_sections && (
                <span className="inline-flex items-center gap-1.5">
                  <Gavel className="h-3.5 w-3.5 text-slate-500" />
                  {c.offence_sections}
                </span>
              )}
              {c.investigating_officer && (
                <span className="inline-flex items-center gap-1.5">
                  <UserRound className="h-3.5 w-3.5 text-slate-500" />
                  IO {c.investigating_officer}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-5">
            {[
              { k: "Exhibits", v: view.evidence.length, cls: "text-white" },
              { k: "Flagged", v: flagged, cls: flagged ? "text-verdict-synthetic" : "text-slate-300" },
              { k: "Pending", v: pending, cls: pending ? "text-accent" : "text-slate-300" },
              { k: "Links", v: links, cls: "text-slate-200" },
            ].map((s) => (
              <div key={s.k} className="text-center">
                <div className={cx("font-mono text-xl font-semibold leading-none tabular", s.cls)}>{s.v}</div>
                <div className="mt-1 text-[10px] uppercase tracking-wider text-slate-500">{s.k}</div>
              </div>
            ))}
            <div className="w-40">
              <DistributionBar parts={parts} />
            </div>
          </div>
        </div>
      </motion.div>
    );
  }
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="panel overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent" />
      <div className="grid grid-cols-1 gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {c.fir_number && (
              <span className="chip border-accent/30 bg-accent/10 font-mono text-xs normal-case tracking-normal text-accent-soft">
                {c.fir_number}
              </span>
            )}
            <span className="chip-muted">{c.status}</span>
            {c.demo && <span className="chip border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-200">Demo data</span>}
            <span className="font-mono text-2xs text-slate-600">{c.id}</span>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">{c.title}</h1>
          {c.summary && <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-slate-400">{c.summary}</p>}
          <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3 2xl:grid-cols-6">
            <Fact icon={<Building2 className="h-3 w-3" />} label="Police station">
              {c.police_station}
            </Fact>
            <Fact icon={<MapPin className="h-3 w-3" />} label="District / State">
              {[c.district, c.state].filter(Boolean).join(", ")}
            </Fact>
            <Fact icon={<Gavel className="h-3 w-3" />} label="Sections">
              {c.offence_sections}
            </Fact>
            <Fact icon={<UserRound className="h-3 w-3" />} label="Investigating officer">
              {c.investigating_officer}
            </Fact>
            <Fact icon={<UserSquare2 className="h-3 w-3" />} label="Examiner">
              {c.examiner}
            </Fact>
            <Fact icon={<CalendarClock className="h-3 w-3" />} label="Opened (IST)">
              {formatIST(c.created_at)}
            </Fact>
          </div>
        </div>
        <div className="rounded-xl border border-white/[0.06] bg-ink-900/50 p-4">
          <div className="flex items-center justify-between">
            <div className="eyebrow">Examination status</div>
            <FlaskConical className="h-3.5 w-3.5 text-slate-600" />
          </div>
          <div className="mt-3 grid grid-cols-4 gap-2 text-center">
            {[
              { k: "Exhibits", v: view.evidence.length, cls: "text-white" },
              { k: "Flagged", v: flagged, cls: flagged ? "text-verdict-synthetic" : "text-slate-300" },
              { k: "Pending", v: pending, cls: pending ? "text-accent" : "text-slate-300" },
              { k: "Links", v: links, cls: "text-slate-200" },
            ].map((s) => (
              <div key={s.k}>
                <div className={cx("font-mono text-2xl font-semibold tabular", s.cls)}>{s.v}</div>
                <div className="text-2xs uppercase tracking-wider text-slate-500">{s.k}</div>
              </div>
            ))}
          </div>
          <DistributionBar parts={parts} className="mt-4" />
          <div className="mt-2">
            <DistributionLegend parts={parts} />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/** Plain-language case findings from the backend (GET /cases/{id} → findings.sentences). */
function CaseFindingsPanel({ view }: { view: CaseView }) {
  const sentences = (view.findings?.sentences ?? []).filter((s) => typeof s === "string" && s.trim());
  if (!sentences.length) return null;
  const [summary, ...rest] = sentences;
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="panel p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="panel-title">
          <ScrollText className="h-4 w-4 text-accent" /> Case findings
        </h3>
        <span className="text-2xs text-slate-500">written by the lab engine from the stored results</span>
      </div>
      {summary && <p className="text-sm font-medium leading-relaxed text-slate-100">{summary}</p>}
      {rest.length > 0 && (
        <ul className="mt-2.5 grid grid-cols-1 gap-x-8 gap-y-1.5 lg:grid-cols-2">
          {rest.map((s, i) => (
            <li key={i} className="flex items-start gap-2 text-sm leading-relaxed text-slate-300">
              <span className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-accent/70" />
              <span>{s}</span>
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  );
}

export function CaseScreen() {
  const { caseId = "", tab } = useParams();
  const navigate = useNavigate();
  const { setActiveCaseId, bumpCustody } = useLab();
  useEffect(() => {
    setActiveCaseId(caseId);
    return () => setActiveCaseId(null);
  }, [caseId, setActiveCaseId]);

  const active: TabId = (TABS.find((t) => t.id === tab)?.id ?? "exhibits") as TabId;
  const view = useAsync(() => api.caseView(caseId), caseId);
  const pending = useMemo(() => (view.data?.evidence ?? []).filter((e) => isPending(e.status)).length, [view.data]);

  // Poll while anything is queued or analysing; slow background refresh otherwise.
  const reload = view.reload;
  useEffect(() => {
    const t = window.setInterval(() => void reload(), pending > 0 ? 2500 : 15000);
    return () => window.clearInterval(t);
  }, [pending, reload]);

  const refresh = useCallback(async () => {
    await reload();
    bumpCustody();
  }, [reload, bumpCustody]);

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
  if (!view.data) return <LoadingState label="Opening case file…" />;
  const data = view.data;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Case files
        </Link>
        <div className="flex items-center gap-1.5 text-2xs text-slate-500">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-400/80" /> Originals stored write-once, named by SHA-256
        </div>
      </div>
      <CaseHeader view={data} compact={active !== "exhibits"} />
      {active === "exhibits" && <CaseFindingsPanel view={data} />}

      <div className="sticky top-16 z-30 -mx-1 border-b border-white/[0.06] bg-ink-950/80 px-1 backdrop-blur-xl">
        <nav className="flex gap-1 overflow-x-auto" role="tablist">
          {TABS.map((t) => {
            const Icon = t.icon;
            const on = t.id === active;
            const count =
              t.id === "exhibits"
                ? data.evidence.length
                : t.id === "graph"
                  ? groupLinks(data.links).length
                  : t.id === "reports"
                    ? data.reports.length
                    : null;
            return (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={on}
                onClick={() => navigate(t.id === "exhibits" ? `/cases/${caseId}` : `/cases/${caseId}/${t.id}`)}
                className={cx(
                  "relative flex items-center gap-2 whitespace-nowrap px-4 py-3 text-sm font-medium transition",
                  on ? "text-white" : "text-slate-400 hover:text-slate-200",
                )}
              >
                <Icon className={cx("h-4 w-4", on ? "text-accent" : "text-slate-500")} />
                {t.label}
                {count !== null && (
                  <span
                    className={cx(
                      "rounded-md px-1.5 py-px font-mono text-2xs",
                      on ? "bg-accent/15 text-accent-soft" : "bg-white/[0.05] text-slate-500",
                    )}
                  >
                    {count}
                  </span>
                )}
                {on && (
                  <motion.span
                    layoutId="case-tab"
                    className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent shadow-[0_0_12px_rgba(34,211,238,0.8)]"
                  />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      <motion.div key={active} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
        {active === "exhibits" && <ExhibitsTab view={data} onChanged={refresh} />}
        {active === "graph" && <GraphTab view={data} />}
        {active === "custody" && <CustodyTab view={data} />}
        {active === "reports" && <ReportsTab view={data} onChanged={refresh} />}
      </motion.div>
    </div>
  );
}
