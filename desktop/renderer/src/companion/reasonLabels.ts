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
  VOICE_INCONCLUSIVE: 'Voice result inconclusive',
  VOICE_LIKELY_SYNTHETIC: 'Voice shows synthetic signs',
  VOICE_UNSEALED_CLAIMED_EXEC: 'Claimed executive is not sealed',
  ASK_NEW_ACCOUNT: 'Asked to pay a new account',
  ASK_CREDENTIAL: 'Asked for an OTP, PIN or password',
  ASK_REMOTE_ACCESS: 'Asked to install remote access',
  ASK_SECRECY: 'Asked to keep it secret',
  ASK_BYPASS: 'Asked to bypass the normal process',
  ASK_UNUSUAL_PAYMENT_METHOD: 'Unusual payment method',
  ASK_PAYEE_CHANGE: 'Asked to change the payee',
  STYLE_PRESSURE: 'Urgency or authority pressure',
  WATCHLIST_HIT: 'Matches the watchlist',
  MULTI_GROUP_STRONG: 'Independent checks agree',
  GREY_FLAG: 'A check could not complete',
  OOB_DENIED: 'The requester denied this request',
  OOB_APPROVED: 'The requester approved this exact request',
  SEAL_PRESENCE_CONFLICT: 'Seal conflict',
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
