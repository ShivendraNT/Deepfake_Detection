"""In-memory case store, seeded from data/demo/cases/*.json. PRE-IMPLEMENTED (T01).

Good enough for the hackathon demo (single process). Every load re-runs the policy engine,
so fixture decisions can never drift from the real engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from satyapan.contracts.case import Case
from satyapan.master.store import MasterData
from satyapan.policy.config import DEFAULT_CONFIG, PolicyConfig
from satyapan.policy.engine import apply_decision, decide


def load_fixture_cases(cases_dir: Path) -> list[Case]:
    return [
        Case.model_validate(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted(cases_dir.glob("*.json"))
    ]


@dataclass
class CaseRepository:
    master: MasterData
    cfg: PolicyConfig = DEFAULT_CONFIG
    cases: dict[str, Case] = field(default_factory=dict)

    def put(self, case: Case, *, redecide: bool = True) -> Case:
        if redecide:
            case = apply_decision(case, decide(case, self.master, self.cfg))
        self.cases[case.id] = case
        return case

    def get(self, case_id: str) -> Case | None:
        return self.cases.get(case_id)

    def all_cases(self) -> list[Case]:
        return sorted(self.cases.values(), key=lambda c: c.id)

    @classmethod
    def from_fixtures(cls, master: MasterData, cases_dir: Path) -> CaseRepository:
        repo = cls(master=master)
        for c in load_fixture_cases(cases_dir):
            repo.put(c)
        return repo
