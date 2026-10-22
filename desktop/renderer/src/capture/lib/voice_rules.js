// PRE-IMPLEMENTED. JavaScript mirror of src/satyapan/voice/rules.py — keep them identical.
// tests/harness/test_voice_rules_parity.py runs both on the same inputs.
//
// Rule: LIKELY_SYNTHETIC if >= 2 CONSECUTIVE 5-second windows score >= tauHi;
//       INCONCLUSIVE if any window >= tauLo (or total speech < 3 s);
//       NO_SIGNS otherwise.

export const MIN_SPEECH_SECONDS = 3.0;
export const MIN_CONSECUTIVE = 2;

export function classifyWindows(scores, thresholds, speechSeconds, minConsecutive = MIN_CONSECUTIVE) {
  const { tauHi, tauLo } = thresholds;
  if (!(0 <= tauLo && tauLo <= tauHi && tauHi <= 1)) throw new Error("need 0 <= tauLo <= tauHi <= 1");
  let run = 0;
  let best = 0;
  for (const s of scores) {
    run = s >= tauHi ? run + 1 : 0;
    best = Math.max(best, run);
  }
  const greyReasons = speechSeconds < MIN_SPEECH_SECONDS ? ["SPEECH_TOO_SHORT"] : [];
  let label;
  if (best >= minConsecutive) label = "likely_synthetic";
  else if (scores.some((s) => s >= tauLo) || greyReasons.length) label = "inconclusive";
  else label = "no_signs";
  return {
    label,
    maxConsecutiveOverHi: best,
    windows: scores.length,
    maxScore: scores.length ? Math.max(...scores) : 0,
    speechSeconds,
    greyReasons,
  };
}
