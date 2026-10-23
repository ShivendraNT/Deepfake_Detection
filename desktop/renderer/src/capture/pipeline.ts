/**
 * Loopback audio pipeline (F10, finale: utterance segmentation).
 *
 * Graph: MediaStream → 16 kHz AudioContext → PCM worklet → (a) utterance segmenter → WAV →
 * `/live/{call_id}/chunk`, and (b) 5 s windower → ONNX voice score → `/live/{call_id}/voice`
 * (only when the voice model files are installed). A silent zero-gain sink keeps the graph
 * pulled without re-routing the call audio to the speakers.
 *
 * Utterances are cut at the other person's pauses (see segmenter.ts), so a caption and its
 * chips arrive about a second after they finish a sentence instead of up to 13 s later.
 * All network calls go to the local backend only (`127.0.0.1:8000`).
 */

import workletUrl from './lib/pcm_worklet.js?url'

import { createWindower, speechSeconds, type AudioWindow } from './lib/audio_window.js'
import { loadScorer, score } from './lib/onnx_scorer.js'
import { THRESHOLDS } from './lib/thresholds.js'
import { classifyWindows } from './lib/voice_rules.js'
import { UtteranceSegmenter, type Utterance } from './segmenter'
import { encodeWav } from './wav'

export const API_BASE = 'http://127.0.0.1:8000'

const SAMPLE_RATE = 16000
const WINDOW_SECONDS = 5
const LEVEL_INTERVAL_MS = 50 // 20 Hz
const REQUEST_TIMEOUT_MS = 30_000

export interface PipelineHooks {
  onLevel?: (rms: number) => void
  onFrame?: () => void
  /** The other person started (true) or stopped (false) speaking. */
  onSpeech?: (active: boolean) => void
  /** An utterance was sent to the speech engine (for a "transcribing…" hint). */
  onUtterance?: (info: { index: number; tStart: number; tEnd: number }) => void
  /** The backend no longer knows this call (stopped elsewhere): stop capturing. */
  onCallGone?: () => void
  /** The local engine stopped answering (crashed or closed): fail closed, never "listen" deaf. */
  onEngineLost?: () => void
}

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
let chunkFailures = 0
let runId = 0
let scores: number[] = []
let speechTotal = 0
let windowQueue: Promise<void> = Promise.resolve()

let chunkQueue: Promise<void> = Promise.resolve()
let segmenter: UtteranceSegmenter | null = null
let hooks: PipelineHooks = {}

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

class CallGoneError extends Error {}

async function postChunk(callId: string, utterance: Utterance, blob: Blob): Promise<void> {
  const form = new FormData()
  form.append('chunk_index', String(utterance.index))
  form.append('t_start_s', utterance.tStart.toFixed(2))
  form.append('t_end_s', utterance.tEnd.toFixed(2))
  form.append('audio', blob, `utterance-${utterance.index}.wav`)
  const url = `${API_BASE}/live/${encodeURIComponent(callId)}/chunk`
  const response = await fetch(url, {
    method: 'POST',
    body: form,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  })
  if (response.status === 404) throw new CallGoneError(`call ${callId} is no longer active`)
  if (!response.ok) throw new Error(`utterance ${utterance.index}: HTTP ${response.status}`)
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

/** Encode one utterance and post it, strictly in order (the engine runs one at a time). */
function enqueueUtterance(callId: string, utterance: Utterance): void {
  const blob = encodeWav(floatToPcm16(utterance.samples), SAMPLE_RATE)
  hooks.onUtterance?.({ index: utterance.index, tStart: utterance.tStart, tEnd: utterance.tEnd })
  chunkQueue = chunkQueue
    .then(async () => {
      await postChunk(callId, utterance, blob)
      chunkFailures = 0
    })
    .catch((error: unknown) => {
      if (error instanceof CallGoneError) {
        if (activeCallId === callId) hooks.onCallGone?.()
        return
      }
      console.warn(`[capture] utterance ${utterance.index} failed`, error)
      chunkFailures += 1
      if (chunkFailures >= 2 && activeCallId === callId) hooks.onEngineLost?.()
    })
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
  callbacks: PipelineHooks = {},
): Promise<void> {
  await stopPipeline()

  const myRun = ++runId
  activeCallId = callId
  chunkFailures = 0
  hooks = callbacks
  scores = []
  speechTotal = 0
  windowQueue = Promise.resolve()
  chunkQueue = Promise.resolve()
  segmenter = new UtteranceSegmenter(
    (utterance) => {
      if (myRun === runId && activeCallId === callId) enqueueUtterance(callId, utterance)
    },
    {},
    (active) => {
      if (myRun === runId) hooks.onSpeech?.(active)
    },
  )

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
      hooks.onFrame?.()

      segmenter?.push(frames)
      const windows = windower?.push(frames) ?? []
      for (const win of windows) enqueueWindow(win, callId)
    }

    mediaSource.connect(pcmWorklet)
    mediaSource.connect(analyser)
    analyser.connect(sink)
    pcmWorklet.connect(sink)
    sink.connect(ctx.destination)

    startLevelMeter(analyser, hooks.onLevel)
    void ensureScorer()
  } catch (error) {
    if (myRun === runId) await stopPipeline()
    throw error
  }
}

/** Stop the graph, release the context and send the utterance in progress, if any. */
export async function stopPipeline(): Promise<void> {
  // The last sentence before "stop" still gets transcribed (flush while the run is current).
  const finalSegmenter = segmenter
  segmenter = null
  finalSegmenter?.flush()
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
  hooks = {}
  windowQueue = Promise.resolve()
}
