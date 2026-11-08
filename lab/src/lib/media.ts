import { urls, type EvidenceAnalysis, type LabEvidence, type MediaKind, type TechniqueResult } from "../api";

/** Artifact names the engine writes for every exhibit of a kind (they may not exist yet). */
export const POSTER_ARTIFACT: Partial<Record<MediaKind, string>> = {
  video: "contact_sheet.jpg",
  audio: "spectrogram.png",
};

/** Best thumbnail for an exhibit card: the image itself, a video's contact sheet, an audio spectrogram. */
export function thumbUrl(ev: Pick<LabEvidence, "id" | "kind">, analysis?: EvidenceAnalysis | null): string | null {
  const kind = analysis?.media.kind ?? ev.kind;
  if (kind === "image") return urls.file(ev.id);
  if (analysis) {
    const want = kind === "video" ? ["contact_sheet.jpg", "face_frames.png"] : ["spectrogram.png"];
    for (const t of analysis.techniques) {
      for (const a of t.artifacts) if (want.includes(a.name)) return urls.artifact(ev.id, a.name);
    }
    return null;
  }
  const name = POSTER_ARTIFACT[kind];
  return name ? urls.artifact(ev.id, name) : null;
}

export function findTechnique(analysis: EvidenceAnalysis | null | undefined, id: string): TechniqueResult | undefined {
  return analysis?.techniques.find((t) => t.id === id);
}

/** Artifacts that can be laid over the image pixel-for-pixel (same geometry as the original). */
export function overlayArtifacts(analysis: EvidenceAnalysis | null | undefined) {
  const out: { technique: string; name: string; title: string; caption: string; kind: string }[] = [];
  for (const t of analysis?.techniques ?? []) {
    for (const a of t.artifacts) {
      if (a.kind === "heatmap" || a.kind === "overlay") {
        out.push({ technique: t.id, name: a.name, title: a.title, caption: a.caption, kind: a.kind });
      }
    }
  }
  return out;
}

const SHORT_LABELS: Record<string, string> = {
  "ela.jpg": "ELA",
  "ela_overlay.jpg": "ELA overlay",
  "noise_map.jpg": "Noise map",
  "noise_overlay.jpg": "Noise overlay",
  "copy_move.jpg": "Copy-move",
};

/** Compact button label for an overlay artifact ("ELA", "Noise map" …). */
export function shortArtifactLabel(name: string, title: string): string {
  const known = SHORT_LABELS[name];
  if (known) return known;
  const t = title.replace(/\s*\([^)]*\)/g, "").trim();
  const words = t.split(/\s+/);
  return words.length > 3 ? `${words.slice(0, 3).join(" ")}…` : t || name;
}

export function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function numArray(v: unknown): number[] {
  return Array.isArray(v) ? v.map((x) => (typeof x === "number" && Number.isFinite(x) ? x : Number.NaN)) : [];
}

export function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

export function obj(v: unknown): Record<string, unknown> | null {
  return typeof v === "object" && v !== null && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

export function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

/** Media facts line: "JPEG · 512×326 · 49.0 KB" etc. */
export function mediaFacts(a: EvidenceAnalysis | null | undefined): string[] {
  if (!a) return [];
  const m = a.media;
  const out: string[] = [m.format.toUpperCase()];
  if (m.width && m.height) out.push(`${m.width}×${m.height}`);
  if (m.duration_s) out.push(`${m.duration_s.toFixed(1)} s`);
  if (m.fps) out.push(`${m.fps.toFixed(m.fps % 1 ? 2 : 0)} fps`);
  if (m.codec) out.push(m.codec);
  if (m.sample_rate) out.push(`${(m.sample_rate / 1000).toFixed(1)} kHz`);
  if (m.channels) out.push(m.channels === 1 ? "mono" : `${m.channels} ch`);
  return out;
}
