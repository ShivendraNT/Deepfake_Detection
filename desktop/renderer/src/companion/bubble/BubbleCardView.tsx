/**
 * BubbleCardView — renders exactly ONE `BubbleCard` (docs/finale/MASCOT_SPEC.md §7).
 * Copy stays short and calm. No gradients, no emoji, no scores, no raw numbers but money.
 */

import type { AskChip, Band, BubbleCard, CardAction } from '../../../../shared/contracts'
import { ASK_LABELS } from '../../../../shared/contracts'

const ACCENT: Record<Band, string> = {
  PASS: '#3CCB7F',
  VERIFY: '#FFB020',
  HOLD: '#FF6B5E',
}

const TOAST_TEXT: Record<string, string> = {
  'scribe.done': 'Done. 5 drafts ready — you review and submit.',
  'toast.sleep': "Sleeping. I'm not listening.",
  'toast.off': 'Bye! Bring me back from the menu bar.',
}

// Temporary local copy until F08 lands shared/copy.ts. Wording is from MASCOT_SPEC §8.
const ACTION_LABELS: Record<string, string> = {
  start_watching: 'Start watching',
  not_now: 'Not now',
  listen_call: 'Listen to this call',
  not_this_call: 'Not this one',
  check_it: 'Check it',
  no_thanks: 'No thanks',
  verify_with_approver: 'Verify with the approver',
  copy_safe_reply: 'Copy a safe reply',
  open_notebook: 'Open Notebook',
  open_reports: 'Open Reports',
  prepare_report: 'Prepare it',
  dismiss: 'Close',
}

function actionLabel(id: string): string {
  return ACTION_LABELS[id] ?? id.replace(/_/g, ' ')
}

const OOB_TEXT: Record<'approved' | 'rejected' | 'not_requested' | 'expired', (name: string) => string> = {
  approved: (name) => `${name} confirmed this exact payment. You can continue.`,
  rejected: (name) => `${name} rejected this request. Keep the payment on hold.`,
  not_requested: (name) => `${name} says they didn't ask for this. I've put the payment on hold.`,
  expired: (name) => `No answer from ${name} — that is not a yes. Keep it on hold.`,
}

export interface BubbleCardViewProps {
  card: BubbleCard
  onAction: (actionId: string) => void
  tail?: 'left' | 'right'
}

function accentFor(card: BubbleCard): string {
  if (card.kind === 'alert' || card.kind === 'result') return ACCENT[card.band]
  if (card.kind === 'oob_result') return card.outcome === 'approved' ? ACCENT.PASS : ACCENT.HOLD
  if (card.kind === 'oob_wait') return ACCENT.VERIFY
  if (card.kind === 'scribe') return '#9C8CFF'
  if (card.kind === 'live') return '#1FB5A3'
  return '#8C96AA'
}

function titleFor(card: BubbleCard): string {
  switch (card.kind) {
    case 'consent':
      return 'Can I keep watch?'
    case 'call_ask':
      return 'Sounds like a call.'
    case 'file_ask':
      return 'Should I read this?'
    case 'live':
      return 'Listening…'
    case 'result':
    case 'alert':
      return card.headline
    case 'oob_wait':
      return `Asked ${card.approver_name} on their own phone. Waiting…`
    case 'oob_result':
      return OOB_TEXT[card.outcome](card.approver_name)
    case 'scribe':
      return 'Writing your report pack…'
    case 'toast':
      return TOAST_TEXT[card.text_key] ?? card.text_key
  }
}

function chips(chips: AskChip[]): JSX.Element {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <span
          key={`${chip.code}-${chip.at_s ?? 'x'}`}
          className="rounded-full bg-slate-800/10 px-2.5 py-1 text-[12px] text-slate-700"
        >
          {ASK_LABELS[chip.code]}
        </span>
      ))}
    </div>
  )
}

function reasons(lines: string[]): JSX.Element {
  return (
    <ul className="mt-2 space-y-1 text-[13px] leading-snug text-slate-600">
      {lines.map((line) => (
        <li key={line} className="flex gap-2">
          <span aria-hidden className="text-slate-400">
            ·
          </span>
          <span>{line}</span>
        </li>
      ))}
    </ul>
  )
}

