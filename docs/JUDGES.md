# Satya for judges: one page per criterion

**Satya (सत्य) is a scam and deepfake check for one person, on their own laptop.** Forward it
what a scammer sent you (a message, a screenshot, a voice note, a photo or a video), or let it
listen to a call after you say yes. It answers in one line: **PASS**, **VERIFY** (call back on a
number you already have before you act) or **HOLD** (stop: don't pay, don't share a code). It
says why in plain English or Hindi and gives the next step. If money has already left, it drafts
your 1930 call with the UTR first. Everything runs on the device; nothing is uploaded or kept.

The same engine also protects a small business's payments (vendor master, approver on their own
phone). That was our Round 1 scope and it still works, but this guide follows the consumer.

---

## 0. Run it (about 5 minutes once the models are on the laptop)

```bash
make sync                      # Python deps (uv); no uv/make: README "pip fallback" / scripts/satya.py
make video                     # face check + screenshot OCR; needs blend_b0.onnx (built locally),
                               # otherwise it abstains ("could not check"), never guesses
make asr                       # on-device speech (voice notes, live calls)
make voice                     # voice-clone model: built from its pinned licensed source (torch once)
make live                      # the engine on :8000 (0.0.0.0, so a phone on the same Wi-Fi works)
#   laptop:  http://127.0.0.1:8000/check        phone: http://<laptop-ip>:8000/check
make scan F=path/to/your/kit   # every file -> band, why, what could not be checked; CSV + MD report
cd desktop && npm install && npm run dev     # Satya on a live call (asleep until you consent)
```

Windows without `make`: `uv run python scripts/satya.py live | scan <folder> | video | voice`. A laptop
without a model file still runs; the answer then lists what it could **not** check (for example
"voice clone (voice model not installed)") instead of pretending.

---

# Stage 1

## 1. Working prototype (25): input → detection → alert → action, on what you pick

| You give Satya | What runs on the laptop | What you get | Time on a 4-core CPU |
|---|---|---|---|
| Pasted text, `.txt`, `.eml`, PDF | scam-text model (with de-obfuscation), asks (OTP, "safe account", secrecy, remote access, gift cards, new payee; EN + Hinglish + Devanagari), impossible-claim rules (digital arrest, RBI safe account, KYC expiry, courier fee, power cut), policy band | band, why (one line per finding), what to do, share-a-warning link | 12 ms per text (`results/consumer_text_eval.md`) |
| Screenshot | on-device OCR, then the text checks; face check if a person is in it | the same, plus "what Satya read" | 4–15 s |
| Photo of a person | face swap / synthetic face check (one GenD crop) | the same | 7–15 s |
| Video file | face check per 6 s window, lip-sync, speech → asks | the same | about 1.5× the video's length |
| Voice note | on-device Whisper → asks + text model; voice-clone model | the same, plus "what Satya heard" | depends on length |
| A live call (desktop app, after a yes for this call) | system audio only (never the microphone) → captions ~1 s behind → asks → band; face check on the shared screen if allowed | alert card quoting the exact words, three actions: copy a safe reply and hang up, call 1930, prepare my report | — |

Every answer ends with an action the person takes: call back on a number they already have,
call 1930, or open the **"Money already sent?"** section, which turns the UTR, amount and time
into a 1930 call script (UTR on line 1), a message for the bank and the cybercrime.gov.in fields.

## 2. Spot-check results and measured accuracy (30)

**On your kit:** `make scan F=kit/`. One line per file: band, channel, seconds, the reasons, and
what this laptop could not check. Files named `fake…`/`scam…` or `real…`/`genuine…` are graded
automatically, with a per-channel table of fakes flagged and genuine files passed.

**On a kit we built the same way from the open test sets:** `python -m research.run_all kit`
writes 184 files and runs the whole product on them: 80 texts, 40 photos, 40 voice clips and 24
videos, seeded, with a sha256 manifest (`results/kit_manifest.json`). The result is
`results/kit_scan.md`; on a 4-core CPU the whole kit takes about 7.5 minutes.

