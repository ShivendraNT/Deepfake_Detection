// F16: OOB-Confirm — the approver's phone.
// The claimed requester sees one calm card: did you ask for this exact payment?
// Approve / Reject / "I did not request this". The last one is stronger than a plain reject:
// the server records reason=not_requested and Satya locks the case in HOLD on the maker's desk.
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { DemoUser } from "../types";

interface OobInboxProps {
  user: DemoUser;
}

interface Message {
  id: string;
  subject: string;
  body: string;
}

type Action = "approve" | "reject" | "not_requested";
type Outcome = "approved" | "rejected" | "not_requested";

const TOKEN_RE = /\/oob\/([A-Za-z0-9_\-]+)/;
const FONT = 'Inter, "Noto Sans Devanagari", system-ui, sans-serif';
const INK = "#2A2238";
const MUTED = "#6B6478";
const LINE = "#E7DFD3";
const CARD = "#FFFCF7";
const INNER = "#F6F1E9";
const GREEN = "#3CCB7F";
const CORAL = "#FF6B5E";
const TEAL = "#1FB5A3";

const DEFAULT_DETAILS = {
  amount: "₹48,50,000",
  payee: "Fictional Escrow Ltd ••••4821",
  maker: "Priya",
};

function tokenFrom(body: string): string | null {
  const match = TOKEN_RE.exec(body);
  return match ? match[1] : null;
}

