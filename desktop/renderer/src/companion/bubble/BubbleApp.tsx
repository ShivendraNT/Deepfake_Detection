/**
 * The bubble window (`?view=bubble`): exactly one card, placed beside Satya by main.
 *
 * QA Helpers:
 * - `?view=bubble&card=<kind>` renders that specific card offline (MASCOT_SPEC §9).
 * - `?view=bubble&card=<kind>&lang=hi` or `&lang=hinglish` switches languages.
 */

import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import type { BubbleCard } from '../../../../shared/contracts'
import { api } from '../../shared/api'
import type { Lang } from '../../shared/copy'
import { SCENARIO_LIST } from '../../shared/mockScenario'
import BubbleCardView from './BubbleCardView'

const FIXTURE_CARDS: Record<string, BubbleCard> = {
  consent: {
    kind: 'consent',
    id: 'card_consent_demo',
    scopes: [
      'Notice calls (no recording)',
      'Listen to a call when you say yes',
      'Check files you give me',
    ],
    actions: [
      { id: 'start_watching', variant: 'primary' },
      { id: 'not_now', variant: 'ghost' },
    ],
  },
  call_ask: {
    kind: 'call_ask',
    id: 'card_call_demo',
    source: 'loopback',
    actions: [
      { id: 'listen_call', variant: 'primary' },
      { id: 'not_this_call', variant: 'ghost' },
    ],
  },
  file_ask: {
    kind: 'file_ask',
    id: 'card_file_demo',
    file_name: 'Invoice_7749_Updated_Beneficiary.pdf',
    file_kind: 'pdf',
    actions: [
      { id: 'check_it', variant: 'primary' },
      { id: 'no_thanks', variant: 'ghost' },
    ],
  },
  live: {
    kind: 'live',
    id: 'card_live_demo',
    chips: [{ code: 'A1', at_s: 12 }, { code: 'A4', at_s: 24 }],
    coverage: 'usable',
    seal: 'not_verified',
    elapsed_s: 42,
  },
  result: {
    kind: 'result',
    id: 'card_result_demo',
    band: 'VERIFY',
    headline: 'Verify first.',
    reasons: ['New payee account ••••9917 not on vendor master', 'Amount ₹48,50,000 exceeds floor limit'],
    actions: [{ id: 'verify', variant: 'primary' }, { id: 'dismiss', variant: 'ghost' }],
  },
  alert: {
    kind: 'alert',
    id: 'card_alert_demo',
    band: 'HOLD',
    headline: 'Pause before you pay.',
    reasons: ['Voice not verified by Seal', 'Urgent bypass requested'],
    chips: [
      { code: 'A1', at_s: 6 },
      { code: 'A2', at_s: 14 },
      { code: 'A4', at_s: 22 },
    ],
    actions: [
      { id: 'verify_with_approver', variant: 'primary' },
      { id: 'copy_safe_reply', variant: 'outline' },
    ],
  },
  oob_wait: {
    kind: 'oob_wait',
    id: 'card_oob_wait_demo',
    approver_name: 'Priya Sharma (CFO)',
    sent_at: new Date().toISOString(),
    actions: [{ id: 'open_notebook', variant: 'outline' }],
  },
  oob_result: {
    kind: 'oob_result',
    id: 'card_oob_result_demo',
    approver_name: 'Priya Sharma (CFO)',
    outcome: 'approved',
    actions: [{ id: 'open_notebook', variant: 'primary' }],
  },
  scribe: {
    kind: 'scribe',
    id: 'card_scribe_demo',
    actions: [{ id: 'open_reports', variant: 'primary' }],
    sections: [
      { id: '1', title: '1930 Helpline Packet', status: 'done' },
      { id: '2', title: 'Bank Freeze Letter', status: 'done' },
      { id: '3', title: 'CERT-In Incident Report', status: 'writing' },
    ],
  },
  toast: {
    kind: 'toast',
    id: 'card_toast_demo',
    text_key: 'toast.sleep',
    tone: 'neutral',
  },
}

function cardFromQuery(): BubbleCard | null {
  const params = new URLSearchParams(window.location.search)
  const kind = params.get('card')
  if (!kind) return null
  if (FIXTURE_CARDS[kind]) return FIXTURE_CARDS[kind]

  for (const scenario of SCENARIO_LIST) {
    for (const step of scenario.steps) {
      if (step.card && step.card.kind === kind) return step.card
    }
  }
  return null
}

function langFromQuery(): Lang {
  const raw = new URLSearchParams(window.location.search).get('lang')?.toLowerCase()
  if (raw === 'hi' || raw === 'hinglish') return raw
  return 'en'
}

export default function BubbleApp(): JSX.Element {
  const [card, setCard] = useState<BubbleCard | null>(() => cardFromQuery())
  const [tail, setTail] = useState<'left' | 'right'>('left')
  const [lang, setLang] = useState<Lang>(() => langFromQuery())
  const hostRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const off = api.onCard((next, side) => {
      setCard(next)
      setTail(side)
    })
    return off
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') api.hideBubble()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    const node = hostRef.current
    if (!node) return
    const observer = new ResizeObserver((entries) => {
      const height = Math.ceil(entries[0]?.contentRect.height ?? 0)
      if (height > 0) api.resizeBubble(height)
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [card])

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-start p-2 overflow-hidden bg-transparent">
      {/* Optional Tiny Dev Language Picker for Visual QA */}
      <div className="mb-1 flex w-full justify-end pr-1 opacity-40 transition-opacity hover:opacity-100 focus-within:opacity-100">
        <select
          value={lang}
          onChange={(event) => setLang(event.target.value as Lang)}
          aria-label="Language"
          className="cursor-pointer rounded-md border border-black/10 bg-[#FFFCF7]/85 px-1.5 py-0.5 font-mono text-[10px] text-slate-600 outline-none dark:border-white/15 dark:bg-[#1C1828]/85 dark:text-[#A8A0B8]"
        >
          <option value="en">en</option>
          <option value="hinglish">hinglish</option>
          <option value="hi">hi</option>
        </select>
      </div>

      <div ref={hostRef} className="flex w-full justify-center">
        <AnimatePresence mode="wait">
          {card ? (
            <motion.div
              key={card.id}
              initial={{ opacity: 0, scale: 0.94, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: -6 }}
              transition={{
                type: 'spring',
                stiffness: 420,
                damping: 24,
                mass: 0.8,
              }}
            >
              <BubbleCardView
                card={card}
                tail={tail}
                lang={lang}
                onAction={(actionId) => api.cardAction(card.id, actionId)}
                onClose={() => api.hideBubble()}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </div>
  )
}
