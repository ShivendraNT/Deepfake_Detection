/**
 * Utterance segmenter for live calls (finale).
 *
 * The old pipeline cut fixed 10-second chunks, so a sentence could wait 13 s for a chip and
 * words were sliced in half at the boundary. This cuts the other person's speech at natural
 * pauses instead: one utterance per sentence-ish, 0.4–6 s long, sent as soon as they pause.
 *
 * Pure and synchronous (no Web Audio, no timers) so it is unit-tested with synthetic audio.
 * Energy VAD with an adaptive noise floor: call audio is usually clean, but Meet's comfort
 * noise and a fan in the room should not count as speech.
 */

export interface Utterance {
  index: number
  samples: Float32Array
  /** Seconds since the start of the call. */
  tStart: number
  tEnd: number
  /** Seconds of frames above the speech threshold inside this utterance. */
  speechSeconds: number
}

export interface SegmenterOptions {
  sampleRate?: number
  frameMs?: number
  /** Utterances with less speech than this are dropped (clicks, coughs). */
  minSpeechMs?: number
  /** A pause this long ends the utterance. */
  endSilenceMs?: number
  /** Never let an utterance grow past this; cut at the next dip, or hard-cut at the limit. */
  maxUtteranceMs?: number
  /** Audio kept from just before speech started, so the first syllable is not clipped. */
  preRollMs?: number
  /** Absolute floor for the speech threshold (RMS). */
  minThreshold?: number
}

const DEFAULTS: Required<SegmenterOptions> = {
  sampleRate: 16000,
  frameMs: 30,
  minSpeechMs: 350,
  endSilenceMs: 550,
  maxUtteranceMs: 6000,
  preRollMs: 240,
  minThreshold: 0.008,
}

export class UtteranceSegmenter {
  private readonly o: Required<SegmenterOptions>
  private readonly frameLen: number
  private pending = new Float32Array(0)
  private processed = 0 // samples consumed into frames
  private noise = 0.004
  private preRoll: Float32Array[] = []
  private current: Float32Array[] | null = null
  private currentStart = 0
  private speechFrames = 0
  private silenceFrames = 0
  private aboveRun = 0
  private nextIndex = 0
  private speaking = false

  constructor(
    private readonly onUtterance: (utterance: Utterance) => void,
    options: SegmenterOptions = {},
    private readonly onSpeech?: (active: boolean) => void,
  ) {
    this.o = { ...DEFAULTS, ...options }
    this.frameLen = Math.round((this.o.sampleRate * this.o.frameMs) / 1000)
  }

  get threshold(): number {
    return Math.max(this.o.minThreshold, this.noise * 2.8)
  }

  /** Feed any number of samples (the worklet sends 128-sample blocks). */
  push(samples: Float32Array): void {
    if (samples.length === 0) return
    const merged = new Float32Array(this.pending.length + samples.length)
    merged.set(this.pending, 0)
    merged.set(samples, this.pending.length)
    let offset = 0
    while (merged.length - offset >= this.frameLen) {
      this.frame(merged.subarray(offset, offset + this.frameLen))
      offset += this.frameLen
    }
    this.pending = merged.slice(offset)
  }

  /** Emit whatever is in progress (call ended / user stopped). */
  flush(): void {
    if (this.current) this.finish()
    this.setSpeaking(false)
  }

  private frame(frame: Float32Array): void {
    const copy = frame.slice()
    const t = this.processed / this.o.sampleRate
    this.processed += copy.length

    let sum = 0
    for (let i = 0; i < copy.length; i += 1) sum += copy[i] * copy[i]
    const rms = Math.sqrt(sum / copy.length)
    const above = rms > this.threshold
    this.aboveRun = above ? this.aboveRun + 1 : 0

    if (!this.current) {
      // Track the noise floor only while nobody is speaking.
      const rate = rms < this.noise ? 0.2 : 0.02
      this.noise = Math.min(0.05, this.noise + (rms - this.noise) * rate)
      this.preRoll.push(copy)
      const keep = Math.ceil(this.o.preRollMs / this.o.frameMs)
      while (this.preRoll.length > keep) this.preRoll.shift()
      // Two loud frames in a row (60 ms) start an utterance.
      if (this.aboveRun >= 2) {
        this.current = [...this.preRoll]
        this.currentStart = t - (this.preRoll.length - 1) * (this.o.frameMs / 1000)
        this.preRoll = []
        this.speechFrames = 2
        this.silenceFrames = 0
        this.setSpeaking(true)
      }
      return
    }

    this.current.push(copy)
    if (above) {
      this.speechFrames += 1
      this.silenceFrames = 0
    } else {
      this.silenceFrames += 1
    }

    const lengthMs = this.current.length * this.o.frameMs
    const silenceMs = this.silenceFrames * this.o.frameMs
    const nearLimit = lengthMs >= this.o.maxUtteranceMs - 1500
    const dip = rms < this.threshold * 1.2

    if (silenceMs >= this.o.endSilenceMs) {
      // Trim most of the trailing silence but keep a little tail.
      const trim = Math.max(0, this.silenceFrames - 4)
      if (trim > 0) this.current.splice(this.current.length - trim, trim)
      this.finish()
    } else if (lengthMs >= this.o.maxUtteranceMs || (nearLimit && dip && silenceMs >= 90)) {
      this.finish()
      // Speech continues straight into the next utterance.
      this.current = []
      this.currentStart = this.processed / this.o.sampleRate
      this.speechFrames = 0
      this.silenceFrames = 0
      this.setSpeaking(true)
    }
  }

  private finish(): void {
    const parts = this.current ?? []
    this.current = null
    this.setSpeaking(false)
    const speechSeconds = (this.speechFrames * this.o.frameMs) / 1000
    this.speechFrames = 0
    this.silenceFrames = 0
    if (speechSeconds * 1000 < this.o.minSpeechMs || parts.length === 0) return
    let length = 0
    for (const p of parts) length += p.length
    const samples = new Float32Array(length)
    let offset = 0
    for (const p of parts) {
      samples.set(p, offset)
      offset += p.length
    }
    const tStart = Math.max(0, this.currentStart)
    this.onUtterance({
      index: this.nextIndex++,
      samples,
      tStart,
      tEnd: tStart + length / this.o.sampleRate,
      speechSeconds,
    })
  }

  private setSpeaking(active: boolean): void {
    if (active === this.speaking) return
    this.speaking = active
    this.onSpeech?.(active)
  }
}
