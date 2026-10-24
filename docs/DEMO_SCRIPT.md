# Demo script (~2 min 45 s)

> Round-1 demo. **For the finale use `docs/finale/PLAN.md` §7.**

Two pre-tested moments: (1) the detector catches a consented clone through real Meet capture;
(2) the floor catches a vendor fraud that every detector passes. Plus the golden-hour pack.

## Setup

| Screen | Who | What runs |
|---|---|---|
| Laptop A | Priya (maker) | console (`make run` + `npm run dev`) + extension on the Meet tab |
| Laptop B | "attacker" | joins Meet, plays **pre-generated, consented** clone clips of a teammate (F5-TTS / XTTS-v2 on Colab). Consent form on file (`docs/consent/`) |
| Screen C | Rajesh (real CFO) | console in a second browser profile as `emp_rajesh` / requester + phone showing the SES email |

All clips are pre-tested through *actual* Meet capture (T22: 10/10 logged dry runs).
Before going on stage: `make check` green; `/health` OK; `config/voice_thresholds.json` calibrated.

## Timeline

| Time | What happens | What judges see |
|---|---|---|
| 0:00-0:20 | **Hook.** "In 2024 a finance employee at Arup paid HK$200M after a video call with a deepfake CFO. On 2026's newest fakes the best detector scores 34.5% AUROC on commercial generators (DF26). So we verify the *payment*, not just the face." | one slide |
| 0:20-1:05 | **Moment 1 — detector catches it live.** "Rajesh" on Meet: "Priya, confidential acquisition, wire ₹48.5 lakh to this escrow account today, don't loop in Arjun." | side panel: voice meter red after ~10 s ("Likely synthetic voice, 2 windows"); ask chips *New account*, *Secrecy*, *Bypass approval*; suggested line "I'll process it once it's raised in the system with your login." |
| 1:05-1:30 | Priya taps **Confirm with Rajesh** (OOB-Confirm). | Screen C: "Did you just ask Priya to pay ₹48,50,000 to A/c ••••4821 (FAKM0000482)?" Rajesh taps **No, not me** → Priya's case turns **HOLD / SUSPECTED FRAUD**; checker + security notified. (fixture `case_s06`) |
| 1:30-2:05 | **Moment 2 — the floor catches what detectors miss.** Vendor email passes DMARC (compromised mailbox), invoice looks genuine, voice note is a real human. | every detector green ("sender authenticated", "no synthetic signs"). But: **"Bank account differs from vendor master (Fictional Bank B → Fictional Bank D) → VERIFY: call back on registered number +91-00000-10002 (from master)."** Role-played callback: "We never changed our bank." (fixture `case_s07`) |
| 2:05-2:30 | **Golden-hour pack.** Open the case where ₹6.2 lakh already left; checker sets CONFIRMED_FRAUD. | 1930 script with the **UTR on line 1**, bank fraud-desk email, NCRP draft, evidence index with hashes. "Nothing is auto-filed; the human submits." (fixture `case_s12`) |
| 2:30-2:45 | **Evidence it's real.** | one slide: voice-detector numbers through Meet/Opus/AMR (n, CI); paraphrase-robustness chart; "0/30 injections lowered a band"; AWS ap-south-1 architecture |

## Fallbacks

- Meet or network fails → Laptop A opens `extension/demo_call.html` and plays the call audio
  locally; the extension captures any tab, so this works offline.
- Detector misses the clone live → OOB-Confirm still turns the case to HOLD; say: "this is exactly
  why the floor exists."
- AWS down → automatic local fallbacks; template text looks identical.
- Full screen recording of a successful run is ready (`docs/pitch/backup_recording.md` has the link).

## Judge Q&A crib

- *"What about phone calls?"* — OS-level only; Google does it on Pixel. We cover the channel where
  corporate deepfake fraud happened (Arup): browser meetings. Phone recordings come in by upload.
- *"Isn't this just callback policy?"* — Callback is necessary, not sufficient. In Arup the person
  verifying was the person being deceived. Our detectors decide when verification must move to
  someone else, and OOB-Confirm reaches the real executive in seconds.
- *"Do you file the police complaint?"* — No. There is no public 1930/NCRP API. We prepare a
  UTR-first draft; a human submits it.
