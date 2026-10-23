/**
 * `?view=stage` — the rehearsal view: mascot, bubble and Notebook side by side with Play,
 * Pause and Reset for the three timed scenarios. It is a UI fixture only: every band shown is
 * relayed from `mockScenario.ts`, never computed here.
 */

import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import type { BubbleCard, MascotMood, Pose } from '../../../shared/contracts'
import { USER_MODE_LABELS } from '../../../shared/contracts'
import { api } from '../shared/api'
import { SCENARIO_LIST, SCENARIOS, stepsUntil, type ScenarioKey } from '../shared/mockScenario'
import Mascot from '../companion/Mascot'
import BubbleCardView from '../companion/bubble/BubbleCardView'

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

const BAND_CLASS: Record<string, string> = {
  PASS: 'bg-emerald-500/15 text-emerald-700',
  VERIFY: 'bg-amber-500/20 text-amber-800',
  HOLD: 'bg-rose-500/15 text-rose-700',
}

function seconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`
}

export default function Stage(): JSX.Element {
  const [key, setKey] = useState<ScenarioKey>('cfo_call')
  const [elapsed, setElapsed] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [lastAction, setLastAction] = useState<string | null>(null)

  const scenario = SCENARIOS[key]

  useEffect(() => {
    setElapsed(0)
    setPlaying(false)
    setLastAction(null)
  }, [key])

  useEffect(() => {
    if (!playing) return
    const startedAt = Date.now() - elapsed
    const timer = window.setInterval(() => {
      const next = Date.now() - startedAt
      if (next >= scenario.duration_ms) {
        setElapsed(scenario.duration_ms)
        setPlaying(false)
        return
      }
      setElapsed(next)
    }, 100)
    return () => window.clearInterval(timer)
    // `elapsed` is read once when playback starts; adding it would restart the clock each tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, scenario.duration_ms])

  const applied = useMemo(() => stepsUntil(scenario, elapsed), [scenario, elapsed])

  const { card, pose } = useMemo(() => {
    let nextCard: BubbleCard | null = null
    let nextPose: Pose = 'idle'
    for (const step of applied) {
      if (step.card !== undefined) nextCard = step.card
      if (step.pose) nextPose = step.pose
    }
    return { card: nextCard, pose: nextPose }
  }, [applied])

  const latest = applied[applied.length - 1]?.event
  const report = latest?.payload.report ?? null

  function replay(): void {
    setElapsed(0)
    setPlaying(true)
    setLastAction(null)
  }

  return (
    <div className="min-h-screen w-full bg-[#FBF8F3] p-5 text-slate-800">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Stage rehearsal — Satya</h1>
          <p className="text-sm text-slate-500">
            Mock playback only. Bands are relayed from the scenario, never computed in the UI.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={replay} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white">
            Play
          </button>
          <button
            type="button"
            onClick={() => setPlaying((value) => !value)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium"
          >
            {playing ? 'Pause' : 'Resume'}
          </button>
          <button
            type="button"
            onClick={() => {
              setElapsed(0)
              setPlaying(false)
              setLastAction(null)
            }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={() => void api.openWorkspace()}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium"
          >
            Open Notebook
          </button>
        </div>
      </header>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {SCENARIO_LIST.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setKey(item.key)}
            className={`rounded-full px-3 py-1.5 text-sm ${
              item.key === key
                ? 'bg-teal-600 text-white'
                : 'border border-slate-300 bg-white/60 text-slate-700'
            }`}
          >
            {item.title}
          </button>
        ))}
        <span className="ml-auto font-mono text-xs text-slate-500">
          {seconds(elapsed)} / {seconds(scenario.duration_ms)}
        </span>
      </div>
      <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full bg-teal-600 transition-[width] duration-100"
          style={{ width: `${Math.min(100, (elapsed / scenario.duration_ms) * 100)}%` }}
        />
      </div>
      <p className="mt-2 text-sm text-slate-500">{scenario.subtitle}</p>

      <div className="mt-4 grid grid-cols-1 items-start gap-4 lg:grid-cols-[240px_360px_1fr]">
        <section className="flex flex-col items-center rounded-2xl border border-black/10 bg-white/60 p-4" aria-label="Mascot">
          <Mascot pose={pose} mood={MOOD[pose]} size={168} />
          <span className="mt-2 font-mono text-xs text-slate-500">pose: {pose}</span>
        </section>

        <section className="min-h-[260px]" aria-label="Bubble">
          <AnimatePresence mode="wait">
            {card ? (
              <motion.div
                key={card.id}
                initial={{ opacity: 0, scale: 0.88, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.9, y: 6 }}
                transition={{ type: 'spring', stiffness: 420, damping: 24, mass: 0.8 }}
              >
                <BubbleCardView
                  card={card}
                  onAction={(actionId) => setLastAction(`${card.id} → ${actionId}`)}
                />
              </motion.div>
            ) : (
              <div className="grid h-full place-items-center rounded-2xl border border-dashed border-slate-300 p-6 text-sm text-slate-400">
                No card
              </div>
            )}
          </AnimatePresence>
        </section>

        <section className="rounded-2xl border border-black/10 bg-white/70 p-4" aria-label="Notebook">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Notebook</h2>
            <span className="text-[11px] text-slate-400">MANUAL_ONLY · satyapan.policy</span>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div>
              <div className="text-slate-400">Mode</div>
              <div className="font-medium">
                {latest?.payload.user_mode
                  ? USER_MODE_LABELS[latest.payload.user_mode]
                  : latest?.payload.state ?? 'SLEEP'}
              </div>
            </div>
            <div>
              <div className="text-slate-400">Band (relayed)</div>
              <span
                className={`inline-block rounded px-2 py-0.5 font-semibold ${
                  latest?.payload.band ? BAND_CLASS[latest.payload.band] : 'bg-slate-200 text-slate-600'
                }`}
              >
                {latest?.payload.band ?? 'none'}
              </span>
            </div>
            <div className="col-span-2">
              <div className="text-slate-400">Case</div>
              <div className="font-mono text-[11px]">
                {latest?.payload.case_id ?? latest?.payload.call_id ?? 'no active case'}
              </div>
            </div>
          </div>

          {latest ? (
            <div className="mt-3 rounded-xl bg-[#F3EEE6] p-3">
              <div className="text-sm font-medium">{latest.payload.headline}</div>
              {latest.payload.explanation ? (
                <p className="mt-1 text-xs leading-relaxed text-slate-600">{latest.payload.explanation}</p>
              ) : null}
            </div>
          ) : null}

          {report ? (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>Report pack v2 · 5 drafts</span>
                <span>{report.submission}</span>
              </div>
              <ul className="mt-1 space-y-1 text-xs">
                {report.sections.map((section) => (
                  <li key={section.id} className="flex items-center justify-between gap-2">
                    <span>{section.title}</span>
                    <span className={section.applies ? 'text-amber-700' : 'text-slate-400'}>
                      {section.applies ? 'draft' : 'check with IT/legal'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-3">
            <div className="text-xs text-slate-400">Timeline (newest first)</div>
            <ol className="mt-1 max-h-48 space-y-1 overflow-auto text-xs">
              {[...applied].reverse().map((step) => (
                <li key={step.event.event_id} className="flex gap-2">
                  <span className="w-12 shrink-0 font-mono text-[10px] text-slate-400">
                    {seconds(step.at_ms)}
                  </span>
                  <span>
                    <span className="font-mono text-[10px] text-slate-500">{step.event.type}</span>
                    {' · '}
                    {step.event.payload.headline}
                  </span>
                </li>
              ))}
            </ol>
            {lastAction ? (
              <div className="mt-2 rounded bg-slate-900 px-2 py-1 font-mono text-[10px] text-white">
                clicked {lastAction}
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  )
}
