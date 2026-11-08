/**
 * Renders a technique's `data` (chart series, tables) in a readable form. Every renderer is
 * defensive: fields may be missing or have unexpected shapes, and an unknown technique falls
 * back to a generic key / value table plus the raw JSON.
 */

import { ChevronRight, Clock } from "lucide-react";
import { useState, type ReactNode } from "react";
import type { TechniqueResult } from "../../api";
import { ChartFrame, GridProfileChart, LegendSwatch, SpectrumChart, TONE_HI, TONE_LO } from "../../components/charts";
import { cx } from "../../components/ui";
import { displayValue, formatNumber, formatPercent, humanize, sigmoid } from "../../lib/format";
import { arr, num, numArray, obj, str } from "../../lib/media";
import { EnfChart, SpliceChart, VoiceChart } from "./AudioParts";

// ------------------------------------------------------------------ building blocks

export function DataTable({ rows, mono = false }: { rows: [string, ReactNode][]; mono?: boolean }) {
  if (!rows.length) return null;
  return (
    <div className="overflow-hidden rounded-lg border border-white/[0.06]">
      <table className="w-full text-xs">
        <tbody>
          {rows.map(([k, v], i) => (
            <tr key={`${k}-${i}`} className="border-b border-white/[0.04] last:border-0 odd:bg-white/[0.015]">
              <td className="w-[38%] max-w-[220px] truncate px-3 py-1.5 align-top text-slate-500" title={k}>
                {k}
              </td>
              <td className={cx("break-all px-3 py-1.5 text-slate-200", mono && "font-mono text-[11px]")}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function scalarRows(data: Record<string, unknown>, skip: string[] = []): [string, ReactNode][] {
  return Object.entries(data)
    .filter(([k, v]) => !skip.includes(k) && (v === null || ["string", "number", "boolean"].includes(typeof v)))
    .map(([k, v]) => [humanize(k), displayValue(v)]);
}

export function Facts({ items }: { items: [string, ReactNode][] }) {
  const shown = items.filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!shown.length) return null;
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
      {shown.map(([k, v]) => (
        <div key={k} className="min-w-0 rounded-lg border border-white/[0.06] bg-ink-950/40 px-3 py-2">
          <div className="truncate text-2xs uppercase tracking-wider text-slate-500" title={k}>
            {k}
          </div>
          <div className="mt-0.5 truncate font-mono text-sm text-slate-100" title={typeof v === "string" ? v : undefined}>
            {v}
          </div>
        </div>
      ))}
    </div>
  );
}

/** A score on a scale with the weak / moderate / strong thresholds the technique used. */
export function ThresholdBar({ score, thresholds, unit = "" }: { score: number | null; thresholds: Record<string, unknown> | null; unit?: string }) {
  const th = (["weak", "moderate", "strong"] as const)
    .map((k) => ({ k, v: num(thresholds?.[k]) }))
    .filter((x): x is { k: "weak" | "moderate" | "strong"; v: number } => x.v !== null && x.v < 1e5);
  if (score === null) return null;
  const max = Math.max(score, ...th.map((t) => t.v), 1) * 1.15;
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  const level = th.filter((t) => score >= t.v).pop()?.k ?? "below";
  const color = level === "strong" ? TONE_HI : level === "moderate" ? "#ff7a45" : level === "weak" ? TONE_LO : "#22d3ee";
  return (
    <div className="rounded-lg border border-white/[0.06] bg-ink-950/40 p-3">
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="text-slate-400">Score against calibrated thresholds</span>
        <span className="font-mono text-slate-100">
          {formatNumber(score, 2)}
          {unit} · <span style={{ color }}>{level === "below" ? "below every threshold" : `${level} level`}</span>
        </span>
      </div>
      <div className="relative h-2.5 rounded-full bg-white/[0.06]">
        <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: pct(score), background: color, boxShadow: `0 0 10px ${color}` }} />
        {th.map((t) => (
          <div key={t.k} className="absolute -top-1 bottom-[-4px] w-px bg-slate-300/70" style={{ left: pct(t.v) }}>
            <span className="absolute left-1/2 top-4 -translate-x-1/2 whitespace-nowrap font-mono text-[9px] text-slate-500">
              {t.k} {formatNumber(t.v, 1)}
            </span>
          </div>
        ))}
      </div>
      <div className="h-4" />
    </div>
  );
}

/**
 * A classifier score on its logit (log-odds) scale with the strict and lenient thresholds. The
 * logit scale keeps thresholds that sit at a few percent probability readable.
 */
export function LogitBar({
  logit,
  tauHi,
  tauLo,
  label,
  lowWord = "camera-like",
  highWord = "AI-like",
}: {
  logit: number;
  tauHi: number | null;
  tauLo: number | null;
  label: string;
  lowWord?: string;
  highWord?: string;
}) {
  const lo = Math.min(-12, logit - 1, (tauLo ?? 0) - 2);
  const hi = Math.max(12, logit + 1, (tauHi ?? 0) + 2);
  const pos = (x: number) => `${((x - lo) / (hi - lo)) * 100}%`;
  const color = tauHi !== null && logit >= tauHi ? TONE_HI : tauLo !== null && logit >= tauLo ? TONE_LO : "#22d3ee";
  const p = sigmoid(logit);
  return (
    <div className="rounded-lg border border-white/[0.06] bg-ink-950/40 p-3.5">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <div className="text-xs text-slate-400">{label}</div>
          <div className="font-mono text-2xs text-slate-500">logit {logit.toFixed(2)}</div>
        </div>
        <span className="font-mono text-2xl font-semibold" style={{ color }}>
          {formatPercent(p, p > 0.001 && p < 0.999 ? 1 : 0)}
        </span>
      </div>
      <div className="relative h-2.5 rounded-full bg-white/[0.06]">
        <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: pos(logit), background: `linear-gradient(90deg, ${color}33, ${color})` }} />
        <div
          className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink-950"
          style={{ left: pos(logit), background: color, boxShadow: `0 0 14px ${color}` }}
        />
        {tauLo !== null && (
          <div className="absolute -bottom-1.5 -top-1.5 w-px bg-amber-300/80" style={{ left: pos(tauLo) }}>
            <span className="absolute right-1 top-6 whitespace-nowrap font-mono text-[10px] text-amber-200/80">lenient {formatPercent(sigmoid(tauLo), 1)} ┘</span>
          </div>
        )}
        {tauHi !== null && (
          <div className="absolute -bottom-1.5 -top-1.5 w-px bg-rose-300/80" style={{ left: pos(tauHi) }}>
            <span className="absolute left-1 top-6 whitespace-nowrap font-mono text-[10px] text-rose-200/80">└ strict {formatPercent(sigmoid(tauHi), 1)}</span>
          </div>
        )}
      </div>
      <div className="mt-7 flex justify-between text-[10px] uppercase tracking-wider text-slate-600">
        <span>← {lowWord}</span>
        <span>{highWord} →</span>
      </div>
    </div>
  );
}

