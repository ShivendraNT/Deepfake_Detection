/**
 * F10 loopback audio pipeline (ported from `extension/offscreen.js`).
 *
 * Graph: MediaStream → 16 kHz AudioContext → PCM worklet → windower → ONNX score → backend.
 * The same worklet frames are accumulated into 10-second mono 16-bit WAV chunks. A silent
 * zero-gain sink keeps the graph pulled without re-routing the call audio to the speakers.
 *
 * All network calls go to the local backend only (`127.0.0.1:8000`), exactly like the
 * extension's `/live/{call_id}/chunk` and `/live/{call_id}/voice` calls.
 */

import workletUrl from './lib/pcm_worklet.js?url'

import { createWindower, speechSeconds, type AudioWindow } from './lib/audio_window.js'
import { loadScorer, score } from './lib/onnx_scorer.js'
import { THRESHOLDS } from './lib/thresholds.js'
import { classifyWindows } from './lib/voice_rules.js'
import { encodeWav } from './wav'

export const API_BASE = 'http://127.0.0.1:8000'

const SAMPLE_RATE = 16000
const WINDOW_SECONDS = 5
const CHUNK_SECONDS = 10
const CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS
const LEVEL_INTERVAL_MS = 50 // 20 Hz
const REQUEST_TIMEOUT_MS = 15_000

interface VoiceWindowPayload {
  call_id: string
  window_index: number
  t_start_s: number
  t_end_s: number
  score: number
  speech_seconds: number
  model_version: string
}

let context: AudioContext | null = null
let sourceNode: MediaStreamAudioSourceNode | null = null
let workletNode: AudioWorkletNode | null = null
let analyserNode: AnalyserNode | null = null
let sinkNode: GainNode | null = null
let levelTimer: ReturnType<typeof setInterval> | null = null
let windower: ReturnType<typeof createWindower> | null = null

let activeCallId: string | null = null
let runId = 0
let scores: number[] = []
let speechTotal = 0
let windowQueue: Promise<void> = Promise.resolve()

let chunkQueue: Promise<void> = Promise.resolve()
let chunkIndex = 0
let chunkParts: Float32Array[] = []
let chunkLength = 0

let scorerPromise: Promise<boolean> | null = null
let scorerWarningSent = false

/**
 * The parity scorer expects `chrome.runtime.getURL` (it was written for the extension). In
 * Electron there is no `chrome.runtime`, so provide a tiny local URL resolver. The ONNX models
 * are not shipped in this repo; `loadScorer()` returns false and the pipeline abstains from
 * acoustic conclusions instead of inventing a score.
 */
function installChromeRuntimeShim(): void {
  try {
    const scope = globalThis as unknown as {
      chrome?: { runtime?: { getURL?: (path: string) => string } } & Record<string, unknown>
    }
    const chrome = scope.chrome ?? {}
    const runtime = chrome.runtime ?? {}
    if (typeof runtime.getURL !== 'function') {
      const base = import.meta.url.replace(/[^/]*$/, '')
      runtime.getURL = (path: string) => new URL(path.replace(/^\/+/, ''), base).href
      chrome.runtime = runtime
      scope.chrome = chrome
    }
  } catch {
    // A locked-down `chrome` global is fine: the scorer simply stays unavailable.
  }
}

function ensureScorer(): Promise<boolean> {
  if (!scorerPromise) {
    installChromeRuntimeShim()
    scorerPromise = loadScorer()
      .then((ready) => {
        if (!ready && !scorerWarningSent) {
          scorerWarningSent = true
          console.warn('[capture] voice scorer unavailable — voice windows will be skipped')
        }
        return ready
      })
      .catch((error: unknown) => {
        if (!scorerWarningSent) {
          scorerWarningSent = true
          console.warn('[capture] voice scorer unavailable', error)
        }
        return false
      })
  }
  return scorerPromise
}

