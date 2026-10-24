# Deck outline (5 slides): Satya, check it before you pay

Every number below has a row in `results/EVIDENCE_LEDGER.md` (n, interval, script).

## Slide 1: the person and the moment
- Anyone with UPI on a phone. **A claim** ("CBI, you are under digital arrest", "your KYC
  expires today", "Mummy, new number") **and then an ask**: a "safe account", an OTP, secrecy,
  a screen-sharing app, a courier fee.
- India lost ₹22,845.73 crore to cyber fraud in 2024 (Lok Sabha reply, 22 Jul 2025; ledger §8).
- Deepfakes make the claim convincing (a "police officer" on video, a cloned voice). Detectors
  alone fail on new fakes: the best video detector scores 69.7 % AUROC on 2026 generators
  (DF26, arXiv 2609.07369).
- **The ask is the part a scam cannot hide.** Satya checks it, and checks the media too.

## Slide 2: Satya, in one line
- Forward anything (text, screenshot, voice note, photo, video), or let Satya hear the call
  after a yes. It answers **PASS / VERIFY (call back first) / HOLD (stop)**, says **why** in
  English or Hindi, and gives the **next step**.
- On the device; nothing is uploaded or kept; Satya never blocks; a human files every report.
- One policy engine. Evidence (text model, voice-clone model, face check) can only raise the
  band, never lower it.

## Slide 3: live demo (`docs/finale/LIVE_DEMO.md` §3b)
- Attack: a juror calls the laptop: "CBI … digital arrest … don't tell anyone … RBI safe
  account … read me the OTP".
- Alert: "Stop: don't pay or share any code on this call", with the exact words quoted and
  why.
- Action: copy a safe reply and hang up; or "Money sent? Call 1930"; or "Prepare my report"
  (UTR-first 1930 script, bank message, portal fields).
- Jury variations: Hinglish, a screenshot, a voice note, a video, a genuine bank OTP SMS
  (→ PASS).

## Slide 4: measured, honestly (held-out test sets, thresholds frozen on validation)
- **Messages:** 96.6 % of 2,213 scam texts flagged; 2.7 % of 4,363 genuine texts flagged
  (n in ledger §10). Under an obfuscation attack: 96.2 % (40.1 % without our de-obfuscation).
- **Video face:** FF++ AUC 0.946, DFDC (never seen) 0.778. 0 of 563 real videos called
  synthetic; 74.7 % / 24.8 % of fakes flagged for a call-back (ledger §11).
- **Photo face:** AUC 0.923 / 0.747 (ledger §11).
- **Voice clone:** see `results/voice_benchmark.md` (ledger §12). The licensed model was
  chosen on validation by a rule fixed in advance.
- **Named misses:**
  - unseen face-swap methods (FaceShifter flagged 32 %);
  - small faces at 360p ("couldn't check");
  - Hinglish genuine texts flagged 6.2 % (n=64);
  - paraphrased asks (lexicon recall 0.33).

## Slide 5: deploy, scale, responsibility
- **Who runs it:**
  - a bank or UPI app as a "check before you pay" share target (text checks on the phone;
    media models on the bank's servers in India, deleted after scoring);
  - a cyber cell or the 1930 desk (`satya scan` offline);
  - anyone (desktop app, or `/check` on a phone on the same Wi-Fi).
- **Cost:** milliseconds of CPU per text; seconds to a minute or two per photo or video, well
  under ₹1 per check (estimate). Pilot: 4 weeks with one bank fraud team; target ≤ 2 % VERIFY
  on genuine traffic.
- **False-positive path:** one call back on a number you already have; Satya never blocks.
  Every alert says why; no scores are shown.
- **Next:** paraphrase-robust asks, webcam-calibrated face thresholds, more Indian languages.
