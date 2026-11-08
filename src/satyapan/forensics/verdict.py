"""From findings to a verdict: a fixed rule table, not a model (docs/forensics/METHODOLOGY.md).

Rules, applied in order:
  1. SYNTHETIC    if any finding supports "synthetic" with STRONG or VERY_STRONG strength, or
                  two different techniques each give at least MODERATE support for it.
  2. MANIPULATED  if any finding supports "manipulated" with STRONG or VERY_STRONG strength,
                  or two different techniques each give at least MODERATE support and at
                  least one of them is structural (not one of the indicative pixel maps:
                  ELA, noise residue, JPEG grid), so two heat maps never convict alone.
  3. SUSPICIOUS   if any synthetic / manipulated finding is MODERATE, or three different
                  techniques give WEAK support for manipulation.
  4. INCONCLUSIVE if fewer than two authenticity techniques (synthetic or tampering
                  category) completed on this file.
  5. NO_INDICATORS otherwise; weak indications below the threshold are named in the text.
Confidence words follow the ENFSI verbal scale. The strongest supported hypothesis sets the
statement; every technique that could not run is listed under "not checked". The risk index
is only a dashboard gauge derived from the same rule.
"""

from __future__ import annotations

from satyapan.forensics.models import (
    STRENGTH_WORDS,
    Category,
    Finding,
    Hypothesis,
    MediaKind,
    Provenance,
    Status,
    Strength,
    TechniqueResult,
    Verdict,
    VerdictLabel,
)

NOUN = {MediaKind.IMAGE: "image", MediaKind.AUDIO: "recording", MediaKind.VIDEO: "video",
        MediaKind.DOCUMENT: "document", MediaKind.OTHER: "file"}  # fmt: skip


def _all_findings(results: list[TechniqueResult]) -> list[Finding]:
    return [f for r in results for f in r.findings]


def _max(findings: list[Finding], hyp: Hypothesis) -> Strength:
    vals = [f.strength for f in findings if f.hypothesis == hyp]
    return max(vals, default=Strength.NONE)


def _techs(findings: list[Finding], hyp: Hypothesis, at_least: Strength) -> set[str]:
    return {f.technique for f in findings if f.hypothesis == hyp and f.strength >= at_least}


# Indicative pixel maps: useful to localise, never sufficient on their own (METHODOLOGY.md).
INDICATIVE = frozenset({"image.ela", "image.noise", "image.jpeg_grid"})


