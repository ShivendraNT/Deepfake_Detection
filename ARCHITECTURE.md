# Architecture

The full architecture lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

One-line summary: **the payment sets the floor, not the message.** A deterministic policy engine
(`src/satyapan/policy/`) compares each pending payment with the vendor master; emails, invoices,
voice notes and live-call audio are raise-only evidence; OOB-Confirm and callbacks on trusted
numbers clear the band; reports are human-submitted drafts.
