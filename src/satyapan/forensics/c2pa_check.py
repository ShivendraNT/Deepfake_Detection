"""C2PA Content Credentials (images, audio and video).

Reads the manifest store with the official C2PA SDK (`c2pa-python`, Apache-2.0/MIT), reports
who signed it, what the claim says about how the content was made (c2pa.created with a
digitalSourceType of trainedAlgorithmicMedia = generative AI) and whether the signature and
the content hashes still validate. A content-hash mismatch means the file was altered after
it was signed.
"""

from __future__ import annotations

import contextlib
import io
import json
from typing import Any

from satyapan.forensics.base import Technique, finding, info, make_result
from satyapan.forensics.context import AnalysisContext
from satyapan.forensics.models import (
    Category,
    Finding,
    Hypothesis,
    MediaKind,
    Status,
    Strength,
    TechniqueResult,
)

AI_SOURCE_TYPES = ("trainedalgorithmicmedia", "compositewithtrainedalgorithmicmedia")
EDIT_ACTIONS = {
    "c2pa.edited", "c2pa.cropped", "c2pa.color_adjustments", "c2pa.resized",
    "c2pa.filtered", "c2pa.drawing", "c2pa.placed", "c2pa.removed", "c2pa.transcoded",
    "c2pa.converted", "c2pa.repackaged", "c2pa.orientation",
}  # fmt: skip


def _read(ctx: AnalysisContext) -> tuple[dict[str, Any] | None, str | None]:
    try:
        import c2pa  # type: ignore[import-not-found]
    except ImportError:
        return None, "unavailable"
    try:
        reader = c2pa.Reader(ctx.sniffed.mime, io.BytesIO(ctx.data))
    except Exception as exc:  # noqa: BLE001 - "no manifest" is an exception in the SDK
        msg = str(exc)
        if "ManifestNotFound" in msg or "no JUMBF" in msg.lower() or "not found" in msg.lower():
            return None, None
        if "NotSupported" in msg or "not supported" in msg.lower():
            return None, "unsupported"
        return None, f"error: {msg[:200]}"
    try:
        store = json.loads(reader.json())
    except Exception as exc:  # noqa: BLE001
        return None, f"error: {exc}"
    finally:
        with contextlib.suppress(Exception):
            reader.close()
    return store, None


