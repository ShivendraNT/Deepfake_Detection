import { describe, expect, it } from "vitest";
import {
  distributionFromCounts,
  evidenceMeta,
  hypothesisMeta,
  isFlagged,
  isPending,
  parseRationale,
  strengthWord,
  techStatusMeta,
  verdictDistribution,
  verdictMeta,
} from "./verdict";

describe("verdict colours", () => {
  it("uses red for synthetic / manipulated, amber for suspicious, green for clean, slate for inconclusive", () => {
    expect(verdictMeta("SYNTHETIC").hex).toBe("#ff4d6d");
    expect(verdictMeta("MANIPULATED").hex).toBe("#ff7a45");
    expect(verdictMeta("SUSPICIOUS").hex).toBe("#fbbf24");
    expect(verdictMeta("NO_INDICATORS").hex).toBe("#34d399");
    expect(verdictMeta("INCONCLUSIVE").hex).toBe("#94a3b8");
  });

  it("labels verdicts in words", () => {
    expect(verdictMeta("NO_INDICATORS").label).toBe("No indications");
    expect(verdictMeta("SYNTHETIC").tone).toBe("synthetic");
  });

  it("never crashes on a missing or unknown verdict", () => {
    expect(verdictMeta(null).label).toBe("No verdict");
    expect(verdictMeta("WHATEVER" as never).tone).toBe("inconclusive");
  });

  it("shows processing status until an exhibit is done", () => {
    expect(evidenceMeta({ status: "queued", verdict: null }).label).toBe("Queued");
    expect(evidenceMeta({ status: "analyzing", verdict: null }).label).toBe("Analysing");
    expect(evidenceMeta({ status: "error", verdict: null }).label).toBe("Error");
    expect(evidenceMeta({ status: "done", verdict: "MANIPULATED" }).label).toBe("Manipulated");
  });

  it("flags the same verdicts as the /cases endpoint", () => {
    expect(isFlagged("SYNTHETIC")).toBe(true);
    expect(isFlagged("MANIPULATED")).toBe(true);
    expect(isFlagged("SUSPICIOUS")).toBe(true);
    expect(isFlagged("INCONCLUSIVE")).toBe(false);
    expect(isFlagged("NO_INDICATORS")).toBe(false);
    expect(isFlagged(null)).toBe(false);
    expect(isPending("queued")).toBe(true);
    expect(isPending("analyzing")).toBe(true);
    expect(isPending("done")).toBe(false);
  });
});

describe("strengths and hypotheses", () => {
  it("maps the ENFSI ordinal to words, clamping out-of-range values", () => {
    expect(strengthWord(0)).toBe("no support");
    expect(strengthWord(3)).toBe("strong support");
    expect(strengthWord(4)).toBe("very strong support");
    expect(strengthWord(9)).toBe("very strong support");
    expect(strengthWord(null)).toBe("no support");
  });

  it("colours hypotheses and falls back to neutral", () => {
    expect(hypothesisMeta("synthetic").hex).toBe("#ff4d6d");
    expect(hypothesisMeta("authentic").label).toBe("Authentic");
    expect(hypothesisMeta("bogus").label).toBe("Informational");
  });

  it("describes technique statuses and never treats an unknown status as ok", () => {
    expect(techStatusMeta("ok").label).toBe("Ran");
    expect(techStatusMeta("skipped").label).toBe("Not applicable");
    expect(techStatusMeta("unavailable").label).toBe("Model unavailable");
    expect(techStatusMeta("weird").label).toBe("Error");
  });

  it("parses rationale lines", () => {
    expect(parseRationale("[strong support] Cloned region: 60 matching keypoints move together")).toEqual({
      strength: 3,
      word: "strong support",
      text: "Cloned region: 60 matching keypoints move together",
    });
    expect(parseRationale("plain text")).toEqual({ strength: null, word: null, text: "plain text" });
  });
});

describe("verdict distribution", () => {
  it("counts verdicts in severity order and groups pending items", () => {
    const parts = verdictDistribution([
      { status: "done", verdict: "NO_INDICATORS" },
      { status: "done", verdict: "SYNTHETIC" },
      { status: "done", verdict: "NO_INDICATORS" },
      { status: "analyzing", verdict: null },
      { status: "queued", verdict: null },
      { status: "error", verdict: null },
    ]);
    expect(parts.map((p) => [p.key, p.count])).toEqual([
      ["SYNTHETIC", 1],
      ["NO_INDICATORS", 2],
      ["PENDING", 2],
      ["ERROR", 1],
    ]);
  });

  it("rebuilds the distribution from the case `counts` map", () => {
    const parts = distributionFromCounts({ NO_INDICATORS: 4, MANIPULATED: 1, SYNTHETIC: 1, INCONCLUSIVE: 2, queued: 1 });
    expect(parts.map((p) => [p.key, p.count])).toEqual([
      ["SYNTHETIC", 1],
      ["MANIPULATED", 1],
      ["INCONCLUSIVE", 2],
      ["NO_INDICATORS", 4],
      ["PENDING", 1],
    ]);
  });
});
