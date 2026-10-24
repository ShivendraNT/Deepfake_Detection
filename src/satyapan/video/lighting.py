"""Lighting, colour and reflection consistency between face regions.

A face swap pastes a generated inner face (cheeks, nose, mouth) into a real frame whose
forehead edge, hair and neck stay real. The two parts were lit and colour-graded separately,
so we compare them:

  light_chroma_gap   colour (Cb/Cr) difference between cheeks and forehead
  light_shade_gap    left/right shading of the cheeks vs. of the forehead (light direction)
  light_flicker      frame-to-frame jitter of cheek brightness relative to the forehead
  light_spec_gap     corneal highlights: both eyes see the same lights, so the highlight sits
                     at the same place in both irises (Hu et al. 2021); NaN when eyes are tiny
"""

from __future__ import annotations

import numpy as np


def _ycbcr(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    return np.stack([y, cb, cr], axis=-1)


def lighting_features(traces: dict[str, np.ndarray], spec: np.ndarray) -> dict[str, float]:
    """traces: {patch: (N, 3) RGB means}; spec: (N, 4) highlight offsets (NaN = none)."""
    out = {"light_chroma_gap": float("nan"), "light_shade_gap": float("nan"),
           "light_flicker": float("nan"), "light_spec_gap": float("nan")}  # fmt: skip
    need = ("forehead", "forehead_l", "forehead_r", "cheek_l", "cheek_r")
    if all(k in traces for k in need):
        ycc = {k: _ycbcr(np.asarray(traces[k], dtype=float)) for k in need}
        ok = np.all([np.all(np.isfinite(v), axis=1) for v in ycc.values()], axis=0)
        ok &= np.all([v[:, 0] > 5.0 for v in ycc.values()], axis=0)
        if ok.sum() >= 8:
            fh = ycc["forehead"][ok]
            cl, cr = ycc["cheek_l"][ok], ycc["cheek_r"][ok]
            ch = (cl + cr) / 2.0
            out["light_chroma_gap"] = float(
                np.median(np.hypot(ch[:, 1] - fh[:, 1], ch[:, 2] - fh[:, 2]))
            )
            cheek_ratio = np.log(cl[:, 0] / cr[:, 0])
            fh_ratio = np.log(ycc["forehead_l"][ok][:, 0] / ycc["forehead_r"][ok][:, 0])
            out["light_shade_gap"] = float(np.median(np.abs(cheek_ratio - fh_ratio)))
            d_cheek = np.diff(np.log(ch[:, 0]))
            d_fh = np.diff(np.log(fh[:, 0]))
            num = float(np.std(d_cheek - d_fh))
            den = float(np.std(d_fh)) + 1e-3
            out["light_flicker"] = float(np.log((num + 1e-4) / den))
    spec = np.asarray(spec, dtype=float).reshape(-1, 4)
    valid = np.all(np.isfinite(spec), axis=1)
    if len(spec) and valid.mean() >= 0.25:
        s = spec[valid]
        out["light_spec_gap"] = float(np.median(np.hypot(s[:, 0] - s[:, 2], s[:, 1] - s[:, 3])))
    return out
