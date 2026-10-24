/**
 * Capture plumbing (F10, finale).
 *
 * Main owns the OS permission handshake: `getDisplayMedia` from the hidden capture window is
 * answered with the primary screen + `audio: 'loopback'` (system audio: the other person's
 * voice). The renderer stops the video track immediately. The microphone is never requested.
 *
 * The capture window reports status / loudness / speech activity over a narrow, sender-checked
 * IPC surface; main relays only what the mascot needs. Audio itself goes straight from the
 * capture window to the local engine (127.0.0.1:8000), never through main and never off-box.
 */

import { BrowserWindow, desktopCapturer, ipcMain, session, type IpcMainEvent } from 'electron'

import type { CaptureSourceKind } from '../shared/contracts'

export type CaptureCommand =
  | { action: 'start'; call_id: string; source: 'loopback' | 'replay'; replay_url?: string }
  | { action: 'stop' }

export interface CaptureStatus {
  state: 'starting' | 'capturing' | 'stopped' | 'error'
  reason?: string
  source?: CaptureSourceKind
  call_id?: string
}

export interface CaptureCallbacks {
  onStatus: (status: CaptureStatus) => void
  onLevel: (level: number) => void
  onSpeech: (active: boolean) => void
  onUtterance: (index: number) => void
}

function parseStatus(value: unknown): CaptureStatus | null {
  if (typeof value !== 'object' || value === null) return null
  const v = value as Record<string, unknown>
  if (v.state !== 'starting' && v.state !== 'capturing' && v.state !== 'stopped' && v.state !== 'error') return null
  return {
    state: v.state,
    reason: typeof v.reason === 'string' ? v.reason.slice(0, 200) : undefined,
    source: v.source === 'loopback' || v.source === 'replay' || v.source === 'extension' ? v.source : undefined,
    call_id: typeof v.call_id === 'string' ? v.call_id : undefined,
  }
}

let handlerInstalled = false

/** Answer getDisplayMedia with the screen + system-audio loopback. Never the microphone. */
export function installDisplayMediaHandler(): void {
  if (handlerInstalled) return
  handlerInstalled = true
  session.defaultSession.setDisplayMediaRequestHandler(async (_request, callback) => {
    try {
      const [source] = await desktopCapturer.getSources({ types: ['screen'], thumbnailSize: { width: 0, height: 0 } })
      if (!source) {
        callback({})
        return
      }
      callback({ video: source, audio: 'loopback' })
    } catch {
      callback({})
    }
  })
}

/**
 * Wire the hidden capture window. Only that window may report capture telemetry.
 * Re-registering replaces the previous listeners.
 */
export function registerCapture(window: BrowserWindow, callbacks: CaptureCallbacks): void {
  installDisplayMediaHandler()
  const trusted = (event: IpcMainEvent): boolean =>
    !window.isDestroyed() && event.sender === window.webContents

  const channels: Array<[string, (event: IpcMainEvent, payload: unknown) => void]> = [
    [
      'capture:status',
      (event, payload) => {
        if (!trusted(event)) return
        const status = parseStatus(payload)
        if (status) callbacks.onStatus(status)
      },
    ],
    [
      'capture:level',
      (event, payload) => {
        if (!trusted(event) || typeof payload !== 'number' || !Number.isFinite(payload)) return
        callbacks.onLevel(Math.max(0, Math.min(1, payload)))
      },
    ],
    [
      'capture:speech',
      (event, payload) => {
        if (trusted(event) && typeof payload === 'boolean') callbacks.onSpeech(payload)
      },
    ],
    [
      'capture:utterance',
      (event, payload) => {
        if (!trusted(event) || typeof payload !== 'object' || payload === null) return
        const index = (payload as { index?: unknown }).index
        if (typeof index === 'number') callbacks.onUtterance(index)
      },
    ],
  ]
  for (const [channel, listener] of channels) {
    ipcMain.removeAllListeners(channel)
    ipcMain.on(channel, listener)
  }
  window.once('closed', () => {
    for (const [channel] of channels) ipcMain.removeAllListeners(channel)
  })
}

export function sendCaptureCommand(window: BrowserWindow | null, command: CaptureCommand): void {
  if (!window || window.isDestroyed() || window.webContents.isDestroyed()) return
  try {
    window.webContents.send('capture:command', command)
  } catch {
    // The window is going away; capture stops with it.
  }
}
