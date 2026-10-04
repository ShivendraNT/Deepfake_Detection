"""D3: fine-tune XLM-R-base / MuRIL-base (and RoBERTa-base to replicate ICFD). TASK T19.

RUN ON KAGGLE (2x T4), not on the laptop. Needs the research-gpu extra.
Config is FROZEN before touching test (pre-registration): see CONFIG below.
Usage on Kaggle:
    python -m research.baselines.d3_finetune --model xlm-roberta-base --out /kaggle/working/d3
Outputs: scores_{split}.csv with columns conv_id,score (no text!).
"""

from __future__ import annotations

CONFIG = {
    "max_length": 512,
    "epochs": 2,
    "lr": 2e-5,
    "batch_size": 16,
    "warmup_ratio": 0.06,
    "weight_decay": 0.01,
    "seed": 13,
}


def main() -> None:
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")


if __name__ == "__main__":
    main()
