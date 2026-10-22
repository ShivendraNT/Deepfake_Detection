import type { CompanionBridge } from '../../shared/contracts'

declare global {
  interface Window {
    satyapan?: CompanionBridge
  }
}

export {}
