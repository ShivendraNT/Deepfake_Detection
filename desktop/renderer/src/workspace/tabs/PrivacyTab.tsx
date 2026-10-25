import {
  Bell,
  Check,
  FileCheck2,
  Laptop,
  Lock,
  MicOff,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useState } from 'react'

import type { CompanionState } from '../../../../shared/contracts'
import { api } from '../../shared/api'
import { formatDateTime } from '../lib/format'
import { EMPTY_LIVE } from '../lib/live'
import { satyaStatus } from '../lib/status'
import Section from '../ui/Section'
import { button, inset, surface, tone } from '../ui/theme'

export interface PrivacyTabProps {
  state: CompanionState | null
}

type DeleteState = 'idle' | 'confirm' | 'sending' | 'done' | 'error'

function ScopeRow({
  icon: Icon,
  label,
  detail,
  status,
  color,
}: {
  icon: LucideIcon
  label: string
  detail: string
  status: string
  color: string
}): JSX.Element {
  return (
    <li className="flex items-start gap-3 py-3">
      <span
        className={`grid h-8 w-8 shrink-0 place-items-center rounded-full border ${surface.line} ${inset}`}
        aria-hidden="true"
      >
        <Icon size={14} style={{ color }} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium">{label}</p>
        <p className={`mt-1 text-[12px] leading-relaxed ${surface.muted}`}>{detail}</p>
      </div>
      <span className="shrink-0 text-[12px] font-semibold" style={{ color }}>
        {status}
      </span>
    </li>
  )
}

