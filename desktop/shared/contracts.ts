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
  // Finale additions (F01): the four windows and the live/OOB/report fan-in.
  | 'call.started'
  | 'call.stopped'
  | 'live.chips'
  | 'coverage.changed'
  | 'oob.sent'
  | 'oob.result'
  | 'case.updated'
  | 'report.ready'

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
  // Finale additions (F01). Every field is optional so old events stay valid.
  case_id?: string
  call_id?: string
  chips?: AskChip[]
  coverage?: Coverage
  seal?: SealStatus
  oob?: OobSummary
  ticket?: OobTicket
  report?: ReportPackV2
  user_mode?: UserMode
  pose?: Pose
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
  /** LAN URL of the approver page, shown as a QR code in Settings (F16). */
  oob_url?: string
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
  openWorkspace(tab?: string): Promise<void>
  hideCompanion(): Promise<BridgeResult<null>>
  quit(): Promise<BridgeResult<null>>
  onEvent(callback: (event: CompanionEvent) => void): () => void
  onConnection(callback: (status: ConnectionStatus) => void): () => void
  onTrayRequest(callback: (request: TrayRequest) => void): () => void
  onHotkey(callback: (action: string) => void): () => void

  // ---- Finale window IPC (F01/F02). Window geometry lives in main, never in the UI. ----
  /** Mascot: make the transparent window click-through (true) or clickable (false). */
  setClickThrough(through: boolean): void
  /** Mascot: move the window while dragging. */
  dragBy(dx: number, dy: number): void
  /** Mascot: finish the drag (snap to an edge, remember the position). */
  dragEnd(): void
  /** Mascot: cursor position at 30 Hz relative to Satya's centre. Stops when hidden. */
  onCursor(callback: (position: { dx: number; dy: number; near: boolean }) => void): () => void
  /** Mascot: ask main to show exactly one card in the bubble window. */
  showCard(card: BubbleCard): void
  /** Mascot: hide the bubble card (optionally only when it is still `cardId`). */
  hideCard(cardId?: string): void
  /** Mascot: a button in the bubble was clicked. */
  onCardAction(callback: (action: { card_id: string; action_id: string }) => void): () => void
  /** Aliases used by the bubble/stage views. */
  showBubble(card: BubbleCard): void
  hideBubble(): void
  /** Bubble: receives the one card and which side of it points at Satya. */
  onCard(callback: (card: BubbleCard | null, tail: 'left' | 'right') => void): () => void
  /** Bubble: send a button click back to main (and on to the mascot). */
  cardAction(cardId: string, actionId: string): void
  /** Bubble: content height changed; main re-places the window. */
  resizeBubble(height: number): void
  setUserMode(mode: UserMode): Promise<BridgeResult<CompanionState>>
  getPrefs(): Promise<Prefs>
  setPrefs(patch: Partial<Prefs>): Promise<Prefs>
  /** Main allow-lists `tel:1930`, `mailto:` and `https://cybercrime.gov.in`. */
  openExternal(url: string): Promise<void>
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

// ---------------------------------------------------------------------------------------------
// Finale additions (F01) — frozen at hour 2. Mirrors `src/satyapan/api/companion/models.py`.
// No score, confidence or probability field may ever appear here (oracle-abuse mitigation).
// ---------------------------------------------------------------------------------------------

/** What the user asked for. Distinct from `CompanionMode`, which is what Satya is doing. */
export type UserMode = 'WATCHING' | 'SLEEPING' | 'OFF'

/** The ten mascot poses from docs/finale/MASCOT_SPEC.md §4. */
export type Pose =
  | 'sleep'
  | 'idle'
  | 'listen'
  | 'think'
  | 'alert'
  | 'relief'
  | 'write'
  | 'catch'
  | 'wave'
  | 'off'

export type Lang = 'en' | 'hinglish' | 'hi'

/** Audio quality gate. Degraded audio means Satya abstains from any acoustic conclusion. */
export type Coverage = 'usable' | 'degraded' | 'incomplete'

/** A missing Seal means "not verified by Seal", never "fake". */
export type SealStatus = 'verified' | 'not_verified' | 'unavailable'

