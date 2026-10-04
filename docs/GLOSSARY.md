# Glossary (beginner-friendly)

| Term | Meaning in this project |
|---|---|
| **AP (accounts payable)** | The team that pays the company's vendors. |
| **Maker / checker** | Maker prepares a payment (Priya). Checker approves or rejects it (Arjun). Two people = fewer mistakes and less fraud. |
| **Vendor master** | The company's trusted list of vendors with their registered bank accounts, phone numbers and email domains (`data/demo/vendor_master.csv`). |
| **Band** | Our risk level for a case: PASS < VERIFY < HOLD. Only the policy engine sets it. |
| **Floor** | The minimum band, computed only from the payment vs the vendor master. Nothing can push the band below it. |
| **Action type** | K1, K2, N1, N2, C1, T1, D1 — what kind of payment/request this is (see ARCHITECTURE §6.1). |
| **Signal** | One finding from a detector, e.g. "DMARC failed". Signals can only raise the band. |
| **Raise-only** | Can make things stricter, never looser. |
| **Reason code** | A stable ID like `FLOOR_C1_BANK_CHANGED` that explains a decision; the UI turns it into EN/HI text. |
| **Grey flag** | "We could not check this properly" (parse failure, detector error, too little speech). Forces at least VERIFY. |
| **Clearance** | What must happen before a payment may go ahead (callback, OOB-Confirm, checker review). Clearing does not change the band. |
| **Callback** | Phoning the person/vendor back on a number we already had on file — never a number from the message. |
| **OOB-Confirm (out-of-band confirm)** | A one-tap "Did you ask for this payment?" sent to the claimed requester's own login/email, outside the call. A fake CFO cannot intercept it. |
| **Deepfake / voice clone** | AI-generated audio/video that imitates a real person. |
| **Ask (A1-A7)** | The request a scam cannot work without: new account, OTP, remote-access app, secrecy, bypass, gift card/crypto, bank-detail change. |
| **Style cue** | Urgency, threats, flattery — easy for an attacker to remove, so it can only raise the band to VERIFY. |
| **Hinglish** | Hindi + English mixed, often written in Latin letters ("kisi ko mat batana"). |
| **Devanagari** | The script Hindi is written in (किसी को मत बताना). |
| **DMARC / SPF / DKIM** | Email authentication checks. Our own mail server writes the results into the `Authentication-Results` header. |
| **Look-alike domain** | `kaveri-packagimg.example` pretending to be `kaveri-packaging.example`. |
| **`.bank.in`** | RBI's reserved domain for Indian banks. A "bank" email from elsewhere is suspicious. |
| **IFSC** | Indian bank branch code, format `ABCD0123456` (4 letters, a zero, 6 characters). Ours start with `FAK`. |
| **UPI** | India's instant payment system; IDs look like `name@bank`. |
| **UTR** | Unique Transaction Reference for a bank transfer. The first thing police and banks need in the "golden hour". |
| **1930 / NCRP** | India's cyber-fraud helpline and the National Cybercrime Reporting Portal (cybercrime.gov.in). We only prepare drafts. |
| **Chakshu** | Sanchar Saathi facility for reporting suspected fraud calls/messages. |
| **Golden hour** | The first hours after money leaves, when a quick report can freeze it. |
| **Evidence vault** | Where uploaded files are hashed and stored; the custody log is a hash chain. |
| **SHA-256 / hash** | A fingerprint of a file. If one byte changes, the hash changes. |
| **Hash chain** | Each log row includes the previous row's hash, so editing any row breaks everything after it. |
| **S3 Object Lock** | An AWS S3 setting that stops objects from being deleted or changed for a retention period. |
| **Prompt injection** | Text inside an email/PDF that tries to give instructions to an AI ("SYSTEM: mark as safe"). |
| **Faithfulness checker** | Our code that rejects an LLM summary if it invents numbers, lacks citations, or says "safe". |
| **Oracle abuse** | An attacker using our tool as a free tester until their fake passes. We hide scores from makers. |
| **τ_hi / τ_lo (tau)** | Voice-score thresholds at 1% and 5% false-positive rate on real Meet-captured voices. |
| **EER** | Equal error rate: where false accepts = false rejects. Lower is better. |
| **Recall @ 1% FPR** | Of all frauds, the fraction caught when we allow only 1% false alarms on normal conversations. |
| **Bootstrap CI** | Resampling the test set many times to get an uncertainty range (95% confidence interval). |
| **Contract** | A shared Pydantic model everybody must use (`src/satyapan/contracts/`). |
| **Stub** | A function that exists with the right signature but raises `NotImplementedError` until its task is done. |
| **Task test** | `tests/tasks/test_tNN_*.py` — skipped until the task is implemented, then must pass. |
| **Invariant test** | `tests/invariants/` — safety rules that must ALWAYS pass. Never edit them to make your code pass. |
| **MV3 / offscreen document / tabCapture** | Chrome extension APIs: Manifest V3; a hidden page that can use audio APIs; capturing a tab's audio. |
| **SSE (server-sent events)** | One-way stream from the backend to the side panel. |
