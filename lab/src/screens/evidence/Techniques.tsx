import { AnimatePresence, motion } from "framer-motion";
import {
  Ban,
  BookOpen,
  Check,
  ChevronDown,
  ChevronsDownUp,
  ChevronsUpDown,
  Clock,
  ImageIcon,
  PlugZap,
  TriangleAlert,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { urls, type EvidenceAnalysis, type Finding, type TechniqueResult } from "../../api";
import { Lightbox, type LightboxItem } from "../../components/Modal";
import { cx, SafeImg, StrengthMeter } from "../../components/ui";
import { displayValue, formatDurationMs, humanize } from "../../lib/format";
import { CATEGORY_META, CATEGORY_ORDER, hypothesisMeta, strengthWord, techStatusMeta } from "../../lib/verdict";
import { TechniqueData } from "./DataViews";

const STATUS_ICON = {
  ok: Check,
  skipped: Ban,
  unavailable: PlugZap,
  error: X,
} as const;

/** The strongest non-neutral finding of a technique (for the collapsed row). */
export function strongestFinding(t: TechniqueResult): Finding | null {
  let best: Finding | null = null;
  for (const f of t.findings) {
    if (f.hypothesis === "neutral") continue;
    if (!best || f.strength > best.strength) best = f;
  }
  return best;
}

function FindingCard({ f, onArtifact }: { f: Finding; onArtifact: (name: string) => void }) {
  const h = hypothesisMeta(f.hypothesis);
  const neutral = f.hypothesis === "neutral";
  const obs = Object.entries(f.observations ?? {}).filter(([, v]) => v !== null && v !== "" && !(Array.isArray(v) && v.length === 0));
  return (
    <div className="relative overflow-hidden rounded-xl border border-white/[0.07] bg-ink-950/40 p-3.5 pl-4">
      <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: neutral ? "#334155" : h.hex }} />
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-100">{f.title}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-2xs text-slate-500">
            <span className="font-mono">{f.code}</span>
            <span>·</span>
            <span className={neutral ? "text-slate-400" : h.text}>{neutral ? "informational (no evidential weight)" : `supports: ${h.label.toLowerCase()}`}</span>
            {f.score !== null && Number.isFinite(f.score) && (
              <>
                <span>·</span>
                <span className="font-mono">score {displayValue(f.score)}</span>
              </>
            )}
          </div>
        </div>
        {!neutral && <StrengthMeter strength={f.strength} hypothesis={f.hypothesis} showWord />}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">{f.detail}</p>
      {(f.regions.length > 0 || f.spans.length > 0 || obs.length > 0 || f.artifacts.length > 0) && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          {f.regions.length > 0 && <span className="chip-muted normal-case tracking-normal">{f.regions.length} region(s) marked on the image</span>}
          {f.spans.length > 0 && (
            <span className="chip-muted normal-case tracking-normal">
              {f.spans.length} time span(s): {f.spans.slice(0, 3).map((s) => `${s.start_s.toFixed(1)}–${s.end_s.toFixed(1)} s`).join(", ")}
              {f.spans.length > 3 ? "…" : ""}
            </span>
          )}
          {obs.slice(0, 6).map(([k, v]) => (
            <span key={k} className="chip-muted normal-case tracking-normal">
              {humanize(k)}: <span className="font-mono text-slate-300">{displayValue(v, 40)}</span>
            </span>
          ))}
          {f.artifacts.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => onArtifact(a)}
              className="chip border-accent/30 bg-accent/10 normal-case tracking-normal text-accent-soft hover:bg-accent/20"
              title={`Open ${a}`}
            >
              <ImageIcon className="h-3 w-3" /> {a}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function HowItWorks({ t }: { t: TechniqueResult }) {
  const [open, setOpen] = useState(false);
  if (!t.method && !t.reference && !t.limitations) return null;
  return (
    <div className="rounded-xl border border-indigo-400/15 bg-indigo-500/[0.04]">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left">
        <BookOpen className="h-4 w-4 text-indigo-300" />
        <span className="text-xs font-semibold text-indigo-100">How this works</span>
        <span className="text-2xs text-slate-500">method · reference · known limits</span>
        <ChevronDown className={cx("ml-auto h-4 w-4 text-slate-500 transition", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="space-y-3 border-t border-indigo-400/10 px-3.5 py-3 text-sm leading-relaxed">
              {t.method && (
                <div>
                  <div className="eyebrow mb-1">Method</div>
                  <p className="text-slate-300">{t.method}</p>
                </div>
              )}
              {t.limitations && (
                <div>
                  <div className="eyebrow mb-1">Known limitations</div>
                  <p className="text-slate-400">{t.limitations}</p>
                </div>
              )}
              {t.reference && (
                <div>
                  <div className="eyebrow mb-1">Reference</div>
                  <p className="font-mono text-xs text-slate-400">{t.reference}</p>
                </div>
              )}
              <div className="font-mono text-2xs text-slate-600">
                {t.id} · version {t.version}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TechniqueItem({
  t,
  open,
  onToggle,
  evidenceId,
  timeline,
  onArtifact,
}: {
  t: TechniqueResult;
  open: boolean;
  onToggle: () => void;
  evidenceId: string;
  timeline: boolean;
  onArtifact: (name: string) => void;
}) {
  const st = techStatusMeta(t.status);
  const Icon = STATUS_ICON[t.status] ?? TriangleAlert;
  const top = strongestFinding(t);
  const neutralCount = t.findings.filter((f) => f.hypothesis === "neutral").length;
  return (
    <div id={`tech-${t.id}`} className={cx("panel-tight scroll-mt-32 overflow-hidden transition", open && "border-white/[0.12]")}>
      <button type="button" onClick={onToggle} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-white/[0.02]">
        <span className={cx("flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border", st.bg, st.border, st.text)} title={st.label}>
          <Icon className="h-3.5 w-3.5" strokeWidth={2.5} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-slate-100">{t.name}</span>
            {t.status !== "ok" && <span className={cx("chip shrink-0", st.text, st.bg, st.border)}>{st.label}</span>}
          </div>
          <div className="truncate text-xs text-slate-500" title={t.summary}>
            {t.summary || "—"}
          </div>
        </div>
        {top ? (
          <span className="hidden shrink-0 items-center gap-2 sm:flex" title={`${top.title} (${strengthWord(top.strength)})`}>
            <span className={cx("text-2xs font-medium", hypothesisMeta(top.hypothesis).text)}>{hypothesisMeta(top.hypothesis).label}</span>
            <StrengthMeter strength={top.strength} hypothesis={top.hypothesis} />
          </span>
        ) : neutralCount > 0 ? (
          <span className="hidden shrink-0 text-2xs text-slate-600 sm:inline">{neutralCount} note{neutralCount > 1 ? "s" : ""}</span>
        ) : null}
        {t.artifacts.length > 0 && (
          <span className="hidden shrink-0 items-center gap-1 text-2xs text-slate-500 md:inline-flex" title="Figures">
            <ImageIcon className="h-3 w-3" /> {t.artifacts.length}
          </span>
        )}
        <span className="hidden w-16 shrink-0 items-center justify-end gap-1 font-mono text-2xs text-slate-500 md:inline-flex">
          <Clock className="h-3 w-3" />
          {formatDurationMs(t.duration_ms)}
        </span>
        <ChevronDown className={cx("h-4 w-4 shrink-0 text-slate-500 transition", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden"
          >
            <div className="space-y-3 border-t hairline px-4 py-4">
              {t.status === "error" && (
                <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                  This technique failed on this file and is listed as “not checked” (never counted as clean). {t.error ? <span className="font-mono">{t.error}</span> : null}
                </div>
              )}
              {t.status === "unavailable" && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                  The model or dependency for this technique is not installed on this workstation: {t.summary}
                </div>
              )}
              {t.findings.length > 0 && (
                <div className="space-y-2">
                  {[...t.findings]
                    .sort((a, b) => (b.hypothesis === "neutral" ? -1 : b.strength) - (a.hypothesis === "neutral" ? -1 : a.strength))
                    .map((f, i) => (
                      <FindingCard key={`${f.code}-${i}`} f={f} onArtifact={onArtifact} />
                    ))}
                </div>
              )}
              <TechniqueData t={t} timeline={timeline} />
              {t.artifacts.length > 0 && (
                <div>
                  <div className="eyebrow mb-2">Figures</div>
                  <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-4">
                    {t.artifacts.map((a) => (
                      <button
                        key={a.name}
                        type="button"
                        onClick={() => onArtifact(a.name)}
                        className="group overflow-hidden rounded-lg border border-white/[0.08] bg-ink-950/60 text-left transition hover:border-accent/40"
                      >
                        <div className="checker flex h-28 items-center justify-center overflow-hidden">
                          <SafeImg
                            src={urls.artifact(evidenceId, a.name)}
                            alt={a.title}
                            className="max-h-full max-w-full object-contain transition duration-300 group-hover:scale-[1.04]"
                            fallback={<span className="text-2xs text-slate-600">not available</span>}
                          />
                        </div>
                        <div className="px-2 py-1.5">
                          <div className="truncate text-2xs font-medium text-slate-200">{a.title}</div>
                          <div className="truncate text-[10px] text-slate-500">{a.kind}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <HowItWorks t={t} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function TechniqueAccordion({
  analysis,
  evidenceId,
  timeline,
  open,
  setOpen,
}: {
  analysis: EvidenceAnalysis;
  evidenceId: string;
  /** True when a playback timeline above already plots the time-series techniques. */
  timeline: boolean;
  open: Set<string>;
  setOpen: (s: Set<string>) => void;
}) {
  const [lightbox, setLightbox] = useState<number | null>(null);
  const gallery: LightboxItem[] = useMemo(
    () =>
      analysis.techniques.flatMap((t) =>
        t.artifacts.map((a) => ({ src: urls.artifact(evidenceId, a.name), title: `${a.title} · ${t.name}`, caption: a.caption, meta: a.name })),
      ),
    [analysis, evidenceId],
  );
  const openArtifact = (name: string) => {
    const i = gallery.findIndex((g) => g.meta === name);
    setLightbox(i >= 0 ? i : null);
  };
  const groups = CATEGORY_ORDER.map((c) => ({ c, items: analysis.techniques.filter((t) => t.category === c) })).filter((g) => g.items.length);
  const others = analysis.techniques.filter((t) => !CATEGORY_ORDER.includes(t.category));
  if (others.length) groups.push({ c: "content", items: others });
  const all = analysis.techniques.map((t) => t.id);
  const allOpen = all.every((id) => open.has(id));
  const ran = analysis.techniques.filter((t) => t.status === "ok").length;
  const total = analysis.techniques.reduce((a, t) => a + t.duration_ms, 0);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Techniques applied</h2>
          <div className="text-xs text-slate-500">
            {ran} of {analysis.techniques.length} ran on this file · {formatDurationMs(total)} of compute · grouped by what they examine
          </div>
        </div>
        <button type="button" className="btn-ghost btn-sm" onClick={() => setOpen(allOpen ? new Set() : new Set(all))}>
          {allOpen ? <ChevronsDownUp className="h-3.5 w-3.5" /> : <ChevronsUpDown className="h-3.5 w-3.5" />}
          {allOpen ? "Collapse all" : "Expand all"}
        </button>
      </div>
      <div className="space-y-5">
        {groups.map(({ c, items }) => {
          const nFind = items.reduce((a, t) => a + t.findings.filter((f) => f.hypothesis !== "neutral" && f.strength > 0).length, 0);
          return (
            <section key={c}>
              <div className="mb-2 flex items-baseline gap-3">
                <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-accent/90">{CATEGORY_META[c].label}</h3>
                <span className="text-2xs text-slate-500">{CATEGORY_META[c].blurb}</span>
                <span className="ml-auto font-mono text-2xs text-slate-500">
                  {items.length} technique{items.length > 1 ? "s" : ""}
                  {nFind ? ` · ${nFind} indicator${nFind > 1 ? "s" : ""}` : ""}
                </span>
              </div>
              <div className="space-y-2">
                {items.map((t) => (
                  <TechniqueItem
                    key={t.id}
                    t={t}
                    open={open.has(t.id)}
                    evidenceId={evidenceId}
                    timeline={timeline}
                    onArtifact={openArtifact}
                    onToggle={() => {
                      const n = new Set(open);
                      if (n.has(t.id)) n.delete(t.id);
                      else n.add(t.id);
                      setOpen(n);
                    }}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
      <Lightbox items={gallery} index={lightbox} onIndex={setLightbox} onClose={() => setLightbox(null)} />
    </div>
  );
}
