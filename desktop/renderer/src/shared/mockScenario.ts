/**
 * mockScenario.ts — three timed rehearsal scripts for `?view=stage`.
 *
 * These are UI fixtures, not detection logic. Every band or result here is a *relay* of what the
 * policy engine would decide; the mock never computes one. All data is fake on purpose:
 * accounts `••••4821`, IFSC `FAKC...`, domains `*.example`, people "Demo ...".
 */

import type {
  AskChip,
  Band,
  BubbleCard,
  CardAction,
  CompanionEvent,
  CompanionEventType,
  CompanionPayload,
  MascotMood,
  NextAction,
  OobTicket,
  Pose,
  ReportPackV2,
  ReportSection,
  UserMode,
} from '../../../shared/contracts'

export type ScenarioKey = 'cfo_call' | 'vendor_email' | 'money_left'

export interface ScenarioStep {
  at_ms: number
  event: CompanionEvent
  /** Update the bubble window. `null` hides it. Omit to leave it unchanged. */
  card?: BubbleCard | null
  pose?: Pose
}

export interface Scenario {
  key: ScenarioKey
  title: string
  subtitle: string
  duration_ms: number
  steps: ScenarioStep[]
}

// ---- Fake demo world ------------------------------------------------------------------------
const CASE_ID = 'case_demo_cfo_call'
const APPROVER = 'Demo Rajesh'
const VENDOR = 'Kaveri Traders (demo.example)'
const PAYEE = 'A/c ••••4821 · IFSC FAKC0000991'
const AMOUNT_INR = 4_850_000
const AMOUNT_TEXT = '₹48,50,000'
const GENERATED_AT = '2026-10-24T10:13:00.000Z'
const MONEY_LEFT_AT = '2026-10-24T10:12:00.000Z'

const ACTIONS = {
  start: [{ id: 'start_watching', variant: 'primary' }, { id: 'not_now', variant: 'ghost' }],
  listen: [{ id: 'listen_call', variant: 'primary' }, { id: 'not_this_call', variant: 'ghost' }],
  check: [{ id: 'check_it', variant: 'primary' }, { id: 'no_thanks', variant: 'ghost' }],
  alert: [
    { id: 'verify_with_approver', variant: 'primary' },
    { id: 'copy_safe_reply', variant: 'outline' },
    { id: 'open_notebook', variant: 'ghost' },
  ],
  oobWaiting: [{ id: 'open_notebook', variant: 'outline' }],
  oobResult: [
    { id: 'open_notebook', variant: 'primary' },
    { id: 'prepare_report', variant: 'outline' },
  ],
  report: [
    { id: 'open_reports', variant: 'primary' },
    { id: 'copy_safe_reply', variant: 'ghost' },
  ],
} satisfies Record<string, CardAction[]>

const NEXT = {
  alert: [
    { id: 'verify_with_approver', label: `Verify with ${APPROVER}`, variant: 'primary' },
    { id: 'copy_safe_reply', label: 'Copy a safe reply', variant: 'outline' },
    { id: 'open_notebook', label: 'Open Notebook', variant: 'outline' },
  ],
  report: [
    { id: 'open_reports', label: 'Open Reports', variant: 'primary' },
    { id: 'copy_safe_reply', label: 'Copy a safe reply', variant: 'outline' },
  ],
} satisfies Record<string, NextAction[]>

const CFO_CHIPS: AskChip[] = [
  { code: 'A1', at_s: 3.2 },
  { code: 'A4', at_s: 6.4 },
  { code: 'A5', at_s: 8.9 },
]

const MOOD: Record<CompanionPayload['state'], MascotMood> = {
  SLEEP: 'sleepy',
  ACTIVE: 'attentive',
  INVESTIGATING: 'focused',
  ALERT: 'calm_alert',
  SCRIBE: 'writing',
  DISABLED: 'off',
}

// ---- Event factory --------------------------------------------------------------------------
let sequence = 0

