/** Human labels for reason codes. Raw detector scores are never present in the payload. */

const LABELS: Record<string, string> = {
  FLOOR_K1_KNOWN_IN_PATTERN: 'Known payee, usual amount',
  FLOOR_K2_OUT_OF_PATTERN: 'Known payee, out-of-pattern amount',
  FLOOR_N1_NEW_SMALL: 'New payee, small amount',
  FLOOR_N2_NEW_LARGE: 'New payee above the small-payment limit',
  FLOOR_C1_BANK_CHANGED: 'Bank details differ from the vendor master',
  FLOOR_T1_TRUST_ANCHOR: 'Change to a saved trust anchor',
  FLOOR_D1_DATA_REQUEST: 'Data or login request',
  FLOOR_NONE: 'No pending payment yet',
  EMAIL_DMARC_FAIL: 'Sender domain failed DMARC',
  EMAIL_LOOKALIKE_DOMAIN: 'Look-alike sender domain',
  EMAIL_REPLYTO_MISMATCH: 'Reply-to differs from the sender',
  EMAIL_FREEMAIL_CORPORATE: 'Corporate claim from a free mailbox',
  DOC_ACCOUNT_MISMATCH: 'Invoice account differs from the master',
  DOC_PDF_EDITED: 'PDF edit metadata found',
  VOICE_INCONCLUSIVE: 'Voice Analysis: Inconclusive audio sample',
  VOICE_LIKELY_SYNTHETIC: 'AI Voice Clone: Neural acoustic synthesis & vocoder artifacts detected',
  VIDEO_INCONCLUSIVE: 'Face check: unsure, or the face was too small / dark to judge',
  VIDEO_LIKELY_SYNTHETIC: 'Face check: swapped or AI-made face in two windows in a row',
  VIDEO_NO_SIGNS: 'Face check: no deepfake signs (not proof)',
  VOICE_UNSEALED_CLAIMED_EXEC: 'VoiceSeal Missing: Executive voice lacks authentic cryptographic hardware key',
  ASK_NEW_ACCOUNT: 'Asked to pay a new account',
  ASK_CREDENTIAL: 'Asked for an OTP, PIN or password',
  ASK_REMOTE_ACCESS: 'Asked to install remote access (AnyDesk/TeamViewer)',
  ASK_SECRECY: 'Asked to keep transaction confidential/secret',
  ASK_BYPASS: 'Asked to bypass normal maker-checker approval',
  ASK_UNUSUAL_PAYMENT_METHOD: 'Unusual payment method instruction',
  ASK_PAYEE_CHANGE: 'Asked to change beneficiary payee',
  STYLE_PRESSURE: 'High-pressure urgency or authority coercion',
  TEXT_SCAM_LIKELY: 'Reads like known scam / phishing messages (text model)',
  WATCHLIST_HIT: 'Matches the watchlist',
  MULTI_GROUP_STRONG: 'Independent forensic checks agree',
  GREY_FLAG: 'A check could not complete',
  OOB_DENIED: 'Out-of-Band Denied: Real executive rejected the payment on mobile',
  OOB_APPROVED: 'Out-of-Band Approved: Real executive confirmed the payment on mobile',
  SEAL_PRESENCE_CONFLICT: 'Executive Impersonation: Key active in another meeting',
}

export function reasonLabel(code: string): string {
  if (LABELS[code]) return LABELS[code]
  return code
    .toLowerCase()
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export const BAND_COPY: Record<
  string,
  { label: string; text: string; border: string; bg: string }
> = {
  PASS: {
    label: 'PASS',
    text: 'text-mint-300',
    border: 'border-mint-400/30',
    bg: 'bg-mint-400/10',
  },
  VERIFY: {
    label: 'VERIFY',
    text: 'text-amber-300',
    border: 'border-amber-400/30',
    bg: 'bg-amber-400/10',
  },
  HOLD: {
    label: 'HOLD',
    text: 'text-rose-300',
    border: 'border-rose-400/30',
    bg: 'bg-rose-400/10',
  },
}
