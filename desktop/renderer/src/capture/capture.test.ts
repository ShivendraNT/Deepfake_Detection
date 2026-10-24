/**
 * F10 unit tests: WAV encoding, Watching-mode VAD, and the replay contract.
 *
 * These tests are deliberately DOM-free. `wav.ts` only uses Blob/DataView (provided by Node),
 * `vad.ts` uses plain Float32 arrays with an injected clock, and the replay contract test mocks
 * the pipeline so no AudioContext / AudioWorklet / ONNX globals are touched.
 */

import { describe, expect, it, vi } from 'vitest'

import { CallHintDetector } from './vad'
import { encodeWav } from './wav'
import { REPLAY_LABEL } from './replay'

vi.mock('./pipeline', () => ({
  startPipeline: vi.fn(),
  stopPipeline: vi.fn(),
}))

const SAMPLE_RATE = 16_000

function ascii(buffer: ArrayBuffer, offset: number, length: number): string {
  return new TextDecoder().decode(new Uint8Array(buffer, offset, length))
}

function tone(seconds: number, amplitude = 0.5): Float32Array {
  const length = Math.round(seconds * SAMPLE_RATE)
  const frames = new Float32Array(length)
  for (let index = 0; index < length; index += 1) {
    frames[index] = amplitude * Math.sin((2 * Math.PI * 220 * index) / SAMPLE_RATE)
  }
  return frames
}

function silence(seconds: number): Float32Array {
  return new Float32Array(Math.round(seconds * SAMPLE_RATE))
}

function noise(seconds: number, amplitude = 0.001): Float32Array {
  const length = Math.round(seconds * SAMPLE_RATE)
  const frames = new Float32Array(length)
  for (let index = 0; index < length; index += 1) {
    frames[index] = amplitude * Math.sin((2 * Math.PI * 997 * index) / SAMPLE_RATE)
  }
  return frames
}

function vadHarness(): {
  detector: CallHintDetector
  onHint: ReturnType<typeof vi.fn>
  pushSpeech: (seconds: number) => void
  pushSilence: (seconds: number) => void
  pushNoise: (seconds: number) => void
  advance: (ms: number) => void
} {
  let clock = 0
  const onHint = vi.fn()
  const detector = new CallHintDetector(onHint, () => clock)

  const pushFrames = (frames: Float32Array, seconds: number): void => {
    // 50 ms pieces keep the injected clock aligned with the detector's 250 ms check cadence.
    const step = Math.max(1, Math.round(0.05 * SAMPLE_RATE))
    let offset = 0
    while (offset < frames.length) {
      const end = Math.min(offset + step, frames.length)
      clock += ((end - offset) / SAMPLE_RATE) * 1000
      detector.push(frames.subarray(offset, end))
      offset = end
    }
    // Keep the clock honest when rounding produced a tiny remainder.
    clock += Math.max(0, seconds * 1000 - ((frames.length / SAMPLE_RATE) * 1000))
  }

  return {
    detector,
    onHint,
    pushSpeech: (seconds) => pushFrames(tone(seconds), seconds),
    pushSilence: (seconds) => pushFrames(silence(seconds), seconds),
    pushNoise: (seconds) => pushFrames(noise(seconds), seconds),
    advance: (ms) => {
      clock += ms
    },
  }
}

