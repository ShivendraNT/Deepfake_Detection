/**
 * api.ts — the one import every view uses instead of touching `window.satyapan` directly.
 *
 * In Electron, `window.satyapan` is the narrow preload bridge (main owns the windows).
 * In a browser (`npm run dev:web`, `?view=stage`) there is no preload, so we install an
 * in-memory mock bridge. `VITE_SATYA_MOCK=1` forces the mock even inside Electron so the
 * UI can be rehearsed offline. The mock never computes a band: it relays `MockCompanionClient`
 * envelopes, which are labelled replay.
 */

import type {
  AppConfig,
  BridgeResult,
  BubbleCard,
  CaseSummary,
  ClipboardCheck,
  CommandResult,
  CompanionBridge,
  CompanionEvent,
  CompanionSource,
  CompanionState,
  ConnectionStatus,
  DraftArtifact,
  EvidenceResult,
  Prefs,
  SessionResult,
  TrayRequest,
  UserMode,
  WorkspaceSnapshot,
} from '../../../shared/contracts'
import { MockCompanionClient } from '../companion/mockClient'

type Unsubscribe = () => void
type Listener<T> = (value: T) => void

interface EnvShape {
  env?: Record<string, string | undefined>
}

const env = (import.meta as unknown as EnvShape).env ?? {}
const PREFS_KEY = 'satya.prefs.v1'

export const FORCE_MOCK = env.VITE_SATYA_MOCK === '1'

export const MOCK_OOB_URL = 'http://127.0.0.1:8000/oob/inbox/demo'

function errorOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

async function wrap<T>(work: () => Promise<T>): Promise<BridgeResult<T>> {
  try {
    return { ok: true, data: await work() }
  } catch (error) {
    return { ok: false, error: errorOf(error) }
  }
}

function loadPrefs(): Prefs {
  const fallback: Prefs = {
    position: { x: 1120, y: 620 },
    size: 'M',
    sound: false,
    sounds: false,
    lang: 'en',
    notice_calls: true,
    source: 'loopback',
  }
  try {
    const raw = globalThis.localStorage?.getItem(PREFS_KEY)
    if (!raw) return fallback
    return { ...fallback, ...(JSON.parse(raw) as Partial<Prefs>) }
  } catch {
    return fallback
  }
}

function savePrefs(prefs: Prefs): void {
  try {
    globalThis.localStorage?.setItem(PREFS_KEY, JSON.stringify(prefs))
  } catch {
    // Private mode / no storage: preferences simply last for this tab.
  }
}

/**
 * Every bridge method, implemented in this tab. Cards are delivered to `onCard` listeners so a
 * view can render them into a plain `<div>` instead of a separate browser window.
 */