function event(
  type: CompanionEventType,
  payload: Partial<CompanionPayload> & Pick<CompanionPayload, 'state' | 'headline'>,
): CompanionEvent {
  sequence += 1
  const state = payload.state
  const full: CompanionPayload = {
    mascot_mood: MOOD[state],
    explanation: '',
    band: null,
    reason_codes: [],
    info_codes: [],
    evidence_ids: [],
    next_actions: [],
    monitoring: false,
    source: null,
    mode_label: null,
    demo: true,
    ...payload,
  }
  return {
    version: '1',
    event_id: `evt_demo_${String(sequence).padStart(8, '0')}`,
    type,
    session_id: 'session_demo_001',
    occurred_at: new Date(Date.UTC(2026, 9, 24, 10, 12, 0) + sequence * 1000).toISOString(),
    payload: full,
  }
}

// ---- Cards ----------------------------------------------------------------------------------
const consentCard: BubbleCard = {
  kind: 'consent',
  id: 'card_consent',
  scopes: ['Notice calls (no recording)', 'Listen to a call when you say yes', 'Check files you give me'],
  actions: ACTIONS.start,
}

const callAskCard: BubbleCard = {
  kind: 'call_ask',
  id: 'card_call_ask',
  source: 'replay',
  actions: ACTIONS.listen,
}

const liveCard: BubbleCard = {
  kind: 'live',
  id: 'card_live',
  chips: CFO_CHIPS,
  coverage: 'usable',
  seal: 'not_verified',
  elapsed_s: 12,
}

const alertCard: BubbleCard = {
  kind: 'alert',
  id: 'card_alert',
  band: 'HOLD',
  headline: 'Pause before you pay.',
  reasons: [
    'The caller asked for a new account.',
    'The caller asked to keep it secret and skip approval.',
    `This payment is ${AMOUNT_TEXT} to ${PAYEE}.`,
  ],
  chips: CFO_CHIPS,
  actions: ACTIONS.alert,
}

const ticket: OobTicket = {
  oob_id: 'oob_demo_001',
  case_id: CASE_ID,
  approver_name: APPROVER,
  channel: 'console',
  inbox_url: 'http://127.0.0.1:8000/oob/inbox/demo',
  expires_at: '2026-10-24T10:17:00.000Z',
}

const oobWaitCard: BubbleCard = {
  kind: 'oob_wait',
  id: 'card_oob_wait',
  approver_name: APPROVER,
  sent_at: '2026-10-24T10:12:30.000Z',
  actions: ACTIONS.oobWaiting,
}

const oobResultCard: BubbleCard = {
  kind: 'oob_result',
  id: 'card_oob_result',
  approver_name: APPROVER,
  outcome: 'not_requested',
  actions: ACTIONS.oobResult,
}

const scribeCard: BubbleCard = {
  kind: 'scribe',
  id: 'card_scribe',
  actions: ACTIONS.report,
  sections: [
    { id: 'helpline_1930', title: '1930 call script', status: 'writing' },
    { id: 'bank_fraud_desk', title: 'Bank fraud desk email', status: 'pending' },
    { id: 'ncrp_portal', title: 'NCRP / cybercrime.gov.in fields', status: 'pending' },
    { id: 'cert_in', title: 'CERT-In incident email', status: 'pending' },
    { id: 'bsa_s63_part_a', title: 'BSA §63 Part A (hashes)', status: 'pending' },
  ],
}

const resultCard: BubbleCard = {
  kind: 'result',
  id: 'card_result',
  band: 'VERIFY',
  headline: 'Verify first.',
  reasons: [
    'The bank account differs from the vendor master.',
    'Call the vendor on the number already on file — not the one in the email.',
  ],
  actions: [{ id: 'verify_with_approver', variant: 'primary' }, { id: 'open_notebook', variant: 'outline' }],
}

const fileAskCard: BubbleCard = {
  kind: 'file_ask',
  id: 'card_file_ask',
  file_name: 'Invoice_Oct.pdf',
  file_kind: 'pdf',
  actions: ACTIONS.check,
}

const toastCard: BubbleCard = {
  kind: 'toast',
  id: 'card_toast',
  text_key: 'scribe.done',
  tone: 'good',
}

