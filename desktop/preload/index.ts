/**
 * The ONLY preload bridge (T25). No Node, no filesystem, no arbitrary IPC: a narrow typed API.
 */

import { contextBridge, ipcRenderer, type IpcRendererEvent } from 'electron'

import type {
  AppConfig,
  BridgeResult,
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
  SessionResult,
  TrayRequest,
  WorkspaceSnapshot,
} from '../shared/contracts'

function subscribe<T>(channel: string, callback: (payload: T) => void): () => void {
  const listener = (_event: IpcRendererEvent, payload: T) => callback(payload)
  ipcRenderer.on(channel, listener)
  return () => ipcRenderer.removeListener(channel, listener)
}

const api: CompanionBridge = {
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
  openWorkspace: () => ipcRenderer.invoke('companion:open-workspace') as Promise<void>,
  hideCompanion: () =>
    ipcRenderer.invoke('companion:hide') as Promise<BridgeResult<null>>,
  quit: () => ipcRenderer.invoke('companion:quit') as Promise<BridgeResult<null>>,
  onEvent: (callback) => subscribe<CompanionEvent>('companion:event', callback),
  onConnection: (callback) => subscribe<ConnectionStatus>('companion:connection', callback),
  onTrayRequest: (callback) => subscribe<TrayRequest>('companion:tray-request', callback),
  onHotkey: (callback) => subscribe<string>('companion:hotkey', callback),
}

contextBridge.exposeInMainWorld('satyapan', api)
