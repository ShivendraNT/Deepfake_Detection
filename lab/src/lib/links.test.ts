import { describe, expect, it } from "vitest";
import type { EvidenceLink, LinkKind } from "../api";
import { dedupeLinks, groupLinks, LINK_META, linkMeta, linksFor, pairKey } from "./links";

const link = (source: string, target: string, kind: LinkKind, score: number, artifacts: string[] = []): EvidenceLink => ({
  source,
  target,
  kind,
  score,
  detail: `${source}->${target}`,
  artifacts,
});

describe("link de-duplication", () => {
  it("builds an order-independent pair key", () => {
    expect(pairKey("ev_b", "ev_a")).toBe(pairKey("ev_a", "ev_b"));
  });

  it("collapses A→B and B→A of the same kind, keeping the higher score", () => {
    const out = dedupeLinks([link("a", "b", "near_duplicate", 0.8), link("b", "a", "near_duplicate", 0.9)]);
    expect(out).toHaveLength(1);
    expect(out[0]?.score).toBe(0.9);
    expect(out[0]?.source).toBe("b");
  });

  it("prefers the copy with artifacts on a tie (the diff figure lives under its source)", () => {
    const out = dedupeLinks([link("a", "b", "shares_content", 1), link("b", "a", "shares_content", 1, ["diff_vs_a.jpg"])]);
    expect(out[0]?.artifacts).toEqual(["diff_vs_a.jpg"]);
  });

  it("keeps different kinds between the same pair", () => {
    const out = dedupeLinks([link("a", "b", "near_duplicate", 0.84), link("a", "b", "shares_content", 1)]);
    expect(out.map((l) => l.kind).sort()).toEqual(["near_duplicate", "shares_content"]);
  });

  it("drops self links and tolerates null input", () => {
    expect(dedupeLinks([link("a", "a", "same_face", 1)])).toEqual([]);
    expect(dedupeLinks(null)).toEqual([]);
  });

  it("groups links per pair, strongest first", () => {
    const groups = groupLinks([
      link("r1", "q1", "near_duplicate", 0.844),
      link("r1", "q1", "shares_content", 1),
      link("q1", "r1", "shares_content", 0.5),
      link("q2", "q1", "shares_content", 0.24),
    ]);
    expect(groups).toHaveLength(2);
    expect(groups[0]?.links.map((l) => l.kind)).toEqual(["shares_content", "near_duplicate"]);
    expect(groups[1]?.links).toHaveLength(1);
  });

  it("filters the links of one exhibit", () => {
    const all = [link("a", "b", "same_face", 0.4), link("c", "d", "same_face", 0.9), link("b", "a", "same_face", 0.6)];
    expect(linksFor("a", all)).toHaveLength(1);
    expect(linksFor("z", all)).toEqual([]);
  });
});

describe("link labels", () => {
  it("labels every link kind and degrades for unknown kinds", () => {
    expect(Object.keys(LINK_META)).toHaveLength(6);
    expect(linkMeta("same_face").label).toBe("Same face");
    expect(linkMeta("brand_new_kind").label).toBe("brand new kind");
  });
});
