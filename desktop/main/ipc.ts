/** Narrow IPC surface between the sandboxed renderer and the local backend (T25). */

import { app, BrowserWindow, clipboard, ipcMain, type IpcMainEvent, type IpcMainInvokeEvent } from 'electron'

import type {
  BridgeResult,
  BubbleCard,
  CaseSummary,
  ClipboardCheck,
  CommandResult,
  CompanionSource,
  CompanionState,
  DraftArtifact,
  EvidenceResult,
  Prefs,
  SessionResult,
  UserMode,
  WorkspaceSnapshot,
} from '../shared/contracts'
import type { BackendClient } from './backend'

export interface IpcDependencies {
  backend: BackendClient
  getCompanion: () => BrowserWindow | null
  openWorkspace: (tab?: string) => void
  hideCompanion: () => Promise<void>
  quit: () => Promise<void>
  // Finale window manager (F02). Optional so the T25 surface keeps working on its own.
  setClickThrough?: (through: boolean) => void
  toggleScreenGuard?: () => void
  dragBy?: (dx: number, dy: number) => void
  dragEnd?: () => void
  showCard?: (card: BubbleCard) => void
  hideCard?: (cardId?: string) => void
  relayCardAction?: (cardId: string, actionId: string) => void
  resizeBubble?: (height: number) => void
  setUserMode?: (mode: UserMode) => Promise<BridgeResult<CompanionState>>
  getUserMode?: () => UserMode
  isScreenGuardActive?: () => boolean
  getActiveCallId?: () => string | null
  getPrefs?: () => Prefs | Promise<Prefs>
  setPrefs?: (patch: Partial<Prefs>) => Prefs | Promise<Prefs>
  openExternal?: (url: string) => Promise<void>
}

/**
 * `openExternal` is deliberately tiny. Satya may open the 1930 dialler, a mail draft, or the
 * NCRP portal for the human. Nothing else, and never with a message-supplied phone number.
 */
export function isAllowedExternal(url: string): boolean {
  if (url === 'tel:1930') return true
  if (/^mailto:[^\s]+@[^\s]+$/i.test(url)) return true
  return /^https:\/\/cybercrime\.gov\.in(?:\/|$)/i.test(url)
}

const URL_PATTERN = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\//

interface RendererEvent {
  senderFrame?: { url: string } | null
}

function trusted(event: RendererEvent): boolean {
  const url = event.senderFrame?.url ?? ''
  return url.startsWith('file://') || URL_PATTERN.test(url)
}

function errorOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function refuseUntrusted<T>(event: RendererEvent): BridgeResult<T> | null {
  if (trusted(event)) return null
  return { ok: false, error: 'untrusted renderer' }
}

async function wrap<T>(work: () => Promise<T>): Promise<BridgeResult<T>> {
  try {
    return { ok: true, data: await work() }
  } catch (error) {
    return { ok: false, error: errorOf(error) }
  }
}

const SUSPICIOUS: Array<{ label: string; pattern: RegExp }> = [
  { label: 'urgency or secrecy language', pattern: /\b(urgent|immediately|today|confidential|between us)\b/i },
  { label: 'bank or payee details', pattern: /\b(account|ifsc|beneficiary|bank details|payee)\b/i },
  { label: 'credential request', pattern: /\b(otp|pin|password|cvv|login)\b/i },
  { label: 'remote-access tool', pattern: /\b(anydesk|teamviewer|quick ?support|screen share)\b/i },
  { label: 'payment instruction', pattern: /\b(transfer|payment|neft|rtgs|imps|upi)\b/i },
]

export function redact(text: string): string {
  return text
    .replace(/\b\d{9,18}\b/g, (value) => `••••${value.slice(-4)}`)
    .replace(/\b[A-Z]{4}0[A-Z0-9]{6}\b/g, 'FAK•••••••')
    .replace(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, (value) => {
      const [name, domain] = value.split('@')
      return `${name.slice(0, 2)}•••@${domain}`
    })
    .replace(/\+?\d[\d\s-]{7,}\d/g, (value) => `••••${value.slice(-4)}`)
    .replace(/\s+/g, ' ')
    .trim()
}

