# Satyapan Seal: prove the real executive, instead of detecting the fake

Component **C14**. Code: `src/satyapan/seal/`, routes in `src/satyapan/api/routes_seal.py`.
Evidence: `research/seal/README.md` and `results/seal_*.json|csv`. Decision: ADR-021.

> **Awaaz nakli ho sakti hai, mohar nahi.** A voice can be faked; the seal cannot.

## 1. The idea in five lines

1. A deepfake can copy the CFO's voice. It cannot copy the CFO's **passkey**.
2. **Voice Seal.** When the CFO speaks from his own enrolled laptop, his Satyapan client hides a
   faint keyed pattern in his outgoing speech (±2 dB level wobbles in 12 bands, 300-3400 Hz).
   The pattern is bound to *this meeting* and *this 5-second epoch*, and its keys come from a hash
   chain he committed to with one Touch ID.
3. Priya's side panel (or the console, for a forwarded voice note) checks the pattern and shows
   **"Rajesh: sealed ✓"** or **"Claims to be Rajesh: NOT sealed → verify"**.
4. **Intent Seal.** The same passkey signs SHA-256 of the exact payment (amount, beneficiary
   hash, case, nonce, expiry). Any change after approval breaks the signature.
5. A seal **adds** evidence only. "Sealed" never lowers a band or clears a HOLD. "Not sealed"
   never means "fake": at most it raises to VERIFY.

## 2. How the Voice Seal works (plain words)

| Step | Who | What |
|---|---|---|
| Enrol | CFO, once | Creates a passkey (Touch ID / Windows Hello). The server stores only the public key. |
| Session start | CFO, one Touch ID per meeting or voice note | The client picks a random secret seed and hashes it n times: `K_{e-1} = SHA-256(K_e)`, commitment `C = SHA-256(K_0)`. The passkey signs SHA-256 of the canonical statement *{employee, meeting, C, t0, 5 s epochs, n, seal parameters}*. The registry verifies it (py_webauthn, user verification required). |
| Sealing | CFO's client | Epoch e's ±1 pattern (12 bands × 104 chips of 48 ms) = SHAKE256(HMAC-SHA256(K_e, "seal\|meeting\|e")). Each band's level follows the pattern by ±2 dB. |
| Key disclosure | CFO's client, every 5 s | After epoch e has **ended**, the client posts K_e. The registry checks SHA-256(K_e) = K_{e-1}. Until then nobody else knows K_e, so nobody can forge the epoch that is being spoken (TESLA). |
| Verification | Receiver (side panel) or server (uploads) | Band energies → remove loudness, syllable motion and formant shape → correlate with the pattern: **z = Σ p·R / √ΣR²**. |

**Why false alarms are set by maths, not training data.** If the audio was not sealed with this
key, meeting and epoch, the pattern p is independent of the audio. Then z has mean 0 and variance
exactly 1 for *any* voice, language or accent, and P(z ≥ t) ≤ exp(−t²/2) (Hoeffding). Measured
over 3,920 attack epochs through 14 real codec chains: **mean +0.04, std 1.03, max 3.13**.

