/**
 * The ONLY preload bridge (T25). No Node, no filesystem, no arbitrary IPC: a narrow typed API.
 */

import { contextBridge, ipcRenderer, type IpcRendererEvent } from 'electron'

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
  ReportOptions,
  SatyaSignal,
  Scopes,
  SessionResult,
  TrayRequest,
  UserMode,
  WorkspaceSnapshot,
} from '../shared/contracts'

/** Channels the hidden capture window may send on. Nothing else crosses from it. */
const CAPTURE_CHANNELS = new Set(['capture:status', 'capture:level', 'capture:speech', 'capture:utterance'])

function subscribe<T>(channel: string, callback: (payload: T) => void): () => void {
  const listener = (_event: IpcRendererEvent, payload: T) => callback(payload)
  ipcRenderer.on(channel, listener)
  return () => ipcRenderer.removeListener(channel, listener)
}

const api: CompanionBridge & {
  onWorkspaceNavigate: (callback: (tab: string) => void) => () => void
  workspaceReady: () => void
  submitLastScreenText: () => Promise<BridgeResult<EvidenceResult>>
  sendCapture: (channel: string, payload?: unknown) => void
  onCaptureCommand: (callback: (command: unknown) => void) => () => void
} = {
  getConfig: () => ipcRenderer.invoke('companion:get-config') as Promise<AppConfig>,
  getState: () =>
    ipcRenderer.invoke('companion:get-state') as Promise<BridgeResult<CompanionState>>,
  startSession: (source: CompanionSource, label?: string) =>
    ipcRenderer.invoke('companion:start-session', source, label) as Promise<
      BridgeResult<SessionResult>
    >,
  stopSession: () => ipcRenderer.invoke('companion:stop-session') as Promise<BridgeResult<SessionResult>>,
  command: (type: string, payload: Record<string, unknown> = {}) =>
    ipcRenderer.invoke('companion:command', type, payload) as Promise<BridgeResult<CommandResult>>,
  submitEvidence: (text: string, evidenceId?: string) =>
    ipcRenderer.invoke('companion:submit-evidence', text, evidenceId) as Promise<
      BridgeResult<EvidenceResult>
    >,
  submitFile: (
    filename: string,
    mediaType: string,
    bytes: ArrayBuffer,
    caseId?: string | null,
  ) =>
    ipcRenderer.invoke('companion:submit-file', filename, mediaType, bytes, caseId) as Promise<
      BridgeResult<EvidenceResult>
    >,
  draft: (kind: 'section63' | 'helpline_1930', caseId: string) =>
    ipcRenderer.invoke('companion:draft', kind, caseId) as Promise<BridgeResult<DraftArtifact>>,
  workspace: (caseId?: string) =>
    ipcRenderer.invoke('companion:workspace', caseId) as Promise<BridgeResult<WorkspaceSnapshot>>,
  listCases: () =>
    ipcRenderer.invoke('companion:list-cases') as Promise<BridgeResult<CaseSummary[]>>,
  checkClipboard: () =>
    ipcRenderer.invoke('companion:check-clipboard') as Promise<BridgeResult<ClipboardCheck>>,
  copyText: (text: string) =>
    ipcRenderer.invoke('companion:copy-text', text) as Promise<BridgeResult<null>>,
  openWorkspace: (tab?: string) =>
    ipcRenderer.invoke('companion:open-workspace', tab) as Promise<void>,
  hideCompanion: () =>
    ipcRenderer.invoke('companion:hide') as Promise<BridgeResult<null>>,
  quit: () => ipcRenderer.invoke('companion:quit') as Promise<BridgeResult<null>>,
  onEvent: (callback) => subscribe<CompanionEvent>('companion:event', callback),
  onConnection: (callback) => subscribe<ConnectionStatus>('companion:connection', callback),
  onTrayRequest: (callback) => subscribe<TrayRequest>('companion:tray-request', callback),
  onHotkey: (callback) => subscribe<string>('companion:hotkey', callback),

  // ---- Finale window IPC (F01/F02) ----
  setClickThrough: (through: boolean) => ipcRenderer.send('companion:set-click-through', through),
  dragBy: (dx: number, dy: number) => ipcRenderer.send('companion:drag-by', dx, dy),
  dragEnd: () => ipcRenderer.send('companion:drag-end'),
  onCursor: (callback) =>
    subscribe<{ dx: number; dy: number; near: boolean }>('companion:cursor', callback),
  showCard: (card: BubbleCard) => ipcRenderer.send('companion:show-card', card),
  hideCard: (cardId?: string) => ipcRenderer.send('companion:hide-card', cardId),
  onCardAction: (callback) =>
    subscribe<{ card_id: string; action_id: string }>('companion:card-action', callback),
  showBubble: (card: BubbleCard) => ipcRenderer.send('companion:show-card', card),
  hideBubble: () => ipcRenderer.send('companion:hide-card'),
  onCard: (callback) =>
    subscribe<{ card: BubbleCard | null; tail: 'left' | 'right' }>('companion:card', (payload) =>
      callback(payload.card, payload.tail),
    ),
  cardAction: (cardId: string, actionId: string) =>
    ipcRenderer.send('companion:card-click', cardId, actionId),
  resizeBubble: (height: number) => ipcRenderer.send('companion:resize-bubble', height),
  setUserMode: (mode: UserMode, scopes?: Scopes) =>
    ipcRenderer.invoke('companion:set-user-mode', mode, scopes) as Promise<BridgeResult<CompanionState>>,
  getPrefs: () => ipcRenderer.invoke('companion:get-prefs') as Promise<Prefs>,
  setPrefs: (patch: Partial<Prefs>) =>
    ipcRenderer.invoke('companion:set-prefs', patch) as Promise<Prefs>,
  openExternal: (url: string) =>
    ipcRenderer.invoke('companion:open-external', url) as Promise<void>,
  // ---- Finale: calls, OOB, reports, screen/clipboard checks, readiness, local signals ----
  startCall: (source) => ipcRenderer.invoke('companion:start-call', source ?? 'loopback'),
  stopCall: () => ipcRenderer.invoke('companion:stop-call'),
  requestOob: (caseId: string) => ipcRenderer.invoke('companion:request-oob', caseId),
  reportPack: (caseId: string, options?: ReportOptions) =>
    ipcRenderer.invoke('companion:report-pack', caseId, options),
  scanScreen: () => ipcRenderer.invoke('companion:scan-screen'),
  checkClipboardText: () => ipcRenderer.invoke('companion:check-clipboard-text'),
  submitLastScreenText: () =>
    ipcRenderer.invoke('companion:submit-last-screen-text') as Promise<BridgeResult<EvidenceResult>>,
  getHealth: () => ipcRenderer.invoke('companion:get-health'),
  setScopes: (scopes: Scopes) => ipcRenderer.invoke('companion:set-scopes', scopes),
  onSignal: (callback) => subscribe<SatyaSignal>('satya:signal', callback),
  sendCapture: (channel: string, payload?: unknown) => {
    if (CAPTURE_CHANNELS.has(channel)) ipcRenderer.send(channel, payload)
  },
  onCaptureCommand: (callback) => subscribe<unknown>('capture:command', callback),
  onWorkspaceNavigate: (callback) => subscribe<string>('companion:navigate-workspace', callback),
  workspaceReady: () => ipcRenderer.send('companion:workspace-ready'),
}

contextBridge.exposeInMainWorld('satyapan', api)
