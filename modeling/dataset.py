"""Dataset loading for the Group 6 persuasion-tactic classifier.

Label space follows labeling_guidelines.md in the group repo. Ads may
carry multiple tactic labels, so targets are multi-hot vectors.
"""
import warnings

import pandas as pd
import torch
from torch.utils.data import Dataset

from tokenizer import Vocab

# Canonical order — index i of the model output corresponds to LABELS[i].
LABELS = [
    "urgency",
    "scarcity",
    "fomo",
    "fear_appeal",
    "social_proof",
    "authority",
    "exaggerated_claim",
    "neutral",
]

# Tolerate spelling variations annotators are likely to use.
_ALIASES = {
    "fear": "fear_appeal",
    "fear_appeals": "fear_appeal",
    "exaggerated_claims": "exaggerated_claim",
    "exaggeration": "exaggerated_claim",
    "authority_manipulation": "authority",
    "none": "neutral",
}


def _normalize_label(raw: str) -> str:
    label = raw.strip().lower().replace(" ", "_").replace("-", "_")
    return _ALIASES.get(label, label)


def parse_labels(cell: str) -> list[str]:
    """Parse a label cell like 'urgency|scarcity' or 'Fear Appeal, FOMO'."""
    labels = []
    for part in str(cell).replace(";", "|").replace(",", "|").split("|"):
        label = _normalize_label(part)
        if not label:
            continue
        if label not in LABELS:
            raise ValueError(f"Unknown label {label!r}; expected one of {LABELS}")
        labels.append(label)
    return labels


def load_ads_csv(path: str) -> tuple[list[str], list[list[str]]]:
    """Load (texts, label lists) from a CSV with ad_text,label columns.

    Rows still carrying the placeholder label 'advertisement' from the
    dataset builder are skipped with a warning — they haven't been
    annotated yet.
    """
    df = pd.read_csv(path)
    unlabeled = df["label"].str.strip().str.lower() == "advertisement"
    if unlabeled.any():
        warnings.warn(
            f"{unlabeled.sum()} of {len(df)} rows still have the placeholder "
            "label 'advertisement' and were skipped. Annotate them per "
            "labeling_guidelines.md to use them for training."
        )
        df = df[~unlabeled]
    texts = df["ad_text"].astype(str).tolist()
    labels = [parse_labels(cell) for cell in df["label"]]
    return texts, labels


class AdsDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[list[str]], vocab: Vocab, max_len: int):
        self.vocab = vocab
        self.max_len = max_len
        self.texts = texts
        self.targets = torch.zeros(len(texts), len(LABELS))
        for i, row in enumerate(labels):
            for label in row:
                self.targets[i, LABELS.index(label)] = 1.0

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, torch.Tensor]:
        ids = torch.tensor(self.vocab.encode(self.texts[i], self.max_len))
        return ids, self.targets[i]
