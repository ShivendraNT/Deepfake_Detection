# `forensics/provenance.py` — metadata, C2PA Content Credentials, source attribution

**What it does.** `extract_and_verify_metadata` pulls EXIF (including SubIFD and GPS), XMP and PNG
text chunks, then runs five consistency checks: timestamp chronology, editing/AI software signatures,
GPS plausibility (bounds, Null Island, GPS-date vs capture-date), embedded APP1 thumbnail vs the main
image, and camera-vs-container contradictions. `verify_c2pa_credentials` verifies a JUMBF `c2pa`
manifest (JPEG APP11, PNG `caBX`, ISO BMFF) including SHA-256 hard binding and the Ed25519 signature.
`attribute_compression_source` classifies the last encoder as `camera_original`,
`social_messaging_reencode` or `editing_software_resave`.

**Core idea.** Metadata is cheap to forge but cheap to *cross-check*: forgers change one field and
forget the others. A thumbnail that no longer matches the image is the classic tell of a crop or
splice. Compression is the other tell: camera originals keep camera tags, a high-quality 4:4:4 profile
and an intact thumbnail, whereas WhatsApp-style copies are 4:2:0, medium quality, and stripped of
metadata. We never say "this camera took it" — only "consistent with camera capture", unless a valid
C2PA manifest binds the bytes to a signer.

**Five questions a judge may ask**

1. *Isn't EXIF trivially fakeable?* Yes. That is why the report says "consistent with", and why the
   strongest statement we allow is a verified C2PA hard binding. Everything else is corroboration.
2. *What does C2PA verification actually prove?* That the manifest's signature is valid and the
   SHA-256 of the asset payload matches the signed claim, i.e. the bytes were not modified after
   signing. It does not prove the signer told the truth.
3. *Did you verify real camera C2PA manifests?* Not fully: the official `c2pa-python` library could
   not be installed offline, so third-party X.509/COSE chains are detected and reported as
   "unparsed" instead of falsely "verified". Our own Ed25519 JUMBF manifests verify 15/15, and
   post-signing tampering is caught 15/15. This is in `BLOCKERS.md`.
4. *How accurate is the 3-class attribution?* 98.0% accuracy / 0.980 macro-F1 on 150 seeded
   re-encoded images (50 per class). The confusion is high-quality messaging re-encodes landing near
   the camera boundary; we report per-class precision/recall.
5. *Could an attacker strip metadata to defeat you?* Yes for the metadata checks — measured: catch
   rate goes 100% -> 0% after stripping. That is exactly why pixel detectors (M2/M3) exist and why we
   report the two evidence families separately.

**Weaknesses.** Unsigned metadata is not evidence of origin. Screenshots/re-shot photos break the
capture chain. Third-party C2PA needs the official library. Attribution identifies the *last* encoder,
not the first.