| Channel | Fakes / scams flagged | Genuine passed |
|---|---|---|
| Texts | 38 / 40 | 40 / 40 |
| Voice notes (≥ 3 s of speech) | 15 / 20 | 18 / 20 |
| Videos | 7 / 16 | 8 / 8 |
| Photos | 8 / 20 | 20 / 20 |
| **All** | **68 / 96** | **86 / 88** |

Satya is built to keep false alarms rare, and accepts misses to do so. Of the 28 misses:
- 21 are faces (12 photos, 9 videos, 2 of those videos with no usable face), mostly unseen
  or expression-only methods (FaceShifter, NeuralTextures), which the benchmarks name;
- 5 are cloned voices scored under τ_lo;
- 2 are scam texts with no ask and no scam wording.

The 2 genuine files flagged are voice notes:
- one voice the model found unusual;
- one speech whose words read like a scam to the text model, which a voice note's transcript
  now goes through, as a message's text does.

Both get VERIFY ("call back first"), never HOLD.

When a model is missing on a laptop, the answer says "could not check …"; it never turns that
into an alarm.

**On open data** (held-out test sets, thresholds frozen on validation first, scored once,
95 % intervals; full index and reproduction: [`BENCHMARKS.md`](BENCHMARKS.md)):

| Channel | Catches | False alarms on genuine items | Named failure case |
|---|---|---|---|
| Messages / e-mail / transcripts (whole consumer path) | 96.6 % of 2,213 scam texts flagged | 2.7 % of 4,363 genuine texts flagged, 0.9 % HOLD | a never-seen source: AUC 0.69 (phishing e-mail, leave-one-dataset-out); phishing e-mail also has the most false alarms (5.4 %) |
| Same, under an obfuscation attack (homoglyphs, leet, zero-width, spacing) | 96.2 % (40.1 % without our de-obfuscation layer) | — | LLM paraphrases are not in this test |
| Face in a video (FF++ c23 test; DFDC never seen) | 74.7 % / 24.8 % of fakes flagged for a call-back | **0 of 563** real videos called synthetic; 1.2 % flagged for a call-back | unseen method (FaceShifter): 32 %; small faces at 360p: "couldn't check" |
| Face in a photo | AUC 0.923 (FF++) / 0.747 (DFDC) | 0.4 % / 0.0 % of real crops over τ_hi | expression-only edits (NeuralTextures) |
| Voice clone (In-the-Wild: real-world deepfakes, speakers never seen) | AUC 0.921 clean / 0.909 Opus; with ≥ 3 s of speech 64–67 % of fakes flagged for a call-back | 0.6 % of genuine voices (≥ 3 s speech); 0.0–0.1 % over the strict threshold | under 3 s of speech: "too short to judge"; our own re-trained model lost the pre-registered comparison (0.79 vs 0.95 val AUC), so the licensed off-the-shelf one ships |

Generic "deepfake" image classifiers from Hugging Face scored 0.52–0.65 AUC on the same face
crops. That is why every model went through one protocol before it could ship
(`results/video_external.md`).

## 3. Own engineering contribution (15)

**Built by us:**
1. The policy engine: a trusted floor, raise-only evidence, ML and style signals capped at
   VERIFY, property-tested invariants.
2. The ask extractor (EN, Hinglish, Devanagari) and its context filter.
3. The scam-text model, its de-obfuscation layer and its 7-dataset benchmark.
4. The face pipeline:
   - a two-stage tracker for small call faces (the stock detector found no face in 361 of 674
     DFDC videos);
   - 6 s windows with abstention;
   - our own blend CNN, trained on real faces only;
   - the call-codec simulation;
   - a pre-registered protocol that compared six models.
5. The voice protocol:
   - a published recipe re-trained on licensed data, compared with 4 Hugging Face models by a
     rule fixed in advance (ours lost);
   - the winner exported exactly into the product's two-file format (its classifier folds
     into one linear head, checked to 2e-5).
6. The consumer path: the quick check, the citizen page and the money-sent drafts.
7. The desktop companion with live captions.
8. The kit runner, `satya scan`.

