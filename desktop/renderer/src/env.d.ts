import type { CompanionBridge } from '../../shared/contracts'

declare module '*.png' {
  const src: string
  export default src
}

declare module '*.webp' {
  const src: string
  export default src
}

declare module '*.svg' {
  const src: string
  export default src
}

declare module '*.glb' {
  const src: string
  export default src
}

declare global {
  interface Window {
    satyapan?: CompanionBridge
  }
}

export {}