// ---- Report pack (manual only) ---------------------------------------------------------------
export function reportPack(): ReportPackV2 {
  const fields = (section: ReportSection['id']): ReportSection => {
    if (section === 'helpline_1930') {
      return {
        id: 'helpline_1930',
        title: '1930 helpline — call script',
        destination: '1930 (national cyber-fraud helpline)',
        deadline_hint: 'Call now — the golden hour matters',
        body: `I am calling to report a suspected deepfake payment fraud. UTR: not provided — ask the maker. Amount: ${AMOUNT_TEXT}. Beneficiary: ${PAYEE}. Time: 24 Oct 2026, 10:12 IST. The request came on a call claiming to be our CFO. I did not verify it independently before paying.`,
        fields: [
          {
            label: 'UTR',
            value: 'Not provided — ask the maker',
            source: 'system',
            evidence_id: null,
            copy: true,
            sensitive: false,
          },
          {
            label: 'Amount',
            value: AMOUNT_TEXT,
            source: 'maker_entered',
            evidence_id: null,
            copy: true,
            sensitive: false,
          },
          {
            label: 'Beneficiary (masked)',
            value: PAYEE,
            source: 'vendor_master',
            evidence_id: null,
            copy: true,
            sensitive: true,
          },
        ],
        open_url: 'tel:1930',
        applies: true,
        status: 'DRAFT_REQUIRES_HUMAN_REVIEW',
      }
    }
    if (section === 'bank_fraud_desk') {
      return {
        id: 'bank_fraud_desk',
        title: 'Bank fraud desk — email draft',
        destination: 'Your bank fraud desk (from the bank’s own website)',
        deadline_hint: 'Same day',
        body: `Request: please hold or recall ${AMOUNT_TEXT} sent to ${PAYEE}. UTR: not provided — ask the maker. This payment followed a suspected impersonation call. Evidence files are listed with hashes in the pack.`,
        fields: [
          {
            label: 'Vendor',
            value: VENDOR,
            source: 'vendor_master',
            evidence_id: null,
            copy: true,
            sensitive: false,
          },
          {
            label: 'Evidence file',
            value: 'ev_demo_cfo_call_01 (demo fixture)',
            source: 'vault',
            evidence_id: 'ev_demo_cfo_call_01',
            copy: true,
            sensitive: false,
          },
        ],
        open_url: 'mailto:frauddesk@bank.example',
        applies: true,
        status: 'DRAFT_REQUIRES_HUMAN_REVIEW',
      }
    }
    if (section === 'ncrp_portal') {
      return {
        id: 'ncrp_portal',
        title: 'NCRP portal — field helper',
        destination: 'cybercrime.gov.in (the human logs in with their OTP)',
        deadline_hint: 'As soon as possible',
        body: 'Copy each field in the portal’s own order. Satya never submits the form and never logs in.',
        fields: [
          {
            label: 'Complaint category',
            value: 'Fraud / impersonation — payment fraud',
            source: 'system',
            evidence_id: null,
            copy: true,
            sensitive: false,
          },
          {
            label: 'Amount lost',
            value: AMOUNT_TEXT,
            source: 'maker_entered',
            evidence_id: null,
            copy: true,
            sensitive: false,
          },
          {
            label: 'Suspected channel',
            value: 'Voice call claiming to be the CFO (demo replay)',
            source: 'user_confirmed',
            evidence_id: null,
            copy: true,
            sensitive: false,
          },
        ],
        open_url: 'https://cybercrime.gov.in',
        applies: true,
        status: 'DRAFT_REQUIRES_HUMAN_REVIEW',
      }
    }
    if (section === 'cert_in') {
      return {
        id: 'cert_in',
        title: 'CERT-In — incident email',
        destination: 'incident@cert-in.org.in (confirm applicability with IT/legal)',
        deadline_hint: 'Direction says 6 hours if applicable',
        body: 'Body corporate incident notification draft. Whether this incident qualifies is a legal call — check with IT/legal.',
        fields: [
          {
            label: 'Incident type',
            value: 'Identity theft / impersonation (suspected)',
            source: 'user_confirmed',
            evidence_id: null,
            copy: true,
            sensitive: false,
          },
        ],
        open_url: 'mailto:incident@cert-in.org.in',
        applies: false,
        status: 'DRAFT_REQUIRES_HUMAN_REVIEW',
      }
    }
    return {
      id: 'bsa_s63_part_a',
      title: 'BSA 2023 §63 — Part A draft',
      destination: 'PDF export; a human signs. Part B needs an expert.',
      deadline_hint: null,
      body: 'Part A lists the SHA-256 hash of each evidence file, device particulars and the lawful-control statement. Draft only.',
      fields: [
        {
          label: 'Evidence hash',
          value: 'ev_demo_cfo_call_01 · SHA-256 computed by the demo vault',
          source: 'vault',
          evidence_id: 'ev_demo_cfo_call_01',
          copy: true,
          sensitive: false,
        },
        {
          label: 'Signatory',
          value: 'A human must sign — Satya cannot',
          source: 'system',
          evidence_id: null,
          copy: false,
          sensitive: false,
        },
      ],
      open_url: null,
      applies: true,
      status: 'DRAFT_REQUIRES_HUMAN_REVIEW',
    }
  }

  return {
    version: '2',
    case_id: CASE_ID,
    generated_at: GENERATED_AT,
    money_left_at: MONEY_LEFT_AT,
    sections: [
      fields('helpline_1930'),
      fields('bank_fraud_desk'),
      fields('ncrp_portal'),
      fields('cert_in'),
      fields('bsa_s63_part_a'),
    ],
    submission: 'MANUAL_ONLY',
    auto_submit: false,
  }
}

