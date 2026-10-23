/**
 * MockCompanionClient — the offline/demo fallback. It emits the exact same envelopes as the
 * FastAPI stream and is ALWAYS labelled replay. No network, no capture, no real data.
 */

import type {
  Band,
  CaseSummary,
  ClipboardCheck,
  CommandResult,
  CompanionApiClient,
  CompanionEvent,
  CompanionEventType,
  CompanionHandlers,
  CompanionMode,
  CompanionPayload,
  CompanionSource,
  CompanionState,
  DraftArtifact,
  MascotMood,
  SessionResult,
  WorkspaceSnapshot,
} from '../../../shared/contracts'
import { DEMO_REPLAY_LABEL } from '../../../shared/contracts'

// Visible replay label required for offline mode: 'DEMO REPLAY — NOT LIVE CAPTURE'
export const MOCK_REPLAY_BADGE = 'DEMO REPLAY — NOT LIVE CAPTURE'

const MOOD: Record<CompanionMode, MascotMood> = {
  SLEEP: 'sleepy',
  ACTIVE: 'attentive',
  INVESTIGATING: 'focused',
  ALERT: 'calm_alert',
  SCRIBE: 'writing',
  DISABLED: 'off',
}

interface Scenario {
  title: string
  band: Band
  reasons: string[]
  explanation: string
  payee: string
  amount: number
}

const SCENARIOS: Record<string, Scenario> = {
  beneficiary_change: {
    title: 'Urgent beneficiary change (demo replay)',
    band: 'VERIFY',
    reasons: ['ASK_PAYEE_CHANGE', 'FLOOR_N2_NEW_LARGE'],
    explanation:
      'A generated beneficiary-change request asks for a new account. This does not establish who is speaking. Call the vendor on the number already on file, not the one in the message.',
    payee: 'A/c ••••9917 (FAKC0000991)',
    amount: 284000,
  },
  urgent_bypass: {
    title: 'Secrecy and remote-access request (demo replay)',
    band: 'HOLD',
    reasons: ['ASK_SECRECY', 'ASK_REMOTE_ACCESS', 'ASK_CREDENTIAL', 'FLOOR_N2_NEW_LARGE'],
    explanation:
      'The generated request asks for secrecy, a remote-access tool and a credential. Pause and verify the exact transaction through the registered callback process.',
    payee: 'A/c ••••9918 (FAKC0000992)',
    amount: 640000,
  },
}

const REFUSAL =
  'I need to verify this through our registered callback process. I will get back to you.'

