# Live demo script (7–8 minutes)

**Once, with network** (≈ 5 min): `make lab-setup` (models) and `make demo-dataset` (downloads
and builds the media of real people that are never committed; `make demo-dataset-check`
verifies the hashes). **Before the session**: `make lab`, open `http://127.0.0.1:8000/lab`,
press **Load demo case** and let every exhibit finish (≈ 70 s on a 4-core machine with 16 GB). Leave it
loaded: the case persists in `lab_data/`, and pressing the button again opens it rather than
wiping it. Keep one or two of your own test files ready for the "judge's file" moment.

Every number below is what the lab actually prints on this case
(`results/forensics_demo_benchmark.md`); nothing is staged.

Pitch line: *"Deepfakes and edited media are now evidence in Indian cyber cases — digital
arrests, voice-clone emergencies, forged notices. An investigator needs three answers about
every file: is it synthetic, was it altered, where did it come from — in a form that survives
cross-examination. Satyapan Forensic Lab runs offline on the examiner's workstation, shows its
working, and says plainly what it cannot tell."*

## 1. The case (30 s)

Open **Operation Pratibimb — FIR No. 0457/2026**. A retired professor, a "digital arrest"
video call, a notice, an officer ID, voice notes from his "daughter" and a Hindi "CBI" note;
₹4,50,000 lost; the suspect's laptop seized. Point at the exhibit marks: **Q** = questioned,
**R** = reference samples (seized laptop, family) — "how an FSL marks exhibits". Read the
**Findings across the case** panel: one paragraph, every sentence traceable to a finding.

## 2. Intake and integrity (40 s)

Drop any file (one exhibit again → *duplicate detected by SHA-256*, or a fresh file). Show the
**live analysis stream**: integrity re-verified, then the techniques ticking off. Open **Chain
of custody**: *"every action is a hash-chained row — intake, each analysis, each
re-evaluation, each report. Change one byte and verification fails, on screen."*

## 3. The deepfake video call — source attribution (75 s)

Open `VID-20261021-WA0003.mp4` → **SYNTHETIC, strong support**.

* Be candid first: on its own file, the face model gives only one *weak* window — *"modern
  online face-swaps beat detectors trained on older ones; our validation page says so."*
* Then **Cross-exhibit comparison**: the key frames are the same footage as the clip from the
  suspect's laptop (perceptual hashes 0–2 bits apart), but a different person (face similarity
  0.22–0.33, below the 0.45 match line); the face is the profile photo's (0.80–0.83); and the
  frame-difference figure lights up only on the face.
* *"The deepfake was assembled from a clip on the suspect's laptop and a photo from the
  suspects' social-media account. That is attribution, not a score."* Show the provenance graph.

## 4. The forged notice (60 s)

Open `IMG-20261021-WA0011.jpg` → **MANIPULATED, very strong support**.
* Copy-move: lines join the cloned stamp to its source (54 keypoints moving together).
* ELA marks the pasted lines (indicative only — capped at *moderate* by design).
* The link to `notice_template_from_laptop.jpg`: the aligned difference map **boxes the
  addressee and the amount** — *"made from the template on the suspect's laptop."*

## 5. The AI-generated "officer ID" (60 s)

Open `officer_id_photo_original.png` → **SYNTHETIC, moderately strong support**, and explain
why it is not "very strong":
* Content Credentials declare `trainedAlgorithmicMedia` — but the signer is not on this
  workstation's trust list, and *"anyone can sign a manifest with their own certificate"*, so
  it counts as *moderate*.
* The AI-image classifier is above its strict threshold — *moderate*, because at that
  threshold it catches 52 % of AI images with 2.5 % false alarms (likelihood ratio ≈ 21).
* Two independent moderate findings → *moderately strong*. Stability's invisible watermark
  was applied to this image, but on its flat grey background neither the reference decoder
  nor ours can read it back: *"signatures are fragile."*

Then `IMG-20261021-WA0012.jpg` (the WhatsApp copy): metadata and credentials are gone; the
classifier still fires and the case comparison identifies it as a copy of Q7 → **SYNTHETIC**.

## 6. The defence's call recording (45 s)

