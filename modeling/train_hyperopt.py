import gc
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from hyperopt import STATUS_OK, Trials, fmin, hp, space_eval, tpe
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, Dataset, Subset
from transformers import AutoModelForSequenceClassification


# File and model settings

DATA_FILE = "../datasets/text_processing/tokenized_ads.pt"
MODEL_NAME = "distilbert-base-uncased"

RANDOM_SEED = 42
MAX_EVALS = 3

OUTPUT_DIRECTORY = Path("hyperopt_results")
RESULTS_FILE = OUTPUT_DIRECTORY / "hyperopt_trials.csv"
BEST_PARAMETERS_FILE = OUTPUT_DIRECTORY / "best_parameters.txt"
BEST_MODEL_DIRECTORY = OUTPUT_DIRECTORY / "best_distilbert_model"


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class TokenizedAdsDataset(Dataset):
    def __init__(self, input_ids, attention_mask, labels):
        self.input_ids = input_ids
        self.attention_mask = attention_mask
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        return {
            "input_ids": self.input_ids[index],
            "attention_mask": self.attention_mask[index],
            "labels": self.labels[index],
        }


def compute_class_weights(label_ids, num_classes):
    counts = torch.bincount(
        label_ids,
        minlength=num_classes,
    ).float()

    total = counts.sum()

    weights = total / (num_classes * counts)

    return weights


def evaluate(model, dataloader, device, id_to_label):
    model.eval()

    all_predictions = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

            predictions = torch.argmax(
                outputs.logits,
                dim=1,
            )

            all_predictions.extend(
                predictions.cpu().tolist()
            )

            all_labels.extend(
                labels.cpu().tolist()
            )

    accuracy = accuracy_score(
        all_labels,
        all_predictions,
    )

    macro_f1 = f1_score(
        all_labels,
        all_predictions,
        average="macro",
        zero_division=0,
    )

    weighted_f1 = f1_score(
        all_labels,
        all_predictions,
        average="weighted",
        zero_division=0,
    )

    target_names = [
        id_to_label[index]
        for index in range(len(id_to_label))
    ]

    report = classification_report(
        all_labels,
        all_predictions,
        target_names=target_names,
        zero_division=0,
    )

    return accuracy, macro_f1, weighted_f1, report


def load_data():
    bundle = torch.load(
        DATA_FILE,
        map_location="cpu",
        weights_only=False,
    )

    input_ids = bundle["input_ids"]
    attention_mask = bundle["attention_mask"]
    raw_labels = bundle["labels"]

    label_names = sorted(set(raw_labels))

    label_to_id = {
        label: index
        for index, label in enumerate(label_names)
    }

    id_to_label = {
        index: label
        for label, index in label_to_id.items()
    }

    label_ids = torch.tensor(
        [label_to_id[label] for label in raw_labels],
        dtype=torch.long,
    )

    dataset = TokenizedAdsDataset(
        input_ids=input_ids,
        attention_mask=attention_mask,
        labels=label_ids,
    )

    all_indices = np.arange(len(dataset))

    train_indices, temp_indices = train_test_split(
        all_indices,
        test_size=0.30,
        random_state=RANDOM_SEED,
        stratify=label_ids.numpy(),
    )

    val_indices, test_indices = train_test_split(
        temp_indices,
        test_size=0.50,
        random_state=RANDOM_SEED,
        stratify=label_ids.numpy()[temp_indices],
    )

    return {
        "dataset": dataset,
        "label_ids": label_ids,
        "label_names": label_names,
        "label_to_id": label_to_id,
        "id_to_label": id_to_label,
        "train_indices": train_indices,
        "val_indices": val_indices,
        "test_indices": test_indices,
    }


def train_configuration(
    parameters,
    data,
    device,
    save_model=False,
):
    set_seed(RANDOM_SEED)

    batch_size = int(parameters["batch_size"])
    epochs = int(parameters["epochs"])
    learning_rate = float(parameters["learning_rate"])
    weight_decay = float(parameters["weight_decay"])

    train_dataset = Subset(
        data["dataset"],
        data["train_indices"],
    )

    val_dataset = Subset(
        data["dataset"],
        data["val_indices"],
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
    )

    num_classes = len(data["label_names"])

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=num_classes,
        id2label=data["id_to_label"],
        label2id=data["label_to_id"],
    )

    model.to(device)

    train_labels = data["label_ids"][data["train_indices"]]

    class_weights = compute_class_weights(
        train_labels,
        num_classes,
    ).to(device)

    loss_function = nn.CrossEntropyLoss(
        weight=class_weights,
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
    )

    best_validation_macro_f1 = -1.0
    best_validation_accuracy = -1.0
    best_validation_weighted_f1 = -1.0
    best_state_dict = None

    for epoch in range(epochs):
        model.train()
        running_loss = 0.0

        for batch in train_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

            loss = loss_function(
                outputs.logits,
                labels,
            )

            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        average_loss = running_loss / len(train_loader)

        accuracy, macro_f1, weighted_f1, _ = evaluate(
            model,
            val_loader,
            device,
            data["id_to_label"],
        )

        print(
            f"Epoch {epoch + 1}/{epochs} | "
            f"Loss: {average_loss:.4f} | "
            f"Validation accuracy: {accuracy:.4f} | "
            f"Validation macro F1: {macro_f1:.4f}"
        )

        if macro_f1 > best_validation_macro_f1:
            best_validation_macro_f1 = macro_f1
            best_validation_accuracy = accuracy
            best_validation_weighted_f1 = weighted_f1

            best_state_dict = {
                name: parameter.detach().cpu().clone()
                for name, parameter in model.state_dict().items()
            }

    if save_model and best_state_dict is not None:
        model.load_state_dict(best_state_dict)

        BEST_MODEL_DIRECTORY.mkdir(
            parents=True,
            exist_ok=True,
        )

        model.save_pretrained(
            BEST_MODEL_DIRECTORY
        )

        torch.save(
            {
                "label_to_id": data["label_to_id"],
                "id_to_label": data["id_to_label"],
                "best_validation_macro_f1": best_validation_macro_f1,
                "parameters": parameters,
            },
            BEST_MODEL_DIRECTORY / "metadata.pt",
        )

    del optimizer
    del loss_function
    del model

    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {
        "validation_accuracy": best_validation_accuracy,
        "validation_macro_f1": best_validation_macro_f1,
        "validation_weighted_f1": best_validation_weighted_f1,
    }