function now(): string {
  return new Date().toISOString()
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function emptyState(): CompanionState {
  return {
    version: '1',
    mode: 'SLEEP',
    hidden: false,
    monitoring: false,
    session_id: null,
    consent_id: null,
    source: null,
    source_label: null,
    started_at: null,
    updated_at: now(),
    expires_at: null,
    demo: false,
    mode_label: null,
    last_event_id: null,
    policy_authority: 'satyapan.policy',
    raw_scores_visible: false,
    manual_only: true,
  }
}

export class MockCompanionClient implements CompanionApiClient {
  private sequence = 0
  private handlers: CompanionHandlers | null = null
  private state: CompanionState = emptyState()
  private lastScenario = 'beneficiary_change'
  private drafts: Partial<Record<'section63' | 'helpline_1930', DraftArtifact>> = {}

  async connect(handlers: CompanionHandlers): Promise<void> {
    this.handlers = handlers
    handlers.onConnection({ connected: false, backendUrl: 'local mock', mock: true })
  }

  disconnect(): void {
    this.handlers = null
  }

  async getState(): Promise<CompanionState> {
    return { ...this.state }
  }

  async startSession(source: CompanionSource, label?: string): Promise<SessionResult> {
    const demo = source === 'demo_replay'
    const monitoring = source === 'user_selected_loopback' || source === 'user_selected_microphone'
    this.state = {
      ...this.state,
      mode: 'ACTIVE',
      hidden: false,
      monitoring,
      session_id: `session_mock_${++this.sequence}`,
      consent_id: `consent_mock_${this.sequence}`,
      source,
      source_label: label ?? null,
      started_at: now(),
      updated_at: now(),
      expires_at: new Date(Date.now() + 8 * 3600_000).toISOString(),
      demo,
      mode_label: demo ? DEMO_REPLAY_LABEL : 'LIVE — CONSENTED SOURCE',
    }
    const event = this.emit('session.started', {
      state: 'ACTIVE',
      headline: demo ? 'Replay fixtures only — not live capture' : 'Watching the source you chose',
      explanation:
        'Only the source you selected is processed. Audio stays in a short in-memory buffer unless you preserve evidence.',
      monitoring,
      source,
      demo,
      mode_label: this.state.mode_label,
    })
    return { state: { ...this.state }, events: [event] }
  }

  async stopSession(): Promise<SessionResult> {
    const wasActive = this.state.session_id !== null
    this.state = { ...emptyState() }
    if (!wasActive) return { state: { ...this.state }, events: [] }
    const event = this.emit('session.stopped', {
      state: 'SLEEP',
      headline: 'Sleep / DND — monitoring is off',
      explanation: 'Capture has been released. Satya is not watching anything.',
      monitoring: false,
    })
    return { state: { ...this.state }, events: [event] }
  }

  async command(type: string, payload: Record<string, unknown> = {}): Promise<CommandResult> {
    if (type === 'demo.replay') {
      const scenario = typeof payload.scenario === 'string' ? payload.scenario : 'beneficiary_change'
      return this.runScenario(scenario)
    }
    if (type === 'ui.hide') {
      await this.stopSession()
      this.state = { ...this.state, hidden: true, mode: 'SLEEP', updated_at: now() }
      const event = this.emit('state.changed', {
        state: 'SLEEP',
        headline: 'Companion hidden — monitoring is off',
        explanation: 'Use the tray to bring Satya back.',
        monitoring: false,
      })
      return this.result('ui.hide', [event])
    }
    if (type === 'ui.disable') {
      this.state = { ...this.state, mode: 'DISABLED', hidden: true, monitoring: false }
      return this.result('ui.disable', [])
    }
    await this.stopSession()
    return this.result(type, [])
  }

  private async runScenario(key: string): Promise<CommandResult> {
    const scenario = SCENARIOS[key] ?? SCENARIOS.beneficiary_change
    this.lastScenario = SCENARIOS[key] ? key : 'beneficiary_change'
    this.state = {
      ...this.state,
      mode: 'INVESTIGATING',
      monitoring: false,
      source: 'demo_replay',
      demo: true,
      mode_label: DEMO_REPLAY_LABEL,
      session_id: this.state.session_id ?? `session_mock_${++this.sequence}`,
      updated_at: now(),
    }
    const started = this.emit('analysis.started', {
      state: 'INVESTIGATING',
      headline: 'Reviewing the replay fixture',
      explanation: `${DEMO_REPLAY_LABEL}. Only generated demo data is processed.`,
      monitoring: false,
      source: 'demo_replay',
      demo: true,
      mode_label: DEMO_REPLAY_LABEL,
    })
    await delay(900)
    this.state = { ...this.state, mode: 'ALERT', updated_at: now() }
    const alert = this.emit('alert.raised', {
      state: 'ALERT',
      headline:
        scenario.band === 'HOLD'
          ? 'Pause this payment and verify independently'
          : 'This request needs independent verification',
      explanation: `${DEMO_REPLAY_LABEL}.\n\n${scenario.explanation}`,
      band: scenario.band,
      reason_codes: scenario.reasons,
      evidence_ids: [`ev_demo_${this.lastScenario}`],
      monitoring: false,
      source: 'demo_replay',
      demo: true,
      mode_label: DEMO_REPLAY_LABEL,
    })
    return this.result('demo.replay', [started, alert])
  }

  async draft(kind: 'section63' | 'helpline_1930', caseId: string): Promise<DraftArtifact> {
    const draft: DraftArtifact = {
      version: '1',
      draft_id: `draft_mock_${kind}_${++this.sequence}`,
      kind,
      case_id: caseId,
      status: 'DRAFT_REQUIRES_HUMAN_REVIEW',
      submission: 'MANUAL_ONLY',
      auto_submit: false,
      generated_at: now(),
      fields:
        kind === 'section63'
          ? {
              record_description: 'USER_CONFIRMED_DESCRIPTION_REQUIRED',
              prescribed_form_version: 'COUNSEL_VERIFIED_VERSION_REQUIRED',
              signatory: null,
            }
          : {
              submission: 'MANUAL_ONLY',
              utr: null,
              utr_missing: true,
              loss_amount_inr: null,
              pronunciation_helper: '1930 → one nine three zero',
            },
      disclaimers: [
        kind === 'section63'
          ? 'Draft only. A qualified person must review the form and signatory.'
          : 'MANUAL_ONLY: no code path dials, transmits or files this draft.',
      ],
    }
    this.drafts[kind] = draft
    this.state = { ...this.state, mode: 'SCRIBE', monitoring: false, updated_at: now() }
    this.emit('draft.ready', {
      state: 'SCRIBE',
      headline: 'Draft ready — human review required',
      explanation: 'Capture is paused while you review this editable draft.',
      band: 'VERIFY',
      monitoring: false,
      mode_label: 'MANUAL_ONLY',
    })
    return draft
  }

  async workspace(caseId?: string): Promise<WorkspaceSnapshot> {
    const key = caseId?.startsWith('case_demo_')
      ? caseId.replace('case_demo_', '')
      : this.lastScenario
    const scenario = SCENARIOS[key] ?? SCENARIOS.beneficiary_change
    const drafts = Object.values(this.drafts).filter(
      (draft): draft is DraftArtifact => draft !== undefined,
    )
    return {
      version: '1',
      case_id: caseId ?? `case_demo_${key}`,
      title: scenario.title,
      kind: 'PAYMENT',
      status: 'OPEN',
      band: scenario.band,
      floor_band: 'VERIFY',
      action_type: 'N2',
      queue: scenario.band === 'HOLD' ? 'CHECKER_REVIEW' : 'MAKER',
      reason_codes: scenario.reasons,
      info_codes: [],
      explanation: `${DEMO_REPLAY_LABEL}.\n\n${scenario.explanation}`,
      payee_masked: scenario.payee,
      amount_inr: scenario.amount,
      evidence: [
        {
          evidence_id: `ev_demo_${key}`,
          channel: 'whatsapp_text',
          filename: `${key}.txt`,
          size_bytes: 320,
          sha256_short: 'demo00000001',
          excerpt: 'Generated demo text. No real person or bank account is used.',
        },
      ],
      drafts,
      audit: [
        {
          at: now(),
          actor: 'emp_priya',
          action: 'demo.replay',
          detail: `scenario=${key} band_set_by_policy=true`,
        },
      ],
      policy_authority: 'satyapan.policy',
      raw_scores_visible: false,
      manual_only: true,
    }
  }

  async listCases(): Promise<CaseSummary[]> {
    return [
      {
        case_id: 'case_s01',
        title: 'Kaveri monthly invoice (routine)',
        status: 'OPEN',
        band: 'PASS',
        queue: 'MAKER',
        updated_at: now(),
      },
      {
        case_id: 'case_demo_beneficiary_change',
        title: SCENARIOS.beneficiary_change.title,
        status: 'OPEN',
        band: 'VERIFY',
        queue: 'MAKER',
        updated_at: now(),
      },
      {
        case_id: 'case_demo_urgent_bypass',
        title: SCENARIOS.urgent_bypass.title,
        status: 'OPEN',
        band: 'HOLD',
        queue: 'CHECKER_REVIEW',
        updated_at: now(),
      },
    ]
  }

  async submitEvidence(text: string): Promise<{
    request_id: string
    accepted: boolean
    evidence_id: string
    reason_codes: string[]
    info_codes: string[]
    ask_count: number
    band_set_by_companion: false
    events: CompanionEvent[]
  }> {
    const asks = /\b(otp|anydesk|between us|new account|beneficiary)\b/gi
    const matches = text.match(asks)?.length ?? 0
    return {
      request_id: `req_mock_${++this.sequence}`,
      accepted: true,
      evidence_id: `ev_text_mock_${this.sequence}`,
      reason_codes: [],
      info_codes: matches ? ['ASK_UNUSUAL_PAYMENT_METHOD'] : [],
      ask_count: matches,
      band_set_by_companion: false,
      events: [],
    }
  }

  async copyText(text: string): Promise<void> {
    await navigator.clipboard.writeText(text)
  }

  async hide(): Promise<void> {
    this.state = { ...this.state, hidden: true, mode: 'SLEEP', monitoring: false }
  }

  async openWorkspace(): Promise<void> {
    window.open('?view=workspace', '_blank')
  }

  async checkClipboard(): Promise<ClipboardCheck> {
    return {
      suspicious: false,
      matches: [],
      preview: 'Clipboard is only read when you press the shortcut.',
      note: 'Local mock — no clipboard access.',
    }
  }

  get refusalScript(): string {
    return REFUSAL
  }

  /** Finale mock bridge: emit a scripted envelope (always labelled demo). */
  emitEvent(
    type: CompanionEventType,
    payload: Partial<CompanionPayload> & Pick<CompanionPayload, 'state' | 'headline'>,
  ): CompanionEvent {
    return this.emit(type, payload)
  }

  private result(type: string, events: CompanionEvent[]): CommandResult {
    return {
      request_id: `req_mock_${type}_${this.sequence}`,
      accepted: true,
      state: { ...this.state },
      events,
    }
  }

  private emit(
    type: CompanionEventType,
    payload: Partial<CompanionPayload> & Pick<CompanionPayload, 'state' | 'headline'>,
  ): CompanionEvent {
    const full: CompanionPayload = {
      mascot_mood: MOOD[payload.state],
      explanation: '',
      band: null,
      reason_codes: [],
      info_codes: [],
      evidence_ids: [],
      next_actions: [
        { id: 'oob_verify', label: 'Verify using a saved contact', variant: 'primary' },
        { id: 'open_scribe', label: 'Prepare an incident draft', variant: 'outline' },
        { id: 'open_workspace', label: 'View details', variant: 'outline' },
      ],
      monitoring: false,
      source: null,
      mode_label: null,
      demo: true,
      ...payload,
    }
    const event: CompanionEvent = {
      version: '1',
      event_id: `evt_mock_${String(++this.sequence).padStart(8, '0')}`,
      type,
      session_id: this.state.session_id,
      occurred_at: now(),
      payload: full,
    }
    this.state = { ...this.state, last_event_id: event.event_id, updated_at: now() }
    this.handlers?.onEvent(event)
    return event
  }
}

export { REFUSAL as MOCK_REFUSAL_SCRIPT }
