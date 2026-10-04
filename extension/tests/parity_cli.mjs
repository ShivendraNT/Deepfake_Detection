// Reads JSON [{scores, tauHi, tauLo, speech}] from argv[2], prints labels as JSON.
import { classifyWindows } from "../lib/voice_rules.js";
const cases = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map((c) => classifyWindows(c.scores, { tauHi: c.tauHi, tauLo: c.tauLo }, c.speech).label)));