function floatToPcm16(frames: Float32Array): Int16Array {
  const pcm = new Int16Array(frames.length)
  for (let index = 0; index < frames.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, frames[index]))
    pcm[index] = sample < 0 ? Math.round(sample * 0x8000) : Math.round(sample * 0x7fff)
  }
  return pcm
}

async function postChunk(callId: string, index: number, blob: Blob): Promise<void> {
  const form = new FormData()
  form.append('chunk_index', String(index))
  form.append('audio', blob, `chunk-${index}.wav`)
  const url = `${API_BASE}/live/${encodeURIComponent(callId)}/chunk?chunk_index=${index}`
  const response = await fetch(url, {
    method: 'POST',
    body: form,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  })
  if (!response.ok) throw new Error(`chunk ${index}: HTTP ${response.status}`)
}

async function postVoice(callId: string, windows: VoiceWindowPayload[]): Promise<void> {
  const response = await fetch(`${API_BASE}/live/${encodeURIComponent(callId)}/voice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(windows),
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  })
  if (!response.ok) throw new Error(`voice: HTTP ${response.status}`)
}

async function processWindow(win: AudioWindow, callId: string): Promise<void> {
  if (activeCallId !== callId) return
  const windowSpeech = speechSeconds(win.data, SAMPLE_RATE)
  speechTotal += windowSpeech

  // D5: no model means abstain. Chunks still upload; we never fabricate a voice score.
  const ready = await ensureScorer()
  if (!ready || activeCallId !== callId) return

  const windowScore = await score(win.data)
  if (activeCallId !== callId) return

  scores.push(windowScore)
  // The backend re-runs the authoritative rule; this local call mirrors the extension.
  void classifyWindows(scores, THRESHOLDS, speechTotal)

  await postVoice(callId, [
    {
      call_id: callId,
      window_index: win.windowIndex,
      t_start_s: win.t_start_s,
      t_end_s: win.t_end_s,
      score: windowScore,
      speech_seconds: windowSpeech,
      model_version: THRESHOLDS.modelVersion,
    },
  ])
}

function enqueueWindow(win: AudioWindow, callId: string): void {
  windowQueue = windowQueue
    .then(() => processWindow(win, callId))
    .catch((error: unknown) => console.warn('[capture] voice window failed', error))
}

function snapshotChunk(): Float32Array {
  const merged = new Float32Array(chunkLength)
  let offset = 0
  for (const part of chunkParts) {
    merged.set(part, offset)
    offset += part.length
  }
  return merged
}

function enqueueWav(callId: string, samples: Float32Array, label: string): void {
  const index = chunkIndex
  chunkIndex += 1
  const blob = encodeWav(floatToPcm16(samples), SAMPLE_RATE)
  chunkQueue = chunkQueue
    .then(() => postChunk(callId, index, blob))
    .catch((error: unknown) => console.warn(`[capture] ${label} ${index} failed`, error))
}

/** Accumulate worklet frames and emit one complete 10 s WAV at a time, in order. */
function appendChunkFrames(frames: Float32Array, callId: string): void {
  chunkParts.push(frames)
  chunkLength += frames.length

  while (chunkLength >= CHUNK_SAMPLES) {
    const merged = snapshotChunk()
    const complete = merged.slice(0, CHUNK_SAMPLES)
    const remainder = merged.slice(CHUNK_SAMPLES)
    chunkParts = remainder.length > 0 ? [remainder] : []
    chunkLength = remainder.length
    enqueueWav(callId, complete, 'chunk')
  }
}

function flushPartialChunk(callId: string): void {
  if (chunkLength === 0) return
  const partial = snapshotChunk()
  chunkParts = []
  chunkLength = 0
  enqueueWav(callId, partial, 'final chunk')
}

function startLevelMeter(analyser: AnalyserNode, onLevel?: (rms: number) => void): void {
  if (!onLevel) return
  const buffer = new Float32Array(analyser.fftSize)
  levelTimer = setInterval(() => {
    analyser.getFloatTimeDomainData(buffer)
    let sumSquares = 0
    for (let index = 0; index < buffer.length; index += 1) {
      sumSquares += buffer[index] * buffer[index]
    }
    const rms = Math.sqrt(sumSquares / buffer.length)
    onLevel(Math.min(1, Math.max(0, rms)))
  }, LEVEL_INTERVAL_MS)
}

/**
 * Start the loopback pipeline for one call. Replaces any previous pipeline; only the local
 * backend receives chunks and voice windows.
 */
export async function startPipeline(
  stream: MediaStream,
  callId: string,
  onLevel?: (rms: number) => void,
  onFrame?: () => void,
): Promise<void> {
  await stopPipeline()

  const myRun = ++runId
  activeCallId = callId
  scores = []
  speechTotal = 0
  windowQueue = Promise.resolve()
  chunkQueue = Promise.resolve()
  chunkIndex = 0
  chunkParts = []
  chunkLength = 0

  const ctx = new AudioContext({ sampleRate: SAMPLE_RATE })
  context = ctx

  try {
    if (ctx.state === 'suspended') await ctx.resume()
    await ctx.audioWorklet.addModule(workletUrl)
    if (myRun !== runId) {
      await ctx.close().catch(() => undefined)
      return
    }

    const mediaSource = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 2048
    analyser.smoothingTimeConstant = 0.2
    const sink = ctx.createGain()
    sink.gain.value = 0 // keep the graph pulled without echoing the call
    const pcmWorklet = new AudioWorkletNode(ctx, 'pcm-worklet', {
      channelCount: 1,
      channelCountMode: 'explicit',
    })

    sourceNode = mediaSource
    analyserNode = analyser
    sinkNode = sink
    workletNode = pcmWorklet
    windower = createWindower({ sampleRate: SAMPLE_RATE, windowSeconds: WINDOW_SECONDS })

    pcmWorklet.port.onmessage = (event: MessageEvent<Float32Array>) => {
      if (myRun !== runId || activeCallId !== callId) return
      const frames = event.data
      if (!(frames instanceof Float32Array) || frames.length === 0) return
      onFrame?.()

      appendChunkFrames(frames, callId)
      const windows = windower?.push(frames) ?? []
      for (const win of windows) enqueueWindow(win, callId)
    }

    mediaSource.connect(pcmWorklet)
    mediaSource.connect(analyser)
    analyser.connect(sink)
    pcmWorklet.connect(sink)
    sink.connect(ctx.destination)

    startLevelMeter(analyser, onLevel)
    void ensureScorer()
  } catch (error) {
    if (myRun === runId) await stopPipeline()
    throw error
  }
}

/** Stop the graph, release the context and send any remaining partial 10 s chunk. */
export async function stopPipeline(): Promise<void> {
  runId += 1
  const callId = activeCallId
  activeCallId = null

  if (levelTimer) {
    clearInterval(levelTimer)
    levelTimer = null
  }

  if (workletNode) {
    workletNode.port.onmessage = null
    try {
      workletNode.disconnect()
    } catch {
      // already disconnected
    }
  }
  if (sourceNode) {
    try {
      sourceNode.disconnect()
    } catch {
      // already disconnected
    }
  }
  if (analyserNode) {
    try {
      analyserNode.disconnect()
    } catch {
      // already disconnected
    }
  }
  if (sinkNode) {
    try {
      sinkNode.disconnect()
    } catch {
      // already disconnected
    }
  }

  const ctx = context
  workletNode = null
  sourceNode = null
  analyserNode = null
  sinkNode = null
  windower = null
  context = null

  if (callId) flushPartialChunk(callId)
  await chunkQueue.catch(() => undefined)

  if (ctx && ctx.state !== 'closed') {
    try {
      await ctx.close()
    } catch {
      // already closed
    }
  }

  scores = []
  speechTotal = 0
  chunkParts = []
  chunkLength = 0
  chunkIndex = 0
  windowQueue = Promise.resolve()
}