def decide(kind: MediaKind, results: list[TechniqueResult]) -> Verdict:
    fs = _all_findings(results)
    syn = _max(fs, Hypothesis.SYNTHETIC)
    man = _max(fs, Hypothesis.MANIPULATED)
    auth = _max(fs, Hypothesis.AUTHENTIC)
    man_mod = _techs(fs, Hypothesis.MANIPULATED, Strength.MODERATE)
    man_weak = _techs(fs, Hypothesis.MANIPULATED, Strength.WEAK)
    syn_strong = _techs(fs, Hypothesis.SYNTHETIC, Strength.STRONG)
    syn_mod = _techs(fs, Hypothesis.SYNTHETIC, Strength.MODERATE)
    structural = man_mod - INDICATIVE
    checks_ok = [
        r for r in results
        if r.status == Status.OK and r.category in (Category.SYNTHETIC, Category.TAMPERING)
    ]  # fmt: skip
    not_checked = [f"{r.name}: {r.summary}" for r in results
                   if r.status in (Status.UNAVAILABLE, Status.ERROR)]  # fmt: skip
    not_checked += [f"{r.name}: {r.summary}" for r in results if r.status == Status.SKIPPED
                    and r.category in (Category.SYNTHETIC, Category.TAMPERING)]  # fmt: skip
    noun = NOUN.get(kind, "file")
    rationale = [
        f"[{STRENGTH_WORDS[f.strength]}] {f.title}"
        for f in sorted(fs, key=lambda f: -int(f.strength))
        if f.hypothesis != Hypothesis.NEUTRAL and f.strength > Strength.NONE
    ][:8]  # fmt: skip
    key = [f.code for f in sorted(fs, key=lambda f: -int(f.strength))
           if f.hypothesis in (Hypothesis.SYNTHETIC, Hypothesis.MANIPULATED)
           and f.strength >= Strength.WEAK][:6]  # fmt: skip
    hyps = {"synthetic": int(syn), "manipulated": int(man), "authentic": int(auth)}

    if syn >= Strength.STRONG or len(syn_mod) >= 2:
        if syn >= Strength.STRONG:
            conf = (Strength.VERY_STRONG if syn == Strength.VERY_STRONG or len(syn_strong) >= 2
                    or (len(syn_mod) >= 2 and syn >= Strength.STRONG) else syn)  # fmt: skip
            word = STRENGTH_WORDS[conf]
            risk = 96 if conf == Strength.VERY_STRONG else 88
        else:  # two independent moderate findings agree
            word, risk = "moderately strong support", 80
        what = (
            "AI-generated or deepfaked"
            if kind != MediaKind.AUDIO
            else "synthetic (AI-generated voice)"
        )
        extra = " It also shows signs of editing." if man >= Strength.MODERATE else ""
        return Verdict(
            label=VerdictLabel.SYNTHETIC,
            headline=f"Synthetic {noun}: {word}",
            statement=f"The findings provide {word} for the proposition that the {noun} is "
            f"{what}, rather than an unaltered original capture.{extra}",
            confidence=word, risk_index=risk, hypotheses=hyps, key_findings=key,
            rationale=rationale, not_checked=not_checked,
        )  # fmt: skip
    if man >= Strength.STRONG or (len(man_mod) >= 2 and structural):
        if man >= Strength.STRONG:
            conf = Strength.VERY_STRONG if len(man_mod) >= 2 else man
            word = STRENGTH_WORDS[conf]
            risk = 92 if conf == Strength.VERY_STRONG else 84
        else:  # two independent moderate findings, one of them structural
            word, risk = "moderately strong support", 76
        return Verdict(
            label=VerdictLabel.MANIPULATED,
            headline=f"Manipulated {noun}: {word}",
            statement=f"The findings provide {word} for the proposition that the {noun} was "
            "altered after capture (content added, removed, copied or re-recorded), rather "
            "than being an unaltered original.",
            confidence=word, risk_index=risk, hypotheses=hyps, key_findings=key,
            rationale=rationale, not_checked=not_checked,
        )  # fmt: skip
    if syn >= Strength.MODERATE or man >= Strength.MODERATE or len(man_weak) >= 3:
        n_mod = len(_techs(fs, Hypothesis.SYNTHETIC, Strength.MODERATE) | man_mod)
        risk = min(69, 50 + 7 * max(1, n_mod) + 2 * len(man_weak))
        which = "synthesis" if syn >= man else "manipulation"
        return Verdict(
            label=VerdictLabel.SUSPICIOUS,
            headline=f"Suspicious {noun}: indications of {which}",
            statement=f"The findings provide moderate support for {which}, which is not "
            "sufficient for a firm conclusion. The flagged segments or regions should be "
            "examined further, ideally against the original source file or device.",
            confidence=STRENGTH_WORDS[max(syn, man, Strength.MODERATE)], risk_index=risk,
            hypotheses=hyps, key_findings=key, rationale=rationale, not_checked=not_checked,
        )  # fmt: skip
    if len(checks_ok) < 2:
        return Verdict(
            label=VerdictLabel.INCONCLUSIVE,
            headline=f"Inconclusive: too little of the {noun} could be examined",
            statement=f"Only {len(checks_ok)} authenticity technique(s) could be applied to this "
            f"{noun}, which is not enough to form an opinion. See 'not checked'.",
            confidence="insufficient data", risk_index=35, hypotheses=hyps, key_findings=key,
            rationale=rationale, not_checked=not_checked,
        )  # fmt: skip
    risk = max(3, min(25, 10 + 4 * len(man_weak) - 4 * int(auth)))
    support = (f" Positive authenticity indicators: {STRENGTH_WORDS[auth]}."
               if auth >= Strength.MODERATE else "")  # fmt: skip
    weak = [f.title for f in fs if f.strength == Strength.WEAK
            and f.hypothesis in (Hypothesis.SYNTHETIC, Hypothesis.MANIPULATED)]  # fmt: skip
    if weak:
        support += (f" Weak indications below the threshold for concern were noted "
                    f"({'; '.join(dict.fromkeys(weak[:3]))}); they are listed in the findings.")  # fmt: skip
    return Verdict(
        label=VerdictLabel.NO_INDICATORS,
        headline=f"No indications of manipulation or synthesis in the {noun}",
        statement=f"None of the {len(checks_ok)} authenticity techniques applied found "
        f"significant indications of synthesis or manipulation.{support} This does not prove "
        f"the {noun} is "
        "authentic: techniques that could not be applied, and their known limits, are listed.",
        confidence="no support for manipulation", risk_index=risk, hypotheses=hyps,
        key_findings=key, rationale=rationale, not_checked=not_checked,
    )  # fmt: skip


