// T12: OOB-Confirm inbox — the claimed requester's second screen.
// "Did you just ask for this payment?" Yes / No. Only the logged-in requester sees it,
// and the server rejects anyone else (WrongResponderError), so a leaked link is useless.
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { DemoUser } from "../types";

interface OobInboxProps {
  user: DemoUser;
}

const TOKEN_RE = /\/oob\/([A-Za-z0-9_\-]+)/;

function tokenFrom(body: string): string | null {
  const m = TOKEN_RE.exec(body);
  return m ? m[1] : null;
}

export function OobInbox({ user }: OobInboxProps) {
  const [messages, setMessages] = useState<{ id: string; subject: string; body: string }[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isRequester = user.role === "requester";

  const load = useCallback(async () => {
    if (!isRequester) {
      setMessages([]);
      return;
    }
    try {
      setMessages(await api.oobInbox(user));
      setError(null);
    } catch (e: unknown) {
      setError(String(e));
    }
  }, [user, isRequester]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isRequester) return null;

  async function answer(id: string, token: string, approve: boolean) {
    setBusy(true);
    try {
      const r = await api.respondOob(user, token, approve);
      setAnswers((prev) => ({ ...prev, [id]: r.result }));
      setError(null);
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      data-testid="oob-inbox"
      className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
        Out-of-band confirm
      </h2>
      <p className="mt-1 text-xs text-slate-500">
        Only you can answer these — the link alone is not enough.
      </p>

      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}

      {messages.length === 0 && (
        <p className="mt-3 text-sm text-slate-500">No confirmation requests.</p>
      )}

      <ul className="mt-3 space-y-3">
        {messages.map((m) => {
          const token = tokenFrom(m.body);
          const shown = answers[m.id];
          return (
            <li
              key={m.id}
              className="rounded border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60"
            >
              <p className="text-xs font-semibold text-slate-500">{m.subject}</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800 dark:text-slate-200">
                {m.body}
              </p>

              {shown ? (
                <p className="mt-2 text-sm font-semibold">
                  Answered: {shown === "DENIED" ? "No — marked as suspected fraud" : shown}
                </p>
              ) : token ? (
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void answer(m.id, token, true)}
                    className="rounded border border-green-300 bg-green-100 px-3 py-1 text-sm font-semibold text-green-800 disabled:opacity-50"
                  >
                    Yes, I asked for this
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void answer(m.id, token, false)}
                    className="rounded border border-red-300 bg-red-100 px-3 py-1 text-sm font-semibold text-red-800 disabled:opacity-50"
                  >
                    No — I did not ask
                  </button>
                </div>
              ) : (
                <p className="mt-2 text-xs text-slate-500">No answer link in this message.</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default OobInbox;
