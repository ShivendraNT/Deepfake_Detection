/**
 * Typed client for the Satyapan Forensic Lab API (/lab/api/...).
 *
 * The types mirror src/satyapan/forensics/models.py and src/satyapan/api/routes_lab.py.
 * Everything the dashboard shows comes from these endpoints; nothing is invented client-side.
 */

export const API_BASE = "/lab/api";

// ------------------------------------------------------------------ enums (models.py)

export type MediaKind = "image" | "audio" | "video" | "document" | "other";
export type Category =
  | "integrity"
  | "metadata"
  | "provenance"
  | "tampering"
  | "synthetic"
  | "content";
export type Hypothesis = "synthetic" | "manipulated" | "authentic" | "neutral";
/** ENFSI-style ordinal: 0 none, 1 weak, 2 moderate, 3 strong, 4 very strong. */
export type Strength = 0 | 1 | 2 | 3 | 4;
export type TechniqueStatus = "ok" | "skipped" | "unavailable" | "error";
export type VerdictLabel =
  | "SYNTHETIC"
  | "MANIPULATED"
  | "SUSPICIOUS"
  | "NO_INDICATORS"
  | "INCONCLUSIVE";
export type EvidenceRole = "questioned" | "reference";
export type EvidenceStatus = "queued" | "analyzing" | "done" | "error";
export type LinkKind =
  | "near_duplicate"
  | "shares_content"
  | "same_device"
  | "same_speaker"
  | "same_face"
  | "same_generator";
export type ProgressStatus = "running" | "ok" | "skipped" | "unavailable" | "error" | "done";

// ------------------------------------------------------------------ analysis shapes

export interface Region {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  score: number | null;
}

export interface TimeSpan {
  start_s: number;
  end_s: number;
  label: string;
  score: number | null;
}

export interface Artifact {
  name: string;
  kind: string; // heatmap | overlay | chart | spectrogram | thumbnail | figure | crop
  title: string;
  caption: string;
  media_type: string;
}

export interface Finding {
  code: string;
  title: string;
  detail: string;
  hypothesis: Hypothesis;
  strength: number;
  category: Category;
  technique: string;
  score: number | null;
  regions: Region[];
  spans: TimeSpan[];
  artifacts: string[];
  observations: Record<string, unknown>;
}

export interface TechniqueResult {
  id: string;
  name: string;
  category: Category;
  status: TechniqueStatus;
  summary: string;
  method: string;
  reference: string | null;
  version: string;
  duration_ms: number;
  findings: Finding[];
  artifacts: Artifact[];
  data: Record<string, unknown>;
  error: string | null;
  limitations: string | null;
}

export interface Hashes {
  md5: string;
  sha1: string;
  sha256: string;
  size_bytes: number;
}

export interface MediaInfo {
  kind: MediaKind;
  mime: string;
  format: string;
  extension: string;
  extension_mismatch: boolean;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  fps: number | null;
  sample_rate: number | null;
  channels: number | null;
  codec: string | null;
  audio_codec: string | null;
  frames: number | null;
  has_audio: boolean | null;
  bit_depth: number | null;
  color_mode: string | null;
}

export interface Provenance {
  device: string | null;
  software: string | null;
  platform: string | null;
  generator: string | null;
  capture_time: string | null;
  gps: Record<string, number> | null;
  content_credentials: string | null;
  chain: string[];
}

export interface Verdict {
  label: VerdictLabel;
  headline: string;
  statement: string;
  confidence: string;
  risk_index: number;
  hypotheses: Record<string, number>;
  key_findings: string[];
  rationale: string[];
  not_checked: string[];
}

export interface EvidenceAnalysis {
  evidence_id: string;
  case_id: string;
  engine_version: string;
  started_at: string;
  finished_at: string | null;
  media: MediaInfo;
  hashes: Hashes;
  integrity_verified: boolean;
  techniques: TechniqueResult[];
  verdict: Verdict | null;
  provenance: Provenance;
  perceptual: Record<string, string>;
}

// ------------------------------------------------------------------ case / evidence shapes

export interface LabEvidence {
  id: string;
  case_id: string;
  exhibit: string;
  filename: string;
  size_bytes: number;
  md5: string;
  sha1: string;
  sha256: string;
  kind: MediaKind;
  mime: string;
  role: EvidenceRole;
  description: string;
  received_from: string;
  received_at: string;
  status: EvidenceStatus;
  verdict: VerdictLabel | null;
  risk_index: number | null;
  headline: string | null;
}

export interface UploadResult extends LabEvidence {
  duplicate: boolean;
}

export interface LabCase {
  id: string;
  title: string;
  fir_number: string;
  police_station: string;
  district: string;
  state: string;
  offence_sections: string;
  investigating_officer: string;
  examiner: string;
  lab_name: string;
  summary: string;
  created_at: string;
  status: string;
  demo: boolean;
}

export interface CaseSummary extends LabCase {
  evidence_count: number;
  flagged: number;
  pending: number;
}

export interface CaseIn {
  title: string;
  fir_number: string;
  police_station: string;
  district: string;
  state: string;
  offence_sections: string;
  investigating_officer: string;
  examiner: string;
  lab_name: string;
  summary: string;
}

export interface EvidenceLink {
  source: string;
  target: string;
  kind: LinkKind;
  score: number;
  detail: string;
  artifacts: string[];
}

export interface ProgressEvent {
  evidence_id: string;
  stage: string; // technique id or intake / queue / integrity / features / links / done
  message: string;
  progress: number; // 0..1
  at?: string;
  status: ProgressStatus | string;
}

export interface ReportRecord {
  id: string;
  case_id: string;
  created_at: string;
  examiner: string;
  designation: string;
  sha256: string;
  size_bytes: number;
  exhibits: string[];
  url: string;
}

