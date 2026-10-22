/**
 * F10 replay fallback for the stage demo.
 *
 * Decodes a WAV (or any supported media) at 16 kHz, feeds it into the same `startPipeline`
 * graph through a MediaStream, and always labels the session
 * `DEMO REPLAY — NOT LIVE CAPTURE`. Nothing is uploaded except the normal local `/live` chunks.
 */

import { startPipeline, stopPipeline } from './pipeline'

export const REPLAY_LABEL = 'DEMO REPLAY — NOT LIVE CAPTURE'

const SAMPLE_RATE = 16000
const REQUEST_TIMEOUT_MS = 15_000

export interface ReplayStatus {
  state: 'capturing' | 'stopped' | 'error'
  label: typeof REPLAY_LABEL
  reason?: string
}

export interface ReplayOptions {
  onLevel?: (rms: number) => void
  onStatus?: (status: ReplayStatus) => void
}

let replayContext: AudioContext | null = null
let replaySource: AudioBufferSourceNode | null = null
let replayRun = 0

function errorOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

async function loadAudioBytes(source: Blob | ArrayBuffer | string): Promise<ArrayBuffer> {
  if (typeof source === 'string') {
    const response = await fetch(source, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) })
    if (!response.ok) throw new Error(`replay fixture: HTTP ${response.status}`)
    return response.arrayBuffer()
  }
  if (source instanceof ArrayBuffer) return source.slice(0)
  return source.arrayBuffer()
}

/**
 * Start a labelled replay through the real pipeline. `source` may be a Blob/File, raw bytes,
 * or a local fixture URL. A new replay replaces any previous one.
 */
export async function startReplay(
  source: Blob | ArrayBuffer | string,
  callId: string,
  options: ReplayOptions = {},
): Promise<void> {
  await stopReplay(false)
  const run = ++replayRun
  options.onStatus?.({ state: 'capturing', label: REPLAY_LABEL })

  try {
    const bytes = await loadAudioBytes(source)
    if (run !== replayRun) return

    const ctx = new AudioContext({ sampleRate: SAMPLE_RATE })
    replayContext = ctx
    if (ctx.state === 'suspended') await ctx.resume()

    // The context is 16 kHz, so decodeAudioData resamples the fixture to 16 kHz mono.
    const decoded = await ctx.decodeAudioData(bytes)
    if (run !== replayRun) {
      await ctx.close().catch(() => undefined)
      return
    }

    const destination = ctx.createMediaStreamDestination()
    const node = ctx.createBufferSource()
    node.buffer = decoded
    node.connect(destination)
    replaySource = node
    node.onended = () => {
      void stopReplay(true, options)
    }

    await startPipeline(destination.stream, callId, options.onLevel)
    if (run !== replayRun) return

    if (ctx.state === 'suspended') await ctx.resume()
    node.start()
  } catch (error) {
    if (run !== replayRun) return
    options.onStatus?.({ state: 'error', label: REPLAY_LABEL, reason: errorOf(error) })
    await stopReplay(false)
  }
}

/** Stop the replay, release the buffer/context and send any remaining partial chunk. */
export async function stopReplay(
  notify = true,
  options: ReplayOptions = {},
): Promise<void> {
  replayRun += 1

  const node = replaySource
  replaySource = null
  if (node) {
    node.onended = null
    try {
      node.stop()
    } catch {
      // already ended
    }
    try {
      node.disconnect()
    } catch {
      // already disconnected
    }
  }

  await stopPipeline()

  const ctx = replayContext
  replayContext = null
  if (ctx && ctx.state !== 'closed') {
    try {
      await ctx.close()
    } catch {
      // already closed
    }
  }

  if (notify) options.onStatus?.({ state: 'stopped', label: REPLAY_LABEL })
}
