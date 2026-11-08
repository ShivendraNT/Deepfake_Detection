/** Pure formatting helpers. Times are always shown in IST (Asia/Kolkata). */

const IST_PARTS = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

/** Parse a backend timestamp. Naive timestamps are UTC; >3 fractional digits are trimmed. */
export function parseTime(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  let s = iso.trim();
  s = s.replace(/(\.\d{3})\d+/, "$1");
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(s)) s += "Z";
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

function istParts(d: Date): Record<string, string> {
  const out: Record<string, string> = {};
  for (const p of IST_PARTS.formatToParts(d)) out[p.type] = p.value;
  return out;
}

/** DD/MM/YYYY HH:mm:ss in IST, or an em dash. */
export function formatIST(iso: string | null | undefined): string {
  const d = parseTime(iso);
  if (!d) return "—";
  const p = istParts(d);
  return `${p.day}/${p.month}/${p.year} ${p.hour}:${p.minute}:${p.second}`;
}

/** DD/MM/YYYY in IST. */
export function formatISTDate(iso: string | null | undefined): string {
  const d = parseTime(iso);
  if (!d) return "—";
  const p = istParts(d);
  return `${p.day}/${p.month}/${p.year}`;
}

/** HH:mm:ss in IST. */
export function formatISTTime(iso: string | null | undefined): string {
  const d = parseTime(iso);
  if (!d) return "—";
  const p = istParts(d);
  return `${p.hour}:${p.minute}:${p.second}`;
}

export function formatBytes(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n) || n < 0) return "—";
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2)} ${units[i]}`;
}

/** Media time: 0:07, 1:05, 1:02:03 (also used for chart axes). */
export function formatClock(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) {
    return "—";
  }
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

/** Seconds with one decimal: "9.96 s" → "10.0 s". */
export function formatSeconds(seconds: number | null | undefined, digits = 1): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "—";
  return `${seconds.toFixed(digits)} s`;
}

/** Technique run time: "0.1 ms", "85 ms", "4.31 s", "2 min 05 s". */
export function formatDurationMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1) return `${ms.toFixed(1)} ms`;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(s < 10 ? 2 : 1)} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${String(Math.round(s % 60)).padStart(2, "0")} s`;
}

/** 36eb38b4…b0b4e6 */
export function shortHash(hash: string | null | undefined, head = 8, tail = 6): string {
  if (!hash) return "—";
  if (hash.length <= head + tail + 1) return hash;
  return `${hash.slice(0, head)}…${hash.slice(-tail)}`;
}

export function formatPercent(p: number | null | undefined, digits = 0): string {
  if (p === null || p === undefined || !Number.isFinite(p)) return "—";
  return `${(p * 100).toFixed(digits)}%`;
}

export function formatNumber(v: unknown, digits = 3): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return String(v ?? "—");
  if (Number.isInteger(v)) return v.toLocaleString("en-IN");
  return Number(v.toFixed(digits)).toString();
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** "image.ela" → "Image Ela"; "same_face" → "Same face". */
export function humanize(id: string): string {
  const s = id.replace(/[._]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Human value for an arbitrary JSON scalar / small object in tables. */
export function displayValue(v: unknown, maxLen = 160): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return formatNumber(v, 4);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "string") return v.length > maxLen ? `${v.slice(0, maxLen)}…` : v;
  try {
    const s = JSON.stringify(v);
    return s.length > maxLen ? `${s.slice(0, maxLen)}…` : s;
  } catch {
    return String(v);
  }
}

export function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}
