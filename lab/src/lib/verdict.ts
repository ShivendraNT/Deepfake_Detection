/** Colours, words and ordering for verdicts, hypotheses, strengths, categories and statuses. */

import type {
  Category,
  EvidenceStatus,
  Hypothesis,
  LabEvidence,
  TechniqueStatus,
  VerdictLabel,
} from "../api";

export type Tone = "synthetic" | "manipulated" | "suspicious" | "clean" | "inconclusive" | "pending" | "error";

export interface ToneMeta {
  tone: Tone;
  /** Short label for badges. */
  label: string;
  /** Longer phrase for headings. */
  long: string;
  /** Hex colour for SVG / charts. */
  hex: string;
  /** Tailwind text colour class. */
  text: string;
  /** Tailwind background tint class. */
  bg: string;
  /** Tailwind border class. */
  border: string;
}

export const TONES: Record<Tone, Omit<ToneMeta, "label" | "long">> = {
  synthetic: {
    tone: "synthetic",
    hex: "#ff4d6d",
    text: "text-verdict-synthetic",
    bg: "bg-verdict-synthetic/10",
    border: "border-verdict-synthetic/40",
  },
  manipulated: {
    tone: "manipulated",
    hex: "#ff7a45",
    text: "text-verdict-manipulated",
    bg: "bg-verdict-manipulated/10",
    border: "border-verdict-manipulated/40",
  },
  suspicious: {
    tone: "suspicious",
    hex: "#fbbf24",
    text: "text-verdict-suspicious",
    bg: "bg-verdict-suspicious/10",
    border: "border-verdict-suspicious/40",
  },
  clean: {
    tone: "clean",
    hex: "#34d399",
    text: "text-verdict-clean",
    bg: "bg-verdict-clean/10",
    border: "border-verdict-clean/40",
  },
  inconclusive: {
    tone: "inconclusive",
    hex: "#94a3b8",
    text: "text-verdict-inconclusive",
    bg: "bg-verdict-inconclusive/10",
    border: "border-verdict-inconclusive/40",
  },
  pending: {
    tone: "pending",
    hex: "#22d3ee",
    text: "text-accent",
    bg: "bg-accent/10",
    border: "border-accent/40",
  },
  error: {
    tone: "error",
    hex: "#f87171",
    text: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/40",
  },
};

export const VERDICT_ORDER: VerdictLabel[] = [
  "SYNTHETIC",
  "MANIPULATED",
  "SUSPICIOUS",
  "INCONCLUSIVE",
  "NO_INDICATORS",
];

const VERDICT_WORDS: Record<VerdictLabel, { tone: Tone; label: string; long: string }> = {
  SYNTHETIC: { tone: "synthetic", label: "Synthetic", long: "Synthetic (AI-generated / deepfake)" },
  MANIPULATED: { tone: "manipulated", label: "Manipulated", long: "Manipulated after capture" },
  SUSPICIOUS: { tone: "suspicious", label: "Suspicious", long: "Suspicious: examine further" },
  NO_INDICATORS: { tone: "clean", label: "No indications", long: "No indications found" },
  INCONCLUSIVE: { tone: "inconclusive", label: "Inconclusive", long: "Inconclusive" },
};

export function isVerdictLabel(v: unknown): v is VerdictLabel {
  return typeof v === "string" && v in VERDICT_WORDS;
}

export function verdictMeta(label: VerdictLabel | null | undefined): ToneMeta {
  if (!label || !isVerdictLabel(label)) {
    return { ...TONES.inconclusive, label: "No verdict", long: "No verdict" };
  }
  const w = VERDICT_WORDS[label];
  return { ...TONES[w.tone], label: w.label, long: w.long };
}

/** Badge meta for an exhibit: its verdict when done, else its processing status. */
export function evidenceMeta(ev: Pick<LabEvidence, "status" | "verdict">): ToneMeta {
  return statusMeta(ev.status, ev.verdict);
}

export function statusMeta(status: EvidenceStatus, verdict: VerdictLabel | null): ToneMeta {
  if (status === "done") return verdictMeta(verdict);
  if (status === "error") return { ...TONES.error, label: "Error", long: "Analysis failed" };
  if (status === "analyzing") return { ...TONES.pending, label: "Analysing", long: "Analysing" };
  return { ...TONES.pending, label: "Queued", long: "Queued for analysis" };
}

export function isPending(status: EvidenceStatus | string | null | undefined): boolean {
  return status === "queued" || status === "analyzing";
}

/** True for the verdicts that count as "flagged" (same rule as GET /lab/api/cases). */
export function isFlagged(label: VerdictLabel | null | undefined): boolean {
  return label === "SYNTHETIC" || label === "MANIPULATED" || label === "SUSPICIOUS";
}

// ------------------------------------------------------------------ hypotheses & strengths

