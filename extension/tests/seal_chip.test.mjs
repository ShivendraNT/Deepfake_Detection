// Satyapan Seal chip: reducer event "seal" + view model (node --test).
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyEvent, initialState } from "../lib/panel_state.js";
import { sealChipView } from "../lib/seal_chip.js";

const ev = (extra) => ({ type: "seal", call_id: "call_x", ...extra });

test("seal chip hidden until a seal event, then follows the states", () => {
  let s = initialState();
  assert.equal(s.seal.state, "idle");
  assert.equal(sealChipView(s.seal), null);
  s = applyEvent(s, ev({ state: "acquiring", employee_id: "emp_rajesh", display_name: "Rajesh Iyer" }));
  assert.equal(sealChipView(s.seal).cls, "seal-acquiring");
  const before = s;
  s = applyEvent(s, ev({ state: "sealed", epochs_sealed: 12, epochs_with_speech: 12 }));
  assert.equal(before.seal.state, "acquiring", "reducer must not mutate the previous state");
  const v = sealChipView(s.seal);
  assert.equal(v.text, "Rajesh Iyer: sealed ✓");
  assert.ok(v.sub.includes("12/12 epochs"));
});

test("not sealed never says fake and keeps the band untouched", () => {
  let s = applyEvent(initialState(), { type: "band", band: "VERIFY", reason_codes: [] });
  s = applyEvent(s, ev({ state: "not_sealed", display_name: "Rajesh Iyer", claimed: true }));
  const v = sealChipView(s.seal);
  assert.equal(v.text, "Claims to be Rajesh Iyer: NOT sealed");
  assert.ok(v.sub.startsWith("Not sealed does not mean fake"));
  assert.ok(!/\bfake\b/i.test(v.text));
  assert.equal(s.band, "VERIFY", "a seal event never changes the band (only band events do)");
  s = applyEvent(s, ev({ state: "sealed", display_name: "Rajesh Iyer" }));
  assert.equal(s.band, "VERIFY", "sealed never lowers the band");
});

test("seal state never stores a score and unknown states are ignored", () => {
  const s = applyEvent(initialState(), ev({ state: "sealed", score: 9.1, z: 7.2 }));
  assert.ok(!JSON.stringify(s).includes("score") && !JSON.stringify(s.seal).includes("7.2"));
  const t = applyEvent(initialState(), ev({ state: "bogus" }));
  assert.equal(t.seal.state, "idle");
});