function actions(list: CardAction[] | undefined, accent: string, onAction: (id: string) => void): JSX.Element | null {
  if (!list || list.length === 0) return null
  return (
    <div className="mt-3 flex flex-col gap-1.5">
      {list.slice(0, 3).map((action) => {
        if (action.variant === 'primary') {
          return (
            <button
              key={action.id}
              type="button"
              onClick={() => onAction(action.id)}
              style={{ backgroundColor: accent }}
              className="h-9 rounded-[10px] text-[13px] font-semibold text-white"
            >
              {actionLabel(action.id)}
            </button>
          )
        }
        if (action.variant === 'outline') {
          return (
            <button
              key={action.id}
              type="button"
              onClick={() => onAction(action.id)}
              className="h-9 rounded-[10px] border border-slate-300 text-[13px] font-medium text-slate-700"
            >
              {actionLabel(action.id)}
            </button>
          )
        }
        return (
          <button
            key={action.id}
            type="button"
            onClick={() => onAction(action.id)}
            className="h-8 text-[12px] text-slate-500"
          >
            {actionLabel(action.id)}
          </button>
        )
      })}
    </div>
  )
}

export default function BubbleCardView({ card, onAction, tail = 'left' }: BubbleCardViewProps): JSX.Element {
  const accent = accentFor(card)
  return (
    <div className="relative w-[340px]">
      <div
        className="relative rounded-[18px] border border-black/10 bg-[#FFFCF7] p-4 text-slate-800 shadow-[0_12px_32px_rgba(20,16,40,0.22)]"
        data-card-kind={card.kind}
        data-card-id={card.id}
      >
        <div className="flex items-start gap-2">
          <span
            aria-hidden
            className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
            style={{ backgroundColor: accent }}
          />
          <h2 className="text-[15px] font-semibold leading-snug text-slate-800">{titleFor(card)}</h2>
        </div>

        {card.kind === 'consent' && (
          <>
            <p className="mt-2 text-[13.5px] leading-relaxed text-slate-600">
              I&apos;ll notice when a call starts and ask before I listen. I only look for payment
              tricks. Nothing is saved unless you say so.
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {card.scopes.map((scope) => (
                <span
                  key={scope}
                  className="rounded-full bg-slate-800/10 px-2.5 py-1 text-[12px] text-slate-700"
                >
                  {scope}
                </span>
              ))}
            </div>
          </>
        )}

        {card.kind === 'call_ask' && (
          <p className="mt-2 text-[13.5px] leading-relaxed text-slate-600">
            Want me to listen for payment tricks? I won&apos;t record it.
          </p>
        )}

        {card.kind === 'file_ask' && (
          <p className="mt-2 text-[13.5px] leading-relaxed text-slate-600">
            I&apos;ll check &ldquo;{card.file_name}&rdquo; and keep its fingerprint in your Notebook.
          </p>
        )}

        {card.kind === 'live' && (
          <>
            {chips(card.chips)}
            <p className="mt-2 text-[12px] text-slate-500">
              {card.coverage === 'usable' ? 'Audio is clear.' : 'Audio is unclear — I won’t judge the voice.'}
              {' '}
              {card.seal === 'verified' ? 'Voice verified by Seal.' : 'Voice not verified by Seal.'}
              {' '}
              {card.elapsed_s}s
            </p>
          </>
        )}

        {card.kind === 'alert' && (
          <>
            {chips(card.chips)}
            {reasons(card.reasons)}
            <p className="mt-2 text-[12px] leading-relaxed text-slate-500">
              That doesn&apos;t prove who is speaking — let&apos;s check the payment with the approver
              on their own phone.
            </p>
          </>
        )}

        {card.kind === 'result' && reasons(card.reasons)}

        {card.kind === 'oob_wait' && (
          <p className="mt-2 text-[13.5px] leading-relaxed text-slate-600">
            The approver and channel come from the employee directory, never from the call.
          </p>
        )}

        {card.kind === 'oob_result' && (
          <p className="mt-2 text-[13.5px] leading-relaxed text-slate-600">
            {card.outcome === 'not_requested'
              ? 'This payment stays on hold until a human verifies it.'
              : 'A human still decides what happens next.'}
          </p>
        )}

        {card.kind === 'scribe' && (
          <ul className="mt-2 space-y-1 text-[13px] text-slate-600">
            {card.sections.map((section) => (
              <li key={section.id} className="flex items-center justify-between gap-2">
                <span>{section.title}</span>
                <span className="text-[11px] uppercase tracking-wide text-slate-400">
                  {section.status}
                </span>
              </li>
            ))}
          </ul>
        )}

        {card.kind === 'toast' && (
          <p className="mt-1 text-[13.5px] leading-relaxed text-slate-600">You review and submit.</p>
        )}

        {card.kind !== 'live' && card.kind !== 'toast' && actions(card.actions, accent, onAction)}
      </div>
      <span
        aria-hidden
        className="absolute top-10 h-3 w-3 rotate-45 border bg-[#FFFCF7]"
        style={{
          borderColor: 'rgba(42,34,56,0.10)',
          left: tail === 'left' ? '-7px' : undefined,
          right: tail === 'right' ? '-7px' : undefined,
        }}
      />
    </div>
  )
}
