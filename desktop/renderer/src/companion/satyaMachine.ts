/**
 * satyaMachine — the pure brain of the mascot window (F07).
 *
 * `(state, action) => state`, no React, no timers, no `Date`, no API calls. Every band in this
 * file is copied from a `CompanionEvent.payload.band`; the reducer never computes or lowers one.
 * Ids and timestamps arrive in actions/events so tests stay deterministic.
 */

import type {
  AskChip,
  AskQuote,
  Band,
  BubbleCard,
  CaptionLine,
  CardAction,
  CompanionEvent,
  CompanionMode,
  CompanionPayload,
  FaceCheck,
  HealthInfo,
  MeetingInfo,
  NextAction,
  Pose,
  SatyaSignal,
  ScreenFinding,
  UserMode,
} from '../../../shared/contracts'
import { ENGINE_LOST_REASON } from '../../../shared/contracts'

export type FileKind = Extract<BubbleCard, { kind: 'file_ask' }>['file_kind']

export interface SatyaState {
  userMode: UserMode
  pose: Pose
  card: BubbleCard | null
  caseId: string | null
  callId: string | null
  chips: AskChip[]
  lastBand: Band | null
  dismissed: boolean
  // Finale: live captions (memory only), exact quotes, meeting notice, engine health.
  lines: CaptionLine[]
  quotes: AskQuote[]
  meeting: MeetingInfo | null
  speaking: boolean
  transcribing: boolean
  approver: string | null
  callStartedAt: string | null
  callDemo: boolean
  callStatus: string | null
  health: HealthInfo | null
  /** Finale video check for the current call (labels only). */
  face: FaceCheck | null
}

export type SatyaAction =
  | { type: 'EVENT'; event: CompanionEvent }
  | { type: 'SET_MODE'; mode: UserMode; card?: BubbleCard | null }
  | {
      type: 'CALL_HINT'
      hintId: string
      source: Extract<BubbleCard, { kind: 'call_ask' }>['source']
      app?: string | null
    }
  | { type: 'SIGNAL'; signal: SatyaSignal; id?: string }
  | { type: 'SHOW_CARD'; card: BubbleCard }
  | { type: 'FILE_HOVER'; active: boolean }
  | { type: 'FILE_DROP'; fileId: string; name: string; kind: FileKind }
  | { type: 'CARD_ACTION'; cardId: string; actionId: string }
  | { type: 'TIMER'; name: 'relief' | 'toast' | 'call_ask'; guardId?: string }

export const initialSatyaState: SatyaState = {
  userMode: 'SLEEPING',
  pose: 'sleep',
  card: null,
  caseId: null,
  callId: null,
  chips: [],
  lastBand: null,
  dismissed: false,
  lines: [],
  quotes: [],
  meeting: null,
  speaking: false,
  transcribing: false,
  approver: null,
  callStartedAt: null,
  callDemo: false,
  callStatus: null,
  health: null,
  face: null,
}

const MAX_LINES = 8

const CALL_RESET = {
  callId: null,
  lines: [] as CaptionLine[],
  speaking: false,
  transcribing: false,
  callStartedAt: null,
  callDemo: false,
  callStatus: null,
  face: null,
}

const CHECK_ACTIONS: CardAction[] = [
  { id: 'check_it', variant: 'primary' },
  { id: 'no_thanks', variant: 'ghost' },
]

const LISTEN_ACTIONS: CardAction[] = [
  { id: 'listen_call', variant: 'primary' },
  { id: 'not_this_call', variant: 'ghost' },
]

const OOB_WAIT_ACTIONS: CardAction[] = [{ id: 'open_notebook', variant: 'outline' }]

const OOB_RESULT_ACTIONS: CardAction[] = [
  { id: 'open_notebook', variant: 'primary' },
  { id: 'prepare_report', variant: 'outline' },
]

const REPORT_ACTIONS: CardAction[] = [
  { id: 'open_reports', variant: 'primary' },
  { id: 'copy_safe_reply', variant: 'ghost' },
]

