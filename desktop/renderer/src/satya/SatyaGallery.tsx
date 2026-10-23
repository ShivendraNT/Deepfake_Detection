/**
 * `?view=gallery` — Satya's model sheet. Every pose live, plus a big interactive preview with
 * the gestures, a fake call level, talking, petting and light/dark/busy backdrops.
 */

import { useEffect, useRef, useState } from 'react'

import { SATYA_POSES, type Emote, type SatyaPose } from './engine'
import SatyaSprite, { type SatyaHandle } from './SatyaSprite'

const EMOTES: Emote[] = [
  'hop',
  'wave',
  'boop',
  'giggle',
  'nod',
  'shake',
  'notice',
  'startle',
  'celebrate',
  'yawn',
  'wake',
  'lookAround',
  'capTip',
  'stretch',
  'gulp',
  'perk',
]

const BACKDROPS = {
  light: '#F6F3EE',
  dark: '#14121C',
  busy: 'linear-gradient(135deg,#3b82f6 0%,#f472b6 40%,#fde68a 70%,#10b981 100%)',
} as const

export default function SatyaGallery(): JSX.Element {
  const params = new URLSearchParams(window.location.search)
  const initial = (params.get('pose') as SatyaPose | null) ?? 'idle'
  const [pose, setPose] = useState<SatyaPose>(SATYA_POSES.includes(initial) ? initial : 'idle')
  const [level, setLevel] = useState(Number(params.get('level') ?? 0.4))
  const [talking, setTalking] = useState(false)
  const [backdrop, setBackdrop] = useState<keyof typeof BACKDROPS>(
    (params.get('bg') as keyof typeof BACKDROPS | null) ?? 'light',
  )
  const [look, setLook] = useState({ dx: 0, dy: 0, near: false })
  const hero = useRef<SatyaHandle | null>(null)

  // Fake a talking voice so the listen pose nods along in screenshots.
  const [autoLevel, setAutoLevel] = useState(params.get('autolevel') === '1')
  useEffect(() => {
    if (!autoLevel) return
    const timer = setInterval(() => {
      setLevel(Math.max(0, Math.min(1, 0.35 + Math.sin(Date.now() / 180) * 0.3 + Math.random() * 0.25)))
    }, 80)
    return () => clearInterval(timer)
  }, [autoLevel])

  const dark = backdrop !== 'light'
  return (
    <div
      className="min-h-screen w-full overflow-auto p-6"
      style={{ background: BACKDROPS[backdrop], color: dark ? '#EDE8F5' : '#2A2238' }}
    >
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="m-0 text-lg font-semibold">Satya — model sheet</h1>
          <p className="m-0 text-sm opacity-70">
            Procedural rig: springs, blinks, gaze, gestures and props. Move the mouse over the big Satya.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            Call level
            <input type="range" min={0} max={1} step={0.05} value={level} onChange={(e) => setLevel(Number(e.target.value))} />
          </label>
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={autoLevel} onChange={(e) => setAutoLevel(e.target.checked)} /> fake voice
          </label>
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={talking} onChange={(e) => setTalking(e.target.checked)} /> talking
          </label>
          {(Object.keys(BACKDROPS) as Array<keyof typeof BACKDROPS>).map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => setBackdrop(name)}
              className={`rounded-full border px-3 py-1 text-xs ${name === backdrop ? 'border-current' : 'border-transparent opacity-60'}`}
            >
              {name}
            </button>
          ))}
        </div>
      </header>

      <section className="mt-6 flex flex-col items-center gap-4 rounded-3xl border border-current/10 p-6" style={{ borderColor: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)' }}>
        <div
          className="grid h-[300px] w-[300px] place-items-center"
          onMouseMove={(event) => {
            const rect = event.currentTarget.getBoundingClientRect()
            setLook({
              dx: event.clientX - (rect.left + rect.width / 2),
              dy: event.clientY - (rect.top + rect.height / 2),
              near: true,
            })
            if (event.buttons === 1) hero.current?.pet()
          }}
          onMouseLeave={() => setLook({ dx: 0, dy: 0, near: false })}
          onClick={() => hero.current?.play('boop')}
        >
          <SatyaSprite ref={hero} pose={pose} size={240} level={level} look={look} talking={talking} />
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          {SATYA_POSES.map((name) => (
            <button
              key={name}
              type="button"
              data-pose={name}
              onClick={() => setPose(name)}
              className={`rounded-full px-3 py-1 font-mono text-xs ${name === pose ? 'bg-cyan-500 text-white' : 'bg-black/10'}`}
            >
              {name}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          {EMOTES.map((emote) => (
            <button
              key={emote}
              type="button"
              data-emote={emote}
              onClick={() => hero.current?.play(emote)}
              className="rounded-full border px-3 py-1 font-mono text-[11px] opacity-80"
              style={{ borderColor: dark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)' }}
            >
              {emote}
            </button>
          ))}
        </div>
      </section>

      <section className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {SATYA_POSES.map((name) => (
          <figure
            key={name}
            className="m-0 flex flex-col items-center rounded-2xl p-3"
            style={{ background: dark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.7)' }}
          >
            <div className="grid h-[150px] w-[150px] place-items-center">
              <SatyaSprite pose={name === 'off' ? 'off' : name} size={128} level={level} seed={name.length * 13} />
            </div>
            <figcaption className="mt-1 font-mono text-xs opacity-70">{name}</figcaption>
          </figure>
        ))}
      </section>
    </div>
  )
}