function QuantTable({ values, title }: { values: number[]; title: string }) {
  if (values.length !== 64) return null;
  const max = Math.max(...values, 1);
  return (
    <div>
      <div className="mb-1.5 text-2xs uppercase tracking-wider text-slate-500">{title}</div>
      <div className="grid w-max grid-cols-8 gap-[2px] rounded-md border border-white/[0.06] p-1">
        {values.map((v, i) => (
          <div
            key={i}
            className="flex h-6 w-7 items-center justify-center rounded-[3px] font-mono text-[9px]"
            style={{ background: `rgba(34,211,238,${0.08 + 0.75 * (v / max)})`, color: v / max > 0.55 ? "#03060c" : "#cbd5e1" }}
            title={`coefficient ${i}: ${v}`}
          >
            {v}
          </div>
        ))}
      </div>
    </div>
  );
}

function RawJson({ data }: { data: unknown }) {
  const [open, setOpen] = useState(false);
  const text = JSON.stringify(data, null, 2) ?? "";
  if (!text || text === "{}") return null;
  return (
    <div>
      <button type="button" onClick={() => setOpen((o) => !o)} className="inline-flex items-center gap-1 text-2xs text-slate-500 hover:text-slate-300">
        <ChevronRight className={cx("h-3 w-3 transition", open && "rotate-90")} /> Raw data (JSON, as stored)
      </button>
      {open && (
        <pre className="mt-1.5 max-h-72 overflow-auto rounded-lg bg-ink-950/80 p-3 font-mono text-[10.5px] leading-relaxed text-slate-400">
          {text.length > 60000 ? `${text.slice(0, 60000)}\n…` : text}
        </pre>
      )}
    </div>
  );
}

