"""Train the single best configuration found by hyperopt and save the weights.

`train_hyperopt.py` searches the space and then retrains the winner, but
re-running it costs every trial again just to recover one set of weights. This
script skips the search: it reads the tuned parameters back out of
`hyperopt_results/best_parameters.txt` and trains only that configuration.

Everything else is imported from `train_hyperopt` rather than reimplemented —
the data split (seed 42, stratified 70/15/15), the class weighting, and the
label encoding are therefore identical to the ones the tuning run scored, so
the weights this produces match the reported trial.

Run from the `modeling/` directory (paths in train_hyperopt are relative):
    python train_best.py
"""
from __future__ import annotations

import torch

from train_hyperopt import (
    BEST_MODEL_DIRECTORY,
    BEST_PARAMETERS_FILE,
    evaluate_best_model,
    load_data,
    set_seed,
    RANDOM_SEED,
)

# best_parameters.txt is written as "name: value" lines by train_hyperopt.main().
# Each parameter is cast back to the type train_configuration() expects.
PARAMETER_TYPES = {
    "batch_size": int,
    "epochs": int,
    "learning_rate": float,
    "weight_decay": float,
}


def read_best_parameters(path=BEST_PARAMETERS_FILE):
    """Parse the tuned parameters back out of the file hyperopt wrote."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — run train_hyperopt.py first to produce it."
        )

    parameters = {}

    with open(path, encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            name, _, value = line.partition(":")
            name = name.strip()

            if name not in PARAMETER_TYPES:
                continue

            parameters[name] = PARAMETER_TYPES[name](value.strip())

    missing = set(PARAMETER_TYPES) - set(parameters)

    if missing:
        raise ValueError(
            f"{path} is missing parameter(s): {sorted(missing)}"
        )

    return parameters


def main():
    set_seed(RANDOM_SEED)

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print(f"Using device: {device}")

    best_parameters = read_best_parameters()

    print("\nTuned parameters (from hyperopt)")
    for name, value in best_parameters.items():
        print(f"  {name}: {value}")

    data = load_data()

    print(f"\nExamples: {len(data['dataset'])}")
    print(f"Classes: {len(data['label_names'])}")
    print(
        f"Train: {len(data['train_indices'])}, "
        f"Validation: {len(data['val_indices'])}, "
        f"Test: {len(data['test_indices'])}"
    )

    # Trains with save_model=True, then reloads the saved weights and scores
    # them on the held-out test split.
    evaluate_best_model(
        best_parameters=best_parameters,
        data=data,
        device=device,
    )

    print(f"\nSaved best model -> {BEST_MODEL_DIRECTORY}")


if __name__ == "__main__":
    main()
