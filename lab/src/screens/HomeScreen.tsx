import { motion } from "framer-motion";
import {
  ArrowRight,
  Boxes,
  Building2,
  CalendarClock,
  FlaskConical,
  FolderOpen,
  Gavel,
  Layers,
  Loader2,
  Plus,
  ShieldAlert,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, demoCaseId, type CaseIn, type CaseSummary } from "../api";
import { Modal } from "../components/Modal";
import {
  cx,
  DistributionBar,
  DistributionLegend,
  EmptyState,
  ErrorState,
  ExhibitBadge,
  LoadingState,
  MediaIcon,
  SafeImg,
} from "../components/ui";
import { useLab, useToast } from "../context";
import { formatIST } from "../lib/format";
import { useAsync, useCountUp } from "../lib/hooks";
import { thumbUrl } from "../lib/media";
import { CATEGORY_META, CATEGORY_ORDER, evidenceMeta, verdictDistribution } from "../lib/verdict";

// ------------------------------------------------------------------ stat tiles

function StatTile({
  icon,
  label,
  value,
  hint,
  tone,
  pulse,
  delay = 0,
}: {
  icon: ReactNode;
  label: string;
  value: number | null;
  hint: string;
  tone: string;
  pulse?: boolean;
  delay?: number;
}) {
  const shown = useCountUp(value ?? 0, 900);
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="panel overflow-hidden p-5"
    >
      <div
        className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full opacity-[0.16] blur-2xl"
        style={{ background: tone }}
      />
      <div className="flex items-center justify-between">
        <div className="eyebrow">{label}</div>
        <div
          className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03]"
          style={{ color: tone }}
        >
          {pulse && <span className="absolute inset-0 animate-pulse-ring rounded-lg border" style={{ borderColor: tone }} />}
          {icon}
        </div>
      </div>
      <div className="mt-3 font-mono text-4xl font-semibold tabular tracking-tight text-white">
        {value === null ? "—" : Math.round(shown)}
      </div>
      <div className="mt-1 text-xs text-slate-500">{hint}</div>
    </motion.div>
  );
}

// ------------------------------------------------------------------ case card