**Used, with licences recorded and pinned:**
- GenD (MIT): won our pre-registered comparison by +0.18 validation AUC; ours is the fallback.
- `Gustking/wav2vec2-large-xlsr-deepfake-audio-classification` (Apache-2.0): won the voice
  comparison by +0.157 validation AUC under Opus.
- XLS-R (Apache-2.0), Whisper (MIT), RapidOCR / PaddleOCR (Apache-2.0), YuNet (MIT), MediaPipe
  (Apache-2.0).
- Open datasets.

## 4. Alert and response flow, as built (15): the safeguards are code, and tests hold them

| Safeguard | How it runs | Enforced by |
|---|---|---|
| Processing on the device | the engine listens on 127.0.0.1; the desktop app talks only to it; network code only in `adapters/` | `tests/invariants/test_network_boundary.py`, `test_no_network.py` |
| No raw data kept | a check runs in memory (`memory://not-stored`); call transcripts never cross the event bus; audio buffers are released on stop | `tests/finale/test_citizen_files.py`, `test_companion_finale.py` |
| Human review | Satya never blocks; reports are drafts (`MANUAL_ONLY`); no submit route exists | `tests/invariants/test_no_auto_reporting.py` |
| Consent first | asleep until a visible consent card; a yes per call; never the microphone; any capture error → asleep | desktop consent flow, `tests/tasks/test_t25_companion.py` |
| No scores for the person | band and reasons only, never a probability | `tests/invariants/test_oracle_coarsening.py` |
| Evidence can only raise | no signal lowers a band; ML and style signals are capped at VERIFY | `test_monotonicity.py`, `test_llm_cap.py`, `test_injection_cannot_lower.py` |

## 5. Delivery against the Round 1 plan (15)

| Round 1 plan (deck pp. 9–10) | Now | Note |
|---|---|---|
| Trusted floor + raise-only policy engine | built, unchanged | property tests green |
| Live call: asks on screen | built | any call app via system audio, on-device Whisper (no Chrome-only limit) |
| OOB-Confirm on the real approver's phone | built | business mode |
| UTR-first report pack (1930, NCRP, bank) | built | plus the citizen version |
| E-mail and invoice checks | built | T03, T04, T08 |
| Voice detector through codecs | **rebuilt** on licensed data | Round 1 numbers were simulated and withdrawn (`results/INVALIDATED.md`) |
| Satyapan Seal live in Meet | prototype only, not in the finale demo | not consumer-facing; parked |
| AWS ap-south-1 deployment | **cut** | on-device became the privacy story; nothing needs a server |
| Not in the plan, added | video face check, photo check, screenshot OCR, consumer Scam Check page, money-sent drafts, kit runner, open-data benchmarks for every channel, phone app (`/pocket`: check, live, report; no mic) and live mirror (`/mobile`) | judges' Round 1 feedback: consumer focus, measured accuracy |

---

# Stage 2

## 6. Problem and user understanding (20): UPI and banking fraud in India

The person is anyone with UPI on their phone, and the attack is the same each time: **a claim
of authority or urgency, then an ask**. Examples:
- "This is CBI, you are under digital arrest; move the money to an RBI safe account."
- "Your KYC expires today, share the OTP."
- "Your parcel is held, pay the customs fee by UPI."
- "Mummy, new number, send ₹20,000, don't tell papa."

Indians lost ₹22,845.73 crore to cyber fraud in 2024 (Lok Sabha reply, 22 Jul 2025; ledger
§8). Deepfakes make the claim more convincing (a "police officer" on video, a cloned voice),
but **the ask is the part a scam cannot hide**, so Satya checks both:
- the ask, which is deterministic and explainable;
- the media (voice, face), as evidence that can only raise the band.

The answer is aimed at the moment of decision, before the UPI PIN. After money leaves, recovery
depends on reporting the UTR within hours, which is why the report step starts with the UTR.

## 7. Deployability and scale (15)

