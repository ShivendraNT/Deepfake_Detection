import { describe, expect, it } from 'vitest'

import { UtteranceSegmenter, type Utterance } from '../renderer/src/capture/segmenter'

const SR = 16000

/** Speech-like audio: an amplitude-modulated tone (syllables) for `seconds`. */
function speech(seconds: number, amp = 0.2): Float32Array {
  const out = new Float32Array(Math.round(seconds * SR))
  for (let i = 0; i < out.length; i += 1) {
    const t = i / SR
    const syllable = 0.55 + 0.45 * Math.sin(2 * Math.PI * 4 * t)
    out[i] = amp * syllable * Math.sin(2 * Math.PI * 180 * t)
  }
  return out
}

function silence(seconds: number, noise = 0.001): Float32Array {
  const out = new Float32Array(Math.round(seconds * SR))
  let seed = 7
  for (let i = 0; i < out.length; i += 1) {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff
    out[i] = ((seed / 0x7fffffff) * 2 - 1) * noise
  }
  return out
}

function feed(seg: UtteranceSegmenter, audio: Float32Array): void {
  // The audio worklet delivers 128-sample blocks.
  for (let i = 0; i < audio.length; i += 128) seg.push(audio.subarray(i, i + 128))
}

describe('UtteranceSegmenter', () => {
  it('cuts one utterance per sentence at the pauses, with call-relative times', () => {
    const got: Utterance[] = []
    const seg = new UtteranceSegmenter((u) => got.push(u))
    feed(seg, silence(1))
    feed(seg, speech(2))
    feed(seg, silence(0.9))
    feed(seg, speech(1.5))
    feed(seg, silence(1))
    seg.flush()
    expect(got.map((u) => u.index)).toEqual([0, 1])
    expect(got[0].tStart).toBeGreaterThan(0.6)
    expect(got[0].tStart).toBeLessThan(1.05)
    expect(got[0].tEnd).toBeGreaterThan(2.9)
    expect(got[0].tEnd).toBeLessThan(3.4)
    expect(got[1].tStart).toBeGreaterThan(3.6)
    expect(got[1].speechSeconds).toBeGreaterThan(1)
  })

  it('never lets an utterance grow past the limit while someone talks non-stop', () => {
    const got: Utterance[] = []
    const seg = new UtteranceSegmenter((u) => got.push(u), { maxUtteranceMs: 4000 })
    feed(seg, speech(11))
    seg.flush()
    expect(got.length).toBeGreaterThanOrEqual(3)
    for (const u of got) expect(u.tEnd - u.tStart).toBeLessThanOrEqual(4.05)
    // Contiguous: no audio lost between forced cuts.
    for (let i = 1; i < got.length; i += 1) {
      expect(Math.abs(got[i].tStart - got[i - 1].tEnd)).toBeLessThan(0.05)
    }
  })

  it('ignores clicks and background noise', () => {
    const got: Utterance[] = []
    const seg = new UtteranceSegmenter((u) => got.push(u))
    feed(seg, silence(2, 0.004))
    feed(seg, speech(0.12, 0.5)) // a click / cough
    feed(seg, silence(2, 0.004))
    seg.flush()
    expect(got).toEqual([])
  })

  it('reports when the other person starts and stops speaking', () => {
    const activity: boolean[] = []
    const seg = new UtteranceSegmenter(() => undefined, {}, (active) => activity.push(active))
    feed(seg, silence(0.5))
    feed(seg, speech(1))
    feed(seg, silence(1))
    expect(activity).toEqual([true, false])
  })
})
