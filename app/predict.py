"""Inference wrapper around the hyperopt-tuned DistilBERT classifier.

Loads the weights written by `modeling/train_best.py` (the winning trial:
lr 5e-5, batch 16, 3 epochs, weight decay 0.0) and turns raw ad text into a
label plus a confidence over all 7 tactic classes.

Two details keep this faithful to training:

* The tokenizer comes from `datasets/text_processing/ads_tokenizer/` -- the
  exact vocab that produced `tokenized_ads.pt` -- and uses the same
  `max_len=128`. A different tokenizer would silently yield garbage ids.
* The label names come from the checkpoint's own `id2label`, written by
  `AutoModelForSequenceClassification` at save time. Nothing here hardcodes
  class order, so re-training on a changed dataset cannot desynchronise the UI.
"""
from __future__ import annotations

import threading
from pathlib import Path

import torch
import torch.nn.functional as F

REPO_ROOT = Path(__file__).resolve().parent.parent

MODEL_DIRECTORY = REPO_ROOT / "modeling" / "hyperopt_results" / "best_distilbert_model"
TOKENIZER_DIRECTORY = REPO_ROOT / "datasets" / "text_processing" / "ads_tokenizer"

# Must match hf_tokenizer.DEFAULT_MAX_LEN, which built the training tensors.
MAX_LEN = 128

_lock = threading.Lock()
_state = {}


class ModelNotTrainedError(RuntimeError):
    """Raised when the tuned weights are missing from disk."""


def _load():
    """Load model + tokenizer once, on first use."""
    if _state:
        return _state

    with _lock:
        # Re-check inside the lock: another thread may have won the race.
        if _state:
            return _state

        if not MODEL_DIRECTORY.exists():
            raise ModelNotTrainedError(
                f"No model at {MODEL_DIRECTORY}.\n"
                "The weights are committed via Git LFS — if this clone skipped "
                "them, run:\n"
                "    git lfs install && git lfs pull\n"
                "Or rebuild them:\n"
                "    cd modeling && python train_best.py"
            )

        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tokenizer_source = (
            TOKENIZER_DIRECTORY if TOKENIZER_DIRECTORY.exists() else MODEL_DIRECTORY
        )

        tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_source))

        model = AutoModelForSequenceClassification.from_pretrained(
            str(MODEL_DIRECTORY)
        )

        # The released weights are float16 to halve the download; a locally
        # trained checkpoint is float32. Cast either one up, because several
        # ops CPU inference relies on have no float16 kernel -- a half-precision
        # model would either crash or run far slower here.
        model = model.float()

        model.eval()

        # id2label round-trips through JSON, so keys arrive as strings.
        id_to_label = {
            int(index): label
            for index, label in model.config.id2label.items()
        }

        _state.update(
            {
                "model": model,
                "tokenizer": tokenizer,
                "id_to_label": id_to_label,
            }
        )

    return _state


def is_ready() -> bool:
    """True when the tuned weights exist on disk (does not load them)."""
    return MODEL_DIRECTORY.exists()


def warm_up() -> None:
    """Load the model ahead of the first request, so the demo's first click is fast."""
    _load()


def predict(text: str) -> dict:
    """Classify one ad.

    Returns the argmax label, its softmax confidence, and the full distribution
    sorted high to low. The distribution is what lets the panel rank secondary
    tactics rather than showing a bare top-1.
    """
    if not text or not text.strip():
        raise ValueError("No text to analyse.")

    state = _load()

    tokenizer = state["tokenizer"]
    model = state["model"]
    id_to_label = state["id_to_label"]

    encoded = tokenizer(
        [text],
        padding="max_length",
        truncation=True,
        max_length=MAX_LEN,
        return_tensors="pt",
    )

    with torch.no_grad():
        outputs = model(
            input_ids=encoded["input_ids"],
            attention_mask=encoded["attention_mask"],
        )

    probabilities = F.softmax(outputs.logits, dim=1)[0]

    distribution = [
        {
            "label": id_to_label[index],
            "confidence": round(float(probability), 4),
        }
        for index, probability in enumerate(probabilities.tolist())
    ]

    distribution.sort(key=lambda entry: -entry["confidence"])

    # Truncation is worth surfacing: an ad longer than 128 subwords was only
    # partly seen by the model.
    token_count = int(encoded["attention_mask"][0].sum())

    return {
        "label": distribution[0]["label"],
        "confidence": distribution[0]["confidence"],
        "distribution": distribution,
        "truncated": token_count >= MAX_LEN,
    }
