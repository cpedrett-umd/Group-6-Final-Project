"""Inference wrapper around the hyperopt-tuned DistilBERT classifier.

Loads the weights written by `modeling/train_best.py` and turns raw ad text
into a label plus a confidence over all tactic classes.

Three details keep this faithful to training:

* The tokenizer comes from `datasets/text_processing/ads_tokenizer/` -- the
  exact vocab that produced `tokenized_ads.pt` -- and uses the same
  `max_len=128`. A different tokenizer would silently yield garbage ids.
* The label names come from the checkpoint's own `id2label`, written by
  `AutoModelForSequenceClassification` at save time. Nothing here hardcodes
  class order, so re-training on a changed dataset cannot desynchronise the UI.
* Text longer than the window is scored in overlapping chunks rather than
  truncated. Every training example fit inside 128 subwords (99th percentile:
  61), so widening the window would hand the model a shape it has never been
  trained on. Chunking keeps each pass inside the distribution it learned.
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

# Content tokens per window, leaving room for [CLS] and [SEP].
WINDOW = MAX_LEN - 2

# Overlap between consecutive windows. A tactic phrase split across a boundary
# would be missed by both windows otherwise; 32 tokens is comfortably longer
# than any trigger phrase in the lexicon.
STRIDE = WINDOW - 32

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


def _windows(token_ids):
    """Split content token ids into overlapping windows.

    Returns a list of id lists, each at most WINDOW long. A short input yields
    exactly one window, so the common case costs nothing extra.
    """
    if len(token_ids) <= WINDOW:
        return [token_ids]

    chunks = []
    start = 0

    while start < len(token_ids):
        chunks.append(token_ids[start:start + WINDOW])

        if start + WINDOW >= len(token_ids):
            break

        start += STRIDE

    return chunks


def _score_windows(state, token_ids):
    """Run every window and pool the per-class probabilities.

    Pooling is per-class **maximum**, not mean. A tactic that appears only in
    the closing seconds of a long ad is still present in that ad; averaging
    would dilute it away. The consequence is that pooled scores no longer sum
    to 1 when there is more than one window -- they are per-class evidence,
    not a distribution -- so they are renormalised before being reported, and
    `windows` is returned so the caller can say how the number was reached.
    """
    tokenizer = state["tokenizer"]
    model = state["model"]

    cls_id = tokenizer.cls_token_id
    sep_id = tokenizer.sep_token_id
    pad_id = tokenizer.pad_token_id

    chunks = _windows(token_ids)

    pooled = None

    for chunk in chunks:
        ids = [cls_id] + chunk + [sep_id]
        attention = [1] * len(ids)

        padding = MAX_LEN - len(ids)

        if padding > 0:
            ids = ids + [pad_id] * padding
            attention = attention + [0] * padding

        input_ids = torch.tensor([ids], dtype=torch.long)
        attention_mask = torch.tensor([attention], dtype=torch.long)

        with torch.no_grad():
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

        probabilities = F.softmax(outputs.logits, dim=1)[0]

        pooled = (
            probabilities
            if pooled is None
            else torch.maximum(pooled, probabilities)
        )

    return pooled, len(chunks)


def predict(text: str) -> dict:
    """Classify one ad.

    Returns the argmax label, its confidence, and the full distribution sorted
    high to low. The distribution is what lets the panel rank secondary
    tactics rather than showing a bare top-1.
    """
    if not text or not text.strip():
        raise ValueError("No text to analyse.")

    state = _load()

    tokenizer = state["tokenizer"]
    id_to_label = state["id_to_label"]

    # No truncation here: the full input is windowed below rather than cut off.
    token_ids = tokenizer(
        text,
        add_special_tokens=False,
        truncation=False,
    )["input_ids"]

    pooled, window_count = _score_windows(state, token_ids)

    # Max-pooling across windows breaks the sum-to-one property, so restore it
    # before reporting. With a single window this is a no-op.
    pooled = pooled / pooled.sum()

    distribution = [
        {
            "label": id_to_label[index],
            "confidence": round(float(probability), 4),
        }
        for index, probability in enumerate(pooled.tolist())
    ]

    distribution.sort(key=lambda entry: -entry["confidence"])

    # An input longer than the window used to be silently cut off. It is now
    # scored in full, but the flag is kept: the UI still wants to say the ad
    # was long, and the test suite asserts it.
    exceeded_window = len(token_ids) + 2 > MAX_LEN

    return {
        "label": distribution[0]["label"],
        "confidence": distribution[0]["confidence"],
        "distribution": distribution,
        "truncated": exceeded_window,
        "windows": window_count,
        "token_count": len(token_ids) + 2,
    }