export const HYPOTHESIS_META: Record<Hypothesis, { label: string; hex: string; text: string; bg: string }> = {
  synthetic: { label: "Synthetic", hex: "#ff4d6d", text: "text-verdict-synthetic", bg: "bg-verdict-synthetic" },
  manipulated: {
    label: "Manipulated",
    hex: "#ff7a45",
    text: "text-verdict-manipulated",
    bg: "bg-verdict-manipulated",
  },
  authentic: { label: "Authentic", hex: "#34d399", text: "text-verdict-clean", bg: "bg-verdict-clean" },
  neutral: { label: "Informational", hex: "#64748b", text: "text-slate-400", bg: "bg-slate-500" },
};

export function hypothesisMeta(h: string | null | undefined) {
  return HYPOTHESIS_META[(h as Hypothesis) in HYPOTHESIS_META ? (h as Hypothesis) : "neutral"];
}

export const STRENGTH_WORDS = [
  "no support",
  "weak support",
  "moderate support",
  "strong support",
  "very strong support",
] as const;

export function strengthWord(s: number | null | undefined): string {
  const i = Math.max(0, Math.min(4, Math.round(s ?? 0)));
  return STRENGTH_WORDS[i] ?? "no support";
}

// ------------------------------------------------------------------ categories

export const CATEGORY_ORDER: Category[] = [
  "integrity",
  "metadata",
  "provenance",
  "tampering",
  "synthetic",
  "content",
];

export const CATEGORY_META: Record<Category, { label: string; blurb: string }> = {
  integrity: { label: "Integrity", blurb: "Hashes, file structure and container sanity" },
  metadata: { label: "Metadata", blurb: "EXIF, XMP, IPTC and container tags" },
  provenance: { label: "Provenance", blurb: "Device, platform, generator and Content Credentials" },
  tampering: { label: "Tampering", blurb: "Localised edits: splices, clones, frame edits" },
  synthetic: { label: "Synthetic media", blurb: "AI-generation and deepfake detectors" },
  content: { label: "Content", blurb: "What is said or shown: context, not authenticity" },
};

export function categoryMeta(c: string) {
  return CATEGORY_META[(c as Category) in CATEGORY_META ? (c as Category) : "content"];
}

// ------------------------------------------------------------------ technique status

export const TECH_STATUS_META: Record<
  TechniqueStatus,
  { label: string; text: string; bg: string; border: string }
> = {
  ok: { label: "Ran", text: "text-accent-soft", bg: "bg-accent/10", border: "border-accent/30" },
  skipped: {
    label: "Not applicable",
    text: "text-slate-300",
    bg: "bg-slate-500/10",
    border: "border-slate-500/30",
  },
  unavailable: {
    label: "Model unavailable",
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
  },
  error: { label: "Error", text: "text-red-300", bg: "bg-red-500/10", border: "border-red-500/30" },
};

export function techStatusMeta(s: string) {
  return TECH_STATUS_META[(s as TechniqueStatus) in TECH_STATUS_META ? (s as TechniqueStatus) : "error"];
}

/** Count verdict labels (and pending/error) for a distribution bar, in display order. */
export function verdictDistribution(
  items: Pick<LabEvidence, "status" | "verdict">[],
): { key: string; count: number; meta: ToneMeta }[] {
  const counts = new Map<string, number>();
  for (const e of items) {
    const key = e.status === "done" ? (e.verdict ?? "INCONCLUSIVE") : e.status === "error" ? "ERROR" : "PENDING";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const keys = [...VERDICT_ORDER, "PENDING", "ERROR"];
  return keys
    .filter((k) => (counts.get(k) ?? 0) > 0)
    .map((k) => ({
      key: k,
      count: counts.get(k) ?? 0,
      meta:
        k === "PENDING"
          ? statusMeta("analyzing", null)
          : k === "ERROR"
            ? statusMeta("error", null)
            : verdictMeta(k as VerdictLabel),
    }));
}

/** Same distribution, from the `counts` map of GET /cases/{id}. */
export function distributionFromCounts(counts: Record<string, number>) {
  const items: Pick<LabEvidence, "status" | "verdict">[] = [];
  for (const [k, n] of Object.entries(counts)) {
    for (let i = 0; i < n; i += 1) {
      if (isVerdictLabel(k)) items.push({ status: "done", verdict: k });
      else if (k === "error") items.push({ status: "error", verdict: null });
      else if (k === "done") items.push({ status: "done", verdict: null });
      else items.push({ status: "analyzing", verdict: null });
    }
  }
  return verdictDistribution(items);
}

/** "[strong support] Cloned region …" → { strength: 3, text: "Cloned region …" } */
export function parseRationale(line: string): { strength: number | null; word: string | null; text: string } {
  const m = /^\s*\[([^\]]+)\]\s*(.*)$/.exec(line);
  if (!m) return { strength: null, word: null, text: line };
  const word = (m[1] ?? "").trim().toLowerCase();
  const idx = (STRENGTH_WORDS as readonly string[]).indexOf(word);
  return { strength: idx >= 0 ? idx : null, word, text: (m[2] ?? "").trim() };
}
