"""Classify ad text with a trained checkpoint.

Usage:
    python predict.py "Act now! Only 3 left - doctors recommend it."
    python predict.py --checkpoint checkpoints/ad_transformer.pt "..."
"""
import argparse

import torch

from model import AdTransformerClassifier
from tokenizer import Vocab

THRESHOLD = 0.5


def load(checkpoint_path: str):
    ckpt = torch.load(checkpoint_path, weights_only=True)
    model = AdTransformerClassifier(**ckpt["config"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model, Vocab(ckpt["vocab"]), ckpt["labels"], ckpt["config"]["max_len"]


@torch.no_grad()
def classify(text: str, model, vocab, labels, max_len):
    ids = torch.tensor([vocab.encode(text, max_len)])
    probs = torch.sigmoid(model(ids))[0]
    tactics = [
        (labels[i], probs[i].item())
        for i in range(len(labels))
        if probs[i] >= THRESHOLD and labels[i] != "neutral"
    ]
    # If no tactic clears the threshold, the ad reads as neutral.
    return tactics or [("neutral", probs[labels.index("neutral")].item())], probs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="ad text to classify")
    parser.add_argument("--checkpoint", default="checkpoints/ad_transformer.pt")
    args = parser.parse_args()

    model, vocab, labels, max_len = load(args.checkpoint)
    tactics, probs = classify(args.text, model, vocab, labels, max_len)

    print("detected tactics:", ", ".join(f"{name} ({p:.2f})" for name, p in tactics))
    print("\nall class probabilities:")
    for i in sorted(range(len(labels)), key=lambda i: -probs[i]):
        print(f"  {labels[i]:<20}{probs[i]:.3f}")


if __name__ == "__main__":
    main()