| Who runs it | How | Cost per check (estimate, pilot to confirm) |
|---|---|---|
| A bank or UPI app | a "Check before you pay" share target. Text, asks, OCR and the rules are small enough for a phone. Photo, video and voice models (GenD 1.2 GB, voice model 1.3 GB) run on the bank's own servers in India, only on an explicit share, deleted after scoring. | text ≈ 12 ms of CPU; a photo or a 30 s video takes seconds to a minute or two of a 4-core CPU (measured wall times above), i.e. well under ₹1 per check at on-demand cloud prices |
| A cyber cell or the 1930 desk | `satya scan` on a complaint's files, offline; the money-sent draft lists the facts the portal and the 1930 call ask for, UTR first | a laptop |
| Anyone | the desktop app or `http://<laptop>:8000/check` on a phone on the same Wi-Fi | free; nothing leaves the device |

**What a 4-week pilot needs:**
- one bank's fraud team (or one cyber cell) and consented samples of real scam and genuine
  messages in Hindi + English;
- a threshold re-fit on their genuine traffic: the targets are VERIFY ≤ 2 % of genuine
  messages, catch rate reported per channel, and time-to-clear for a genuine user;
- DPDP-Act review (processing is on the device or in the bank's own systems; no third party).

## 8. Communication (10)

This page, [`README.md`](../README.md), and the live script in
[`finale/LIVE_DEMO.md`](finale/LIVE_DEMO.md). Every number on a slide has a row in
[`results/EVIDENCE_LEDGER.md`](../results/EVIDENCE_LEDGER.md).

## 9. Live user journey (25): attack → alert → action → review/report, varied by the jury

**Base run, "digital arrest" on a video call.** Start the engine with `make live-personal`
(Windows: `uv run python scripts/satya.py live-personal`) and the desktop app (`npm run dev`).

1. **Attack.** A juror calls the laptop (WhatsApp, Meet, any app) and says, in English or
   Hinglish: *"This is CBI. Your Aadhaar is linked to money laundering. You are under digital
   arrest. Don't tell anyone. Transfer ₹50,000 to the RBI safe account and read me the OTP."*
2. **Alert**, a few seconds after the sentence (captions about 1 s behind speech). The alert
   reads *"Stop: don't pay or share any code on this call."* It quotes the exact words (new / "safe" account, secrecy, OTP) and says
   why: *real police, banks and officials never ask for money, a code or secrecy on a call.*
3. **Action.**
   - *Copy a safe reply, then hang up*;
   - or **Money sent? Call 1930** (opens the dialler);
   - or **Prepare my report**: UTR → 1930 script, bank message, portal fields.
4. **Review / report.** The person reads the drafts and submits them themselves. Nothing is
   sent automatically.

**Jury variations:**
- *Different words:* Hindi, "install AnyDesk", "buy gift cards", "pay the courier fee".
- *Different channel:* forward the same script as a screenshot, a voice note or a video to
  `/check`.
- *A genuine message:* a bank OTP SMS ("do not share this OTP") or a lunch plan → PASS.
- *An awareness forward:* "Police never arrest anyone over a video call" → PASS.
- *Swap the face or voice* with any deepfake file → the face or voice finding adds to the band.

## 10. Adversarial robustness (20): how an attacker would evade Satya, what it misses, what we'd change

| Attacker move | Effect today (measured where we could) | What we would change |
|---|---|---|
| Obfuscate the text (homoglyphs, leet, zero-width, spacing) | 96.2 % still caught (40.1 % without the de-obfuscation layer) | keep the layer in front of every text model |
| Paraphrase the ask (LLM rewrites) | the ask lexicon catches about 1 in 3 paraphrased asks (recall 0.33); the text model covers part of the rest | train on paraphrased scams; T20 is pre-registered |
| A scam from a source we never trained on | AUC 0.69–0.995 by dataset (leave-one-dataset-out) | add Indian bank and telecom samples in a pilot |
| A new face-swap method | FaceShifter (unseen) flagged 32 % vs 85 % for the 4 seen methods | add newer generators when a licensed test set exists; liveness prompt on the alert (turn your head, hand over the face) |
| A fully AI-generated portrait (GAN / diffusion), no swap | **not measured**: our face model learned swaps (FF++); the one generated-image model we tried (CommunityForensics) failed on swaps (AUC 0.65), and no licensed generated-face set was in our test | add a generated-image detector through the same protocol; until then the asks and the call-back carry it |
| Forward the fake photo through WhatsApp (JPEG re-encode) | photo check AUC 0.913 → 0.872 (paired −0.042 [−0.078, −0.008]); fakes flagged 49 % → 35 %; real photos flagged 0 % both ways (n = 200, `results/photo_whatsapp.md`) | train / calibrate on re-encoded copies; ask for the original file |
| Small face / low bitrate | at 360p, 82 % of DFDC faces are too small: "couldn't check — pin the caller" | ask for a larger view; never guess |
| Real footage of the person + a cloned voice | the face check is blind by design; lip-sync is weak (0.62–0.67 AUC) | the voice check and the asks carry this case |
| Send the cloned voice through WhatsApp / VoIP compression | Opus 16 kbps barely moves the voice check (In-the-Wild AUC 0.921 → 0.909) | keep testing new codecs (AMR-NB needs sox) |
| **Add background noise to the cloned voice** (10 dB SNR) | **works against us:** fakes flagged 63.9 % → 1.9 %, AUC 0.952 → 0.843; genuine flagged stays ≤ 0.6 %. Speed +10 % and pitch +2 semitones do not help an attacker (AUC −0.004 / −0.007). n = 155 fake + 160 genuine, `results/voice_evasion.md` | a denoiser in front does **not** fix it (val-only probe: −0.010 AUC on noisy, −0.023 on clean, `results/voice_denoise_probe.md`), so next is noise-augmented fine-tuning, chosen on val and tested once. Until then the asks, the text check and the call-back carry noisy calls, and "no signs" is never a pass |
| A very short voice note | under 3 s of speech is "too short to judge" (VERIFY: fail closed), never a pass | ask for a longer note or a call back |
| A newer voice-cloning system | In-the-Wild (real-world fakes of public figures) is our proxy: AUC 0.92–0.95; one model is still one model | re-run the protocol on new public sets; calibrate on consented calls (T18) |
| Probe Satya to tune a fake | only coarse answers (band + reasons), no scores, local only | keep scores hidden; rate-limit any hosted version |
| Text that "talks to" an LLM | the LLM never sets the band; untrusted text never enters the system prompt | — |
| A scam with no ask (a long con, investment "groups") | missed until money is asked for | a payment-time check in the UPI app, where the ask always appears |

## 11. Responsible AI (10)

**The false-positive path.** VERIFY means one call back on a number the person already has.
Satya never blocks a payment, so a genuine user is past it as soon as that call confirms; a
"think this is a mistake?" box under every answer says exactly that. Measured false alarms on
genuine items:
- texts 2.7 % (0.9 % HOLD);
- genuine voices 0.6 % with ≥ 3 s of speech (1.6–1.8 % of all clips);
- real videos 1.2 % flagged for a call-back, 0 called synthetic;
- real photo crops 0.4 % over the strict threshold.

**Every alert says why:** one sentence per finding, the exact words quoted on a call, and a
named rule. Never a bare score.

**Privacy, as it runs:**
- on the device; nothing stored;
- consent per call; never the microphone;
- transcripts never leave the call session.

**Errors by language** (whole consumer path, held-out texts, `results/consumer_text_eval.md`):

| Language | Genuine texts flagged |
|---|---|
| English | 3.2 % (n = 3,375) |
| English/Hindi SMS | 0.6 % (n = 711) |
| Hindi | 0 % (n = 35) |
| Hinglish | **6.2 %** (n = 64): the worst; the text model learned Hinglish mostly from scam calls |
| Other Indian languages | 0.6 % (n = 178) |

Scams are flagged at 96–100 % in each language.

**Known gaps:**
- Explanations are in English and Hindi only; Devanagari asks are the weakest (recall 0.15).
- Face thresholds come from FF++ broadcast video, not webcams (`calibrated: false`).
- No per-demographic error audit yet.