function personName(employeeId: string): string {
  const known: Record<string, string> = {
    emp_priya: "Priya",
    emp_arjun: "Arjun",
    emp_rajesh: "Rajesh",
    emp_meera: "Meera",
  };
  return (
    known[employeeId] ??
    employeeId
      .replace(/^emp_/, "")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

function cleanPayee(value: string): string {
  return value.replace(/\s+today\b.*$/i, "").replace(/[.,;:!?]+$/, "").trim();
}

/** Read the demo mailer's plain-text body; fall back to the fake demo world. */
function extractDetails(body: string): typeof DEFAULT_DETAILS {
  const amount = /₹\s?([\d,]+)/.exec(body)?.[1];
  const payee =
    /\b(?:pay|paid)\b[^\n]*?\bto\s+([^\n.]+?)(?:\s+today\b|[.\n]|$)/i.exec(body)?.[1] ??
    /\bto\s+([A-Z][^\n.]+?)(?:\s+today\b|[.\n]|$)/i.exec(body)?.[1];
  const maker = /\b(?:ask|asked)\s+([A-Z][a-z]+)\s+to\s+pay\b/i.exec(body)?.[1];
  return {
    amount: amount ? `₹${amount}` : DEFAULT_DETAILS.amount,
    payee: payee ? cleanPayee(payee) : DEFAULT_DETAILS.payee,
    maker: maker ?? DEFAULT_DETAILS.maker,
  };
}

function demoHeaders(user: DemoUser): HeadersInit {
  return {
    "X-Demo-User": user.employeeId,
    "X-Demo-Role": user.role,
    "Content-Type": "application/json",
  };
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function ShieldMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3.5 19 6v5.2c0 4.4-2.9 7.7-7 9.3-4.1-1.6-7-4.9-7-9.3V6l7-2.5Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="m8.8 12.1 2.1 2.1 4.4-4.4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ActionIcon({ action }: { action: Action }) {
  if (action === "approve") {
    return (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="m5 12.5 4.2 4.2L19 7"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (action === "reject") {
    return (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="m7 7 10 10M17 7 7 17"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3.5 21 20H3L12 3.5Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M12 9v4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="12" cy="16.8" r="1" fill="currentColor" />
    </svg>
  );
}

function ResultIcon({ outcome }: { outcome: Outcome }) {
  if (outcome === "approved") {
    return (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="m5 12.5 4.2 4.2L19 7"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (outcome === "not_requested") {
    return (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 3.5 19 6v5.2c0 4.4-2.9 7.7-7 9.3-4.1-1.6-7-4.9-7-9.3V6l7-2.5Z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path d="M12 8.5v4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="12" cy="15.8" r="1" fill="currentColor" />
      </svg>
    );
  }
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m7 7 10 10M17 7 7 17" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

function outcomeCopy(outcome: Outcome): string {
  if (outcome === "approved") return "Payment approved. Priya's desk has been notified.";
  if (outcome === "rejected") return "Payment rejected. Transfer cancelled.";
  return "Reported as unrequested. Satya has locked this case in HOLD on Priya's desk.";
}

function outcomeColor(outcome: Outcome): string {
  if (outcome === "approved") return GREEN;
  if (outcome === "not_requested") return CORAL;
  return MUTED;
}

export function OobInbox({ user }: OobInboxProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [answers, setAnswers] = useState<Record<string, Outcome>>({});
  const [busy, setBusy] = useState<{ id: string; action: Action } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const isRequester = user.role === "requester";

  const load = useCallback(async () => {
    if (!isRequester) {
      setMessages([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setMessages(await api.oobInbox(user));
      setLoadError(null);
    } catch (error: unknown) {
      setLoadError(errorText(error));
    } finally {
      setLoading(false);
    }
  }, [user, isRequester]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isRequester) return null;

  async function answer(id: string, token: string, action: Action): Promise<void> {
    setBusy({ id, action });
    setErrors((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });

    try {
      if (action === "approve") {
        const response = await api.respondOob(user, token, true);
        const outcome: Outcome = response.result === "APPROVED" ? "approved" : "rejected";
        setAnswers((current) => ({ ...current, [id]: outcome }));
        return;
      }

      const payload =
        action === "not_requested"
          ? { token, approve: false, reason: "not_requested" }
          : { token, approve: false };
      const response = await fetch("/api/oob/respond", {
        method: "POST",
        headers: demoHeaders(user),
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${await response.text()}`);
      }
      const data = (await response.json()) as { result?: string; reason?: string };
      const outcome: Outcome =
        action === "not_requested" || data.reason === "not_requested"
          ? "not_requested"
          : "rejected";
      setAnswers((current) => ({ ...current, [id]: outcome }));
    } catch (error: unknown) {
      setErrors((current) => ({ ...current, [id]: errorText(error) }));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section
      data-testid="oob-inbox"
      className="mx-auto w-full max-w-[375px]"
      style={{ fontFamily: FONT, color: INK }}
    >
      {loadError ? (
        <div
          className="rounded-[20px] border p-5 text-[13px]"
          style={{ background: CARD, borderColor: LINE, color: MUTED }}
          role="alert"
        >
          Could not load confirmation requests: {loadError}
        </div>
      ) : null}

      {loading ? (
        <div
          className="rounded-[20px] border p-5 text-center text-[13px]"
          style={{ background: CARD, borderColor: LINE, color: MUTED }}
          role="status"
        >
          Loading confirmation requests…
        </div>
      ) : messages.length === 0 && !loadError ? (
        <div
          className="rounded-[20px] border p-5 text-center text-[13px]"
          style={{ background: CARD, borderColor: LINE, color: MUTED }}
        >
          No confirmation requests.
        </div>
      ) : null}

      <div className="space-y-4">
        {messages.map((message) => {
          const outcome = answers[message.id];
          const token = tokenFrom(message.body);
          const details = extractDetails(message.body);
          const requester = personName(user.employeeId);

          if (outcome) {
            return (
              <article
                key={message.id}
                className="rounded-[20px] border p-6 text-center shadow-[0_12px_32px_rgba(20,16,40,0.08)]"
                style={{ background: CARD, borderColor: LINE }}
                aria-live="polite"
              >
                <div
                  className="mx-auto grid h-16 w-16 place-items-center rounded-full"
                  style={{
                    background: `${outcomeColor(outcome)}1A`,
                    color: outcomeColor(outcome),
                  }}
                >
                  <ResultIcon outcome={outcome} />
                </div>
                <p className="mt-5 text-[20px] font-semibold leading-snug tracking-[-0.01em]">
                  {outcomeCopy(outcome)}
                </p>
                <p className="mt-2 text-[13px]" style={{ color: MUTED }}>
                  You can close this tab.
                </p>
              </article>
            );
          }

          const isBusy = busy?.id === message.id;
          const error = errors[message.id];

          return (
            <article
              key={message.id}
              className="rounded-[20px] border p-5 shadow-[0_12px_32px_rgba(20,16,40,0.08)]"
              style={{ background: CARD, borderColor: LINE }}
            >
              <header className="flex items-center gap-2.5">
                <span
                  className="grid h-9 w-9 shrink-0 place-items-center rounded-full"
                  style={{ background: `${TEAL}1A`, color: TEAL }}
                >
                  <ShieldMark />
                </span>
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold">Satya</p>
                  <p className="text-[12px]" style={{ color: MUTED }}>
                    Out-of-band confirmation
                  </p>
                </div>
                <span
                  className="ml-auto shrink-0 rounded-full border px-2 py-0.5 text-[12px]"
                  style={{ borderColor: LINE, color: MUTED }}
                >
                  For {requester}
                </span>
              </header>

              <h2 className="mt-5 text-[20px] font-semibold leading-snug tracking-[-0.01em]">
                Did you ask {details.maker} to pay {details.amount} to {details.payee} today?
              </h2>

              <div
                className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-[12px] px-3 py-2 text-[12px]"
                style={{ background: INNER, color: MUTED }}
              >
                <span className="font-semibold" style={{ color: INK }}>
                  Just now
                </span>
                <span aria-hidden="true">·</span>
                <span>Asked via Satya on {details.maker}&apos;s laptop</span>
              </div>

              {token ? (
                <div className="mt-5 space-y-3">
                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => void answer(message.id, token, "approve")}
                    className="flex h-14 w-full items-center justify-center gap-2 rounded-[12px] px-4 text-[15px] font-semibold transition disabled:opacity-60"
                    style={{ background: GREEN, color: "#12301F" }}
                  >
                    <ActionIcon action="approve" />
                    {busy?.id === message.id && busy.action === "approve"
                      ? "Sending…"
                      : "Approve this exact payment"}
                  </button>

                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => void answer(message.id, token, "reject")}
                    className="flex h-14 w-full items-center justify-center gap-2 rounded-[12px] border px-4 text-[15px] font-semibold transition disabled:opacity-60"
                    style={{ background: CARD, borderColor: LINE, color: INK }}
                  >
                    <ActionIcon action="reject" />
                    {busy?.id === message.id && busy.action === "reject" ? "Sending…" : "Reject"}
                  </button>

                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => void answer(message.id, token, "not_requested")}
                    className="flex h-14 w-full items-center justify-center gap-2 rounded-[12px] px-4 text-[15px] font-semibold text-white transition disabled:opacity-60"
                    style={{ background: CORAL }}
                  >
                    <ActionIcon action="not_requested" />
                    {busy?.id === message.id && busy.action === "not_requested"
                      ? "Sending…"
                      : "I did not request this"}
                  </button>
                </div>
              ) : (
                <p className="mt-4 text-[12px]" style={{ color: MUTED }}>
                  No answer link in this message.
                </p>
              )}

              {error ? (
                <p className="mt-3 text-[12px]" style={{ color: "#C24136" }} role="alert">
                  {error}
                </p>
              ) : null}

              <p className="mt-4 text-[12px] leading-relaxed" style={{ color: MUTED }}>
                Only you can answer this. The link alone is not enough.
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default OobInbox;