// ---- The three scripts ----------------------------------------------------------------------
const CFO_CALL: Scenario = {
  key: 'cfo_call',
  title: 'Deepfake CFO call',
  subtitle: 'Consent → call ask → live chips → alert → OOB rejected → Scribe',
  duration_ms: 24_000,
  steps: [
    {
      at_ms: 0,
      pose: 'wave',
      card: consentCard,
      event: event('session.started', {
        state: 'ACTIVE',
        headline: 'Watching is on — I ask before I listen.',
        explanation: 'Scope: notice calls, listen on your yes, check files you hand me.',
        user_mode: 'WATCHING',
        monitoring: true,
        source: 'demo_replay',
        mode_label: 'DEMO REPLAY — NOT LIVE CAPTURE',
      }),
    },
    {
      at_ms: 2_400,
      pose: 'listen',
      card: callAskCard,
      event: event('call.started', {
        state: 'ACTIVE',
        headline: 'Sounds like a call.',
        explanation:
          'Caller: "Priya, confidential acquisition. Transfer ₹48.5 lakh to this new escrow account today. Don\'t loop in Arjun."',
        call_id: 'call_demo_001',
        source: 'demo_replay',
      }),
    },
    {
      at_ms: 5_200,
      pose: 'listen',
      card: liveCard,
      event: event('live.chips', {
        state: 'ACTIVE',
        headline: 'Listening — payment trick words are showing up.',
        chips: CFO_CHIPS,
        coverage: 'usable',
        seal: 'not_verified',
        call_id: 'call_demo_001',
        monitoring: true,
      }),
    },
    {
      at_ms: 10_000,
      pose: 'alert',
      card: alertCard,
      event: event('alert.raised', {
        state: 'ALERT',
        headline: 'Pause before you pay.',
        explanation:
          'This call asked for a new account, secrecy and skipping approval. That does not prove who is speaking — verify the payment with Demo Rajesh on his own phone.',
        band: 'HOLD',
        reason_codes: ['ASK_NEW_ACCOUNT', 'ASK_SECRECY', 'ASK_BYPASS_APPROVAL'],
        chips: CFO_CHIPS,
        evidence_ids: ['ev_demo_cfo_call_01'],
        next_actions: NEXT.alert,
      }),
    },
    {
      at_ms: 13_200,
      pose: 'think',
      card: oobWaitCard,
      event: event('oob.sent', {
        state: 'ALERT',
        headline: `Asked ${APPROVER} on their own phone.`,
        explanation: 'The approver and channel come only from the employee directory.',
        band: 'HOLD',
        ticket,
        oob: { oob_id: ticket.oob_id, approver_name: APPROVER },
      }),
    },
    {
      at_ms: 17_200,
      pose: 'alert',
      card: oobResultCard,
      event: event('oob.result', {
        state: 'ALERT',
        headline: `${APPROVER} says they did not ask for this.`,
        explanation: 'I have put this payment on hold. Silence would also never be a yes.',
        band: 'HOLD',
        oob: { oob_id: ticket.oob_id, approver_name: APPROVER, outcome: 'not_requested' },
      }),
    },
    {
      at_ms: 20_000,
      pose: 'write',
      card: scribeCard,
      event: event('report.ready', {
        state: 'SCRIBE',
        headline: 'Writing your report pack.',
        explanation: 'Five drafts. You review and submit; Satya files nothing.',
        band: 'HOLD',
        report: reportPack(),
        next_actions: NEXT.report,
      }),
    },
    {
      at_ms: 22_000,
      card: toastCard,
      event: event('case.updated', {
        state: 'SCRIBE',
        headline: 'Done. 5 drafts ready — you review and submit.',
        band: 'HOLD',
        report: reportPack(),
        monitoring: false,
      }),
    },
  ],
}