describe('encodeWav', () => {
  it('writes a valid 44-byte RIFF/WAVE header for 16-bit PCM mono', async () => {
    const pcm = new Int16Array([0, 1, -1, 32767, -32768])
    const blob = encodeWav(pcm, 16000)
    const buffer = await blob.arrayBuffer()
    const view = new DataView(buffer)
    const dataBytes = pcm.length * 2

    expect(blob.type).toBe('audio/wav')
    expect(buffer.byteLength).toBe(44 + dataBytes)
    expect(ascii(buffer, 0, 4)).toBe('RIFF')
    expect(view.getUint32(4, true)).toBe(36 + dataBytes)
    expect(ascii(buffer, 8, 4)).toBe('WAVE')

    expect(ascii(buffer, 12, 4)).toBe('fmt ')
    expect(view.getUint32(16, true)).toBe(16)
    expect(view.getUint16(20, true)).toBe(1) // PCM
    expect(view.getUint16(22, true)).toBe(1) // mono
    expect(view.getUint32(24, true)).toBe(16000)
    expect(view.getUint32(28, true)).toBe(16000 * 2)
    expect(view.getUint16(32, true)).toBe(2) // block align
    expect(view.getUint16(34, true)).toBe(16) // bits per sample

    expect(ascii(buffer, 36, 4)).toBe('data')
    expect(view.getUint32(40, true)).toBe(dataBytes)

    expect(view.getInt16(44, true)).toBe(0)
    expect(view.getInt16(46, true)).toBe(1)
    expect(view.getInt16(48, true)).toBe(-1)
    expect(view.getInt16(50, true)).toBe(32767)
    expect(view.getInt16(52, true)).toBe(-32768)
  })

  it('defaults to 16 kHz and handles an empty buffer', async () => {
    const blob = encodeWav(new Int16Array(0))
    const buffer = await blob.arrayBuffer()
    const view = new DataView(buffer)

    expect(blob.size).toBe(44)
    expect(view.getUint32(24, true)).toBe(16000)
    expect(view.getUint32(28, true)).toBe(32000)
    expect(view.getUint32(40, true)).toBe(0)
  })

  it('honours a custom sample rate', async () => {
    const pcm = new Int16Array([1, 2, 3])
    const blob = encodeWav(pcm, 8000)
    const view = new DataView(await blob.arrayBuffer())

    expect(view.getUint32(24, true)).toBe(8000)
    expect(view.getUint32(28, true)).toBe(16000)
    expect(view.getUint32(40, true)).toBe(6)
    expect(view.getInt16(44, true)).toBe(1)
    expect(view.getInt16(48, true)).toBe(3)
  })
})

describe('CallHintDetector', () => {
  it('does not trigger for silence or low-level noise', () => {
    const { onHint, pushSilence, pushNoise } = vadHarness()

    pushSilence(2)
    pushNoise(2)

    expect(onHint).not.toHaveBeenCalled()
  })

  it('does not trigger below 3 seconds of speech in the 10-second window', () => {
    const { onHint, pushSpeech, pushSilence } = vadHarness()

    pushSpeech(2)
    pushSilence(1)

    expect(onHint).not.toHaveBeenCalled()
  })

  it('triggers { source: "loopback" } once >= 3 seconds of speech is in the window', () => {
    const { onHint, pushSpeech, pushSilence } = vadHarness()

    pushSpeech(1.5)
    pushSilence(1)
    pushSpeech(1.5)

    expect(onHint).toHaveBeenCalledTimes(1)
    expect(onHint).toHaveBeenCalledWith({ source: 'loopback' })
  })

  it('suppresses repeat hints for 30 seconds, then allows another', () => {
    const { onHint, pushSpeech, pushSilence, advance } = vadHarness()

    pushSpeech(1.5)
    pushSilence(1)
    pushSpeech(1.5)
    expect(onHint).toHaveBeenCalledTimes(1)

    // Still inside the 30 s cooldown: this is enough speech to trigger normally.
    pushSpeech(3)
    expect(onHint).toHaveBeenCalledTimes(1)

    advance(30_000)
    pushSpeech(3)
    expect(onHint).toHaveBeenCalledTimes(2)
  })

  it('reset() clears both the rolling buffer and the cooldown', () => {
    const { detector, onHint, pushSpeech, pushSilence } = vadHarness()

    pushSpeech(1.5)
    pushSilence(1)
    pushSpeech(1.5)
    expect(onHint).toHaveBeenCalledTimes(1)

    detector.reset()

    // If the pre-reset buffer survived, this would trigger on the first check.
    pushSpeech(2)
    expect(onHint).toHaveBeenCalledTimes(1)

    // Cooldown is cleared too: this is still well within 30 s of the first hint.
    pushSpeech(1.5)
    expect(onHint).toHaveBeenCalledTimes(2)
  })
})

describe('replay contract', () => {
  it('labels replay sessions as demo replay, never live capture', () => {
    expect(REPLAY_LABEL).toBe('DEMO REPLAY — NOT LIVE CAPTURE')
  })
})
