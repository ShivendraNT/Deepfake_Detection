/** Types for the parity `audio_window.js` module (the implementation stays identical). */

export interface AudioWindow {
  windowIndex: number
  t_start_s: number
  t_end_s: number
  data: Float32Array
}

export interface Windower {
  push(frames: Float32Array): AudioWindow[]
}

export function createWindower(options?: {
  sampleRate?: number
  windowSeconds?: number
}): Windower

export function speechSeconds(
  windowData: Float32Array,
  sampleRate?: number,
  rmsThreshold?: number,
): number
