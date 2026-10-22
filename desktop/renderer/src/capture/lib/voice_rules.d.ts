/** Types for the parity `voice_rules.js` module (the implementation stays identical). */

export interface VoiceThresholds {
  tauHi: number
  tauLo: number
}

export type VoiceLabel = 'likely_synthetic' | 'inconclusive' | 'no_signs'

export interface VoiceClassification {
  label: VoiceLabel
  maxConsecutiveOverHi: number
  windows: number
  maxScore: number
  speechSeconds: number
  greyReasons: string[]
}

export const MIN_SPEECH_SECONDS: number
export const MIN_CONSECUTIVE: number

export function classifyWindows(
  scores: number[],
  thresholds: VoiceThresholds,
  speechSeconds: number,
  minConsecutive?: number,
): VoiceClassification
