"""Satyapan Seal (component C14): prove the REAL executive instead of detecting the fake.

* Voice Seal (`voiceseal.py`, `tesla.py`, `registry.py`, `verify_upload.py`): the enrolled
  executive's client hides a keyed, meeting-bound level pattern in outgoing speech; keys come from
  a passkey-committed TESLA hash chain and are disclosed only after each 5 s epoch.
* Intent Seal (`intent.py`): the same passkey signs SHA-256 of the exact payment.
* `signals.py` turns results into raise-only policy signals (VOICE_SEALED is info only).

Design, threat model and privacy notes: docs/SEAL.md. Evidence: research/seal/README.md.
Requires the `seal` extra (numpy, scipy, webauthn); the API imports it lazily.
"""
