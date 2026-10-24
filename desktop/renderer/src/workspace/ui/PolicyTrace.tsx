/**
 * Expert view: how the policy engine reached the band. Floor first (trusted data only), then each
 * raise-only signal with its group, strength, source and target rule, then what clears it.
 * There is no score anywhere in this view by construction (the contract has no score field).
 */

import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import type { PolicyTrace as Trace } from '../../../../shared/contracts'
import { reasonLabel } from '../../companion/reasonLabels'
import { FONT_MONO, inset, surface, tone } from './theme'

const TARGET_WORDS: Record<string, string> = {
  NONE: 'information only',
  VERIFY: 'raises to Verify',
  HOLD: 'raises to Hold',
  VERIFY_HOLD_IF_FLOOR_GE_VERIFY: 'Verify, or Hold if the payment already needs Verify',
  PLUS_ONE: 'one band above the floor',
  HOLD_IF_MONEY_ELSE_VERIFY: 'Hold if money is being moved, else Verify',
}

const SOURCE_WORDS: Record<string, string> = {
  deterministic: 'rule',
  ml: 'model (capped)',
  llm: 'LLM (capped at Verify)',
  human: 'person',
}

export default function PolicyTrace({ trace }: { trace: Trace }): JSX.Element {
  const [open, setOpen] = useState(false)
  return (
    <div className={`${inset} mt-3 overflow-hidden`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-[12.5px] font-semibold"
        aria-expanded={open}
      >
        Expert view: how the policy decided
        <ChevronDown size={15} className={`transition ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      {open ? (
        <div className="space-y-3 border-t px-3 pb-3 pt-2 text-[12px]" style={{ borderColor: 'rgba(42,34,56,0.08)' }}>
          <div>
            <p className={`font-semibold ${surface.muted}`}>1 · Floor (payment vs vendor master only)</p>
            <p className="mt-1">
              Action <span style={{ fontFamily: FONT_MONO }}>{trace.action_type}</span> → floor band{' '}
              <b>{trace.floor_band}</b>. Messages, files and calls cannot lower this.
            </p>
          </div>
          <div>
            <p className={`font-semibold ${surface.muted}`}>2 · Signals (each can only raise)</p>
            {trace.signals.length === 0 ? (
              <p className="mt-1">No signals.</p>
            ) : (
              <ul className="mt-1 space-y-1.5">
                {trace.signals.map((s, i) => (
                  <li key={`${s.code}-${i}`} className="border-t pt-1.5" style={{ borderColor: 'rgba(42,34,56,0.06)' }}>
                    <p className="font-medium">{reasonLabel(s.code)}</p>
                    <p className={`text-[10.5px] ${surface.muted}`} style={{ fontFamily: FONT_MONO }}>
                      {s.code} · {s.detector}
                    </p>
                    <p className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[11.5px]">
                      <span>{s.group.replace(/_/g, ' ')}</span>
                      <span style={{ color: s.strength === 'strong' ? tone.coral : undefined }}>{s.strength}</span>
                      <span>{SOURCE_WORDS[s.source] ?? s.source}</span>
                      <span className={surface.muted}>→ {TARGET_WORDS[s.target] ?? s.target}</span>
                    </p>
                  </li>
                ))}
              </ul>
            )}
            {trace.grey ? <p className="mt-1" style={{ color: tone.amber }}>A detector could not finish, so the case is grey (never treated as safe).</p> : null}
          </div>
          <div>
            <p className={`font-semibold ${surface.muted}`}>3 · What clears it</p>
            <p className="mt-1">
              {trace.clearance_methods.length > 0
                ? `${trace.clearance_methods.map((m) => m.replace(/_/g, ' ').toLowerCase()).join(', ')}${
                    trace.clearance_who.length ? ` by ${trace.clearance_who.join(' / ')}` : ''
                  }. Clearing never lowers the band; it records who verified.`
                : 'Nothing extra is needed.'}
            </p>
            {trace.clearance_notes.map((note) => (
              <p key={note} className={`mt-0.5 ${surface.muted}`}>{note}</p>
            ))}
          </div>
          <p className={surface.muted} style={{ fontFamily: FONT_MONO }}>policy {trace.policy_version}</p>
        </div>
      ) : null}
    </div>
  )
}
