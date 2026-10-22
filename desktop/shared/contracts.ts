/**
 * Shared companion contracts (T25).
 *
 * These mirror the FastAPI envelopes in `src/satyapan/api/companion/models.py`. They contain no
 * score fields by design: the UI only receives bands, reason codes and evidence references.
 */

export type CompanionMode =
  | 'SLEEP'
  | 'ACTIVE'
  | 'INVESTIGATING'
  | 'ALERT'
  | 'SCRIBE'
  | 'DISABLED'

export type MascotMood =
  | 'sleepy'
  | 'attentive'
  | 'focused'
  | 'calm_alert'
  | 'writing'
  | 'off'

export type Band = 'PASS' | 'VERIFY' | 'HOLD'

export type CompanionSource =
  | 'demo_replay'
  | 'user_selected_email'
  | 'user_selected_loopback'
  | 'user_selected_microphone'

export type CompanionEventType =
  | 'state.changed'
  | 'analysis.started'
  | 'analysis.completed'
  | 'evidence.received'
  | 'alert.raised'
  | 'draft.ready'
  | 'session.started'
  | 'session.stopped'
  | 'error'

export interface NextAction {
  id: string
  label: string
  variant: 'primary' | 'outline' | 'ghost'
}

export interface CompanionPayload {
  state: CompanionMode
  mascot_mood: MascotMood
  headline: string
  explanation: string
  band: Band | null
  reason_codes: string[]
  info_codes: string[]
  evidence_ids: string[]
  next_actions: NextAction[]
  monitoring: boolean
  source: CompanionSource | null
  mode_label: string | null
  demo: boolean
}

export interface CompanionEvent {
  version: '1'
  event_id: string
  type: CompanionEventType
  session_id: string | null
  occurred_at: string
  payload: CompanionPayload
}

export interface CompanionState {
  version: '1'
  mode: CompanionMode
  hidden: boolean
  monitoring: boolean
  session_id: string | null
  consent_id: string | null
  source: CompanionSource | null
  source_label: string | null
  started_at: string | null
  updated_at: string
  expires_at: string | null
  demo: boolean
  mode_label: string | null
  last_event_id: string | null
  policy_authority: 'satyapan.policy'
  raw_scores_visible: false
  manual_only: true
}

export interface DraftArtifact {
  version: '1'
  draft_id: string
  kind: 'section63' | 'helpline_1930'
  case_id: string
  status: 'DRAFT_REQUIRES_HUMAN_REVIEW'
  submission: 'MANUAL_ONLY'
  auto_submit: false
  generated_at: string
  fields: Record<string, string | number | boolean | null>
  disclaimers: string[]
}

export interface EvidenceRef {
  evidence_id: string
  channel: string
  filename: string | null
  size_bytes: number
  sha256_short: string
  excerpt: string | null
}

export interface AuditRow {
  at: string
  actor: string
  action: string
  detail: string
}

export interface WorkspaceSnapshot {
  version: '1'
  case_id: string
  title: string
  kind: string
  status: string
  band: Band
  floor_band: Band
  action_type: string
  queue: string
  reason_codes: string[]
  info_codes: string[]
  explanation: string
  payee_masked: string | null
  amount_inr: number | null
  evidence: EvidenceRef[]
  drafts: DraftArtifact[]
  audit: AuditRow[]
  policy_authority: 'satyapan.policy'
  raw_scores_visible: false
  manual_only: true
}

export interface CaseSummary {
  case_id: string
  title: string
  status: string
  band: Band
  queue: string
  updated_at: string
}

export interface AppConfig {
  backendUrl: string
  demoUser: string
  demoRole: string
  platform: string
  version: string
}

export interface ClipboardCheck {
  suspicious: boolean
  matches: string[]
  preview: string
  note: string
}

export type BridgeResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string }

export interface SessionResult {
  state: CompanionState
  events: CompanionEvent[]
}

