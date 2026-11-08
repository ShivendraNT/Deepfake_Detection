import { motion } from "framer-motion";
import {
  AppWindow,
  BadgeCheck,
  Bot,
  CalendarClock,
  Camera,
  CircleSlash,
  Fingerprint,
  GitBranch,
  GitCompareArrows,
  MapPin,
  Quote,
  ShieldAlert,
  ShieldCheck,
  Share2,
  Stamp,
} from "lucide-react";
import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { urls, type EvidenceAnalysis, type EvidenceLink, type LabEvidence } from "../../api";
import { RiskGauge } from "../../components/RiskGauge";
import { CopyButton, cx, ExhibitBadge, MediaIcon, SafeImg, SectionTitle, StrengthMeter, ToneBadge } from "../../components/ui";
import { formatBytes, formatDurationMs, formatIST, parseTime } from "../../lib/format";
import { linkMeta } from "../../lib/links";
import { thumbUrl } from "../../lib/media";
import { evidenceMeta, HYPOTHESIS_META, parseRationale, strengthWord, verdictMeta } from "../../lib/verdict";

// ------------------------------------------------------------------ verdict

export function VerdictPanel({
  analysis,
  onFinding,
}: {
  analysis: EvidenceAnalysis;
  onFinding: (code: string) => void;
}) {
  const v = analysis.verdict;
  if (!v) {
    return (
      <div className="panel p-5 text-sm text-slate-400">
        <SectionTitle icon={<Stamp className="h-4 w-4" />}>Verdict</SectionTitle>
        No verdict was produced for this exhibit.
      </div>
    );
  }
  const meta = verdictMeta(v.label);
  const findings = analysis.techniques.flatMap((t) => t.findings.map((f) => ({ ...f, techniqueName: t.name })));
  const hyps = (["synthetic", "manipulated", "authentic"] as const).map((h) => ({ h, s: v.hypotheses[h] ?? 0 }));
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="panel overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-28" style={{ background: `radial-gradient(420px 120px at 30% 0%, ${meta.hex}26, transparent 70%)` }} />
      <div className="relative p-5">
        <SectionTitle icon={<Stamp className="h-4 w-4" />} right={<span className="font-mono text-2xs text-slate-500">rule table · engine {analysis.engine_version}</span>}>
          Verdict
        </SectionTitle>
        <div className="flex items-center gap-4">
          <div className="shrink-0">
            <RiskGauge value={v.risk_index} color={meta.hex} size={132} stroke={10} />
          </div>
          <div className="min-w-0">
            <motion.div
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
              className="text-[26px] font-bold uppercase leading-none tracking-tight"
              style={{ color: meta.hex, textShadow: `0 0 28px ${meta.hex}55` }}
            >
              {meta.label}
            </motion.div>
            <div className="mt-2 text-sm font-medium leading-snug text-slate-100">{v.headline}</div>
            <div className="mt-2 text-2xs text-slate-500">
              Confidence: <span className="font-semibold text-slate-200">{v.confidence}</span>
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          {hyps.map(({ h, s }) => (
            <div key={h} className="rounded-lg border border-white/[0.06] bg-ink-950/40 px-2.5 py-2">
              <div className="text-2xs uppercase tracking-wider text-slate-500">{HYPOTHESIS_META[h].label}</div>
              <StrengthMeter strength={s} hypothesis={h} className="mt-1.5" />
              <div className={cx("mt-1 text-2xs", s > 0 ? HYPOTHESIS_META[h].text : "text-slate-600")}>{strengthWord(s)}</div>
            </div>
          ))}
        </div>

        <figure className="mt-4 rounded-xl border border-white/[0.07] bg-ink-950/50 p-4">
          <div className="eyebrow mb-1.5 flex items-center gap-1.5">
            <Quote className="h-3 w-3" /> ENFSI evaluative statement
          </div>
          <blockquote className="text-sm leading-relaxed text-slate-200">{v.statement}</blockquote>
        </figure>

        {v.rationale.length > 0 && (
          <div className="mt-4">
            <div className="eyebrow mb-2">Key findings</div>
            <ul className="space-y-1.5">
              {v.rationale.map((line, i) => {
                const r = parseRationale(line);
                const code = v.key_findings[i];
                const f = findings.find((x) => x.code === code);
                return (
                  <li key={i}>
                    <button
                      type="button"
                      onClick={() => code && onFinding(code)}
                      className="group flex w-full items-start gap-2.5 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-left transition hover:border-white/15 hover:bg-white/[0.05]"
                    >
                      <StrengthMeter strength={f?.strength ?? r.strength ?? 0} hypothesis={f?.hypothesis ?? "neutral"} className="mt-1 shrink-0" />
                      <span className="min-w-0">
                        <span className="block text-sm text-slate-100 group-hover:text-white">{r.text}</span>
                        <span className="block text-2xs text-slate-500">
                          {r.word ?? (f ? strengthWord(f.strength) : "")}
                          {f ? ` · ${f.techniqueName}` : ""}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {v.not_checked.length > 0 && (
          <div className="mt-4">
            <div className="eyebrow mb-2">Could not be checked</div>
            <ul className="space-y-1">
              {v.not_checked.map((n, i) => {
                const [name, ...rest] = n.split(": ");
                return (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-400" title={n}>
                    <CircleSlash className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" />
                    <span className="line-clamp-2 min-w-0 break-words">
                      <span className="text-slate-300">{name}</span>
                      {rest.length ? <>: {rest.join(": ")}</> : null}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ------------------------------------------------------------------ integrity

function HashRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="group flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-white/[0.03]">
      <span className="w-14 shrink-0 text-2xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      <span className="min-w-0 flex-1 break-all font-mono text-[11px] leading-snug text-slate-300">{value}</span>
      <CopyButton text={value} className="opacity-60 group-hover:opacity-100" />
    </div>
  );
}

export function IntegrityPanel({ ev, analysis }: { ev: LabEvidence; analysis: EvidenceAnalysis | null }) {
  const h = analysis?.hashes ?? { md5: ev.md5, sha1: ev.sha1, sha256: ev.sha256, size_bytes: ev.size_bytes };
  const matches = !analysis || analysis.hashes.sha256 === ev.sha256;
  const started = parseTime(analysis?.started_at)?.getTime();
  const finished = parseTime(analysis?.finished_at)?.getTime();
  return (
    <div className="panel p-5">
      <SectionTitle icon={<Fingerprint className="h-4 w-4" />}>Integrity</SectionTitle>
      {analysis ? (
        analysis.integrity_verified && matches ? (
          <div className="mb-3 flex items-start gap-2.5 rounded-xl border border-emerald-400/25 bg-emerald-500/[0.07] px-3 py-2.5">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />
            <div>
              <div className="text-sm font-semibold text-emerald-200">Integrity re-verified ✓</div>
              <div className="text-2xs leading-relaxed text-emerald-100/60">
                The stored original was re-hashed before analysis and matches the intake SHA-256.
              </div>
            </div>
          </div>
        ) : (
          <div className="mb-3 flex items-start gap-2.5 rounded-xl border border-red-400/30 bg-red-500/10 px-3 py-2.5">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-red-300" />
            <div className="text-sm font-semibold text-red-200">Integrity NOT verified: hashes differ from intake</div>
          </div>
        )
      ) : null}
      <div className="-mx-2 space-y-0.5">
        <HashRow label="SHA-256" value={h.sha256} />
        <HashRow label="SHA-1" value={h.sha1} />
        <HashRow label="MD5" value={h.md5} />
      </div>
      <dl className="kv mt-3 border-t hairline pt-3 text-xs">
        <dt>Size</dt>
        <dd className="font-mono">
          {formatBytes(h.size_bytes)} <span className="text-slate-500">({h.size_bytes.toLocaleString("en-IN")} bytes)</span>
        </dd>
        <dt>Received</dt>
        <dd>{formatIST(ev.received_at)} IST</dd>
        {ev.received_from && (
          <>
            <dt>Received from</dt>
            <dd>{ev.received_from}</dd>
          </>
        )}
        {analysis && (
          <>
            <dt>Analysed</dt>
            <dd>
              {formatIST(analysis.finished_at ?? analysis.started_at)} IST
              {started && finished ? <span className="text-slate-500"> · took {formatDurationMs(finished - started)}</span> : null}
            </dd>
          </>
        )}
        {analysis &&
          Object.entries(analysis.perceptual).map(([k, val]) => (
            <Fragment key={k}>
              <dt>Perceptual {k}</dt>
              <dd className="font-mono">{val}</dd>
            </Fragment>
          ))}
      </dl>
    </div>
  );
}

// ------------------------------------------------------------------ provenance

function ProvRow({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode | null | undefined }) {
  const empty = value === null || value === undefined || value === "";
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className={cx("mt-0.5 shrink-0", empty ? "text-slate-600" : "text-accent")}>{icon}</span>
      <span className="w-[104px] shrink-0 text-xs text-slate-500">{label}</span>
      <span className={cx("min-w-0 break-words text-sm", empty ? "text-slate-600" : "text-slate-100")}>{empty ? "not recorded" : value}</span>
    </div>
  );
}

export function ProvenancePanel({ analysis }: { analysis: EvidenceAnalysis }) {
  const p = analysis.provenance;
  const gps = p.gps && typeof p.gps.lat === "number" && typeof p.gps.lon === "number" ? p.gps : null;
  return (
    <div className="panel p-5">
      <SectionTitle icon={<GitBranch className="h-4 w-4" />}>Provenance</SectionTitle>
      <div className="divide-y divide-white/[0.04]">
        <ProvRow icon={<Camera className="h-4 w-4" />} label="Device" value={p.device} />
        <ProvRow icon={<AppWindow className="h-4 w-4" />} label="Software" value={p.software} />
        <ProvRow icon={<Share2 className="h-4 w-4" />} label="Platform" value={p.platform} />
        <ProvRow icon={<Bot className="h-4 w-4" />} label="AI generator" value={p.generator} />
        <ProvRow icon={<CalendarClock className="h-4 w-4" />} label="Capture time" value={p.capture_time} />
        <ProvRow
          icon={<MapPin className="h-4 w-4" />}
          label="GPS"
          value={gps ? <span className="font-mono text-xs">{gps.lat?.toFixed(5)}, {gps.lon?.toFixed(5)}</span> : p.gps ? JSON.stringify(p.gps) : null}
        />
        <ProvRow icon={<BadgeCheck className="h-4 w-4" />} label="Content Credentials" value={p.content_credentials} />
      </div>
      <div className="mt-4">
        <div className="eyebrow mb-2">Reconstructed history</div>
        {p.chain.length === 0 ? (
          <div className="rounded-lg border border-dashed border-white/10 px-3 py-3 text-xs text-slate-500">
            No source, device, encoder or platform traces survive in this file (common after messaging apps strip metadata).
          </div>
        ) : (
          <ol className="relative ml-2 space-y-3 border-l border-accent/30 pl-5">
            {p.chain.map((step, i) => (
              <motion.li key={i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 * i }} className="relative">
                <span className="absolute -left-[27px] top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full border border-accent/60 bg-ink-900">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                </span>
                <div className="text-2xs uppercase tracking-wider text-slate-500">{i === 0 ? "oldest trace" : i === p.chain.length - 1 ? "latest trace" : `step ${i + 1}`}</div>
                <div className="text-sm text-slate-200">{step}</div>
              </motion.li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ related exhibits

export function RelatedPanel({
  ev,
  links,
  byId,
  onArtifact,
}: {
  ev: LabEvidence;
  links: EvidenceLink[];
  byId: Map<string, LabEvidence>;
  onArtifact: (src: string, title: string, caption: string) => void;
}) {
  if (!links.length) return null;
  return (
    <div className="panel p-5">
      <SectionTitle icon={<GitCompareArrows className="h-4 w-4" />} right={<span className="font-mono text-2xs text-slate-500">{links.length}</span>}>
        Related exhibits
      </SectionTitle>
      <ul className="space-y-2.5">
        {links.map((l) => {
          const otherId = l.source === ev.id ? l.target : l.source;
          const other = byId.get(otherId);
          const m = linkMeta(l.kind);
          return (
            <li key={`${l.source}-${l.target}-${l.kind}`} className="rounded-xl border border-white/[0.06] bg-ink-950/40 p-3">
              <div className="flex items-center gap-3">
                <Link to={`/evidence/${otherId}`} className="relative h-12 w-16 shrink-0 overflow-hidden rounded-md border border-white/10 bg-ink-900">
                  {other ? (
                    <SafeImg src={thumbUrl(other)} alt={other.filename} className="h-full w-full object-cover" fallback={<div className="flex h-full items-center justify-center text-slate-600"><MediaIcon kind={other.kind} /></div>} />
                  ) : null}
                </Link>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {other && <ExhibitBadge exhibit={other.exhibit} role={other.role} size="sm" />}
                    <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-100">
                      <span className="h-2 w-2 rounded-full" style={{ background: m.hex }} />
                      {m.label}
                    </span>
                    <span className="ml-auto font-mono text-2xs text-slate-400">{l.score.toFixed(2)}</span>
                  </div>
                  <div className="mt-0.5 truncate text-2xs text-slate-500">{other?.filename ?? otherId}</div>
                </div>
                {other && <ToneBadge meta={evidenceMeta(other)} size="sm" />}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-400">{l.detail}</p>
              {l.artifacts.length > 0 && (
                <div className="mt-2 flex gap-2">
                  {l.artifacts.map((a) => (
                    <button
                      key={a}
                      type="button"
                      onClick={() => onArtifact(urls.artifact(l.source, a), `${m.label}: comparison`, l.detail)}
                      className="overflow-hidden rounded-md border border-white/10 transition hover:border-accent/50"
                    >
                      <SafeImg src={urls.artifact(l.source, a)} alt="comparison" className="h-14 w-auto" fallback={<span className="block p-2 text-2xs text-slate-500">figure missing</span>} />
                    </button>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