const VENDOR_EMAIL: Scenario = {
  key: 'vendor_email',
  title: 'Vendor email + edited invoice',
  subtitle: 'File ask → checks → result VERIFY (account differs from vendor master)',
  duration_ms: 7_000,
  steps: [
    {
      at_ms: 0,
      pose: 'catch',
      card: fileAskCard,
      event: event('evidence.received', {
        state: 'INVESTIGATING',
        headline: 'Should I read this?',
        explanation: 'Invoice_Oct.pdf was handed over by the maker. Hash first, then check.',
        case_id: 'case_demo_vendor_email',
      }),
    },
    {
      at_ms: 2_200,
      pose: 'think',
      card: null,
      event: event('analysis.started', {
        state: 'INVESTIGATING',
        headline: 'Checking the invoice against the vendor master.',
        case_id: 'case_demo_vendor_email',
      }),
    },
    {
      at_ms: 4_200,
      pose: 'alert',
      card: resultCard,
      event: event('analysis.completed', {
        state: 'ALERT',
        headline: 'Verify first — the bank account differs from the vendor master.',
        explanation:
          'The email passed its domain checks, but the account in the invoice is new. Call the vendor on their registered number.',
        band: 'VERIFY',
        reason_codes: ['FLOOR_PAYEE_CHANGE', 'DOC_ACCOUNT_DIFFERS_FROM_MASTER'],
        evidence_ids: ['ev_demo_vendor_invoice_01'],
      }),
    },
    {
      at_ms: 5_800,
      pose: 'idle',
      event: event('case.updated', {
        state: 'ACTIVE',
        headline: 'Added to the case. Nothing was sent anywhere.',
        band: 'VERIFY',
        case_id: 'case_demo_vendor_email',
      }),
    },
  ],
}

const MONEY_LEFT: Scenario = {
  key: 'money_left',
  title: 'Money already left',
  subtitle: 'Scribe → 5 manual drafts → golden-hour timer',
  duration_ms: 8_000,
  steps: [
    {
      at_ms: 0,
      pose: 'write',
      card: scribeCard,
      event: event('draft.ready', {
        state: 'SCRIBE',
        headline: 'Money already left? I can prepare your report pack now.',
        explanation: 'Every minute counts. I will not file anything — you review and submit.',
        case_id: CASE_ID,
      }),
    },
    {
      at_ms: 2_600,
      pose: 'write',
      card: toastCard,
      event: event('report.ready', {
        state: 'SCRIBE',
        headline: 'Done. 5 drafts ready — you review and submit.',
        explanation:
          '1930 script (UTR on line 1), bank email, NCRP field helper, CERT-In draft, BSA §63 Part A with hashes.',
        band: 'HOLD',
        report: reportPack(),
        next_actions: NEXT.report,
      }),
    },
    {
      at_ms: 4_600,
      event: event('case.updated', {
        state: 'SCRIBE',
        headline: 'Golden-hour timer started from the money-left time.',
        explanation: 'MANUAL_ONLY: Satya prepares, a human sends.',
        report: reportPack(),
      }),
    },
  ],
}

export const SCENARIOS: Record<ScenarioKey, Scenario> = {
  cfo_call: CFO_CALL,
  vendor_email: VENDOR_EMAIL,
  money_left: MONEY_LEFT,
}

export const SCENARIO_LIST: Scenario[] = [CFO_CALL, VENDOR_EMAIL, MONEY_LEFT]

export function scenarioFor(key: string | null | undefined): Scenario {
  if (key === 'vendor_email' || key === 'money_left') return SCENARIOS[key]
  return SCENARIOS.cfo_call
}

/** The steps whose `at_ms` has been reached, in order. Pure: the stage view owns the clock. */
export function stepsUntil(scenario: Scenario, elapsedMs: number): ScenarioStep[] {
  return scenario.steps.filter((step) => step.at_ms <= elapsedMs)
}

export const DEMO_USER_MODE: UserMode = 'WATCHING'
export const DEMO_BAND: Band = 'HOLD'
