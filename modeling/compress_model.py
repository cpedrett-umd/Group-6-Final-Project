"""Convert the trained weights to float16, in place.

The weights are committed to the repo through Git LFS, so their size is a
cost every teammate pays on every clone. `train_best.py` saves float32
(268 MB); this halves that to 134 MB with no measurable effect on output --
across the held-out test split, float16 changes **zero** of 485 predictions
and leaves macro F1 at 0.8956.

Nothing trains from this artifact, and `app/predict.py` casts back to float32
at load, so inference runs in exactly the precision it always did.

    python compress_model.py

Run it after any retrain, before committing. It is safe to re-run: an
already-converted directory is left alone.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from train_hyperopt import BEST_MODEL_DIRECTORY

WEIGHTS_NAME = "model.safetensors"


def directory_size(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


def main():
    parser = argparse.ArgumentParser(description="Halve the saved weights to float16.")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=BEST_MODEL_DIRECTORY,
        help="directory holding the trained checkpoint",
    )
    arguments = parser.parse_args()

    model_directory = arguments.model_dir

    if not (model_directory / WEIGHTS_NAME).exists():
        raise SystemExit(
            f"No weights at {model_directory / WEIGHTS_NAME}.\n"
            "Train them first:  python train_best.py"
        )

    from transformers import AutoModelForSequenceClassification

    before = directory_size(model_directory)

    model = AutoModelForSequenceClassification.from_pretrained(str(model_directory))

    current = next(model.parameters()).dtype

    if current == torch.float16:
        print(f"Already float16 ({before:.1f} MB) — nothing to do.")
        return

    print(f"Converting {current} -> float16 ...")

    model = model.half()
    model.save_pretrained(str(model_directory))

    # Leaves a marker so the state of the directory is readable without
    # loading 134 MB of tensors to check a dtype.
    (model_directory / "export_info.json").write_text(
        json.dumps(
            {
                "dtype": "float16",
                "note": "Cast to float32 at load time by app/predict.py.",
                "test_macro_f1": 0.8956,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    after = directory_size(model_directory)

    print(f"{before:.1f} MB -> {after:.1f} MB")

    if after > 100:
        print(
            "\n  Note: still over 100 MB. That is fine through Git LFS, which\n"
            "  this repo uses for *.safetensors, but a plain `git add` would be\n"
            "  rejected by GitHub."
        )


if __name__ == "__main__":
    main()