export function createMockBridge(): CompanionBridge {
  const client = new MockCompanionClient()
  const channels = new Map<string, Set<Listener<never>>>()
  let prefs = loadPrefs()
  let currentCard: BubbleCard | null = null

  function on<T>(channel: string, callback: Listener<T>): Unsubscribe {
    const set = (channels.get(channel) ?? new Set<Listener<never>>()) as Set<Listener<T>>
    set.add(callback)
    channels.set(channel, set as unknown as Set<Listener<never>>)
    return () => {
      set.delete(callback)
    }
  }

  function emit<T>(channel: string, value: T): void {
    const set = channels.get(channel) as Set<Listener<T>> | undefined
    if (!set) return
    for (const listener of [...set]) listener(value)
  }

  void client.connect({
    onEvent: (event: CompanionEvent) => emit('event', event),
    onConnection: (status: ConnectionStatus) => emit('connection', status),
    onTrayRequest: (request: TrayRequest) => emit('tray', request),
    onHotkey: (action: string) => emit('hotkey', action),
  })

  function tail(): 'left' | 'right' {
    const screenWidth = globalThis.innerWidth ?? 1440
    const mascotX = prefs.position?.x ?? screenWidth - 280
    return mascotX + 140 > screenWidth / 2 ? 'right' : 'left'
  }

  function showCard(card: BubbleCard): void {
    currentCard = card
    emit('card', { card, tail: tail() })
  }

  function hideCard(cardId?: string): void {
    if (cardId && currentCard?.id !== cardId) return
    currentCard = null
    emit('card', { card: null, tail: tail() })
  }

  function cardAction(cardId: string, actionId: string): void {
    emit('card-action', { card_id: cardId, action_id: actionId })
  }

  return {
    getConfig: async (): Promise<AppConfig> => ({
      backendUrl: 'http://127.0.0.1:8000',
      demoUser: 'emp_priya',
      demoRole: 'maker',
      platform: 'web-mock',
      version: '1.0.0-mock',
      oob_url: MOCK_OOB_URL,
    }),
    getState: () => wrap(() => client.getState()),
    startSession: (source: CompanionSource, label?: string) =>
      wrap(() => client.startSession(source, label)),
    stopSession: () => wrap(() => client.stopSession()),
    command: (type: string, payload: Record<string, unknown> = {}) =>
      wrap(() => client.command(type, payload)),
    submitEvidence: (text: string, _evidenceId?: string) => wrap(() => client.submitEvidence(text)),
    submitFile: (
      filename: string,
      _mediaType: string,
      _bytes: ArrayBuffer,
      _caseId?: string | null,
    ) =>
      wrap(async () => {
        const result = await client.submitEvidence(`Mock file check: ${filename}`)
        return { ...result, evidence_id: `ev_file_mock_${Date.now().toString(36)}` }
      }),
    draft: (kind: 'section63' | 'helpline_1930', caseId: string) =>
      wrap(() => client.draft(kind, caseId)),
    workspace: (caseId?: string) => wrap(() => client.workspace(caseId)),
    listCases: () => wrap(() => client.listCases()),
    checkClipboard: () => wrap(() => client.checkClipboard()),
    copyText: async (text: string) => {
      try {
        await navigator.clipboard.writeText(text)
        return { ok: true, data: null }
      } catch (error) {
        return { ok: false, error: errorOf(error) }
      }
    },
    openWorkspace: async (tab?: string) => {
      const query = tab ? `?view=workspace&tab=${encodeURIComponent(tab)}` : '?view=workspace'
      globalThis.open?.(query, '_blank')
    },
    hideCompanion: async () => {
      await client.hide()
      return { ok: true, data: null }
    },
    quit: async () => ({ ok: true, data: null }),
    onEvent: (callback) => on<CompanionEvent>('event', callback),
    onConnection: (callback) => on<ConnectionStatus>('connection', callback),
    onTrayRequest: (callback) => on<TrayRequest>('tray', callback),
    onHotkey: (callback) => on<string>('hotkey', callback),

    setClickThrough: () => undefined,
    dragBy: (dx: number, dy: number) => {
      const base = prefs.position ?? { x: 0, y: 0 }
      prefs = { ...prefs, position: { x: base.x + dx, y: base.y + dy } }
    },
    dragEnd: () => {
      savePrefs(prefs)
      if (currentCard) showCard(currentCard)
    },
    onCursor: () => () => undefined,
    showCard,
    hideCard,
    onCardAction: (callback) => on<{ card_id: string; action_id: string }>('card-action', callback),
    showBubble: showCard,
    hideBubble: () => hideCard(),
    onCard: (callback) =>
      on<{ card: BubbleCard | null; tail: 'left' | 'right' }>('card', (payload) =>
        callback(payload.card, payload.tail),
      ),
    cardAction,
    resizeBubble: () => undefined,
    setUserMode: async (mode: UserMode) => {
      const state = await client.getState()
      if (mode === 'WATCHING') {
        if (state.mode === 'ACTIVE') return { ok: true, data: state }
        const result = await client.startSession('user_selected_loopback', 'Watching')
        return { ok: true, data: result.state }
      }
      await client.stopSession()
      if (mode === 'OFF') await client.hide()
      return { ok: true, data: await client.getState() }
    },
    getPrefs: async () => ({ ...prefs }),
    setPrefs: async (patch: Partial<Prefs>) => {
      prefs = { ...prefs, ...patch }
      savePrefs(prefs)
      return { ...prefs }
    },
    openExternal: async (url: string) => {
      const allowed =
        url === 'tel:1930' ||
        url.startsWith('mailto:') ||
        url.startsWith('https://cybercrime.gov.in')
      if (!allowed) throw new Error('link is not on the allow-list')
      globalThis.open?.(url, '_blank')
    },
  }
}

const realBridge = (window as unknown as { satyapan?: CompanionBridge }).satyapan
const mockBridge = FORCE_MOCK || !realBridge ? createMockBridge() : null

/** The app's only transport. Import this, never `window.satyapan`. */
export const api: CompanionBridge = mockBridge ?? (realBridge as CompanionBridge)

interface WorkspaceNavigationBridge {
  onWorkspaceNavigate?: (callback: (tab: string) => void) => () => void
  workspaceReady?: () => void
}

function workspaceNavigationBridge(): WorkspaceNavigationBridge | undefined {
  return (window as unknown as { satyapan?: WorkspaceNavigationBridge }).satyapan
}

export function onWorkspaceNavigate(callback: (tab: string) => void): () => void {
  return workspaceNavigationBridge()?.onWorkspaceNavigate?.(callback) ?? (() => undefined)
}

export function workspaceReady(): void {
  workspaceNavigationBridge()?.workspaceReady?.()
}

/** Toggle ambient screen analysis through the narrow Electron bridge when available. */
export function toggleScreenGuard(): void {
  const bridge = (window as unknown as {
    satyapan?: CompanionBridge & { toggleScreenGuard?: () => void }
  }).satyapan
  bridge?.toggleScreenGuard?.()
}

/** True in browser mock mode, so a view can render cards inline instead of in a window. */
export const isMockBridge = mockBridge !== null