export type CaptureSourceKind = 'extension' | 'loopback' | 'replay'

export type AskCode = 'A1' | 'A2' | 'A3' | 'A4' | 'A5' | 'A6' | 'A7'

/** An ask chip observed in a call or message. `at_s` is seconds into the call, if known. */
export interface AskChip {
  code: AskCode
  at_s: number | null
}

export interface CardAction {
  id: string
  variant: 'primary' | 'outline' | 'ghost'
}

/** Exactly one card is visible at a time. Text comes from copy.ts by key/code. */
export type BubbleCard =
  | { kind: 'consent'; id: string; scopes: string[]; actions: CardAction[] }
  | { kind: 'call_ask'; id: string; source: CaptureSourceKind; actions: CardAction[] }
  | {
      kind: 'file_ask'
      id: string
      file_name: string
      file_kind: 'email' | 'pdf' | 'audio' | 'text' | 'image'
      actions: CardAction[]
    }
  | {
      kind: 'live'
      id: string
      chips: AskChip[]
      coverage: Coverage
      seal: SealStatus
      elapsed_s: number
    }
  | { kind: 'result'; id: string; band: Band; headline: string; reasons: string[]; actions: CardAction[] }
  | {
      kind: 'alert'
      id: string
      band: Band
      headline: string
      reasons: string[]
      chips: AskChip[]
      actions: CardAction[]
    }
  | { kind: 'oob_wait'; id: string; approver_name: string; sent_at: string; actions: CardAction[] }
  | {
      kind: 'oob_result'
      id: string
      approver_name: string
      outcome: 'approved' | 'rejected' | 'not_requested' | 'expired'
      actions: CardAction[]
    }
  | {
      kind: 'scribe'
      id: string
      actions: CardAction[]
      sections: Array<{ id: string; title: string; status: 'pending' | 'writing' | 'done' }>
    }
  | { kind: 'toast'; id: string; text_key: string; tone: 'neutral' | 'good' | 'warn' }

export interface OobTicket {
  oob_id: string
  case_id: string
  approver_name: string
  channel: 'console' | 'email'
  inbox_url: string
  expires_at: string
}

export type OobOutcome = 'approved' | 'rejected' | 'not_requested' | 'expired'

export interface OobSummary {
  oob_id: string
  approver_name: string
  outcome?: OobOutcome
}

export interface ReportField {
  label: string
  value: string
  source: 'maker_entered' | 'vault' | 'vendor_master' | 'user_confirmed' | 'system'
  evidence_id: string | null
  copy: boolean
  sensitive: boolean
}

export interface ReportSection {
  id: 'helpline_1930' | 'bank_fraud_desk' | 'ncrp_portal' | 'cert_in' | 'bsa_s63_part_a'
  title: string
  destination: string
  deadline_hint: string | null
  body: string
  fields: ReportField[]
  open_url: string | null
  applies: boolean
  status: 'DRAFT_REQUIRES_HUMAN_REVIEW'
}

/** A human always presses Submit. No code path files anything. */
export interface ReportPackV2 {
  version: '2'
  case_id: string
  generated_at: string
  money_left_at: string | null
  sections: ReportSection[]
  submission: 'MANUAL_ONLY'
  auto_submit: false
}

/** Local preferences only. Never leaves the laptop. */
export interface Prefs {
  position?: { x: number; y: number }
  size?: 'S' | 'M' | 'L'
  sound?: boolean
  sounds?: boolean
  lang?: Lang
  notice_calls?: boolean
  source?: CaptureSourceKind
}

export interface CustodyRow {
  evidence_id: string
  at: string
  actor: string
  action: string
  sha256_short: string
}

export const ASK_LABELS: Record<AskCode, string> = {
  A1: 'New account',
  A2: 'OTP / PIN',
  A3: 'Screen sharing',
  A4: 'Keep it secret',
  A5: 'Skip approval',
  A6: 'Gift card / crypto / UPI collect',
  A7: 'Change bank details',
}

export const USER_MODE_LABELS: Record<UserMode, string> = {
  WATCHING: 'Watching',
  SLEEPING: 'Sleeping',
  OFF: 'Off',
}