**Receiver protocol (v2, unbiased).** The network delay or file offset is unknown, so the verifier
searches it **once** (acquisition), with a threshold that pays for every offset tried
(Bonferroni, 10⁻⁶ per look). Then every epoch is scored at that **fixed** offset. Later looks
(Stouffer's combined z) use alpha spending, so the total false-seal budget per session stays at
3 × 10⁻⁶ live (2 acquisition looks + all later looks) and 4 × 10⁻⁶ for uploads (3 looks), however
long the call runs (Gaussian approximation; the distribution-free Hoeffding bound is looser, about
14× at the 5.49 threshold, and is reported in `results/seal_summary.json`). The lab's v1 re-searched the lag in every epoch; the maximum
biased attack scores upward and produced 1 false seal in 560 sessions. v2 removes that bias and
the code says so in large letters.

## 3. Policy: raise-only, as everywhere else

| Code | Group | Strength | Target | When it fires |
|---|---|---|---|---|
| `VOICE_SEALED` | provenance | weak | **NONE** (info only) | the audio carries a valid seal of an enrolled exec for this session |
| `VOICE_UNSEALED_CLAIMED_EXEC` | provenance | weak | **VERIFY** | an enrolled exec is *claimed* (Meet name, WhatsApp contact, maker's entry) and ≥ 15 s of speech carry no seal from that exec |
| `SEAL_PRESENCE_CONFLICT` | provenance | strong | HOLD with money movement, else VERIFY | the claimed exec's passkey-started session is live in a *different* meeting right now, and the voice here is not sealed |

All three are deterministic only (never from an LLM). Property tests over the real engine
(`tests/seal/test_seal_policy.py`, Hypothesis, 200 examples each) prove: adding any seal signal
never lowers a band; `VOICE_SEALED` changes neither band, queue nor clearance (so it can never
clear a HOLD); `VOICE_UNSEALED_CLAIMED_EXEC` alone gives exactly max(floor, VERIFY) and on top of
other signals raises to at most VERIFY. EN + Hindi explanation text says "Not sealed does not mean
fake" and uses no reassuring words (`explain/templates.py`).

Live-call caveat: in a multi-party meeting the 15 s must be speech *attributed to the claimed
participant* (Meet active-speaker). That wiring is finale work; for uploads (a voice note
claimed to be from the exec) all speech is attributed to the claimed sender.

## 4. Threat model

| Attack | Result | Why |
|---|---|---|
| Voice clone or real-time voice conversion of the CFO, any quality, any future generator | **Defeated: "not sealed"** | No K_e, so z ~ N(0,1). 0/560 attack sessions falsely sealed through 14 codec chains. Generator quality is irrelevant: this does not decay as deepfakes improve. |
| Strip or damage the seal | Irrelevant | Removal yields "not sealed", which the attacker already is. |
| Replay a recording of an earlier sealed call | **Defeated** | The pattern is bound to (meeting, epoch). Measured: replay at epoch+3 never sealed. |
| Relay the CFO's live sealed audio from meeting A into meeting B | **Defeated** | The pattern is bound to the meeting id; plus `SEAL_PRESENCE_CONFLICT`. |
| An insider with their own valid seal poses as the CFO | **Defeated** | The seal is identity-specific; the UI shows *who* sealed. |
| A receiver forges the CFO's seal for a later epoch | **Defeated** (live) | TESLA: K_{e+1} cannot be derived from K_e; keys are public only after their epoch. |
| Splice an unsealed fake sentence into a genuine sealed voice note | **Shown as a gap** | Per-epoch strip marks speech without seal; ≥ 15 s raises VERIFY. Shorter splices are shown, not escalated. |
| Forge a sealed *upload* after keys are known | Mitigated, not eliminated | Timing cannot be proven offline. Voice-note keys never leave the server; verification runs server-side; the result says `timing_provable = false`. A server/insider with key access could forge an upload. |
| Malware on the CFO's laptop | **Not defeated** | It can seal anything once he starts a session (same as any device-bound credential). Mitigations: Touch ID per session, short sessions, Intent Seal per payment. |
| Browser malware shows ₹48,500 but asks the passkey to sign ₹48,50,000 | **Not defeated** | A WebAuthn prompt shows no transaction text. Production fix: Secure-Payment-Confirmation-style browser UI or a second device. |
| CFO calls from a phone without the client | "Not sealed" (friction, not harm) | Honest UI: not sealed ≠ fake; normal VERIFY path (callback / OOB-Confirm). |
| Jam the seal with noise or heavy compression | Falls back to "not sealed" | Fail-safe: never fails open. Measured: Opus 24k + 15 dB white noise verified 9/10. |
| Overlay a fake voice in the same meeting while the real CFO is present and sealed | Partially | The seal proves his device's audio is in the mix, not that every word is his. Mitigation: active-speaker attribution (finale). |

## 5. Privacy and safety

- **No voiceprint, no biometric, no speaker model.** The seal is a key. Nothing about anyone's
  voice is stored. This avoids DPDP sensitive-data questions and accent/language bias.
- **Fairness by construction.** The false-alarm distribution does not depend on the voice.
  Measured attack z: English 6 voices vs Hindi 4 voices both ≈ N(0,1) (`results/seal_summary.json`).
- **Keys, not audio.** The exec's client sends 32-byte keys; receivers correlate locally; uploads
  are decoded in memory and not stored by the seal endpoint. The registry sees meeting ids and
  timing only.
- **Consent.** Only enrolled executives are sealed, behind their own Touch ID, on their own mic.
  Counterparties' audio is never modified. A visible "your voice is sealed in this meeting" badge
  and per-meeting opt-out are part of exec mode.
- **No accusations.** "Not sealed" is always phrased as "verify", never "fake"; the LLM is not
  involved. Makers see statuses only; raw z goes to checker/security (oracle-abuse rule 9).
- **Misuse.** Patterns are meaningless without disclosed keys; keys expire with the session. A seal
  cannot be put on someone's voice without their passkey.

## 6. Where it plugs into the architecture

| Component | Change |
|---|---|
| C9 policy | 3 provenance codes in `SIGNAL_TABLE` (above). Engine unchanged. |
| C14 Seal Registry (new) | `seal/registry.py` + `POST /seal/sessions`, `POST /seal/sessions/{id}/keys`, `GET /seal/meetings/{meeting}` |
| C6 uploads | `POST /seal/verify-upload` (`seal/verify_upload.py`): any ffmpeg-readable audio; offset search; per-epoch strip; gaps |
| C10 OOB-Confirm | Intent Seal: `POST /intent/challenge` builds the intent from the case's **trusted txn**; `POST /intent/verify`; every accepted/refused attempt goes to the custody chain. Wiring it in as a T12 clearance method is follow-up work; policy stays: OOB alone cannot clear HOLD. |
| C13 extension | Side-panel seal chip (`lib/seal_chip.js`, reducer event `seal`). Exec-mode embedder (AudioWorklet) and receiver-side detector are finale work. |
| C11 explanations | EN/HI text for the 3 codes. |

API summary:

| Method + path | Purpose |
|---|---|
| `POST /passkeys/{id}/register/options`, `POST /passkeys/{id}/register` | enrol your own passkey |
| `POST /seal/sessions` | passkey-signed SEAL-START → session |
| `POST /seal/sessions/{id}/keys` | disclose K_e after its epoch (hash-chain checked) |
| `GET /seal/meetings/{meeting}` | meeting sessions + disclosed keys (voice-note keys never listed) |
| `POST /seal/verify-upload` | voice note / recording → verification + signals |
| `POST /intent/challenge`, `POST /intent/verify` | Intent Seal |

## 7. Numbers (all from scripts in the repo; synthetic voices; illustrative, n stated)

| Claim | Number | Source |
|---|---|---|
| Attack sessions falsely sealed (clone, relay, replay e+3, wrong identity; 14 codec chains × 10 voices) | **0 / 560** | `results/seal_codec_eval.csv` |
| Attack z per epoch (post-acquisition, n = 3,920) | mean +0.04, std 1.03, max 3.13, 0 ≥ 4 | `results/seal_summary.json` |
| Genuine sessions verified | **139 / 140** (miss: Opus 24k + 15 dB white noise, one Hindi voice) | same |
| Median time to verdict | 5 s for clean, Opus 12-32k, AMR-NB 12.2, G.711, MP3, 5 % loss; 10 s Opus 8k; 20 s AMR-NB 4.75 | same |
| Chrome 141 WebRTC loopback (getUserMedia + APM, Opus, NetEQ), 2 voices × APM on/off | sealed 4/4 (EN 13/13 epochs, z̄ 6.89 / 6.79; HI 9/9, z̄ 5.27 / 5.48); unsealed, relay, replay controls not sealed | `results/seal_webrtc_probe.json` |
| + RNNoise ML denoiser (ffmpeg arnndn) | still sealed (13/13, 9/9) | same |
| + constant ±3 % time-scale (sox tempo) | **fails** at fixed rate; rate search recovers the verdict but only 4-5 of 9-13 epochs | same |
| Audibility proxies, ±2 dB | PESQ-WB 4.61, STOI 0.988 (plain Opus 32k: 4.46 / 0.994) | `results/seal_quality.json` |
| Intent Seal tamper tests | amount change, beneficiary swap, phishing origin, foreign key → refused; replay → refused | `tests/seal/test_seal_registry_intent.py`, `test_seal_api.py` |

Not yet measured: Google Meet's own server-side / ML noise cancellation (two-laptop test in
research/seal/README.md), a human listening test, real enrolment UX.