function SeeTimeline() {
  return (
    <div className="inline-flex items-center gap-1.5 rounded-md bg-accent/[0.07] px-2 py-1 text-2xs text-accent-soft">
      <Clock className="h-3 w-3" /> Plotted on the playback timeline above (click to seek)
    </div>
  );
}

// ------------------------------------------------------------------ per-technique views

function MetadataView({ d }: { d: Record<string, unknown> }) {
  const exif = obj(d.exif) ?? {};
  const xmp = obj(d.xmp) ?? {};
  const iptc = obj(d.iptc) ?? {};
  const gps = obj(d.gps);
  const history = arr(d.xmp_history).map((h) => obj(h)).filter((h): h is Record<string, unknown> => h !== null);
  const camera = arr(d.camera_tags).map(String);
  const png = arr(d.png_text_keys).map(String);
  const empty = !Object.keys(exif).length && !Object.keys(xmp).length && !Object.keys(iptc).length && !history.length && !gps;
  if (empty) {
    return (
      <div className="rounded-lg border border-dashed border-white/10 px-3 py-3 text-xs text-slate-500">
        No EXIF, XMP or IPTC metadata embedded. Messaging apps, social networks and screenshots strip it; its absence is not by itself
        evidence of manipulation.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {camera.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {camera.map((c) => (
            <span key={c} className="chip-muted normal-case tracking-normal">
              {c}
            </span>
          ))}
        </div>
      )}
      {gps && (
        <DataTable
          rows={Object.entries(gps).map(([k, v]) => [k.toUpperCase(), displayValue(v)] as [string, ReactNode])}
          mono
        />
      )}
      {Object.keys(exif).length > 0 && (
        <div>
          <div className="mb-1.5 text-2xs uppercase tracking-wider text-slate-500">EXIF · {Object.keys(exif).length} fields</div>
          <div className="max-h-72 overflow-y-auto">
            <DataTable rows={Object.entries(exif).map(([k, v]) => [k, displayValue(v, 200)])} mono />
          </div>
        </div>
      )}
      {history.length > 0 && (
        <div>
          <div className="mb-1.5 text-2xs uppercase tracking-wider text-slate-500">XMP edit history</div>
          <ol className="relative ml-2 space-y-2 border-l border-amber-400/30 pl-4">
            {history.map((h, i) => (
              <li key={i} className="relative text-xs">
                <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border border-amber-300/70 bg-ink-900" />
                <span className="font-semibold text-slate-200">{str(h.action) ?? str(h["stEvt:action"]) ?? "event"}</span>{" "}
                <span className="text-slate-400">
                  {Object.entries(h)
                    .filter(([k]) => !/action$/i.test(k))
                    .map(([k, v]) => `${k.replace(/^stEvt:/, "")}: ${displayValue(v, 80)}`)
                    .join(" · ")}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {Object.keys(xmp).length > 0 && (
        <div>
          <div className="mb-1.5 text-2xs uppercase tracking-wider text-slate-500">XMP · {Object.keys(xmp).length} fields</div>
          <div className="max-h-60 overflow-y-auto">
            <DataTable rows={Object.entries(xmp).map(([k, v]) => [k, displayValue(v, 200)])} mono />
          </div>
        </div>
      )}
      {Object.keys(iptc).length > 0 && <DataTable rows={Object.entries(iptc).map(([k, v]) => [k, displayValue(v, 200)])} mono />}
      {png.length > 0 && <div className="text-2xs text-slate-500">PNG text chunks: {png.join(", ")}</div>}
    </div>
  );
}

function StructureView({ d }: { d: Record<string, unknown> }) {
  const q0 = numArray(d.qtable0);
  const q1 = numArray(d.qtable1);
  const errors = arr(d.errors).map(String);
  return (
    <div className="space-y-3">
      <Facts
        items={[
          ["Format", str(d.format)?.toUpperCase() ?? null],
          ["Frame", str(d.frame)],
          ["Subsampling", str(d.subsampling)],
          ["Quality ≈", num(d.estimated_quality) !== null ? String(num(d.estimated_quality)) : null],
          ["Standard tables", d.standard_tables === undefined ? null : d.standard_tables ? "yes (IJG)" : "no (custom)"],
          ["Huffman", str(d.huffman)],
          ["Progressive", d.progressive === undefined ? null : d.progressive ? "yes" : "no"],
          ["Trailing bytes", num(d.trailing_bytes) !== null ? String(num(d.trailing_bytes)) : null],
        ]}
      />
      {(q0.length === 64 || q1.length === 64) && (
        <div className="flex flex-wrap gap-6">
          <QuantTable values={q0} title="Luma quantisation table" />
          <QuantTable values={q1} title="Chroma quantisation table" />
        </div>
      )}
      {arr(d.app_segments).length > 0 && (
        <div className="text-2xs text-slate-500">
          Segments: <span className="font-mono text-slate-400">{arr(d.app_segments).map(String).join(" · ")}</span>
        </div>
      )}
      {errors.length > 0 && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">{errors.join("; ")}</div>}
    </div>
  );
}

function metricLabel(k: string): string {
  return humanize(k)
    .replace(/\bauc\b/gi, "AUC")
    .replace(/\btpr\b/gi, "TPR")
    .replace(/\bfpr\b/gi, "FPR")
    .replace(/\btau hi\b/gi, "strict threshold")
    .replace(/\btau lo\b/gi, "lenient threshold");
}

function AigenView({ d }: { d: Record<string, unknown> }) {
  const logit = num(d.logit);
  const p = num(d.probability);
  const hi = num(d.tau_hi);
  const lo = num(d.tau_lo);
  const metrics = obj(d.metrics) ?? {};
  const views = numArray(d.views);
  const dataset = str(metrics.dataset);
  return (
    <div className="space-y-3">
      {logit !== null ? (
        <LogitBar logit={logit} tauHi={hi} tauLo={lo} label="Classifier output: P(AI-generated)" />
      ) : p !== null ? (
        <Facts items={[["P(AI-generated)", formatPercent(p, 1)]]} />
      ) : null}
      <Facts
        items={[
          ["Model", str(d.model)],
          ["Licence", str(d.model_license)],
          ["Views scored", views.length ? String(views.length) : null],
        ]}
      />
      {Object.keys(metrics).length > 0 && (
        <div>
          <div className="mb-1.5 text-2xs uppercase tracking-wider text-slate-500">
            Published validation{dataset ? ` · ${dataset}` : ""}
          </div>
          <Facts
            items={Object.entries(metrics)
              .filter(([k]) => k !== "dataset")
              .map(([k, v]) => [metricLabel(k), typeof v === "number" && v <= 1 ? formatPercent(v, 1) : displayValue(v)] as [string, ReactNode])}
          />
        </div>
      )}
    </div>
  );
}

function FacesView({ d }: { d: Record<string, unknown> }) {
  const faces = arr(d.faces).map((f) => obj(f)).filter((f): f is Record<string, unknown> => f !== null);
  const hi = num(d.tau_hi);
  const lo = num(d.tau_lo);
  return (
    <div className="space-y-3">
      {faces.length > 0 ? (
        <div className="overflow-hidden rounded-lg border border-white/[0.06]">
          <table className="w-full text-xs">
            <thead className="bg-white/[0.03] text-2xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-3 py-1.5 text-left font-medium">Face</th>
                <th className="px-3 py-1.5 text-right font-medium">Size (px)</th>
                <th className="px-3 py-1.5 text-right font-medium">Logit</th>
                <th className="px-3 py-1.5 text-left font-medium">Level</th>
              </tr>
            </thead>
            <tbody>
              {faces.map((f, i) => {
                const logit = num(f.logit);
                const color = logit !== null && hi !== null && logit >= hi ? TONE_HI : logit !== null && lo !== null && logit >= lo ? TONE_LO : "#94a3b8";
                return (
                  <tr key={i} className="border-t border-white/[0.04]">
                    <td className="px-3 py-1.5 text-slate-300">{str(obj(f.box)?.label) ?? `face ${i + 1}`}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-slate-300">{formatNumber(num(f.face_px), 0)}</td>
                    <td className="px-3 py-1.5 text-right font-mono" style={{ color }}>
                      {logit !== null ? logit.toFixed(2) : "—"}
                    </td>
                    <td className="px-3 py-1.5 text-slate-400">{str(f.level) ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-xs text-slate-500">No face large enough to score.</div>
      )}
      <Facts
        items={[
          ["Strict threshold (logit)", hi !== null ? hi.toFixed(2) : null],
          ["Lenient threshold (logit)", lo !== null ? lo.toFixed(2) : null],
          ["Model", str(d.model)],
          ["Calibrated on", str(d.calibrated_on)],
        ]}
      />
    </div>
  );
}

function WatermarkView({ d }: { d: Record<string, unknown> }) {
  const rows = Object.entries(d)
    .map(([k, v]) => ({ k, v: obj(v) }))
    .filter((x): x is { k: string; v: Record<string, unknown> } => x.v !== null);
  if (!rows.length) return null;
  return (
    <div className="overflow-hidden rounded-lg border border-white/[0.06]">
      <table className="w-full text-xs">
        <thead className="bg-white/[0.03] text-2xs uppercase tracking-wider text-slate-500">
          <tr>
            <th className="px-3 py-1.5 text-left font-medium">Watermark scheme</th>
            <th className="px-3 py-1.5 text-left font-medium">Bit agreement</th>
            <th className="px-3 py-1.5 text-right font-medium">P(chance)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ k, v }) => {
            const acc = num(v.accuracy) ?? 0;
            return (
              <tr key={k} className="border-t border-white/[0.04]">
                <td className="px-3 py-1.5 text-slate-300">{k}</td>
                <td className="px-3 py-1.5">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-28 rounded-full bg-white/[0.06]">
                      <div className="h-full rounded-full" style={{ width: `${acc * 100}%`, background: acc > 0.85 ? TONE_HI : "#64748b" }} />
                    </div>
                    <span className="font-mono text-slate-400">
                      {num(v.matching) ?? "?"}/{num(v.bits) ?? "?"} ({formatPercent(acc, 0)})
                    </span>
                  </div>
                </td>
                <td className="px-3 py-1.5 text-right font-mono text-slate-400">{num(v.p_chance)?.toExponential(1) ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ContainerView({ d }: { d: Record<string, unknown> }) {
  const tags = obj(d.tags) ?? {};
  return (
    <div className="space-y-3">
      <DataTable rows={scalarRows(d, ["tags"])} />
      {Object.keys(tags).length > 0 && (
        <div>
          <div className="mb-1.5 text-2xs uppercase tracking-wider text-slate-500">Container tags</div>
          <DataTable rows={Object.entries(tags).map(([k, v]) => [k, displayValue(v)])} mono />
        </div>
      )}
    </div>
  );
}

function C2paView({ d }: { d: Record<string, unknown> }) {
  if (!Object.keys(d).length) return null;
  const actions = arr(d.actions).map((a) => obj(a)).filter((a): a is Record<string, unknown> => a !== null);
  const codes = arr(d.validation_codes).map(String);
  const ingredients = arr(d.ingredients).map(String);
  return (
    <div className="space-y-3">
      <Facts
        items={[
          ["Claim generator", str(d.claim_generator)],
          ["Signed by", str(d.issuer)],
          ["Signed at", str(d.signed_at)],
          ["Manifests", num(d.manifests) !== null ? String(num(d.manifests)) : null],
        ]}
      />
      {actions.length > 0 && (
        <DataTable rows={actions.map((a, i) => [`action ${i + 1}`, `${str(a.action) ?? "?"}${a.digitalSourceType ? ` · ${String(a.digitalSourceType).split("/").pop()}` : ""}`])} mono />
      )}
      {codes.length > 0 && <div className="text-2xs text-slate-400">Validation: <span className="font-mono">{codes.join(", ")}</span></div>}
      {ingredients.length > 0 && <div className="text-2xs text-slate-400">Ingredients: {ingredients.join(", ")}</div>}
    </div>
  );
}

function CopyMoveView({ d }: { d: Record<string, unknown> }) {
  const clusters = arr(d.clusters).map((c) => obj(c)).filter((c): c is Record<string, unknown> => c !== null);
  return (
    <div className="space-y-3">
      <ThresholdBar score={num(d.score)} thresholds={obj(d.thresholds)} unit=" pairs" />
      {clusters.length > 0 && (
        <DataTable
          rows={clusters.map((c, i) => [
            `clone ${i + 1}`,
            `${num(c.pairs) ?? "?"} keypoint pairs · shifted ${formatNumber(num(c.shift_px), 1)} px · scale ${formatNumber(num(c.scale), 3)} · rotation ${formatNumber(num(c.rotation_deg), 1)}°`,
          ])}
        />
      )}
    </div>
  );
}

function JpegGridView({ d }: { d: Record<string, unknown> }) {
  const h = numArray(d.profile_h);
  const v = numArray(d.profile_v);
  const phase = numArray(d.phase);
  return (
    <div className="space-y-3">
      {(h.length > 0 || v.length > 0) && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <ChartFrame title="Horizontal blockiness by column offset (mod 8)" height={130} legend={<LegendSwatch color="#22d3ee" label="detected grid phase" area />}>
            <GridProfileChart values={h} phase={Number.isFinite(phase[0]) ? (phase[0] as number) : null} label="column" />
          </ChartFrame>
          <ChartFrame title="Vertical blockiness by row offset (mod 8)" height={130} legend={<LegendSwatch color="#22d3ee" label="detected grid phase" area />}>
            <GridProfileChart values={v} phase={Number.isFinite(phase[1]) ? (phase[1] as number) : null} label="row" />
          </ChartFrame>
        </div>
      )}
      <Facts
        items={[
          ["Grid phase (x, y)", phase.length === 2 ? `${phase[0]}, ${phase[1]}` : null],
          ["Grid strength", arr(d.grid_strength).length ? arr(d.grid_strength).map((x) => formatNumber(x, 3)).join(", ") : null],
          ["Shifted-grid score", num(d.shift_score) !== null ? formatNumber(num(d.shift_score), 3) : null],
          ["Second-grid score", num(d.second_score) !== null ? formatNumber(num(d.second_score), 3) : null],
        ]}
      />
    </div>
  );
}

function SpectralView({ t }: { t: TechniqueResult }) {
  const d = t.data;
  return (
    <div className="space-y-3">
      <ChartFrame
        title="Long-term average spectrum"
        legend={
          <>
            <LegendSwatch color="#a78bfa" label="level (dB)" />
            <LegendSwatch color={TONE_LO} label="effective bandwidth cut-off" dashed />
          </>
        }
        caption="A sharp wall well below the file's Nyquist frequency reveals an earlier low-bandwidth stage (phone call, MP3/AAC, voice-note codec)."
        height={160}
      >
        <SpectrumChart hz={numArray(d.ltas_hz)} db={numArray(d.ltas_db)} cutoffHz={num(d.cutoff_hz)} maxHz={num(d.max_hz)} />
      </ChartFrame>
      <Facts
        items={[
          ["Sample rate", num(d.sample_rate) !== null ? `${num(d.sample_rate)} Hz` : null],
          ["Cut-off", num(d.cutoff_hz) !== null ? `${((num(d.cutoff_hz) ?? 0) / 1000).toFixed(1)} kHz` : null],
          ["Sharp cut-off", d.sharp_cutoff === undefined ? null : d.sharp_cutoff ? "yes" : "no"],
          ["Drop", num(d.drop_db) !== null ? `${num(d.drop_db)} dB` : null],
        ]}
      />
    </div>
  );
}

function VideoDeepfakeView({ d }: { d: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <SeeTimeline />
      <Facts
        items={[
          ["Label", str(d.label)],
          ["Usable windows", num(d.usable_windows) !== null ? String(num(d.usable_windows)) : null],
          ["Analysed", num(d.analysed_s) !== null ? `${formatNumber(num(d.analysed_s), 1)} s` : null],
          ["Strict threshold", num(d.tau_hi) !== null ? formatNumber(num(d.tau_hi), 3) : null],
          ["Lenient threshold", num(d.tau_lo) !== null ? formatNumber(num(d.tau_lo), 3) : null],
        ]}
      />
      {str(d.benchmark) && <div className="text-2xs text-slate-500">Benchmark: {str(d.benchmark)}</div>}
    </div>
  );
}

function FramesView({ d }: { d: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <SeeTimeline />
      <Facts
        items={[
          ["Frames", num(d.frames) !== null ? String(num(d.frames)) : null],
          ["Median interval", num(d.median_interval_ms) !== null ? `${formatNumber(num(d.median_interval_ms), 1)} ms` : null],
          ["Hard cuts", String(arr(d.cuts_s).length)],
          ["Duplicated frames", String(arr(d.duplicates_s).length)],
          ["Timestamp gaps", String(arr(d.gaps).length)],
        ]}
      />
    </div>
  );
}

function TranscriptView({ d }: { d: Record<string, unknown> }) {
  const asks = arr(d.asks).map((a) => obj(a)).filter((a): a is Record<string, unknown> => a !== null);
  return (
    <div className="space-y-3">
      <SeeTimeline />
      <Facts
        items={[
          ["Language", str(d.language)],
          ["Language p", num(d.language_probability) !== null ? formatNumber(num(d.language_probability), 2) : null],
          ["Engine", str(d.engine)],
          ["Fraud asks", String(asks.length)],
          ["Scam-script rules", String(arr(d.rules).length)],
        ]}
      />
    </div>
  );
}

// ------------------------------------------------------------------ dispatcher

export function TechniqueData({ t, timeline }: { t: TechniqueResult; timeline: boolean }) {
  const d = t.data ?? {};
  let body: ReactNode = null;
  switch (t.id) {
    case "image.metadata":
      body = <MetadataView d={d} />;
      break;
    case "image.structure":
      body = <StructureView d={d} />;
      break;
    case "image.aigen":
      body = <AigenView d={d} />;
      break;
    case "image.faces":
      body = Object.keys(d).length ? <FacesView d={d} /> : null;
      break;
    case "image.watermark":
      body = <WatermarkView d={d} />;
      break;
    case "image.ela":
    case "image.noise":
      body = (
        <div className="space-y-3">
          <ThresholdBar score={num(d.score)} thresholds={obj(d.thresholds)} />
          <Facts items={scalarRows(d, ["score", "thresholds"]).map(([k, v]) => [k, v])} />
        </div>
      );
      break;
    case "image.copymove":
      body = <CopyMoveView d={d} />;
      break;
    case "image.jpeg_grid":
      body = <JpegGridView d={d} />;
      break;
    case "provenance.c2pa":
      body = <C2paView d={d} />;
      break;
    case "audio.container":
    case "video.container":
      body = <ContainerView d={d} />;
      break;
    case "audio.spectral":
      body = t.status === "ok" ? <SpectralView t={t} /> : null;
      break;
    case "audio.voice":
      body = timeline && t.status === "ok" ? (
        <div className="space-y-3">
          <SeeTimeline />
          <DataTable rows={scalarRows(d, ["scores", "window_starts", "speech_segments"])} />
        </div>
      ) : t.status === "ok" ? (
        <VoiceChart t={t} duration={0} />
      ) : (
        <DataTable rows={scalarRows(d)} />
      );
      break;
    case "audio.enf":
      body = (
        <div className="space-y-3">
          {timeline ? null : <EnfChart t={t} compact />}
          <Facts
            items={[
              ["Mains hum", d.present === undefined ? null : d.present ? "present" : "not found"],
              ["SNR", num(d.snr_db) !== null ? `${num(d.snr_db)} dB` : null],
              ["Harmonic", num(d.harmonic_hz) !== null ? `${num(d.harmonic_hz)} Hz` : null],
              ["Discontinuities", String(arr(d.jumps).length)],
            ]}
          />
        </div>
      );
      break;
    case "audio.splice":
      body = timeline ? (
        <div className="space-y-3">
          <SeeTimeline />
          <Facts items={[["Edit cues", String(arr(d.cues).length)], ["Duration", num(d.duration_s) !== null ? `${num(d.duration_s)} s` : null]]} />
        </div>
      ) : (
        <SpliceChart t={t} />
      );
      break;
    case "audio.transcript":
      body = <TranscriptView d={d} />;
      break;
    case "video.frames":
      body = <FramesView d={d} />;
      break;
    case "video.deepfake":
      body = <VideoDeepfakeView d={d} />;
      break;
    default: {
      const rows = scalarRows(d);
      body = rows.length ? <DataTable rows={rows} /> : null;
    }
  }
  return (
    <div className="space-y-3">
      {body}
      <RawJson data={d} />
    </div>
  );
}
