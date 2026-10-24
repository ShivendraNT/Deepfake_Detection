/** Tiny synthesized cues — optional, user-controlled, never a siren (T25 §3.1). */

type Chime = 'alert' | 'soft' | 'error'

let context: AudioContext | null = null

function audio(): AudioContext | null {
  if (typeof window === 'undefined') return null
  try {
    context ??= new AudioContext()
    return context
  } catch {
    return null
  }
}

export function playChime(kind: Chime): void {
  const ctx = audio()
  if (!ctx) return
  if (ctx.state === 'suspended') void ctx.resume()

  const notes =
    kind === 'alert'
      ? [
          { at: 0, hz: 523.25, ms: 220 },
          { at: 0.18, hz: 392.0, ms: 320 },
        ]
      : kind === 'error'
        ? [{ at: 0, hz: 220, ms: 240 }]
        : [{ at: 0, hz: 659.25, ms: 180 }]

  for (const note of notes) {
    const oscillator = ctx.createOscillator()
    const gain = ctx.createGain()
    oscillator.type = 'sine'
    oscillator.frequency.value = note.hz
    const start = ctx.currentTime + note.at
    const end = start + note.ms / 1000
    gain.gain.setValueAtTime(0, start)
    gain.gain.linearRampToValueAtTime(0.045, start + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, end)
    oscillator.connect(gain).connect(ctx.destination)
    oscillator.start(start)
    oscillator.stop(end + 0.02)
  }
}
