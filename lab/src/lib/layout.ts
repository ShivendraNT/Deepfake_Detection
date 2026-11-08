/** Graph layout for the provenance graph (pure, deterministic). */

import type { LabEvidence } from "../api";

/** Circle layout: references grouped on the left arc, questioned items around the right. */
export function circleLayout(evidence: LabEvidence[]): Record<string, { x: number; y: number }> {
  const refs = evidence.filter((e) => e.role === "reference");
  const qs = evidence.filter((e) => e.role !== "reference");
  const byNum = (a: LabEvidence, b: LabEvidence) => a.exhibit.localeCompare(b.exhibit, undefined, { numeric: true });
  const ordered = [...refs.sort(byNum), ...qs.sort(byNum)];
  const n = ordered.length;
  const out: Record<string, { x: number; y: number }> = {};
  if (n === 0) return out;
  if (n === 1) {
    out[ordered[0]!.id] = { x: 0, y: 0 };
    return out;
  }
  const step = (2 * Math.PI) / n;
  const r = Math.max(200, 205 / (2 * Math.sin(Math.PI / n)));
  const start = Math.PI + ((refs.length - 1) / 2) * step; // centre the references on the left
  ordered.forEach((e, i) => {
    const a = start - i * step;
    out[e.id] = { x: Math.cos(a) * r * 1.45 - 94, y: Math.sin(a) * r * 0.92 - 75 };
  });
  return out;
}
