"""Train the persuasion-tactic transformer.

Usage:
    python train.py --data "path/to/ads_dataset_labeled.csv"

Saves the best checkpoint (by validation macro-F1) to
checkpoints/ad_transformer.pt, bundled with the vocab and config so
predict.py needs nothing else.
"""
import argparse
import os

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from dataset import LABELS, AdsDataset, load_ads_csv
from model import AdTransformerClassifier
from tokenizer import Vocab

DEFAULT_DATA = (
    r"C:\Users\chris\Github Repos\Group-6-Final-Project"
    r"\datasets\text processing\ads_dataset_full.csv"
)


def split_indices(n: int, seed: int = 42) -> tuple[list[int], list[int], list[int]]:
    """80/10/10 train/val/test split."""
    g = torch.Generator().manual_seed(seed)
    perm = torch.randperm(n, generator=g).tolist()
    n_val = n_test = max(1, n // 10)
    n_train = n - n_val - n_test
    return perm[:n_train], perm[n_train : n_train + n_val], perm[n_train + n_val :]


@torch.no_grad()
def evaluate(model, loader, device, threshold: float = 0.5):
    """Per-class and macro/micro precision, recall, F1."""
    model.eval()
    preds, targets = [], []
    for ids, y in loader:
        logits = model(ids.to(device))
        preds.append(torch.sigmoid(logits).cpu() >= threshold)
        targets.append(y.bool())
    preds, targets = torch.cat(preds), torch.cat(targets)

    tp = (preds & targets).sum(0).float()
    fp = (preds & ~targets).sum(0).float()
    fn = (~preds & targets).sum(0).float()
    eps = 1e-9
    precision = tp / (tp + fp + eps)
    recall = tp / (tp + fn + eps)
    f1 = 2 * precision * recall / (precision + recall + eps)
    micro_f1 = (2 * tp.sum() / (2 * tp.sum() + fp.sum() + fn.sum() + eps)).item()
    return {
        "per_class": {
            LABELS[i]: (precision[i].item(), recall[i].item(), f1[i].item())
            for i in range(len(LABELS))
        },
        "macro_f1": f1.mean().item(),
        "micro_f1": micro_f1,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--max-len", type=int, default=128)
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--n-heads", type=int, default=4)
    parser.add_argument("--n-layers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=4, help="early-stop patience")
    parser.add_argument("--out", default="checkpoints/ad_transformer.pt")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    texts, labels = load_ads_csv(args.data)
    if not texts:
        raise SystemExit(
            "No labeled rows found. The dataset must be annotated with tactic "
            "labels (see labeling_guidelines.md) before training."
        )
    print(f"{len(texts)} labeled ads on {device}")

    train_idx, val_idx, test_idx = split_indices(len(texts))
    pick = lambda idx: ([texts[i] for i in idx], [labels[i] for i in idx])
    train_texts, train_labels = pick(train_idx)

    # Vocab from training split only, so val/test measure real generalization.
    vocab = Vocab.build(train_texts)
    print(f"vocab size: {len(vocab)}")

    make_ds = lambda t, l: AdsDataset(t, l, vocab, args.max_len)
    train_ds = make_ds(train_texts, train_labels)
    val_loader = DataLoader(make_ds(*pick(val_idx)), batch_size=args.batch_size)
    test_loader = DataLoader(make_ds(*pick(test_idx)), batch_size=args.batch_size)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)

    config = dict(
        vocab_size=len(vocab),
        n_classes=len(LABELS),
        d_model=args.d_model,
        n_heads=args.n_heads,
        n_layers=args.n_layers,
        d_ff=4 * args.d_model,
        max_len=args.max_len,
    )
    model = AdTransformerClassifier(**config).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"parameters: {n_params:,}")

    # Up-weight rare tactics so the model doesn't collapse to frequent ones.
    pos = train_ds.targets.sum(0)
    pos_weight = ((len(train_ds) - pos) / pos.clamp(min=1)).clamp(max=20.0).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_f1, stale = -1.0, 0
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    for epoch in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        for ids, y in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(ids.to(device)), y.to(device))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += loss.item() * ids.size(0)
        scheduler.step()

        metrics = evaluate(model, val_loader, device)
        print(
            f"epoch {epoch:2d}  loss {total / len(train_ds):.4f}  "
            f"val macro-F1 {metrics['macro_f1']:.3f}  micro-F1 {metrics['micro_f1']:.3f}"
        )
        if metrics["macro_f1"] > best_f1:
            best_f1, stale = metrics["macro_f1"], 0
            torch.save(
                {"state_dict": model.state_dict(), "config": config,
                 "labels": LABELS, "vocab": vocab.itos},
                args.out,
            )
        else:
            stale += 1
            if stale >= args.patience:
                print("early stop")
                break

    # Final report on the held-out test split using the best checkpoint.
    model.load_state_dict(torch.load(args.out, weights_only=True)["state_dict"])
    metrics = evaluate(model, test_loader, device)
    print(f"\ntest macro-F1 {metrics['macro_f1']:.3f}  micro-F1 {metrics['micro_f1']:.3f}")
    print(f"{'label':<20}{'P':>7}{'R':>7}{'F1':>7}")
    for label, (p, r, f) in metrics["per_class"].items():
        print(f"{label:<20}{p:>7.3f}{r:>7.3f}{f:>7.3f}")
    print(f"\nsaved best checkpoint to {args.out}")


if __name__ == "__main__":
    main()
