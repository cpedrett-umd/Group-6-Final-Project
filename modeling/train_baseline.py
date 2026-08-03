import random
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader, Subset
from transformers import AutoModelForSequenceClassification
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score

# Tokenized data 
DATA_FILE = "../datasets/text_processing/tokenized_ads.pt"
# Pretrained BERT model baseline
MODEL_NAME = "distilbert-base-uncased"
# Training settings
BATCH_SIZE = 16
LEARNING_RATE = 2e-5
EPOCHS = 3
RANDOM_SEED = 42

def set_seed(seed):
    # Sets seed
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class TokenizedAdsDataset(Dataset):
    # Wraps the tokenized data for PyTorch batches
    def __init__(self, input_ids, attention_mask, labels):
        self.input_ids = input_ids
        self.attention_mask = attention_mask
        self.labels = labels

    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, index):
        # Returns one ad and associated label
        return {
            "input_ids": self.input_ids[index],
            "attention_mask": self.attention_mask[index],
            "labels": self.labels[index],
        }

def compute_class_weights(label_ids, num_classes):
    counts = torch.bincount(
        label_ids,
        minlength=num_classes
    ).float()
    total = counts.sum()

    # Assign the lower rarer classes higher weight accordingly
    weights = total / (num_classes * counts)
    return weights


def evaluate(model, dataloader, device, id_to_label):
    # Evaluation display
    model.eval()
    all_predictions = []
    all_labels = []

    # Discard gradients
    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )
            # Pick class with highest score for our final prediction
            predictions = torch.argmax(
                outputs.logits,
                dim=1
            )
            all_predictions.extend(
                predictions.cpu().tolist()
            )
            all_labels.extend(
                labels.cpu().tolist()
            )

    # Macro F1 as main metric
    accuracy = accuracy_score(
        all_labels,
        all_predictions
    )
    macro_f1 = f1_score(
        all_labels,
        all_predictions,
        average="macro",
        zero_division=0
    )
    weighted_f1 = f1_score(
        all_labels,
        all_predictions,
        average="weighted",
        zero_division=0
    )

    # Change displayed number ids to class names for clarity sake
    target_names = [
        id_to_label[index]
        for index in range(len(id_to_label))
    ]
    report = classification_report(
        all_labels,
        all_predictions,
        target_names=target_names,
        zero_division=0
    )
    return accuracy, macro_f1, weighted_f1, report


def main():
    set_seed(RANDOM_SEED)
    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    # Load saved token IDs, masks and labels
    bundle = torch.load(
        DATA_FILE,
        map_location="cpu",
        weights_only=False
    )

    input_ids = bundle["input_ids"]
    attention_mask = bundle["attention_mask"]
    raw_labels = bundle["labels"]

    # Index labels
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
        dtype=torch.long
    )
    num_classes = len(label_names)

    print(f"Examples: {len(label_ids)}")
    print(f"Classes: {num_classes}")
    print("Label mapping:")

    for label, label_id in label_to_id.items():
        print(f"  {label_id}: {label}")

    dataset = TokenizedAdsDataset(
        input_ids=input_ids,
        attention_mask=attention_mask,
        labels=label_ids
    )
    all_indices = np.arange(len(dataset))

    # 70/30 split
    train_indices, temp_indices = train_test_split(
        all_indices,
        test_size=0.30,
        random_state=RANDOM_SEED,
        stratify=label_ids.numpy()
    )

    # 30 split into validation and test
    val_indices, test_indices = train_test_split(
        temp_indices,
        test_size=0.50,
        random_state=RANDOM_SEED,
        stratify=label_ids.numpy()[temp_indices]
    )

    train_dataset = Subset(
        dataset,
        train_indices
    )
    val_dataset = Subset(
        dataset,
        val_indices
    )
    test_dataset = Subset(
        dataset,
        test_indices
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True # Shuffle training only
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False
    )

    print(
        f"Train: {len(train_dataset)}, "
        f"Validation: {len(val_dataset)}, "
        f"Test: {len(test_dataset)}"
    )

    # Add classifier for ther seven labels
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=num_classes,
        id2label=id_to_label,
        label2id=label_to_id
    )
    model.to(device)

    train_labels = label_ids[train_indices]
    class_weights = compute_class_weights(
        train_labels,
        num_classes
    ).to(device)
    print("Class weights:")

    for index, weight in enumerate(class_weights):
        print(
            f"  {id_to_label[index]}: "
            f"{weight.item():.4f}"
        )

    # Weighted loss
    loss_function = nn.CrossEntropyLoss(
        weight=class_weights
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE
    )

    # Save epoch with best validation Macro F1
    best_macro_f1 = -1.0
    for epoch in range(EPOCHS):
        model.train()
        running_loss = 0.0

        for batch in train_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            optimizer.zero_grad()

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )
            loss = loss_function(
                outputs.logits,
                labels
            )
            # Update step
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        average_loss = running_loss / len(train_loader)
        accuracy, macro_f1, weighted_f1, report = evaluate(
            model,
            val_loader,
            device,
            id_to_label
        )

        print(f"\nEpoch {epoch + 1}/{EPOCHS}")
        print(f"Training loss: {average_loss:.4f}")
        print(f"Validation accuracy: {accuracy:.4f}")
        print(f"Validation macro F1: {macro_f1:.4f}")
        print(f"Validation weighted F1: {weighted_f1:.4f}")
        print(report)

        # Save best Macro_f1
        if macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1

            model.save_pretrained(
                "baseline_distilbert_model"
            )
            # Save label mappings
            torch.save(
                {
                    "label_to_id": label_to_id,
                    "id_to_label": id_to_label,
                    "best_validation_macro_f1": best_macro_f1,
                },
                "baseline_distilbert_model/metadata.pt"
            )
            print("Saved new best model.")
    print("\nEvaluating best model on the test split")

    # Reload the best checkpoint
    best_model = (
        AutoModelForSequenceClassification
        .from_pretrained("baseline_distilbert_model")
    )
    best_model.to(device)

    accuracy, macro_f1, weighted_f1, report = evaluate(
        best_model,
        test_loader,
        device,
        id_to_label
    )

    print(f"Test accuracy: {accuracy:.4f}")
    print(f"Test macro F1: {macro_f1:.4f}")
    print(f"Test weighted F1: {weighted_f1:.4f}")
    print("\nTest classification report:")
    print(report)


if __name__ == "__main__":
    main()