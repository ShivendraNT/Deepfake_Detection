import { useEffect, useState } from 'react'
import { useReducedMotion } from 'framer-motion'

export function useTypewriter(text: string, intervalMs = 18, chunk = 6): string {
  const reduced = useReducedMotion()
  const [shown, setShown] = useState(reduced ? text : '')

  useEffect(() => {
    if (reduced) {
      setShown(text)
      return
    }
    setShown('')
    let index = 0
    const timer = setInterval(() => {
      index = Math.min(text.length, index + chunk)
      setShown(text.slice(0, index))
      if (index >= text.length) clearInterval(timer)
    }, intervalMs)
    return () => clearInterval(timer)
  }, [chunk, intervalMs, reduced, text])

  return shown
}
