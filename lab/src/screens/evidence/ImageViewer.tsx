import { motion } from "framer-motion";
import { Columns2, Eye, EyeOff, Layers, Maximize2, ScanSearch, SquareDashed } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { urls, type EvidenceAnalysis, type LabEvidence, type Region } from "../../api";
import { Lightbox, type LightboxItem } from "../../components/Modal";
import { cx, SafeImg } from "../../components/ui";
import { overlayArtifacts, shortArtifactLabel } from "../../lib/media";
import { hypothesisMeta } from "../../lib/verdict";

interface MarkedRegion extends Region {
  key: string;
  hypothesis: string;
  finding: string;
  technique: string;
}

/** Every region any finding marked on the image (clones, faces, splices …). */
export function collectRegions(analysis: EvidenceAnalysis | null): MarkedRegion[] {
  const out: MarkedRegion[] = [];
  for (const t of analysis?.techniques ?? []) {
    for (const f of t.findings) {
      f.regions.forEach((r, i) => {
        if (![r.x, r.y, r.w, r.h].every((v) => Number.isFinite(v))) return;
        out.push({ ...r, key: `${f.code}-${t.id}-${i}`, hypothesis: f.hypothesis, finding: f.title, technique: t.name });
      });
    }
  }
  return out;
}

type Mode = "overlay" | "compare";

