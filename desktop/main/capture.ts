/**
 * F10 capture foundation — system-audio loopback only.
 *
 * The hidden capture window owns the audio graph. Main owns the OS permission handshake and
 * relays the renderer's low-rate telemetry (level, VAD hint, status) to the mascot/bubble shell.
 * We never request the microphone: `getDisplayMedia` is answered with a screen source plus
 * `audio: 'loopback'`, and the renderer stops the video track after the grant.
 *
 * There is no network code here. The capture renderer posts only to the local backend
 * (`127.0.0.1:8000`) through the preload bridge in a later step.
 */

import {
  BrowserWindow,
  desktopCapturer,
  ipcMain,
  session,
  type IpcMainEvent,
} from 'electron'

import type { CaptureSourceKind } from '../shared/contracts'
import type { BackendClient } from './backend'

const NO_AUDIO_TIMEOUT_MS = 3000

interface CaptureStart {
  source: CaptureSourceKind
  call_id: string
}

type CaptureStatus =
  | { state: 'capturing' }
  | { state: 'stopped' }
  | { state: 'error'; reason: string }

function isCaptureSourceKind(value: unknown): value is CaptureSourceKind {
  return value === 'extension' || value === 'loopback' || value === 'replay'
}

function parseStart(value: unknown): CaptureStart | null {
  if (typeof value !== 'object' || value === null) return null
  const start = value as { source?: unknown; call_id?: unknown }
  if (!isCaptureSourceKind(start.source)) return null
  if (typeof start.call_id !== 'string' || start.call_id.length === 0) return null
  return { source: start.source, call_id: start.call_id }
}

/** Accept `'capturing' | 'stopped' | 'error(reason)'` and the object form `{ state, reason }`. */
function parseStatus(value: unknown): CaptureStatus | null {
  if (value === 'capturing') return { state: 'capturing' }
  if (value === 'stopped') return { state: 'stopped' }
  if (typeof value === 'string') {
    const match = /^error(?:\(|:)\s*(.*?)\)?$/i.exec(value)
    if (match) return { state: 'error', reason: match[1] || 'capture error' }
    return null
  }
  if (typeof value !== 'object' || value === null) return null
  const status = value as { state?: unknown; reason?: unknown }
  if (status.state === 'capturing') return { state: 'capturing' }
  if (status.state === 'stopped') return { state: 'stopped' }
  if (status.state === 'error') {
    return {
      state: 'error',
      reason: typeof status.reason === 'string' ? status.reason : 'capture error',
    }
  }
  return null
}

function parseCallHint(value: unknown): { source: CaptureSourceKind } {
  if (typeof value === 'object' && value !== null) {
    const source = (value as { source?: unknown }).source
    if (isCaptureSourceKind(source)) return { source }
  }
  return { source: 'loopback' }
}

function clampLevel(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.min(1, Math.max(0, value))
}

/**
 * Register the capture window's OS permission handler and its narrow IPC surface.
 *
 * Called once by `main/index.ts` when the user first enters Watching. Registering again
 * replaces the handler/listeners rather than stacking them.
 */
export function registerCapture(options: {
  window: BrowserWindow
  backend: BackendClient
}): void {
  const { window, backend } = options

  // F10 spike: answer getDisplayMedia with the primary screen + system audio loopback.
  // No microphone is ever offered, and no window/video source is exposed to the renderer.
  session.defaultSession.setDisplayMediaRequestHandler(async (_request, callback) => {
    try {
      const sources = await desktopCapturer.getSources({ types: ['screen'] })
      const [source] = sources
      if (!source) {
        callback({})
        return
      }
      callback({ video: source, audio: 'loopback' })
    } catch {
      callback({})
    }
  })

  let active: CaptureStart | null = null
  let watchdog: ReturnType<typeof setTimeout> | null = null
  let failureReported = false

  const clearWatchdog = (): void => {
    if (watchdog) {
      clearTimeout(watchdog)
      watchdog = null
    }
  }

  const sendToCapture = (channel: string, payload: unknown): void => {
    if (window.isDestroyed() || window.webContents.isDestroyed()) return
    try {
      window.webContents.send(channel, payload)
    } catch {}
  }

  const broadcastToShell = (channel: string, payload: unknown): void => {
    for (const other of BrowserWindow.getAllWindows()) {
      if (
        other === window ||
        other.isDestroyed() ||
        other.webContents.isDestroyed() ||
        other.webContents.isLoading()
      ) {
        continue
      }
      try {
        other.webContents.send(channel, payload)
      } catch {}
    }
  }

  /** Any level packet proves samples are flowing, even when the call is silent (RMS 0). */
  const armWatchdog = (): void => {
    clearWatchdog()
    watchdog = setTimeout(() => {
      failCapture('no audio samples for 3 s')
    }, NO_AUDIO_TIMEOUT_MS)
  }

  /**
   * Fail closed: stop the consented session, ask the capture window to release its tracks,
   * and tell the shell to show Sleeping with a toast. There is no auto-restart.
   */
  const failCapture = (reason: string): void => {
    if (failureReported) return
    failureReported = true
    clearWatchdog()
    active = null
    sendToCapture('capture:stop', { reason })
    broadcastToShell('companion:capture-status', {
      state: 'error',
      reason,
      sleeping: true,
      toast: 'toast.capture_error',
    })
    void backend.stopSession().catch(() => undefined)
  }

  const trusted = (event: IpcMainEvent): boolean => {
    // Only the hidden capture window may drive the capture session.
    return !window.isDestroyed() && event.sender === window.webContents
  }

  const onStart = (event: IpcMainEvent, payload: unknown): void => {
    if (!trusted(event)) return
    const start = parseStart(payload)
    if (!start) return
    failureReported = false
    active = start
    armWatchdog()
    broadcastToShell('companion:capture-status', { state: 'capturing', ...start })
  }

  const onStop = (event: IpcMainEvent): void => {
    if (!trusted(event)) return
    clearWatchdog()
    active = null
    // A normal stop must not mask the error/toast that triggered a fail-closed stop.
    if (!failureReported) broadcastToShell('companion:capture-status', { state: 'stopped' })
  }

  const onLevel = (event: IpcMainEvent, value: unknown): void => {
    if (!trusted(event) || typeof value !== 'number' || !active) return
    // 0..1 RMS, 20 Hz. Local only; it is never sent to the backend.
    armWatchdog()
    broadcastToShell('companion:audio-level', clampLevel(value))
  }

  const onCallHint = (event: IpcMainEvent, value: unknown): void => {
    if (!trusted(event)) return
    broadcastToShell('companion:call-hint', parseCallHint(value))
  }

  const onStatus = (event: IpcMainEvent, value: unknown): void => {
    if (!trusted(event)) return
    const status = parseStatus(value)
    if (!status) return
    if (status.state === 'capturing') {
      armWatchdog()
      return
    }
    if (status.state === 'stopped') {
      clearWatchdog()
      active = null
      if (!failureReported) broadcastToShell('companion:capture-status', { state: 'stopped' })
      return
    }
    failCapture(status.reason)
  }

  const channels: Array<[string, (event: IpcMainEvent, ...args: unknown[]) => void]> = [
    ['capture:start', onStart],
    ['capture:stop', onStop],
    ['capture:level', onLevel],
    ['capture:call-hint', onCallHint],
    ['capture:status', onStatus],
  ]

  for (const [channel, listener] of channels) {
    ipcMain.removeAllListeners(channel)
    ipcMain.on(channel, listener)
  }

  window.once('closed', () => {
    clearWatchdog()
    active = null
    for (const [channel] of channels) ipcMain.removeAllListeners(channel)
  })
}
