// T10 acceptance (node --test). Skips while lib/panel_state.js is a stub.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "..", "lib", "panel_state.js"), "utf8");
const isStub = src.includes("STUB(" + "T10)");
const events = readFileSync(join(here, "..", "replay", "sample_events.jsonl"), "utf8")
  .split("\n").filter(Boolean).map((l) => JSON.parse(l));

test("replay renders the demo story", { skip: isStub && "T10 not implemented yet" }, async () => {
  const { initialState, applyEvent } = await import("../lib/panel_state.js");
  let s = initialState();
  const s0 = s;
  for (const e of events) s = applyEvent(s, e);
  assert.equal(s0.band, "PASS", "reducer must not mutate the previous state");
  assert.equal(s.band, "HOLD");
  assert.equal(s.voice.label, "likely_synthetic");
  assert.deepEqual(s.asks.map((a) => a.askType), ["A1", "A4", "A5"]);
  assert.equal(s.asks[1].label, "Secrecy");
  assert.ok(s.suggestedLine.includes("in the system"));
  assert.ok(s.transcript.length === 3);
  assert.ok(!JSON.stringify(s).includes("score"), "never keep raw scores in panel state");
});

test("duplicate ask is not added twice", { skip: isStub && "T10 not implemented yet" }, async () => {
  const { initialState, applyEvent } = await import("../lib/panel_state.js");
  const ask = events.find((e) => e.type === "ask");
  const s = applyEvent(applyEvent(initialState(), ask), ask);
  assert.equal(s.asks.length, 1);
});