export function ImageViewer({ ev, analysis }: { ev: LabEvidence; analysis: EvidenceAnalysis | null }) {
  const overlays = useMemo(() => overlayArtifacts(analysis), [analysis]);
  const regions = useMemo(() => collectRegions(analysis), [analysis]);
  const flaggedOverlay = useMemo(() => {
    // Prefer the overlay of a technique that produced a non-neutral finding.
    for (const t of analysis?.techniques ?? []) {
      if (t.findings.some((f) => f.hypothesis !== "neutral" && f.strength > 0)) {
        const a = t.artifacts.find((x) => x.kind === "overlay" || x.kind === "heatmap");
        if (a) return a.name;
      }
    }
    return null;
  }, [analysis]);
  const [selected, setSelected] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("overlay");
  const [opacity, setOpacity] = useState(0.7);
  const [split, setSplit] = useState(0.5);
  const [showRegions, setShowRegions] = useState(true);
  const [hover, setHover] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState<number | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  useEffect(() => {
    setSelected(flaggedOverlay);
  }, [flaggedOverlay, ev.id]);

  const sel = overlays.find((o) => o.name === selected) ?? null;
  const overlaySrc = sel ? urls.artifact(ev.id, sel.name) : null;

  const moveSplit = useCallback((clientX: number) => {
    const el = stage.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setSplit(Math.max(0, Math.min(1, (clientX - r.left) / Math.max(1, r.width))));
  }, []);
  const onPointerDown = (e: ReactPointerEvent) => {
    if (mode !== "compare" || !sel) return;
    dragging.current = true;
    (e.target as Element).setPointerCapture?.(e.pointerId);
    moveSplit(e.clientX);
  };

  const lightboxItems: LightboxItem[] = [
    { src: urls.file(ev.id), title: `${ev.exhibit} · ${ev.filename}`, caption: "Original exhibit (as received, write-once copy)" },
    ...overlays.map((o) => ({ src: urls.artifact(ev.id, o.name), title: o.title, caption: o.caption, meta: o.name })),
  ];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-ink-950/50 p-1">
          <button
            type="button"
            onClick={() => setSelected(null)}
            className={cx("rounded-md px-2.5 py-1 text-xs font-medium transition", !selected ? "bg-white/10 text-white" : "text-slate-400 hover:text-slate-200")}
          >
            Original
          </button>
          {overlays.map((o) => (
            <button
              key={o.name}
              type="button"
              title={o.caption || o.title}
              onClick={() => setSelected(o.name)}
              className={cx(
                "rounded-md px-2.5 py-1 text-xs font-medium transition",
                selected === o.name ? "bg-accent/20 text-accent-soft shadow-[inset_0_0_0_1px_rgba(34,211,238,0.35)]" : "text-slate-400 hover:text-slate-200",
              )}
            >
              {shortArtifactLabel(o.name, o.title)}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1">
          {regions.length > 0 && (
            <button
              type="button"
              onClick={() => setShowRegions((s) => !s)}
              className={cx("btn-sm", showRegions ? "btn-secondary" : "btn-ghost")}
              title="Regions marked by the findings"
            >
              {showRegions ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />} Regions {regions.length}
            </button>
          )}
          <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-ink-950/50 p-1">
            <button
              type="button"
              disabled={!sel}
              onClick={() => setMode("overlay")}
              className={cx("flex items-center gap-1 rounded-md px-2 py-1 text-xs transition disabled:opacity-40", mode === "overlay" ? "bg-white/10 text-white" : "text-slate-400")}
              title="Blend the heatmap over the image"
            >
              <Layers className="h-3.5 w-3.5" /> Overlay
            </button>
            <button
              type="button"
              disabled={!sel}
              onClick={() => setMode("compare")}
              className={cx("flex items-center gap-1 rounded-md px-2 py-1 text-xs transition disabled:opacity-40", mode === "compare" ? "bg-white/10 text-white" : "text-slate-400")}
              title="Before / after slider"
            >
              <Columns2 className="h-3.5 w-3.5" /> Compare
            </button>
          </div>
          <button type="button" className="btn-ghost btn-sm" onClick={() => setLightbox(selected ? 1 + overlays.findIndex((o) => o.name === selected) : 0)} title="Enlarge">
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="checker flex min-h-[320px] items-center justify-center overflow-hidden rounded-xl border border-white/[0.08] p-3">
        <div
          ref={stage}
          className={cx("relative inline-block max-w-full select-none leading-none", mode === "compare" && sel && "cursor-ew-resize")}
          onPointerDown={onPointerDown}
          onPointerMove={(e) => dragging.current && moveSplit(e.clientX)}
          onPointerUp={() => (dragging.current = false)}
          onPointerCancel={() => (dragging.current = false)}
        >
          <SafeImg
            src={urls.file(ev.id)}
            alt={ev.filename}
            draggable={false}
            className="block max-h-[540px] max-w-full object-contain"
            fallback={<div className="p-16 text-sm text-slate-500">The original could not be displayed by the browser.</div>}
          />
          {overlaySrc && (
            <img
              key={overlaySrc}
              src={overlaySrc}
              alt={sel?.title ?? "overlay"}
              draggable={false}
              className="pointer-events-none absolute inset-0 h-full w-full"
              style={
                mode === "overlay"
                  ? { opacity }
                  : { clipPath: `inset(0 0 0 ${split * 100}%)`, opacity: 1 }
              }
              onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
            />
          )}
          {mode === "compare" && sel && (
            <div className="pointer-events-none absolute inset-y-0" style={{ left: `${split * 100}%` }}>
              <div className="absolute inset-y-0 -left-px w-0.5 bg-white shadow-[0_0_12px_rgba(255,255,255,0.8)]" />
              <div className="absolute top-1/2 flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/70 bg-ink-950/80 text-white shadow-lg">
                <Columns2 className="h-4 w-4" />
              </div>
              <span className="absolute -left-2 top-2 -translate-x-full whitespace-nowrap rounded bg-ink-950/80 px-1.5 py-0.5 text-[10px] text-slate-200">
                original
              </span>
              <span className="absolute left-2 top-2 whitespace-nowrap rounded bg-ink-950/80 px-1.5 py-0.5 text-[10px] text-accent-soft">
                {shortArtifactLabel(sel.name, sel.title)}
              </span>
            </div>
          )}
          {showRegions &&
            regions.map((r, i) => {
              const h = hypothesisMeta(r.hypothesis);
              const color = r.hypothesis === "neutral" ? "#94a3b8" : h.hex;
              const on = hover === r.key;
              return (
                <motion.div
                  key={r.key}
                  initial={{ opacity: 0, scale: 1.08 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.15 + i * 0.08 }}
                  className="absolute"
                  style={{
                    left: `${r.x * 100}%`,
                    top: `${r.y * 100}%`,
                    width: `${r.w * 100}%`,
                    height: `${r.h * 100}%`,
                    border: `2px solid ${color}`,
                    boxShadow: on ? `0 0 0 2px ${color}55, 0 0 24px ${color}` : `0 0 14px -2px ${color}`,
                    background: on ? `${color}1f` : "transparent",
                    borderRadius: 4,
                  }}
                  onMouseEnter={() => setHover(r.key)}
                  onMouseLeave={() => setHover(null)}
                >
                  <span
                    className="absolute -top-px left-[-2px] -translate-y-full whitespace-nowrap rounded-t px-1.5 py-0.5 text-[10px] font-semibold text-ink-950"
                    style={{ background: color }}
                  >
                    {r.label || r.finding}
                    {r.score !== null && Number.isFinite(r.score) ? ` · ${Math.abs(r.score) >= 10 ? r.score.toFixed(0) : r.score.toFixed(2)}` : ""}
                  </span>
                </motion.div>
              );
            })}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <div className="min-w-0 text-xs text-slate-400">
          {sel ? (
            <>
              <span className="font-medium text-slate-200">{sel.title}.</span> {sel.caption}
            </>
          ) : regions.length ? (
            <span className="inline-flex items-center gap-1.5">
              <SquareDashed className="h-3.5 w-3.5 text-slate-500" /> Boxes mark regions cited by the findings. Choose a heatmap above to
              see the pixel evidence.
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5">
              <ScanSearch className="h-3.5 w-3.5 text-slate-500" /> Choose a heatmap above to see what each technique measured.
            </span>
          )}
          {hover && <div className="mt-1 text-slate-300">{regions.find((r) => r.key === hover)?.finding}</div>}
        </div>
        {sel && mode === "overlay" && (
          <label className="flex items-center gap-2 text-2xs text-slate-400">
            Opacity
            <input type="range" min={0} max={1} step={0.01} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} className="w-36" />
            <span className="w-8 font-mono text-slate-300">{Math.round(opacity * 100)}%</span>
          </label>
        )}
        {sel && mode === "compare" && (
          <label className="flex items-center gap-2 text-2xs text-slate-400">
            Split
            <input type="range" min={0} max={1} step={0.01} value={split} onChange={(e) => setSplit(Number(e.target.value))} className="w-36" />
            <span className="w-8 font-mono text-slate-300">{Math.round(split * 100)}%</span>
          </label>
        )}
      </div>
      <Lightbox items={lightboxItems} index={lightbox} onIndex={setLightbox} onClose={() => setLightbox(null)} />
    </div>
  );
}