function CaseCard({ c, index }: { c: CaseSummary; index: number }) {
  const view = useAsync(() => api.caseView(c.id), `${c.id}:${c.evidence_count}:${c.pending}:${c.flagged}`, {
    pollMs: c.pending > 0 ? 4000 : null,
  });
  const evidence = view.data?.evidence ?? [];
  const parts = verdictDistribution(evidence);
  const thumbs = evidence.slice(0, 6);
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 * index, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    >
      <Link
        to={`/cases/${c.id}`}
        className="panel group block p-5 transition duration-200 hover:-translate-y-0.5 hover:border-accent/30 hover:shadow-glow"
      >
        <ArrowRight className="absolute right-5 top-5 h-5 w-5 text-slate-600 transition group-hover:translate-x-1 group-hover:text-accent" />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0 pr-6 lg:pr-0">
            <div className="flex flex-wrap items-center gap-2">
              {c.fir_number && (
                <span className="chip border-accent/30 bg-accent/10 font-mono normal-case tracking-normal text-accent-soft">
                  {c.fir_number}
                </span>
              )}
              {c.demo && <span className="chip border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-200">Demo</span>}
              <span className="chip-muted">{c.status}</span>
            </div>
            <h3 className="mt-2 truncate text-lg font-semibold text-white group-hover:text-accent-soft">{c.title}</h3>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
              {c.police_station && (
                <span className="inline-flex items-center gap-1.5">
                  <Building2 className="h-3.5 w-3.5 text-slate-500" />
                  {c.police_station}
                  {c.district || c.state ? `, ${[c.district, c.state].filter(Boolean).join(", ")}` : ""}
                </span>
              )}
              {c.investigating_officer && (
                <span className="inline-flex items-center gap-1.5">
                  <UserRound className="h-3.5 w-3.5 text-slate-500" />
                  IO {c.investigating_officer}
                </span>
              )}
              <span className="inline-flex items-center gap-1.5">
                <CalendarClock className="h-3.5 w-3.5 text-slate-500" />
                {formatIST(c.created_at)} IST
              </span>
            </div>
            {c.offence_sections && (
              <div className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-slate-500">
                <Gavel className="h-3.5 w-3.5" />
                <span className="text-slate-300">{c.offence_sections}</span>
              </div>
            )}
            {thumbs.length > 0 && (
              <div className="mt-4 flex gap-2">
                {thumbs.map((e) => {
                  const meta = evidenceMeta(e);
                  return (
                    <div
                      key={e.id}
                      className="relative h-14 w-[76px] shrink-0 overflow-hidden rounded-md border bg-ink-900"
                      style={{ borderColor: `${meta.hex}55` }}
                      title={`${e.exhibit} · ${e.filename} · ${meta.label}`}
                    >
                      <SafeImg
                        src={thumbUrl(e)}
                        alt={e.filename}
                        className="h-full w-full object-cover opacity-85"
                        fallback={
                          <div className="flex h-full w-full items-center justify-center text-slate-600">
                            <MediaIcon kind={e.kind} />
                          </div>
                        }
                      />
                      <ExhibitBadge exhibit={e.exhibit} role={e.role} size="sm" className="absolute left-1 top-1" />
                      <span className="absolute inset-x-0 bottom-0 h-[3px]" style={{ background: meta.hex }} />
                    </div>
                  );
                })}
                {evidence.length > thumbs.length && (
                  <div className="flex h-14 w-12 items-center justify-center rounded-md border border-white/[0.06] font-mono text-xs text-slate-500">
                    +{evidence.length - thumbs.length}
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="flex flex-col justify-center gap-3 rounded-xl border border-white/[0.06] bg-ink-900/40 p-3.5 lg:mt-7">
            <div className="grid grid-cols-3 gap-2">
              {[
                { k: "Exhibits", v: c.evidence_count, cls: "text-white" },
                { k: "Flagged", v: c.flagged, cls: c.flagged ? "text-verdict-synthetic" : "text-slate-300" },
                { k: "Pending", v: c.pending, cls: c.pending ? "text-accent" : "text-slate-300" },
              ].map((s) => (
                <div key={s.k}>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">{s.k}</div>
                  <div className={cx("font-mono text-2xl font-semibold tabular", s.cls)}>{s.v}</div>
                </div>
              ))}
            </div>
            <DistributionBar parts={parts} />
            {parts.length > 0 ? (
              <DistributionLegend parts={parts} />
            ) : (
              <div className="text-2xs text-slate-600">{view.loading ? "Loading verdicts…" : "No exhibits yet"}</div>
            )}
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

// ------------------------------------------------------------------ engine panel

function EnginePanel() {
  const { health, techniques } = useLab();
  const models = health ? Object.values(health.models) : [];
  const byCat = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const t of techniques) m.set(t.category, [...(m.get(t.category) ?? []), t.name]);
    return m;
  }, [techniques]);
  const kinds = useMemo(() => new Set(techniques.flatMap((t) => t.kinds)).size, [techniques]);
  return (
    <div className="panel p-5">
      <div className="flex items-center justify-between">
        <h3 className="panel-title">
          <FlaskConical className="h-4 w-4 text-accent" /> Forensic engine
        </h3>
        {health && <span className="font-mono text-2xs text-slate-500">v{health.engine}</span>}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg border border-white/[0.06] bg-ink-900/50 py-2.5">
          <div className="font-mono text-2xl font-semibold text-white">{techniques.length || "—"}</div>
          <div className="text-2xs uppercase tracking-wider text-slate-500">techniques</div>
        </div>
        <div className="rounded-lg border border-white/[0.06] bg-ink-900/50 py-2.5">
          <div className="font-mono text-2xl font-semibold text-white">
            {models.filter((m) => m.available).length || "—"}
            <span className="text-base text-slate-500">/{models.length || "—"}</span>
          </div>
          <div className="text-2xs uppercase tracking-wider text-slate-500">models ready</div>
        </div>
        <div className="rounded-lg border border-white/[0.06] bg-ink-900/50 py-2.5">
          <div className="font-mono text-2xl font-semibold text-white">{kinds || "—"}</div>
          <div className="text-2xs uppercase tracking-wider text-slate-500">media types</div>
        </div>
      </div>
      <div className="mt-5 space-y-3.5">
        {CATEGORY_ORDER.filter((c) => byCat.has(c)).map((c) => (
          <div key={c}>
            <div className="flex items-baseline justify-between">
              <div className="text-xs font-semibold text-slate-200">{CATEGORY_META[c].label}</div>
              <div className="font-mono text-2xs text-slate-500">{byCat.get(c)?.length}</div>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {(byCat.get(c) ?? []).map((n) => (
                <span key={n} className="rounded border border-white/[0.06] bg-white/[0.025] px-1.5 py-0.5 text-2xs text-slate-400">
                  {n}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-5 rounded-xl border border-white/[0.06] bg-ink-900/40 p-3 text-xs leading-relaxed text-slate-400">
        Each finding is graded on the ENFSI verbal scale (weak → very strong support). The verdict is derived from the
        findings by a fixed, published rule table and always lists what could not be checked.
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ new case

const EMPTY_CASE: CaseIn = {
  title: "",
  fir_number: "",
  police_station: "",
  district: "",
  state: "",
  offence_sections: "",
  investigating_officer: "",
  examiner: "",
  lab_name: "Satyapan Multimedia Forensic Lab",
  summary: "",
};

const CASE_FIELDS: { key: keyof CaseIn; label: string; placeholder: string; span?: 2 }[] = [
  { key: "title", label: "Case title *", placeholder: "Deepfake video call extortion of a senior citizen", span: 2 },
  { key: "fir_number", label: "FIR No.", placeholder: "FIR No. 0457/2026" },
  { key: "police_station", label: "Police station", placeholder: "Cyber Crime PS" },
  { key: "district", label: "District", placeholder: "South-West, New Delhi" },
  { key: "state", label: "State / UT", placeholder: "Delhi" },
  { key: "offence_sections", label: "Offence sections", placeholder: "BNS 318(4)/319(2), IT Act 66C/66D", span: 2 },
  { key: "investigating_officer", label: "Investigating officer", placeholder: "Insp. R. Verma" },
  { key: "examiner", label: "Examiner", placeholder: "Dr. A. Rao, Scientific Officer (Cyber)" },
  { key: "lab_name", label: "Laboratory", placeholder: "Satyapan Multimedia Forensic Lab", span: 2 },
];

function NewCaseModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form, setForm] = useState<CaseIn>(EMPTY_CASE);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const navigate = useNavigate();
  const { push } = useToast();
  useEffect(() => {
    if (open) {
      setForm(EMPTY_CASE);
      setErr(null);
    }
  }, [open]);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) {
      setErr("A case title is required.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const c = await api.createCase({ ...form, title: form.title.trim() });
      push({ tone: "success", title: "Case opened", body: `${c.fir_number || c.title}: custody log started.` });
      onClose();
      navigate(`/cases/${c.id}`);
    } catch (ex) {
      setErr(ex instanceof ApiError ? ex.detail : String(ex));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Open a new case"
      subtitle="The case is written to the hash-chained custody log the moment it is created."
      width="max-w-3xl"
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="new-case" className="btn-primary" disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Open case
          </button>
        </>
      }
    >
      <form id="new-case" onSubmit={submit} className="grid grid-cols-2 gap-x-4 gap-y-3.5">
        {CASE_FIELDS.map((f) => (
          <div key={f.key} className={f.span === 2 ? "col-span-2" : ""}>
            <label className="label" htmlFor={`case-${f.key}`}>
              {f.label}
            </label>
            <input
              id={`case-${f.key}`}
              className="input"
              placeholder={f.placeholder}
              value={form[f.key]}
              autoFocus={f.key === "title"}
              maxLength={f.key === "title" ? 200 : 300}
              onChange={(e) => setForm((s) => ({ ...s, [f.key]: e.target.value }))}
            />
          </div>
        ))}
        <div className="col-span-2">
          <label className="label" htmlFor="case-summary">
            Brief facts
          </label>
          <textarea
            id="case-summary"
            className="input min-h-[84px] resize-y"
            placeholder="Complainant received a WhatsApp video call showing a fabricated intimate video and a voice note demanding ₹50,000 via UPI…"
            value={form.summary}
            onChange={(e) => setForm((s) => ({ ...s, summary: e.target.value }))}
          />
        </div>
        {err && <div className="col-span-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{err}</div>}
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ demo loader

let demoUnavailable: string | null = null;

function DemoButton() {
  const [state, setState] = useState<"idle" | "loading" | "unavailable">(demoUnavailable ? "unavailable" : "idle");
  const navigate = useNavigate();
  const { push } = useToast();
  const load = async () => {
    setState("loading");
    try {
      const body = await api.loadDemo();
      const id = demoCaseId(body);
      push({ tone: "success", title: "Demo case loaded", body: "Exhibits are being analysed live." });
      setState("idle");
      navigate(id ? `/cases/${id}` : "/");
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      demoUnavailable =
        status === 404
          ? "The demo dataset is not installed on this workstation."
          : "The demo loader is not available on this workstation.";
      setState("unavailable");
      push({ tone: "warn", title: "Demo case unavailable", body: demoUnavailable });
    }
  };
  return (
    <button
      type="button"
      className="btn-secondary"
      onClick={() => void load()}
      disabled={state !== "idle"}
      title={state === "unavailable" ? (demoUnavailable ?? "") : "Load the scripted demo case (fake data)"}
    >
      {state === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4 text-fuchsia-300" />}
      {state === "unavailable" ? "Demo unavailable" : "Load demo case"}
    </button>
  );
}

// ------------------------------------------------------------------ screen

export function HomeScreen() {
  const { setActiveCaseId, health, techniques } = useLab();
  const techniqueCount = health?.techniques ?? techniques.length;
  useEffect(() => setActiveCaseId(null), [setActiveCaseId]);
  const [pollFast, setPollFast] = useState(false);
  const cases = useAsync(api.cases, "cases", { pollMs: pollFast ? 3000 : 10000 });
  const list = cases.data ?? [];
  useEffect(() => setPollFast(list.some((c) => c.pending > 0)), [list]);
  const [showNew, setShowNew] = useState(false);
  const totals = useMemo(
    () => ({
      cases: list.length,
      exhibits: list.reduce((a, c) => a + c.evidence_count, 0),
      flagged: list.reduce((a, c) => a + c.flagged, 0),
      pending: list.reduce((a, c) => a + c.pending, 0),
    }),
    [list],
  );
  const loaded = cases.data !== null;

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow text-accent/80">Case files</div>
          <h1 className="mt-1 text-[28px] font-semibold tracking-tight text-white">Forensic examination workstation</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Authenticate images, voice notes and videos seized in cyber-crime investigations. Every exhibit is hashed on
            intake, stored write-once and examined by{" "}
            {techniqueCount ? `${techniqueCount} independent techniques` : "independent techniques"}, with a court-ready
            report.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DemoButton />
          <button type="button" className="btn-primary" onClick={() => setShowNew(true)}>
            <Plus className="h-4 w-4" /> New case
          </button>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile icon={<FolderOpen className="h-4 w-4" />} label="Cases" value={loaded ? totals.cases : null} hint="Open case files" tone="#22d3ee" />
        <StatTile
          icon={<Boxes className="h-4 w-4" />}
          label="Exhibits"
          value={loaded ? totals.exhibits : null}
          hint="Questioned + reference items"
          tone="#a78bfa"
          delay={0.05}
        />
        <StatTile
          icon={<ShieldAlert className="h-4 w-4" />}
          label="Flagged"
          value={loaded ? totals.flagged : null}
          hint="Synthetic, manipulated or suspicious"
          tone="#ff4d6d"
          delay={0.1}
        />
        <StatTile
          icon={<Layers className="h-4 w-4" />}
          label="Pending"
          value={loaded ? totals.pending : null}
          hint={totals.pending ? "Being analysed right now" : "Analysis queue is empty"}
          tone="#2dd4bf"
          pulse={totals.pending > 0}
          delay={0.15}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div>
          {cases.error && !cases.data ? (
            <div className="panel">
              <ErrorState error={cases.error} onRetry={() => void cases.reload()} />
            </div>
          ) : !loaded ? (
            <div className="panel">
              <LoadingState label="Reading case files…" />
            </div>
          ) : list.length === 0 ? (
            <div className="panel">
              <EmptyState
                title="No cases yet"
                body="Open a case for the FIR, then drop the seized images, audio and video into it. Analysis starts immediately and runs on this workstation."
                action={
                  <div className="mt-2 flex gap-2">
                    <button type="button" className="btn-primary" onClick={() => setShowNew(true)}>
                      <Plus className="h-4 w-4" /> New case
                    </button>
                    <DemoButton />
                  </div>
                }
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
              {[...list]
                .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
                .map((c, i) => (
                  <CaseCard key={c.id} c={c} index={i} />
                ))}
            </div>
          )}
        </div>
        <EnginePanel />
      </div>
      <NewCaseModal open={showNew} onClose={() => setShowNew(false)} />
    </div>
  );
}
