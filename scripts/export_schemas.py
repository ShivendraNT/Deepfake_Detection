"""Export JSON Schemas for every contract model to schemas/. Run: `make schemas`.

The console (TypeScript) and the extension (JS) are built against these files.
tests/contracts/test_schemas_up_to_date.py fails if you change a contract and forget this.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pydantic import BaseModel  # noqa: E402

from satyapan import contracts  # noqa: E402
from satyapan.contracts.live import LIVE_EVENT_ADAPTER  # noqa: E402

MODELS = [
    "Case",
    "Decision",
    "PaymentAction",
    "Signal",
    "Evidence",
    "DetectorOutput",
    "AskSpan",
    "Vendor",
    "Employee",
    "OOBRequest",
    "CallbackRecord",
    "ReportPack",
    "CustodyRow",
    "ParsedEmail",
    "InvoiceFields",
    "PdfMeta",
    "Explanation",
    "EvidenceItemForLLM",
    "CitizenResult",
    "CitizenFileResult",
    "CitizenReportDraft",
    "VoiceWindowResult",
    "SealSession",
    "SealMeetingView",
    "SealVerification",
    "PaymentIntent",
]


def build() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in MODELS:
        model: type[BaseModel] = getattr(contracts, name)
        out[f"{name}.schema.json"] = (
            json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n"
        )
    out["LiveEvent.schema.json"] = json.dumps(LIVE_EVENT_ADAPTER.json_schema(), indent=2) + "\n"
    out["signal_table.json"] = (
        json.dumps(
            {
                code.value: {
                    "group": spec.group.value,
                    "target": spec.target.value,
                    "strength": spec.strength.value,
                    "allowed_sources": sorted(s.value for s in spec.allowed_sources),
                }
                for code, spec in contracts.SIGNAL_TABLE.items()
            },
            indent=2,
        )
        + "\n"
    )
    return out


def main() -> None:
    target = ROOT / "schemas"
    target.mkdir(exist_ok=True)
    for name, text in build().items():
        (target / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(MODELS) + 2} schema files to schemas/")


if __name__ == "__main__":
    main()
