/** Evidence links (provenance graph edges): labels, colours and de-duplication. */

import type { EvidenceLink, LinkKind } from "../api";

/**
 * Categorical colours for link kinds, in this fixed order (validated for the dark surface with
 * the dataviz palette validator: lightness band, chroma, CVD ΔE ≥ 8.9, normal-vision ΔE ≥ 19.7).
 * They avoid the verdict status hues; edges also carry a text label and a dash pattern.
 */
export const LINK_META: Record<LinkKind, { label: string; hex: string; blurb: string; dash?: string }> = {
  near_duplicate: {
    label: "Near duplicate",
    hex: "#3987e5",
    blurb: "Perceptual hashes are close: the same picture, re-encoded or resized",
  },
  shares_content: {
    label: "Shares content",
    hex: "#199e70",
    blurb: "A region or background is common: one is derived from the other",
    dash: "7 5",
  },
  same_face: { label: "Same face", hex: "#9085e9", blurb: "Face embeddings match (SFace)", dash: "2 5" },
  same_speaker: { label: "Same speaker", hex: "#d55181", blurb: "Speaker embeddings match", dash: "2 5" },
  same_device: { label: "Same device", hex: "#0f9fb8", blurb: "Same camera make / model / serial", dash: "10 4 2 4" },
  same_generator: { label: "Same generator", hex: "#c98500", blurb: "Same AI-generator signature", dash: "10 4 2 4" },
};

export function linkMeta(kind: string): { label: string; hex: string; blurb: string; dash?: string } {
  return (
    LINK_META[kind as LinkKind] ?? {
      label: kind.replace(/_/g, " "),
      hex: "#94a3b8",
      blurb: "",
    }
  );
}

/** Order-independent key of the two exhibits a link joins. */
export function pairKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

/**
 * One link per (unordered pair, kind). When both A→B and B→A exist (each exhibit compares
 * itself with the others when it is analysed) keep the higher score; on a tie keep the one
 * with artifacts. Artifacts stay with their own source (they live under link.source).
 */
export function dedupeLinks(links: EvidenceLink[] | null | undefined): EvidenceLink[] {
  const best = new Map<string, EvidenceLink>();
  for (const l of links ?? []) {
    if (!l || !l.source || !l.target || l.source === l.target) continue;
    const key = `${pairKey(l.source, l.target)}#${l.kind}`;
    const cur = best.get(key);
    if (
      !cur ||
      l.score > cur.score ||
      (l.score === cur.score && (l.artifacts?.length ?? 0) > (cur.artifacts?.length ?? 0))
    ) {
      best.set(key, l);
    }
  }
  return [...best.values()];
}

export interface LinkGroup {
  key: string;
  a: string;
  b: string;
  links: EvidenceLink[];
}

/** De-duplicated links grouped per pair of exhibits (one graph edge per pair), strongest first. */
export function groupLinks(links: EvidenceLink[] | null | undefined): LinkGroup[] {
  const groups = new Map<string, LinkGroup>();
  for (const l of dedupeLinks(links)) {
    const key = pairKey(l.source, l.target);
    const [a, b] = key.split("|") as [string, string];
    const g = groups.get(key) ?? { key, a, b, links: [] };
    g.links.push(l);
    groups.set(key, g);
  }
  for (const g of groups.values()) g.links.sort((x, y) => y.score - x.score);
  return [...groups.values()].sort((x, y) => (y.links[0]?.score ?? 0) - (x.links[0]?.score ?? 0));
}

/** Links that touch one exhibit, de-duplicated. */
export function linksFor(evidenceId: string, links: EvidenceLink[] | null | undefined): EvidenceLink[] {
  return dedupeLinks(links).filter((l) => l.source === evidenceId || l.target === evidenceId);
}