def provenance(results: list[TechniqueResult]) -> Provenance:
    """Collect the provenance facts the techniques established, with a reconstructed chain."""
    p = Provenance()
    chain: list[str] = []
    for r in results:
        for f in r.findings:
            o = f.observations
            if f.code == "CAMERA_IDENTIFIED":
                p.device = (f"{o.get('make', '')} {o.get('model', '')}").strip() or p.device
                chain.insert(0, f"Captured by {p.device} (EXIF)")
            elif f.code == "DEVICE_METADATA":
                p.device = p.device or f.title.split(": ", 1)[-1]
                chain.insert(0, f"Recorded on {p.device} (container tags)")
            elif f.code in ("GENERATOR_SIGNATURE", "SD_WATERMARK", "C2PA_AI_GENERATED",
                            "TTS_SIGNATURE", "VIDEO_GENERATOR_SIGNATURE", "AI_SYSTEM_DECLARED"):  # fmt: skip
                gen = str(o.get("generator") or o.get("tool") or o.get("value") or f.title)
                if not p.generator:
                    p.generator = gen
                chain.insert(0, f"Generated by {gen} ({r.name.lower()})")
            elif f.code == "EDITING_SOFTWARE":
                p.software = str(o.get("editor"))
                chain.append(f"Edited / saved with {p.software}")
            elif f.code == "ENCODER_TAG":
                p.software = p.software or str(o.get("encoder"))
                chain.append(f"Encoded by {str(o.get('encoder'))[:40]}")
            elif f.code == "PLATFORM_TRACE":
                p.platform = p.platform or str(o.get("platform"))
                chain.append(f"Passed through {o.get('platform')}")
            elif f.code in ("GPS_LOCATION",) and "lat" in o:
                p.gps = {"lat": float(o["lat"]), "lon": float(o["lon"])}
            elif f.code == "CREATION_TIME":
                p.capture_time = p.capture_time or str(o.get("creation_time"))
            elif f.code == "PRIOR_JPEG_COMPRESSION":
                chain.append("JPEG-compressed, later converted to a lossless format")
            elif f.code == "BANDWIDTH_LIMIT":
                chain.append(f"Audio history: {o.get('meaning')}")
            elif f.code in ("C2PA_CAPTURE", "C2PA_EDIT_HISTORY", "C2PA_INVALID"):
                p.content_credentials = f.title
        if r.id == "image.metadata":
            ex = r.data.get("exif", {}) if isinstance(r.data.get("exif"), dict) else {}
            p.capture_time = p.capture_time or ex.get("DateTimeOriginal")
        if r.id == "provenance.c2pa" and r.status == Status.OK and r.data.get("issuer"):
            p.content_credentials = p.content_credentials or r.summary
    p.chain = list(dict.fromkeys(chain))[:10]
    return p
