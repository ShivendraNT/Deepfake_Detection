/**
 * Turns the analysis progress events (SSE /evidence/{id}/events) into a checklist.
 *
 * Stage ids are technique ids (image.ela, audio.voice …) or the pipeline stages below.
 * Names for technique stages come from GET /lab/api/techniques.
 */

import type { Category, MediaKind, ProgressEvent, TechniqueInfo } from "../api";
import { parseTime } from "./format";

export const PIPELINE_STAGES: Record<string, { label: string; detail: string }> = {
  intake: { label: "Evidence received & fingerprinted", detail: "MD5 / SHA-1 / SHA-256 of the raw upload" },
  queue: { label: "Queued for analysis", detail: "Waiting for a free analysis worker" },
  integrity: { label: "Integrity re-verified", detail: "Stored file re-hashed against the intake SHA-256" },
  features: { label: "Perceptual hashes & identity embeddings", detail: "For cross-exhibit comparison" },
  links: { label: "Cross-exhibit comparison", detail: "Near duplicates, shared content, same face / speaker" },
  verdict: { label: "Verdict from the rule table", detail: "Findings fused by a fixed, documented rule table" },
  done: { label: "Analysis complete", detail: "" },
};

export type TechIndex = Record<string, Pick<TechniqueInfo, "name" | "category" | "kinds">>;

export function indexTechniques(list: TechniqueInfo[] | null | undefined): TechIndex {
  const out: TechIndex = {};
  for (const t of list ?? []) out[t.id] = { name: t.name, category: t.category, kinds: t.kinds };
  return out;
}

/** Friendly label for any stage id. Unknown ids are humanised, never dropped. */
export function stageLabel(stage: string, techs?: TechIndex): string {
  const t = techs?.[stage];
  if (t) return t.name;
  const p = PIPELINE_STAGES[stage];
  if (p) return p.label;
  const s = stage.replace(/[._]+/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "Stage";
}

export function stageCategory(stage: string, techs?: TechIndex): Category | null {
  return techs?.[stage]?.category ?? null;
}

export type RowStatus = "pending" | "running" | "ok" | "skipped" | "unavailable" | "error";

export interface StageRow {
  stage: string;
  label: string;
  status: RowStatus;
  message: string;
  isTechnique: boolean;
  category: Category | null;
  startedAt: number | null;
  endedAt: number | null;
  durationMs: number | null;
  /** Sub-progress 0..1 parsed from messages such as "face model at 3s / 10s". */
  sub: number | null;
}

const TERMINAL: ReadonlySet<string> = new Set(["ok", "skipped", "unavailable", "error"]);

export function isTerminalRow(s: RowStatus): boolean {
  return TERMINAL.has(s);
}

/**
 * The events of the latest run only. A re-analysis appends a new "queue" stage to the same
 * event list; everything before the last "queue" belongs to an older run (keep its intake row).
 */
export function currentRun(events: ProgressEvent[]): ProgressEvent[] {
  let start = -1;
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i]?.stage === "queue") {
      start = i;
      break;
    }
  }
  if (start <= 0) return events;
  const intake = events.slice(0, start).filter((e) => e.stage === "intake");
  return [...intake.slice(-1), ...events.slice(start)];
}

function subProgress(message: string): number | null {
  const m = /(\d+(?:\.\d+)?)\s*s\s*\/\s*(\d+(?:\.\d+)?)\s*s/.exec(message);
  if (!m) return null;
  const a = Number(m[1]);
  const b = Number(m[2]);
  if (!Number.isFinite(a) || !Number.isFinite(b) || b <= 0) return null;
  return Math.max(0, Math.min(1, a / b));
}

/**
 * Build the checklist rows from events (in order) plus the techniques still expected for this
 * media kind (shown as pending until they start). Rows keep first-seen order.
 */