const DISMISS_ACTIONS = new Set(['close', 'dismiss', 'no'])
const WALK_AWAY_ACTIONS = new Set(['not_now', 'not_this_call', 'no_thanks'])
const VERIFY_ACTIONS = new Set(['verify', 'verify_with_approver', 'oob_verify'])
const WRITE_ACTIONS = new Set(['prepare', 'prepare_report', 'open_scribe', 'open_reports'])
const COPY_ACTIONS = new Set(['copy_reply', 'copy_safe_reply'])

/** Display-only file-kind inference. The bytes themselves never enter this module. */
export function fileKindOf(name: string, mediaType = ''): FileKind {
  const lower = name.toLowerCase()
  const type = mediaType.toLowerCase()
  if (lower.endsWith('.eml') || lower.endsWith('.msg') || type === 'message/rfc822') return 'email'
  if (lower.endsWith('.pdf') || type === 'application/pdf') return 'pdf'
  if (/\.(mp4|mov|m4v|mkv|avi)$/.test(lower) || type.startsWith('video/')) return 'video'
  if (/\.(wav|m4a|mp3|ogg|opus|aac|flac)$/.test(lower) || type.startsWith('audio/')) return 'audio'
  if (/\.(png|jpe?g|webp|gif|heic|bmp)$/.test(lower) || type.startsWith('image/')) return 'image'
  return 'text'
}

function modeFromPayload(payload: CompanionPayload): UserMode {
  if (payload.user_mode) return payload.user_mode
  switch (payload.state) {
    case 'SLEEP':
      return 'SLEEPING'
    case 'DISABLED':
      return 'OFF'
    default:
      return 'WATCHING'
  }
}

function poseForMode(mode: UserMode): Pose {
  if (mode === 'SLEEPING') return 'sleep'
  if (mode === 'OFF') return 'off'
  return 'idle'
}

function actionsFrom(next: NextAction[] | undefined): CardAction[] {
  if (!next || next.length === 0) return []
  return next.slice(0, 3).map((action) => ({ id: action.id, variant: action.variant }))
}

function mergeChips(current: AskChip[], incoming: AskChip[]): AskChip[] {
  if (incoming.length === 0) return current
  const merged = current.map((chip) => ({ ...chip }))
  for (const chip of incoming) {
    const index = merged.findIndex((item) => item.code === chip.code)
    if (index === -1) merged.push({ ...chip })
    else merged[index] = { ...chip }
  }
  return merged
}

function toastCard(event: CompanionEvent, textKey: string, tone: 'neutral' | 'good' | 'warn'): BubbleCard {
  return { kind: 'toast', id: `toast_${event.event_id}`, text_key: textKey, tone }
}

function liveCard(event: CompanionEvent, callId: string | null, state?: SatyaState): BubbleCard {
  return {
    kind: 'live',
    id: `live_${callId ?? event.event_id}`,
    chips: event.payload.chips ?? state?.chips ?? [],
    coverage: event.payload.coverage ?? 'incomplete',
    seal: event.payload.seal ?? 'unavailable',
    elapsed_s: 0,
    lines: state?.lines ?? [],
    band: state?.lastBand ?? null,
    status: state?.callStatus ?? null,
    transcribing: state?.transcribing ?? false,
    demo: state?.callDemo ?? false,
    started_at: state?.callStartedAt ?? event.occurred_at,
    face: state?.face ?? null,
  }
}

/** Rebuild the live card from state (after a caption, or when an alert is dismissed). */
function restoreLive(state: SatyaState): BubbleCard | null {
  if (!state.callId) return null
  const current = state.card?.kind === 'live' ? state.card : null
  return {
    kind: 'live',
    id: current?.id ?? `live_${state.callId}`,
    chips: state.chips,
    coverage: current?.coverage ?? 'usable',
    seal: current?.seal ?? 'not_verified',
    elapsed_s: current?.elapsed_s ?? 0,
    lines: state.lines,
    band: state.lastBand,
    status: state.callStatus,
    transcribing: state.transcribing,
    demo: state.callDemo,
    started_at: state.callStartedAt,
    face: state.face,
  }
}

