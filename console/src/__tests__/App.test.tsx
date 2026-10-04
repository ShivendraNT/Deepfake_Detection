// T06 acceptance (vitest): renders all 12 fixture cases from a mocked API.
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "../App";

const SUMMARIES = Array.from({ length: 12 }, (_, i) => ({
  id: `case_s${String(i + 1).padStart(2, "0")}`,
  title: `Scenario ${i + 1}`,
  kind: "PAYMENT",
  status: "OPEN",
  queue: "MAKER",
  band: (["PASS", "VERIFY", "HOLD"] as const)[i % 3],
  action_type: "K1",
  amount_inr: 100000 + i,
  beneficiary_name: `Payee ${i + 1}`,
  reason_codes: ["FLOOR_K1_KNOWN_IN_PATTERN"],
  created_at: "2026-10-05T10:00:00+05:30",
}));

describe("App", () => {
  it("lists all 12 fixture cases with a band badge", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(SUMMARIES), { status: 200 })));
    render(<App />);
    await waitFor(() => expect(screen.getAllByTestId("case-row")).toHaveLength(12));
    expect(screen.getAllByTestId("band-badge").length).toBeGreaterThanOrEqual(12);
  });
});