def run_c2pa(ctx: AnalysisContext) -> TechniqueResult:
    t = C2PA
    store, problem = _read(ctx)
    jumbf_bytes = b"c2pa" in ctx.data[:2_000_000] and b"jumb" in ctx.data[:2_000_000]
    if problem == "unavailable":
        if jumbf_bytes:
            return make_result(t, summary="C2PA data present but the C2PA SDK is not installed",
                               status=Status.UNAVAILABLE)  # fmt: skip
        return make_result(t, summary="C2PA SDK not installed", status=Status.UNAVAILABLE)
    if problem == "unsupported":
        return make_result(t, summary="format not supported by the C2PA SDK",
                           status=Status.SKIPPED)  # fmt: skip
    if problem and problem.startswith("error"):
        findings = []
        if jumbf_bytes:
            findings.append(
                finding(
                    "C2PA_UNREADABLE",
                    "Content Credentials present but unreadable",
                    f"A C2PA manifest is embedded but could not be parsed ({problem[7:]}). "
                    "A damaged manifest can result from editing a signed file.",
                    Hypothesis.MANIPULATED,
                    Strength.WEAK,
                    Category.PROVENANCE,
                )  # fmt: skip
            )
        return make_result(t, summary="C2PA manifest could not be read", findings=findings)
    if store is None:
        return make_result(
            t, summary="no Content Credentials (C2PA) embedded",
            findings=[info("NO_C2PA", "No Content Credentials",
                           "The file carries no C2PA manifest. Most cameras, phones and "
                           "platforms do not add one yet, and re-saving removes it, so this is "
                           "expected and neutral.", Category.PROVENANCE)],
        )  # fmt: skip
    active_id = store.get("active_manifest")
    manifests = store.get("manifests", {})
    active = manifests.get(active_id, {}) if active_id else {}
    gen = active.get("claim_generator") or ""
    gen_info = active.get("claim_generator_info") or []
    if not gen and gen_info:
        gen = ", ".join(f"{g.get('name', '')} {g.get('version', '')}".strip() for g in gen_info)
    sig = active.get("signature_info") or {}
    issuer = sig.get("issuer") or sig.get("common_name") or "unknown signer"
    actions: list[dict[str, Any]] = []
    for a in active.get("assertions", []):
        if str(a.get("label", "")).startswith("c2pa.actions"):
            actions.extend(a.get("data", {}).get("actions", []))
    statuses = store.get("validation_status") or []
    vr = store.get("validation_results") or {}
    failures = [s for s in statuses if isinstance(s, dict)]
    if isinstance(vr, dict):
        am = vr.get("activeManifest") or {}
        failures += [f for f in am.get("failure", []) if isinstance(f, dict)]
    codes = sorted({str(f.get("code", "")) for f in failures if f.get("code")})
    findings: list[Finding] = []
    data = {
        "claim_generator": gen, "issuer": issuer, "signed_at": sig.get("time"),
        "title": active.get("title"), "actions": actions[:30], "validation_codes": codes,
        "manifests": len(manifests),
        "ingredients": [i.get("title") for i in active.get("ingredients", [])][:10],
    }  # fmt: skip
    hash_fail = [c for c in codes if "mismatch" in c or "hash" in c and "valid" not in c]
    untrusted = [c for c in codes if "untrusted" in c or "trust" in c]
    sig_fail = [c for c in codes if "signature" in c and "mismatch" in c or c.endswith(".invalid")]
    ai_actions = [
        a for a in actions
        if str(a.get("digitalSourceType", "")).rstrip("/").rsplit("/", 1)[-1].lower()
        in AI_SOURCE_TYPES
    ]  # fmt: skip
    if ai_actions:
        agent = ai_actions[0].get("softwareAgent")
        agent_name = agent.get("name") if isinstance(agent, dict) else agent
        findings.append(
            finding(
                "C2PA_AI_GENERATED",
                "Content Credentials declare generative AI",
                f"The signed C2PA manifest (signed by {issuer}, claim generator “{gen}”) "
                f"records the action “{ai_actions[0].get('action')}” with digital source "
                f"type trainedAlgorithmicMedia"
                + (f", software agent “{agent_name}”" if agent_name else "")
                + ". The "
                "creator's own signed record states the content was made with AI."
                + (
                    " The signer is not on this workstation's trust list, so anyone could have "
                    "made this manifest: moderate support until the signer is verified."
                    if untrusted and not (hash_fail or sig_fail)
                    else ""
                )
                + (
                    " The file was altered after signing, so the declaration describes an "
                    "earlier version of it."
                    if (hash_fail or sig_fail)
                    else ""
                ),
                Hypothesis.SYNTHETIC,
                (
                    Strength.MODERATE
                    if (hash_fail or sig_fail or untrusted)
                    else Strength.VERY_STRONG
                ),
                Category.PROVENANCE,
                issuer=issuer,
                generator=gen,
            )  # fmt: skip
        )
    edits = [a for a in actions if a.get("action") in EDIT_ACTIONS]
    if edits:
        findings.append(
            info(
                "C2PA_EDIT_HISTORY",
                f"Content Credentials record {len(edits)} edit action(s)",
                "Recorded actions: "
                + ", ".join(sorted({str(a.get("action")) for a in edits}))
                + ". These are declared, signed edits (an honest edit history), not hidden "
                "tampering.",
                Category.PROVENANCE,
                actions=[a.get("action") for a in edits],
            )  # fmt: skip
        )
    if hash_fail or sig_fail:
        findings.append(
            finding(
                "C2PA_INVALID",
                "Content Credentials no longer validate",
                "Validation failed with: " + ", ".join(hash_fail + sig_fail) + ". The "
                "content or the manifest was altered after it was signed; the claims in "
                "the manifest describe an earlier version of this file.",
                Hypothesis.MANIPULATED,
                Strength.STRONG,
                Category.INTEGRITY,
                codes=codes,
            )  # fmt: skip
        )
    elif not ai_actions:
        created = [a for a in actions if a.get("action") == "c2pa.created"]
        src = str(created[0].get("digitalSourceType", "")).rsplit("/", 1)[-1] if created else ""
        if src.lower() in ("digitalcapture", "computationalcapture"):
            findings.append(
                finding(
                    "C2PA_CAPTURE",
                    "Signed capture provenance",
                    f"The C2PA manifest, signed by {issuer}, declares a {src} with no "
                    "later edits, and its content hashes validate"
                    + (" (the signer is not on this workstation's trust list)" if untrusted else "")
                    + ".",
                    Hypothesis.AUTHENTIC,
                    Strength.MODERATE if untrusted else Strength.STRONG,
                    Category.PROVENANCE,
                    issuer=issuer,
                )  # fmt: skip
            )
    trust = ("trust not established" if untrusted else "signer trusted") if not (
        hash_fail or sig_fail) else "INVALID"  # fmt: skip
    summary = f"C2PA manifest by {gen or 'unknown tool'}, signed by {issuer} ({trust})"
    return make_result(t, summary=summary, findings=findings, data=data)


C2PA = Technique(
    "provenance.c2pa", "Content Credentials (C2PA)", Category.PROVENANCE,
    (MediaKind.IMAGE, MediaKind.AUDIO, MediaKind.VIDEO), run_c2pa,
    "The C2PA manifest store is read and validated with the reference SDK: the claim "
    "generator, the signer's certificate, the recorded actions (created / edited, with their "
    "digital source type) and the hard-binding content hashes. A failed content hash means "
    "the file changed after signing.",
    "C2PA Technical Specification 2.1 (Coalition for Content Provenance and Authenticity)",
    "Absence of a manifest is neutral. A valid manifest proves who signed what, not that the "
    "signer told the truth.", order=5,
)  # fmt: skip