export default function PrivacyTab({ state }: PrivacyTabProps): JSX.Element {
  const [deleteState, setDeleteState] = useState<DeleteState>('idle')
  const [message, setMessage] = useState('')

  const status = satyaStatus(state, EMPTY_LIVE)
  const sessionActive = status.sessionActive

  async function removeSessionData(): Promise<void> {
    if (deleteState === 'idle') {
      setDeleteState('confirm')
      return
    }
    if (deleteState === 'sending' || deleteState === 'done') return

    setDeleteState('sending')
    try {
      const result = await api.command('privacy.delete_session')
      if (!result.ok) {
        setDeleteState('error')
        setMessage(result.error)
        return
      }
      if (!result.data.accepted) {
        setDeleteState('error')
        setMessage('The request was not accepted yet. No data was deleted.')
        return
      }
      setDeleteState('done')
      setMessage('Delete request accepted. This session’s buffers will be cleared.')
    } catch (reason) {
      setDeleteState('error')
      setMessage(reason instanceof Error ? reason.message : 'The request could not be sent.')
    }
  }

  return (
    <div className="space-y-4">
      <Section
        title="On this laptop"
        description="Satya is a local guardian. Your notes do not leave this machine."
      >
        <div
          className={`flex items-start gap-3 rounded-[14px] border px-4 py-4`}
          style={{ borderColor: `${tone.watch}33`, backgroundColor: `${tone.watch}0D` }}
        >
          <span
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full"
            style={{ backgroundColor: `${tone.watch}1A` }}
            aria-hidden="true"
          >
            <Laptop size={17} style={{ color: tone.watch }} />
          </span>
          <p className="text-[14px] font-medium leading-relaxed">
            Satya runs on this laptop. He never uses your microphone. Call audio stays in memory
            unless you tap &lsquo;Keep as evidence&rsquo;.
          </p>
        </div>
      </Section>

      <div className="grid grid-cols-2 gap-4">
        <Section title="What is on right now">
          <ul className="divide-y divide-[rgba(42,34,56,0.08)] dark:divide-[rgba(237,232,245,0.08)]">
            <ScopeRow
              icon={Bell}
              label="Notice calls (no recording)"
              detail="Satya notices that a call started and shows you a card. Recording never starts by itself."
              status={sessionActive ? 'On' : 'Off'}
              color={sessionActive ? tone.green : tone.slate}
            />
            <ScopeRow
              icon={FileCheck2}
              label="Check files you give me"
              detail={
                sessionActive
                  ? 'Only files you drag in or hand over are opened, hashed and checked.'
                  : 'Available only while a consented session is on.'
              }
              status={sessionActive ? 'On' : 'Off'}
              color={sessionActive ? tone.green : tone.slate}
            />
            <ScopeRow
              icon={MicOff}
              label="Microphone"
              detail="Satya never opens the microphone, in any mode. Call audio comes from the source you choose."
              status="Never"
              color={tone.slate}
            />
          </ul>
        </Section>

        <Section title="Consent receipt">
          {state ? (
            <dl className="grid grid-cols-2 gap-4 text-[12px]">
              <div>
                <dt className={surface.muted}>Session</dt>
                <dd className="mt-1 break-words font-medium">{state.session_id ?? 'None'}</dd>
              </div>
              <div>
                <dt className={surface.muted}>Consent</dt>
                <dd className="mt-1 break-words font-medium">{state.consent_id ?? 'None'}</dd>
              </div>
              <div>
                <dt className={surface.muted}>Started</dt>
                <dd className="mt-1 font-medium">{formatDateTime(state.started_at)}</dd>
              </div>
              <div>
                <dt className={surface.muted}>Expires</dt>
                <dd className="mt-1 font-medium">{formatDateTime(state.expires_at)}</dd>
              </div>
              <div className="col-span-2">
                <dt className={surface.muted}>Source</dt>
                <dd className="mt-1 font-medium">{state.source_label ?? 'No source selected'}</dd>
              </div>
            </dl>
          ) : (
            <p className={`text-[12px] leading-relaxed ${surface.muted}`}>
              No active consent. Satya is sleeping, and no scope is on.
            </p>
          )}
        </Section>
      </div>

      <Section
        title="What is kept, and why"
        description="The Notebook keeps only what it needs to explain a decision and prove a file did not change."
      >
        <ul className="space-y-2 text-[12px] leading-relaxed">
          <li className="flex items-start gap-2">
            <ShieldCheck
              size={14}
              className="mt-0.5 shrink-0"
              style={{ color: tone.green }}
              aria-hidden="true"
            />
            <span>Call audio stays in memory. It is kept only when you choose Keep as evidence.</span>
          </li>
          <li className="flex items-start gap-2">
            <Lock
              size={14}
              className="mt-0.5 shrink-0"
              style={{ color: tone.watch }}
              aria-hidden="true"
            />
            <span>
              Files you hand over keep a SHA-256 fingerprint and a custody row, so tampering is
              visible.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <FileCheck2
              size={14}
              className="mt-0.5 shrink-0"
              style={{ color: tone.write }}
              aria-hidden="true"
            />
            <span>Report drafts stay drafts. Nothing is sent to 1930, NCRP, a bank or the police.</span>
          </li>
        </ul>

        <div className={`mt-4 flex flex-wrap items-center gap-3 border-t pt-4 ${surface.line}`}>
          <button
            type="button"
            onClick={() => void removeSessionData()}
            disabled={deleteState === 'sending' || deleteState === 'done'}
            className={button.danger}
          >
            {deleteState === 'sending' ? (
              <RefreshCw size={14} className="animate-spin" aria-hidden="true" />
            ) : deleteState === 'done' ? (
              <Check size={14} aria-hidden="true" />
            ) : (
              <Trash2 size={14} aria-hidden="true" />
            )}
            {deleteState === 'idle'
              ? 'Delete session data'
              : deleteState === 'confirm'
                ? 'Confirm delete'
                : deleteState === 'sending'
                  ? 'Deleting…'
                  : deleteState === 'done'
                    ? 'Session data deleted'
                    : 'Try again'}
          </button>
          {message ? (
            <p
              className={`text-[12px] ${deleteState === 'error' ? 'text-[#C24136] dark:text-[#FF9A90]' : surface.muted}`}
              role="status"
            >
              {message}
            </p>
          ) : (
            <p className={`text-[12px] ${surface.muted}`}>
              This clears this session’s buffers. Saved evidence stays until you delete it.
            </p>
          )}
        </div>
      </Section>
    </div>
  )
}
