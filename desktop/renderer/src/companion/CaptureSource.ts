/**
 * CaptureSource — the audio boundary (T25 §3.2).
 *
 * Real OS loopback wiring lives in `desktop/capture/` (Kartikey). This fake emits PCM chunks so
 * the companion, quality telemetry and preflight UI can be built and rehearsed offline. It never
 * touches a microphone.
 */

export interface PcmChunk {
  sequence: number
  capturedAt: string
  sampleRate: 16000
  channels: 1
  format: 'PCM_S16LE'
  pcm: Int16Array
  durationMs: number
}

export interface CaptureSource {
  readonly label: string
  readonly live: boolean
  start(onChunk: (chunk: PcmChunk) => void): Promise<void>
  stop(): Promise<void>
}

export class FakeCaptureSource implements CaptureSource {
  readonly label = 'Generated demo audio (no microphone)'
  readonly live = false
  private timer: ReturnType<typeof setInterval> | null = null
  private sequence = 0

  async start(onChunk: (chunk: PcmChunk) => void): Promise<void> {
    this.stop()
    this.timer = setInterval(() => {
      const pcm = new Int16Array(8000)
      for (let i = 0; i < pcm.length; i += 1) {
        pcm[i] = Math.round(Math.sin((i + this.sequence * 80) / 12) * 1200)
      }
      onChunk({
        sequence: this.sequence++,
        capturedAt: new Date().toISOString(),
        sampleRate: 16000,
        channels: 1,
        format: 'PCM_S16LE',
        pcm,
        durationMs: 500,
      })
    }, 500)
  }

  async stop(): Promise<void> {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
  }
}

export function createDemoCapture(): CaptureSource {
  return new FakeCaptureSource()
}
