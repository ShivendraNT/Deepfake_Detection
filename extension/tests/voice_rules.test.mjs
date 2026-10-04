// node --test extension/tests/   (no npm install needed)
import { test } from "node:test";
import assert from "node:assert/strict";
import { classifyWindows } from "../lib/voice_rules.js";

const TH = { tauHi: 0.9, tauLo: 0.6 };

test("two consecutive windows over tauHi -> likely_synthetic", () => {
  assert.equal(classifyWindows([0.3, 0.95, 0.91], TH, 15).label, "likely_synthetic");
});

test("non-consecutive highs are only inconclusive", () => {
  assert.equal(classifyWindows([0.95, 0.2, 0.95], TH, 15).label, "inconclusive");
});

test("all low -> no_signs", () => {
  assert.equal(classifyWindows([0.1, 0.2], TH, 10).label, "no_signs");
});

test("short speech is grey + inconclusive", () => {
  const v = classifyWindows([0.1], TH, 2);
  assert.equal(v.label, "inconclusive");
  assert.deepEqual(v.greyReasons, ["SPEECH_TOO_SHORT"]);
});
