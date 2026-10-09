"""D3: fine-tune XLM-R-base / MuRIL-base (and RoBERTa-base to replicate ICFD). TASK T19.

RUN ON KAGGLE (2x T4), not on the laptop. Needs the research-gpu extra.
Config is FROZEN before touching test (pre-registration): see CONFIG below.
Usage on Kaggle:
    python -m research.baselines.d3_finetune --model xlm-roberta-base --out /kaggle/working/d3
Outputs: scores_{split}.csv with columns conv_id,score (no text!).
"""

from __future__ import annotations

import argparse
from pathlib import Path

CONFIG = {
    "max_length": 512,
    "epochs": 2,
    "lr": 2e-5,
    "batch_size": 16,
    "warmup_ratio": 0.06,
    "weight_decay": 0.01,
    "seed": 13,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune D3 transformer baseline on Kaggle.")
    parser.add_argument("--model", type=str, default="xlm-roberta-base", help="Model name or path")
    parser.add_argument(
        "--data_dir",
        type=Path,
        default=Path("research/_data/icfd"),
        help="Path to ICFD directory",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("results/scores/d3"),
        help="Output directory for scores",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import torch  # type: ignore[import-not-found] # noqa: F401
        from transformers import (  # type: ignore[import-not-found] # noqa: F401
            AutoModelForSequenceClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
    except ImportError as e:
        print(f"Transformers/Torch not installed (run on Kaggle with GPU): {e}")
        return

    print(f"Starting D3 fine-tuning for model {args.model} with config {CONFIG}")


if __name__ == "__main__":
    main()
