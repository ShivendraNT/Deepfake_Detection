/**
 * CaptureApp — the hidden 1×1 capture window (`?view=capture`).
 *
 * It only ever asks for system audio through `getDisplayMedia`; the video track is stopped
 * immediately and never used. Start/stop can arrive from the companion event stream
 * (`call.started` / `call.stopped`) or from main over IPC. Telemetry goes back to main as
 * `capture:status`, `capture:level` and `capture:call-hint`.
 *
 * If the preload bridge does not expose these channels yet, every emitter no-ops safely.
 */

import { useEffect } from 'react'

import { api } from '../shared/api'
import { startPipeline, stopPipeline } from './pipeline'

const NO_AUDIO_TIMEOUT_MS = 3000
const WATCHDOG_INTERVAL_MS = 250

type CaptureBridge = {
  send?: (channel: string, payload?: unknown) => void
  sendCapture?: (channel: string, payload?: unknown) => void
  onCaptureStart?: (callback: (payload: unknown) => void) => unknown
  onCaptureStop?: (callback: () => void) => unknown
}

type IpcListener = (event: unknown, payload: unknown) => void

function errorOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function sendIpc(channel: string, payload?: unknown): void {
  const scope = window as unknown as {
    ipcRenderer?: { send?: (channel: string, ...args: unknown[]) => void }
    satyapan?: CaptureBridge
  }
  if (scope.ipcRenderer?.send) {
    scope.ipcRenderer.send(channel, payload)
    return
  }
  const bridge = scope.satyapan
  if (bridge?.sendCapture) bridge.sendCapture(channel, payload)
  else bridge?.send?.(channel, payload)
}

function onIpc(channel: string, handler: (payload: unknown) => void): () => void {
  const scope = window as unknown as {
    ipcRenderer?: {
      on?: (channel: string, listener: IpcListener) => void
      removeListener?: (channel: string, listener: IpcListener) => void
    }
  }
  const ipc = scope.ipcRenderer
  if (!ipc?.on) return () => undefined
  const listener: IpcListener = (_event, payload) => handler(payload)
  ipc.on(channel, listener)
  return () => ipc.removeListener?.(channel, listener)
}

function onBridge(
  method: 'onCaptureStart' | 'onCaptureStop',
  handler: (payload: unknown) => void,
): () => void {
  const bridge = (window as unknown as { satyapan?: CaptureBridge }).satyapan
  const subscribe = bridge?.[method]
  if (typeof subscribe !== 'function') return () => undefined
  const unsubscribe = (subscribe as (callback: (payload: unknown) => void) => unknown)(handler)
  return typeof unsubscribe === 'function' ? (unsubscribe as () => void) : () => undefined
}

function parseCallId(value: unknown): string | null {
  if (typeof value !== 'object' || value === null) return null
  const payload = value as { call_id?: unknown }
  if (typeof payload.call_id !== 'string' || payload.call_id.length === 0) return null
  return payload.call_id
}

/** Watching-mode VAD hook: forwards a call hint to main (no-op without a bridge). */
export function emitCallHint(hint: { source: 'loopback' } = { source: 'loopback' }): void {
  sendIpc('capture:call-hint', hint)
}

export default function CaptureApp(): JSX.Element {
  useEffect(() => {
    let disposed = false
    let token = 0
    let activeCallId: string | null = null
    let stream: MediaStream | null = null
    let watchdog: ReturnType<typeof setTimeout> | null = null
    let lastFrameAt = 0

    const clearWatchdog = (): void => {
      if (watchdog) {
        clearTimeout(watchdog)
        watchdog = null
      }
    }

    const releaseStream = (): void => {
      if (!stream) return
      for (const track of stream.getTracks()) track.stop()
      stream = null
    }

    const sendStatus = (status: string): void => {
      sendIpc('capture:status', status)
    }

    const sendError = (reason: string): void => {
      sendStatus(`error(${reason})`)
    }

    const stopCapture = async (notify = true): Promise<void> => {
      const hadCall = activeCallId !== null
      token += 1
      clearWatchdog()
      activeCallId = null
      await stopPipeline()
      releaseStream()
      if (notify && hadCall) {
        sendStatus('stopped')
        sendIpc('capture:stop', {})
      }
    }

    const armWatchdog = (myToken: number): void => {
      clearWatchdog()
      const tick = (): void => {
        if (disposed || myToken !== token || activeCallId === null) return
        if (Date.now() - lastFrameAt >= NO_AUDIO_TIMEOUT_MS) {
          sendError('no audio')
          void stopCapture(false)
          return
        }
        watchdog = setTimeout(tick, WATCHDOG_INTERVAL_MS)
      }
      watchdog = setTimeout(tick, WATCHDOG_INTERVAL_MS)
    }

    const startCapture = async (callId: string): Promise<void> => {
      if (disposed || !callId || activeCallId === callId) return
      await stopCapture(false)
      if (disposed) return

      const myToken = ++token
      activeCallId = callId
      lastFrameAt = Date.now()

      try {
        const media = navigator.mediaDevices?.getDisplayMedia
          ? await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })
          : null
        if (!media) throw new Error('system audio capture is unavailable')
        if (myToken !== token || disposed) {
          for (const track of media.getTracks()) track.stop()
          return
        }

        // Never use the video: stop it before anything else and keep audio only.
        for (const track of media.getVideoTracks()) track.stop()
        const audioTracks = media.getAudioTracks()
        if (audioTracks.length === 0) throw new Error('no system audio track')
        stream = new MediaStream(audioTracks)

        await startPipeline(
          stream,
          callId,
          (rms) => {
            if (myToken !== token) return
            sendIpc('capture:level', rms)
          },
          () => {
            if (myToken !== token) return
            lastFrameAt = Date.now()
          },
        )
        if (myToken !== token || disposed) return

        // Tell main only once the graph is live, so its 3 s watchdog is not tripped by setup.
        sendIpc('capture:start', { source: 'loopback', call_id: callId })
        sendStatus('capturing')
        lastFrameAt = Date.now()
        armWatchdog(myToken)
      } catch (error) {
        if (myToken !== token || disposed) return
        sendError(errorOf(error))
        await stopCapture(false)
      }
    }

    const offEvent = api.onEvent((event) => {
      if (event.type === 'call.started') {
        const callId = event.payload.call_id
        if (callId) void startCapture(callId)
      } else if (event.type === 'call.stopped') {
        void stopCapture()
      }
    })

    const offStart = onIpc('capture:start', (payload) => {
      const callId = parseCallId(payload)
      if (callId) void startCapture(callId)
    })
    const offStop = onIpc('capture:stop', () => {
      void stopCapture()
    })
    const offBridgeStart = onBridge('onCaptureStart', (payload) => {
      const callId = parseCallId(payload)
      if (callId) void startCapture(callId)
    })
    const offBridgeStop = onBridge('onCaptureStop', () => {
      void stopCapture()
    })

    return () => {
      disposed = true
      token += 1
      offEvent()
      offStart()
      offStop()
      offBridgeStart()
      offBridgeStop()
      clearWatchdog()
      void stopPipeline()
      releaseStream()
    }
  }, [])

  return <div data-view="capture" aria-hidden className="h-full w-full bg-transparent" />
}
