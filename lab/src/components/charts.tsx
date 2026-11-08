/**
 * Time-series charts for the evidence viewers (recharts). One y-axis per chart, recessive
 * grid, thresholds as labelled reference lines, a playback cursor and click-to-seek.
 */

import type { ReactNode } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from "recharts";
import { formatClock } from "../lib/format";
import { cx } from "./ui";

export const AXIS = { stroke: "rgba(148,163,184,0.25)", tick: { fill: "#64748b", fontSize: 10 } } as const;

/** Round-number time ticks (seconds) for a 0..max axis, at most ~8 of them. */
export function timeTicks(max: number): number[] {
  if (!Number.isFinite(max) || max <= 0) return [0];
  const steps = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600];
  const step = steps.find((s) => max / s <= 8) ?? 3600;
  const out: number[] = [];
  for (let t = 0; t <= max + 1e-9; t += step) out.push(Number(t.toFixed(3)));
  return out;
}
export const GRID = "rgba(148,163,184,0.08)";
export const CURSOR = "#e2e8f0";
export const SERIES = "#22d3ee";
export const TONE_HI = "#ff4d6d";
export const TONE_LO = "#fbbf24";

/** A chart figure: title, optional legend and caption, fixed height. */
export function ChartFrame({
  title,
  right,
  legend,
  caption,
  height = 180,
  children,
  className,
}: {
  title: ReactNode;
  right?: ReactNode;
  legend?: ReactNode;
  caption?: ReactNode;
  height?: number;
  children: ReactNode;
  className?: string;
}) {
  return (
    <figure className={cx("rounded-xl border border-white/[0.06] bg-ink-950/40 p-3", className)}>
      <figcaption className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-200">{title}</span>
        {right}
      </figcaption>
      {legend && <div className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-2xs text-slate-400">{legend}</div>}
      <div style={{ height }}>{children}</div>
      {caption && <div className="mt-2 text-2xs leading-relaxed text-slate-500">{caption}</div>}
    </figure>
  );
}

export function LegendSwatch({ color, label, dashed, area }: { color: string; label: string; dashed?: boolean; area?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {area ? (
        <span className="h-2.5 w-3.5 rounded-sm" style={{ background: `${color}40`, border: `1px solid ${color}88` }} />
      ) : (
        <svg width="16" height="6" aria-hidden="true">
          <line x1="1" y1="3" x2="15" y2="3" stroke={color} strokeWidth="2" strokeDasharray={dashed ? "3 2" : undefined} strokeLinecap="round" />
        </svg>
      )}
      {label}
    </span>
  );
}

interface TipRow {
  label: string;
  value: string;
  color?: string;
}

function TipBox({ title, rows }: { title: string; rows: TipRow[] }) {
  return (
    <div className="rounded-lg border border-white/10 bg-ink-950/95 px-3 py-2 shadow-xl backdrop-blur">
      <div className="mb-1 font-mono text-2xs text-slate-400">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2 text-xs text-slate-200">
          {r.color && <span className="h-2 w-2 rounded-full" style={{ background: r.color }} />}
          <span className="text-slate-400">{r.label}</span>
          <span className="ml-auto font-mono">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

type Payload<T> = { payload?: T }[] | undefined;

function first<T>(p: Payload<T>): T | undefined {
  return p && p.length ? p[0]?.payload : undefined;
}

function seekHandler(onSeek?: (t: number) => void) {
  return (state: unknown) => {
    if (!onSeek || !state || typeof state !== "object") return;
    const s = state as { activeLabel?: unknown; activePayload?: { payload?: { seek?: number; t?: number } }[] };
    const p = s.activePayload?.[0]?.payload;
    const t = typeof p?.seek === "number" ? p.seek : typeof p?.t === "number" ? p.t : Number(s.activeLabel);
    if (Number.isFinite(t)) onSeek(Math.max(0, t));
  };
}

// ------------------------------------------------------------------ window scores (voice / deepfake)

export interface ScoreWindow {
  start: number;
  end: number;
  score: number | null;
  cues?: string[];
}

interface WindowPoint {
  t: number;
  seek: number;
  score: number | null;
  start: number;
  end: number;
  cues: string;
  tone: string;
}

/**
 * Per-window model scores over time with the strict (τ hi) and lenient (τ lo) thresholds.
 * Windows above a threshold are shaded across their full time span.
 */
export function WindowScoreChart({
  windows,
  tauHi,
  tauLo,
  duration,
  cursor,
  onSeek,
  yLabel = "score",
  height = 190,
}: {
  windows: ScoreWindow[];
  tauHi: number | null;
  tauLo: number | null;
  duration: number;
  cursor?: number | null;
  onSeek?: (t: number) => void;
  yLabel?: string;
  height?: number;
}) {
  const pts: WindowPoint[] = windows.map((w) => {
    const s = w.score;
    const tone = s === null ? "#475569" : tauHi !== null && s >= tauHi ? TONE_HI : tauLo !== null && s >= tauLo ? TONE_LO : SERIES;
    return { t: (w.start + w.end) / 2, seek: w.start, score: s, start: w.start, end: w.end, cues: (w.cues ?? []).join(", "), tone };
  });
  const maxScore = Math.max(1, ...pts.map((p) => p.score ?? 0));
  const xMax = Math.max(duration, ...windows.map((w) => w.end), 1);
  return (
    <div style={{ height }} className={onSeek ? "cursor-pointer" : undefined}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={pts} margin={{ top: 8, right: 16, bottom: 0, left: 0 }} onClick={seekHandler(onSeek)}>
          <CartesianGrid stroke={GRID} vertical={false} />
          {windows.map((w, i) =>
            w.score !== null && tauLo !== null && w.score >= tauLo ? (
              <ReferenceArea
                key={i}
                x1={w.start}
                x2={w.end}
                fill={tauHi !== null && w.score >= tauHi ? TONE_HI : TONE_LO}
                fillOpacity={0.1}
                strokeOpacity={0}
              />
            ) : null,
          )}
          <XAxis
            type="number"
            dataKey="t"
            domain={[0, xMax]}
            ticks={timeTicks(xMax)}
            tickFormatter={(v: number) => formatClock(v)}
            {...AXIS}
            tickLine={false}
          />
          <YAxis
            domain={[0, maxScore > 1 ? "auto" : 1]}
            ticks={maxScore > 1 ? undefined : [0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v: number) => v.toFixed(2)}
            {...AXIS}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          {tauLo !== null && <ReferenceLine y={tauLo} stroke={TONE_LO} strokeDasharray="4 3" strokeOpacity={0.85} />}
          {tauHi !== null && <ReferenceLine y={tauHi} stroke={TONE_HI} strokeDasharray="4 3" strokeOpacity={0.9} />}
          <Line type="monotone" dataKey="score" stroke={SERIES} strokeWidth={2} dot={false} activeDot={false} isAnimationActive={false} connectNulls />
          <Scatter
            dataKey="score"
            isAnimationActive={false}
            shape={(props: unknown) => {
              const p = props as { cx?: number; cy?: number; payload?: WindowPoint };
              if (p.cx === undefined || p.cy === undefined || !p.payload || p.payload.score === null) return <g />;
              return <circle cx={p.cx} cy={p.cy} r={4.5} fill={p.payload.tone} stroke="#060b16" strokeWidth={2} />;
            }}
          />
          {cursor !== null && cursor !== undefined && <ReferenceLine x={cursor} stroke={CURSOR} strokeWidth={1.5} />}
          <Tooltip
            cursor={{ stroke: "rgba(226,232,240,0.25)" }}
            content={({ active, payload }: TooltipProps<number, string>) => {
              const p = active ? first<WindowPoint>(payload as Payload<WindowPoint>) : undefined;
              if (!p) return null;
              const rows: TipRow[] = [{ label: yLabel, value: p.score === null ? "no face" : p.score.toFixed(3), color: p.tone }];
              if (p.cues) rows.push({ label: "cues", value: p.cues });
              return <TipBox title={`window ${formatClock(p.start)}–${formatClock(p.end)}`} rows={rows} />;
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ------------------------------------------------------------------ generic line over time with markers

export interface Marker {
  t: number;
  color: string;
  label: string;
}

export function TimeLineChart({
  t,
  y,
  color = SERIES,
  area = true,
  markers = [],
  reference,
  cursor,
  onSeek,
  yFormat = (v: number) => v.toFixed(1),
  yLabel,
  yDomain,
  height = 170,
  step = false,
}: {
  t: number[];
  y: number[];
  color?: string;
  area?: boolean;
  markers?: Marker[];
  reference?: { y: number; label: string };
  cursor?: number | null;
  onSeek?: (t: number) => void;
  yFormat?: (v: number) => string;
  yLabel: string;
  yDomain?: [number | "auto" | "dataMin" | "dataMax", number | "auto" | "dataMin" | "dataMax"];
  height?: number;
  step?: boolean;
}) {
  const n = Math.min(t.length, y.length);
  const data = Array.from({ length: n }, (_, i) => ({ t: t[i] ?? 0, y: Number.isFinite(y[i]) ? (y[i] as number) : null }));
  const xMax = Math.max(1, ...data.map((d) => d.t), ...markers.map((m) => m.t));
  const gid = `g${Math.abs(color.split("").reduce((a, c) => a * 31 + c.charCodeAt(0), 7)) % 100000}`;
  return (
    <div style={{ height }} className={onSeek ? "cursor-pointer" : undefined}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }} onClick={seekHandler(onSeek)}>
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis type="number" dataKey="t" domain={[0, xMax]} ticks={timeTicks(xMax)} tickFormatter={(v: number) => formatClock(v)} {...AXIS} tickLine={false} />
          <YAxis
            domain={yDomain ?? ["auto", "auto"]}
            tickFormatter={(v: number) => yFormat(v)}
            {...AXIS}
            tickLine={false}
            axisLine={false}
            width={48}
            tickCount={4}
          />
          {reference && (
            <ReferenceLine y={reference.y} stroke="#94a3b8" strokeDasharray="4 3" strokeOpacity={0.6} ifOverflow="extendDomain" />
          )}
          {area ? (
            <Area
              type={step ? "stepAfter" : "monotone"}
              dataKey="y"
              stroke={color}
              strokeWidth={1.75}
              fill={`url(#${gid})`}
              baseValue="dataMin"
              isAnimationActive={false}
              connectNulls
              dot={false}
            />
          ) : (
            <Line type={step ? "stepAfter" : "monotone"} dataKey="y" stroke={color} strokeWidth={2} isAnimationActive={false} connectNulls dot={data.length < 40 ? { r: 2.5, fill: color, strokeWidth: 0 } : false} />
          )}
          {markers.map((m, i) => (
            <ReferenceLine key={`${m.t}-${i}`} x={m.t} stroke={m.color} strokeWidth={1.5} strokeDasharray="3 2" />
          ))}
          {cursor !== null && cursor !== undefined && <ReferenceLine x={cursor} stroke={CURSOR} strokeWidth={1.5} />}
          <Tooltip
            cursor={{ stroke: "rgba(226,232,240,0.25)" }}
            content={({ active, payload }: TooltipProps<number, string>) => {
              const p = active ? first<{ t: number; y: number | null }>(payload as Payload<{ t: number; y: number | null }>) : undefined;
              if (!p) return null;
              const near = markers.filter((m) => Math.abs(m.t - p.t) < xMax / 80);
              return (
                <TipBox
                  title={formatClock(p.t) + ` (${p.t.toFixed(2)} s)`}
                  rows={[
                    { label: yLabel, value: p.y === null ? "—" : yFormat(p.y), color },
                    ...near.map((m) => ({ label: m.label, value: `${m.t.toFixed(2)} s`, color: m.color })),
                  ]}
                />
              );
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ------------------------------------------------------------------ spectrum (LTAS)

export function SpectrumChart({
  hz,
  db,
  cutoffHz,
  maxHz,
  height = 170,
}: {
  hz: number[];
  db: number[];
  cutoffHz: number | null;
  maxHz: number | null;
  height?: number;
}) {
  const n = Math.min(hz.length, db.length);
  const data = Array.from({ length: n }, (_, i) => ({ k: (hz[i] ?? 0) / 1000, db: Number.isFinite(db[i]) ? (db[i] as number) : null }));
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="ltas" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis type="number" dataKey="k" domain={[0, maxHz ? maxHz / 1000 : "dataMax"]} tickFormatter={(v: number) => `${v.toFixed(0)}k`} {...AXIS} tickLine={false} />
          <YAxis tickFormatter={(v: number) => `${v.toFixed(0)}`} {...AXIS} tickLine={false} axisLine={false} width={40} domain={["auto", "auto"]} tickCount={4} />
          <Area type="monotone" dataKey="db" stroke="#a78bfa" strokeWidth={1.5} fill="url(#ltas)" baseValue="dataMin" isAnimationActive={false} connectNulls dot={false} />
          {cutoffHz !== null && (
            <ReferenceLine x={cutoffHz / 1000} stroke={TONE_LO} strokeDasharray="4 3" />
          )}
          <Tooltip
            content={({ active, payload }: TooltipProps<number, string>) => {
              const p = active ? first<{ k: number; db: number | null }>(payload as Payload<{ k: number; db: number | null }>) : undefined;
              if (!p) return null;
              return <TipBox title={`${p.k.toFixed(2)} kHz`} rows={[{ label: "level", value: p.db === null ? "—" : `${p.db.toFixed(1)} dB`, color: "#a78bfa" }]} />;
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ------------------------------------------------------------------ JPEG grid profile

export function GridProfileChart({ values, phase, label, height = 120 }: { values: number[]; phase: number | null; label: string; height?: number }) {
  const data = values.map((v, i) => ({ i, v: Number.isFinite(v) ? v : 0 }));
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="i" {...AXIS} tickLine={false} />
          <YAxis {...AXIS} tickLine={false} axisLine={false} width={44} tickCount={4} tickFormatter={(v: number) => v.toFixed(2)} />
          <ReferenceLine y={0} stroke="rgba(148,163,184,0.3)" />
          <Bar dataKey="v" radius={[3, 3, 3, 3]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.i} fill={d.i === phase ? SERIES : "rgba(148,163,184,0.35)"} />
            ))}
          </Bar>
          <Tooltip
            cursor={{ fill: "rgba(148,163,184,0.06)" }}
            content={({ active, payload }: TooltipProps<number, string>) => {
              const p = active ? first<{ i: number; v: number }>(payload as Payload<{ i: number; v: number }>) : undefined;
              if (!p) return null;
              return <TipBox title={`${label} offset ${p.i} (mod 8)`} rows={[{ label: "blockiness", value: p.v.toFixed(4) }]} />;
            }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