function mergeQuotes(current: AskQuote[], incoming: AskQuote[] | undefined): AskQuote[] {
  if (!incoming || incoming.length === 0) return current
  const byCode = new Map(current.map((q) => [q.code, q]))
  for (const quote of incoming) if (!byCode.has(quote.code)) byCode.set(quote.code, quote)
  return [...byCode.values()]
}

const CARD_PRIORITY: Record<BubbleCard['kind'], number> = {
  consent: 5,
  alert: 5,
  oob_wait: 5,
  oob_result: 5,
  scribe: 4,
  file_ask: 4,
  result: 4,
  screen: 3,
  liveness: 3,
  call_ask: 2,
  notice: 2,
  live: 1,
  toast: 0,
}

function screenCard(finding: ScreenFinding, source: 'screen' | 'clipboard', id: string): BubbleCard {
  return {
    kind: 'screen',
    id: `screen_${id}`,
    source,
    finding,
    actions: finding.suspicious
      ? [
          { id: 'check_this', variant: 'primary' },
          { id: 'dismiss', variant: 'ghost' },
        ]
      : [{ id: 'dismiss', variant: 'ghost' }],
  }
}

function alertCard(
  event: CompanionEvent,
  band: Band,
  chips: AskChip[],
  extra: { quotes?: AskQuote[]; approver?: string | null; context?: 'call' | 'file' | 'screen' } = {},
): BubbleCard {
  const actions = actionsFrom(event.payload.next_actions)
  // During a call, the third action is the video liveness tips instead of the Notebook.
  const callActions =
    extra.context === 'call'
      ? actions.map((action) => (action.id === 'open_notebook' ? { ...action, id: 'liveness' } : action))
      : actions
  return {
    kind: 'alert',
    id: `alert_${event.event_id}`,
    band,
    headline: event.payload.headline,
    reasons: event.payload.reason_codes,
    chips,
    actions: callActions,
    quotes: extra.quotes ?? event.payload.quotes ?? [],
    approver: extra.approver ?? null,
    context: extra.context,
  }
}

function resultCard(event: CompanionEvent, band: Band): BubbleCard {
  return {
    kind: 'result',
    id: `result_${event.event_id}`,
    band,
    headline: event.payload.headline,
    reasons: event.payload.reason_codes,
    actions: actionsFrom(event.payload.next_actions),
  }
}

function scribeCard(event: CompanionEvent, done: boolean): Extract<BubbleCard, { kind: 'scribe' }> {
  const report = event.payload.report
  return {
    kind: 'scribe',
    id: `scribe_${event.event_id}`,
    actions: REPORT_ACTIONS,
    sections: report
      ? report.sections.map((section) => ({
          id: section.id,
          title: section.title,
          status: done ? 'done' : 'writing',
        }))
      : [],
  }
}

function oobWaitCard(event: CompanionEvent): BubbleCard | null {
  const approver = event.payload.oob?.approver_name ?? event.payload.ticket?.approver_name
  if (!approver) return null
  return {
    kind: 'oob_wait',
    id: `oob_wait_${event.event_id}`,
    approver_name: approver,
    sent_at: event.occurred_at,
    actions: OOB_WAIT_ACTIONS,
  }
}

function oobResultCard(event: CompanionEvent): BubbleCard | null {
  const outcome = event.payload.oob?.outcome
  if (!outcome) return null
  const wait = event.payload.oob?.approver_name
  return {
    kind: 'oob_result',
    id: `oob_result_${event.event_id}`,
    approver_name: wait ?? 'Approver',
    outcome,
    actions: OOB_RESULT_ACTIONS,
  }
}

