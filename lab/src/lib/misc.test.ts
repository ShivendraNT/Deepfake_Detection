import { describe, expect, it } from "vitest";
import type { LabEvidence } from "../api";
import { demoCaseId, urls } from "../api";
import { circleLayout } from "./layout";
import { shortArtifactLabel, thumbUrl } from "./media";
import { groupAsks, highlightAsks } from "./transcript";

describe("transcript highlighting", () => {
  it("highlights each ask phrase inside a segment, case-insensitively", () => {
    expect(highlightAsks("Do not tell anyone about this call.", ["do not tell anyone"])).toEqual([
      { text: "Do not tell anyone", hit: true },
      { text: " about this call.", hit: false },
    ]);
  });

  it("merges overlapping matches", () => {
    const parts = highlightAsks("share the OTP now", ["share the OTP", "the OTP now"]);
    expect(parts).toEqual([{ text: "share the OTP now", hit: true }]);
  });

  it("highlights a whole segment that lies inside a longer ask", () => {
    expect(highlightAsks("your account.", ["verify your account."])[0]?.hit).toBe(false); // two words only
    expect(highlightAsks("transfer to the safe account", ["please transfer to the safe account now"])[0]?.hit).toBe(true);
  });

  it("leaves text without asks untouched", () => {
    expect(highlightAsks("Hello there", [])).toEqual([{ text: "Hello there", hit: false }]);
  });

  it("groups asks by type", () => {
    const g = groupAsks([
      { type: "A4", text: "Do not tell anyone", meaning: "demands secrecy / isolation" },
      { type: "A4", text: "Keep it secret", meaning: "demands secrecy / isolation" },
      { type: "A2", text: "share the OTP", meaning: "asks for OTP / PIN / password" },
    ]);
    expect(g).toEqual([
      { type: "A4", meaning: "demands secrecy / isolation", texts: ["Do not tell anyone", "Keep it secret"] },
      { type: "A2", meaning: "asks for OTP / PIN / password", texts: ["share the OTP"] },
    ]);
  });
});

describe("media helpers", () => {
  it("picks a thumbnail per media kind", () => {
    expect(thumbUrl({ id: "ev_1", kind: "image" })).toBe(urls.file("ev_1"));
    expect(thumbUrl({ id: "ev_2", kind: "video" })).toBe(urls.artifact("ev_2", "contact_sheet.jpg"));
    expect(thumbUrl({ id: "ev_3", kind: "audio" })).toBe(urls.artifact("ev_3", "spectrogram.png"));
    expect(thumbUrl({ id: "ev_4", kind: "other" })).toBeNull();
  });

  it("shortens overlay labels", () => {
    expect(shortArtifactLabel("ela.jpg", "Error Level Analysis (q=90)")).toBe("ELA");
    expect(shortArtifactLabel("noise_map.jpg", "Local noise level deviation")).toBe("Noise map");
    expect(shortArtifactLabel("x.png", "A very long artifact title here")).toBe("A very long…");
  });

  it("finds the case id in a demo response", () => {
    expect(demoCaseId({ id: "case_1" })).toBe("case_1");
    expect(demoCaseId({ case: { id: "case_2" } })).toBe("case_2");
    expect(demoCaseId({ case_id: "case_3" })).toBe("case_3");
    expect(demoCaseId({})).toBeNull();
  });
});

describe("graph layout", () => {
  const ev = (id: string, exhibit: string, role: "questioned" | "reference"): LabEvidence =>
    ({ id, exhibit, role }) as LabEvidence;

  it("places every exhibit, references on the left", () => {
    const pos = circleLayout([ev("q1", "Q1", "questioned"), ev("r1", "R1", "reference"), ev("q2", "Q2", "questioned")]);
    expect(Object.keys(pos).sort()).toEqual(["q1", "q2", "r1"]);
    expect(pos.r1!.x).toBeLessThan(pos.q1!.x);
    expect(pos.r1!.x).toBeLessThan(pos.q2!.x);
  });

  it("is deterministic and handles tiny inputs", () => {
    const list = [ev("a", "Q1", "questioned"), ev("b", "Q2", "questioned")];
    expect(circleLayout(list)).toEqual(circleLayout(list));
    expect(circleLayout([])).toEqual({});
    expect(circleLayout([ev("a", "Q1", "questioned")])).toEqual({ a: { x: 0, y: 0 } });
  });
});
