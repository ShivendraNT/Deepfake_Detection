"""Role-based output coarsening (oracle-abuse mitigation, ARCHITECTURE §10). PRE-IMPLEMENTED.

| Viewer            | Sees                                  | Does not see                    |
| maker             | band, reason codes, steps, evidence   | raw scores, score-like details  |
| checker/security  | everything                            | —                               |
"""

from __future__ import annotations

from typing import Any

from satyapan.contracts.case import Case
from satyapan.contracts.enums import Role
from satyapan.policy.permissions import can_view_scores

_SCORE_KEYS = ("score", "scores", "prob", "logit", "consecutive_over_hi")


def _strip_scores(signal: dict[str, Any]) -> dict[str, Any]:
    signal = dict(signal)
    signal["score"] = None
    signal["detail"] = {
        k: v for k, v in (signal.get("detail") or {}).items() if not k.startswith(_SCORE_KEYS)
    }
    return signal


def case_view(case: Case, role: Role) -> dict[str, Any]:
    data = case.model_dump(mode="json")
    if not can_view_scores(role):
        data["signals"] = [_strip_scores(s) for s in data["signals"]]
    return data


def case_summary(case: Case) -> dict[str, Any]:
    d = case.decision
    return {
        "id": case.id,
        "title": case.title,
        "kind": case.kind.value,
        "status": case.status.value,
        "queue": case.queue.value,
        "band": d.band.value if d else None,
        "action_type": d.action_type.value if d else None,
        "amount_inr": case.txn.amount_inr if case.txn else None,
        "beneficiary_name": case.txn.beneficiary_name if case.txn else None,
        "reason_codes": [c.value for c in d.reason_codes] if d else [],
        "created_at": case.created_at.isoformat(),
    }
