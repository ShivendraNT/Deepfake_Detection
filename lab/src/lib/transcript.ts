/** Pure helpers for the transcript view: fraud-language highlighting and grouping. */

export interface Ask {
  type: string;
  text: string;
  meaning: string;
}

function norm(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Split a segment's text into plain and highlighted parts for the ask phrases it contains. */
export function highlightAsks(text: string, asks: string[]): { text: string; hit: boolean }[] {
  const lower = text.toLowerCase();
  const ranges: [number, number][] = [];
  for (const a of asks) {
    const needle = a.trim().toLowerCase();
    if (needle.length < 3) continue;
    let from = 0;
    for (;;) {
      const i = lower.indexOf(needle, from);
      if (i < 0) break;
      ranges.push([i, i + needle.length]);
      from = i + needle.length;
    }
  }
  if (!ranges.length) {
    // the ask may span several segments: highlight a segment that lies wholly inside one
    const n = norm(text);
    if (n && n.split(" ").length >= 3 && asks.some((a) => norm(a).includes(n))) return [{ text, hit: true }];
    return [{ text, hit: false }];
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  const out: { text: string; hit: boolean }[] = [];
  let pos = 0;
  for (const [a, b] of merged) {
    if (a > pos) out.push({ text: text.slice(pos, a), hit: false });
    out.push({ text: text.slice(a, b), hit: true });
    pos = b;
  }
  if (pos < text.length) out.push({ text: text.slice(pos), hit: false });
  return out;
}

/** One chip per ask type, with every matched phrase (the extractor can match a type twice). */
export function groupAsks(asks: Ask[]): { type: string; meaning: string; texts: string[] }[] {
  const out = new Map<string, { type: string; meaning: string; texts: string[] }>();
  for (const a of asks) {
    const key = a.type || a.meaning || a.text;
    const g = out.get(key) ?? { type: a.type, meaning: a.meaning || a.text, texts: [] };
    if (a.text && !g.texts.includes(a.text)) g.texts.push(a.text);
    out.set(key, g);
  }
  return [...out.values()];
}