export function buildStageRows(
  events: ProgressEvent[],
  techs: TechIndex = {},
  expected: string[] = [],
): StageRow[] {
  const run = currentRun(events);
  const rows: StageRow[] = [];
  const byStage = new Map<string, StageRow>();
  let finished: "done" | "error" | null = null;

  const closeOpenPipelineRows = (except: string, at: number | null) => {
    for (const r of rows) {
      if (r.stage !== except && !r.isTechnique && r.status === "running") {
        r.status = "ok";
        r.endedAt = at;
        r.durationMs = r.startedAt !== null && at !== null ? Math.max(0, at - r.startedAt) : null;
      }
    }
  };

  for (const ev of run) {
    const at = parseTime(ev.at ?? null)?.getTime() ?? null;
    if (ev.stage === "done") {
      finished = ev.status === "error" ? "error" : "done";
      for (const r of rows) {
        if (r.status === "running") {
          r.status = finished === "error" && r.isTechnique ? "error" : "ok";
          r.endedAt = at;
          r.durationMs = r.startedAt !== null && at !== null ? Math.max(0, at - r.startedAt) : null;
          if (finished === "error" && ev.message) r.message = ev.message;
        }
      }
      continue;
    }
    let row = byStage.get(ev.stage);
    if (!row) {
      row = {
        stage: ev.stage,
        label: stageLabel(ev.stage, techs),
        status: "running",
        message: ev.message,
        isTechnique: ev.stage in techs,
        category: stageCategory(ev.stage, techs),
        startedAt: at,
        endedAt: null,
        durationMs: null,
        sub: null,
      };
      byStage.set(ev.stage, row);
      rows.push(row);
      closeOpenPipelineRows(ev.stage, at);
    }
    const st = String(ev.status);
    if (TERMINAL.has(st)) {
      row.status = st as RowStatus;
      row.message = ev.message;
      row.endedAt = at;
      row.durationMs = row.startedAt !== null && at !== null ? Math.max(0, at - row.startedAt) : null;
      row.sub = null;
    } else if (!TERMINAL.has(row.status)) {
      row.status = "running";
      // the first running message is just "<name>…"; later ones are live sub-progress
      if (ev.message && !ev.message.endsWith("…")) row.message = ev.message;
      else if (!row.message) row.message = ev.message;
      row.sub = subProgress(ev.message);
    }
  }

  if (!finished) {
    for (const id of expected) {
      if (byStage.has(id)) continue;
      rows.push({
        stage: id,
        label: stageLabel(id, techs),
        status: "pending",
        message: "",
        isTechnique: id in techs,
        category: stageCategory(id, techs),
        startedAt: null,
        endedAt: null,
        durationMs: null,
        sub: null,
      });
    }
  }
  return rows;
}

/** Overall progress 0..1, monotonic over the run (sub-progress events can step backwards). */
export function overallProgress(events: ProgressEvent[]): number {
  let p = 0;
  for (const e of currentRun(events)) {
    if (e.stage === "done") return 1;
    if (Number.isFinite(e.progress)) p = Math.max(p, e.progress);
  }
  return Math.max(0, Math.min(1, p));
}

/** The stage currently running (last non-terminal event), for compact card labels. */
export function activeStage(events: ProgressEvent[], techs: TechIndex = {}): { label: string; message: string } | null {
  const run = currentRun(events);
  const last = run[run.length - 1];
  if (!last) return null;
  if (last.stage === "done") return { label: PIPELINE_STAGES.done?.label ?? "Done", message: last.message };
  return { label: stageLabel(last.stage, techs), message: last.message };
}

/** Technique ids that apply to a media kind, in GET /techniques order. */
export function expectedTechniques(list: TechniqueInfo[] | null | undefined, kind: MediaKind): string[] {
  return (list ?? []).filter((t) => t.kinds.includes(kind)).map((t) => t.id);
}

export function isDone(events: ProgressEvent[]): boolean {
  return currentRun(events).some((e) => e.stage === "done");
}
