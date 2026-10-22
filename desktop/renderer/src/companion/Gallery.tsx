/** `?view=gallery` — all ten poses side by side for visual QA (MASCOT_SPEC §9). */

import { useState } from 'react'

import type { MascotMood, Pose } from '../../../shared/contracts'
import Mascot from './Mascot'

const POSES: Pose[] = ['sleep', 'idle', 'listen', 'think', 'alert', 'relief', 'write', 'catch', 'wave', 'off']

const MOOD: Record<Pose, MascotMood> = {
  sleep: 'sleepy',
  idle: 'attentive',
  listen: 'attentive',
  think: 'focused',
  alert: 'calm_alert',
  relief: 'attentive',
  write: 'writing',
  catch: 'attentive',
  wave: 'attentive',
  off: 'off',
}

export default function Gallery(): JSX.Element {
  const [level, setLevel] = useState(0)

  return (
    <div className="min-h-screen w-full bg-[#FBF8F3] p-6 text-slate-800">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Satya — pose gallery</h1>
          <p className="text-sm text-slate-500">
            Ten poses, drawn from the same data table. F06 owns the final component.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Fake audio level
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={level}
            onChange={(event) => setLevel(Number(event.target.value))}
          />
          <span className="w-10 text-right font-mono text-xs">{level.toFixed(2)}</span>
        </label>
      </header>

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {POSES.map((pose) => (
          <figure
            key={pose}
            className="flex flex-col items-center rounded-2xl border border-black/10 bg-white/70 p-4"
            data-pose={pose}
          >
            <Mascot mood={MOOD[pose]} size={128} />
            <figcaption className="mt-2 font-mono text-xs text-slate-500">{pose}</figcaption>
            {pose === 'listen' ? (
              <div
                aria-hidden
                className="mt-1 h-1.5 w-16 rounded-full bg-teal-500/30"
                style={{ transform: `scaleX(${0.2 + level * 0.8})` }}
              />
            ) : null}
          </figure>
        ))}
      </div>
    </div>
  )
}