export interface CommandResult {
  request_id: string
  accepted: boolean
  state: CompanionState
  events: CompanionEvent[]
}

export interface EvidenceResult {
  request_id: string
  accepted: boolean
  evidence_id: string
  reason_codes: string[]
  info_codes: string[]
  ask_count: number
  band_set_by_companion: false
  events: CompanionEvent[]
}

export type TrayRequest =
  | { kind: 'start'; source: CompanionSource }
  | { kind: 'demo'; scenario: string }
  | { kind: 'clipboard'; check: ClipboardCheck }

export interface CompanionApiClient {
  connect(handlers: CompanionHandlers): Promise<void>
  disconnect(): void
  getState(): Promise<CompanionState>
  startSession(source: CompanionSource, label?: string): Promise<SessionResult>
  stopSession(): Promise<SessionResult>
  command(type: string, payload?: Record<string, unknown>): Promise<CommandResult>
  draft(kind: 'section63' | 'helpline_1930', caseId: string): Promise<DraftArtifact>
  workspace(caseId?: string): Promise<WorkspaceSnapshot>
  listCases(): Promise<CaseSummary[]>
  submitEvidence?(text: string): Promise<EvidenceResult>
  copyText?(text: string): Promise<void>
  openWorkspace?(): Promise<void>
  hide?(): Promise<void>
  checkClipboard?(): Promise<ClipboardCheck>
}

export interface CompanionHandlers {
  onEvent: (event: CompanionEvent) => void
  onConnection: (status: ConnectionStatus) => void
  onTrayRequest: (request: TrayRequest) => void
  onHotkey: (action: string) => void
}

export interface ConnectionStatus {
  connected: boolean
  backendUrl: string
  mock: boolean
  error?: string
}

/** The narrow surface exposed by `preload/index.ts` as `window.satyapan`. */
export interface CompanionBridge {
  getConfig(): Promise<AppConfig>
  getState(): Promise<BridgeResult<CompanionState>>
  startSession(source: CompanionSource, label?: string): Promise<BridgeResult<SessionResult>>
  stopSession(): Promise<BridgeResult<SessionResult>>
  command(type: string, payload?: Record<string, unknown>): Promise<BridgeResult<CommandResult>>
  submitEvidence(text: string, evidenceId?: string): Promise<BridgeResult<EvidenceResult>>
  draft(kind: 'section63' | 'helpline_1930', caseId: string): Promise<BridgeResult<DraftArtifact>>
  workspace(caseId?: string): Promise<BridgeResult<WorkspaceSnapshot>>
  listCases(): Promise<BridgeResult<CaseSummary[]>>
  checkClipboard(): Promise<BridgeResult<ClipboardCheck>>
  copyText(text: string): Promise<BridgeResult<null>>
  openWorkspace(): Promise<void>
  hideCompanion(): Promise<BridgeResult<null>>
  quit(): Promise<BridgeResult<null>>
  onEvent(callback: (event: CompanionEvent) => void): () => void
  onConnection(callback: (status: ConnectionStatus) => void): () => void
  onTrayRequest(callback: (request: TrayRequest) => void): () => void
  onHotkey(callback: (action: string) => void): () => void
}

export const DEMO_REPLAY_LABEL = 'DEMO REPLAY — NOT LIVE CAPTURE'

export const SOURCE_LABELS: Record<CompanionSource, string> = {
  demo_replay: 'Demo replay',
  user_selected_email: 'Selected email / text',
  user_selected_loopback: 'Meet or Teams tab (loopback)',
  user_selected_microphone: 'Microphone',
}

export const MODE_LABELS: Record<CompanionMode, string> = {
  SLEEP: 'Sleep / DND',
  ACTIVE: 'Watching',
  INVESTIGATING: 'Investigating',
  ALERT: 'Needs verification',
  SCRIBE: 'Drafting',
  DISABLED: 'Disabled',
}
