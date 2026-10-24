/**
 * Screen-frame sampler for the video check (finale, docs/VIDEO_DEEPFAKE.md).
 *
 * Runs only after the user said yes to watching this call's video. ~15 frames/s are grabbed from
 * the screen track, downscaled (longest side <= 1280 px), JPEG-encoded in memory and posted in
 * one-second batches to the local engine (`/live/{call_id}/video`, 127.0.0.1 only). Nothing is
 * written to disk; the engine measures each frame and drops it. A slow engine never piles up
 * frames: at most two batches wait, older ones are dropped (never stitched back in).
 */

import { API_BASE } from './pipeline'

export const VIDEO_FPS = 15
const MAX_SIDE = 1280
const BATCH_MS = 1000
const JPEG_QUALITY = 0.85
const MAX_WAITING = 2
const REQUEST_TIMEOUT_MS = 20_000

export interface VideoHooks {
  /** The backend no longer knows this call. */
  onCallGone?: () => void
  /** Frames stopped arriving (track ended / grab failed repeatedly). */
  onVideoLost?: (reason: string) => void
}

interface Grabber {
  grab(): Promise<ImageBitmap | null>
  close(): void
}

interface ImageCaptureLike {
  grabFrame(): Promise<ImageBitmap>
}

/** ImageCapture works in a hidden window; a muted <video> is the fallback. */
function makeGrabber(track: MediaStreamTrack): Grabber {
  const Ctor = (globalThis as unknown as { ImageCapture?: new (t: MediaStreamTrack) => ImageCaptureLike })
    .ImageCapture
  if (Ctor) {
    const capture = new Ctor(track)
    return {
      grab: async () => {
        try {
          return await capture.grabFrame()
        } catch {
          return null
        }
      },
      close: () => undefined,
    }
  }
  const video = document.createElement('video')
  video.muted = true
  video.playsInline = true
  video.srcObject = new MediaStream([track])
  void video.play().catch(() => undefined)
  return {
    grab: async () => {
      if (video.readyState < 2 || video.videoWidth === 0) return null
      return createImageBitmap(video)
    },
    close: () => {
      video.pause()
      video.srcObject = null
    },
  }
}

export function scaledSize(width: number, height: number, maxSide = MAX_SIDE): { width: number; height: number } {
  const scale = Math.min(1, maxSide / Math.max(width, height, 1))
  return { width: Math.max(2, Math.round(width * scale)), height: Math.max(2, Math.round(height * scale)) }
}

let running = false
let timer: ReturnType<typeof setInterval> | null = null
let flushTimer: ReturnType<typeof setInterval> | null = null
let grabber: Grabber | null = null
let canvas: OffscreenCanvas | null = null
let batch: Array<{ t: number; blob: Blob }> = []
let waiting = 0
let busy = false
let failures = 0
let t0 = 0
let runToken = 0

export async function startVideo(track: MediaStreamTrack, callId: string, hooks: VideoHooks = {}): Promise<void> {
  await stopVideo()
  const myRun = ++runToken
  running = true
  grabber = makeGrabber(track)
  t0 = performance.now()
  failures = 0
  track.onended = () => {
    if (myRun === runToken) hooks.onVideoLost?.('screen video stopped')
  }

  timer = setInterval(() => {
    if (!running || busy || !grabber) return
    busy = true
    const t = (performance.now() - t0) / 1000
    void grabber
      .grab()
      .then(async (bitmap) => {
        if (!bitmap || myRun !== runToken) {
          failures += 1
          if (failures > VIDEO_FPS * 5) hooks.onVideoLost?.('no screen frames arrived')
          return
        }
        failures = 0
        const size = scaledSize(bitmap.width, bitmap.height)
        if (!canvas || canvas.width !== size.width || canvas.height !== size.height) {
          canvas = new OffscreenCanvas(size.width, size.height)
        }
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        ctx.drawImage(bitmap, 0, 0, size.width, size.height)
        bitmap.close()
        const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality: JPEG_QUALITY })
        if (myRun === runToken) batch.push({ t, blob })
      })
      .finally(() => {
        busy = false
      })
  }, 1000 / VIDEO_FPS)

  flushTimer = setInterval(() => {
    if (!running || batch.length === 0) return
    const frames = batch
    batch = []
    if (waiting >= MAX_WAITING) return // the engine is behind: drop this second, never queue
    waiting += 1
    void postFrames(callId, frames)
      .then((status) => {
        if (status === 404 && myRun === runToken) hooks.onCallGone?.()
      })
      .catch(() => undefined)
      .finally(() => {
        waiting -= 1
      })
  }, BATCH_MS)
}

async function postFrames(callId: string, frames: Array<{ t: number; blob: Blob }>): Promise<number> {
  const form = new FormData()
  frames.forEach((frame, index) => form.append('frames', frame.blob, `f${index}.jpg`))
  form.append('times', JSON.stringify(frames.map((frame) => Number(frame.t.toFixed(3)))))
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(`${API_BASE}/live/${encodeURIComponent(callId)}/video`, {
      method: 'POST',
      body: form,
      signal: controller.signal,
    })
    return response.status
  } finally {
    clearTimeout(timeout)
  }
}

export async function stopVideo(): Promise<void> {
  runToken += 1
  running = false
  if (timer) clearInterval(timer)
  if (flushTimer) clearInterval(flushTimer)
  timer = null
  flushTimer = null
  grabber?.close()
  grabber = null
  batch = []
  canvas = null
}
