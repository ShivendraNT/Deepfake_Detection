// PRE-IMPLEMENTED typed API client. All requests carry the DEMO identity headers.
import type { Case, CaseStatus, CaseSummary, DemoUser } from "./types";

const BASE = "/api";

function headers(user: DemoUser): HeadersInit {
  return { "X-Demo-User": user.employeeId, "X-Demo-Role": user.role, "Content-Type": "application/json" };
}

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return (await r.json()) as T;
}

export const api = {
  listCases: (user: DemoUser) => fetch(`${BASE}/cases`, { headers: headers(user) }).then(json<CaseSummary[]>),
  getCase: (user: DemoUser, id: string) =>
    fetch(`${BASE}/cases/${id}`, { headers: headers(user) }).then(json<Case>),
  explanation: (user: DemoUser, id: string, lang: "en" | "hi") =>
    fetch(`${BASE}/cases/${id}/explanation?lang=${lang}`, { headers: headers(user) }).then(
      json<{ text: string; source: string }>,
    ),
  startOob: (user: DemoUser, id: string, requesterId: string) =>
    fetch(`${BASE}/cases/${id}/oob`, {
      method: "POST",
      headers: headers(user),
      body: JSON.stringify({ requester_employee_id: requesterId }),
    }).then(json<{ oob_id: string; expires_at: string }>),
  oobInbox: (user: DemoUser) =>
    fetch(`${BASE}/oob/inbox`, { headers: headers(user) }).then(json<{ id: string; subject: string; body: string }[]>),
  respondOob: (user: DemoUser, token: string, approve: boolean) =>
    fetch(`${BASE}/oob/respond`, { method: "POST", headers: headers(user), body: JSON.stringify({ token, approve }) }).then(
      json<{ result: string }>,
    ),
  // T13: callbacks / clear / status / security ack
  addCallback: (
    user: DemoUser,
    id: string,
    body: {
      number_dialed: string;
      outcome: "CONFIRMED" | "DENIED" | "NO_ANSWER";
      confirmed_by_name?: string | null;
      bank_shown_payee_name?: string | null;
      notes?: string;
    },
  ) =>
    fetch(`${BASE}/cases/${id}/callbacks`, {
      method: "POST",
      headers: headers(user),
      body: JSON.stringify(body),
    }).then(json<Case>),
  clearCase: (user: DemoUser, id: string) =>
    fetch(`${BASE}/cases/${id}/clear`, { method: "POST", headers: headers(user) }).then(json<Case>),
  setCaseStatus: (user: DemoUser, id: string, status: CaseStatus) =>
    fetch(`${BASE}/cases/${id}/status`, {
      method: "POST",
      headers: headers(user),
      body: JSON.stringify({ status }),
    }).then(json<Case>),
  securityAck: (user: DemoUser, id: string) =>
    fetch(`${BASE}/cases/${id}/security-ack`, { method: "POST", headers: headers(user) }).then(
      json<Case>,
    ),
};

export const DEMO_USERS: { label: string; user: DemoUser }[] = [
  { label: "Priya (maker)", user: { employeeId: "emp_priya", role: "maker" } },
  { label: "Arjun (checker)", user: { employeeId: "emp_arjun", role: "checker" } },
  { label: "Rajesh (CFO, requester)", user: { employeeId: "emp_rajesh", role: "requester" } },
  { label: "Meera (security)", user: { employeeId: "emp_meera", role: "security" } },
];
