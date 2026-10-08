// PRE-IMPLEMENTED. Hand-written mirror of the Pydantic contracts (src/satyapan/contracts).
// Source of truth = Python. If a contract changes, update this file too:
// tests/harness/test_docs_consistency.py checks that every contract field name appears here.

export type Band = "PASS" | "VERIFY" | "HOLD";
export type Role = "maker" | "checker" | "security" | "requester" | "system";
export type CaseStatus = "OPEN" | "CLEARED" | "SUSPECTED_FRAUD" | "CONFIRMED_FRAUD" | "OVERRIDDEN";
export type ActionType = "K1" | "K2" | "N1" | "N2" | "C1" | "T1" | "D1" | "NONE";

export interface PaymentAction {
  id: string;
  vendor_id: string | null;
  beneficiary_name: string;
  account_number: string | null;
  ifsc: string | null;
  upi_id: string | null;
  beneficiary_bank: string | null;
  amount_inr: number;
  rail: "NEFT" | "RTGS" | "IMPS" | "UPI";
  debit_account_masked: string;
  requested_by_employee_id: string | null;
  bank_shown_payee_name: string | null;
  created_by: string;
  created_at: string;
  utr: string | null;
  sent_at: string | null;
}

export interface Signal {
  id: string;
  code: string;
  group: string;
  target: string;
  strength: "weak" | "strong";
  source: "deterministic" | "ml" | "llm" | "human";
  evidence_ids: string[];
  detector: string;
  score: number | null; // null for makers (server strips it)
  detail: Record<string, string | number | boolean | null>;
}

export interface Evidence {
  id: string;
  case_id: string;
  channel: string;
  filename: string | null;
  media_type: string;
  sha256: string;
  size_bytes: number;
  captured_at: string;
  submitted_by: string;
  storage_uri: string;
  excerpt: string | null;
  analysis_runs: { detector: string; version: string; at: string }[];
}

export interface ClearanceRequirement {
  band: Band;
  who: Role[];
  methods: string[];
  mode: "any" | "all" | "none";
  callback_number: string | null;
  callback_number_source: string | null;
  notes: string[];
}

export interface Decision {
  band: Band;
  floor_band: Band;
  action_type: ActionType;
  reason_codes: string[];
  info_codes: string[];
  clearance: ClearanceRequirement;
  queue: "MAKER" | "CHECKER_REVIEW";
  suggested_status: CaseStatus | null;
  grey: boolean;
  policy_version: string;
  decided_at: string;
}

export interface Case {
  id: string;
  title: string;
  kind: "PAYMENT" | "MASTER_CHANGE" | "DATA_REQUEST" | "LIVE_CALL";
  created_at: string;
  created_by: string;
  txn: PaymentAction | null;
  master_change: Record<string, string | null> | null;
  evidence: Evidence[];
  signals: Signal[];
  grey_reasons: string[];
  oob: Record<string, unknown> | null;
  callbacks: Record<string, unknown>[];
  linked_call_ids: string[];
  status: CaseStatus;
  queue: "MAKER" | "CHECKER_REVIEW";
  decision: Decision | null;
  override: Record<string, unknown> | null;
  security_acknowledged_by: string | null;
  notes: string[];
}

// GET /cases returns these
export interface CaseSummary {
  id: string;
  title: string;
  kind: string;
  status: CaseStatus;
  queue: string;
  band: Band | null;
  action_type: ActionType | null;
  amount_inr: number | null;
  beneficiary_name: string | null;
  reason_codes: string[];
  created_at: string;
}

export interface DemoUser {
  employeeId: string;
  role: Role;
}

// ---- Satyapan Seal (src/satyapan/contracts/seal.py, docs/SEAL.md) ----
export type SignalGroup =
  | "sender_auth" | "document" | "media" | "ask" | "style" | "watchlist" | "provenance";
// Provenance reason codes: VOICE_SEALED is info only (never lowers a band, never clears).
export type SealReasonCode =
  | "VOICE_SEALED" | "VOICE_UNSEALED_CLAIMED_EXEC" | "SEAL_PRESENCE_CONFLICT";
export type SealSessionKind = "meeting" | "voice_note";
export type SealEpochStatus = "sealed" | "weak" | "unsealed" | "no_speech";

export interface SealSession {
  id: string;
  employee_id: string;
  kind: SealSessionKind;
  binding: string;
  commitment: string;
  t0: string;
  epoch_s: number;
  n_epochs: number;
  params_id: string;
  started_at: string;
  last_disclosed_epoch: number | null;
  last_disclosed_at: string | null;
}

export interface SealKey {
  epoch: number;
  key: string;
}

export interface SealMeetingView {
  session: SealSession;
  keys: SealKey[];
}

export interface SealEpoch {
  epoch: number;
  start_s: number;
  cells: number;
  status: SealEpochStatus;
  z: number | null; // null for makers (server strips it)
}

export interface SealGap {
  first_epoch: number;
  last_epoch: number;
  start_s: number;
  end_s: number;
}

export interface SealVerification {
  session_id: string | null;
  employee_id: string | null;
  binding: string | null;
  sealed: boolean;
  decided_by: string;
  decided_at_epoch: number | null;
  offset_s: number | null;
  first_epoch: number;
  acquisition_threshold: number;
  acquisition_statistic: number | null; // null for makers
  stouffer_z: number | null; // null for makers
  epochs: SealEpoch[];
  n_epochs_speech: number;
  n_epochs_sealed: number;
  gaps: SealGap[];
  speech_seconds: number;
  audio_seconds: number;
  params_id: string;
  verifier_version: string;
  timing_provable: boolean;
  notes: string[];
}

export interface IntentBeneficiary {
  account_sha256: string;
  account_masked: string;
  ifsc: string | null;
}

export interface PaymentIntent {
  v: number;
  case_id: string;
  requester: string;
  action: string;
  amount_inr: number;
  beneficiary: IntentBeneficiary;
  nonce: string;
  expires_at: number;
}