export interface CaseFindings {
  counts: Record<string, number>;
  /** Plain-language case findings written by the backend (one sentence each). */
  sentences: string[];
}

export interface CaseView {
  case: LabCase;
  evidence: LabEvidence[];
  links: EvidenceLink[];
  counts: Record<string, number>;
  reports: ReportRecord[];
  findings?: CaseFindings | null;
}

export interface EvidenceView {
  evidence: LabEvidence;
  analysis: EvidenceAnalysis | null;
  links: EvidenceLink[];
  events: ProgressEvent[];
}

export interface CustodyRow {
  seq: number;
  case_id: string;
  evidence_id: string | null;
  event: string;
  actor: string;
  at: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  row_hash: string;
}

export interface ChainStatus {
  ok: boolean;
  rows_checked: number;
  broken_at_seq: number | null;
  reason: string | null;
}

export interface CustodyView {
  rows: CustodyRow[];
  chain: ChainStatus;
  head: string;
}

export interface HealthModel {
  available: boolean;
  purpose: string;
  model?: string;
  detail?: string;
}

export interface Health {
  status: string;
  engine: string;
  models: Record<string, HealthModel>;
  lab_dir: string;
  techniques: number;
}

export interface TechniqueInfo {
  id: string;
  name: string;
  category: Category;
  kinds: MediaKind[];
  method: string;
  reference: string | null;
  limitations: string | null;
}

export interface ReportIn {
  evidence_ids: string[];
  examiner: string;
  designation: string;
  notes: string;
}

// ------------------------------------------------------------------ transport

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`HTTP ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function errorDetail(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((d: unknown) =>
          typeof d === "object" && d !== null && "msg" in d ? String((d as { msg: unknown }).msg) : String(d),
        )
        .join("; ");
    }
  } catch {
    /* not JSON */
  }
  return text.slice(0, 300) || res.statusText;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new ApiError(res.status, await errorDetail(res));
  return (await res.json()) as T;
}

function jsonBody(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// ------------------------------------------------------------------ URLs (for <img>, <audio>, links)

export const urls = {
  file: (evidenceId: string) => `${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/file`,
  artifact: (evidenceId: string, name: string) =>
    `${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/artifacts/${encodeURIComponent(name)}`,
  events: (evidenceId: string) => `${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/events`,
  reportPdf: (reportId: string) => `${API_BASE}/reports/${encodeURIComponent(reportId)}.pdf`,
  exportJson: (caseId: string) => `${API_BASE}/cases/${encodeURIComponent(caseId)}/export.json`,
};

// ------------------------------------------------------------------ endpoints

export const api = {
  health: () => request<Health>("/health"),
  techniques: () => request<TechniqueInfo[]>("/techniques"),
  cases: () => request<CaseSummary[]>("/cases"),
  createCase: (body: CaseIn) => request<LabCase>("/cases", jsonBody(body)),
  caseView: (caseId: string) => request<CaseView>(`/cases/${encodeURIComponent(caseId)}`),
  evidence: (evidenceId: string) =>
    request<EvidenceView>(`/evidence/${encodeURIComponent(evidenceId)}`),
  reanalyze: (evidenceId: string) =>
    request<{ status: string }>(`/evidence/${encodeURIComponent(evidenceId)}/reanalyze`, {
      method: "POST",
    }),
  custody: (caseId: string) => request<CustodyView>(`/cases/${encodeURIComponent(caseId)}/custody`),
  makeReport: (caseId: string, body: ReportIn) =>
    request<ReportRecord>(`/cases/${encodeURIComponent(caseId)}/reports`, jsonBody(body)),
  loadDemo: () => request<Record<string, unknown>>("/demo", { method: "POST" }),
  upload: (
    caseId: string,
    files: File[],
    meta: { role: EvidenceRole; description: string; received_from: string },
  ) => {
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    form.append("role", meta.role);
    form.append("description", meta.description);
    form.append("received_from", meta.received_from);
    return request<UploadResult[]>(`/cases/${encodeURIComponent(caseId)}/evidence`, {
      method: "POST",
      body: form,
    });
  },
};

/**
 * Multipart upload with progress (XMLHttpRequest: fetch has no upload progress events).
 * Resolves with the server's evidence records (hashes are computed server-side, before parsing).
 */
export function uploadEvidence(
  caseId: string,
  files: File[],
  meta: { role: EvidenceRole; description: string; received_from: string },
  onProgress?: (fraction: number) => void,
): Promise<UploadResult[]> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    form.append("role", meta.role);
    form.append("description", meta.description);
    form.append("received_from", meta.received_from);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/cases/${encodeURIComponent(caseId)}/evidence`);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / Math.max(1, e.total));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as UploadResult[]);
        } catch (e) {
          reject(new ApiError(xhr.status, `bad response: ${String(e)}`));
        }
        return;
      }
      let detail = xhr.statusText || "upload failed";
      try {
        const body = JSON.parse(xhr.responseText) as { detail?: unknown };
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        if (xhr.responseText) detail = xhr.responseText.slice(0, 300);
      }
      reject(new ApiError(xhr.status, detail));
    };
    xhr.onerror = () => reject(new ApiError(0, "network error: the lab workstation did not answer"));
    xhr.send(form);
  });
}

/** The id of the case a POST /demo returned, whatever its exact shape. */
export function demoCaseId(body: Record<string, unknown>): string | null {
  if (typeof body.id === "string") return body.id;
  const c = body.case;
  if (typeof c === "object" && c !== null && typeof (c as { id?: unknown }).id === "string") {
    return (c as { id: string }).id;
  }
  if (typeof body.case_id === "string") return body.case_id;
  return null;
}
