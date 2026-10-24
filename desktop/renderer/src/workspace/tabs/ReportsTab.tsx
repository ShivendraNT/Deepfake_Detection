import { Clock3, FileText, Lock, ShieldCheck } from 'lucide-react'

import Empty from '../ui/Empty'
import Section from '../ui/Section'
import { inset, surface, tone } from '../ui/theme'

const SECTIONS = [
  { title: '1930 helpline — call script', detail: 'UTR first. A human makes the call.' },
  { title: 'Bank fraud desk — email draft', detail: 'The human sends it from their own mailbox.' },
  { title: 'NCRP portal — field helper', detail: 'Copy each field. Satya never logs in.' },
  { title: 'CERT-In — incident draft', detail: 'Applicability is a legal call.' },
  { title: 'BSA 2023 §63 — Part A', detail: 'Hashes listed. A human signs.' },
]

export default function ReportsTab(): JSX.Element {
  return (
    <div className="space-y-4">
      <Section
        title="Golden-Hour Reports (F15)"
        description="The Scribe animation and the five-step checklist arrive with F15. The guarantees are already fixed."
      >
        <div
          className={`flex items-start gap-3 rounded-[14px] border px-4 py-4`}
          style={{ borderColor: `${tone.amber}40`, backgroundColor: `${tone.amber}10` }}
        >
          <span
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full"
            style={{ backgroundColor: `${tone.amber}1A` }}
            aria-hidden="true"
          >
            <ShieldCheck size={17} style={{ color: tone.amber }} />
          </span>
          <div>
            <p className="text-[14px] font-semibold">
              Drafts only. Nothing has been sent. You review and submit.
            </p>
            <p className={`mt-1 text-[12px] leading-relaxed ${surface.muted}`}>
              There is no auto-reporting path. Satya prepares the words and the hashes; a human opens
              each destination and presses Submit.
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          {SECTIONS.map((section) => (
            <div
              key={section.title}
              className={`flex items-start gap-2 rounded-[10px] border px-3 py-3 ${surface.line} ${inset}`}
            >
              <FileText
                size={14}
                className="mt-0.5 shrink-0"
                style={{ color: tone.slate }}
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className="text-[13px] font-medium">{section.title}</p>
                <p className={`mt-1 text-[12px] leading-relaxed ${surface.muted}`}>{section.detail}</p>
              </div>
            </div>
          ))}
        </div>

        <div className={`mt-4 flex items-center gap-2 text-[12px] ${surface.muted}`}>
          <Lock size={13} aria-hidden="true" />
          <span>Manual submission only, by design.</span>
          <span aria-hidden="true">·</span>
          <Clock3 size={13} aria-hidden="true" />
          <span>The golden-hour timer starts from the money-left time.</span>
        </div>
      </Section>

      <Section>
        <Empty
          icon={FileText}
          title="No report pack yet"
          body="When money has already left, the pack will write itself here — section by section, with a source under each line. Until then, nothing exists and nothing was sent."
        />
      </Section>
    </div>
  )
}
