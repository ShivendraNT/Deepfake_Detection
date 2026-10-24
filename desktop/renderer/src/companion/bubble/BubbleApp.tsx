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

  // Language comes from the user's preference (Notebook → Settings); `?lang=` for visual QA.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('lang')) return
    void api
      .getPrefs()
      .then((prefs) => {
        if (prefs.lang) setLang(prefs.lang)
      })
      .catch(() => undefined)
  }, [card?.id])

  // Close / Esc go through the mascot's reducer, so it knows the card is gone.
  const dismiss = (): void => {
    if (card) api.cardAction(card.id, 'dismiss')
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape' && card) api.cardAction(card.id, 'dismiss')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [card])

  // The window is exactly as tall as the card (+ the 8 px padding and room for the shadow).
  useEffect(() => {
    const node = hostRef.current
    if (!node) return
    const observer = new ResizeObserver((entries) => {
      const height = Math.ceil(entries[0]?.contentRect.height ?? 0)
      if (height > 0) api.resizeBubble(height + 28)
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [card])

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-start overflow-hidden bg-transparent p-2">
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
                onClose={dismiss}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </div>
  )
}
