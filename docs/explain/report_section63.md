# `forensics/report.py` + `forensics/section63.py` — the court-facing report

**What it does.** One call produces `forensic_report.pdf`, `.html`, `.md` and `.json` inside the case
folder: case details, SHA-256 schedule, signed custody log, Merkle root, methods, per-exhibit findings
with embedded heatmaps, limitations, examiner sign-off, and a draft Section 63 (Bharatiya Sakshya
Adhiniyam, 2023) Parts A & B certificate.

**Core idea.** A forensic report must be (1) reproducible, (2) inspectable, (3) honest about limits.
So the generator takes its timestamp from the stored `analysis.json` (not the wall clock): given the
same case data, all four formats come out byte-identical. The PDF is written directly (PDF 1.4, vector
Helvetica/Courier text + `/DCTDecode` image streams) so every hash and finding is selectable and
`pdfplumber`-extractable, and so it needs no external renderer offline. Section 63 is produced as a
**draft for a human**: Part A is the declaration by the person in charge (records schedule + device
particulars), Part B is the technical examiner's certificate (SHA-256 FIPS 180-4, Ed25519 RFC 8032,
Merkle root vs anchor, offline checkbox).

**Five questions a judge may ask**

1. *Can I regenerate the report and compare?* Yes — that is a test: run the generator twice on the
   same stored case and compare SHA-256 of all four files. They match.
2. *Why not ReportLab?* It is not in the base offline environment. Writing the PDF directly keeps the
   install small and the output deterministic; the trade-off is a simpler layout.
3. *Does the PDF prove the evidence is authentic?* No. It records the hashes, signatures and Merkle
   root so a human can verify them; admissibility is for a court.
4. *What exactly does Part B certify?* Hash standard, signing standard, chain head, Merkle root and
   whether it matches the anchor, verification status at generation, and the examiner's declaration —
   with blanks left for signature, designation and seal.
5. *Is the Section 63 text legally reviewed?* No. It is a technical draft modelled on the statute's
   requirements (and reused from our sibling project Pramaan). A lawyer must review it before use.

**Weaknesses.** Layout is functional, not typeset. Embedded images are JPEG renderings of derived
artefacts (the sealed originals are the evidence). The anchor is local. No RFC 3161 timestamp.