Open `call_recording_20261021_1412.wav` → **MANIPULATED, strong support**. The **ENF chart**:
the 50 Hz grid hum drifts smoothly, then breaks once at **16.5 s** by **−57 mHz** — the two
sessions were joined at 16.54 s with a 55 mHz difference in mains frequency. *"The classic FSL
technique, automated, and within a tenth of a second."*

## 7. The voices — where we draw the line (60 s)

* `PTT-20261021-WA0009.opus` (Hindi): the **Hindi transcript with English translation**, and
  the fraud lexicon marking "digital arrest", "safe account", OTP and secrecy. The voice
  detector puts 3 of 4 windows above its lenient threshold — *weak* only.
* `PTT-20261021-WA0007.opus` ("daughter"): the case graph shows the **same speaker** as the
  family's known sample (cosine 0.90). The voice detector does not flag it, and the verdict
  says *"no indications — this does not prove it is authentic"*.
* *"Free open-source TTS voices are our documented blind spot. We trained a head for them:
  AUC 0.93 on unseen voices — but at the strict threshold it caught 49.3 % against the 50 % we
  pre-registered, so it is not in the verdicts. A forensic tool that moves its own goalposts
  is worse than one that admits a gap."* Next step for the investigator: the sender's device.

## 8. The report (45 s)

Reports tab → generate → open the PDF: QR verification code, findings across the case, hash
table, methodology with references, one section per exhibit with figures, the custody chain,
**known error rates**, and the **Section 63(4)(c) BSA 2023 certificate (Part B) pre-filled
with the hashes — for the examiner to verify and sign**. *"The software never signs or submits
anything."*

## 9. The judge's own file (open-ended)

Invite a judge to drop any image, video or audio. Talk through whatever comes back, including
the *"could not be checked"* list. When a technique abstains (no face, too little speech), say
why — abstaining honestly is a feature.

## 10. Close (20 s)

*"Offline on an FSL workstation; 22 techniques per file plus cross-exhibit reasoning;
deterministic verdict rules with strength words tied to measured error rates; no false alarm on
the genuine exhibits; court-ready reporting. Next: a three-month pilot with one cyber cell and
one FSL, validation on Indian casework, NABL scope and Section 79A notification."*
(→ `docs/forensics/DEPLOYMENT_ROADMAP.md`)

## Fallbacks

* Dataset not built: **Load demo case** says which files are missing → `make demo-dataset`.
* Laptop without some models: the case still runs; affected techniques show *unavailable* and
  are listed under "not checked".
* No network needed once models and dataset are local.
* Terminal alternative: `make examine F=data/forensics/demo REPORT=1` prints every verdict, link
  and the custody-chain status, and writes the PDF.

## Q&A crib

| Question | Answer |
|---|---|
| How accurate is it? | Per technique, on held-out public data (VALIDATION.md): face-swap video AUC 0.946 on FF++ with 0 of 563 real videos called synthetic; AI images AUC 0.88, 52 % caught at 2.5 % false alarms; voice AUC 0.92 on real-world deepfakes. End to end on held-out photos: see `results/forensics_e2e_images.md`. Failure cases are listed too. |
| Why "moderate" when the classifier is sure? | A score is not a probability for *this* file. The word comes from the measured error rate at that threshold (LR ≈ 21 → moderate on the ENFSI scale). |
| Can an attacker evade it? | Any single detector, yes — which is why a firm verdict needs a strong finding or two independent ones, why cross-exhibit links matter, and why "no indications" never means authentic. |
| Is this admissible? | It supports an expert opinion: hash-first intake, write-once storage, custody chain, method references, known error rates, ENFSI wording, the BSA s.63 Part B draft. The examiner gives the opinion and signs. |
| Why not cloud? | Evidence cannot leave the lab; everything runs on CPU locally. |
| Indian languages? | Whisper (offline) transcribes Hindi and Hinglish and translates to English; the fraud lexicon covers English, Hinglish and Devanagari. The shipped voice detector was validated on English; Hindi false-alarm rates still need Indian casework (roadmap). |
| Where does the demo media come from? | Generated by us (notice, forgery, AI portrait, call mix) or public research data used under licence (UniData consented participants, LJSpeech public domain). Media of real people are built locally, never committed. |