def save_trial_results(trials):
    trial_rows = []

    for trial_number, trial in enumerate(trials.trials, start=1):
        result = trial["result"]

        trial_rows.append(
            {
                "trial": trial_number,
                "learning_rate": result["learning_rate"],
                "batch_size": result["batch_size"],
                "epochs": result["epochs"],
                "weight_decay": result["weight_decay"],
                "validation_accuracy": result[
                    "validation_accuracy"
                ],
                "validation_macro_f1": result[
                    "validation_macro_f1"
                ],
                "validation_weighted_f1": result[
                    "validation_weighted_f1"
                ],
            }
        )

    results_df = pd.DataFrame(trial_rows)

    results_df = results_df.sort_values(
        by="validation_macro_f1",
        ascending=False,
    )

    results_df.to_csv(
        RESULTS_FILE,
        index=False,
    )

    return results_df


def evaluate_best_model(best_parameters, data, device):
    print("\nRetraining best configuration before test evaluation")

    train_configuration(
        parameters=best_parameters,
        data=data,
        device=device,
        save_model=True,
    )

    best_model = (
        AutoModelForSequenceClassification
        .from_pretrained(BEST_MODEL_DIRECTORY)
    )

    best_model.to(device)

    test_dataset = Subset(
        data["dataset"],
        data["test_indices"],
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=int(best_parameters["batch_size"]),
        shuffle=False,
    )

    accuracy, macro_f1, weighted_f1, report = evaluate(
        best_model,
        test_loader,
        device,
        data["id_to_label"],
    )

    print("\nFinal test results")
    print(f"Test accuracy: {accuracy:.4f}")
    print(f"Test macro F1: {macro_f1:.4f}")
    print(f"Test weighted F1: {weighted_f1:.4f}")
    print("\nTest classification report:")
    print(report)

    return accuracy, macro_f1, weighted_f1, report


def main():
    set_seed(RANDOM_SEED)

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print(f"Using device: {device}")

    data = load_data()

    print(f"Examples: {len(data['dataset'])}")
    print(f"Classes: {len(data['label_names'])}")
    print(
        f"Train: {len(data['train_indices'])}, "
        f"Validation: {len(data['val_indices'])}, "
        f"Test: {len(data['test_indices'])}"
    )

    search_space = {
        "learning_rate": hp.choice(
            "learning_rate",
            [1e-5, 2e-5, 3e-5, 5e-5],
        ),
        "batch_size": hp.choice(
            "batch_size",
            [8, 16],
        ),
        "epochs": hp.choice(
            "epochs",
            [2, 3, 4],
        ),
        "weight_decay": hp.choice(
            "weight_decay",
            [0.0, 0.01, 0.05],
        ),
    }

    trials = Trials()

    trial_counter = {"value": 0}

    def objective(parameters):
        trial_counter["value"] += 1

        print("\n" + "=" * 70)
        print(
            f"Starting trial "
            f"{trial_counter['value']}/{MAX_EVALS}"
        )
        print(parameters)
        print("=" * 70)

        metrics = train_configuration(
            parameters=parameters,
            data=data,
            device=device,
            save_model=False,
        )

        return {
            "loss": -metrics["validation_macro_f1"],
            "status": STATUS_OK,
            "validation_accuracy": metrics[
                "validation_accuracy"
            ],
            "validation_macro_f1": metrics[
                "validation_macro_f1"
            ],
            "validation_weighted_f1": metrics[
                "validation_weighted_f1"
            ],
            "learning_rate": float(
                parameters["learning_rate"]
            ),
            "batch_size": int(
                parameters["batch_size"]
            ),
            "epochs": int(
                parameters["epochs"]
            ),
            "weight_decay": float(
                parameters["weight_decay"]
            ),
        }

    best_indices = fmin(
        fn=objective,
        space=search_space,
        algo=tpe.suggest,
        max_evals=MAX_EVALS,
        trials=trials,
        rstate=np.random.default_rng(RANDOM_SEED),
    )

    best_parameters = space_eval(
        search_space,
        best_indices,
    )

    results_df = save_trial_results(trials)

    print("\nAll tuning results")
    print(results_df.to_string(index=False))

    print("\nBest parameters")
    print(best_parameters)

    with open(
        BEST_PARAMETERS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        for parameter, value in best_parameters.items():
            file.write(f"{parameter}: {value}\n")

    evaluate_best_model(
        best_parameters=best_parameters,
        data=data,
        device=device,
    )

    print("\nSaved:")
    print(f"- Trial results: {RESULTS_FILE}")
    print(f"- Best parameters: {BEST_PARAMETERS_FILE}")
    print(f"- Best model: {BEST_MODEL_DIRECTORY}")


if __name__ == "__main__":
    main()
