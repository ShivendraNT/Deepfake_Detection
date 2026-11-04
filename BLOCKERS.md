# BLOCKERS.md — Encountered Blockers & Fallbacks

Any item that fails 3 times or cannot be installed in the offline environment is documented here along with its fallback.

1. **`c2pa-python` Native Rust/FFI Wheel in Offline Environment (M4)**:
   - **Check**: `import c2pa` in `.venv` (`No module named 'c2pa'`), and `~/.cache/uv` does not contain a cached `c2pa-python` wheel for offline installation.
   - **Fallback Implemented**: In `src/satyapan/forensics/provenance.py` (`verify_c2pa_credentials`), we first attempt `import c2pa` dynamically, and when absent, execute a built-in pure-Python **JUMBF (`c2pa` superbox) Content Credentials Parser & Cryptographic Verifier** supporting JPEG APP11 (`0xFFEB`), PNG `caBX`, and ISO BMFF `uuid` (`63327061-0011-0010-8000-00aa00389b71`) manifests with SHA-256 payload hard-binding verification and Ed25519 (`cryptography`) signature verification.

2. **Docker daemon unavailable on this workstation (M8 verification only)**:
   - **Check**: `docker --version` works (28.3.2, Compose v2.39.1) but `docker compose build` fails with
     `Cannot connect to the Docker daemon ... Is the docker daemon running?` (Docker Desktop is not
     started in this environment).
   - **Fallback Implemented**: The non-Docker path is fully verified (`make demo`: intake -> analysis ->
     PDF + Section 63 on the committed `demo_kit/`, all 6 expectations matched), and
     `tests/forensics/test_m8_deploy.py` validates the compose file structure, the Dockerfile contract
     (offline runtime, no baked models, healthcheck), and the documented commands without needing a
     daemon. `docker compose up --build` must be run once on a machine with Docker running before it is
     claimed as tested; the image build itself has NOT been executed here.