function reduceEvent(state: SatyaState, event: CompanionEvent): SatyaState {
  if (state.userMode === 'OFF') return state

  const payload = event.payload
  const inboundMode = modeFromPayload(payload)
  const band = payload.band ?? state.lastBand

  if (state.userMode === 'SLEEPING') {
    const allowed =
      event.type === 'state.changed' ||
      event.type === 'session.started' ||
      event.type === 'session.stopped' ||
      event.type === 'error'
    if (!allowed) return state
  }

  switch (event.type) {
    case 'state.changed': {
      const mode = inboundMode
      if (mode === 'SLEEPING' || mode === 'OFF') {
        return {
          ...state,
          userMode: mode,
          pose: poseForMode(mode),
          card: null,
          callId: null,
          chips: [],
          caseId: payload.case_id ?? state.caseId,
          lastBand: payload.band ?? state.lastBand,
          dismissed: false,
        }
      }
      const wasWatching = state.userMode === 'WATCHING'
      const nextPose: Pose =
        payload.pose ?? (state.callId ? 'listen' : wasWatching && state.pose !== 'sleep' ? state.pose : 'idle')
      return {
        ...state,
        userMode: mode,
        pose: nextPose,
        caseId: payload.case_id ?? state.caseId,
        callId: payload.call_id ?? state.callId,
        lastBand: payload.band ?? state.lastBand,
      }
    }

    case 'session.started':
      return {
        ...state,
        userMode: 'WATCHING',
        pose: payload.pose ?? (state.callId ? 'listen' : 'idle'),
        caseId: payload.case_id ?? state.caseId,
        callId: payload.call_id ?? state.callId,
        lastBand: payload.band ?? state.lastBand,
      }

    case 'session.stopped':
      return {
        ...state,
        userMode: 'SLEEPING',
        pose: 'sleep',
        card: toastCard(event, 'toast.sleep', 'neutral'),
        callId: null,
        chips: [],
        caseId: payload.case_id ?? state.caseId,
        lastBand: payload.band ?? state.lastBand,
        dismissed: false,
      }

    case 'call.started': {
      const callId = payload.call_id ?? state.callId
      const next: SatyaState = {
        ...state,
        pose: state.pose === 'alert' ? 'alert' : 'listen',
        callId,
        caseId: payload.case_id ?? state.caseId,
        chips: mergeChips([], payload.chips ?? []),
        quotes: [],
        lines: [],
        callStatus: null,
        transcribing: false,
        callStartedAt: event.occurred_at,
        callDemo: payload.demo === true && payload.source === 'demo_replay',
        lastBand: payload.band ?? null,
        dismissed: false,
      }
      return {
        ...next,
        card:
          state.card?.kind === 'alert' || state.card?.kind === 'oob_wait'
            ? state.card
            : liveCard(event, callId, next),
      }
    }

    case 'call.stopped': {
      const keepAlert =
        state.card?.kind === 'alert' ||
        state.card?.kind === 'oob_wait' ||
        state.card?.kind === 'oob_result'
      return {
        ...state,
        ...CALL_RESET,
        card: state.card?.kind === 'live' ? null : state.card,
        pose: keepAlert ? 'alert' : state.pose === 'listen' ? 'idle' : state.pose,
        lastBand: payload.band ?? state.lastBand,
      }
    }

    case 'live.chips': {
      const chips = mergeChips(state.chips, payload.chips ?? [])
      const quotes = mergeQuotes(state.quotes, payload.quotes)
      const card = state.card
      if (card && card.kind !== 'live' && card.kind !== 'toast' && card.kind !== 'call_ask') {
        return { ...state, chips, quotes, lastBand: payload.band ?? state.lastBand }
      }
      const nextCard: BubbleCard =
        card?.kind === 'live'
          ? {
              ...card,
              chips,
              coverage: payload.coverage ?? card.coverage,
              seal: payload.seal ?? card.seal,
            }
          : liveCard(event, state.callId, { ...state, chips })
      return {
        ...state,
        chips,
        quotes,
        card: nextCard,
        pose: state.pose === 'write' ? 'write' : 'listen',
        callId: payload.call_id ?? state.callId,
        lastBand: payload.band ?? state.lastBand,
      }
    }

    case 'coverage.changed': {
      if (state.card?.kind !== 'live') {
        return { ...state, lastBand: payload.band ?? state.lastBand }
      }
      return {
        ...state,
        card: {
          ...state.card,
          coverage: payload.coverage ?? state.card.coverage,
          seal: payload.seal ?? state.card.seal,
        },
        lastBand: payload.band ?? state.lastBand,
      }
    }

    case 'alert.raised': {
      if (!band) {
        return {
          ...state,
          pose: 'alert',
          chips: payload.chips ?? state.chips,
          caseId: payload.case_id ?? state.caseId,
          callId: payload.call_id ?? state.callId,
          dismissed: false,
        }
      }
      const quotes = mergeQuotes(state.quotes, payload.quotes)
      return {
        ...state,
        pose: 'alert',
        card: alertCard(event, band, payload.chips ?? state.chips, {
          quotes,
          approver: payload.approver_name ?? state.approver,
          context: payload.call_id || state.callId ? 'call' : undefined,
        }),
        chips: payload.chips ?? state.chips,
        quotes,
        approver: payload.approver_name ?? state.approver,
        caseId: payload.case_id ?? state.caseId,
        callId: payload.call_id ?? state.callId,
        lastBand: band,
        dismissed: false,
      }
    }

    case 'call.status': {
      const status = payload.status_code ?? 'status'
      const next = { ...state, callStatus: status === 'asr_unavailable' ? status : state.callStatus }
      return state.card?.kind === 'live' ? { ...next, card: restoreLive(next) } : next
    }

    case 'analysis.started':
      return {
        ...state,
        pose: 'think',
        card: state.card?.kind === 'file_ask' ? null : state.card,
        caseId: payload.case_id ?? state.caseId,
      }

    case 'analysis.completed': {
      const nextBand = payload.band
      if (!nextBand) {
        return {
          ...state,
          pose: state.callId ? 'listen' : 'idle',
          caseId: payload.case_id ?? state.caseId,
        }
      }
      return {
        ...state,
        pose: nextBand === 'PASS' ? 'relief' : 'alert',
        card: resultCard(event, nextBand),
        caseId: payload.case_id ?? state.caseId,
        lastBand: nextBand,
        dismissed: false,
      }
    }

    case 'oob.sent': {
      const card = oobWaitCard(event)
      return {
        ...state,
        pose: 'alert',
        card: card ?? state.card,
        caseId: event.payload.ticket?.case_id ?? payload.case_id ?? state.caseId,
        lastBand: payload.band ?? state.lastBand,
        dismissed: false,
      }
    }

    case 'oob.result': {
      const card = oobResultCard(event)
      const approved = payload.oob?.outcome === 'approved'
      return {
        ...state,
        pose: approved ? 'relief' : 'alert',
        card: card ?? state.card,
        lastBand: payload.band ?? state.lastBand,
        dismissed: false,
      }
    }

    case 'draft.ready':
      return {
        ...state,
        pose: 'write',
        card: scribeCard(event, false),
        caseId: payload.case_id ?? state.caseId,
        lastBand: payload.band ?? state.lastBand,
      }

    case 'report.ready':
      return {
        ...state,
        pose: 'write',
        card: scribeCard(event, true),
        caseId: payload.case_id ?? state.caseId,
        lastBand: payload.band ?? state.lastBand,
      }

    case 'case.updated': {
      let card: BubbleCard | null = state.card
      const checkedBand = payload.band ?? null
      if (state.card?.kind === 'file_ask' && checkedBand) {
        card =
          checkedBand === 'PASS'
            ? resultCard(event, checkedBand)
            : alertCard(event, checkedBand, payload.chips ?? state.chips, {
              approver: payload.approver_name ?? state.approver,
              context: 'file',
            })
      } else if (state.card?.kind === 'scribe' && payload.report) {
        card = { ...state.card, sections: scribeCard(event, true).sections }
      }
      const pose: Pose =
        state.pose === 'think' && !state.callId ? 'idle' : state.pose
      return {
        ...state,
        pose,
        card,
        caseId: payload.case_id ?? state.caseId,
        lastBand: payload.band ?? state.lastBand,
      }
    }

    case 'evidence.received':
      return {
        ...state,
        caseId: payload.case_id ?? state.caseId,
        lastBand: payload.band ?? state.lastBand,
      }

    case 'error':
      return {
        ...state,
        ...CALL_RESET,
        userMode: 'SLEEPING',
        pose: 'sleep',
        card: toastCard(event, 'toast.no_backend', 'warn'),
        chips: [],
        dismissed: false,
      }

    default:
      return state
  }
}

