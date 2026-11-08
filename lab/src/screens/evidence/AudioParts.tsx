import { AlertOctagon, Languages, Pause, Play, RotateCcw, RotateCw } from "lucide-react";
import { useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { urls, type EvidenceAnalysis, type TechniqueResult, type TimeSpan } from "../../api";
import { ChartFrame, LegendSwatch, TimeLineChart, TONE_HI, TONE_LO, WindowScoreChart, type Marker } from "../../components/charts";
import { cx } from "../../components/ui";
import { formatClock } from "../../lib/format";
import { arr, findTechnique, num, numArray, obj, str } from "../../lib/media";
import { groupAsks, highlightAsks } from "../../lib/transcript";

// ------------------------------------------------------------------ transport

export function Transport({
  media,
  current,
  duration,
  playing,
}: {
  media: RefObject<HTMLMediaElement>;
  current: number;
  duration: number;
  playing: boolean;
}) {
  const toggle = () => {
    const m = media.current;
    if (!m) return;
    if (m.paused) void m.play().catch(() => undefined);
    else m.pause();
  };
  const skip = (d: number) => {
    const m = media.current;
    if (!m) return;
    m.currentTime = Math.max(0, Math.min(duration || m.duration || 0, m.currentTime + d));
  };
  const pct = duration > 0 ? Math.min(1, current / duration) : 0;
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={toggle}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-b from-cyan-300 to-cyan-500 text-ink-950 shadow-[0_0_24px_-4px_rgba(34,211,238,0.8)] transition hover:scale-105"
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? <Pause className="h-5 w-5" fill="currentColor" /> : <Play className="ml-0.5 h-5 w-5" fill="currentColor" />}
      </button>
      <button type="button" className="btn-ghost btn-sm" onClick={() => skip(-5)} aria-label="Back 5 seconds">
        <RotateCcw className="h-4 w-4" />
      </button>
      <button type="button" className="btn-ghost btn-sm" onClick={() => skip(5)} aria-label="Forward 5 seconds">
        <RotateCw className="h-4 w-4" />
      </button>
      <div
        className="relative h-1.5 flex-1 cursor-pointer rounded-full bg-white/10"
        onClick={(e) => {
          const m = media.current;
          if (!m || !duration) return;
          const r = e.currentTarget.getBoundingClientRect();
          m.currentTime = ((e.clientX - r.left) / r.width) * duration;
        }}
      >
        <div className="absolute inset-y-0 left-0 rounded-full bg-accent" style={{ width: `${pct * 100}%` }} />
        <div className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow" style={{ left: `${pct * 100}%` }} />
      </div>
      <div className="w-[92px] shrink-0 text-right font-mono text-xs text-slate-300">
        {formatClock(current)} <span className="text-slate-600">/ {formatClock(duration)}</span>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ spectrogram with cursor

export interface Band {
  start: number;
  end: number;
  color: string;
  label: string;
}

export function Spectrogram({
  evidenceId,
  name,
  duration,
  cursor,
  onSeek,
  bands = [],
  caption,
  maxHz,
}: {
  evidenceId: string;
  name: string;
  duration: number;
  cursor: number;
  onSeek: (t: number) => void;
  bands?: Band[];
  caption?: ReactNode;
  maxHz?: number | null;
}) {
  const box = useRef<HTMLDivElement>(null);
  const ticks = useMemo(() => {
    if (!duration) return [] as number[];
    const step = duration > 120 ? 30 : duration > 60 ? 10 : duration > 20 ? 5 : duration > 8 ? 2 : 1;
    return Array.from({ length: Math.floor(duration / step) + 1 }, (_, i) => i * step);
  }, [duration]);
  const pct = duration > 0 ? Math.min(1, Math.max(0, cursor / duration)) : 0;
  return (
    <div>
      <div className="flex">
        {maxHz ? (
          <div className="flex w-10 shrink-0 flex-col justify-between py-0.5 pr-1.5 text-right font-mono text-[10px] text-slate-500">
            <span>{(maxHz / 1000).toFixed(0)}k</span>
            <span>{(maxHz / 2000).toFixed(0)}k</span>
            <span>0</span>
          </div>
        ) : null}
        <div
          ref={box}
          className="relative min-w-0 flex-1 cursor-crosshair overflow-hidden rounded-lg border border-white/[0.08] bg-black"
          onClick={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            onSeek(((e.clientX - r.left) / r.width) * duration);
          }}
          title="Click to seek"
        >
          <img src={urls.artifact(evidenceId, name)} alt="Spectrogram" className="block h-[170px] w-full object-fill" draggable={false} />
          {bands.map((b, i) => (
            <div
              key={i}
              className="absolute inset-y-0"
              title={`${b.label}: ${formatClock(b.start)}–${formatClock(b.end)}`}
              style={{
                left: `${(b.start / duration) * 100}%`,
                width: `${Math.max(0.4, ((b.end - b.start) / duration) * 100)}%`,
                background: `${b.color}26`,
                borderLeft: `1px solid ${b.color}`,
                borderRight: `1px solid ${b.color}`,
              }}
            />
          ))}
          <div className="pointer-events-none absolute inset-y-0 w-px bg-white shadow-[0_0_10px_rgba(255,255,255,0.9)]" style={{ left: `${pct * 100}%` }} />
        </div>
      </div>
      <div className={cx("relative mt-1 h-4 font-mono text-[10px] text-slate-500", maxHz ? "ml-10" : "")}>
        {ticks.map((t) => (
          <span key={t} className="absolute -translate-x-1/2" style={{ left: `${(t / Math.max(duration, 1e-6)) * 100}%` }}>
            {formatClock(t)}
          </span>
        ))}
      </div>
      {caption && <div className="mt-1 text-2xs text-slate-500">{caption}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ voice

export function voiceWindows(t: TechniqueResult | undefined, duration: number) {
  if (!t || t.status !== "ok") return null;
  const scores = numArray(t.data.scores);
  if (!scores.length) return null;
  const w = num(t.data.window_s) ?? 5;
  const starts = numArray(t.data.window_starts);
  return {
    windows: scores.map((s, i) => {
      const start = Number.isFinite(starts[i]) ? (starts[i] as number) : i * w;
      return { start, end: duration ? Math.min(duration, start + w) : start + w, score: Number.isFinite(s) ? s : null };
    }),
    tauHi: num(t.data.tau_hi),
    tauLo: num(t.data.tau_lo),
  };
}

export function VoiceChart({ t, duration, cursor, onSeek }: { t: TechniqueResult | undefined; duration: number; cursor?: number; onSeek?: (s: number) => void }) {
  const v = voiceWindows(t, duration);
  if (!t || !v) return null;
  return (
    <ChartFrame
      title="Synthetic-voice score per 5-second window"
      right={<span className="font-mono text-2xs text-slate-500">{str(t.data.model) ?? "voice model"}</span>}
      legend={
        <>
          <LegendSwatch color="#22d3ee" label="window score" />
          {v.tauHi !== null && <LegendSwatch color={TONE_HI} label={`strict ${v.tauHi.toFixed(2)} (1% false alarms)`} dashed />}
          {v.tauLo !== null && <LegendSwatch color={TONE_LO} label={`lenient ${v.tauLo.toFixed(2)} (5%)`} dashed />}
        </>
      }
      caption={str(t.data.benchmark) ? `Benchmark: ${str(t.data.benchmark)}. Click a point to play that window.` : "Click a point to play that window."}
      height={190}
    >
      <WindowScoreChart windows={v.windows} tauHi={v.tauHi} tauLo={v.tauLo} duration={duration} cursor={cursor} onSeek={onSeek} yLabel="P(synthetic)" />
    </ChartFrame>
  );
}

// ------------------------------------------------------------------ ENF

export function EnfChart({ t, cursor, onSeek, compact }: { t: TechniqueResult | undefined; cursor?: number; onSeek?: (s: number) => void; compact?: boolean }) {
  if (!t) return null;
  const times = numArray(t.data.times);
  const freqs = numArray(t.data.freqs);
  if (times.length < 2 || freqs.length < 2) return null;
  const present = t.data.present === true;
  const jumps = arr(t.data.jumps)
    .map((j) => obj(j))
    .filter((j): j is Record<string, unknown> => j !== null)
    .map((j) => ({ t: num(j.t) ?? 0, d: num(j.delta_hz) ?? 0 }));
  const nominal = num(t.data.nominal_hz) ?? 50;
  const markers: Marker[] = jumps.map((j) => ({ t: j.t, color: TONE_HI, label: `jump ${(j.d * 1000).toFixed(0)} mHz` }));
  return (
    <ChartFrame
      title="Electrical Network Frequency (mains hum) over time"
      right={
        <span className={cx("chip", present ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : "chip-muted")}>
          {present ? `present · SNR ${num(t.data.snr_db)?.toFixed(1) ?? "?"} dB` : "not detected: trace unreliable"}
        </span>
      }
      legend={
        <>
          <LegendSwatch color="#2dd4bf" label="estimated grid frequency" />
          <LegendSwatch color="#94a3b8" label={`nominal ${nominal} Hz`} dashed />
          {jumps.length > 0 && <LegendSwatch color={TONE_HI} label="discontinuity" dashed />}
        </>
      }
      caption={
        compact
          ? undefined
          : "Indian grid frequency drifts slowly around 50 Hz. An abrupt jump means pieces recorded at different times were joined."
      }
      height={compact ? 140 : 170}
    >
      <TimeLineChart
        t={times}
        y={freqs}
        color="#2dd4bf"
        area={false}
        markers={markers}
        reference={{ y: nominal, label: `${nominal} Hz` }}
        cursor={cursor}
        onSeek={onSeek}
        yFormat={(v) => v.toFixed(3)}
        yLabel="Hz"
      />
    </ChartFrame>
  );
}

// ------------------------------------------------------------------ splice / noise floor

export function SpliceChart({ t, cursor, onSeek }: { t: TechniqueResult | undefined; cursor?: number; onSeek?: (s: number) => void }) {
  if (!t || t.status !== "ok") return null;
  const tt = numArray(t.data.noise_floor_t);
  const db = numArray(t.data.noise_floor_db);
  if (tt.length < 2) return null;
  const cues = arr(t.data.cues)
    .map((c) => obj(c))
    .filter((c): c is Record<string, unknown> => c !== null);
  const markers: Marker[] = cues.map((c) => ({
    t: num(c.t) ?? 0,
    color: (num(c.weight) ?? 0) >= 2 ? TONE_HI : TONE_LO,
    label: arr(c.kinds).map(String).join(", ") || "edit cue",
  }));
  return (
    <ChartFrame
      title="Background noise floor (splice detection)"
      right={<span className="font-mono text-2xs text-slate-500">{cues.length} cue{cues.length === 1 ? "" : "s"}</span>}
      legend={
        <>
          <LegendSwatch color="#a78bfa" label="noise floor (dB)" />
          {cues.length > 0 && <LegendSwatch color={TONE_LO} label="possible edit point" dashed />}
        </>
      }
      caption="A continuous recording keeps a steady background; a step or inserted digital silence marks a join."
      height={150}
    >
      <TimeLineChart t={tt} y={db} color="#a78bfa" markers={markers} cursor={cursor} onSeek={onSeek} yFormat={(v) => v.toFixed(0)} yLabel="dB" />
    </ChartFrame>
  );
}

// ------------------------------------------------------------------ transcript

const RULE_LABELS: Record<string, string> = {
  digital_arrest: "‘digital arrest’ threat",
  rbi_safe_account: "‘RBI safe account’",
  otp_request: "OTP request",
  kyc_expiry: "KYC-expiry pressure",
  courier_fee: "courier / customs fee",
  power_cut: "electricity disconnection threat",
};

function segmentsOf(v: unknown) {
  return arr(v)
    .map((s) => obj(s))
    .filter((s): s is Record<string, unknown> => s !== null)
    .map((s) => ({ start: num(s.start) ?? 0, end: num(s.end) ?? 0, text: str(s.text) ?? "" }));
}

export function Transcript({ t, cursor, onSeek }: { t: TechniqueResult | undefined; cursor?: number; onSeek?: (s: number) => void }) {
  const [english, setEnglish] = useState(false);
  if (!t) return null;
  if (t.status !== "ok") {
    return (
      <div className="rounded-xl border border-white/[0.06] bg-ink-950/40 p-3 text-xs text-slate-500">
        <span className="font-semibold text-slate-300">Transcript:</span> {t.summary || t.status}
      </div>
    );
  }
  const original = segmentsOf(t.data.segments);
  const translated = segmentsOf(t.data.translation_segments);
  const translationText = str(t.data.translation);
  const hasTranslation = translated.length > 0 || !!translationText;
  const segs =
    english && hasTranslation
      ? translated.length
        ? translated
        : [{ start: original[0]?.start ?? 0, end: original[original.length - 1]?.end ?? 0, text: translationText ?? "" }]
      : original;
  const asks = arr(t.data.asks)
    .map((a) => obj(a))
    .filter((a): a is Record<string, unknown> => a !== null)
    .map((a) => ({ type: str(a.type) ?? "", text: str(a.text) ?? "", meaning: str(a.meaning) ?? "" }));
  const rules = arr(t.data.rules).map(String);
  const askTexts = asks.map((a) => a.text).filter(Boolean);
  const lang = str(t.data.language);
  const prob = num(t.data.language_probability);
  return (
    <div className="rounded-xl border border-white/[0.06] bg-ink-950/40">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b hairline px-3 py-2">
        <span className="text-xs font-semibold text-slate-200">Transcript (offline speech recognition)</span>
        <span className="flex items-center gap-2">
          {hasTranslation && (
            <span className="flex rounded-md border border-white/10 p-0.5 text-2xs">
              <button type="button" onClick={() => setEnglish(false)} className={cx("rounded px-1.5 py-0.5", !english ? "bg-white/10 text-white" : "text-slate-400")}>
                Original
              </button>
              <button type="button" onClick={() => setEnglish(true)} className={cx("rounded px-1.5 py-0.5", english ? "bg-white/10 text-white" : "text-slate-400")}>
                English
              </button>
            </span>
          )}
          <span className="inline-flex items-center gap-1.5 font-mono text-2xs text-slate-500">
            <Languages className="h-3.5 w-3.5" />
            {lang ?? "?"}
            {prob !== null ? ` · p=${prob.toFixed(2)}` : ""} · {str(t.data.engine) ?? "asr"}
          </span>
        </span>
      </div>
      {(asks.length > 0 || rules.length > 0) && (
        <div className="space-y-1.5 border-b border-red-500/20 bg-red-500/[0.05] px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-red-200">
            <AlertOctagon className="h-3.5 w-3.5" /> Fraud-language cues (investigative context, not authenticity evidence)
          </div>
          <div className="flex flex-wrap gap-1.5">
            {groupAsks(asks).map((g) => (
              <span
                key={g.type}
                className="rounded-md border border-red-400/30 bg-red-500/10 px-2 py-0.5 text-2xs text-red-100"
                title={g.texts.map((x) => `“${x}”`).join("\n")}
              >
                <span className="font-mono text-red-300">{g.type}</span> {g.meaning}
                {g.texts.length > 1 ? <span className="ml-1 font-mono text-red-300/80">×{g.texts.length}</span> : null}
              </span>
            ))}
            {rules.map((r) => (
              <span key={r} className="rounded-md border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-2xs text-amber-100">
                {RULE_LABELS[r] ?? r.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}
      <ol className="max-h-[260px] space-y-0.5 overflow-y-auto p-2">
        {segs.length === 0 && <li className="p-2 text-xs text-slate-500">No speech segments.</li>}
        {segs.map((s, i) => {
          const active = cursor !== undefined && cursor >= s.start && cursor < s.end;
          const parts = highlightAsks(s.text, askTexts);
          return (
            <li key={i}>
              <button
                type="button"
                onClick={() => onSeek?.(s.start)}
                className={cx(
                  "flex w-full gap-3 rounded-lg px-2 py-1.5 text-left transition",
                  active ? "bg-accent/10 shadow-[inset_2px_0_0_0_#22d3ee]" : "hover:bg-white/[0.04]",
                )}
              >
                <span className="w-[86px] shrink-0 pt-0.5 font-mono text-2xs text-slate-500">
                  {formatClock(s.start)}–{formatClock(s.end)}
                </span>
                <span className={cx("min-w-0 text-sm leading-relaxed", active ? "text-white" : "text-slate-300")}>
                  {parts.map((p, j) =>
                    p.hit ? (
                      <mark key={j} className="rounded bg-red-500/25 px-0.5 text-red-100 underline decoration-red-400/70 underline-offset-2">
                        {p.text}
                      </mark>
                    ) : (
                      <span key={j}>{p.text}</span>
                    ),
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

// ------------------------------------------------------------------ the whole audio track analysis

/** Shaded spans for the spectrogram: synthetic-voice windows, splice cues and ENF jumps. */
export function audioBands(analysis: EvidenceAnalysis | null): Band[] {
  const out: Band[] = [];
  const add = (spans: TimeSpan[], color: string, label: string) => {
    for (const s of spans) out.push({ start: s.start_s, end: s.end_s, color, label: s.label || label });
  };
  for (const id of ["audio.voice", "audio.splice", "audio.enf"]) {
    const t = findTechnique(analysis, id);
    for (const f of t?.findings ?? []) {
      if (f.hypothesis === "neutral") continue;
      add(f.spans, f.hypothesis === "synthetic" ? TONE_HI : TONE_LO, f.title);
    }
  }
  return out;
}
