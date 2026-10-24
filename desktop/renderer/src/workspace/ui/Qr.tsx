/** QR code for a local URL (the approver's phone page). Generated on this laptop, offline. */

import { useEffect, useState } from 'react'

// qrcode@1.5.4 ships no TypeScript declarations; Vite still resolves the runtime package.
// @ts-expect-error - the package has no bundled types and this project does not add @types/qrcode.
import QRCode from 'qrcode'

export default function Qr({ value, size = 132 }: { value: string; size?: number }): JSX.Element | null {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    if (!value) return
    void (QRCode.toDataURL(value, { margin: 1, width: size * 2, color: { dark: '#2A2238', light: '#FFFCF7' } }) as Promise<string>)
      .then((url) => {
        if (alive) setSrc(url)
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [value, size])
  if (!src) return null
  return <img src={src} width={size} height={size} alt={`QR code for ${value}`} className="rounded-lg" />
}