export function inspectClipboard(text: string): ClipboardCheck {
  const matches = SUSPICIOUS.filter((rule) => rule.pattern.test(text)).map((rule) => rule.label)
  return {
    suspicious: matches.length >= 2,
    matches,
    preview: redact(text).slice(0, 240),
    note: 'Checked only because you pressed the shortcut. Nothing is sent anywhere.',
  }
}

export function registerIpc(deps: IpcDependencies): void {
  const { backend } = deps
  const handle = (
    channel: string,
    listener: (event: IpcMainInvokeEvent, ...args: unknown[]) => unknown,
  ) => {
    ipcMain.removeHandler(channel)
    ipcMain.handle(channel, listener)
  }

  handle('companion:get-config', (event) => {
    const refused = refuseUntrusted(event)
    if (refused) return refused
    return backend.config()
  })

  handle('companion:get-state', async (event) => {
    const refused = refuseUntrusted<CompanionState>(event)
    if (refused) return refused
    const currentMode = deps.getUserMode?.() ?? 'SLEEPING'
    const isWatching = currentMode === 'WATCHING' || deps.isScreenGuardActive?.() === true
    let baseState: CompanionState | null = null
    try {
      baseState = await backend.getState()
    } catch {}

    const state: CompanionState = {
      version: '1',
      mode: isWatching ? ('ACTIVE' as any) : ('SLEEP' as any),
      hidden: false,
      monitoring: isWatching,
      session_id: baseState?.session_id ?? `session_${Date.now()}`,
      consent_id: baseState?.consent_id ?? `consent_${Date.now()}`,
      source: isWatching ? 'user_selected_loopback' : null,
      source_label: isWatching ? 'Watching Google Meet & Screen' : 'Sleeping',
      started_at: baseState?.started_at ?? (isWatching ? new Date().toISOString() : null),
      updated_at: new Date().toISOString(),
      expires_at: null,
      demo: false,
      mode_label: isWatching ? 'Watching Google Meet & Screen' : 'Sleeping',
      last_event_id: baseState?.last_event_id ?? null,
      policy_authority: 'satyapan.policy',
      raw_scores_visible: false,
      manual_only: true,
      ...(baseState ?? {}),
      ...(isWatching
        ? {
            mode: 'ACTIVE' as any,
            monitoring: true,
            mode_label: 'Watching Google Meet & Screen',
            source: 'user_selected_loopback',
          }
        : {}),
    }

    return { ok: true, data: state }
  })

  handle('companion:start-session', (event, ...args) => {
    const refused = refuseUntrusted<SessionResult>(event)
    if (refused) return refused
    const [source, label] = args as unknown as [CompanionSource, string | undefined]
    const win = deps.getCompanion()
    if (!win || !win.isVisible()) {
      return { ok: false, error: 'the consent card must be visible before monitoring starts' }
    }
    return wrap(() => backend.startSession(source, label))
  })

  handle('companion:stop-session', (event) => {
    const refused = refuseUntrusted<SessionResult>(event)
    if (refused) return refused
    return wrap(() => backend.stopSession())
  })

  handle('companion:command', (event, ...args) => {
    const refused = refuseUntrusted<CommandResult>(event)
    if (refused) return refused
    const [type, payload] = args as unknown as [string, Record<string, unknown> | undefined]
    return wrap(() => backend.command(type, payload ?? {}))
  })

  handle('companion:submit-evidence', (event, ...args) => {
    const refused = refuseUntrusted<EvidenceResult>(event)
    if (refused) return refused
    const [text, evidenceId] = args as unknown as [string, string | undefined]
    return wrap(() => backend.submitEvidence(text, evidenceId))
  })

  handle('companion:draft', (event, ...args) => {
    const refused = refuseUntrusted<DraftArtifact>(event)
    if (refused) return refused
    const [kind, caseId] = args as unknown as ['section63' | 'helpline_1930', string]
    return wrap(() => backend.draft(kind, caseId))
  })

  handle('companion:workspace', (event, ...args) => {
    const refused = refuseUntrusted<WorkspaceSnapshot>(event)
    if (refused) return refused
    const [caseId] = args as unknown as [string | undefined]
    return wrap(() => backend.workspace(caseId))
  })

  handle('companion:list-cases', (event) => {
    const refused = refuseUntrusted<CaseSummary[]>(event)
    if (refused) return refused
    return wrap(() => backend.listCases())
  })

  handle('companion:check-clipboard', (event) => {
    const refused = refuseUntrusted<ClipboardCheck>(event)
    if (refused) return refused
    return wrap(async () => inspectClipboard(clipboard.readText()))
  })

  handle('companion:copy-text', (event, ...args) => {
    const refused = refuseUntrusted<null>(event)
    if (refused) return refused
    const [text] = args as unknown as [string]
    clipboard.writeText(text)
    return { ok: true, data: null }
  })

  handle('companion:open-workspace', (event, ...args) => {
    const refused = refuseUntrusted<null>(event)
    if (refused) return refused
    const [tab] = args as [string | undefined]
    deps.openWorkspace(tab)
    return { ok: true, data: null }
  })

  handle('companion:hide', (event) => {
    const refused = refuseUntrusted<null>(event)
    if (refused) return refused
    return deps.hideCompanion().then(() => ({ ok: true, data: null }))
  })

  handle('companion:quit', (event) => {
    const refused = refuseUntrusted<null>(event)
    if (refused) return refused
    return deps.quit().then(() => ({ ok: true, data: null }))
  })

  // ---- Finale window IPC (F02): fire-and-forget messages from the mascot/bubble windows ----
  const listen = (
    channel: string,
    listener: (event: IpcMainEvent, ...args: unknown[]) => void,
  ) => {
    ipcMain.removeAllListeners(channel)
    ipcMain.on(channel, listener)
  }

  listen('companion:set-click-through', (event, ...args) => {
    if (!trusted(event)) return
    const [through] = args as [boolean]
    deps.setClickThrough?.(Boolean(through))
  })

  listen('companion:toggle-screen-guard', (event) => {
    if (!trusted(event)) return
    deps.toggleScreenGuard?.()
  })

  listen('companion:drag-by', (event, ...args) => {
    if (!trusted(event)) return
    const [dx, dy] = args as [number, number]
    if (Number.isFinite(dx) && Number.isFinite(dy)) deps.dragBy?.(dx, dy)
  })

  listen('companion:drag-end', (event) => {
    if (!trusted(event)) return
    deps.dragEnd?.()
  })

  listen('companion:show-card', (event, ...args) => {
    if (!trusted(event)) return
    const [card] = args as [BubbleCard]
    if (card?.kind && card?.id) deps.showCard?.(card)
  })

  listen('companion:hide-card', (event, ...args) => {
    if (!trusted(event)) return
    const [cardId] = args as [string | undefined]
    deps.hideCard?.(cardId)
  })

  listen('companion:card-click', (event, ...args) => {
    if (!trusted(event)) return
    const [cardId, actionId] = args as [string, string]
    deps.relayCardAction?.(cardId, actionId)
  })

  listen('companion:resize-bubble', (event, ...args) => {
    if (!trusted(event)) return
    const [height] = args as [number]
    if (Number.isFinite(height) && height > 0) deps.resizeBubble?.(height)
  })

  handle('companion:set-user-mode', (event, ...args) => {
    const refused = refuseUntrusted<CompanionState>(event)
    if (refused) return refused
    const [mode] = args as [UserMode]
    if (!deps.setUserMode) return { ok: false, error: 'window manager is not ready' }
    return deps.setUserMode(mode)
  })

  handle('companion:get-prefs', (event) => {
    if (!trusted(event)) throw new Error('untrusted renderer')
    return deps.getPrefs?.() ?? {}
  })

  handle('companion:set-prefs', (event, ...args) => {
    if (!trusted(event)) throw new Error('untrusted renderer')
    const [patch] = args as [Partial<Prefs>]
    return deps.setPrefs?.(patch ?? {}) ?? {}
  })

  handle('companion:open-external', async (event, ...args) => {
    if (!trusted(event)) throw new Error('untrusted renderer')
    const [url] = args as [string]
    if (!isAllowedExternal(url)) throw new Error('link is not on the allow-list')
    await deps.openExternal?.(url)
  })

  // Keep app metadata available to the workspace without exposing Node to the renderer.
  handle('companion:app-version', (event) => {
    const refused = refuseUntrusted<string>(event)
    if (refused) return refused
    return { ok: true, data: app.getVersion() }
  })
}
