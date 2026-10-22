/**
 * F10 in-memory call detector (VAD) for Watching mode.
 *
 * It only looks at the last 10 seconds of float samples in RAM. It never records, transcribes
 * or uploads anything: the only thing that leaves this module is the `onCallHint` callback
 * (`{ source: 'loopback' }`), which the capture window forwards to main.
 */

import { speechSeconds } from './lib/audio_window.js'

export const VAD_SAMPLE_RATE = 16000
export const VAD_WINDOW_SECONDS = 10
export const VAD_SPEECH_TRIGGER_SECONDS = 3
export const VAD_COOLDOWN_MS = 30_000

const CHECK_INTERVAL_MS = 250
const MAX_SAMPLES = VAD_SAMPLE_RATE * VAD_WINDOW_SECONDS

export interface CallHint {
  source: 'loopback'
}

export type OnCallHint = (hint: CallHint) => void

/**
 * Sliding-window speech detector. Push the same Float32 worklet frames used by the pipeline;
 * when the last 10 s contain >= 3 s of speech, fire once and then stay quiet for 30 s.
 */
export class CallHintDetector {
  private parts: Float32Array[] = []
  private buffered = 0
  private lastCheckAt = 0
  private lastHintAt: number | null = null

  constructor(
    private readonly onHint: OnCallHint,
    private readonly now: () => number = () => Date.now(),
  ) {}

  push(frames: Float32Array): CallHint | null {
    if (!(frames instanceof Float32Array) || frames.length === 0) return null

    this.append(frames)
    const at = this.now()
    if (at - this.lastCheckAt < CHECK_INTERVAL_MS) return null
    this.lastCheckAt = at

    // After a hint, ignore further hints (but keep the rolling window current).
    if (this.lastHintAt !== null && at - this.lastHintAt < VAD_COOLDOWN_MS) return null

    const speech = speechSeconds(this.snapshot(), VAD_SAMPLE_RATE)
    if (speech < VAD_SPEECH_TRIGGER_SECONDS) return null

    this.lastHintAt = at
    this.parts = []
    this.buffered = 0
    const hint: CallHint = { source: 'loopback' }
    this.onHint(hint)
    return hint
  }

  /** Clear the rolling window and the cooldown (e.g. when Watching stops). */
  reset(): void {
    this.parts = []
    this.buffered = 0
    this.lastCheckAt = 0
    this.lastHintAt = null
  }

  private append(frames: Float32Array): void {
    this.parts.push(frames)
    this.buffered += frames.length

    while (this.buffered > MAX_SAMPLES && this.parts.length > 0) {
      const first = this.parts[0]
      const excess = this.buffered - MAX_SAMPLES
      if (first.length <= excess) {
        this.parts.shift()
        this.buffered -= first.length
      } else {
        this.parts[0] = first.subarray(excess)
        this.buffered -= excess
      }
    }
  }

  private snapshot(): Float32Array {
    const merged = new Float32Array(this.buffered)
    let offset = 0
    for (const part of this.parts) {
      merged.set(part, offset)
      offset += part.length
    }
    return merged
  }
}

export function createCallHintDetector(
  onHint: OnCallHint,
  now?: () => number,
): CallHintDetector {
  return new CallHintDetector(onHint, now)
}
