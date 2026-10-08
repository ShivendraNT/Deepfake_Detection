// Pure view model for the Satyapan Seal chip (docs/SEAL.md). No DOM, so node can test it.
// Copy rules: a seal shows WHOSE enrolled device is speaking; "not sealed" never says "fake".
export function sealChipView(seal) {
  if (!seal || !seal.state || seal.state === "idle") return null;
  const who = seal.name || seal.employeeId || "executive";
  const epochs = `${seal.epochsSealed || 0}/${seal.epochsWithSpeech || 0} epochs`;
  switch (seal.state) {
    case "acquiring":
      return { cls: "seal-acquiring", icon: "…", text: `Checking voice seal: ${who}`,
               sub: "First result after about 5-10 s of speech" };
    case "sealed":
      return { cls: "seal-sealed", icon: "✓", text: `${who}: sealed ✓`,
               sub: `Passkey-started, this meeting · ${epochs}` };
    case "not_sealed":
      return { cls: "seal-not-sealed", icon: "!",
               text: seal.claimed ? `Claims to be ${who}: NOT sealed` : `${who}: not sealed`,
               sub: "Not sealed does not mean fake. Verify via OOB-Confirm before paying." };
    case "lost":
      return { cls: "seal-lost", icon: "!", text: `${who}: seal lost`,
               sub: `Recent speech carries no seal · ${epochs}. Verify before acting.` };
    default:
      return null;
  }
}
