# BLOCKERS.md — Encountered Blockers & Fallbacks

Any item that fails 3 times or cannot be installed in the offline environment is documented here along with its fallback.

1. **`c2pa-python` Native Rust/FFI Wheel in Offline Environment (M4)**:
   - **Check**: `import c2pa` in `.venv` (`No module named 'c2pa'`), and `~/.cache/uv` does not contain a cached `c2pa-python` wheel for offline installation.
   - **Fallback Implemented**: In `src/satyapan/forensics/provenance.py` (`verify_c2pa_credentials`), we first attempt `import c2pa` dynamically, and when absent, execute a built-in pure-Python **JUMBF (`c2pa` superbox) Content Credentials Parser & Cryptographic Verifier** supporting JPEG APP11 (`0xFFEB`), PNG `caBX`, and ISO BMFF `uuid` (`63327061-0011-0010-8000-00aa00389b71`) manifests with SHA-256 payload hard-binding verification and Ed25519 (`cryptography`) signature verification.