function reduceSignal(state: SatyaState, signal: SatyaSignal, id: string): SatyaState {
  switch (signal.kind) {
    case 'health':
      return { ...state, health: signal.health }
    case 'meeting': {
      if (state.userMode !== 'WATCHING') return { ...state, meeting: signal.meeting }
      return { ...state, meeting: signal.meeting }
    }
    case 'speech':
      return state.callId ? { ...state, speaking: signal.active } : state
    case 'transcribing': {
      if (!state.callId) return state
      const next = { ...state, transcribing: true }
      return state.card?.kind === 'live' ? { ...next, card: restoreLive(next) } : next
    }
    case 'face': {
      // Labels only. The band still comes from the policy engine (alert.raised).
      if (state.callId && signal.call_id !== state.callId) return state
      const next = { ...state, face: signal.face }
      return state.card?.kind === 'live' ? { ...next, card: restoreLive(next) } : next
    }
    case 'caption': {
      if (!state.callId || signal.call_id !== state.callId) return state
      const lines = [...state.lines, signal.line].slice(-MAX_LINES)
      const next = { ...state, lines, transcribing: false }
      return state.card?.kind === 'live' ? { ...next, card: restoreLive(next) } : next
    }
    case 'capture': {
      if (signal.state === 'error') {
        // Fail closed: any capture error puts Satya to sleep and says why.
        return {
          ...state,
          ...CALL_RESET,
          userMode: 'SLEEPING',
          pose: 'sleep',
          chips: [],
          card: {
            kind: 'notice',
            id: `notice_capture_${id}`,
            tone: 'warn',
            title:
              signal.reason === ENGINE_LOST_REASON ? 'notice.backend.title' : 'notice.capture_error.title',
            body:
              signal.reason === ENGINE_LOST_REASON
                ? 'notice.backend.body'
                : `notice.capture_error.body|reason=${encodeURIComponent(signal.reason ?? 'Capture failed')}`,
            actions: [{ id: 'dismiss', variant: 'ghost' }],
          },
          dismissed: false,
        }
      }
      return state
    }
    case 'text_check': {
      if (state.userMode !== 'WATCHING') return state
      if (!signal.finding.suspicious && !signal.on_demand) return state
      const card = screenCard(signal.finding, signal.source, id)
      const current = state.card ? CARD_PRIORITY[state.card.kind] : -1
      if (!signal.on_demand && current > CARD_PRIORITY.screen) return state
      return {
        ...state,
        card,
        pose: signal.finding.suspicious ? 'alert' : state.callId ? 'listen' : 'relief',
        dismissed: false,
      }
    }
    case 'level':
    case 'hotkey':
      return state
    default:
      return state
  }
}

