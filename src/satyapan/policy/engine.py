"""The decision engine (C9). PRE-IMPLEMENTED (T02). THE ONLY COMPONENT THAT SETS THE BAND.

decide() is a PURE function: it reads a Case and returns a Decision. It never mutates the
case; apply_decision() does that. Property tests in tests/invariants/ prove:
  1. Monotone: removing signals never raises the band; adding signals never lowers it.
  2. No LLM/style-only path reaches HOLD.
  3. The floor depends only on trusted inputs (txn + master + config).
  4. band >= floor_band, always.
  5. OOB DENIED -> HOLD + SUSPECTED_FRAUD.
  6. Grey reasons -> at least VERIFY + checker queue.
"""

from __future__ import annotations

from datetime import datetime

from satyapan.contracts.case import Case, Decision
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import (
    FLOOR_REASON,
    ActionType,
    Band,
    CaseStatus,
    OOBResult,
    Queue,
    ReasonCode,
    SignalGroup,
)
from satyapan.contracts.evidence import Signal
from satyapan.contracts.signal_table import MONEY_ASK_CODES
from satyapan.master.store import MasterData
from satyapan.policy.bands import bmax, bmin, rank
from satyapan.policy.clearance import clearance_rules
from satyapan.policy.config import DEFAULT_CONFIG, PolicyConfig
from satyapan.policy.floor import compute_floor
from satyapan.policy.targets import counts_as_strong_group, is_capped, target_band


def has_money_movement(case: Case) -> bool:
    """A payment exists, or someone asked to move money (A1/A6/A7) in this case."""
    return case.txn is not None or any(s.code in MONEY_ASK_CODES for s in case.signals)


# ADR-021: trusted floor actions that already put money or data at risk. With one of these
# pending, a single ask is corroborated (the ask is about a real, risky action).
CORROBORATING_ACTIONS: frozenset[ActionType] = frozenset(
    {ActionType.N1, ActionType.N2, ActionType.C1, ActionType.K2, ActionType.T1, ActionType.D1}
)


def ask_corroborated(
    signals: list[Signal], floor_band: Band, money_movement: bool, action: ActionType | None
) -> bool:
    """True if an ask signal is backed by a second, independent indication:
    (a) two or more DISTINCT ask types, (b) a raising signal from another group that is not
    LLM/style (capped signals never corroborate), or (c) a risky action in the trusted floor.
    Monotone: adding signals can only turn this from False to True."""
    if len({s.code for s in signals if s.group == SignalGroup.ASK}) >= 2:
        return True
    if action in CORROBORATING_ACTIONS:
        return True
    return any(
        s.group != SignalGroup.ASK
        and not is_capped(s)
        and rank(target_band(s, floor_band, money_movement)) > rank(Band.PASS)
        for s in signals
    )


def escalate(
    signals: list[Signal],
    floor_band: Band,
    money_movement: bool,
    action: ActionType | None = None,
    require_ask_corroboration: bool = False,
) -> tuple[Band, list[ReasonCode], bool]:
    """Raise-only escalation lattice. Returns (band, raising_codes, multi_group_rule_fired).

    With require_ask_corroboration (policy >= 1.1, ADR-021), an uncorroborated ask signal is
    capped at VERIFY: one keyword hit alone never causes a HOLD (brief: "avoid automatic
    blocking ... based on a single weak signal")."""
    cap_asks = require_ask_corroboration and not ask_corroborated(
        signals, floor_band, money_movement, action
    )
    band = Band.PASS
    raising: list[ReasonCode] = []
    for s in signals:
        t = target_band(s, floor_band, money_movement)
        if cap_asks and s.group == SignalGroup.ASK:
            t = bmin(t, Band.VERIFY)
        if rank(t) > rank(Band.PASS) and s.code not in raising:
            raising.append(s.code)
        band = bmax(band, t)
    strong_groups = {s.group for s in signals if counts_as_strong_group(s)}
    multi = len(strong_groups) >= 2
    if multi:
        band = bmax(band, Band.HOLD)
    return band, raising, multi


def decide(
    case: Case,
    master: MasterData,
    cfg: PolicyConfig = DEFAULT_CONFIG,
    now: datetime | None = None,
) -> Decision:
    floor_band, action = compute_floor(case.kind, case.txn, case.master_change, master, cfg)
    reason_codes: list[ReasonCode] = [FLOOR_REASON[action]]

    esc_band, raising, multi = escalate(
        case.signals,
        floor_band,
        has_money_movement(case),
        action=action,
        require_ask_corroboration=cfg.ask_corroboration,
    )
    band = bmax(floor_band, esc_band)
    reason_codes += [c for c in raising if c not in reason_codes]
    if multi:
        reason_codes.append(ReasonCode.MULTI_GROUP_STRONG)

    info_codes = [s.code for s in case.signals if s.code not in reason_codes]
    info_codes = list(dict.fromkeys(info_codes))

    queue = Queue.MAKER
    grey = bool(case.grey_reasons)
    if grey:
        band = bmax(band, Band.VERIFY)
        queue = Queue.CHECKER_REVIEW
        reason_codes.append(ReasonCode.GREY_FLAG)

    suggested_status: CaseStatus | None = None
    if case.oob is not None and case.oob.result == OOBResult.DENIED:
        band = Band.HOLD
        suggested_status = CaseStatus.SUSPECTED_FRAUD
        reason_codes.append(ReasonCode.OOB_DENIED)
    elif case.oob is not None and case.oob.result == OOBResult.APPROVED:
        info_codes.append(ReasonCode.OOB_APPROVED)

    if band == Band.HOLD:
        queue = Queue.CHECKER_REVIEW

    return Decision(
        band=band,
        floor_band=floor_band,
        action_type=action,
        reason_codes=reason_codes,
        info_codes=info_codes,
        clearance=clearance_rules(band, action, case, master, cfg),
        queue=queue,
        suggested_status=suggested_status,
        grey=grey,
        policy_version=cfg.policy_version,
        decided_at=now or utcnow(),
    )


def decide_rules_only(
    case: Case, master: MasterData, cfg: PolicyConfig = DEFAULT_CONFIG
) -> Decision:
    """Same case with no detector signals, no grey flags and no OOB: the 'rules-only' baseline
    used in the decision-relevance table (docs/EVALUATION.md)."""
    bare = case.model_copy(update={"signals": [], "grey_reasons": [], "oob": None})
    return decide(bare, master, cfg)


_STATUS_LOCKED = {CaseStatus.CONFIRMED_FRAUD}


def apply_decision(case: Case, decision: Decision) -> Case:
    """Return a copy of the case with the decision applied. Never downgrades a fraud status."""
    update: dict[str, object] = {"decision": decision, "queue": decision.queue}
    if decision.suggested_status is not None and case.status not in _STATUS_LOCKED:
        update["status"] = decision.suggested_status
    return case.model_copy(update=update)
