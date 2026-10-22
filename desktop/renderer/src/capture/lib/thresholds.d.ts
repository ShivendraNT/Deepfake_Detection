/** Types for the parity `thresholds.js` module (the implementation stays identical). */

export interface ThresholdConfig {
  tauHi: number
  tauLo: number
  modelVersion: string
  calibrated: boolean
}

export const THRESHOLDS: ThresholdConfig