export function satyaReducer(state: SatyaState, action: SatyaAction): SatyaState {
  switch (action.type) {
    case 'EVENT':
      return reduceEvent(state, action.event)

    case 'SET_MODE': {
      if (action.mode === state.userMode) {
        if (action.card === undefined || action.card === state.card) return state
        return { ...state, card: action.card }
      }
      return {
        ...state,
        ...CALL_RESET,
        userMode: action.mode,
        pose: poseForMode(action.mode),
        card: action.card ?? null,
        chips: [],
        quotes: [],
        meeting: action.mode === 'WATCHING' ? state.meeting : null,
        dismissed: false,
      }
    }

    case 'SHOW_CARD':
      return { ...state, card: action.card, dismissed: false }

    case 'SIGNAL':
      return reduceSignal(state, action.signal, action.id ?? 'local')

    case 'CALL_HINT': {
      if (state.userMode !== 'WATCHING') return state
      if (state.callId) return state
      if (state.card && state.card.kind !== 'live') return state
      if (state.pose === 'alert' || state.pose === 'write') return state
      return {
        ...state,
        pose: 'idle',
        card: {
          kind: 'call_ask',
          id: `call_ask_${action.hintId}`,
          source: action.source,
          actions: LISTEN_ACTIONS,
          ...(action.app ? { app: action.app } : {}),
        },
        dismissed: false,
      }
    }

    case 'FILE_HOVER': {
      if (state.userMode !== 'WATCHING') return state
      if (!action.active) {
        return state.pose === 'catch'
          ? { ...state, pose: state.callId ? 'listen' : 'idle' }
          : state
      }
      if (state.callId || state.card?.kind === 'alert') return state
      if (state.pose === 'alert' || state.pose === 'write') return state
      return state.pose === 'catch' ? state : { ...state, pose: 'catch' }
    }

    case 'FILE_DROP': {
      if (state.userMode !== 'WATCHING') return state
      return {
        ...state,
        pose: 'think',
        card: {
          kind: 'file_ask',
          id: `file_ask_${action.fileId}`,
          file_name: action.name,
          file_kind: action.kind,
          actions: CHECK_ACTIONS,
        },
        dismissed: false,
      }
    }

    case 'CARD_ACTION': {
      const card = state.card
      if (!card || card.id !== action.cardId) return state
      if (DISMISS_ACTIONS.has(action.actionId)) {
        return {
          ...state,
          card: restoreLive(state),
          dismissed: true,
          pose: state.callId ? 'listen' : 'idle',
        }
      }
      if (WALK_AWAY_ACTIONS.has(action.actionId)) {
        return {
          ...state,
          card: null,
          dismissed: true,
          pose: state.userMode === 'WATCHING' ? (state.callId ? 'listen' : 'idle') : state.pose,
        }
      }
      if (action.actionId === 'start_watching' || action.actionId.startsWith('start_watching:')) {
        return { ...state, card: null, pose: 'idle', dismissed: false }
      }
      if (action.actionId === 'listen_call') {
        return { ...state, pose: 'listen', dismissed: false }
      }
      if (action.actionId === 'check_it') {
        return { ...state, pose: 'think' }
      }
      if (VERIFY_ACTIONS.has(action.actionId)) {
        return { ...state, pose: 'alert' }
      }
      if (COPY_ACTIONS.has(action.actionId)) {
        return { ...state, pose: 'relief' }
      }
      if (WRITE_ACTIONS.has(action.actionId)) {
        return { ...state, pose: 'write' }
      }
      return state
    }

    case 'TIMER': {
      if (action.guardId) {
        const cardId = state.card?.id
        if (action.guardId !== cardId && action.guardId !== state.callId && action.guardId !== state.caseId) {
          return state
        }
      }
      if (action.name === 'relief') {
        if (state.pose !== 'relief') return state
        return { ...state, pose: state.callId ? 'listen' : 'idle' }
      }
      if (action.name === 'toast') {
        if (state.card?.kind !== 'toast') return state
        return { ...state, card: null }
      }
      if (state.card?.kind !== 'call_ask') return state
      return { ...state, card: null, pose: state.callId ? 'listen' : 'idle' }
    }

    default:
      return state
  }
}

/** Exposed for tests only: maps a backend `CompanionState.mode` to the user-visible mode. */
export function modeForCompanionState(mode: CompanionMode): UserMode {
  if (mode === 'SLEEP') return 'SLEEPING'
  if (mode === 'DISABLED') return 'OFF'
  return 'WATCHING'
}
