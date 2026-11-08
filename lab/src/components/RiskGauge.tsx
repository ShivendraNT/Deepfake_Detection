import { motion } from "framer-motion";
import { useId } from "react";
import { useCountUp } from "../lib/hooks";

/**
 * Radial risk-index gauge (0–100), 270° sweep. The colour comes from the verdict label, not
 * from the number: the verdict words are authoritative, the index is only a dashboard aid.
 */
export function RiskGauge({
  value,
  color,
  size = 168,
  stroke = 12,
  label = "risk index",
  animate = true,
}: {
  value: number | null | undefined;
  color: string;
  size?: number;
  stroke?: number;
  label?: string;
  animate?: boolean;
}) {
  const id = useId().replace(/:/g, "");
  const v = typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null;
  const shown = useCountUp(animate && v !== null ? v : (v ?? 0), 1100);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const sweep = 0.75; // 270°
  const track = c * sweep;
  const frac = v === null ? 0 : v / 100;
  const ticks = Array.from({ length: 11 }, (_, i) => i / 10);
  const cx = size / 2;
  const cy = size / 2;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="overflow-visible">
        <defs>
          <linearGradient id={`g${id}`} x1="0" y1="1" x2="1" y2="0">
            <stop offset="0%" stopColor={color} stopOpacity="0.45" />
            <stop offset="100%" stopColor={color} stopOpacity="1" />
          </linearGradient>
          <filter id={`f${id}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <g transform={`rotate(135 ${cx} ${cy})`}>
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="rgba(148,163,184,0.12)"
            strokeWidth={stroke}
            strokeDasharray={`${track} ${c}`}
            strokeLinecap="round"
          />
          <motion.circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={`url(#g${id})`}
            strokeWidth={stroke}
            strokeLinecap="round"
            filter={`url(#f${id})`}
            strokeDasharray={`${track} ${c}`}
            initial={{ strokeDashoffset: animate ? track : track * (1 - frac) }}
            animate={{ strokeDashoffset: track * (1 - frac) }}
            transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          />
        </g>
        {ticks.map((t) => {
          const a = ((135 + 270 * t) * Math.PI) / 180;
          const r1 = r - stroke / 2 - 5;
          const major = Math.round(t * 10) % 5 === 0;
          const r2 = major ? r1 - 6 : r1 - 3;
          return (
            <line
              key={t}
              x1={cx + Math.cos(a) * r1}
              y1={cy + Math.sin(a) * r1}
              x2={cx + Math.cos(a) * r2}
              y2={cy + Math.sin(a) * r2}
              stroke="rgba(148,163,184,0.3)"
              strokeWidth={1}
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div
          className="font-mono font-semibold tabular leading-none text-white"
          style={{ fontSize: size * 0.24, textShadow: `0 0 24px ${color}66` }}
        >
          {v === null ? "—" : Math.round(shown)}
        </div>
        <div className="mt-1 text-2xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      </div>
    </div>
  );
}

/** Compact ring for cards. */
export function MiniGauge({ value, color, size = 40 }: { value: number | null | undefined; color: string; size?: number }) {
  const v = typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null;
  const stroke = 4;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const frac = v === null ? 0 : v / 100;
  return (
    <div className="relative" style={{ width: size, height: size }} title={v === null ? "no risk index" : `risk index ${v}/100`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(148,163,184,0.15)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - frac) }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          style={{ filter: `drop-shadow(0 0 4px ${color})` }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center font-mono text-[0.7rem] font-semibold text-slate-100">
        {v === null ? "—" : v}
      </div>
    </div>
  );
}
